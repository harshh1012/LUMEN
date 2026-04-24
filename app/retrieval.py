# app/retrieval.py  (OpenAI embeddings + cosine similarity)
import os
import json
import pdfplumber
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.embeddings import embed_texts

INDEX_EMBED_PATH = "data/embeddings.npy"
INDEX_META_PATH = "data/embeddings_meta.json"


def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text() or ""
            text += extracted + "\n"
    return text


def chunk_text(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        start = end - overlap
        if start < 0:
            start = 0
        if end == length:
            break
    return chunks


def ingest_folder(folder="data/kb_docs", batch_size=16):
    """
    Read .txt and .pdf files from `folder`, chunk them, create embeddings using embed_texts(),
    and save embeddings + metadata to disk.
    """
    os.makedirs("data", exist_ok=True)

    texts = []
    metas = []

    if not os.path.exists(folder):
        raise FileNotFoundError(f"{folder} not found. Create it and add .txt/.pdf files.")

    for fname in sorted(os.listdir(folder)):
        path = os.path.join(folder, fname)
        if not os.path.isfile(path):
            continue
        ext = fname.rsplit(".", 1)[-1].lower()
        if ext == "txt":
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        elif ext == "pdf":
            content = extract_text_from_pdf(path)
        else:
            # skip other file types
            continue

        # chunk content and store
        chunks = chunk_text(content)
        for i, c in enumerate(chunks):
            texts.append(c)
            metas.append({"source": fname, "chunk": i, "text": c[:400]})

    if not texts:
        raise ValueError("No .txt or .pdf files found in data/kb_docs/ — add docs before ingestion.")

    print(f"Creating embeddings for {len(texts)} chunks (calls OpenAI Embeddings API)...")

    # embed in batches
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vecs = embed_texts(batch)  # must return list[list[float]]
        if not isinstance(vecs, (list, tuple)) or len(vecs) != len(batch):
            raise RuntimeError("embed_texts() did not return expected list of embeddings for the batch")
        all_vecs.extend(vecs)

    embeddings = np.array(all_vecs, dtype="float32")

    # save embeddings and metadata
    np.save(INDEX_EMBED_PATH, embeddings)
    with open(INDEX_META_PATH, "w", encoding="utf-8") as f:
        json.dump({"metas": metas}, f, ensure_ascii=False, indent=2)

    print(f"Saved {embeddings.shape[0]} embeddings to {INDEX_EMBED_PATH} and metadata to {INDEX_META_PATH}.")
    return len(texts)


def query(q, k=5):
    """
    Query the saved embeddings. Returns a list of metadata dicts with 'score' keys.
    """
    if not os.path.exists(INDEX_EMBED_PATH) or not os.path.exists(INDEX_META_PATH):
        raise FileNotFoundError("Embeddings or metadata not found. Run ingest_folder() before querying.")

    embeddings = np.load(INDEX_EMBED_PATH)
    with open(INDEX_META_PATH, "r", encoding="utf-8") as f:
        metas = json.load(f).get("metas", [])

    # get query vector (embed_texts should return a list)
    q_vec = embed_texts([q])[0]
    sims = cosine_similarity([q_vec], embeddings)[0]

    top_idx = sims.argsort()[::-1][:k]
    results = []
    for i in top_idx:
        m = metas[i].copy()
        m["score"] = float(sims[i])
        results.append(m)
    return results
