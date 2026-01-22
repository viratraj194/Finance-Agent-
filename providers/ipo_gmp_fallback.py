import re
from providers.news import fetch_news


GMP_KEYWORDS = [
    "grey market premium",
    "gmp",
    "listing premium",
    "grey market buzz",
    "expected premium",
]


def infer_gmp_from_news(company: str) -> dict:
    news_items = fetch_news(company)

    hits = []
    for n in news_items:
        text = f"{n.get('title','')} {n.get('description','')}".lower()
        if any(k in text for k in GMP_KEYWORDS):
            hits.append(text)

    if not hits:
        return {"status": "not_available", "reason": "No GMP-related news found"}

    # Try extracting numbers if present
    numbers = []
    for h in hits:
        nums = re.findall(r"₹?\d{2,3}", h)
        numbers.extend(nums)

    if numbers:
        values = sorted({int(re.sub(r"\D", "", n)) for n in numbers})
        return {
            "gmp_range": (values[0], values[-1]),
            "trend": "forming",
            "source": "news consensus",
            "confidence": "medium",
        }

    return {
        "gmp_signal": "positive",
        "reason": "Media commentary suggests grey market interest",
        "trend": "forming",
        "confidence": "low",
    }
