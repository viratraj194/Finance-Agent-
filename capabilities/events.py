from datetime import datetime, timedelta
from typing import Dict, Optional, List
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.news import fetch_news
from providers.yahoo import get_market_data, search_symbol

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)


def get_macro_queries_via_ai(asset_name: str) -> str:
    """Uses LLM to dynamically formulate a macro/sector search query for the asset's industry."""
    prompt = (
        f"For the company/stock \"{asset_name}\", identify its primary business industry in India "
        f"and generate a highly concise 2-word or 3-word search query for news search engines "
        f"that captures the sector-wide demand or major government policy shifts affecting it.\n\n"
        f"Examples:\n"
        f"- Tata Motors -> 'India EV policy'\n"
        f"- HDFC Bank -> 'India banking regulation'\n"
        f"- JPPOWER -> 'India power demand'\n\n"
        f"Output ONLY the 2-3 word search query without any quotes or punctuation."
    )
    try:
        response = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[
                {"role": "system", "content": "You are a precise search query generator. Output only a 2-3 word query. No conversational filler."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        query = response.choices[0].message.content.strip().replace('"', '').replace('.', '').strip()
        # Enforce length limit
        if len(query.split()) > 4:
            query = " ".join(query.split()[:3])
        return query if query and query.lower() != "none" else f"{asset_name} sector India"
    except Exception:
        return f"{asset_name} sector India"


def get_asset_events(
    asset_name: str,
    lookback_days: int = 7,
    max_events: int = 5
) -> Dict:
    """
    Aggregates news events (both company-specific and sectoral macro/policy shifts) and corporate actions.
    """
    # 1. Fetch Company Specific News
    company_news = fetch_news(asset_name, limit=max_events)
    for item in company_news:
        item["category"] = "company_specific"

    # 2. Fetch Sector & Macro/Government Policy News
    macro_query = get_macro_queries_via_ai(asset_name)
    macro_news = fetch_news(macro_query, limit=max_events)
    for item in macro_news:
        item["category"] = "sector_macro_policy"

    # Merge news
    all_news = company_news + macro_news
    
    # 3. Fetch Corporate Actions
    symbol = search_symbol(asset_name)
    corporate_actions = []
    if symbol:
        data = get_market_data(symbol)
        if data:
            corporate_actions = data.get("recent_actions", [])

    return {
        "asset": asset_name,
        "symbol": symbol,
        "news_events": all_news,
        "corporate_actions": corporate_actions,
        "confidence": "high" if all_news or corporate_actions else "low",
        "macro_policy_focus": macro_query
    }

