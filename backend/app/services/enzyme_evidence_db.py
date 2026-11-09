"""Read-only helpers for local simplified enzyme evidence SQLite databases."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, settings

SIMPLE_EXPECTED_TABLES = {"papers", "variants", "measurements"}

SIMPLE_ENZYME_DATABASES: dict[str, dict[str, str]] = {
    "amylase": {"label": "Amylase", "relative_path": "amylase-db/amylase.db"},
    "mannanase": {"label": "Mannanase", "relative_path": "mannanase-db/mannanase.db"},
    "xylanase": {"label": "Xylanase", "relative_path": "xylanase-db/xylanase.db"},
    "acid_protease": {"label": "Acid protease", "relative_path": "acid-protease-db/acid_protease.db"},
    "phytase": {"label": "Phytase", "relative_path": "phytase-db/phytase.db"},
    "glucose_oxidase": {"label": "Glucose oxidase", "relative_path": "glucose_oxidase-db/glucose_oxidase.db"},
}
_BROWSER_SCOPE_POLICY = (
    "Browser/search endpoints are read-only audit views and may include hold, B, medium, "
    "preprint, review, and other non-exportable rows. Use /export-safe/measurements for "
    "high-confidence export candidates."
)
_NON_EXPORTABLE_MARKERS = ("hold", "boundary", "non_exportable", "patent", "preprint")
POLICY_DECISION_CONFIRMATION_TOKEN = "MANUAL_ENZYME_POLICY_DECISION_REVIEW"


def _marker_exclusion_clause(alias: str, columns: tuple[str, ...]) -> str:
    checks: list[str] = []
    for column in columns:
        for marker in _NON_EXPORTABLE_MARKERS:
            checks.append(f"COALESCE(CAST({alias}.{column} AS TEXT), '') NOT LIKE '%{marker}%'")
    return "\n    AND ".join(checks)

_COMPACT_EXPORT_SAFE_PAPER_CLAUSE = (
    "COALESCE(p.quality, '') = 'A'\n"
    "    AND " + _marker_exclusion_clause("p", ("access", "priority", "category", "quality", "notes"))
)
_COMPACT_EXPORT_SAFE_MEASUREMENT_CLAUSE = (
    "COALESCE(m.conf, '') = 'A'\n"
    "    AND " + _marker_exclusion_clause("m", ("conf", "src"))
)


def _root() -> Path:
    raw = (settings.ENZYME_DB_ROOT or "").strip()
    if raw:
        return Path(raw).expanduser()
    return PROJECT_ROOT.parent / "酶数据库"


def _db_path(family: str) -> Path:
    config = SIMPLE_ENZYME_DATABASES.get(family)
    if not config:
        raise KeyError(family)
    return _root() / config["relative_path"]


def _missing_database_payload(family: str) -> dict[str, Any] | None:
    """Return an explicit unavailable state instead of silently treating a missing DB as empty."""
    status = collect_simple_enzyme_db_status(family)
    if status.get("status") == "missing":
        return {
            "status": "missing_database",
            "family": family,
            "count": 0,
            "path": status.get("path"),
            "error": "The configured read-only enzyme evidence database is not mounted.",
        }
    if status.get("status") == "error":
        return {
            "status": "database_error",
            "family": family,
            "count": 0,
            "path": status.get("path"),
            "error": status.get("error") or "The enzyme evidence database could not be opened.",
        }
    return None


def _path_info(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        if path.exists() and path.is_file()
        else None,
    }


def _load_policy_decision_manifests(db_path: Path) -> dict[str, Any]:
    root = db_path.parent
    manifests: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    decision_count = 0
    record_types: set[str] = set()
    review_statuses: set[str] = set()
    for path in sorted(root.glob("enzyme_metadata_policy_decisions_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        decisions = payload.get("decisions") if isinstance(payload, dict) else None
        if not isinstance(decisions, list):
            errors.append({"path": str(path), "error": "decisions must be a list"})
            continue
        decision_count += len(decisions)
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            if decision.get("record_type"):
                record_types.add(str(decision["record_type"]))
            if decision.get("review_status"):
                review_statuses.add(str(decision["review_status"]))
        manifests.append(
            {
                "path": str(path),
                "schema_version": payload.get("schema_version"),
                "family": payload.get("family"),
                "created_at": payload.get("created_at"),
                "scope": payload.get("scope"),
                "decision_count": len(decisions),
                "export_safe": bool(payload.get("export_safe") is True),
            }
        )
    return {
        "status": "ok" if not errors else "warning",
        "manifest_count": len(manifests),
        "decision_count": decision_count,
        "record_types": sorted(record_types),
        "review_statuses": sorted(review_statuses),
        "manifests": manifests,
        "errors": errors,
    }


def _load_policy_decision_records(db_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(db_path.parent.glob("enzyme_metadata_policy_decisions_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        decisions = payload.get("decisions") if isinstance(payload, dict) else None
        if not isinstance(decisions, list):
            continue
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            records.append(
                {
                    **decision,
                    "manifest_path": str(path),
                    "manifest_schema_version": payload.get("schema_version"),
                    "manifest_created_at": payload.get("created_at"),
                    "family": payload.get("family"),
                }
            )
    return records


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
    return int(row["count"] if row else 0)


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return 0
    value = row[0]
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _simple_quality_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    missing_doi = _scalar(conn, "SELECT COUNT(*) FROM papers WHERE doi IS NULL OR trim(doi)=''")
    missing_pmid = _scalar(conn, "SELECT COUNT(*) FROM papers WHERE pmid IS NULL OR trim(pmid)=''")
    marker_condition = " OR ".join(
        f"COALESCE(CAST({column} AS TEXT), '') LIKE '%{marker}%'"
        for column in ("access", "priority", "category", "quality", "notes")
        for marker in _NON_EXPORTABLE_MARKERS
    )
    patent_like_sources = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM papers
        WHERE (doi IS NULL OR trim(doi)='')
          AND (
            COALESCE(journal, '') GLOB 'US[0-9]*'
            OR COALESCE(journal, '') GLOB 'EP[0-9]*'
            OR COALESCE(access, '') LIKE '%patent%'
            OR COALESCE(category, '') LIKE '%patent%'
            OR COALESCE(notes, '') LIKE '%patent%'
          )
        """,
    )
    preprint_papers = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM papers
        WHERE COALESCE(access, '') LIKE '%preprint%'
           OR COALESCE(CAST(priority AS TEXT), '') LIKE '%preprint%'
           OR COALESCE(category, '') LIKE '%preprint%'
           OR COALESCE(quality, '') LIKE '%preprint%'
           OR COALESCE(notes, '') LIKE '%preprint%'
        """,
    )
    boundary_papers = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM papers
        WHERE COALESCE(access, '') LIKE '%boundary%'
           OR COALESCE(CAST(priority AS TEXT), '') LIKE '%boundary%'
           OR COALESCE(category, '') LIKE '%boundary%'
           OR COALESCE(quality, '') LIKE '%boundary%'
           OR COALESCE(notes, '') LIKE '%boundary%'
        """,
    )
    boundary_measurements = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM measurements
        WHERE COALESCE(conf, '') LIKE '%boundary%'
           OR COALESCE(src, '') LIKE '%boundary%'
        """,
    )
    policy_excluded_measurements = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM measurements
        WHERE COALESCE(conf, '') LIKE '%hold%'
           OR COALESCE(conf, '') LIKE '%boundary%'
           OR COALESCE(conf, '') LIKE '%non_exportable%'
           OR COALESCE(conf, '') LIKE '%patent%'
           OR COALESCE(conf, '') LIKE '%preprint%'
           OR COALESCE(src, '') LIKE '%hold%'
           OR COALESCE(src, '') LIKE '%boundary%'
           OR COALESCE(src, '') LIKE '%non_exportable%'
           OR COALESCE(src, '') LIKE '%patent%'
           OR COALESCE(src, '') LIKE '%preprint%'
        """,
    )
    policy_excluded_papers = _scalar(
        conn,
        f"""
        SELECT COUNT(*)
        FROM papers
        WHERE {marker_condition}
        """,
    )
    hold_papers = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM papers
        WHERE COALESCE(access, '') LIKE '%hold%'
           OR COALESCE(CAST(priority AS TEXT), '') LIKE '%hold%'
           OR COALESCE(quality, '') LIKE '%hold%'
           OR COALESCE(quality, '') = 'non_exportable'
        """,
    )
    hold_measurements = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM measurements
        WHERE COALESCE(conf, '') LIKE '%hold%'
           OR COALESCE(conf, '') = 'non_exportable'
        """,
    )
    export_safe_measurements = _scalar(
        conn,
        f"""
        SELECT COUNT(*)
        FROM measurements m
        JOIN papers p ON p.id=m.pid
        WHERE {_COMPACT_EXPORT_SAFE_PAPER_CLAUSE}
          AND {_COMPACT_EXPORT_SAFE_MEASUREMENT_CLAUSE}
        """,
    )
    return {
        "missing_doi": missing_doi,
        "missing_pmid": missing_pmid,
        "patent_like_sources": patent_like_sources,
        "preprint_papers": preprint_papers,
        "boundary_papers": boundary_papers,
        "boundary_measurements": boundary_measurements,
        "policy_excluded_papers": policy_excluded_papers,
        "policy_excluded_measurements": policy_excluded_measurements,
        "non_exportable_markers": list(_NON_EXPORTABLE_MARKERS),
        "export_policy": {
            "browser_scope": "audit_includes_hold_boundary_patent_preprint_rows",
            "export_scope": "compact_high_confidence_a_only",
            "patent_metadata": "keep_out_of_doi_pmid_until_policy_exists",
            "preprint_version_of_record": "manual_identity_upgrade_required",
            "blocked_markers": list(_NON_EXPORTABLE_MARKERS),
        },
        "hold_papers": hold_papers,
        "hold_measurements": hold_measurements,
        "export_safe_measurements": export_safe_measurements,
        "metadata_gap_count": missing_doi + missing_pmid,
        "browser_scope": "audit_includes_hold_rows",
    }


