# 🎓 Campus Knowledge Assistant (Full-Version RAG Demo)

> **A full-version Retrieval-Augmented Generation (RAG) demo over university policy documents featuring PostgreSQL PGVector semantic search, Full-Text GIN keyword search, Role-Based Access Control (RBAC), temporal policy versioning, and JWT authentication.**

---

## 🌟 Key Features

1. **Exact-Match & Semantic Hybrid Retrieval**:
   - Embeddings understand high-level concepts but frequently miss exact alphanumeric course codes or form IDs.
   - We combine **PGVector cosine similarity** (`BAAI/bge-small-en-v1.5`) with **PostgreSQL Full-Text Search** (`to_tsvector` + GIN index + `ts_rank`) fused via **Reciprocal Rank Fusion (RRF)**.
   - A BGE cross-encoder reranks the filtered hybrid candidates before they reach the answer model.
   - Handles concept questions and exact alphanumeric queries like *"What is Form F-12 used for?"* or *"Prerequisites for CS-301"*.

2. **Table-Aware PDF Ingestion**:
   - Docling's `HybridChunker` preserves table structure and page provenance for citations.
   - Every registered document must parse successfully before the collection is replaced.

3. **Cryptographically Enforced Role-Based Access Control (RBAC)**:
   - Permissions are embedded in signed JWT claims (`HS256`), preventing role impersonation.
   - Permission filters (`access_level <= user_level AND is_current = True`) execute **directly inside the database engine** for both vector and keyword queries.
   - **Zero-trust security guarantee**: Restricted chunks never leave the database, never reach memory, and never leak into LLM prompts.

4. **Temporal Policy Versioning ("Newest Policy Wins")**:
   - Outdated documents are **never deleted** (preserving audit history), but flagged with `is_current = false` during ingestion.
   - Queries automatically retrieve only active policies (e.g. Attendance Policy 2025's 70% threshold cleanly overrides Attendance Policy 2023's 75% rule).

5. **Hallucination Prevention & Refusal Shortcut**:
   - Strict system prompt with Pydantic structured output (`CampusAnswer`).
   - Short-circuit mechanism: if zero chunks pass the RBAC/version filter, the pipeline **skips the LLM entirely**, saving API costs and guaranteeing zero hallucinations.

6. **Optional Tracing & Quality Evaluation**:
   - Langfuse callbacks trace API requests when configured.
   - Ragas metrics are available through the `evaluation` extra; they are not run by the default benchmark.

7. **Agentic State Machine with LangGraph (Upgrade 11 - Stretch Goal)**:
   - Dynamic cyclic agent graph (`src/graph.py`) with explicit State: `retrieve` ➔ `grade/route` ➔ `answer` or `refuse`.
   - Dedicated `/ask/graph` endpoint and UI toggle for executing queries via the compiled state machine.

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
[Docling + HybridChunker] ──► [Page-Provenance, Table-Aware Chunks]
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
                                    [BGE Cross-Encoder Reranker]
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

### 5. Why LangGraph Agentic Workflow (Upgrade 11)
In production RAG systems, fixed linear chains struggle to handle multi-step reasoning, conditional routing, and self-correction. LangGraph models the pipeline as a formal State Graph (`AgentState: {question, role, docs, result}`):
```
[User Query] ──► (Retrieve Node) ──► (Grade / Route) ──┬──► [Docs Found?] ──► (Answer Node) ──► END
                                                       │
                                                       └──► [No Docs?]    ──► (Refuse Node) ──► END
```
This decouples retrieval evaluation from generation, ensuring refusal logic is transparently testable as a deterministic state transition.

---

## 📊 Benchmark & Evaluation Scorecard

### 1. 50-Question Benchmark Dataset (`eval/questions.jsonl`)
The dataset contains 50 questions across all 6 case categories:

| Category | Description | Sample Query | Questions |
|---|---|---|:---:|
| `outdated_vs_new` | Superseded policy disambiguation | *"What is the minimum attendance to sit in exams?"* | 8 |
| `restricted` | RBAC isolation across student/prof/admin | *"How are faculty grades moderated?" (Student)* | 10 |
| `exact_match` | Alphanumeric form codes & course codes | *"What is Form F-12 used for?"* | 8 |
| `table` | Multi-column fee structures | *"What is the fee for B.Tech CSE Semester 1?"* | 8 |
| `normal` | General campus policy and exam rules | *"What happens if a student arrives 20m late?"* | 8 |
| `not_covered` | Out-of-domain refusal verification | *"What is the cafeteria lunch timing?"* | 8 |
| **TOTAL** | **50 questions** | Run `src/evaluate.py` to measure this checkout | **50** |

The default runner reports refusal, expected-document citation, and expected-answer key-term checks; these are a lightweight regression signal, not a substitute for judged answer quality. Add `--ragas` to collect faithfulness, answer relevance, context precision, and context recall scores. No benchmark scores are claimed here until run against a configured database and model API.

### 2. Automated Test Suite (`pytest`)
Tests cover API authentication and role propagation, SQL-level permission/version filters, version selection, Docling page provenance, and benchmark scoring. The unit tests do not require Docker or call the LLM.

---

## 🚀 Quickstart Guide

### 1. Clone & Setup Dependencies
```bash
git clone https://github.com/SimranDangol/Campus_Knowledge_Assistant_RAG.git
cd Campus_Knowledge_Assistant_RAG
uv sync --extra observability
```

### 2. Configure Environment (`.env`)
```env
GROQ_API_KEY="your-groq-api-key"
DATABASE_URL="postgresql://postgres:pass@localhost:5432/postgres"
JWT_SECRET="campus-rag-dev-secret-change-in-prod"
```
For production, set a unique `JWT_SECRET` and `ENVIRONMENT=production`. Optional
settings include `RERANKER_ENABLED=false` to disable reranking,
`RERANKER_MODEL`, `CORS_ORIGINS`, and the three `LANGFUSE_*` variables.
Reranking defaults on and downloads its model on the first retrieval;
Langfuse tracing is enabled only when both keys are set.

### 3. Start PostgreSQL with pgvector (Docker)
```bash
docker run -d --name pgvector -e POSTGRES_PASSWORD=pass -p 5432:5432 pgvector/pgvector:pg16
```

### 4. Ingest Documents & Build GIN Index
```bash
uv run python src/ingest.py
```
Run `uv run python src/generate_pdfs.py` only when you want to recreate the
sample PDFs. Ingestion validates that all registered PDFs exist and replaces
only the `campus_docs` collection.

### 5. Run Tests & Evaluation
```bash
# Run local API, retrieval-security, and evaluation unit tests
uv run pytest -v

# Run the 50-question reference-check benchmark (requires DB and Groq access)
uv run python src/evaluate.py

# Optional Ragas quality evaluation (requires the evaluation extra)
uv run --extra evaluation python src/evaluate.py --ragas
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
* **Reranking**: Sentence Transformers BGE cross-encoder
* **PDF Parsing**: Docling `HybridChunker` with page provenance
* **Embedding Model**: `BAAI/bge-small-en-v1.5` (via `langchain-huggingface`)
* **LLM**: Groq API (`qwen/qwen3.8-27b`) with Pydantic structured outputs
* **API & Security**: FastAPI, OAuth2 Password Bearer, JWT (`python-jose`), `bcrypt`
* **Frontend**: Vanilla HTML5, CSS3 Glassmorphic Design, ES6 JavaScript
* **Testing & Benchmarking**: Pytest, Custom 50-question benchmark runner
* **Optional Observability / Evaluation**: Langfuse and Ragas extras
