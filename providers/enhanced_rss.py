"""
Enhanced RSS Feed Provider
Aggregates news from multiple premium financial sources simultaneously.

Sources included:
- Economic Times Markets (India's #1 financial news)
- Moneycontrol (India's largest investment platform)
- Business Standard (India's top business newspaper)
- LiveMint (Financial newspaper by HT Media)
- Reuters Business (Global breaking news)
- Bloomberg Markets (Global premium financial news)
- CNBC Markets (US market news with India impact)
- RBI Press Releases (Reserve Bank of India - monetary policy)
- SEBI News (Securities regulator - regulatory changes)
- NSE Circulars (Exchange-level announcements)
- Investing.com India (Technical + fundamental combined)
"""

import requests
import feedparser
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

# Premium RSS feeds — all free, no API keys required
RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "Moneycontrol Markets": "https://www.moneycontrol.com/rss/marketsindia.xml",
    "Moneycontrol Business": "https://www.moneycontrol.com/rss/business.xml",
    "Business Standard Markets": "https://www.business-standard.com/rss/markets-106.rss",
    "Business Standard Economy": "https://www.business-standard.com/rss/economy-policy-102.rss",
    "LiveMint Markets": "https://www.livemint.com/rss/markets",
    "LiveMint Companies": "https://www.livemint.com/rss/companies",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Reuters Markets": "https://feeds.reuters.com/reuters/INmarket",
    "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "Financial Times": "https://www.ft.com/rss/home/india",
    "RBI Press Releases": "https://www.rbi.org.in/scripts/RSS.aspx?Id=103",
    "SEBI Press Releases": "https://www.sebi.gov.in/sebirss.xml",
    "NSE India News": "https://nsearchives.nseindia.com/content/RSS/NSENews.xml",
    "The Hindu Business": "https://www.thehindu.com/business/feeder/default.rss",
    "NDTV Business": "https://feeds.feedburner.com/ndtvprofit-latest",
}

# Geopolitical-specific feeds
GEO_FEEDS = {
    "Al Jazeera Middle East": "https://www.aljazeera.com/xml/rss/all.xml",
    "Reuters World": "https://feeds.reuters.com/reuters/worldNews",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian World": "https://www.theguardian.com/world/rss",
    "Associated Press": "https://rsshub.app/ap/topics/apf-business",
    "Oil Price News": "https://oilprice.com/rss/main",
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
}


def _fetch_single_feed(name: str, url: str, limit: int = 5) -> List[Dict]:
    """Fetches a single RSS feed with timeout protection."""
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.content)
        articles = []
        for entry in feed.entries[:limit]:
            published = None
            try:
                if entry.get("published_parsed"):
                    published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
            articles.append({
                "title": entry.get("title", ""),
                "description": (entry.get("summary") or entry.get("title", ""))[:300],
                "source": name,
                "published_at": published,
                "url": entry.get("link", ""),
            })
        return articles
    except Exception as e:
        logger.debug(f"Feed '{name}' failed: {e}")
        return []


def fetch_enhanced_news(
    categories: List[str] = None,
    limit_per_feed: int = 4,
    max_total: int = 40,
    include_geo: bool = False,
) -> List[Dict]:
    """
    Fetches news from multiple premium RSS feeds in parallel.

    Args:
        categories: subset of RSS_FEEDS keys to fetch (None = all India feeds)
        limit_per_feed: articles per feed
        max_total: max total articles returned
        include_geo: whether to also include geopolitical feeds

    Returns:
        Deduplicated list of articles sorted by source diversity
    """
    import concurrent.futures

    feeds_to_fetch = dict(RSS_FEEDS)
    if include_geo:
        feeds_to_fetch.update(GEO_FEEDS)

    if categories:
        allowed = set(categories)
        if include_geo:
            allowed.update(GEO_FEEDS.keys())
        feeds_to_fetch = {k: v for k, v in feeds_to_fetch.items() if k in allowed}

    all_articles = []
    seen_titles = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(_fetch_single_feed, name, url, limit_per_feed): name
            for name, url in feeds_to_fetch.items()
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                articles = future.result()
                for a in articles:
                    title_key = a["title"].lower().strip()[:80]
                    if title_key and title_key not in seen_titles:
                        seen_titles.add(title_key)
                        all_articles.append(a)
            except Exception:
                pass

    return all_articles[:max_total]


def fetch_india_market_news(limit_per_feed: int = 3, max_total: int = 30) -> List[Dict]:
    """Fetch only India-focused financial news feeds."""
    india_feeds = [
        "Economic Times Markets",
        "Economic Times Stocks",
        "Moneycontrol Markets",
        "Moneycontrol Business",
        "Business Standard Markets",
        "Business Standard Economy",
        "LiveMint Markets",
        "LiveMint Companies",
        "NDTV Business",
        "The Hindu Business",
    ]
    return fetch_enhanced_news(categories=india_feeds, limit_per_feed=limit_per_feed, max_total=max_total)


def fetch_global_and_geo_news(limit_per_feed: int = 4, max_total: int = 30) -> List[Dict]:
    """Fetch global news with geopolitical feeds for war/conflict analysis."""
    return fetch_enhanced_news(
        categories=[
            "Reuters Business", "Reuters Markets", "Bloomberg Markets",
            "CNBC Finance", "Financial Times",
        ],
        limit_per_feed=limit_per_feed,
        max_total=max_total,
        include_geo=True,
    )


def fetch_regulatory_news(limit_per_feed: int = 5) -> List[Dict]:
    """Fetch RBI, SEBI, and NSE regulatory announcements."""
    reg_feeds = ["RBI Press Releases", "SEBI Press Releases", "NSE India News"]
    return fetch_enhanced_news(categories=reg_feeds, limit_per_feed=limit_per_feed, max_total=15)
