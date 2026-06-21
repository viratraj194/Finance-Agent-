# Finance-Agent-

> ⚠️ **CRITICAL DIRECTIVE FOR ALL DEVS & AI AGENTS** ⚠️
> EVERY TIME you make a change or complete a task, you MUST update this `README.md` file (in the Changelog section below) to reflect the changes for better understanding. 
> EVERY new dev or AI Agent MUST read this file first to fully understand the project before making any changes.

📊 Market Intelligence AI Agent (Telegram Bot)

A Telegram-based AI-powered market assistant that analyzes stocks, news, and global events in real time and explains market conditions through natural conversation.

🧠 Overview

Market Intelligence AI Agent is a conversational AI system built to act like a personal market analyst.

You can chat with it on Telegram and ask things like:

“What happened in the market today?”

“Any news affecting TCS / RELIANCE / BTC?”

“Explain the current condition of this stock.”

“What international events might impact markets?”

The agent:

Understands natural language

Fetches live stock & crypto data

Tracks company & global news

Maintains short-term memory

Uses AI reasoning to explain what’s happening in the market

This project combines AI + real-time data + backend engineering + cloud deployment into a single intelligent system.

🎯 Goals of This Project

Build a real AI market assistant, not just a chatbot

Centralize market events, stock data, and news analysis

Learn how to design AI agents with tools/function calling

Create a portfolio-grade fintech project

Lay foundation for future expansion (web app, alerts, WhatsApp, blockchain analytics)

🚀 Core Features

🤖 AI-powered natural language conversation

📈 Live stock & crypto price fetching

🗞️ Company-specific and global news analysis

🌍 International event impact explanation

🧠 Short-term chat memory (context-aware replies)

🔌 Tool-based agent logic (AI decides what data to fetch)

☁️ Cloud hosted – accessible from phone, tablet, or PC

🔐 Secure API key handling & scalable backend design

🏗️ System Architecture
User (Telegram App)
        ↓
Telegram Bot API
        ↓
    Python
        ↓
AI Engine (OpenAI)
 + Market APIs (Stocks)
 + News APIs (Events)
 + Database (Chat Memory)
        ↓
AI-generated analysis
        ↓
Response back to Telegram


Telegram acts as the chat interface.
The backend acts as the brain and controller.
The AI + APIs act as the intelligence layer.

🧩 Project Phases
Phase	Focus	Description
1	Connection	Telegram bot + Python backend (basic replies)
2	Intelligence	OpenAI integration (natural conversation)
3	Data	Live stock & news fetching
4	Agent Logic	Function calling, decision-making AI
5	Production	Database + cloud hosting (24/7 uptime)
🛠️ Tech Stack
Chat Platform

Telegram Bot API

Backend

Python


AI

OpenAI API (GPT models)

Market Data

yfinance

Alpha Vantage / Finnhub

Binance API (crypto)

News & Events

NewsAPI

Finnhub News

Economic calendar sources

Database

SQLite (development)

PostgreSQL (production)

Hosting

Railway / Render / Fly.io

📁 Suggested Folder Structure
market-ai-agent/
│
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── bot.py               # Telegram bot handler
│   ├── ai_engine.py         # OpenAI logic
│   ├── market_data.py       # Stocks/crypto APIs
│   ├── news.py              # News fetching
│   ├── agent.py             # Tool calling & reasoning
│   ├── database.py          # DB connection
│   └── models.py            # Chat/session models
│
├── requirements.txt
├── .env.example
├── README.md
└── LICENSE

⚙️ How It Works (Simplified Flow)

User sends message on Telegram

Backend receives it

AI interprets the intent

If needed, system fetches:

Market data

News

Events

AI analyzes everything together

Final explanation is sent back to user

🧪 Example Use Cases

Daily market summary

Stock-specific event tracking

News-driven price movement explanation

Global macro impact analysis

Learning markets through conversation

🛡️ Disclaimer

This project is for educational and analytical purposes only.
It does not provide financial advice or guaranteed trading signals.

🌱 Future Roadmap

Price & news alerts

User watchlists

Web-based chat interface

Discord & WhatsApp integration

Chart image analysis

Sector & sentiment dashboards

Blockchain & on-chain analytics

## 📝 AI / Developer Changelog

