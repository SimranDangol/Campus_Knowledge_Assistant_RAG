"""
graph.py - LangGraph Agentic Pipeline for Campus Knowledge Assistant (Upgrade 11).

Implements a state machine workflow with retrieve, grade/route, answer, and refuse nodes:
- StateGraph with TypedDict State
- Conditional routing: Refuses early if zero relevant chunks pass RBAC and versioning filters.
- Answer generation node with Pydantic structured output.
- Refusal node returning strict refusal without invoking LLM (guarantees zero hallucinations).
"""

from typing import Any, List, Optional, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from src.chain import (
    CampusAnswer,
    NO_INFO,
    format_docs,
    get_answer_chain,
    get_store,
)
from src.retrieval import build_retriever


class AgentState(TypedDict):
    question: str
    role: str
    docs: List[Any]
    result: Optional[CampusAnswer]


def create_agent_graph(retriever_fn=None, answer_chain_fn=None):
    """
    Construct and compile the LangGraph workflow.
    Optional dependency injection for easy unit testing without live DB or LLMs.
    """

    def retrieve_node(state: AgentState) -> dict:
        role = state.get("role", "student")
        question = state.get("question", "")
        if retriever_fn:
            docs = retriever_fn(question, role)
        else:
            docs = build_retriever(role, get_store()).invoke(question)
        return {"docs": docs or []}

    def route_decision(state: AgentState) -> str:
        """Grade step: refuse early when nothing relevant or allowed came back."""
        docs = state.get("docs", [])
        if docs and len(docs) > 0:
            return "answer"
        return "refuse"

    def answer_node(
        state: AgentState,
        config: Optional[RunnableConfig] = None,
    ) -> dict:
        docs = state.get("docs", [])
        question = state.get("question", "")
        context = format_docs(docs)

        if answer_chain_fn:
            res = answer_chain_fn(question, context, config)
        else:
            res = get_answer_chain().invoke(
                {"context": context, "question": question},
                config=config,
            )
        return {"result": res}

    def refuse_node(state: AgentState) -> dict:
        return {
            "result": CampusAnswer(
                found=False,
                answer=NO_INFO,
                citations=[],
            )
        }

    builder = StateGraph(AgentState)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("answer", answer_node)
    builder.add_node("refuse", refuse_node)

    builder.set_entry_point("retrieve")
    builder.add_conditional_edges(
        "retrieve",
        route_decision,
        {
            "answer": "answer",
            "refuse": "refuse",
        },
    )
    builder.add_edge("answer", END)
    builder.add_edge("refuse", END)

    return builder.compile()


# Default compiled graph
app_graph = create_agent_graph()


def ask_graph(
    question: str,
    role: str,
    vector_store=None,
    config: Optional[dict] = None,
) -> tuple[CampusAnswer, list]:
    """
    Execute query via LangGraph state machine.
    Returns (CampusAnswer, list_of_docs) matching the interface of ask().
    """
    if vector_store is not None:
        graph = create_agent_graph(
            retriever_fn=lambda q, r: build_retriever(r, vector_store).invoke(q)
        )
    else:
        graph = app_graph

    initial_state: AgentState = {
        "question": question,
        "role": role,
        "docs": [],
        "result": None,
    }

    final_state = graph.invoke(initial_state, config=config)
    result = final_state.get("result")
    if result is None:
        result = CampusAnswer(found=False, answer=NO_INFO, citations=[])
    docs = final_state.get("docs", [])
    return result, docs
