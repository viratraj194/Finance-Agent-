"""
Options Market Intelligence Provider
Fetches pre-market options data: Put-Call Ratio, pivot levels, and key support/resistance.

Data sources (in fallback order):
1. nselib derivatives module (nse_live_option_chain)
2. NSE session-based API (option-chain-indices endpoint)
3. Graceful degradation with partial data

Pivot levels use yfinance for previous-day OHLC (Nifty ^NSEI, BankNifty ^NSEBANK).
"""

import logging
import concurrent.futures
from datetime import datetime, timedelta

import requests
import yfinance as yf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  NSE session helpers (mirrors nse_data.py approach)
# ---------------------------------------------------------------------------

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

NSE_BASE = "https://www.nseindia.com"


def _get_nse_session() -> requests.Session:
    """Creates a session pre-loaded with NSE cookies (2-step handshake)."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get(f"{NSE_BASE}/", timeout=12)
        session.get(
            f"{NSE_BASE}/option-chain",
            timeout=12,
        )
    except Exception as exc:
        logger.debug(f"NSE session init warning: {exc}")
    return session


# ---------------------------------------------------------------------------
#  1.  Put-Call Ratio
# ---------------------------------------------------------------------------

def _pcr_interpretation(pcr: float) -> str:
    """Human-readable interpretation of a Nifty PCR value."""
    if pcr > 1.3:
        return "Very Bullish (heavy put writing = strong support)"
    if pcr >= 1.0:
        return "Mildly Bullish (PCR > 1.0)"
    if pcr >= 0.7:
        return "Neutral to Mildly Bearish"
    return "Very Bearish (heavy call writing = resistance)"


def _pcr_from_nselib() -> dict | None:
    """Attempt 1: use nselib.derivatives.nse_live_option_chain to compute PCR."""
    try:
        import pandas as pd
        from nselib import derivatives

        df = derivatives.nse_live_option_chain("NIFTY", oi_mode="compact")
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None

        # Column names vary across nselib versions; try common variants
        ce_oi_col = None
        pe_oi_col = None
        for col in df.columns:
            lower = str(col).lower()
            if "ce" in lower and "oi" in lower:
                ce_oi_col = col
            if "pe" in lower and "oi" in lower:
                pe_oi_col = col

        if ce_oi_col and pe_oi_col:
            total_ce_oi = pd.to_numeric(df[ce_oi_col], errors="coerce").sum()
            total_pe_oi = pd.to_numeric(df[pe_oi_col], errors="coerce").sum()
            if total_ce_oi > 0:
                pcr = round(total_pe_oi / total_ce_oi, 4)
                return {
                    "nifty_pcr": pcr,
                    "interpretation": _pcr_interpretation(pcr),
                    "source": "nselib option chain",
                }
    except Exception as exc:
        logger.debug(f"nselib option chain PCR failed: {exc}")
    return None


def _pcr_from_nse_api() -> dict | None:
    """Attempt 2: NSE session-based API for option chain aggregated OI."""
    try:
        session = _get_nse_session()
        url = f"{NSE_BASE}/api/option-chain-indices?symbol=NIFTY"
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            logger.debug(f"NSE option chain API returned {resp.status_code}")
            return None

        data = resp.json()

        # The 'filtered' key contains aggregated CE/PE totals
        filtered = data.get("filtered", {})
        ce_data = filtered.get("CE", {})
        pe_data = filtered.get("PE", {})

        total_ce_oi = ce_data.get("totOI", 0)
        total_pe_oi = pe_data.get("totOI", 0)

        if total_ce_oi > 0:
            pcr = round(total_pe_oi / total_ce_oi, 4)
            return {
                "nifty_pcr": pcr,
                "interpretation": _pcr_interpretation(pcr),
                "source": "NSE option chain API",
            }
    except Exception as exc:
        logger.debug(f"NSE session option chain PCR failed: {exc}")
    return None


def _pcr_from_nselib_urlfetch() -> dict | None:
    """Attempt 3: use nselib's internal nse_urlfetch for the same NSE endpoint."""
    try:
        from nselib.libutil import nse_urlfetch

        resp = nse_urlfetch(
            "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
            origin_url="https://www.nseindia.com/option-chain",
        )
        if resp.status_code != 200 or not resp.text.strip():
            return None

        data = resp.json()
        filtered = data.get("filtered", {})
        ce_data = filtered.get("CE", {})
        pe_data = filtered.get("PE", {})

        total_ce_oi = ce_data.get("totOI", 0)
        total_pe_oi = pe_data.get("totOI", 0)

        if total_ce_oi > 0:
            pcr = round(total_pe_oi / total_ce_oi, 4)
            return {
                "nifty_pcr": pcr,
                "interpretation": _pcr_interpretation(pcr),
                "source": "NSE (nselib urlfetch)",
            }
    except Exception as exc:
        logger.debug(f"nselib urlfetch option chain PCR failed: {exc}")
    return None


