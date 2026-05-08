"""
Black Box Tests — LUMEN AI Assistant
Tests all REST API endpoints based on inputs and expected outputs.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ── Patch heavy dependencies before importing the app ──────────────────────
import sys

# Mock google.generativeai so api_client.py imports without a real API key
google_mock = MagicMock()
sys.modules["google"] = google_mock
sys.modules["google.generativeai"] = google_mock
sys.modules["google.api_core"] = google_mock
sys.modules["google.api_core.exceptions"] = google_mock

# Mock transformers so sentiment.py imports without downloading models
transformers_mock = MagicMock()
sys.modules["transformers"] = transformers_mock

# Mock retrieval dependencies
sys.modules["pdfplumber"] = MagicMock()
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.metrics"] = MagicMock()
sys.modules["sklearn.metrics.pairwise"] = MagicMock()
sys.modules["numpy"] = MagicMock()

import os
os.environ["DATABASE_URL"] = "sqlite:///./data/test_bb.sqlite"
os.environ["JWT_SECRET"] = "test-secret-key-blackbox"
os.environ["GOOGLE_API_KEY"] = "fake-key-for-tests"

from app.api_server import app

client = TestClient(app, raise_server_exceptions=False)

# ── Helpers ────────────────────────────────────────────────────────────────

def _phone_for(suffix: str) -> str:
    """Produce a deterministic 10-digit phone from any suffix string."""
    digits = ''.join(c for c in suffix if c.isdigit())
    base = (digits + "0000000000")[:10]
    # Make sure it starts with 9 so it looks like a mobile number
    return "9" + base[1:]


def register_and_login(suffix="bb"):
    """Register a user and return their JWT token."""
    reg = client.post("/api/auth/register", json={
        "full_name": f"Test User {suffix}",
        "email": f"testuser_{suffix}@example.com",
        "phone": _phone_for(suffix),
        "password": "SecurePass123"
    })
    if reg.status_code == 409:
        # Already exists, just login
        login = client.post("/api/auth/login", json={
            "identifier": f"testuser_{suffix}@example.com",
            "password": "SecurePass123"
        })
        return login.json().get("token")
    return reg.json().get("token")


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-01  Register with valid data
# ══════════════════════════════════════════════════════════════════════════
def test_bb01_register_valid():
    resp = client.post("/api/auth/register", json={
        "full_name": "Alice Smith",
        "email": "alice.bb01@example.com",
        "phone": "9876543210",
        "password": "Password123"
    })
    assert resp.status_code == 201 or resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data.get("ok") is True


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-02  Register with duplicate email
# ══════════════════════════════════════════════════════════════════════════
def test_bb02_register_duplicate_email():
    payload = {
        "full_name": "Bob Dup",
        "email": "bob.dup@example.com",
        "phone": "9111111111",
        "password": "Password123"
    }
    client.post("/api/auth/register", json=payload)   # first registration
    resp = client.post("/api/auth/register", json=payload)  # duplicate
    assert resp.status_code == 409
    assert "already registered" in resp.json().get("detail", "").lower()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-03  Register with phone < 10 digits
# ══════════════════════════════════════════════════════════════════════════
def test_bb03_register_short_phone():
    resp = client.post("/api/auth/register", json={
        "full_name": "Charlie Short",
        "email": "charlie@example.com",
        "phone": "12345",          # only 5 digits
        "password": "Password123"
    })
    assert resp.status_code == 400
    assert "10 digits" in resp.json().get("detail", "")


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-04  Login with valid credentials
# ══════════════════════════════════════════════════════════════════════════
def test_bb04_login_valid():
    client.post("/api/auth/register", json={
        "full_name": "Dave Login",
        "email": "dave.login@example.com",
        "phone": "9222222222",
        "password": "Password123"
    })
    resp = client.post("/api/auth/login", json={
        "identifier": "dave.login@example.com",
        "password": "Password123"
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-05  Login with wrong password
# ══════════════════════════════════════════════════════════════════════════
def test_bb05_login_wrong_password():
    client.post("/api/auth/register", json={
        "full_name": "Eve Wrong",
        "email": "eve.wrong@example.com",
        "phone": "9333333333",
        "password": "CorrectPass1"
    })
    resp = client.post("/api/auth/login", json={
        "identifier": "eve.wrong@example.com",
        "password": "WrongPass999"
    })
    assert resp.status_code == 401
    assert "invalid" in resp.json().get("detail", "").lower()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-06  Login using phone as identifier
# ══════════════════════════════════════════════════════════════════════════
def test_bb06_login_with_phone():
    client.post("/api/auth/register", json={
        "full_name": "Frank Phone",
        "email": "frank.phone@example.com",
        "phone": "9444444444",
        "password": "Password123"
    })
    resp = client.post("/api/auth/login", json={
        "identifier": "9444444444",
        "password": "Password123"
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-07  Chat — mental mode with valid message
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("I hear you, and I'm here for you.", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEGATIVE", "score": 0.85})
def test_bb07_chat_mental_mode(mock_sentiment, mock_mental):
    token = register_and_login("bb07")
    resp = client.post("/api/chat", json={
        "mode": "mental",
        "message": "I have been feeling very anxious lately."
    }, headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "sentiment" in data
    assert "is_crisis" in data


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-08  Chat — legal mode with valid message
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_legal", return_value=("You have the right to remain silent.", [{"source": "ipc.pdf", "text": "..."}]))
@patch("app.api_server.kb_query", return_value=[])
def test_bb08_chat_legal_mode(mock_kb, mock_legal):
    token = register_and_login("bb08")
    resp = client.post("/api/chat", json={
        "mode": "legal",
        "message": "What are my rights if I am arrested?"
    }, headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "sources" in data


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-09  Chat — message exceeding 2000 characters
# ══════════════════════════════════════════════════════════════════════════
def test_bb09_chat_message_too_long():
    token = register_and_login("bb09")
    resp = client.post("/api/chat", json={
        "mode": "mental",
        "message": "A" * 2001
    }, headers=auth_header(token))
    assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-10  Chat — missing Authorization header
# ══════════════════════════════════════════════════════════════════════════
def test_bb10_chat_no_auth_header():
    resp = client.post("/api/chat", json={
        "mode": "mental",
        "message": "Hello"
    })
    assert resp.status_code == 401
    assert "authorization" in resp.json().get("detail", "").lower()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-11  Chat — expired JWT token
# ══════════════════════════════════════════════════════════════════════════
def test_bb11_chat_expired_token():
    import jwt as pyjwt
    from datetime import datetime, timedelta
    from app.api_server import JWT_SECRET, JWT_ALGORITHM
    expired_token = pyjwt.encode(
        {"sub": "1", "email": "x@x.com", "exp": datetime.utcnow() - timedelta(hours=1), "iat": datetime.utcnow() - timedelta(hours=2)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )
    resp = client.post("/api/chat", json={
        "mode": "mental",
        "message": "Hello"
    }, headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    detail = resp.json().get("detail", "").lower()
    assert "expired" in detail or "invalid" in detail


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-12  Chat — rate limit enforcement (30+ requests)
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("Response", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEUTRAL", "score": 0.5})
def test_bb12_rate_limit(mock_sentiment, mock_mental):
    token = register_and_login("bb12rl")
    headers = auth_header(token)
    # Send 30 requests to hit the limit
    for _ in range(30):
        client.post("/api/chat", json={"mode": "mental", "message": "test"}, headers=headers)
    resp = client.post("/api/chat", json={"mode": "mental", "message": "one more"}, headers=headers)
    assert resp.status_code == 429
    assert "rate limit" in resp.json().get("detail", "").lower()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-13  GET /api/conversations — authenticated user
# ══════════════════════════════════════════════════════════════════════════
def test_bb13_list_conversations():
    token = register_and_login("bb13")
    resp = client.get("/api/conversations", headers=auth_header(token))
    assert resp.status_code == 200
    assert "conversations" in resp.json()
    assert isinstance(resp.json()["conversations"], list)


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-14  GET /api/conversations/{id}/messages — valid conversation
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("I understand.", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEUTRAL", "score": 0.5})
def test_bb14_conversation_messages(mock_sentiment, mock_mental):
    token = register_and_login("bb14")
    chat_resp = client.post("/api/chat", json={
        "mode": "mental", "message": "I need someone to talk to."
    }, headers=auth_header(token))
    conv_id = chat_resp.json().get("conversation_id")
    resp = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_header(token))
    assert resp.status_code == 200
    assert "messages" in resp.json()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-15  GET /api/conversations/{id}/messages — wrong user
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("I understand.", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEUTRAL", "score": 0.5})
def test_bb15_conversation_wrong_user(mock_sentiment, mock_mental):
    token1 = register_and_login("bb15a")
    token2 = register_and_login("bb15b")
    chat_resp = client.post("/api/chat", json={
        "mode": "mental", "message": "Private message"
    }, headers=auth_header(token1))
    conv_id = chat_resp.json().get("conversation_id")
    resp = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_header(token2))
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-16  DELETE /api/conversations/{id} — owner deletes
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("Reply", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEUTRAL", "score": 0.5})
def test_bb16_delete_conversation(mock_sentiment, mock_mental):
    token = register_and_login("bb16")
    chat_resp = client.post("/api/chat", json={
        "mode": "mental", "message": "Delete this please."
    }, headers=auth_header(token))
    conv_id = chat_resp.json().get("conversation_id")
    resp = client.delete(f"/api/conversations/{conv_id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-17  POST /api/kb/upload — valid PDF under 10MB
# ══════════════════════════════════════════════════════════════════════════
def test_bb17_kb_upload_valid_pdf():
    token = register_and_login("bb17")
    fake_pdf = b"%PDF-1.4 fake pdf content for testing"
    resp = client.post("/api/kb/upload",
        files=[("files", ("test_doc.pdf", fake_pdf, "application/pdf"))],
        headers=auth_header(token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("count", 0) >= 1


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-18  POST /api/kb/upload — file > 10MB
# ══════════════════════════════════════════════════════════════════════════
def test_bb18_kb_upload_oversized_file():
    token = register_and_login("bb18")
    large_content = b"A" * (11 * 1024 * 1024)  # 11 MB
    resp = client.post("/api/kb/upload",
        files=[("files", ("big_file.pdf", large_content, "application/pdf"))],
        headers=auth_header(token)
    )
    assert resp.status_code == 200
    assert resp.json().get("count") == 0   # file skipped


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-19  POST /api/kb/upload — unsupported file extension
# ══════════════════════════════════════════════════════════════════════════
def test_bb19_kb_upload_invalid_extension():
    token = register_and_login("bb19")
    resp = client.post("/api/kb/upload",
        files=[("files", ("malware.exe", b"MZ fake exe", "application/octet-stream"))],
        headers=auth_header(token)
    )
    assert resp.status_code == 200
    assert resp.json().get("count") == 0   # .exe skipped


# ══════════════════════════════════════════════════════════════════════════
# TC-BB-20  GET /api/health
# ══════════════════════════════════════════════════════════════════════════
def test_bb20_health_check():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "db" in data
    assert "retrieval_enabled" in data