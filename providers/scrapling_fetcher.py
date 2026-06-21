import logging
import asyncio
import concurrent.futures
from scrapling import Fetcher

logger = logging.getLogger(__name__)

def fetch_article_text(url: str, max_chars: int = 1500) -> str:
    """Uses Scrapling to deeply scrape the text of an article."""
    try:
        # Standard fetcher is fast. If we hit cloudflare, StealthyFetcher could be used, but Fetcher is usually fine for news RSS links
        fetcher = Fetcher.fetch(url)
        # Extract all paragraph text
        paragraphs = fetcher.css('p::text').get_all()
        text = " ".join([p.strip() for p in paragraphs if p.strip()])
        
        if len(text) < 50:
            return "" # Probably failed to extract meaningful text
            
        return text[:max_chars]
    except Exception as e:
        logger.debug(f"Scrapling extraction failed for {url}: {e}")
        return ""

def enrich_articles_with_deep_scrape(articles: list[dict]) -> list[dict]:
    """Concurrently fetches the full deep text for a list of articles."""
    if not articles:
        return []
        
    logger.info(f"Deep scraping {len(articles)} new articles with Scrapling...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for idx, article in enumerate(articles):
            url = article.get('url')
            if url:
                futures[executor.submit(fetch_article_text, url)] = idx
                
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                deep_text = future.result()
                if deep_text:
                    # Replace the short RSS description with the deep-scraped text!
                    articles[idx]['deep_content'] = deep_text
            except Exception:
                pass
                
    return articles