* **2026-06-19**:
  * **Global Pre-Market Dashboard**: Created `market_dashboard.py` — fetches 20 symbols in parallel via yfinance (US markets, Asian markets, European markets, Brent Crude, Gold, Silver, USD/INR, Dollar Index, India VIX, Nifty 50, Bank Nifty, and 5 Indian ADRs). Pure data formatting with `format_dashboard_text()` — zero AI, zero hallucination possible.
  * **Options Intelligence (PCR + Pivot Levels)**: Created `options_data.py` — fetches Nifty Put-Call Ratio with 3-tier fallback (nselib → NSE API → nselib urlfetch) and computes classic pivot points (S1-S3, Pivot, R1-R3) for both Nifty and BankNifty using previous day OHLC from yfinance.
  * **Report Restructure (Data-First Architecture)**: Completely restructured `daily_report.py` to lead with a hard-data dashboard (no AI) followed by AI analysis grounded in real numbers. Now fetches 5 data sources in parallel (was 2): news, NSE institutional, global markets, options snapshot, and earnings calendar (Finnhub — was built but never used). Increased LLM max_tokens from 3000 to 4000.
  * **Anti-Hallucination Guardrails**: Overhauled LLM prompt to prevent the model from inventing stock recommendations, fake analyst names, or generic "bullish RSI" catalysts. Every stock mention must now cite the exact data source. Changed report sections to be data-driven (Opening Outlook references dashboard numbers, Watchlist requires cited proof).
  * **NSE JSON Parsing Fix**: Fixed `nse_data.py` to handle non-JSON framing bytes in NSE API responses (e.g., `\xb0\x01\x10{...}\x03`). Added a fallback that strips leading/trailing junk characters to extract valid JSON.
  * **Discord Bot Enhancements**: Updated `discord_main.py` `/start` command with new capabilities, and `/report` now sends a quick-glance dashboard text preview (readable on mobile) before attaching the full .md report file.

* **2026-06-18**:
  * **Daily Report Schedule Optimization**: Shifted the daily report background trigger from 09:00 AM to 08:50 AM IST in both `main.py` and `discord_main.py` to give the user 25 minutes of edge before the 09:15 AM market open.
  * **Zero-Minute Corporate Announcements**: Created `bse_announcements.py` to scrape the hidden BSE API for live corporate filings (contracts, earnings, board meetings) and integrated it into both the daily report and live scanner.
  * **Insider Trading / SAST Tracker**: Implemented a parser in `nse_data.py` (`get_insider_trading`) that tracks massive open-market stock purchases by Promoters and Directors. Added a dedicated "Smart Money" section to the LLM prompt to highlight these setups.
  * **eProcure Government Tender Scraper**: Built `eprocure_scraper.py` to systematically parse the Central Public Procurement Portal (`eprocure.gov.in`) for massive infrastructure and defense contracts, supplementing the Google News tender fallback.

* **2026-06-17**:
  * **Discord Fallback Integration**: Switched the fallback strategy from WhatsApp to Discord, as it provides a true 1:1 replacement for Telegram bots without requiring phone numbers. Created `discord_main.py` mimicking the exact background schedulers and features of the main Telegram bot, and added `discord.py` to the requirements. Removed all OpenWA/WhatsApp related files to keep the codebase clean and focused on cloud-based bot APIs.

* **2026-06-16**: 
  * **Daily Report Rendering Fix**: Addressed an issue where `daily_report.py` was generating Markdown tables without a standard separator row (`|---|---|`). Updated the LLM system prompt to explicitly enforce this formatting, ensuring tables render correctly in Telegram and other Markdown viewers.
  * **Deep Scraping Integration**: Made `scrapling_fetcher.py` synchronous and integrated it into the daily report pipeline to extract full-text content of articles rather than just relying on RSS summaries, feeding up to 500 characters of deep content per article into the LLM context.
  * **Realtime Scanner Patch**: Fixed an `object list can't be used in 'await' expression` crash in `realtime_scanner.py` by offloading the newly synchronous `scrapling_fetcher` into an async `loop.run_in_executor` thread pool.
  * **Broader Market & Breakout Detection**: Modified `nse_data.py` to stop artificially filtering gainers to NIFTY-50 stocks only, pulling the top 10 overall gainers across the market instead. Wired this `top_gainers` array into the `daily_report.py` LLM context so the AI can actually see smallcap/midcap breakouts.
  * **Smart Money Paradigm Shift**: Rewrote the core LLM prompt in `daily_report.py` to adopt an "Elite Institutional Quant" persona. The AI is now instructed to actively hunt for pre-market catalysts, stealth government orders, and asymmetric trade setups to give users a massive edge over retail investors before the market opens.

🧑‍💻 Author

Built by Virat Raj
A personal project exploring AI agents, market intelligence, and full-stack systems.