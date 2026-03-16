import os
import json
import gspread
import yfinance as yf
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

# --- CONFIGURATION ---
# Mixing high-volatility (NVDA, TSLA, PLTR) with balanced large caps (AAPL, VOO)
UNIVERSE = ["NVDA", "TSLA", "PLTR", "AAPL", "GOOGL", "PYPL", "VOO", "BAC", "DAL", "ATEC", "F", "GE", "XOM"]
ACCOUNT_SIZE = 27000 
RISK_PER_TRADE = 0.01  # Max $270 risk per trade
TARGET_ALLOCATION = 2000  # Aiming for ~$2k per position
SHEET_NAME = "Swing Trade Ledger"

def connect_to_sheets():
    """Authenticates using the GCP JSON credentials stored in GitHub Secrets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GCP_CREDENTIALS')
    
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS environment variable is missing.")
        
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    
    try:
        # Try to find the specific tab
        return spreadsheet.worksheet("Ledger")
    except gspread.exceptions.WorksheetNotFound:
        print("Tab 'Ledger' not found. Auto-renaming the first tab...")
        # Fallback: Grab the first tab and rename it
        first_sheet = spreadsheet.get_worksheet(0)
        first_sheet.update_title("Ledger")
        
        # Self-healing: If row 1 is empty, inject the headers
        if not first_sheet.row_values(1):
            headers = ['Date', 'Ticker', 'Action', 'Suggested Entry', 'Actual Fill', 'Stop Loss', 'Target Exit', 'Shares', 'Status']
            first_sheet.append_row(headers)
            
        return first_sheet

def run_monday_scan():
    """Finds the top 3 momentum setups and calculates risk-adjusted entry/exit."""
    stock_data = yf.download(UNIVERSE, period="3mo", interval="1d", auto_adjust=True)
    setups = []

    for ticker in UNIVERSE:
        try:
            df = stock_data.xs(ticker, axis=1, level=1)
            price = df['Close'].iloc[-1]
            
            # Simple Momentum Filter: Is price above 20-day SMA?
            sma_20 = df['Close'].rolling(20).mean().iloc[-1]
            if price < sma_20:
                continue # Skip stocks in short-term downtrends
            
            # ATR for Stop Loss & Volatility Measurement
            high_low = df['High'] - df['Low']
            high_cp = abs(df['High'] - df['Close'].shift())
            low_cp = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            stop_loss = price - (2 * atr)
            target_exit = price + (4 * atr) # 1:2 Risk/Reward Ratio
            
            # Position Sizing Math
            risk_per_share = price - stop_loss
            max_shares_by_risk = int((ACCOUNT_SIZE * RISK_PER_TRADE) / risk_per_share)
            max_shares_by_capital = int(TARGET_ALLOCATION / price)
            
            # Take the smaller size to respect both the $270 risk cap and the $2000 capital cap
            shares = min(max_shares_by_risk, max_shares_by_capital)
            
            # Calculate 5-day performance for ranking
            perf_5d = ((price / df['Close'].iloc[-6]) - 1) * 100
            
            setups.append({
                "ticker": ticker, "price": price, "perf": perf_5d,
                "stop": stop_loss, "target": target_exit, "shares": shares
            })
        except Exception as e:
            pass # Silently skip errors for individual tickers in a batch scan

    # Return top 3 based on 5-day momentum
    return sorted(setups, key=lambda x: x['perf'], reverse=True)[:3]

def write_to_ledger_and_alert(sheet, setups):
    """Writes the PENDING_FILL rows to Google Sheets and sends to Discord."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="🔔 Monday Action: Top 3 Swing Setups", color="f1c40f")
    
    discord_text = ""
    for s in setups:
        # 1. Write to Google Sheet
        row = [
            today_str, s['ticker'], "BUY", round(s['price'], 2), "", 
            round(s['stop'], 2), round(s['target'], 2), s['shares'], "PENDING_FILL"
        ]
        sheet.append_row(row)
        
        # 2. Format Discord Alert
        capital_req = s['shares'] * s['price']
        discord_text += f"**{s['ticker']}** @ ~${s['price']:.2f}\n"
        discord_text += f"↳ Target: ${s['target']:.2f} | Stop: ${s['stop']:.2f}\n"
        discord_text += f"↳ Size: {s['shares']} shares (Est. Capital: ${capital_req:,.2f})\n\n"

    embed.add_embed_field(name="Recommendations added to Ledger", value=discord_text, inline=False)
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Connecting to Google Sheets...")
    sheet = connect_to_sheets()
    
    print("Running Monday Scanner...")
    top_3_setups = run_monday_scan()
    
    print("Writing to Ledger and Discord...")
    write_to_ledger_and_alert(sheet, top_3_setups)
    print("Monday workflow complete.")