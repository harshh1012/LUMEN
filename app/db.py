import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SQLITE_URL = "sqlite:///./data/kb.sqlite"
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SUPABASE_DB_URL")
    or DEFAULT_SQLITE_URL
)
LOCAL_DB_FALLBACK_URL = os.getenv("LOCAL_DB_FALLBACK_URL", DEFAULT_SQLITE_URL)
ALLOW_DB_FALLBACK = os.getenv("ALLOW_DB_FALLBACK", "true").lower() not in {"0", "false", "no"}

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")
if (not is_sqlite) and ("supabase.co" in DATABASE_URL) and ("sslmode=" not in DATABASE_URL):
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

# Build engine kwargs based on DB type
def make_engine():
    url = DATABASE_URL

    if "sqlite" in url:
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
        )

    # PostgreSQL / Supabase — SSL is already in the URL (?sslmode=require)
    # pool_pre_ping ensures dropped connections are detected and recycled
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "connect_timeout": 10,
            "options": "-c timezone=utc",
        },
    )

engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def _using_sqlite(url=None):
    return (url or DATABASE_URL).startswith("sqlite")


def _db_label(url=None):
    url = url or DATABASE_URL
    return "PostgreSQL (Supabase)" if "supabase" in url else url


def _switch_to_local_db(reason):
    global DATABASE_URL, engine, SessionLocal, is_sqlite

    if not ALLOW_DB_FALLBACK or _using_sqlite() or not LOCAL_DB_FALLBACK_URL:
        raise reason

    original_url = DATABASE_URL
    DATABASE_URL = LOCAL_DB_FALLBACK_URL
    is_sqlite = _using_sqlite()
    os.makedirs("data", exist_ok=True)
    engine.dispose()
    engine = make_engine()
    SessionLocal.configure(bind=engine)
    print(f"[DB] Remote database unavailable ({reason}). Falling back to {DATABASE_URL}.")
    print(f"[DB] Original database was: {_db_label(original_url)}")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    section = Column(String)       # mental or legal
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    messages = relationship("Message", back_populates="conversation", order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    sender = Column(String)        # user or bot
    text = Column(Text)
    sentiment = Column(JSON)
    is_crisis = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True)
    auth_user_id = Column(Integer, ForeignKey("auth_users.id"))
    window_start = Column(DateTime, default=datetime.utcnow)
    request_count = Column(Integer, default=0)


def init_db():
    # For PostgreSQL, ensure the data folder isn't needed
    if _using_sqlite():
        os.makedirs("data", exist_ok=True)
    try:
        Base.metadata.create_all(engine)
    except OperationalError as exc:
        _switch_to_local_db(exc)
        Base.metadata.create_all(engine)
    print(f"[DB] Connected to: {_db_label()}")

def ping_db():
    """Check if database connection is alive."""
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        db.close()
