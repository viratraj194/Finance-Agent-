import feedparser
from datetime import datetime
from typing import List, Dict


GOOGLE_NEWS_RSS_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
)


def fetch_google_news(ipo_name: str, max_items: int = 20) -> List[Dict]:
    """
    Fetches recent Google News articles related to an IPO.

    Returns a list of dicts with:
    - source
    - title
    - summary
    - url
    - published (YYYY-MM-DD)

    Never raises exceptions.
    """

    query = f"{ipo_name} IPO"
    url = GOOGLE_NEWS_RSS_TEMPLATE.format(query=query.replace(" ", "+"))

    try:
        feed = feedparser.parse(url)
    except Exception:
        return []

    results = []

    for entry in feed.entries[:max_items]:
        try:
            published_raw = entry.get("published", "")
            published_date = None

            if published_raw:
                published_date = datetime(
                    *entry.published_parsed[:6]
                ).strftime("%Y-%m-%d")

            results.append({
                "source": "google_news",
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "").strip(),
                "url": entry.get("link", ""),
                "published": published_date,
            })
        except Exception:
            continue

    return results
