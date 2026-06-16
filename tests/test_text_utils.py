"""Unit tests for the dependency-light text helpers.

These cover the security- and correctness-sensitive pure functions without
needing fastapi / qdrant / sqlalchemy installed:
    python -m pytest tests/test_text_utils.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.text_utils import (  # noqa: E402
    slugify, safe_filename, normalize_answer, answer_matches,
)


# ── slugify ───────────────────────────────────────────────────────────────────
def test_slugify_basic():
    assert slugify("Organic Chemistry") == "organic_chemistry"
    assert slugify("  French   History  ") == "french_history"
    assert slugify("Data-Structures & Algorithms!") == "data_structures_algorithms"


def test_slugify_length_cap():
    assert len(slugify("x" * 200)) <= 64


# ── safe_filename (path traversal defence) ────────────────────────────────────
def test_safe_filename_strips_directories():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("/abs/path/notes.pdf") == "notes.pdf"
    assert safe_filename("..\\..\\windows\\system32\\evil.txt") == "evil.txt"


def test_safe_filename_no_traversal_remains():
    for bad in ["../x.pdf", "..", "....//x.csv", "a/b/c.md"]:
        out = safe_filename(bad)
        assert "/" not in out and "\\" not in out
        assert not out.startswith(".")


def test_safe_filename_preserves_unicode():
    # Multilingual filenames should remain readable, not be mangled to "_".
    assert safe_filename("résumé français.pdf") == "résumé français.pdf"
    assert safe_filename("笔记.txt") == "笔记.txt"


def test_safe_filename_empty_fallback():
    assert safe_filename("") == "file"
    assert safe_filename("...") == "file"


# ── normalize_answer ──────────────────────────────────────────────────────────
def test_normalize_answer():
    assert normalize_answer("  Hello, World.  ") == "hello, world"
    assert normalize_answer("THE   ANSWER!") == "the answer"  # collapses whitespace


# ── answer_matches ────────────────────────────────────────────────────────────
def test_answer_matches_plain():
    assert answer_matches("Paris", "paris")
    assert answer_matches("Paris.", "paris")
    assert not answer_matches("London", "Paris")


def test_answer_matches_multiple_choice_letter_vs_text():
    options = ["Mitochondria", "Nucleus", "Ribosome", "Golgi"]
    # Correct stored as a letter, user picked the full option text.
    assert answer_matches("Nucleus", "B", options)
    # Correct stored as full text, user answered with a letter.
    assert answer_matches("B", "Nucleus", options)
    # Both as letters.
    assert answer_matches("B", "B", options)
    # Wrong option.
    assert not answer_matches("A", "Nucleus", options)


def test_answer_matches_true_false_synonyms():
    assert answer_matches("T", "True", ["True", "False"])
    assert answer_matches("yes", "true", ["True", "False"])
    assert not answer_matches("F", "True", ["True", "False"])


def test_answer_matches_empty_is_wrong():
    assert not answer_matches("", "Paris")
    assert not answer_matches("   ", "Paris")
