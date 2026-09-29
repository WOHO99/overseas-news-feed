#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google News CBMi 解密诊断：测试 /rss/articles/ 与 /articles/ 端点在不同 header 下的响应"""
import json
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def get(url, headers=None, timeout=15):
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
    for link in links[:4]:
        print("=" * 80)
        print("链接:", link[:100])
        variants = [
            ("rss_plain", link, {"Accept": "*/*"}),
            ("rss_html", link, {"Accept": "text/html,*/*"}),
            ("art_plain", link.replace("/rss/articles/", "/articles/"), {"Accept": "*/*"}),
            ("art_html", link.replace("/rss/articles/", "/articles/"),
             {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}),
            ("art_cookie", link.replace("/rss/articles/", "/articles/"),
             {"Accept": "text/html,*/*", "Cookie": "SOCS=CAI; CONSENT=YES+cb"}),
        ]
        for name, u, hd in variants:
            st, final, ln, body = get(u, hd)
            if isinstance(body, str) and body.startswith("ERR"):
                print(f"  {name}: {body}")
                continue
            canon = bool(re.search(r'rel=["\']canonical["\']', body[:5000]))
            ncl = "data-ncl-heading" in body[:8000]
            ext = [c for c in re.findall(r'href="(https?://[^"]+)"', body)
                   if "google." not in c and "gstatic" not in c][:2]
            print(f"  {name}: status={st} final={final[:70]} len={ln} canon={canon} ncl={ncl} ext={ext}")
            if ln < 3000:
                print(f"    body: {body[:250]!r}")


if __name__ == "__main__":
    main()
