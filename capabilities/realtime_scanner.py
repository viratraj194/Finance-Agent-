import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from openai import OpenAI
from config import NVIDIA_API_KEY
from providers.enhanced_rss import fetch_india_market_news, fetch_global_and_geo_news
from providers.finnhub import get_market_news
from providers.news import fetch_news
from providers.scrapling_fetcher import enrich_articles_with_deep_scrape
from providers.bse_announcements import fetch_latest_bse_announcements
from providers.eprocure_scraper import fetch_eprocure_tenders

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
MODEL = "meta/llama-3.3-70b-instruct"

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "seen_breaking_news.json")
ALERT_SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "alert_subscribers.json")

def load_alert_subscribers() -> list[int]:
    if not os.path.exists(ALERT_SUBSCRIBERS_FILE):
        os.makedirs(os.path.dirname(ALERT_SUBSCRIBERS_FILE), exist_ok=True)
        with open(ALERT_SUBSCRIBERS_FILE, "w") as f:
            json.dump({"chat_ids": []}, f)
        return []
    try:
        with open(ALERT_SUBSCRIBERS_FILE, "r") as f:
            data = json.load(f)
            return data.get("chat_ids", [])
    except Exception as e:
        logger.error(f"Error loading alert subscribers: {e}")
        return []

def save_alert_subscribers(subscribers: list[int]):
    try:
        with open(ALERT_SUBSCRIBERS_FILE, "w") as f:
            json.dump({"chat_ids": subscribers}, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving alert subscribers: {e}")

def add_alert_subscriber(chat_id: int) -> bool:
    subscribers = load_alert_subscribers()
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_alert_subscribers(subscribers)
        return True
    return False

def remove_alert_subscriber(chat_id: int) -> bool:
    subscribers = load_alert_subscribers()
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_alert_subscribers(subscribers)
        return True
    return False

def load_seen_news() -> set:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("seen_urls", []))
        except Exception:
            pass
    return set()

def save_seen_news(seen_urls: set):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        # Keep only the last 500 URLs to prevent infinite growth
        with open(STATE_FILE, "w") as f:
            json.dump({"seen_urls": list(seen_urls)[-500:]}, f)
    except Exception as e:
        logger.error(f"Error saving seen breaking news: {e}")

async def analyze_and_broadcast_breaking_news(application, new_articles: list):
    """Passes new articles to LLM to detect if any are highly urgent/breaking."""
    if not new_articles:
        return

    formatted_news = []
    for idx, item in enumerate(new_articles, 1):
        pub_date = item.get('published_at') or 'Unknown Date'
        
        # Use deep-scraped content if available, otherwise fallback to short description
        content_snippet = item.get('deep_content') or item.get('description', '')
        # Allow up to 800 characters per article since we are now getting the real meat of the article
        content_snippet = content_snippet[:800] 
        
        formatted_news.append(
            f"[{idx}] {item.get('title')} - {content_snippet} "
            f"(Source: {item.get('source')}, Date: {pub_date}, URL: {item.get('url')})"
        )
    news_context = "\n".join(formatted_news)

    current_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S IST")

    prompt = (
        f"You are an ELITE FINANCIAL MARKET ALERT SYSTEM focusing heavily (80%+) on the Indian Stock Market and specific, high-impact global market-moving events. The current date and time is {current_time}.\n"
        "Your job is to read the latest breaking news and identify ONLY highly specific, actionable events that will INSTANTLY affect specific stocks, sectors, or major indices.\n\n"
        "CRITERIA FOR A VALID ALERT (Must meet at least one):\n"
        "- Huge company-specific news in India (e.g., USA bans a specific company's products like Dabur, major unexpected investments by Ambani/Adani, CEO arrest, Hindenburg report).\n"
        "- Major regulatory crackdowns (e.g., RBI bans a bank, SEBI bans a major broker).\n"
        "- Sudden and massive commodity/index movements (e.g., US Silver futures drop 7%, a foreign stock exchange crashes).\n"
        "- Major geopolitical escalations triggering safe-haven flows into Gold or Silver (massive sudden spikes in precious metals).\n"
        "- Highly specific international news that directly and instantly moves major stocks (e.g., Trump unexpectedly invests in a specific stock).\n\n"
        "WHAT TO IGNORE (CRITICAL):\n"
        "- Do NOT alert on general ongoing geopolitical news or war updates. These are noise. Only alert if there is a massive, unexpected new event that explicitly crashes markets TODAY.\n"
        "- Do NOT alert on routine economic data, standard earnings, or general news that users can find on daily news apps.\n"
        "- Check the Date of the article. Do NOT alert on old news.\n\n"
        "If you find an event matching these strict criteria, reply strictly with the word 'ALERT' followed by a newline, and then a professional, highly specific Telegram message. Tell the user EXACTLY what happened and the specific stocks/assets affected. Avoid generic panic phrases (e.g. avoid 'GEOPOLITICAL SHOCK' unless it truly is one).\n"
        "If there are NO highly specific, actionable events, reply strictly with 'NO_ALERT'.\n\n"
        f"--- RECENT NEWS ---\n{news_context}\n--- END ---"
    )

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are an urgent financial risk management AI."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
        )
        content = response.choices[0].message.content.strip()
        
        if content.startswith("ALERT"):
            # Strip the 'ALERT' keyword and clean up
            alert_msg = content[5:].strip()
            final_msg = f"🚨 *BREAKING MARKET ALERT* 🚨\n🕒 {current_time}\n\n{alert_msg}"
            
            subscribers = load_alert_subscribers()
            for chat_id in subscribers:
                try:
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=final_msg,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Sent breaking news alert to {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send breaking news alert to {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Error in realtime breaking news LLM check: {e}")

async def realtime_breaking_news_task(application):
    logger.info("Realtime breaking news scanner started. Running every 5 minutes.")
    seen_urls = load_seen_news()
    
    while True:
        try:
            loop = asyncio.get_running_loop()
            
            # Fetch news from RSS feeds, Finnhub API, and GNews API in parallel
            india_news = await loop.run_in_executor(None, fetch_india_market_news, 2, 20)
            global_news = await loop.run_in_executor(None, fetch_global_and_geo_news, 2, 20)
            finnhub_news = await loop.run_in_executor(None, get_market_news, "general")
            gnews_news = await loop.run_in_executor(None, fetch_news, "breaking global market crisis", 5)
            bse_news = await loop.run_in_executor(None, fetch_latest_bse_announcements, 10)
            eprocure_news = await loop.run_in_executor(None, fetch_eprocure_tenders, 10)
            
            india_news = india_news or []
            global_news = global_news or []
            finnhub_news = finnhub_news or []
            gnews_news = gnews_news or []
            bse_news = bse_news or []
            eprocure_news = eprocure_news or []
            
            all_recent = india_news + global_news + finnhub_news + gnews_news + bse_news + eprocure_news
            
            new_articles = []
            for article in all_recent:
                url = article.get("url")
                if url and url not in seen_urls:
                    new_articles.append(article)
                    seen_urls.add(url)
            
            if new_articles:
                # DEEP SCRAPE: Fetch the full paragraph text for all new articles concurrently
                new_articles = await loop.run_in_executor(None, enrich_articles_with_deep_scrape, new_articles)
                
                await analyze_and_broadcast_breaking_news(application, new_articles)
                save_seen_news(seen_urls)
                
        except Exception as e:
            logger.error(f"Error in realtime breaking news loop: {e}")
            
        # Check every 5 minutes (300 seconds)
        await asyncio.sleep(300)
