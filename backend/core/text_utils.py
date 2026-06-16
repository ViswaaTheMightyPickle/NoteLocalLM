"""Dependency-light text helpers (stdlib only, no heavy imports).

Kept import-clean so it is unit-testable without pydantic / sqlalchemy /
tiktoken installed.
"""
import hashlib
import re
import unicodedata

# ── Slug ──────────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s-]+", "_", text)
    return text.strip("_")[:64]


def ascii_slug(text: str) -> str:
    """ASCII-only slug: transliterate accents, drop everything non-[a-z0-9_]."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:48]


def make_subject_id(text: str) -> str:
    """Return a filesystem- and collection-safe id, never empty.

    Falls back to a deterministic hash when the input has no ASCII letters
    (e.g. a purely non-Latin subject name), so multilingual names still work.
    """
    s = ascii_slug(text)
    if s:
        return s
    digest = hashlib.md5((text or "").encode("utf-8")).hexdigest()[:8]
    return f"subject_{digest}"


# ── Upload filename safety ────────────────────────────────────────────────────
def safe_filename(name: str) -> str:
    """Return a filesystem-safe basename, preventing path traversal.

    Preserves unicode letters/digits (multilingual filenames stay readable)
    while stripping directory components, control characters and separators.
    """
    name = unicodedata.normalize("NFKC", name or "")
    # Collapse separators and keep only the final path component.
    name = re.sub(r"[\\/]+", "/", name).split("/")[-1]
    # Drop control / non-printable characters.
    name = "".join(ch for ch in name if ch.isprintable())
    # Replace anything that isn't a word char, dot, dash, underscore or space.
    name = re.sub(r"[^\w.\- ]", "_", name, flags=re.UNICODE)
    name = name.strip().strip(".")
    return (name or "file")[:200]


# ── Quiz answer matching ──────────────────────────────────────────────────────
_TF_SYNONYMS = {"t": "true", "f": "false", "yes": "true", "no": "false"}


def normalize_answer(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,:;!?\"'()[]{}")


def _letter_to_option(answer: str, options: list[str]) -> str | None:
    a = (answer or "").strip().upper()
    if len(a) == 1 and "A" <= a <= "Z" and options:
        idx = ord(a) - ord("A")
        if 0 <= idx < len(options):
            return options[idx]
    return None


def answer_matches(user_answer: str, correct_answer: str, options: list[str] | None = None) -> bool:
    """Lenient correctness check.

    Handles multiple-choice answered by letter ("A") or full option text,
    true/false synonyms, and whitespace/punctuation/case differences. Stays
    conservative for free-text answers to avoid false positives.
    """
    options = options or []

    # Resolve single-letter answers to the full option text on both sides.
    resolved_correct = _letter_to_option(correct_answer, options) or correct_answer
    resolved_user = _letter_to_option(user_answer, options) or user_answer

    nu = normalize_answer(resolved_user)
    nc = normalize_answer(resolved_correct)
    if not nu:
        return False
    if nu == nc:
        return True

    # Direct letter-vs-letter equality (e.g. both "A").
    raw_u, raw_c = normalize_answer(user_answer), normalize_answer(correct_answer)
    if raw_u and raw_u == raw_c:
        return True

    # True/False synonym matching.
    if _TF_SYNONYMS.get(nc, nc) in ("true", "false"):
        if _TF_SYNONYMS.get(nu, nu) == _TF_SYNONYMS.get(nc, nc):
            return True

    return False
