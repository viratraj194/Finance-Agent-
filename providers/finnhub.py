"""
Finnhub.io Data Provider
Free tier: 60 API calls/minute, no credit card required.
Sign up at: https://finnhub.io/register (takes 1 minute, completely free)

Data available on free tier:
- Real-time company news (by ticker)
- General market news (crypto, forex, merger, general)
- Earnings calendar (upcoming earnings dates + EPS estimates)
- Insider transactions (when insiders buy/sell their own stock)
- IPO calendar (upcoming IPOs)
- Market sentiment (bullish/bearish from news analysis)
- Basic financials (PE, EPS, revenue, profit margins)
- Support: 60 reqs/min, unlimited historical

Setup: Add FINNHUB_API_KEY=your_key to .env file
Get free key at: https://finnhub.io/register
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import FINNHUB_API_KEY

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"


def _finnhub_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """Makes a GET request to Finnhub API."""
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set. Add it to .env for enhanced data.")
        return None
    try:
        url = f"{FINNHUB_BASE}/{endpoint}"
        params = params or {}
        params["token"] = FINNHUB_API_KEY
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 401:
            logger.error("Finnhub API key invalid. Check FINNHUB_API_KEY in .env")
        elif resp.status_code == 429:
            logger.warning("Finnhub rate limit hit (60/min free tier). Slow down requests.")
        return None
    except Exception as e:
        logger.error(f"Finnhub API error at {endpoint}: {e}")
        return None


def get_company_news(symbol: str, days_back: int = 7) -> List[Dict]:
    """
    Fetch recent news articles for a specific company.
    Symbol should be US format (e.g., 'INFY' for Infosys ADR).
    For Indian tickers, use NSE symbol without .NS
    """
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    data = _finnhub_get("company-news", {
        "symbol": symbol,
        "from": from_date,
        "to": to_date
    })
    if not data:
        return []

    articles = []
    for item in data[:8]:
        articles.append({
            "title": item.get("headline", ""),
            "description": item.get("summary", "")[:300],
            "source": item.get("source", "Finnhub"),
            "published_at": datetime.fromtimestamp(item.get("datetime", 0)).strftime("%Y-%m-%dT%H:%M:%SZ") if item.get("datetime") else None,
            "url": item.get("url", ""),
            "sentiment": item.get("sentiment", "neutral"),
            "category": item.get("category", "company")
        })
    return articles


def get_market_news(category: str = "general") -> List[Dict]:
    """
    Fetch general market news.
    Categories: 'general', 'forex', 'crypto', 'merger'
    """
    data = _finnhub_get("news", {"category": category, "minId": 0})
    if not data:
        return []

    articles = []
    for item in data[:10]:
        articles.append({
            "title": item.get("headline", ""),
            "description": item.get("summary", "")[:300],
            "source": item.get("source", "Finnhub"),
            "published_at": datetime.fromtimestamp(item.get("datetime", 0)).strftime("%Y-%m-%dT%H:%M:%SZ") if item.get("datetime") else None,
            "url": item.get("url", ""),
            "category": category
        })
    return articles


def get_earnings_calendar(days_ahead: int = 7) -> List[Dict]:
    """
    Get upcoming earnings releases — CRITICAL for trading around earnings.
    Tells you which companies report results in the next N days.
    """
    from_date = datetime.now().strftime("%Y-%m-%d")
    to_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    data = _finnhub_get("calendar/earnings", {"from": from_date, "to": to_date})
    if not data:
        return []

    earnings_list = data.get("earningsCalendar", [])
    results = []
    for item in earnings_list[:15]:
        results.append({
            "symbol": item.get("symbol"),
            "date": item.get("date"),
            "eps_estimate": item.get("epsEstimate"),
            "eps_actual": item.get("epsActual"),
            "revenue_estimate": item.get("revenueEstimate"),
            "quarter": item.get("quarter"),
            "year": item.get("year"),
        })
    return results


def get_insider_transactions(symbol: str) -> List[Dict]:
    """
    Get insider buying/selling — when company executives buy/sell their own stock.
    Insider buying is one of the most reliable bullish signals.
    """
    data = _finnhub_get("stock/insider-transactions", {"symbol": symbol})
    if not data:
        return []

    transactions = data.get("data", [])[:10]
    results = []
    for t in transactions:
        results.append({
            "name": t.get("name"),
            "transaction_type": "BUY" if t.get("transactionType") in ["P - Purchase", "Purchase"] else "SELL",
            "shares": t.get("share"),
            "value": t.get("value"),
            "date": t.get("transactionDate"),
            "filing_date": t.get("filingDate"),
        })
    return results


def get_ipo_calendar(days_ahead: int = 30) -> List[Dict]:
    """Fetch upcoming IPO calendar."""
    from_date = datetime.now().strftime("%Y-%m-%d")
    to_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    data = _finnhub_get("calendar/ipo", {"from": from_date, "to": to_date})
    if not data:
        return []

    ipos = data.get("ipoCalendar", [])[:10]
    return [
        {
            "symbol": ipo.get("symbol"),
            "name": ipo.get("name"),
            "date": ipo.get("date"),
            "price_range": f"{ipo.get('price', 'TBD')}",
            "shares": ipo.get("numberOfShares"),
            "status": ipo.get("status"),
        }
        for ipo in ipos
    ]


def get_market_sentiment_for_tickers(symbols: List[str]) -> Dict[str, str]:
    """
    Batch-fetch news sentiment for a list of tickers.
    Returns {symbol: 'bullish'/'bearish'/'neutral'} mapping.
    """
    if not FINNHUB_API_KEY:
        return {}

    results = {}
    for symbol in symbols[:10]:  # Respect rate limits
        try:
            data = _finnhub_get("news-sentiment", {"symbol": symbol})
            if data and "sentiment" in data:
                s = data["sentiment"]
                bull = s.get("bullishPercent", 0.5)
                bear = s.get("bearishPercent", 0.5)
                if bull > 0.55:
                    results[symbol] = f"bullish ({bull:.0%} positive)"
                elif bear > 0.55:
                    results[symbol] = f"bearish ({bear:.0%} negative)"
                else:
                    results[symbol] = "neutral"
        except Exception:
            pass
    return results


def get_basic_financials(symbol: str) -> Dict:
    """Get key financial metrics: PE, EPS, margins, revenue growth."""
    data = _finnhub_get("stock/metric", {"symbol": symbol, "metric": "all"})
    if not data:
        return {}
    metrics = data.get("metric", {})
    return {
        "pe_ratio_ttm": metrics.get("peTTM"),
        "eps_ttm": metrics.get("epsTTM"),
        "revenue_growth_3y": metrics.get("revenueGrowth3Y"),
        "gross_margin": metrics.get("grossMarginTTM"),
        "52_week_high": metrics.get("52WeekHigh"),
        "52_week_low": metrics.get("52WeekLow"),
        "beta": metrics.get("beta"),
        "rsi": metrics.get("rsi14d"),
    }
