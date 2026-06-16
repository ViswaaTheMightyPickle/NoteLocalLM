import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from backend.core.text_utils import slugify  # re-exported for callers

# ── Model catalogue ───────────────────────────────────────────────────────────
MODEL_TIERS = {
    "fast": {
        "tier": "fast",
        "label": "Fast · Llama 3.1 8B",
        "model": "llama3.1:8b",
        "description": "~4.7 GB — quick responses, lower VRAM requirement",
    },
    "balanced": {
        "tier": "balanced",
        "label": "Balanced · Mistral Nemo 12B (4-bit)",
        "model": "mistral-nemo:12b-instruct-q4_K_M",
        "description": "~7.1 GB — 4-bit quantised, good quality (recommended)",
    },
    "powerful": {
        "tier": "powerful",
        "label": "Powerful · Qwen 2.5 14B",
        "model": "qwen2.5:14b",
        "description": "~8.7 GB — best quality, needs more VRAM",
    },
}

DEFAULT_MODEL_TIER = "balanced"
DEFAULT_MODEL = MODEL_TIERS[DEFAULT_MODEL_TIER]["model"]


def tier_for_model(model: str) -> str:
    for tier, info in MODEL_TIERS.items():
        if info["model"] == model:
            return tier
    return "balanced"


# ── Config models ─────────────────────────────────────────────────────────────
class AppConfig(BaseModel):
    qdrant_url: str = "http://qdrant:6333"
    ollama_url: str = "http://ollama:11434"
    sqlite_path: str = "/data/app.db"
    data_dir: str = "/data"
    default_embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    default_chat_model: str = DEFAULT_MODEL
    default_quiz_model: str = DEFAULT_MODEL
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
    chat_model: str = DEFAULT_MODEL
    quiz_model: str = DEFAULT_MODEL
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    config_path: Optional[str] = None


# ── Loaders ───────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    config_path = Path(__file__).parent.parent.parent / "config" / "app_config.yaml"
    data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    overrides = {
        "qdrant_url": os.getenv("QDRANT_URL"),
        "ollama_url": os.getenv("OLLAMA_URL"),
        "sqlite_path": os.getenv("SQLITE_PATH"),
        "data_dir": os.getenv("DATA_DIR"),
        "default_chat_model": os.getenv("DEFAULT_CHAT_MODEL"),
        "default_quiz_model": os.getenv("DEFAULT_QUIZ_MODEL"),
    }
    for k, v in overrides.items():
        if v:
            data[k] = v
    return AppConfig(**data)


def get_data_dir() -> Path:
    return Path(get_app_config().data_dir)


def list_subject_configs() -> list[SubjectConfig]:
    subjects_dir = get_data_dir() / "subjects"
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
            if not Path(cfg.input_folder).is_absolute():
                # Strip the literal "data/" prefix (not a character set) before
                # re-rooting under the configured data_dir.
                rel = cfg.input_folder.removeprefix("data/").lstrip("/")
                cfg.input_folder = str(get_data_dir() / rel)
            configs.append(cfg)
        except Exception as e:
            print(f"[config] Failed to load {config_file}: {e}")
    return configs


def get_subject_config(subject_id: str) -> Optional[SubjectConfig]:
    for cfg in list_subject_configs():
        if cfg.subject_id == subject_id:
            return cfg
    return None


def create_subject_on_disk(
    subject_id: str,
    display_name: str,
    source_language: str = "auto",
    output_language: str = "en",
    chat_model: str = DEFAULT_MODEL,
    quiz_model: str = DEFAULT_MODEL,
) -> SubjectConfig:
    # Defence in depth: subject_id must be a single safe path component.
    if not re.fullmatch(r"[A-Za-z0-9_]+", subject_id or ""):
        raise ValueError(f"Unsafe subject_id: {subject_id!r}")

    data_dir = get_data_dir()
    subjects_root = (data_dir / "subjects").resolve()
    subject_dir = (subjects_root / subject_id).resolve()
    if subject_dir.parent != subjects_root:
        raise ValueError(f"subject_id escapes subjects directory: {subject_id!r}")

    raw_dir = subject_dir / "raw"
    processed_dir = subject_dir / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    input_folder = str(raw_dir)
    vector_collection = f"subject_{subject_id}"
    config_path = subject_dir / "config.yaml"

    cfg_data = {
        "subject_id": subject_id,
        "display_name": display_name,
        "source_language": source_language,
        "output_language": output_language,
        "input_folder": input_folder,
        "vector_collection": vector_collection,
        "chat_model": chat_model,
        "quiz_model": quiz_model,
        "embedding_model": "paraphrase-multilingual-mpnet-base-v2",
    }
    with open(config_path, "w") as f:
        yaml.dump(cfg_data, f, default_flow_style=False, allow_unicode=True)

    return SubjectConfig(**cfg_data, config_path=str(config_path))
