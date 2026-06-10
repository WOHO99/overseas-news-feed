# Overseas News Feed

自动抓取海外新闻RSS，通过jsDelivr CDN分发给国内使用。

## 覆盖场景

| 场景 | 源数量 | 代表源 |
|------|--------|--------|
| 财经主流 | 5 | Nikkei Asia, SCMP, Bloomberg, Google News Trade |
| 科技+出海 | 4 | TechCrunch China/SE Asia, Google News Going Global |
| 政策法规 | 5 | Federal Register USTR/BIS/DoD, Google News 1260H |
| 东南亚本地 | 7 | Jakarta Post, Straits Times, Bangkok Post, The Star, Google News VN/ID/TH |

## API地址

```
https://cdn.jsdelivr.net/gh/WOHO99/overseas-news-feed@main/news.json
```

国内直接GET即可，jsDelivr CDN加速，延迟<500ms。

## 更新频率

每4小时自动更新（UTC 0,4,8,12,16,20），也支持手动触发。

## 数据结构

```json
{
  "updated": "2026-06-11T08:00:00+00:00",
  "total": 89,
  "high_priority": 12,
  "stats_by_category": { "财经主流": 23, "科技+出海": 15, "政策法规": 18, "东南亚本地": 33 },
  "articles": [
    {
      "title": "...",
      "link": "...",
      "published": "...",
      "summary": "...",
      "source": "Nikkei Asia",
      "priority": 3,
      "relevance": "high"
    }
  ]
}
```

## 优先级标记

- `high` (priority>=3): 命中3个以上关键关键词（301/tariff/sanctions/1260H/supply chain等）
- `medium` (priority>=1): 命中1-2个关键词
- `low` (priority=0): 未命中关键词

## 使用方式

### 在写作流程中调用

Step 1.6搜索验证阶段，除了DeepSeek+KIMI搜索外，额外读取news.json：
1. 筛选`relevance=high`的条目
2. 按场景筛选对应category的条目
3. 对高相关条目用webfetch访问原文全文

### 作为信号发现工具

每4小时检查一次`high_priority`条目，发现新信号及时跟进。

## 自定义

- 增删RSS源：编辑`fetch_news.py`中的`FEEDS`字典
- 调整关键词：编辑`HIGH_PRIORITY_KEYWORDS`列表
- 调整更新频率：编辑`.github/workflows/update.yml`中的cron表达式
