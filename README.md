# IPTV 直播源维护工具

本地手动运行的 IPTV 源检测、修复、发布工具。不需要 24 小时开机，
只在**想更新订阅的时候**手动跑一次。

## 当前状态

| 项 | 值 |
|---|---|
| 订阅地址 | `https://raw.githubusercontent.com/jingzhonghua552/iptv-vstv/main/iptv.m3u` |
| 节目单 | 同目录 `epg.xml.gz`（152→144 频道，自建精简版） |
| 频道 / 源 | 148 个唯一频道 / 310 条源 |
| 缺台标 | 0 |
| 仓库 | GitHub `jingzhonghua552/iptv-vstv` (main) |

> ⚠️ **不要用 jsdelivr 的 `@main` 当订阅地址**。三个 CDN 节点各自缓存不同
> 历史版本，`?v=` / `?ts=` 参数完全穿不透，会拿到旧文件。
> 用 `raw.githubusercontent.com`，commit 后约 5 分钟生效。
> 要绝对稳定就用 `@<commit-sha>`。

---

## 四个工具

四个脚本各管一件事，可以单独跑，也可以按顺序串起来。

### 1. `_scan.py` — 抽帧看台标 / 抓串台 / 清废源

把每个源真的解出画面来看。**HTTP 200 不代表能看，也不代表频道对**，
只有看到画面才知道。

```powershell
python _scan.py --list                        # 只列频道和源，不抽帧
python _scan.py                               # 全表抽帧 + 生成 report.html
python _scan.py --filter 台球 高尔夫           # 只查指定频道
python _scan.py --filter 海峡 --shots 2        # 每源抽 2 帧
python _scan.py --no-grab                     # 复用已有帧，只重算分析
python _scan.py --fix --drop-empty            # 删除抽帧失败的源
```

产物：`frames/*.jpg`（每源多帧）+ `report.html`（按频道分组的画面网格）。

自动判定：

| 标记 | 判据 |
|---|---|
| 抽帧失败 | 没解出帧，或帧文件 < 2KB |
| 黑屏 | 平均亮度 < 18 |
| 纯色 | 像素标准差 < 9 |
| **串台嫌疑** | 同一频道多个源之间 dHash 汉明距离 > 12 |

**串台**是重点：一个频道挂了 3 个源，如果某个源画面和其他源完全不同，
说明它播的不是这个频道。`report.html` 里并排显示，一眼能看出来。

> 已用这个工具抓到过的真实案例：
> - 「CCTV 高尔夫·网球」线路 1 播的是 CCTV 兵器科技
> - 「海峡卫视」线路 1 播的是厦门卫视
> - 「中天综合台」的源是「中天娛樂HD」
> - 「广州综合」线路 2 是「GZ 新闻」
> - 「中天娱乐台」线路 1 是「Relaxing piano music」静态图配轻音乐（填充片）

### 2. `_adfix.py` — 去广告 / 清令牌源

```powershell
python _adfix.py                              # 体检（不改文件）
python _adfix.py --probe                      # 额外做 302 探测
python _adfix.py --probe --apply              # 探测 + 写回
python _adfix.py --probe --filter 海峡 农林    # 只查指定频道
```

要治的四种"广告"：

1. **令牌型源**：`...?msisdn=..&timestamp=..&SecurityKey=..`
   令牌有过期时间，过期后不报错，直接 HTTP 660 / 0 字节。
2. **302 跳转到令牌源**：源看着干净，一请求就跳到 migu 长地址。
   光看 m3u 发现不了，必须 `--probe`。
3. **广告占位片**：播放列表里直接放广告 mp4，路径常含 `aad` / `ad`。
4. **已知失效代理**：`mgtv.ottiptv.cc`、`mursor.ottiptv.cc`（长期 000）。

判定分两级，**不会误删能用的源**：

- `bad` → 处理（静态令牌 / 广告片 / 失效代理）
- `warn` → 只提示（**动态** 302 跳转，每次请求都换新令牌，只要跳转服务活着就能用）

### 3. `_logo.py` — 台标自动补齐

```powershell
python _logo.py              # 体检，列出缺台标的频道和匹配建议
python _logo.py --apply      # 写回 iptv.m3u
python _logo.py --fetch      # 强制刷新台标库索引（3266 张）
```

