#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉取 taksssss/tv 的 epg.pw 国内/港台三变体，合并并按 iptv.m3u 的 tvg-id 过滤，
输出 epg.xml 与 epg.xml.gz。

数据源（每 2 小时自动同步，Gitee 国内直连快）：
  https://gitee.com/taksssss/tv/raw/main/epg/epgpw_cn.xml.gz
  https://gitee.com/taksssss/tv/raw/main/epg/epgpw_hk.xml.gz
  https://gitee.com/taksssss/tv/raw/main/epg/epgpw_tw.xml.gz

输出仅保留 iptv.m3u 中实际使用的 tvg-id，体积从 ~49MB 降到几十 KB。
"""
import gzip
import io
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
M3U = os.path.join(ROOT, "iptv.m3u")
OUT_XML = os.path.join(ROOT, "epg.xml")
OUT_GZ = os.path.join(ROOT, "epg.xml.gz")

SOURCES = [
    "https://gitee.com/taksssss/tv/raw/main/epg/epgpw_cn.xml.gz",
    "https://gitee.com/taksssss/tv/raw/main/epg/epgpw_hk.xml.gz",
    "https://gitee.com/taksssss/tv/raw/main/epg/epgpw_tw.xml.gz",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def fetch(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def wanted_ids():
    with open(M3U, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    ids, out = re.findall(r'tvg-id="([^"]*)"', txt), []
    for i in ids:
        if i not in out:
            out.append(i)
    return set(out)


CH_RE = re.compile(r"<channel\b[^>]*>.*?</channel>|<channel\b[^>]*/>", re.S)
PR_RE = re.compile(r"<programme\b[^>]*>.*?</programme>|<programme\b[^>]*/>", re.S)


def extract(text, want):
    chans, progs, seen_ch, seen_pr = [], [], set(), set()
    for m in CH_RE.finditer(text):
        blk = m.group(0)
        cm = re.search(r'<channel id="([^"]+)"', blk)
        if not cm:
            continue
        cid = cm.group(1)
        if cid in want and cid not in seen_ch:
            seen_ch.add(cid)
            chans.append(blk)
    for m in PR_RE.finditer(text):
        blk = m.group(0)
        pm = re.search(r'channel="([^"]+)"', blk)
        if not pm:
            continue
        cid = pm.group(1)
        if cid in want and cid not in seen_pr:
            seen_pr.add(cid)
            progs.append(blk)
    return chans, progs


def main():
    want = wanted_ids()
    print(f"目标 tvg-id: {len(want)} 个")

    all_ch, all_pr = [], []
    seen_ch, seen_pr = set(), set()
    for url in SOURCES:
        try:
            raw = fetch(url)
        except Exception as e:
            print(f"  跳过 {url.rsplit('/', 1)[-1]}: {e}")
            continue
        try:
            text = gzip.decompress(raw).decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  解压失败 {url.rsplit('/', 1)[-1]}: {e}")
            continue
        ch, pr = extract(text, want)
        new_ch = [c for c in ch if re.search(r'<channel id="([^"]+)"', c).group(1) not in seen_ch]
        new_pr = [p for p in pr if re.search(r'channel="([^"]+)"', p).group(1) not in seen_pr]
        for c in new_ch:
            seen_ch.add(re.search(r'<channel id="([^"]+)"', c).group(1))
        for p in new_pr:
            seen_pr.add(re.search(r'channel="([^"]+)"', p).group(1))
        all_ch += new_ch
        all_pr += new_pr
        print(f"  {url.rsplit('/', 1)[-1]}: channel +{len(new_ch)}, programme +{len(new_pr)}")

    if not all_ch:
        print("所有源均失败，保留原文件不改动")
        return 1

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
           '<tv generator-info-name="merged-cn-hk-tw">\n'
           + "\n".join(all_ch) + "\n"
           + "\n".join(all_pr) + "\n"
           + "</tv>\n")

    with open(OUT_XML, "w", encoding="utf-8") as f:
        f.write(xml)
    with gzip.open(OUT_GZ, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))

    print(f"输出: {len(all_ch)} channel / {len(all_pr)} programme")
    print(f"  {OUT_XML}  {os.path.getsize(OUT_XML)} bytes")
    print(f"  {OUT_GZ}  {os.path.getsize(OUT_GZ)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
