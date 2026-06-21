import json
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.finnhub import get_company_news

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
MODEL = "meta/llama-3.3-70b-instruct"

def analyze_news_sentiment(company_name: str) -> str:
    """
    Aggregates news for a specific stock and uses LLM to score sentiment as Bullish/Bearish/Neutral.
    """
    from providers.yahoo import search_symbol
    symbol = search_symbol(company_name)
    if not symbol:
        return f"Could not resolve symbol for {company_name}"
        
    # Remove .NS for finnhub search if necessary, but finnhub takes standard queries
    # Finnhub may not have all Indian stocks, but we try:
    ticker = symbol.replace(".NS", "")
    news = get_company_news(ticker, days_back=3)
    
    if not news or len(news) == 0:
        return f"No recent news found for {company_name} ({ticker})."

    prompt = (
        f"Recent news for {company_name} ({ticker}):\n{json.dumps(news[:10], default=str)}\n\n"
        "Analyze the sentiment of these news articles. "
        "1. Give an overall Sentiment Score (-100 to +100).\n"
        "2. Categorize as Bullish, Bearish, or Neutral.\n"
        "3. Identify key themes and catalysts.\n"
        "4. Provide a brief trading perspective based solely on this sentiment."
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a quantitative news sentiment analyst."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content or "Error analyzing sentiment."
    except Exception as e:
        return f"Sentiment analysis error: {e}"
