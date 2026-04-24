from transformers import pipeline
import re

_sentiment = None

POSITIVE_WORDS = {"happy", "great", "wonderful", "excited", "joyful", "grateful", "good", "amazing", "love", "fantastic"}
NEGATIVE_WORDS = {"sad", "depressed", "anxious", "afraid", "angry", "hopeless", "terrible", "awful", "hate", "miserable"}


def get_sentiment():
    global _sentiment
    if _sentiment is None:
        _sentiment = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    return _sentiment


def analyze_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return {"label": "NEUTRAL", "score": 0.0}

    try:
        pipe = get_sentiment()
        # Truncate to model's max tokens (approx 500 chars is safe)
        result = pipe(text[:500])[0]
        label = result.get("label", "NEUTRAL").upper()
        score = float(result.get("score", 0.0))

        # Map to more nuanced labels
        if label == "POSITIVE" and score > 0.9:
            label = "VERY_POSITIVE"
        elif label == "NEGATIVE" and score > 0.9:
            label = "VERY_NEGATIVE"
        elif score < 0.6:
            label = "NEUTRAL"

        return {"label": label, "score": score}

    except Exception as e:
        print("Sentiment analysis error:", e)
        # Simple fallback: keyword matching
        text_lower = text.lower()
        words = set(re.findall(r"\w+", text_lower))
        pos_hits = len(words & POSITIVE_WORDS)
        neg_hits = len(words & NEGATIVE_WORDS)
        if neg_hits > pos_hits:
            return {"label": "NEGATIVE", "score": 0.6}
        elif pos_hits > neg_hits:
            return {"label": "POSITIVE", "score": 0.6}
        return {"label": "NEUTRAL", "score": 0.5}