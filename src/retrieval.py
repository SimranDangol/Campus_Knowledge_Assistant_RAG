"""
retrieval.py - Hybrid Retrieval (Semantic PGVector + Postgres Full-Text Search).

Why Hybrid Search?
- Semantic search (embeddings) understands concepts and meanings, but often misses
  exact alphanumeric codes like "Form F-12" or "CS-301".
- Postgres Full-Text Search (FTS) indexes exact words and tokens using a GIN index.
- EnsembleRetriever fuses the two rankings using Reciprocal Rank Fusion (RRF).

Security Rule:
The permission filter (access_level <= user_level AND is_current = True) runs
INSIDE PostgreSQL for BOTH retrievers, so restricted content never leaves the DB.
"""

import os
import psycopg
from dotenv import load_dotenv
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

load_dotenv()

ROLE_LEVEL = {"student": 1, "professor": 2, "admin": 3}
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pass@localhost:5432/postgres")
PSYCOPG_CONN = (
    DB_URL.replace("postgresql+psycopg://", "postgresql://", 1)
    if DB_URL.startswith("postgresql+psycopg://")
    else DB_URL
)


def build_filter(role: str) -> dict:
    """Filter used by the semantic PGVector retriever."""
    return {
        "$and": [
            {"access_level": {"$lte": ROLE_LEVEL[role]}},
            {"is_current": {"$eq": True}},
        ]
    }


class PgFTSRetriever(BaseRetriever):
    """
    Custom PostgreSQL Full-Text Search retriever using GIN index and ts_rank.
    Enforces RBAC and versioning directly in SQL.
    """

    role: str
    k: int = 5

    def _get_relevant_documents(self, query: str, *, run_manager=None):
        sql = """
        SELECT e.document, e.cmetadata
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON c.uuid = e.collection_id
        WHERE c.name = 'campus_docs'
          AND to_tsvector('english', e.document) @@ websearch_to_tsquery('english', %s)
          AND (e.cmetadata->>'access_level')::int <= %s
          AND (e.cmetadata->>'is_current')::boolean
        ORDER BY ts_rank(to_tsvector('english', e.document),
                         websearch_to_tsquery('english', %s)) DESC
        LIMIT %s;
        """
        try:
            with psycopg.connect(PSYCOPG_CONN) as conn:
                rows = conn.execute(
                    sql,
                    (query, ROLE_LEVEL[self.role], query, self.k),
                ).fetchall()
            return [Document(page_content=t, metadata=m) for t, m in rows]
        except Exception as e:
            # Fallback if query contains special characters not parsed by websearch_to_tsquery
            plain_sql = """
            SELECT e.document, e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name = 'campus_docs'
              AND to_tsvector('english', e.document) @@ plainto_tsquery('english', %s)
              AND (e.cmetadata->>'access_level')::int <= %s
              AND (e.cmetadata->>'is_current')::boolean
            ORDER BY ts_rank(to_tsvector('english', e.document),
                             plainto_tsquery('english', %s)) DESC
            LIMIT %s;
            """
            with psycopg.connect(PSYCOPG_CONN) as conn:
                rows = conn.execute(
                    plain_sql,
                    (query, ROLE_LEVEL[self.role], query, self.k),
                ).fetchall()
            return [Document(page_content=t, metadata=m) for t, m in rows]


def build_hybrid(role: str, store, k: int = 5):
    """
    Builds hybrid retriever combining Semantic Search (PGVector) and
    Full-Text Search (PgFTSRetriever) with Reciprocal Rank Fusion.
    """
    semantic = store.as_retriever(
        search_kwargs={"k": k, "filter": build_filter(role)}
    )
    keyword = PgFTSRetriever(role=role, k=k)
    return EnsembleRetriever(
        retrievers=[semantic, keyword],
        weights=[0.5, 0.5],
    )


def build_retriever(role: str, store, k: int = 5):
    """Entrypoint to build the role-aware hybrid retriever."""
    return build_hybrid(role, store, k=k)
