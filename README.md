# 🎓 Campus Knowledge Assistant (Enterprise RAG)

> **A production-grade Retrieval-Augmented Generation (RAG) assistant over university policy documents featuring PostgreSQL PGVector semantic search, Full-Text GIN keyword search, cryptographically enforced Role-Based Access Control (RBAC), temporal policy versioning, and JWT authentication.**

---

## 🌟 Key Features

1. **Exact-Match & Semantic Hybrid Retrieval**:
   - Embeddings understand high-level concepts but frequently miss exact alphanumeric course codes or form IDs.
   - We combine **PGVector cosine similarity** (`BAAI/bge-small-en-v1.5`) with **PostgreSQL Full-Text Search** (`to_tsvector` + GIN index + `ts_rank`) fused via **Reciprocal Rank Fusion (RRF)**.
   - Accurately answers both concept questions and exact alphanumeric queries like *"What is Form F-12 used for?"* or *"Prerequisites for CS-301"*.

2. **Cryptographically Enforced Role-Based Access Control (RBAC)**:
   - Permissions are embedded in signed JWT claims (`HS256`), preventing role impersonation.
   - Permission filters (`access_level <= user_level AND is_current = True`) execute **directly inside the database engine** for both vector and keyword queries.
   - **Zero-trust security guarantee**: Restricted chunks never leave the database, never reach memory, and never leak into LLM prompts.

3. **Temporal Policy Versioning ("Newest Policy Wins")**:
   - Outdated documents are **never deleted** (preserving audit history), but flagged with `is_current = false` during ingestion.
   - Queries automatically retrieve only active policies (e.g. Attendance Policy 2025's 70% threshold cleanly overrides Attendance Policy 2023's 75% rule).

4. **Hallucination Prevention & Refusal Shortcut**:
   - Strict system prompt with Pydantic structured output (`CampusAnswer`).
   - Short-circuit mechanism: if zero chunks pass the RBAC/version filter, the pipeline **skips the LLM entirely**, saving API costs and guaranteeing zero hallucinations.

---

## 🖥️ Interactive Web UI & Live Demo

The application comes with an integrated dark-themed web application with real-time role switching, query chips, and page citation tags.

```
URL: http://127.0.0.1:8080/app
API Docs: http://127.0.0.1:8080/docs
```

### Demo Accounts

| User | Password | Role | Clearance Level | Access Scope |
|---|---|---|---|---|
| **Alice** | `studentpass` | `student` | Level 1 | Public handbooks, 2025 attendance, exam rules, fee tables |
| **Bob** | `profpass` | `professor` | Level 2 | Public documents + Confidential faculty grading guidelines |
| **Carol** | `adminpass` | `admin` | Level 3 | All university documents + Disciplinary sanction reports |

---

## 🏗️ System Architecture

```
[University Policy PDFs] 
         │
         ▼
[PyPDF / Docling Parser] ──► [RecursiveCharacterTextSplitter] (700 char, 100 overlap)
                                      │
                                      ▼
                      [Metadata Registry & Versioning Engine]
                      (access_level: 1/2/3, is_current: bool, page, dates)
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
      [HuggingFace BGE Embeddings]              [PostgreSQL GIN Full-Text Index]
                 │                                         │
                 └──────────────┬──────────────────────────┘
                                ▼
         [Docker PostgreSQL 16 + PGVector (langchain_pg_embedding)]
                                │
════════════════════════════════╪════════════════════════════════════════════
                        QUERY RUNTIME (FastAPI)
════════════════════════════════╪════════════════════════════════════════════
                                │
[User / Web UI] ──(POST /token)─┼──► [JWT Signed Token: {sub, role}]
                                │
[User / Web UI] ──(POST /ask)───┴──► [Extract Role from JWT]
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
    [PGVector Semantic Search]                                    [Custom PgFTSRetriever]
  (access_level <= role & is_current)                           (access_level <= role & is_current)
                 │                                                             │
                 └──────────────────────────────┬──────────────────────────────┘
                                                ▼
                                    [EnsembleRetriever (RRF)]
                                                │
                                    ┌───────────┴───────────┐
                        (Docs Found?)                     (No Docs?)
                             │                                 │
                             ▼                                 ▼
                    [Prompt + Context]              [Pre-LLM Refusal Shortcut]
                             │                      ("I don't have information...")
                             ▼
                    [Groq LLM (Qwen 27B)]
                             │
                             ▼
              [Pydantic Structured CampusAnswer]
              - found: bool
              - answer: str
              - citations: [{document, page}]
```

---

## 💡 Key Design Decisions

### 1. Why Permission Filters Run Inside PostgreSQL
Many naïve RAG systems retrieve the top $K$ chunks and filter out unauthorized documents in Python afterwards. This creates catastrophic security vulnerabilities:
- If a student asks about faculty grading, the top 5 chunks might all be restricted faculty documents. Post-filtering discards all 5, leaving 0 relevant results even if valid public chunks existed at ranks 6–10.
- Running `(cmetadata->>'access_level')::int <= role` and `(cmetadata->>'is_current')::boolean = true` directly inside PostgreSQL guarantees that the top $K$ retrieved chunks are **already 100% authorized and active**.

