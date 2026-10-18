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

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from src.auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
)
from src.chain import CampusAnswer, ask

# ── App init ────────────────────────────────────────────────────────────
app = FastAPI(
    title="Campus Knowledge Assistant",
    description=(
        "RAG assistant over university documents with role-based access, "
        "hybrid search, and JWT authentication."
    ),
    version="1.0.0",
)


# ── Request / Response schemas ──────────────────────────────────────────
class QuestionRequest(BaseModel):
    """
    JSON body for /ask:
    {
        "question": "What is the minimum attendance?"
    }
    The role is automatically extracted from the JWT token.
    """

    question: str


class AskResponse(BaseModel):
    """Structured response from /ask."""

    found: bool
    answer: str
    citations: list
    role: str
    chunks_retrieved: int


# ── Routes ──────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """Health check confirming the server is up."""
    return {
        "service": "Campus Knowledge Assistant",
        "version": "1.0.0",
        "auth": "JWT (POST /token)",
        "docs": "/docs",
    }


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
    result, docs = ask(q.question, current_user.role)
    return AskResponse(
        found=result.found,
        answer=result.answer,
        citations=[c.model_dump() for c in result.citations],
        role=current_user.role,
        chunks_retrieved=len(docs),
    )


@app.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return {"username": current_user.username, "role": current_user.role}
