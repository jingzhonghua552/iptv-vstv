#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成精简 EPG：只保留 iptv.m3u 里实际用到的频道，体积从 ~49MB 降到 ~240KB。

数据源（Gitee 镜像，国内直连快，每 2 小时自动同步）：
  taks 号段  epgpw_cn / epgpw_hk / epgpw_tw.xml.gz   —— 覆盖大陆+港台主力频道
  erw  号段  erw.xml.gz                              —— 覆盖央视付费频道/地方台

两套号段合并输出，因为 m3u 里的 tvg-id 有的用 taks 号（如 545936），
有的只能用 erw 号（如 cctv风云音乐 -> 142）。

用法：
  python _merge_epg.py            # 正常生成
  python _merge_epg.py --check    # 只体检覆盖率，不写文件
"""
import gzip
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
M3U = os.path.join(ROOT, "iptv.m3u")
OUT_XML = os.path.join(ROOT, "epg.xml")
OUT_GZ = os.path.join(ROOT, "epg.xml.gz")

BASE = "https://gitee.com/taksssss/tv/raw/main/epg/"
TAKS_SOURCES = ["epgpw_cn.xml.gz", "epgpw_hk.xml.gz", "epgpw_tw.xml.gz"]
ERW_SOURCES = ["erw.xml.gz"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CH_RE = re.compile(r"<channel\b([^>]*)>(.*?)</channel>", re.S)
PR_RE = re.compile(r"<programme\b([^>]*)>(.*?)</programme>", re.S)


def fetch(name, timeout=180):
    url = BASE + name
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return gzip.decompress(r.read()).decode("utf-8", errors="replace")


def parse(text):
    """返回 (channels: {id: 内部XML}, programmes: {id: [(attrs, body)]})"""
    chans, progs = {}, {}
    for m in CH_RE.finditer(text):
        attrs, body = m.groups()
        cm = re.search(r'id="([^"]+)"', attrs)
        if cm:
            chans.setdefault(cm.group(1), body)
    for m in PR_RE.finditer(text):
        attrs, body = m.groups()
        cm = re.search(r'channel="([^"]+)"', attrs)
        if not cm:
            continue
        sm = re.search(r'start="([^"]+)"', attrs)
        if not sm:
            continue
        progs.setdefault(cm.group(1), []).append((attrs, body))
    return chans, progs


def main():
    check_only = "--check" in sys.argv

    with open(M3U, encoding="utf-8", errors="replace") as f:
        m3u = f.read()
    used = set(re.findall(r'tvg-id="([^"]+)"', m3u))
    numeric = {i for i in used if i.isdigit()}
    print(f"m3u 中 tvg-id: 共 {len(used)} 个，其中数字型 {len(numeric)} 个")

    taks_ch, taks_pr = {}, {}
    for name in TAKS_SOURCES:
        try:
            c, p = parse(fetch(name))
        except Exception as e:
            print(f"  跳过 {name}: {e}")
            continue
        for k, v in c.items():
            taks_ch.setdefault(k, v)
        for k, v in p.items():
            taks_pr.setdefault(k, []).extend(v)
        print(f"  {name}: channel {len(c)}, programme {sum(len(v) for v in p.values())}")

    erw_ch, erw_pr = {}, {}
    for name in ERW_SOURCES:
        try:
            c, p = parse(fetch(name))
        except Exception as e:
            print(f"  跳过 {name}: {e}")
            continue
        for k, v in c.items():
            erw_ch.setdefault(k, v)
        for k, v in p.items():
            erw_pr.setdefault(k, []).extend(v)
        print(f"  {name}: channel {len(c)}, programme {sum(len(v) for v in p.values())}")

    want_taks = set(numeric)
    want_erw = set()

    # 数字型 id 若 taks 里没有、但 erw 里有同名号段，也纳入（极少见）
    for cid in list(want_taks):
        if cid not in taks_ch and cid in erw_ch:
            want_erw.add(cid)

    if not taks_ch and not erw_ch:
        print("所有数据源均失败，保留现有 epg.xml 不改动")
        return 1

    ch_out, pr_out = [], []
    seen_c, seen_p = set(), set()

    def sort_key(x):
        return (0, int(x)) if x.isdigit() else (1, x)

    for cid in sorted(want_taks, key=sort_key):
        if cid in taks_ch and cid not in seen_c:
            seen_c.add(cid)
            ch_out.append(f'<channel id="{cid}">{taks_ch[cid]}</channel>')
    for cid in sorted(want_erw, key=sort_key):
        if cid in erw_ch and cid not in seen_c:
            seen_c.add(cid)
            ch_out.append(f'<channel id="{cid}">{erw_ch[cid]}</channel>')

    for cid in sorted(want_taks, key=sort_key):
        for attrs, body in taks_pr.get(cid, []):
            key = (cid, attrs)
            if key in seen_p:
                continue
            seen_p.add(key)
            pr_out.append(f"<programme {attrs}>{body}</programme>")
    for cid in sorted(want_erw, key=sort_key):
        for attrs, body in erw_pr.get(cid, []):
            key = (cid, attrs)
            if key in seen_p:
                continue
            seen_p.add(key)
            pr_out.append(f"<programme {attrs}>{body}</programme>")

    has_pr = {c for c, _ in seen_p}
    miss = sorted([c for c in numeric if c not in has_pr], key=sort_key)
    print()
    print(f"输出 channel {len(ch_out)} / programme {len(pr_out)}")
    print(f"数字型 tvg-id 有节目数据的: {len(numeric) - len(miss)} / {len(numeric)}")
    if miss:
        print(f"  无节目数据: {miss[:20]}")

    if check_only:
        return 0

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
           '<tv generator-info-name="merged-taks-erw">\n'
           + "\n".join(ch_out) + "\n"
           + "\n".join(pr_out) + "\n"
           + "</tv>\n")
    with open(OUT_XML, "w", encoding="utf-8") as f:
        f.write(xml)
    with gzip.open(OUT_GZ, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))
    print(f"  {OUT_XML}  {os.path.getsize(OUT_XML)} bytes")
    print(f"  {OUT_GZ}  {os.path.getsize(OUT_GZ)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
