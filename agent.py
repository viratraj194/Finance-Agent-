from openai import OpenAI
from config import OPENAI_API_KEY
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


def is_ipo_query(text: str) -> bool:
    keywords = ["ipo", "initial public offering", "listing"]
    return any(k in text.lower() for k in keywords)


def extract_ipo_company(text: str) -> str | None:
    cleaned = (
        text.lower()
        .replace("ipo", "")
        .replace("initial public offering", "")
        .replace("listing", "")
        .strip()
    )

    return cleaned.title() if cleaned else None


# Detect if the user is asking about IPOs
def is_ipo_query(text: str) -> bool:
    keywords = {
        "ipo", "apply", "listing", "drhp", "issue",
        "should i apply", "ipo analysis", "ipo review"
    }
    return any(k in text.lower() for k in keywords)

# Simple heuristic extraction for IPO name
def extract_ipo_name(text: str) -> str | None:
    text = text.lower()

    # remove intent words
    junk = {
        "ipo", "apply", "analysis", "review",
        "should", "i", "invest", "in", "for"
    }

    words = [w for w in text.split() if w not in junk]

    if not words:
        return None

    # Capitalize properly for scrapers
    return " ".join(words).title()


# Utility to clean extracted asset candidates
def clean_asset_candidate(candidate):
    if not candidate:
        return None

    # If list → take first element
    if isinstance(candidate, list):
        if not candidate:
            return None
        candidate = candidate[0]

    junk = {
        "say", "people", "what", "about", "for", "on", "reddit",
        "sentiment", "news", "latest", "recent"
    }

    words = [w for w in candidate.split() if w not in junk]
    return " ".join(words).strip()



