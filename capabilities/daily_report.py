import os
import json
import logging
from datetime import datetime, timedelta
import feedparser
import requests
import pytz
from openai import OpenAI
from config import NVIDIA_API_KEY, GNEWS_API_KEY

logger = logging.getLogger(__name__)

# Initialize OpenAI client with NVIDIA endpoints as configured in agent.py
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
MODEL = "meta/llama-3.3-70b-instruct"

# Directory to save the reports
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "subscribers.json")

def fetch_rss_news(feed_url: str, limit: int = 10) -> list[dict]:
    """Fetch and parse news from a given RSS feed URL."""
    try:
        # feedparser.parse(url) has no timeout — must fetch with requests first
        rss_response = requests.get(feed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        feed = feedparser.parse(rss_response.content)
        articles = []
        for entry in feed.entries[:limit]:
            published = None
            try:
                if entry.get("published_parsed"):
                    published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
            
            articles.append({
                "title": entry.get("title"),
                "description": entry.get("summary") or entry.get("title"),
                "source": entry.get("source", {}).get("title", "Google News RSS"),
                "published_at": published,
                "url": entry.get("link")
            })
        return articles
    except Exception as e:
        logger.error(f"Error fetching RSS feed {feed_url}: {e}")
        return []

def fetch_tender_news_with_fallback(query_base: str, limit: int = 10) -> list[dict]:
    """Fetch tender/funding news from Google News RSS with a fall-back cascade (24h -> 48h -> 3d)."""
    # 1. Try last 24 hours
    query_24h = f"({query_base}) when:24h"
    url_24h = f"https://news.google.com/rss/search?q={query_24h.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    logger.info(f"Fetching tender/funding news (24h) for query: {query_base}")
    articles = fetch_rss_news(url_24h, limit=limit)
    if articles:
        return articles
    
    # 2. Try last 48 hours
    query_48h = f"({query_base}) when:48h"
    url_48h = f"https://news.google.com/rss/search?q={query_48h.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    logger.info(f"No 24h results. Fetching tender/funding news (48h) for query: {query_base}")
    articles = fetch_rss_news(url_48h, limit=limit)
    if articles:
        return articles

    # 3. Try last 3 days
    query_3d = f"({query_base}) when:3d"
    url_3d = f"https://news.google.com/rss/search?q={query_3d.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    logger.info(f"No 48h results. Fetching tender/funding news (3d) for query: {query_base}")
    articles = fetch_rss_news(url_3d, limit=limit)
    return articles

def get_combined_daily_news() -> list[dict]:
    """
    Fetches comprehensive market intelligence from ALL sources in parallel:
    1. Premium Indian financial RSS (ET, Moneycontrol, Business Standard, LiveMint)
    2. Global financial RSS (Reuters, Bloomberg, CNBC, FT)
    3. Regulatory news (RBI, SEBI, NSE)
    4. Economic calendar events (RBI, Fed, OPEC, IMF)
    5. Government tenders/contracts (existing functionality, preserved)
    6. Google News fallback (existing functionality, preserved)
    """
    import concurrent.futures
    news_items = []
    seen_titles = set()

    def tag_and_add(articles, region, category):
        for item in articles:
            title_key = (item.get("title") or "").lower().strip()[:80]
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                item["region"] = region
                item["category"] = category
                news_items.append(item)

    # Run all fetches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        try:
            from providers.enhanced_rss import fetch_india_market_news, fetch_global_and_geo_news, fetch_regulatory_news
            from providers.economic_calendar import fetch_economic_calendar_news
            from providers.bse_announcements import fetch_latest_bse_announcements
            from providers.eprocure_scraper import fetch_eprocure_tenders

            futures = {
                executor.submit(fetch_india_market_news, 4, 30): ("India", "Premium India Finance News"),
                executor.submit(fetch_global_and_geo_news, 3, 20): ("Global", "Global Finance & Geo News"),
                executor.submit(fetch_regulatory_news, 5): ("India", "RBI / SEBI / NSE Regulatory"),
                executor.submit(fetch_economic_calendar_news, 4): ("Global", "Economic Calendar Events"),
                executor.submit(fetch_latest_bse_announcements, 15): ("India", "BSE Corporate Announcements"),
                executor.submit(fetch_eprocure_tenders, 15): ("India", "Government eProcure Tenders"),
            }
            for future, (region, category) in futures.items():
                try:
                    articles = future.result(timeout=30)
                    tag_and_add(articles, region, category)
                except Exception as e:
                    logger.warning(f"Enhanced source failed: {e}")
        except ImportError as e:
            logger.warning(f"Enhanced providers not available: {e}")

    # Fallback / supplement: original Google News sources (always run)
    logger.info("Fetching Google News fallback sources...")
    in_rss = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en"
    global_rss = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"
    in_news = fetch_rss_news(in_rss, limit=8)
    global_news = fetch_rss_news(global_rss, limit=8)
    tag_and_add(in_news, "India", "General Business")
    tag_and_add(global_news, "Global", "General Business")

    # Government tenders (preserved from original)
    tender_query = '"government tender" OR "government contract" OR "defense order" OR "railway contract" OR "cabinet approval"'
    funding_query = '"government funding" OR "government grant" OR "PLI scheme" OR "government subsidy"'
    tender_news = fetch_tender_news_with_fallback(tender_query, limit=8)
    funding_news = fetch_tender_news_with_fallback(funding_query, limit=8)
    tag_and_add(tender_news + funding_news, "India", "Government Tenders & Contracts")

    logger.info(f"Total news items collected: {len(news_items)}")
    return news_items


def analyze_news_impact_via_llm(news_data: list[dict], nse_data: dict = None, dashboard_text: str = "", options_text: str = "") -> str:
    """Uses LLM to analyze the impact of news + institutional data on stocks and ETFs."""

    # Format news articles
    formatted_news = []
    for idx, item in enumerate(news_data[:50], start=1):  # Cap at 50 to control token count
        summary = item.get('deep_content') or item.get('description') or ''
        formatted_news.append(
            f"[{idx}] [{item.get('region','?')}] [{item.get('category','General')}]\n"
            f"Title: {item.get('title', 'No Title')}\n"
            f"Summary: {summary[:500]}\n"
            f"Source: {item.get('source', 'Unknown')} | {(item.get('published_at') or '')[:10]}"
        )
    news_context = "\n\n".join(formatted_news)

    # Format NSE institutional data
    nse_context = ""
    if nse_data:
        fii_dii = nse_data.get("fii_dii", {})
        if fii_dii and "fii" in fii_dii:
            fii = fii_dii["fii"]
            dii = fii_dii["dii"]
            nse_context += (
                f"\n📊 FII/DII INSTITUTIONAL FLOWS (Date: {fii_dii.get('date','today')}):\n"
                f"  FII: {fii.get('sentiment')} | Net: ₹{fii.get('net_value', 'N/A')} Cr "
                f"(Buy: ₹{fii.get('buy_value','N/A')} Cr | Sell: ₹{fii.get('sell_value','N/A')} Cr)\n"
                f"  DII: {dii.get('sentiment')} | Net: ₹{dii.get('net_value', 'N/A')} Cr "
                f"(Buy: ₹{dii.get('buy_value','N/A')} Cr | Sell: ₹{dii.get('sell_value','N/A')} Cr)\n"
                f"  → FII SELLING + DII BUYING = market supported at lower levels\n"
                f"  → FII BUYING + DII BUYING = strong bullish signal\n"
            )

        fii_deriv = nse_data.get("fii_derivatives", {})
        if fii_deriv and isinstance(fii_deriv, dict) and "stats" in fii_deriv:
            nse_context += f"\n📈 FII DERIVATIVES POSITIONING (Date: {fii_deriv.get('date','N/A')}):\n"
            for item in fii_deriv.get("stats", []):
                inst = item.get("instrument", "")
                if inst:
                    nse_context += f"  {inst} | Buy: ₹{item.get('buy_val')} Cr | Sell: ₹{item.get('sell_val')} Cr | OI: ₹{item.get('oi_val')} Cr\n"

        block_deals = nse_data.get("block_deals", [])
        # Guard: block_deals could be an error dict if NSE API failed
        if block_deals and isinstance(block_deals, list):
            nse_context += f"\n🔷 BLOCK DEALS (Large Institutional Trades):\n"
            for deal in block_deals[:5]:
                nse_context += f"  {deal.get('symbol')} | {deal.get('deal_type')} | Qty: {deal.get('quantity')} @ ₹{deal.get('price')} | {deal.get('client_name','?')}\n"

        top_gainers = nse_data.get("top_gainers", [])
        if top_gainers and isinstance(top_gainers, list):
            nse_context += f"\n🚀 TOP MARKET GAINERS (Smallcap/Midcap/Largecap breakouts):\n"
            for stock in top_gainers:
                nse_context += f"  {stock.get('symbol')} | LTP: ₹{stock.get('ltp')} | Change: +{stock.get('change_pct')}%\n"

        insider = nse_data.get("insider_trading", [])
        if insider and isinstance(insider, list):
            nse_context += f"\n🕵️ INSIDER TRADING (Promoter/Director Market Purchases):\n"
            for trade in insider:
                nse_context += f"  {trade.get('symbol')} | {trade.get('person')} ({trade.get('category')}) bought ₹{trade.get('buy_value_inr')} on {trade.get('date')}\n"

        circuits = nse_data.get("circuit_stocks", {})
        # Guard: circuits could be an error dict if NSE API failed
        if circuits and isinstance(circuits, dict) and "upper_circuit" in circuits:
            upper = circuits.get("upper_circuit", [])
            lower = circuits.get("lower_circuit", [])
            if upper and isinstance(upper, list):
                nse_context += f"\n🔺 UPPER CIRCUIT STOCKS (momentum plays): {', '.join(s.get('symbol','') for s in upper[:6])}\n"
            if lower and isinstance(lower, list):
                nse_context += f"🔻 LOWER CIRCUIT STOCKS (panic/exit): {', '.join(s.get('symbol','') for s in lower[:6])}\n"

    prompt = (
        "You are an ELITE INSTITUTIONAL QUANT & RESEARCH ANALYST whose sole objective is to give the reader an unfair 'smart money' edge before the market opens.\n"
        "You have access to today's news from premium sources (Economic Times, Moneycontrol, Reuters, Bloomberg) and real-time institutional flow data.\n"
        "Your goal is to identify early catalysts, stealthy government contracts, asymmetric bets, and stocks that are about to break out BEFORE the rest of the market prices them in.\n\n"
        "CRITICAL RULE: DO NOT HALLUCINATE. You MUST ONLY use the provided NEWS DATA, NSE INSTITUTIONAL DATA, and MARKET DASHBOARD DATA. If a stock or event is not in the provided text, DO NOT invent it. DO NOT invent recommendations or bullish/bearish signals without concrete proof from the text.\n\n"
        "You are also provided with a PRE-MARKET DASHBOARD containing global market data, commodities, currencies, VIX, Indian ADRs, Nifty/BankNifty pivot levels, and PCR data. Use this data to provide context for your analysis.\n\n"
        "Generate a highly actionable DAILY MARKET INTELLIGENCE REPORT with these exact sections:\n\n"
        "## 1. 🌐 OPENING OUTLOOK & GLOBAL CUES\n"
        "Based on the PRE-MARKET DASHBOARD data (US close, Asia live, crude oil, USD/INR, VIX, ADRs), predict the likely market opening (gap up/down/flat) with specific reasoning from the numbers. EXPLICITLY mention the performance of Gold and Silver — these are premium safe-haven metals; if they are surging, point out the risk-off sentiment in the market. Mention Nifty/BankNifty key pivot support/resistance levels for today. This section should be DATA-DRIVEN with specific numbers from the dashboard.\n\n"
        "## 2. 💰 INSTITUTIONAL FLOW ANALYSIS\n"
        "Analyze the FII/DII cash flows and FII derivatives positioning. Combine with PCR data to give a clear directional bias. Are institutions building longs or shorts? What does the PCR tell us about options writers' positioning?\n\n"
        "## 3. 🏛️ STEALTH CATALYSTS: Orders, Tenders & Policy\n"
        "List *every single* government contract, defense order, railway contract, PLI scheme, funding, or cabinet approval found in the news. Use a detailed bulleted list.\n\n"
        "## 4. 📊 NEWS-DRIVEN STOCK CATALYSTS\n"
        "Provide a table ONLY for stocks that have a clear, concrete catalyst in the provided NEWS DATA. DO NOT guess or hallucinate. If there is no data for a sector, skip it.\n"
        "Table Format MUST strictly follow Markdown standards with a separator row:\n"
        "| Stock/ETF | Symbol | Concrete Catalyst / Event | Source | Expected Impact |\n"
        "|---|---|---|---|---|\n"
        "| Example Stock | EXMPL | Bags $500M Order | Economic Times | Bullish — institutional buying likely |\n\n"
        "## 5. 🕵️ SMART MONEY: INSIDER TRADING & BLOCK DEALS\n"
        "Analyze block deals and Promoter/Director open market purchases from the NSE data. When a CEO buys their own stock heavily, it's a massive conviction signal.\n\n"
        "## 6. ⚡ TODAY'S WATCHLIST (DATA-BACKED ONLY)\n"
        "List stocks to watch today based EXCLUSIVELY on the provided news, institutional data, or ADR performance. For each stock, cite the exact data point supporting it. If no strong data exists, state 'No clear setups today based on the provided data.' DO NOT invent ideas.\n\n"
        "CRITICAL: Write a detailed report. Format as beautiful Markdown. Be specific with stock names and NSE tickers. Add disclaimer at end.\n\n"
        f"--- PRE-MARKET DASHBOARD ---\n{dashboard_text or 'Not available'}\n\n"
        f"--- KEY LEVELS & OPTIONS ---\n{options_text or 'Not available'}\n\n"
        f"--- NSE INSTITUTIONAL DATA ---\n{nse_context or 'Not available today'}\n\n"
        f"--- NEWS DATA ({len(news_data)} articles from premium sources) ---\n{news_context}\n--- END ---"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional equity research analyst at a top Indian brokerage. Generate a premium, actionable daily market intelligence report based ONLY on the provided news and data. DO NOT hallucinate. DO NOT invent recommendations, stock movements, or catalysts. Stay strictly factual and cite the provided data."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
        )
        content = response.choices[0].message.content if response and response.choices else None
        if not content:
            return "# Report Generation Issue\nThe LLM returned an empty response. This may be due to high server load. Please try /report again."
        return content
    except Exception as e:
        logger.error(f"Error in LLM news impact analysis: {e}")
        return f"# Error Generating Report\nAn error occurred while generating the daily analysis: {e}"

def generate_daily_report() -> str:
    """Main function to fetch ALL data sources, analyze, and save the daily market report.
    
    Data fetched in parallel:
    1. News (RSS, BSE, eProcure, Google News)
    2. NSE institutional data (FII/DII, block deals, insider trading, gainers)
    3. Global market dashboard (US/Asia/Europe, commodities, currencies, VIX, ADRs)
    4. Options snapshot (Nifty/BankNifty pivot levels, PCR)
    5. Earnings calendar (upcoming results)
    """
    import concurrent.futures
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    report_filename = f"market_impact_report_{date_str}.md"
    report_path = os.path.join(REPORTS_DIR, report_filename)

    logger.info(f"Starting enhanced daily report generation for {date_str}...")

    # Fetch ALL data sources in parallel
    nse_data = None
    dashboard_data = None
    dashboard_text = ""
    options_data = None
    options_text = ""
    earnings_data = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 1. News
        news_future = executor.submit(get_combined_daily_news)

        # 2. NSE institutional data
        nse_future = None
        try:
            from providers.nse_data import get_nse_full_snapshot
            nse_future = executor.submit(get_nse_full_snapshot)
        except ImportError:
            logger.warning("NSE data provider not available")

        # 3. Global market dashboard
        dashboard_future = None
        try:
            from providers.market_dashboard import get_pre_market_dashboard, format_dashboard_text
            dashboard_future = executor.submit(get_pre_market_dashboard)
        except ImportError:
            logger.warning("Market dashboard provider not available")

        # 4. Options snapshot (PCR + pivot levels)
        options_future = None
        try:
            from providers.options_data import get_options_snapshot, format_options_text
            options_future = executor.submit(get_options_snapshot)
        except ImportError:
            logger.warning("Options data provider not available")

        # 5. Earnings calendar
        earnings_future = None
        try:
            from providers.finnhub import get_earnings_calendar
            earnings_future = executor.submit(get_earnings_calendar, 3)
        except ImportError:
            logger.warning("Finnhub provider not available for earnings calendar")

        # Collect results
        news_data = news_future.result()

        if nse_future:
            try:
                nse_data = nse_future.result(timeout=30)
                logger.info(f"NSE data fetched: {list(nse_data.keys())}")
            except Exception as e:
                logger.warning(f"NSE data fetch failed: {e}")

        if dashboard_future:
            try:
                dashboard_data = dashboard_future.result(timeout=30)
                dashboard_text = format_dashboard_text(dashboard_data)
                logger.info(f"Market dashboard fetched: {len(dashboard_data.get('us_markets', []))} US, {len(dashboard_data.get('asian_markets', []))} Asia, {len(dashboard_data.get('indian_adrs', []))} ADRs")
            except Exception as e:
                logger.warning(f"Market dashboard fetch failed: {e}")

        if options_future:
            try:
                options_data = options_future.result(timeout=30)
                from providers.options_data import format_options_text
                options_text = format_options_text(options_data)
                logger.info(f"Options snapshot fetched: PCR={options_data.get('pcr', {}).get('nifty_pcr', 'N/A')}")
            except Exception as e:
                logger.warning(f"Options snapshot fetch failed: {e}")

        if earnings_future:
            try:
                earnings_data = earnings_future.result(timeout=15)
                logger.info(f"Earnings calendar fetched: {len(earnings_data)} upcoming")
            except Exception as e:
                logger.warning(f"Earnings calendar fetch failed: {e}")

    if not news_data:
        err_msg = f"# Daily Market Impact Report - {date_str}\n\nCould not fetch any news events for today."
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(err_msg)
        return report_path

    logger.info(f"Total articles fetched: {len(news_data)}. Enhancing with Scrapling deep text...")
    try:
        from providers.scrapling_fetcher import enrich_articles_with_deep_scrape
        news_data = enrich_articles_with_deep_scrape(news_data)
    except ImportError as e:
        logger.warning(f"Scrapling fetcher not available: {e}")

    logger.info(f"Deep scraping complete. Generating LLM analysis...")

    # Analyze with all data (pass dashboard + options context to LLM)
    report_content = analyze_news_impact_via_llm(
        news_data, nse_data=nse_data,
        dashboard_text=dashboard_text, options_text=options_text
    )

    # Format earnings section (pure data, no AI)
    earnings_section = ""
    if earnings_data:
        earnings_section = "\n## 📅 Upcoming Earnings (Next 3 Days)\n"
        earnings_section += "| Symbol | Date | EPS Estimate | Revenue Estimate |\n"
        earnings_section += "|---|---|---|---|\n"
        for e in earnings_data[:10]:
            symbol = e.get('symbol', 'N/A')
            date = e.get('date', 'N/A')
            eps_est = e.get('eps_estimate', 'N/A')
            rev_est = e.get('revenue_estimate', 'N/A')
            earnings_section += f"| {symbol} | {date} | {eps_est} | {rev_est} |\n"

    # Build final report: HARD DATA FIRST, then AI analysis
    source_count = len(set(item.get('source', '') for item in news_data))
    
    # Header
    final_report = (
        f"# 📊 Daily Market Intelligence Report - {date_str}\n"
        f"*Generated at {datetime.now().strftime('%I:%M %p')} IST | Sources: {source_count} premium feeds | Articles: {len(news_data)} | "
        f"NSE: {'✅' if nse_data else '❌'} | Global Markets: {'✅' if dashboard_data else '❌'} | "
        f"Options: {'✅' if options_data else '❌'}*\n\n"
    )

    # Section 0: Hard Data Dashboard (NO AI — pure formatted numbers)
    if dashboard_text:
        final_report += f"---\n\n```\n{dashboard_text}\n```\n\n"

    if options_text:
        final_report += f"```\n{options_text}\n```\n\n"

    if earnings_section:
        final_report += f"{earnings_section}\n"

    final_report += "---\n\n"

    # AI analysis sections (grounded in the data above)
    final_report += f"{report_content}\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)

    logger.info(f"Enhanced daily report saved to: {report_path}")
    return report_path

def add_subscriber(chat_id: int) -> bool:
    """Adds a chat ID to the subscribers list."""
    subscribers = load_subscribers()
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
        return True
    return False

def remove_subscriber(chat_id: int) -> bool:
    """Removes a chat ID from the subscribers list."""
    subscribers = load_subscribers()
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        return True
    return False

def load_subscribers() -> list[int]:
    """Loads subscribers from the JSON file."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump({"chat_ids": []}, f)
        return []
        
    try:
        with open(SUBSCRIBERS_FILE, "r") as f:
            data = json.load(f)
            return data.get("chat_ids", [])
    except Exception as e:
        logger.error(f"Error loading subscribers: {e}")
        return []

def save_subscribers(subscribers: list[int]):
    """Saves subscribers to the JSON file."""
    try:
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump({"chat_ids": subscribers}, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving subscribers: {e}")

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "scheduler_state.json")

def get_last_run_date() -> str:
    """Gets the date of the last successful daily report run."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f).get("last_run_date", "")
        except Exception:
            pass
    return ""

def save_last_run_date(date_str: str):
    """Saves the date of the last successful daily report run."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({"last_run_date": date_str}, f)
    except Exception as e:
        logger.error(f"Error saving last run date state: {e}")

def get_ist_now() -> datetime:
    """Returns current time in Indian Standard Time (IST) timezone."""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)