def _safe_limit(limit: int, *, default: int = 50, max_value: int = 500) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, max_value))


def list_enzyme_db_families() -> dict[str, Any]:
    root = _root()
    statuses = [collect_simple_enzyme_db_status(family) for family in SIMPLE_ENZYME_DATABASES]
    return {
        "status": "ready" if all(item["status"] == "ready" for item in statuses) else "partial",
        "read_only": True,
        "root": {"path": str(root), "exists": root.exists()},
        "families": statuses,
    }


def collect_simple_enzyme_db_status(family: str) -> dict[str, Any]:
    config = SIMPLE_ENZYME_DATABASES.get(family)
    if not config:
        return {"status": "unknown_family", "family": family, "known_families": sorted(SIMPLE_ENZYME_DATABASES)}
    path = _db_path(family)
    info = _path_info(path)
    base = {
        "family": family,
        "label": config["label"],
        "schema": "simplified_three_table",
        "read_only": True,
        "path": info,
        "expected_tables": sorted(SIMPLE_EXPECTED_TABLES),
        "metadata_policy_decisions": _load_policy_decision_manifests(path) if info["exists"] else {},
    }
    if not info["exists"]:
        return {**base, "status": "missing", "tables": {}, "missing_tables": sorted(SIMPLE_EXPECTED_TABLES)}

    try:
        with _connect_readonly(path) as conn:
            tables = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            }
            missing = sorted(SIMPLE_EXPECTED_TABLES - tables)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            integrity_check = str(integrity[0]) if integrity else "unknown"
            counts = {table: _count(conn, table) for table in sorted(SIMPLE_EXPECTED_TABLES & tables)}
            summary = _simple_quality_summary(conn) if not missing else {}
    except sqlite3.Error as exc:
        return {**base, "status": "error", "tables": {}, "missing_tables": sorted(SIMPLE_EXPECTED_TABLES), "error": str(exc)}

    ready = not missing and integrity_check == "ok"
    return {
        **base,
        "status": "ready" if ready else "partial",
        "tables": counts,
        "missing_tables": missing,
        "quality": {"integrity_check": integrity_check, "ready_for_query": ready},
        "metadata_quality": summary,
    }


