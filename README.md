# 📈 AI Swing Trading Dashboard & Quantitative Pipeline

A production-grade, closed-loop algorithmic trading system designed to safely scale a swing trading portfolio. This system performs multi-factor technical analysis, manages active trades, enforces strict risk-management rules, and provides institutional-level observability directly to Discord.

Powered by **Python**, **GitHub Actions**, **Google Sheets**, and **Discord**.

## 🚀 System Architecture Overview

This pipeline operates entirely headlessly, utilizing Google Sheets as a state-machine database to track the lifecycle of every trade. It is divided into four autonomous engines:

1. **The Scanner (`monday_scanner.py`):** Runs Monday mornings. Dynamically scrapes the S&P 500, calculates technical indicators (RSI, EMAs, Golden Cross), filters out bad regimes, and writes `PENDING_FILL` setups to the database.
2. **The Observer (`wednesday_checkup.py`):** Runs midday Wednesday. A read-only telemetry script that calculates the exact distance to targets/stops for all active inventory and reports mid-week portfolio health.
3. **The Manager (`friday_retro.py`):** Runs Friday afternoons. Evaluates end-of-week prices to update trade states, triggers "Free Ride" trailing exits, logs realized PnL, and enforces IRS Wash Sale lockouts.
4. **The Reporter (`equity_curve.py`):** Runs monthly. Reconstructs the ledger to generate a visual, dark-mode equity curve chart of portfolio growth.

---

## 🛡️ Core Defensive Features

* **Dynamic Market Regime Filter:** Checks the S&P 500 (SPY) against its 50-day moving average. If the market is in a downtrend, the algorithm automatically slices capital allocation per trade by 50%.
* **Risk-Adjusted Sizing:** Automatically calculates position sizes to ensure maximum risk never exceeds 1% of total equity based on the ATR (Average True Range) stop loss.
* **Sector Correlation Limits:** Prevents portfolio bloat by strictly limiting recommendations to a maximum of 2 stocks per sector.
* **"Free Ride" Trailing Exits:** When a trade hits a 1:2 Risk/Reward target, the system automatically books 50% of the profit and moves the stop loss to break-even for the remaining shares.
* **Automated Wash Sale Compliance:** If a trade is closed for a loss, the ticker is automatically placed in a 30-day IRS lockout database and explicitly ignored by the scanner until the window clears.
* **Earnings Blackout:** Interrogates the corporate calendar and automatically disqualifies any ticker reporting earnings within the next 7 days to prevent overnight gap-down risk.

---

## 🧮 The Risk Model

The system strictly enforces capital preservation using Volatility-Adjusted Sizing.

$$PositionSize = \frac{TotalEquity \times 0.01}{Price - (Price - (2 \times ATR))}$$

---

## ⚙️ Infrastructure & Setup

### Environment Secrets (GitHub Actions)
You must configure the following repository secrets:
* `DISCORD_WEBHOOK`: The URL for the Discord channel where the bot sends alerts.
* `GCP_CREDENTIALS`: The JSON Service Account key used to authenticate with the Google Sheets API.

### Google Sheets Schema
The bot expects a Google Sheet named `Swing Trade Ledger` with two tabs:
1. **`Ledger`** (Columns: Date, Ticker, Action, Suggested Entry, Actual Fill, Stop Loss, Target Exit, Actual Exit, Shares, Status)
2. **`Wash_Sales`** (Dynamically managed by the bot to track 30-day lockouts)

### Action Status Flow (State Machine)
* `PENDING_FILL`: Written by the Monday scanner.
* `ACTIVE`: (Manual) Updated by the user after filling the trade in their broker.
* `FREE_RIDE`: Updated by the Friday retro when the first target is hit.
* `CLOSED_WIN` / `CLOSED_LOSS`: Finalized states resolved by the Friday retro.
* `EXPIRED`: Replaces pending trades that were never filled.

---

## 🤖 CI/CD Deployment (GitHub Actions)

The pipeline is governed by cron-scheduled workflows in `.github/workflows/`:
* **Monday Scanner:** `0 13 * * 1` (8:00 AM CDT Monday)
* **Wednesday Checkup:** `0 17 * * 3` (12:00 PM CDT Wednesday)
* **Friday Retro:** `0 20 * * 5` (3:00 PM CDT Friday)
* **Monthly Equity Curve:** `0 13 1 * *` (8:00 AM CDT on the 1st of every month)

*Disclaimer: This tool is for educational purposes only. Trading involves significant risk. Ensure all trade plans are reviewed manually before execution.*