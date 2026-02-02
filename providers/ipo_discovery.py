import requests
from bs4 import BeautifulSoup
import re
from typing import Optional, Dict

BASE_URL = "https://www.chittorgarh.com"
SEARCH_URL = "https://www.chittorgarh.com/search/"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"(limited|ltd|labs|technologies|technology)", "", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_ipo_page(company_name: str) -> Optional[Dict]:
    """
    Finds IPO page on Chittorgarh using search.
    """
    try:
        resp = requests.get(
            SEARCH_URL,
            params={"q": company_name},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    results = soup.find_all("a", href=True)

    target = _clean(company_name)

    for a in results:
        href = a["href"]
        text = a.get_text(strip=True)

        # We only care about IPO pages
        if "/ipo/" not in href:
            continue

        if target in _clean(text):
            return {
                "company": company_name,
                "ipo_name": text,
                "url": href if href.startswith("http") else BASE_URL + href,
                "source": "chittorgarh_search",
            }

    return None
