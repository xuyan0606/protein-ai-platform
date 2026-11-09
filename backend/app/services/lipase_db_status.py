"""Read-only access helpers for the KWB lipase evidence SQLite database."""

from __future__ import annotations

import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

EXPECTED_TABLES = {
    "papers",
    "paper_aliases",
    "variants",
    "variant_mutations",
    "evidence_claims",
    "substrates",
    "claim_substrates",
    "metrics",
    "comparators",
    "unresolved_gaps",
    "lineage_notes",
}

_MUTATION_CODE_RE = re.compile(r"(?<![A-Z])([A-Z])(\d+)([A-Z])(?![A-Z])")


def _configured_path() -> Path:
    raw = (settings.LIPASE_DB_PATH or "").strip()
    return Path(raw).expanduser() if raw else Path("/Users/xuyan/lipase-db/lipase.db")


def _path_info(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        if path.exists() and path.is_file()
        else None,
    }


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
    return int(row["count"] if row else 0)


def _group_counts(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql).fetchall()]


def _extract_mutation_codes(values: list[str] | tuple[str, ...] | None) -> list[str]:
    codes: set[str] = set()
    for value in values or []:
        text = str(value or "").upper()
        for match in _MUTATION_CODE_RE.finditer(text):
            codes.add("".join(match.groups()))
    return sorted(codes)


def _extract_positions_from_mutations(codes: list[str]) -> list[int]:
    positions: set[int] = set()
    for code in codes:
        match = _MUTATION_CODE_RE.search(code.upper())
        if match:
            positions.add(int(match.group(2)))
    return sorted(positions)


def _coerce_positions(values: list[int] | tuple[int, ...] | None) -> list[int]:
    positions: set[int] = set()
    for value in values or []:
        try:
            position = int(value)
        except (TypeError, ValueError):
            continue
        if position > 0:
            positions.add(position)
    return sorted(positions)


_PROVISIONAL_READY_PAPER_CLAUSE = "COALESCE(p.ready_for_db, '') LIKE 'provisional_%'"


def _evidence_scope(include_non_ready: bool) -> str:
    return "all_readiness_states" if include_non_ready else "provisional_ready"


