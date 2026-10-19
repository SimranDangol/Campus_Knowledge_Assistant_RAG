"""
evaluate.py - Benchmark the full 50-question evaluation dataset against the Campus RAG pipeline.

Evaluates 6 case categories:
1. outdated_vs_new (policy versioning: 2025 vs 2023)
2. restricted (RBAC security: student/prof asking above their access level)
3. exact_match (alphanumeric codes: Form F-12, CS-301)
4. table (structured fee tables and amounts)
5. normal (regular policy, conduct, and exam queries)
6. not_covered (out-of-domain queries: cafeteria, dean, buses)
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Fix for Windows console output encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.chain import ask

QUESTIONS_FILE = PROJECT_ROOT / "eval" / "questions.jsonl"


def score_answer(q: dict, res, docs) -> tuple[bool, str]:
    """Check refusal, expected answer terms, and citations against the reference."""
    case_type = q.get("case_type", "normal")
    expected_doc = q.get("expected_doc", "").strip().lower()

    if case_type in ("restricted", "not_covered"):
        refused = "don't have information" in res.answer.lower()
        passed = not res.found and refused and not res.citations
        detail = "Refusal verified" if passed else "FAILED: Leaked or hallucinated"
        return passed, detail

    if not res.found:
        return False, "FAILED: Expected answer but got not found"

    cited_docs = [c.document.lower() for c in res.citations]
    if expected_doc and not any(expected_doc in cd for cd in cited_docs):
        return False, f"FAILED: Missing expected citation '{q.get('expected_doc')}'"

    expected_terms = _key_terms(q.get("expected_answer", ""))
    answer_terms = set(_key_terms(res.answer))
    if expected_terms:
        matched = expected_terms & answer_terms
        coverage = len(matched) / len(expected_terms)
        if coverage < 0.5:
            return (
                False,
                f"FAILED: Expected-answer key-term coverage {len(matched)}/"
                f"{len(expected_terms)}",
            )
        return True, f"PASSED: citation + key-term coverage {len(matched)}/{len(expected_terms)}"

    return True, "PASSED: Verified with citations"


def _key_terms(text: str) -> set[str]:
    ignored = {
        "a", "an", "and", "are", "as", "at", "be", "because", "by", "does",
        "for", "from", "how", "in", "is", "it", "of", "on", "or", "the",
        "to", "under", "was", "what", "which", "who", "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in ignored and (len(token) > 2 or token.isdigit())
    }


def run_ragas(rows: list[dict]) -> None:
    """Run optional LLM-judge metrics over the already-collected answers."""
    from openai import OpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import HuggingFaceEmbeddings as RagasHuggingFaceEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        Faithfulness,
    )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required to run Ragas with the Groq judge")
    ragas_llm = llm_factory(
        model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        provider="openai",
        client=OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        ),
        temperature=0,
    )
    ragas_embeddings = RagasHuggingFaceEmbeddings(
        model="BAAI/bge-small-en-v1.5"
    )
    report = evaluate(
        EvaluationDataset.from_list(rows),
        metrics=[
            Faithfulness(llm=ragas_llm),
            AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
            ContextPrecisionWithReference(llm=ragas_llm),
            ContextRecall(llm=ragas_llm),
        ],
        llm=ragas_llm,
        embeddings=ragas_embeddings,
    )
    print("\nRagas quality metrics:")
    print(report)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Campus RAG Dataset")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions")
    parser.add_argument(
        "--ragas",
        action="store_true",
        help="Also run Ragas LLM-judge metrics (requires the evaluation extra)",
    )
    args = parser.parse_args()

    questions = []
    with QUESTIONS_FILE.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    if args.limit:
        questions = questions[:args.limit]

    print("\n=======================================================")
    print(f"   Campus RAG Benchmark: Running {len(questions)} Questions   ")
    print("=======================================================\n")

    stats = defaultdict(lambda: {"total": 0, "passed": 0})
    ragas_rows = []
    total_start = time.time()

    for i, q in enumerate(questions, start=1):
        case_type = q.get("case_type", "normal")
        stats[case_type]["total"] += 1
        stats["overall"]["total"] += 1

        t0 = time.time()
        result, docs = ask(q["question"], q["role"])
        passed, detail = score_answer(q, result, docs)
        elapsed = time.time() - t0
        ragas_rows.append(
            {
                "user_input": q["question"],
                "response": result.answer,
                "retrieved_contexts": [doc.page_content for doc in docs],
                "reference": q["expected_answer"],
            }
        )

        if passed:
            stats[case_type]["passed"] += 1
            stats["overall"]["passed"] += 1

        status_sym = "[PASS]" if passed else "[FAIL]"
        print(f"{status_sym} [{i:02d}/{len(questions):02d}] ({case_type}) [{q['role']}] {q['question']}")
        print(f"       -> {detail} ({elapsed:.2f}s)\n")

    total_time = time.time() - total_start

    print("=======================================================")
    print("                EVALUATION SCORECARD                   ")
    print("=======================================================")
    print(f"{'Category':<20} {'Passed / Total':<18} {'Accuracy':<10}")
    print("-------------------------------------------------------")
    for category, s in sorted(stats.items()):
        if category == "overall":
            continue
        acc = (s["passed"] / s["total"] * 100) if s["total"] else 0
        print(f"{category:<20} {s['passed']}/{s['total']:<16} {acc:>6.1f}%")
    print("-------------------------------------------------------")
    overall = stats["overall"]
    overall_acc = (overall["passed"] / overall["total"] * 100) if overall["total"] else 0
    print(f"{'OVERALL TOTAL':<20} {overall['passed']}/{overall['total']:<16} {overall_acc:>6.1f}%")
    print(f"Total time elapsed: {total_time:.2f}s")
    print("=======================================================\n")

    if args.ragas:
        run_ragas(ragas_rows)


if __name__ == "__main__":
    main()
