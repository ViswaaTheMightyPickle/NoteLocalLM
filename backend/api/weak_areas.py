from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.quiz.tracker import get_weak_areas

router = APIRouter(prefix="/weak-areas", tags=["weak-areas"])


@router.get("/{subject_id}")
def weak_areas(subject_id: str, db: Session = Depends(get_db)):
    areas = get_weak_areas(subject_id, db)
    return {"subject_id": subject_id, "weak_areas": areas}
