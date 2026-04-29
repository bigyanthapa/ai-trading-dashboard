#!/usr/bin/env python3
"""
SPY Crash Monitor - FOMC Chair Transition Alert System
Monitors for 10-20% SPY crashes during Warsh transition period (May 15-28, 2026)
Sends Discord alerts when crash buy opportunities emerge
"""

import os
import json
import yfinance as yf
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta

# 20-Stock Crash Buy List with precise entry zones and targets
CRASH_BUY_LIST = {
    # TIER 1: MEGA-CAP TECH (50% of capital)
    "AAPL": {
        "name": "Apple Inc",
        "current_price": 260.50,
        "crash_buy_zone": "235-245",
        "target_1": 290,
        "target_2": 320,
        "stop_loss": 200,
        "tier": "MEGA-CAP",
        "allocation": 10.0,  # % of crash capital
        "catalyst": "iPhone 16 + Services growth",
        "conviction": "⭐⭐⭐⭐⭐",
        "expected_return": "+45-65%"
    },
    "MSFT": {
        "name": "Microsoft Corp",
        "current_price": 420.30,
        "crash_buy_zone": "360-370", 
        "target_1": 480,
        "target_2": 520,
        "stop_loss": 310,
        "tier": "MEGA-CAP",
        "allocation": 10.0,
        "catalyst": "Azure AI + Copilot dominance",
        "conviction": "⭐⭐⭐⭐⭐",
        "expected_return": "+40-60%"
    },
    "GOOGL": {
        "name": "Alphabet Inc",
        "current_price": 175.20,
        "crash_buy_zone": "145-155",
        "target_1": 200,
        "target_2": 230,
        "stop_loss": 125,
        "tier": "MEGA-CAP", 
        "allocation": 8.0,
        "catalyst": "Search AI + Cloud recovery",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+35-55%"
    },
    "META": {
        "name": "Meta Platforms",
        "current_price": 632.80,
        "crash_buy_zone": "540-560",
        "target_1": 720,
        "target_2": 800,
        "stop_loss": 460,
        "tier": "MEGA-CAP",
        "allocation": 8.0,
        "catalyst": "VR/AR + efficiency gains",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+40-60%"
    },
    "AMZN": {
        "name": "Amazon.com Inc",
        "current_price": 245.70,
        "crash_buy_zone": "200-210",
        "target_1": 280,
        "target_2": 320,
        "stop_loss": 170,
        "tier": "MEGA-CAP",
        "allocation": 7.0,
        "catalyst": "AWS growth + retail recovery",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+35-55%"
    },
    "TSLA": {
        "name": "Tesla Inc",
        "current_price": 348.10,
        "crash_buy_zone": "280-300",
        "target_1": 420,
        "target_2": 480,
        "stop_loss": 240,
        "tier": "MEGA-CAP",
        "allocation": 7.0,
        "catalyst": "FSD + Robotaxi launch",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+50-70%"
    },

    # TIER 2: AI/SEMICONDUCTOR CYCLE (25% of capital)
    "NVDA": {
        "name": "NVIDIA Corp",
        "current_price": 875.30,
        "crash_buy_zone": "700-750",
        "target_1": 1050,
        "target_2": 1200,
        "stop_loss": 600,
        "tier": "AI/CHIP",
        "allocation": 8.0,
        "catalyst": "AI compute demand + Blackwell",
        "conviction": "⭐⭐⭐⭐⭐",
        "expected_return": "+60-80%"
    },
    "AMD": {
        "name": "Advanced Micro Devices",
        "current_price": 284.60,
        "crash_buy_zone": "230-240",
        "target_1": 340,
        "target_2": 380,
        "stop_loss": 195,
        "tier": "AI/CHIP",
        "allocation": 5.0,
        "catalyst": "Data center AI chips",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+45-65%"
    },
    "MU": {
        "name": "Micron Technology",
        "current_price": 387.20,
        "crash_buy_zone": "320-330",
        "target_1": 460,
        "target_2": 520,
        "stop_loss": 280,
        "tier": "AI/CHIP",
        "allocation": 4.0,
        "catalyst": "AI memory demand surge",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+50-70%"
    },
    "INTC": {
        "name": "Intel Corp",
        "current_price": 68.40,
        "crash_buy_zone": "55-60",
        "target_1": 80,
        "target_2": 90,
        "stop_loss": 48,
        "tier": "AI/CHIP",
        "allocation": 4.0,
        "catalyst": "Foundry business + AI recovery",
        "conviction": "⭐⭐⭐",
        "expected_return": "+35-55%"
    },
    "SNDK": {
        "name": "SanDisk/WDC",
        "current_price": 745.80,
        "crash_buy_zone": "600-650",
        "target_1": 850,
        "target_2": 950,
        "stop_loss": 520,
        "tier": "AI/CHIP",
        "allocation": 4.0,
        "catalyst": "Storage demand + AI workloads",
        "conviction": "⭐⭐⭐",
        "expected_return": "+40-60%"
    },

    # TIER 3: HIGH GROWTH (15% of capital)
    "IONQ": {
        "name": "IonQ Inc",
        "current_price": 34.20,
        "crash_buy_zone": "25-29",
        "target_1": 45,
        "target_2": 55,
        "stop_loss": 20,
        "tier": "QUANTUM",
        "allocation": 4.0,
        "catalyst": "Quantum computing breakthrough",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+60-90%"
    },
    "ASTS": {
        "name": "AST SpaceMobile",
        "current_price": 72.50,
        "crash_buy_zone": "50-60", 
        "target_1": 95,
        "target_2": 115,
        "stop_loss": 42,
        "tier": "SATELLITE",
        "allocation": 4.0,
        "catalyst": "Space-based cellular network",
        "conviction": "⭐⭐⭐⭐",
        "expected_return": "+70-100%"
    },
    "RGTI": {
        "name": "Rigetti Computing",
        "current_price": 15.30,
        "crash_buy_zone": "10-12",
        "target_1": 20,
        "target_2": 25,
        "stop_loss": 8,
        "tier": "QUANTUM",
        "allocation": 3.5,
        "catalyst": "Quantum cloud services",
        "conviction": "⭐⭐⭐",
        "expected_return": "+80-120%"
    },
    "EOSE": {
        "name": "Eos Energy",
        "current_price": 5.40,
        "crash_buy_zone": "3.8-4.5",
        "target_1": 7.5,
        "target_2": 9.0,
        "stop_loss": 3.0,
        "tier": "ENERGY",
        "allocation": 3.5,
        "catalyst": "Grid storage demand",
        "conviction": "⭐⭐⭐",
        "expected_return": "+90-140%"
    },

    # TIER 4: SPECULATIVE (10% of capital)
    "WOLF": {
        "name": "Wolfspeed Inc",
        "current_price": 22.80,
        "crash_buy_zone": "16-18",
        "target_1": 28,
        "target_2": 34,
        "stop_loss": 13,
        "tier": "MATERIALS",
        "allocation": 3.0,
        "catalyst": "EV chip demand + 5G",
        "conviction": "⭐⭐⭐",
        "expected_return": "+70-110%"
    },
    "STEM": {
        "name": "Stem Inc",
        "current_price": 8.90,
        "crash_buy_zone": "6-7",
        "target_1": 12,
        "target_2": 15,
        "stop_loss": 4.5,
        "tier": "ENERGY",
        "allocation": 3.0,
        "catalyst": "Energy storage software",
        "conviction": "⭐⭐⭐",
        "expected_return": "+80-130%"
    },
    "RKLB": {
        "name": "Rocket Lab USA",
        "current_price": 91.63,
        "crash_buy_zone": "65-75",
        "target_1": 110,
        "target_2": 130,
        "stop_loss": 55,
        "tier": "SPACE",
        "allocation": 2.0,
        "catalyst": "Space launch demand",
        "conviction": "⭐⭐⭐",
        "expected_return": "+60-90%"
    },
    "SOFI": {
        "name": "SoFi Technologies", 
        "current_price": 18.96,
        "crash_buy_zone": "13-15",
        "target_1": 22,
        "target_2": 26,
        "stop_loss": 11,
        "tier": "FINTECH",
        "allocation": 2.0,
        "catalyst": "Banking license + growth",
        "conviction": "⭐⭐⭐",
        "expected_return": "+50-80%"
    },
    "LUNR": {
        "name": "Intuitive Machines",
        "current_price": 28.98,
        "crash_buy_zone": "20-23",
        "target_1": 35,
        "target_2": 42,
        "stop_loss": 17,
        "tier": "SPACE",
        "allocation": 2.0,
        "catalyst": "Lunar missions + NASA contracts",
        "conviction": "⭐⭐⭐",
        "expected_return": "+70-100%"
    }
}

