# app/api_client.py
import os
import re
import time
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY missing! Set it inside .env")

genai.configure(api_key=API_KEY)

DEFAULT_MODEL = os.getenv("MODEL_NAME", "models/gemini-2.5-flash")

# Crisis keywords for mental health mode — triggers immediate safety resources
CRISIS_PATTERNS = re.compile(
    r"\b(suicide|suicidal|kill myself|end my life|self.harm|cutting myself|"
    r"don't want to live|want to die|hurt myself|overdose|no reason to live)\b",
    re.IGNORECASE,
)

CRISIS_RESPONSE = """I'm really concerned about what you've shared, and I want you to know you're not alone.

Please reach out to a crisis helpline right now:
• **iCall (India):** 9152987821
• **Vandrevala Foundation:** 1860-2662-345 (24/7)
• **International Association for Suicide Prevention:** https://www.iasp.info/resources/Crisis_Centres/

I'm not a substitute for a professional — please talk to someone who can truly help. 💙

Are you safe right now?"""


def detect_crisis(text: str) -> bool:
    return bool(CRISIS_PATTERNS.search(text))


def _generate_safe(model_name: str, prompt: str, system: str = "", retries: int = 2) -> str:
    """Call the model, retry on transient errors, return friendly message on quota issues."""
    try:
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system if system else None,
        )
    except Exception:
        model = genai.GenerativeModel(model_name)

    attempt = 0
    while True:
        try:
            resp = model.generate_content(prompt)
            return getattr(resp, "text", str(resp)).strip()
        except google_exceptions.ResourceExhausted as e:
            print("Quota exhausted for model:", model_name, "->", e)
            return (
                "Sorry — this model's quota is exceeded right now. "
                "Try another model from the sidebar or try again later."
            )
        except (
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
            google_exceptions.InternalServerError,
        ) as e:
            if attempt >= retries:
                print("Transient generation error, retries exhausted:", e)
                return "Temporary service issue. Please try again in a moment."
            time.sleep(1.0 * (2**attempt))
            attempt += 1
        except Exception as e:
            print("Unexpected generation error:", e)
            return "I'm having trouble generating an answer right now. Please try again later."


def ask_mental(user_msg: str, sentiment: dict, model_name: str | None = None) -> tuple[str, bool]:
    """
    Generate an empathetic mental-health response.
    Returns: (reply_text, is_crisis)
    """
    model_to_use = model_name or DEFAULT_MODEL

    # Check for crisis first
    crisis = detect_crisis(user_msg)
    if crisis:
        return CRISIS_RESPONSE, True

    sentiment_label = (sentiment or {}).get("label", "neutral")
    sentiment_score = (sentiment or {}).get("score", 0.0)

    system = (
        "You are a warm, empathetic mental health companion. "
        "You do NOT provide medical diagnoses or prescription advice. "
        "If the user expresses suicidal ideation or self-harm intent, "
        "provide crisis hotline numbers immediately. "
        "Keep responses focused, compassionate, and under 150 words unless detail is truly needed."
    )

    prompt = (
        f"Detected emotional tone: {sentiment_label} (confidence: {sentiment_score:.2f})\n\n"
        f"User message: {user_msg}\n\n"
        "Respond compassionately in 3-5 sentences. "
        "Acknowledge their feelings, offer a gentle coping suggestion if appropriate, "
        "and end with an open question to keep them talking."
    )

    return _generate_safe(model_to_use, prompt, system=system), False


def ask_legal(
    user_msg: str, retrieved_passages=None, model_name: str | None = None
) -> tuple[str, list]:
    """
    Answer legal information questions using optional retrieved passages.
    Returns: (answer_text, retrieved_passages)
    """
    model_to_use = model_name or DEFAULT_MODEL
    retrieved_passages = retrieved_passages or []

    context = ""
    for r in retrieved_passages[:5]:
        src = r.get("source", "unknown")
        txt = r.get("text", "")
        context += f"[{src}] {txt[:800]}\n\n"

    system = (
        "You are a legal information assistant. "
        "You provide general legal information only — never legal advice. "
        "Always end with the disclaimer: *This is general information, not legal advice. "
        "Consult a qualified lawyer for your specific situation.*"
    )

    prompt = (
        f"{'Context from knowledge base:' + chr(10) + context if context else 'No documents provided.'}\n\n"
        f"User question: {user_msg}\n\n"
        "Answer clearly in 3-6 sentences. "
        "If you used a source from context, cite it like [Source: filename]. "
        "Use plain language and structure your answer logically."
    )

    answer = _generate_safe(model_to_use, prompt, system=system)
    return answer, retrieved_passages