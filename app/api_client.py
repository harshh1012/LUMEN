# app/api_client.py
# RESTORE: Google AI Studio (google-generativeai) client helpers
import os
import time
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY missing! Set it inside .env")

genai.configure(api_key=API_KEY)

# Default model if not overridden from the UI
DEFAULT_MODEL = os.getenv("MODEL_NAME", "models/gemini-2.5-flash")

# Simple safe generator with retries and graceful fallback on quota errors
def _generate_safe(model_name: str, prompt: str, retries: int = 2):
    """Call the model, retry on transient errors, return friendly message on quota issues."""
    model = genai.GenerativeModel(model_name)
    attempt = 0
    while True:
        try:
            resp = model.generate_content(prompt)
            return getattr(resp, "text", str(resp)).strip()
        except google_exceptions.ResourceExhausted as e:
            # Quota exhausted for this model — return friendly message so UI doesn't crash
            print("Quota exhausted for model:", model_name, "->", e)
            return ("Sorry — this model's quota is exceeded right now. "
                    "Try another model from the sidebar or try again later.")
        except (google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                google_exceptions.InternalServerError) as e:
            # transient server error -> retry
            if attempt >= retries:
                print("Transient generation error, retries exhausted:", e)
                return ("Temporary service issue. Please try again in a moment.")
            delay = 1.0 * (2 ** attempt)
            time.sleep(delay)
            attempt += 1
        except Exception as e:
            # unexpected error
            print("Unexpected generation error:", e)
            return ("I'm having trouble generating an answer right now. Please try again later.")


def ask_mental(user_msg: str, sentiment: dict, model_name: str | None = None) -> str:
    """
    Generate an empathetic mental-health response.
    model_name: optional model override (string), otherwise DEFAULT_MODEL used.
    """
    model_to_use = model_name or DEFAULT_MODEL
    prompt = f"""
You are a warm, empathetic mental health companion. Do NOT provide medical diagnoses or prescription advice.
Detected sentiment: {sentiment}
User: {user_msg}
Reply compassionately and safely in 3-5 sentences.
"""
    return _generate_safe(model_to_use, prompt)


def ask_legal(user_msg: str, retrieved_passages=None, model_name: str | None = None):
    """
    Answer legal information questions using optional retrieved passages.
    Returns: (answer_text, retrieved_passages)
    """
    model_to_use = model_name or DEFAULT_MODEL
    retrieved_passages = retrieved_passages or []

    # Build a short context from retrieved passages (if any)
    context = ""
    for r in retrieved_passages[:5]:
        src = r.get("source", "unknown")
        txt = r.get("text", "")
        # keep only small previews to reduce token usage
        context += f"[{src}] {txt[:800]}\n\n"

    prompt = f"""
You are a legal information assistant. You do not give legal advice, only general information.
If the context below is relevant, use it and cite source filenames in square brackets.

Context:
{context}

User question:
{user_msg}

Answer clearly and concisely (3-6 sentences). If you used a source, cite it like [Source: filename].
"""
    answer = _generate_safe(model_to_use, prompt)
    return answer, retrieved_passages