def get_pcr_data() -> dict:
    """
    Fetch Nifty Put-Call Ratio using a waterfall of data sources.

    Returns dict with keys: nifty_pcr, interpretation, source.
    On total failure returns an error dict.
    """
    for fn in (_pcr_from_nselib, _pcr_from_nse_api, _pcr_from_nselib_urlfetch):
        result = fn()
        if result is not None:
            return result

    logger.warning("All PCR data sources failed")
    return {
        "nifty_pcr": None,
        "interpretation": "Data unavailable",
        "source": "none",
        "error": "All PCR data sources failed. NSE bot protection may be active.",
    }


# ---------------------------------------------------------------------------
#  2.  Pivot Levels (Classic)
# ---------------------------------------------------------------------------

_SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}


def _calc_pivots(high: float, low: float, close: float) -> dict:
    """Classic pivot point calculation from a single day's HLC."""
    pivot = (high + low + close) / 3.0
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)

    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "r3": round(r3, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "s3": round(s3, 2),
    }


def _pivots_for_symbol(name: str, yf_symbol: str) -> dict | None:
    """Fetch previous day OHLC from yfinance and compute pivot levels."""
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="5d")
        if hist is None or hist.empty or len(hist) < 2:
            logger.warning(f"Insufficient history data for {yf_symbol}")
            return None

        # Previous trading day is the second-to-last row
        prev = hist.iloc[-2]
        prev_high = float(prev["High"])
        prev_low = float(prev["Low"])
        prev_close = float(prev["Close"])
        prev_open = float(prev["Open"])

        pivots = _calc_pivots(prev_high, prev_low, prev_close)
        pivots.update({
            "prev_close": round(prev_close, 2),
            "prev_high": round(prev_high, 2),
            "prev_low": round(prev_low, 2),
            "prev_open": round(prev_open, 2),
        })
        return pivots

    except Exception as exc:
        logger.error(f"Pivot calculation failed for {name} ({yf_symbol}): {exc}")
        return None


def get_pivot_levels(symbol: str = "NIFTY") -> dict:
    """
    Calculate classic pivot points for Nifty and BankNifty from previous day OHLC.

    Uses yfinance (^NSEI, ^NSEBANK). Fetches both indices in parallel.

    Returns:
        {
            'nifty': {pivot, r1, r2, r3, s1, s2, s3, prev_close, prev_high, prev_low, prev_open},
            'banknifty': { ... }
        }
    """
    targets = {
        "nifty": ("NIFTY", "^NSEI"),
        "banknifty": ("BANKNIFTY", "^NSEBANK"),
    }

    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_pivots_for_symbol, name, yf_sym): key
            for key, (name, yf_sym) in targets.items()
        }
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                data = future.result()
                if data is not None:
                    result[key] = data
                else:
                    result[key] = {"error": "No data available"}
            except Exception as exc:
                logger.error(f"Pivot future failed for {key}: {exc}")
                result[key] = {"error": str(exc)}

    return result


