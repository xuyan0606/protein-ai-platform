"""Protein AI Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversations, files, auth, tools
from app.core.config import settings
from app.core.metrics import MetricsMiddleware, metrics_response

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("Starting Protein AI Platform v0.1.0")

    # Initialise DB engine and create tables (MVP dev convenience)
    from app.core.database import init_db
    await init_db()
    logger.info("Database tables ensured")

    # Discover & register tools
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    logger.info("Tools registered: %s", list(ToolRegistry._tools.keys()))

    yield
    # ---- Shutdown ----
    from app.core.database import dispose_engine
    await dispose_engine()
    logger.info("Database engine disposed")


app = FastAPI(
    title="Protein AI Platform",
    description="AI-powered protein research agent platform with MCP tool integration",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/metrics")
async def metrics():
    return metrics_response()
