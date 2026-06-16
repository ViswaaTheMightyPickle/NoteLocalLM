import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.core.config import SubjectConfig, get_app_config
from backend.core.models import QuizItem
from backend.llm import client as llm_client
from backend.llm.prompts import QUIZ_SYSTEM, QUIZ_USER
from backend.retrieval.embedder import get_embedder
from backend.retrieval.retriever import retrieve

logger = logging.getLogger(__name__)

VALID_TYPES = {"multiple_choice", "short_answer", "fill_blank", "true_false", "scenario", "flashcard", "mixed"}


def generate_quiz(
    subject_cfg: SubjectConfig,
    topic: str,
    n: int,
    difficulty: str,
    quiz_type: str,
    output_language: str,
    db: Session,
) -> list[dict]:
    cfg = get_app_config()
    if quiz_type not in VALID_TYPES:
        quiz_type = "multiple_choice"

    embedder = get_embedder(subject_cfg.embedding_model)
    query = topic if topic else f"important concepts in {subject_cfg.display_name}"
    query_vector = embedder.embed_one(query)

    chunks = retrieve(
        collection_name=subject_cfg.vector_collection,
        query_vector=query_vector,
        subject_id=subject_cfg.subject_id,
        top_k=min(n * 2, 10),
    )

    if not chunks:
        return []

    context = "\n\n---\n\n".join(
        f"[Chunk {i+1}]\n{c['text']}" for i, c in enumerate(chunks)
    )
    chunk_ids = [c["chunk_id"] for c in chunks]

    if quiz_type == "mixed":
        type_instruction = (
            "Quiz type: mixed. Vary the type across questions using a blend of "
            "multiple_choice, true_false, short_answer and fill_blank. Set each item's "
            '"quiz_type" field to the type you chose for that question.'
        )
    else:
        type_instruction = f'Quiz type: every question must be of type "{quiz_type}".'

    system = QUIZ_SYSTEM.format(output_language=output_language)
    user = QUIZ_USER.format(
        context=context,
        n=n,
        topic=topic or "general",
        difficulty=difficulty,
        type_instruction=type_instruction,
    )

    raw = llm_client.chat(
        model=subject_cfg.quiz_model,
        system_prompt=system,
        user_prompt=user,
        temperature=0.8,
    )

    items = _parse_quiz_json(raw)
    if not items:
        # Retry with stricter prompt
        logger.warning("[quiz] JSON parse failed, retrying with stricter prompt")
        user_strict = user + "\n\nIMPORTANT: Output ONLY the JSON array. Start with [ and end with ]."
        raw = llm_client.chat(
            model=subject_cfg.quiz_model,
            system_prompt=system,
            user_prompt=user_strict,
            temperature=0.3,
        )
        items = _parse_quiz_json(raw)

    if not items:
        logger.error("[quiz] Could not parse quiz JSON after retry")
        return []

    saved = []
    for item in items:
        item_id = str(uuid.uuid4())

        # Map the per-question chunk numbers the model reported back to real
        # chunk IDs. Fall back to all retrieved chunks if it didn't specify.
        item_chunk_ids = _resolve_chunk_ids(item.get("source_chunk_numbers"), chunk_ids)
        item["source_chunk_ids"] = item_chunk_ids

        # Normalise the per-item type (mixed lets the model pick per question).
        item_type = item.get("quiz_type", quiz_type)
        if item_type not in VALID_TYPES:
            item_type = "multiple_choice" if quiz_type == "mixed" else quiz_type
        item["quiz_type"] = item_type

        row = QuizItem(
            id=item_id,
            subject_id=subject_cfg.subject_id,
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            options_json=json.dumps(item.get("options", [])),
            explanation=item.get("explanation", ""),
            quiz_type=item_type,
            difficulty=item.get("difficulty", difficulty),
            concept_tags_json=json.dumps(item.get("concept_tags", [])),
            source_chunk_ids_json=json.dumps(item_chunk_ids),
            output_language=output_language,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        item["id"] = item_id
        saved.append(item)

    db.commit()
    return saved


def _resolve_chunk_ids(numbers, chunk_ids: list[str]) -> list[str]:
    """Map 1-based chunk numbers from the model to actual chunk IDs."""
    if not isinstance(numbers, list) or not numbers:
        return chunk_ids
    resolved = []
    for num in numbers:
        try:
            idx = int(num) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(chunk_ids) and chunk_ids[idx] not in resolved:
            resolved.append(chunk_ids[idx])
    return resolved or chunk_ids


def _parse_quiz_json(text: str) -> list[dict]:
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        items = json.loads(text[start : end + 1])
        return [i for i in items if isinstance(i, dict) and "question" in i and "answer" in i]
    except json.JSONDecodeError:
        return []
