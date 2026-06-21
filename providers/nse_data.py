"""
NSE India Data Provider
Fetches real-time institutional data from NSE's public APIs (no API key required).

Data available:
- FII/DII daily buying/selling flows (most critical market direction signal)
- Market breadth (advances vs declines)
- Top gainers and losers
- 52-week high/low stocks
- Block deals
- Circuit filter stocks (upper/lower)
"""

import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# NSE requires a browser-like session to serve data
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

NSE_BASE = "https://www.nseindia.com"


def _get_nse_session() -> requests.Session:
    """Creates a session with NSE cookies. NSE requires a 2-step cookie fetch."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        # Step 1: Hit homepage to set initial cookies
        r1 = session.get(f"{NSE_BASE}/", timeout=12)
        logger.debug(f"NSE homepage: {r1.status_code}, cookies: {dict(session.cookies)}")
        # Step 2: Hit a data page to refresh/get API cookies
        r2 = session.get(f"{NSE_BASE}/market-data/live-equity-market?symbol=NIFTY 50", timeout=12)
        logger.debug(f"NSE market page: {r2.status_code}, cookies: {dict(session.cookies)}")
    except Exception as e:
        logger.debug(f"NSE session init warning: {e}")
    return session


def _nse_api_get(path: str) -> dict | list | None:
    """Single-session NSE API call — session must be kept alive between homepage and API."""
    session = _get_nse_session()
    try:
        url = f"{NSE_BASE}{path}"
        resp = session.get(url, timeout=15)
        logger.debug(f"NSE API {path}: status={resp.status_code}, content-length={resp.headers.get('Content-Length','?')}, encoding={resp.encoding}")
        if resp.status_code == 200:
            # NSE uses gzip — use resp.json() which handles decompression automatically
            try:
                return resp.json()
            except Exception:
                # Try decoding content directly
                content = resp.content
                if content:
                    import json
                    try:
                        return json.loads(content)
                    except Exception:
                        # Attempt to strip out any non-JSON framing/junk
                        try:
                            text_content = content.decode('utf-8', errors='ignore')
                            start_idx = -1
                            for i, c in enumerate(text_content):
                                if c in ('{', '['):
                                    start_idx = i
                                    break
                            
                            end_idx = -1
                            for i in range(len(text_content) - 1, -1, -1):
                                if text_content[i] in ('}', ']'):
                                    end_idx = i
                                    break
                                    
                            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                                clean_json = text_content[start_idx:end_idx+1]
                                return json.loads(clean_json)
                        except Exception:
                            pass
                logger.warning(f"NSE API {path}: could not parse JSON. Content preview: {resp.content[:100]}")
        return None
    except Exception as e:
        logger.error(f"NSE API call failed for {path}: {e}")
        return None


def get_fii_dii_data() -> dict:
    """
    Fetch FII/DII institutional flow data.
    Uses nse_urlfetch to query the live provisional FII/DII API endpoint.
    Falls back to Economic Times RSS headlines on error.
    """
    from nselib.libutil import nse_urlfetch

    # Try live provisional API via nse_urlfetch
    try:
        url = "https://www.nseindia.com/api/fiidiiTradeReact"
        resp = nse_urlfetch(url, origin_url="https://www.nseindia.com/market-data/fii-dii")
        if resp.status_code == 200 and resp.text.strip():
            data = resp.json()
            if data:
                # Format: [{'buyValue': '...', 'category': 'DII', 'date': '...', 'netValue': '...', 'sellValue': '...'}, ...]
                fii_entry = next((d for d in data if "FII" in str(d.get("category", ""))), {})
                dii_entry = next((d for d in data if str(d.get("category", "")) == "DII"), {})

                def parse_val(v):
                    try:
                        return float(str(v).replace(",", ""))
                    except Exception:
                        return 0.0

                fii_net = parse_val(fii_entry.get("netValue", 0))
                dii_net = parse_val(dii_entry.get("netValue", 0))
                return {
                    "date": fii_entry.get("date", "N/A"),
                    "source": "NSE Provisional API",
                    "fii": {
                        "buy_value": fii_entry.get("buyValue"),
                        "sell_value": fii_entry.get("sellValue"),
                        "net_value": fii_entry.get("netValue"),
                        "sentiment": "BUYING 🟢" if fii_net > 0 else "SELLING 🔴"
                    },
                    "dii": {
                        "buy_value": dii_entry.get("buyValue"),
                        "sell_value": dii_entry.get("sellValue"),
                        "net_value": dii_entry.get("netValue"),
                        "sentiment": "BUYING 🟢" if dii_net > 0 else "SELLING 🔴"
                    },
                    "interpretation": (
                        "💪 BOTH BUYING — Very Bullish" if fii_net > 0 and dii_net > 0
                        else "🔴 BOTH SELLING — Very Bearish" if fii_net < 0 and dii_net < 0
                        else "🤝 DII supporting market while FII exits — Cautious Bullish" if fii_net < 0 and dii_net > 0
                        else "⚠️ FII buying but DII cautious — Mixed signal"
                    )
                }
    except Exception as e:
        logger.debug(f"NSE live FII/DII API failed: {e}")

    # Fallback: fetch FII/DII news from Economic Times RSS
    try:
        rss_url = "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"
        resp = requests.get(rss_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            import feedparser
            feed = feedparser.parse(resp.content)
            fii_news = [
                e.get("title", "") for e in feed.entries[:20]
                if any(k in e.get("title", "").upper() for k in ["FII", "DII", "FOREIGN", "INSTITUTIONAL"])
            ]
            if fii_news:
                return {
                    "source": "Economic Times RSS (news-based)",
                    "fii_dii_headlines": fii_news[:5],
                    "note": "Live institutional data temporarily unavailable. Here are the latest FII/DII news headlines."
                }
    except Exception as e:
        logger.debug(f"ET RSS FII/DII fallback failed: {e}")

    return {"error": "FII/DII data temporarily unavailable. NSE bot protection active."}


def get_market_breadth() -> dict:
    """
    Fetch market breadth data: advances vs declines across NSE.
    Returns empty dict gracefully since the direct endpoint is heavily blocked.
    """
    return {}


def get_nse_most_active() -> dict:
    """Fetch most active stocks/gainers using nselib."""
    try:
        import pandas as pd
        from nselib import capital_market
        
        df = capital_market.top_gainers_or_losers('gainers')
        if isinstance(df, pd.DataFrame) and not df.empty:
            gainers = []
            # Take top 10 gainers across the entire market
            for _, row in df.head(10).iterrows():
                gainers.append({
                    "symbol": row.get("symbol"),
                    "ltp": row.get("ltp"),
                    "change_pct": row.get("perChange"),
                })
            return {"top_gainers": gainers}
        return {"top_gainers": []}
    except Exception as e:
        logger.error(f"Error fetching NSE gainers via nselib: {e}")
        return {"error": str(e)}


def get_block_deals() -> list:
    """Fetch block deals using nselib (large institutional trades)."""
    try:
        import pandas as pd
        from nselib import capital_market
        
        # Try 1D first, fall back to 1W if empty
        df = capital_market.block_deals_data(period='1D')
        if not isinstance(df, pd.DataFrame) or df.empty:
            df = capital_market.block_deals_data(period='1W')
            
        if isinstance(df, pd.DataFrame) and not df.empty:
            deals = []
            for _, row in df.iterrows():
                deals.append({
                    "symbol": row.get("Symbol"),
                    "client_name": row.get("ClientName"),
                    "deal_type": row.get("Buy/Sell"),
                    "quantity": row.get("QuantityTraded"),
                    "price": row.get("TradePrice/Wght.Avg.Price"),
                    "date": row.get("Date"),
                })
            return deals[:10]
        return []
    except Exception as e:
        logger.error(f"Error fetching block deals via nselib: {e}")
        return []


def get_nse_circuit_stocks() -> dict:
    """
    Returns upper/lower circuit limits gracefully.
    Since circuit index parameters are deprecated/restricted by NSE, returns empty lists.
    """
    return {"upper_circuit": [], "lower_circuit": []}


def get_fii_derivatives_data() -> dict | None:
    """
    Fetches the most recent FII derivatives statistics.
    Searches back up to 15 days to find the latest available trading day.
    """
    try:
        from nselib import derivatives
        import pandas as pd
        from datetime import datetime, timedelta

        d = datetime.now()
        for i in range(15):
            dt_str = (d - timedelta(days=i)).strftime('%d-%m-%Y')
            try:
                df = derivatives.fii_derivatives_statistics(dt_str)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    stats = []
                    for _, row in df.iterrows():
                        stats.append({
                            "instrument": row.get("fii_derivatives"),
                            "buy_val": row.get("buy_value_in_Cr"),
                            "sell_val": row.get("sell_value_in_Cr"),
                            "oi_val": row.get("open_contracts_value_in_Cr")
                        })
                    return {
                        "date": dt_str,
                        "stats": stats
                    }
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Error fetching FII derivatives data: {e}")
    return None


def get_insider_trading() -> list:
    """
    Fetch recent Prohibition of Insider Trading (PIT) disclosures.
    Tracks Promoters and Directors buying their own company's stock from the open market.
    """
    try:
        data = _nse_api_get("/api/corporates-pit?index=equities")
        if data and "data" in data:
            results = []
            for item in data["data"]:
                # Filter for Promoters/Directors buying stock (Market Purchase)
                person_cat = str(item.get("personCategory", ""))
                acq_mode = str(item.get("acqMode", ""))
                
                if person_cat in ["Promoters", "Director", "Promoter Group"] and acq_mode in ["Market Purchase", "Acquisition"]:
                    try:
                        sec_val = float(str(item.get("secVal", "0")).replace(",", ""))
                    except ValueError:
                        sec_val = 0.0
                        
                    # Only log significant purchases (> 10 Lakhs)
                    if sec_val > 1000000:
                        results.append({
                            "symbol": item.get("symbol"),
                            "person": item.get("acqName"),
                            "category": person_cat,
                            "buy_value_inr": sec_val,
                            "date": item.get("date")
                        })
            
            # Return top 5 largest insider buys
            results.sort(key=lambda x: x.get("buy_value_inr", 0), reverse=True)
            return results[:5]
    except Exception as e:
        logger.error(f"Error fetching insider trading data: {e}")
    return []


def get_nse_full_snapshot() -> dict:
    """
    Aggregates all NSE data into a single comprehensive market snapshot.
    Used by the daily report and geo impact analyzer.
    """
    import concurrent.futures
    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(get_fii_dii_data): "fii_dii",
            executor.submit(get_fii_derivatives_data): "fii_derivatives",
            executor.submit(get_block_deals): "block_deals",
            executor.submit(get_nse_most_active): "top_gainers",
            executor.submit(get_nse_circuit_stocks): "circuit_stocks",
            executor.submit(get_insider_trading): "insider_trading",
        }
        for future, key in futures.items():
            try:
                result[key] = future.result()
            except Exception as e:
                result[key] = {"error": str(e)}
    return result
