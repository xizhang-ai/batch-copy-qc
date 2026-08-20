from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from ..domain.errors import DomainError

SUPPORTED_SUFFIXES = {".txt", ".md", ".docx"}


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def extract_text(path: str | Path) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DomainError(
            "BRIEF_FORMAT_UNSUPPORTED",
            "Only txt, md and docx briefs are supported",
            status_code=415,
        )
    if suffix in {".txt", ".md"}:
        text = file_path.read_text(encoding="utf-8-sig")
    else:
        document = Document(file_path)
        parts: list[str] = []
        for block in document.iter_inner_content():
            if hasattr(block, "rows"):
                for row in block.rows:
                    parts.append("\t".join(cell.text for cell in row.cells))
            else:
                parts.append(block.text)
        text = "\n".join(parts)
    result = normalize_text(text)
    if not result:
        raise DomainError("BRIEF_TEXT_EMPTY", "Brief contains no readable text")
    return result
