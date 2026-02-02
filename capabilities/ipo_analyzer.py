from capabilities.ipo_documents import get_ipo_documents
from capabilities.ipo_financials import analyze_financials
from capabilities.ipo_sentiment import analyze_ipo_sentiment
from capabilities.ipo_red_flags import analyze_red_flags
from capabilities.ipo_final_report import assemble_final_ipo_report


def analyze_ipo(company: str) -> str:
    """
    Master IPO analyzer.
    Always returns a report — even if data is partial.
    """

    # 1️⃣ IPO documents (best-effort, never fail)
    ipo_doc = get_ipo_documents(company)

    financial_analysis = None
    red_flags = {"flags": [], "details": [], "assessment": "No structural red flags identified."}

    # 2️⃣ Financials (only if available)
    if ipo_doc and ipo_doc.get("financials"):
        financial_analysis = analyze_financials(ipo_doc)

        red_flags = analyze_red_flags(
            financials=ipo_doc["financials"],
            issue_details=ipo_doc.get("issue", {}),
            sector=ipo_doc.get("sector")
        )

    # 3️⃣ Retail & social sentiment (ALWAYS run)
    sentiment = analyze_ipo_sentiment(company)

    # 4️⃣ Assemble final report (handles missing sections internally)
    report = assemble_final_ipo_report(
        company=company,
        financials=financial_analysis,
        sentiment=sentiment,
        red_flags=red_flags,
        ipo_doc=ipo_doc
    )

    return report