def list_simple_enzyme_papers(family: str, *, q: str | None = None, limit: int = 50) -> dict[str, Any]:
    unavailable = _missing_database_payload(family)
    if unavailable:
        return {**unavailable, "papers": [], "export_scope": "browser_audit", "export_safe": False, "policy": _BROWSER_SCOPE_POLICY}
    path = _db_path(family)
    safe_limit = _safe_limit(limit)
    params: list[Any] = []
    where = ""
    if q and q.strip():
        like = f"%{q.strip()}%"
        where = "WHERE id LIKE ? OR title LIKE ? OR author LIKE ? OR journal LIKE ? OR doi LIKE ? OR pmid LIKE ? OR notes LIKE ?"
        params.extend([like, like, like, like, like, like, like])
    params.append(safe_limit)
    sql = f"""
        SELECT id, title, author, journal, year, doi, pmid, access, priority, lab, category, quality, notes
        FROM papers
        {where}
        ORDER BY year DESC, id DESC
        LIMIT ?
    """
    rows = _query_rows(path, sql, params)
    return {
        "status": "ready",
        "family": family,
        "export_scope": "browser_audit",
        "export_safe": False,
        "policy": _BROWSER_SCOPE_POLICY,
        "count": len(rows),
        "papers": rows,
        "path": _path_info(path),
    }


