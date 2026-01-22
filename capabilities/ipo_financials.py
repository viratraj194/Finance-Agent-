# capabilities/ipo_financials.py

import re
from typing import Dict, List


# -----------------------------
# REGEX PATTERNS
# -----------------------------

REVENUE_PATTERN = re.compile(
    r"(revenue|turnover).*?(₹|\bRs\.?)\s?([\d,.]+)\s?(cr|crore|crores)?",
    re.IGNORECASE
)

PROFIT_PATTERN = re.compile(
    r"(profit|net profit).*?(₹|\bRs\.?)\s?([\d,.]+)\s?(cr|crore|crores)?",
    re.IGNORECASE
)

LOSS_PATTERN = re.compile(
    r"(loss|net loss).*?(₹|\bRs\.?)\s?([\d,.]+)\s?(cr|crore|crores)?",
    re.IGNORECASE
)

DEBT_PATTERN = re.compile(
    r"(debt|borrowings).*?(₹|\bRs\.?)\s?([\d,.]+)\s?(cr|crore|crores)?",
    re.IGNORECASE
)

FY_PATTERN = re.compile(r"(FY\d{2})", re.IGNORECASE)


# -----------------------------
# CORE EXTRACTION
# -----------------------------

def extract_financials_from_text(text_blocks: List[str]) -> Dict:
    revenues = {}
    profits = {}
    losses = {}
    debt = None

    for text in text_blocks:
        # Revenue
        for match in REVENUE_PATTERN.finditer(text):
            fy = _detect_fy(text)
            value = _format_amount(match)
            if fy:
                revenues[fy] = value

        # Profit
        for match in PROFIT_PATTERN.finditer(text):
            fy = _detect_fy(text)
            value = _format_amount(match)
            if fy:
                profits[fy] = value

        # Loss
        for match in LOSS_PATTERN.finditer(text):
            fy = _detect_fy(text)
            value = _format_amount(match)
            if fy:
                losses[fy] = value

        # Debt
        if not debt:
            match = DEBT_PATTERN.search(text)
            if match:
                debt = _format_amount(match)

    growth_trend = _infer_growth_trend(revenues)

    return {
        "revenue": revenues,
        "profit": profits if profits else None,
        "loss": losses if losses else None,
        "debt": debt,
        "growth_trend": growth_trend,
        "raw_numbers_found": bool(revenues or profits or losses or debt)
    }


# -----------------------------
# HELPERS
# -----------------------------

def _detect_fy(text: str) -> str | None:
    match = FY_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    return None


def _format_amount(match) -> str:
    amount = match.group(3)
    unit = match.group(4) or ""
    return f"₹{amount} {unit}".strip()


def _infer_growth_trend(revenues: Dict[str, str]) -> str:
    if len(revenues) < 2:
        return "insufficient data"

    # crude ordering by FY
    sorted_fy = sorted(revenues.keys())
    values = []

    for fy in sorted_fy:
        num = float(revenues[fy].replace("₹", "").replace("Cr", "").replace(",", "").strip())
        values.append(num)

    if values[-1] > values[0]:
        return "improving"
    elif values[-1] < values[0]:
        return "deteriorating"
    else:
        return "flat"
