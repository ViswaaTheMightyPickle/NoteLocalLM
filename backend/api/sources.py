import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.models import Chunk

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/{chunk_id}")
def get_source(chunk_id: str, db: Session = Depends(get_db)):
    chunk = db.query(Chunk).filter_by(id=chunk_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {
        "chunk_id": chunk.id,
        "subject_id": chunk.subject_id,
        "text": chunk.text,
        "metadata": json.loads(chunk.metadata_json or "{}"),
    }
