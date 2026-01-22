from capabilities.ipo_documents import get_ipo_documents
from capabilities.ipo_financials import analyze_financials
from capabilities.ipo_red_flags import analyze_red_flags
from capabilities.ipo_sentiment import analyze_ipo_sentiment
from providers.news import fetch_news


def generate_ipo_report(company: str) -> str:
    # -----------------------------
    # 1. DOCUMENTS
    # -----------------------------
    doc = get_ipo_documents(company)
    if not doc:
        return f"No IPO documents found for {company}."

    financials_raw = doc["financials"]
    issue = doc.get("issue", {})

    # -----------------------------
    # 2. FINANCIAL ANALYSIS
    # -----------------------------
    fin = analyze_financials(doc)

    # -----------------------------
    # 3. RED FLAGS
    # -----------------------------
    red_flags = analyze_red_flags(
        financials=financials_raw,
        issue_details=issue,
        sector=None
    )

    # -----------------------------
    # 4. SENTIMENT
    # -----------------------------
    sentiment = analyze_ipo_sentiment(company)

    # -----------------------------
    # 5. NEWS (RAW, READABLE)
    # -----------------------------
    news = fetch_news(company, days=7)[:5]

    # -----------------------------
    # 6. CONFIDENCE SCORE (RULE-BASED)
    # -----------------------------
    score = 50

    if fin["cagr"] and fin["cagr"] > 10:
        score += 10
    if fin["margin_trend"] == "improving":
        score += 10
    if sentiment["posts_analyzed"] >= 10:
        score += 10
    if red_flags["flags"]:
        score -= 8

    score = max(0, min(100, score))

    # -----------------------------
    # 7. FINAL REPORT
    # -----------------------------
    report = []

    report.append(f"Final IPO Entry Confidence: {score}%\n")

    # ---- Fundamentals
    report.append("1) Business Fundamentals")
    for fy, rev in fin["revenue"].items():
        report.append(f"• Revenue ({fy}): ₹{rev} Cr")
    for fy, prof in fin["profit"].items():
        report.append(f"• Net Profit ({fy}): ₹{prof} Cr")
    report.append(f"\nAssessment: {fin['assessment']}\n")

    # ---- Growth
    report.append("2) Revenue & Growth Trend")
    report.append(f"• CAGR: ~{fin['cagr']}%")
    report.append(f"• Margin trend: {fin['margin_trend']}")
    report.append("\nAssessment: Growth trajectory appears sustainable.\n")

    # ---- Sentiment
    report.append("4) Retail & Social Sentiment")
    report.append(f"• Reddit posts analyzed: {sentiment['posts_analyzed']}")
    ps = sentiment["sentiment_split"]
    report.append(
        f"• Positive / Neutral / Negative: "
        f"{ps['positive']} / {ps['neutral']} / {ps['negative']}"
    )
    report.append(f"\nAssessment: {sentiment['assessment']}\n")

    # ---- Raw signals
    report.append("What People Are Saying:")
    for post in sentiment.get("sample_posts", []):
        report.append(f"- {post['title']} (r/{post['subreddit']})")

    report.append("\nRecent News:")
    for n in news:
        report.append(f"- {n['title']} — {n['source']}")

    # ---- Red flags
    report.append("\n5) Red Flags")
    if red_flags["flags"]:
        for f in red_flags["flags"]:
            report.append(f"• {f}")
    else:
        report.append("• No major red flags identified.")
    report.append(f"\nAssessment: {red_flags['assessment']}\n")

    # ---- Investor clarity
    report.append(
        "Investor Clarity\n"
        "Suitable for investors with **moderate risk appetite** "
        "seeking medium- to long-term exposure."
    )

    return "\n".join(report)
