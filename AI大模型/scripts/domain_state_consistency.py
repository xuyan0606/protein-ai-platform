"""Build a fail-closed consistency snapshot for domain architecture curation."""

import argparse
import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_summary(evidence_path: Path, decision_path: Path, applied_path: Path, sidecar_path: Path):
    evidence = _load(evidence_path)
    decisions = _load(decision_path)
    applied = _load(applied_path)
    sidecar = _load(sidecar_path)
    evidence_rows = evidence.get("input_rows", evidence.get("evidence_rows", 0))
    single_usable = applied.get("usable_for_position_features", 0)
    multi_usable = sidecar.get("safe_for_position_features_rows", sidecar.get("feature_rows", 0))
    output_rows = applied.get("output_rows", 0)
    unresolved = applied.get("status_counts", {}).get("domain_interval_unresolved", 0)
    errors = []
    if decisions.get("evidence_rows") != evidence_rows:
        errors.append("decision evidence_rows does not match evidence input_rows")
    if applied.get("queue_rows") != evidence_rows:
        errors.append("applied queue_rows does not match evidence input_rows")
    status_total = sum(applied.get("status_counts", {}).values())
    if status_total != output_rows:
        errors.append("applied status counts do not sum to output_rows")
    if output_rows != decisions.get("merged_decision_rows", output_rows):
        errors.append("applied output_rows does not match merged decisions")
    if single_usable > output_rows or multi_usable > evidence_rows:
        errors.append("usable feature counts exceed source rows")
    if single_usable + multi_usable + unresolved > evidence_rows:
        errors.append("feature scope counts exceed evidence rows")
    consistency = {"ok": not errors, "errors": errors}
    status = "blocked_inconsistent" if errors else "blocked"
    return {
        "status": status,
        "policy": "feature readiness does not authorize supervised training or model claims",
        "totals": {
            "evidence": evidence_rows,
            "single_interval_usable": single_usable,
            "multi_occurrence_usable": multi_usable,
            "unresolved": unresolved,
        },
        "source_reports": {
            "evidence": str(evidence_path),
            "decisions": str(decision_path),
            "applied": str(applied_path),
            "sidecar": str(sidecar_path),
        },
        "allowed_feature_scopes": ["single_interval_plus_sidecar"] if not errors else [],
        "consistency": consistency,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.base
    summary = build_summary(
        base / "reports/domain_interpro_evidence_report.json",
        base / "reports/domain_interval_interpro_decision_report.json",
        base / "reports/domain_interval_apply_report.json",
        base / "reports/domain_multi_occurrence_feature_report.json",
    )
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["consistency"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