def list_simple_enzyme_variants(family: str, *, q: str | None = None, limit: int = 50) -> dict[str, Any]:
    unavailable = _missing_database_payload(family)
    if unavailable:
        return {**unavailable, "variants": [], "export_scope": "browser_audit", "export_safe": False, "policy": _BROWSER_SCOPE_POLICY}
    path = _db_path(family)
    safe_limit = _safe_limit(limit)
    params: list[Any] = []
    where = ""
    if q and q.strip():
        like = f"%{q.strip()}%"
        where = "WHERE v.id LIKE ? OR v.pid LIKE ? OR v.name LIKE ? OR v.norm LIKE ? OR v.mtype LIKE ? OR v.effect LIKE ? OR p.title LIKE ?"
        params.extend([like, like, like, like, like, like, like])
    params.append(safe_limit)
    sql = f"""
        SELECT v.id, v.eid, v.pid, p.title AS paper_title, p.year, v.name, v.norm, v.mtype, v.cnt, v.sm, v.bg, v.effect
        FROM variants v
        LEFT JOIN papers p ON p.id = v.pid
        {where}
        ORDER BY p.year DESC, v.pid DESC, v.id DESC
        LIMIT ?
    """
    rows = _query_rows(path, sql, params)
    return {
        "status": "ready",
        "family": family,
        "export_scope": "browser_audit",
        "export_safe": False,
        "policy": _BROWSER_SCOPE_POLICY,
        "count": len(rows),
        "variants": rows,
        "path": _path_info(path),
    }


def list_simple_enzyme_measurements(family: str, *, q: str | None = None, limit: int = 50) -> dict[str, Any]:
    unavailable = _missing_database_payload(family)
    if unavailable:
        return {**unavailable, "measurements": [], "export_scope": "browser_audit", "export_safe": False, "policy": _BROWSER_SCOPE_POLICY}
    path = _db_path(family)
    safe_limit = _safe_limit(limit)
    params: list[Any] = []
    where = ""
    if q and q.strip():
        like = f"%{q.strip()}%"
        where = (
            "WHERE m.vid LIKE ? OR m.pid LIKE ? OR m.cat LIKE ? OR m.prop LIKE ? OR "
            "m.unit LIKE ? OR m.dir LIKE ? OR m.sub LIKE ? OR m.src LIKE ? OR p.title LIKE ? OR v.name LIKE ?"
        )
        params.extend([like, like, like, like, like, like, like, like, like, like])
    params.append(safe_limit)
    sql = f"""
        SELECT
            m.mid, m.vid, m.pid, p.title AS paper_title, v.name AS variant_name,
            m.cat, m.prop, m.val, m.unit, m.wt, m.fc, m.dir, m.temp, m.pH, m.sub, m.src, m.conf
        FROM measurements m
        LEFT JOIN papers p ON p.id = m.pid
        LEFT JOIN variants v ON v.id = m.vid
        {where}
        ORDER BY p.year DESC, m.pid DESC, m.mid DESC
        LIMIT ?
    """
    rows = _query_rows(path, sql, params)
    for row in rows:
        row["export_scope"] = "browser_audit"
        row["export_safe"] = False
    return {
        "status": "ready",
        "family": family,
        "export_scope": "browser_audit",
        "export_safe": False,
        "policy": _BROWSER_SCOPE_POLICY,
        "count": len(rows),
        "measurements": rows,
        "path": _path_info(path),
    }


