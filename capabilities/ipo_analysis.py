from typing import Dict, Any
from math import pow


# =====================================================
# FY NORMALIZATION UTILITIES
# =====================================================

def _extract_fy_year(label: str) -> int | None:
    """
    Converts raw financial labels to FY year.

    Examples:
    - 31Mar2024  -> FY2024
    - 30Sep2025  -> FY2026
    """
    if "Mar" in label:
        return int(label[-4:])
    if "Sep" in label:
        return int(label[-4:]) + 1
    return None


def normalize_financials(
    financials: Dict[str, Any]
) -> tuple[Dict[str, float], Dict[str, float]]:
    """
    Normalizes raw revenue & profit data into FY-based dictionaries.
    """
    revenue_raw = financials.get("revenue", {})
    profit_raw = financials.get("profit", {})

    revenue: Dict[str, float] = {}
    profit: Dict[str, float] = {}

    for label, value in revenue_raw.items():
        fy = _extract_fy_year(label)
        if fy and value is not None:
            revenue[f"FY{fy}"] = float(value)

    for label, value in profit_raw.items():
        fy = _extract_fy_year(label)
        if fy and value is not None:
            profit[f"FY{fy}"] = float(value)

    revenue = dict(sorted(revenue.items()))
    profit = dict(sorted(profit.items()))

    return revenue, profit


# =====================================================
# FINANCIAL METRICS
# =====================================================

def compute_yoy_growth(revenue: Dict[str, float]) -> Dict[str, float]:
    """
    Computes YoY revenue growth percentages.
    """
    yoy: Dict[str, float] = {}
    years = list(revenue.keys())

    for i in range(1, len(years)):
        prev = revenue[years[i - 1]]
        curr = revenue[years[i]]

        if prev > 0:
            yoy[years[i]] = round(((curr - prev) / prev) * 100, 2)

    return yoy


def compute_cagr(revenue: Dict[str, float]) -> float | None:
    """
    Computes CAGR across available FYs.
    """
    if len(revenue) < 2:
        return None

    years = list(revenue.keys())
    start = revenue[years[0]]
    end = revenue[years[-1]]
    n = len(years) - 1

    if start <= 0:
        return None

    return round((pow(end / start, 1 / n) - 1) * 100, 2)


# =====================================================
# CORE FINANCIAL ANALYSIS
# =====================================================

def analyze_financials(ipo_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core IPO financial analysis (NO GMP, NO sentiment here).
    """
    financials = ipo_doc["financials"]

    revenue, profit = normalize_financials(financials)

    # Exclude partial FYs (e.g., FY26 half-year data)
    completed_revenue = {
        fy: val for fy, val in revenue.items() if not fy.endswith("26")
    }
    completed_profit = {
        fy: val for fy, val in profit.items() if not fy.endswith("26")
    }

    yoy = compute_yoy_growth(completed_revenue)
    cagr = compute_cagr(completed_revenue)

    # Margin trend analysis
    margin_trend = "insufficient data"
    if len(revenue) >= 2 and len(profit) >= 2:
        years = list(revenue.keys())
        latest_year = years[-1]
        prev_year = years[-2]

        if revenue[latest_year] > 0 and revenue[prev_year] > 0:
            last_margin = profit[latest_year] / revenue[latest_year]
            prev_margin = profit[prev_year] / revenue[prev_year]

            if last_margin > prev_margin:
                margin_trend = "improving"
            elif last_margin < prev_margin:
                margin_trend = "compressed"
            else:
                margin_trend = "stable"

    # Growth classification
    if cagr is not None and cagr >= 15:
        growth_label = "strong growth"
    elif cagr is not None and cagr >= 8:
        growth_label = "moderate growth"
    else:
        growth_label = "low growth"

    assessment = (
        f"{growth_label.capitalize()} business with "
        f"{'profitability' if financials.get('is_profitable') else 'losses'} "
        f"and {margin_trend} margins."
    )

    return {
        "revenue": revenue,
        "profit": profit,
        "yoy_growth": yoy,
        "cagr": cagr,
        "margin_trend": margin_trend,
        "assessment": assessment,
    }
