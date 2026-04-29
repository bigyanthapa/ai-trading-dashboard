#!/usr/bin/env python3
"""
Crash Position Management - Track SPY Crash Buy Positions
Monitors positions entered during the May 2026 FOMC transition crash
Provides real-time P&L, target distances, and profit-taking recommendations
"""

import os
import json
import yfinance as yf
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta

# SAMPLE CRASH POSITIONS - Update with your actual entries
CRASH_POSITIONS = {
    # Tier 1: Mega-cap positions (entered during crash)
    "AAPL": {
        "entry_price": 240.50,
        "entry_date": "2026-05-16",
        "shares": 56,  # ~$13,500 position
        "target_1": 290,
        "target_2": 320,
        "stop_loss": 204,  # -15% stop
        "tier": "MEGA-CAP",
        "tranche": 1,  # First tranche (of 2)
        "expected_return": "+45-65%",
        "conviction": "⭐⭐⭐⭐⭐"
    },
    "MSFT": {
        "entry_price": 365.00,
        "entry_date": "2026-05-16", 
        "shares": 37,  # ~$13,500 position
        "target_1": 480,
        "target_2": 520,
        "stop_loss": 310,  # -15% stop
        "tier": "MEGA-CAP",
        "tranche": 1,
        "expected_return": "+40-60%",
        "conviction": "⭐⭐⭐⭐⭐"
    },
    "GOOGL": {
        "entry_price": 150.00,
        "entry_date": "2026-05-17",
        "shares": 72,  # ~$10,800 position  
        "target_1": 200,
        "target_2": 230,
        "stop_loss": 127.50,  # -15% stop
        "tier": "MEGA-CAP", 
        "tranche": 1,
        "expected_return": "+35-55%",
        "conviction": "⭐⭐⭐⭐"
    },
    "NVDA": {
        "entry_price": 720.00,
        "entry_date": "2026-05-18",
        "shares": 11,  # ~$8,000 position
        "target_1": 1050,
        "target_2": 1200,
        "stop_loss": 612,  # -15% stop (higher risk tolerance for NVDA)
        "tier": "AI/CHIP",
        "tranche": 1,
        "expected_return": "+60-80%",
        "conviction": "⭐⭐⭐⭐⭐"
    },
    "META": {
        "entry_price": 550.00,
        "entry_date": "2026-05-19",
        "shares": 15,  # ~$8,250 position
        "target_1": 720,
        "target_2": 800,
        "stop_loss": 467.50,  # -15% stop
        "tier": "MEGA-CAP",
        "tranche": 1,
        "expected_return": "+40-60%",
        "conviction": "⭐⭐⭐⭐"
    },
    
    # Add more positions as you enter them...
    # "IONQ": {
    #     "entry_price": 27.50,
    #     "entry_date": "2026-05-20",
    #     "shares": 400,  # ~$11,000 position
    #     "target_1": 45,
    #     "target_2": 55,
    #     "stop_loss": 20.50,  # -25% stop (higher risk tolerance)
    #     "tier": "QUANTUM",
    #     "tranche": 1,
    #     "expected_return": "+60-90%",
    #     "conviction": "⭐⭐⭐⭐"
    # }
}

def get_current_price(ticker):
    """Fetch current stock price with robust error handling"""
    try:
        data = yf.download(ticker, period="1d", interval="1m", auto_adjust=True, progress=False)
        if len(data) > 0:
            price = data['Close'].iloc[-1]
            return float(price) if price is not None and not pd.isna(price) else None
        return None
    except:
        return None

def calculate_position_metrics(position, current_price):
    """Calculate P&L, target distances, and recommendations"""
    entry_price = position["entry_price"]
    shares = position["shares"]
    
    # P&L calculations
    unrealized_pnl = (current_price - entry_price) * shares
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    position_value = current_price * shares
    
    # Target analysis
    target_1_distance = ((position["target_1"] - current_price) / current_price) * 100
    target_2_distance = ((position["target_2"] - current_price) / current_price) * 100
    
    # Stop loss analysis
    stop_distance = ((current_price - position["stop_loss"]) / current_price) * 100
    
    # Risk/Reward ratios
    risk_from_entry = entry_price - position["stop_loss"]
    reward_to_t1 = position["target_1"] - entry_price
    reward_to_t2 = position["target_2"] - entry_price
    
    rr_ratio_t1 = reward_to_t1 / risk_from_entry if risk_from_entry > 0 else 0
    rr_ratio_t2 = reward_to_t2 / risk_from_entry if risk_from_entry > 0 else 0
    
    return {
        "unrealized_pnl": unrealized_pnl,
        "pnl_pct": pnl_pct,
        "position_value": position_value,
        "target_1_distance": target_1_distance,
        "target_2_distance": target_2_distance,
        "stop_distance": stop_distance,
        "rr_ratio_t1": rr_ratio_t1,
        "rr_ratio_t2": rr_ratio_t2
    }

