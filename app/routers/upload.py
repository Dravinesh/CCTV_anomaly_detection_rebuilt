from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.config import settings
from app.services.video_analyzer import analyze_video

logger = logging.getLogger("upload_router")

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg"}
CHUNK = 1024 * 1024


@router.post("/api/analyze-video")
def analyze_uploaded_video(request: Request, video: UploadFile = File(...)):
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix or 'unknown'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    fd, tmp_name = tempfile.mkstemp(suffix=suffix, dir=settings.UPLOAD_DIR)
    tmp_path = Path(tmp_name)
    try:
        written = 0
        with os.fdopen(fd, "wb") as out:
            while chunk := video.file.read(CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.",
                    )
                out.write(chunk)

        try:
            result = analyze_video(tmp_path, request.app.state.engine, settings)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

        result["filename"] = video.filename
        return result
    finally:
        tmp_path.unlink(missing_ok=True)
