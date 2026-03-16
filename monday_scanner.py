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
TICKER_SECTORS = {
    "NVDA": "Tech", "TSLA": "Consumer", "PLTR": "Tech", "AAPL": "Tech", 
    "GOOGL": "Comm", "PYPL": "Financials", "VOO": "Index", "BAC": "Financials", 
    "DAL": "Industrials", "ATEC": "Health", "F": "Consumer", "GE": "Industrials", "XOM": "Energy"
}
ACCOUNT_SIZE = 27000 
RISK_PER_TRADE = 0.01 
BASE_ALLOCATION = 2000 
SHEET_NAME = "Swing Trade Ledger"

def connect_to_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS missing.")
        
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    
    try:
        return spreadsheet, spreadsheet.worksheet("Ledger")
    except gspread.exceptions.WorksheetNotFound:
        first_sheet = spreadsheet.get_worksheet(0)
        first_sheet.update_title("Ledger")
        if not first_sheet.row_values(1):
            first_sheet.append_row(['Date', 'Ticker', 'Action', 'Suggested Entry', 'Actual Fill', 'Stop Loss', 'Target Exit', 'Shares', 'Status'])
        return spreadsheet, first_sheet

def get_wash_sale_lockouts(spreadsheet):
    try:
        ws = spreadsheet.worksheet("Wash_Sales")
        records = ws.get_all_records()
        locked = set()
        today = datetime.now()
        for row in records:
            if row.get("Ticker") and row.get("Lockout_End_Date"):
                try:
                    if today <= datetime.strptime(str(row.get("Lockout_End_Date")), '%Y-%m-%d'):
                        locked.add(row.get("Ticker"))
                except ValueError: pass
        return locked
    except gspread.exceptions.WorksheetNotFound:
        return set()

def get_market_regime():
    """Checks if SPY is above its 50-day SMA. Returns an allocation multiplier."""
    try:
        spy = yf.download("SPY", period="3mo", interval="1d", auto_adjust=True)['Close'].squeeze()
        sma_50 = spy.rolling(50).mean().iloc[-1]
        if spy.iloc[-1] < sma_50:
            return 0.5, "🔴 DEFENSIVE (SPY < 50 SMA)"
        return 1.0, "🟢 AGGRESSIVE (SPY > 50 SMA)"
    except:
        return 1.0, "⚪ NEUTRAL (Regime Check Failed)"

def is_earnings_near(ticker, days_out=7):
    """Checks if earnings are within the next X days."""
    try:
        tkr = yf.Ticker(ticker)
        cal = tkr.calendar
        if cal is not None and not cal.empty and 'Earnings Date' in cal:
            next_earnings = pd.to_datetime(cal['Earnings Date'].iloc[0]).tz_localize(None)
            days_until = (next_earnings - datetime.now()).days
            if 0 <= days_until <= days_out:
                return True
    except:
        pass
    return False

def run_monday_scan(locked_tickers, allocation_multiplier):
    stock_data = yf.download(UNIVERSE, period="3mo", interval="1d", auto_adjust=True)
    target_capital = BASE_ALLOCATION * allocation_multiplier
    raw_setups = []
    skipped_earnings = []

    for ticker in UNIVERSE:
        if ticker in locked_tickers:
            continue
            
        if is_earnings_near(ticker):
            skipped_earnings.append(ticker)
            continue
            
        try:
            df = stock_data.xs(ticker, axis=1, level=1)
            price = df['Close'].iloc[-1]
            
            # Trend Filter
            if price < df['Close'].rolling(20).mean().iloc[-1]:
                continue 
            
            # ATR Math
            high_low = df['High'] - df['Low']
            high_cp = abs(df['High'] - df['Close'].shift())
            low_cp = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            stop_loss = price - (2 * atr)
            target_exit = price + (4 * atr)
            
            # Risk Sizing
            risk_per_share = price - stop_loss
            shares = min(int((ACCOUNT_SIZE * RISK_PER_TRADE) / risk_per_share), int(target_capital / price))
            perf_5d = ((price / df['Close'].iloc[-6]) - 1) * 100
            
            raw_setups.append({
                "ticker": ticker, "price": price, "perf": perf_5d,
                "stop": stop_loss, "target": target_exit, "shares": shares,
                "sector": TICKER_SECTORS.get(ticker, "Unknown")
            })
        except Exception:
            pass 

    # Sort by performance
    raw_setups = sorted(raw_setups, key=lambda x: x['perf'], reverse=True)
    
    # SECTOR CORRELATION FILTER
    final_setups = []
    selected_sectors = set()
    
    for s in raw_setups:
        if s['sector'] in selected_sectors and s['sector'] != "Index":
            continue # We already have a stock from this sector
            
        final_setups.append(s)
        selected_sectors.add(s['sector'])
        
        if len(final_setups) >= 5:
            break
            
    return final_setups, skipped_earnings

def write_to_ledger_and_alert(sheet, setups, locked_tickers, skipped_earnings, regime_text):
    today_str = datetime.now().strftime('%Y-%m-%d')
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="🔔 Monday Action: Top 5 Swing Setups", color="f1c40f")
    
    embed.add_embed_field(name="🌍 Market Regime", value=regime_text, inline=False)
    
    discord_text = ""
    for s in setups:
        sheet.append_row([
            today_str, s['ticker'], "BUY", round(s['price'], 2), "", 
            round(s['stop'], 2), round(s['target'], 2), s['shares'], "PENDING_FILL"
        ])
        
        capital_req = s['shares'] * s['price']
        discord_text += f"**{s['ticker']}** ({s['sector']}) @ ~${s['price']:.2f}\n"
        discord_text += f"↳ Target: ${s['target']:.2f} | Stop: ${s['stop']:.2f}\n"
        discord_text += f"↳ Size: {s['shares']} shares (Est. Cap: ${capital_req:,.2f})\n\n"

    embed.add_embed_field(name="Recommendations added to Ledger", value=discord_text if discord_text else "No valid setups found.", inline=False)
    
    if locked_tickers:
        embed.add_embed_field(name="🛑 Ignored (Wash Sale)", value=", ".join(locked_tickers), inline=False)
    if skipped_earnings:
        embed.add_embed_field(name="⚠️ Ignored (Earnings < 7 Days)", value=", ".join(skipped_earnings), inline=False)
        
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Connecting to Google Sheets...")
    spreadsheet, ledger_sheet = connect_to_sheets()
    
    print("Checking Market Regime & Lockouts...")
    locked_tickers = get_wash_sale_lockouts(spreadsheet)
    multiplier, regime_text = get_market_regime()
    
    print(f"Regime: {regime_text}. Running Scanner...")
    top_5_setups, skipped_earnings = run_monday_scan(locked_tickers, multiplier)
    
    print("Writing to Ledger and Discord...")
    write_to_ledger_and_alert(ledger_sheet, top_5_setups, locked_tickers, skipped_earnings, regime_text)
    print("Monday workflow complete.")