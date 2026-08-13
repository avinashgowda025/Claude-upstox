"""Small reusable rendering helpers shared across the dashboard's sections."""
from __future__ import annotations

import streamlit as st

from core.config import market_is_open
from core.signals import Signal

_SIGNAL_PILLS = {
    "BUY CALL": ("🟢 BUY CALL", "signal-green"),
    "BUY PUT": ("🔴 BUY PUT", "signal-red"),
    "SIDEWAYS / RANGE": ("🔵 SIDEWAYS / RANGE", "signal-blue"),
    "NO TRADE": ("🟡 NO TRADE", "signal-yellow"),
}


def signal_pill(signal: str) -> tuple[str, str]:
    return _SIGNAL_PILLS.get(signal, ("🟡 NO TRADE", "signal-yellow"))


def market_status_badge() -> str:
    is_open = market_is_open()
    label = "MARKET OPEN" if is_open else "MARKET CLOSED"
    css_class = "status-open" if is_open else "status-closed"
    return f'<span class="status-badge {css_class}">{label}</span>'


def render_hero(name: str, spot: float, sig: Signal) -> None:
    pill_label, pill_cls = signal_pill(sig.signal)
    st.markdown(
        f"""
        <div class="hero-card">
          <div class="signal-pill {pill_cls}">{pill_label}</div>
          <div class="hero-title">{name} <span style="opacity:.55">&middot;</span> {spot:,.2f}
            {market_status_badge()}
          </div>
          <div class="hero-sub">Confidence {sig.confidence}% &nbsp;&bull;&nbsp; {sig.strategy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
