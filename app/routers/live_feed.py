"""Android capture endpoint + browser viewer endpoint.

/ws/capture-feed keeps the auto_identification protocol the Android app
already speaks: first a JSON text message {"camera_name", "type"}, answered
with {"status": "registered", ...}, then binary JPEG frames. Public, no login.
"""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_hub import hub

logger = logging.getLogger("live_feed_router")

router = APIRouter(tags=["live-feed"])

CAMERA_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _sanitize_camera_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        name = "camera_unknown"
    if not name.startswith("camera_"):
        name = f"camera_{name}"
    return CAMERA_NAME_RE.sub("_", name)


@router.websocket("/ws/capture-feed")
async def capture_feed_ws(websocket: WebSocket):
    await websocket.accept()
    processor = websocket.app.state.processor
    camera_name: str | None = None
    streaming = False

    try:
        handshake = json.loads(await websocket.receive_text())
        camera_name = _sanitize_camera_name(handshake.get("camera_name", ""))
        feed_type = handshake.get("type") if handshake.get("type") in ("live_feed", "register_desk") else "live_feed"

        await websocket.send_json({"status": "registered", "camera_name": camera_name, "type": feed_type})

        if feed_type == "live_feed":
            streaming = True
            processor.start_stream(camera_name)
            await hub.broadcast_event({"type": "stream_started", "camera_name": camera_name})

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            frame_bytes = message.get("bytes")
            if frame_bytes is None or not streaming:
                continue

            await hub.broadcast_frame(frame_bytes)
            processor.publish(frame_bytes)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("capture_feed_ws error (camera=%s)", camera_name)
    finally:
        if streaming:
            processor.reset()
            await hub.broadcast_event({"type": "stream_ended", "camera_name": camera_name})


@router.websocket("/ws/live-feed")
async def live_feed_viewer_ws(websocket: WebSocket):
    """Browser viewer: receives binary frames and JSON analysis events."""
    await websocket.accept()
    await hub.add_viewer(websocket)
    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("live_feed_viewer_ws error")
    finally:
        await hub.remove_viewer(websocket)
