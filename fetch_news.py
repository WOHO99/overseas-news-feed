#!/usr/bin/env python3
"""
Overseas News Feed Fetcher v3
抓取海外新闻RSS，合并为news.json，通过jsDelivr CDN分发给国内使用。

v3 改动：
1. 增量去重（SeenIndex）：读取旧news.json，记住已见过的文章，避免重复
2. 熔断机制：记录每个源的产出，连续3次零产出的源标记为熔断
3. 从v2继承：when:3d、72h日期过滤、Federal Register降噪、双重去重
"""
import feedparser
import json
import re
import os
import hashlib
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# ============================================================
# RSS源定义 — 按4个场景分组
# Google News 搜索词统一加 when:3d，强制返回最近3天
# ============================================================
FEEDS = {
    "财经主流": [
        {
            "url": "https://news.google.com/rss/search?q=China+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | China Trade/Tariff"
        },
        {
            "url": "https://news.google.com/rss/search?q=Southeast+Asia+tariff+export+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | SE Asia Trade"
        },
        {
            "url": "https://www.scmp.com/rss/91/feed",
            "tag": "SCMP | China Economy"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:reuters.com+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Reuters | Trade/Tariff"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:cnbc.com+tariff+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "CNBC | Tariff/Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:bloomberg.com+tariff+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Bloomberg | Tariff/Trade"
        },
    ],
    "科技+出海": [
        {
            "url": "https://techcrunch.com/tag/china/feed/",
            "tag": "TechCrunch | China"
        },
        {
            "url": "https://news.google.com/rss/search?q=Chinese+companies+going+global+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | China Going Global"
        },
        {
            "url": "https://news.google.com/rss/search?q=Amazon+seller+ban+suspension+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Amazon Seller Policy"
        },
        {
            "url": "https://news.google.com/rss/search?q=Temu+SHEIN+TikTok+Shop+tariff+regulation+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Cross-border Ecom Policy"
        },
        {
            "url": "https://news.google.com/rss/search?q=de+minimis+small+parcel+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "De Minimis Tariff"
        },
        {
            "url": "https://news.google.com/rss/search?q=VAT+cross-border+e-commerce+seller+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Ecom VAT/Tax"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:maersk.com+trade+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Maersk | Shipping/Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:dhl.com+shipping+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "DHL | Logistics"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:fedex.com+shipping+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "FedEx | Logistics"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:shopee.com+seller+policy+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Shopee | Seller Policy"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:lazada.com+seller+policy+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Lazada | Seller Policy"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:msc.com+shipping+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "MSC | Shipping"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:hapag-lloyd.com+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Hapag-Lloyd | Shipping"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:cma-cgm.com+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "CMA CGM | Shipping"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:ups.com+shipping+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "UPS | Logistics"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:ebay.com+seller+policy+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "eBay | Seller Policy"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:mercadolibre.com+seller+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Mercado Libre | Seller"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:walmart.com+trade+sourcing+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Walmart | Sourcing/Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:apple.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Apple | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:toyota.com+supply+chain+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Toyota | Supply Chain"
        },
    ],
    "政策法规": [
        {
            "url": "https://ustr.gov/taxonomy/term/244/feed",
            "tag": "USTR | Press Releases"
        },
        {
            "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=office-of-the-united-states-trade-representative&conditions%5Btype%5D%5B%5D=NOTICE",
            "tag": "Federal Register | USTR Notices"
        },
        {
            "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=department-of-commerce-bureau-of-industry-and-security&conditions%5Btype%5D%5B%5D=RULE",
            "tag": "Federal Register | BIS Rules"
        },
        {
            "url": "https://news.google.com/rss/search?q=USTR+301+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | USTR 301"
        },
        {
            "url": "https://news.google.com/rss/search?q=1260H+Chinese+military+companies+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | 1260H Sanctions"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:policy.trade.ec.europa.eu+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "EU DG Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:mti.gov.sg+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Singapore MTI"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:wto.org+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "WTO"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:unctad.org+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "UNCTAD"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:worldbank.org+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "World Bank"
        },
    ],
    "东南亚本地": [
        {
            "url": "https://www.straitstimes.com/rss/breaking-news",
            "tag": "Straits Times | Breaking"
        },
        {
            "url": "https://www.bangkokpost.com/rss/data/breakingnews.xml",
            "tag": "Bangkok Post | Breaking"
        },
        {
            "url": "https://www.thestar.com.my/rss/News",
            "tag": "The Star (Malaysia)"
        },
        {
            "url": "https://news.google.com/rss/search?q=Vietnam+export+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | Vietnam Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=Indonesia+tariff+export+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | Indonesia Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=Thailand+export+manufacturing+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | Thailand Trade"
        },
    ],
}

# 关键词过滤 — 标题或摘要包含以下关键词的条目优先级提升
HIGH_PRIORITY_KEYWORDS = [
    "301", "tariff", "sanction", "1260h", "export control",
    "supply chain", "trade war", "ustr", "forced labor",
    "decoupling", "de-risking", "overcapacity",
    "going global", "出海", "overseas expansion",
    "restructuring", "diversion", "transshipment",
    "import", "duty", "embargo", "fdi",
]

