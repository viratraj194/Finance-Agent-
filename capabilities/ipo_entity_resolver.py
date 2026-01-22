# capabilities/ipo_entity_resolver.py

from providers.news import fetch_news
import re


LEGAL_SUFFIXES = [
    "limited", "ltd", "private", "pvt", "llp", "plc", "technologies",
    "industries", "mobility", "services", "solutions"
]


def resolve_parent_company(ipo_name: str) -> dict | None:
    """
    Resolve IPO name to its operating / parent company.
    Returns None if confidence is low.
    """

    news = fetch_news(ipo_name)
    if not news:
        return None

    candidates = {}

    for item in news:
        text = (
            item.get("title", "") + " " +
            item.get("description", "")
        ).lower()

        # Look for patterns like:
        # "Shadowfax Technologies Pvt Ltd"
        matches = re.findall(
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,4})\s+(ltd|limited|private|pvt|llp)",
            text,
            flags=re.IGNORECASE
        )

        for name, suffix in matches:
            full_name = f"{name} {suffix}".title()
            candidates[full_name] = candidates.get(full_name, 0) + 1

    if not candidates:
        return None

    # Pick most frequent candidate
    parent = max(candidates, key=candidates.get)
    count = candidates[parent]

    confidence = "high" if count >= 2 else "medium"

    return {
        "entity_name": parent,
        "confidence": confidence
    }
