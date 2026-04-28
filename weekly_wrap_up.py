import os
import json
import yfinance as yf
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta


# Top setups to review each week
REVIEW_LIST = {
    "SOFI": {"entry": 18.96, "target_1": 24, "target_2": 30, "catalyst": "April 29 earnings"},
    "IREN": {"entry": 47.93, "target_1": 60, "target_2": 75, "catalyst": "Microsoft $9.7B deal"},
    "RKLB": {"entry": 91.63, "target_1": 105, "target_2": 120, "catalyst": "Neutron rocket Q4 2026"},
    "LUNR": {"entry": 28.98, "target_1": 35, "target_2": 42, "catalyst": "NASA CLPS contracts"},
    "UUUU": {"entry": 37.50, "target_1": 48, "target_2": 58, "catalyst": "Nuclear contracts"},
}

UPCOMING_CATALYSTS = [
    {"date": "April 29", "days_out": 6, "event": "SOFI Q1 2026 Earnings", "impact": "🔴 BINARY"},
    {"date": "May 6", "days_out": 13, "event": "IONQ Q1 2026 Earnings", "impact": "🔴 BINARY"},
    {"date": "May 19", "days_out": 26, "event": "LUNR Q1 2026 Earnings", "impact": "🟡 MEDIUM"},
]

def get_current_price(ticker):
    """Fetch current price"""
    try:
        data = yf.download(ticker, period="1d", interval="1m", auto_adjust=True, progress=False)
        if len(data) > 0:
            price = data['Close'].iloc[-1]
            # Ensure we return a scalar value, not a Series
            return float(price) if price is not None and not pd.isna(price) else None
        return None
    except:
        return None

def calculate_rsi(ticker):
    """Calculate RSI"""
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

def main():
    print("Starting Friday Weekly Wrap-Up Alert...")
    
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK environment variable is missing.")
        return
    
    webhook = DiscordWebhook(url=webhook_url)
    
    # Main embed
    embed = DiscordEmbed(
        title="📊 FRIDAY WEEKLY WRAP-UP & NEXT WEEK PREVIEW",
        description=f"End of Week Review (5:00 PM CST Friday) - {datetime.now().strftime('%B %d, %Y')}",
        color="e74c3c"
    )
    
    # Weekly performance section
    performance_text = """
**POSITIONS RECAP:**

Use this template to fill in your actual trades:
| Ticker | Entry | Current | % Gain | Target 1 | Target 2 | Status |
|--------|-------|---------|--------|----------|----------|--------|
| SOFI   | $18.50 | $[?] | [+X%] | $24 | $30 | [?] |
| IREN   | $46.50 | $[?] | [+X%] | $60 | $75 | [?] |
| RKLB   | $83.00 | $[?] | [+X%] | $105 | $120 | [?] |

**Analysis Questions:**
• Which positions exceeded Target 1? → Take 50% profit
• Which hit stop loss? → Log lesson learned
• Which moved sideways? → Still holding for catalyst
• Did you follow the trading rules?
  ✓ Honor stops (discipline)
  ✓ Take profits at 1:2 R/R
  ✓ Avoid earnings week trades
  ✓ Max 1% risk per trade
"""
    
    embed.add_embed_field(
        name="📈 WEEKLY PERFORMANCE REVIEW",
        value=performance_text,
        inline=False
    )
    
    # Top setups status
    setup_status = ""
    for ticker, setup in REVIEW_LIST.items():
        current = get_current_price(ticker)
        rsi = calculate_rsi(ticker)
        
        if current is not None and not pd.isna(current):
            pnl = ((current - setup["entry"]) / setup["entry"]) * 100
            
            if current >= setup["target_2"]:
                status_emoji = "🟢🟢"
                text = f"HIT TARGET 2"
            elif current >= setup["target_1"]:
                status_emoji = "🟢"
                text = f"HIT TARGET 1"
            elif current >= setup["entry"]:
                status_emoji = "🟡"
                text = f"PROFIT +{pnl:.1f}%"
            else:
                status_emoji = "🔴"
                text = f"LOSS {pnl:.1f}%"
            
            setup_status += f"{status_emoji} **{ticker}**: ${float(current):.2f} ({text}) | RSI: {rsi:.0f if rsi is not None and not pd.isna(rsi) else 'N/A'}\n"
    
    embed.add_embed_field(
        name="🎯 TOP SETUPS THIS WEEK",
        value=setup_status if setup_status else "Update with your actual positions",
        inline=False
    )
    
    # Next week catalysts
    catalysts_text = ""
    for cat in UPCOMING_CATALYSTS:
        catalysts_text += f"{cat['impact']} **{cat['date']}** ({cat['days_out']} days): {cat['event']}\n"
    
    catalysts_text += """

**TRADING IMPLICATIONS:**
🔴 April 29 SOFI: If earnings beat → +26-48% potential
                  If miss → -12% risk
                  → Position size accordingly, reduce if nervous

🔴 May 6 IONQ: Do NOT hold through earnings (binary risk)
              Exit before report if holding

🟡 May 19 LUNR: Skip new entries 2 weeks before
               Currently safe to hold existing positions
"""
    
    embed.add_embed_field(
        name="📅 NEXT WEEK CATALYST CALENDAR",
        value=catalysts_text,
        inline=False
    )
    
    # Next week game plan
    game_plan = """
**🎯 NEXT WEEK PRIORITIES (Ranked):**

1️⃣ **HIGHEST:** SOFI entry @ $17-19 (April 29 earnings)
   • This is a 6-day fuse on +26-58% potential move
   • Risk: Muddy Waters short attack uncertainty
   • Position size: 15-20% of account

2️⃣ **SECOND:** IREN dips to $45-48 (Microsoft deal)
   • $9.7B locked contract = real upside
   • Position size: 15-20% of account
   • Hold 8-16 weeks

3️⃣ **THIRD:** RKLB pullback to $85-88 (already winning)
   • Wait for 8-10% dip from $91.63
   • Only re-enter on that dip
   • Targets: $105 / $120

4️⃣ **AVOID:**
   ❌ IONQ ($48.16) - RSI 85+, May 6 earnings
   ❌ QBTS - Parabolic, expect crash
   ❌ PLTR ($147.44) - Take profits only

5️⃣ **WATCH:** LUNR for $25-27 dip entry
"""
    
    embed.add_embed_field(
        name="🎮 NEXT WEEK GAME PLAN",
        value=game_plan,
        inline=False
    )
    
    # Technical rules reminder
    rules = """
**📌 TRADING RULES TO REINFORCE:**
1. Never chase parabolic moves (IONQ warning)
2. Always honor stops (discipline > being right)
3. Take profits at 1:2 R/R (half position free ride)
4. Wait for pullbacks in strong uptrends (patience)
5. Respect earnings blackouts (1 week before/after)
6. Sector limits: Max 3 positions per sector
7. Max risk: 1% of account per trade

**✅ 3-STEP DAILY PROCESS:**
→ 8:00 AM: Pre-market scan
→ 9:30 AM: Entry check (confirm pullback/support)
→ 2:00 PM: Profit management (adjust stops, take profits)

If ANY step is skipped, results suffer. Stay disciplined!
"""
    
    embed.add_embed_field(
        name="📋 RULES & PROCESS",
        value=rules,
        inline=False
    )
    
    embed.set_footer(text="See you Monday 8:00 AM for next week's scan! Remember: Discipline = Profits")
    
    webhook.add_embed(embed)
    webhook.execute()
    
    print("✅ Friday wrap-up alert sent to Discord!")

if __name__ == "__main__":
    main()
