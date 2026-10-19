"""Load policy PDFs with Docling and replace the campus PGVector collection."""

import sys
import os

import psycopg
from dotenv import load_dotenv

# Fix for Windows command prompt so it doesn't crash on special characters
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from docling.chunking import HybridChunker
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
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
    Step 1: Parse each PDF into table-aware chunks with page provenance.
    """
    chunks = []
    chunker = HybridChunker()

    for fname, meta in REGISTRY.items():
        filepath = os.path.join(DOCS_DIR, fname)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required policy PDF is missing: {filepath}")

        print(f"  Loading {fname}...")
        loader = DoclingLoader(
            file_path=filepath,
            export_type=ExportType.DOC_CHUNKS,
            chunker=chunker,
        )
        doc_chunks = loader.load()

        # Docling page numbers are one-based and stored with chunk provenance.
        for c in doc_chunks:
            doc_items = c.metadata.get("dl_meta", {}).get("doc_items", [])
            pages = [
                provenance["page_no"]
                for item in doc_items
                for provenance in item.get("prov", [])
                if isinstance(provenance.get("page_no"), int)
            ]
            if not pages:
                raise ValueError(
                    f"Docling did not provide page provenance for a chunk in {fname}"
                )
            c.metadata = {
                **meta,
                "page": min(pages),
                "source_file": fname,
            }
            chunks.append(c)

        print(f"    -> {len(doc_chunks)} table-aware chunks")

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
    if not chunks:
        raise ValueError("Refusing to replace campus_docs with an empty document set")

    print("  Loading embedding model (BAAI/bge-small-en-v1.5)...")
    emb = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    print(f"\n  Replacing campus_docs with {len(chunks)} chunks...")
    store = PGVector(
        embeddings=emb,
        collection_name="campus_docs",
        connection=CONN,
        use_jsonb=True,
        pre_delete_collection=True,
    )
    store.add_documents(chunks)
    print(f"  [OK] Stored {len(chunks)} chunks in PostgreSQL with pgvector successfully!")

    print("  Creating PostgreSQL GIN index for Full-Text Search...")
    with psycopg.connect(DB_URL) as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_fts ON langchain_pg_embedding "
            "USING GIN (to_tsvector('english', document));"
        )
        conn.commit()
    print("  [OK] Full-Text GIN index created successfully!\n")


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
