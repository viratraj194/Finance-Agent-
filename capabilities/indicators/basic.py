import yfinance as yf
import pandas as pd


def get_indicators(symbol: str) -> dict | None:
    """
    Computes basic technical indicators using daily data.
    Returns values only (no interpretation).
    """

    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1y", interval="1d")

        if data.empty or len(data) < 200:
            return None


        close = data["Close"]

        # Moving Averages
        sma_20 = float(close.rolling(window=20).mean().iloc[-1])
        sma_50 = float(close.rolling(window=50).mean().iloc[-1])
        sma_200 = float(close.rolling(window=200).mean().iloc[-1])

        ema_20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema_50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])

        # RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()

        rs = avg_gain / avg_loss
        rsi_14 = float((100 - (100 / (1 + rs))).iloc[-1])

        current_price = float(close.iloc[-1])

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "ema_20": round(ema_20, 2),
            "ema_50": round(ema_50, 2),
            "rsi_14": round(rsi_14, 2),
        }

    except Exception:
        return None
