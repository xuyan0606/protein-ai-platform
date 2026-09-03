"""Import legacy SQLite domain data into the production PostgreSQL database.

This intentionally imports only biological/domain data. It does not import
users, conversations, messages, projects, files, or tool-call history.

This is a full domain-table restore, not an export-safe or training-safe path.
It does not apply A-only, hold, reviewed-label, or model-readiness filters.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings

DOMAIN_TABLES = [
    "taxonomy",
    "ec_numbers",
    "pfam_domains",
    "substrate_compounds",
    "reaction_equations",
    "kv_store",
    "enzyme_records",
    "enzyme_ec_links",
    "domain_architecture",
    "pdb_structures",
    "alphafold_structures",
    "kinetic_parameters",
    "stability_records",
    "directed_evolution_entries",
    "database_crossrefs",
]

TRUNCATE_TABLES = [
    "database_crossrefs",
    "directed_evolution_entries",
    "stability_records",
    "kinetic_parameters",
    "alphafold_structures",
    "pdb_structures",
    "domain_architecture",
    "enzyme_ec_links",
    "enzyme_records",
    "reaction_equations",
    "substrate_compounds",
    "pfam_domains",
    "ec_numbers",
    "taxonomy",
    "kv_store",
]

BOOLEAN_COLUMNS = {"is_reviewed", "is_primary", "is_balanced", "is_transport"}
JSON_COLUMNS = {
    "cofactors",
    "chain_ids",
    "plddt_per_residue",
    "reactants",
    "products",
    "ec_numbers",
    "mutations_introduced",
    "results",
}
DATETIME_COLUMNS = {"created_at", "updated_at", "deposited_at", "last_synced"}


def _pg_dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _missing_domain_tables(source_tables: set[str]) -> list[str]:
    return [table for table in DOMAIN_TABLES if table not in source_tables]


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


async def _pg_columns(conn: asyncpg.Connection, table: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table,
    )
    return {str(row["column_name"]) for row in rows}


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _coerce_value(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in BOOLEAN_COLUMNS:
        return bool(value)
    if column in JSON_COLUMNS:
        if isinstance(value, str):
            try:
                return json.dumps(json.loads(value))
            except (TypeError, ValueError):
                return json.dumps(value)
        return json.dumps(value)
    if column in DATETIME_COLUMNS and isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return value


def _iter_batches(sqlite_conn: sqlite3.Connection, table: str, columns: list[str], batch_size: int):
    sqlite_conn.row_factory = sqlite3.Row
    column_sql = ", ".join(f'"{column}"' for column in columns)
    offset = 0
    while True:
        rows = sqlite_conn.execute(
            f'SELECT {column_sql} FROM "{table}" LIMIT ? OFFSET ?',
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break
        yield [
            tuple(_coerce_value(column, row[column]) for column in columns)
            for row in rows
        ]
        offset += len(rows)


async def _truncate_domain_tables(pg_conn: asyncpg.Connection) -> None:
    existing = {
        str(row["tablename"])
        for row in await pg_conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    }
    tables = [table for table in TRUNCATE_TABLES if table in existing]
    if tables:
        quoted = ", ".join(f'"{table}"' for table in tables)
        await pg_conn.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY")


async def _reset_sequence(pg_conn: asyncpg.Connection, table: str) -> None:
    has_id = await pg_conn.fetchval(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1 AND column_name = 'id'
        """,
        table,
    )
    if not has_id:
        return
    await pg_conn.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            COALESCE((SELECT MAX(id) FROM "{table}"), 1),
            (SELECT MAX(id) FROM "{table}") IS NOT NULL
        )
        """
    )


async def _import_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn: asyncpg.Connection,
    table: str,
    *,
    batch_size: int,
) -> int:
    source_columns = _sqlite_columns(sqlite_conn, table)
    destination_columns = await _pg_columns(pg_conn, table)
    columns = [column for column in source_columns if column in destination_columns]
    if not columns:
        print(f"{table}\tskipped\tno shared columns")
        return 0

    total = _row_count(sqlite_conn, table)
    imported = 0
    for batch in _iter_batches(sqlite_conn, table, columns, batch_size):
        await pg_conn.copy_records_to_table(table, records=batch, columns=columns)
        imported += len(batch)
        if imported % 50000 == 0 or imported == total:
            print(f"{table}\t{imported}/{total}")
    await _reset_sequence(pg_conn, table)
    return imported


async def run(args: argparse.Namespace) -> None:
    sqlite_path = Path(args.sqlite_path).expanduser()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    source_tables = _sqlite_tables(sqlite_conn)
    import_tables = [table for table in DOMAIN_TABLES if table in source_tables]
    missing_tables = _missing_domain_tables(source_tables)
    counts = {table: _row_count(sqlite_conn, table) for table in import_tables}

    print("scope\tfull_domain_restore_not_export_safe_not_training_safe_not_a_only")
    print("filter_policy\tno_a_only_or_hold_filters_applied")
    print(f"sqlite_path\t{sqlite_path}")
    for table in missing_tables:
        print(f"missing_domain_table\t{table}")
    for table, count in counts.items():
        print(f"plan\t{table}\t{count}")
    if args.dry_run:
        print("status\tdry-run")
        return
    if not args.replace:
        raise SystemExit("Refusing to import without --replace. Run --dry-run first, then pass --replace.")
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise SystemExit(
            "Refusing --replace because SQLite is missing required domain tables: "
            f"{missing}. Use a complete full-domain SQLite restore source."
        )

    pg_conn = await asyncpg.connect(dsn=_pg_dsn())
    try:
        async with pg_conn.transaction():
            await _truncate_domain_tables(pg_conn)
            total = 0
            for table in import_tables:
                total += await _import_table(sqlite_conn, pg_conn, table, batch_size=args.batch_size)
        print(f"status\timported\t{total}")
    finally:
        await pg_conn.close()
        sqlite_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Restore domain tables from SQLite to PostgreSQL. This is not an "
            "export-safe, training-safe, or A-only filtered import."
        )
    )
    parser.add_argument("--sqlite-path", default="/app/deploy_data/sqlite/protein_ai.db")
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
