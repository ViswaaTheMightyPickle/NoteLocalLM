import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.core.config import get_subject_config
from backend.core.database import get_db
from backend.quiz.generator import generate_quiz, VALID_TYPES
from backend.quiz.tracker import record_attempt

router = APIRouter(prefix="/quiz", tags=["quiz"])

_MAX_QUESTIONS = 20
_DIFFICULTIES = {"easy", "medium", "hard"}


class QuizGenerateRequest(BaseModel):
    subject_id: str
    topic: str = ""
    n: int = 5
    difficulty: str = "medium"
    quiz_type: str = "multiple_choice"
    output_language: str = "en"

    @field_validator("n")
    @classmethod
    def _clamp_n(cls, v: int) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 5
        return max(1, min(v, _MAX_QUESTIONS))

    @field_validator("difficulty")
    @classmethod
    def _valid_difficulty(cls, v: str) -> str:
        return v if v in _DIFFICULTIES else "medium"

    @field_validator("quiz_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        return v if v in VALID_TYPES else "multiple_choice"

    @field_validator("output_language")
    @classmethod
    def _sanitize_lang(cls, v: str) -> str:
        v = re.sub(r"[^A-Za-z-]", "", (v or ""))[:16]
        return v or "en"

    @field_validator("topic")
    @classmethod
    def _trim_topic(cls, v: str) -> str:
        return (v or "").strip()[:200]


class QuizAttemptRequest(BaseModel):
    item_id: str
    user_answer: str


@router.post("/generate")
def generate(req: QuizGenerateRequest, db: Session = Depends(get_db)):
    cfg = get_subject_config(req.subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{req.subject_id}' not found")

    items = generate_quiz(
        subject_cfg=cfg,
        topic=req.topic,
        n=req.n,
        difficulty=req.difficulty,
        quiz_type=req.quiz_type,
        output_language=req.output_language,
        db=db,
    )
    return {"items": items, "count": len(items)}


@router.post("/attempt")
def attempt(req: QuizAttemptRequest, db: Session = Depends(get_db)):
    result = record_attempt(req.item_id, req.user_answer, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
