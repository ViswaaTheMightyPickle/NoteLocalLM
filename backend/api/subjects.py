import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import (
    MODEL_TIERS,
    create_subject_on_disk,
    get_subject_config,
    list_subject_configs,
    slugify,
)
from backend.core.database import get_db, SessionLocal
from backend.core.models import Document
from backend.core.text_utils import safe_filename
from backend.ingestion.ingestor import ingest_subject

router = APIRouter(prefix="/subjects", tags=["subjects"])
logger = logging.getLogger(__name__)

_ingest_status: dict[str, dict] = {}

_ALLOWED_EXTENSIONS = {".pdf", ".csv", ".txt", ".md"}
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB per file


# ── Models catalogue (must be before /{subject_id} routes) ───────────────────
@router.get("/models/tiers")
def model_tiers():
    return list(MODEL_TIERS.values())


# ── List ──────────────────────────────────────────────────────────────────────
@router.get("")
def list_subjects():
    return [
        {
            "subject_id": c.subject_id,
            "display_name": c.display_name,
            "source_language": c.source_language,
            "output_language": c.output_language,
            "input_folder": c.input_folder,
            "chat_model": c.chat_model,
            "quiz_model": c.quiz_model,
        }
        for c in list_subject_configs()
    ]


# ── Create ────────────────────────────────────────────────────────────────────
class CreateSubjectRequest(BaseModel):
    display_name: str
    subject_id: str = ""
    source_language: str = "auto"
    output_language: str = "en"
    chat_model: str = ""
    quiz_model: str = ""


@router.post("")
def create_subject(req: CreateSubjectRequest):
    from backend.core.config import DEFAULT_MODEL

    subject_id = req.subject_id.strip() or slugify(req.display_name)
    if not subject_id:
        raise HTTPException(status_code=422, detail="Could not derive a subject ID from the display name.")

    if get_subject_config(subject_id):
        raise HTTPException(status_code=409, detail=f"Subject '{subject_id}' already exists.")

    chat_model = req.chat_model or DEFAULT_MODEL
    quiz_model = req.quiz_model or DEFAULT_MODEL

    cfg = create_subject_on_disk(
        subject_id=subject_id,
        display_name=req.display_name,
        source_language=req.source_language,
        output_language=req.output_language,
        chat_model=chat_model,
        quiz_model=quiz_model,
    )
    return {
        "subject_id": cfg.subject_id,
        "display_name": cfg.display_name,
        "input_folder": cfg.input_folder,
        "chat_model": cfg.chat_model,
        "quiz_model": cfg.quiz_model,
    }


# ── Upload files ──────────────────────────────────────────────────────────────
@router.post("/{subject_id}/files")
async def upload_files(subject_id: str, files: list[UploadFile] = File(...)):
    cfg = get_subject_config(subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    raw_dir = Path(cfg.input_folder).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved, errors = [], []
    for f in files:
        original = f.filename or "file"
        safe_name = safe_filename(original)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in _ALLOWED_EXTENSIONS:
            errors.append(f"{original}: unsupported type (use PDF, CSV, TXT, MD)")
            continue

        content = await f.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            errors.append(f"{original}: too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
            continue

        dest = (raw_dir / safe_name).resolve()
        # Defence in depth: never write outside the subject's raw folder.
        if raw_dir not in dest.parents:
            errors.append(f"{original}: rejected unsafe filename")
            continue
        try:
            dest.write_bytes(content)
            saved.append(safe_name)
            logger.info(f"[upload] Saved {original} -> {dest}")
        except Exception as e:
            errors.append(f"{original}: {e}")

    return {"saved": saved, "errors": errors}


# ── List documents ────────────────────────────────────────────────────────────
@router.get("/{subject_id}/documents")
def list_documents(subject_id: str, db: Session = Depends(get_db)):
    cfg = get_subject_config(subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    # Files on disk in raw/
    raw_dir = Path(cfg.input_folder)
    disk_files = []
    if raw_dir.exists():
        for p in sorted(raw_dir.iterdir()):
            if p.suffix.lower() in _ALLOWED_EXTENSIONS:
                disk_files.append({
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "document_type": p.suffix.lower().lstrip("."),
                })

    # Ingested docs from DB
    db_docs = db.query(Document).filter_by(subject_id=subject_id).order_by(Document.ingested_at.desc()).all()
    ingested_names = {d.filename for d in db_docs}

    return {
        "subject_id": subject_id,
        "files": [
            {**f, "ingested": f["filename"] in ingested_names}
            for f in disk_files
        ],
        "last_ingested": [
            {"filename": d.filename, "ingested_at": d.ingested_at.isoformat()}
            for d in db_docs
        ],
    }


# ── Delete subject ────────────────────────────────────────────────────────────
@router.delete("/{subject_id}")
def delete_subject(subject_id: str, db: Session = Depends(get_db)):
    cfg = get_subject_config(subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    from backend.core.config import get_data_dir
    subject_dir = get_data_dir() / "subjects" / subject_id
    if subject_dir.exists():
        shutil.rmtree(subject_dir)

    from backend.core.models import Subject
    row = db.query(Subject).filter_by(subject_id=subject_id).first()
    if row:
        db.delete(row)
        db.commit()

    return {"deleted": subject_id}


# ── Ingest ────────────────────────────────────────────────────────────────────
@router.post("/{subject_id}/ingest")
def ingest(subject_id: str, background_tasks: BackgroundTasks):
    cfg = get_subject_config(subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    _ingest_status[subject_id] = {"status": "running"}

    def run():
        # Use a dedicated session — the request-scoped one is closed once this
        # endpoint returns, so it must not be reused in the background task.
        task_db = SessionLocal()
        try:
            result = ingest_subject(cfg, task_db)
            _ingest_status[subject_id] = {"status": "done", **result}
        except Exception as e:
            logger.exception(f"[ingest] Failed for {subject_id}")
            _ingest_status[subject_id] = {"status": "error", "error": str(e)}
        finally:
            task_db.close()

    background_tasks.add_task(run)
    return {"status": "started", "subject_id": subject_id}


@router.get("/{subject_id}/ingest/status")
def ingest_status(subject_id: str):
    return _ingest_status.get(subject_id, {"status": "not_started"})


