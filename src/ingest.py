"""
ingest.py - Reads PDFs, splits them into small pieces (chunks),
tags metadata (permissions & dates), converts text to vectors (embeddings),
and saves everything in Chroma DB.

"""

import sys
import os

# Fix for Windows command prompt so it doesn't crash on special characters
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector

# Database connection
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pass@localhost:5432/postgres")
CONN = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1) if DB_URL.startswith("postgresql://") else DB_URL

# ---------------------------------------------------------------------------
# 1. Document Registry
# Here we define the "rules" and "permissions" for each PDF.
# - access_level: 1 = Student, 2 = Professor, 3 = Admin
# - doc_family: groups different versions of the same policy together
# - effective_date: used to determine which document is the newest
# ---------------------------------------------------------------------------
REGISTRY = {
    "student_handbook.pdf": dict(
        doc_name="Student Handbook",
        doc_family="handbook",
        effective_date="2024-08-01",
        access_level=1,  # Everyone (students, faculty, admin)
    ),
    "attendance_2023.pdf": dict(
        doc_name="Attendance Policy 2023",
        doc_family="attendance",
        effective_date="2023-01-01",
        access_level=1,  # Superseded, hidden by is_current=False
    ),
    "attendance_2025.pdf": dict(
        doc_name="Attendance Policy 2025",
        doc_family="attendance",
        effective_date="2025-01-01",
        access_level=1,  # Current attendance policy
    ),
    "fee_structure.pdf": dict(
        doc_name="Fee Structure",
        doc_family="fee",
        effective_date="2024-07-01",
        access_level=1,  # Everyone
    ),
    "exam_rules.pdf": dict(
        doc_name="Exam Rules",
        doc_family="exam",
        effective_date="2024-09-01",
        access_level=1,  # Everyone
    ),
    "grading_faculty.pdf": dict(
        doc_name="Grading Guidelines for Faculty",
        doc_family="grading",
        effective_date="2024-06-01",
        access_level=2,  # Professors & Admins only
    ),
    "disciplinary_report.pdf": dict(
        doc_name="Disciplinary Committee Report",
        doc_family="disciplinary",
        effective_date="2024-11-01",
        access_level=3,  # Admins only
    ),
}

# Paths to folders
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")


def load_and_chunk():
    """
    Step 1: Read each PDF page and cut it into smaller paragraphs (chunks).
    """
    # chunk_size=700: ~700 characters per chunk
    # chunk_overlap=100: keeps 100 characters from previous chunk so sentences aren't cut in half
    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    chunks = []

    for fname, meta in REGISTRY.items():
        filepath = os.path.join(DOCS_DIR, fname)
        if not os.path.exists(filepath):
            print(f"  [!] Skipping {fname} (file not found at {filepath})")
            continue

        print(f"  Loading {fname}...")
        # PyPDFLoader reads the PDF page-by-page
        pages = PyPDFLoader(filepath).load()
        # Split pages into smaller pieces
        doc_chunks = splitter.split_documents(pages)

        # Attach metadata to each chunk (including the exact page number)
        for c in doc_chunks:
            # PyPDF counts pages from 0, so we add 1 (Page 0 -> Page 1)
            c.metadata = {**meta, "page": c.metadata.get("page", 0) + 1}
            chunks.append(c)

        print(f"    -> {len(doc_chunks)} chunks from {len(pages)} pages")

    return chunks


def mark_current(chunks):
    """
    Step 2: Compare policy dates to find the newest one.
    - 2025 attendance policy -> is_current = True
    - 2023 attendance policy -> is_current = False (superseded)
    """
    newest = {}
    # Find the latest date for each document family
    for c in chunks:
        family = c.metadata["doc_family"]
        date = c.metadata["effective_date"]
        newest[family] = max(newest.get(family, date), date)

    # Tag each chunk: True if it matches the newest date, else False
    for c in chunks:
        c.metadata["is_current"] = (
            c.metadata["effective_date"] == newest[c.metadata["doc_family"]]
        )

    current_count = sum(1 for c in chunks if c.metadata["is_current"])
    superseded_count = len(chunks) - current_count
    print(f"\n  [OK] {current_count} current chunks, {superseded_count} superseded chunks")

    return chunks


def embed_and_store(chunks):
    """
    Step 3: Convert text to mathematical vectors (embeddings)
    and save them into PostgreSQL + pgvector.
    """
    import psycopg

    print("\n  Resetting collection in PostgreSQL...")
    with psycopg.connect(DB_URL) as conn:
        conn.execute("DROP TABLE IF EXISTS langchain_pg_embedding, langchain_pg_collection CASCADE;")
        conn.commit()

    print("  Loading embedding model (BAAI/bge-small-en-v1.5)...")
    emb = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    print(f"  Storing {len(chunks)} chunks in PostgreSQL collection 'campus_docs'...")
    store = PGVector(
        embeddings=emb,
        collection_name="campus_docs",
        connection=CONN,
        use_jsonb=True,
    )
    store.add_documents(chunks)
    print(f"  [OK] Stored {len(chunks)} chunks in PostgreSQL with pgvector successfully!\n")


def main():
    print("\n============================================")
    print("   Campus RAG MVP - Document Ingestion      ")
    print("============================================\n")

    # 1. Load PDFs and split
    chunks = load_and_chunk()
    if not chunks:
        print("\n  [X] No chunks created. Make sure PDFs exist in docs/ folder.")
        return

    # 2. Tag old vs new policies
    chunks = mark_current(chunks)

    # 3. Save to database
    embed_and_store(chunks)

    # Print a sample chunk to verify
    print("-- Sample chunk ------------------------------------------")
    sample = chunks[0]
    print(f"  doc_name:       {sample.metadata['doc_name']}")
    print(f"  page:           {sample.metadata['page']}")
    print(f"  access_level:   {sample.metadata['access_level']}")
    print(f"  effective_date: {sample.metadata['effective_date']}")
    print(f"  is_current:     {sample.metadata['is_current']}")
    print(f"  content:        {sample.page_content[:150]}...")
    print("----------------------------------------------------------\n")


if __name__ == "__main__":
    main()
