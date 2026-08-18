#!/usr/bin/env python3
"""播放列表探活工具。

并发请求每条流,验证是否真的能拉到 HLS 清单 / 媒体数据,输出存活报告,
并可写出一份只含存活频道的干净播放列表。

  python3 check_streams.py --playlist out/sports.m3u
  python3 check_streams.py --playlist out/sports.m3u --prune out/sports.live.m3u
  python3 check_streams.py --playlist out/sports.m3u --workers 24 --timeout 12
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
EXTINF = re.compile(r'#EXTINF:-?\d+\s*(?P<attrs>[^,]*),(?P<name>.*)')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(path):
    """解析 M3U,保留 tvg 属性与 VLC 请求头选项。"""
    entries, pending = [], None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or (line.startswith("#") and not line.startswith(("#EXTINF", "#EXTVLCOPT"))):
                continue
            m = EXTINF.match(line)
            if m:
                attrs = dict(ATTR.findall(m.group("attrs")))
                pending = {"name": m.group("name").strip(), "extinf": line,
                           "group": attrs.get("group-title", ""), "id": attrs.get("tvg-id", ""),
                           "opts": [], "user_agent": "", "referrer": ""}
                continue
            if line.startswith("#EXTVLCOPT") and pending:
                pending["opts"].append(line)
                if "http-user-agent=" in line:
                    pending["user_agent"] = line.split("http-user-agent=", 1)[1]
                elif "http-referrer=" in line:
                    pending["referrer"] = line.split("http-referrer=", 1)[1]
                continue
            if pending:
                pending["url"] = line
                entries.append(pending)
                pending = None
    return entries


def probe(entry, timeout, read_bytes=2048):
    """拉取流的前若干字节,判断是否为有效 HLS/媒体响应。"""
    url = entry["url"]
    headers = {"User-Agent": entry.get("user_agent") or UA, "Accept": "*/*"}
    if entry.get("referrer"):
        headers["Referer"] = entry["referrer"]

    started = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            body = resp.read(read_bytes)
    except urllib.error.HTTPError as exc:
        return {**entry, "ok": False, "status": exc.code, "reason": f"HTTP {exc.code}",
                "ms": int((time.time() - started) * 1000)}
    except Exception as exc:                                    # noqa: BLE001 - 网络异常种类多
        reason = type(exc).__name__
        detail = str(exc)[:70]
        return {**entry, "ok": False, "status": 0,
                "reason": f"{reason}: {detail}" if detail else reason,
                "ms": int((time.time() - started) * 1000)}

    ms = int((time.time() - started) * 1000)
    text = body.decode("utf-8", "ignore")

    if "#EXTM3U" in text:
        variants = len(re.findall(r"#EXT-X-STREAM-INF", text))
        segs = len(re.findall(r"#EXTINF", text))
        kind = "master" if variants else ("media" if segs else "m3u8")
        return {**entry, "ok": True, "status": code, "reason": f"HLS/{kind}", "ms": ms}
    if "mpegurl" in ctype or url.split("?")[0].endswith(".m3u8"):
        return {**entry, "ok": False, "status": code, "reason": "响应不是有效 HLS 清单", "ms": ms}
    if ctype.startswith("video/") or ctype.startswith("audio/") or "mp2t" in ctype or "octet-stream" in ctype:
        return {**entry, "ok": True, "status": code, "reason": f"stream/{ctype.split(';')[0]}", "ms": ms}
    if "dash+xml" in ctype or "<MPD" in text:
        return {**entry, "ok": True, "status": code, "reason": "MPEG-DASH", "ms": ms}
    if "text/html" in ctype:
        return {**entry, "ok": False, "status": code, "reason": "返回 HTML(多为拦截页/已下线)", "ms": ms}
    return {**entry, "ok": False, "status": code, "reason": f"未知响应 {ctype or '无类型'}", "ms": ms}


def write_m3u(results, path):
    lines = ["#EXTM3U", f"# 探活通过 {len(results)} 个频道 · {time.strftime('%Y-%m-%d %H:%M:%S %z')}", ""]
    for r in results:
        lines.append(r["extinf"])
        lines.extend(r["opts"])
        lines.append(r["url"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="播放列表探活 / 剔除死链")
    ap.add_argument("--playlist", required=True, help="待检测的 M3U 文件")
    ap.add_argument("--prune", help="把存活频道写入这个新 M3U")
    ap.add_argument("--report", help="探活报告 JSON 路径")
    ap.add_argument("--workers", type=int, default=16, help="并发数 (默认 16)")
    ap.add_argument("--timeout", type=int, default=10, help="单条超时秒数 (默认 10)")
    args = ap.parse_args()

    entries = parse_m3u(args.playlist)
    if not entries:
        raise SystemExit(f"{args.playlist} 里没有解析到频道")
    print(f"共 {len(entries)} 个频道,并发 {args.workers},超时 {args.timeout}s\n", file=sys.stderr)

    results = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, e, args.timeout): e for e in entries}
        for done, fut in enumerate(cf.as_completed(futures), 1):
            r = fut.result()
            results.append(r)
            mark = "✓" if r["ok"] else "✗"
            print(f"[{done:>4}/{len(entries)}] {mark} {r['name'][:34]:<34} {r['reason'][:44]:<44} {r['ms']:>5}ms",
                  file=sys.stderr)

    alive = [r for r in results if r["ok"]]
    alive.sort(key=lambda r: (r["group"], r["name"].lower()))
    dead = [r for r in results if not r["ok"]]

    print(f"\n存活 {len(alive)} / {len(results)}  ({len(alive)*100//max(len(results),1)}%)", file=sys.stderr)
    if dead:
        buckets = {}
        for d in dead:
            buckets[d["reason"].split(":")[0]] = buckets.get(d["reason"].split(":")[0], 0) + 1
        print("失败原因分布: " + ", ".join(f"{k}×{v}" for k, v in
                                            sorted(buckets.items(), key=lambda kv: -kv[1])), file=sys.stderr)

    if args.prune:
        write_m3u(alive, args.prune)
        print(f"干净列表 -> {args.prune}", file=sys.stderr)

    report = args.report or (os.path.splitext(args.playlist)[0] + ".report.json")
    with open(report, "w", encoding="utf-8") as fh:
        json.dump({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   "total": len(results), "alive": len(alive),
                   "results": [{k: v for k, v in r.items() if k != "opts"} for r in results]},
                  fh, ensure_ascii=False, indent=2)
    print(f"报告 -> {report}", file=sys.stderr)
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
