from typing import Dict


def analyze_red_flags(
    financials: Dict,
    issue_details: Dict,
    sector: str | None = None
) -> Dict:
    flags = []
    notes = []

    # OFS risk
    ofs_pct = issue_details.get("ofs_pct")
    if ofs_pct and ofs_pct > 40:
        flags.append("High OFS component")
        notes.append(f"OFS constitutes ~{ofs_pct}% of issue")

    # Profitability risk
    if not financials.get("is_profitable"):
        flags.append("Loss-making company")
        notes.append("Company has not demonstrated sustained profitability")

    # Debt risk
    debt = financials.get("debt")
    equity = financials.get("equity")

    if debt and equity and debt / equity > 1:
        flags.append("High leverage")
        notes.append("Debt-to-equity exceeds comfortable levels")

    # Sector risk
    if sector and sector.lower() in {"infrastructure", "commodities", "shipping"}:
        flags.append("Cyclical sector exposure")
        notes.append("Earnings may fluctuate with economic cycles")

    assessment = "No structural red flags identified."
    if flags:
        assessment = "Some risk factors identified, but no critical red flags."

    return {
        "flags": flags,
        "details": notes,
        "assessment": assessment
    }
