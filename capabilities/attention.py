from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.reddit import fetch_reddit_posts

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)


def get_social_macro_query_via_ai(asset_name: str) -> str:
    """Uses LLM to dynamically formulate a sector/momentum discussion search query for Reddit."""
    prompt = (
        f"For the company/stock \"{asset_name}\", identify its primary business industry in India "
        f"and generate a highly concise 2-word search query for popular Indian finance discussion forums (like Reddit) "
        f"that captures general retail investor interest, sector momentum, or trend talk.\n\n"
        f"Examples:\n"
        f"- Tata Motors -> 'EV stocks'\n"
        f"- HDFC Bank -> 'banking stocks'\n"
        f"- JPPOWER -> 'power stocks'\n\n"
        f"Output ONLY the 2-word search query without any quotes or punctuation."
    )
    try:
        response = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[
                {"role": "system", "content": "You are a precise search query generator. Output only a 2-word query. No conversational filler."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        query = response.choices[0].message.content.strip().replace('"', '').replace('.', '').strip()
        # Enforce length limit
        if len(query.split()) > 3:
            query = " ".join(query.split()[:2])
        return query if query and query.lower() != "none" else f"{asset_name} stocks"
    except Exception:
        return f"{asset_name} stocks"


def get_social_attention(asset_name: str, max_posts: int = 6):
    # 1. Fetch Company Specific Discussions
    company_posts = fetch_reddit_posts(asset_name, limit=max_posts)
    for p in company_posts:
        p["category"] = "company_specific"

    # 2. Fetch Sector & Macro Momentum Discussions
    macro_query = get_social_macro_query_via_ai(asset_name)
    sector_posts = fetch_reddit_posts(macro_query, limit=max_posts)
    for p in sector_posts:
        p["category"] = "sector_macro"

    # Merge posts
    all_posts = company_posts + sector_posts

    if not all_posts:
        return {
            "asset": asset_name,
            "status": "no_signal",
            "posts": [],
            "analysis_input": None,
        }

    # Prepare structured text for AI reasoning
    discussion_points = []
    for p in all_posts:
        discussion_points.append(
            f"- [{p['category'].upper()}] ({p['subreddit']}, score {p['score']}): {p['title']}"
        )

    analysis_input = (
        f"Reddit discussions related to {asset_name} and its broader sector (Query: '{macro_query}'):\n\n"
        + "\n".join(discussion_points)
        + "\n\nAnalyze the above discussions as an active sector analyst.\n"
          "Identify:\n"
          "1. Sectoral Catalysts: Is the sector experiencing active tailwinds, demand growth, or government investments?\n"
          "2. Company Sentiment vs Sector Sentiment: How do retail investors view the specific company compared to the overall sector trend?\n"
          "3. Risks & Volatility: Are there warnings of cyclical corrections, policy bottlenecks, or speculative hypes?\n"
          "4. Stock Move Implications: Based on the demand trends and government decisions discussed, what moves are investors anticipating?\n"
          "Do NOT give direct buy/sell advice.\n"
          "Do NOT predict precise target prices.\n"
    )

    return {
        "asset": asset_name,
        "status": "signal_present",
        "posts": all_posts,
        "analysis_input": analysis_input,
        "social_macro_focus": macro_query
    }