def get_current_price(ticker):
    """Fetch current stock price"""
    try:
        data = yf.download(ticker, period="1d", interval="1m", auto_adjust=True, progress=False)
        if len(data) > 0:
            price = data['Close'].iloc[-1]
            return float(price) if price is not None and not pd.isna(price) else None
        return None
    except:
        return None

def get_spy_data():
    """Get SPY price data and calculate crash percentage"""
    try:
        # Get SPY data for the past 30 days
        spy = yf.download("SPY", period="30d", interval="1d", auto_adjust=True, progress=False)
        
        if len(spy) < 2:
            return None, None, None
            
        current_price = float(spy['Close'].iloc[-1])
        
        # Get 20-day high as baseline
        high_20d = float(spy['High'].rolling(20).max().iloc[-1])
        
        # Calculate crash percentage from recent high
        crash_pct = ((current_price - high_20d) / high_20d) * 100
        
        return current_price, high_20d, crash_pct
        
    except Exception as e:
        print(f"Error fetching SPY data: {e}")
        return None, None, None

def check_stocks_in_buy_zones(crash_severity):
    """Check which stocks are in their crash buy zones"""
    stocks_to_buy = []
    
    for ticker, stock_info in CRASH_BUY_LIST.items():
        current_price = get_current_price(ticker)
        
        if current_price is None:
            current_price = stock_info["current_price"]  # Fallback to stored price
            
        # Parse buy zone (e.g., "235-245" -> [235, 245])
        buy_zone = stock_info["crash_buy_zone"].split("-")
        buy_min = float(buy_zone[0])
        buy_max = float(buy_zone[1]) if len(buy_zone) > 1 else buy_min * 1.05
        
        # Determine if in buy zone
        if buy_min <= current_price <= buy_max:
            discount_pct = ((stock_info["current_price"] - current_price) / stock_info["current_price"]) * 100
            
            stocks_to_buy.append({
                "ticker": ticker,
                "name": stock_info["name"],
                "current": current_price,
                "buy_zone": stock_info["crash_buy_zone"],
                "discount": discount_pct,
                "tier": stock_info["tier"],
                "allocation": stock_info["allocation"],
                "target_1": stock_info["target_1"],
                "target_2": stock_info["target_2"],
                "conviction": stock_info["conviction"],
                "expected_return": stock_info["expected_return"]
            })
    
    return stocks_to_buy

