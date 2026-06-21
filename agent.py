import json
import concurrent.futures
from openai import OpenAI
from config import NVIDIA_API_KEY

from capabilities.snapshot import get_market_snapshot
from capabilities.context import get_asset_context
from capabilities.history.range import get_high_low
from capabilities.history.performance import get_performance
from capabilities.indicators.basic import get_indicators
from capabilities.indicators.signals import compute_signals
from capabilities.events import get_asset_events
from capabilities.attention import get_social_attention
from providers.ipo_documents import get_ipo_documents
from capabilities.ipo_analysis import analyze_financials
from capabilities.ipo_sentiment import analyze_ipo_sentiment
from capabilities.ipo_red_flags import analyze_red_flags
from capabilities.ipo_final_report import assemble_final_ipo_report
from providers.yahoo import search_symbol

from capabilities.premarket import get_premarket_dashboard
from capabilities.alerts import get_overnight_alerts
from capabilities.sentiment import analyze_news_sentiment
from capabilities.gaps import scan_gap_opportunities

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

MODEL = "meta/llama-3.3-70b-instruct"

def get_latest_market_report() -> str:
    """Reads the most recent market impact report from the reports directory."""
    import glob
    import os
    
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    if not os.path.exists(reports_dir):
        return ""
    
    report_files = glob.glob(os.path.join(reports_dir, "market_impact_report_*.md"))
    if not report_files:
        return ""
    
    # Sort files by name (since they contain YYYY-MM-DD in the filename, sorting alphabetically sorts by date)
    report_files.sort()
    latest_report_path = report_files[-1]
    
    try:
        with open(latest_report_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


# =====================================================
# SPECIALIZED SUB-AGENTS (WORKERS)
# =====================================================

def market_worker(query: str):
    """Worker 1: Market Data & Fundamentals"""
    return get_market_snapshot(query)

def technical_worker(query: str):
    """Worker 2: Technical Analysis"""
    symbol = search_symbol(query)
    if not symbol: return {"error": "Symbol not found"}
    ind = get_indicators(symbol)
    if not ind: return {"error": "Indicators unavailable"}
    sig = compute_signals(ind)
    return {"indicators": ind, "signals": sig}

def news_worker(query: str):
    """Worker 3: News & Corporate Events"""
    return get_asset_events(query)

def social_worker(query: str):
    """Worker 4: Social Sentiment (Reddit)"""
    return get_social_attention(query)

def ipo_worker(query: str):
    """Worker 5: IPO Analysis"""
    doc = get_ipo_documents(query)
    if not doc: return {"error": "IPO details not found"}
    fin = analyze_financials(doc)
    sen = analyze_ipo_sentiment(query)
    red = analyze_red_flags(doc["financials"], doc.get("issue", {}), None)
    return {
        "financials": fin,
        "sentiment": sen,
        "red_flags": red,
        "report": assemble_final_ipo_report(query, fin, sen, red, doc)
    }

# =====================================================
# INTENT DETECTION (SCRIPT-FIRST)
# =====================================================

def detect_script_intent(text: str) -> str | None:
    text = text.lower()
    if any(k in text for k in ["price", "snapshot", "how is", "quote"]):
        return "market"
    if any(k in text for k in ["technical", "indicator", "rsi", "sma", "ema", "signal"]):
        return "technical"
    if any(k in text for k in ["news", "event", "happen", "update", "dividend", "split"]):
        return "news"
    if any(k in text for k in ["sentiment", "reddit", "people saying", "opinion"]):
        return "social"
    if any(k in text for k in ["ipo", "listing", "drhp", "apply"]):
        return "ipo"
    if any(k in text for k in ["research", "analyze in detail", "deep dive", "everything about"]):
        return "deep_research"
    # Geopolitical keywords — check BEFORE sector_scan to avoid misclassification
    if any(k in text for k in ["war", "conflict", "sanction", "strike", "military", "iran", "israel",
                                 "russia", "ukraine", "middle east", "geopolit", "crude oil price",
                                 "trade war", "tariff", "embargo", "tension"]):
        return "geopolitical_impact"
    
    if any(k in text for k in ["premarket", "pre-market", "dashboard", "gift nifty", "open"]):
        return "premarket"
    if any(k in text for k in ["alert", "overnight", "watchlist"]):
        return "alerts"
    if any(k in text for k in ["news sentiment", "news feeling"]):
        return "news_sentiment"
    if any(k in text for k in ["gap", "gap-up", "gap-down", "gap up", "gap down"]):
        return "gaps"
        
    return None

def extract_asset(text: str) -> str:
    """Simple heuristic for asset extraction before AI fallback"""
    junk = {"price", "of", "the", "for", "news", "on", "ipo", "analyze", "deep", "research", "technical", "about"}
    words = [w for w in text.lower().split() if w not in junk]
    return " ".join(words).strip()

# =====================================================
# CORE LOGIC
# =====================================================

def ai_summarize(data: dict, query: str, context: str = "") -> str:
    """Uses AI ONLY to summarize the deterministic data fetched by scripts."""
    prompt = (
        f"User Query: {query}\n"
        f"Data Fetched by Scripts: {json.dumps(data, default=str)}\n\n"
        f"Context: {context}\n"
        "- Summarize the data above clearly and concisely.\n"
        "- Focus on facts. Do NOT give investment advice.\n"
        "- If the user asks about a 'dip' or 'rise' but the stock is net-green/net-red compared to yesterday's close, check today's 'open' and 'high'/'low' to see if there was a notable intraday correction or rebound and explain that action clearly.\n"
        "- If data is missing or errored, explain that clearly."
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a financial data summarizer. Be factual, conservative, and brief. No advice."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content if response and response.choices else None
        return content or "Summary unavailable — LLM returned empty response."
    except Exception as e:
        return f"Summary failed: {e}"

def run_deep_research(query: str) -> str:
    """Multi-agent Deep Research mode using 5 specialized workers in parallel."""
    workers = {
        "Market": market_worker,
        "Technical": technical_worker,
        "News": news_worker,
        "Social": social_worker,
        "IPO": ipo_worker
    }
    
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_worker = {executor.submit(func, query): name for name, func in workers.items()}
        for future in concurrent.futures.as_completed(future_to_worker):
            worker_name = future_to_worker[future]
            try:
                results[worker_name] = future.result()
            except Exception as e:
                results[worker_name] = {"error": str(e)}

    # AI aggregates all worker findings
    prompt = (
        f"Deep Research Report for: {query}\n\n"
        f"Market Data: {json.dumps(results['Market'], default=str)}\n"
        f"Technical Data: {json.dumps(results['Technical'], default=str)}\n"
        f"News & Events: {json.dumps(results['News'], default=str)}\n"
        f"Social Sentiment: {json.dumps(results['Social'], default=str)}\n"
        f"IPO Analysis: {json.dumps(results['IPO'], default=str)}\n\n"
        "Synthesize a professional, 5-part research report. Separate into: Fundamentals, Technicals, News/Sentiment, IPO/Strategy, and Risks. No advice."
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a lead equity research analyst. Synthesize a detailed report from multiple sub-agent findings. Stay objective and factual."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content if response and response.choices else None
        return content or "Research report unavailable — LLM returned empty response."
    except Exception as e:
        return f"Research aggregation failed: {e}"


def extract_intent_and_asset_via_ai(text: str) -> tuple[str, str]:
    """Uses LLM to cleanly extract intent and asset name from natural language."""
    import re
    prompt = (
        f"You are a financial query parser.\n"
        f"Analyze the user query: \"{text}\"\n\n"
        "Identify:\n"
        "1. The primary intent. Choose exactly one of:\n"
        "   - 'market': Questions about price, current stock quote, or how a stock is doing today.\n"
        "   - 'technical': Questions about indicators, RSI, moving averages, technical trends.\n"
        "   - 'news': Questions about recent news, dividends, stock splits, corporate updates, or explaining WHY a stock is rising/falling/dipping.\n"
        "   - 'social': Questions about what people are saying, Reddit discussions, retail sentiment.\n"
        "   - 'ipo': Questions about IPO analysis, listing details, applying, or DRHP.\n"
        "   - 'deep_research': Exhaustive, comprehensive analysis or everything about a company.\n"
        "   - 'geopolitical_impact': Questions about how a WAR, CONFLICT, SANCTION, GEOPOLITICAL EVENT, TRADE WAR, or GLOBAL CRISIS (e.g. Middle East war, Russia-Ukraine, Iran sanctions, US tariffs) affects Indian stocks — asking which stocks go UP or DOWN due to that event. This takes PRIORITY over sector_scan if any war/conflict/country tension is mentioned.\n"
        "   - 'sector_scan': ONLY use this when the user asks to scan or find stocks to trade this week/month across sectors, WITHOUT mentioning any specific global event or conflict. Examples: 'find 3 stocks in IT and banking to trade this week'.\n"
        "   - 'premarket': Questions about pre-market data, GIFT Nifty, overnight global markets, or how the market will open today.\n"
        "   - 'alerts': Requests for overnight alerts or watchlist monitoring.\n"
        "   - 'news_sentiment': Questions specifically asking for AI sentiment score on recent news for a stock.\n"
        "   - 'gaps': Questions about gap-ups or gap-downs at market open.\n"
        "   - 'general': General chat, financial questions, or greetings.\n\n"
        "2. The clean asset or company name OR the geopolitical event description (e.g., 'Middle East war', 'Russia Ukraine conflict', 'US tariffs on India'). Return null if neither is mentioned.\n\n"
        "Output a JSON object with keys 'intent' and 'asset'. For geopolitical_impact, put the event description in 'asset'. Example:\n"
        '{"intent": "geopolitical_impact", "asset": "Middle East war between Israel and Iran"}'
    )
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a precise query parser that outputs only raw JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content if response and response.choices else None
        if not content:
            raise ValueError("LLM parser returned empty response")
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n|```$", "", content, flags=re.MULTILINE).strip()
        
        parsed = json.loads(content)
        return parsed.get("intent", "general"), parsed.get("asset") or ""
    except Exception:
        # Fallback to simple heuristics
        return detect_script_intent(text) or "general", extract_asset(text)


def handle_user_message(user_text: str) -> str:
    cleaned_query = user_text.strip()
    
    # Heuristic check: if the query is a single clean word, skip LLM parsing for speed
    if len(cleaned_query.split()) == 1 and cleaned_query.isalnum():
        intent = detect_script_intent(cleaned_query) or "market"
        asset = cleaned_query
    else:
        # Conversational query: use LLM for robust extraction
        intent, asset = extract_intent_and_asset_via_ai(cleaned_query)
    
    if not asset and intent not in ["deep_research", "general", "sector_scan", "geopolitical_impact", "premarket", "alerts", "gaps"]:
        intent = "general"

    # 1. PRIORITY: SCRIPT-FIRST
    if intent == "market":
        data = market_worker(asset)
        return ai_summarize(data, user_text)
    
    if intent == "technical":
        data = technical_worker(asset)
        return ai_summarize(data, user_text)
    
    if intent == "news":
        data = news_worker(asset)
        # Fetch current price context to help explain price movements
        price_data = market_worker(asset)
        if isinstance(price_data, dict) and price_data.get("resolved"):
            data["price_context"] = {
                "price": price_data.get("price"),
                "change": price_data.get("change"),
                "change_pct": price_data.get("change_pct"),
                "open": price_data.get("open"),
                "high": price_data.get("high"),
                "low": price_data.get("low"),
                "direction": price_data.get("direction")
            }
        return ai_summarize(data, user_text)
    
    if intent == "social":
        data = social_worker(asset)
        return ai_summarize(data, user_text)
    
    if intent == "ipo":
        data = ipo_worker(asset)
        if isinstance(data, dict) and "report" in data: 
            return data["report"]
        return ai_summarize(data, user_text)

    # 2. DEEP RESEARCH MODE (5 Sub-Agents)
    if intent == "deep_research":
        return run_deep_research(asset or user_text)

    # 3. GEOPOLITICAL IMPACT MODE
    if intent == "geopolitical_impact":
        from capabilities.geo_impact import run_geo_impact_analysis
        # asset here holds the event description extracted by the LLM parser
        event_desc = asset if asset else user_text
        return run_geo_impact_analysis(user_text, event_desc)

    if intent == "sector_scan":
        from capabilities.sector_scanner import run_sector_scanner
        return run_sector_scanner(user_text)

    # NEW TOOLS ROUTING
    if intent == "premarket":
        return get_premarket_dashboard()
        
    if intent == "alerts":
        return get_overnight_alerts()
        
    if intent == "news_sentiment":
        return analyze_news_sentiment(asset)
        
    if intent == "gaps":
        return scan_gap_opportunities()

    # 3. FALLBACK: Use AI to handle conversational filler or general chat
    try:
        report_context = get_latest_market_report()
        system_content = (
            "You are FinanceAI, a helpful, premium AI financial assistant for Indian stocks (NSE).\n"
            "If the user asks a complex question about a specific stock, suggest using 'Deep Research' (e.g. 'Tell me about Infosys (Deep Research)').\n"
            "If the user asks general market/financial questions, sector suggestions, or stock recommendations, answer them comprehensively and factually.\n"
        )
        if report_context:
            system_content += (
                "\nHere is the latest Daily Market Impact Report for context, containing recent sector analysis, stock recommendations, and market events:\n"
                f"--- LATEST REPORT CONTEXT ---\n{report_context}\n--- END CONTEXT ---\n"
                "Use the sector tables, price movement suggestions (Bullish/Bearish), and reasons from the context to guide your response. Focus on facts. Do NOT give guaranteed investment advice, and add a disclaimer at the end."
            )
        else:
            system_content += "\nProvide objective financial analysis based on your knowledge, and add a disclaimer that this is not investment advice."

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_text}
            ]
        )
        content = response.choices[0].message.content if response and response.choices else None
        return content or "I couldn't generate a response. Please try again."
    except Exception as e:
        return f"Error: {e}"

