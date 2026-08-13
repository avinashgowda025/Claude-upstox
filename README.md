# Indian Trading Terminal — Upstox Research & Paper-Trading Dashboard

A read-only, mobile-friendly Streamlit dashboard for NSE index options
(NIFTY 50 / BANK NIFTY / FINNIFTY) built on the Upstox API. It surfaces price
structure, option-chain positioning, and a transparent rule-based signal
engine — and lets you log **simulated** trades to a paper journal.

**No order-placement endpoint is called anywhere in this codebase.** This is
a research tool, not a broker integration for live trading.

## Features

**Market data**
- Live LTP for NIFTY 50 / BANK NIFTY / FINNIFTY (extend `core/config.py` to add more)
- Full option chain: OI, ΔOI, IV, and Delta/Gamma/Theta/Vega per strike
- Max pain (vectorized), PCR, and support/resistance from OI concentration

**OI buildup classification** *(new)*
- Each contract is tagged **Long Buildup / Short Buildup / Short Covering /
  Long Unwinding** from its own price move + OI change — the same read
  professional option-chain tools use, not just a raw ΔOI number

**Technicals** *(new)*
- Candlestick chart (Plotly) with EMA20/50, Bollinger Bands(20,2) and
  session-anchored VWAP overlaid, plus RSI(14) and MACD(12,26,9) subplots
- Daily, 1H, 30m and 15m timeframes

**Multi-timeframe candle check**
- Classifies the latest candle on 15m / 30m / 1H / Daily (Doji, Hammer,
  Shooting Star, Marubozu, Engulfing, Inside Bar…) and reports whether
  timeframes agree

**Signal engine**
- A transparent, explainable heuristic — every vote it casts is listed in
  plain English, never a black box
- Combines EMA/RSI/MACD structure, PCR, near-ATM OI buildup, and (when
  available) intraday VWAP into BUY CALL / BUY PUT / SIDEWAYS-RANGE / NO TRADE
- **For paper trading only.** It is a checklist, not financial advice

**Paper trading & journal**
- Record simulated trades with planned SL/target, track mark-to-market P&L,
  export the journal as CSV

## Architecture

```
app.py                  Streamlit entrypoint — wires everything together
core/
  config.py              Instrument keys, API base URLs, IST market-hours check
  api.py                 Cached, retrying Upstox client (no order endpoints)
  indicators.py           EMA / RSI / MACD / ATR / Bollinger / VWAP (pure functions)
  candles.py               Candle-pattern classification + multi-timeframe scoring
  options.py               Chain flattening, OI buildup, max pain, PCR, support/resistance
  signals.py                The heuristic signal engine
  paper_trading.py           Session-state trade journal
ui/
  style.py                CSS for the dashboard shell
  components.py            Hero card / signal pill / market-status badge
  charts.py                 Plotly technical chart
tests/                    pytest coverage for every pure function above
```

Everything in `core/` except `api.py` and `paper_trading.py` is a pure
function with no network or Streamlit dependency, which is what makes it
unit-testable — see `tests/`.

## Security

**Never** put your Upstox Analytics Token in source code, GitHub, chat,
screenshots, or this README. The app reads it only from:

```
UPSTOX_ANALYTICS_TOKEN
```
as a Streamlit secret or environment variable — never hardcoded.

## Streamlit Cloud deployment

1. Create a GitHub repository and push these files.
2. Create a Streamlit Community Cloud app pointing at `app.py`.
3. In the app's **Settings → Secrets**, add:

   ```toml
   UPSTOX_ANALYTICS_TOKEN = "PASTE_YOUR_TOKEN_HERE"
   ```

4. Save/redeploy.
5. Open the generated app URL on your phone.

## Local testing

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then paste your token
streamlit run app.py
```

`.streamlit/secrets.toml` is gitignored — never commit it.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests cover indicators, candle-pattern classification, max pain, PCR, and OI
buildup classification against hand-verified fixtures — no network access or
Upstox token required. A GitHub Actions workflow (`.github/workflows/tests.yml`)
runs the same suite on every push and pull request.

## Roadmap

- [x] Historical candles
- [x] EMA / RSI / MACD / VWAP / ATR
- [x] OI buildup classification
- [x] Max pain
- [ ] IV rank / IV percentile (needs historical IV, not just a point-in-time read)
- [ ] Backtesting engine
- [ ] Multi-day/multi-account trading journal with tags and win-rate analytics
- [ ] Optional live WebSocket layer for sub-30s updates

This project does not place real trades and never will — it's a research and
paper-trading tool only.
