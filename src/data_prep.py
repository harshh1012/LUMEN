# src/data_prep.py

import os
from tqdm import tqdm
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
from src.utils import ensure_dir


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def clean_text(text: str) -> str:
    """Clean unwanted formatting from extracted text."""
    text = text.replace('\n', ' ')
    text = ' '.join(text.split())  # remove multiple spaces
    return text


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150):
    """Split text into overlapping chunks for embeddings."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    chunks = splitter.split_text(text)
    return chunks


def process_pdfs(raw_dir: str = "./data/raw", processed_dir: str = "./data/processed"):
    """Extract, clean, and chunk all PDFs from raw_dir, save to processed_dir."""
    ensure_dir(processed_dir)
    all_docs = []

    pdf_files = [f for f in os.listdir(raw_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("⚠️  No PDF files found in /data/raw/")
        return

    for file in tqdm(pdf_files, desc="Processing PDFs"):
        path = os.path.join(raw_dir, file)
        text = extract_text_from_pdf(path)
        cleaned = clean_text(text)
        chunks = chunk_text(cleaned)

        out_file = os.path.join(processed_dir, f"{os.path.splitext(file)[0]}_chunks.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(chunk + "\n---\n")

        all_docs.append({
            "source": file,
            "num_chunks": len(chunks),
        })

    print(f"✅ Processed {len(pdf_files)} PDFs and saved chunks to {processed_dir}")
    return all_docs


if __name__ == "__main__":
    process_pdfs()
