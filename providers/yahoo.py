import yfinance as yf
import datetime
import logging

# Suppress yfinance internal error logging to keep the console clean
yf_logger = logging.getLogger('yfinance')
yf_logger.setLevel(logging.CRITICAL)

def search_symbol(query: str):
    """
    Resolve a company name or ticker to a Yahoo symbol.
    Returns symbol string or None.
    """
    try:
        query = query.strip()
        # Check if the query itself is a valid NSE symbol (e.g., RELIANCE.NS)
        if query.upper().endswith(".NS"):
             return query.upper()
        
        # If query is a plain ticker like RELIANCE, try it with .NS
        if len(query.split()) == 1 and query.isalnum():
            ticker_ns = f"{query.upper()}.NS"
            try:
                s = yf.Ticker(ticker_ns)
                # Use history(period="1d") as it's the quietest way to verify existence
                if not s.history(period="1d").empty:
                    return ticker_ns
            except Exception:
                pass

        # Search for the symbol
        search = yf.Search(query, max_results=8)
        results = getattr(search, 'quotes', [])
        
        for item in results:
            # Match NSE or BSE or ETFs
            if item.get("exchange") in ["NSI", "BSE"] or item.get("quoteType") == "ETF":
                return item.get("symbol")
        return None
    except Exception:
        return None


def get_market_data(symbol: str):
    try:
        stock = yf.Ticker(symbol)
        
        # Fetch history first - it is the most reliable and quiet call
        hist = stock.history(period="5d")
        if hist.empty or len(hist) < 2:
            return None

        latest = hist.iloc[-1]
        previous = hist.iloc[-2]

        price = round(float(latest["Close"]), 2)
        prev_close = round(float(previous["Close"]), 2)
        prev_date = previous.name.date().isoformat()

        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

        # Attempt to get fundamentals gracefully
        fundamentals = {}
        try:
            # fast_info is reliable and doesn't usually trigger 404 logs
            fast = stock.fast_info
            fundamentals = {
                "market_cap": getattr(fast, 'market_cap', None),
                "fifty_two_week_high": getattr(fast, 'year_high', None),
                "fifty_two_week_low": getattr(fast, 'year_low', None),
                "quote_type": getattr(fast, 'quote_type', None),
                "currency": getattr(fast, 'currency', None),
            }
            
            # Only try .info if we have a clear need, as it is the 404 culprit
            # For now, we wrap it very tightly
            info = stock.info
            if info:
                fundamentals.update({
                    "pe_ratio": info.get("trailingPE"),
                    "dividend_yield": info.get("dividendYield"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "long_name": info.get("longName"),
                })
        except Exception:
            pass

        # Corporate Actions
        recent_actions = []
        try:
            # .actions can also be fragile
            actions = stock.actions
            if actions is not None and not actions.empty:
                cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
                recent = actions[actions.index >= cutoff.strftime('%Y-%m-%d')]
                for date, row in recent.iterrows():
                    if row["Dividends"] > 0:
                        recent_actions.append(f"Dividend: ₹{row['Dividends']} on {date.date()}")
                    if row["Stock Splits"] > 0:
                        recent_actions.append(f"Stock Split: {row['Stock Splits']} on {date.date()}")
        except Exception:
            pass

        return {
            "price": price,
            "prev_close": prev_close,
            "prev_date": prev_date,
            "change": change,
            "change_pct": change_pct,
            "open": round(float(latest["Open"]), 2),
            "high": round(float(latest["High"]), 2),
            "low": round(float(latest["Low"]), 2),
            "fundamentals": fundamentals,
            "recent_actions": recent_actions
        }

    except Exception:
        return None
