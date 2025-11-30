from transformers import pipeline

_sentiment = None

def get_sentiment():
    global _sentiment
    if _sentiment is None:
        _sentiment = pipeline("sentiment-analysis")
    return _sentiment


def analyze_sentiment(text: str):
    if not text or not text.strip():
        return {"label": "neutral", "score": 0.0}
    pipe = get_sentiment()
    result = pipe(text[:500])[0]
    return {"label": result.get("label"), "score": float(result.get("score", 0.0))}