# Reddit fetching imports
def ai_extract_asset_name(user_text: str) -> str | None:
    """
    AI fallback: extract ONLY the asset/company name from user text.
    Returns a clean string or None.
    """

    prompt = (
        "Extract the company or asset name from the text below.\n"
        "Rules:\n"
        "- Return ONLY the asset name\n"
        "- No explanations\n"
        "- No extra words\n"
        "- If none found, return NONE\n\n"
        f"Text: {user_text}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract asset names only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    result = response.choices[0].message.content.strip()

    if result.upper() == "NONE":
        return None

    # Safety cleanup
    return result.replace("on reddit", "").strip()



# Looser asset extraction for sentiment queries
def extract_asset_for_sentiment(text: str) -> list[str]:
    """
    Looser extraction for sentiment queries.
    Assumes asset name is usually the last meaningful noun.
    """

    stop_words = {
        "sentiment", "reddit", "people", "saying", "opinion",
        "about", "on", "is", "there", "any", "what", "are",
        "bullish", "bearish", "fear", "panic"
    }

    words = text.lower().replace(",", " ").split()

    candidates = [w for w in words if w not in stop_words and len(w) > 1]

    # Heuristic: last 1–2 words usually form the asset name
    if len(candidates) >= 2:
        return [" ".join(candidates[-2:])]
    elif candidates:
        return [candidates[-1]]

    return []
# AI-based asset extraction (stricter)
def ai_extract_asset(text: str) -> str | None:
    prompt = (
        "Extract the company or stock name from the following text.\n"
        "Rules:\n"
        "- Return ONLY the company/asset name\n"
        "- 1 to 3 words maximum\n"
        "- No explanation\n"
        "- If unclear, return NOTHING\n\n"
        f"Text: {text}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract company names only."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=10,
    )

    asset = response.choices[0].message.content.strip()

    if not asset or len(asset.split()) > 3:
        return None

    return asset.lower()
# Simple heuristic to filter out messy extractions
def looks_messy(asset: str) -> bool:
    bad_words = {"say", "people", "what", "about", "reddit", "on", "for"}
    words = asset.split()
    return any(w in bad_words for w in words)


# Detect if the user is asking for sentiment data
def is_sentiment_query(text: str) -> bool:
    keywords = [
        "sentiment", "people saying", "reddit", "opinion",
        "fear", "panic", "bullish", "bearish"
    ]
    return any(k in text for k in keywords)


# Detect if the user is asking for event data
def is_event_query(text: str) -> bool:
    keywords = [
        "news", "events", "latest", "recent",
        "announcement", "updates", "what happened"
    ]
    return any(k in text for k in keywords)



# Detect if the user is asking for performance data
def is_performance_query(text: str) -> bool:
    keywords = ["performance", "return", "returns", "gained", "lost"]
    return any(k in text for k in keywords)

# Detect if the user is asking for indicator data
def is_indicator_query(text: str) -> bool:
    keywords = [
        "indicator", "indicators", "moving average", "ma", "ema", "sma",
        "rsi", "bullish", "bearish", "breakout", "breakdown"
    ]
    return any(k in text for k in keywords)



# Detect timeframe from user text
def detect_timeframe(text: str) -> str | None:
    timeframe_map = {
        # Intraday
        "1 hour": "1h",
        "one hour": "1h",
        "last hour": "1h",
        "1h": "1h",

        "4 hour": "4h",
        "four hour": "4h",
        "last 4 hours": "4h",
        "4h": "4h",

        "today": "today",
        "intraday": "today",

        # Daily / longer
        "yesterday": "1d",
        "previous day": "1d",
        "last day": "1d",

        "last week": "1w",
        "previous week": "1w",

        "last month": "1m",
        "previous month": "1m",

        "last quarter": "3m",
        "last 3 months": "3m",

        "last 6 months": "6m",

        "last year": "1y",
        "previous year": "1y",

        "last 5 years": "5y",
    }

    for phrase, tf in timeframe_map.items():
        if phrase in text:
            return tf

    return None


def is_range_query(text: str) -> bool:
    keywords = ["high", "low", "high low", "range"]
    return any(k in text for k in keywords)


client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are a conservative financial market assistant.

Rules:
- Do NOT give buy/sell advice
- Do NOT promise profits
- Use provided data only
- Avoid time-based claims like 'right now'
- Be concise and factual
"""
def detect_intent(text: str) -> str:
    compare_keywords = ["compare", "vs", "versus", "which", "difference", "better"]
    context_keywords = ["what is", "tell me about", "explain", "about"]

    for phrase in context_keywords:
        if phrase in text:
            return "context"

    for word in compare_keywords:
        if word in text:
            return "compare"

    return "snapshot"


def extract_asset_queries(text: str) -> list[str]:
    stop_words = {
    "price", "prices", "of", "share", "shares", "stock", "stocks",
    "compare", "vs", "versus", "which", "is", "are", "the", "and",
    "between", "tell", "me", "about", "how", "doing",
    "what", "explain", "explanation",
    "last", "previous", "month", "week", "year",
    "months", "weeks", "years", "yesterday", "quarter","hour",
    "hours", "today", "intraday", "1h", "4h","performance","high","low","range","indicator", "indicators", "bullish", "bearish",
    "breakout", "breakdown", "rsi", "sma", "ema", "ma",
    "news", "latest", "recent", "events", "event",
    "happened", "happen", "with", "update", "updates","owner","sentiment ","people", "saying", "reddit", "opinion", "fear", "panic","bullish", "bearish"

    }


    words = text.lower().replace(",", " ").split()

    candidates = []
    current = []

    for word in words:
        if word in stop_words:
            if current:
                candidates.append(" ".join(current))
                current = []
        else:
            current.append(word)

    if current:
        candidates.append(" ".join(current))

    # remove duplicates & very short junk
    cleaned = []
    for c in candidates:
        if len(c) > 1 and c not in cleaned:
            cleaned.append(c)

    return cleaned



# Main handler function
def handle_user_message(user_text: str) -> str:
    text = user_text.lower()
    intent = detect_intent(text)
    
    # -------- SENTIMENT MODE --------
    if is_sentiment_query(text):

        # Step 1: rule-based extraction
        asset = extract_asset_for_sentiment(text)
        # 🔒 NORMALIZE: list → string (sentiment expects ONE asset)
        if isinstance(asset, list):
            asset = asset[0] if asset else None

        asset = clean_asset_candidate(asset)

        # Step 2: AI fallback if still messy
        if not asset or len(asset.split()) > 2:
            asset = ai_extract_asset_name(user_text)

        if not asset:
            return "Please mention the company or asset you want sentiment on."

        # Step 3: fetch Reddit attention
        attention = get_social_attention(asset)

        if attention["status"] == "no_signal":
            return f"No meaningful Reddit discussion was found for {asset.title()}."

        # Step 4: AI reasoning (safe, constrained)
        ai_prompt = (
            "You are a conservative equity research analyst.\n\n"
            f"{attention['analysis_input']}\n\n"
            "Provide a concise investor-focused assessment:\n"
            "- Summarize the dominant narrative\n"
            "- Describe the emotional tone\n"
            "- Assess whether this is short-term noise, "
            "medium-term uncertainty, or potential long-term risk\n"
            "- Explain portfolio relevance (monitor vs concern)\n"
            "- Do NOT give buy/sell advice\n"
            "- Do NOT predict price\n"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ai_prompt},
            ],
            timeout=15,
        )

        return response.choices[0].message.content
    # -------- IPO MODE --------
    # -------- IPO MODE --------
    if is_ipo_query(user_text):

        company = extract_ipo_company(user_text)

        if not company:
            return "Please mention the IPO name you want to analyze."

        try:
            from capabilities.ipo_analyzer import analyze_ipo

            report = analyze_ipo(company)

            if not report:
                return (
                    f"I couldn’t find detailed IPO documents for {company}.\n\n"
                    "However, this IPO may be upcoming, speculative, or not fully disclosed yet.\n"
                    "You can try again once more details are public."
                )

            return report

        except Exception as e:
            return (
                "IPO analysis is temporarily unavailable.\n"
                f"Reason: {str(e)}"
            )

        ipo_name = extract_ipo_name(user_text)

        if not ipo_name:
            return "Please mention the IPO name you want to analyze."

        # 1️⃣ Documents
        ipo_doc = get_ipo_documents(ipo_name)
        if not ipo_doc:
            return f"I couldn’t find IPO details for {ipo_name}."

        # 2️⃣ Financial analysis
        financial_analysis = analyze_financials(ipo_doc)

        # 3️⃣ Sentiment
        sentiment = analyze_ipo_sentiment(ipo_name)

        # 4️⃣ Red flags
        red_flags = analyze_red_flags(
            financials=ipo_doc["financials"],
            issue_details=ipo_doc.get("issue", {}),
            sector=None  # optional for now
        )

        # 5️⃣ Final report
        report = assemble_final_ipo_report(
            company=ipo_name,
            financials=financial_analysis,
            sentiment=sentiment,
            red_flags=red_flags
        )

        return report

    # -------- CONTEXT MODE (FIRST) --------
    if intent == "context":
        asset_queries = extract_asset_queries(text)

        if not asset_queries:
            return "Please mention the company or asset you want to know about."

        contexts = []
        for query in asset_queries:
            ctx = get_asset_context(query)
            if ctx:
                contexts.append(ctx)

        if not contexts:
            return (
                "I couldn’t identify the asset clearly. "
                "Please try using the company name."
            )

        replies = []
        for c in contexts:
            replies.append(f"{c['symbol']}:\n{c['description']}")

        return "\n\n".join(replies)
    # -------- EVENTS MODE --------
    if is_event_query(text):
        asset_queries = extract_asset_queries(text)

        if not asset_queries:
            return "Please mention the company name to check recent events."

        responses = []

        for asset in asset_queries:
            events_data = get_asset_events(asset_name=asset)
            events = events_data.get("events", [])

            # ✅ EARLY CONTINUE — SAFE
            if not events:
                # 🔹 HYBRID MODE: AI inference ONLY because no live data exists
                ai_prompt = (
                    f"You are a conservative financial analyst.\n\n"
                    f"No live, verifiable news was found for {asset.title()} from current sources.\n\n"
                    f"Provide contextual insight ONLY based on general business understanding:\n"
                    f"- Explain what typically influences this company's stock\n"
                    f"- Separate short-term vs long-term factors\n"
                    f"- Clearly state this is NOT live news\n"
                    f"- Do NOT invent events, analyst calls, numbers, or dates\n"
                    f"- Do NOT give buy/sell advice\n"
                )

                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": ai_prompt}
                        ],
                        timeout=15
                    )
                    responses.append(response.choices[0].message.content)
                except Exception:
                    responses.append(
                        f"No live news was found for {asset.title()}, and analysis could not be generated at this time."
                    )

                continue


            event_lines = []
            for e in events:
                event_lines.append(
                    f"- {e['title']} ({e['source']}): {e['description']}"
                )

            ai_prompt = (
                f"You are a conservative financial analyst.\n\n"
                f"The following are recent news events related to {asset.title()}:\n\n"
                + "\n".join(event_lines)
                + "\n\nYour task:\n"
                "- Explain what happened\n"
                "- Explain why these events matter\n"
                "- Separate short-term impact vs long-term impact\n"
                "- Explain potential portfolio relevance\n"
                "- Do NOT give buy/sell advice\n"
                "- Do NOT predict price levels\n"
                "- Keep it factual and risk-aware\n"
            )

            # ✅ OPENAI CALL INSIDE LOOP
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": ai_prompt}
                ]
            )

            responses.append(response.choices[0].message.content)

        return "\n\n".join(responses)



    # -------- RANGE MODE --------
    if is_range_query(text):
        timeframe = detect_timeframe(text)

        if not timeframe:
            return (
                "Please specify a timeframe like last week, last month, or last year "
                "to get the high and low."
            )

        asset_queries = extract_asset_queries(text)

        if not asset_queries:
            return "Please mention the company name for the high and low range."

        results = []

        for query in asset_queries:
            snap = get_market_snapshot(query)
            if not snap or not snap.get("resolved"):
                continue

            symbol = snap["symbol"]
            data = get_high_low(symbol, timeframe)

            if data:
                results.append(data)

        if not results:
            return (
                "Intraday high and low data isn’t available for this stock at the moment. "
                "This can happen outside market hours."
            )


        lines = []
        for r in results:
            lines.append(
                f"{r['symbol']} traded between ₹{r['low']} and ₹{r['high']} "
                f"from {r['start_date']} to {r['end_date']}."
            )

        ai_prompt = (
            "Historical price range data:\n"
            + "\n".join(lines)
            + "\n\nExplain this clearly in 1–2 sentences using only the data above."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ai_prompt}
            ]
        )

        return response.choices[0].message.content
    # -------- PERFORMANCE MODE --------
    if is_performance_query(text):
        timeframe = detect_timeframe(text)

        if not timeframe:
            return (
                "Please specify a timeframe like last month, last quarter, or last year "
                "to check performance."
            )

        asset_queries = extract_asset_queries(text)

        if not asset_queries:
            return "Please mention the company name to check performance."

        results = []

        for query in asset_queries:
            snap = get_market_snapshot(query)
            if not snap or not snap.get("resolved"):
                continue

            symbol = snap["symbol"]
            data = get_performance(symbol, timeframe)

            if data:
                results.append(data)

        if not results:
            return "I couldn’t fetch performance data for the requested stock(s)."

        lines = []
        for r in results:
            lines.append(
                f"{r['symbol']} moved from ₹{r['start_price']} to ₹{r['end_price']} "
                f"between {r['start_date']} and {r['end_date']} "
                f"({r['change']} / {r['change_pct']}%)."
            )

        ai_prompt = (
            "Historical performance data:\n"
            + "\n".join(lines)
            + "\n\nSummarize this performance clearly without judgment or advice."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ai_prompt}
            ]
        )

        return response.choices[0].message.content
    # -------- INDICATORS + SIGNALS MODE --------
    if is_indicator_query(text):
        asset_queries = extract_asset_queries(text)

        if not asset_queries:
            return "Please mention the company name to check indicators."

        results = []

        for query in asset_queries:
            snap = get_market_snapshot(query)
            if not snap or not snap.get("resolved"):
                continue

            symbol = snap["symbol"]
            indicators = get_indicators(symbol)
            if not indicators:
                continue

            signals = compute_signals(indicators)

            results.append({
                "symbol": symbol,
                "indicators": indicators,
                "signals": signals
            })

        if not results:
            return "I couldn’t compute indicators for the requested stock(s)."

        lines = []
        for r in results:
            ind = r["indicators"]
            sig = r["signals"]

            lines.append(
                f"{r['symbol']}:\n"
                f"- Price: ₹{ind['price']}\n"
                f"- SMA (20/50/200): ₹{ind['sma_20']} / ₹{ind['sma_50']} / ₹{ind['sma_200']}\n"
                f"- EMA (20/50): ₹{ind['ema_20']} / ₹{ind['ema_50']}\n"
                f"- RSI (14): {ind['rsi_14']}\n"
                f"- Trend bias: {sig['trend']} ({sig['trend_reason']})\n"
                f"- Momentum: {sig['momentum']} ({sig['momentum_reason']})\n"
                f"- Structure: {sig['structure']} ({sig['structure_reason']})"
            )

        ai_prompt = (
            "Technical indicator states derived from rule-based conditions:\n"
            + "\n\n".join(lines)
            + "\n\nExplain these states descriptively. "
            "Do not provide advice, predictions, or actions."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ai_prompt}
            ]
        )

        return response.choices[0].message.content

    # -------- SNAPSHOT / COMPARE MODE --------
    asset_queries = extract_asset_queries(text)

    if not asset_queries:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content

    snapshots = []

    for query in asset_queries:
        snap = get_market_snapshot(query)
        if snap and snap.get("resolved") and snap.get("data_available"):
            snapshots.append(snap)

    if not snapshots:
        return (
            "I couldn’t identify valid Indian stocks in your request. "
            "Please try using clear company names."
        )

    # -------- COMPARE MODE --------
    if intent == "compare" and len(snapshots) >= 2:
        lines = []
        for s in snapshots:
            lines.append(
                f"{s['symbol']}: ₹{s['price']} "
                f"({s['change']} / {s['change_pct']}%), "
                f"previous close on {s['prev_date']}"
            )

        ai_prompt = (
            "Market comparison data:\n"
            + "\n".join(lines)
            + "\n\nCompare these stocks briefly using only the data above. "
              "Do not give opinions or predictions."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ai_prompt}
            ]
        )
        return response.choices[0].message.content


   
    # -------- INDIVIDUAL SNAPSHOT MODE --------
    replies = []
    for s in snapshots:
        replies.append(
            f"{s['symbol']}: ₹{s['price']} "
            f"({s['change']} / {s['change_pct']}%) "
            f"vs previous close on {s['prev_date']}"
        )

    ai_prompt = (
        "Market snapshot data:\n"
        + "\n".join(replies)
        + "\n\nSummarize this information clearly without comparison or advice."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ai_prompt}
        ]
    )

    return response.choices[0].message.content