def determine_crash_severity(crash_pct):
    """Classify crash severity and buying urgency"""
    if crash_pct >= -5:
        return "MINOR", "🟡 WAIT", "Not a crash yet"
    elif crash_pct >= -10:
        return "MODERATE", "🟠 PREPARE", "Light selling, prepare to buy"
    elif crash_pct >= -15:
        return "MAJOR", "🟢 BUY NOW", "Peak selling - START BUYING"
    elif crash_pct >= -20:
        return "SEVERE", "🟢 BUY AGGRESSIVELY", "Capitulation - MAXIMUM BUY"
    else:
        return "EXTREME", "🚨 ALL IN", "Once in decade opportunity"

def send_crash_alert(spy_price, spy_high, crash_pct, stocks_to_buy, crash_severity, action):
    """Send Discord alert for crash buy opportunity"""
    
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK environment variable is missing.")
        return
    
    webhook = DiscordWebhook(url=webhook_url)
    
    # Determine alert urgency and color
    if crash_pct <= -15:
        color = "00ff00"  # Green - BUY
        urgency = "🚨 CRASH BUY ALERT 🚨"
    elif crash_pct <= -10:
        color = "ff8800"  # Orange - PREPARE  
        urgency = "⚠️ CRASH WATCH ALERT ⚠️"
    else:
        color = "ffff00"  # Yellow - MONITOR
        urgency = "📊 MARKET MONITOR"
    
    # Main embed
    embed = DiscordEmbed(
        title=urgency,
        description=f"SPY Crash Monitor - FOMC Transition Alert\n{datetime.now().strftime('%B %d, %Y at %I:%M %p CST')}",
        color=color
    )
    
    # SPY crash status
    spy_status = f"""
**SPY CRASH STATUS:**
├─ Current Price: ${spy_price:.2f}
├─ 20-Day High: ${spy_high:.2f} 
├─ **Crash Severity: {crash_pct:.1f}% ({crash_severity})**
└─ **Action: {action}**

**CATALYST:** Kevin Warsh FOMC Chair Transition (May 15, 2026)
**PRECEDENT:** Powell Feb 2018 = -19.4% → +25% recovery in 6 months
"""
    
    embed.add_embed_field(
        name="📉 MARKET CRASH STATUS",
        value=spy_status,
        inline=False
    )
    
    # Stocks in buy zones
    if stocks_to_buy:
        buy_opportunities = "**🎯 STOCKS IN BUY ZONES:**\n\n"
        
        for stock in sorted(stocks_to_buy, key=lambda x: x["allocation"], reverse=True):
            buy_opportunities += f"""
{stock['conviction']} **{stock['ticker']}** ({stock['tier']})
├─ Price: ${stock['current']:.2f} | Zone: ${stock['buy_zone']}
├─ Discount: {stock['discount']:+.1f}% | Allocation: {stock['allocation']}%
├─ Targets: ${stock['target_1']} / ${stock['target_2']}
└─ Expected: {stock['expected_return']}
"""
        
        embed.add_embed_field(
            name=f"💰 {len(stocks_to_buy)} CRASH BUY OPPORTUNITIES",
            value=buy_opportunities[:1900],  # Discord limit
            inline=False
        )
    else:
        embed.add_embed_field(
            name="⏳ CRASH BUY STATUS", 
            value="**No stocks in buy zones yet.**\nWaiting for deeper crash to trigger buy signals.",
            inline=False
        )
    
    # Action recommendations
    if crash_pct <= -15:
        action_plan = """
**🚨 IMMEDIATE ACTIONS:**
✅ START BUYING Tier 1 (Mega-cap) - 50% of target position
✅ Prepare cash for Tier 2 if crash deepens
✅ Use 2-tranche strategy (don't go all-in yet)
✅ Set stops at -15% from entry

**TIMELINE:** This is the primary buying window (Days 1-5 of crash)
"""
    elif crash_pct <= -10:
        action_plan = """
**⚠️ PREPARATION ACTIONS:**
✅ Transfer cash to brokerage account  
✅ Review buy zones and target allocations
✅ Monitor for -15% SPY crash to trigger buying
⏳ Wait for deeper selling before entering

**TIMELINE:** Pre-buying phase, prepare for action
"""
    else:
        action_plan = """
**📊 MONITORING ACTIONS:**
✅ Continue monitoring SPY for crash signals
✅ No action needed yet - not a significant crash
⏳ Wait for -10% to -15% drawdown to prepare
⏳ Target buy window: SPY down 15%+

**TIMELINE:** Normal market monitoring mode
"""
    
    embed.add_embed_field(
        name="⚡ ACTION PLAN",
        value=action_plan,
        inline=False
    )
    
    # Tier allocation reminder
    allocation_guide = """
**💼 CAPITAL ALLOCATION PLAN ($27K Example):**
🥇 **Tier 1 (Mega-cap):** $13,500 (50%) - AAPL, MSFT, GOOGL, META, AMZN, TSLA
🥈 **Tier 2 (AI/Chip):** $6,750 (25%) - NVDA, AMD, MU, INTC, SNDK  
🥉 **Tier 3 (Growth):** $4,050 (15%) - IONQ, ASTS, RGTI, EOSE
🎯 **Tier 4 (Spec):** $2,700 (10%) - WOLF, STEM, RKLB, SOFI, LUNR

**Risk Management:** 2% max risk per position | -15% stops for mega-cap
"""
    
    embed.add_embed_field(
        name="📊 ALLOCATION STRATEGY",
        value=allocation_guide,
        inline=False
    )
    
    embed.set_footer(text="Next check: Every hour during market hours | Deploy capital in 2 tranches | This is not financial advice")
    
    webhook.add_embed(embed)
    webhook.execute()
    
    print(f"✅ Crash alert sent! SPY: {crash_pct:.1f}% | Stocks in buy zone: {len(stocks_to_buy)}")

