import json
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.yahoo import search_symbol, get_market_data
from providers.finnhub import get_company_news

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
MODEL = "meta/llama-3.3-70b-instruct"

def scan_gap_opportunities(stocks: list = None) -> str:
    """
    Scans for potential gap-up or gap-down opportunities based on overnight news and momentum.
    """
    if not stocks:
        stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
    
    gap_data = {}
    for symbol in stocks:
        data = get_market_data(symbol)
        ticker = symbol.replace(".NS", "")
        news = get_company_news(ticker, days_back=1)
        gap_data[symbol] = {
            "price": data.get("price"),
            "change_pct": data.get("change_pct"),
            "latest_news": news[0] if news else None
        }

    prompt = (
        f"Overnight data for selected stocks:\n{json.dumps(gap_data, default=str)}\n\n"
        "Identify potential gap-up or gap-down opportunities for today's opening. "
        "Score the gap probability (High/Medium/Low) for each stock and explain why "
        "based on the previous close and recent news. Format as a clear, readable report."
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an expert day trader specializing in opening gaps."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content or "Error generating gap scan."
    except Exception as e:
        return f"Gap scan error: {e}"
