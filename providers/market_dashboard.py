import yfinance as yf
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Suppress yfinance internal error logging to keep the console clean
yf_logger = logging.getLogger('yfinance')
yf_logger.setLevel(logging.CRITICAL)

# ── Symbol definitions ────────────────────────────────────────────────────────

US_MARKETS = [
    ('^GSPC',  'S&P 500'),
    ('^IXIC',  'Nasdaq'),
    ('^DJI',   'Dow Jones'),
]

ASIAN_MARKETS = [
    ('^N225',     'Nikkei 225'),
    ('^HSI',      'Hang Seng'),
    ('000001.SS', 'Shanghai'),
]

EUROPEAN_MARKETS = [
    ('^FTSE',  'FTSE 100'),
    ('^GDAXI', 'DAX'),
]

COMMODITIES = [
    ('BZ=F', 'Brent Crude'),
    ('CL=F', 'WTI Crude'),
    ('GC=F', 'Gold'),
    ('SI=F', 'Silver'),
]

CURRENCIES = [
    ('USDINR=X',  'USD/INR'),
    ('DX-Y.NYB',  'Dollar Index'),
]

INDIA_VIX = ('^INDIAVIX', 'India VIX')

INDIA_INDICES = [
    ('^NSEI',     'Nifty 50'),
    ('^NSEBANK',  'Bank Nifty'),
]

INDIAN_ADRS = [
    ('INFY', 'Infosys'),
    ('HDB',  'HDFC Bank'),
    ('IBN',  'ICICI Bank'),
    ('WIT',  'Wipro'),
    ('RDY',  "Dr Reddy's"),
]


# ── Helper ────────────────────────────────────────────────────────────────────

def _fetch_quote(symbol: str, name: str) -> dict | None:
    """Fetch latest price data for a single symbol using yfinance history.

    Returns a dict with name, symbol, price, change, change_pct, prev_close
    or None on any error.
    """
    try:
        hist = yf.Ticker(symbol).history(period='5d')
        if hist.empty or len(hist) < 2:
            logger.warning("Insufficient history for %s (%s)", name, symbol)
            return None

        latest = hist.iloc[-1]
        previous = hist.iloc[-2]

        price = round(float(latest['Close']), 2)
        prev_close = round(float(previous['Close']), 2)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

        return {
            'name': name,
            'symbol': symbol,
            'price': price,
            'change': change,
            'change_pct': change_pct,
            'prev_close': prev_close,
        }
    except Exception as exc:
        logger.error("Failed to fetch %s (%s): %s", name, symbol, exc)
        return None


def _fetch_group(symbols: list[tuple[str, str]], executor: ThreadPoolExecutor) -> list[dict]:
    """Submit a group of (symbol, name) pairs and collect non-None results."""
    futures = {
        executor.submit(_fetch_quote, sym, name): name
        for sym, name in symbols
    }
    results = []
    for future in as_completed(futures):
        result = future.result()
        if result is not None:
            results.append(result)
    # Preserve the original ordering from the symbols list
    order = {name: idx for idx, (_, name) in enumerate(symbols)}
    results.sort(key=lambda r: order.get(r['name'], 999))
    return results


# ── Main function ─────────────────────────────────────────────────────────────

def get_pre_market_dashboard() -> dict:
    """Fetch all pre-market data in parallel and return a structured dict.

    Designed to be called before Indian market opens at 9:15 AM IST.
    Uses a thread pool with 10 workers to fetch ~20 symbols concurrently.
    """
    logger.info("Fetching pre-market dashboard data…")

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Launch all groups concurrently — _fetch_group itself submits to
        # the shared executor, so all symbols across every group compete
        # for the same 10 worker threads.
        us_future      = executor.submit(_fetch_group, US_MARKETS, executor)
        asian_future   = executor.submit(_fetch_group, ASIAN_MARKETS, executor)
        europe_future  = executor.submit(_fetch_group, EUROPEAN_MARKETS, executor)
        comm_future    = executor.submit(_fetch_group, COMMODITIES, executor)
        curr_future    = executor.submit(_fetch_group, CURRENCIES, executor)
        vix_future     = executor.submit(_fetch_quote, INDIA_VIX[0], INDIA_VIX[1])
        indices_future = executor.submit(_fetch_group, INDIA_INDICES, executor)
        adrs_future    = executor.submit(_fetch_group, INDIAN_ADRS, executor)

        us_markets       = us_future.result()
        asian_markets    = asian_future.result()
        european_markets = europe_future.result()
        commodities      = comm_future.result()
        currencies       = curr_future.result()
        india_vix        = vix_future.result()
        india_indices    = indices_future.result()
        indian_adrs      = adrs_future.result()

    # IST timestamp
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    timestamp = datetime.datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S IST')

    dashboard = {
        'us_markets': us_markets,
        'asian_markets': asian_markets,
        'european_markets': european_markets,
        'commodities': commodities,
        'currencies': currencies,
        'india_vix': india_vix,
        'india_indices': india_indices,
        'indian_adrs': indian_adrs,
        'timestamp': timestamp,
    }

    total = (
        len(us_markets) + len(asian_markets) + len(european_markets)
        + len(commodities) + len(currencies) + (1 if india_vix else 0)
        + len(india_indices) + len(indian_adrs)
    )
    logger.info("Pre-market dashboard ready — %d/%d symbols fetched", total, 20)
    return dashboard


