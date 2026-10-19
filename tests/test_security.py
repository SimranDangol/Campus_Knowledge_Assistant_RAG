"""Unit tests for policy ingestion and retrieval filters; no database or LLM needed."""

import pytest
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from src import ingest, retrieval
from src.ingest import mark_current
from src.retrieval import (
    PgFTSRetriever,
    SentenceTransformerCrossEncoder,
    build_filter,
    build_retriever,
)


def test_semantic_filter_limits_each_role_and_current_documents():
    assert build_filter("student") == {
        "$and": [
            {"access_level": {"$lte": 1}},
            {"is_current": {"$eq": True}},
        ]
    }
    assert build_filter("professor")["$and"][0]["access_level"]["$lte"] == 2
    assert build_filter("admin")["$and"][0]["access_level"]["$lte"] == 3


def test_unknown_role_is_rejected():
    with pytest.raises(ValueError, match="Unsupported role: guest"):
        build_filter("guest")


def test_keyword_query_enforces_role_and_version_filters(monkeypatch):
    observed = {}

    class Cursor:
        def fetchall(self):
            return []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params):
            observed["sql"] = sql
            observed["params"] = params
            return Cursor()

    def connect(connection_string):
        observed["connection_string"] = connection_string
        return Connection()

    monkeypatch.setattr(retrieval.psycopg, "connect", connect)
    docs = PgFTSRetriever(role="student", k=7)._get_relevant_documents(
        "faculty grade changes"
    )

    assert docs == []
    assert "(e.cmetadata->>'access_level')::int <= %s" in observed["sql"]
    assert "(e.cmetadata->>'is_current')::boolean" in observed["sql"]
    assert observed["params"] == (
        "faculty grade changes",
        retrieval.ROLE_LEVEL["student"],
        "faculty grade changes",
        7,
    )


def test_keyword_query_propagates_database_errors(monkeypatch):
    def connect(_):
        raise OSError("database unavailable")

    monkeypatch.setattr(retrieval.psycopg, "connect", connect)
    with pytest.raises(OSError, match="database unavailable"):
        PgFTSRetriever(role="student")._get_relevant_documents("attendance")


def test_newest_document_version_is_current():
    old_policy = Document(
        page_content="75%",
        metadata={"doc_family": "attendance", "effective_date": "2023-01-01"},
    )
    current_policy = Document(
        page_content="70%",
        metadata={"doc_family": "attendance", "effective_date": "2025-01-01"},
    )

    chunks = mark_current([old_policy, current_policy])

    assert [chunk.metadata["is_current"] for chunk in chunks] == [False, True]


def test_docling_page_provenance_is_preserved(monkeypatch, tmp_path):
    pdf_path = tmp_path / "policy.pdf"
    pdf_path.touch()
    source = Document(
        page_content="Policy threshold: 70%",
        metadata={
            "dl_meta": {
                "doc_items": [{"prov": [{"page_no": 3}, {"page_no": 3}]}]
            }
        },
    )

    class FakeLoader:
        def __init__(self, **kwargs):
            assert kwargs["file_path"] == str(pdf_path)

        def load(self):
            return [source]

    monkeypatch.setattr(ingest, "DOCS_DIR", str(tmp_path))
    monkeypatch.setattr(
        ingest,
        "REGISTRY",
        {
            "policy.pdf": {
                "doc_name": "Attendance Policy",
                "doc_family": "attendance",
                "effective_date": "2025-01-01",
                "access_level": 1,
            }
        },
    )
    monkeypatch.setattr(ingest, "DoclingLoader", FakeLoader)

    chunks = ingest.load_and_chunk()

    assert chunks[0].metadata["page"] == 3
    assert chunks[0].metadata["source_file"] == "policy.pdf"


def test_missing_registered_pdf_fails_ingestion(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "DOCS_DIR", str(tmp_path))
    monkeypatch.setattr(ingest, "REGISTRY", {"missing.pdf": {}})

    with pytest.raises(FileNotFoundError, match="missing.pdf"):
        ingest.load_and_chunk()


def test_empty_ingestion_cannot_delete_existing_collection():
    with pytest.raises(ValueError, match="empty document set"):
        ingest.embed_and_store([])


def test_reranker_receives_filtered_candidate_set(monkeypatch):
    observed = {}

    class EmptyRetriever(BaseRetriever):
        def _get_relevant_documents(self, query, *, run_manager=None):
            return []

    class FakeStore:
        def as_retriever(self, *, search_kwargs):
            observed["search_kwargs"] = search_kwargs
            return EmptyRetriever()

    monkeypatch.setenv("RERANKER_ENABLED", "true")
    retriever = build_retriever("student", FakeStore(), k=5)

    assert retriever.base_compressor.top_n == 5
    assert observed["search_kwargs"]["k"] == 20
    assert observed["search_kwargs"]["filter"] == build_filter("student")


def test_sentence_transformer_scores_are_plain_floats(monkeypatch):
    class FakeModel:
        def predict(self, text_pairs):
            assert text_pairs == [("query", "relevant"), ("query", "other")]
            return [0.9, 0.1]

    monkeypatch.setattr(retrieval, "_cross_encoder_model", lambda _: FakeModel())
    scores = SentenceTransformerCrossEncoder("test-model").score(
        [("query", "relevant"), ("query", "other")]
    )

    assert scores == [0.9, 0.1]
    assert all(isinstance(score, float) for score in scores)
