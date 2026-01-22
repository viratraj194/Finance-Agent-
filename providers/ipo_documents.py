import requests
from bs4 import BeautifulSoup
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}

BASE_LIST_URL = "https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/"


def _find_ipo_page(company: str) -> str | None:
    res = requests.get(BASE_LIST_URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")

    for a in soup.find_all("a", href=True):
        if company.lower() in a.text.lower() and "/ipo/" in a["href"]:
            return (
                a["href"]
                if a["href"].startswith("http")
                else "https://www.chittorgarh.com" + a["href"]
            )
    return None


def _parse_financials(soup: BeautifulSoup) -> dict:
    financials = {"revenue": {}, "profit": {}, "loss": None}

    for table in soup.find_all("table"):
        text = table.get_text().lower()
        if "profit after tax" in text or "total revenue" in text:
            rows = table.find_all("tr")
            headers = [c.text.strip() for c in rows[0].find_all(["th", "td"])]

            for row in rows[1:]:
                cols = [c.text.strip() for c in row.find_all(["th", "td"])]
                label = cols[0].lower()

                for i in range(1, min(len(cols), len(headers))):
                    year = headers[i].replace(" ", "")
                    value = cols[i].replace(",", "")

                    if not re.search(r"\d", value):
                        continue

                    num = float(re.sub(r"[^\d.]", "", value))

                    if "revenue" in label or "income" in label:
                        financials["revenue"][year] = num
                    elif "profit after tax" in label or label == "pat":
                        financials["profit"][year] = num

    return financials


def _parse_issue_details(soup: BeautifulSoup) -> dict:
    issue = {}

    for row in soup.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 2:
            continue

        key = cols[0].text.lower()
        val = cols[1].text.strip()

        if "price band" in key:
            issue["price_band"] = val
        elif "issue size" in key:
            issue["issue_size"] = val

    return issue


def get_ipo_documents(company: str) -> dict | None:
    ipo_url = _find_ipo_page(company)
    if not ipo_url:
        return None

    page = requests.get(ipo_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(page.text, "html.parser")

    financials = _parse_financials(soup)
    issue = _parse_issue_details(soup)

    is_profitable = any(v > 0 for v in financials["profit"].values())
    growth_trend = "insufficient data"

    if len(financials["revenue"]) >= 2:
        years = list(financials["revenue"].keys())
        if financials["revenue"][years[-1]] > financials["revenue"][years[-2]]:
            growth_trend = "improving"
        else:
            growth_trend = "flat"

    return {
        "company": company,
        "url": ipo_url,
        "financials": {
            **financials,
            "is_profitable": is_profitable,
            "growth_trend": growth_trend,
        },
        "issue": issue,
        "source": "chittorgarh.com",
    }