# ── Text formatter ────────────────────────────────────────────────────────────

def _fmt_row(item: dict, prefix: str = '', currency_symbol: str = '') -> str:
    """Format a single quote row with alignment and emoji indicator."""
    indicator = '🟢' if item['change_pct'] >= 0 else '🔴'
    sign = '+' if item['change_pct'] >= 0 else ''
    price_str = f"{currency_symbol}{item['price']:,.2f}"
    return f"  {prefix}{item['name']:.<20s} {price_str:>12s}  ({sign}{item['change_pct']:.2f}%)  {indicator}"


def format_dashboard_text(data: dict) -> str:
    """Format the full dashboard dict into a readable text block.

    Pure string formatting — no AI involved. Uses emoji indicators
    (🟢 positive, 🔴 negative) for quick scanning.
    """
    lines: list[str] = []
    ts = data.get('timestamp', 'N/A')

    lines.append(f"📊 PRE-MARKET DASHBOARD ({ts})")
    lines.append('━' * 55)

    # US Markets
    if data['us_markets']:
        lines.append('')
        lines.append('🇺🇸 US MARKETS (Previous Close):')
        for item in data['us_markets']:
            lines.append(_fmt_row(item))

    # Asian Markets
    if data['asian_markets']:
        lines.append('')
        lines.append('🌏 ASIAN MARKETS (Live):')
        for item in data['asian_markets']:
            lines.append(_fmt_row(item))

    # European Markets
    if data['european_markets']:
        lines.append('')
        lines.append('🇪🇺 EUROPEAN MARKETS:')
        for item in data['european_markets']:
            lines.append(_fmt_row(item))

    # Commodities
    if data['commodities']:
        lines.append('')
        lines.append('🛢️ COMMODITIES:')
        for item in data['commodities']:
            lines.append(_fmt_row(item, currency_symbol='$'))

    # Currencies
    if data['currencies']:
        lines.append('')
        lines.append('💱 CURRENCIES:')
        for item in data['currencies']:
            indicator = '🟢' if item['change_pct'] >= 0 else '🔴'
            sign = '+' if item['change_pct'] >= 0 else ''
            extra = ''
            if item['symbol'] == 'USDINR=X':
                extra = '  (Rupee weakening)' if item['change_pct'] > 0 else '  (Rupee strengthening)'
            lines.append(
                f"  {item['name']:.<20s} {item['price']:>12,.2f}  ({sign}{item['change_pct']:.2f}%)  {indicator}{extra}"
            )

    # India VIX
    lines.append('')
    vix = data.get('india_vix')
    if vix:
        sign = '+' if vix['change_pct'] >= 0 else ''
        vix_note = '(Low volatility = stable market)' if vix['price'] < 15 else (
            '(Moderate volatility)' if vix['price'] < 20 else '(High volatility = caution)'
        )
        lines.append(f"📈 INDIA VIX: {vix['price']:.2f}  ({sign}{vix['change_pct']:.2f}%)  {vix_note}")
    else:
        lines.append('📈 INDIA VIX: Data unavailable')

    # Indian Indices
    if data['india_indices']:
        lines.append('')
        lines.append('🇮🇳 INDIAN INDICES (Previous Close):')
        for item in data['india_indices']:
            lines.append(_fmt_row(item))

    # Indian ADRs
    if data['indian_adrs']:
        lines.append('')
        lines.append('🇮🇳 INDIAN ADRs (Overnight US):')
        for item in data['indian_adrs']:
            indicator = '🟢' if item['change_pct'] >= 0 else '🔴'
            sign = '+' if item['change_pct'] >= 0 else ''
            lines.append(
                f"  {item['name']} ({item['symbol']}):{'.' * max(1, 16 - len(item['name']))} ${item['price']:>8,.2f}  ({sign}{item['change_pct']:.2f}%)  {indicator}"
            )

    lines.append('')
    lines.append('━' * 55)
    return '\n'.join(lines)
