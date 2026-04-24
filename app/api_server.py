import hashlib
import hmac
import logging
import os
import re
import secrets
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator

load_dotenv()

from app.api_client import ask_legal, ask_mental
from app.db import AuthUser, Conversation, Message, RateLimit, SessionLocal, User, init_db, ping_db
from app.sentiment import analyze_sentiment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from app.retrieval import ingest_folder, query as kb_query
    HAS_RETRIEVAL = True
except Exception as e:
    logger.warning(f"Retrieval not available: {e}")
    ingest_folder = None
    kb_query = None
    HAS_RETRIEVAL = False

try:
    from app.rewards import compute_session_reward
    HAS_REWARDS = True
except Exception:
    HAS_REWARDS = False

SELECTED_MODEL = os.getenv("MODEL_NAME", "models/gemini-2.5-flash")
KB_FOLDER = os.path.join("data", "kb_docs")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "30"))
RATE_LIMIT_WINDOW_MINUTES = int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "60"))
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

os.makedirs(KB_FOLDER, exist_ok=True)

try:
    init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.error(f"Database init failed: {e}")
    raise

app = FastAPI(title="AI Assistant API", version="2.0.0")

# ─── Global exception handlers — always return JSON ──────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {str(exc)}"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    return JSONResponse(status_code=422, content={"detail": msg})

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    mode: Literal["mental", "legal"]
    message: str
    conversation_id: Optional[int] = None

    @validator("message")
    def message_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty.")
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message exceeds {MAX_MESSAGE_LENGTH} character limit.")
        return v


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    sentiment: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = []
    is_crisis: bool = False


class RewardRequest(BaseModel):
    conversation_id: int


class RegisterRequest(BaseModel):
    full_name: str
    phone: str
    email: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str
    phone: str
    new_password: str
    confirm_password: str


# ─── Auth Helpers ─────────────────────────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return raw.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


def get_current_user(authorization: Optional[str] = Header(None)) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid.")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    user_id = int(payload["sub"])
    db = SessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.id == user_id, AuthUser.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found or inactive.")
        return user
    finally:
        db.close()


def check_rate_limit(user_id: int, db) -> None:
    window_start = datetime.utcnow() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    rl = db.query(RateLimit).filter(RateLimit.auth_user_id == user_id).first()
    if not rl:
        db.add(RateLimit(auth_user_id=user_id, window_start=datetime.utcnow(), request_count=1))
        db.commit()
        return
    if rl.window_start < window_start:
        rl.window_start = datetime.utcnow()
        rl.request_count = 1
        db.commit()
        return
    if rl.request_count >= RATE_LIMIT_MAX:
        reset_in = int((rl.window_start + timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES) - datetime.utcnow()).total_seconds() / 60)
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Try again in ~{reset_in} minute(s).")
    rl.request_count += 1
    db.commit()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "db": ping_db(),
        "retrieval_enabled": HAS_RETRIEVAL,
        "rewards_enabled": HAS_REWARDS,
        "version": "2.0.0",
    }


@app.post("/api/db-init")
def db_init_route() -> Dict[str, Any]:
    """Force-create all tables. Safe to call multiple times."""
    try:
        init_db()
        return {"ok": True, "message": "All tables created/verified successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB init failed: {str(e)}")


