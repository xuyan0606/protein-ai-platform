#!/usr/bin/env python3
"""Parse FoldX BuildModel outputs into the local ddG table contract."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


FOLDX_OUTPUT_GLOBS = {
    "difference": ("Dif_*", "Dif_*.fxout", "Dif_*.txt"),
    "average": ("Average_*", "Average_*.fxout", "Average_*.txt"),
    "raw": ("Raw_*", "Raw_*.fxout", "Raw_*.txt"),
}


def _normal(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _split(line: str) -> list[str]:
    if "\t" in line:
        return [part.strip() for part in line.rstrip("\n").split("\t")]
    return line.strip().split()


def _find_total_energy_index(header: list[str]) -> int | None:
    normalized = [_normal(item) for item in header]
    for target in ("total energy", "total"):
        if target in normalized:
            return normalized.index(target)
    for index, item in enumerate(normalized):
        if item in {"energy", "ddg", "delta g", "delta delta g"}:
            return index
    return None


def _as_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_energy_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse a FoldX table-like output file.

    FoldX BuildModel reports are whitespace/tabular files. The canonical
    stability value is normally in the `total energy` column of `Dif_*`.
    """

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists() or not path.is_file():
        return rows, [f"missing_file:{path}"]

    header: list[str] | None = None
    total_index: int | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = _split(stripped)
        if not parts:
            continue
        if header is None:
            candidate_index = _find_total_energy_index(parts)
            if candidate_index is not None:
                header = parts
                total_index = candidate_index
                continue
            if len(parts) == 2 and _as_float(parts[1]) is not None:
                header = ["model", "total energy"]
                total_index = 1
            else:
                # FoldX writes a fixed banner and metadata before the table header.
                # Ignore that preamble; malformed rows after a real header remain errors.
                continue
        if total_index is None or total_index >= len(parts):
            errors.append(f"row_missing_total_energy:{path.name}:{line_number}")
            continue
        total = _as_float(parts[total_index])
        if total is None:
            errors.append(f"row_total_energy_not_numeric:{path.name}:{line_number}")
            continue
        row = {
            "source_file": str(path),
            "line_number": line_number,
            "model": parts[0],
            "total_energy_kcal_mol": total,
        }
        if header and len(header) == len(parts):
            row["raw_columns"] = dict(zip(header, parts))
        rows.append(row)
    if not rows and not errors:
        errors.append(f"no_parseable_rows:{path.name}")
    return rows, errors


def _unique_files(output_dir: Path, patterns: tuple[str, ...]) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in patterns:
        for path in sorted(output_dir.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                files.append(path)
    return files


def parse_buildmodel_output(output_dir: Path, mutation_context: dict[str, Any] | None = None) -> dict[str, Any]:
    mutation_context = mutation_context or {}
    parsed: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    for family, patterns in FOLDX_OUTPUT_GLOBS.items():
        family_rows: list[dict[str, Any]] = []
        for path in _unique_files(output_dir, patterns):
            rows, row_errors = parse_energy_rows(path)
            family_rows.extend(rows)
            errors.extend(row_errors)
        parsed[family] = family_rows

    primary_rows = parsed.get("difference") or parsed.get("average") or []
    table_rows: list[dict[str, Any]] = []
    for row in primary_rows:
        table_rows.append({
            "chain_id": mutation_context.get("chain_id"),
            "pdb_position": mutation_context.get("pdb_position"),
            "wild_type": mutation_context.get("wild_type"),
            "mutant": mutation_context.get("mutant"),
            "foldx_model": row.get("model"),
            "ddg_kcal_mol": row.get("total_energy_kcal_mol"),
            "negative_ddg_is_stabilizing": True,
            "source_file": row.get("source_file"),
            "source_line_number": row.get("line_number"),
        })

    parse_status = "parsed" if table_rows else "blocked_no_parseable_foldx_ddg"
    return {
        "backend": "foldx",
        "protocol": "BuildModel",
        "parse_status": parse_status,
        "unit": "kcal/mol",
        "negative_ddg_is_stabilizing": True,
        "rows": table_rows,
        "source_family_counts": {key: len(value) for key, value in parsed.items()},
        "parse_errors": errors,
        "policy": "FoldX BuildModel parser only. Parsed kcal/mol ddG is computational evidence, not a wet-lab label or training-import approval.",
    }


def write_ddg_table(output_dir: Path, mutation_context: dict[str, Any] | None = None) -> dict[str, Any]:
    table = parse_buildmodel_output(output_dir, mutation_context)
    (output_dir / "ddg_table.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return table
