"""
Economic Calendar Provider
Tracks upcoming high-impact economic events that move markets.

Events tracked:
- RBI (Reserve Bank of India) policy meetings & decisions
- US Federal Reserve FOMC meetings
- India CPI / WPI Inflation releases
- India GDP data
- US CPI, PPI, NFP (Non-Farm Payroll) — all move Indian markets
- India IIP (Industrial Production)
- US Interest rate decisions
- G7/G20 summits
- OPEC meetings (oil price impact)

Data source: Investing.com RSS + ForexFactory-style scraping (free, no key)
"""

import requests
import feedparser
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

# Economic event RSS feeds (free, no key required)
ECONOMIC_CALENDAR_FEEDS = {
    "Investing.com India Calendar": "https://in.investing.com/economic-calendar/Service/getCalendarFilteredData",
    "RBI Announcements": "https://www.rbi.org.in/scripts/RSS.aspx?Id=103",
    "RBI Monetary Policy": "https://www.rbi.org.in/scripts/RSS.aspx?Id=58",
    "India Budget & Finance Ministry": "https://www.indiabudget.gov.in/rss/rss.xml",
    "IMF News": "https://www.imf.org/en/News/rss",
    "World Bank India": "https://feeds.worldbank.org/RSS/country/ind/",
    "OPEC News": "https://www.opec.org/opec_web/en/media_centre/rss.htm",
    "US Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
}

# Pre-seeded calendar of recurring high-impact events (supplement to live data)
# These are the events that consistently move Indian markets the most
HIGH_IMPACT_EVENT_SCHEDULE = [
    {
        "name": "RBI Monetary Policy Committee (MPC) Meeting",
        "frequency": "Bi-monthly (6 times/year)",
        "impact": "CRITICAL - Sets interest rates. Rate cuts = bullish for banks, rate hikes = bearish",
        "sectors_affected": ["Banking", "NBFC", "Real Estate", "Auto"],
        "typical_market_reaction": "Nifty Bank moves ±3% on surprise decisions"
    },
    {
        "name": "US Federal Reserve FOMC Meeting",
        "frequency": "8 times/year",
        "impact": "CRITICAL - Sets global rates. Rate hikes = FII sell-off in India",
        "sectors_affected": ["All sectors via FII flows", "IT (dollar earnings)", "Banking"],
        "typical_market_reaction": "Nifty moves ±2% on day of Fed decision"
    },
    {
        "name": "India CPI Inflation Data",
        "frequency": "Monthly (released ~12th of each month)",
        "impact": "HIGH - Drives RBI rate expectations",
        "sectors_affected": ["Banking", "FMCG", "Consumer Staples"],
        "typical_market_reaction": "High CPI = rate hike fears = bond yields rise = bank stocks fall"
    },
    {
        "name": "India GDP Growth Data",
        "frequency": "Quarterly",
        "impact": "HIGH - Shows economic health",
        "sectors_affected": ["Infrastructure", "Capital Goods", "Banks", "Autos"],
        "typical_market_reaction": "Strong GDP = broad rally. Weak GDP = defensive rotation"
    },
    {
        "name": "US Non-Farm Payrolls (NFP)",
        "frequency": "Monthly (first Friday of each month)",
        "impact": "HIGH - Strong jobs = Fed hawkish = dollar rises = INR weakens",
        "sectors_affected": ["IT (INR/USD impact)", "Metals (global demand)", "Pharma (US exports)"],
        "typical_market_reaction": "Strong NFP = IT stocks benefit (weaker INR), OMCs hurt"
    },
    {
        "name": "India Union Budget",
        "frequency": "Annual (February 1)",
        "impact": "EXTREME - Single largest event for Indian markets",
        "sectors_affected": ["All sectors depending on spending allocation"],
        "typical_market_reaction": "Nifty can move ±5-10% in a single session"
    },
    {
        "name": "OPEC Meeting / Production Decision",
        "frequency": "Bi-annual + emergency meetings",
        "impact": "HIGH for oil-sensitive stocks",
        "sectors_affected": ["Oil & Gas", "Aviation", "Paint", "Chemicals", "Fertilizers"],
        "typical_market_reaction": "Production cuts = oil rises = ONGC/OIL.NS up, IndiGo/BPCL down"
    },
    {
        "name": "US CPI Inflation Data",
        "frequency": "Monthly",
        "impact": "HIGH - Drives Fed rate expectations = FII flows",
        "sectors_affected": ["IT", "Pharma", "Banking via FII movements"],
        "typical_market_reaction": "High US CPI = Fed hawkish = FII sell India = broad fall"
    },
    {
        "name": "India IIP (Industrial Production)",
        "frequency": "Monthly",
        "impact": "MEDIUM - Shows manufacturing health",
        "sectors_affected": ["Capital Goods", "Metals", "Power"],
        "typical_market_reaction": "Strong IIP = manufacturing stocks rally"
    },
    {
        "name": "Quarterly Earnings Season (Q1/Q2/Q3/Q4)",
        "frequency": "Quarterly (April, July, October, January)",
        "impact": "CRITICAL - Stock-specific and sector-wide moves",
        "sectors_affected": ["All sectors — each stock reacts to its own results"],
        "typical_market_reaction": "Individual stocks can move ±10-20% on earnings surprise"
    },
]


def fetch_economic_calendar_news(limit_per_feed: int = 4) -> List[Dict]:
    """
    Fetches economic event news from RBI, IMF, World Bank, OPEC, and Fed RSS feeds.
    """
    import concurrent.futures

    all_articles = []
    seen_titles = set()

    def fetch_feed(name: str, url: str) -> List[Dict]:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return []
            feed = feedparser.parse(resp.content)
            articles = []
            for entry in feed.entries[:limit_per_feed]:
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
                    "category": "economic_event"
                })
            return articles
        except Exception as e:
            logger.debug(f"Economic calendar feed '{name}' failed: {e}")
            return []

    # Skip the Investing.com POST endpoint (requires form data), fetch RSS feeds only
    rss_feeds = {k: v for k, v in ECONOMIC_CALENDAR_FEEDS.items()
                 if not "investing.com" in v.lower()}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_feed, name, url): name for name, url in rss_feeds.items()}
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

    return all_articles


def get_high_impact_events_summary() -> str:
    """
    Returns a formatted summary of recurring high-impact market events.
    Used by the daily report and LLM prompts for context.
    """
    lines = ["HIGH-IMPACT RECURRING MARKET EVENTS (India + Global):"]
    for event in HIGH_IMPACT_EVENT_SCHEDULE:
        lines.append(
            f"\n• {event['name']} ({event['frequency']})\n"
            f"  Impact: {event['impact']}\n"
            f"  Sectors: {', '.join(event['sectors_affected'][:3])}\n"
            f"  Reaction: {event['typical_market_reaction']}"
        )
    return "\n".join(lines)
