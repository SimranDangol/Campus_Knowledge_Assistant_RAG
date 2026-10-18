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


def evaluate_question(q: dict) -> tuple[bool, str]:
    """Score an answer against ground truth expectations."""
    res, docs = ask(q["question"], q["role"])
    case_type = q.get("case_type", "normal")
    expected_doc = q.get("expected_doc", "").strip().lower()

    # Case 1: Restricted or Not Covered queries MUST be refused
    if case_type in ("restricted", "not_covered"):
        passed = (not res.found) or ("don't have information" in res.answer.lower())
        detail = "Refusal verified" if passed else "FAILED: Leaked or hallucinated"
        return passed, detail

    # Case 2: Positive queries must be found and cite the expected document
    if not res.found:
        return False, "FAILED: Expected answer but got not found"

    cited_docs = [c.document.lower() for c in res.citations]
    if expected_doc and not any(expected_doc in cd for cd in cited_docs):
        return False, f"FAILED: Missing expected citation '{q.get('expected_doc')}'"

    return True, "PASSED: Verified with citations"


def main():
    parser = argparse.ArgumentParser(description="Evaluate Campus RAG Dataset")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions")
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
    total_start = time.time()

    for i, q in enumerate(questions, start=1):
        case_type = q.get("case_type", "normal")
        stats[case_type]["total"] += 1
        stats["overall"]["total"] += 1

        t0 = time.time()
        passed, detail = evaluate_question(q)
        elapsed = time.time() - t0

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


if __name__ == "__main__":
    main()
