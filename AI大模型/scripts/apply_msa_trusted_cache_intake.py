#!/usr/bin/env python3
"""Apply trusted MSA/conservation cache intake rows to the cache manifest.

This does not run homology search or generate conservation. It only accepts
precomputed local files with source metadata and checksums, then leaves final
file/content validation to validate_msa_conservation_cache.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TARGETS = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
INTAKE = AI_ROOT / "datasets" / "curation" / "msa_trusted_cache_intake.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "curation" / "msa_trusted_cache_intake.template.jsonl"
MANIFEST_OUT = AI_ROOT / "reports" / "msa_conservation_manifest.json"
REPORT_OUT = AI_ROOT / "reports" / "msa_trusted_cache_intake_report.json"
HEX_DIGITS = set("0123456789abcdefABCDEF")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha256_hex(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in HEX_DIGITS for char in text)


def build_template(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        uniprot_id = target.get("uniprot_id")
        rows.append({
            "uniprot_id": uniprot_id,
            "sequence_length": target.get("sequence_length"),
            "source": "trusted_precomputed_cache",
            "source_database": "",
            "database_version": "",
            "msa_path": f"cache/msa/{uniprot_id}.aln.fasta",
            "msa_sha256": "",
            "conservation_feature_path": f"datasets/curation/msa_conservation/{uniprot_id}.conservation.json",
            "conservation_sha256": "",
            "reviewer": "",
            "reviewed_at": "",
            "notes": "Fill only with real precomputed cache artifacts; do not use single-sequence pseudo-conservation.",
        })
    return rows


def validate_intake_row(row: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not expected:
        errors.append("uniprot_id_not_in_targets")
        return errors
    if int(row.get("sequence_length") or 0) != int(expected.get("sequence_length") or 0):
        errors.append("sequence_length_mismatch")
    for key in ["source", "source_database", "database_version", "reviewer", "reviewed_at"]:
        if not row.get(key):
            errors.append(f"{key}_missing")
    msa_path = resolve_path(row.get("msa_path"))
    conservation_path = resolve_path(row.get("conservation_feature_path"))
    if not msa_path or not msa_path.exists():
        errors.append("msa_file_missing")
    if not conservation_path or not conservation_path.exists():
        errors.append("conservation_file_missing")
    if not is_sha256_hex(row.get("msa_sha256")):
        errors.append("msa_sha256_missing_or_invalid")
    elif msa_path and msa_path.exists() and sha256(msa_path) != str(row.get("msa_sha256")).lower():
        errors.append("msa_sha256_mismatch")
    if not is_sha256_hex(row.get("conservation_sha256")):
        errors.append("conservation_sha256_missing_or_invalid")
    elif conservation_path and conservation_path.exists() and sha256(conservation_path) != str(row.get("conservation_sha256")).lower():
        errors.append("conservation_sha256_mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply trusted MSA cache intake")
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--intake", type=Path, default=INTAKE)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    targets = load_jsonl(args.targets)
    intake_rows = load_jsonl(args.intake)
    expected_by_id = {str(row.get("uniprot_id")): row for row in targets if row.get("uniprot_id")}

    if not args.template.exists():
        write_jsonl(args.template, build_template(targets))
    if not args.intake.exists():
        write_jsonl(args.intake, [])

    accepted_by_id: dict[str, dict[str, Any]] = {}
    rejected = []
    error_counts: Counter[str] = Counter()
    seen = set()
    for row in intake_rows:
        uniprot_id = str(row.get("uniprot_id") or "")
        errors = []
        if uniprot_id in seen:
            errors.append("duplicate_uniprot_id")
        seen.add(uniprot_id)
        errors.extend(validate_intake_row(row, expected_by_id.get(uniprot_id, {})))
        if errors:
            error_counts.update(errors)
            rejected.append({"uniprot_id": uniprot_id, "errors": errors})
            continue
        accepted_by_id[uniprot_id] = row

    manifest_targets = []
    for target in targets:
        uniprot_id = str(target.get("uniprot_id"))
        accepted = accepted_by_id.get(uniprot_id)
        if accepted:
            manifest_targets.append({
                "uniprot_id": uniprot_id,
                "sequence_length": int(target.get("sequence_length") or accepted.get("sequence_length") or 0),
                "msa_path": accepted.get("msa_path"),
                "msa_sha256": str(accepted.get("msa_sha256")).lower(),
                "conservation_feature_path": accepted.get("conservation_feature_path"),
                "conservation_sha256": str(accepted.get("conservation_sha256")).lower(),
                "status": "present",
            })
        else:
            manifest_targets.append({
                "uniprot_id": uniprot_id,
                "sequence_length": target.get("sequence_length"),
                "msa_path": None,
                "conservation_feature_path": None,
                "status": "missing",
            })

    source_values = sorted({str(row.get("source")) for row in accepted_by_id.values() if row.get("source")})
    source_database_values = sorted({str(row.get("source_database")) for row in accepted_by_id.values() if row.get("source_database")})
    database_version_values = sorted({str(row.get("database_version")) for row in accepted_by_id.values() if row.get("database_version")})
    ready = bool(targets) and len(accepted_by_id) == len(targets) and not rejected
    manifest = {
        "local_only": True,
        "status": "ready" if ready else "not_configured",
        "source": ",".join(source_values) if source_values else "not_configured",
        "source_database": ",".join(source_database_values),
        "database_version": ",".join(database_version_values),
        "targets": manifest_targets,
        "policy": "Trusted cache manifest is assembled only from real local files and checksums; final validator must pass before use.",
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "target_rows": len(targets),
        "intake_rows": len(intake_rows),
        "accepted_rows": len(accepted_by_id),
        "rejected_rows": len(rejected),
        "missing_target_rows": len(targets) - len(accepted_by_id),
        "manifest_status": manifest["status"],
        "ready_to_validate_cache": ready,
        "template": str(args.template.relative_to(AI_ROOT) if args.template.is_absolute() else args.template),
        "intake": str(args.intake.relative_to(AI_ROOT) if args.intake.is_absolute() else args.intake),
        "manifest": str(args.manifest.relative_to(AI_ROOT) if args.manifest.is_absolute() else args.manifest),
        "error_counts": dict(error_counts),
        "rejected": rejected[:200],
        "policy": "No MSA generation is performed; empty intake remains fail-closed.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "accepted_rows": report["accepted_rows"],
        "rejected_rows": report["rejected_rows"],
        "missing_target_rows": report["missing_target_rows"],
        "ready_to_validate_cache": report["ready_to_validate_cache"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
