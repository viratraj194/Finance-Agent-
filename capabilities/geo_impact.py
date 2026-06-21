"""
Geopolitical Impact Analyzer
Analyzes how global events (wars, sanctions, trade disputes, etc.) affect Indian stocks.
Produces a structured WINNERS vs LOSERS report with real prices and reasoning.
"""
import concurrent.futures
import logging
import json
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.news import fetch_news
from providers.yahoo import get_market_data, search_symbol

logger = logging.getLogger(__name__)

MODEL = "meta/llama-3.3-70b-instruct"

# Stocks most sensitive to geopolitical events — pre-seeded for speed
# Format: { category: [(name, symbol)] }
GEO_SENSITIVE_STOCKS = {
    "Oil & Gas (upstream - benefits from high oil)": [
        ("ONGC", "ONGC.NS"),
        ("Oil India", "OIL.NS"),
        ("Reliance Industries", "RELIANCE.NS"),
    ],
    "Oil Marketing (downstream - hurt by high oil)": [
        ("Indian Oil Corporation", "IOC.NS"),
        ("BPCL", "BPCL.NS"),
        ("HPCL", "HINDPETRO.NS"),
    ],
    "Defense & Aerospace (benefits from war spending)": [
        ("HAL", "HAL.NS"),
        ("BEL", "BEL.NS"),
        ("Data Patterns", "DATAPATTNS.NS"),
        ("Paras Defence", "PDRP.NS"),
    ],
    "Aviation (hurt by high oil / travel disruption)": [
        ("IndiGo", "INDIGO.NS"),
        ("SpiceJet", "SPICEJET.NS"),
    ],
    "Gold / Safe Haven ETFs": [
        ("SBI Gold ETF", "GOLDBEES.NS"),
        ("Nippon Gold ETF", "GOLDETF.NS"),
    ],
    "IT / Technology (US exposure)": [
        ("TCS", "TCS.NS"),
        ("Infosys", "INFY.NS"),
        ("Wipro", "WIPRO.NS"),
        ("HCL Technologies", "HCLTECH.NS"),
    ],
    "Pharma (defensive / USD earner)": [
        ("Sun Pharma", "SUNPHARMA.NS"),
        ("Dr Reddy's", "DRREDDY.NS"),
        ("Cipla", "CIPLA.NS"),
    ],
    "Fertilizers (high oil = high input costs)": [
        ("Chambal Fertilizers", "CHAMBLFERT.NS"),
        ("Coromandel International", "COROMANDEL.NS"),
    ],
    "Shipping & Logistics": [
        ("Shipping Corporation", "SCI.NS"),
        ("Great Eastern Shipping", "GESHIP.NS"),
    ],
    "Banks & Financials": [
        ("HDFC Bank", "HDFCBANK.NS"),
        ("ICICI Bank", "ICICIBANK.NS"),
        ("SBI", "SBIN.NS"),
    ],
}


def fetch_stock_price(name: str, symbol: str) -> dict:
    """Fetch live price data for a stock."""
    try:
        data = get_market_data(symbol)
        if data:
            return {
                "name": name,
                "symbol": symbol,
                "price": data["price"],
                "change": data["change"],
                "change_pct": data["change_pct"],
                "direction": "up" if data["change"] > 0 else "down" if data["change"] < 0 else "flat",
                "high": data.get("high"),
                "low": data.get("low"),
            }
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
    return {"name": name, "symbol": symbol, "price": None}


def fetch_geo_news(event_query: str) -> list:
    """
    Fetch news related to the geopolitical event from multiple sources:
    - GNews API (existing)
    - Al Jazeera, BBC World, Reuters World, Defense News, Oil Price (new enhanced feeds)
    """
    all_news = []
    seen = set()

    def add_articles(articles):
        for a in articles:
            title = a.get("title", "")
            if title and title not in seen:
                seen.add(title)
                all_news.append(a)

    # 1. GNews API queries (fast, keyword-targeted, in parallel)
    queries = [
        event_query,
        f"{event_query} impact India stocks market",
        f"{event_query} oil price crude petroleum",
        "India defense sector geopolitical military spending",
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_news, q, 3): q for q in queries}
        for future in concurrent.futures.as_completed(futures):
            try:
                articles = future.result()
                add_articles(articles)
            except Exception:
                pass

    # 2. Enhanced geopolitical RSS feeds (breaking news from global sources)
    try:
        from providers.enhanced_rss import fetch_global_and_geo_news
        geo_articles = fetch_global_and_geo_news(limit_per_feed=5, max_total=25)
        add_articles(geo_articles)
        logger.info(f"Enhanced geo RSS: {len(geo_articles)} articles fetched")
    except Exception as e:
        logger.warning(f"Enhanced geo RSS failed: {e}")

    # 3. Economic calendar events (RBI, Fed, OPEC meetings)
    try:
        from providers.economic_calendar import fetch_economic_calendar_news
        cal_articles = fetch_economic_calendar_news(limit_per_feed=3)
        add_articles(cal_articles)
    except Exception:
        pass

    return all_news[:20]


