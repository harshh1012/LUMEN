# backend/legal_rag.py

import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


VECTOR_DB_PATH = "./vector_store"
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"


def load_vector_db():
    """Load vector store."""
    embedding = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

    db = Chroma(
        persist_directory=VECTOR_DB_PATH,
        embedding_function=embedding
    )
    return db


def load_llm():
    """Load Groq model."""
    llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
    temperature=0.1,
    )
    return llm


def answer_legal_query(query: str) -> str:
    """Main RAG answer function."""
    try:
        db = load_vector_db()
        retriever = db.as_retriever(search_kwargs={"k": 3})
        llm = load_llm()

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )

        result = qa_chain.invoke({"query": query})
        answer = result.get("result", "No answer found.")

        return answer

    except Exception as e:
        return f"Error in Legal RAG Pipeline: {str(e)}"
