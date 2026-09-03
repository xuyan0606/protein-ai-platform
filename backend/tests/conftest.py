"""Shared test fixtures for black-box and white-box testing."""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force SQLite for tests
os.environ["USE_SQLITE"] = "true"

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test_protein_ai.db")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine(tmp_path):
    # Keep each test isolated; a shared SQLite file races when async fixtures
    # reset metadata across tests.
    db_url = TEST_DB_URL
    if db_url.startswith("sqlite+aiosqlite:///./"):
        db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    e = create_async_engine(db_url, echo=False)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    # Import model modules before DDL so every declarative table is registered.
    import app.models  # noqa: F401
    from app.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(session) -> AsyncGenerator[AsyncClient, None]:
    from app.core.database import get_session
    from app.main import app

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def sample_enzyme_data():
    return {
        "uniprot_id": "P00519",
        "entry_name": "ABL1_HUMAN",
        "sequence": "MLEICLKLVGCKSKKGLSSSSSCYLEEALQRPVASDFEPQGLSEAARWNSKENLLAGPSENDPNLFVALYDFVASGDNTLSITKGEKLRVLGYNHNGEWCEAQTKNGQGWVPSNYITPVNSLEKHSWYHGPVSRNAAEYLLSSGINGSFLVRESESSPGQRSISLRYEGRVYHYRINTASDGKLYVSSESRFNTLAELVHHHSTVADGLITTLHYPAPKRNKPTVYGVSPNYDKWEMERTDITMKHKLGGGQYGEVYEGVWKKYSLTVAVKTLKEDTMEVEEFLKEAAVMKEIKHPNLVQLLGVCTREPPFYIITEFMTYGNLLDYLRECNRQEVNAVVLLYMATQISSAMEYLEKKNFIHRDLAARNCLVGENHLVKVADFGLSRLMTGDTYTAHAGAKFPIKWTAPESLAYNKFSIKSDVWAFGVLLWEIATYGMSPYPGIDLSQVYELLEKDYRMERPEGCPEKVYELMRACWQWNPSDRPSFAEIHQAFETMFQES",
        "seq_length": 1130,
        "protein_name": "Tyrosine-protein kinase ABL1",
        "gene_name": "ABL1",
        "function_annotation": "Non-receptor tyrosine-protein kinase that plays a role in many key processes.",
        "catalytic_activity": "ATP + L-tyrosyl-[protein] = ADP + H(+) + O-phospho-L-tyrosyl-[protein]",
        "is_reviewed": True,
    }
