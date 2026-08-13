"""Pure, side-effect-free technical indicator functions.

Every function here takes/returns pandas objects and touches no network or
Streamlit state, which keeps them cheap to unit test (see tests/test_indicators.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_OHLC = ("open", "high", "low", "close")


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI (the standard definition — most charting platforms use this,
    not a plain rolling average of gains/losses)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR. Expects high/low/close columns."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift()
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def bollinger(
    series: pd.Series, period: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    return pd.DataFrame(
        {"mid": mid, "upper": mid + num_std * std, "lower": mid - num_std * std}
    )


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP: resets at the start of each calendar day in `time`.
    Requires high/low/close/volume/time columns; returns NaN where volume is
    all-zero (e.g. an index has no traded volume)."""
    if "volume" not in df or df["volume"].sum() == 0:
        return pd.Series(np.nan, index=df.index)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    session = df["time"].dt.date
    tp_vol = (typical * df["volume"]).groupby(session).cumsum()
    cum_vol = df["volume"].groupby(session).cumsum()
    return tp_vol / cum_vol.replace(0, np.nan)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `df` (columns: time, open, high, low, close, volume, oi)
    with EMA20/50/200, RSI14, MACD, ATR14, Bollinger(20,2) and VWAP attached.
    Short series simply get NaN tails for the longer-period indicators."""
    if df.empty or not all(c in df.columns for c in REQUIRED_OHLC):
        return df

    out = df.copy()
    close = out["close"]
    out["EMA20"] = ema(close, 20)
    out["EMA50"] = ema(close, 50)
    out["EMA200"] = ema(close, 200)
    out["RSI14"] = rsi(close, 14)
    out["ATR14"] = atr(out, 14)

    macd_df = macd(close)
    out["MACD"] = macd_df["macd"]
    out["MACD_SIGNAL"] = macd_df["signal"]
    out["MACD_HIST"] = macd_df["hist"]

    bb = bollinger(close, 20, 2.0)
    out["BB_MID"] = bb["mid"]
    out["BB_UPPER"] = bb["upper"]
    out["BB_LOWER"] = bb["lower"]

    if "volume" in out.columns and "time" in out.columns:
        out["VWAP"] = vwap(out)

    return out
