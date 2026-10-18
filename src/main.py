"""
main.py - FastAPI Web API for the Campus Knowledge Assistant.

What this file does:
1. Exposes an HTTP POST endpoint `/ask`
2. Takes a JSON request containing `question` and `role`
3. Calls the `ask()` function in rag.py
4. Returns the answer as JSON
5. Auto-generates the interactive Swagger UI at http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.rag import ask

# Initialize the FastAPI app
app = FastAPI(
    title="Campus Knowledge Assistant",
    description="RAG assistant over university documents with role-based access and citations.",
    version="0.1.0",
)


class QuestionRequest(BaseModel):
    """
    The JSON structure expected when sending a question:
    Example:
    {
        "question": "What is the minimum attendance?",
        "role": "student"
    }
    """
    question: str
    role: str = "student"  # Default role is student; can be 'student', 'professor', or 'admin'


@app.get("/")
def root():
    """Welcome route confirming the server is up."""
    return {"message": "Campus Knowledge Assistant MVP", "docs": "/docs"}


@app.post("/ask")
def ask_endpoint(q: QuestionRequest):
    """
    Main endpoint to ask questions to the assistant.

    The user's role controls which documents they are allowed to access:
    - 'student' (level 1): public documents only (e.g. attendance)
    - 'professor' (level 2): public documents + faculty grading guidelines
    - 'admin' (level 3): all documents
    """
    # Validate the role
    if q.role not in ("student", "professor", "admin"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {q.role}. Use student, professor, or admin.",
        )

    # Execute the RAG pipeline
    result, docs = ask(q.question, q.role)
    return result
