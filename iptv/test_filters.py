#!/usr/bin/env python3
"""过滤管线回归测试:用合成数据验证付费频道不会泄漏进播放列表。

  python3 test_filters.py
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_playlist as bp                                        # noqa: E402

CHANNELS = [
    {"id": "ESPN.us", "name": "ESPN", "country": "US", "categories": ["sports"], "network": "ESPN Inc."},
    {"id": "SkySportsMainEvent.uk", "name": "Sky Sports Main Event", "country": "GB", "categories": ["sports"]},
    {"id": "beINSports1.fr", "name": "beIN Sports 1", "country": "FR", "categories": ["sports"]},
    {"id": "beINSportsXTRA.us", "name": "beIN SPORTS XTRA", "country": "US", "categories": ["sports"]},
    {"id": "Stadium.us", "name": "Stadium", "country": "US", "categories": ["sports"]},
    {"id": "Sport1.de", "name": "Sport1", "country": "DE", "categories": ["sports"]},
    {"id": "DAZN1.de", "name": "DAZN 1", "country": "DE", "categories": ["sports"]},
    {"id": "Eurosport1.de", "name": "Eurosport 1", "country": "DE", "categories": ["sports"]},
    {"id": "TVPSport.pl", "name": "TVP Sport", "country": "PL", "categories": ["sports"]},
    {"id": "CNN.us", "name": "CNN", "country": "US", "categories": ["news"]},
    {"id": "OldSports.us", "name": "Dead Sports Net", "country": "US", "categories": ["sports"],
     "closed": "2020-01-01"},
    {"id": "Adult.us", "name": "XXX Sports", "country": "US", "categories": ["sports"], "is_nsfw": True},
    {"id": "Sportsnet1.ca", "name": "Sportsnet One", "country": "CA", "categories": ["sports"]},
    {"id": "CBCSportsX.ca", "name": "CBC Sports Extra", "country": "CA", "categories": ["sports"]},
    {"id": "AsiaSport.jp", "name": "Japan Sports", "country": "JP", "categories": ["sports"]},
]
STREAMS = [
    {"channel": "ESPN.us", "url": "http://pirate.example/espn.m3u8", "quality": "1080p"},
    {"channel": "SkySportsMainEvent.uk", "url": "http://pirate.example/sky.m3u8", "quality": "1080p"},
    {"channel": "beINSports1.fr", "url": "http://pirate.example/bein1.m3u8", "quality": "720p"},
    {"channel": "beINSportsXTRA.us", "url": "https://legit.example/xtra.m3u8", "quality": "720p"},
    {"channel": "Stadium.us", "url": "https://legit.example/stadium-720.m3u8", "quality": "720p"},
    {"channel": "Stadium.us", "url": "https://legit.example/stadium-1080.m3u8", "quality": "1080p"},
    {"channel": "Sport1.de", "url": "https://legit.example/sport1.m3u8", "quality": "1080p"},
    {"channel": "DAZN1.de", "url": "http://pirate.example/dazn.m3u8", "quality": "1080p"},
    {"channel": "Eurosport1.de", "url": "http://pirate.example/euro.m3u8", "quality": "1080p"},
    {"channel": "TVPSport.pl", "url": "https://legit.example/tvpsport.m3u8", "quality": "1080p"},
    {"channel": "CNN.us", "url": "https://legit.example/cnn.m3u8", "quality": "1080p"},
    {"channel": "OldSports.us", "url": "https://legit.example/old.m3u8", "quality": "480p"},
    {"channel": "Adult.us", "url": "https://legit.example/xxx.m3u8", "quality": "480p"},
    {"channel": "Sportsnet1.ca", "url": "http://pirate.example/sn1.m3u8", "quality": "1080p"},
    {"channel": "CBCSportsX.ca", "url": "https://legit.example/cbcx.m3u8", "quality": "1080p"},
    {"channel": "AsiaSport.jp", "url": "https://legit.example/jp.m3u8", "quality": "1080p"},
    {"channel": "Stadium.us", "url": "ftp://bad.example/nope", "quality": "1080p"},
]
LOGOS = [{"channel": "Stadium.us", "url": "https://logo.example/stadium.png"}]

MUST_BLOCK = ["ESPN", "Sky Sports Main Event", "beIN Sports 1", "DAZN 1", "Eurosport 1",
              "Sportsnet One", "CNN", "Dead Sports Net", "XXX Sports", "Japan Sports"]
MUST_PASS = ["beIN SPORTS XTRA", "Stadium", "Sport1", "TVP Sport", "CBC Sports Extra"]


def run():
    tmp = tempfile.mkdtemp(prefix="iptv-test-")
    bp.CACHE_DIR = tmp
    for name, payload in (("channels.json", CHANNELS), ("streams.json", STREAMS), ("logos.json", LOGOS)):
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    try:
        blocked = bp.build_blocker()
        countries = bp.REGIONS["na-eu"]
        api = bp.collect_from_api(countries, refresh=False, blocked=blocked, include_unknown_country=False)
        curated, _ = bp.collect_curated(countries, {e["id"]: e for e in api}, blocked)

        merged = {e["url"]: e for e in api}
        merged.update({e["url"]: e for e in curated})
        by_name = {e["name"]: e for e in merged.values()}

        failures = []
        for name in MUST_BLOCK:
            if name in by_name:
                failures.append(f"付费/无关频道泄漏: {name}")
        for name in MUST_PASS:
            if name not in by_name:
                failures.append(f"合法免费频道缺失: {name}")
        if any("pirate.example" in u for u in merged):
            failures.append("盗播源地址进入结果")
        stadium = by_name.get("Stadium")
        if stadium:
            if "1080" not in stadium["url"]:
                failures.append(f"未选中最高画质: {stadium['url']}")
            if not stadium.get("logo"):
                failures.append("curated 条目未继承 logo")
            if stadium.get("license") != "fast":
                failures.append("curated 元数据未合并")
        if any(e["url"].startswith("ftp://") for e in merged.values()):
            failures.append("非 HTTP 协议地址未被过滤")

        for f in failures:
            print("✗ " + f)
        if failures:
            print(f"\n{len(failures)} 项失败")
            return 1
        print(f"✓ 全部通过 —— 屏蔽 {len(MUST_BLOCK)} 项 / 放行 {len(MUST_PASS)} 项 / 结果 {len(merged)} 个频道")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(run())
