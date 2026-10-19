"""Tests for the offline answer-reference checks."""

from src.chain import CampusAnswer, Citation
from src.evaluate import score_answer


def test_positive_answer_requires_expected_document_and_key_terms():
    question = {
        "case_type": "outdated_vs_new",
        "expected_doc": "Attendance Policy 2025",
        "expected_answer": "70% under Attendance Policy 2025",
    }
    answer = CampusAnswer(
        found=True,
        answer="Minimum attendance is 70% under Attendance Policy 2025.",
        citations=[Citation(document="Attendance Policy 2025", page=2)],
    )

    passed, _ = score_answer(question, answer, [])

    assert passed


def test_positive_answer_fails_when_expected_fact_is_missing():
    question = {
        "case_type": "exact_match",
        "expected_doc": "Student Handbook",
        "expected_answer": "CS-101 and CS-201 with grade C or higher",
    }
    answer = CampusAnswer(
        found=True,
        answer="CS-301 requires prior coursework.",
        citations=[Citation(document="Student Handbook", page=2)],
    )

    passed, detail = score_answer(question, answer, [])

    assert not passed
    assert detail.startswith("FAILED: Expected-answer key-term coverage")


def test_restricted_answer_must_be_a_refusal_without_citations():
    question = {"case_type": "restricted"}
    answer = CampusAnswer(
        found=True,
        answer="I don't have information on that.",
        citations=[Citation(document="Grading Guidelines for Faculty", page=2)],
    )

    passed, _ = score_answer(question, answer, [])

    assert not passed
