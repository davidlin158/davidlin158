# 体育直播源工具包

按 **美国 / 加拿大 / 欧洲** 过滤体育频道，生成可直接导入播放器的 M3U 播放列表。

## 先说清楚边界

这套工具**只收录合法免费频道**，不提供各大联赛付费频道的破解源。

各大联赛的核心转播权都在付费方手里 —— NFL 在 ESPN/Amazon，NBA 在 ESPN/NBC/Amazon，
英超在 Sky/TNT，欧冠在 Paramount+/TNT，西甲在 Movistar/DAZN。网上流传的这些频道地址
基本都是未授权盗播，本工具的屏蔽表默认把它们全部剔除（`catalog/blocklist.json`，85 条规则）。

**能合法免费看到的是这些**，而且内容不少：

| 类型 | 例子 | 能看到什么 |
|---|---|---|
| 官方免费台 | Red Bull TV、FIFA+、Olympics Channel | 全球无区域限制，自有赛事直播 |
| 美国 FAST 频道 | beIN SPORTS XTRA、Stadium、CBS Sports HQ、NFL Channel | 法甲/西甲部分场次、NCAA 直播、集锦资讯 |
| 欧洲免费开路台 | TVP Sport、Rai Sport、Teledeporte、L'Équipe、M4 Sport、ČT Sport、TRT Spor | 波甲/匈甲/意丙/法乙直播，环法环西全程，排球冰球，欧洲杯世界杯 |

完整对照见 `catalog/leagues.json`（25 个联赛 → 免费/付费分别在哪看）。

## 用法

需要 Python 3.8+，无第三方依赖。

```bash
# 1) 生成播放列表（联网从公开频道库拉实时地址）
python3 build_playlist.py --region na-eu          # 美加欧，默认
python3 build_playlist.py --region us             # 只要美国
python3 build_playlist.py --countries GB,DE,ES    # 指定国家
python3 build_playlist.py --curated-only          # 离线，只用本地免费目录

# 2) 探活，剔除死链（重要 —— 公开源普遍有大量失效地址）
python3 check_streams.py --playlist out/sports.m3u --prune out/sports.live.m3u

# 3) 把 out/sports.live.m3u 拖进 VLC / IINA / PotPlayer / TiviMate
```

**必须跑第 2 步。** 任何公开体育源列表都有很高的自然死亡率，不探活拿到的就是一堆转圈。
探活会输出存活率统计和 `*.report.json` 明细。建议加进 cron 定期重跑。

## 文件

| 文件 | 作用 |
|---|---|
| `build_playlist.py` | 生成器：拉取 → 按体育分类+国家过滤 → 套屏蔽表 → 去重取最高画质 → 出 M3U |
| `check_streams.py` | 探活：并发拉流首包，校验是否为有效 HLS/DASH，剔除死链 |
| `test_filters.py` | 回归测试：合成数据验证付费频道不会泄漏 |
| `catalog/free-sports.json` | 44 个合法免费频道（含官网、地域限制、联赛标签） |
| `catalog/leagues.json` | 25 个联赛的转播权对照 |
| `catalog/blocklist.json` | 付费频道屏蔽规则 |
| `player/index.html` | 网页播放器（hls.js） |
| `out/` | 生成结果 |

## 已知限制

- **地域锁**：欧洲公共台绝大多数只在本国 IP 可看，`catalog/free-sports.json` 的 `geo` 字段标了范围。
  `worldwide` 的目前只有 Red Bull TV 和 TRT Spor。
- **网页播放器受 CORS 限制**：不少电视台不允许跨域取流，网页里失败但 VLC 里正常。桌面播放器更可靠。
- **部分免费频道拿不到直连地址**：FIFA+、CBC、BBC/ITV 等用 DRM 或动态令牌，只能走官网/App。
  生成器会把这些列在"未解析"里并附官网链接。
- **本仓库不附带可用的成品列表**：地址会失效，跑一次生成器拿实时的比抄一份死名单有用。

## 合规

`catalog/` 里的频道均为运营方自己公开推流的免费频道。工具不解密、不绕过地域限制、
不访问付费内容。请遵守所在地法律与各平台服务条款。
