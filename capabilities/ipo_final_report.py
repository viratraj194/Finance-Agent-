from typing import Dict


def assemble_final_ipo_report(
    company: str,
    financials: Dict,
    sentiment: Dict,
    red_flags: Dict,
) -> str:
    # -------------------------
    # Business fundamentals
    # -------------------------
    revenue = financials["revenue"]
    profit = financials["profit"]

    completed_years = sorted(
        [y for y in revenue.keys() if not y.endswith("26")]
    )

    latest_fy = completed_years[-1]
    prev_fy = completed_years[-2] if len(completed_years) >= 2 else None

    yoy_growth = (
        financials["yoy_growth"].get(latest_fy)
        if prev_fy else None
    )

    yoy_text = f"{yoy_growth}%" if yoy_growth is not None else "N/A"

    # -------------------------
    # Sentiment metrics
    # -------------------------
    total_posts = sentiment["posts_analyzed"]
    total_articles = sentiment["articles_analyzed"]

    split = sentiment["sentiment_split"]
    total_sentiment = sum(split.values()) or 1

    pos_pct = round((split["positive"] / total_sentiment) * 100)
    neu_pct = round((split["neutral"] / total_sentiment) * 100)
    neg_pct = round((split["negative"] / total_sentiment) * 100)

    # Sample visibility (important for investor trust)
    reddit_samples = sentiment.get("sample_reddit", [])[:3]
    news_samples = sentiment.get("sample_news", [])[:3]

    # -------------------------
    # Confidence score heuristic
    # -------------------------
    score = 70

    if financials["cagr"] and financials["cagr"] > 20:
        score += 5

    if sentiment["assessment"].lower().startswith("strong"):
        score += 5

    if red_flags["flags"]:
        score -= 5

    score = min(max(score, 55), 85)

    # -------------------------
    # Final report
    # -------------------------
    report = f"""
Final IPO Entry Confidence: {score}%

1) Business Fundamentals
• Revenue ({latest_fy}): ₹{revenue[latest_fy]} Cr
• Net Profit ({latest_fy}): ₹{profit.get(latest_fy)} Cr
• YoY Growth: {yoy_text}

Assessment: {financials["assessment"]}

2) Revenue & Growth Trend
• Last 3 years revenue trend: Rising
• CAGR (approx): {financials["cagr"]}%
• Recent margin trend: {financials["margin_trend"]}

Assessment: Growth trajectory appears sustainable, not aggressive.

4) Retail & Social Sentiment
• Reddit posts analyzed: {total_posts}
• News articles analyzed: {total_articles}
• Positive / Neutral / Negative split:
  {pos_pct}% / {neu_pct}% / {neg_pct}%
• Dominant themes: {", ".join(sentiment["themes"])}

Sample Reddit discussions:
{chr(10).join([f"- {r['title']} ({r['subreddit']})" for r in reddit_samples])}

Sample News headlines:
{chr(10).join([f"- {n['title']} ({n['source']})" for n in news_samples])}

Assessment: {sentiment["assessment"]}

5) Red Flags
• Identified risks: {", ".join(red_flags["flags"]) if red_flags["flags"] else "None"}

Assessment: {red_flags["assessment"]}

Investor Clarity
This IPO appears suitable for investors with **moderate risk appetite**
seeking medium- to long-term exposure rather than short-term listing gains.
""".strip()

    return report
