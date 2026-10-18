"""
rag.py - Answers questions using Chroma DB + Groq LLM.

What this file does:
1. Receives a question and a role (e.g. 'student' or 'professor')
2. Filters out confidential or outdated chunks INSIDE the database
3. Feeds only allowed chunks to the LLM
4. Returns a clean answer with exact citations (document name + page)
"""

from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import os
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables (such as GROQ_API_KEY from .env)
load_dotenv()

# ---------------------------------------------------------------------------
# Role hierarchy:
# - student: level 1 (can only read public policy)
# - professor: level 2 (can read public policy + faculty grading rules)
# - admin: level 3 (can read everything)
# ---------------------------------------------------------------------------
ROLE_LEVEL = {"student": 1, "professor": 2, "admin": 3}
NO_INFO = "I don't have information on that."
CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")

# ---------------------------------------------------------------------------
# Load embedding model and connect to Chroma database (loaded once at startup)
# ---------------------------------------------------------------------------
emb = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
store = Chroma(
    collection_name="campus",
    embedding_function=emb,
    persist_directory=CHROMA_DIR,
)

# ---------------------------------------------------------------------------
# Pydantic Schemas: Define the exact shape of the output
# This forces the LLM to return structured JSON rather than unstructured text.
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """Where the fact was found."""
    document: str  # e.g. "Attendance Policy 2025"
    page: int      # e.g. 1


class CampusAnswer(BaseModel):
    """The structured answer returned by the AI."""
    found: bool = Field(description="Set to False if the documents do not answer the question")
    answer: str
    citations: List[Citation]


# ---------------------------------------------------------------------------
# System Instructions for the LLM
# Strict instructions: answer ONLY from context, cite page numbers, never guess!
# ---------------------------------------------------------------------------
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

# Connect to Groq LLM (temperature=0 means deterministic, no random guessing)
model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
llm = ChatGroq(model=model_name, temperature=0)

# Chain together: Prompt -> LLM -> Pydantic Schema
chain = prompt | llm.with_structured_output(CampusAnswer)


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def retrieve(question: str, role: str, k: int = 5):
    """
    Search Chroma DB for relevant chunks with security filters.

    SECURITY RULE:
    The filter runs INSIDE Chroma DB before any text is retrieved:
    1. access_level <= user_level (students cannot get faculty chunks)
    2. is_current == True (outdated 2023 policies are excluded)
    """
    level = ROLE_LEVEL[role]
    flt = {
        "$and": [
            {"access_level": {"$lte": level}},
            {"is_current": True},
        ]
    }
    # Returns top-k matching chunks that pass the filter
    return store.similarity_search(question, k=k, filter=flt)


def format_docs(docs):
    """
    Combines retrieved chunks into a single readable string for the LLM.
    Includes document name, page number, and effective date.
    """
    return "\n\n".join(
        f"[{d.metadata['doc_name']}, page {d.metadata['page']}, "
        f"effective {d.metadata['effective_date']}]\n{d.page_content}"
        for d in docs
    )


def ask(question: str, role: str):
    """
    Full pipeline:
    1. Search database with permissions filter
    2. If no docs found -> short-circuit and say "I don't know" (saves money & time)
    3. If docs found -> send context to LLM and return structured answer
    """
    docs = retrieve(question, role)

    # Short-circuit: no allowed chunks found -> exit immediately without calling the LLM
    if not docs:
        return CampusAnswer(found=False, answer=NO_INFO, citations=[]), []

    # Send retrieved chunks and question to LLM
    result = chain.invoke({
        "context": format_docs(docs),
        "question": question,
    })
    return result, docs



if __name__ == "__main__":
    print("\n============================================")
    print("     Campus RAG MVP - Query Demo            ")
    print("============================================\n")

    test_questions = [
        ("student", "What is the minimum attendance to sit in exams?"),
        ("professor", "What is the minimum attendance to sit in exams?"),
        ("student", "How are faculty grades moderated?"),
        ("professor", "How are faculty grades moderated?"),
        ("student", "What is the cafeteria timing?"),
    ]

    for role, question in test_questions:
        print(f"--- [{role}] {question}")
        result, docs = ask(question, role)
        print(f"    found:    {result.found}")
        print(f"    answer:   {result.answer}")
        if result.citations:
            for c in result.citations:
                print(f"    citation: {c.document}, page {c.page}")
        print(f"    chunks:   {len(docs)} retrieved")
        print()
