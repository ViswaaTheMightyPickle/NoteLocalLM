import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import init_db
from backend.retrieval.embedder import get_embedder
from backend.core.config import get_app_config
from backend.api import subjects, chat, quiz, weak_areas, sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="StudyApp API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(subjects.router)
app.include_router(chat.router)
app.include_router(quiz.router)
app.include_router(weak_areas.router)
app.include_router(sources.router)


@app.on_event("startup")
def startup():
    init_db()
    cfg = get_app_config()
    # Pre-load embedding model so first request isn't slow
    get_embedder(cfg.default_embedding_model)


@app.get("/health")
def health():
    return {"status": "ok"}
