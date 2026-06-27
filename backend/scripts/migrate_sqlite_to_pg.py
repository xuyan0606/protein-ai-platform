"""Migrate all data from SQLite to PostgreSQL.

Uses batch inserts for performance — 375MB DB with 280K enzymes migrates in minutes.

Usage:
    python scripts/migrate_sqlite_to_pg.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
from app.models.base import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQLITE_URL = f"sqlite:///{Path.cwd() / 'protein_ai.db'}"
PG_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

BATCH_SIZE = 2000

# SQLite stores booleans as 0/1 ints; PostgreSQL wants actual booleans
BOOLEAN_COLUMNS = {"is_reviewed", "is_primary", "is_balanced", "is_transport"}

# SQLite stores JSON as text strings; PostgreSQL wants parsed JSON
JSON_COLUMNS = {"cofactors", "chain_ids", "plddt_per_residue",
                "reactants", "products", "ec_numbers",
                "mutations_introduced", "results"}


def main():
    sqlite_eng = create_engine(SQLITE_URL)
    pg_eng = create_engine(PG_URL, echo=False)

    logger.info("Creating tables in PostgreSQL...")
    Base.metadata.create_all(pg_eng)

    inspector = inspect(sqlite_eng)
    tables = inspector.get_table_names()
    logger.info("Found %d tables in SQLite", len(tables))

    # Order: base FK-free tables first, then dependent tables
    ordered = [
        "users", "taxonomy", "ec_numbers", "pfam_domains",
        "substrate_compounds", "reaction_equations", "kv_store",
        "enzyme_records", "conversations", "projects",
        "enzyme_ec_links", "domain_architecture",
        "pdb_structures", "alphafold_structures",
        "kinetic_parameters", "stability_records",
        "directed_evolution_entries", "database_crossrefs",
        "messages", "tool_calls", "project_sequences", "batch_jobs",
    ]
    ordered = [t for t in ordered if t in tables]

    total_rows = 0
    # Per-table transactions: if one table fails, previous data is preserved
    for table_name in ordered:
        try:
            with pg_eng.begin() as conn:
                conn.execute(text("SET session_replication_role = 'replica'"))
                count = _copy_table_batch(sqlite_eng, conn, table_name)
                conn.execute(text("SET session_replication_role = 'origin'"))
                _reset_sequences(conn, [table_name])
                total_rows += count
        except Exception:
            logger.exception("Failed to migrate table: %s, skipping", table_name)

    logger.info("Migration complete. %d rows across %d tables", total_rows, len(ordered))


def _copy_table_batch(src_eng, dest_conn, table_name):
    """Copy all rows using multi-VALUES batch inserts for performance."""
    from sqlalchemy import Table, MetaData

    col_info = inspect(src_eng).get_columns(table_name)
    col_names = [c["name"] for c in col_info]

    with src_eng.connect() as src_conn:
        count = src_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

    if count == 0:
        logger.info("  %s: 0 rows", table_name)
        return 0

    col_list = ", ".join(col_names)

    offset = 0
    while offset < count:
        with src_eng.connect() as src_conn:
            rows = src_conn.execute(
                text(f"SELECT * FROM {table_name} LIMIT {BATCH_SIZE} OFFSET {offset}")
            ).fetchall()

        if not rows:
            break

        # Build multi-row VALUES: INSERT INTO t (a,b) VALUES (:a1,:b1), (:a2,:b2), ...
        value_groups = []
        all_params = {}
        for i, row in enumerate(rows):
            placeholders = [f":{c}_{i}" for c in col_names]
            value_groups.append(f"({', '.join(placeholders)})")
            for c, v in zip(col_names, row):
                if c in BOOLEAN_COLUMNS:
                    v = bool(v) if v is not None else None
                elif c in JSON_COLUMNS and v is not None:
                    # Always convert to JSON string for PostgreSQL INSERT
                    if isinstance(v, str):
                        try:
                            parsed = json.loads(v)
                            v = json.dumps(parsed)  # normalize
                        except (json.JSONDecodeError, TypeError):
                            v = json.dumps(v)  # wrap string as JSON string
                    else:
                        v = json.dumps(v)  # serialize list/dict/scalar
                all_params[f"{c}_{i}"] = v

        values_str = ", ".join(value_groups)
        sql = f"INSERT INTO {table_name} ({col_list}) VALUES {values_str}"
        dest_conn.execute(text(sql), all_params)

        offset += BATCH_SIZE
        if offset % 50000 == 0 or offset >= count:
            logger.info("  %s: %d/%d", table_name, min(offset, count), count)

    logger.info("  %s: %d rows done", table_name, count)
    return count


def _reset_sequences(conn, tables):
    """Reset PostgreSQL sequences after explicit-ID inserts."""
    for table_name in tables:
        result = conn.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table_name}' AND column_name = 'id'
        """))
        if result.fetchone():
            try:
                conn.execute(text(f"""
                    SELECT setval(pg_get_serial_sequence('{table_name}', 'id'),
                                  COALESCE((SELECT MAX(id) FROM {table_name}), 1))
                """))
            except Exception:
                pass


if __name__ == "__main__":
    main()
