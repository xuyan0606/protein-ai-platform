"""Residue numbering confirmation gate for structure/literature projection."""

from __future__ import annotations

from typing import Any

from app.tools.registry import ToolRegistry


def _row_key(row: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(row.get("source_scheme") or "user_sequence"),
        int(row.get("source_position")),
        str(row.get("target_scheme") or "pdb"),
    )


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_mapping_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Accept unified numbering rows and legacy residue_mapping_sifts mappings."""
    if not isinstance(raw, dict):
        return None

    source_position = _safe_int(raw.get("source_position"))
    target_position = _safe_int(raw.get("target_position"))
    source_scheme = str(raw.get("source_scheme") or "").strip()
    target_scheme = str(raw.get("target_scheme") or "").strip()

    if source_position is None or target_position is None:
        source_position = _safe_int(raw.get("uniprot_position"))
        target_position = _safe_int(raw.get("pdb_residue_no"))
        if source_position is None or target_position is None:
            return None
        source_scheme = source_scheme or "user_sequence"
        target_scheme = target_scheme or "pdb_author"

    confidence = str(raw.get("confidence") or raw.get("mapping_confidence") or "unknown").strip().lower()
    if confidence == "curated_sifts":
        confidence = "sifts"
    if confidence == "inferred_from_coordinate_order":
        confidence = "inferred"

    return {
        **raw,
        "source_scheme": source_scheme or "user_sequence",
        "source_position": source_position,
        "target_scheme": target_scheme or "pdb_author",
        "target_position": target_position,
        "target_chain_id": raw.get("target_chain_id") or raw.get("chain_id"),
        "target_insertion_code": raw.get("target_insertion_code") or raw.get("insertion_code"),
        "target_residue_aa": raw.get("target_residue_aa") or raw.get("residue_aa"),
        "confidence": confidence or "unknown",
        "method": str(raw.get("method") or raw.get("source") or "unknown"),
        "coordinate_system": raw.get("coordinate_system") or "pdb_author_residue_number",
        "mapping_scope": raw.get("mapping_scope") or "chain",
        "gap_status": raw.get("gap_status") or ("missing" if raw.get("missing_in_structure") else "present"),
    }


async def residue_numbering_gate(
    requested_positions: list[int],
    mapping_rows: list[dict[str, Any]] | None = None,
    user_confirmed: bool = False,
    sequence_length: int | None = None,
    pdb_residue_count: int | None = None,
    uniprot_id: str | None = None,
    pdb_id: str | None = None,
    chain_id: str | None = None,
) -> dict[str, Any]:
    """Block unsafe residue projection until numbering evidence is explicit."""
    positions = sorted({int(item) for item in requested_positions or [] if int(item) > 0})
    if not positions:
        return {
            "status": "blocked",
            "blocked_reason": "requested_positions_required",
            "required_inputs": ["requested_positions"],
        }

    limitations: list[str] = []
    if sequence_length and any(pos > sequence_length for pos in positions):
        limitations.append("requested_position_exceeds_user_sequence_length")
    if not mapping_rows:
        return {
            "status": "blocked",
            "blocked_reason": "missing_numbering_mapping",
            "requested_positions": positions,
            "context": {
                "sequence_length": sequence_length,
                "pdb_residue_count": pdb_residue_count,
                "uniprot_id": uniprot_id,
                "pdb_id": pdb_id,
                "chain_id": chain_id,
            },
            "required_evidence": [
                "alignment_or_sifts_mapping",
                "source_scheme_and_target_scheme",
                "gap_or_missing_residue_report",
                "user_confirmation_for_manual_mapping",
            ],
        }

    conflicts: list[dict[str, Any]] = []
    mapped: list[dict[str, Any]] = []
    seen: dict[tuple[str, int, str], int] = {}

    for raw in mapping_rows:
        row = _normalize_mapping_row(raw)
        if row is None:
            limitations.append("invalid_mapping_row")
            continue
        key = _row_key(row)
        previous = seen.get(key)
        if previous is not None and previous != row["target_position"]:
            conflicts.append({
                "source_scheme": key[0],
                "source_position": key[1],
                "target_scheme": key[2],
                "targets": sorted({previous, row["target_position"]}),
            })
        seen[key] = row["target_position"]
        if row["source_position"] in positions:
            mapped.append(row)
            if row.get("has_gap") or row.get("missing_in_structure"):
                limitations.append("requested_position_has_gap_or_missing_structure_residue")
            if row.get("gap_status") and row.get("gap_status") not in {"present", "mapped"}:
                limitations.append("requested_position_has_gap_or_missing_structure_residue")
            if row["confidence"] not in {"high", "curated", "sifts", "exact"}:
                limitations.append("low_or_unknown_mapping_confidence")

    missing = [pos for pos in positions if not any(row["source_position"] == pos for row in mapped)]
    if missing:
        limitations.append("some_requested_positions_not_mapped")
    if conflicts:
        limitations.append("conflicting_mapping_rows")

    if conflicts or missing or not user_confirmed:
        status = "blocked"
        reason = "mapping_conflicts_or_unconfirmed"
    elif limitations:
        status = "warning"
        reason = "mapping_has_limitations"
    else:
        status = "allowed"
        reason = "mapping_confirmed"

    return {
        "status": status,
        "blocked_reason": reason if status == "blocked" else None,
        "requested_positions": positions,
        "mapped_positions": mapped,
        "missing_positions": missing,
        "conflicts": conflicts,
        "limitations": sorted(set(limitations)),
        "numbering_schema": "unified_numbering_registry_v1",
        "user_confirmed": user_confirmed,
        "context": {
            "sequence_length": sequence_length,
            "pdb_residue_count": pdb_residue_count,
            "uniprot_id": uniprot_id,
            "pdb_id": pdb_id,
            "chain_id": chain_id,
        },
        "allowed_operations": {
            "structure_highlight": status in {"allowed", "warning"},
            "literature_projection": status == "allowed",
            "automatic_combination_design": status == "allowed",
        },
    }


ToolRegistry.register(
    name="residue_numbering_gate",
    description=(
        "Validate residue numbering before projecting user/literature mutation positions "
        "onto PDB/UniProt/structure coordinates. Blocks unsafe projection when mapping rows, "
        "gap reports, or user confirmation are missing."
    ),
    parameters={
        "type": "object",
        "properties": {
            "requested_positions": {"type": "array", "items": {"type": "integer"}},
            "mapping_rows": {"type": "array", "items": {"type": "object"}},
            "user_confirmed": {"type": "boolean", "default": False},
            "sequence_length": {"type": "integer"},
            "pdb_residue_count": {"type": "integer"},
            "uniprot_id": {"type": "string"},
            "pdb_id": {"type": "string"},
            "chain_id": {"type": "string"},
        },
        "required": ["requested_positions"],
    },
    handler=residue_numbering_gate,
    category="engineering",
    timeout_seconds=30,
)
