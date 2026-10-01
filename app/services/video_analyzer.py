"""Uploaded-video analysis. Mirrors the notebook's clip chunking
(chunk_into_clips: CLIP_LEN-frame clips, a trailing partial clip kept only if
it has at least CLIP_LEN/2 frames) and load_and_pad (more than
MAX_CLIPS_PER_BAG clips -> evenly sub-sampled down to that many)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.config import Settings
from app.services.anomaly_engine import AnomalyEngine


def _count_frames(cap: cv2.VideoCapture) -> int:
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total > 0:
        return total
    total = 0
    while cap.grab():
        total += 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return total


def _count_clips(total_frames: int, clip_len: int) -> int:
    full, rest = divmod(total_frames, clip_len)
    return full + (1 if rest >= clip_len // 2 else 0)


def analyze_video(path: Path, engine: AnomalyEngine, settings: Settings) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Could not open the video file.")

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        clip_len = settings.CLIP_LEN
        total_frames = _count_frames(cap)
        n_clips = _count_clips(total_frames, clip_len)
        if n_clips == 0:
            raise ValueError(f"Video is too short (need at least {clip_len // 2} frames).")

        if n_clips > settings.MAX_CLIPS_PER_BAG:
            selected = set(np.linspace(0, n_clips - 1, settings.MAX_CLIPS_PER_BAG).astype(int).tolist())
        else:
            selected = set(range(n_clips))

        features: list[np.ndarray] = []
        spans: list[tuple[int, int]] = []  # (start_frame, end_frame) of each scored clip
        clip_idx = 0
        while len(features) < len(selected):
            keep = clip_idx in selected
            frames = []
            read = 0
            for _ in range(clip_len):
                if keep:
                    ok, frame = cap.read()
                    if ok:
                        frames.append(frame)
                else:
                    ok = cap.grab()
                if not ok:
                    break
                read += 1

            if read < clip_len // 2:
                break
            if keep:
                sampled = [frames[i] for i in engine.sample_indices(len(frames))]
                features.append(engine.clip_feature(sampled))
                start = clip_idx * clip_len
                spans.append((start, start + read))
            clip_idx += 1
            if read < clip_len:
                break

        if not features:
            raise ValueError("No frames could be decoded from the video.")

        scores = engine.score_features(np.stack(features))
    finally:
        cap.release()

    threshold = settings.ANOMALY_THRESHOLD
    clips = []
    for (start, end), score in zip(spans, scores):
        clips.append(
            {
                "start_frame": start,
                "end_frame": end,
                "start_sec": round(start / fps, 2) if fps > 0 else None,
                "end_sec": round(end / fps, 2) if fps > 0 else None,
                "score": round(float(score), 4),
                "is_anomaly": bool(score >= threshold),
            }
        )

    peak = int(np.argmax(scores))
    max_score = float(scores[peak])
    return {
        "is_anomaly": bool(max_score >= threshold),
        "label": "Anomaly" if max_score >= threshold else "Normal",
        "score": round(max_score, 4),
        "threshold": threshold,
        "peak_clip": peak,
        "num_clips": len(clips),
        "total_frames": total_frames,
        "fps": round(fps, 2) if fps > 0 else None,
        "clips": clips,
    }
