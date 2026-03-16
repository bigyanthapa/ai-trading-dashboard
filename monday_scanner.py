import os
import json
import gspread
import yfinance as yf
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

# --- CONFIGURATION ---
UNIVERSE = ["NVDA", "TSLA", "PLTR", "AAPL", "GOOGL", "PYPL", "VOO", "BAC", "DAL", "ATEC", "F", "GE", "XOM"]
ACCOUNT_SIZE = 27000 
RISK_PER_TRADE = 0.01  # Max $270 risk per trade
TARGET_ALLOCATION = 2000  # Aiming for ~$2k per position
SHEET_NAME = "Swing Trade Ledger"

def connect_to_sheets():
    """Authenticates using the GCP JSON credentials."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GCP_CREDENTIALS')
    
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS environment variable is missing.")
        
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    
    try:
        return spreadsheet, spreadsheet.worksheet("Ledger")
    except gspread.exceptions.WorksheetNotFound:
        print("Tab 'Ledger' not found. Auto-renaming the first tab...")
        first_sheet = spreadsheet.get_worksheet(0)
        first_sheet.update_title("Ledger")
        
        if not first_sheet.row_values(1):
            headers = ['Date', 'Ticker', 'Action', 'Suggested Entry', 'Actual Fill', 'Stop Loss', 'Target Exit', 'Shares', 'Status']
            first_sheet.append_row(headers)
            
        return spreadsheet, first_sheet

def get_wash_sale_lockouts(spreadsheet):
    """Reads the Wash_Sales tab and returns a set of tickers currently locked out."""
    try:
        ws = spreadsheet.worksheet("Wash_Sales")
        records = ws.get_all_records()
        locked_tickers = set()
        today = datetime.now()
        
        for row in records:
            ticker = row.get("Ticker")
            lockout_end_str = row.get("Lockout_End_Date")
            if ticker and lockout_end_str:
                try:
                    lockout_end = datetime.strptime(str(lockout_end_str), '%Y-%m-%d')
                    if today <= lockout_end:
                        locked_tickers.add(ticker)
                except ValueError:
                    pass # Ignore malformed dates
        return locked_tickers
    except gspread.exceptions.WorksheetNotFound:
        return set() # Tab doesn't exist yet, so no lockouts

def run_monday_scan(locked_tickers):
    """Finds the top 5 momentum setups, excluding wash sales."""
    stock_data = yf.download(UNIVERSE, period="3mo", interval="1d", auto_adjust=True)
    setups = []

    for ticker in UNIVERSE:
        if ticker in locked_tickers:
            print(f"Skipping {ticker}: Active Wash Sale Lockout.")
            continue
            
        try:
            df = stock_data.xs(ticker, axis=1, level=1)
            price = df['Close'].iloc[-1]
            
            # Simple Momentum Filter: Is price above 20-day SMA?
            sma_20 = df['Close'].rolling(20).mean().iloc[-1]
            if price < sma_20:
                continue 
            
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
            
            shares = min(max_shares_by_risk, max_shares_by_capital)
            
            perf_5d = ((price / df['Close'].iloc[-6]) - 1) * 100
            
            setups.append({
                "ticker": ticker, "price": price, "perf": perf_5d,
                "stop": stop_loss, "target": target_exit, "shares": shares
            })
        except Exception as e:
            pass 

    # Return top 5
    return sorted(setups, key=lambda x: x['perf'], reverse=True)[:5]

def write_to_ledger_and_alert(sheet, setups, locked_tickers):
    """Writes the PENDING_FILL rows to Google Sheets and sends to Discord."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="🔔 Monday Action: Top 5 Swing Setups", color="f1c40f")
    
    discord_text = ""
    for s in setups:
        row = [
            today_str, s['ticker'], "BUY", round(s['price'], 2), "", 
            round(s['stop'], 2), round(s['target'], 2), s['shares'], "PENDING_FILL"
        ]
        sheet.append_row(row)
        
        capital_req = s['shares'] * s['price']
        discord_text += f"**{s['ticker']}** @ ~${s['price']:.2f}\n"
        discord_text += f"↳ Target: ${s['target']:.2f} | Stop: ${s['stop']:.2f}\n"
        discord_text += f"↳ Size: {s['shares']} shares (Est. Capital: ${capital_req:,.2f})\n\n"

    embed.add_embed_field(name="Recommendations added to Ledger", value=discord_text, inline=False)
    
    if locked_tickers:
        embed.add_embed_field(name="🛑 Ignored (Wash Sale Lockout)", value=", ".join(locked_tickers), inline=False)
        
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Connecting to Google Sheets...")
    spreadsheet, ledger_sheet = connect_to_sheets()
    
    print("Checking Wash Sale Lockouts...")
    locked_tickers = get_wash_sale_lockouts(spreadsheet)
    
    print("Running Monday Scanner...")
    top_5_setups = run_monday_scan(locked_tickers)
    
    print("Writing to Ledger and Discord...")
    write_to_ledger_and_alert(ledger_sheet, top_5_setups, locked_tickers)
    print("Monday workflow complete.")