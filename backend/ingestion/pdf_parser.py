from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF


def parse_pdf(file_path: Path, subject_id: str) -> Iterator[dict]:
    """Yield page-level dicts with text and metadata."""
    doc = fitz.open(str(file_path))
    filename = file_path.name
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if not text:
            continue
        # Try to extract first bold/large text as heading
        heading = _extract_heading(page)
        yield {
            "text": text,
            "metadata": {
                "source_file": filename,
                "page_number": page_num,
                "heading": heading,
                "subject_id": subject_id,
                "document_type": "pdf",
            },
        }
    doc.close()


def _extract_heading(page) -> str:
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                size = span.get("size", 0)
                flags = span.get("flags", 0)
                is_bold = bool(flags & 2**4)
                if text and (size > 12 or is_bold):
                    return text[:200]
    return ""
