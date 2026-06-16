import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from backend.core.models import QuizAttempt, QuizItem


def record_attempt(item_id: str, user_answer: str, db: Session) -> dict:
    item = db.query(QuizItem).filter_by(id=item_id).first()
    if not item:
        return {"error": "Item not found"}

    correct_answer = item.answer.strip().lower()
    is_correct = user_answer.strip().lower() == correct_answer

    attempt = QuizAttempt(
        item_id=item_id,
        user_answer=user_answer,
        is_correct=is_correct,
        timestamp=datetime.utcnow(),
    )
    db.add(attempt)
    db.commit()

    return {
        "is_correct": is_correct,
        "correct_answer": item.answer,
        "explanation": item.explanation,
        "concept_tags": json.loads(item.concept_tags_json or "[]"),
    }


def get_weak_areas(subject_id: str, db: Session) -> list[dict]:
    items = db.query(QuizItem).filter_by(subject_id=subject_id).all()
    if not items:
        return []

    tag_stats: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0, "wrong_questions": []})

    for item in items:
        tags = json.loads(item.concept_tags_json or "[]")
        if not tags:
            tags = ["(untagged)"]
        attempts = item.attempts
        if not attempts:
            continue
        for attempt in attempts:
            for tag in tags:
                tag_stats[tag]["total"] += 1
                if attempt.is_correct:
                    tag_stats[tag]["correct"] += 1
                elif len(tag_stats[tag]["wrong_questions"]) < 3:
                    tag_stats[tag]["wrong_questions"].append(item.question)

    result = []
    for tag, stats in tag_stats.items():
        if stats["total"] == 0:
            continue
        accuracy = stats["correct"] / stats["total"]
        result.append({
            "concept": tag,
            "accuracy": round(accuracy, 3),
            "correct": stats["correct"],
            "total": stats["total"],
            "wrong_questions": stats["wrong_questions"],
        })

    result.sort(key=lambda x: x["accuracy"])
    return result
