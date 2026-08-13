"""Option-chain transforms: flattening, OI buildup classification, max pain,
PCR, and support/resistance from OI concentration. Pure pandas/numpy — no
network calls — so it's unit-testable (see tests/test_options.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BUILDUP_LONG = "Long Buildup"
BUILDUP_SHORT = "Short Buildup"
BUILDUP_COVERING = "Short Covering"
BUILDUP_UNWINDING = "Long Unwinding"
BUILDUP_NEUTRAL = "Neutral"
BUILDUP_UNKNOWN = "—"


def _classify_buildup(ltp, prev_close, oi_change: float) -> str:
    """Classic OI-buildup read: price direction + OI direction together.

    Long Buildup    = price up   & OI up    (new longs opening)
    Short Buildup    = price down & OI up    (new shorts opening)
    Short Covering   = price up   & OI down  (shorts exiting)
    Long Unwinding   = price down & OI down  (longs exiting)

    Needs the contract's previous close, which Upstox includes in
    market_data.close on most quote payloads; if it's missing we can't
    classify and say so rather than guessing.
    """
    if ltp is None or prev_close is None or pd.isna(ltp) or pd.isna(prev_close):
        return BUILDUP_UNKNOWN
    price_change = ltp - prev_close
    if price_change > 0 and oi_change > 0:
        return BUILDUP_LONG
    if price_change < 0 and oi_change > 0:
        return BUILDUP_SHORT
    if price_change > 0 and oi_change < 0:
        return BUILDUP_COVERING
    if price_change < 0 and oi_change < 0:
        return BUILDUP_UNWINDING
    return BUILDUP_NEUTRAL


def flatten_chain(raw: list[dict]) -> pd.DataFrame:
    """Turn Upstox's nested /option/chain payload into one row per strike."""
    rows = []
    for entry in raw:
        call = entry.get("call_options") or {}
        put = entry.get("put_options") or {}
        cm = call.get("market_data") or {}
        pm = put.get("market_data") or {}
        cg = call.get("option_greeks") or {}
        pg = put.get("option_greeks") or {}

        ce_oi, pe_oi = cm.get("oi") or 0, pm.get("oi") or 0
        ce_prev_oi, pe_prev_oi = cm.get("prev_oi") or 0, pm.get("prev_oi") or 0
        ce_doi, pe_doi = ce_oi - ce_prev_oi, pe_oi - pe_prev_oi

        rows.append(
            {
                "Strike": entry.get("strike_price"),
                "CE LTP": cm.get("ltp"),
                "CE OI": ce_oi,
                "CE ΔOI": ce_doi,
                "CE Buildup": _classify_buildup(cm.get("ltp"), cm.get("close"), ce_doi),
                "CE IV": cg.get("iv"),
                "CE Delta": cg.get("delta"),
                "CE Gamma": cg.get("gamma"),
                "CE Theta": cg.get("theta"),
                "CE Vega": cg.get("vega"),
                "CE Instrument": call.get("instrument_key"),
                "PE LTP": pm.get("ltp"),
                "PE OI": pe_oi,
                "PE ΔOI": pe_doi,
                "PE Buildup": _classify_buildup(pm.get("ltp"), pm.get("close"), pe_doi),
                "PE IV": pg.get("iv"),
                "PE Delta": pg.get("delta"),
                "PE Gamma": pg.get("gamma"),
                "PE Theta": pg.get("theta"),
                "PE Vega": pg.get("vega"),
                "PE Instrument": put.get("instrument_key"),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)


def atm_index(df: pd.DataFrame, spot: float) -> int:
    """Positional (iloc-based) index of the row whose Strike is closest to
    `spot` — deliberately position-based, not label-based, so it stays valid
    even if `df` has a non-default index (e.g. an already-windowed slice)."""
    return int(np.abs(df["Strike"].to_numpy(dtype=float) - spot).argmin())


def max_pain(df: pd.DataFrame) -> float | None:
    """Vectorized max-pain: the strike at which option writers collectively
    owe the least if expiry settled there right now."""
    clean = df.dropna(subset=["Strike"])
    strikes = clean["Strike"].to_numpy(dtype=float)
    if strikes.size == 0:
        return None
    ce_oi = clean["CE OI"].fillna(0).to_numpy(dtype=float)
    pe_oi = clean["PE OI"].fillna(0).to_numpy(dtype=float)

    diff = strikes[:, None] - strikes[None, :]  # diff[i, j] = strikes[i] - strikes[j]
    call_loss = np.maximum(diff, 0) @ ce_oi  # payout to call holders if settle = strikes[i]
    put_loss = np.maximum(-diff, 0) @ pe_oi  # payout to put holders if settle = strikes[i]

    total_loss = call_loss + put_loss
    return float(strikes[int(np.argmin(total_loss))])


def pcr(df: pd.DataFrame) -> tuple[float | None, float, float]:
    """Returns (put_call_ratio, total_call_oi, total_put_oi)."""
    ce_total = float(df["CE OI"].fillna(0).sum())
    pe_total = float(df["PE OI"].fillna(0).sum())
    ratio = pe_total / ce_total if ce_total else None
    return ratio, ce_total, pe_total


def support_resistance(df: pd.DataFrame, top_n: int = 3) -> dict:
    """Strikes with the heaviest call OI act as resistance (writers expect
    price to stay below); heaviest put OI acts as support."""
    resistance = df.nlargest(top_n, "CE OI")[["Strike", "CE OI"]].values.tolist()
    support = df.nlargest(top_n, "PE OI")[["Strike", "PE OI"]].values.tolist()
    return {"resistance": resistance, "support": support}


def near_atm_window(df: pd.DataFrame, spot: float, width: int = 8) -> pd.DataFrame:
    idx = atm_index(df, spot)
    lo, hi = max(0, idx - width), min(len(df), idx + width + 1)
    return df.iloc[lo:hi]


def oi_buildup_summary(window_df: pd.DataFrame) -> dict:
    """Count buildup classifications within a near-ATM window, for both legs."""
    return {
        "ce_counts": window_df["CE Buildup"].value_counts().to_dict(),
        "pe_counts": window_df["PE Buildup"].value_counts().to_dict(),
    }
