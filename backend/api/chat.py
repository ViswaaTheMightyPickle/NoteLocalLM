import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import get_subject_config, get_app_config
from backend.core.database import get_db
from backend.core.models import ChatSession, ChatMessage
from backend.llm import client as llm_client
from backend.llm.prompts import CHAT_SYSTEM, CHAT_USER
from backend.retrieval.embedder import get_embedder
from backend.retrieval.retriever import retrieve

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    subject_id: str
    question: str
    session_id: str | None = None
    output_language: str = "en"


@router.post("")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    cfg = get_subject_config(req.subject_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Subject '{req.subject_id}' not found")

    app_cfg = get_app_config()

    # Resolve or create session. A supplied id must exist AND belong to this
    # subject; otherwise we start a fresh session rather than risk FK errors or
    # mixing history across subjects.
    session_id = req.session_id
    session = (
        db.query(ChatSession).filter_by(id=session_id).first() if session_id else None
    )
    if not session or session.subject_id != req.subject_id:
        session_id = str(uuid.uuid4())
        db.add(ChatSession(
            id=session_id, subject_id=req.subject_id, created_at=datetime.utcnow()
        ))
        db.commit()

    embedder = get_embedder(cfg.embedding_model)
    query_vector = embedder.embed_one(req.question)

    chunks = retrieve(
        collection_name=cfg.vector_collection,
        query_vector=query_vector,
        subject_id=req.subject_id,
        top_k=app_cfg.retrieval_top_k,
    )

    output_lang = req.output_language or cfg.output_language

    if not chunks:
        answer = "I don't have any indexed materials for this subject yet. Please ingest documents first."
        sources = []
    else:
        context = "\n\n---\n\n".join(
            f"[Source {i+1} | {c['metadata'].get('source_file','?')} p.{c['metadata'].get('page_number','?')}]\n{c['text']}"
            for i, c in enumerate(chunks)
        )
        system = CHAT_SYSTEM.format(output_language=output_lang)
        user = CHAT_USER.format(context=context, question=req.question)
        answer = llm_client.chat(
            model=cfg.chat_model,
            system_prompt=system,
            user_prompt=user,
        )
        sources = [
            {
                "chunk_id": c["chunk_id"],
                "source_file": c["metadata"].get("source_file"),
                "page_number": c["metadata"].get("page_number"),
                "score": round(c["score"], 4),
                "text_preview": c["text"][:200],
            }
            for c in chunks
        ]

    # Persist messages
    chunk_ids = [c["chunk_id"] for c in chunks]
    db.add(ChatMessage(
        session_id=session_id, role="user", content=req.question,
        source_chunk_ids_json="[]", timestamp=datetime.utcnow(),
    ))
    db.add(ChatMessage(
        session_id=session_id, role="assistant", content=answer,
        source_chunk_ids_json=json.dumps(chunk_ids), timestamp=datetime.utcnow(),
    ))
    db.commit()

    return {"answer": answer, "session_id": session_id, "sources": sources}
