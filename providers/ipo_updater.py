import json
import feedparser
import re
from datetime import datetime
from pathlib import Path

# --------------------
# PATH SETUP (CORRECT)
# --------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REGISTRY_PATH = DATA_DIR / "ipo_registry.json"

# --------------------
# RSS SOURCES
# --------------------
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=IPO+India",
    "https://news.google.com/rss/search?q=IPO+opens+India",
    "https://news.google.com/rss/search?q=IPO+listing+India",
    "https://news.google.com/rss/search?q=DRHP+IPO+India",
]

STOPWORDS = {
    "india", "indian", "ipo", "psu", "crore", "rs",
    "files", "filed", "opens", "open", "opening",
    "listing", "listed", "lists",
    "sebi", "market", "issue", "offer", "drhp",
    "gets", "to", "for", "of", "in", "on", "with",
}

# --------------------
# EXTRACTION LOGIC
# --------------------
def extract_company_candidates(title: str) -> list[str]:
    """
    Extract probable company-name phrases from a news headline.
    """
    title = re.sub(r"[₹,$()%:;\"']", " ", title)
    words = title.split()

    candidates = []
    buffer = []

    for w in words:
        lw = w.lower()

        if lw in STOPWORDS or lw.isdigit() or len(lw) < 3:
            if len(buffer) >= 2:
                candidates.append(" ".join(buffer))
            buffer = []
        else:
            buffer.append(w)

    if len(buffer) >= 2:
        candidates.append(" ".join(buffer))

    return candidates


# --------------------
# REGISTRY BUILDER
# --------------------
def rebuild_ipo_registry():
    print("Rebuilding IPO registry...")

    ipos = {}
    today = datetime.now().strftime("%Y-%m-%d")

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            title = entry.get("title", "")
            companies = extract_company_candidates(title)

            for company in companies:
                key = company.upper()

                if key not in ipos:
                    ipos[key] = {
                        "name": company,
                        "short_name": key,
                        "status": "unknown",
                        "source": "Google News RSS",
                        "first_seen": today,
                        "last_seen": today,
                    }
                else:
                    ipos[key]["last_seen"] = today

    registry = {
        "updated_on": today,
        "ipos": list(ipos.values()),
    }

    # Ensure /data exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    print(f"IPO registry rebuilt. Total IPOs found: {len(registry['ipos'])}")
    print(f"Saved to: {REGISTRY_PATH}")


if __name__ == "__main__":
    rebuild_ipo_registry()
