# 1️⃣ IMPORT ANALYSIS MODULES
from providers.ipo_documents import get_ipo_documents
from capabilities.ipo_analysis import analyze_financials
from capabilities.ipo_sentiment import analyze_ipo_sentiment
from capabilities.ipo_red_flags import analyze_red_flags
from capabilities.ipo_final_report import assemble_final_ipo_report


# 2️⃣ FETCH IPO DOCUMENTS
doc = get_ipo_documents("Shadowfax")

# 3️⃣ RUN FINANCIAL ANALYSIS
financial_analysis = analyze_financials(doc)

# 4️⃣ RUN IPO SENTIMENT (Reddit + Google)
ipo_sentiment = analyze_ipo_sentiment("Shadowfax")

# 5️⃣ RUN RED FLAG ANALYSIS
red_flags = analyze_red_flags(
    financials=doc["financials"],
    issue_details=doc.get("issue", {}),
    sector="logistics"
)

# 6️⃣ ASSEMBLE FINAL REPORT
final_report = assemble_final_ipo_report(
    company="Shadowfax",
    financials=financial_analysis,
    sentiment=ipo_sentiment,
    red_flags=red_flags
)

print(final_report)
