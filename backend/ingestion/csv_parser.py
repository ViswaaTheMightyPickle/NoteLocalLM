import logging
from pathlib import Path
from typing import Iterator

import pandas as pd

logger = logging.getLogger(__name__)

_QUESTION_COLS = {"question", "q", "prompt", "stem", "problem"}
_ANSWER_COLS = {"answer", "a", "response", "correct_answer", "solution", "correct"}
_EXPLANATION_COLS = {"explanation", "rationale", "reason", "justification"}
_TOPIC_COLS = {"topic", "category", "subject", "concept", "chapter", "section"}
_DIFFICULTY_COLS = {"difficulty", "level", "grade", "complexity"}


def _match(col: str, candidates: set[str]) -> bool:
    return col.lower().strip() in candidates


def _find_col(columns: list[str], candidates: set[str]) -> str | None:
    for col in columns:
        if _match(col, candidates):
            return col
    return None


def parse_csv(file_path: Path, subject_id: str) -> Iterator[dict]:
    try:
        df = pd.read_csv(file_path, dtype=str).fillna("")
    except Exception as e:
        logger.warning(f"[csv_parser] Cannot read {file_path}: {e}")
        return

    cols = list(df.columns)
    q_col = _find_col(cols, _QUESTION_COLS)
    a_col = _find_col(cols, _ANSWER_COLS)

    if not q_col or not a_col:
        logger.warning(
            f"[csv_parser] {file_path.name}: could not detect question/answer columns "
            f"(found: {cols}). Falling back to full-row text."
        )
        for _, row in df.iterrows():
            text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            if text.strip():
                yield {
                    "text": text,
                    "metadata": {
                        "source_file": file_path.name,
                        "subject_id": subject_id,
                        "document_type": "csv",
                        "page_number": None,
                        "heading": None,
                    },
                }
        return

    exp_col = _find_col(cols, _EXPLANATION_COLS)
    topic_col = _find_col(cols, _TOPIC_COLS)
    diff_col = _find_col(cols, _DIFFICULTY_COLS)

    for _, row in df.iterrows():
        question = row[q_col].strip()
        answer = row[a_col].strip()
        if not question:
            continue

        parts = [f"Question: {question}", f"Answer: {answer}"]
        if exp_col and row[exp_col].strip():
            parts.append(f"Explanation: {row[exp_col].strip()}")
        if topic_col and row[topic_col].strip():
            parts.append(f"Topic: {row[topic_col].strip()}")
        if diff_col and row[diff_col].strip():
            parts.append(f"Difficulty: {row[diff_col].strip()}")

        yield {
            "text": "\n".join(parts),
            "metadata": {
                "source_file": file_path.name,
                "subject_id": subject_id,
                "document_type": "csv",
                "page_number": None,
                "heading": row[topic_col].strip() if topic_col else None,
                "csv_question": question,
                "csv_answer": answer,
            },
        }
