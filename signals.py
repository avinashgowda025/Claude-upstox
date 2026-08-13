"""A transparent, explainable heuristic signal engine — PAPER TRADING ONLY.

This is not a black box: every vote it casts is listed in `reasons` so the UI
can show its work. It combines price structure (EMA/RSI/MACD), option
positioning (PCR, near-ATM OI buildup), and optionally intraday VWAP into a
bounded bull/bear score, then maps that to one of four calls: BUY CALL,
BUY PUT, SIDEWAYS / RANGE, or NO TRADE.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.options import (
    BUILDUP_LONG,
    BUILDUP_SHORT,
    atm_index,
    near_atm_window,
    oi_buildup_summary,
    pcr as compute_pcr,
)


@dataclass
class Signal:
    signal: str
    confidence: int
    strategy: str
    reasons: list[str]
    atm: float
    pcr: float | None
    bull: int
    bear: int
    sideways_score: int
    rsi: float
    trend: int
    atr_pct: float
    ema_gap_pct: float
    ce_doi: float = 0.0
    pe_doi: float = 0.0
    extras: dict = field(default_factory=dict)


def _trend_score(last: pd.Series) -> int:
    close, e20, e50 = last.get("close"), last.get("EMA20"), last.get("EMA50")
    if pd.isna(close) or pd.isna(e20) or pd.isna(e50):
        return 0
    if close > e20 > e50:
        return 2
    if close > e20:
        return 1
    if close < e20 < e50:
        return -2
    if close < e20:
        return -1
    return 0


def generate_signal(
    spot: float,
    chain_df: pd.DataFrame,
    hist_df: pd.DataFrame,
    intraday_df: pd.DataFrame | None = None,
    window: int = 8,
) -> Signal:
    idx = atm_index(chain_df, spot)
    atm = float(chain_df.iloc[idx]["Strike"])
    near = near_atm_window(chain_df, spot, window)
    ce_doi, pe_doi = float(near["CE ΔOI"].sum()), float(near["PE ΔOI"].sum())
    ratio, _, _ = compute_pcr(chain_df)

    trend = rsi_val = atr_pct = ema_gap_pct = np.nan
    macd_hist_last = macd_hist_prev = np.nan
    if not hist_df.empty:
        last = hist_df.iloc[-1]
        trend = _trend_score(last)
        rsi_val = last.get("RSI14", np.nan)
        atr_pct = (
            (last["ATR14"] / last["close"] * 100)
            if pd.notna(last.get("ATR14")) and last.get("close")
            else np.nan
        )
        ema_gap_pct = (
            abs(last["EMA20"] - last["EMA50"]) / last["close"] * 100
            if pd.notna(last.get("EMA20")) and pd.notna(last.get("EMA50")) and last.get("close")
            else np.nan
        )
        if "MACD_HIST" in hist_df.columns and len(hist_df) >= 2:
            macd_hist_last = last.get("MACD_HIST", np.nan)
            macd_hist_prev = hist_df.iloc[-2].get("MACD_HIST", np.nan)
    trend = 0 if pd.isna(trend) else int(trend)

    bull = bear = 0
    reasons_bull: list[str] = []
    reasons_bear: list[str] = []
    reasons_side: list[str] = []

    # --- Price structure ---
    if trend > 0:
        bull += 2 if trend == 2 else 1
        reasons_bull.append("price/EMA structure is bullish")
    elif trend < 0:
        bear += 2 if trend == -2 else 1
        reasons_bear.append("price/EMA structure is bearish")

    if pd.notna(rsi_val):
        if 52 <= rsi_val <= 70:
            bull += 1
            reasons_bull.append("RSI supports upside")
        elif 30 <= rsi_val <= 48:
            bear += 1
            reasons_bear.append("RSI supports downside")
        else:
            reasons_side.append("RSI is near the midpoint")

    if pd.notna(macd_hist_last) and pd.notna(macd_hist_prev):
        if macd_hist_last > 0 and macd_hist_last > macd_hist_prev:
            bull += 1
            reasons_bull.append("MACD histogram is positive and rising")
        elif macd_hist_last < 0 and macd_hist_last < macd_hist_prev:
            bear += 1
            reasons_bear.append("MACD histogram is negative and falling")
        else:
            reasons_side.append("MACD momentum lacks a clear edge")

    # --- Options positioning ---
    if ratio is not None:
        if ratio >= 1.10:
            bull += 1
            reasons_bull.append("PCR is above 1.10")
        elif ratio <= 0.90:
            bear += 1
            reasons_bear.append("PCR is below 0.90")
        else:
            reasons_side.append("PCR is in a balanced range")

    if pe_doi > ce_doi * 1.15:
        bull += 1
        reasons_bull.append("near-ATM put OI buildup is stronger")
    elif ce_doi > pe_doi * 1.15:
        bear += 1
        reasons_bear.append("near-ATM call OI buildup is stronger")
    else:
        reasons_side.append("near-ATM OI buildup (raw ΔOI) is balanced")

    buildup = oi_buildup_summary(near)
    ce_counts, pe_counts = buildup["ce_counts"], buildup["pe_counts"]
    bullish_votes = ce_counts.get(BUILDUP_LONG, 0) + pe_counts.get(BUILDUP_SHORT, 0)
    bearish_votes = pe_counts.get(BUILDUP_LONG, 0) + ce_counts.get(BUILDUP_SHORT, 0)
    net_buildup = bullish_votes - bearish_votes
    if net_buildup >= 2:
        bull += 1
        reasons_bull.append("fresh call buying / put writing dominates near ATM")
    elif net_buildup <= -2:
        bear += 1
        reasons_bear.append("fresh put buying / call writing dominates near ATM")
    else:
        reasons_side.append("CE/PE OI-buildup classification is mixed near ATM")

    # --- Intraday VWAP (optional, only when an intraday frame is supplied) ---
    if intraday_df is not None and not intraday_df.empty and "VWAP" in intraday_df.columns:
        vwap_series = intraday_df["VWAP"].dropna()
        if not vwap_series.empty:
            last_vwap = float(vwap_series.iloc[-1])
            if spot > last_vwap * 1.0005:
                bull += 1
                reasons_bull.append("price is trading above session VWAP")
            elif spot < last_vwap * 0.9995:
                bear += 1
                reasons_bear.append("price is trading below session VWAP")
            else:
                reasons_side.append("price is hugging session VWAP")

    # --- Sideways / range regime ---
    sideways_score = 0
    if pd.notna(ema_gap_pct) and ema_gap_pct < 0.35:
        sideways_score += 1
        reasons_side.append("EMA20/EMA50 are tightly grouped")
    if pd.notna(rsi_val) and 42 <= rsi_val <= 58:
        sideways_score += 1
    if ratio is not None and 0.90 <= ratio <= 1.10:
        sideways_score += 1
    if abs(pe_doi - ce_doi) <= max(abs(pe_doi), abs(ce_doi), 1) * 0.20:
        sideways_score += 1
    if trend == 0:
        sideways_score += 1

    if sideways_score >= 3 and abs(bull - bear) <= 2:
        signal, strategy = "SIDEWAYS / RANGE", "Defined-risk range setup (paper only)"
        confidence = min(85, 55 + sideways_score * 7)
        reasons = reasons_side or ["directional evidence is weak"]
    elif bull >= 5 and bull - bear >= 3:
        signal, strategy = "BUY CALL", "Directional bullish paper setup"
        confidence = min(92, 55 + 6 * (bull - bear))
        reasons = reasons_bull
    elif bear >= 5 and bear - bull >= 3:
        signal, strategy = "BUY PUT", "Directional bearish paper setup"
        confidence = min(92, 55 + 6 * (bear - bull))
        reasons = reasons_bear
    else:
        signal, strategy = "NO TRADE", "Wait"
        confidence = 50
        reasons = ["conditions are mixed; wait for confirmation"]

    return Signal(
        signal=signal,
        confidence=confidence,
        strategy=strategy,
        reasons=reasons,
        atm=atm,
        pcr=ratio,
        bull=bull,
        bear=bear,
        sideways_score=sideways_score,
        rsi=rsi_val,
        trend=trend,
        atr_pct=atr_pct,
        ema_gap_pct=ema_gap_pct,
        ce_doi=ce_doi,
        pe_doi=pe_doi,
        extras={"buildup": buildup},
    )
