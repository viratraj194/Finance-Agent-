import logging
import socket
import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN, PROXY_URL
from agent import handle_user_message
import os
import asyncio
from capabilities.daily_report import (
    add_subscriber,
    remove_subscriber,
    generate_daily_report,
    load_subscribers,
    get_last_run_date,
    save_last_run_date,
    get_ist_now
)
from capabilities.realtime_scanner import (
    realtime_breaking_news_task,
    add_alert_subscriber,
    remove_alert_subscriber
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# Suppress verbose logs from httpx/httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Track last network error log time to avoid flooding the console
_last_network_error_log = 0


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors but suppress repeated NetworkError floods (log at most once per 60s)."""
    global _last_network_error_log
    from telegram.error import NetworkError
    if isinstance(context.error, NetworkError):
        now = time.time()
        if now - _last_network_error_log > 60:
            logger.warning(
                "NetworkError: Cannot reach Telegram servers. "
                "Check your internet connection or set PROXY_URL in .env\n"
                f"Detail: {context.error}"
            )
            _last_network_error_log = now
        # Don't log the full traceback for every network retry
        return
    logger.error("Exception while handling an update:", exc_info=context.error)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "📊 *FinanceAI Bot Online*\n\n"
        "I am your AI-powered market assistant for Indian stocks (NSE).\n\n"
        "Here is what I can do for you:\n"
        "• *Pre-Market Dashboard*: Global cues, GIFT Nifty & opening predictions.\n"
        "• *Overnight Alerts*: Scan overnight news for watchlist impact.\n"
        "• *Stock Sentiment*: AI scoring (Bullish/Bearish) of the latest news.\n"
        "• *Gap Scanner*: Predict Gap-Up/Gap-Down opportunities at 9:15 AM.\n"
        "• *Market Snapshots*: Get real-time price & daily changes.\n"
        "• *Technical Analysis*: Check SMA, EMA, RSI, and trend signals.\n"
        "• *Historical Performance*: View returns and high/low ranges (1w to 5y).\n"
        "• *News & Events*: Get the latest headlines and corporate updates.\n"
        "• *IPO Analysis*: Get deep-dive reports on upcoming/recent IPOs.\n"
        "• *Social Sentiment*: See what investors are saying on Reddit.\n"
        "• *Deep Research*: Comprehensive overview of any company.\n"
        "• *Daily Market Impact Report*: Automatically analyze daily news impact on stocks & ETFs.\n"
        "  └ `/subscribe` - Get reports automatically at 08:50 AM IST\n"
        "  └ `/unsubscribe` - Stop receiving daily reports\n"
        "  └ `/report` - Get the latest report on-demand\n"
        "• *Live Breaking News Alerts*: Get notified instantly of market crashes/shocks.\n"
        "  └ `/breaking_market_alert` - Subscribe to live urgent alerts\n"
        "  └ `/stop_market_alert` - Unsubscribe from live alerts\n\n"
        "*Example Queries:*\n"
        "💬 \"Show me the premarket dashboard\"\n"
        "💬 \"What is the news sentiment for Reliance?\"\n"
        "💬 \"Scan for gaps today\"\n"
        "💬 \"Show me overnight alerts\"\n"
        "💬 \"What is the price of Reliance?\"\n"
        "💬 \"Technical analysis for TCS\"\n"
        "💬 \"Tell me about Infosys (Deep Research)\"\n\n"
        "How can I help you today?"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # Run the CPU/IO bound handler in an executor so we don't block the loop
    loop = asyncio.get_running_loop()
    handler_task = loop.run_in_executor(None, handle_user_message, user_text)
    
    # Wait for either the handler to finish or 5 seconds to pass
    status_message = None
    try:
        done, pending = await asyncio.wait(
            [handler_task],
            timeout=5.0
        )
        
        if handler_task in pending:
            # If it takes more than 5 seconds, send a status update message
            lower_text = user_text.lower()
            if any(k in lower_text for k in ["research", "deep dive", "everything about", "detailed"]):
                msg = "🔍 *Running deep research...* Gathering fundamentals, technical signals, news, and sentiment in parallel. This may take 10-15 seconds."
            elif any(k in lower_text for k in ["ipo", "listing", "drhp"]):
                msg = "⏳ *Analyzing IPO details...* Fetching DRHP documents, financial statements, and analyzing risks. Please stand by."
            elif any(k in lower_text for k in ["war", "conflict", "sanction", "middle east", "russia", "ukraine", "iran", "israel", "trade war", "tariff"]):
                msg = "🌍 *Analyzing geopolitical impact...* Fetching live prices for affected sectors, event news, and synthesizing winners vs losers. Please stand by (30-60 seconds)."
            elif any(k in lower_text for k in ["sector", "scan", "list 3", "grow this week"]):
                msg = "🔎 *Scanning sectors and stocks...* Analyzing technical indicators, trends, and news in parallel for all 35 sector stocks. Please stand by."
            elif any(k in lower_text for k in ["alert", "overnight"]):
                msg = "🔔 *Scanning overnight news and alerts...* Please stand by."
            elif any(k in lower_text for k in ["premarket", "dashboard", "gift nifty"]):
                msg = "📈 *Fetching Pre-Market Dashboard...* Checking global cues and GIFT Nifty."
            elif any(k in lower_text for k in ["gap", "gap-up", "gap-down"]):
                msg = "🚀 *Scanning for opening gap opportunities...* Please stand by."
            else:
                msg = "⏳ *Gathering data and generating analysis...* Please stand by."
            
            status_message = await update.message.reply_text(msg, parse_mode='Markdown')
            
            # Now wait for the handler task to complete fully
            reply = await handler_task
        else:
            # Finished within 5 seconds
            reply = handler_task.result()
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        reply = f"❌ An error occurred while parsing your request: {e}"

    # Clean up interim status message first to keep chat clean
    if status_message:
        try:
            await status_message.delete()
        except Exception:
            pass

    # Telegram has a 4096 char limit per message — split long replies into chunks
    MAX_LEN = 4000
    if len(reply) <= MAX_LEN:
        await update.message.reply_text(reply)
    else:
        # Split on newlines to avoid cutting mid-sentence
        chunks = []
        current = ""
        for line in reply.splitlines(keepends=True):
            if len(current) + len(line) > MAX_LEN:
                if current:
                    chunks.append(current)
                current = line
            else:
                current += line
        if current:
            chunks.append(current)

        for i, chunk in enumerate(chunks):
            await update.message.reply_text(chunk)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if add_subscriber(chat_id):
        await update.message.reply_text(
            "🔔 *Subscribed to Daily Market Impact Reports!*\n\n"
            "You will now receive a report automatically every morning at 08:50 AM (IST) based on the latest global and domestic news.\n\n"
            "To unsubscribe at any time, use /unsubscribe.\n"
            "To get the latest report on-demand, use /report.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "ℹ️ You are already subscribed to the daily reports.\n"
            "Use /report to get the latest report on-demand or /unsubscribe to cancel."
        )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if remove_subscriber(chat_id):
        await update.message.reply_text(
            "🔕 *Unsubscribed from Daily Market Impact Reports.*\n\n"
            "You will no longer receive the automatic morning reports. You can subscribe again anytime using /subscribe."
        )
    else:
        await update.message.reply_text(
            "ℹ️ You were not subscribed to the daily reports.\n"
            "Use /subscribe if you'd like to sign up."
        )


async def subscribe_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if add_alert_subscriber(chat_id):
        await update.message.reply_text(
            "🚨 *Subscribed to Live Breaking Market Alerts!*\n\n"
            "You will now receive instant push notifications if our AI detects any highly urgent market-moving news (like commodity crashes, geopolitical shocks, or major regulatory bans).\n\n"
            "To unsubscribe at any time, use /stop_market_alert.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "ℹ️ You are already subscribed to breaking market alerts.\n"
            "Use /stop_market_alert to cancel."
        )

async def unsubscribe_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if remove_alert_subscriber(chat_id):
        await update.message.reply_text(
            "🔕 *Unsubscribed from Live Breaking Market Alerts.*\n\n"
            "You will no longer receive instant push notifications for urgent news."
        )
    else:
        await update.message.reply_text(
            "ℹ️ You were not subscribed to breaking market alerts."
        )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    status_msg = await update.message.reply_text(
        "⏳ *Generating the latest market impact report on-demand...* This may take a minute.",
        parse_mode="Markdown"
    )
    
    loop = asyncio.get_running_loop()
    try:
        report_path = await loop.run_in_executor(None, generate_daily_report)
        caption = "📊 *Daily Market Impact Report (On-Demand)*\n\nHere is the latest analysis on how news can affect stocks and ETFs."
        
        with open(report_path, "rb") as document:
            await context.bot.send_document(
                chat_id=chat_id,
                document=document,
                filename=os.path.basename(report_path),
                caption=caption,
                parse_mode="Markdown"
            )
        
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error generating on-demand report: {e}")
        await update.message.reply_text(f"❌ Failed to generate report: {e}")


async def run_and_send_daily_report(application):
    loop = asyncio.get_running_loop()
    report_path = await loop.run_in_executor(None, generate_daily_report)
    
    subscribers = load_subscribers()
    if not subscribers:
        logger.info("No subscribers found to send report to.")
        return
        
    logger.info(f"Sending daily report to {len(subscribers)} subscribers...")
    caption = "📊 *Daily Market Impact Report*\n\nHere is your daily report on how latest news and events can affect stocks and ETFs."
    
    for chat_id in subscribers:
        try:
            with open(report_path, "rb") as document:
                await application.bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    filename=os.path.basename(report_path),
                    caption=caption,
                    parse_mode="Markdown"
                )
            logger.info(f"Successfully sent report to chat_id {chat_id}")
        except Exception as e:
            logger.error(f"Error sending report to chat_id {chat_id}: {e}")


async def check_and_run_daily_report(application):
    ist_now = get_ist_now()
    today_str = ist_now.strftime("%Y-%m-%d")
    last_run = get_last_run_date()
    
    # If the current time (IST) is >= 08:50 AM, and we haven't run today yet
    if (ist_now.hour > 8 or (ist_now.hour == 8 and ist_now.minute >= 50)) and last_run != today_str:
        logger.info(f"Daily report for {today_str} hasn't run yet. Triggering report...")
        save_last_run_date(today_str)
        try:
            await run_and_send_daily_report(application)
        except Exception as e:
            logger.error(f"Failed to run daily report: {e}")
            # Reset run date state so it can retry
            save_last_run_date(last_run)


async def daily_report_scheduler(application):
    logger.info("Daily report scheduler task started.")
    while True:
        try:
            await check_and_run_daily_report(application)
        except Exception as e:
            logger.error(f"Error in check_and_run_daily_report: {e}")
        # Check every 60 seconds
        await asyncio.sleep(60)


async def post_init(application) -> None:
    # Start the scheduler as a background task on the application's event loop
    task = asyncio.create_task(daily_report_scheduler(application))
    application.bot_data['scheduler_task'] = task
    
    rt_task = asyncio.create_task(realtime_breaking_news_task(application))
    application.bot_data['rt_task'] = rt_task


async def post_shutdown(application) -> None:
    # Clean up the scheduler task during shutdown to avoid pending task warning
    task = application.bot_data.get('scheduler_task')
    if task:
        logger.info("Cancelling daily report scheduler task...")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Daily report scheduler task successfully cancelled.")
            
    rt_task = application.bot_data.get('rt_task')
    if rt_task:
        logger.info("Cancelling realtime news scanner task...")
        rt_task.cancel()
        try:
            await rt_task
        except asyncio.CancelledError:
            logger.info("Realtime news scanner task successfully cancelled.")


def check_network() -> bool:
    """Quick check if api.telegram.org is reachable via DNS."""
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo("api.telegram.org", 443)
        return True
    except OSError:
        return False


def main():
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not defined in the environment!")
        return

    # ── Network connectivity check ──────────────────────────────────────────
    if not PROXY_URL and not check_network():
        logger.warning("DNS resolution for api.telegram.org failed. Applying DNS bypass (Direct IP connection).")
        
        # Monkeypatch socket.getaddrinfo to bypass ISP DNS block for Telegram
        original_getaddrinfo = socket.getaddrinfo
        def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            if host == "api.telegram.org":
                # Use known Telegram API IP to bypass DNS poisoning
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('149.154.167.220', port))]
            return original_getaddrinfo(host, port, family, type, proto, flags)
        
        socket.getaddrinfo = custom_getaddrinfo
    # ────────────────────────────────────────────────────────────────────────


    # Build application with proxy support and lifecycle hooks
    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown)

    if PROXY_URL:
        logger.info(f"Using proxy configured in .env: {PROXY_URL}")
        request_obj = HTTPXRequest(
            proxy=PROXY_URL,
            connect_timeout=30.0,
            read_timeout=30.0,
        )
        builder = builder.request(request_obj)
    else:
        # Even without a proxy, set generous timeouts for resilience
        request_obj = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
        )
        builder = builder.request(request_obj)

    app = builder.build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("breaking_market_alert", subscribe_alerts))
    app.add_handler(CommandHandler("stop_market_alert", unsubscribe_alerts))
    
    # Delegate remaining intent detection to the main text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Register the error handler
    app.add_error_handler(error_handler)

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

