import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd


# Map friendly timeframes to yfinance parameters
TIMEFRAME_MAP = {
    # Intraday (SAFE combinations)
    "1h": {"period": "1d", "interval": "5m"},
    "4h": {"period": "1d", "interval": "5m"},
    "today": {"period": "1d", "interval": "5m"},

    # Daily / longer
    "1d": {"period": "2d", "interval": "1d"},
    "1w": {"period": "7d", "interval": "1d"},
    "1m": {"period": "1mo", "interval": "1d"},
    "3m": {"period": "3mo", "interval": "1d"},
    "6m": {"period": "6mo", "interval": "1d"},
    "1y": {"period": "1y", "interval": "1d"},
    "5y": {"period": "5y", "interval": "1d"},
}



def get_high_low(symbol: str, timeframe: str) -> dict | None:
    """
    Returns high and low price for a given symbol and timeframe.
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
        if timeframe in ["1h", "4h"]:
            now = datetime.now(data.index.tz)
            hours = 1 if timeframe == "1h" else 4
            cutoff = now - timedelta(hours=hours)
            data = data[data.index >= cutoff]

        if data.empty:
            return None

        high = round(float(data["High"].max()), 2)
        low = round(float(data["Low"].min()), 2)

        start_date = data.index.min().date().isoformat()
        end_date = data.index.max().date().isoformat()

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "high": high,
            "low": low,
            "start_date": start_date,
            "end_date": end_date
        }

    except Exception:
        return None
