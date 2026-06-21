import requests
import feedparser
from datetime import datetime
from typing import List, Dict
from config import GNEWS_API_KEY


def fetch_news(query: str, limit: int = 5) -> List[Dict]:
    """
    Fetch recent news articles for an asset using GNews API.
    Falls back to Google News RSS if GNews API key is rate-limited or fails.
    """

    url = "https://gnews.io/api/v4/search"

    params = {
        "q": query,
        "lang": "en",
        "country": "in",
        "max": limit,
        "apikey": GNEWS_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=4)
        if response.status_code == 200:
            data = response.json()
            articles = []

            for item in data.get("articles", []):
                articles.append({
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "source": item.get("source", {}).get("name", "GNews"),
                    "published_at": item.get("publishedAt"),
                    "url": item.get("url"),
                })

            if articles:
                return articles
    except Exception:
        pass

    # =====================================================
    # FALLBACK: Fetch via Free Google News RSS Feed
    # feedparser.parse(url) has no timeout — must fetch with requests first
    # =====================================================
    try:
        url_rss = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        rss_response = requests.get(url_rss, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
        feed = feedparser.parse(rss_response.content)
        articles = []
        for entry in feed.entries[:limit]:
            published = None
            try:
                if entry.get("published_parsed"):
                    published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

            articles.append({
                "title": entry.get("title"),
                "description": entry.get("summary") or entry.get("title"),
                "source": entry.get("source", {}).get("title", "Google News RSS"),
                "published_at": published,
                "url": entry.get("link")
            })
        if articles:
            return articles
    except Exception:
        pass

    return []

