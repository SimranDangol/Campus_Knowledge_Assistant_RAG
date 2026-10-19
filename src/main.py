"""
main.py - FastAPI Web API for the Campus Knowledge Assistant (Full Version).

Endpoints:
  POST /token       → OAuth2 password login, returns JWT
  GET  /            → Health check
  POST /ask         → Protected: answer a question (role from JWT)

The user's role is embedded in the JWT token (not passed in the request body),
so the RBAC filter is cryptographically enforced — users cannot impersonate
a higher role.

Run with:  uv run uvicorn src.main:app --reload
Docs at:   http://127.0.0.1:8000/docs
"""

from pathlib import Path
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator

from src.auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
)
from src.chain import Citation, ask
from src.graph import ask_graph

FRONTEND_FILE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

# ── App init ────────────────────────────────────────────────────────────
app = FastAPI(
    title="Campus Knowledge Assistant",
    description=(
        "RAG assistant over university documents with role-based access, "
        "hybrid search, and JWT authentication."
    ),
    version="1.0.0",
)

# ── CORS Middleware ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8080,http://127.0.0.1:8080",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ──────────────────────────────────────────
class QuestionRequest(BaseModel):
    """
    JSON body for /ask:
    {
        "question": "What is the minimum attendance?",
        "use_graph": false
    }
    The role is automatically extracted from the JWT token.
    """

    question: str = Field(min_length=1, max_length=2000)
    use_graph: bool = Field(
        default=False,
        description="Whether to execute query through Upgrade 11 LangGraph state machine",
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("Question must not be blank")
        return question


class AskResponse(BaseModel):
    """Structured response from /ask."""

    found: bool
    answer: str
    citations: list[Citation]
    role: str
    chunks_retrieved: int
    pipeline: str = Field(
        default="chain",
        description="Execution engine ('chain' or 'langgraph')",
    )


# ── Routes ──────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """Health check confirming the server is up."""
    return {
        "service": "Campus Knowledge Assistant",
        "version": "1.0.0",
        "auth": "JWT (POST /token)",
        "app": "/app",
        "docs": "/docs",
    }


@app.get("/app", response_class=HTMLResponse)
def serve_app():
    """Serves the interactive web UI."""
    if FRONTEND_FILE.exists():
        return HTMLResponse(content=FRONTEND_FILE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


def _langfuse_config() -> dict | None:
    keys = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    configured = [bool(os.getenv(key)) for key in keys]
    if not any(configured):
        return None
    if not all(configured):
        raise RuntimeError("Set both Langfuse public and secret keys to enable tracing")

    try:
        from langfuse.langchain import CallbackHandler
    except ImportError as exc:
        raise RuntimeError(
            "Langfuse tracing is configured but the observability extra is not installed"
        ) from exc

    return {"callbacks": [CallbackHandler()]}


@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 password flow: exchange username + password for a JWT.

    Demo users:
      alice / studentpass   → student role
      bob   / profpass      → professor role
      carol / adminpass     → admin role
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/ask", response_model=AskResponse)
async def ask_endpoint(
    q: QuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Ask a question to the Campus Knowledge Assistant.

    The user's role is extracted from the JWT token:
      - student (level 1): public documents only
      - professor (level 2): + faculty-only documents
      - admin (level 3): all documents including disciplinary reports

    Returns a structured answer with citations and retrieval metadata.
    """
    if q.use_graph:
        result, docs = ask_graph(
            q.question,
            current_user.role,
            config=_langfuse_config(),
        )
        pipeline_name = "langgraph"
    else:
        result, docs = ask(
            q.question,
            current_user.role,
            config=_langfuse_config(),
        )
        pipeline_name = "chain"

    return AskResponse(
        found=result.found,
        answer=result.answer,
        citations=[c.model_dump() for c in result.citations],
        role=current_user.role,
        chunks_retrieved=len(docs),
        pipeline=pipeline_name,
    )


@app.post("/ask/graph", response_model=AskResponse)
async def ask_graph_endpoint(
    q: QuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Upgrade 11: Dedicated endpoint executing queries via the LangGraph state machine.
    """
    result, docs = ask_graph(
        q.question,
        current_user.role,
        config=_langfuse_config(),
    )
    return AskResponse(
        found=result.found,
        answer=result.answer,
        citations=[c.model_dump() for c in result.citations],
        role=current_user.role,
        chunks_retrieved=len(docs),
        pipeline="langgraph",
    )


@app.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return {"username": current_user.username, "role": current_user.role}
