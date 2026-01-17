import requests
from typing import List, Dict
from config import GNEWS_API_KEY


def fetch_news(query: str, limit: int = 5) -> List[Dict]:
    """
    Fetch recent news articles for an asset using GNews API.
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
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    articles = []

    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title"),
            "description": item.get("description"),
            "source": item.get("source", {}).get("name", "GNews"),
            "published_at": item.get("publishedAt"),
            "url": item.get("url"),
        })

    return articles
