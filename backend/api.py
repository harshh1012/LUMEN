# backend/api.py

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from backend.legal_rag import answer_legal_query
from backend.mental_bot import mental_response


app = FastAPI(
    title="LUMEN Backend",
    description="Unified API for Legal RAG Assistant & Mental Health Support",
    version="1.0"
)

# Allow Streamlit frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    query: str
    mode: str  # "legal" or "mental"


@app.post("/chat")
async def chat(data: Query):
    """Main unified endpoint."""
    if data.mode == "legal":
        response = answer_legal_query(data.query)
        return {"answer": response}

    elif data.mode == "mental":
        response = mental_response(data.query)
        return {"answer": response}

    return {"answer": "Invalid mode selected."}
