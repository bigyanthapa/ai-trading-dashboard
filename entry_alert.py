import os
import json
import yfinance as yf
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime


# Top 5 priority entries with exact trigger levels
TOP_5_ENTRIES = {
    "SOFI": {
        "current_price": 18.96,
        "entry_zone": "17-19",
        "buy_trigger": 18.50,
        "target_1": 24,
        "target_2": 30,
        "stop_loss": 16,
        "conviction": "⭐⭐⭐⭐⭐",
        "catalyst": "April 29 earnings (6 DAYS)",
        "upside": "+26% to +58%",
        "status": "🟢 READY TO ENTER"
    },
    "IREN": {
        "current_price": 47.93,
        "entry_zone": "45-48",
        "buy_trigger": 46.50,
        "target_1": 60,
        "target_2": 75,
        "stop_loss": 41,
        "conviction": "⭐⭐⭐⭐⭐",
        "catalyst": "$9.7B Microsoft GPU deal",
        "upside": "+25% to +56%",
        "status": "🟢 READY TO ENTER"
    },
    "RKLB": {
        "current_price": 91.63,
        "entry_zone": "85-88",
        "buy_trigger": 87.50,
        "target_1": 105,
        "target_2": 120,
        "stop_loss": 82,
        "conviction": "⭐⭐⭐⭐",
        "catalyst": "Neutron rocket Q4 2026",
        "upside": "+20% to +36%",
        "status": "🟡 WAIT FOR DIP (RSI overbought)"
    },
    "LUNR": {
        "current_price": 28.98,
        "entry_zone": "25-27",
        "buy_trigger": 26.50,
        "target_1": 35,
        "target_2": 42,
        "stop_loss": 23,
        "conviction": "⭐⭐⭐",
        "catalyst": "Lunar cargo boom",
        "upside": "+21% to +45%",
        "status": "🟡 AT RESISTANCE (wait for dip)"
    },
    "UUUU": {
        "current_price": None,  # Will fetch live
        "entry_zone": "36-38",
        "buy_trigger": 37.50,
        "target_1": 48,
        "target_2": 58,
        "stop_loss": 33,
        "conviction": "⭐⭐⭐⭐⭐",
        "catalyst": "Nuclear renaissance + uranium contracts",
        "upside": "+26% to +52%",
        "status": "🟢 MONITOR FOR ENTRY"
    }
}

AVOID_LIST = {
    "IONQ": {
        "current_price": 48.16,
        "problem": "RSI 85+ (OVERBOUGHT), April +60.5%",
        "earnings": "May 6 (binary risk)",
        "action": "🚨 DO NOT CHASE - Wait for $35-40 crash"
    },
    "QBTS": {
        "problem": "Parabolic 3,670% gain in 12 months",
        "issue": "About to correct 40-50%",
        "action": "🚨 STAY OUT - Will get better entry"
    },
    "PLTR": {
        "current_price": 147.44,
        "problem": "Nearly DOUBLED from estimates",
        "issue": "Way too extended",
        "action": "⚠️ TAKE PROFITS ONLY - Don't chase"
    }
}

def get_current_price(ticker):
    """Fetch current stock price"""
    try:
        data = yf.download(ticker, period="1d", interval="1m", auto_adjust=True, progress=False)
        if len(data) > 0:
            return data['Close'].iloc[-1]
        return None
    except:
        return None

def calculate_rsi(series, period=14):
    """Calculate RSI"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def get_rsi_status(ticker):
    """Get RSI and determine health"""
    try:
        data = yf.download(ticker, period="100d", interval="1d", auto_adjust=True, progress=False)
        if len(data) < 14:
            return None
        rsi = calculate_rsi(data['Close']).iloc[-1]
        return rsi
    except:
        return None

def main():
    print("Starting Entry Alert Check (9:30 AM)...")
    
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK environment variable is missing.")
        return
    
    webhook = DiscordWebhook(url=webhook_url)
    
    # Main embed
    embed = DiscordEmbed(
        title="📍 MID-MORNING ENTRY ALERT CHECK",
        description=f"After Market Settles (9:30 AM CST) - {datetime.now().strftime('%I:%M %p')}",
        color="f39c12"
    )
    
    # Top 5 Priority Entries
    entry_text = ""
    for ticker, setup in list(TOP_5_ENTRIES.items())[:5]:
        
        # Fetch live price if not set
        if setup["current_price"] is None:
            setup["current_price"] = get_current_price(ticker)
        
        # Handle case where price couldn't be fetched
        if setup["current_price"] is None:
            continue
        
        rsi = get_rsi_status(ticker)
        rsi_text = f"(RSI: {rsi:.0f})" if rsi is not None and not pd.isna(rsi) else ""
        
        entry_text += f"""
{setup['conviction']} **{ticker}** {setup['status']}
├─ Price: ${float(setup['current_price']):.2f} {rsi_text}
├─ Entry: ${setup['entry_zone']} | Buy Trigger: ${setup['buy_trigger']:.2f}
├─ Stop: ${setup['stop_loss']} | Targets: ${setup['target_1']} / ${setup['target_2']}
├─ R/R: 1:{(setup['target_1']-setup['buy_trigger'])/(setup['buy_trigger']-setup['stop_loss']):.1f}
├─ Catalyst: {setup['catalyst']}
└─ Upside: {setup['upside']}
"""
    
    embed.add_embed_field(
        name="🎯 TOP 5 PRIORITY ENTRIES",
        value=entry_text if entry_text else "Unable to fetch data",
        inline=False
    )
    
    # Avoid list
    avoid_text = ""
    for ticker, info in AVOID_LIST.items():
        avoid_text += f"**{ticker}**: {info['action']}\n"
    
    embed.add_embed_field(
        name="🚨 AVOID (Overbought/Parabolic)",
        value=avoid_text,
        inline=False
    )
    
    # Action triggers
    action_triggers = """
✅ **BUY IF:**
• SPY + stock both confirming bullish → ENTER full size
• SPY weak but stock holding support → ENTER half size
• Volume declining on dips → ACCUMULATION (keep buying)

❌ **SKIP IF:**
• SPY weak + stock not following → WAIT for confirmation
• Volume spiking on dips → PANIC SELLING (could be trap)
• Earnings within 1 week → TOO MUCH BINARY RISK
"""
    
    embed.add_embed_field(
        name="⚡ ACTION TRIGGERS",
        value=action_triggers,
        inline=False
    )
    
    embed.set_footer(text="Next check: 2:00 PM (Position Management) | Next week: Friday 5:00 PM (Weekly Review)")
    
    webhook.add_embed(embed)
    webhook.execute()
    
    print("✅ Entry alert sent to Discord!")

if __name__ == "__main__":
    main()