匹配优先级：`ALIAS` 手工别名 → 归一化精确 → 归一化包含。
归一化会去空格、去 `HD/高清/4K` 后缀、`CCTV`→`央视`。

补不到的会列出来，把对应关系加进脚本里的 `ALIAS` 字典即可。

### 4. `_merge_epg.py` — 生成精简 EPG

```powershell
python _merge_epg.py           # 生成 epg.xml + epg.xml.gz
python _merge_epg.py --check   # 只体检不写文件
```

从 Gitee 镜像拉 4 个 EPG 变体，按 m3u 里的 `tvg-id` 过滤合并。
产出约 260KB（对比 epg.pw 全量 49.5MB，压缩到 1/190）。

数据源：

```
https://gitee.com/taksssss/tv/raw/main/epg/epgpw_cn.xml.gz   712 频道
https://gitee.com/taksssss/tv/raw/main/epg/epgpw_hk.xml.gz   230 频道
https://gitee.com/taksssss/tv/raw/main/epg/epgpw_tw.xml.gz   519 频道
https://gitee.com/taksssss/tv/raw/main/epg/erw.xml.gz        512 频道
```

---

## 标准工作流

```powershell
# 1. 抽帧体检：看画面、抓串台、找废源
python _scan.py

# 2. 去广告体检：抓令牌源和广告片
python _adfix.py --probe

# 3. 按报告手工确认后执行清理
python _scan.py --fix --drop-empty
python _adfix.py --probe --apply

# 4. 补台标
python _logo.py --apply

# 5. 重建 EPG
python _merge_epg.py

# 6. 发布
python _gh_put.py iptv.m3u epg.xml.gz --msg "chore: 更新"
```

每一步写回前都会留 `.bak_*` 备份。

---

## 状态码怎么读（决定该不该删台）

| 状态 | 含义 | 该删吗 |
|---|---|---|
| **502** | 服务器活着，上游源挂了 | ❌ 多为临时，会自行恢复 |
| **567** | 腾讯云 EdgeOne 按 IP/地域拦截 | ❌ 你本地可能不被拦 |
| **000** | 连不上（超时/拒绝） | ⚠️ 可能地域限制 |
| **660** | 咪咕令牌校验失败 | ✅ 令牌废了 |
| **画面是报错页/填充片** | 内容本身废了 | ✅ 不可恢复 |

最后一条最关键：抽帧抽到 D-BOX 机顶盒的 `E07 Checking Smartcard`、
或者「Relaxing piano music」这种静态图配音乐，说明**视频流本身就是废的**，
换任何网络、任何设备都一样，可以放心删。

---

## 文件清单

| 文件 | 作用 |
|---|---|
| `iptv.m3u` | 订阅文件（发布物） |
| `epg.xml` / `epg.xml.gz` | 精简节目单（发布物） |
| `_scan.py` | 抽帧 / 台标 / 串台 / 废源 |
| `_adfix.py` | 去广告 / 清令牌源 |
| `_logo.py` | 台标自动补齐 |
| `_merge_epg.py` | 生成精简 EPG |
| `_gh_put.py` | 上传到 GitHub（token 从注册表 `HKCU:\Environment\GITHUB_TOKEN` 读） |
| `_tvg_id_map.py` | tvg-id 映射表（中文自造 id / 数字 id 重映射） |
| `report.html` | 抽帧检测报告（自动生成） |
| `frames/` | 抽帧图片（自动生成） |
| `.github/workflows/update_epg.yml` | 每天 03:17 UTC 自动重建 EPG |

---

## 台标

从 `taksssss/tv` 仓库通过 jsdelivr 加载：

```
https://gcore.jsdelivr.net/gh/taksssss/tv/icon/<频道名>.png
```

中文名直接拼，**不要做百分号编码**——表里其余台标都是原文，保持一致。
`testingcf.jsdelivr.net` 可作为备用节点。

---

## 注意事项

- **不要设置定时任务**（EPG 的 Actions 除外），全部手动运行
- 家用宽带并发不要超过 5，容易触发源站限流
- `173.208.212.130:8181` 线路优先排序（全国通用）
- `38.75.136.137:98/gslb/dsdqpub/` 是央视付费频道源，命名是拼音缩写：
  `gefwq`=高尔夫网球、`ystq`=央视台球、`gfjs`=国防军事。
  **`gfjs` 不是高尔夫**，曾经被错挂到高尔夫网球下面。
