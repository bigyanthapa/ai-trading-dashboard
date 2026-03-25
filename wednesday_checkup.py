import os
import json
import gspread
import yfinance as yf
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

# --- CONFIGURATION ---
SHEET_NAME = "Swing Trade Ledger"

def get_spreadsheet():
    """Authenticates and returns the Google Spreadsheet."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS environment variable is missing.")
    
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def run_wednesday_checkup():
    """Reads active inventory and calculates mid-week health."""
    try:
        spreadsheet = get_spreadsheet()
        ledger = spreadsheet.worksheet("Ledger")
        records = ledger.get_all_records()
    except Exception as e:
        print(f"Error accessing Google Sheets: {e}")
        return None

    if not records:
        return []

    active_reports = []
    
    # gspread rows are 1-indexed, row 1 is headers. Data starts at row 2.
    for row in records:
        status = str(row.get('Status', '')).strip().upper()
        ticker = row.get('Ticker', '')
        
        # We only care about trades currently in play
        if status in ['ACTIVE', 'FREE_RIDE'] and ticker:
            try:
                # Fallback to Suggested Entry if Actual Fill is somehow blank
                entry_price = float(row.get('Actual Fill') or row.get('Suggested Entry'))
                stop_loss = float(row.get('Stop Loss'))
                target_exit = float(row.get('Target Exit'))
                shares = int(row.get('Shares'))
                
                # Fetch live intraday price
                current_price = float(yf.download(ticker, period="1d", interval="1d", auto_adjust=True)['Close'].iloc[-1])
                
                # Financial Math
                pnl_dollars = (current_price - entry_price) * shares
                pnl_pct = ((current_price / entry_price) - 1) * 100
                
                dist_to_target = target_exit - current_price
                dist_to_stop = current_price - stop_loss
                
                # Contextual Status Logic
                if status == 'FREE_RIDE':
                    health_icon = "🌊"
                    urgency = "Free Ride phase. Risk-free trend riding."
                elif current_price >= target_exit:
                    health_icon = "🎯"
                    urgency = "Target hit! Waiting for Friday Retro to execute."
                elif current_price <= stop_loss:
                    health_icon = "🛑"
                    urgency = "Stop breached! Waiting for Friday Retro to execute."
                elif current_price > entry_price:
                    health_icon = "🟢"
                    urgency = f"On track. ${dist_to_target:.2f} away from target."
                else:
                    health_icon = "🟡"
                    urgency = f"Drawdown. ${dist_to_stop:.2f} away from stop loss."

                # Format the Payload
                report_line = f"{health_icon} **{ticker}** ({status})\n"
                report_line += f"↳ Entry: ${entry_price:.2f} | Current: **${current_price:.2f}** | Target: ${target_exit:.2f}\n"
                report_line += f"↳ Open PnL: **${pnl_dollars:,.2f}** ({pnl_pct:+.2f}%)\n"
                report_line += f"↳ Status: {urgency}\n"
                
                active_reports.append(report_line)
                
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                
    return active_reports

def send_checkup_discord(reports):
    """Fires the formatted report to the Discord Webhook."""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("CRITICAL: No Discord Webhook configured.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="🩺 Mid-Week Portfolio Health Scan", color="3498db")
    embed.set_description("Observational scan of open inventory and trajectory.")

    if not reports:
        embed.add_embed_field(name="Active Inventory", value="No active trades currently in the ledger.", inline=False)
    else:
        embed.add_embed_field(name="Open Positions Status", value="\n\n".join(reports), inline=False)

    embed.set_footer(text=f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CDT")
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Running Wednesday Checkup...")
    reports = run_wednesday_checkup()
    if reports is not None:
        send_checkup_discord(reports)
        print("Mid-week checkup sent to Discord.")