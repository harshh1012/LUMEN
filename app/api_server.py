import hashlib
import hmac
import os
import re
import secrets
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api_client import ask_legal, ask_mental
from app.db import AuthUser, Conversation, Message, SessionLocal, User, init_db
from app.sentiment import analyze_sentiment

try:
    from app.retrieval import ingest_folder, query as kb_query

    HAS_RETRIEVAL = True
except Exception:
    ingest_folder = None
    kb_query = None
    HAS_RETRIEVAL = False

try:
    from app.rewards import compute_session_reward

    HAS_REWARDS = True
except Exception:
    HAS_REWARDS = False

load_dotenv()

SELECTED_MODEL = "models/gemini-2.5-flash"
KB_FOLDER = os.path.join("data", "kb_docs")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

os.makedirs(KB_FOLDER, exist_ok=True)
init_db()

app = FastAPI(title="AI Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    mode: Literal["mental", "legal"]
    message: str
    username: Optional[str] = None
    conversation_id: Optional[int] = None
    auth_user_id: Optional[int] = None


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    sentiment: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = []


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


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return raw.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "retrieval_enabled": HAS_RETRIEVAL,
        "rewards_enabled": HAS_REWARDS,
    }


@app.post("/api/auth/register")
def register(req: RegisterRequest) -> Dict[str, Any]:
    full_name = (req.full_name or "").strip()
    email = (req.email or "").strip().lower()
    phone = normalize_phone(req.phone)
    password = req.password or ""

    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required.")
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Phone number must be exactly 10 digits.")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    db = SessionLocal()
    try:
        exists_email = db.query(AuthUser).filter(AuthUser.email == email).first()
        if exists_email:
            raise HTTPException(status_code=409, detail="Email is already registered.")
        exists_phone = db.query(AuthUser).filter(AuthUser.phone == phone).first()
        if exists_phone:
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

        return {
            "ok": True,
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
            },
        }
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

        return {
            "ok": True,
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
            },
        }
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
    finally:
        db.close()


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    db = SessionLocal()
    try:
        user = None
        auth_user = None
        if req.auth_user_id:
            auth_user = db.query(AuthUser).filter(AuthUser.id == req.auth_user_id).first()
            if not auth_user:
                raise HTTPException(status_code=401, detail="Invalid authenticated user.")

        username_value = req.username
        if not username_value and auth_user:
            username_value = auth_user.full_name

        if username_value:
            user = db.query(User).filter(User.username == username_value).first()
            if not user:
                user = User(username=username_value, email=(auth_user.email if auth_user else None))
                db.add(user)
                db.commit()
                db.refresh(user)

        conv = None
        if req.conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()

        if not conv:
            conv = Conversation(
                user_id=(user.id if user else None),
                section=req.mode,
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
        try:
            if req.mode == "mental":
                reply = ask_mental(req.message, sentiment, model_name=SELECTED_MODEL)
            else:
                retrieved = []
                if kb_query:
                    try:
                        retrieved = kb_query(req.message, k=5)
                    except Exception:
                        retrieved = []
                reply, sources = ask_legal(req.message, retrieved_passages=retrieved, model_name=SELECTED_MODEL)
        except Exception:
            reply = "Sorry, I could not generate a response right now. Please try again."
            sources = []

        db.add(
            Message(
                conversation_id=conv.id,
                sender="bot",
                text=reply,
                sentiment=(sentiment if req.mode == "mental" else None),
            )
        )
        db.commit()

        return ChatResponse(
            conversation_id=conv.id,
            reply=reply,
            sentiment=sentiment,
            sources=sources,
        )
    finally:
        db.close()


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        msgs = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.id.asc())
            .all()
        )
        return {
            "conversation_id": conv.id,
            "mode": conv.section,
            "messages": [
                {"id": m.id, "sender": m.sender, "text": m.text, "created_at": str(m.created_at)}
                for m in msgs
            ],
        }
    finally:
        db.close()


@app.post("/api/session/reward")
def session_reward(req: RewardRequest) -> Dict[str, Any]:
    if not HAS_REWARDS:
        raise HTTPException(status_code=501, detail="Rewards feature is not available.")

    db = SessionLocal()
    try:
        conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        msgs = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.id.asc())
            .all()
        )
        serial_msgs = [{"sender": m.sender, "text": m.text} for m in msgs]
        reward = compute_session_reward(conv.id, serial_msgs)
        return reward
    finally:
        db.close()


@app.post("/api/kb/upload")
async def upload_kb(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    saved = []
    for f in files:
        if not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in {"txt", "pdf"}:
            continue
        target = os.path.join(KB_FOLDER, f.filename)
        base, ext_with_dot = os.path.splitext(target)
        i = 1
        while os.path.exists(target):
            target = f"{base}_{i}{ext_with_dot}"
            i += 1

        content = await f.read()
        with open(target, "wb") as out:
            out.write(content)
        saved.append(os.path.basename(target))

    return {"saved_files": saved, "count": len(saved)}


@app.post("/api/kb/ingest")
def ingest_kb() -> Dict[str, Any]:
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
def root() -> FileResponse:
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found.")
