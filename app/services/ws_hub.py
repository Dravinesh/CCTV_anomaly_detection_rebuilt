"""Broadcasts the live feed (binary JPEG frames) and analysis events (JSON text)
from the backend to every connected browser viewer. One global feed, as in
auto_identification."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger("ws_hub")


class LiveFeedHub:
    def __init__(self) -> None:
        self._viewers: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.last_status: Optional[dict] = None  # replayed to viewers that connect mid-stream

    async def add_viewer(self, ws: WebSocket) -> None:
        async with self._lock:
            self._viewers.add(ws)
        if self.last_status is not None:
            try:
                await ws.send_json(self.last_status)
            except Exception:
                await self.remove_viewer(ws)

    async def remove_viewer(self, ws: WebSocket) -> None:
        async with self._lock:
            self._viewers.discard(ws)

    async def broadcast_frame(self, frame_bytes: bytes) -> None:
        await self._broadcast(lambda viewer: viewer.send_bytes(frame_bytes))

    async def broadcast_event(self, payload: dict) -> None:
        if payload.get("type") in ("stream_started", "analysis", "stream_ended"):
            self.last_status = payload
        await self._broadcast(lambda viewer: viewer.send_json(payload))

    async def _broadcast(self, send) -> None:
        async with self._lock:
            viewers = list(self._viewers)
        if not viewers:
            return
        results = await asyncio.gather(*(send(v) for v in viewers), return_exceptions=True)
        stale = [v for v, r in zip(viewers, results) if isinstance(r, Exception)]
        if stale:
            async with self._lock:
                for viewer in stale:
                    self._viewers.discard(viewer)


hub = LiveFeedHub()
