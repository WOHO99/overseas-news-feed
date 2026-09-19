#!/usr/bin/env python3
"""
Overseas News Feed Fetcher v2
抓取海外新闻RSS，合并为news.json，通过jsDelivr CDN分发给国内使用。

v2 改动：
1. Google News 搜索词加 when:3d，强制返回最近3天文章
2. 加日期过滤：只保留最近72小时内的条目
3. Federal Register 降噪：标题不含贸易关键词的丢弃
4. 去重优化：title 哈希 + link 双重去重
5. 去掉明显无效的源（feedburner Bloomberg、TechCrunch 旧 feed）
"""
import feedparser
import json
import re
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
            "url": "https://asia.nikkei.com/rss/feed/nar",
            "tag": "Nikkei Asia"
        },
        {
            "url": "https://www.scmp.com/rss/91/feed",
            "tag": "SCMP | China Economy"
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
    ],
    "政策法规": [
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
    ],
    "东南亚本地": [
        {
            "url": "https://www.thejakartapost.com/rss",
            "tag": "Jakarta Post"
        },
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
    print(f"[{now_str}] Starting news fetch v2...")
    all_items = []
    stats = {}

    for category, feeds in FEEDS.items():
        cat_items = []
        for feed_def in feeds:
            url = feed_def["url"]
            tag = feed_def["tag"]
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

    # 日期过滤：只保留最近72小时
    recent_items = [i for i in unique_items if is_recent(i.get("published", ""), 72)]

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

    # 构建输出
    output = {
        "updated": now_str,
        "total": len(recent_items),
        "high_priority": len([i for i in recent_items if i["relevance"] == "high"]),
        "stats_by_category": stats,
        "articles": recent_items[:200],
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Recent(72h): {output['total']}, High priority: {output['high_priority']}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
