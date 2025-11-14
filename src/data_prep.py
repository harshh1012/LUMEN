# src/data_prep.py

import os
import re
import json
import pandas as pd
from tqdm import tqdm
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.utils import ensure_dir


# ---------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
        except Exception as e:
            print(f"⚠️ Skipping page {page_num} in {pdf_path}: {e}")

    return text


# ---------------------------------------------
# CLEAN TEXT
# ---------------------------------------------
def clean_text(text: str) -> str:
    """Basic cleaning and formatting."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"–", "-", text)
    text = re.sub(r"Page \d+", "", text)
    return text.strip()


# ---------------------------------------------
# CHUNK TEXT
# ---------------------------------------------
def chunk_text(text: str, file_name: str, chunk_size: int = 800, overlap: int = 150):
    """Split text into overlapping chunks."""
    # Special chunking rules for Constitution of India
    if "constitution" in file_name.lower():
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["Article", "ARTICLE", "Part", "PART", "Schedule", "SCHEDULE"]
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap
        )

    return splitter.split_text(text)


# ---------------------------------------------
# PROCESS CSV
# ---------------------------------------------
def process_csv(csv_path: str, processed_dir: str = "./data/processed"):
    """Process a CSV file and convert rows into chunked JSONs."""
    ensure_dir(processed_dir)

    df = pd.read_csv(csv_path)

    # Determine the text column automatically
    text_column = None
    for col in df.columns:
        if col.lower() in ["text", "content", "body", "description"]:
            text_column = col
            break

    # If no text column found, merge all text-like columns
    if text_column is None:
        df["content"] = df.apply(
            lambda r: " ".join([str(x) for x in r.values if isinstance(x, str)]),
            axis=1
        )
        text_column = "content"

    rows = df.to_dict("records")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    all_chunks = []
    chunk_id = 1

    for row in rows:
        text = str(row[text_column])
        chunks = splitter.split_text(text)

        for chunk in chunks:
            all_chunks.append({
                "source": os.path.basename(csv_path),
                "chunk_id": chunk_id,
                "content": chunk
            })
            chunk_id += 1

    out_file = os.path.join(processed_dir, "csv_chunks.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"✅ CSV processed → {out_file} ({len(all_chunks)} chunks)")
    return len(all_chunks)


# ---------------------------------------------
# PROCESS PDFs
# ---------------------------------------------
def process_pdfs(raw_dir: str = "./data/raw", processed_dir: str = "./data/processed"):
    ensure_dir(processed_dir)

    pdf_files = [f for f in os.listdir(raw_dir) if f.lower().endswith(".pdf")]
    all_docs = []

    if not pdf_files:
        print("⚠️ No PDF files found.")
        return 0

    for file in tqdm(pdf_files, desc="Processing PDFs"):
        path = os.path.join(raw_dir, file)
        text = extract_text_from_pdf(path)
        cleaned = clean_text(text)
        chunks = chunk_text(cleaned, file)

        structured_chunks = [
            {"source": file, "chunk_id": i + 1, "content": chunk}
            for i, chunk in enumerate(chunks)
        ]

        out_file = os.path.join(processed_dir, f"{os.path.splitext(file)[0]}_chunks.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(structured_chunks, f, indent=2, ensure_ascii=False)

        print(f"📄 Processed {file}: {len(chunks)} chunks → {out_file}")
        all_docs.append({"file": file, "chunks": len(chunks)})

    return all_docs


# ---------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------
def process_all(raw_dir="./data/raw", processed_dir="./data/processed"):
    ensure_dir(processed_dir)

    print("\n===== Starting Data Processing =====")

    # Process PDFs
    pdf_info = process_pdfs(raw_dir, processed_dir)

    # Process CSVs
    csv_files = [f for f in os.listdir(raw_dir) if f.lower().endswith(".csv")]
    csv_chunks_total = 0

    for file in csv_files:
        csv_chunks_total += process_csv(os.path.join(raw_dir, file), processed_dir)

    print("\n===== Processing Completed =====")
    print(f"PDFs processed: {len(pdf_info) if pdf_info else 0}")
    print(f"CSV chunks generated: {csv_chunks_total}")

    return {
        "pdfs_processed": len(pdf_info) if pdf_info else 0,
        "csv_chunks": csv_chunks_total
    }


if __name__ == "__main__":
    process_all()
