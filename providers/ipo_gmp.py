import requests
from bs4 import BeautifulSoup
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _find_gmp_page(company: str) -> str | None:
    slug = company.lower().replace(" ", "-")
    url = f"https://www.chittorgarh.com/ipo/ipo-gmp/{slug}/"

    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code == 200 and "GMP" in res.text:
        return url
    return None


def _extract_gmp_range(text: str) -> tuple[int, int] | None:
    # Matches patterns like ₹35–₹45 or 35 to 45
    match = re.search(r"(₹?\d+)\s*(?:to|–|-)\s*(₹?\d+)", text)
    if not match:
        return None

    low = int(re.sub(r"\D", "", match.group(1)))
    high = int(re.sub(r"\D", "", match.group(2)))
    return low, high


def get_ipo_gmp(company: str, price_band_high: int | None = None) -> dict | None:
    gmp_url = _find_gmp_page(company)
    if not gmp_url:
        return {"status": "not_available", "reason": "GMP page not found"}

    page = requests.get(gmp_url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(page.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    gmp_range = _extract_gmp_range(text)
    if not gmp_range:
        return {"status": "not_available", "reason": "GMP not disclosed"}

    implied_pct = None
    if price_band_high:
        implied_pct = (
            round((gmp_range[0] / price_band_high) * 100),
            round((gmp_range[1] / price_band_high) * 100),
        )

    return {
        "gmp_range": gmp_range,
        "implied_premium_pct": implied_pct,
        "trend": "stable",  # refined later if historical GMP added
        "source": "chittorgarh.com",
        "confidence": "medium",
    }
