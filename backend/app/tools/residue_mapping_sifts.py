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
from app.services.pdb_parser import _AA3TO1, parse_pdb
from app.tools.registry import ToolRegistry


# Global-alignment acceptance thresholds for projecting input-sequence numbering
# onto PDB author numbering. Identity is checked first: below 0.95 the aligned
# pairs are unreliable enough that a systematic (whole-block) numbering
# misprojection can masquerade as a handful of mismatches, so the projection is
# not accepted as an ordering-number basis at all.
MIN_ALIGNMENT_IDENTITY = 0.95
# Coverage guards against mostly-unmapped sequences: a short aligned island in a
# long input leaves most positions without a structure coordinate.
MIN_ALIGNMENT_COVERAGE = 0.8
# Coverage and identity only mean something if enough aligned pairs are actually
# comparable. Structure residues with a non-standard component (e.g. UNK, MSE
# before conversion) render as "X"; such pairs are excluded from the identity
# ratio, so a short island of matching residues could otherwise yield identity
# 1.0 over a handful of comparable sites. Require at least this many comparable
# aligned pairs before the projection is accepted.
MIN_IDENTITY_BASIS = 20
# Sentinel letters that carry no residue identity: structure "X" for unknown
# components, plus the usual non-residue characters a user FASTA may contain.
_NON_IDENTITY_LETTERS = frozenset({"X", "-", "*"})