def run_geo_impact_analysis(user_query: str, event_description: str) -> str:
    """
    Full geopolitical impact analysis:
    1. Fetches live prices for geo-sensitive stocks in parallel
    2. Fetches event-related news
    3. LLM synthesizes WINNERS vs LOSERS with precise reasoning
    """

    # 1. Fetch all prices in parallel
    logger.info(f"Fetching prices for {sum(len(v) for v in GEO_SENSITIVE_STOCKS.values())} geo-sensitive stocks...")
    all_stocks = []
    stock_to_category = {}
    for category, stocks in GEO_SENSITIVE_STOCKS.items():
        for name, symbol in stocks:
            all_stocks.append((name, symbol))
            stock_to_category[symbol] = category

    price_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_stock_price, name, sym): sym for name, sym in all_stocks}
        for future in concurrent.futures.as_completed(futures):
            sym = futures[future]
            try:
                result = future.result()
                category = stock_to_category.get(sym, "Other")
                if category not in price_data:
                    price_data[category] = []
                price_data[category].append(result)
            except Exception as e:
                logger.error(f"Price fetch failed for {sym}: {e}")

    # 2. Fetch geopolitical news
    logger.info("Fetching geopolitical news...")
    news = fetch_geo_news(event_description)

    # 3. Retrieve latest market report for additional context
    from agent import get_latest_market_report
    report_context = get_latest_market_report()

    # 4. Build LLM prompt
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY
    )

    prompt = (
        f"User Question: {user_query}\n\n"
        f"Geopolitical Event Context: {event_description}\n\n"
        "You are a senior geopolitical market analyst specializing in Indian equity markets.\n"
        "Analyze how this geopolitical event impacts Indian stocks. Produce a comprehensive report structured as:\n\n"

        "## 📈 STOCKS THAT CAN GO UP (WINNERS)\n"
        "For each winner:\n"
        "- Stock Name (NSE Symbol) | Current Price | Today's Change\n"
        "- Why it benefits (specific geopolitical mechanism: e.g., 'high crude oil prices boost upstream revenues')\n"
        "- Key risk to this view\n\n"

        "## 📉 STOCKS THAT CAN GO DOWN (LOSERS)\n"
        "For each loser:\n"
        "- Stock Name (NSE Symbol) | Current Price | Today's Change\n"
        "- Why it gets hurt (specific mechanism: e.g., 'aviation fuel costs spike, margins crushed')\n"
        "- Key risk to this view\n\n"

        "## 🌍 MACRO IMPACT ON INDIA\n"
        "Summarize the broader macroeconomic effects: currency (INR), inflation, RBI response, FII flows.\n\n"

        "## ⚠️ RISK MANAGEMENT ADVICE\n"
        "Brief practical guidance for traders navigating geopolitical uncertainty.\n\n"

        "Use the LIVE PRICE DATA below to cite REAL current prices. Be specific — name exact stocks with their NSE ticker.\n"
        "Do NOT give generic answers. This must be actionable.\n\n"
        f"--- LIVE PRICE DATA (categorized) ---\n{json.dumps(price_data, default=str)}\n\n"
        f"--- LATEST NEWS ON THE EVENT ---\n{json.dumps(news, default=str)}\n\n"
        f"--- LATEST MARKET REPORT CONTEXT ---\n{report_context[:3000] if report_context else 'Not available'}\n\n"
        "Add a disclaimer at the end that this is AI-generated analysis, not financial advice."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional geopolitical equity analyst for Indian markets. "
                        "You give precise, data-backed analysis on how global events impact specific Indian stocks. "
                        "Always cite real stock names and current prices from the data provided. Be direct and actionable."
                    )
                },
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content if response and response.choices else None
        if not content:
            return "❌ The LLM returned an empty response. This may be due to server load. Please try again."
        return content
    except Exception as e:
        logger.error(f"LLM geo impact analysis failed: {e}")
        return f"❌ Failed to generate geopolitical impact report: {e}"
