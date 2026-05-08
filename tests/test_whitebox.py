"""
White Box Tests — LUMEN AI Assistant
Tests internal helper functions, branching logic, and exception paths.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock

# ── Mock all heavy dependencies before any app import ─────────────────────
google_mock = MagicMock()
sys.modules["google"] = google_mock
sys.modules["google.generativeai"] = google_mock
sys.modules["google.api_core"] = google_mock
sys.modules["google.api_core.exceptions"] = google_mock

transformers_mock = MagicMock()
sys.modules["transformers"] = transformers_mock

sys.modules["pdfplumber"] = MagicMock()
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.metrics"] = MagicMock()
sys.modules["sklearn.metrics.pairwise"] = MagicMock()
sys.modules["numpy"] = MagicMock()

import os
os.environ["DATABASE_URL"] = "sqlite:///./data/test_wb.sqlite"
os.environ["JWT_SECRET"] = "test-secret-key-whitebox"
os.environ["GOOGLE_API_KEY"] = "fake-key-for-tests"

from datetime import datetime, timedelta
import jwt as pyjwt
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api_server import (
    app,
    normalize_phone,
    hash_password,
    verify_password,
    create_token,
    decode_token,
    check_rate_limit,
)
from app.db import AuthUser, RateLimit, SessionLocal, init_db

client = TestClient(app, raise_server_exceptions=False)

# Ensure tables exist for white box tests
init_db()


# ══════════════════════════════════════════════════════════════════════════
# WB-01  hash_password — same input + salt produces same output
# ══════════════════════════════════════════════════════════════════════════
def test_wb01_hash_password_deterministic():
    salt = "abc123salt"
    h1 = hash_password("mypassword", salt)
    h2 = hash_password("mypassword", salt)
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) > 0


# ══════════════════════════════════════════════════════════════════════════
# WB-02  verify_password — correct password returns True, wrong returns False
# ══════════════════════════════════════════════════════════════════════════
def test_wb02_verify_password_correct_and_wrong():
    salt = "randomsalt99"
    hashed = hash_password("correct_password", salt)
    assert verify_password("correct_password", salt, hashed) is True
    assert verify_password("wrong_password", salt, hashed) is False


# ══════════════════════════════════════════════════════════════════════════
# WB-03  normalize_phone — strips non-digit characters
# ══════════════════════════════════════════════════════════════════════════
def test_wb03_normalize_phone():
    assert normalize_phone("+91-9876543210") == "919876543210"
    assert normalize_phone("(98) 765-4321") == "987654321"
    assert normalize_phone("9876543210") == "9876543210"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


# ══════════════════════════════════════════════════════════════════════════
# WB-04  create_token — JWT payload contains correct fields
# ══════════════════════════════════════════════════════════════════════════
def test_wb04_create_token_payload():
    from app.api_server import JWT_SECRET, JWT_ALGORITHM
    token = create_token(42, "test@example.com")
    payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "42"
    assert payload["email"] == "test@example.com"
    assert "exp" in payload
    assert "iat" in payload


# ══════════════════════════════════════════════════════════════════════════
# WB-05  decode_token — expired JWT raises HTTPException 401
# ══════════════════════════════════════════════════════════════════════════
def test_wb05_decode_expired_token():
    from app.api_server import JWT_SECRET, JWT_ALGORITHM
    expired = pyjwt.encode(
        {
            "sub": "1",
            "email": "x@x.com",
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(expired)
    assert exc_info.value.status_code == 401
    # PyJWT may surface expired tokens as either "Token expired" or "Invalid token"
    detail = exc_info.value.detail.lower()
    assert "expired" in detail or "invalid" in detail


# ══════════════════════════════════════════════════════════════════════════
# WB-06  get_current_user — inactive user raises 401
# ══════════════════════════════════════════════════════════════════════════
def test_wb06_inactive_user_blocked():
    db = SessionLocal()
    import secrets
    salt = secrets.token_hex(16)
    user = AuthUser(
        full_name="Inactive User",
        phone="9700000001",
        email="inactive.wb06@example.com",
        password_hash=hash_password("pass", salt),
        password_salt=salt,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    token = create_token(user.id, user.email)
    resp = client.post("/api/chat", json={
        "mode": "mental", "message": "Hello"
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "inactive" in resp.json().get("detail", "").lower()


# ══════════════════════════════════════════════════════════════════════════
# WB-07  check_rate_limit — first request creates RateLimit row with count=1
# ══════════════════════════════════════════════════════════════════════════
def test_wb07_rate_limit_first_request():
    db = SessionLocal()
    import secrets
    salt = secrets.token_hex(16)
    user = AuthUser(
        full_name="Rate Test WB07",
        phone="9700000002",
        email="rate.wb07@example.com",
        password_hash=hash_password("pass", salt),
        password_salt=salt,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    check_rate_limit(user.id, db)
    rl = db.query(RateLimit).filter(RateLimit.auth_user_id == user.id).first()
    assert rl is not None
    assert rl.request_count == 1
    db.close()


# ══════════════════════════════════════════════════════════════════════════
# WB-08  check_rate_limit — 30th request raises HTTPException 429
# ══════════════════════════════════════════════════════════════════════════
def test_wb08_rate_limit_exceeded():
    db = SessionLocal()
    import secrets
    salt = secrets.token_hex(16)
    user = AuthUser(
        full_name="Rate Test WB08",
        phone="9700000003",
        email="rate.wb08@example.com",
        password_hash=hash_password("pass", salt),
        password_salt=salt,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Insert a RateLimit row already at max
    rl = RateLimit(
        auth_user_id=user.id,
        window_start=datetime.utcnow(),
        request_count=30,
    )
    db.add(rl)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(user.id, db)
    assert exc_info.value.status_code == 429
    db.close()


# ══════════════════════════════════════════════════════════════════════════
# WB-09  check_rate_limit — expired window resets count to 1
# ══════════════════════════════════════════════════════════════════════════
def test_wb09_rate_limit_window_reset():
    db = SessionLocal()
    import secrets
    salt = secrets.token_hex(16)
    user = AuthUser(
        full_name="Rate Test WB09",
        phone="9700000004",
        email="rate.wb09@example.com",
        password_hash=hash_password("pass", salt),
        password_salt=salt,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Insert an old rate limit row (2 hours ago — outside the 60-min window)
    rl = RateLimit(
        auth_user_id=user.id,
        window_start=datetime.utcnow() - timedelta(hours=2),
        request_count=25,
    )
    db.add(rl)
    db.commit()

    check_rate_limit(user.id, db)   # should reset, not raise
    db.refresh(rl)
    assert rl.request_count == 1
    db.close()


# ══════════════════════════════════════════════════════════════════════════
# WB-10  Chat route — mental mode triggers analyze_sentiment + ask_mental
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("Stay strong!", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEGATIVE", "score": 0.91})
def test_wb10_mental_mode_branch(mock_sentiment, mock_mental):
    resp = client.post("/api/auth/register", json={
        "full_name": "Mental WB10",
        "email": "mental.wb10@example.com",
        "phone": "9700000005",
        "password": "Password123"
    })
    token = resp.json().get("token")
    chat_resp = client.post("/api/chat", json={
        "mode": "mental", "message": "I feel very sad today."
    }, headers={"Authorization": f"Bearer {token}"})
    assert chat_resp.status_code == 200
    mock_sentiment.assert_called_once()
    mock_mental.assert_called_once()
    data = chat_resp.json()
    assert data["sentiment"] == {"label": "NEGATIVE", "score": 0.91}
    assert data["is_crisis"] is False


# ══════════════════════════════════════════════════════════════════════════
# WB-11  Chat route — legal mode triggers kb_query + ask_legal, no sentiment
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_legal", return_value=("Legal info here.", [{"source": "law.pdf", "text": "..."}]))
@patch("app.api_server.kb_query", return_value=[])
def test_wb11_legal_mode_branch(mock_kb, mock_legal):
    resp = client.post("/api/auth/register", json={
        "full_name": "Legal WB11",
        "email": "legal.wb11@example.com",
        "phone": "9700000006",
        "password": "Password123"
    })
    token = resp.json().get("token")
    chat_resp = client.post("/api/chat", json={
        "mode": "legal", "message": "What is bail?"
    }, headers={"Authorization": f"Bearer {token}"})
    assert chat_resp.status_code == 200
    mock_kb.assert_called_once()
    mock_legal.assert_called_once()
    data = chat_resp.json()
    assert data["sentiment"] is None   # legal mode returns no sentiment


# ══════════════════════════════════════════════════════════════════════════
# WB-12  Chat route — no conversation_id creates a new Conversation row
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", return_value=("New conv reply.", False))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEUTRAL", "score": 0.5})
def test_wb12_new_conversation_created(mock_sentiment, mock_mental):
    resp = client.post("/api/auth/register", json={
        "full_name": "Conv WB12",
        "email": "conv.wb12@example.com",
        "phone": "9700000007",
        "password": "Password123"
    })
    token = resp.json().get("token")
    chat_resp = client.post("/api/chat", json={
        "mode": "mental",
        "message": "Starting a new conversation here."
        # no conversation_id — new one should be created
    }, headers={"Authorization": f"Bearer {token}"})
    assert chat_resp.status_code == 200
    assert "conversation_id" in chat_resp.json()
    assert isinstance(chat_resp.json()["conversation_id"], int)


# ══════════════════════════════════════════════════════════════════════════
# WB-13  Chat route — ask_mental raises exception → fallback reply returned
# ══════════════════════════════════════════════════════════════════════════
@patch("app.api_server.ask_mental", side_effect=Exception("Gemini API down"))
@patch("app.api_server.analyze_sentiment", return_value={"label": "NEUTRAL", "score": 0.5})
def test_wb13_generation_exception_fallback(mock_sentiment, mock_mental):
    resp = client.post("/api/auth/register", json={
        "full_name": "Fallback WB13",
        "email": "fallback.wb13@example.com",
        "phone": "9700000008",
        "password": "Password123"
    })
    token = resp.json().get("token")
    chat_resp = client.post("/api/chat", json={
        "mode": "mental", "message": "This will trigger a failure."
    }, headers={"Authorization": f"Bearer {token}"})
    assert chat_resp.status_code == 200
    reply = chat_resp.json().get("reply", "")
    assert "sorry" in reply.lower() or "could not" in reply.lower()


# ══════════════════════════════════════════════════════════════════════════
# WB-14  init_db — creates data/ directory if missing (SQLite branch)
# ══════════════════════════════════════════════════════════════════════════
def test_wb14_init_db_creates_directory():
    from app.db import init_db
    init_db()   # safe to call multiple times
    assert os.path.exists("data")


# ══════════════════════════════════════════════════════════════════════════
# WB-15  ping_db — valid connection returns True
# ══════════════════════════════════════════════════════════════════════════
def test_wb15_ping_db_returns_true():
    from app.db import ping_db
    result = ping_db()
    assert result is True