def get_position_recommendation(position, current_price, metrics):
    """Generate specific trading recommendation for the position"""
    
    entry_price = position["entry_price"]
    target_1 = position["target_1"]
    target_2 = position["target_2"]
    stop_loss = position["stop_loss"]
    tier = position["tier"]
    
    # Determine action based on price levels and tier
    if current_price <= stop_loss:
        action = "🔴 STOP HIT - SELL IMMEDIATELY"
        reason = f"Price below stop loss ${stop_loss:.2f}"
        color = "dc3545"
        
    elif current_price >= target_2:
        action = "🟢 TAKE PROFITS - SELL 75%"
        reason = f"Hit Target 2 ${target_2:.2f} - Lock in gains"
        color = "28a745"
        
    elif current_price >= target_1:
        action = "🟡 TAKE PROFITS - SELL 50%"
        reason = f"Hit Target 1 ${target_1:.2f} - Secure profits, let rest run"
        color = "ffc107"
        
    elif metrics["pnl_pct"] >= 25 and tier in ["MEGA-CAP", "AI/CHIP"]:
        action = "🟡 CONSIDER PARTIAL PROFITS"
        reason = f"Up {metrics['pnl_pct']:+.1f}% - Take 25% off table"
        color = "17a2b8"
        
    elif metrics["pnl_pct"] <= -8 and tier == "MEGA-CAP":
        action = "🟠 TIGHTEN STOP"
        reason = f"Down {metrics['pnl_pct']:+.1f}% - Move stop to -10%"
        color = "fd7e14"
        
    elif metrics["pnl_pct"] <= -12 and tier in ["QUANTUM", "SPACE", "ENERGY"]:
        action = "🟠 WATCH CLOSELY"
        reason = f"Down {metrics['pnl_pct']:+.1f}% - Approaching stop zone"
        color = "fd7e14"
        
    elif current_price < entry_price * 0.90 and position["tranche"] == 1:
        action = "🟢 ADD TRANCHE 2"
        reason = f"Down {metrics['pnl_pct']:+.1f}% - Average down opportunity"
        color = "20c997"
        
    elif metrics["pnl_pct"] >= 5:
        action = "🟢 TRAIL STOP TO BREAKEVEN"
        reason = f"Up {metrics['pnl_pct']:+.1f}% - Protect gains"
        color = "28a745"
        
    else:
        action = "🔵 HOLD - NO ACTION"
        reason = f"Position within normal range ({metrics['pnl_pct']:+.1f}%)"
        color = "6c757d"
    
    return action, reason, color

def calculate_portfolio_summary(positions_data):
    """Calculate overall portfolio metrics"""
    total_invested = 0
    total_value = 0
    total_pnl = 0
    
    tier_summary = {}
    
    for ticker, data in positions_data.items():
        position = data["position"]
        metrics = data["metrics"]
        
        total_invested += position["entry_price"] * position["shares"]
        total_value += metrics["position_value"]
        total_pnl += metrics["unrealized_pnl"]
        
        tier = position["tier"]
        if tier not in tier_summary:
            tier_summary[tier] = {"invested": 0, "value": 0, "pnl": 0, "count": 0}
        
        tier_summary[tier]["invested"] += position["entry_price"] * position["shares"]
        tier_summary[tier]["value"] += metrics["position_value"]
        tier_summary[tier]["pnl"] += metrics["unrealized_pnl"]
        tier_summary[tier]["count"] += 1
    
    total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested > 0 else 0
    
    return {
        "total_invested": total_invested,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "tier_summary": tier_summary
    }

