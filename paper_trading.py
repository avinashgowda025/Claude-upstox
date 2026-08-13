"""Paper-trading journal. Every trade recorded here is simulated — this
module never calls an order-placement endpoint and never will.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

SESSION_KEY = "paper_trades"
DEFAULT_CAPITAL = 100_000.0


def init_state() -> None:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []
    if "capital" not in st.session_state:
        st.session_state["capital"] = DEFAULT_CAPITAL


def add_trade(
    contract: str,
    instrument: str,
    opt_type: str,
    strike: float,
    side: str,
    qty: int,
    entry: float,
    sl: float,
    target: float,
    note: str,
) -> None:
    init_state()
    st.session_state[SESSION_KEY].append(
        {
            "Time": pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d %H:%M:%S"),
            "Contract": contract,
            "Instrument": instrument,
            "Type": opt_type,
            "Strike": strike,
            "Side": side,
            "Qty": int(qty),
            "Entry": float(entry),
            "SL": float(sl),
            "Target": float(target),
            "Status": "OPEN",
            "Note": note,
        }
    )


def journal_df() -> pd.DataFrame:
    init_state()
    return pd.DataFrame(st.session_state[SESSION_KEY])


def with_live_pnl(df: pd.DataFrame, price_map: dict[str, float]) -> pd.DataFrame:
    """Attach Current price + mark-to-market P&L using `price_map`
    (instrument_key -> latest LTP). A contract missing from `price_map` falls
    back to its entry price, so P&L reads as 0 rather than crashing."""
    if df.empty:
        return df
    out = df.copy()
    out["Current"] = out["Instrument"].map(price_map).fillna(out["Entry"])
    out["P&L"] = np.where(
        out["Side"] == "BUY",
        out["Qty"] * (out["Current"] - out["Entry"]),
        out["Qty"] * (out["Entry"] - out["Current"]),
    )
    return out


def summary(df: pd.DataFrame) -> dict:
    if df.empty or "P&L" not in df.columns:
        return {"total_pnl": 0.0, "open_pnl": 0.0, "wins": 0, "losses": 0}
    return {
        "total_pnl": float(df["P&L"].sum()),
        "open_pnl": float(df.loc[df["Status"] == "OPEN", "P&L"].sum()),
        "wins": int((df["P&L"] > 0).sum()),
        "losses": int((df["P&L"] < 0).sum()),
    }


def plan_stop_and_target(
    side: str, entry: float, sl_pct: float, target_pct: float
) -> tuple[float, float]:
    if side == "BUY":
        sl = max(0.05, entry * (1 - sl_pct / 100))
        target = entry * (1 + target_pct / 100)
    else:
        sl = entry * (1 + sl_pct / 100)
        target = max(0.05, entry * (1 - target_pct / 100))
    return sl, target
