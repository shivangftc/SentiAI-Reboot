import os
import time
import requests
from flask import Flask
from threading import Thread
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# 1. SETUP
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('APCA_SECRET')
AV_API_KEY = os.getenv('AV_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

trading_client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
TICKERS = ['TSLA', 'AAPL', 'NVDA', 'MSFT']

# Track the last time Alpha Vantage was used
last_av_run = 0 
AV_INTERVAL = 14400  # 4 Hours in seconds (to stay under 25/day limit)

app = Flask(__name__)
@app.route('/')
def home(): return "SentiAI Hybrid Engine V3.0 Active"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. THE TWO BRAINS
def get_av_sentiment(ticker):
    """Institutional Brain (Alpha Vantage)"""
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={AV_API_KEY}"
    try:
        data = requests.get(url).json()
        feed = data.get('feed', [])
        if not feed: return "NEUTRAL", 0.0
        score = float(feed[0].get('overall_sentiment_score', 0))
        return ("POSITIVE" if score >= 0.2 else "NEGATIVE" if score <= -0.2 else "NEUTRAL"), abs(score)
    except: return "NEUTRAL", 0.0

def get_newsapi_sentiment(ticker):
    """Scout Brain (NewsAPI)"""
    url = f'https://newsapi.org/v2/everything'
    params = {'qInTitle': f'"{ticker}"', 'sortBy': 'publishedAt', 'language': 'en', 'apiKey': NEWS_API_KEY}
    try:
        data = requests.get(url, params=params).json()
        articles = data.get('articles', [])
        if not articles or ticker.upper() not in articles[0]['title'].upper(): return "NEUTRAL", 0.0
        text = articles[0]['title'].lower()
        if any(w in text for w in ['surge', 'up', 'ai', 'beats']): return "POSITIVE", 0.8
        if any(w in text for w in ['fall', 'miss', 'down', 'lawsuit']): return "NEGATIVE", 0.8
        return "NEUTRAL", 0.0
    except: return "NEUTRAL", 0.0

# 3. HYBRID LOOP
def main():
    global last_av_run
    Thread(target=run_flask, daemon=True).start()
    print("--- SentiAI Hybrid Active ---")

    while True:
        current_time = time.time()
        
        # Decide which API to use
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
                    print(f"✅ {side.value.upper()} {ticker} (Conf: {conf})")
                except Exception as e:
                    print(f"⚠️ {ticker} Skip: {e}")
            
            time.sleep(2) # Prevent rate limiting

        if use_av:
            last_av_run = current_time
            print("💤 AV used. Reverting to NewsAPI for the next 4 hours.")

        print("💤 Cycle complete. Sleeping 700s...")
        time.sleep(700)

if __name__ == "__main__":
    main()