def _iter_pdb_residues(pdb_data: str, chain_id: str | None = None) -> list[dict[str, Any]]:
    profile = parse_pdb(pdb_data)
    return [
        {"chain_id": chain["chain_id"], "pdb_residue_no": row["residue_number"],
         "insertion_code": row.get("insertion_code"), "residue_name": row["component_id"],
         "residue_aa": _AA3TO1.get(row["component_id"], "X")}
        for chain in profile.get("chains", [])
        if not chain_id or chain["chain_id"] == chain_id
        for row in chain.get("residues", [])
    ]


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
        if source != "local_sifts_mapping":
            rows.append({
                **base,
                "source_scheme": "user_sequence",
                "source_position": uniprot_position,
                "source_coordinate": f"user_sequence:{uniprot_position}",
                "target_coordinate": f"{mapping.get('chain_id') or '_'}:{pdb_position}{mapping.get('insertion_code') or ''}",
                "mapping_basis": "assumed_user_sequence_matches_uniprot_coordinate",
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


def _global_align(query: str, target: str) -> list[tuple[int | None, int | None]]:
    """Needleman-Wunsch global alignment; returns (query_idx, target_idx) pairs (0-based)."""
    n, m = len(query), len(target)
    if n == 0 or m == 0:
        return [(i, None) for i in range(n)] if m == 0 else [(None, j) for j in range(m)]
    match, mismatch, gap = 2, -1, -2
    score = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + gap
        trace[i][0] = 1
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + gap
        trace[0][j] = 2
    for i in range(1, n + 1):
        qi = query[i - 1]
        row, prev = score[i], score[i - 1]
        for j in range(1, m + 1):
            diagonal = prev[j - 1] + (match if qi == target[j - 1] else mismatch)
            up = prev[j] + gap
            left = row[j - 1] + gap
            best = diagonal if diagonal >= up and diagonal >= left else (up if up >= left else left)
            row[j] = best
            trace[i][j] = 0 if best == diagonal else (1 if best == up else 2)
    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        direction = trace[i][j]
        if direction == 0:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif direction == 1:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    pairs.reverse()
    return pairs


def _alignment_identity_with_basis(
    pairs: list[tuple[int | None, int | None]], query: str, target: str
) -> tuple[float, int]:
    """Identity restricted to comparable pairs, plus the count those pairs form.

    Aligned pairs where either side is a non-identity sentinel ("X" for unknown
    structure components, or "-"/"*"/"X" on the user side) are dropped from both
    the identical numerator and the denominator: an unknown residue is not
    evidence of a substitution, so it must not depress identity, and it also
    must not be counted as a comparable site when checking the basis floor.
    """
    comparable = [
        (q, t) for q, t in pairs
        if q is not None and t is not None
        and query[q] not in _NON_IDENTITY_LETTERS
        and target[t] not in _NON_IDENTITY_LETTERS
    ]
    if not comparable:
        return 0.0, 0
    identical = sum(1 for q, t in comparable if query[q] == target[t])
    return identical / len(comparable), len(comparable)


def _alignment_identity(pairs: list[tuple[int | None, int | None]], query: str, target: str) -> float:
    return _alignment_identity_with_basis(pairs, query, target)[0]


def projection_accepted(identity: float, coverage: float, basis_count: int) -> bool:
    """The acceptance predicate for a global-alignment numbering projection."""
    return (
        identity >= MIN_ALIGNMENT_IDENTITY
        and coverage >= MIN_ALIGNMENT_COVERAGE
        and basis_count >= MIN_IDENTITY_BASIS
    )


def alignment_accepts_projection(query: str, target: str) -> bool:
    """Whether an input sequence may be used as a numbering basis for a structure chain.

    Single source of truth for the "near-identical FASTA" decision, shared by
    this tool and the plan hydration in agent_graph. Identity alone is not
    enough: an aligned fragment island can reach identity 1.0 over a handful of
    residues, so the comparable-pair floor and coverage are checked here too.
    Splitting this policy across call sites is what let a 12-residue fragment
    pass hydration while mapping refused the same pair.
    """
    left = "".join(str(query or "").split()).upper()
    right = "".join(str(target or "").split()).upper()
    if not left or not right:
        return False
    if left == right:
        return True
    if max(len(left), len(right)) > 5000:
        return False
    pairs = _global_align(left, right)
    identity, basis_count = _alignment_identity_with_basis(pairs, left, right)
    mapped = sum(1 for q, t in pairs if q is not None and t is not None)
    return projection_accepted(identity, mapped / len(left), basis_count)


def _constant_numbering_offset(mappings: list[dict[str, Any]]) -> int | None:
    """Author number minus input-sequence position, when it is one number everywhere.

    A construct that lost an N-terminal fragment to missing electron density is
    the common case: every mapped residue shifts by the same amount, and the user
    otherwise has to work out "+3" by hand. That conclusion is only safe when the
    whole mapping sits on one chain, no residue carries an insertion code (the
    arithmetic of 100A vs 100B is not a single offset), and every row yields an
    integer pair. Anything less and the right answer is "no single offset".
    """
    offsets: set[int] = set()
    chains: set[Any] = set()
    for mapping in mappings:
        if not isinstance(mapping, dict):
            return None
        if mapping.get("insertion_code"):
            return None
        user_position = _safe_int(mapping.get("user_sequence_position"))
        pdb_position = _safe_int(mapping.get("pdb_residue_no"))
        if user_position is None or pdb_position is None:
            return None
        offsets.add(pdb_position - user_position)
        chains.add(mapping.get("chain_id"))
    if len(offsets) != 1 or len(chains) != 1:
        return None
    return offsets.pop()


def _chain_residues(residues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group coordinate residues by chain, keeping file order within a chain."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for residue in residues:
        grouped.setdefault(str(residue.get("chain_id") or ""), []).append(residue)
    return grouped


def _select_matching_chain(
    residues: list[dict[str, Any]], input_sequence: str
) -> dict[str, Any]:
    """Pick the chain whose residues are the input sequence's numbering basis.

    Without an explicit chain the tool used to concatenate every protein chain
    and align the FASTA against the join. A homodimer then burned its coverage
    budget on the duplicate, and a complex with a short chain could clear the
    coverage floor while producing cross-chain consecutive numbering. Choose a
    chain the same way hydration does — by aligning against that chain — and
    report the choice so the caller can show it.
    """
    grouped = _chain_residues(residues)
    # Acceptance goes through the same gate as every other projection, so this
    # selects exactly the chains residue_mapping_sifts would accept below.
    candidates: list[tuple[str, str, list[dict[str, Any]]]] = []
    for chain_id, chain_residues in grouped.items():
        chain_sequence = "".join(str(item.get("residue_aa") or "X") for item in chain_residues)
        if chain_sequence:
            candidates.append((chain_id, chain_sequence, chain_residues))
    accepted = [
        item for item in candidates if alignment_accepts_projection(input_sequence, item[1])
    ]
    if len(accepted) > 1:
        # A homodimer's chains are interchangeable only if they produce the same
        # numbering; two different author frames for one FASTA must not be guessed.
        signatures = {
            tuple(residue.get("pdb_residue_no") for residue in chain_residues)
            for _, _, chain_residues in accepted
        }
        if len(signatures) > 1:
            return {
                "status": "ambiguous",
                "candidates": sorted(item[0] for item in accepted),
            }
        return {"status": "selected", "chain_id": accepted[0][0], "shared_numbering": True}
    if len(accepted) == 1:
        return {"status": "selected", "chain_id": accepted[0][0], "shared_numbering": False}
    return {"status": "unmatched"}


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
    elif source == "input_sequence_global_alignment":
        payload.setdefault("capability_status", "aligned_user_sequence_mapping")
        payload.setdefault("evidence_level", "GLOBAL_ALIGNMENT_MAPPING")
        boundary = (
            "该映射由输入 FASTA 与所选 PDB 蛋白链坐标序列的全局比对推导，属于编号投影证据，"
            "不是序列同一性判定；突变位点必须使用输入序列编号报告，结构 author 编号只作括注；"
            "低一致性或结构分歧区域不得作为下单编号依据。"
        )
        sequence_match = payload.get("sequence_match") or {}
        identity = sequence_match.get("identity")
        coverage = sequence_match.get("coverage")
        if isinstance(identity, (int, float)) and isinstance(coverage, (int, float)):
            boundary += (
                f"本次比对一致性 {identity * 100:.2f}%，"
                f"输入序列覆盖结构坐标 {coverage * 100:.2f}%。"
            )
        basis_count = sequence_match.get("identity_basis_count")
        if isinstance(basis_count, int):
            boundary += f"可比对位点 {basis_count} 个（结构未知残基不计入）。"
        numbering_offset = payload.get("numbering_offset")
        if isinstance(numbering_offset, int):
            if numbering_offset == 0:
                boundary += "全部可比对位点偏移一致：结构编号 = 输入序列编号，无需换算。"
            else:
                sign = "+" if numbering_offset > 0 else "-"
                boundary += (
                    f"全部可比对位点偏移一致：结构编号 = 输入序列编号 {sign} {abs(numbering_offset)}"
                    f"（输入位点 {numbering_offset:+d} 得到结构编号）。"
                )
        substitutions = payload.get("sequence_substitutions") or []
        if substitutions:
            details = "、".join(
                f"{item.get('user_sequence_position') or item.get('pdb_residue_no')}"
                f"{item.get('pdb_residue_aa') or 'X'}"
                f">{item.get('user_residue_aa') or 'X'}"
                for item in substitutions
                if isinstance(item, dict)
            )
            if details:
                boundary += f"输入序列与结构存在 {len(substitutions)} 处差异：{details}。"
        payload.setdefault("report_boundary", boundary)
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

    if pdb_data.lstrip().startswith("data_"):
        try:
            parse_pdb(pdb_data)
        except Exception as exc:
            return _with_report_contract({
                "found": False,
                "status": "failed",
                "error_code": "MMCIF_PARSE_FAILED",
                "error": str(exc),
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
        coordinate_rows = {
            (row["chain_id"], row["pdb_residue_no"], row.get("insertion_code")): row
            for row in _iter_pdb_residues(pdb_data, chain_filter)
        }
        for mapping in local_mappings:
            coordinate = coordinate_rows.get(
                (mapping["chain_id"], mapping["pdb_residue_no"], mapping.get("insertion_code"))
            )
            if coordinate is None or (
                mapping.get("residue_aa") not in {None, "", "X"}
                and coordinate.get("residue_aa") != mapping.get("residue_aa")
            ):
                return _with_report_contract({
                    "found": False,
                    "status": "blocked",
                    "error_code": "LOCAL_MAPPING_COORDINATE_MISMATCH",
                    "error": "Local residue mapping does not match the uploaded coordinate residue.",
                    "numbering_registry_rows": [],
                    "mappings": [],
                })
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
            "numbering_registry_status": (
                "ready" if input_sequence else "uniprot_only_requires_input_alignment"
            ),
            "coordinate_systems": ["uniprot", "pdb_author"],
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
    # Chain selection runs only when the caller did not name a chain. Concatenating
    # every chain and aligning the FASTA against the join produced cross-chain
    # numbering that still claimed mapping_scope="chain".
    chain_selection: dict[str, Any] | None = None
    if normalized_input_sequence and chain_filter is None:
        chain_selection = _select_matching_chain(residues, normalized_input_sequence)
        if chain_selection.get("status") == "selected":
            selected_chain = chain_selection["chain_id"]
            chain_filter = selected_chain
            residues = _iter_pdb_residues(pdb_data, selected_chain)
        elif chain_selection.get("status") == "ambiguous":
            candidate_names = "、".join(chain_selection.get("candidates") or [])
            return _with_report_contract({
                "found": False,
                "status": "blocked",
                "error_code": "AMBIGUOUS_CHAIN_MATCH",
                "error": (
                    "The input sequence matches more than one PDB chain with different "
                    "author numbering. Specify chain_id before using these coordinates."
                ),
                "capability_status": "chain_selection_required",
                "evidence_level": "NUMBERING_QC",
                "report_boundary": (
                    f"输入序列与 {candidate_names} 多条 PDB 链均可比对，但这些链的 author 编号不同，"
                    "自动选链会改变报告的位点编号；请先指定 chain_id，本次不给出映射。"
                ),
                "ambiguous_chains": chain_selection.get("candidates", []),
                "mapping_count": 0,
                "mappings": [],
                "numbering_registry_rows": [],
                "numbering_registry_status": "blocked",
            })
    coordinate_sequence = "".join(str(item.get("residue_aa") or "X") for item in residues)
    if normalized_input_sequence and normalized_input_sequence == coordinate_sequence:
        mappings = [
            {
                **residue,
                "user_sequence_position": idx,
                "coordinate_sequence_position": idx,
                "uniprot_id": None,
                "uniprot_position": None,
                "mapping_confidence": "exact_input_sequence_match",
            }
            for idx, residue in enumerate(residues, start=1)
        ]
        registry_rows = []
        for mapping in mappings:
            registry_rows.append({
                "source_scheme": "coordinate_sequence",
                "source_position": mapping["user_sequence_position"],
                "source_coordinate": f"coordinate_sequence:{mapping['user_sequence_position']}",
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
            "chain_selection": chain_selection,
            "mapping_count": len(mappings),
            "mappings": mappings,
            "numbering_registry_rows": registry_rows,
            "numbering_registry_status": "ready",
                "coordinate_systems": ["coordinate_sequence", "pdb_author"],
            "sequence_match": {"status": "exact", "length": len(mappings)},
            "limitations": ["No UniProt coordinate mapping was established."],
        })

    if normalized_input_sequence:
        # A near-identical input sequence (signal-peptide truncation, a point
        # substitution, or a few missing termini) is still a usable numbering
        # basis; only refuse when alignment identity cannot support one-to-one
        # projection.
        pairs = _global_align(normalized_input_sequence, coordinate_sequence)
        identity, identity_basis_count = _alignment_identity_with_basis(
            pairs, normalized_input_sequence, coordinate_sequence
        )
        mapped_input_positions = [q + 1 for q, t in pairs if q is not None and t is not None]
        coverage = len(mapped_input_positions) / len(normalized_input_sequence)
        if projection_accepted(identity, coverage, identity_basis_count):
            mappings: list[dict[str, Any]] = []
            registry_rows: list[dict[str, Any]] = []
            substitutions: list[dict[str, Any]] = []
            for q, t in pairs:
                if q is None or t is None:
                    continue
                residue = residues[t]
                user_position = q + 1
                user_aa = normalized_input_sequence[q]
                structure_aa = str(residue.get("residue_aa") or "X")
                # Unknown/ambiguous residues are not substitutions: the identity
                # ratio excludes these pairs, so the substitution list must not
                # report them either.
                if (
                    user_aa != structure_aa
                    and user_aa not in _NON_IDENTITY_LETTERS
                    and structure_aa not in _NON_IDENTITY_LETTERS
                ):
                    substitutions.append({
                        "user_sequence_position": user_position,
                        "user_residue_aa": user_aa,
                        "pdb_residue_no": residue.get("pdb_residue_no"),
                        "pdb_residue_aa": structure_aa,
                    })
                mappings.append({
                    **residue,
                    "user_sequence_position": user_position,
                    "coordinate_sequence_position": t + 1,
                    "uniprot_id": None,
                    "uniprot_position": None,
                    "mapping_confidence": "high_alignment",
                })
                registry_rows.append({
                    "source_scheme": "user_sequence",
                    "source_position": user_position,
                    "source_coordinate": f"user_sequence:{user_position}",
                    "source_residue_aa": user_aa,
                    "target_scheme": "pdb_author",
                    "target_position": residue.get("pdb_residue_no"),
                    "target_chain_id": residue.get("chain_id"),
                    "target_insertion_code": residue.get("insertion_code"),
                    "target_residue_aa": structure_aa,
                    "target_coordinate": f"{residue.get('chain_id')}:{residue.get('pdb_residue_no')}{residue.get('insertion_code') or ''}",
                    "pdb_id": pdb_id or None,
                    "uniprot_id": None,
                    "coordinate_system": "pdb_author_residue_number",
                    "mapping_scope": "chain",
                    "gap_status": "present",
                    "has_gap": False,
                    "missing_in_structure": False,
                    "confidence": "high",
                    "method": "global_alignment",
                    "source": "input_sequence_global_alignment",
                    "mapping_basis": f"global_alignment_identity_{identity:.4f}",
                })
            mapped_position_set = set(mapped_input_positions)
            unmapped_input_positions = [
                position for position in range(1, len(normalized_input_sequence) + 1)
                if position not in mapped_position_set
            ]
            numbering_offset = _constant_numbering_offset(mappings)
            return _with_report_contract({
                "found": True,
                "status": "completed",
                "source": "input_sequence_global_alignment",
                "pdb_id": pdb_id or None,
                "uniprot_id": None,
                "chain_id": chain_filter,
                "chain_selection": chain_selection,
                "mapping_count": len(mappings),
                "mappings": mappings,
                "numbering_registry_rows": registry_rows,
                "numbering_registry_status": "ready",
                "coordinate_systems": ["user_sequence", "pdb_author"],
                "numbering_offset": numbering_offset,
                "sequence_match": {
                    "status": "aligned",
                    "identity": round(identity, 4),
                    "coverage": round(coverage, 4),
                    "identity_basis_count": identity_basis_count,
                    "input_length": len(normalized_input_sequence),
                    "coordinate_length": len(coordinate_sequence),
                },
                "sequence_substitutions": substitutions,
                "unmapped_input_positions": unmapped_input_positions,
                "numbering_contract": {
                    "canonical_scheme": "user_sequence",
                    "projection_scheme": "pdb_author",
                    "report_hint": "报告中的突变位点必须使用输入序列绝对编号；结构坐标编号只作括注。",
                },
                "limitations": ["No UniProt coordinate mapping was established."],
            })
        # Distinguish "the sequences genuinely differ" from "there were too few
        # comparable residues to judge": both are blocked, but the caller must
        # not read a sparse-comparison refusal as evidence of a sequence mismatch.
        if identity_basis_count < MIN_IDENTITY_BASIS:
            error_message = (
                f"Only {identity_basis_count} comparable aligned residues "
                f"(minimum {MIN_IDENTITY_BASIS}); the structure"
                " sequence has too few standard residues overlapping the input"
                " sequence to establish a numbering projection."
            )
        else:
            error_message = "Input sequence does not match the selected PDB coordinate sequence."
        return _with_report_contract({
            "found": False,
            "status": "blocked",
            "error_code": "INPUT_SEQUENCE_MISMATCH",
            "error": error_message,
            "alignment": {
                "identity": round(identity, 4),
                "coverage": round(coverage, 4),
                "identity_basis_count": identity_basis_count,
            },
            "mapping_count": 0,
            "mappings": [],
            "numbering_registry_rows": [],
            "numbering_registry_status": "blocked",
        })

    mappings = []
    for idx, residue in enumerate(residues):
        mappings.append(
            {
                **residue,
                "coordinate_sequence_position": idx + 1,
                "uniprot_id": None,
                "uniprot_position": None,
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
    inferred_registry_rows = [
        {
            "source_scheme": "coordinate_sequence",
            "source_position": mapping["coordinate_sequence_position"],
            "source_coordinate": f"coordinate_sequence:{mapping['coordinate_sequence_position']}",
            "target_scheme": "pdb_author",
            "target_position": mapping["pdb_residue_no"],
            "target_chain_id": mapping["chain_id"],
            "target_insertion_code": mapping.get("insertion_code"),
            "target_residue_aa": mapping["residue_aa"],
            "coordinate_system": "pdb_author_residue_number",
            "mapping_scope": "chain",
            "gap_status": "present",
            "has_gap": False,
            "missing_in_structure": False,
            "confidence": "inferred",
            "method": "coordinate_order_inference",
            "source": "local_sifts_style_inference",
            "mapping_basis": f"coordinate_order_uniprot_start_{start}",
        }
        for mapping in mappings
    ]
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
        "numbering_registry_rows": inferred_registry_rows,
        "numbering_registry_status": "inferred_requires_confirmation",
            "coordinate_systems": ["coordinate_sequence", "pdb_author"],
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
