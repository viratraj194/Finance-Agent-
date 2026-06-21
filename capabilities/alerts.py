import json
from datetime import datetime
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.finnhub import get_market_news

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
MODEL = "meta/llama-3.3-70b-instruct"

def get_overnight_alerts(watchlist: list = None) -> str:
    """
    Generates alerts for overnight events impacting a watchlist of stocks.
    """
    if not watchlist:
        watchlist = ["Reliance", "TCS", "HDFC Bank", "Infosys"]

    news = get_market_news("general")
    news_subset = news[:15] if isinstance(news, list) else []

    prompt = (
        f"Watchlist: {', '.join(watchlist)}\n"
        f"Overnight Market News:\n{json.dumps(news_subset, default=str)}\n\n"
        "Scan the news for events that could impact the watchlist stocks today. "
        "Generate a prioritized alert list (Critical/High/Medium/Low). "
        "Include a brief AI assessment of the impact for each alert."
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a risk management and alert system for Indian stocks."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content or "Error generating alerts."
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"📅 {current_time}\n\n{content}"
    except Exception as e:
        return f"Alert generation error: {e}"
