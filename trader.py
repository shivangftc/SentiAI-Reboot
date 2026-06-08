import alpaca_trade_api as tradeapi
import os
from dotenv import load_dotenv
from pathlib import Path

# 1. Locate the .env file in the same folder as this script
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def execute_trade(symbol, sentiment_label, confidence):
    """
    Handles connection and trading inside the function to prevent 
    startup crashes if keys are missing.
    """
    # 2. Fetch keys right when they are needed
    api_key = os.getenv('ALPACA_KEY')
    secret_key = os.getenv('ALPACA_SECRET')
    base_url = 'https://paper-api.alpaca.markets'

    # 3. Safety Check: If keys are missing, don't even try to connect
    if not api_key or not secret_key:
        print(f"❌ CRITICAL ERROR: API Keys not found. Checked: {env_path}")
        return

    try:
        # Initialize connection locally
        api = tradeapi.REST(api_key, secret_key, base_url, api_version='v2')
        
        # Trade Logic
        if confidence > 0.80:
            side = 'buy' if sentiment_label == 'positive' else 'sell'
            print(f"🚀 {side.upper()} SIGNAL: {symbol} (Conf: {confidence:.2f})")
            
            api.submit_order(
                symbol=symbol,
                qty=1, 
                side=side,
                type='market',
                time_in_force='gtc'
            )
        else:
            print(f"⏳ Confidence {confidence:.2f} is too low for {symbol}.")
            
    except Exception as e:
        print(f"❌ Alpaca Error: {e}")

# This part lets you test JUST this file by running 'python trader.py'
if __name__ == "__main__":
    print("Running manual trade test...")
    execute_trade("TSLA", "positive", 0.99)