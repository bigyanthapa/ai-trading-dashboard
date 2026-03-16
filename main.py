import os
import yfinance as yf
import pandas as pd
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

# --- CONFIGURATION ---
WATCHLIST = ["NVDA", "TSLA", "PLTR", "AAPL", "BAC", "DAL", "ATEC", "F", "GE", "XOM"]
SECTORS = {
    "Technology": "XLK",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Utilities": "XLU",
    "Materials": "XLB"
}
ACCOUNT_SIZE = 27000 
RISK_PER_TRADE = 0.01 

def get_market_analysis():
    """Fetches data and performs technical analysis."""
    # 1. Sector Leadership - Using auto_adjust to handle Yahoo API changes
    sector_tickers = list(SECTORS.values())
    s_data = yf.download(sector_tickers, period="2mo", interval="1d", auto_adjust=True)['Close']
    sector_perf = ((s_data.iloc[-1] / s_data.iloc[-20]) - 1) * 100
    top_sectors = sector_perf.sort_values(ascending=False)

    # 2. Stock Scanning & Position Sizing
    stock_data = yf.download(WATCHLIST, period="3mo", interval="1d", auto_adjust=True)
    setups = []

    for ticker in WATCHLIST:
        try:
            df = stock_data.xs(ticker, axis=1, level=1)
            # Ensure we use 'Close' everywhere now
            price = df['Close'].iloc[-1]
            
            # ATR Calculation for stop-loss
            high_low = df['High'] - df['Low']
            high_cp = abs(df['High'] - df['Close'].shift())
            low_cp = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            stop_loss = price - (2 * atr)
            risk_per_share = price - stop_loss
            shares = int((ACCOUNT_SIZE * RISK_PER_TRADE) / risk_per_share)
            
            # FIX: Changed 'Adj Close' to 'Close' here
            perf_5d = ((price / df['Close'].iloc[-5]) - 1) * 100
            
            setups.append({
                "ticker": ticker,
                "price": price,
                "perf": perf_5d,
                "shares": shares,
                "stop": stop_loss
            })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    top_setups = sorted(setups, key=lambda x: x['perf'], reverse=True)
    return top_sectors, top_setups

def format_trade_plans(top_setups):
    plans = ""
    for s in top_setups:
        if s['ticker'] == "NVDA":
            plans += f"**NVDA Plan:** Pivot at $180. If holds, target $195. Stop: ${s['stop']:.2f}\n"
        if s['ticker'] == "TSLA":
            plans += f"**TSLA Plan:** Resistance at $405. Watch for break. Stop: ${s['stop']:.2f}\n"
    return plans

def send_to_discord(sectors, setups, plans):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("CRITICAL: DISCORD_WEBHOOK secret not found.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="📊 Weekly AI Swing Trade Dashboard", color="2ecc71")
    
    leader_text = "\n".join([f"**{k}**: {sectors[v]:.1f}%" for k, v in list(SECTORS.items())[:3]])
    embed.add_embed_field(name="🔥 Top Sectors (4W)", value=leader_text, inline=False)

    setup_text = "\n".join([f"{s['ticker']}: ${s['price']:.2f} ({s['perf']:.1f}%) | Size: {s['shares']}" for s in setups[:5]])
    embed.add_embed_field(name="🚀 Top Swing Setups", value=setup_text, inline=False)

    embed.add_embed_field(name="🎯 Ticker Trade Plans", value=plans if plans else "No core plans found.", inline=False)
    
    embed.set_footer(text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} CST")
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Running Weekly Market Scan...")
    sectors, setups = get_market_analysis()
    plans = format_trade_plans(setups)
    send_to_discord(sectors, setups, plans)
    print("Dashboard sent to Discord.")