import os
import json
import yfinance as yf
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime


# Sample positions (you'll update these based on actual trades)
SAMPLE_POSITIONS = {
    "RKLB": {
        "entry": 83.00,
        "current": 91.63,
        "target_1": 105,
        "target_2": 120,
        "stop_loss": 78,
        "status": "WINNING",
    },
    "IREN": {
        "entry": 46.50,
        "current": 47.93,
        "target_1": 60,
        "target_2": 75,
        "stop_loss": 41,
        "status": "BUILDING",
    },
    "SOFI": {
        "entry": 18.50,
        "current": 18.96,
        "target_1": 24,
        "target_2": 30,
        "stop_loss": 16,
        "status": "EARLY",
    },
}

def calculate_rsi(ticker):
    """Calculate RSI for position management"""
    try:
        data = yf.download(ticker, period="100d", interval="1d", auto_adjust=True, progress=False)
        if len(data) < 14:
            return None
        
        delta = data['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return None

def get_current_price(ticker):
    """Fetch current price"""
    try:
        data = yf.download(ticker, period="1d", interval="1m", auto_adjust=True, progress=False)
        if len(data) > 0:
            return data['Close'].iloc[-1]
        return None
    except:
        return None

def analyze_position(ticker, entry, current, target_1, target_2, stop_loss):
    """Analyze position and provide action"""
    
    # Calculate metrics
    pnl_pct = ((current - entry) / entry) * 100
    risk_per_share = entry - stop_loss
    reward_to_target1 = target_1 - entry
    reward_to_target2 = target_2 - entry
    rr_ratio_t1 = reward_to_target1 / risk_per_share if risk_per_share > 0 else 0
    rr_ratio_t2 = reward_to_target2 / risk_per_share if risk_per_share > 0 else 0
    
    # Get RSI
    rsi = calculate_rsi(ticker)
    
    # Determine action
    if current >= target_1 and current < target_2:
        action = f"🟢 HIT TARGET 1 - BOOK 50% PROFIT at ${target_1:.2f}"
        action += f"\n└─ Move stop to breakeven (${entry:.2f})"
        color = "28a745"
    elif current >= target_2:
        action = f"🟢🟢 HIT TARGET 2 - BOOK REMAINING PROFIT at ${target_2:.2f}"
        action += f"\n└─ Close full position, lock in gains"
        color = "1abc9c"
    elif rsi is not None and rsi > 75:
        action = f"🟡 TIGHTEN STOPS - RSI {rsi:.0f} (overbought)"
        action += f"\n└─ Move stop to ${entry + (risk_per_share * 0.5):.2f} (lock in half profit)"
        color = "f39c12"
    elif rsi is not None and rsi > 65:
        action = f"🟢 TRAIL STOP - RSI {rsi:.0f} (strong)"
        action += f"\n└─ Move stop to breakeven + 2% (${entry * 1.02:.2f})"
        color = "3498db"
    elif rsi is not None and rsi < 30:
        action = f"🟢 ADD TO POSITION - RSI {rsi:.0f} (oversold)"
        action += f"\n└─ Buy dip if support holding"
        color = "e74c3c"
    else:
        action = f"🟢 HOLD FULL POSITION - RSI {rsi:.0f if rsi is not None else 'N/A'}"
        action += f"\n└─ Wait for Target 1 at ${target_1:.2f}"
        color = "3498db"
    
    return {
        "pnl_pct": pnl_pct,
        "rsi": rsi,
        "rr_t1": rr_ratio_t1,
        "rr_t2": rr_ratio_t2,
        "action": action,
        "color": color
    }

def main():
    print("Starting Position Management Alert (2:00 PM)...")
    
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK environment variable is missing.")
        return
    
    webhook = DiscordWebhook(url=webhook_url)
    
    # Main embed
    embed = DiscordEmbed(
        title="💰 POSITION MANAGEMENT & PROFIT-TAKING",
        description=f"Afternoon Review (2:00 PM CST) - {datetime.now().strftime('%I:%M %p')}",
        color="9b59b6"
    )
    
    # Position reviews
    positions_text = ""
    for ticker, position in SAMPLE_POSITIONS.items():
        current = get_current_price(ticker)
        if current is None:
            current = position["current"]
        
        analysis = analyze_position(
            ticker,
            position["entry"],
            current,
            position["target_1"],
            position["target_2"],
            position["stop_loss"]
        )
        
        positions_text += f"""
**{ticker}** | Entry: ${position['entry']:.2f} | Current: ${current:.2f}
├─ P&L: {analysis['pnl_pct']:+.1f}% | RSI: {analysis['rsi']:.0f if analysis['rsi'] else 'N/A'}
├─ R/R to T1: 1:{analysis['rr_t1']:.1f} | R/R to T2: 1:{analysis['rr_t2']:.1f}
├─ Stop Loss: ${position['stop_loss']:.2f} | Targets: ${position['target_1']:.2f} / ${position['target_2']:.2f}
└─ {analysis['action']}
"""
    
    embed.add_embed_field(
        name="📊 OPEN POSITIONS",
        value=positions_text if positions_text else "No active positions",
        inline=False
    )
    
    # Free ride rules
    free_ride = """
**FREE RIDE RULES** (Your 1:2 R/R System):

When position hits Target 1 (1:2 R/R):
1. ✅ Book 50% profit at Target 1 price
2. ✅ Move stop loss to breakeven
3. ✅ Let remaining 50% ride to Target 2 (risk-free)

**Example:**
• Bought SOFI @ $18.50
• Target 1: $24 (1:2 R/R reached)
→ Sell 50% of position at $24
→ Move stop to $18.50 (locked breakeven)
→ Let 50% ride for Target 2 at $30

This ensures you NEVER lose money on winning trades.
"""
    
    embed.add_embed_field(
        name="🎁 FREE RIDE PROFIT LOCKS",
        value=free_ride,
        inline=False
    )
    
    # Stop loss triggers
    stop_triggers = """
**EXIT IMMEDIATELY IF:**
✋ Price breaks below support on HIGH VOLUME
✋ Earnings miss announced (don't fight it)
✋ Sector weakness from negative news
✋ Stop loss hit (honor the discipline)

**Don't Hope, Just Execute.**
"""
    
    embed.add_embed_field(
        name="⚠️ STOP LOSS TRIGGERS",
        value=stop_triggers,
        inline=False
    )
    
    # Earnings risk management
    earnings_risk = """
**⏰ UPCOMING EARNINGS (Avoid if within 1 week):**
🗓️ April 29: SOFI Q1 earnings (6 DAYS)
   → If holding: Size down or exit before
   → If entering: Wait until after report

🗓️ May 6: IONQ Q1 earnings (13 DAYS)
   → Do NOT hold through earnings (binary risk)

🗓️ May 19: LUNR earnings (26 DAYS)
   → Skip new entries 2 weeks before
"""
    
    embed.add_embed_field(
        name="📅 EARNINGS RISK MANAGEMENT",
        value=earnings_risk,
        inline=False
    )
    
    embed.set_footer(text="Next check: Friday 5:00 PM (Weekly Review) | Position updates needed? Adjust above data")
    
    webhook.add_embed(embed)
    webhook.execute()
    
    print("✅ Position management alert sent to Discord!")

if __name__ == "__main__":
    main()
