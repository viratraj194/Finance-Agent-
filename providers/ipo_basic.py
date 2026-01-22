import requests
from datetime import datetime
from typing import List, Dict


def get_ipos_bse() -> List[Dict]:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.bseindia.com/",
    })

    try:
        # Warm-up request (important)
        session.get("https://www.bseindia.com", timeout=10)

        response = session.get(
            "https://api.bseindia.com/BseIndiaAPI/api/IPO/GetIPOListNew/w",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("BSE IPO fetch error:", e)
        return []

    if not isinstance(data, list):
        return []

    ipos = []
    today = datetime.now().date()

    for item in data:
        try:
            open_date = datetime.strptime(item["OpenDate"], "%d %b %Y")
            close_date = datetime.strptime(item["CloseDate"], "%d %b %Y")
        except Exception:
            continue

        listing_date = None
        if item.get("ListingDate"):
            try:
                listing_date = datetime.strptime(
                    item["ListingDate"], "%d %b %Y"
                ).strftime("%Y-%m-%d")
            except Exception:
                pass

        if today < open_date.date():
            status = "upcoming"
        elif open_date.date() <= today <= close_date.date():
            status = "open"
        else:
            status = "closed"

        ipos.append({
            "company": item.get("CompanyName"),
            "status": status,
            "open_date": open_date.strftime("%Y-%m-%d"),
            "close_date": close_date.strftime("%Y-%m-%d"),
            "listing_date": listing_date,
            "price_band": item.get("PriceBand") or "Not disclosed",
            "issue_size": item.get("IssueSize"),
            "exchange": "BSE",
        })

    return ipos


def get_ipos_overview() -> List[Dict]:
    """
    Returns upcoming, open, and recently closed IPOs
    by combining NSE + BSE sources.
    """
    ipos = []
    ipos.extend(get_open_ipos_nse())
    ipos.extend(get_ipos_bse())
    return ipos

