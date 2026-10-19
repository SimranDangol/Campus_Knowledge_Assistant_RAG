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

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

import psycopg
from dotenv import load_dotenv
from langchain_classic.retrievers import EnsembleRetriever
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_core.cross_encoders import BaseCrossEncoder
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

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
    if role not in ROLE_LEVEL:
        raise ValueError(f"Unsupported role: {role}")
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
        if self.role not in ROLE_LEVEL:
            raise ValueError(f"Unsupported role: {self.role}")
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
        with psycopg.connect(PSYCOPG_CONN) as conn:
            rows = conn.execute(
                sql,
                (query, ROLE_LEVEL[self.role], query, self.k),
            ).fetchall()
        return [Document(page_content=t, metadata=m) for t, m in rows]


def _reranking_enabled() -> bool:
    value = os.getenv("RERANKER_ENABLED", "true").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError("RERANKER_ENABLED must be 'true' or 'false'")
    return value == "true"


@lru_cache(maxsize=1)
def _cross_encoder_model(model_name: str) -> CrossEncoder:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


class SentenceTransformerCrossEncoder(BaseCrossEncoder):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        scores = _cross_encoder_model(self.model_name).predict(text_pairs)
        return [float(score) for score in scores]


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
    """Build a filtered hybrid retriever and optionally rerank its candidates."""
    if not _reranking_enabled():
        return build_hybrid(role, store, k=k)

    candidates = build_hybrid(role, store, k=max(k * 4, 20))
    model_name = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
    reranker = CrossEncoderReranker(
        model=SentenceTransformerCrossEncoder(model_name),
        top_n=k,
    )
    return ContextualCompressionRetriever(
        base_compressor=reranker,
        base_retriever=candidates,
    )
