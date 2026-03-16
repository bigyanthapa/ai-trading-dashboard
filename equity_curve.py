import os
import json
import gspread
import pandas as pd
import matplotlib.pyplot as plt
from oauth2client.service_account import ServiceAccountCredentials
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = "Swing Trade Ledger"
INITIAL_CAPITAL = 27000

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

def calculate_equity_curve():
    """Parses the ledger, calculates realized PnL, and generates a chart."""
    spreadsheet = get_spreadsheet()
    ledger = spreadsheet.worksheet("Ledger")
    records = ledger.get_all_records()
    
    if not records:
        print("No records found.")
        return None

    trade_data = []
    
    # 1. Reconstruct Realized PnL from the Ledger
    for row in records:
        status = str(row.get('Status', '')).strip().upper()
        
        # We only plot trades that have realized a gain or loss
        if status in ['CLOSED_LOSS', 'CLOSED_WIN', 'FREE_RIDE']:
            date_str = row.get('Date')
            entry = float(row.get('Actual Fill') or row.get('Suggested Entry'))
            stop = float(row.get('Stop Loss'))
            target = float(row.get('Target Exit'))
            shares = int(row.get('Shares'))
            
            pnl = 0
            if status == 'CLOSED_LOSS':
                # Full loss calculated from entry to stop
                pnl = (stop - entry) * shares
            elif status in ['FREE_RIDE', 'CLOSED_WIN']:
                # If it hit FREE_RIDE, we booked half the original position at the Target Exit.
                # Since the Friday script halves the 'Shares' cell when it hits FREE_RIDE, 
                # the current 'shares' value is exactly the amount we sold at the target.
                pnl = (target - entry) * shares
                
            trade_data.append({'Date': date_str, 'PnL': pnl, 'Ticker': row.get('Ticker')})

    if not trade_data:
        print("No completed trades to plot yet.")
        return None

    # 2. Build the Time Series
    df = pd.DataFrame(trade_data)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    df['Cumulative_PnL'] = df['PnL'].cumsum()
    df['Equity'] = INITIAL_CAPITAL + df['Cumulative_PnL']

    # 3. Generate the Chart (Dark Mode)
    plt.figure(figsize=(10, 6))
    plt.plot(df['Date'], df['Equity'], marker='o', linestyle='-', color='#2ecc71', linewidth=2, markersize=6)
    plt.title('Portfolio Equity Curve', fontsize=16, fontweight='bold', color='white', pad=15)
    plt.xlabel('Trade Entry Date', fontsize=12, color='white')
    plt.ylabel('Account Balance ($)', fontsize=12, color='white')
    plt.grid(True, linestyle='--', alpha=0.2, color='white')
    
    # Institutional Styling
    ax = plt.gca()
    ax.set_facecolor('#1e1e1e')
    plt.gcf().patch.set_facecolor('#1e1e1e')
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#444444')

    # 4. Save to Disk
    file_path = "equity_curve.png"
    plt.savefig(file_path, bbox_inches='tight', facecolor=plt.gcf().get_facecolor())
    plt.close()
    
    current_equity = df['Equity'].iloc[-1]
    return file_path, current_equity

def send_chart_to_discord(file_path, current_equity):
    """Uploads the generated image directly to Discord."""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("CRITICAL: Webhook missing.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="📈 Portfolio Growth Report", color="2ecc71")
    
    roi = ((current_equity / INITIAL_CAPITAL) - 1) * 100
    
    embed.add_embed_field(name="Account Balance", value=f"**${current_equity:,.2f}**", inline=True)
    embed.add_embed_field(name="Total ROI", value=f"**{roi:+.2f}%**", inline=True)
    embed.set_footer(text=f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    
    # Attach the image file
    with open(file_path, "rb") as f:
        webhook.add_file(file=f.read(), filename="equity.png")
    
    # Link the attachment to the embed
    embed.set_image(url="attachment://equity.png")
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    print("Generating Equity Curve...")
    result = calculate_equity_curve()
    if result:
        file_path, current_equity = result
        print("Sending to Discord...")
        send_chart_to_discord(file_path, current_equity)
        print("Equity curve workflow complete.")