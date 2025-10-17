# src/retriever.py

import os
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings



def load_vector_store(persist_dir="./vector_store", model_name="all-mpnet-base-v2"):
    """Load the persisted Chroma vector store with HuggingFace embeddings."""

    if not os.path.exists(persist_dir):
        raise FileNotFoundError(f" Vector store not found at: {persist_dir}\nRun embedder.py first!")

    print(f" Loading Chroma vector store from {persist_dir}")

    embedding = HuggingFaceEmbeddings(model_name=model_name)
    db = Chroma(persist_directory=persist_dir, embedding_function=embedding)
    print(" Vector store loaded successfully.")
    return db


def retrieve_top_k(query: str, k: int = 3):
    """Retrieve top-k most relevant legal text chunks for a given query."""
    db = load_vector_store()
    print(f"\n Query: {query}")
    results = db.similarity_search(query, k=k)

    if not results:
        print(" No relevant results found.")
        return []

    print(f"\n Top {k} results:")
    for i, res in enumerate(results, 1):
        print(f"\n🔹 Result {i}")
        print("Source:", res.metadata.get("source", "Unknown"))
        print("Chunk ID:", res.metadata.get("chunk_id", "N/A"))
        print("Text Snippet:", res.page_content[:400], "...")
    return results


if __name__ == "__main__":
    # Example interactive usage
    query = input(" Enter your legal query: ")
    retrieve_top_k(query, k=3)
