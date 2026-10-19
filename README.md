# Campus Knowledge Assistant

A production-grade Retrieval-Augmented Generation (RAG) service designed for querying university policies, course catalogs, and administrative handbooks. It features database-level Role-Based Access Control (RBAC), hybrid search (PGVector + PostgreSQL full-text search) with cross-encoder reranking, policy versioning, and an interactive UI.

## Overview

University policy documents require strict access control and deterministic citation backing. Students should not be able to retrieve confidential faculty grading guides or disciplinary committee records, and queries must always resolve to the most recent policy version without discarding historical audit trails.

This system addresses these requirements by enforcing permission and version filters directly inside the PostgreSQL query engine, ensuring restricted chunks never leave the database.

## System Architecture

```
                                [PDF Documents]
                                       │
                              [Docling Parser]
                        (Table-aware Hybrid Chunker)
                                       │
                         [Metadata Registry & Versioning]
                        (access_level, is_current, page)
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
             [BGE Embeddings]                 [PostgreSQL GIN FTS]
                      │                                 │
                      └────────────────┬────────────────┘
                                       ▼
                       [PostgreSQL 16 + pgvector Store]
                                       │
═══════════════════════════════════════╪═══════════════════════════════════════
                                Runtime Query
═══════════════════════════════════════╪═══════════════════════════════════════
                                       │
    [Client / Web UI] ──► [JWT Auth: role & permissions]
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
           [Vector Similarity]                 [Keyword Search]
           (access_level <= role)             (access_level <= role)
           (is_current = true)                (is_current = true)
                      │                                 │
                      └────────────────┬────────────────┘
                                       ▼
                          [Ensemble Retriever (RRF)]
                                       │
                         [BGE Cross-Encoder Reranker]
                                       │
                         ┌─────────────┴─────────────┐
                    (Docs Found)                 (No Docs)
                         │                           │
                         ▼                           ▼
                 [Groq LLM (Qwen)]          [Refusal Shortcut]
                         │                 ("No information...")
                         ▼
             [Structured CampusAnswer]
          (found, answer, citations)
```

## Core Features

- **Hybrid Retrieval with Cross-Encoder Reranking**: Combines dense vector similarity (`BAAI/bge-small-en-v1.5`) via `pgvector` with keyword search (`websearch_to_tsquery` over a GIN index). Results are merged via Reciprocal Rank Fusion (RRF) and scored through a `bge-reranker-base` cross-encoder.
- **Database-Level RBAC**: Permission filtering (`access_level <= user_level`) is applied in SQL `WHERE` clauses for both dense and keyword retrieval. Unauthorized text never enters application memory or LLM context windows.
- **Temporal Policy Versioning**: Superseded documents are preserved for auditability with `is_current = false`. Ingestion automatically identifies and flags older versions within the same document family.
- **Refusal Short-Circuit**: If retrieval yields 0 authorized chunks, the pipeline returns a structured refusal immediately without invoking the LLM, reducing latency and avoiding hallucinations.
- **LangGraph State Machine**: Supports conditional query execution via an agentic state graph (`retrieve` -> `grade/route` -> `generate` / `refuse`) through `/ask/graph` or the UI toggle.
- **Observability**: Optional distributed tracing via Langfuse callbacks.

## Demo Users (RBAC)

The built-in web interface provides three test profiles:

| Username | Password | Role | Access Level | Permitted Scope |
|---|---|---|---|---|
| `alice` | `studentpass` | student | 1 | Public student handbook, 2025 attendance policy, exam regulations, fee structure |
| `bob` | `profpass` | professor | 2 | Level 1 docs + confidential faculty grading guidelines |
| `carol` | `adminpass` | admin | 3 | All documents including disciplinary committee records |

## Local Development

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for local PostgreSQL + pgvector) or a hosted Postgres instance (e.g., Supabase)

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/SimranDangol/Campus_Knowledge_Assistant_RAG.git
cd Campus_Knowledge_Assistant_RAG
uv sync --extra observability
```

### 2. Configure Environment (`.env`)
Create a `.env` file in the project root:
```env
GROQ_API_KEY="your-groq-api-key"
DATABASE_URL="postgresql://postgres:password@localhost:5432/postgres"
JWT_SECRET="development-secret-key"
```

Optional settings:
- `ENVIRONMENT`: Set to `production` to enforce a strict `JWT_SECRET`.
- `RERANKER_ENABLED`: Set to `false` to disable the cross-encoder stage.
- `RERANKER_MODEL`: Custom Hugging Face model identifier (default: `BAAI/bge-reranker-base`).
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`: Tracing configuration.

### 3. Database Setup (Docker)
If running Postgres locally:
```bash
docker run -d --name pgvector -e POSTGRES_PASSWORD=password -p 5432:5432 pgvector/pgvector:pg16
```

### 4. Document Ingestion
Parse and ingest the registered policy PDFs:
```bash
uv run python src/ingest.py
```
*(To regenerate the synthetic PDF documents from source, run `uv run python src/generate_pdfs.py` beforehand).*

### 5. Running the Application
Start the FastAPI server:
```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
```

- Web UI: http://127.0.0.1:8080/app
- Interactive API Docs: http://127.0.0.1:8080/docs

## Testing & Evaluation

### Automated Tests
Run the deterministic test suite (tests RBAC filters, versioning, API endpoints, and graph routing without requiring external LLM calls):
```bash
uv run pytest -v
```

### 50-Question Benchmark
Evaluate retrieval precision, document citations, and refusal correctness across 50 categorized test queries:
```bash
uv run python src/evaluate.py
```

To run with Ragas LLM-judge metrics (faithfulness, answer relevance, context precision/recall):
```bash
uv run --extra evaluation python src/evaluate.py --ragas
```

## Docker Deployment

Build and run the container locally:
```bash
docker build -t campus-rag .
docker run -p 8080:7860 --env-file .env campus-rag
```

The container defaults to port `7860` for direct compatibility with Hugging Face Spaces (Docker SDK), while dynamically binding to `${PORT}` when deployed on platforms like Render or Cloud Run.
