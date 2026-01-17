import yfinance as yf


def search_symbol(query: str):
    """
    Resolve a company name to a Yahoo symbol.
    Returns symbol string or None.
    """
    try:
        results = yf.Search(query, max_results=5).quotes
        for item in results:
            if item.get("exchange") == "NSI":  # NSE India
                return item.get("symbol")
        return None
    except Exception:
        return None


def get_market_data(symbol: str):
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="2d")

        if data.empty or len(data) < 2:
            return None

        latest = data.iloc[-1]
        previous = data.iloc[-2]

        price = round(latest["Close"], 2)
        prev_close = round(previous["Close"], 2)
        prev_date = previous.name.date().isoformat()

        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

        return {
            "price": price,
            "prev_close": prev_close,
            "prev_date": prev_date,
            "change": change,
            "change_pct": change_pct
        }

    except Exception:
        return None