def send_position_update():
    """Send Discord update on all crash positions"""
    
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK environment variable is missing.")
        return
    
    # Gather all position data
    positions_data = {}
    
    for ticker, position in CRASH_POSITIONS.items():
        current_price = get_current_price(ticker)
        
        if current_price is None:
            print(f"Warning: Could not fetch price for {ticker}")
            continue
            
        metrics = calculate_position_metrics(position, current_price)
        action, reason, color = get_position_recommendation(position, current_price, metrics)
        
        positions_data[ticker] = {
            "position": position,
            "current_price": current_price,
            "metrics": metrics,
            "action": action,
            "reason": reason,
            "color": color
        }
    
    if not positions_data:
        print("No position data available")
        return
    
    # Calculate portfolio summary
    portfolio = calculate_portfolio_summary(positions_data)
    
    # Create Discord webhook
    webhook = DiscordWebhook(url=webhook_url)
    
    # Determine overall portfolio color
    if portfolio["total_pnl_pct"] >= 10:
        main_color = "28a745"  # Green
    elif portfolio["total_pnl_pct"] >= 0:
        main_color = "17a2b8"  # Blue
    elif portfolio["total_pnl_pct"] >= -10:
        main_color = "ffc107"  # Yellow
    else:
        main_color = "dc3545"  # Red
    
    # Main embed
    embed = DiscordEmbed(
        title="💼 CRASH POSITION MANAGEMENT UPDATE",
        description=f"SPY Crash Buy Portfolio Status - {datetime.now().strftime('%B %d, %Y at %I:%M %p CST')}",
        color=main_color
    )
    
    # Portfolio summary
    portfolio_summary = f"""
**OVERALL PORTFOLIO:**
├─ Total Invested: ${portfolio['total_invested']:,.0f}
├─ Current Value: ${portfolio['total_value']:,.0f}
├─ **Unrealized P&L: ${portfolio['total_pnl']:+,.0f} ({portfolio['total_pnl_pct']:+.1f}%)**
└─ Positions: {len(positions_data)} active

**TIER BREAKDOWN:**"""
    
    for tier, data in portfolio["tier_summary"].items():
        pnl_pct = (data["pnl"] / data["invested"]) * 100 if data["invested"] > 0 else 0
        portfolio_summary += f"\n├─ {tier}: ${data['pnl']:+,.0f} ({pnl_pct:+.1f}%) - {data['count']} pos"
    
    embed.add_embed_field(
        name="📊 PORTFOLIO SUMMARY",
        value=portfolio_summary,
        inline=False
    )
    
    # Individual position details
    positions_text = "**INDIVIDUAL POSITIONS:**\n\n"
    
    # Sort positions by P&L percentage (best performers first)
    sorted_positions = sorted(positions_data.items(), key=lambda x: x[1]["metrics"]["pnl_pct"], reverse=True)
    
    for ticker, data in sorted_positions[:10]:  # Limit to top 10 for Discord
        position = data["position"]
        current = data["current_price"]
        metrics = data["metrics"]
        
        positions_text += f"""
{position['conviction']} **{ticker}** ({position['tier']})
├─ Entry: ${position['entry_price']:.2f} | Current: ${current:.2f}
├─ P&L: ${metrics['unrealized_pnl']:+,.0f} ({metrics['pnl_pct']:+.1f}%)
├─ Targets: ${position['target_1']:.0f} ({metrics['target_1_distance']:+.0f}%) / ${position['target_2']:.0f} ({metrics['target_2_distance']:+.0f}%)
├─ Stop: ${position['stop_loss']:.2f} ({metrics['stop_distance']:+.0f}%)
└─ **{data['action']}**
"""
    
    embed.add_embed_field(
        name="📈 POSITION DETAILS",
        value=positions_text[:1900],  # Discord limit
        inline=False
    )
    
    # Action items summary
    action_items = []
    for ticker, data in positions_data.items():
        if "SELL" in data["action"] or "ADD" in data["action"] or "TIGHTEN" in data["action"]:
            action_items.append(f"**{ticker}**: {data['action']}")
    
    if action_items:
        actions_text = "**IMMEDIATE ACTIONS NEEDED:**\n" + "\n".join(action_items[:10])
    else:
        actions_text = "**✅ NO IMMEDIATE ACTIONS REQUIRED**\nAll positions within normal ranges"
    
    embed.add_embed_field(
        name="⚡ ACTION ITEMS",
        value=actions_text,
        inline=False
    )
    
    # Recovery timeline 
    timeline_text = """
**📅 CRASH RECOVERY TIMELINE:**
• **Phase 1 (May 15-20):** Peak selling - Primary buying window
• **Phase 2 (May 21-28):** Capitulation - Secondary buying/averaging
• **Phase 3 (June-July):** Early recovery - Trail stops, take partial profits
• **Phase 4 (Aug-Sept):** Full recovery - Hit targets, book gains

**Current Phase:** Based on market action and position performance
"""
    
    embed.add_embed_field(
        name="🗓️ RECOVERY ROADMAP",
        value=timeline_text,
        inline=False
    )
    
    embed.set_footer(text="Next update: Every 4 hours during market hours | This is not financial advice")
    
    webhook.add_embed(embed)
    webhook.execute()
    
    print(f"✅ Position update sent! Portfolio P&L: ${portfolio['total_pnl']:+,.0f} ({portfolio['total_pnl_pct']:+.1f}%)")

def main():
    """Main position management function"""
    print("Starting Crash Position Management Update...")
    
    if not CRASH_POSITIONS:
        print("No crash positions configured. Please add your positions to CRASH_POSITIONS.")
        return
    
    send_position_update()

if __name__ == "__main__":
    main()