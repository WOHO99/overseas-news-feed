#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Overseas News Feed Fetcher v6.2
海外一手信源优先的新闻聚合管道，输出 news.json 供日报/商业分析取用。

v6.2 修复（2026-09-27）：
1. 贸易相关性过滤：只保留标题含贸易关键词的文章（Federal Register 噪音过滤）
2. 未来日期拒绝：发布时间晚于当前时间+24h 的文章丢弃（联邦公报的时区/预发布问题）
3. 清理失效源：USITC/EU DG Trade/World Bank/Straits Times/Vietnam Plus 原生RSS
   404 或解析失败 → 改为 Google News site: 包装
4. IMF/OECD/IEA 403 反爬 → 移除原生RSS，改 Google News site: 包装
5. Google News 查询合并减少（降 503 限流概率）
6. 来源分级 base 分提升官方权重
"""
import feedparser
import json
import re
import sys
import hashlib
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# ============================================================
# 信源定义 —— 海外一手优先，按模块分组
# ============================================================
FEEDS = {
    "美国官方": [
        {
            "url": "https://ustr.gov/taxonomy/term/244/feed",
            "tag": "USTR | Press Releases",
            "base": 3,
        },
        {
            "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=office-of-the-united-states-trade-representative&conditions%5Btype%5D%5B%5D=NOTICE",
            "tag": "Federal Register | USTR",
            "base": 3,
        },
        {
            "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=department-of-commerce-bureau-of-industry-and-security&conditions%5Btype%5D%5B%5D=RULE",
            "tag": "Federal Register | BIS",
            "base": 3,
        },
    ],
    "欧盟官方": [
        {
            "url": "https://news.google.com/rss/search?q=site:policy.trade.ec.europa.eu+OR+site:ec.europa.eu+trade+safeguard+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "EU DG Trade",
            "base": 3,
        },
    ],
    "国际组织": [
        {
            "url": "https://news.google.com/rss/search?q=site:wto.org+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "WTO",
            "base": 3,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:imf.org+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "IMF",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:worldbank.org+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "World Bank",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:oecd.org+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "OECD",
            "base": 2,
        },
    ],
    "海外媒体": [
        {
            "url": "https://www.scmp.com/rss/91/feed",
            "tag": "SCMP | China Economy",
            "base": 2,
        },
        {
            "url": "https://www.bangkokpost.com/rss/data/breakingnews.xml",
            "tag": "Bangkok Post | Breaking",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:straitstimes.com+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Straits Times",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:vietnamplus.vn+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Vietnam Plus",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:reuters.com+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Reuters | Trade/Tariff",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:bloomberg.com+tariff+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Bloomberg | Tariff/Trade",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:cnbc.com+tariff+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "CNBC | Tariff/Trade",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=China+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | China Trade",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=US+trade+tariff+sanction+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | US Trade",
            "base": 2,
        },
    ],
    "企业官方": [
        {
            "url": "https://news.google.com/rss/search?q=site:maersk.com+trade+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Maersk | Shipping",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:cma-cgm.com+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "CMA CGM | Shipping",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:msc.com+shipping+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "MSC | Shipping",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:hapag-lloyd.com+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Hapag-Lloyd | Shipping",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:dhl.com+shipping+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "DHL | Logistics",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:fedex.com+shipping+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "FedEx | Logistics",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:ups.com+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "UPS | Logistics",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:ebay.com+seller+policy+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "eBay | Seller",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:shopee.com+seller+policy+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Shopee | Seller",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:apple.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Apple | Supply Chain",
            "base": 1,
        },
    ],
    "亚太官方": [
        {
            "url": "https://news.google.com/rss/search?q=site:meti.go.jp+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Japan METI | Trade",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:mti.gov.sg+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Singapore MTI | Trade",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=site:dfat.gov.au+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Australia DFAT | Trade",
            "base": 2,
        },
        {
            "url": "https://news.google.com/rss/search?q=Southeast+Asia+tariff+export+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | SE Asia",
            "base": 1,
        },
        {
            "url": "https://news.google.com/rss/search?q=Indonesia+Vietnam+Thailand+export+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | ASEAN Trade",
            "base": 1,
        },
    ],
}

# ============================================================
# 贸易相关性关键词（用于过滤 Federal Register 等官方源的噪音）
# ============================================================
TRADE_KW = [
    "tariff", "trade", "import", "export", "duty", "dumping", "antidumping",
    "anti-dumping", "countervailing", "subsidy", "china", "301", "232",
    "safeguard", "steel", "aluminum", "ev", "electric vehicle", "semiconductor",
    "chip", "battery", "customs", "free trade", "fta", "solar", "rare earth",
    "section 301", "quota", "embargo", "sanction", "supply chain",
]

# 优先级打分关键词
HIGH_KW = [
    "tariff", "301", "232", "sanction", "embargo", "export control",
    "safeguard", "antidumping", "anti-dumping", "countervailing",
    "trade war", "de minimis", "forced labor", "1260h",
]
MED_KW = [
    "trade", "export", "import", "supply chain", "ecommerce", "e-commerce",
    "duty", "fdi", "cross-border", "logistics", "shipping",
]

# 相关性分类
CAT_KEYWORDS = {
    "中美经贸": ["china", "us-china", "beijing", "washington", "xi", "trump"],
    "美国关税": ["ustr", "federal register", "301", "232", "tariff", "section 301"],
    "欧盟贸易": ["eu ", "europe", "brussels", "european commission", "safeguard"],
    "跨境电商": ["ecommerce", "e-commerce", "seller", "amazon", "shopee", "temu", "shein"],
    "航运物流": ["shipping", "maersk", "cma cgm", "msc", "hapag", "dhl", "fedex", "ups", "port"],
    "亚太动态": ["asean", "vietnam", "thailand", "indonesia", "singapore", "japan", "korea", "australia"],
}


def parse_date(s):
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_rss(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NewsFeed/1.0; +https://github.com/WOHO99)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def is_trade_relevant(title):
    """官方源噪音过滤：标题需含贸易相关词才保留"""
    t = title.lower()
    return any(k in t for k in TRADE_KW)


def score_article(title, summary, source):
    text = (title + " " + (summary or "")).lower()
    pri = 0
    for kw in HIGH_KW:
        if kw in text:
            pri = max(pri, 2)
    for kw in MED_KW:
        if kw in text and pri < 1:
            pri = 1
    base = source.get("base", 0)
    pri = max(pri, base)
    return pri


def categorize(title, summary):
    text = (title + " " + (summary or "")).lower()
    for cat, kws in CAT_KEYWORDS.items():
        if any(k in text for k in kws):
            return cat
    return "其他"


def main():
    seen = set()
    old_articles = []
    try:
        with open("news.json", "r", encoding="utf-8") as f:
            old = json.load(f)
        for a in old.get("articles", []):
            seen.add(a.get("link", ""))
            seen.add(hashlib.md5((a.get("source", "") + "|" + a.get("title", "")).encode()).hexdigest())
            old_articles.append(a)
    except Exception as e:
        print(f"[warn] 读取旧 news.json 失败: {e}")

    now = datetime.now(timezone.utc)
    cut = now - timedelta(hours=72)
    future_limit = now + timedelta(hours=24)
    articles = []
    fail_counts = {}
    stats = {}

    for module, sources in FEEDS.items():
        stats[module] = 0
        for src in sources:
            url = src["url"]
            try:
                data = fetch_rss(url, timeout=20)
                feed = feedparser.parse(data)
                if feed.bozo and not feed.entries:
                    raise ValueError(f"RSS 解析失败: {feed.bozo_exception}")
                got = 0
                for entry in feed.entries:
                    title = (entry.get("title") or "").strip()
                    link = entry.get("link", "").strip()
                    if not title or not link:
                        continue
                    # 官方源噪音过滤
                    if src.get("filter", True) and not is_trade_relevant(title):
                        continue
                    pub = parse_date(entry.get("published", "") or entry.get("updated", ""))
                    if pub is None or pub < cut:
                        continue
                    # 未来日期拒绝（时区/预发布问题）
                    if pub > future_limit:
                        continue
                    # 去重
                    link_hash = hashlib.md5((src["tag"] + "|" + title).encode()).hexdigest()
                    if link in seen or link_hash in seen:
                        continue
                    summary = entry.get("summary", "") or ""
                    summary = re.sub(r"<[^>]+>", "", summary)[:500]
                    pri = score_article(title, summary, src)
                    art = {
                        "title": title,
                        "link": link,
                        "published": pub.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                        "summary": summary,
                        "source": src["tag"],
                        "module": module,
                        "category": categorize(title, summary),
                        "priority": pri,
                    }
                    articles.append(art)
                    seen.add(link)
                    seen.add(link_hash)
                    got += 1
                    stats[module] += 1
                fail_counts[src["tag"]] = 0
                print(f"[ok] {src['tag']}: {got} 篇新增")
            except Exception as e:
                fail_counts[src["tag"]] = 1
                print(f"[fail] {src['tag']}: {e}")

    # 3. 合并旧文章（保留7天内），同样做贸易过滤+未来日期拒绝
    keep_old = []
    for a in old_articles:
        pd = parse_date(a.get("published", ""))
        if pd is None or pd < now - timedelta(days=7):
            continue
        if pd > future_limit:
            continue
        if not is_trade_relevant(a.get("title", "")):
            continue
        keep_old.append(a)
    all_articles = keep_old + articles

    dedup = {}
    for a in all_articles:
        key = a["source"] + "|" + a["title"]
        if key not in dedup:
            dedup[key] = a
    all_articles = list(dedup.values())
    all_articles.sort(key=lambda x: (x.get("priority", 0), x.get("published", "")), reverse=True)

    high = sum(1 for a in all_articles if a.get("priority", 0) >= 2)
    total = len(all_articles)

    out = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
        "total": total,
        "high_priority": high,
        "stats_by_category": stats,
        "fail_counts": fail_counts,
        "articles": all_articles,
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"\n# 完成: updated={out['updated']} total={total} high={high} 新增={len(articles)}")
    print(f"# 模块产出: {json.dumps(stats, ensure_ascii=False)}")
    fails = [k for k, v in fail_counts.items() if v]
    print(f"# 失败源: {len(fails)} 个 -> {fails}")


if __name__ == "__main__":
    main()
