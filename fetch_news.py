#!/usr/bin/env python3
"""
Overseas News Feed Fetcher v3
æåæµ·å¤æ°é»RSSï¼åå¹¶ä¸ºnews.jsonï¼éè¿jsDelivr CDNååç»å½åä½¿ç¨ã

v3 æ¹å¨ï¼
1. å¢éå»éï¼SeenIndexï¼ï¼è¯»åæ§news.jsonï¼è®°ä½å·²è§è¿çæç« ï¼é¿åéå¤
2. çæ­æºå¶ï¼è®°å½æ¯ä¸ªæºçäº§åºï¼è¿ç»­3æ¬¡é¶äº§åºçæºæ è®°ä¸ºçæ­
3. ä»v2ç»§æ¿ï¼when:3dã72hæ¥æè¿æ»¤ãFederal Registeréåªãåéå»é
"""
import feedparser
import json
import re
import os
import hashlib
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# ============================================================
# RSSæºå®ä¹ â æ4ä¸ªåºæ¯åç»
# Google News æç´¢è¯ç»ä¸å  when:3dï¼å¼ºå¶è¿åæè¿3å¤©
# ============================================================
FEEDS = {
    "è´¢ç»ä¸»æµ": [
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
    "ç§æ+åºæµ·": [
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
    "æ¿ç­æ³è§": [
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
    "ä¸åäºæ¬å°": [
        {
            "url": "https://www.straitstimes.com/rss/breaking-news",
            "tag": "Straits Times | Breaking"
        },
        {
            "url": "https://www.bangkokpost.com/rss/data/breakingnews.xml",
            "tag": "Bangkok Post | Breaking"
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
        },    ],
    "APEC国家官方": [
        {
            "url": "https://news.google.com/rss/search?q=site:meti.go.jp+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Japan METI | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:motie.go.kr+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Korea MOTIE | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:dfat.gov.au+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Australia DFAT | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:mfat.govt.nz+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "New Zealand MFAT | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:international.gc.ca+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Canada Global Affairs | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:gob.mx/se+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Mexico Economy Ministry | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:dt.gov.ph+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Philippines DT | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:economy.gov.ru+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Russia Economy Ministry | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:minrel.gob.cl+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Chili MFA | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:mincetur.gob.pe+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Peru MINCETUR | Trade"
        },
    ],
    "国际组织": [
        {
            "url": "https://news.google.com/rss/search?q=site:imf.org+trade+tariff+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "IMF | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:oecd.org+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "OECD | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:ilo.org+supply+chain+labor+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "ILO | Supply Chain/Labor"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:wipo.int+ip+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "WIPO | IP/Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:intracen.org+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "ITC | Trade"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:unido.org+manufacturing+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "UNIDO | Manufacturing"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:iea.org+energy+trade+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "IEA | Energy/Trade"
        },
    ],
    "制造业企业": [
        {
            "url": "https://news.google.com/rss/search?q=site:volkswagen.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Volkswagen | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:gm.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "General Motors | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:byd.com+overseas+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "BYD | Overseas"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:tesla.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Tesla | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:samsung.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Samsung | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:foxconn.com+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Foxconn | Manufacturing"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:caterpillar.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Caterpillar | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:sanyglobal.com+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "SANY | Overseas"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:basf.com+supply+chain+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "BASF | Supply Chain"
        },
        {
            "url": "https://news.google.com/rss/search?q=site:nike.com+sourcing+when:3d&hl=en-US&gl=US&ceid=US:en",
            "tag": "Nike | Sourcing"
        },
    ],
}
