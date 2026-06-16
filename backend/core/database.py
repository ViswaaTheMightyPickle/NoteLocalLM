from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from backend.core.config import get_app_config


class Base(DeclarativeBase):
    pass


def get_engine():
    cfg = get_app_config()
    db_path = Path(cfg.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend.core import models  # noqa: F401 — registers all models
    Base.metadata.create_all(bind=engine)
