"""Thin, cached, retrying client for the read-only Upstox endpoints this dashboard uses.

No order-placement endpoint is called anywhere in this module, by design — this
dashboard is for research and paper trading only.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import (
    API_V2,
    API_V3,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECS,
    TTL_CHAIN,
    TTL_CONTRACTS,
    TTL_HISTORY,
    TTL_LTP,
)


class UpstoxAPIError(RuntimeError):
    """Raised for a missing token, a transport error, an HTTP error, or a
    non-success payload from the Upstox API. Callers should catch this and
    render a friendly message instead of letting the app crash."""


def get_token() -> str:
    try:
        token = st.secrets.get("UPSTOX_ANALYTICS_TOKEN", "")
    except Exception:
        token = ""
    return token or os.getenv("UPSTOX_ANALYTICS_TOKEN", "")


@st.cache_resource(show_spinner=False)
def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _get(base: str, path: str, params: dict | None = None) -> Any:
    token = get_token()
    if not token:
        raise UpstoxAPIError("UPSTOX_ANALYTICS_TOKEN is not configured.")
    try:
        resp = _session().get(
            base + path,
            params=params or {},
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECS,
        )
    except requests.RequestException as exc:
        raise UpstoxAPIError(f"Network error calling {path}: {exc}") from exc

    if resp.status_code >= 400:
        raise UpstoxAPIError(f"HTTP {resp.status_code} on {path}: {resp.text[:400]}")

    try:
        body = resp.json()
    except ValueError as exc:
        raise UpstoxAPIError(f"Non-JSON response from {path}: {resp.text[:200]}") from exc

    if body.get("status") != "success":
        raise UpstoxAPIError(f"Upstox API returned non-success for {path}: {body}")
    return body.get("data")


@st.cache_data(ttl=TTL_LTP, show_spinner=False)
def get_ltp(instrument_key: str) -> float:
    data = _get(API_V2, "/market-quote/ltp", {"instrument_key": instrument_key})
    if not data:
        raise UpstoxAPIError(f"No LTP data returned for {instrument_key}")
    return float(next(iter(data.values()))["last_price"])


@st.cache_data(ttl=TTL_CONTRACTS, show_spinner=False)
def get_expiries(instrument_key: str) -> list[str]:
    data = _get(API_V2, "/option/contract", {"instrument_key": instrument_key})
    return sorted({row["expiry"] for row in (data or []) if row.get("expiry")})


@st.cache_data(ttl=TTL_CHAIN, show_spinner=False)
def get_option_chain(instrument_key: str, expiry: str) -> list[dict]:
    return _get(API_V2, "/option/chain", {"instrument_key": instrument_key, "expiry_date": expiry}) or []


@st.cache_data(ttl=TTL_HISTORY, show_spinner=False)
def get_daily_candles(instrument_key: str, days: int = 120) -> list[list]:
    end = date.today()
    start = end - timedelta(days=days)
    data = _get(API_V3, f"/historical-candle/{instrument_key}/days/1/{end}/{start}")
    return (data or {}).get("candles", [])


@st.cache_data(ttl=TTL_HISTORY, show_spinner=False)
def get_intraday_candles(instrument_key: str, interval_minutes: int, days: int = 31) -> list[list]:
    end = date.today()
    start = end - timedelta(days=days)
    data = _get(
        API_V3,
        f"/historical-candle/{instrument_key}/minutes/{interval_minutes}/{end}/{start}",
    )
    return (data or {}).get("candles", [])
