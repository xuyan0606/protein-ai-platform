"""Protein AI Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversations, files, auth, tools, projects, data, pdb, oidc, outline_proxy, publish, ops, research
from app.core.config import settings
from app.core.metrics import MetricsMiddleware, metrics_response
from app.core.version import PROJECT_VERSION

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("Starting Protein AI Platform v%s", PROJECT_VERSION)

    # Initialise DB engine and create tables (MVP dev convenience)
    from app.core.database import init_db
    await init_db()
    logger.info("Database tables ensured")

    # Discover & register tools
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    logger.info("Tools registered: %s", list(ToolRegistry._tools.keys()))

    # Register data ingestors
    import app.data.ingestors.uniprot  # noqa
    import app.data.ingestors.pfam  # noqa
    import app.data.ingestors.pdb  # noqa
    import app.data.ingestors.alphafold  # noqa
    import app.data.ingestors.brenda  # noqa
    import app.data.ingestors.protherm  # noqa
    import app.data.ingestors.pubchem  # noqa
    import app.data.ingestors.rhea  # noqa
    import app.data.ingestors.enzengdb  # noqa
    import app.data.ingestors.local_annotations  # noqa
    from app.data.ingestor_registry import list_sources
    logger.info("Data ingestors registered: %s", list_sources())


    # Check Outline reachability (non-blocking background task)
    import asyncio as _asyncio
    _asyncio.create_task(outline_proxy.check_outline_reachable())
    yield
    # ---- Shutdown ----
    from app.core.database import dispose_engine
    await dispose_engine()
    logger.info("Database engine disposed")


app = FastAPI(
    title="Protein AI Platform",
    description="AI-powered protein research agent platform with MCP tool integration",
    version=PROJECT_VERSION,
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
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(publish.router, prefix="/api/projects", tags=["Publish"])
app.include_router(publish.conv_router, prefix="/api", tags=["Publish"])
app.include_router(data.router, prefix="/api/data", tags=["Data"])
app.include_router(pdb.router, prefix="/api/pdb", tags=["PDB"])
app.include_router(ops.router, prefix="/api/ops", tags=["Ops"])
app.include_router(research.router, prefix="/api/research", tags=["Research"])
app.include_router(oidc.router, tags=["OIDC"])  # handles /.well-known/... and /api/oidc/...


@app.get("/api/health")
async def health():
    # Keep this probe dependency-light so it remains useful during partial
    # outages and can always return a user-visible response.
    from app.tools.registry import ToolRegistry

    tool_count = len(ToolRegistry._tools)
    return {
        "status": "ok",
        "service": "protein-ai-platform",
        "version": PROJECT_VERSION,
        "tools_registered": tool_count,
        "message": "服务正常" if tool_count else "服务已启动，工具注册尚未完成",
    }


@app.get("/api/metrics")
async def metrics():
    return metrics_response()

# Outline proxy must be registered LAST — it's a catch-all that forwards
# all unmatched requests to Outline (for iframe embedding).
app.include_router(outline_proxy.router, tags=["Outline Proxy"])
