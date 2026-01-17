from typing import Dict


def compute_signals(indicators: Dict) -> Dict:
    """
    Computes descriptive technical states from indicator values.
    No advice, no prediction — labels only.
    """

    price = indicators["price"]
    sma_50 = indicators["sma_50"]
    sma_200 = indicators["sma_200"]
    rsi = indicators["rsi_14"]

    # ---- Trend Bias ----
    if price > sma_50 and sma_50 > sma_200:
        trend = "bullish"
        trend_reason = "price > 50-day SMA and 50-day SMA > 200-day SMA"
    elif price < sma_50 and sma_50 < sma_200:
        trend = "bearish"
        trend_reason = "price < 50-day SMA and 50-day SMA < 200-day SMA"
    else:
        trend = "neutral"
        trend_reason = "mixed positioning relative to key moving averages"

    # ---- Momentum (RSI) ----
    if rsi >= 70:
        momentum = "overbought"
        momentum_reason = "RSI is at or above 70"
    elif rsi <= 30:
        momentum = "oversold"
        momentum_reason = "RSI is at or below 30"
    else:
        momentum = "neutral"
        momentum_reason = "RSI is between 30 and 70"

    # ---- Structure (simple breakout/breakdown proxy) ----
    # We approximate 20-day structure using SMA-20 positioning
    sma_20 = indicators["sma_20"]
    if price > sma_20:
        structure = "breakout"
        structure_reason = "price is above its 20-day average"
    elif price < sma_20:
        structure = "breakdown"
        structure_reason = "price is below its 20-day average"
    else:
        structure = "none"
        structure_reason = "price is near its 20-day average"

    return {
        "trend": trend,
        "trend_reason": trend_reason,
        "momentum": momentum,
        "momentum_reason": momentum_reason,
        "structure": structure,
        "structure_reason": structure_reason,
    }
