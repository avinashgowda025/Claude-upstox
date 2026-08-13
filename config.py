"""Static configuration: API endpoints, tradable instruments, market-hours helper.

Nothing in this module makes network calls or touches Streamlit secrets.
"""
from __future__ import annotations

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

# Windows has no built-in IANA tz database, so ZoneInfo needs the `tzdata`
# package (see requirements.txt) to resolve this on anything but Linux/macOS.
IST = ZoneInfo("Asia/Kolkata")

API_V2 = "https://api.upstox.com/v2"
API_V3 = "https://api.upstox.com/v3"

# Extend this dict to add more indices/underlyings. Keys are what the UI shows,
# values are the Upstox instrument_key for the underlying index.
INSTRUMENTS: dict[str, str] = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "BANK NIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
}

MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)

REQUEST_TIMEOUT_SECS = 20
MAX_RETRIES = 3

# Cache TTLs (seconds) — tuned so the dashboard stays fresh without hammering
# Upstox rate limits when auto-refresh is on.
TTL_LTP = 5
TTL_CHAIN = 15
TTL_CONTRACTS = 3600
TTL_HISTORY = 300


def now_ist() -> datetime:
    return datetime.now(IST)


def market_is_open(at: datetime | None = None) -> bool:
    """Best-effort NSE cash/derivatives market-hours check (Mon-Fri, 09:15-15:30 IST).

    Does not account for exchange holidays — treat as a UI hint, not ground truth.
    """
    moment = at or now_ist()
    if moment.weekday() >= 5:  # Sat=5, Sun=6
        return False
    return MARKET_OPEN <= moment.time() <= MARKET_CLOSE
