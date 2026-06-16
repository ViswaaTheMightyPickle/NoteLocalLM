import os
import glob
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class AppConfig(BaseModel):
    qdrant_url: str = "http://qdrant:6333"
    ollama_url: str = "http://ollama:11434"
    sqlite_path: str = "/data/app.db"
    data_dir: str = "/data"
    default_embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    default_chat_model: str = "mistral-nemo:12b"
    default_quiz_model: str = "mistral-nemo:12b"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    retrieval_top_k: int = 5
    chunk_target_tokens: int = 700
    chunk_overlap_tokens: int = 100
    embed_batch_size: int = 32


class SubjectConfig(BaseModel):
    subject_id: str
    display_name: str
    source_language: str = "auto"
    output_language: str = "en"
    input_folder: str
    vector_collection: str
    chat_model: str = "mistral-nemo:12b"
    quiz_model: str = "mistral-nemo:12b"
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    config_path: Optional[str] = None


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    config_path = Path(__file__).parent.parent.parent / "config" / "app_config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    # Environment variables override yaml
    overrides = {
        "qdrant_url": os.getenv("QDRANT_URL"),
        "ollama_url": os.getenv("OLLAMA_URL"),
        "sqlite_path": os.getenv("SQLITE_PATH"),
        "data_dir": os.getenv("DATA_DIR"),
    }
    for k, v in overrides.items():
        if v:
            data[k] = v
    return AppConfig(**data)


def get_data_dir() -> Path:
    cfg = get_app_config()
    return Path(cfg.data_dir)


def list_subject_configs() -> list[SubjectConfig]:
    data_dir = get_data_dir()
    subjects_dir = data_dir / "subjects"
    if not subjects_dir.exists():
        return []
    configs = []
    for config_file in sorted(subjects_dir.glob("*/config.yaml")):
        try:
            with open(config_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            cfg = SubjectConfig(**data, config_path=str(config_file))
            # Resolve input_folder relative to data_dir if not absolute
            if not Path(cfg.input_folder).is_absolute():
                cfg.input_folder = str(data_dir / cfg.input_folder.lstrip("data/"))
            configs.append(cfg)
        except Exception as e:
            print(f"[config] Failed to load {config_file}: {e}")
    return configs


def get_subject_config(subject_id: str) -> Optional[SubjectConfig]:
    for cfg in list_subject_configs():
        if cfg.subject_id == subject_id:
            return cfg
    return None
