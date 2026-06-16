"""Tests for subject config path handling and id safety.

config.py imports only pydantic + yaml + text_utils, so these run without the
heavy backend stack:
    python -m pytest tests/test_config.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _fresh_config(tmp_dir):
    import os
    os.environ["DATA_DIR"] = tmp_dir
    from backend.core import config
    config.get_app_config.cache_clear()
    return config


def test_create_subject_rejects_unsafe_ids():
    config = _fresh_config(tempfile.mkdtemp())
    for bad in ["../evil", "a/b", "x..y/", "with space", "", "..", "a/../b"]:
        try:
            config.create_subject_on_disk(bad, "Bad")
            assert False, f"accepted unsafe id {bad!r}"
        except ValueError:
            pass


def test_create_subject_accepts_safe_id():
    config = _fresh_config(tempfile.mkdtemp())
    cfg = config.create_subject_on_disk("history_101", "History 101")
    assert cfg.subject_id == "history_101"
    assert cfg.vector_collection == "subject_history_101"
    assert cfg.input_folder.endswith("subjects/history_101/raw")


def test_input_folder_prefix_strip_is_literal():
    # The old lstrip("data/") bug ate any leading d/a/t/ chars. removeprefix
    # must only strip the literal "data/" prefix.
    assert "documents/raw".removeprefix("data/") == "documents/raw"
    assert "data/subjects/x/raw".removeprefix("data/") == "subjects/x/raw"
    assert "attic/notes".removeprefix("data/") == "attic/notes"