# ---------------------------------------------------------------------------
#  3.  Options Snapshot (combines PCR + Pivots)
# ---------------------------------------------------------------------------

def get_options_snapshot() -> dict:
    """
    Combined options market intelligence snapshot.
    Fetches PCR and pivot levels in parallel.

    Returns:
        {'pcr': {...}, 'levels': {...}}
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        pcr_future = executor.submit(get_pcr_data)
        levels_future = executor.submit(get_pivot_levels)

        try:
            pcr = pcr_future.result()
        except Exception as exc:
            logger.error(f"PCR fetch failed: {exc}")
            pcr = {"error": str(exc)}

        try:
            levels = levels_future.result()
        except Exception as exc:
            logger.error(f"Pivot levels fetch failed: {exc}")
            levels = {"error": str(exc)}

    return {
        "pcr": pcr,
        "levels": levels,
    }


# ---------------------------------------------------------------------------
#  4.  Text Formatter
# ---------------------------------------------------------------------------

def _fmt_number(n) -> str:
    """Format a number with commas (e.g. 24750 → '24,750'). Returns '—' on failure."""
    try:
        if n is None:
            return "—"
        return f"{float(n):,.0f}"
    except (ValueError, TypeError):
        return "—"


def format_options_text(data: dict) -> str:
    """
    Format the options snapshot dict into a clean, human-readable text block
    suitable for the daily pre-market report.  No AI required.
    """
    lines = [
        "📐 KEY LEVELS & OPTIONS DATA",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    levels = data.get("levels", {})

    # --- Nifty levels ---
    nifty = levels.get("nifty", {})
    if nifty and "error" not in nifty:
        prev_close = _fmt_number(nifty.get("prev_close"))
        lines.append(f"NIFTY 50 Levels (Prev Close: {prev_close}):")
        lines.append(
            f"  Resistance: R1 {_fmt_number(nifty.get('r1'))} "
            f"| R2 {_fmt_number(nifty.get('r2'))} "
            f"| R3 {_fmt_number(nifty.get('r3'))}"
        )
        lines.append(f"  Pivot:      {_fmt_number(nifty.get('pivot'))}")
        lines.append(
            f"  Support:    S1 {_fmt_number(nifty.get('s1'))} "
            f"| S2 {_fmt_number(nifty.get('s2'))} "
            f"| S3 {_fmt_number(nifty.get('s3'))}"
        )
    else:
        lines.append("NIFTY 50 Levels: Data unavailable")

    lines.append("")

    # --- BankNifty levels ---
    bnifty = levels.get("banknifty", {})
    if bnifty and "error" not in bnifty:
        prev_close = _fmt_number(bnifty.get("prev_close"))
        lines.append(f"BANK NIFTY Levels (Prev Close: {prev_close}):")
        lines.append(
            f"  Resistance: R1 {_fmt_number(bnifty.get('r1'))} "
            f"| R2 {_fmt_number(bnifty.get('r2'))} "
            f"| R3 {_fmt_number(bnifty.get('r3'))}"
        )
        lines.append(f"  Pivot:      {_fmt_number(bnifty.get('pivot'))}")
        lines.append(
            f"  Support:    S1 {_fmt_number(bnifty.get('s1'))} "
            f"| S2 {_fmt_number(bnifty.get('s2'))} "
            f"| S3 {_fmt_number(bnifty.get('s3'))}"
        )
    else:
        lines.append("BANK NIFTY Levels: Data unavailable")

    lines.append("")

    # --- PCR ---
    pcr = data.get("pcr", {})
    pcr_val = pcr.get("nifty_pcr")
    interpretation = pcr.get("interpretation", "Data unavailable")
    if pcr_val is not None:
        lines.append(f"Nifty PCR: {pcr_val} → {interpretation}")
    else:
        lines.append(f"Nifty PCR: {interpretation}")

    return "\n".join(lines)