@app.post("/api/auth/register")
def register(req: RegisterRequest) -> Dict[str, Any]:
    full_name = (req.full_name or "").strip()
    email = (req.email or "").strip().lower()
    phone = normalize_phone(req.phone)
    password = req.password or ""

    if not full_name or len(full_name) < 2:
        raise HTTPException(status_code=400, detail="Full name must be at least 2 characters.")
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Phone number must be exactly 10 digits.")
    if not re.match(r"^[\w.+-]+@[\w-]+\.[a-z]{2,}$", email):
        raise HTTPException(status_code=400, detail="A valid email is required.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    db = SessionLocal()
    try:
        if db.query(AuthUser).filter(AuthUser.email == email).first():
            raise HTTPException(status_code=409, detail="Email is already registered.")
        if db.query(AuthUser).filter(AuthUser.phone == phone).first():
            raise HTTPException(status_code=409, detail="Phone number is already registered.")

        salt = secrets.token_hex(16)
        user = AuthUser(
            full_name=full_name,
            phone=phone,
            email=email,
            password_hash=hash_password(password, salt),
            password_salt=salt,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_token(user.id, user.email)
        logger.info(f"New user registered: {email}")
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        db.close()


@app.post("/api/auth/login")
def login(req: LoginRequest) -> Dict[str, Any]:
    identifier = (req.identifier or "").strip().lower()
    password = req.password or ""
    if not identifier or not password:
        raise HTTPException(status_code=400, detail="Identifier and password are required.")

    db = SessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.email == identifier).first()
        if not user:
            phone = normalize_phone(identifier)
            user = db.query(AuthUser).filter(AuthUser.phone == phone).first()
        if not user or not verify_password(password, user.password_salt, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials.")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated.")

        token = create_token(user.id, user.email)
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
    finally:
        db.close()


@app.post("/api/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest) -> Dict[str, Any]:
    email = (req.email or "").strip().lower()
    phone = normalize_phone(req.phone)
    new_password = req.new_password or ""
    confirm = req.confirm_password or ""

    if not email or len(phone) != 10:
        raise HTTPException(status_code=400, detail="Email and 10-digit phone are required.")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
    if new_password != confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    db = SessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.email == email, AuthUser.phone == phone).first()
        if not user:
            raise HTTPException(status_code=404, detail="No user found with the provided email and phone.")
        salt = secrets.token_hex(16)
        user.password_salt = salt
        user.password_hash = hash_password(new_password, salt)
        db.commit()
        return {"ok": True, "message": "Password reset successful."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")
    finally:
        db.close()


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, current_user: AuthUser = Depends(get_current_user)) -> ChatResponse:
    db = SessionLocal()
    try:
        check_rate_limit(current_user.id, db)

        user = db.query(User).filter(User.username == current_user.full_name).first()
        if not user:
            user = User(username=current_user.full_name, email=current_user.email)
            db.add(user)
            db.commit()
            db.refresh(user)

        conv = None
        if req.conversation_id:
            conv = db.query(Conversation).filter(
                Conversation.id == req.conversation_id,
                Conversation.user_id == user.id,
            ).first()

        if not conv:
            conv = Conversation(
                user_id=user.id,
                section=req.mode,
                title=req.message[:60] + ("..." if len(req.message) > 60 else ""),
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        db.add(Message(conversation_id=conv.id, sender="user", text=req.message, sentiment=None))
        db.commit()

        sentiment = None
        if req.mode == "mental":
            try:
                sentiment = analyze_sentiment(req.message)
            except Exception:
                sentiment = None

        sources: List[Dict[str, Any]] = []
        is_crisis = False
        try:
            if req.mode == "mental":
                reply, is_crisis = ask_mental(req.message, sentiment, model_name=SELECTED_MODEL)
            else:
                retrieved = []
                if kb_query:
                    try:
                        retrieved = kb_query(req.message, k=5)
                    except Exception:
                        retrieved = []
                reply, sources = ask_legal(req.message, retrieved_passages=retrieved, model_name=SELECTED_MODEL)
        except Exception as e:
            logger.error(f"Generation error: {traceback.format_exc()}")
            reply = "Sorry, I could not generate a response right now. Please try again."
            sources = []

        db.add(Message(
            conversation_id=conv.id,
            sender="bot",
            text=reply,
            sentiment=sentiment if req.mode == "mental" else None,
            is_crisis=is_crisis,
        ))
        db.commit()

        return ChatResponse(
            conversation_id=conv.id,
            reply=reply,
            sentiment=sentiment,
            sources=sources,
            is_crisis=is_crisis,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Chat error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
    finally:
        db.close()


@app.get("/api/conversations")
def list_conversations(current_user: AuthUser = Depends(get_current_user)) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == current_user.full_name).first()
        if not user:
            return {"conversations": []}
        convs = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(50)
            .all()
        )
        return {
            "conversations": [
                {
                    "id": c.id,
                    "section": c.section,
                    "title": c.title or f"Conversation #{c.id}",
                    "created_at": str(c.created_at),
                }
                for c in convs
            ]
        }
    finally:
        db.close()


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: int,
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == current_user.full_name).first()
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        if user and conv.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied.")
        msgs = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.id.asc())
            .all()
        )
        return {
            "conversation_id": conv.id,
            "mode": conv.section,
            "title": conv.title or f"Conversation #{conv.id}",
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "text": m.text,
                    "sentiment": m.sentiment,
                    "is_crisis": m.is_crisis,
                    "created_at": str(m.created_at),
                }
                for m in msgs
            ],
        }
    finally:
        db.close()


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == current_user.full_name).first()
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        if user and conv.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied.")
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
        db.delete(conv)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/session/reward")
def session_reward(
    req: RewardRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    if not HAS_REWARDS:
        raise HTTPException(status_code=501, detail="Rewards feature is not available.")
    db = SessionLocal()
    try:
        conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        msgs = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.id.asc()).all()
        reward = compute_session_reward(conv.id, [{"sender": m.sender, "text": m.text} for m in msgs])
        return reward
    finally:
        db.close()


@app.post("/api/kb/upload")
async def upload_kb(
    files: List[UploadFile] = File(...),
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    saved = []
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    for f in files:
        if not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in {"txt", "pdf"}:
            continue
        content = await f.read()
        if len(content) > max_bytes:
            continue
        target = os.path.join(KB_FOLDER, f.filename)
        base, ext_dot = os.path.splitext(target)
        i = 1
        while os.path.exists(target):
            target = f"{base}_{i}{ext_dot}"
            i += 1
        with open(target, "wb") as out:
            out.write(content)
        saved.append(os.path.basename(target))
    return {"saved_files": saved, "count": len(saved)}


@app.post("/api/kb/ingest")
def ingest_kb(current_user: AuthUser = Depends(get_current_user)) -> Dict[str, Any]:
    if not HAS_RETRIEVAL or not ingest_folder:
        raise HTTPException(status_code=501, detail="Retrieval ingestion is not available.")
    try:
        chunks = ingest_folder(KB_FOLDER)
        return {"ok": True, "chunks": chunks}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if os.path.isdir(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
def root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found.")
