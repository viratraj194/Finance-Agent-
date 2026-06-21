import requests
import feedparser
from datetime import datetime
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
    Falls back to Google News RSS sentiment queries if Reddit API blocks the request.
    """

    url = "https://www.reddit.com/search.json"

    # Avoid double-suffixing 'stock' if the query already has it
    search_query = query
    if "stock" not in query.lower() and len(query.split()) <= 2:
        search_query = f"{query} stock"

    params = {
        "q": search_query,
        "sort": "new",
        "limit": limit,
        "restrict_sr": False,
    }

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
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

            if posts:
                return posts
    except Exception:
        pass

    # =====================================================
    # FALLBACK: Query Google News RSS for Retail Sentiment
    # =====================================================
    try:
        rss_query = f"{query} stock sentiment discussion"
        url_rss = f"https://news.google.com/rss/search?q={rss_query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url_rss)
        posts = []
        for entry in feed.entries[:limit]:
            created_date = datetime.now().strftime("%Y-%m-%d")
            try:
                if entry.get("published_parsed"):
                    created_date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
            
            posts.append({
                "title": entry.get("title"),
                "selftext": entry.get("summary") or entry.get("title"),
                "subreddit": "Retail Forum / " + (entry.get("source", {}).get("title") or "News"),
                "score": 10,
                "created_utc": datetime.now().timestamp(),
                "url": entry.get("link")
            })
        if posts:
            return posts
    except Exception:
        pass

    return []

