# app/streamlit_app.py

# --- ensure project root is importable (fixes ModuleNotFoundError when Streamlit runs) ---
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ---------------------------------------------------------------------

import traceback
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

# app internals
from app.db import init_db, SessionLocal, User, Conversation, Message
from app.sentiment import analyze_sentiment
from app.api_client import ask_mental, ask_legal

# optional retrieval (ingest + query)
try:
    from app.retrieval import ingest_folder, query as kb_query
    HAS_RETRIEVAL = True
except Exception:
    ingest_folder = None
    kb_query = None
    HAS_RETRIEVAL = False

# ensure kb folder
KB_FOLDER = os.path.join("data", "kb_docs")
os.makedirs(KB_FOLDER, exist_ok=True)

# init DB
init_db()

# Streamlit setup
st.set_page_config(page_title="AI Smart Companion", layout="wide")
st.title("AI Smart Companion")

# Sidebar: mode, user, model selector, KB upload
section = st.sidebar.radio("Mode", ["Mental Health", "Legal Assistance"], index=0)
username = st.sidebar.text_input("Your name (optional)")

st.sidebar.markdown("---")
st.sidebar.markdown("### Model (chat-capable)")

# Model selector: list models but filter out embedding/image/tts models
selected_model = None
try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    models = genai.list_models()
    allowed = []
    for m in models:
        n = m.name.lower()
        if ("embedding" in n) or ("imagen" in n) or ("veo" in n) or ("tts" in n) or ("live" in n):
            continue
        allowed.append(m.name)
    if not allowed:
        allowed = [os.getenv("MODEL_NAME", "models/gemini-2.5-flash")]
    selected_model = st.sidebar.selectbox("Model", allowed, index=0, key="model_select")
except Exception:
    selected_model = st.sidebar.text_input("Model name", value=os.getenv("MODEL_NAME", "models/gemini-2.5-flash"), key="model_input")

st.sidebar.markdown("---")
st.sidebar.markdown("### Knowledge base (legal)")

uploaded_files = st.sidebar.file_uploader("Upload PDFs / TXT", type=["pdf", "txt"], accept_multiple_files=True, key="upload_kb")
if uploaded_files and st.sidebar.button("Save files to KB", key="save_kb"):
    saved = []
    for f in uploaded_files:
        target = os.path.join(KB_FOLDER, f.name)
        base, ext = os.path.splitext(target)
        i = 1
        while os.path.exists(target):
            target = f"{base}_{i}{ext}"
            i += 1
        with open(target, "wb") as out:
            out.write(f.getbuffer())
        saved.append(os.path.basename(target))
    st.sidebar.success(f"Saved {len(saved)} files.")
    st.sidebar.write(saved)

if HAS_RETRIEVAL:
    if st.sidebar.button("Ingest KB now", key="ingest_kb"):
        try:
            with st.spinner("Ingesting documents and creating embeddings..."):
                count = ingest_folder(KB_FOLDER)
            st.sidebar.success(f"Ingested {count} chunks.")
        except Exception:
            st.sidebar.error("Ingest failed — see traceback.")
            st.sidebar.code(traceback.format_exc())
else:
    st.sidebar.info("Retrieval (KB) not available.")

st.sidebar.markdown("---")
st.sidebar.markdown("Tip: Use 'Start New Chat' to begin a fresh conversation and clear the active chat session.")

# --- Conversation state management ---
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# New chat button
if st.sidebar.button("Start New Chat", key="start_new_chat"):
    st.session_state.conversation_id = None
    st.experimental_rerun()

# Chat input UI
st.markdown("---")
st.header("Chat with your assistant")
user_msg = st.text_area("Your message...", height=160, key="main_input")
send_clicked = st.button("Send", key="send_main")

# Sending logic — ensure single insertion of user message and single assistant reply
if send_clicked and user_msg.strip():
    db = SessionLocal()

    # create/find user (optional)
    user = None
    if username:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(username=username)
            db.add(user)
            db.commit()
            db.refresh(user)

    # get or create conversation
    conv = None
    if st.session_state.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == st.session_state.conversation_id).first()

    if not conv:
        conv = Conversation(
            user_id=(user.id if user else None),
            section=("mental" if section == "Mental Health" else "legal")
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        st.session_state.conversation_id = conv.id

    # Save user message ONCE
    user_message_obj = Message(conversation_id=conv.id, sender="user", text=user_msg, sentiment=None)
    db.add(user_message_obj)
    db.commit()
    db.refresh(user_message_obj)

    # Analyze sentiment only for mental health
    sentiment = analyze_sentiment(user_msg) if section == "Mental Health" else None

    # Generate reply with spinner; ensure one assistant message saved even on error
    with st.spinner("Assistant is typing..."):
        try:
            if section == "Mental Health":
                reply = ask_mental(user_msg, sentiment, model_name=selected_model)
                sources = []
            else:
                retrieved = []
                if kb_query:
                    try:
                        retrieved = kb_query(user_msg, k=5)
                    except Exception:
                        retrieved = []
                reply, sources = ask_legal(user_msg, retrieved_passages=retrieved, model_name=selected_model)

        except Exception as e:
            # log and produce friendly fallback reply
            print("Generation error:", e)
            reply = "Sorry — I couldn't generate a response right now. Please try again or choose another model."
            sources = []

        # Save assistant reply ONCE
        bot_message_obj = Message(conversation_id=conv.id, sender="bot", text=reply, sentiment=(sentiment if section == "Mental Health" else None))
        db.add(bot_message_obj)
        db.commit()
        db.refresh(bot_message_obj)

    # show assistant reply immediately
    st.markdown("### Assistant:")
    st.write(reply)

    if section == "Legal Assistance" and sources:
        st.markdown("**Sources (top results):**")
        for s in sources:
            st.write(f"- {s.get('source')}  (score={s.get('score', 0):.3f})")
            st.write(s.get('text', '')[:400] + ("..." if len(s.get('text',''))>400 else ""))

# --- Conversation history rendering (ordered by id to avoid timestamp issues) ---
if st.session_state.conversation_id:
    st.markdown("---")
    st.subheader("Conversation history")
    db = SessionLocal()
    conv = db.query(Conversation).filter(Conversation.id == st.session_state.conversation_id).first()
    if conv:
        msgs = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.id.asc()).all()
        for m in msgs:
            if m.sender == "user":
                st.markdown(
                    f"<div style='background:#DCF8C6;padding:12px;border-radius:12px;max-width:75%;margin-left:auto;margin-bottom:8px'>{m.text}</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div style='background:#F1F0F0;color:#111;padding:12px;border-radius:12px;max-width:75%;margin-right:auto;margin-bottom:8px'>{m.text}</div>",
                    unsafe_allow_html=True
                )