def list_simple_enzyme_export_safe_measurements(
    family: str, *, q: str | None = None, limit: int = 500
) -> dict[str, Any]:
    """Return compact-schema measurements eligible for high-confidence export."""
    path = _db_path(family)
    safe_limit = _safe_limit(limit, default=500, max_value=2000)
    params: list[Any] = []
    clauses = [
        _COMPACT_EXPORT_SAFE_PAPER_CLAUSE,
        _COMPACT_EXPORT_SAFE_MEASUREMENT_CLAUSE,
    ]
    if q and q.strip():
        like = f"%{q.strip()}%"
        clauses.append(
            "(m.vid LIKE ? OR m.pid LIKE ? OR m.cat LIKE ? OR m.prop LIKE ? OR "
            "m.unit LIKE ? OR m.dir LIKE ? OR m.sub LIKE ? OR m.src LIKE ? OR p.title LIKE ? OR v.name LIKE ?)"
        )
        params.extend([like, like, like, like, like, like, like, like, like, like])
    params.append(safe_limit)
    where = f"WHERE {' AND '.join(clauses)}"
    sql = f"""
        SELECT
            m.mid, m.vid, m.pid, p.title AS paper_title, p.year,
            p.access AS paper_access, p.priority AS paper_priority, p.quality AS paper_quality,
            v.name AS variant_name,
            m.cat, m.prop, m.val, m.unit, m.wt, m.fc, m.dir, m.temp, m.pH, m.sub, m.src, m.conf
        FROM measurements m
        JOIN papers p ON p.id = m.pid
        LEFT JOIN variants v ON v.id = m.vid
        {where}
        ORDER BY p.year DESC, m.pid DESC, m.mid DESC
        LIMIT ?
    """
    rows = _query_rows(path, sql, params)
    for row in rows:
        row["export_safe"] = True
    return {
        "status": "ready",
        "family": family,
        "export_scope": "compact_high_confidence_a_only",
        "export_safe": True,
        "policy": (
            "High-confidence export requires non-hold paper state plus paper quality='A' "
            "and measurement conf='A'; B/medium/preprint and hold/non_exportable rows are excluded."
        ),
        "count": len(rows),
        "measurements": rows,
        "path": _path_info(path),
    }


