import requests
from datetime import datetime
from typing import List, Dict


SUBREDDITS = [
    "IndianStockMarket",
    "IndiaInvestments",
    "IndianIPO",
    "DalalStreetTalks",
    "StockMarketIndia",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (IPO-Sentiment-Bot/1.0)"
}


def fetch_reddit_posts(ipo_name: str, limit: int = 30) -> List[Dict]:
    """
    Fetches Reddit discussions related to an IPO from Indian finance subreddits.
    Uses public Reddit JSON endpoints (no API key required).
    """

    results = []
    query = f"{ipo_name} IPO"

    for subreddit in SUBREDDITS:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"

        params = {
            "q": query,
            "restrict_sr": "on",
            "sort": "new",
            "limit": limit,
        }

        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
        except Exception:
            continue

        for item in data.get("data", {}).get("children", []):
            post = item.get("data", {})

            try:
                created_date = datetime.fromtimestamp(
                    post.get("created_utc", 0)
                ).strftime("%Y-%m-%d")

                results.append({
                    "source": "reddit",
                    "subreddit": subreddit,
                    "title": post.get("title", "").strip(),
                    "body": post.get("selftext", "").strip(),
                    "score": post.get("score", 0),
                    "comments": post.get("num_comments", 0),
                    "created": created_date,
                    "url": f"https://www.reddit.com{post.get('permalink')}",
                })
            except Exception:
                continue

    return results
