"""Live-feed anomaly detection.

Frames arrive from the Android app over /ws/capture-feed. Only the most
recent CLIP_LEN frames are kept (older ones are overwritten, so there is never
a backlog). Every LIVE_CLIP_STRIDE new frames, that window is turned into one
clip feature (same as the upload pipeline), appended to a rolling history of
the last MAX_CLIPS_PER_BAG clip features, and the LSTM scores the history; the
newest clip's score decides Normal / Anomaly for the live view.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np

from app.config import Settings
from app.services.anomaly_engine import AnomalyEngine
from app.services.ws_hub import LiveFeedHub

logger = logging.getLogger("live_processor")


class LiveProcessor:
    def __init__(self, engine: AnomalyEngine, hub: LiveFeedHub, settings: Settings) -> None:
        self.engine = engine
        self.hub = hub
        self.settings = settings
        self._frames: deque[bytes] = deque(maxlen=settings.CLIP_LEN)
        self._features: deque[np.ndarray] = deque(maxlen=settings.MAX_CLIPS_PER_BAG)
        self._new_frames = 0
        self._camera_name: Optional[str] = None
        self._in_anomaly = False
        self._generation = 0
        self._event = asyncio.Event()

    def start_stream(self, camera_name: str) -> None:
        self.reset()
        self._camera_name = camera_name

    def reset(self) -> None:
        self._generation += 1
        self._frames.clear()
        self._features.clear()
        self._new_frames = 0
        self._in_anomaly = False
        self._camera_name = None

    def publish(self, frame_bytes: bytes) -> None:
        self._frames.append(frame_bytes)
        self._new_frames += 1
        self._event.set()

    def _analyze(self, frames: list[bytes], history: list[np.ndarray]) -> tuple[np.ndarray, float]:
        decoded = []
        for i in self.engine.sample_indices(len(frames)):
            img = cv2.imdecode(np.frombuffer(frames[i], dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                decoded.append(img)
        if not decoded:
            raise ValueError("no decodable frames in clip")
        feature = self.engine.clip_feature(decoded)
        scores = self.engine.score_features(np.stack(history + [feature]))
        return feature, float(scores[-1])

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            try:
                await self._event.wait()
                self._event.clear()
                if len(self._frames) < self.settings.CLIP_LEN or self._new_frames < self.settings.LIVE_CLIP_STRIDE:
                    continue

                frames = list(self._frames)
                history = list(self._features)
                generation = self._generation
                camera_name = self._camera_name
                self._new_frames = 0

                start = time.time()
                feature, score = await loop.run_in_executor(None, self._analyze, frames, history)
                elapsed = time.time() - start

                if generation != self._generation:
                    continue  # stream stopped/restarted while this clip was being scored

                self._features.append(feature)
                is_anomaly = score >= self.settings.ANOMALY_THRESHOLD
                new_anomaly = is_anomaly and not self._in_anomaly
                self._in_anomaly = is_anomaly

                logger.info(
                    "[%s] camera=%s time=%.3fs score=%.4f anomaly=%s",
                    datetime.now(timezone.utc).isoformat(), camera_name, elapsed, score, is_anomaly,
                )
                await self.hub.broadcast_event(
                    {
                        "type": "analysis",
                        "camera_name": camera_name,
                        "is_anomaly": is_anomaly,
                        "new_anomaly": new_anomaly,
                        "score": round(score, 4),
                        "threshold": self.settings.ANOMALY_THRESHOLD,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("live analysis iteration failed")
