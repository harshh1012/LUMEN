# backend/mental_bot.py

import joblib
import os


MODEL_PATH = "backend/models/emotion_classifier.pkl"

# Load ML model if it exists
if os.path.exists(MODEL_PATH):
    emotion_model = joblib.load(MODEL_PATH)
else:
    emotion_model = None


BASIC_RESPONSES = {
    "sad": "I'm sorry you're feeling sad. You're not alone — I'm here with you.",
    "happy": "That’s wonderful to hear! Tell me more about it.",
    "anxious": "Anxiety can feel overwhelming. You’re safe here — would you like to talk about it?",
    "angry": "It’s okay to feel angry when things go wrong. What happened?",
}


def detect_emotion(user_text: str):
    """Predict emotion using ML model if available."""
    if emotion_model:
        try:
            return emotion_model.predict([user_text])[0]
        except:
            return "neutral"
    return "neutral"


def mental_response(user_text: str) -> str:
    """Generate empathetic mental-health safe response."""
    emotion = detect_emotion(user_text)

    if emotion in BASIC_RESPONSES:
        return BASIC_RESPONSES[emotion]

    return (
        "I’m here to listen. It’s okay to express whatever you're feeling. "
        "Tell me more about what’s going on."
    )
