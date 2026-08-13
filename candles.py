"""Candle-pattern classification and multi-timeframe agreement scoring.

Pure functions/dataclasses only — no network or Streamlit calls — so this
module is fully unit-testable (see tests/test_candles.py). Callers convert raw
Upstox candle rows to a DataFrame with `candles_to_df`, then build snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

CANDLE_COLUMNS = ["time", "open", "high", "low", "close", "volume", "oi"]


def candles_to_df(raw_candles: list[list]) -> pd.DataFrame:
    """Convert raw Upstox candle rows [time, o, h, l, c, volume, oi] into a
    time-sorted DataFrame. Returns an empty (but correctly-columned) frame for
    empty input so downstream `.empty` checks work without special-casing."""
    if not raw_candles:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    df = pd.DataFrame(raw_candles, columns=CANDLE_COLUMNS)
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def classify_candle(
    o: float,
    h: float,
    l: float,
    c: float,
    prev: tuple[float, float, float, float] | None = None,
) -> tuple[str, str]:
    """Classify one OHLC candle (optionally against the previous candle's OHLC
    for two-bar patterns). Returns (pattern_name, direction) where direction
    is one of "bullish" / "bearish" / "neutral"."""
    body = abs(c - o)
    rng = max(h - l, 1e-9)
    upper = h - max(o, c)
    lower = min(o, c) - l
    close_pos = (c - l) / rng

    if prev is not None:
        po, ph, pl, pc = prev
        if pc < po and c > o and o <= pc and c >= po:
            return "Bullish Engulfing", "bullish"
        if pc > po and c < o and o >= pc and c <= po:
            return "Bearish Engulfing", "bearish"
        if h <= ph and l >= pl:
            return "Inside Bar", "neutral"

    if body / rng <= 0.12:
        return "Doji", "neutral"
    if body / rng >= 0.80 and c > o:
        return "Bullish Marubozu", "bullish"
    if body / rng >= 0.80 and c < o:
        return "Bearish Marubozu", "bearish"
    if lower >= body * 2 and upper <= max(body * 0.8, 1e-9) and close_pos >= 0.65:
        return "Hammer", "bullish"
    if upper >= body * 2 and lower <= max(body * 0.8, 1e-9) and close_pos <= 0.35:
        return "Shooting Star", "bearish"
    if c > o and close_pos >= 0.65:
        return "Bullish Candle", "bullish"
    if c < o and close_pos <= 0.35:
        return "Bearish Candle", "bearish"
    return "Neutral Candle", "neutral"


@dataclass
class TimeframeSnapshot:
    timeframe: str
    time: object
    open: float
    high: float
    low: float
    close: float
    colour: str
    pattern: str
    direction: str
    body_pct: float
    range_pct: float


def snapshot_from_df(df: pd.DataFrame, label: str) -> TimeframeSnapshot | None:
    """Build a TimeframeSnapshot from the latest candle in `df`, or None if
    `df` has no rows yet (e.g. a data-fetch hiccup)."""
    if df.empty:
        return None
    last = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) >= 2 else None
    prev = (
        (
            float(prev_row["open"]),
            float(prev_row["high"]),
            float(prev_row["low"]),
            float(prev_row["close"]),
        )
        if prev_row is not None
        else None
    )
    o, h, l, c = (
        float(last["open"]),
        float(last["high"]),
        float(last["low"]),
        float(last["close"]),
    )
    pattern, direction = classify_candle(o, h, l, c, prev)
    return TimeframeSnapshot(
        timeframe=label,
        time=last["time"],
        open=o,
        high=h,
        low=l,
        close=c,
        colour="GREEN" if c > o else "RED" if c < o else "FLAT",
        pattern=pattern,
        direction=direction,
        body_pct=abs(c - o) / max(h - l, 1e-9) * 100,
        range_pct=(h - l) / max(o, 1e-9) * 100,
    )


@dataclass
class MultiTimeframeView:
    snapshots: list[TimeframeSnapshot]
    bullish_count: int
    bearish_count: int
    agreement: str


def summarize(snapshots: list[TimeframeSnapshot | None]) -> MultiTimeframeView | None:
    """Roll up a list of per-timeframe snapshots into an overall agreement
    verdict. Needs at least 3 of the timeframes leaning the same way to call
    it an alignment rather than "Mixed / transitional"."""
    clean = [s for s in snapshots if s is not None]
    if not clean:
        return None
    bull = sum(1 for s in clean if s.direction == "bullish")
    bear = sum(1 for s in clean if s.direction == "bearish")
    if bull >= 3 and bull > bear:
        agreement = "Bullish alignment"
    elif bear >= 3 and bear > bull:
        agreement = "Bearish alignment"
    else:
        agreement = "Mixed / transitional"
    return MultiTimeframeView(
        snapshots=clean, bullish_count=bull, bearish_count=bear, agreement=agreement
    )
