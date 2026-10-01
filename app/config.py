from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _resolve(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@dataclass(frozen=True)
class Settings:
    # Model (values below match the training notebook: cctv_anomaly_detection_local.ipynb)
    MODEL_PATH: Path = field(default_factory=lambda: _resolve("MODEL_PATH", BACKEND_DIR.parent / "best_model (1).pt"))
    DEVICE: str = os.getenv("DEVICE", "auto")  # auto | cpu | cuda
    USE_AMP: bool = _bool("USE_AMP", True)
    CLIP_LEN: int = int(os.getenv("CLIP_LEN", "16"))
    FRAMES_PER_CLIP_SAMPLED: int = int(os.getenv("FRAMES_PER_CLIP_SAMPLED", "8"))
    MAX_CLIPS_PER_BAG: int = int(os.getenv("MAX_CLIPS_PER_BAG", "32"))

    # Not defined by the notebook -- untuned starting point, calibrate on your own footage.
    ANOMALY_THRESHOLD: float = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))

    # Live feed: analyse a new clip every N received frames (N = CLIP_LEN -> non-overlapping clips)
    LIVE_CLIP_STRIDE: int = int(os.getenv("LIVE_CLIP_STRIDE", "16"))

    # Upload
    UPLOAD_DIR: Path = field(default_factory=lambda: _resolve("UPLOAD_DIR", BACKEND_DIR / "uploads"))
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "500"))

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