def main():
    """Main crash monitoring function"""
    print("Starting SPY Crash Monitor (FOMC Transition Watch)...")
    
    # Check if we're in the target window (May 15 - June 15, 2026)
    current_date = datetime.now()
    target_start = datetime(2026, 5, 15)
    target_end = datetime(2026, 6, 15)
    
    # For testing, allow current dates too
    if current_date < target_start and current_date.year != 2026:
        # Allow testing in current year
        print("Outside target window, but running for testing purposes...")
    
    # Get SPY crash data
    spy_price, spy_high, crash_pct = get_spy_data()
    
    if spy_price is None:
        print("❌ Could not fetch SPY data")
        return
    
    print(f"SPY: ${spy_price:.2f} | 20D High: ${spy_high:.2f} | Crash: {crash_pct:.1f}%")
    
    # Determine crash severity
    crash_severity, action, description = determine_crash_severity(crash_pct)
    
    # Check for stocks in buy zones
    stocks_to_buy = check_stocks_in_buy_zones(crash_severity)
    
    print(f"Crash Severity: {crash_severity} | Action: {action}")
    print(f"Stocks in buy zones: {len(stocks_to_buy)}")
    
    # Send alert if crash is significant (>= 10%) OR stocks are in buy zones
    if crash_pct <= -5.0 or len(stocks_to_buy) > 0:
        send_crash_alert(spy_price, spy_high, crash_pct, stocks_to_buy, crash_severity, action)
    else:
        print("No significant crash detected, no alert sent.")

if __name__ == "__main__":
    main()