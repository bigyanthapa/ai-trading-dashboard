import os
import json
import random
import gspread
import yfinance as yf
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

# --- CONFIGURATION ---
CORE_UNIVERSE = ["NVDA", "TSLA", "PLTR", "AAPL", "GOOGL", "PYPL", "VOO", "BAC", "DAL", "ATEC", "F", "GE", "XOM"]
CORE_SECTORS = {
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
        first_sheet.append_row(['Date', 'Ticker', 'Action', 'Suggested Entry', 'Actual Fill', 'Stop Loss', 'Target Exit', 'Actual Exit', 'Shares', 'Status'])
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

def get_dynamic_universe(sample_size=100):
    """Scrapes the S&P 500 and returns a dynamic list of tickers combined with the core universe."""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        html = pd.read_html(url)
        df = html[0]
        sp500_tickers = df['Symbol'].tolist()
        sp500_tickers = [t.replace('.', '-') for t in sp500_tickers] # Fix BRK.B for yfinance
        
        # Randomly sample the S&P 500 to keep the scan fresh and avoid yfinance timeouts
        random_sample = random.sample(sp500_tickers, sample_size)
        
        # Combine core and random sample, removing duplicates
        combined_universe = list(set(CORE_UNIVERSE + random_sample))
        return combined_universe, df # Return df to extract sectors later
    except Exception as e:
        print(f"Failed to fetch S&P 500: {e}")
        return CORE_UNIVERSE, None

def get_market_regime():
    try:
        spy = yf.download("SPY", period="1y", interval="1d", auto_adjust=True)['Close'].squeeze()
        sma_50 = spy.rolling(50).mean().iloc[-1]
        if spy.iloc[-1] < sma_50:
            return 0.5, "🔴 DEFENSIVE (SPY < 50 SMA)"
        return 1.0, "🟢 AGGRESSIVE (SPY > 50 SMA)"
    except:
        return 1.0, "⚪ NEUTRAL (Regime Check Failed)"

def is_earnings_near(ticker, days_out=7):
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

def calculate_rsi(series, period=14):
    """Calculates the Relative Strength Index."""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def run_monday_scan(locked_tickers, allocation_multiplier):
    scan_universe, sp500_df = get_dynamic_universe()
    print(f"Scanning {len(scan_universe)} tickers...")
    
    # We now fetch 1 year of data to ensure the 200-day SMA can calculate
    stock_data = yf.download(scan_universe, period="1y", interval="1d", auto_adjust=True)
    target_capital = BASE_ALLOCATION * allocation_multiplier
    raw_setups = []
    skipped_earnings = []

    for ticker in scan_universe:
        if ticker in locked_tickers:
            continue
        if is_earnings_near(ticker):
            skipped_earnings.append(ticker)
            continue
            
        try:
            df = stock_data.xs(ticker, axis=1, level=1).copy()
            df = df.dropna()
            if len(df) < 200:
                continue # Skip if not enough data for 200 SMA
                
            price = df['Close'].iloc[-1]
            
            # --- TECHNICAL INDICATORS ---
            sma_50 = df['Close'].rolling(50).mean().iloc[-1]
            sma_200 = df['Close'].rolling(200).mean().iloc[-1]
            ema_21 = df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
            rsi = calculate_rsi(df['Close']).iloc[-1]
            
            # Trend Filter: Price must be above 21 EMA for short-term momentum
            if price < ema_21:
                continue 
            
            # Overall Trend Evaluation
            is_golden_cross = sma_50 > sma_200
            trend_status = "🟢 Bullish" if (price > sma_50 and is_golden_cross) else "🟡 Neutral/Transition"
            
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
            if shares == 0:
                continue
                
            # Estimated Hold Time (Assuming directional drift is ~40% of ATR per day)
            distance_to_target = target_exit - price
            est_days = distance_to_target / (atr * 0.4)
            est_weeks = round(est_days / 5, 1)
            
            perf_5d = ((price / df['Close'].iloc[-6]) - 1) * 100
            
            # Get Sector
            sector = CORE_SECTORS.get(ticker)
            if not sector and sp500_df is not None:
                sector_match = sp500_df[sp500_df['Symbol'] == ticker.replace('-', '.')]
                if not sector_match.empty:
                    sector = sector_match['GICS Sector'].iloc[0][:10] # Truncate long sector names
            sector = sector or "Unknown"

            raw_setups.append({
                "ticker": ticker, "price": price, "perf": perf_5d,
                "stop": stop_loss, "target": target_exit, "shares": shares,
                "sector": sector, "sma_50": sma_50, "sma_200": sma_200, 
                "ema_21": ema_21, "rsi": rsi, "trend": trend_status, 
                "golden_cross": is_golden_cross, "est_weeks": est_weeks
            })
        except Exception as e:
            pass 

    # Sort by performance
    raw_setups = sorted(raw_setups, key=lambda x: x['perf'], reverse=True)
    
    # SECTOR CORRELATION FILTER
    final_setups = []
    sector_counts = {}
    
    for s in raw_setups:
        current_count = sector_counts.get(s['sector'], 0)
        
        # Allow up to 2 stocks per sector (unless it's an Index, which is unlimited)
        if current_count >= 2 and s['sector'] != "Index":
            continue 
            
        final_setups.append(s)
        sector_counts[s['sector']] = current_count + 1
        
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
        # Write to Google Sheet
        sheet.append_row([
            today_str, s['ticker'], "BUY", round(s['price'], 2), "", 
            round(s['stop'], 2), round(s['target'], 2), "", s['shares'], "PENDING_FILL"
        ])
        
        # Financial Math
        capital_req = s['shares'] * s['price']
        pot_gain_dlr = (s['target'] - s['price']) * s['shares']
        pot_gain_pct = ((s['target'] / s['price']) - 1) * 100
        pot_risk_dlr = (s['price'] - s['stop']) * s['shares']
        pot_risk_pct = (1 - (s['stop'] / s['price'])) * 100
        
        # Format the Payload
        gx_emoji = "✅" if s['golden_cross'] else "❌"
        hold_text = f"~{s['est_weeks']} weeks" if s['est_weeks'] >= 1.0 else "Under 1 week"
        
        discord_text += f"**{s['ticker']}** ({s['sector']}) @ ~${s['price']:.2f}\n"
        discord_text += f"↳ Target: ${s['target']:.2f} | Stop: ${s['stop']:.2f}\n"
        discord_text += f"↳ Size: {s['shares']} shares (Est. Cap: ${capital_req:,.2f})\n"
        discord_text += f"↳ **Gain:** ${pot_gain_dlr:,.2f} (+{pot_gain_pct:.1f}%) | **Risk:** ${pot_risk_dlr:,.2f} (-{pot_risk_pct:.1f}%)\n"
        discord_text += f"↳ 📊 **Techs:** RSI: {s['rsi']:.0f} | 21EMA: ${s['ema_21']:.2f} | GX: {gx_emoji} | {s['trend']}\n"
        discord_text += f"↳ ⏱️ **Est. Hold:** {hold_text}\n\n"

    embed.add_embed_field(name="Recommendations added to Ledger", value=discord_text if discord_text else "No valid setups found.", inline=False)
    
    if locked_tickers:
        embed.add_embed_field(name="🛑 Ignored (Wash Sale)", value=", ".join(list(locked_tickers)[:10]) + "...", inline=False)
        
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