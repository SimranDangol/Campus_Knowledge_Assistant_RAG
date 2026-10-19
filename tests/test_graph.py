"""
tests/test_graph.py - Unit tests for LangGraph state machine (Upgrade 11).

Tests cover:
1. Routing decision: when docs are retrieved, route to 'answer'.
2. Routing decision: when 0 docs retrieved (or restricted), route to 'refuse'.
3. State preservation: question, role, docs, and structured result.
4. Execution of ask_graph without requiring live DB or external LLMs.
"""

import pytest
from langchain_core.documents import Document
from src.chain import CampusAnswer, Citation
from src.graph import AgentState, create_agent_graph, ask_graph


def test_langgraph_refusal_branch_when_no_docs():
    """When retriever returns 0 docs, the graph must route to 'refuse' and not call LLM."""
    llm_called = False

    def fake_retriever(question, role):
        return []

    def fake_answer_chain(question, context, config):
        nonlocal llm_called
        llm_called = True
        return CampusAnswer(found=True, answer="Should not happen", citations=[])

    graph = create_agent_graph(
        retriever_fn=fake_retriever,
        answer_chain_fn=fake_answer_chain,
    )

    state: AgentState = {
        "question": "How are faculty grades moderated?",
        "role": "student",
        "docs": [],
        "result": None,
    }

    output = graph.invoke(state)

    assert not llm_called
    assert output["result"].found is False
    assert "don't have information" in output["result"].answer.lower()
    assert output["result"].citations == []


def test_langgraph_answer_branch_when_docs_found():
    """When retriever returns docs, the graph routes to 'answer' and executes answer node."""
    retrieved_docs = [
        Document(
            page_content="Under Attendance Policy 2025, minimum attendance is 70%.",
            metadata={
                "doc_name": "Attendance Policy 2025",
                "page": 1,
                "effective_date": "2025-01-01",
                "access_level": 1,
                "is_current": True,
            },
        )
    ]

    llm_called = False

    def fake_retriever(question, role):
        return retrieved_docs

    def fake_answer_chain(question, context, config):
        nonlocal llm_called
        llm_called = True
        assert "Attendance Policy 2025" in context
        return CampusAnswer(
            found=True,
            answer="Minimum attendance is 70%.",
            citations=[Citation(document="Attendance Policy 2025", page=1)],
        )

    graph = create_agent_graph(
        retriever_fn=fake_retriever,
        answer_chain_fn=fake_answer_chain,
    )

    state: AgentState = {
        "question": "What is minimum attendance?",
        "role": "student",
        "docs": [],
        "result": None,
    }

    output = graph.invoke(state)

    assert llm_called is True
    assert output["result"].found is True
    assert output["result"].answer == "Minimum attendance is 70%."
    assert len(output["result"].citations) == 1
    assert output["result"].citations[0].document == "Attendance Policy 2025"


def test_ask_graph_convenience_wrapper(monkeypatch):
    """ask_graph returns (CampusAnswer, docs) tuple."""
    retrieved_docs = [
        Document(
            page_content="Faculty grades are reviewed by a second marker.",
            metadata={
                "doc_name": "Grading Guidelines for Faculty",
                "page": 2,
                "effective_date": "2024-06-01",
                "access_level": 2,
                "is_current": True,
            },
        )
    ]

    from src import graph

    def fake_retriever_fn(q, r):
        return retrieved_docs if r in ("professor", "admin") else []

    def fake_answer_fn(q, ctx, cfg):
        return CampusAnswer(
            found=True,
            answer="A second marker reviews grades.",
            citations=[Citation(document="Grading Guidelines for Faculty", page=2)],
        )

    test_graph = create_agent_graph(fake_retriever_fn, fake_answer_fn)
    monkeypatch.setattr(graph, "app_graph", test_graph)

    # Professor can see it
    res_prof, docs_prof = ask_graph("How are faculty grades moderated?", "professor")
    assert res_prof.found is True
    assert len(docs_prof) == 1

    # Student cannot see it
    res_stu, docs_stu = ask_graph("How are faculty grades moderated?", "student")
    assert res_stu.found is False
    assert len(docs_stu) == 0
