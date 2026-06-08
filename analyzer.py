import requests
import os

# Get the token and strip any hidden spaces or newlines (\n)
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

# Updated 2026 Hugging Face Router URL for the FinBERT model
API_URL = "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

def analyze_sentiment(text):
    """
    Sends news text to the Hugging Face Inference Router.
    Returns: (label, confidence_score)
    """
    # 'wait_for_model' ensures it doesn't fail if the model is 'sleeping' on the server
    payload = {
        "inputs": text, 
        "options": {"wait_for_model": True}
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        
        # Check if the API returned an error (like the migration warning)
        if response.status_code != 200:
            print(f"⚠️ API Error ({response.status_code}): {response.text}")
            return "neutral", 0.0
            
        result = response.json()

        # The new Router returns a nested list: [[{'label': '...', 'score': ...}, ...]]
        if isinstance(result, list) and len(result) > 0:
            # We want the label with the highest score
            top_prediction = max(result[0], key=lambda x: x['score'])
            return top_prediction['label'].lower(), top_prediction['score']
        else:
            print(f"⚠️ Unexpected Router format: {result}")
            
    except Exception as e:
        print(f"❌ Sentiment Analysis Exception: {e}")
        
    return "neutral", 0.0

# Simple test block (won't run when imported by your main script)
if __name__ == "__main__":
    test_text = "Tesla stock reaches all-time high after record-breaking quarter."
    sentiment, confidence = analyze_sentiment(test_text)
    print(f"Test Result -> Sentiment: {sentiment}, Confidence: {confidence:.2f}")
