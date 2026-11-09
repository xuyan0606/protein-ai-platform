"""Rosetta ΔΔG mutation stability tool contract.

This tool is conservative: it only reports real Rosetta ΔΔG when a Rosetta
runtime is configured. If Rosetta is unavailable, it returns a blocked contract.
Callers may explicitly enable a local heuristic estimate for triage, but that
result is labelled as non-Rosetta evidence.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services import storage
from app.tools.registry import ToolRegistry

_AA_LIST = set("ACDEFGHIKLMNPQRSTVWY")
_MUTATION_RE = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([0-9]{1,5})([ACDEFGHIKLMNPQRSTVWY])$", re.IGNORECASE)
_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _resolve_rosetta_binary() -> str | None:
    configured = os.getenv("ROSETTA_CARTESIAN_DDG") or os.getenv("ROSETTA_DDG_BINARY")
    if configured and Path(configured).exists():
        return configured
    for candidate in (
        "cartesian_ddg",
        "cartesian_ddg.default.linuxgccrelease",
        "cartesian_ddg.mpi.linuxgccrelease",
        "rosetta_scripts",
        "rosetta_scripts.default.linuxgccrelease",
    ):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _parse_mutations(mutations: list[str]) -> list[dict[str, Any]]:
    parsed = []
    for raw in mutations:
        mutation = str(raw or "").strip().upper()
        match = _MUTATION_RE.match(mutation)
        if not match:
            raise ValueError(f"INVALID_MUTATION: {raw!r}; expected format A123G")
        wt, pos, mt = match.groups()
        parsed.append({"mutation": mutation, "wild_type": wt, "position": int(pos), "mutant": mt})
    return parsed


def _validate_sequence(sequence: str, parsed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seq = (sequence or "").strip().upper()
    if not seq:
        return []
    invalid = sorted(set(seq) - _AA_LIST)
    if invalid:
        raise ValueError(f"INVALID_AA: sequence contains non-standard amino acids: {''.join(invalid)}")
    errors = []
    for item in parsed:
        pos = item["position"]
        if pos < 1 or pos > len(seq):
            errors.append({
                "mutation": item["mutation"],
                "error": f"Position {pos} is outside sequence range 1..{len(seq)}",
            })
            continue
        observed = seq[pos - 1]
        if observed != item["wild_type"]:
            errors.append({
                "mutation": item["mutation"],
                "error": f"Wild-type residue mismatch at {pos}: expected {item['wild_type']}, sequence has {observed}",
            })
    return errors


def _parse_pdb_residue_map(pdb_text: str, chain_id: str) -> dict[int, str]:
    chain = (chain_id or "A").strip()[:1]
    residues: dict[int, str] = {}
    for line in (pdb_text or "").splitlines():
        if not line.startswith(("ATOM", "HETATM")) or len(line) < 26:
            continue
        if line[21:22].strip() != chain:
            continue
        resname = line[17:20].strip().upper()
        try:
            resseq = int(line[22:26].strip())
        except ValueError:
            continue
        aa = _THREE_TO_ONE.get(resname)
        if aa and resseq not in residues:
            residues[resseq] = aa
    return residues


def _validate_pdb_mutations(
    pdb_text: str | None,
    parsed: list[dict[str, Any]],
    chain_id: str,
) -> list[dict[str, Any]]:
    if not pdb_text or not pdb_text.strip():
        return []
    residues = _parse_pdb_residue_map(pdb_text, chain_id)
    chain = (chain_id or "A").strip()[:1]
    errors: list[dict[str, Any]] = []
    if not residues:
        errors.append({
            "chain_id": chain,
            "error": f"Chain {chain!r} not found or has no standard residues in the provided PDB",
        })
        return errors
    for item in parsed:
        pos = item["position"]
        observed = residues.get(pos)
        if observed is None:
            errors.append({
                "mutation": item["mutation"],
                "error": f"Position {pos} not found in chain {chain!r} PDB residue numbering",
            })
            continue
        if observed != item["wild_type"]:
            errors.append({
                "mutation": item["mutation"],
                "error": f"PDB residue mismatch at {pos}{chain}: expected {item['wild_type']}, PDB has {observed}",
            })
    return errors


def _thresholds(
    strong_stabilizing_max: float,
    stabilizing_max: float,
    neutral_max: float,
    destabilizing_max: float,
) -> dict[str, Any]:
    return {
        "unit": "kcal/mol",
        "interpretation": "Rosetta/FoldX-style ΔΔG convention here: negative = mutant more stable than WT; positive = mutant less stable than WT.",
        "ranges": [
            {"label": "strong_stabilizing", "max_inclusive": strong_stabilizing_max, "meaning": "strong candidate, but still requires manual structural review"},
            {"label": "stabilizing", "min_exclusive": strong_stabilizing_max, "max_inclusive": stabilizing_max, "meaning": "likely stabilizing"},
            {"label": "neutral_or_uncertain", "min_exclusive": stabilizing_max, "max_inclusive": neutral_max, "meaning": "small effect; do not over-interpret"},
            {"label": "destabilizing", "min_exclusive": neutral_max, "max_inclusive": destabilizing_max, "meaning": "likely destabilizing"},
            {"label": "strong_destabilizing", "min_exclusive": destabilizing_max, "meaning": "high risk"},
        ],
    }


def _classify_ddg(
    ddg: float,
    strong_stabilizing_max: float,
    stabilizing_max: float,
    neutral_max: float,
    destabilizing_max: float,
) -> str:
    if ddg <= strong_stabilizing_max:
        return "strong_stabilizing"
    if ddg <= stabilizing_max:
        return "stabilizing"
    if ddg <= neutral_max:
        return "neutral_or_uncertain"
    if ddg <= destabilizing_max:
        return "destabilizing"
    return "strong_destabilizing"


def _manual_review_flags(item: dict[str, Any], ddg_label: str) -> list[str]:
    flags = ["confirm residue numbering against user sequence/PDB/UniProt before wet-lab design"]
    if ddg_label in {"strong_stabilizing", "stabilizing"}:
        flags.append("manually inspect local packing, clashes, active-site distance, and conserved motif overlap before promotion")
    if ddg_label in {"destabilizing", "strong_destabilizing"}:
        flags.append("treat as watch/no-go unless activity or specificity mechanism justifies destabilization")
    if item["wild_type"] in {"D", "E", "H", "C", "S", "K", "R"} or item["mutant"] in {"D", "E", "H", "C", "S", "K", "R"}:
        flags.append("review catalytic, protonation, disulfide, metal-binding, and pH effects")
    return flags


def _is_float_token(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _parse_scorefile(scorefile_text: str) -> list[dict[str, Any]]:
    header: list[str] | None = None
    rows: list[dict[str, Any]] = []
    for raw_line in (scorefile_text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("SCORE:"):
            continue
        parts = line.split()
        payload = parts[1:]
        if not payload:
            continue
        if not _is_float_token(payload[0]):
            header = payload
            continue
        if header:
            row: dict[str, Any] = {}
            width = min(len(header), len(payload))
            for idx in range(width):
                key = header[idx]
                value = payload[idx]
                if key == "description":
                    row[key] = " ".join(payload[idx:]) if idx < len(payload) else ""
                    break
                try:
                    row[key] = float(value)
                except ValueError:
                    row[key] = value
            rows.append(row)
            continue
        row = {"values": payload}
        rows.append(row)
    return rows


def _extract_row_metric(row: dict[str, Any]) -> tuple[float | None, str | None]:
    for key in ("ddg", "dG", "delta_delta_g", "deltaG", "total_score", "I_sc", "score"):
        for candidate in (key, key.lower(), key.upper()):
            value = row.get(candidate)
            if isinstance(value, (int, float)):
                return float(value), candidate
    return None, None


def _build_real_rosetta_results(
    score_rows: list[dict[str, Any]],
    requested_mutations: list[str],
    strong_stabilizing_max: float,
    stabilizing_max: float,
    neutral_max: float,
    destabilizing_max: float,
) -> tuple[list[dict[str, Any]], str | None]:
    matched: list[dict[str, Any]] = []
    used_rows: set[int] = set()
    for mutation in requested_mutations:
        row_idx = None
        for idx, row in enumerate(score_rows):
            description = str(row.get("description") or row.get("mutant") or row.get("mutation") or row.get("label") or "")
            if mutation in description:
                row_idx = idx
                break
        if row_idx is None and len(requested_mutations) == 1 and len(score_rows) == 1:
            row_idx = 0
        if row_idx is None:
            continue
        row = score_rows[row_idx]
        used_rows.add(row_idx)
        ddg, metric_name = _extract_row_metric(row)
        if ddg is None:
            continue
        label = _classify_ddg(ddg, strong_stabilizing_max, stabilizing_max, neutral_max, destabilizing_max)
        item = {
            "mutation": mutation,
            "ddg_kcal_mol": ddg,
            "ddg_label": label,
            "manual_review_flags": [
                "confirm residue numbering against user sequence/PDB/UniProt before wet-lab design",
                "manual inspect Rosetta scorefile context before promoting candidates",
            ],
            "scorefile_row": row,
            "score_metric": metric_name,
        }
        item["manual_review_flags"] = _manual_review_flags({
            "wild_type": mutation[0],
            "mutant": mutation[-1],
        }, label) + ["manual inspect Rosetta scorefile context before promoting candidates"]
        matched.append(item)
    return matched, None if matched else "SCOREFILE_PARSE_UNRESOLVED"


def _local_estimate(sequence: str, parsed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.tools.mutation_scan import _predict_ddg

    results = []
    for item in parsed:
        ddg = _predict_ddg(item["wild_type"], item["mutant"])
        results.append({**item, "ddg_kcal_mol": ddg})
    return results


async def _load_pdb_text(
    pdb_data: str | None,
    pdb_object_name: str | None,
    pdb_path: str | None,
) -> tuple[str | None, dict[str, Any]]:
    if pdb_data and pdb_data.strip():
        return pdb_data, {"input_type": "pdb_data", "size_bytes": len(pdb_data.encode("utf-8"))}
    if pdb_object_name and pdb_object_name.strip():
        data = await storage.download_file(pdb_object_name)
        return data.decode("utf-8", errors="replace"), {
            "input_type": "pdb_object_name",
            "pdb_object_name": pdb_object_name,
            "size_bytes": len(data),
        }
    if pdb_path and pdb_path.strip():
        path = Path(pdb_path).expanduser()
        if not path.exists():
            raise ValueError(f"PDB path not found: {pdb_path}")
        return path.read_text(encoding="utf-8", errors="replace"), {
            "input_type": "pdb_path",
            "pdb_path": str(path),
            "size_bytes": path.stat().st_size,
        }
    return None, {"input_type": "none"}


def _write_rosetta_mutfile(path: Path, parsed: list[dict[str, Any]], chain_id: str) -> None:
    lines = [f"total {len(parsed)}"]
    for item in parsed:
        lines.append("1")
        lines.append(f"{item['wild_type']} {item['position']} {item['mutant']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_rosetta_ddg(
    *,
    rosetta_binary: str,
    pdb_text: str,
    parsed: list[dict[str, Any]],
    chain_id: str,
    timeout_seconds: int,
    iterations: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rosetta-ddg-") as tmp:
        workdir = Path(tmp)
        pdb_file = workdir / "input.pdb"
        mut_file = workdir / "mutations.mutfile"
        score_file = workdir / "ddg.sc"
        pdb_file.write_text(pdb_text, encoding="utf-8")
        _write_rosetta_mutfile(mut_file, parsed, chain_id)

        command = [
            rosetta_binary,
            "-s",
            str(pdb_file),
            "-ddg::mut_file",
            str(mut_file),
            "-ddg::iterations",
            str(max(1, min(int(iterations), 50))),
            "-ddg::dump_pdbs",
            "false",
            "-out:file:scorefile",
            str(score_file),
        ]
        proc = subprocess.run(
            command,
            cwd=str(workdir),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "returncode": proc.returncode,
            "command": command,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
            "scorefile_exists": score_file.exists(),
            "scorefile_preview": score_file.read_text(encoding="utf-8", errors="replace")[:4000] if score_file.exists() else "",
        }


async def rosetta_ddg(
    mutations: list[str],
    sequence: str = "",
    pdb_data: str | None = None,
    pdb_object_name: str | None = None,
    pdb_path: str | None = None,
    chain_id: str = "A",
    strong_stabilizing_max: float = -2.0,
    stabilizing_max: float = -1.0,
    neutral_max: float = 1.0,
    destabilizing_max: float = 2.0,
    allow_local_estimate: bool = False,
    run_real_rosetta: bool = True,
    iterations: int = 3,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Calculate mutation ΔΔG with Rosetta when runtime is available."""
    parsed = _parse_mutations(mutations)
    sequence_errors = _validate_sequence(sequence, parsed)
    threshold_table = _thresholds(strong_stabilizing_max, stabilizing_max, neutral_max, destabilizing_max)
    rosetta_binary = _resolve_rosetta_binary()
    pdb_text, pdb_input = await _load_pdb_text(pdb_data, pdb_object_name, pdb_path)

    base = {
        "tool": "rosetta_ddg",
        "requested_mutations": [item["mutation"] for item in parsed],
        "thresholds": threshold_table,
        "manual_review_required": True,
        "chain_id": (chain_id or "A").strip()[:1],
        "manual_review_checklist": [
            "confirm residue numbering and chain mapping",
            "check catalytic residues, metal/cofactor binding, disulfides, signal/pro-peptide offsets",
            "inspect Rosetta/FoldX/MD agreement before promoting candidates",
            "validate top candidates experimentally with expression, soluble yield, activity, Tm/DSF, and SEC/aggregation checks",
        ],
        "runtime": {
            "rosetta_binary": rosetta_binary,
            "available": bool(rosetta_binary),
            "env_vars": ["ROSETTA_CARTESIAN_DDG", "ROSETTA_DDG_BINARY"],
        },
        "pdb_input": pdb_input,
        "sequence_validation_errors": sequence_errors,
        "pdb_validation_errors": _validate_pdb_mutations(pdb_text, parsed, chain_id) if pdb_text else [],
    }

    if sequence_errors or base["pdb_validation_errors"]:
        return {
            **base,
            "status": "blocked",
            "reason": "SEQUENCE_OR_PDB_MUTATION_MISMATCH",
            "recovery": "Fix mutation numbering or provide the sequence/PDB numbering map before ddG calculation.",
        }

    if run_real_rosetta and rosetta_binary and pdb_text:
        try:
            execution = _run_rosetta_ddg(
                rosetta_binary=rosetta_binary,
                pdb_text=pdb_text,
                parsed=parsed,
                chain_id=chain_id,
                timeout_seconds=timeout_seconds,
                iterations=iterations,
            )
        except subprocess.TimeoutExpired:
            return {
                **base,
                "status": "blocked",
                "reason": "ROSETTA_TIMEOUT",
                "recovery": "Reduce mutation batch size or increase timeout_seconds.",
            }
        if execution["returncode"] != 0:
            return {
                **base,
                "status": "blocked",
                "reason": "ROSETTA_EXECUTION_FAILED",
                "execution": execution,
                "recovery": "Review Rosetta stderr, PDB cleanup, mutation file format, and Rosetta database configuration.",
            }
        return {
            **base,
            "status": "completed",
            "is_real_rosetta": True,
            "execution": execution,
            "results": _build_real_rosetta_results(
                _parse_scorefile(execution.get("scorefile_preview", "")),
                base["requested_mutations"],
                strong_stabilizing_max,
                stabilizing_max,
                neutral_max,
                destabilizing_max,
            )[0],
            "scorefile_rows": _parse_scorefile(execution.get("scorefile_preview", "")),
            "note": "Rosetta execution completed; scorefile was parsed conservatively and still requires manual review.",
        }

    if allow_local_estimate:
        estimated = []
        for item in _local_estimate(sequence, parsed):
            ddg = float(item["ddg_kcal_mol"])
            label = _classify_ddg(ddg, strong_stabilizing_max, stabilizing_max, neutral_max, destabilizing_max)
            estimated.append({
                **item,
                "ddg_label": label,
                "manual_review_flags": _manual_review_flags(item, label),
            })
        return {
            **base,
            "status": "completed",
            "is_real_rosetta": False,
            "evidence_level": "local_heuristic_estimate",
            "results": estimated,
            "note": "This is a non-Rosetta local FoldX-style triage estimate because allow_local_estimate=true.",
        }

    missing = []
    if not rosetta_binary:
        missing.append("Rosetta cartesian_ddg/rosetta_scripts executable")
    if not pdb_text:
        missing.append("PDB structure input")
    return {
        **base,
        "status": "blocked",
        "reason": "ROSETTA_RUNTIME_OR_STRUCTURE_UNAVAILABLE",
        "missing": missing,
        "recovery": (
            "Configure ROSETTA_CARTESIAN_DDG or ROSETTA_DDG_BINARY and provide pdb_data/"
            "pdb_object_name/pdb_path. For quick non-Rosetta triage, call this tool with "
            "allow_local_estimate=true and provide sequence."
        ),
    }


