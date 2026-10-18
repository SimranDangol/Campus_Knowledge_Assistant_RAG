# 🎓 Campus Knowledge Assistant (Campus RAG MVP)

A Role-Based Access Controlled (RBAC) Retrieval-Augmented Generation (RAG) assistant for university campus policies.

## 🌟 Core Features Proven in MVP

1. **Citations & Grounding**: Returns accurate answers citing the specific policy document and page number.
2. **Role-Based Access Control (RBAC)**: Search filters enforce permissions directly at the database layer (students cannot view faculty grading policies).
3. **Temporal Policy Versioning**: Filters out outdated policies (e.g., automatically ignores 2023 75% attendance rule in favor of the current 2025 70% rule).
4. **Hallucination Prevention**: Explicitly returns *"I don't have information on that"* when the context does not contain the answer.

---

## 🛠️ Tech Stack

* **Language & Package Manager**: Python 3.11 + `uv`
* **Orchestration**: LangChain (`langchain-core`, `langchain-chroma`, `langchain-groq`)
* **Vector Store**: Chroma DB (`chroma_db/`)
* **Embedding Model**: `BAAI/bge-small-en-v1.5` (via HuggingFace)
* **LLM**: Groq (`qwen/qwen3.8-27b`)
* **API Framework**: FastAPI + Uvicorn
* **Testing**: Pytest

---

## 🚀 Quickstart

### 1. Setup Environment
Ensure your `.env` file contains your Groq API key:
```env
GROQ_API_KEY="your-groq-api-key"
```

### 2. Generate Sample PDFs
```powershell
uv run python src/generate_pdfs.py
```

### 3. Ingest Documents into Vector Store
```powershell
uv run python src/ingest.py
```

### 4. Run Security & RBAC Tests
```powershell
uv run pytest -v
```

### 5. Run the MVP Evaluation
Add your Groq API key to `.env`, then compare the actual answers and citations with the expected results:
```powershell
uv run python -m src.evaluate
```
Score answer correctness, citation correctness, and refusal correctness by hand, as the guide recommends.
Record the results below after running the evaluation; no results are claimed until the LLM-backed run
has been completed.

### 6. Run the Query Demo
```powershell
uv run python src/rag.py
```

### 7. Start the FastAPI Server
```powershell
uv run uvicorn src.main:app --reload
```
Open **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** to test queries through the interactive Swagger UI.
An unsupported role returns HTTP 400.

### Evaluation Results

| Measure | Result |
|---|---:|
| Questions in evaluation set | 10 |
| Correct answers | 10/10 |
| Correct citations | 6/6 answerable questions |
| Correct refusals | 4/4 unanswerable questions |

Results are from a live Groq run. Question 9 asks about the historical 2023 attendance threshold; the
2025 policy explicitly states that the previous threshold was 75%, so its expected answer cites the
current 2025 document rather than requiring a refusal. Scoring was done by checking each answer against
the policy facts, each citation against the expected document, and each unsupported/restricted question
for a refusal. The security and API validation tests do not need the LLM API key.

---

## 📁 Project Structure

```
CKA/
├── docs/                     # Sample university policy PDFs
├── chroma_db/                # Local Chroma vector database
├── src/
│   ├── generate_pdfs.py      # Generates sample policy PDFs
│   ├── ingest.py             # PDF chunking, metadata tagging, and vector storage
│   ├── evaluate.py           # Runs the 10-question hand-scored evaluation
│   ├── rag.py                # RAG pipeline: retrieval, RBAC filter, LLM answer
│   └── main.py               # FastAPI application endpoints
├── tests/
│   ├── test_api.py           # API input validation tests
│   └── test_security.py      # Automated security tests for RBAC & versioning
├── pyproject.toml            # Project dependencies and configuration
└── README.md
```
