import os
import json
import gspread
import yfinance as yf
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from discord_webhook import DiscordWebhook, DiscordEmbed

SHEET_NAME = "Swing Trade Ledger"

def get_spreadsheet():
    """Authenticates and returns the Google Spreadsheet object."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS environment variable is missing.")
    
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def get_or_create_wash_sales(spreadsheet):
    """Ensures the Wash_Sales tab exists to track 30-day lockouts."""
    try:
        return spreadsheet.worksheet("Wash_Sales")
    except gspread.exceptions.WorksheetNotFound:
        print("Creating Wash_Sales tab...")
        ws = spreadsheet.add_worksheet(title="Wash_Sales", rows="100", cols="2")
        ws.append_row(["Ticker", "Lockout_End_Date"])
        return ws

def run_friday_retro():
    spreadsheet = get_spreadsheet()
    ledger = spreadsheet.worksheet("Ledger")
    wash_sales_sheet = get_or_create_wash_sales(spreadsheet)
    
    records = ledger.get_all_records()
    if not records:
        return None, None

    discord_report = []
    wash_sale_alerts = []

    # gspread rows are 1-indexed, and row 1 is headers. So data starts at row 2.
    for i, row in enumerate(records, start=2):
        status = str(row.get('Status', '')).strip().upper()
        ticker = row.get('Ticker', '')
        
        # Clean up PENDING trades that were never filled
        if status == 'PENDING_FILL':
            ledger.update_cell(i, 9, 'EXPIRED') # Column I is Status
            continue
            
        if status == 'ACTIVE' and ticker:
            try:
                # 1. Gather Trade Data
                # Fallback to Suggested Entry if Actual Fill is left blank
                entry_price = float(row.get('Actual Fill') or row.get('Suggested Entry'))
                stop_loss = float(row.get('Stop Loss'))
                target = float(row.get('Target Exit'))
                shares = int(row.get('Shares'))
                
                # 2. Fetch Current Market Price
                current_price = yf.download(ticker, period="1d", interval="1d", auto_adjust=True)['Close'].iloc[-1]
                current_price = float(current_price)
                
                # 3. Calculate PnL
                pnl_dollars = (current_price - entry_price) * shares
                pnl_pct = ((current_price / entry_price) - 1) * 100
                
                new_status = 'HOLDING'
                
                # 4. Evaluate Exit Conditions
                if current_price <= stop_loss:
                    new_status = 'CLOSED_LOSS'
                    lockout_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                    wash_sales_sheet.append_row([ticker, lockout_date])
                    wash_sale_alerts.append(f"🛑 **{ticker}**: Wash sale triggered. Locked until {lockout_date}.")
                    
                elif current_price >= target:
                    new_status = 'CLOSED_WIN'
                
                # Update the sheet if the trade closed
                if new_status != 'ACTIVE':
                    ledger.update_cell(i, 9, new_status) # Column I
                
                # 5. Format the Discord Report String
                icon = "🟢" if pnl_dollars > 0 else "🔴"
                report_line = f"{icon} **{ticker}** ({new_status})\n"
                report_line += f"↳ Entry: ${entry_price:.2f} | Current: ${current_price:.2f}\n"
                report_line += f"↳ PnL: **${pnl_dollars:,.2f}** ({pnl_pct:+.2f}%)\n"
                discord_report.append(report_line)

            except Exception as e:
                print(f"Error evaluating {ticker}: {e}")

    return discord_report, wash_sale_alerts

def send_retro_discord(report_lines, wash_alerts):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="📊 Friday Retro & PnL Scorecard", color="9b59b6")

    if not report_lines:
        embed.add_embed_field(name="Weekly Performance", value="No active trades to evaluate this week.", inline=False)
    else:
        embed.add_embed_field(name="Open/Closed Trades", value="\n".join(report_lines), inline=False)

    if wash_alerts:
        embed.add_embed_field(name="⚠️ Wash Sale Lockouts Generated", value="\n".join(wash_alerts), inline=False)

    embed.set_footer(text=f"Market Close Analysis: {datetime.now().strftime('%Y-%m-%d')}")
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Running Friday Retrospective...")
    report, wash_alerts = run_friday_retro()
    if report is not None:
        send_retro_discord(report, wash_alerts)
        print("Retro sent to Discord.")
    else:
        print("No data in ledger.")