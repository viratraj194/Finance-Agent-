import json
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.yahoo import search_symbol, get_market_data
from providers.nse_data import get_fii_dii_data
from providers.finnhub import get_market_news
from providers.gift_nifty import get_gift_nifty

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
MODEL = "meta/llama-3.3-70b-instruct"

def get_premarket_dashboard() -> str:
    """
    Aggregates overnight data before 9:15 AM:
    GIFT Nifty, US markets close, Asian markets open, FII/DII data, overnight news.
    """
    dashboard_data = {}
    
    # 1. US Markets Close (S&P 500, NASDAQ)
    us_markets = ["^GSPC", "^IXIC"]
    us_data = {}
    for sym in us_markets:
        data = get_market_data(sym)
        us_data[sym] = {"price": data.get("price"), "change_pct": data.get("change_pct")}
    dashboard_data["US_Markets"] = us_data
    
    # 2. Asian Markets Open (Nikkei, Hang Seng)
    asian_markets = ["^N225", "^HSI"]
    asian_data = {}
    for sym in asian_markets:
        data = get_market_data(sym)
        asian_data[sym] = {"price": data.get("price"), "change_pct": data.get("change_pct")}
    dashboard_data["Asian_Markets"] = asian_data
    
    # 3. GIFT Nifty
    dashboard_data["GIFT_Nifty"] = get_gift_nifty()
    
    # 4. FII/DII Data
    fii_dii = get_fii_dii_data()
    dashboard_data["FII_DII"] = fii_dii if isinstance(fii_dii, dict) else {"status": "Unavailable"}
    
    # 5. Overnight News
    news = get_market_news("general")
    dashboard_data["Top_News"] = news[:3] if isinstance(news, list) else []

    # AI Summarization
    prompt = (
        f"Pre-Market Data for today:\n{json.dumps(dashboard_data, default=str)}\n\n"
        "Generate a structured Pre-Market Dashboard for Indian stock market traders. "
        "Include sections for: Global Cues (US & Asia), GIFT Nifty indication, "
        "FII/DII Sentiment, and Top Overnight News. Provide a brief 'Expected Opening' "
        "prediction (Gap Up, Gap Down, or Flat) based on this data."
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a pre-market analyst for the NSE."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content or "Error generating dashboard."
    except Exception as e:
        return f"Pre-market dashboard error: {e}"
