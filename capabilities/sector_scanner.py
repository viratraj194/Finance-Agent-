import concurrent.futures
import logging
import json
from openai import OpenAI
from config import NVIDIA_API_KEY
from capabilities.indicators.basic import get_indicators
from capabilities.indicators.signals import compute_signals
from providers.news import fetch_news
MODEL = "meta/llama-3.3-70b-instruct"

logger = logging.getLogger(__name__)

SECTOR_MAP = {
    "IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "COALINDIA.NS"],
    "Power": ["NTPC.NS", "TATAPOWER.NS", "POWERGRID.NS", "JSWENERGY.NS", "ADANIPOWER.NS"],
    "Metal": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "NATIONALUM.NS"],
    "Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
    "Health": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "MAXHEALTH.NS"],
    "Government": ["RVNL.NS", "HAL.NS", "BEL.NS", "PFC.NS", "RECLTD.NS", "IRCON.NS"]
}

SECTOR_NEWS_QUERIES = {
    "IT": "India IT sector news TCS Infosys Wipro",
    "Energy": "India energy sector oil gas ONGC Reliance",
    "Power": "India power sector solar renewable NTPC Tata Power",
    "Metal": "India metal sector steel aluminium copper Tata Steel",
    "Bank": "India banking sector HDFC ICICI SBI RBI",
    "Health": "India pharma healthcare pharmaceuticals sector",
    "Government": "India PSU defense railways infrastructure contracts"
}

def scan_stock(symbol: str) -> dict | None:
    """Fetches indicators and computes signals for a single stock."""
    try:
        ind = get_indicators(symbol)
        if not ind:
            return None
        sig = compute_signals(ind)
        return {
            "symbol": symbol,
            "indicators": ind,
            "signals": sig
        }
    except Exception as e:
        logger.error(f"Error scanning stock {symbol}: {e}")
        return None

def fetch_sector_news(sector: str) -> list:
    """Fetches sector-wide news to provide context for stock movements."""
    query = SECTOR_NEWS_QUERIES.get(sector, f"{sector} sector news India")
    try:
        return fetch_news(query, limit=4)
    except Exception as e:
        logger.error(f"Error fetching news for sector {sector}: {e}")
        return []

def run_sector_scanner(user_query: str) -> str:
    """
    Scans all 35 stocks across 7 sectors in parallel, fetches sector news,
    and uses LLM to generate trade recommendations with precise entry, target, and stop loss.
    """
    # 1. Scan all stocks in parallel
    all_symbols = []
    symbol_to_sector = {}
    for sector, symbols in SECTOR_MAP.items():
        all_symbols.extend(symbols)
        for sym in symbols:
            symbol_to_sector[sym] = sector
            
    scanned_data = {}
    logger.info(f"Scanning {len(all_symbols)} stocks in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(scan_stock, sym): sym for sym in all_symbols}
        for future in concurrent.futures.as_completed(futures):
            sym = futures[future]
            try:
                res = future.result()
                if res:
                    sector = symbol_to_sector[sym]
                    if sector not in scanned_data:
                        scanned_data[sector] = []
                    scanned_data[sector].append(res)
            except Exception as e:
                logger.error(f"Failed to scan {sym}: {e}")

    # 2. Fetch sector news in parallel
    logger.info("Fetching sector news in parallel...")
    sector_news = {}
    sectors = list(SECTOR_MAP.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(fetch_sector_news, sec): sec for sec in sectors}
        for future in concurrent.futures.as_completed(futures):
            sec = futures[future]
            try:
                sector_news[sec] = future.result()
            except Exception as e:
                logger.error(f"Failed to fetch news for {sec}: {e}")

    # 3. Retrieve latest daily market report for extra context
    from agent import get_latest_market_report
    report_context = get_latest_market_report()

    # 4. Synthesize prompt for LLM
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY
    )
    
    prompt = (
        "You are a lead trading strategist and technical analyst.\n"
        "Your task is to analyze the technical indicators, trend signals, and news context for stocks across 7 sectors:\n"
        "IT, Energy, Power, Metal, Bank, Health, and Government (PSUs).\n\n"
        "For EACH sector, select the top 3 stocks that exhibit the most promising setups for growth this week based on:\n"
        "- Trend Bias (bullish/neutral)\n"
        "- Momentum (RSI, avoiding overbought unless strong breakout, favoring oversold/neutral turning up)\n"
        "- Structure (favoring breakouts above 20-day averages)\n"
        "- Sector News & Market Context\n\n"
        "For EACH selected stock, you MUST provide:\n"
        "1. Precise Stock Name and NSE Symbol (e.g. Tata Consultancy Services - TCS)\n"
        "2. Current Price\n"
        "3. Actionable Trade Setup Plan:\n"
        "   - Entry Range (specific price range to buy)\n"
        "   - Target Price (expected upside level)\n"
        "   - Stop Loss (price level to cut losses, helping manage the risk of losing money)\n"
        "   - Risk/Reward Ratio\n"
        "4. Precise Rationale (combining technical indicators and news catalysts)\n\n"
        "Structure the report beautifully in Markdown:\n"
        "- Use clean tables or callout blocks for trade setups.\n"
        "- Add a general 'Risk Management & Trading Guidelines' section at the end detailing position sizing, stop-loss adherence, and capital protection.\n"
        "- Include a prominent disclaimer stating that this is an AI-generated analysis based on technical configurations and public news, not financial advice.\n\n"
        f"--- SCANNED TECHNICAL DATA ---\n{json.dumps(scanned_data, default=str)}\n\n"
        f"--- SECTOR NEWS CONTEXT ---\n{json.dumps(sector_news, default=str)}\n\n"
        f"--- LATEST REPORT CONTEXT ---\n{report_context}\n"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional technical analyst and risk manager. Generate a detailed, actionable swing trading report. Be objective and precise with price numbers."
                },
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content if response and response.choices else None
        if not content:
            return "❌ The LLM returned an empty response. Please try again in a moment."
        return content
    except Exception as e:
        logger.error(f"Error in LLM sector scan synthesis: {e}")
        return f"❌ Failed to generate sector scan report: {e}"
