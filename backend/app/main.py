from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import live_feed, upload
from app.services.anomaly_engine import AnomalyEngine
from app.services.live_processor import LiveProcessor
from app.services.ws_hub import hub

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading model from %s ...", settings.MODEL_PATH)
    engine = AnomalyEngine(settings)
    logger.info("Model ready on device=%s", engine.device)

    processor = LiveProcessor(engine, hub, settings)
    app.state.engine = engine
    app.state.processor = processor
    task = asyncio.create_task(processor.run())

    yield

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="CCTV Anomaly Detection API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(live_feed.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "device": app.state.engine.device,
        "anomaly_threshold": settings.ANOMALY_THRESHOLD,
    }
