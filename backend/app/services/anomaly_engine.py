"""ResNet50 feature extractor + LSTM scorer, ported from the training notebook
(AI_CCTV_rebuilt/cctv_anomaly_detection_local.ipynb) so inference matches how
best_model.pt was trained: frozen ImageNet ResNet50 -> one 2048-d vector per
clip (mean of FRAMES_PER_CLIP_SAMPLED frames) -> LSTM -> per-clip score in [0, 1].
"""

from __future__ import annotations

import threading

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models

from app.config import Settings

FEATURE_DIM = 2048


class LSTMAnomalyScorer(nn.Module):
    def __init__(self, input_dim: int = FEATURE_DIM, hidden_dim: int = 256, num_layers: int = 1, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim, hidden_size=hidden_dim,
            num_layers=num_layers, batch_first=True, bidirectional=False,
        )
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out).squeeze(-1)  # (batch, num_clips)


def _resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("DEVICE=cuda but PyTorch cannot see a CUDA GPU (install a CUDA build of torch).")
    return requested


class AnomalyEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.device = _resolve_device(settings.DEVICE)
        self.use_amp = settings.USE_AMP and self.device == "cuda"

        if not settings.MODEL_PATH.is_file():
            raise FileNotFoundError(f"Model file not found: {settings.MODEL_PATH} (set MODEL_PATH in backend/.env)")

        # Uses the torchvision-cached ImageNet weights; downloads them on the very first run.
        weights = models.ResNet50_Weights.IMAGENET1K_V2
        backbone = models.resnet50(weights=weights)
        backbone.fc = nn.Identity()
        backbone.eval().to(self.device)
        for p in backbone.parameters():
            p.requires_grad = False
        self.backbone = backbone
        self.preprocess = weights.transforms()

        scorer = LSTMAnomalyScorer()
        state = torch.load(settings.MODEL_PATH, map_location=self.device, weights_only=True)
        scorer.load_state_dict(state)
        scorer.eval().to(self.device)
        self.scorer = scorer

        # One GPU/CPU model shared by uploads and the live feed.
        self._lock = threading.Lock()

    def sample_indices(self, clip_size: int) -> np.ndarray:
        n = self.settings.FRAMES_PER_CLIP_SAMPLED
        if clip_size <= n:
            return np.arange(clip_size)
        return np.linspace(0, clip_size - 1, n).astype(int)

    @torch.no_grad()
    def clip_feature(self, frames_bgr: list[np.ndarray]) -> np.ndarray:
        """Mean ResNet50 feature of already-sampled BGR frames -> (2048,)."""
        batch = []
        for frame_bgr in frames_bgr:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            tensor = self.preprocess(torch.from_numpy(frame_rgb).permute(2, 0, 1))
            batch.append(tensor)
        batch_t = torch.stack(batch).to(self.device)
        with self._lock:
            with torch.autocast(device_type=self.device, enabled=self.use_amp):
                feats = self.backbone(batch_t)
        return feats.float().mean(dim=0).cpu().numpy()

    @torch.no_grad()
    def score_features(self, features: np.ndarray) -> np.ndarray:
        """(num_clips, 2048) -> (num_clips,) anomaly score per clip."""
        x = torch.from_numpy(features.astype(np.float32)).unsqueeze(0).to(self.device)
        with self._lock:
            with torch.autocast(device_type=self.device, enabled=self.use_amp):
                scores = self.scorer(x)
        return scores.float().squeeze(0).cpu().numpy()