ToolRegistry.register(
    name="rosetta_ddg",
    description=(
        "Rosetta ΔΔG mutation stability calculation contract. Given mutations such as A123G, "
        "runs real Rosetta cartesian_ddg when a Rosetta executable and PDB are available. "
        "Negative ΔΔG means predicted stabilization; positive ΔΔG means predicted destabilization. "
        "If Rosetta is unavailable, returns a structured blocked result unless allow_local_estimate=true."
    ),
    handler=rosetta_ddg,
    category="engineering",
    timeout_seconds=1200,
    parameters={
        "type": "object",
        "properties": {
            "mutations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Mutation codes in WT-position-mutant format, e.g. A123G.",
            },
            "sequence": {
                "type": "string",
                "description": "Optional WT sequence for numbering/residue validation and local estimate fallback.",
                "default": "",
            },
            "pdb_data": {"type": "string", "description": "Optional PDB text."},
            "pdb_object_name": {"type": "string", "description": "Optional uploaded PDB object name."},
            "pdb_path": {"type": "string", "description": "Optional local PDB path for trusted backend/runtime use."},
            "chain_id": {"type": "string", "description": "PDB chain ID for mutation mapping.", "default": "A"},
            "strong_stabilizing_max": {"type": "number", "default": -2.0},
            "stabilizing_max": {"type": "number", "default": -1.0},
            "neutral_max": {"type": "number", "default": 1.0},
            "destabilizing_max": {"type": "number", "default": 2.0},
            "allow_local_estimate": {
                "type": "boolean",
                "description": "If true, return a clearly labelled local heuristic estimate when Rosetta cannot run.",
                "default": False,
            },
            "run_real_rosetta": {"type": "boolean", "default": True},
            "iterations": {"type": "integer", "default": 3},
            "timeout_seconds": {"type": "integer", "default": 900},
        },
        "required": ["mutations"],
    },
    errors=[
        {
            "reason": "validation_failed",
            "code": "INVALID_MUTATION",
            "when": "mutation code does not match A123G",
            "recovery": "Provide mutations using WT-position-mutant format, e.g. A123G.",
        },
        {
            "reason": "validation_failed",
            "code": "SEQUENCE_MUTATION_MISMATCH",
            "when": "sequence residue does not match requested WT residue",
            "recovery": "Confirm numbering and WT sequence before running ddG.",
        },
        {
            "reason": "compute_error",
            "code": "ROSETTA_RUNTIME_OR_STRUCTURE_UNAVAILABLE",
            "when": "Rosetta executable or PDB structure is missing",
            "recovery": "Configure Rosetta and provide PDB input, or enable allow_local_estimate for triage.",
        },
    ],
)
