from typing import Dict, Optional


def assemble_final_ipo_report(
    company: str,
    financials: Optional[Dict],
    sentiment: Dict,
    red_flags: Dict,
    ipo_doc: Optional[Dict] = None,
) -> str:

    # -------------------------
    # Confidence score (grounded)
    # -------------------------
    confidence = 60  # neutral base

    if financials:
        if financials.get("cagr") and financials["cagr"] > 15:
            confidence += 5
        if "strong" in financials["assessment"].lower():
            confidence += 5

    if sentiment["assessment"].lower().startswith("strong"):
        confidence += 5

    if red_flags["flags"]:
        confidence -= 5

    confidence = max(55, min(confidence, 80))

    # -------------------------
    # Business fundamentals block
    # -------------------------
    fundamentals_block = "Financial data not fully disclosed yet."

    if financials:
        revenue = financials["revenue"]
        profit = financials["profit"]

        latest_year = list(revenue.keys())[-1]
        prev_year = list(revenue.keys())[-2] if len(revenue) >= 2 else None
        yoy = financials["yoy_growth"].get(latest_year) if prev_year else None

        fundamentals_block = f"""
• Revenue ({latest_year}): ₹{revenue[latest_year]} Cr
• Net Profit ({latest_year}): ₹{profit.get(latest_year)} Cr
• YoY Growth: {yoy if yoy is not None else "N/A"}%
""".strip()

    # -------------------------
    # Sentiment samples
    # -------------------------
    reddit_samples = "\n".join(
        f"- {p['title']} ({p['subreddit']})"
        for p in sentiment.get("sample_reddit", [])[:3]
    )

    news_samples = "\n".join(
        f"- {a['title']}"
        for a in sentiment.get("sample_news", [])[:3]
    )

    # -------------------------
    # Final report
    # -------------------------
    report = f"""
Final IPO Entry Confidence: {confidence}%

1) Business Fundamentals
{fundamentals_block}

Assessment:
{financials["assessment"] if financials else "Insufficient financial disclosures at this stage."}

2) Revenue & Growth Trend
• CAGR (approx): {financials["cagr"] if financials else "N/A"}%
• Margin trend: {financials["margin_trend"] if financials else "N/A"}

4) Retail & Social Sentiment
• Posts & articles analyzed: {sentiment["posts_analyzed"] + sentiment["articles_analyzed"]}
• Positive / Neutral / Negative split:
  {sentiment["sentiment_split"]["positive"]} / {sentiment["sentiment_split"]["neutral"]} / {sentiment["sentiment_split"]["negative"]}
• Dominant themes: {", ".join(sentiment["themes"])}

Sample Reddit discussions:
{reddit_samples if reddit_samples else "- No strong Reddit discussions found"}

Sample News coverage:
{news_samples if news_samples else "- Limited mainstream media coverage"}

Assessment:
{sentiment["assessment"]}

5) Red Flags
• Identified risks: {", ".join(red_flags["flags"]) if red_flags["flags"] else "None"}

Assessment:
{red_flags["assessment"]}

Investor Clarity
This IPO appears suitable for investors with **moderate risk appetite**
who prefer understanding business fundamentals and sentiment,
rather than chasing listing-day speculation.
""".strip()

    return report


def quick_summary(financials: dict, sentiment: dict, red_flags: dict) -> str:
    """
    Generates a short human-readable IPO summary.
    """

    parts = []

    # Financial strength
    if financials.get("is_profitable"):
        parts.append("profitable business")
    else:
        parts.append("loss-making business")

    # Growth
    cagr = financials.get("cagr")
    if cagr:
        if cagr >= 15:
            parts.append("strong revenue growth")
        elif cagr >= 8:
            parts.append("moderate growth")
        else:
            parts.append("low growth")

    # Sentiment
    sentiment_assessment = sentiment.get("assessment", "").lower()
    if "strong" in sentiment_assessment:
        parts.append("positive retail sentiment")
    elif "low" in sentiment_assessment:
        parts.append("low retail visibility")

    # Red flags
    if red_flags.get("flags"):
        parts.append("some risk factors present")
    else:
        parts.append("no major red flags")

    return ", ".join(parts).capitalize() + "."
