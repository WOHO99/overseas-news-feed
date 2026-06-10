#!/usr/bin/env python3
"""
Overseas News Feed Fetcher
抓取海外新闻RSS，合并为news.json，通过jsDelivr CDN分发给国内使用。

覆盖4个场景：
1. 财经主流 (Reuters/Bloomberg/FT/Nikkei/SCMP/WSJ)
2. 科技+出海 (TechCrunch/The Information/SCMP Tech)
3. 政策法规 (Federal Register/USTR/DoD/Commerce)
4. 东南亚本地 (Jakarta Post/Straits Times/VnExpress/Bangkok Post/The Star)
"""

import feedparser
import json
import os
import re
from datetime import datetime, timezone

# ============================================================
# RSS源定义 — 按4个场景分组
# ============================================================
FEEDS = {
    "财经主流": [
        {
            "url": "https://news.google.com/rss/search?q=China+trade+tariff+301+supply+chain&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | China Trade/Tariff/Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=Southeast+Asia+tariff+export+manufacturing&hl=en-US&gl=US&ceid=US:en",
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
        {
            "url": "https://feeds.feedburner.com/bloomberg-markets-news",
            "tag": "Bloomberg Markets"
        },
    ],
    "科技+出海": [
        {
            "url": "https://techcrunch.com/tag/china/feed/",
            "tag": "TechCrunch | China"
        },
        {
            "url": "https://techcrunch.com/tag/southeast-asia/feed/",
            "tag": "TechCrunch | SE Asia"
        },
        {
            "url": "https://news.google.com/rss/search?q=Chinese+companies+going+global+overseas+expansion&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | China Going Global"
        },
        {
            "url": "https://www.scmp.com/rss/92/feed",
            "tag": "SCMP | Tech"
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
            "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=department-of-defense&conditions%5Btype%5D%5B%5D=NOTICE",
            "tag": "Federal Register | DoD Notices (1260H etc)"
        },
        {
            "url": "https://news.google.com/rss/search?q=USTR+301+tariff+investigation+2026&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | USTR 301"
        },
        {
            "url": "https://news.google.com/rss/search?q=1260H+Chinese+military+companies+sanctions&hl=en-US&gl=US&ceid=US:en",
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
            "url": "https://news.google.com/rss/search?q=Vietnam+export+trade+tariff+manufacturing&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | Vietnam Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=Indonesia+tariff+export+nickel+critical+minerals&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | Indonesia Trade/Minerals"
        },
        {
            "url": "https://news.google.com/rss/search?q=Thailand+export+manufacturing+investment&hl=en-US&gl=US&ceid=US:en",
            "tag": "Google News | Thailand Trade"
        },
    ],
}

# 关键词过滤 — 标题或摘要包含以下关键词的条目优先级提升
HIGH_PRIORITY_KEYWORDS = [
    "301", "tariff", "sanctions", "1260H", "export control",
    "supply chain", "trade war", "USTR", "forced labor",
    "decoupling", "de-risking", "overcapacity",
    "going global", "出海", "chuhai", "overseas expansion",
    "restructuring", "diversion", "transshipment",
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
            # 清理HTML标签
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            if len(summary) > 500:
                summary = summary[:500] + "..."

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
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting news fetch...")
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

    # 去重（按link去重，保留优先级最高的）
    seen_links = {}
    for item in all_items:
        link = item["link"]
        if link in seen_links:
            if item["priority"] > seen_links[link]["priority"]:
                seen_links[link] = item
        else:
            seen_links[link] = item

    unique_items = list(seen_links.values())

    # 排序：优先级降序→发布时间降序
    unique_items.sort(key=lambda x: (x["priority"], x["published"]), reverse=True)

    # 分类标记
    for item in unique_items:
        if item["priority"] >= 3:
            item["relevance"] = "high"
        elif item["priority"] >= 1:
            item["relevance"] = "medium"
        else:
            item["relevance"] = "low"

    # 构建输出
    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "total": len(unique_items),
        "high_priority": len([i for i in unique_items if i["relevance"] == "high"]),
        "stats_by_category": stats,
        "articles": unique_items[:200],  # 总量上限200
    }

    # 写入文件
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Total: {output['total']}, High priority: {output['high_priority']}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
