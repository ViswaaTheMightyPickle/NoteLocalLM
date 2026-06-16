from pathlib import Path
from typing import Iterator


def parse_txt(file_path: Path, subject_id: str) -> Iterator[dict]:
    text = file_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return
    yield {
        "text": text,
        "metadata": {
            "source_file": file_path.name,
            "subject_id": subject_id,
            "document_type": "txt",
            "page_number": None,
            "heading": None,
        },
    }
