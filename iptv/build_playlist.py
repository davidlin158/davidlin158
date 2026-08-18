#!/usr/bin/env python3
"""体育频道 M3U 播放列表生成器。

从公开频道库(iptv-org API)拉取实时数据,按 体育分类 + 国家集 过滤,
剔除付费订阅频道(catalog/blocklist.json),合并本地合法免费频道目录
(catalog/free-sports.json),输出 M3U 与 JSON 边车文件。

只用标准库,无第三方依赖。

  python3 build_playlist.py --region na-eu          # 美加欧全部体育频道
  python3 build_playlist.py --region us --out us.m3u
  python3 build_playlist.py --curated-only          # 只用本地免费频道目录
  python3 build_playlist.py --region eu --refresh   # 强制刷新缓存
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://iptv-org.github.io/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, ".cache")
CATALOG_DIR = os.path.join(HERE, "catalog")
OUT_DIR = os.path.join(HERE, "out")

EU = ["GB", "IE", "FR", "DE", "IT", "ES", "PT", "NL", "BE", "LU", "CH", "AT",
      "PL", "CZ", "SK", "HU", "RO", "BG", "GR", "TR", "SE", "NO", "DK", "FI",
      "IS", "HR", "RS", "SI", "BA", "ME", "MK", "AL", "UA", "LT", "LV", "EE",
      "CY", "MT", "AD", "MC", "SM"]

REGIONS = {
    "us": ["US"],
    "ca": ["CA"],
    "na": ["US", "CA"],
    "eu": EU,
    "na-eu": ["US", "CA"] + EU,
    "all": ["US", "CA"] + EU + ["INT"],
}


def log(msg):
    print(msg, file=sys.stderr)


def fetch_json(name, ttl=21600, refresh=False, timeout=90):
    """抓 API 并缓存。网络不可用时回退到过期缓存。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, name)
    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl
    if fresh and not refresh:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    req = urllib.request.Request(f"{API}/{name}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw)
        with open(path, "wb") as fh:
            fh.write(raw)
        log(f"  [fetch] {name}: {len(data)} 条")
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        if os.path.exists(path):
            log(f"  [warn] {name} 拉取失败({exc}),使用本地缓存")
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        log(f"  [error] {name} 拉取失败且无缓存: {exc}")
        raise SystemExit(
            "无法访问 iptv-org API。请检查网络/代理后重试,或用 --curated-only 仅生成本地免费频道目录。"
        )


def load_catalog(name):
    with open(os.path.join(CATALOG_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


def build_blocker():
    patterns = load_catalog("blocklist.json")["patterns"]
    compiled = [re.compile(p, re.I) for p in patterns]

    def blocked(*fields):
        text = " ".join(f for f in fields if f)
        return any(rx.search(text) for rx in compiled)

    return blocked


QUALITY_RANK = {"2160p": 5, "1440p": 4, "1080p": 3, "720p": 2, "576p": 1, "480p": 1, "360p": 0, "240p": 0}


def quality_score(stream):
    q = (stream.get("quality") or "").lower()
    return QUALITY_RANK.get(q, 1)


def collect_from_api(countries, refresh, blocked, include_unknown_country):
    channels = fetch_json("channels.json", refresh=refresh)
    streams = fetch_json("streams.json", refresh=refresh)
    try:
        logos = fetch_json("logos.json", refresh=refresh)
    except SystemExit:
        logos = []

    logo_by_channel = {}
    for item in logos:
        cid = item.get("channel")
        if cid and cid not in logo_by_channel and item.get("url"):
            logo_by_channel[cid] = item["url"]

    wanted = set(countries)
    chan_by_id = {}
    for ch in channels:
        if ch.get("closed") or ch.get("is_nsfw"):
            continue
        cats = [c.lower() for c in (ch.get("categories") or [])]
        if "sports" not in cats:
            continue
        country = ch.get("country")
        if country not in wanted:
            if not (include_unknown_country and not country):
                continue
        if blocked(ch.get("name"), ch.get("network"), " ".join(ch.get("alt_names") or [])):
            continue
        chan_by_id[ch["id"]] = ch

    # 每个频道取质量最高的一条流
    best = {}
    for st in streams:
        cid = st.get("channel")
        if not cid or cid not in chan_by_id:
            continue
        url = st.get("url")
        if not url or not url.startswith(("http://", "https://")):
            continue
        if blocked(st.get("title")):
            continue
        cur = best.get(cid)
        if cur is None or quality_score(st) > quality_score(cur):
            best[cid] = st

    entries = []
    for cid, st in best.items():
        ch = chan_by_id[cid]
        entries.append({
            "id": cid,
            "name": ch.get("name") or cid,
            "country": ch.get("country") or "INT",
            "group": ch.get("country") or "INT",
            "logo": logo_by_channel.get(cid, ""),
            "url": st["url"],
            "referrer": st.get("referrer") or "",
            "user_agent": st.get("user_agent") or "",
            "quality": st.get("quality") or "",
            "source": "iptv-org",
            "official": ch.get("website") or "",
        })
    return entries


def collect_curated(countries, resolved_by_id, blocked):
    """本地免费频道目录:优先用直连地址,否则按 iptv_org_id 解析。"""
    catalog = load_catalog("free-sports.json")["channels"]
    wanted = set(countries)
    entries = []
    unresolved = []
    for ch in catalog:
        if ch["country"] not in wanted and ch["country"] != "INT":
            continue
        if blocked(ch["name"]):
            # 两份目录打架时以屏蔽表为准,宁可少收也不误收付费频道
            log(f"  [skip] 免费目录里的 {ch['name']} 命中付费屏蔽规则,已跳过")
            continue
        url, source, logo = ch.get("stream"), "curated", ""
        if not url and ch.get("iptv_org_id"):
            hit = resolved_by_id.get(ch["iptv_org_id"])
            if hit:
                url, source, logo = hit["url"], "curated+iptv-org", hit.get("logo", "")
        if not url:
            unresolved.append(ch)
            continue
        entries.append({
            "id": ch["id"],
            "name": ch["name"],
            "country": ch["country"],
            "group": ch["group"],
            "logo": logo,
            "url": url,
            "referrer": "",
            "user_agent": "",
            "quality": "",
            "source": source,
            "official": ch.get("official", ""),
            "license": ch.get("license", ""),
            "geo": ch.get("geo", ""),
            "leagues": ch.get("leagues", []),
            "note": ch.get("note", ""),
        })
    return entries, unresolved


def write_m3u(entries, path):
    lines = ['#EXTM3U x-tvg-url=""', "# 由 iptv/build_playlist.py 生成 —— 仅收录公开可访问的合法免费频道",
             f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S %z')}   频道数: {len(entries)}", ""]
    for e in entries:
        attrs = f'tvg-id="{e["id"]}" tvg-name="{e["name"]}"'
        if e.get("logo"):
            attrs += f' tvg-logo="{e["logo"]}"'
        attrs += f' group-title="{e["group"]}"'
        lines.append(f'#EXTINF:-1 {attrs},{e["name"]}')
        if e.get("user_agent"):
            lines.append(f'#EXTVLCOPT:http-user-agent={e["user_agent"]}')
        if e.get("referrer"):
            lines.append(f'#EXTVLCOPT:http-referrer={e["referrer"]}')
        lines.append(e["url"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="生成合法免费体育频道 M3U 播放列表")
    ap.add_argument("--region", default="na-eu", choices=sorted(REGIONS), help="国家集预设 (默认 na-eu)")
    ap.add_argument("--countries", help="覆盖预设,逗号分隔的 ISO 国家码,如 US,GB,DE")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "sports.m3u"), help="输出 M3U 路径")
    ap.add_argument("--curated-only", action="store_true", help="只用本地免费频道目录,不访问 API")
    ap.add_argument("--refresh", action="store_true", help="强制刷新 API 缓存")
    ap.add_argument("--limit", type=int, default=0, help="最多输出多少条(0=不限)")
    args = ap.parse_args()

    countries = [c.strip().upper() for c in args.countries.split(",")] if args.countries else REGIONS[args.region]
    blocked = build_blocker()
    log(f"目标国家: {len(countries)} 个 · 屏蔽规则已加载")

    api_entries = []
    if not args.curated_only:
        api_entries = collect_from_api(countries, args.refresh, blocked, include_unknown_country=False)
        log(f"公开库命中体育频道: {len(api_entries)}")

    resolved = {e["id"]: e for e in api_entries}
    curated, unresolved = collect_curated(countries, resolved, blocked)
    log(f"本地免费目录命中: {len(curated)} (未解析到地址: {len(unresolved)})")

    merged = {}
    for e in api_entries:
        merged[e["url"]] = e
    for e in curated:                      # 本地目录优先覆盖(带 group/note 等元数据)
        merged[e["url"]] = e

    entries = sorted(merged.values(), key=lambda e: (e["group"], e["name"].lower()))
    if args.limit:
        entries = entries[:args.limit]

    write_m3u(entries, args.out)
    sidecar = os.path.splitext(args.out)[0] + ".json"
    with open(sidecar, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   "countries": countries, "count": len(entries),
                   "entries": entries,
                   "unresolved": [{"name": c["name"], "official": c.get("official", ""),
                                   "note": c.get("note", "")} for c in unresolved]},
                  fh, ensure_ascii=False, indent=2)

    log(f"\n已写出 {len(entries)} 个频道 -> {args.out}")
    log(f"边车数据 -> {sidecar}")
    if unresolved:
        log(f"\n以下 {len(unresolved)} 个免费频道没有可直连地址(需用官网/App 观看):")
        for c in unresolved[:12]:
            log(f"  · {c['name']:<28} {c.get('official','')}")
        if len(unresolved) > 12:
            log(f"  … 其余 {len(unresolved)-12} 个见边车 JSON")
    log("\n下一步: python3 check_streams.py --playlist " + args.out + "   # 探活并剔除死链")


if __name__ == "__main__":
    main()
