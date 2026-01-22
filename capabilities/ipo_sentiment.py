from typing import Dict, List
from collections import Counter

from providers.reddit_ipo import fetch_reddit_posts
from providers.gnews_ipo import fetch_google_news


POSITIVE_KEYWORDS = {
    "good", "strong", "positive", "profit", "growth",
    "subscribed", "oversubscribed", "demand", "well priced"
}

NEGATIVE_KEYWORDS = {
    "bad", "poor", "loss", "overpriced", "risk",
    "avoid", "weak", "concern", "muted"
}


def _classify_text_sentiment(text: str) -> str:
    text = text.lower()
    pos = sum(1 for w in POSITIVE_KEYWORDS if w in text)
    neg = sum(1 for w in NEGATIVE_KEYWORDS if w in text)

    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def analyze_ipo_sentiment(company: str) -> Dict:
    # -----------------------------
    # 1. FETCH DATA
    # -----------------------------
    reddit_posts = fetch_reddit_posts(company, limit=20)
    news_articles = fetch_google_news(company)

    # -----------------------------
    # 2. SENTIMENT SPLIT
    # -----------------------------
    sentiment_counter = Counter({"positive": 0, "neutral": 0, "negative": 0})
    themes = Counter()

    for post in reddit_posts:
        text = f"{post['title']} {post.get('selftext', '')}"
        label = _classify_text_sentiment(text)
        sentiment_counter[label] += 1

        for word in ["valuation", "subscription", "growth", "profit", "risk"]:
            if word in text.lower():
                themes[word] += 1

    # -----------------------------
    # 3. ASSESSMENT LOGIC
    # -----------------------------
    total_posts = len(reddit_posts)

    if total_posts == 0:
        assessment = "Low retail visibility."
    else:
        pos = sentiment_counter["positive"]
        neg = sentiment_counter["negative"]

        if pos >= neg * 2:
            assessment = "Strong positive retail sentiment."
        elif neg > pos:
            assessment = "Cautious to negative retail sentiment."
        else:
            assessment = "Retail interest present, sentiment broadly balanced."

    # -----------------------------
    # 4. OUTPUT
    # -----------------------------
    return {
        "posts_analyzed": total_posts,
        "articles_analyzed": len(news_articles),
        "sentiment_split": dict(sentiment_counter),
        "themes": [t for t, _ in themes.most_common(3)],
        "sample_reddit": [
            {
                "title": p["title"],
                "subreddit": p["subreddit"],
                "url": p["url"],
            }
            for p in reddit_posts[:5]
        ],
        "sample_news": [
            {
                "title": n["title"],
                "source": n["source"],
                "url": n["url"],
            }
            for n in news_articles[:5]
        ],
        "assessment": assessment,
    }
