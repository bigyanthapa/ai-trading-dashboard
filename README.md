# 📈 Weekly AI Swing Trade Dashboard

A production-grade automation engine that performs multi-factor technical analysis, sector rotation tracking, and risk-adjusted position sizing for a $NK swing trading portfolio.

## 🚀 Overview
This system runs headlessly via **GitHub Actions** every Sunday at 6:00 PM CST. It analyzes market internals to prepare a "Battle Plan" for the Monday market open, delivering actionable insights directly to Discord.

### Key Features
* **Sector Leadership:** Identifies the top 3 performing sectors using 4-week relative strength.
* **Smart Scanning:** Filters a custom watchlist (NVDA, TSLA, PLTR, etc.) for 5-day momentum setups.
* **Risk Management:** Automatically calculates share size based on a 1% total account risk model using 2x ATR (Average True Range) stops.
* **Automated Pipeline:** Zero-infrastructure deployment using GitHub's cron-scheduler.

---

## 🏗️ Architecture
The project follows a decoupled functional design:
1.  **Data Layer:** Leverages `yfinance` to pull OHLCV data for equity and sector ETFs.
2.  **Analysis Engine:** Processes raw data into technical signals (ATR, Relative Strength, Performance %).
3.  **Notification Layer:** Formats findings into a rich Discord Embed for mobile-friendly consumption.

---

## 🛠️ Local Setup

### Prerequisites
* Python 3.10+
* A Discord Webhook URL

### Installation
1. **Clone and Navigate:**
   ```bash
   git clone <your-repo-url>
   cd ai-trading-dashboard

2. **Environment Setup:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3. **Local Testing:**
   ```bash
   export DISCORD_WEBHOOK="your_webhook_url"
   python main.py 

# 🤖 CI/CD Deployment

## GitHub Actions Configuration
The dashboard is controlled by .github/workflows/weekly_swing.yml.
* Schedule: 0 0 * * 1 (UTC) — Equivalent to Sunday 6:00 PM CST.
* Secrets: Requires a repository secret named DISCORD_WEBHOOK.

## Risk Model Formula
The system enforces strict capital preservation:
$$PositionSize = \frac{TotalEquity \times 0.01}{Price - (2 \times ATR)}$$

# 📝 Roadmap
[ ] Integrate Sentiment Analysis via NewsAPI.

[ ] Add MACD/RSI divergence detection.

[ ] Support for multi-timeframe analysis (Daily vs Weekly trends).

Disclaimer: This tool is for educational purposes only. Trading involves significant risk. Ensure all trade plans are reviewed manually before execution.