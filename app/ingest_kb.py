"""
CLI to ingest .txt and .pdf docs under data/kb_docs/ into FAISS.

Usage:
    python -m app.ingest_kb
"""
if __name__ == "__main__":
    from app.retrieval import ingest_folder
    n = ingest_folder("data/kb_docs")
    print("Ingestion complete. Total chunks:", n)
