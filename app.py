"""Upstox Phone Trading Research Dashboard — read-only market data + a
transparent paper-trading signal engine. No order-placement endpoint is
called anywhere in this codebase.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from core import candles, indicators, options, paper_trading, signals
from core.api import UpstoxAPIError, get_daily_candles, get_expiries, get_ltp, get_option_chain, get_intraday_candles, get_token
from core.config import INSTRUMENTS, market_is_open
from ui.charts import render_technical_chart
from ui.components import render_hero
from ui.style import inject as inject_style

st.set_page_config(
    page_title="Indian Trading Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_style()

st.markdown('<div class="section-kicker">UPSTOX • PAPER TRADING • 15-MINUTE PRIMARY</div>', unsafe_allow_html=True)
st.markdown("## 📊 Indian Trading Terminal")
st.caption("Read the market first. Trade only when price, candles, structure and options positioning agree.")

if not get_token():
    st.error("Add `UPSTOX_ANALYTICS_TOKEN` in Streamlit Secrets (or as an environment variable locally) to continue.")
    st.stop()

# ---------------------------------------------------------------- Sidebar --
with st.sidebar:
    st.markdown("### 🎛️ Control Panel")
    st.caption("Use the **sidebar arrow** to collapse/expand this panel.")
    auto = st.checkbox("Auto refresh · 30 sec", value=True)
    name = st.selectbox("Market", list(INSTRUMENTS.keys()))
    key = INSTRUMENTS[name]

    try:
        expiries = get_expiries(key)
    except UpstoxAPIError as exc:
        st.error(f"Could not load expiries: {exc}")
        st.stop()
    if not expiries:
        st.error("No option expiries returned for this instrument.")
        st.stop()
    expiry = st.selectbox("Expiry", expiries)
    n = st.slider("Strikes around ATM", 5, 20, 10)

    st.divider()
    st.markdown("**Chart hierarchy**")
    st.caption("15m = trigger  •  30m / 1H = confirmation  •  Daily = context")
    st.success("No 1m / 3m / 5m signals")
    st.divider()
    st.caption("🟢 Green candle = close above open")
    st.caption("🔴 Red candle = close below open")
    st.caption("⚪ Flat = open and close nearly equal")
    if not market_is_open():
        st.warning("Market is closed — prices are from the last available update.")

if auto and market_is_open():
    st_autorefresh(interval=30_000, key="refresh")
elif auto:
    st.sidebar.caption("Auto-refresh paused while the market is closed.")

# ------------------------------------------------------------- Data fetch --
try:
    spot = get_ltp(key)
    raw_chain = get_option_chain(key, expiry)
except UpstoxAPIError as exc:
    st.error(f"Could not load market data: {exc}")
    st.stop()

df = options.flatten_chain(raw_chain)
if df.empty:
    st.warning("Option chain came back empty — Upstox may be between updates. Try refreshing shortly.")
    st.stop()


def _safe_daily() -> pd.DataFrame:
    try:
        return indicators.add_indicators(candles.candles_to_df(get_daily_candles(key)))
    except UpstoxAPIError:
        return pd.DataFrame()


def _safe_intraday(interval: int) -> pd.DataFrame:
    try:
        return indicators.add_indicators(candles.candles_to_df(get_intraday_candles(key, interval)))
    except UpstoxAPIError:
        return pd.DataFrame()


hist = _safe_daily()
intraday = {"15m": _safe_intraday(15), "30m": _safe_intraday(30), "1H": _safe_intraday(60)}

mtf = candles.summarize(
    [
        candles.snapshot_from_df(intraday["15m"], "15m"),
        candles.snapshot_from_df(intraday["30m"], "30m"),
        candles.snapshot_from_df(intraday["1H"], "1H"),
        candles.snapshot_from_df(hist, "Daily"),
    ]
)

sig = signals.generate_signal(spot, df, hist, intraday_df=intraday["15m"])

# ------------------------------------------------------------- Signal hero --
st.markdown("### 🚦 What should I do right now?")
render_hero(name, spot, sig)

c1, c2, c3, c4 = st.columns(4)
c1.metric("ATM", f"{sig.atm:,.0f}")
c2.metric("PCR", f"{sig.pcr:.2f}" if sig.pcr is not None else "—")
c3.metric("Bull score", sig.bull)
c4.metric("Bear score", sig.bear)

st.markdown(
    '<div class="learning-note"><b>🧠 Why?</b> The signal is only a paper-trading hypothesis. '
    "We want price structure, candle behaviour, OI buildup and key levels to agree before acting.</div>",
    unsafe_allow_html=True,
)

with st.expander("📚 Explain this setup"):
    st.write("**What the engine sees:**")
    for reason in sig.reasons:
        st.write("• " + reason)
    st.write(
        "**Learning rule:** the 15-minute chart is the trigger. Higher timeframes confirm or "
        "weaken the setup; a candle pattern or a single indicator is never enough on its own."
    )

if sig.signal == "SIDEWAYS / RANGE":
    st.info(
        "**Sideways strategy:** use a **defined-risk range setup** for paper trading only. "
        "A practical template is an iron condor: sell an OTM call + OTM put and buy farther OTM "
        "call + put as protection. The system does **not** place these orders automatically."
    )
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Sideways score", f"{sig.sideways_score}/5")
    sc2.metric("EMA gap", f"{sig.ema_gap_pct:.2f}%" if pd.notna(sig.ema_gap_pct) else "—")
    sc3.metric("ATR %", f"{sig.atr_pct:.2f}%" if pd.notna(sig.atr_pct) else "—")
    for item in [
        "Wait for price to remain inside a clearly defined range.",
        "Use defined-risk hedges; avoid naked option selling.",
        "Prefer strikes outside the range and keep max loss known before entry.",
        "Exit if the range breaks with confirmation.",
    ]:
        st.write("• " + item)

# ---------------------------------------------------- Multi-timeframe check --
st.divider()
st.subheader("🕯️ Multi-Timeframe Candle Check")
st.caption("Primary trading timeframe: 15 minutes. Higher timeframes are context. No 1m/3m/5m signals are used.")

if not mtf:
    st.warning("Multi-timeframe candle data is temporarily unavailable.")
else:
    a, b, c = st.columns(3)
    a.metric("15m / 30m / 1H / Daily", mtf.agreement)
    b.metric("Bullish candles", mtf.bullish_count)
    c.metric("Bearish candles", mtf.bearish_count)

    rows = [
        {
            "Timeframe": s.timeframe,
            "Candle": "🟢 Green" if s.colour == "GREEN" else "🔴 Red" if s.colour == "RED" else "⚪ Flat",
            "Pattern": s.pattern,
            "Close": round(s.close, 2),
            "Range %": round(s.range_pct, 2),
            "Body %": round(s.body_pct, 0),
        }
        for s in mtf.snapshots
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if mtf.agreement == "Bullish alignment":
        st.success("🟢 **Multiple timeframes agree with buyers.** The 15-minute chart is still the trigger.")
    elif mtf.agreement == "Bearish alignment":
        st.error("🔴 **Multiple timeframes agree with sellers.** The 15-minute chart is still the trigger.")
    else:
        st.info("🟡 **Timeframes disagree.** Treat this as a transition or wait for confirmation.")

    with st.expander("How to read this"):
        st.write("**Green candle:** close above open. **Red candle:** close below open.")
        st.write(
            "**Pattern:** body/wick geometry plus the previous candle, for Doji, Hammer, "
            "Shooting Star, Marubozu, Engulfing and Inside Bar."
        )
        st.write("**Important:** a candle pattern is never a trade by itself — combine it with the rest of this page.")

# --------------------------------------------------------- Market snapshot --
st.divider()
st.subheader("Market at a glance")
mp = options.max_pain(df)
sr = options.support_resistance(df, top_n=3)

q1, q2, q3, q4, q5 = st.columns(5)
q1.metric("Spot", f"{spot:,.2f}")
q1.caption(name)
q2.metric("Max Pain", f"{mp:,.0f}" if mp else "—")
q3.metric("RSI 14", f"{sig.rsi:.1f}" if pd.notna(sig.rsi) else "—")
trend_text = "Bullish" if sig.trend > 0 else "Bearish" if sig.trend < 0 else "Mixed"
q4.metric("EMA Trend", trend_text)
q5.metric("Expiry", expiry)

resistance_txt = ", ".join(f"{int(s):,} ({int(oi):,} OI)" for s, oi in sr["resistance"]) or "—"
support_txt = ", ".join(f"{int(s):,} ({int(oi):,} OI)" for s, oi in sr["support"]) or "—"
rsi_txt = f"{sig.rsi:.1f}" if pd.notna(sig.rsi) else "—"
max_pain_txt = f"{mp:,.0f}" if mp else "—"
st.markdown(
    f"""
    <div class="level-card">
      <div class="section-kicker">MARKET STATE</div>
      <b>{trend_text}</b> EMA structure &nbsp;•&nbsp; RSI {rsi_txt}
      &nbsp;•&nbsp; Max Pain {max_pain_txt}<br/>
      <span class="section-kicker">RESISTANCE (heaviest CE OI)</span> {resistance_txt}<br/>
      <span class="section-kicker">SUPPORT (heaviest PE OI)</span> {support_txt}
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------- Tabs --
tab_chain, tab_buildup, tab_technical, tab_paper = st.tabs(
    ["📈 Option Chain & OI", "🧱 OI Buildup", "📐 Technical Chart", "🧪 Paper Trading & Journal"]
)

