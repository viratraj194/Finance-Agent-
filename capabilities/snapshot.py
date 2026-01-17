from providers.yahoo import get_market_data, search_symbol


def get_market_snapshot(user_text: str):
    symbol = search_symbol(user_text)

    if not symbol:
        return {
            "resolved": False
        }

    data = get_market_data(symbol)

    if not data:
        return {
            "resolved": True,
            "data_available": False,
            "symbol": symbol
        }

    direction = (
        "up" if data["change"] > 0
        else "down" if data["change"] < 0
        else "flat"
    )

    return {
        "resolved": True,
        "data_available": True,
        "symbol": symbol,
        "price": data["price"],
        "prev_close": data["prev_close"],
        "prev_date": data["prev_date"],
        "change": data["change"],
        "change_pct": data["change_pct"],
        "direction": direction
    }