### 2. Why a Custom `PgFTSRetriever` Instead of in-memory BM25
LangChain's standard `BM25Retriever` operates in-memory on pre-loaded document objects. Applying RBAC to in-memory BM25 would require pre-filtering all documents per user role into memory.
Our custom `PgFTSRetriever` executes standard PostgreSQL `websearch_to_tsquery('english', query)` against a GIN index on `to_tsvector('english', document)` with strict SQL `WHERE` clauses.

### 3. Why Policy Versioning Uses `is_current` Flags
Universities do not destroy outdated policies; historical records must be retained for audits and transcripts. During ingestion, the registry checks the latest `effective_date` per `doc_family`. Outdated versions are marked `is_current = false`. They remain stored in PostgreSQL for auditability, but are excluded at query time.

### 4. Why Pydantic Structured Output with Pre-LLM Shortcut
If the hybrid retriever returns 0 chunks (either because the topic doesn't exist or because the user's role was blocked), the pipeline short-circuits and immediately returns `CampusAnswer(found=False, answer="I don't have information on that.", citations=[])`. This cuts latency, saves LLM API costs, and prevents hallucinations.

---

## 📊 Benchmark & Evaluation Scorecard

### 1. 50-Question Benchmark Dataset (`eval/questions.jsonl`)
The system was benchmarked across 50 questions spanning all 6 case categories:

| Category | Description | Sample Query | Result |
|---|---|---|:---:|
| `outdated_vs_new` | Superseded policy disambiguation | *"What is the minimum attendance to sit in exams?"* | **100% (8/8)** |
| `restricted` | RBAC isolation across student/prof/admin | *"How are faculty grades moderated?" (Student)* | **100% (10/10)** |
| `exact_match` | Alphanumeric form codes & course codes | *"What is Form F-12 used for?"* | **100% (8/8)** |
| `table` | Multi-column fee structures | *"What is the fee for B.Tech CSE Semester 1?"* | **100% (8/8)** |
| `normal` | General campus policy and exam rules | *"What happens if a student arrives 20m late?"* | **100% (8/8)** |
| `not_covered` | Out-of-domain refusal verification | *"What is the cafeteria lunch timing?"* | **100% (8/8)** |
| **OVERALL** | **Full 50-Question Benchmark** | — | **100% (50/50)** |

### 2. Automated Test Suite (`pytest`)
**13/13 passing tests** running in CI/local:
- `tests/test_security.py` (5 tests):
  - `test_student_never_sees_faculty_docs`
  - `test_professor_can_see_faculty_docs`
  - `test_professor_never_sees_admin_only`
  - `test_admin_can_see_all_documents`
  - `test_outdated_policy_never_returned`
- `tests/test_api.py` (8 tests):
  - `test_frontend_served`
  - `test_unauthenticated_request_rejected` (401)
  - `test_invalid_token_rejected` (401)
  - `test_login_success` (OAuth2 JWT)
  - `test_login_wrong_credentials` (401)
  - `test_user_me_profile`
  - `test_student_cannot_access_faculty_doc` (RBAC)
  - `test_professor_can_access_faculty_doc` (RBAC)

---

## 🚀 Quickstart Guide

### 1. Clone & Setup Dependencies
```bash
git clone https://github.com/SimranDangol/Campus_Knowledge_Assistant_RAG.git
cd Campus_Knowledge_Assistant_RAG
uv sync
```

### 2. Configure Environment (`.env`)
```env
GROQ_API_KEY="your-groq-api-key"
DATABASE_URL="postgresql://postgres:pass@localhost:5432/postgres"
JWT_SECRET="campus-rag-dev-secret-change-in-prod"
```

### 3. Start PostgreSQL with pgvector (Docker)
```bash
docker run -d --name pgvector -e POSTGRES_PASSWORD=pass -p 5432:5432 pgvector/pgvector:pg16
```

### 4. Ingest Documents & Build GIN Index
```bash
uv run python src/generate_pdfs.py
uv run python src/ingest.py
```

### 5. Run Tests & Evaluation
```bash
# Run 13/13 automated security & API tests
uv run pytest -v

# Run the 50-question evaluation benchmark
uv run python src/evaluate.py
```

### 6. Start the Application & Web UI
```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
```
Open **[http://127.0.0.1:8080/app](http://127.0.0.1:8080/app)** in your browser.

---

## 🛠️ Tech Stack

* **Vector Database**: PostgreSQL 16 + `pgvector` (`langchain-postgres`)
* **Keyword Search**: PostgreSQL Full-Text Search (`tsvector` + GIN Index)
* **Hybrid Fusion**: `langchain-classic` (`EnsembleRetriever` with RRF)
* **Embedding Model**: `BAAI/bge-small-en-v1.5` (via `langchain-huggingface`)
* **LLM**: Groq API (`qwen/qwen3.8-27b`) with Pydantic structured outputs
* **API & Security**: FastAPI, OAuth2 Password Bearer, JWT (`python-jose`), `bcrypt`
* **Frontend**: Vanilla HTML5, CSS3 Glassmorphic Design, ES6 JavaScript
* **Testing & Benchmarking**: Pytest, Custom 50-question benchmark runner