def _combine_where(clauses: list[str]) -> str:
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def collect_lipase_db_status() -> dict[str, Any]:
    """Return a read-only quality snapshot for the lipase evidence database."""
    path = _configured_path()
    info = _path_info(path)
    if not info["exists"]:
        return {
            "status": "missing",
            "read_only": True,
            "path": info,
            "expected_tables": sorted(EXPECTED_TABLES),
            "tables": {},
            "missing_tables": sorted(EXPECTED_TABLES),
            "quality": {
                "integrity_check": "missing",
                "foreign_key_issues": [],
                "ready_for_ingestion": False,
            },
            "next_actions": ["Set LIPASE_DB_PATH to an existing lipase.db file."],
        }

    try:
        with _connect_readonly(path) as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            }
            counts = {table: _fetch_count(conn, table) for table in sorted(tables)}
            missing_tables = sorted(EXPECTED_TABLES - tables)
            extra_tables = sorted(tables - EXPECTED_TABLES)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            integrity_check = str(integrity[0]) if integrity else "unknown"
            foreign_key_issues = [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
            evidence_levels = _group_counts(
                conn,
                """
                SELECT evidence_level, COUNT(*) AS count
                FROM evidence_claims
                GROUP BY evidence_level
                ORDER BY count DESC, evidence_level
                """,
            ) if "evidence_claims" in tables else []
            claim_groups = _group_counts(
                conn,
                """
                SELECT claim_group, COUNT(*) AS count
                FROM evidence_claims
                GROUP BY claim_group
                ORDER BY count DESC, claim_group
                """,
            ) if "evidence_claims" in tables else []
            gap_summary = _group_counts(
                conn,
                """
                SELECT gap_type, priority, status, COUNT(*) AS count
                FROM unresolved_gaps
                GROUP BY gap_type, priority, status
                ORDER BY count DESC, gap_type
                """,
            ) if "unresolved_gaps" in tables else []
    except sqlite3.Error as exc:
        return {
            "status": "error",
            "read_only": True,
            "path": info,
            "expected_tables": sorted(EXPECTED_TABLES),
            "tables": {},
            "missing_tables": sorted(EXPECTED_TABLES),
            "quality": {
                "integrity_check": "error",
                "foreign_key_issues": [],
                "ready_for_ingestion": False,
                "error": str(exc),
            },
            "next_actions": ["Fix lipase.db SQLite readability before enabling ingestion."],
        }

    ready = integrity_check == "ok" and not missing_tables and not foreign_key_issues
    return {
        "status": "ready" if ready else "partial",
        "read_only": True,
        "path": info,
        "expected_tables": sorted(EXPECTED_TABLES),
        "tables": counts,
        "missing_tables": missing_tables,
        "extra_tables": extra_tables,
        "summary": {
            "paper_count": counts.get("papers", 0),
            "variant_count": counts.get("variants", 0),
            "mutation_count": counts.get("variant_mutations", 0),
            "claim_count": counts.get("evidence_claims", 0),
            "metric_count": counts.get("metrics", 0),
            "substrate_count": counts.get("substrates", 0),
            "gap_count": counts.get("unresolved_gaps", 0),
        },
        "quality": {
            "integrity_check": integrity_check,
            "foreign_key_issues": foreign_key_issues,
            "ready_for_ingestion": ready,
        },
        "evidence_levels": evidence_levels,
        "claim_groups": claim_groups,
        "gap_summary": gap_summary,
        "next_actions": [] if ready else ["Review missing tables, integrity check, or foreign key issues before ingestion."],
    }


def list_lipase_variants(
    *, q: str | None = None, limit: int = 50, include_non_ready: bool = False
) -> dict[str, Any]:
    """Return evidence-linked lipase variants for UI and tool-context previews."""
    path = _configured_path()
    if not path.exists():
        return {"status": "missing", "count": 0, "variants": [], "path": _path_info(path)}

    safe_limit = max(1, min(int(limit), 200))
    params: list[Any] = []
    clauses: list[str] = []
    if not include_non_ready:
        clauses.append(_PROVISIONAL_READY_PAPER_CLAUSE)
    if q and q.strip():
        like = f"%{q.strip()}%"
        clauses.append(
            "(p.paper_key LIKE ? OR p.enzyme_name LIKE ? OR v.variant_label LIKE ? "
            "OR v.anchor_display LIKE ? OR ec.claim_summary LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    where = _combine_where(clauses)
    params.append(safe_limit)

    sql = f"""
        SELECT
            v.id AS variant_id,
            p.paper_key,
            p.citation,
            p.year,
            p.enzyme_name,
            p.engineering_objective,
            p.lock_status,
            p.ready_for_db,
            v.variant_label,
            v.anchor_display,
            v.variant_type,
            GROUP_CONCAT(DISTINCT vm.mutation_code) AS mutations,
            ec.claim_group,
            ec.evidence_level,
            ec.claim_summary,
            GROUP_CONCAT(DISTINCT m.metric_type || ':' || COALESCE(m.metric_value, '') || COALESCE(' ' || m.metric_unit, '')) AS metrics
        FROM variants v
        JOIN papers p ON p.id = v.paper_id
        LEFT JOIN variant_mutations vm ON vm.variant_id = v.id
        LEFT JOIN evidence_claims ec ON ec.variant_id = v.id
        LEFT JOIN metrics m ON m.claim_id = ec.id
        {where}
        GROUP BY v.id, ec.id
        ORDER BY p.year, p.paper_key, v.id
        LIMIT ?
    """
    with _connect_readonly(path) as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    return {
        "status": "ready",
        "evidence_scope": _evidence_scope(include_non_ready),
        "count": len(rows),
        "variants": rows,
        "path": _path_info(path),
    }


def list_lipase_papers(*, q: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List curated lipase papers with aggregate evidence counts."""
    path = _configured_path()
    if not path.exists():
        return {"status": "missing", "count": 0, "papers": [], "path": _path_info(path)}

    safe_limit = max(1, min(int(limit), 200))
    params: list[Any] = []
    where = ""
    if q and q.strip():
        like = f"%{q.strip()}%"
        where = (
            "WHERE p.paper_key LIKE ? OR p.citation LIKE ? OR p.title LIKE ? "
            "OR p.enzyme_name LIKE ? OR p.engineering_objective LIKE ?"
        )
        params.extend([like, like, like, like, like])
    params.append(safe_limit)

    sql = f"""
        SELECT
            p.id,
            p.paper_key,
            p.citation,
            p.title,
            p.authors,
            p.journal,
            p.year,
            p.doi,
            p.pmid,
            p.enzyme_name,
            p.engineering_objective,
            p.lock_status,
            p.ready_for_db,
            p.notes,
            COUNT(DISTINCT v.id) AS variant_count,
            COUNT(DISTINCT ec.id) AS claim_count,
            COUNT(DISTINCT m.id) AS metric_count,
            COUNT(DISTINCT g.id) AS gap_count
        FROM papers p
        LEFT JOIN variants v ON v.paper_id = p.id
        LEFT JOIN evidence_claims ec ON ec.paper_id = p.id
        LEFT JOIN metrics m ON m.claim_id = ec.id
        LEFT JOIN unresolved_gaps g ON g.paper_id = p.id
        {where}
        GROUP BY p.id
        ORDER BY p.year, p.paper_key
        LIMIT ?
    """
    with _connect_readonly(path) as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    return {"status": "ready", "count": len(rows), "papers": rows, "path": _path_info(path)}


def get_lipase_paper_detail(paper_key: str) -> dict[str, Any] | None:
    """Return one paper plus linked variants, claims, metrics, substrates, and gaps."""
    path = _configured_path()
    if not path.exists():
        return None

    with _connect_readonly(path) as conn:
        paper = conn.execute(
            "SELECT * FROM papers WHERE paper_key = ?",
            [paper_key],
        ).fetchone()
        if not paper:
            return None
        paper_dict = dict(paper)
        paper_id = paper_dict["id"]
        variants = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    v.*,
                    GROUP_CONCAT(vm.mutation_code, '/') AS mutations
                FROM variants v
                LEFT JOIN variant_mutations vm ON vm.variant_id = v.id
                WHERE v.paper_id = ?
                GROUP BY v.id
                ORDER BY v.id
                """,
                [paper_id],
            ).fetchall()
        ]
        claims = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    ec.*,
                    v.variant_label,
                    GROUP_CONCAT(DISTINCT s.substrate_name) AS substrates,
                    GROUP_CONCAT(DISTINCT m.metric_type || ':' || COALESCE(m.metric_value, '') || COALESCE(' ' || m.metric_unit, '')) AS metrics
                FROM evidence_claims ec
                LEFT JOIN variants v ON v.id = ec.variant_id
                LEFT JOIN claim_substrates cs ON cs.claim_id = ec.id
                LEFT JOIN substrates s ON s.id = cs.substrate_id
                LEFT JOIN metrics m ON m.claim_id = ec.id
                WHERE ec.paper_id = ?
                GROUP BY ec.id
                ORDER BY ec.id
                """,
                [paper_id],
            ).fetchall()
        ]
        gaps = [
            dict(row)
            for row in conn.execute(
                """
                SELECT g.*, v.variant_label
                FROM unresolved_gaps g
                LEFT JOIN variants v ON v.id = g.variant_id
                WHERE g.paper_id = ?
                ORDER BY
                    CASE g.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    g.id
                """,
                [paper_id],
            ).fetchall()
        ]
        aliases = [
            dict(row)
            for row in conn.execute(
                "SELECT alias_key, alias_type, note FROM paper_aliases WHERE canonical_paper_id = ? ORDER BY alias_key",
                [paper_id],
            ).fetchall()
        ]
    return {
        "status": "ready",
        "paper": paper_dict,
        "aliases": aliases,
        "variants": variants,
        "claims": claims,
        "gaps": gaps,
        "counts": {
            "variants": len(variants),
            "claims": len(claims),
            "gaps": len(gaps),
        },
        "path": _path_info(path),
    }


def list_lipase_gaps(*, priority: str | None = None, status: str | None = None, limit: int = 100) -> dict[str, Any]:
    """List unresolved evidence/data gaps for curation planning."""
    path = _configured_path()
    if not path.exists():
        return {"status": "missing", "count": 0, "gaps": [], "path": _path_info(path)}

    safe_limit = max(1, min(int(limit), 500))
    clauses: list[str] = []
    params: list[Any] = []
    if priority:
        clauses.append("g.priority = ?")
        params.append(priority)
    if status:
        clauses.append("g.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(safe_limit)
    sql = f"""
        SELECT
            g.*,
            p.paper_key,
            p.enzyme_name,
            v.variant_label,
            ec.claim_group
        FROM unresolved_gaps g
        LEFT JOIN papers p ON p.id = g.paper_id
        LEFT JOIN variants v ON v.id = g.variant_id
        LEFT JOIN evidence_claims ec ON ec.id = g.claim_id
        {where}
        ORDER BY
            CASE g.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            g.gap_type,
            g.id
        LIMIT ?
    """
    with _connect_readonly(path) as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    return {"status": "ready", "count": len(rows), "gaps": rows, "path": _path_info(path)}


def search_lipase_evidence(*, q: str, limit: int = 50, include_non_ready: bool = False) -> dict[str, Any]:
    """Search papers, variants, claims, substrates, and gaps in one payload."""
    query = q.strip()
    if not query:
        return {"status": "empty_query", "query": q, "results": {"papers": [], "variants": [], "claims": [], "substrates": [], "gaps": []}}

    path = _configured_path()
    if not path.exists():
        return {"status": "missing", "query": q, "results": {"papers": [], "variants": [], "claims": [], "substrates": [], "gaps": []}, "path": _path_info(path)}

    safe_limit = max(1, min(int(limit), 100))
    like = f"%{query}%"
    ready_clause = "" if include_non_ready else f"AND {_PROVISIONAL_READY_PAPER_CLAUSE}"
    with _connect_readonly(path) as conn:
        papers = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT paper_key, title, citation, year, doi, pmid, enzyme_name, engineering_objective, lock_status, ready_for_db
                FROM papers p
                WHERE (paper_key LIKE ? OR title LIKE ? OR citation LIKE ? OR enzyme_name LIKE ? OR engineering_objective LIKE ?)
                {ready_clause}
                ORDER BY year, paper_key
                LIMIT ?
                """,
                [like, like, like, like, like, safe_limit],
            ).fetchall()
        ]
        variants = list_lipase_variants(
            q=query, limit=safe_limit, include_non_ready=include_non_ready
        ).get("variants", [])
        claims = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT ec.id, p.paper_key, p.lock_status, p.ready_for_db, v.variant_label, ec.claim_group, ec.evidence_level, ec.claim_summary, ec.direct_evidence
                FROM evidence_claims ec
                JOIN papers p ON p.id = ec.paper_id
                LEFT JOIN variants v ON v.id = ec.variant_id
                WHERE (ec.claim_group LIKE ? OR ec.evidence_level LIKE ? OR ec.claim_summary LIKE ? OR ec.direct_evidence LIKE ? OR ec.known_payload LIKE ?)
                {ready_clause}
                ORDER BY p.year, ec.id
                LIMIT ?
                """,
                [like, like, like, like, like, safe_limit],
            ).fetchall()
        ]
        substrates = [
            dict(row)
            for row in conn.execute(
                """
                SELECT substrate_name, substrate_role, notes
                FROM substrates
                WHERE substrate_name LIKE ? OR substrate_role LIKE ? OR notes LIKE ?
                ORDER BY substrate_name
                LIMIT ?
                """,
                [like, like, like, safe_limit],
            ).fetchall()
        ]
        gaps = [
            dict(row)
            for row in conn.execute(
                """
                SELECT g.id, p.paper_key, v.variant_label, g.gap_type, g.gap_detail, g.priority, g.status
                FROM unresolved_gaps g
                LEFT JOIN papers p ON p.id = g.paper_id
                LEFT JOIN variants v ON v.id = g.variant_id
                WHERE g.gap_type LIKE ? OR g.gap_detail LIKE ? OR g.priority LIKE ? OR g.status LIKE ?
                ORDER BY g.id
                LIMIT ?
                """,
                [like, like, like, like, safe_limit],
            ).fetchall()
        ]
    return {
        "status": "ready",
        "query": query,
        "evidence_scope": _evidence_scope(include_non_ready),
        "results": {
            "papers": papers,
            "variants": variants,
            "claims": claims,
            "substrates": substrates,
            "gaps": gaps,
        },
        "counts": {
            "papers": len(papers),
            "variants": len(variants),
            "claims": len(claims),
            "substrates": len(substrates),
            "gaps": len(gaps),
        },
        "path": _path_info(path),
    }


def build_lipase_evidence_context(
    *,
    mutations: list[str] | None = None,
    positions: list[int] | None = None,
    q: str | None = None,
    limit: int = 20,
    include_non_ready: bool = False,
) -> dict[str, Any]:
    """Return compact lipase evidence for downstream mutation/structure/MD tools."""
    path = _configured_path()
    normalized_mutations = _extract_mutation_codes(mutations)
    normalized_positions = sorted(set(_coerce_positions(positions) + _extract_positions_from_mutations(normalized_mutations)))
    query = (q or "").strip()
    if not path.exists():
        return {
            "status": "missing",
            "read_only": True,
            "query": query or None,
            "requested_mutations": normalized_mutations,
            "requested_positions": normalized_positions,
            "evidence_scope": _evidence_scope(include_non_ready),
            "exact_mutation_matches": [],
            "position_matches": [],
            "search": None,
            "counts": {"exact_mutation_matches": 0, "position_matches": 0, "search_matches": 0},
            "path": _path_info(path),
        }

    safe_limit = max(1, min(int(limit or 20), 100))
    ready_clause = "" if include_non_ready else f"AND {_PROVISIONAL_READY_PAPER_CLAUSE}"
    exact_matches: list[dict[str, Any]] = []
    position_matches: list[dict[str, Any]] = []
    with _connect_readonly(path) as conn:
        if normalized_mutations:
            placeholders = ",".join("?" for _ in normalized_mutations)
            exact_matches = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT
                        vm.mutation_code,
                        vm.position,
                        vm.residue_from,
                        vm.residue_to,
                        v.variant_label,
                        v.anchor_display,
                        p.paper_key,
                        p.citation,
                        p.year,
                        p.enzyme_name,
                        p.engineering_objective,
                        p.lock_status,
                        p.ready_for_db,
                        ec.claim_group,
                        ec.evidence_level,
                        ec.claim_summary,
                        GROUP_CONCAT(DISTINCT m.metric_type || ':' || COALESCE(m.metric_value, '') || COALESCE(' ' || m.metric_unit, '')) AS metrics
                    FROM variant_mutations vm
                    JOIN variants v ON v.id = vm.variant_id
                    JOIN papers p ON p.id = v.paper_id
                    LEFT JOIN evidence_claims ec ON ec.variant_id = v.id
                    LEFT JOIN metrics m ON m.claim_id = ec.id
                    WHERE UPPER(vm.mutation_code) IN ({placeholders})
                    {ready_clause}
                    GROUP BY vm.id, ec.id
                    ORDER BY p.year, p.paper_key, vm.position
                    LIMIT ?
                    """,
                    [*normalized_mutations, safe_limit],
                ).fetchall()
            ]

        if normalized_positions:
            placeholders = ",".join("?" for _ in normalized_positions)
            position_matches = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT
                        vm.mutation_code,
                        vm.position,
                        vm.residue_from,
                        vm.residue_to,
                        v.variant_label,
                        v.anchor_display,
                        p.paper_key,
                        p.citation,
                        p.year,
                        p.enzyme_name,
                        p.engineering_objective,
                        p.lock_status,
                        p.ready_for_db,
                        ec.claim_group,
                        ec.evidence_level,
                        ec.claim_summary,
                        GROUP_CONCAT(DISTINCT m.metric_type || ':' || COALESCE(m.metric_value, '') || COALESCE(' ' || m.metric_unit, '')) AS metrics
                    FROM variant_mutations vm
                    JOIN variants v ON v.id = vm.variant_id
                    JOIN papers p ON p.id = v.paper_id
                    LEFT JOIN evidence_claims ec ON ec.variant_id = v.id
                    LEFT JOIN metrics m ON m.claim_id = ec.id
                    WHERE vm.position IN ({placeholders})
                    {ready_clause}
                    GROUP BY vm.id, ec.id
                    ORDER BY vm.position, p.year, p.paper_key
                    LIMIT ?
                    """,
                    [*normalized_positions, safe_limit],
                ).fetchall()
            ]

    search_payload = (
        search_lipase_evidence(q=query, limit=safe_limit, include_non_ready=include_non_ready)
        if query
        else None
    )
    search_counts = search_payload.get("counts", {}) if isinstance(search_payload, dict) else {}
    search_matches = sum(int(value or 0) for value in search_counts.values()) if isinstance(search_counts, dict) else 0
    evidence_level_order = {"direct": 4, "article_level": 3, "inferred": 2, "unknown": 1}
    strongest_evidence = "none"
    for row in [*exact_matches, *position_matches]:
        level = str(row.get("evidence_level") or "unknown")
        if evidence_level_order.get(level, 0) > evidence_level_order.get(strongest_evidence, 0):
            strongest_evidence = level

    return {
        "status": "ready",
        "read_only": True,
        "query": query or None,
        "requested_mutations": normalized_mutations,
        "requested_positions": normalized_positions,
        "evidence_scope": _evidence_scope(include_non_ready),
        "exact_mutation_matches": exact_matches,
        "position_matches": position_matches,
        "search": search_payload,
        "counts": {
            "exact_mutation_matches": len(exact_matches),
            "position_matches": len(position_matches),
            "search_matches": search_matches,
        },
        "strongest_evidence_level": strongest_evidence,
        "recommended_use": (
            "Use exact mutation matches as literature evidence; use position matches as weak context only unless sequence numbering is confirmed."
        ),
        "path": _path_info(path),
    }
