import requests
from config import NEWS_API_KEY


def fetch_company_news(query: str) -> list[dict]:
    """
    Fetches news articles related to a company name.
    Returns normalized article data.
    """

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "articles" not in data:
            return []

        articles = []
        for a in data["articles"]:
            articles.append({
                "title": a.get("title"),
                "summary": a.get("description"),
                "source": a.get("source", {}).get("name"),
                "publishedAt": a.get("publishedAt"),
            })

        return articles

    except Exception:
        return []
