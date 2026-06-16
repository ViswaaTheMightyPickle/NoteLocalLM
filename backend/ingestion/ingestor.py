import json
import logging
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session

from backend.core.config import SubjectConfig, get_app_config
from backend.core.models import Document, Chunk, Subject
from backend.ingestion.pdf_parser import parse_pdf
from backend.ingestion.csv_parser import parse_csv
from backend.ingestion.txt_parser import parse_txt
from backend.ingestion.chunker import chunk_text
from backend.retrieval.embedder import get_embedder
from backend.retrieval.retriever import (
    get_qdrant_client, ensure_collection, delete_document_points,
)

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf": parse_pdf, ".csv": parse_csv, ".txt": parse_txt, ".md": parse_txt}


def ingest_subject(subject_cfg: SubjectConfig, db: Session) -> dict:
    cfg = get_app_config()
    input_dir = Path(subject_cfg.input_folder)
    if not input_dir.exists():
        return {"error": f"Input folder not found: {input_dir}"}

    # Ensure subject row exists
    subject_row = db.query(Subject).filter_by(subject_id=subject_cfg.subject_id).first()
    if not subject_row:
        subject_row = Subject(
            subject_id=subject_cfg.subject_id,
            display_name=subject_cfg.display_name,
            config_path=subject_cfg.config_path,
        )
        db.add(subject_row)
        db.commit()

    qdrant = get_qdrant_client()
    embedder = get_embedder(subject_cfg.embedding_model)
    ensure_collection(qdrant, subject_cfg.vector_collection, vector_size=embedder.dim())

    files = [f for f in input_dir.iterdir() if f.suffix.lower() in _SUPPORTED]
    if not files:
        return {"status": "no_files", "subject_id": subject_cfg.subject_id}

    total_chunks = 0
    processed_files = []
    skipped_files = []

    for file_path in files:
        parser = _SUPPORTED[file_path.suffix.lower()]
        logger.info(f"[ingestor] Parsing {file_path.name}")

        # Remove old document + chunks for this file (SQL and vector store)
        old_doc = (
            db.query(Document)
            .filter_by(subject_id=subject_cfg.subject_id, filename=file_path.name)
            .first()
        )
        if old_doc:
            db.delete(old_doc)
            db.commit()
        # Always purge any prior vectors for this file so re-indexing is clean,
        # even if the SQL row was lost or this is a content change.
        delete_document_points(
            qdrant, subject_cfg.vector_collection, subject_cfg.subject_id, file_path.name
        )

        # Parse and chunk BEFORE recording the document, so a file that yields no
        # text isn't falsely shown as "indexed".
        raw_chunks = []
        try:
            for page_dict in parser(file_path, subject_cfg.subject_id):
                raw_chunks.extend(
                    chunk_text(
                        page_dict["text"],
                        page_dict["metadata"],
                        target_tokens=cfg.chunk_target_tokens,
                        overlap_tokens=cfg.chunk_overlap_tokens,
                    )
                )
        except Exception as e:
            logger.warning(f"[ingestor] Failed to parse {file_path.name}: {e}")
            skipped_files.append(file_path.name)
            continue

        if not raw_chunks:
            logger.info(f"[ingestor] {file_path.name}: no extractable text — skipped")
            skipped_files.append(file_path.name)
            continue

        doc_row = Document(
            subject_id=subject_cfg.subject_id,
            filename=file_path.name,
            document_type=file_path.suffix.lower().lstrip("."),
            ingested_at=datetime.utcnow(),
        )
        db.add(doc_row)
        db.commit()
        db.refresh(doc_row)

        # Embed in batches
        texts = [c["text"] for c in raw_chunks]
        batch_size = cfg.embed_batch_size
        all_vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_vectors.extend(embedder.embed(batch))

        # Save chunks and upsert to Qdrant
        from qdrant_client.models import PointStruct

        points = []
        for chunk_dict, vector in zip(raw_chunks, all_vectors):
            import uuid as _uuid_mod
            chunk_id = str(_uuid_mod.uuid4())
            chunk_row = Chunk(
                id=chunk_id,
                document_id=doc_row.id,
                subject_id=subject_cfg.subject_id,
                text=chunk_dict["text"],
                metadata_json=json.dumps(chunk_dict["metadata"]),
            )
            db.add(chunk_row)
            points.append(
                PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload={**chunk_dict["metadata"], "chunk_id": chunk_id, "text": chunk_dict["text"]},
                )
            )

        db.commit()
        qdrant.upsert(collection_name=subject_cfg.vector_collection, points=points)
        total_chunks += len(raw_chunks)
        processed_files.append(file_path.name)
        logger.info(f"[ingestor] {file_path.name}: {len(raw_chunks)} chunks")

    return {
        "status": "ok",
        "subject_id": subject_cfg.subject_id,
        "files_processed": processed_files,
        "files_skipped": skipped_files,
        "total_chunks": total_chunks,
    }
