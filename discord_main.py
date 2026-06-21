import os
import asyncio
import logging
import discord
from discord.ext import commands, tasks

from config import DISCORD_BOT_TOKEN
from agent import handle_user_message
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

import capabilities.daily_report as dr
import capabilities.realtime_scanner as rs

# Isolate Discord subscribers from Telegram subscribers
dr.SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.dirname(dr.__file__)), "data", "discord_subscribers.json")
rs.ALERT_SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.dirname(rs.__file__)), "data", "discord_alert_subscribers.json")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Intents are required for reading messages
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

# ---------------------------------------------------------
# MOCK TELEGRAM APP TO REUSE EXISTING SCANNERS UNMODIFIED
# ---------------------------------------------------------
class MockTelegramBot:
    def __init__(self, discord_bot):
        self._discord_bot = discord_bot

    async def send_message(self, chat_id, text, parse_mode=None):
        try:
            # chat_id can be a user ID or a channel ID
            target = self._discord_bot.get_user(int(chat_id)) or self._discord_bot.get_channel(int(chat_id))
            if not target:
                # If user isn't cached, try fetching
                target = await self._discord_bot.fetch_user(int(chat_id))
            
            if target:
                # Discord handles markdown natively, no parse_mode needed
                await target.send(text)
        except Exception as e:
            logger.error(f"Discord MockBot send_message failed for {chat_id}: {e}")

class MockTelegramApplication:
    def __init__(self, discord_bot):
        self.bot = MockTelegramBot(discord_bot)

# ---------------------------------------------------------
# BACKGROUND TASKS
# ---------------------------------------------------------
@tasks.loop(minutes=1.0)
async def daily_report_scheduler():
    ist_now = get_ist_now()
    today_str = ist_now.strftime("%Y-%m-%d")
    last_run = get_last_run_date()
    
    # If the current time (IST) is >= 08:50 AM, and we haven't run today yet
    if (ist_now.hour > 8 or (ist_now.hour == 8 and ist_now.minute >= 50)) and last_run != today_str:
        logger.info(f"Daily report for {today_str} hasn't run yet. Triggering report...")
        save_last_run_date(today_str)
        try:
            loop = asyncio.get_running_loop()
            report_path = await loop.run_in_executor(None, generate_daily_report)
            
            subscribers = load_subscribers()
            if not subscribers:
                return
            
            caption = "📊 **Daily Market Impact Report**\n\nHere is your daily report on how latest news and events can affect stocks and ETFs."
            
            for chat_id in subscribers:
                try:
                    target = bot.get_user(int(chat_id)) or bot.get_channel(int(chat_id))
                    if not target:
                        target = await bot.fetch_user(int(chat_id))
                    if target:
                        await target.send(content=caption, file=discord.File(report_path))
                except Exception as e:
                    logger.error(f"Error sending report to {chat_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to run daily report: {e}")
            save_last_run_date(last_run) # reset so it tries again

@bot.event
async def on_ready():
    logger.info(f"Discord Bot is online as {bot.user}")
    daily_report_scheduler.start()
    
    # Start the realtime news scanner as a background task
    mock_app = MockTelegramApplication(bot)
    bot.loop.create_task(realtime_breaking_news_task(mock_app))

# ---------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------
@bot.command(name='start')
async def start_cmd(ctx):
    welcome_text = (
        "📊 **FinanceAI Bot Online**\n\n"
        "I am your AI-powered market assistant for Indian stocks (NSE).\n\n"
        "Here is what I can do for you:\n"
        "• **Pre-Market Dashboard**: US/Asia/Europe markets, Crude Oil, Gold, USD/INR, VIX, Indian ADRs.\n"
        "• **Key Levels & Options**: Nifty/BankNifty pivot points (S1-S3, R1-R3), Put-Call Ratio.\n"
        "• **Institutional Flows**: FII/DII cash flows, FII derivatives positioning, block deals.\n"
        "• **Insider Trading**: Promoter/Director open-market purchases (smart money signals).\n"
        "• **Deep Research**: Comprehensive overview of any company.\n"
        "• **Sector Scanner**: Technical scan of 35 stocks across 7 sectors with trade setups.\n"
        "• **Gap Scanner**: Predict Gap-Up/Gap-Down opportunities at 9:15 AM.\n"
        "• **Daily Market Report**: Full pre-market intelligence with hard data + AI analysis.\n"
        "  └ `/subscribe` - Get reports automatically at 08:50 AM IST\n"
        "  └ `/unsubscribe` - Stop receiving daily reports\n"
        "  └ `/report` - Get the latest report on-demand\n"
        "• **Live Breaking News Alerts**: Get notified instantly of market crashes/shocks.\n"
        "  └ `/breaking_market_alert` - Subscribe to live urgent alerts\n"
        "  └ `/stop_market_alert` - Unsubscribe from live alerts\n\n"
        "Just type your questions directly here!"
    )
    await ctx.send(welcome_text)

@bot.command(name='subscribe')
async def subscribe_cmd(ctx):
    chat_id = ctx.author.id if not ctx.guild else ctx.channel.id
    if add_subscriber(chat_id):
        await ctx.send("🔔 **Subscribed to Daily Market Impact Reports!**\nYou will receive a report automatically every morning at 08:50 AM (IST).")
    else:
        await ctx.send("ℹ️ You are already subscribed.")

