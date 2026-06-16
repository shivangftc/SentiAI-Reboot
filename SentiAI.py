import os
import time
import requests
from flask import Flask
from threading import Thread
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pytz

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ==========================================
# 1. SETUP & ENVIRONMENT CONFIGURATION
# ==========================================
# Load local .env file if it exists (for local testing environment)
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
AV_API_KEY = os.getenv('AV_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

# Crash prevention check
if not ALPACA_KEY or not ALPACA_SECRET:
    raise ValueError("CRITICAL: ALPACA_KEY or ALPACA_SECRET environment variables are missing!")

# Unified, single initialization of the Alpaca Client
trading_client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

TICKERS = ['TSLA', 'AAPL', 'NVDA', 'MSFT', 'SPY', 'QQQ']
last_av_run = 0 
AV_INTERVAL = 14400  # 4 Hours

app = Flask(__name__)

@app.route('/')
def home(): 
    return "SentiAI Hybrid Engine V3.0 Active", 200

# ==========================================
# 2. THE SENTIMENT BRAINS
# ==========================================
def get_av_sentiment(ticker):
    """Institutional Brain (Alpha Vantage)"""
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={AV_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        
        if "Information" in data or "Note" in data:
            print(f"⚠️ [AV] Rate Limit/Notice for {ticker}: {data.get('Information', data.get('Note'))}")
            return "NEUTRAL", 0.0

        feed = data.get('feed', [])
        if not feed: 
            return "NEUTRAL", 0.0
            
        score = float(feed[0].get('overall_sentiment_score', 0))
        sentiment = "NEUTRAL"
        if score >= 0.2: sentiment = "POSITIVE"
        elif score <= -0.2: sentiment = "NEGATIVE"
        
        return sentiment, abs(score)
    except Exception as e: 
        print(f"💥 [AV] Exception for {ticker}: {e}")
        return "NEUTRAL", 0.0

def get_newsapi_sentiment(ticker):
    """Scout Brain (NewsAPI)"""
    url = f'https://newsapi.org/v2/everything'
    params = {'q': ticker, 'sortBy': 'publishedAt', 'language': 'en', 'apiKey': NEWS_API_KEY}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get('status') == 'error':
            print(f"⚠️ [NewsAPI] Error: {data.get('message')}")
            return "NEUTRAL", 0.0

        articles = data.get('articles', [])
        if not articles: 
            return "NEUTRAL", 0.0
            
        text = articles[0].get('title', '').lower() + " " + articles[0].get('description', '').lower()
        
        if any(w in text for w in ['surge', 'up', 'ai', 'beats', 'growth', 'bullish']): 
            return "POSITIVE", 0.8
        if any(w in text for w in ['fall', 'miss', 'down', 'lawsuit', 'drop', 'bearish']): 
            return "NEGATIVE", 0.8
            
        return "NEUTRAL", 0.0
    except Exception as e: 
        print(f"💥 [NewsAPI] Exception for {ticker}: {e}")
        return "NEUTRAL", 0.0

# ==========================================
# 3. TRADING ENGINE (MANUAL & AUTOMATED)
# ==========================================
def is_market_open():
    """Checks if the US Market is open (Standard Hours: 9:30 AM - 4:00 PM EST)"""
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    if now_eastern.weekday() >= 5:
        return False
    market_start = now_eastern.replace(hour=9, minute=30, second=0, microsecond=0)
    market_end = now_eastern.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_start <= now_eastern <= market_end

def execute_manual_trade(symbol, sentiment_label, confidence):
    """Brought over from trader.py: Safely forces a manual order execution packet."""
    try:
        if confidence >= 0.80:
            side = OrderSide.BUY if sentiment_label.lower() == 'positive' else OrderSide.SELL
            print(f"🚀 [MANUAL SIGNAL] {side.value.upper()}: {symbol} (Conf: {confidence:.2f})")
            
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=1,
                side=side,
                time_in_force=TimeInForce.GTC
            )
            trading_client.submit_order(order_request)
            print(f"✅ Manual order for {symbol} processed successfully.")
        else:
            print(f"⏳ Manual block skipped: Confidence {confidence:.2f} too low for {symbol}.")
    except Exception as e:
        print(f"❌ Manual execution block failed: {e}")

def automated_trading_loop():
    """The automated algorithmic scanning loop task"""
    global last_av_run
    print("--- SentiAI Hybrid Trading Loop Started ---")

    while True:
        if not is_market_open():
            eastern = pytz.timezone('US/Eastern')
            print(f"💤 Market closed (EST {datetime.now(eastern).strftime('%H:%M')}). Sleeping 300s...")
            time.sleep(300)
            continue

        current_time = time.time()
        use_av = (current_time - last_av_run) >= AV_INTERVAL
        mode = "INSTITUTIONAL (AV)" if use_av else "SCOUT (NewsAPI)"
        print(f"\n--- Cycle Start: {mode} Mode ---")

        for ticker in TICKERS:
            sentiment, conf = get_av_sentiment(ticker) if use_av else get_newsapi_sentiment(ticker)
            
            if conf >= 0.25:
                side = OrderSide.BUY if sentiment == "POSITIVE" else OrderSide.SELL
                try:
                    order = MarketOrderRequest(symbol=ticker, qty=1, side=side, time_in_force=TimeInForce.GTC)
                    trading_client.submit_order(order)
                    print(f"✅ {side.value.upper()} order submitted for {ticker} (Conf: {conf})")
                except Exception as e:
                    print(f"⚠️ {ticker} Order Execution Skipped: {e}")
            
            time.sleep(15 if use_av else 2) 

        if use_av:
            last_av_run = current_time
            print("💤 AV quota cycle utilized. Reverting engine to NewsAPI for the next 4 hours.")

        print("💤 Cycle complete. Sleeping 700s...")
        time.sleep(700)

# ==========================================
# 4. RUNNER ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    # --- MANUAL TESTING SWITCH ---
    # When running locally ('python app.py'), you can uncomment this line to run an immediate test trade.
    # print("--- Initiating Pre-Flight Manual Trade Test ---")
    # execute_manual_trade("TSLA", "positive", 0.99)
    # -----------------------------

    # Spin up background automated loop
    bot_thread = Thread(target=automated_trading_loop, daemon=True)
    bot_thread.start()
    
    # Fire up the Flask Keep-Alive framework
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
