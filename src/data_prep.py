# src/data_prep.py

import os
import re
import json
from tqdm import tqdm
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from src.utils import ensure_dir


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
        except Exception as e:
            print(f" Skipping page {page_num} in {pdf_path}: {e}")
    return text


def clean_text(text: str) -> str:
    """Clean unwanted formatting from text."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'–', '-', text)
    text = re.sub(r'Page \d+', '', text)
    return text.strip()


def chunk_text(text: str, file_name: str, chunk_size: int = 800, overlap: int = 150):
    """Split text into overlapping chunks ."""
    if "constitution" in file_name.lower():
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=100, separators=["Article", "PART", "SCHEDULE"]
        )
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_text(text)


def process_pdfs(raw_dir: str = "./data/raw", processed_dir: str = "./data/processed"):
    """Extract, clean, and chunk all PDFs from raw_dir, save to processed_dir."""
    ensure_dir(processed_dir)
    all_docs = []

    pdf_files = [f for f in os.listdir(raw_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(" No PDF files found in /data/raw/")
        return

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

        all_docs.append({
            "file": file,
            "num_chunks": len(chunks)
        })
        print(f"Processed {file}: {len(chunks)} chunks saved → {out_file}")

    print(f"\n Total PDFs processed: {len(pdf_files)}")
    for doc in all_docs:
        print(f"  - {doc['file']} → {doc['num_chunks']} chunks")

    return {"processed_files": len(pdf_files), "details": all_docs}


if __name__ == "__main__":
    process_pdfs()
