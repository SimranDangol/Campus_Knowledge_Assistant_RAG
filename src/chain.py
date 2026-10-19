"""
chain.py - Query-time PGVector store and LCEL answer chain for the full version.
(Replaces rag.py from the MVP, using Hybrid Search with EnsembleRetriever).
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path so 'src' can be imported anywhere
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functools import lru_cache
from typing import Any, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from src.retrieval import build_retriever

# Fix for Windows console output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

ROLE_LEVEL = {"student": 1, "professor": 2, "admin": 3}
NO_INFO = "I don't have information on that."

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pass@localhost:5432/postgres")
CONN = (
    DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    if DB_URL.startswith("postgresql://")
    else DB_URL
)

class Citation(BaseModel):
    document: str
    page: int


class CampusAnswer(BaseModel):
    found: bool = Field(description="False if the context does not answer the question")
    answer: str
    citations: List[Citation]


SYSTEM = (
    "You are a university assistant. Answer ONLY from the context.\n"
    "- Cite every fact as (document, page).\n"
    "- If documents conflict, use the one with the latest effective date.\n"
    "- If the context does not answer the question, set found=false and answer "
    '"I don\'t have information on that." Never guess.'
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)

@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")


@lru_cache(maxsize=1)
def get_store() -> PGVector:
    return PGVector(
        embeddings=get_embeddings(),
        collection_name="campus_docs",
        connection=CONN,
        use_jsonb=True,
    )


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    return ChatGroq(model=model_name, temperature=0)


@lru_cache(maxsize=1)
def get_answer_chain():
    return prompt | get_llm().with_structured_output(CampusAnswer)


class _LazyStore:
    """Keep the historical ``store`` export without loading models at import time."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_store(), name)


store = _LazyStore()


def format_docs(docs):
    return "\n\n".join(
        f"[{d.metadata['doc_name']}, page {d.metadata['page']}, "
        f"effective {d.metadata['effective_date']}]\n{d.page_content}"
        for d in docs
    )


def retrieve(question: str, role: str, k: int = 5):
    """Retrieve documents using the hybrid EnsembleRetriever."""
    return build_retriever(role, get_store(), k=k).invoke(question)


def ask(question: str, role: str, vector_store=None, config: Optional[dict] = None):
    """
    Execute Hybrid Retrieval + Groq structured output answer.
    """
    target_store = vector_store if vector_store is not None else get_store()
    docs = build_retriever(role, target_store).invoke(question)

    if not docs:
        return CampusAnswer(found=False, answer=NO_INFO, citations=[]), []

    result = get_answer_chain().invoke(
        {"context": format_docs(docs), "question": question},
        config=config,
    )
    return result, docs


if __name__ == "__main__":
    print("\n============================================")
    print("   Campus RAG Hybrid Search - Query Demo    ")
    print("============================================\n")

    test_queries = [
        ("student", "What is Form F-12 used for?"),
        ("student", "What are the prerequisites for CS-301?"),
        ("student", "What is the minimum attendance to sit in exams?"),
        ("professor", "How are faculty grades moderated?"),
        ("student", "How are faculty grades moderated?"),
        ("admin", "What are the penalties for academic plagiarism?"),
    ]

    for role, q in test_queries:
        print(f"--- [{role}] {q}")
        res, retrieved_docs = ask(q, role)
        print(f"    found:    {res.found}")
        print(f"    answer:   {res.answer}")
        for c in res.citations:
            print(f"    citation: {c.document}, page {c.page}")
        print(f"    chunks:   {len(retrieved_docs)} hybrid docs retrieved\n")
