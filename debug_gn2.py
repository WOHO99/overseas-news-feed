#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google News CBMi 解密诊断 v2：定位文章真实URL在HTML中的位置"""
import json
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def get(url, headers=None, timeout=20):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", "ignore")
        return resp.status, resp.geturl(), len(body), body
    except Exception as e:
        return None, None, 0, f"ERR:{type(e).__name__}:{str(e)[:100]}"


def main():
    data = json.load(open("news.json", encoding="utf-8"))
    links = [a["link"] for a in data.get("articles", []) if "news.google.com" in a.get("link", "")]
    print(f"# CBMi 链接数: {len(links)}")
    # 只测2条，避免限流
    for link in links[:2]:
        print("=" * 80)
        print("链接:", link[:100])
        st, final, ln, body = get(link.replace("/rss/articles/", "/articles/"),
                                  {"Accept": "text/html,*/*", "Accept-Language": "en-US,en;q=0.9"})
        if isinstance(body, str) and body.startswith("ERR"):
            print(f"  ERR: {body}")
            continue
        print(f"  status={st} len={ln}")
        # 1. canonical 实际值
        cm = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*>', body)
        if cm:
            print("  canonical标签:", cm.group(0)[:200])
        # 2. 全body所有 http 外链，排除 google 域
        all_urls = re.findall(r'https?://[^"\s<>\\]+', body)
        non_google = [u for u in all_urls
                      if not any(g in u for g in ["news.google", "googleusercontent", "gstatic", "google.com/", "googleapis"])]
        # 去重保序
        seen = set()
        uniq = [u for u in non_google if not (u in seen or seen.add(u))]
        print(f"  非google URL总数: {len(uniq)}")
        for u in uniq[:15]:
            print(f"    URL: {u[:130]}")
        # 3. 常见媒体域名出现在body中的片段
        for dom in ["reuters.com", "bloomberg.com", "cnbc.com", "straitstimes", "vietnamplus", "scmp.com", "wsj.com"]:
            idx = body.find(dom)
            if idx > 0:
                print(f"  {dom} @ {idx}: ...{body[max(0,idx-60):idx+120]!r}...")
                break


if __name__ == "__main__":
    main()