# Federal Register 降噪：标题不含这些词的丢弃
FR_TRADE_KEYWORDS = [
    "tariff", "trade", "import", "export", "sanction", "301",
    "1260h", "customs", "duty", "commerce", "industry",
    "supply chain", "foreign", "investment", "entity list",
]

# ============================================================
# 抓取逻辑
# ============================================================

def calc_priority(title, summary):
    """计算优先级分数，命中关键词越多分数越高"""
    text = (title + " " + summary).lower()
    score = 0
    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw.lower() in text:
            score += 1
    return score


def is_recent(published_str, max_age_hours=72):
    """判断文章是否在最近 max_age_hours 内"""
    try:
        pub = parsedate_to_datetime(published_str)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - pub).total_seconds() / 3600
        return 0 <= age_hours <= max_age_hours
    except Exception:
        return False


def fr_is_trade_related(title):
    """Federal Register 条目降噪：标题是否与贸易相关"""
    t = title.lower()
    return any(kw in t for kw in FR_TRADE_KEYWORDS)


def fetch_feed(url, tag, max_items=20):
    """抓取单个RSS源，返回条目列表"""
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            summary = entry.get("summary", entry.get("description", ""))
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            if len(summary) > 500:
                summary = summary[:500] + "..."

            # Federal Register 降噪
            if "Federal Register" in tag and not fr_is_trade_related(title):
                continue

            items.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": summary,
                "source": tag,
                "priority": calc_priority(title, summary),
            })
    except Exception as e:
        print(f"  [FAIL] {tag}: {e}")
    return items


def main():
    now_str = datetime.now(timezone.utc).isoformat()
    print(f"[{now_str}] Starting news fetch v3...")
    all_items = []
    stats = {}

    # 加载旧 news.json（增量去重）
    old_seen = set()
    old_articles = []
    source_health = {}
    if os.path.exists("news.json"):
        try:
            with open("news.json", "r", encoding="utf-8") as f:
                old = json.load(f)
            old_articles = old.get("articles", [])
            for a in old_articles:
                key = a.get("link") or hashlib.md5(a.get("title", "").lower().encode()).hexdigest()
                old_seen.add(key)
                # 记录源健康状态
                src = a.get("source", "")
                if src not in source_health:
                    source_health[src] = {"runs": 0, "total_items": 0}
                source_health[src]["runs"] += 1
                source_health[src]["total_items"] += 1
            print(f"  Loaded old news.json: {len(old_seen)} seen articles, {len(source_health)} sources")
        except Exception as e:
            print(f"  [WARN] Failed to load old news.json: {e}")

    # 熔断：连续3次零产出的源跳过
    circuit_broken = set()
    for src, health in source_health.items():
        if health["runs"] >= 3 and health["total_items"] == 0:
            circuit_broken.add(src)
    if circuit_broken:
        print(f"  Circuit broken (skipped): {circuit_broken}")

    for category, feeds in FEEDS.items():
        cat_items = []
        for feed_def in feeds:
            url = feed_def["url"]
            tag = feed_def["tag"]

            # 熔断检查
            if tag in circuit_broken:
                print(f"  [SKIP] {tag} (circuit broken)")
                continue

            print(f"  Fetching: {tag}...")
            items = fetch_feed(url, tag)
            cat_items.extend(items)
            print(f"    Got {len(items)} items")
        stats[category] = len(cat_items)
        all_items.extend(cat_items)

    # 去重：先按 link，再按 title 哈希
    seen = {}
    for item in all_items:
        key = item["link"] or hashlib.md5(item["title"].lower().encode()).hexdigest()
        if key in seen:
            if item["priority"] > seen[key]["priority"]:
                seen[key] = item
        else:
            seen[key] = item
    unique_items = list(seen.values())

    # 增量去重：过滤掉旧 news.json 里已有的文章
    new_items = []
    for item in unique_items:
        key = item["link"] or hashlib.md5(item["title"].lower().encode()).hexdigest()
        if key not in old_seen:
            new_items.append(item)
    print(f"  Incremental: {len(unique_items)} unique -> {len(new_items)} new (filtered out {len(unique_items)-len(new_items)} duplicates)")

    # 日期过滤：只保留最近72小时
    recent_items = [i for i in new_items if is_recent(i.get("published", ""), 72)]

    # 排序：优先级降序 → 发布时间降序
    recent_items.sort(key=lambda x: (x["priority"], x.get("published", "")), reverse=True)

    # 分类标记（标题命中2个关键词即high）
    for item in recent_items:
        if item["priority"] >= 2:
            item["relevance"] = "high"
        elif item["priority"] >= 1:
            item["relevance"] = "medium"
        else:
            item["relevance"] = "low"

    # 合并新旧：新文章放前面，旧文章补到后面（保留历史）
    combined = recent_items + [a for a in old_articles if a not in recent_items][:100]

    # 构建输出
    output = {
        "updated": now_str,
        "total": len(combined),
        "high_priority": len([i for i in combined if i.get("relevance") == "high"]),
        "stats_by_category": stats,
        "circuit_broken": list(circuit_broken),
        "articles": combined[:200],
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone. New recent(72h): {len(recent_items)}, Total: {output['total']}, High priority: {output['high_priority']}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
