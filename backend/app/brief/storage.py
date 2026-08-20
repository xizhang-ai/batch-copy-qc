from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..domain.errors import DomainError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PROJECT_ATTACHMENTS = 20


def validate_display_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise DomainError("BRIEF_FILENAME_INVALID", "Invalid brief filename")
    return name


async def save_upload(upload: UploadFile, upload_dir: Path) -> tuple[str, Path, int]:
    display_name = validate_display_name(upload.filename or "")
    suffix = Path(display_name).suffix.lower()
    if suffix not in {".txt", ".md", ".docx"}:
        raise DomainError(
            "BRIEF_FORMAT_UNSUPPORTED",
            "Only txt, md and docx briefs are supported",
            status_code=415,
        )
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4()}{suffix}"
    target = upload_dir / stored_name
    descriptor, temporary_name = tempfile.mkstemp(dir=upload_dir, suffix=".upload")
    size = 0
    try:
        with os.fdopen(descriptor, "wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise DomainError(
                        "BRIEF_FILE_TOO_LARGE", "Brief exceeds 10 MB", status_code=413
                    )
                stream.write(chunk)
        if size == 0:
            raise DomainError("BRIEF_FILE_EMPTY", "Brief file is empty")
        os.replace(temporary_name, target)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return display_name, target, size
