import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/corporates/ann.html",
    "Origin": "https://www.bseindia.com"
}

def fetch_latest_bse_announcements(limit: int = 15) -> list[dict]:
    """
    Fetches the latest corporate announcements directly from the BSE India API.
    These are the raw filings submitted by companies before they hit the news.
    """
    # The BSE API endpoint for announcements
    # strCat=-1 means all categories. strPrevDate and strToDate can be today's date.
    today_str = datetime.now().strftime("%Y%m%d")
    url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?strCat=-1&strPrevDate={today_str}&strToDate={today_str}&strType=C&strData=all&strHCData=all"
    
    articles = []
    try:
        response = requests.get(url, headers=BSE_HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "Table" in data:
                # Iterate through the latest announcements
                for item in data["Table"][:limit]:
                    company_name = item.get("SLONGNAME", "Unknown Company")
                    headline = item.get("HEADLINE", "")
                    details = item.get("MORE", "")
                    time_submitted = item.get("NEWS_DT", "")
                    
                    # We only care about major announcements (ignore mundane updates like 'Trading Window Closed')
                    ignore_keywords = ["trading window", "loss of share certificate", "issue of duplicate", "newspaper publication"]
                    if any(k in headline.lower() or k in details.lower() for k in ignore_keywords):
                        continue
                        
                    articles.append({
                        "title": f"BSE FILING: {company_name} - {headline}",
                        "description": details,
                        "source": "BSE Corporate Announcements (Raw Filing)",
                        "published_at": time_submitted,
                        "region": "India",
                        "category": "Corporate Filings (Zero-Minute Edge)"
                    })
        return articles
    except Exception as e:
        logger.error(f"Failed to fetch BSE announcements: {e}")
        return []
