import os
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

# --- CONFIGURATION ---
WATCHLIST = ["NVDA", "TSLA", "PLTR", "AAPL", "GOOGL", "PYPL", "VOO", "BAC", "DAL", "ATEC", "F", "GE", "XOM"]
SECTORS = {
    "Technology": "XLK", "Energy": "XLE", "Financials": "XLF", 
    "Health Care": "XLV", "Industrials": "XLI", "Utilities": "XLU", "Materials": "XLB"
}
ACCOUNT_SIZE = 27000 
RISK_PER_TRADE = 0.01 

def get_sentiment(ticker):
    """Scrapes headlines for basic sentiment scoring."""
    try:
        url = f"https://www.google.com/search?q={ticker}+stock+news&tbm=nws"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = [g.text.lower() for g in soup.find_all('div', dict(role='heading'))]
        
        bull = ['breakout', 'growth', 'upgrade', 'buy', 'positive', 'surpass', 'soar']
        bear = ['drop', 'downgrade', 'sell', 'lawsuit', 'investigation', 'fall', 'miss']
        
        score = sum(1 for h in headlines for w in bull if w in h) - sum(1 for h in headlines for w in bear if w in h)
        return "🟢 Bullish" if score > 0 else "🔴 Bearish" if score < 0 else "⚪ Neutral"
    except:
        return "❓ Unknown"

def get_market_analysis():
    # 1. Sector Leadership
    sector_tickers = list(SECTORS.values())
    s_data = yf.download(sector_tickers, period="2mo", interval="1d", auto_adjust=True)['Close']
    sector_perf = ((s_data.iloc[-1] / s_data.iloc[-20]) - 1) * 100
    top_sectors = sector_perf.sort_values(ascending=False)

    # 2. Benchmark (SPY) - Unified 5-day lookback
    spy_data = yf.download("SPY", period="1mo", interval="1d", auto_adjust=True)['Close']
    spy_perf_5d = ((spy_data.iloc[-1] / spy_data.iloc[-6]) - 1) * 100

    # 3. Stock Scanning
    stock_data = yf.download(WATCHLIST, period="3mo", interval="1d", auto_adjust=True)
    setups = []

    for ticker in WATCHLIST:
        try:
            df = stock_data.xs(ticker, axis=1, level=1)
            price = df['Close'].iloc[-1]

            # Relative Strength (RS) vs SPY
            stock_perf_5d = ((price / df['Close'].iloc[-6]) - 1) * 100
            rs_score = stock_perf_5d - spy_perf_5d
            
            # ATR/Stop Loss
            high_low = df['High'] - df['Low']
            high_cp = abs(df['High'] - df['Close'].shift())
            low_cp = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            stop_loss = price - (2 * atr)
            
            # --- STOP LOSS WARNING LOGIC ---
            # Flag if price is within 2% of the stop loss
            proximity_to_stop = (price - stop_loss) / price
            risk_alert = True if proximity_to_stop <= 0.02 else False
            
            risk_per_share = price - stop_loss
            shares = int((ACCOUNT_SIZE * RISK_PER_TRADE) / risk_per_share)
            
            setups.append({
                "ticker": ticker, "price": price, "perf": stock_perf_5d,
                "rs_score": rs_score, "shares": shares, "stop": stop_loss,
                "sentiment": get_sentiment(ticker), "risk_alert": risk_alert
            })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    return top_sectors, sorted(setups, key=lambda x: x['rs_score'], reverse=True), spy_perf_5d

def send_to_discord(sectors, setups, plans, spy_perf):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    webhook = DiscordWebhook(url=webhook_url)
    color = "3498db" if spy_perf > 0 else "e67e22"
    embed = DiscordEmbed(title="🚀 Weekly AI Swing Dashboard", color=color)

    embed.add_embed_field(name="📊 Benchmark", value=f"**SPY 5-Day:** {spy_perf:.2f}%", inline=False)

    # 1. High Risk / Stop Loss Alerts
    alerts = [f"⚠️ **{s['ticker']}** is near stop: ${s['stop']:.2f}" for s in setups if s['risk_alert']]
    if alerts:
        embed.add_embed_field(name="🚨 Risk Alerts (Price < 2% from Stop)", value="\n".join(alerts), inline=False)

    # 2. Sector Leadership
    leader_text = "\n".join([f"**{k}**: {sectors[v]:.1f}%" for k, v in list(SECTORS.items())[:3]])
    embed.add_embed_field(name="🔥 Top Sectors (4W)", value=leader_text, inline=True)

    # 3. Top 5 Setups (Fixed redundancy)
    setup_text = ""
    for s in setups[:5]:
        rs_icon = "📈" if s['rs_score'] > 0 else "📉"
        setup_text += f"**{s['ticker']}**: ${s['price']:.2f} ({s['perf']:.1f}%) | {s['sentiment']}\n"
        setup_text += f"↳ RS vs SPY: {s['rs_score']:+.2f}% {rs_icon} | Size: {s['shares']}\n"
    
    embed.add_embed_field(name="🚀 Top Swing Setups", value=setup_text, inline=False)
    embed.add_embed_field(name="🎯 Ticker Trade Plans", value=plans if plans else "No core plans.", inline=False)
    
    embed.set_footer(text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} CST")
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Running Weekly Market Scan...")
    sectors, setups = get_market_analysis()
    plans = format_trade_plans(setups)
    send_to_discord(sectors, setups, plans)
    print("Dashboard sent to Discord.")