"""Run the hand-scored MVP evaluation questions against the RAG pipeline."""

import json
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Fix for Windows console output encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.rag import ask


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = PROJECT_ROOT / "eval" / "questions.jsonl"


def main():
    """Print actual and expected results for manual evaluation."""
    with QUESTIONS_FILE.open(encoding="utf-8") as questions_file:
        for line_number, line in enumerate(questions_file, start=1):
            if not line.strip():
                continue
            question = json.loads(line)
            result, _ = ask(question["question"], question["role"])
            citations = ", ".join(
                f"{citation.document}, page {citation.page}"
                for citation in result.citations
            ) or "none"

            print(f"[{line_number}] {question['role']}: {question['question']}")
            print(f"  Actual:   {result.answer}")
            print(f"  Found:    {result.found}")
            print(f"  Citations: {citations}")
            print(f"  Expected: {question['expected_answer']}")
            print(f"  Expected document: {question['expected_doc'] or 'none'}")
            print()


if __name__ == "__main__":
    main()
