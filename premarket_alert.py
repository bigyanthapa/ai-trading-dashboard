import os
import json
import yfinance as yf
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime


# Stocks to monitor from the analysis
WATCH_LIST = {
    "PLTR": {"support": 135, "resistance": 160, "status": "extended"},
    "SOFI": {"support": 17, "resistance": 24, "status": "entry_zone"},
    "IREN": {"support": 45, "resistance": 60, "status": "entry_zone"},
    "RKLB": {"support": 85, "resistance": 105, "status": "overbought"},
    "IONQ": {"support": 35, "resistance": 55, "status": "danger"},
    "LUNR": {"support": 25, "resistance": 35, "status": "resistance"},
    "UUUU": {"support": 36, "resistance": 48, "status": "watch"},
    "USAR": {"support": 8.50, "resistance": 12, "status": "watch"},
}

def calculate_rsi(series, period=14):
    """Calculate RSI indicator"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def get_market_regime():
    """Check SPY vs 50-day MA for market regime"""
    try:
        spy = yf.download("SPY", period="100d", interval="1d", auto_adjust=True, progress=False)['Close'].squeeze()
        current_price = spy.iloc[-1]
        sma_50 = spy.rolling(50).mean().iloc[-1]
        
        if current_price > sma_50:
            regime = "🟢 BULLISH (SPY > 50 SMA)"
            emoji = "🟢"
        else:
            regime = "🔴 BEARISH (SPY < 50 SMA)"
            emoji = "🔴"
        
        return regime, emoji, current_price, sma_50
    except Exception as e:
        return "⚪ NEUTRAL (Failed to fetch)", "⚪", 0, 0

def get_stock_data(ticker):
    """Fetch stock price and RSI"""
    try:
        data = yf.download(ticker, period="100d", interval="1d", auto_adjust=True, progress=False)
        if len(data) < 14:
            return None
        
        price = data['Close'].iloc[-1]
        rsi = calculate_rsi(data['Close']).iloc[-1]
        
        # Determine RSI status
        if rsi > 75:
            rsi_status = f"🔴 OVERBOUGHT ({rsi:.0f})"
        elif rsi > 65:
            rsi_status = f"🟡 STRONG ({rsi:.0f})"
        elif rsi > 50:
            rsi_status = f"🟢 BULLISH ({rsi:.0f})"
        elif rsi > 35:
            rsi_status = f"🟡 WEAK ({rsi:.0f})"
        else:
            rsi_status = f"🟢 OVERSOLD ({rsi:.0f})"
        
        return {
            "price": price,
            "rsi": rsi,
            "rsi_status": rsi_status
        }
    except Exception as e:
        return None

def main():
    print("Starting Pre-Market Alert...")
    
    # Get market regime
    regime, emoji, spy_price, sma_50 = get_market_regime()
    
    # Create Discord webhook
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK environment variable is missing.")
        return
    
    webhook = DiscordWebhook(url=webhook_url)
    
    # Main embed
    embed = DiscordEmbed(
        title="🚀 PRE-MARKET SWING TRADE SCAN",
        description=f"Market Open Checklist - {datetime.now().strftime('%I:%M %p CST')}",
        color="3498db"
    )
    
    # Market Regime
    embed.add_embed_field(
        name="📊 Market Regime",
        value=f"{regime}\nSPY: ${spy_price:.2f} | 50 SMA: ${sma_50:.2f}",
        inline=False
    )
    
    # Stock monitoring
    stock_status = ""
    for ticker, config in WATCH_LIST.items():
        data = get_stock_data(ticker)
        if data:
            status_emoji = {
                "extended": "⚠️",
                "entry_zone": "🟢",
                "overbought": "🔴",
                "danger": "🚨",
                "resistance": "🟡",
                "watch": "📍"
            }.get(config["status"], "⭕")
            
            stock_status += f"{status_emoji} **{ticker}**: ${data['price']:.2f} | RSI {data['rsi_status']}\n"
    
    embed.add_embed_field(
        name="📈 Stock Status",
        value=stock_status if stock_status else "Unable to fetch data",
        inline=False
    )
    
    # Action items
    action_text = """
✅ **ACTIONS TO TAKE:**
• Check if SOFI dips to $18-19 (entry zone)
• Monitor IREN support at $45-48 (accumulation)
• Watch RKLB RSI cooling (pullback setup)
• AVOID chasing IONQ (RSI 85+, danger)
• Track earnings: SOFI April 29 (6 DAYS)

⚡ **SET ALERTS FOR 9:30 AM CHECK** after market settles
"""
    
    embed.add_embed_field(
        name="🎯 Next Steps",
        value=action_text,
        inline=False
    )
    
    embed.set_footer(text="Alert sent at 8:00 AM CST | Check again at 9:30 AM for entry confirmation")
    
    webhook.add_embed(embed)
    webhook.execute()
    
    print("✅ Pre-market alert sent to Discord!")

if __name__ == "__main__":
    main()
