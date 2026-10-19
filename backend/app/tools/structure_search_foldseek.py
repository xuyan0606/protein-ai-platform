"""Foldseek/template structure search entrypoint.

The first deployable layer exposes a stable tool contract and a deterministic
local fallback. If a Foldseek endpoint is configured later, the call site can
be upgraded without changing planner/tool integration.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

import httpx

from app.core.config import settings
from app.services import storage
from app.services.pdb_parser import parse_pdb
from app.services.tool_cache import get_cached_result, set_cached_result
from app.tools.registry import ToolRegistry

_LOCAL_RESULT_FIELDS = (
    "query",
    "target",
    "evalue",
    "bits",
    "alntmscore",
    "qtmscore",
    "ttmscore",
    "prob",
)


class LocalFoldseekConfigError(RuntimeError):
    pass


def _extract_pdb_id(target: str) -> str:
    match = re.search(r"\b([0-9][A-Za-z0-9]{3})\b", str(target or ""))
    return match.group(1).upper() if match else ""


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _structure_summary(pdb_data: str) -> dict[str, Any]:
    analysis = parse_pdb(pdb_data)
    chains = analysis.get("chains") or []
    return {
        "method": analysis.get("method"),
        "resolution": analysis.get("resolution"),
        "r_factor": analysis.get("r_factor"),
        "space_group": analysis.get("space_group"),
        "b_factor_stats": analysis.get("b_factor_stats"),
        "b_factor_scope": analysis.get("b_factor_scope"),
        "title": (analysis.get("header") or {}).get("title"),
        "chain_count": len(chains),
        "total_residues": analysis.get("total_residues") or 0,
        "total_atoms": analysis.get("total_atoms") or 0,
        "seqres_length": len(analysis.get("seqres_sequence") or ""),
        "seqres_by_chain": {
            chain_id: len(sequence)
            for chain_id, sequence in (analysis.get("seqres_by_chain") or {}).items()
        },
        "compound_annotation": analysis.get("compound_annotation") or {},
        "engineered_mutations": analysis.get("engineered_mutations") or [],
        "chains": [
            {
                "chain_id": chain.get("chain_id"),
                "residue_count": chain.get("residue_count"),
                "residue_range": chain.get("residue_range"),
                "sequence_sha256": hashlib.sha256(
                    str(chain.get("sequence") or "").upper().encode("utf-8")
                ).hexdigest() if chain.get("sequence") else None,
            }
            for chain in chains
        ],
        "nonpolymer_components": analysis.get("nonpolymer_components") or [],
    }


def _with_report_contract(payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "").lower()
    found = bool(payload.get("found"))
    if status == "completed" and found:
        payload.setdefault("capability_status", "structure_similarity_search")
        payload.setdefault("evidence_level", "STRUCTURE_SIMILARITY")
    else:
        payload.setdefault("capability_status", "structure_input_qc")
        payload.setdefault("evidence_level", "STRUCTURE_INPUT_QC")
    payload.setdefault(
        "report_boundary",
        (
            "Foldseek/结构解析只能作为结构相似性和输入质控证据；弱 TM-score、模板 RCSB 注释或结构摘要"
            "不能单独确认输入结构的酶身份、催化残基、底物口袋或 UniProt 编号。"
        ),
    )
    return payload


async def _load_pdb_data(pdb_data: str, pdb_object_name: str) -> str:
    if pdb_data.strip():
        return pdb_data
    if pdb_object_name:
        return (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")
    return ""


def _resolve_local_database_path(database: str) -> str:
    def _resolve_db_prefix(path: Path) -> str:
        if path.is_file():
            return str(path)
        if not path.is_dir():
            return ""

        # Prefer base DB prefixes like `protein_ai_pdb` over auxiliary files
        # such as `.idx`, `_ca`, `_ss`, `.lookup`, or `.index`.
        for dbtype_file in sorted(path.glob("*.dbtype")):
            stem = dbtype_file.name.removesuffix(".dbtype")
            if any(
                token in stem
                for token in (".idx", "_ca", "_ss", "_h", ".lookup", ".source", ".index")
            ):
                continue
            candidate = path / stem
            if candidate.exists():
                return str(candidate)
        return ""

    explicit_attr = f"FOLDSEEK_DATABASE_{database.upper()}"
    explicit_path = getattr(settings, explicit_attr, "") or ""
    if explicit_path.strip():
        resolved = _resolve_db_prefix(Path(explicit_path.strip()).expanduser())
        return resolved or explicit_path.strip()

    root = getattr(settings, "FOLDSEEK_DATABASE_ROOT", "") or ""
    if not root.strip():
        return ""
    database_dir = (Path(root).expanduser() / database).resolve()
    resolved = _resolve_db_prefix(database_dir)
    return resolved or str(database_dir)


def _parse_local_results(result_path: Path, max_results: int) -> list[dict[str, Any]]:
    if not result_path.exists():
        return []

    results: list[dict[str, Any]] = []
    with result_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, fieldnames=_LOCAL_RESULT_FIELDS, delimiter="\t")
        for rank, row in enumerate(reader, start=1):
            if rank > max_results:
                break
            target = (row.get("target") or "").strip()
            if not target:
                continue
            results.append(
                {
                    "rank": rank,
                    "query": (row.get("query") or "").strip(),
                    "target": target,
                    "evalue": _to_float(row.get("evalue") or ""),
                    "bits": _to_float(row.get("bits") or ""),
                    "aligned_tm_score": _to_float(row.get("alntmscore") or ""),
                    "query_tm_score": _to_float(row.get("qtmscore") or ""),
                    "target_tm_score": _to_float(row.get("ttmscore") or ""),
                    "probability": _to_float(row.get("prob") or ""),
                    "source": "local_cli",
                }
            )
    return results


async def _fetch_rcsb_entries(pdb_ids: list[str], *, include_nonpolymer: bool = False) -> dict[str, Any]:
    """Fetch lightweight official RCSB annotations for PDB hits.

    This is best-effort evidence enrichment. Any network/API failure is returned
    as degraded metadata and never changes the raw Foldseek hit list.
    """
    pdb_ids = list(dict.fromkeys(item.upper() for item in pdb_ids if item))[:5]
    if not pdb_ids:
        return {"status": "not_applicable", "source": "RCSB Data API", "hits": []}

    annotations: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            for pdb_id in pdb_ids:
                entry_resp = await client.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}")
                entry_resp.raise_for_status()
                entry = entry_resp.json()
                entity_ids = (
                    entry.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids")
                    if isinstance(entry, dict)
                    else []
                )
                entity_id = str(entity_ids[0]) if isinstance(entity_ids, list) and entity_ids else "1"
                entity_payload: dict[str, Any] = {}
                try:
                    entity_resp = await client.get(
                        f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"
                    )
                    entity_resp.raise_for_status()
                    entity_payload = entity_resp.json()
                except Exception:
                    entity_payload = {}

                entity = entity_payload.get("rcsb_polymer_entity", {}) if isinstance(entity_payload, dict) else {}
                identifiers = (
                    entity_payload.get("rcsb_polymer_entity_container_identifiers", {})
                    if isinstance(entity_payload, dict)
                    else {}
                )
                refs = identifiers.get("reference_sequence_identifiers") if isinstance(identifiers, dict) else []
                nonpolymer_entities: list[dict[str, Any]] = []
                if include_nonpolymer and isinstance(entry, dict):
                    nonpolymer_ids = entry.get("rcsb_entry_container_identifiers", {}).get("non_polymer_entity_ids") or []
                    for nonpolymer_id in nonpolymer_ids if isinstance(nonpolymer_ids, list) else []:
                        try:
                            nonpolymer_resp = await client.get(
                                f"https://data.rcsb.org/rest/v1/core/nonpolymer_entity/{pdb_id}/{nonpolymer_id}"
                            )
                            nonpolymer_resp.raise_for_status()
                            nonpolymer_payload = nonpolymer_resp.json()
                        except Exception:
                            continue
                        identifiers_payload = nonpolymer_payload.get(
                            "rcsb_nonpolymer_entity_container_identifiers", {}
                        ) if isinstance(nonpolymer_payload, dict) else {}
                        description_payload = nonpolymer_payload.get("pdbx_entity_nonpoly", {}) if isinstance(nonpolymer_payload, dict) else {}
                        nonpolymer_entities.append({
                            "entity_id": str(nonpolymer_id),
                            "component_id": identifiers_payload.get("nonpolymer_comp_id"),
                            "name": description_payload.get("name"),
                            "source": "RCSB Data API",
                        })
                annotations.append({
                    "pdb_id": pdb_id,
                    "title": entry.get("struct", {}).get("title") if isinstance(entry, dict) else None,
                    "experimental_methods": [
                        item.get("method")
                        for item in entry.get("exptl", [])
                        if isinstance(item, dict) and item.get("method")
                    ] if isinstance(entry, dict) else [],
                    "resolution": (
                        entry.get("rcsb_entry_info", {}).get("resolution_combined")
                        if isinstance(entry, dict)
                        else None
                    ),
                    "entity_id": entity_id,
                    "entity_description": entity.get("pdbx_description") if isinstance(entity, dict) else None,
                    "reference_sequence_identifiers": refs if isinstance(refs, list) else [],
                    "nonpolymer_entities": nonpolymer_entities,
                    "source": "RCSB Data API",
                })
    except Exception as exc:
        return {
            "status": "degraded",
            "source": "RCSB Data API",
            "error": str(exc),
            "hits": annotations,
        }
    return {
        "status": "completed",
        "source": "RCSB Data API",
        "hits": annotations,
    }


async def _fetch_rcsb_annotations(results: list[dict[str, Any]]) -> dict[str, Any]:
    pdb_ids: list[str] = []
    for row in results[:5]:
        pdb_id = _extract_pdb_id(str(row.get("target") or ""))
        if pdb_id and pdb_id not in pdb_ids:
            pdb_ids.append(pdb_id)
    return await _fetch_rcsb_entries(pdb_ids)


async def _fetch_query_rcsb_annotation(pdb_id: str) -> dict[str, Any]:
    payload = await _fetch_rcsb_entries([pdb_id], include_nonpolymer=True)
    payload["evidence_role"] = "direct_query_entry_annotation"
    payload["pdb_id"] = pdb_id.upper() if pdb_id else None
    return payload


def _execute_local_foldseek_command(
    *,
    binary: str,
    query_path: Path,
    database_path: str,
    result_path: Path,
    work_dir: Path,
    max_results: int,
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        binary,
        "easy-search",
        str(query_path),
        database_path,
        str(result_path),
        str(work_dir),
        "--max-seqs",
        str(max_results),
        "--format-output",
        ",".join(_LOCAL_RESULT_FIELDS),
    ]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        detail = stderr or stdout or f"exit code {proc.returncode}"
        raise RuntimeError(detail)


async def _run_local_foldseek_search(
    loaded_pdb: str,
    database: str,
    max_results: int,
) -> dict[str, Any]:
    binary = (getattr(settings, "FOLDSEEK_BINARY", "") or "").strip()
    database_path = _resolve_local_database_path(database)
    if not binary and not database_path:
        raise LocalFoldseekConfigError("Local Foldseek CLI is not configured.")
    if not binary:
        raise LocalFoldseekConfigError("FOLDSEEK_BINARY is not configured.")
    if not database_path:
        raise LocalFoldseekConfigError(
            f"Foldseek database path is not configured for database '{database}'."
        )

    with tempfile.TemporaryDirectory(prefix="foldseek_search_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        query_path = tmp_path / "query.pdb"
        result_path = tmp_path / "results.tsv"
        work_dir = tmp_path / "work"
        query_path.write_text(loaded_pdb, encoding="utf-8")
        await asyncio.to_thread(
            _execute_local_foldseek_command,
            binary=binary,
            query_path=query_path,
            database_path=database_path,
            result_path=result_path,
            work_dir=work_dir,
            max_results=max_results,
        )
        return {
            "backend": "local_cli",
            "database_path": database_path,
            "results": _parse_local_results(result_path, max_results),
        }


async def structure_search_foldseek(
    pdb_data: str = "",
    pdb_object_name: str = "",
    pdb_id: str = "",
    database: str = "pdb",
    max_results: int = 10,
) -> dict[str, Any]:
    """Search for structural templates using Foldseek when configured.

    Without a configured Foldseek backend this returns a clear degraded result
    with parsed structure context, rather than pretending a search was run.
    """

    loaded_pdb = await _load_pdb_data(pdb_data, pdb_object_name)
    if not loaded_pdb.strip():
        return _with_report_contract({
            "found": False,
            "status": "failed",
            "error_code": "MISSING_PDB",
            "error": "Provide pdb_data or pdb_object_name.",
            "results": [],
        })

    max_results = max(1, min(int(max_results or 10), 50))
    endpoint = getattr(settings, "FOLDSEEK_API_URL", "") or ""
    local_database_path = _resolve_local_database_path(database)
    normalized_pdb_id = pdb_id.strip().upper()
    cache_params = {
        "cache_contract_version": 2,
        "pdb_sha256": hashlib.sha256(loaded_pdb.encode("utf-8")).hexdigest(),
        "pdb_object_name": pdb_object_name,
        "pdb_id": normalized_pdb_id,
        "database": database,
        "max_results": max_results,
        "foldseek_endpoint": endpoint,
        "foldseek_binary": getattr(settings, "FOLDSEEK_BINARY", "") or "",
        "foldseek_database_path": local_database_path,
    }
    cached = await get_cached_result("structure_search_foldseek", cache_params)
    if cached is not None:
        return _with_report_contract(cached)

    if not endpoint:
        try:
            local_payload = await _run_local_foldseek_search(loaded_pdb, database, max_results)
        except LocalFoldseekConfigError:
            local_payload = None
        except Exception as exc:
            stale = await get_cached_result("structure_search_foldseek", cache_params, allow_stale=True)
            if stale is not None:
                stale["status"] = "stale_cache"
                stale["warning"] = (
                    "Foldseek local CLI unavailable; returned cached result. "
                    f"Cause: {exc}"
                )
                stale["backend"] = "local_cli"
                stale.setdefault("cache", {})
                stale["cache"]["stale"] = True
                return _with_report_contract(stale)
            return _with_report_contract({
                "found": False,
                "status": "degraded",
                "error_code": "FOLDSEEK_DEGRADED",
                "warning": f"Foldseek local CLI failed: {exc}",
                "backend": "local_cli",
                "database": database,
                "results_count": 0,
                "results": [],
                "query_structure": _structure_summary(loaded_pdb),
                "cache": {"hit": False, "stale": False},
            })

        if local_payload is not None:
            rcsb_annotations = await _fetch_rcsb_annotations(local_payload["results"])
            query_annotation = await _fetch_query_rcsb_annotation(normalized_pdb_id) if normalized_pdb_id else {
                "status": "not_applicable", "source": "RCSB Data API", "hits": [],
                "evidence_role": "direct_query_entry_annotation", "pdb_id": None,
            }
            completed = {
                "found": bool(local_payload["results"]),
                "status": "completed",
                "backend": "local_cli",
                "database": database,
                "database_path": local_payload["database_path"],
                "results_count": len(local_payload["results"]),
                "results": local_payload["results"],
                "rcsb_annotations": rcsb_annotations,
                "query_rcsb_annotation": query_annotation,
                "query_pdb_id": normalized_pdb_id or None,
                "query_structure": _structure_summary(loaded_pdb),
                "cache": {"hit": False, "stale": False},
            }
            _with_report_contract(completed)
            await set_cached_result("structure_search_foldseek", cache_params, completed)
            return completed

        degraded = {
            "found": False,
            "status": "degraded",
            "error_code": "FOLDSEEK_NOT_CONFIGURED",
            "warning": (
                "Foldseek endpoint/local CLI is not configured; returned local structure summary only."
            ),
            "backend": "summary_only",
            "database": database,
            "results_count": 0,
            "results": [],
            "query_rcsb_annotation": (
                await _fetch_query_rcsb_annotation(normalized_pdb_id)
                if normalized_pdb_id else {
                    "status": "not_applicable", "source": "RCSB Data API", "hits": [],
                    "evidence_role": "direct_query_entry_annotation", "pdb_id": None,
                }
            ),
            "query_pdb_id": normalized_pdb_id or None,
            "query_structure": _structure_summary(loaded_pdb),
            "cache": {"hit": False, "stale": False},
        }
        _with_report_contract(degraded)
        await set_cached_result("structure_search_foldseek", cache_params, degraded, ttl_seconds=300)
        return degraded

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                endpoint.rstrip("/") + "/search",
                json={"pdb": loaded_pdb, "database": database, "max_results": max_results},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        stale = await get_cached_result("structure_search_foldseek", cache_params, allow_stale=True)
        if stale is not None:
            stale["status"] = "stale_cache"
            stale["warning"] = f"Foldseek live query unavailable; returned cached result. Cause: {exc}"
            stale["backend"] = "http"
            stale.setdefault("cache", {})
            stale["cache"]["stale"] = True
            return _with_report_contract(stale)
        return _with_report_contract({
            "found": False,
            "status": "degraded",
            "error_code": "FOLDSEEK_DEGRADED",
            "warning": f"Foldseek request failed: {exc}",
            "backend": "http",
            "database": database,
            "results_count": 0,
            "results": [],
            "query_structure": _structure_summary(loaded_pdb),
            "cache": {"hit": False, "stale": False},
        })

    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list):
        results = []

    completed = {
        "found": bool(results),
        "status": "completed",
        "backend": "http",
        "database": database,
        "results_count": len(results),
        "results": results[:max_results],
        "rcsb_annotations": await _fetch_rcsb_annotations(results[:max_results]),
        "query_rcsb_annotation": (
            await _fetch_query_rcsb_annotation(normalized_pdb_id)
            if normalized_pdb_id else {
                "status": "not_applicable", "source": "RCSB Data API", "hits": [],
                "evidence_role": "direct_query_entry_annotation", "pdb_id": None,
            }
        ),
        "query_pdb_id": normalized_pdb_id or None,
        "query_structure": _structure_summary(loaded_pdb),
        "cache": {"hit": False, "stale": False},
    }
    _with_report_contract(completed)
    await set_cached_result("structure_search_foldseek", cache_params, completed)
    return completed


ToolRegistry.register(
    name="structure_search_foldseek",
    description=(
        "Search for structurally similar templates with Foldseek via remote "
        "endpoint or local CLI when configured. Returns a degraded local "
        "structure summary if Foldseek is unavailable, preserving a stable tool contract."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pdb_data": {"type": "string", "description": "Raw PDB text."},
            "pdb_object_name": {"type": "string", "description": "Stored PDB object name."},
            "pdb_id": {"type": "string", "description": "Known four-character PDB ID for direct query-entry annotation."},
            "database": {
                "type": "string",
                "enum": ["pdb", "alphafold", "custom"],
                "description": "Structure database to search.",
                "default": "pdb",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of template hits to return.",
                "default": 10,
            },
        },
    },
    handler=structure_search_foldseek,
    is_async=True,
    category="structure",
    timeout_seconds=60,
)
