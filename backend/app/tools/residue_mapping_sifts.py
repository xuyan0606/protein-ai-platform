"""Residue-level PDB ↔ UniProt mapping helper.

Phase 1 implementation intentionally avoids external SIFTS downloads. It
creates an auditable SIFTS-style mapping from parsed PDB coordinates and an
optional UniProt start offset, which is enough to wire downstream structure
annotation and guardrail workflows without introducing a database migration.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services import storage
from app.services.pdb_parser import _AA3TO1, _POLYMER_HETATM_RESIDUES
from app.tools.registry import ToolRegistry


def _iter_pdb_residues(pdb_data: str, chain_id: str | None = None) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str, str]] = set()
    residues: list[dict[str, Any]] = []

    for line in pdb_data.splitlines():
        record = line[:6].strip()
        if record not in {"ATOM", "HETATM"}:
            continue

        try:
            alt_loc = line[16]
            res_name = line[17:20].strip().upper()
            chain = line[21].strip() or "_"
            pdb_residue_no = int(line[22:26])
            insertion_code = line[26].strip()
        except (IndexError, ValueError):
            continue

        if chain_id and chain != chain_id:
            continue
        if alt_loc not in {"", " ", "A"}:
            continue
        if res_name == "HOH":
            continue
        if record == "HETATM" and res_name not in _POLYMER_HETATM_RESIDUES:
            continue

        key = (chain, pdb_residue_no, insertion_code, res_name)
        if key in seen:
            continue
        seen.add(key)
        residues.append(
            {
                "chain_id": chain,
                "pdb_residue_no": pdb_residue_no,
                "insertion_code": insertion_code or None,
                "residue_name": res_name,
                "residue_aa": _AA3TO1.get(res_name, "X"),
            }
        )

    return sorted(residues, key=lambda item: (item["chain_id"], item["pdb_residue_no"], item["insertion_code"] or ""))


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _normalize_mapping_row(row: dict[str, Any]) -> dict[str, Any] | None:
    pdb_residue_no = _safe_int(
        _first_value(row, "pdb_residue_no", "pdb_residue_number", "pdb_resnum", "residue_number")
    )
    uniprot_position = _safe_int(
        _first_value(row, "uniprot_position", "uniprot_residue_no", "uniprot_residue_number")
    )
    chain = str(_first_value(row, "chain_id", "chain", "pdb_chain") or "").strip() or "_"
    if pdb_residue_no is None or uniprot_position is None:
        return None

    residue_name = str(_first_value(row, "residue_name", "pdb_residue_name") or "").strip().upper()
    residue_aa = str(_first_value(row, "residue_aa", "aa", "uniprot_residue") or "").strip().upper()
    if not residue_aa and residue_name:
        residue_aa = _AA3TO1.get(residue_name, "X")

    return {
        "chain_id": chain,
        "pdb_residue_no": pdb_residue_no,
        "insertion_code": str(_first_value(row, "insertion_code", "icode") or "").strip() or None,
        "residue_name": residue_name or None,
        "residue_aa": residue_aa[:1] or "X",
        "uniprot_id": str(_first_value(row, "uniprot_id", "uniprot", "accession") or "").strip() or None,
        "uniprot_position": uniprot_position,
        "mapping_confidence": str(_first_value(row, "mapping_confidence", "confidence") or "").strip()
        or "curated_sifts",
    }


def _gate_confidence(confidence: Any) -> str:
    normalized = str(confidence or "").strip().lower()
    if normalized in {"curated_sifts", "local_sifts", "sifts", "curated", "exact", "high"}:
        return "sifts"
    if normalized in {"inferred_from_coordinate_order", "coordinate_order_inference", "inferred"}:
        return "inferred"
    return normalized or "unknown"


def _build_numbering_registry_rows(
    mappings: list[dict[str, Any]],
    *,
    source: str,
    pdb_id: str,
    uniprot_id: str,
    uniprot_start: int | None = None,
) -> list[dict[str, Any]]:
    """Emit gate-ready numbering rows while preserving legacy mapping rows."""
    rows: list[dict[str, Any]] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        pdb_position = _safe_int(mapping.get("pdb_residue_no"))
        uniprot_position = _safe_int(mapping.get("uniprot_position"))
        if pdb_position is None or uniprot_position is None:
            continue
        confidence = _gate_confidence(mapping.get("mapping_confidence") or mapping.get("confidence"))
        base = {
            "target_scheme": "pdb_author",
            "target_position": pdb_position,
            "target_chain_id": mapping.get("chain_id"),
            "target_insertion_code": mapping.get("insertion_code"),
            "target_residue_aa": mapping.get("residue_aa") or "X",
            "pdb_id": pdb_id or None,
            "uniprot_id": mapping.get("uniprot_id") or uniprot_id or None,
            "coordinate_system": "pdb_author_residue_number",
            "mapping_scope": "chain",
            "gap_status": "present",
            "has_gap": False,
            "missing_in_structure": False,
            "confidence": confidence,
            "method": source,
            "source": source,
        }
        rows.append({
            **base,
            "source_scheme": "user_sequence",
            "source_position": uniprot_position,
            "source_coordinate": f"user_sequence:{uniprot_position}",
            "target_coordinate": f"{mapping.get('chain_id') or '_'}:{pdb_position}{mapping.get('insertion_code') or ''}",
            "mapping_basis": (
                "assumed_user_sequence_matches_uniprot_coordinate"
                if source == "local_sifts_mapping"
                else f"coordinate_order_uniprot_start_{uniprot_start or 1}"
            ),
        })
        if mapping.get("uniprot_id") or uniprot_id:
            rows.append({
                **base,
                "source_scheme": "uniprot",
                "source_position": uniprot_position,
                "source_coordinate": f"{mapping.get('uniprot_id') or uniprot_id}:{uniprot_position}",
                "target_coordinate": f"{mapping.get('chain_id') or '_'}:{pdb_position}{mapping.get('insertion_code') or ''}",
                "mapping_basis": (
                    "local_sifts_mapping"
                    if source == "local_sifts_mapping"
                    else f"coordinate_order_uniprot_start_{uniprot_start or 1}"
                ),
            })
    return rows


def _candidate_mapping_files(mapping_path: str, pdb_id: str) -> list[Path]:
    root = Path(mapping_path).expanduser()
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []

    candidates = []
    normalized_id = pdb_id.strip().lower()
    if normalized_id:
        for suffix in (".json", ".csv", ".tsv"):
            candidates.append(root / f"{normalized_id}{suffix}")
            candidates.append(root / f"{normalized_id.upper()}{suffix}")
    candidates.extend(
        [
            root / "mappings.json",
            root / "mappings.csv",
            root / "mappings.tsv",
            root / "residue_mappings.json",
            root / "residue_mappings.csv",
            root / "residue_mappings.tsv",
        ]
    )
    return [path for path in candidates if path.exists()]


def _read_mapping_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("mappings") or payload.get("entries") or payload.get("rows") or []
        else:
            rows = payload
        return [row for row in rows if isinstance(row, dict)]

    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def _load_local_sifts_mappings(
    *,
    pdb_id: str,
    chain_id: str | None,
    uniprot_id: str,
) -> tuple[list[dict[str, Any]], str | None]:
    mapping_path = (getattr(settings, "SIFTS_MAPPING_PATH", "") or "").strip()
    if not mapping_path:
        return [], None

    normalized_pdb_id = pdb_id.strip().lower()
    requested_uniprot = uniprot_id.strip().upper()
    mappings: list[dict[str, Any]] = []
    source_path: str | None = None

    for path in _candidate_mapping_files(mapping_path, normalized_pdb_id):
        rows = _read_mapping_file(path)
        source_path = str(path)
        for row in rows:
            row_pdb_id = str(_first_value(row, "pdb_id", "structure_id", "entry_id") or "").strip().lower()
            if normalized_pdb_id and row_pdb_id and row_pdb_id != normalized_pdb_id:
                continue
            normalized = _normalize_mapping_row(row)
            if normalized is None:
                continue
            if chain_id and normalized["chain_id"] != chain_id:
                continue
            if requested_uniprot and (normalized.get("uniprot_id") or "").upper() != requested_uniprot:
                continue
            mappings.append(normalized)

        if mappings:
            break

    mappings.sort(key=lambda item: (item["chain_id"], item["pdb_residue_no"], item["insertion_code"] or ""))
    return mappings, source_path


def _with_report_contract(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "")
    if source == "input_sequence_exact_coordinate_mapping":
        payload.setdefault("capability_status", "verified_input_structure_mapping")
        payload.setdefault("evidence_level", "EXACT_SEQUENCE_COORDINATE_MAPPING")
        payload.setdefault(
            "report_boundary",
            (
                "输入 FASTA 与所选 PDB 蛋白链的坐标序列逐残基一致；可用于输入序列↔PDB author 编号换算。"
                "这不是 UniProt/SIFTS 映射，不得伪造 UniProt 编号。"
            ),
        )
    elif source == "local_sifts_mapping":
        payload.setdefault("capability_status", "local_residue_mapping")
        payload.setdefault("evidence_level", "NUMBERING_MAPPING")
        payload.setdefault(
            "report_boundary",
            (
                "使用本地映射文件建立 PDB↔UniProt/序列编号关系；仍需核对来源、链、缺失残基、成熟肽/"
                "标签边界后，才可作为下单编号依据。"
            ),
        )
    elif source == "local_sifts_style_inference":
        payload.setdefault("capability_status", "coordinate_order_inference")
        payload.setdefault("evidence_level", "COORDINATE_ORDER_INFERENCE")
        payload.setdefault(
            "report_boundary",
            (
                "这是按 PDB 坐标残基顺序生成的 SIFTS-style 推断，不是外部 SIFTS/UniProt 实证映射；"
                "不能把 coordinate position 直接写成成熟蛋白或 UniProt 编号。"
            ),
        )
    else:
        payload.setdefault("capability_status", "residue_mapping_qc")
        payload.setdefault("evidence_level", "NUMBERING_QC")
        payload.setdefault(
            "report_boundary",
            "残基编号工具当前未得到可用映射；只能记录缺口，不能作为突变下单编号依据。",
        )
    return payload


async def residue_mapping_sifts(
    pdb_data: str = "",
    pdb_object_name: str = "",
    pdb_id: str = "",
    chain_id: str = "",
    uniprot_id: str = "",
    uniprot_start: int = 1,
    input_sequence: str = "",
) -> dict[str, Any]:
    """Return a SIFTS-style residue mapping for a PDB chain.

    Args:
        pdb_data: Raw PDB text. Used directly when provided.
        pdb_object_name: Stored PDB object name to load when pdb_data is empty.
        pdb_id: Optional PDB identifier used to filter local SIFTS mapping files.
        chain_id: Optional PDB chain filter.
        uniprot_id: Optional UniProt accession to attach to mapping rows.
        uniprot_start: UniProt position corresponding to the first mapped PDB residue.
    """

    if not pdb_data and pdb_object_name:
        pdb_data = (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")

    if not pdb_data.strip():
        return _with_report_contract({
            "found": False,
            "status": "failed",
            "error_code": "MISSING_PDB",
            "error": "Provide pdb_data or pdb_object_name.",
            "mappings": [],
        })

    start = max(1, int(uniprot_start or 1))
    chain_filter = chain_id.strip() or None
    local_mappings, mapping_source = _load_local_sifts_mappings(
        pdb_id=pdb_id,
        chain_id=chain_filter,
        uniprot_id=uniprot_id,
    )
    if local_mappings:
        registry_rows = _build_numbering_registry_rows(
            local_mappings,
            source="local_sifts_mapping",
            pdb_id=pdb_id,
            uniprot_id=uniprot_id,
        )
        return _with_report_contract({
            "found": True,
            "status": "completed",
            "source": "local_sifts_mapping",
            "mapping_source": mapping_source,
            "pdb_id": pdb_id or None,
            "uniprot_id": uniprot_id or None,
            "chain_id": chain_filter,
            "mapping_count": len(local_mappings),
            "mappings": local_mappings,
            "numbering_registry_rows": registry_rows,
            "numbering_registry_status": "ready",
            "coordinate_systems": ["user_sequence", "uniprot", "pdb_author"],
            "limitations": [],
        })

    residues = _iter_pdb_residues(pdb_data, chain_filter)

    if not residues:
        return _with_report_contract({
            "found": False,
            "status": "failed",
            "error_code": "NO_RESIDUES",
            "error": "No protein residues were found for the requested chain.",
            "mappings": [],
        })

    normalized_input_sequence = "".join(str(input_sequence or "").split()).upper()
    coordinate_sequence = "".join(str(item.get("residue_aa") or "X") for item in residues)
    if normalized_input_sequence and normalized_input_sequence == coordinate_sequence:
        mappings = [
            {
                **residue,
                "user_sequence_position": idx,
                "uniprot_id": None,
                "uniprot_position": None,
                "mapping_confidence": "exact_input_sequence_match",
            }
            for idx, residue in enumerate(residues, start=1)
        ]
        registry_rows = []
        for mapping in mappings:
            registry_rows.append({
                "source_scheme": "user_sequence",
                "source_position": mapping["user_sequence_position"],
                "source_coordinate": f"user_sequence:{mapping['user_sequence_position']}",
                "target_scheme": "pdb_author",
                "target_position": mapping["pdb_residue_no"],
                "target_chain_id": mapping["chain_id"],
                "target_insertion_code": mapping.get("insertion_code"),
                "target_residue_aa": mapping["residue_aa"],
                "target_coordinate": f"{mapping['chain_id']}:{mapping['pdb_residue_no']}{mapping.get('insertion_code') or ''}",
                "pdb_id": pdb_id or None,
                "uniprot_id": None,
                "coordinate_system": "pdb_author_residue_number",
                "mapping_scope": "chain",
                "gap_status": "present",
                "has_gap": False,
                "missing_in_structure": False,
                "confidence": "exact",
                "method": "exact_input_sequence_match",
                "source": "input_sequence_exact_coordinate_mapping",
                "mapping_basis": "input_sequence_equals_coordinate_sequence",
            })
        return _with_report_contract({
            "found": True,
            "status": "completed",
            "source": "input_sequence_exact_coordinate_mapping",
            "pdb_id": pdb_id or None,
            "uniprot_id": None,
            "chain_id": chain_filter,
            "mapping_count": len(mappings),
            "mappings": mappings,
            "numbering_registry_rows": registry_rows,
            "numbering_registry_status": "ready",
            "coordinate_systems": ["user_sequence", "pdb_author"],
            "sequence_match": {"status": "exact", "length": len(mappings)},
            "limitations": ["No UniProt coordinate mapping was established."],
        })

    mappings = []
    for idx, residue in enumerate(residues):
        mappings.append(
            {
                **residue,
                "uniprot_id": uniprot_id or None,
                "uniprot_position": start + idx,
                "mapping_confidence": "inferred_from_coordinate_order",
            }
        )

    registry_rows = _build_numbering_registry_rows(
        mappings,
        source="local_sifts_style_inference",
        pdb_id=pdb_id,
        uniprot_id=uniprot_id,
        uniprot_start=start,
    )
    return _with_report_contract({
        "found": True,
        "status": "completed",
        "source": "local_sifts_style_inference",
        "pdb_id": pdb_id or None,
        "uniprot_id": uniprot_id or None,
        "chain_id": chain_filter,
        "uniprot_start": start,
        "mapping_count": len(mappings),
        "mappings": mappings,
        "numbering_registry_rows": registry_rows,
        "numbering_registry_status": "inferred_requires_confirmation",
        "coordinate_systems": ["user_sequence", "uniprot", "pdb_author"],
        "limitations": [
            "External SIFTS residue records were not downloaded in this phase.",
            "UniProt positions are inferred from coordinate order and uniprot_start.",
        ],
    })


ToolRegistry.register(
    name="residue_mapping_sifts",
    description=(
        "Build a SIFTS-style residue mapping between PDB residue numbering and "
        "UniProt positions. Uses local PDB coordinate order plus an optional "
        "UniProt start offset; suitable as a first-pass structure annotation map."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pdb_data": {"type": "string", "description": "Raw PDB text."},
            "pdb_object_name": {"type": "string", "description": "Stored PDB object name."},
            "pdb_id": {"type": "string", "description": "Optional PDB ID for local SIFTS mapping lookup."},
            "chain_id": {"type": "string", "description": "Optional PDB chain ID filter."},
            "uniprot_id": {"type": "string", "description": "Optional UniProt accession."},
            "uniprot_start": {
                "type": "integer",
                "minimum": 1,
                "description": "UniProt position aligned to the first mapped PDB residue.",
                "default": 1,
            },
            "input_sequence": {
                "type": "string",
                "description": "Optional independent FASTA sequence for exact input-sequence to PDB author mapping.",
            },
        },
    },
    handler=residue_mapping_sifts,
    is_async=True,
    category="structure",
    timeout_seconds=30,
)
