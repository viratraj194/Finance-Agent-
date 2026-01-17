import yfinance as yf
from datetime import datetime


TIMEFRAME_MAP = {
    "1m": {"period": "2mo", "interval": "1d"},
    "3m": {"period": "4mo", "interval": "1d"},
    "6m": {"period": "7mo", "interval": "1d"},
    "1y": {"period": "13mo", "interval": "1d"},
    "3y": {"period": "4y", "interval": "1d"},
    "5y": {"period": "6y", "interval": "1d"},
}


def get_performance(symbol: str, timeframe: str) -> dict | None:
    """
    Returns performance (absolute and percentage change) over a timeframe.
    """

    if timeframe not in TIMEFRAME_MAP:
        return None

    params = TIMEFRAME_MAP[timeframe]

    try:
        stock = yf.Ticker(symbol)
        data = stock.history(
            period=params["period"],
            interval=params["interval"]
        )

        if data.empty or len(data) < 2:
            return None

        start_price = float(data["Close"].iloc[0])
        end_price = float(data["Close"].iloc[-1])

        change = round(end_price - start_price, 2)
        change_pct = round((change / start_price) * 100, 2)

        start_date = data.index[0].date().isoformat()
        end_date = data.index[-1].date().isoformat()

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "change": change,
            "change_pct": change_pct,
            "start_date": start_date,
            "end_date": end_date
        }

    except Exception:
        return None