@bot.command(name='unsubscribe')
async def unsubscribe_cmd(ctx):
    chat_id = ctx.author.id if not ctx.guild else ctx.channel.id
    if remove_subscriber(chat_id):
        await ctx.send("🔕 **Unsubscribed from Daily Market Impact Reports.**")
    else:
        await ctx.send("ℹ️ You were not subscribed.")

@bot.command(name='breaking_market_alert')
async def breaking_market_alert_cmd(ctx):
    chat_id = ctx.author.id if not ctx.guild else ctx.channel.id
    if add_alert_subscriber(chat_id):
        await ctx.send("🚨 **Subscribed to Live Breaking Market Alerts!**\nYou will now receive instant push notifications for urgent news.")
    else:
        await ctx.send("ℹ️ You are already subscribed to breaking market alerts.")

@bot.command(name='stop_market_alert')
async def stop_market_alert_cmd(ctx):
    chat_id = ctx.author.id if not ctx.guild else ctx.channel.id
    if remove_alert_subscriber(chat_id):
        await ctx.send("🔕 **Unsubscribed from Live Breaking Market Alerts.**")
    else:
        await ctx.send("ℹ️ You were not subscribed.")

@bot.command(name='report')
async def report_cmd(ctx):
    status_msg = await ctx.send("⏳ **Generating the latest market impact report on-demand...** This may take a minute.\n(Fetching global markets, NSE data, options, news in parallel...)")
    try:
        loop = asyncio.get_running_loop()
        report_path = await loop.run_in_executor(None, generate_daily_report)

        # Send a quick dashboard preview as text (readable in Discord mobile)
        dashboard_preview = ""
        try:
            from providers.market_dashboard import get_pre_market_dashboard, format_dashboard_text
            dashboard_data = await loop.run_in_executor(None, get_pre_market_dashboard)
            dashboard_preview = format_dashboard_text(dashboard_data)
        except Exception:
            pass

        if dashboard_preview:
            # Send dashboard as a quick-glance text message (fits Discord's 2000 char limit)
            preview_chunks = [dashboard_preview[i:i+1900] for i in range(0, len(dashboard_preview), 1900)]
            for chunk in preview_chunks:
                await ctx.send(f"```\n{chunk}\n```")

        caption = "📊 **Full Daily Market Intelligence Report** (attached below)"
        await ctx.send(content=caption, file=discord.File(report_path))
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error generating on-demand report: {e}")
        await ctx.send(f"❌ Failed to generate report: {e}")

# ---------------------------------------------------------
# TEXT MESSAGE HANDLER
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    # Don't respond to ourselves or other bots
    if message.author.bot:
        return

    # Process commands first
    if message.content.startswith('/'):
        await bot.process_commands(message)
        return

    # Otherwise treat as normal user query
    user_text = message.content
    lower_text = user_text.lower()
    
    # Optional typing indicator
    async with message.channel.typing():
        # Determine status message
        if any(k in lower_text for k in ["research", "deep dive", "everything about", "detailed"]):
            msg = "🔍 **Running deep research...** Gathering fundamentals, technical signals, news, and sentiment in parallel. This may take 10-15 seconds."
        elif any(k in lower_text for k in ["ipo", "listing", "drhp"]):
            msg = "⏳ **Analyzing IPO details...** Fetching DRHP documents, financial statements, and analyzing risks."
        elif any(k in lower_text for k in ["war", "conflict", "sanction", "middle east", "russia", "ukraine", "iran", "israel", "trade war", "tariff"]):
            msg = "🌍 **Analyzing geopolitical impact...** Fetching live prices and synthesizing winners vs losers. (30-60 seconds)."
        elif any(k in lower_text for k in ["sector", "scan", "list 3", "grow this week"]):
            msg = "🔎 **Scanning sectors and stocks...** Analyzing technical indicators and trends."
        elif any(k in lower_text for k in ["alert", "overnight", "premarket", "dashboard", "gift nifty", "gap"]):
            msg = "📈 **Scanning pre-market and overnight data...**"
        else:
            msg = "⏳ **Analyzing...**"
            
        status_message = await message.channel.send(msg)

        try:
            loop = asyncio.get_running_loop()
            reply = await loop.run_in_executor(None, handle_user_message, user_text)
            
            # Clean up interim status message
            await status_message.delete()
            
            # Discord message limit is 2000 chars, so we chunk it just like Telegram (which was 4000)
            MAX_LEN = 1900
            if len(reply) <= MAX_LEN:
                await message.channel.send(reply)
            else:
                chunks = []
                current = ""
                for line in reply.splitlines(keepends=True):
                    if len(current) + len(line) > MAX_LEN:
                        chunks.append(current)
                        current = line
                    else:
                        current += line
                if current:
                    chunks.append(current)
                
                for chunk in chunks:
                    await message.channel.send(chunk)
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await status_message.edit(content=f"❌ An error occurred while parsing your request: {e}")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        logger.critical("DISCORD_BOT_TOKEN is not defined in the environment!")
    else:
        logger.info("Starting Discord Bot...")
        bot.run(DISCORD_BOT_TOKEN)