def prepare_simple_enzyme_policy_decision_batch(
    family: str,
    *,
    limit: int = 100,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Return a controlled release plan for sidecar policy decisions.

    The first production layer is intentionally fail-closed: sidecar decisions
    can be packaged for human review, but this function never mutates SQLite or
    changes export-safe eligibility.
    """
    path = _db_path(family)
    safe_limit = _safe_limit(limit, default=100, max_value=500)
    records = _load_policy_decision_records(path)[:safe_limit]
    blocked_reasons = [
        "policy sidecars are metadata decisions, not direct SQLite patch instructions",
        "patent rows require an approved patent metadata schema before any database import",
        "preprint-to-version-of-record rows require full citation identity upgrade and payload mapping review",
        "export-safe release requires a separate reviewed export decision",
    ]
    return {
        "status": "planned" if dry_run else "blocked_manual_upgrade_required",
        "dry_run": bool(dry_run),
        "sqlite_mutated": False,
        "sqlite_mutation_allowed": False,
        "export_safe_released": False,
        "export_safe": False,
        "blocked": not dry_run,
        "blocked_reasons": blocked_reasons if not dry_run else [],
        "family": family,
        "read_only_source_db": True,
        "confirmation_required": True,
        "confirmation_token": POLICY_DECISION_CONFIRMATION_TOKEN,
        "manifest": {
            "record_count": len(records),
            "record_types": sorted({str(record.get("record_type")) for record in records if record.get("record_type")}),
            "review_statuses": sorted(
                {str(record.get("review_status")) for record in records if record.get("review_status")}
            ),
            "status_policy": (
                "sidecar policy decisions are queued for manual curation; preview does not mutate SQLite DBs "
                "and does not make rows export-safe"
            ),
        },
        "export_payload": {
            "source": "simple_enzyme_policy_decision_sidecar",
            "target": "manual_enzyme_db_curation_or_upgrade_script",
            "family": family,
            "record_count": len(records),
            "records": records,
            "required_manual_steps": [
                "review sidecar decisions against live DOI/PubMed/Crossref/Europe PMC evidence",
                "for patent rows, keep patent metadata outside DOI/PMID fields unless a patent schema is approved",
                "for preprint rows, upgrade the full citation identity only after variant payload mapping is confirmed",
                "run dry-run -> backup -> apply -> PRAGMA integrity_check for any future SQLite mutation",
                "keep export-safe blocked until a separate export release decision is recorded",
            ],
        },
        "release_plan": {
            "mode": "manual_upgrade_script_required",
            "apply_supported": False,
            "dry_run_contract": "dry-run emits a review package only",
            "apply_contract": "dry_run=false is blocked until a reviewed family-specific upgrade script exists",
            "safety_gate": "future mutation must run dry-run -> backup -> apply -> PRAGMA integrity_check",
        },
    }


def preview_simple_enzyme_policy_decision_batch(family: str, *, limit: int = 100) -> dict[str, Any]:
    """Return a read-only dry-run payload for sidecar policy decisions."""
    return prepare_simple_enzyme_policy_decision_batch(family, limit=limit, dry_run=True)


def publish_simple_enzyme_policy_decision_batch(
    family: str,
    *,
    confirmation: str | None,
    limit: int = 100,
) -> dict[str, Any]:
    """Fail-closed placeholder for future reviewed policy-decision upgrades."""
    if confirmation != POLICY_DECISION_CONFIRMATION_TOKEN:
        raise ValueError(f"Set confirmation to {POLICY_DECISION_CONFIRMATION_TOKEN} to prepare a blocked publish plan")
    return prepare_simple_enzyme_policy_decision_batch(family, limit=limit, dry_run=False)


def search_simple_enzyme_db(family: str, *, q: str, limit: int = 50) -> dict[str, Any]:
    if not q or not q.strip():
        return {"status": "empty_query", "family": family, "results": {"papers": [], "variants": [], "measurements": []}}
    per_section = _safe_limit(limit, default=50, max_value=100)
    paper_payload = list_simple_enzyme_papers(family, q=q, limit=per_section)
    variant_payload = list_simple_enzyme_variants(family, q=q, limit=per_section)
    measurement_payload = list_simple_enzyme_measurements(family, q=q, limit=per_section)
    section_payloads = (paper_payload, variant_payload, measurement_payload)
    unavailable = next(
        (payload for payload in section_payloads if payload.get("status") in {"missing_database", "database_error"}),
        None,
    )
    return {
        "status": unavailable.get("status") if unavailable else "ready",
        "family": family,
        "query": q,
        **({"error": unavailable.get("error"), "path": unavailable.get("path")} if unavailable else {}),
        "export_scope": "browser_audit",
        "export_safe": False,
        "policy": _BROWSER_SCOPE_POLICY,
        "results": {
            "papers": paper_payload["papers"],
            "variants": variant_payload["variants"],
            "measurements": measurement_payload["measurements"],
        },
    }


def _query_rows(path: Path, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with _connect_readonly(path) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
