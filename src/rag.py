"""
rag.py - Compatibility wrapper forwarding to chain.py.
In Part B, this is renamed to chain.py.
"""

from src.chain import ask, retrieve, store, format_docs, CampusAnswer, Citation, ROLE_LEVEL, NO_INFO

__all__ = [
    "ask",
    "retrieve",
    "store",
    "format_docs",
    "CampusAnswer",
    "Citation",
    "ROLE_LEVEL",
    "NO_INFO",
]
