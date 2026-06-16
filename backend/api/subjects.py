import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.config import list_subject_configs, get_subject_config
from backend.core.database import get_db
from backend.ingestion.ingestor import ingest_subject

router = APIRouter(prefix="/subjects", tags=["subjects"])
logger = logging.getLogger(__name__)

_ingest_status: dict[str, dict] = {}


@router.get("")
def list_subjects():
    configs = list_subject_configs()
    return [
        {
            "subject_id": c.subject_id,
            "display_name": c.display_name,
            "output_language": c.output_language,
            "input_folder": c.input_folder,
        }
        for c in configs
    ]


@router.post("/{subject_id}/ingest")
def ingest(subject_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    cfg = get_subject_config(subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    _ingest_status[subject_id] = {"status": "running"}

    def run():
        try:
            result = ingest_subject(cfg, db)
            _ingest_status[subject_id] = {"status": "done", **result}
        except Exception as e:
            logger.exception(f"[ingest] Failed for {subject_id}")
            _ingest_status[subject_id] = {"status": "error", "error": str(e)}

    background_tasks.add_task(run)
    return {"status": "started", "subject_id": subject_id}


@router.get("/{subject_id}/ingest/status")
def ingest_status(subject_id: str):
    return _ingest_status.get(subject_id, {"status": "not_started"})
