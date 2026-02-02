from typing import Dict

def resolve_ipo_state(
    documents: Dict | None,
    sentiment: Dict | None
) -> str:
    """
    Determines IPO stage using deterministic rules.
    """

    # No documents but buzz exists → speculation
    if not documents and sentiment and sentiment["posts_analyzed"] > 0:
        return "SPECULATION"

    if documents:
        issue = documents.get("issue", {})
        financials = documents.get("financials", {})

        has_price_band = bool(issue.get("price_band"))
        has_financials = bool(financials.get("revenue"))

        if has_financials and not has_price_band:
            return "FILED"

        if has_price_band and not issue.get("subscription"):
            return "PRE_APPLY"

        if issue.get("subscription"):
            return "OPEN"

    return "UNKNOWN"
