"""Plotly technical chart: candlesticks + EMA/Bollinger/VWAP overlay, RSI and
MACD subplots. Kept out of app.py purely to keep that file readable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def render_technical_chart(df: pd.DataFrame, height: int = 640) -> None:
    if df.empty:
        st.info("No historical data available for this timeframe yet.")
        return

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.2, 0.25],
        vertical_spacing=0.04,
        subplot_titles=("Price", "RSI (14)", "MACD (12, 26, 9)"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
        ),
        row=1,
        col=1,
    )
    for col, color in (("EMA20", "#60a5fa"), ("EMA50", "#f59e0b")):
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df["time"], y=df[col], name=col, line=dict(width=1.3, color=color)),
                row=1,
                col=1,
            )
    if "BB_UPPER" in df.columns and "BB_LOWER" in df.columns:
        band_color = "rgba(148,163,184,.55)"
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["BB_UPPER"], name="BB Upper", line=dict(width=1, color=band_color), showlegend=False),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["BB_LOWER"],
                name="BB Lower",
                line=dict(width=1, color=band_color),
                fill="tonexty",
                fillcolor="rgba(148,163,184,.07)",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
    if "VWAP" in df.columns and df["VWAP"].notna().any():
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["VWAP"], name="VWAP", line=dict(width=1.4, color="#a855f7", dash="dot")),
            row=1,
            col=1,
        )

    if "RSI14" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["RSI14"], name="RSI14", line=dict(width=1.4, color="#38bdf8")),
            row=2,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dot", line_color="rgba(239,68,68,.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="rgba(34,197,94,.5)", row=2, col=1)

    if {"MACD", "MACD_SIGNAL", "MACD_HIST"}.issubset(df.columns):
        hist_colors = np.where(df["MACD_HIST"] >= 0, "#22c55e", "#ef4444")
        fig.add_trace(go.Bar(x=df["time"], y=df["MACD_HIST"], name="Histogram", marker_color=hist_colors), row=3, col=1)
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["MACD"], name="MACD", line=dict(width=1.2, color="#60a5fa")),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["MACD_SIGNAL"], name="Signal", line=dict(width=1.2, color="#f59e0b")),
            row=3,
            col=1,
        )

    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        template="plotly_dark",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
