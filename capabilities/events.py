from datetime import datetime, timedelta
from typing import Dict, Optional, List
from providers.news import fetch_news
from providers.news import fetch_news


def get_asset_events(asset_name: str, lookback_days: int = 7, max_events: int = 5):
    news_items = fetch_news(asset_name, limit=max_events)

    return {
        "asset": asset_name,
        "events": news_items,
        "confidence": "high" if news_items else "low",
    }



def get_asset_events(
    asset_name: str,
    symbol: Optional[str] = None,
    lookback_days: int = 7,
    max_events: int = 5
) -> Dict:
    """
    Aggregates decision-relevant events for a given asset
    using factual news sources only (v1).
    """

    raw_news = fetch_news(asset_name)

    events = []
    

    for item in raw_news[:max_events]:
        events.append({
            "title": item.get("title"),
            "description": item.get("description") or "",
            "source": item.get("source"),
            "published_at": item.get("published_at"),
            "url": item.get("url"),
        })

    return {
        "asset": asset_name,
        "symbol": symbol,
        "time_window": f"last {lookback_days} days",
        "events": events,
        "confidence": "medium" if events else "low",
    }
