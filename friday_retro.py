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
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS environment variable is missing.")
    
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def get_or_create_wash_sales(spreadsheet):
    try:
        return spreadsheet.worksheet("Wash_Sales")
    except gspread.exceptions.WorksheetNotFound:
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

    # gspread rows are 1-indexed, row 1 is headers. Data starts at row 2.
    for i, row in enumerate(records, start=2):
        status = str(row.get('Status', '')).strip().upper()
        ticker = row.get('Ticker', '')
        
        if status == 'PENDING_FILL':
            ledger.update_cell(i, 9, 'EXPIRED') # Column I
            continue
            
        if status in ['ACTIVE', 'FREE_RIDE'] and ticker:
            try:
                entry_price = float(row.get('Actual Fill') or row.get('Suggested Entry'))
                stop_loss = float(row.get('Stop Loss'))
                shares = int(row.get('Shares'))
                
                # Fetch Current Market Price
                current_price = yf.download(ticker, period="1d", interval="1d", auto_adjust=True)['Close'].iloc[-1]
                current_price = float(current_price)
                
                pnl_dollars = (current_price - entry_price) * shares
                pnl_pct = ((current_price / entry_price) - 1) * 100
                
                new_status = status
                action_note = ""
                
                # --- ACTIVE PHASE LOGIC ---
                if status == 'ACTIVE':
                    target = float(row.get('Target Exit'))
                    if current_price <= stop_loss:
                        new_status = 'CLOSED_LOSS'
                        lockout_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                        wash_sales_sheet.append_row([ticker, lockout_date])
                        wash_sale_alerts.append(f"🛑 **{ticker}**: Wash sale. Locked until {lockout_date}.")
                        ledger.update_cell(i, 9, new_status)
                        
                    elif current_price >= target:
                        new_status = 'FREE_RIDE'
                        new_shares = shares // 2
                        
                        # 1. Move Stop Loss to Break-Even (Col F is 6)
                        ledger.update_cell(i, 6, entry_price) 
                        # 2. Cut Shares in half (Col H is 8)
                        ledger.update_cell(i, 8, new_shares)  
                        # 3. Update Status (Col I is 9)
                        ledger.update_cell(i, 9, new_status)  
                        
                        action_note = "🎯 **TAKE HALF!** Target hit. Stop moved to break-even."
                        pnl_dollars = (current_price - entry_price) * new_shares # Recalculate for remaining
                
                # --- FREE RIDE PHASE LOGIC ---
                elif status == 'FREE_RIDE':
                    if current_price <= stop_loss:
                        new_status = 'CLOSED_WIN' # Stopped out at break-even
                        ledger.update_cell(i, 9, new_status)
                        action_note = "🛡️ **STOPPED OUT** at break-even. Free ride ended."
                    else:
                        action_note = "🌊 **RIDING TREND** risk-free."

                # --- FORMAT DISCORD OUTPUT ---
                icon = "🟢" if pnl_dollars > 0 else "🔴"
                report_line = f"{icon} **{ticker}** ({new_status})\n"
                if action_note:
                    report_line += f"↳ {action_note}\n"
                report_line += f"↳ Entry: ${entry_price:.2f} | Current: ${current_price:.2f}\n"
                report_line += f"↳ Open PnL: **${pnl_dollars:,.2f}** ({pnl_pct:+.2f}%)\n"
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