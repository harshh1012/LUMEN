# src/embedder.py

import os
import json
from tqdm import tqdm
from langchain_community.vectorstores import Chroma
from langchain.docstore.document import Document
from src.utils import ensure_dir
from langchain_huggingface import HuggingFaceEmbeddings




def get_embedding_model(model_name="all-mpnet-base-v2"):
    """
    Load the embedding model from Hugging Face.
    Uses Sentence Transformers via LangChain wrapper.
    """
    print(f"🔢 Loading embedding model: {model_name}")
    model_kwargs = {"device": "cpu"}  # change to "cuda" if GPU available
    encode_kwargs = {"normalize_embeddings": True}
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )


def load_processed_docs(processed_dir="./data/processed"):
    """
    Load structured JSON chunked files and convert them to LangChain Document objects.
    Each JSON file contains a list of dicts with 'source', 'chunk_id', and 'content'.
    """
    docs = []
    files = [f for f in os.listdir(processed_dir) if f.endswith("_chunks.json")]

    if not files:
        print("No processed JSON files found in /data/processed/. Run data_prep.py first.")
        return docs

    print(f" Found {len(files)} processed JSON files")
    for file in tqdm(files, desc="Loading processed documents"):
        path = os.path.join(processed_dir, file)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            content = item.get("content", "").strip()
            if not content:
                continue
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": item.get("source", file),
                        "chunk_id": item.get("chunk_id", None),
                    },
                )
            )

    print(f" Loaded {len(docs)} document chunks from JSON files")
    return docs


def build_vector_store(
    processed_dir="./data/processed",
    persist_dir="./vector_store",
    model_name="all-mpnet-base-v2",
):
    """
    Create embeddings for all processed chunks and store them in a persistent Chroma DB.
    """
    ensure_dir(persist_dir)

    # Step 1: Load documents
    docs = load_processed_docs(processed_dir)
    if not docs:
        print(" No documents loaded. Aborting vector store creation.")
        return None

    # Step 2: Initialize embedding model
    embedding = get_embedding_model(model_name)

    # Step 3: Create or update Chroma vector store
    print(" Building Chroma vector database...")
    vector_store = Chroma.from_documents(docs, embedding, persist_directory=persist_dir)

    # Step 4: Save to disk
    vector_store.persist()
    print(f" Vector store saved successfully to: {persist_dir}")
    print(f" Total chunks embedded: {len(docs)}")
    return vector_store


if __name__ == "__main__":
    build_vector_store()
