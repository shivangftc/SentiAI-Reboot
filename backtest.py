import os
import sys
import time
import pandas as pd
import pandas_ta as ta
import alpaca_trade_api as tradeapi
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
TICKERS = ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMD']
QTY_PER_TRADE = 10  # Start small!
TRAIL_PERCENT = 0.3  # Alpaca API expects percent as a whole number (0.3 = 0.3%)
processed_news_ids = set()

# Initialize Alpaca REST API
api = tradeapi.REST(
    os.getenv('ALPACA_KEY'), 
    os.getenv('ALPACA_SECRET'), 
    base_url='https://paper-api.alpaca.markets'
)

try:
    from analyzer import analyze_sentiment
    print("🧠 Sentiment Brain loaded.")
except ImportError:
    print("⚠️ analyzer.py not found. Bot will not function.")
    sys.exit()

def is_market_open():
    """Checks Alpaca's clock to see if the NYSE is currently open."""
    clock = api.get_clock()
    return clock.is_open

def execute_trade(symbol, sentiment):
    """Submits a real market order with an attached trailing stop."""
    side = 'buy' if sentiment == 'POSITIVE' else 'sell'
    
    try:
        # Submit the initial entry order
        order = api.submit_order(
            symbol=symbol,
            qty=QTY_PER_TRADE,
            side=side,
            type='market',
            time_in_force='day'
        )
        print(f"🚀 [ENTRY] {side.upper()} {symbol} executed.")

        # Note: In a true live scenario, you'd wait for fill then set a trailing stop.
        # For this version, we are sending the market order. 
        # Alpaca also supports 'trailing_stop' order types directly.
        
        api.submit_order(
            symbol=symbol,
            qty=QTY_PER_TRADE,
            side='sell' if side == 'buy' else 'buy',
            type='trailing_stop',
            trail_percent=TRAIL_PERCENT,
            time_in_force='gtc'
        )
        print(f"🛡️ [PROTECTION] Trailing Stop set at {TRAIL_PERCENT}% for {symbol}.")

    except Exception as e:
        print(f"❌ Order Failed for {symbol}: {e}")

def monitor_market():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📡 SentiAI Scanning News...")
    
    for symbol in TICKERS:
        # Get the single latest news headline
        news = api.get_news(symbol, limit=1)
        if not news: continue
        
        article = news[0]
        if article.id in processed_news_ids: continue
        
        # Analyze news
        label, score = analyze_sentiment(article.headline)
        processed_news_ids.add(article.id)
        
        # Run 6 logic: We trade anything non-neutral with > 0.5 confidence
        if label != 'neutral' and score > 0.5:
            print(f"🎯 SIGNAL FOUND: {symbol} | {label.upper()} ({score:.2f})")
            execute_trade(symbol, label.upper())

# --- MAIN ENGINE ---
if __name__ == "__main__":
    print("🟢 SentiAI Live Executor Started (Paper Trading Mode)")
    
    while True:
        if is_market_open():
            try:
                monitor_market()
            except Exception as e:
                print(f"⚠️ Runtime Error: {e}")
        else:
            print(f"💤 Market is closed. Waiting... ({datetime.now().strftime('%H:%M')})")
        
        # Wait 1 minute before next scan to avoid API rate limits
        time.sleep(60)