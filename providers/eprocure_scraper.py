import requests
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

EPROCURE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

def fetch_eprocure_tenders(limit: int = 15) -> list[dict]:
    """
    Scrapes the Central Public Procurement Portal (eprocure.gov.in) for the latest active tenders.
    Provides an edge for infrastructure, defense, and railway stocks.
    """
    url = "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page"
    
    articles = []
    try:
        # Government websites are notoriously slow. Increased timeout to 25s.
        response = requests.get(url, headers=EPROCURE_HEADERS, timeout=25, verify=False)
        if response.status_code == 200:
            html = response.text
            
            # Since eprocure is an old JSP site, we use regex to extract the table rows to avoid heavy bs4 dependencies
            # We are looking for rows in the tender table.
            # Example row data: Tender Title, Reference No, Closing Date, Bid Opening Date
            
            # Simple regex to find all <tr> tags with class "list_table" or similar inside the main table
            # Actually, the active tenders are within <a class="link2" ...>Title</a>
            links = re.findall(r'<a\s+class="link2"\s+id="[^"]+"\s+href="[^"]+"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
            orgs = re.findall(r'<td\s+class="list_table">([^<]+)</td>', html, re.IGNORECASE)
            
            # Filter and construct the data
            for idx, title in enumerate(links[:limit]):
                clean_title = title.replace("\r", "").replace("\n", "").strip()
                
                # Try to associate with an organization (heuristic mapping)
                org_name = "Govt of India"
                if len(orgs) > idx * 5 + 3:
                    org_name = orgs[idx * 5 + 3].replace("\r", "").replace("\n", "").strip()
                    
                # We only want to alert on massive/significant sounding tenders, or just pass them to LLM
                articles.append({
                    "title": f"GOVT TENDER: {org_name} - {clean_title}",
                    "description": f"New government tender published by {org_name} on eprocure.gov.in.",
                    "source": "Central Public Procurement Portal (eProcure)",
                    "published_at": datetime.now().strftime("%Y-%m-%d"),
                    "region": "India",
                    "category": "Government Tenders & Contracts"
                })
                
        return articles
    except Exception as e:
        logger.error(f"Failed to fetch eprocure tenders: {e}")
        return []

# Ignore insecure request warnings for government sites
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
