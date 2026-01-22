import requests
from typing import List, Dict

HEADERS = {
    "User-Agent": "FinanceAI/0.1 (sentiment analysis)"
}

ALLOWED_SUBREDDITS = {
    "IndianStockMarket",
    "IndiaInvestments",
    "IndianStreetBets",
    "stocks",
    "investing",
    "IndiaStockPulse",
    "IPO_india",
}

SIGNAL_KEYWORDS = {
    "why", "worried", "concern", "fear", "panic", "risk", "problem",
    "fall", "down", "drop", "crash", "up", "rally", "spike",
    "results", "earnings", "margin", "guidance", "revenue", "profit", "loss",
    "regulation", "sebi", "rbi", "ban", "rule", "policy", "audit",
    "holding", "hold", "sell", "exit", "buy", "invest", "portfolio",
}


def fetch_reddit_posts(query: str, limit: int = 10) -> List[Dict]:
    """
    Fetch investor-relevant Reddit posts related to a stock or company.
    """

    url = "https://www.reddit.com/search.json"

    params = {
        "q": f"{query} stock",
        "sort": "new",
        "limit": limit,
        "restrict_sr": False,
    }

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    posts = []

    for item in data.get("data", {}).get("children", []):
        post = item.get("data", {})

        subreddit = post.get("subreddit")
        if subreddit not in ALLOWED_SUBREDDITS:
            continue

        text_blob = (
            (post.get("title") or "") + " " +
            (post.get("selftext") or "")
        ).lower()

        if not any(keyword in text_blob for keyword in SIGNAL_KEYWORDS):
            continue

        posts.append({
            "title": post.get("title"),
            "selftext": post.get("selftext", ""),
            "subreddit": subreddit,
            "score": post.get("score"),
            "created_utc": post.get("created_utc"),
            "url": f"https://www.reddit.com{post.get('permalink')}",
        })

        if len(posts) >= limit:
            break

    return posts
