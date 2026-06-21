from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.yahoo import search_symbol

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

SYSTEM_PROMPT = """
You are a financial reference assistant.

Rules:
- Explain what the asset is, not whether it is good or bad
- Do NOT give investment advice
- Do NOT mention prices or performance
- Keep explanations neutral, factual, and concise
- If unsure, say so clearly
"""


def get_asset_context(asset_query: str) -> dict | None:
    """
    Returns basic context about an asset.
    """
    symbol = search_symbol(asset_query)

    if not symbol:
        return None

    prompt = (
        f"Asset identifier:\n"
        f"- Query: {asset_query}\n"
        f"- Symbol: {symbol}\n\n"
        "Explain in 2–3 sentences:\n"
        "- What this asset represents\n"
        "- The sector or category it belongs to\n"
        "- What kind of business or exposure it has\n\n"
        "Do not include prices, performance, or opinions."
    )

    try:
        response = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content if response and response.choices else None
    except Exception:
        content = None

    return {
        "symbol": symbol,
        "description": content or "Details temporarily unavailable."
    }
