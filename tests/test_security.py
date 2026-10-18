"""
test_security.py - Security tests that verify RBAC and version filtering.

These tests use the retriever directly (no LLM needed), so they are
fast, deterministic, and free to run.

"""

import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.rag import retrieve


def test_student_never_sees_faculty_docs():
    """A student must never retrieve chunks from faculty-only documents."""
    docs = retrieve("How are faculty grades moderated?", "student")
    for d in docs:
        assert d.metadata["access_level"] <= 1, (
            f"Student retrieved a restricted chunk: {d.metadata['doc_name']} "
            f"(access_level={d.metadata['access_level']})"
        )


def test_professor_can_see_faculty_docs():
    """A professor should be able to retrieve faculty-level documents."""
    docs = retrieve("How are faculty grades moderated?", "professor")
    assert any(d.metadata["access_level"] == 2 for d in docs), (
        "Professor could not retrieve any faculty documents"
    )


def test_outdated_policy_never_returned():
    """Superseded policies (is_current=False) must never appear in results."""
    docs = retrieve("minimum attendance", "student")
    for d in docs:
        assert d.metadata["is_current"], (
            f"Superseded document retrieved: {d.metadata['doc_name']} "
            f"(effective_date={d.metadata['effective_date']})"
        )
