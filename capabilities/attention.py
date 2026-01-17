from providers.reddit import fetch_reddit_posts


def get_social_attention(asset_name: str, max_posts: int = 6):
    posts = fetch_reddit_posts(asset_name, limit=max_posts)

    if not posts:
        return {
            "asset": asset_name,
            "status": "no_signal",
            "posts": [],
            "analysis_input": None,
        }

    # Prepare structured text for AI reasoning (NOT sentiment score)
    discussion_points = []

    for p in posts:
        discussion_points.append(
            f"- ({p['subreddit']}, score {p['score']}): {p['title']}"
        )

    analysis_input = (
        f"Reddit discussions related to {asset_name}:\n\n"
        + "\n".join(discussion_points)
        + "\n\nAnalyze the above discussions as a conservative investor.\n"
          "Identify:\n"
          "1. The dominant narrative or concern\n"
          "2. The overall emotional tone (calm, concerned, fearful, mixed)\n"
          "3. Whether this appears to be short-term noise, "
          "medium-term uncertainty, or a potential long-term thesis risk\n"
          "4. How strong or weak the signal is based on repetition and clarity\n"
          "Do NOT give buy/sell advice.\n"
          "Do NOT predict price.\n"
    )

    return {
        "asset": asset_name,
        "status": "signal_present",
        "posts": posts,
        "analysis_input": analysis_input,
    }