with tab_chain:
    st.caption("OI, change in OI, IV and Greeks. Use this to see where positioning is concentrated.")
    view = options.near_atm_window(df, spot, n)

    l, r = st.columns(2)
    with l:
        st.write("**Strongest Call OI**")
        st.dataframe(
            df.nlargest(8, "CE OI")[["Strike", "CE OI", "CE ΔOI", "CE Buildup", "CE LTP", "CE IV"]],
            use_container_width=True,
            hide_index=True,
        )
    with r:
        st.write("**Strongest Put OI**")
        st.dataframe(
            df.nlargest(8, "PE OI")[["Strike", "PE OI", "PE ΔOI", "PE Buildup", "PE LTP", "PE IV"]],
            use_container_width=True,
            hide_index=True,
        )

    st.write(f"**ATM ± {n} strikes**")
    st.dataframe(
        view[
            [
                "Strike", "CE LTP", "CE OI", "CE ΔOI", "CE IV", "CE Delta",
                "PE LTP", "PE OI", "PE ΔOI", "PE IV", "PE Delta",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download full option chain (CSV)",
        df.to_csv(index=False).encode(),
        f"{name.replace(' ', '_')}_{expiry}_chain.csv",
        "text/csv",
    )

with tab_buildup:
    st.caption(
        "Classic OI-buildup read, applied per option leg using that leg's own price move: "
        "**Long Buildup** = price↑ & OI↑ (fresh buying) · **Short Buildup** = price↓ & OI↑ (fresh writing) · "
        "**Short Covering** = price↑ & OI↓ · **Long Unwinding** = price↓ & OI↓."
    )
    near = options.near_atm_window(df, spot, n)
    buildup = options.oi_buildup_summary(near)

    bc1, bc2 = st.columns(2)
    with bc1:
        st.write(f"**Calls (CE) — ATM ± {n}**")
        st.table(pd.Series(buildup["ce_counts"], name="Count") if buildup["ce_counts"] else pd.Series(dtype=int))
    with bc2:
        st.write(f"**Puts (PE) — ATM ± {n}**")
        st.table(pd.Series(buildup["pe_counts"], name="Count") if buildup["pe_counts"] else pd.Series(dtype=int))

    st.write("**Strike-by-strike buildup**")
    st.dataframe(
        near[["Strike", "CE Buildup", "CE ΔOI", "CE LTP", "PE Buildup", "PE ΔOI", "PE LTP"]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Buildup needs each contract's previous close, which isn't always present in the "
        'quote payload — those rows show "—" rather than a guess.'
    )

with tab_technical:
    frame_choice = st.radio("Timeframe", ["Daily", "1H", "30m", "15m"], horizontal=True)
    frame_map = {"Daily": hist, "1H": intraday["1H"], "30m": intraday["30m"], "15m": intraday["15m"]}
    render_technical_chart(frame_map[frame_choice])
    active = frame_map[frame_choice]
    if not active.empty:
        last = active.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Close", f"{last['close']:,.2f}")
        m2.metric("EMA20", f"{last['EMA20']:,.2f}" if pd.notna(last.get("EMA20")) else "—")
        m3.metric("EMA50", f"{last['EMA50']:,.2f}" if pd.notna(last.get("EMA50")) else "—")
        m4.metric("ATR14", f"{last['ATR14']:,.2f}" if pd.notna(last.get("ATR14")) else "—")

with tab_paper:
    st.caption("Everything below is simulated. No Upstox order is placed.")
    paper_trading.init_state()

    target_type = "CE" if sig.signal == "BUY CALL" else "PE" if sig.signal == "BUY PUT" else "CE"
    view = options.near_atm_window(df, spot, n)
    candidates = []
    for _, row in view.iterrows():
        if target_type == "CE" and row["CE Instrument"] and pd.notna(row["CE LTP"]):
            candidates.append((f"{int(row['Strike'])} CE", row["CE Instrument"], float(row["CE LTP"]), "CE", float(row["Strike"])))
        if target_type == "PE" and row["PE Instrument"] and pd.notna(row["PE LTP"]):
            candidates.append((f"{int(row['Strike'])} PE", row["PE Instrument"], float(row["PE LTP"]), "PE", float(row["Strike"])))
    if not candidates:
        for _, row in view.iterrows():
            for typ, ik, price in [("CE", row["CE Instrument"], row["CE LTP"]), ("PE", row["PE Instrument"], row["PE LTP"])]:
                if ik and pd.notna(price):
                    candidates.append((f"{int(row['Strike'])} {typ}", ik, float(price), typ, float(row["Strike"])))

    if not candidates:
        st.warning("No tradable contracts with live prices in the current ATM window.")
    else:
        labels = [c[0] for c in candidates]
        choice = st.selectbox("Contract", labels)
        chosen = next(c for c in candidates if c[0] == choice)
        side = st.selectbox("Side", ["BUY", "SELL"])
        qty = st.number_input("Quantity", 1, 100_000, 1)
        entry = st.number_input("Entry price", min_value=0.05, value=max(0.05, float(chosen[2])), step=0.05)
        risk_pct = st.number_input("Risk per trade %", 0.25, 5.0, 1.0, 0.25)
        risk_rupees = st.session_state["capital"] * risk_pct / 100
        sl_pct = st.number_input("Stop-loss %", 1.0, 50.0, 20.0, 1.0)
        target_pct = st.number_input("Target %", 1.0, 100.0, 40.0, 1.0)
        sl, target = paper_trading.plan_stop_and_target(side, entry, sl_pct, target_pct)

        a, b, c = st.columns(3)
        a.metric("Max planned loss / trade", f"₹{risk_rupees:,.0f}")
        b.metric("Paper SL", f"₹{sl:,.2f}")
        c.metric("Paper target", f"₹{target:,.2f}")

        note = st.text_input("Trade thesis / reason")
        if st.button("Record PAPER TRADE", type="primary"):
            paper_trading.add_trade(chosen[0], chosen[1], chosen[3], chosen[4], side, qty, entry, sl, target, note)
            st.success("Paper trade recorded. No real order was sent.")

    st.subheader("📒 Paper Journal")
    journal = paper_trading.journal_df()
    if not journal.empty:
        price_map: dict[str, float] = {}
        for _, row in df.iterrows():
            if row["CE Instrument"]:
                price_map[row["CE Instrument"]] = row["CE LTP"]
            if row["PE Instrument"]:
                price_map[row["PE Instrument"]] = row["PE LTP"]
        journal = paper_trading.with_live_pnl(journal, price_map)
        stats = paper_trading.summary(journal)

        a, b, c, d = st.columns(4)
        a.metric("Paper P&L", f"₹{stats['total_pnl']:,.2f}")
        b.metric("Open P&L", f"₹{stats['open_pnl']:,.2f}")
        c.metric("Winning records", stats["wins"])
        d.metric("Losing records", stats["losses"])
        st.dataframe(journal, use_container_width=True, hide_index=True)
        st.download_button(
            "Download journal CSV", journal.to_csv(index=False).encode(), "paper_trading_journal.csv", "text/csv"
        )
    else:
        st.info("No paper trades recorded yet.")

    st.warning(
        "Paper-trading only. The signal engine can be wrong; use it as a checklist, not an automatic "
        "trade recommendation. Live order placement is intentionally disabled."
    )
