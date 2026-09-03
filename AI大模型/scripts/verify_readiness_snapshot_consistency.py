import argparse
import json
from pathlib import Path


def verify(base: Path):
    readiness = json.loads((base / "reports/training_readiness_report.json").read_text())
    board = json.loads((base / "reports/master_readiness_board.json").read_text())
    domain = readiness["label_integrity"]["domain_architecture"]
    streams = {row["stream"]: row for row in board["streams"]}
    errors = []
    if domain["rows"] != 1942 or domain["invalid_interval_rows"] != 2:
        errors.append("domain totals mismatch")
    if board["ready_streams"] != 1:
        errors.append("strict ready stream count must remain one (MSA trusted cache)")
    if streams["domain_intervals"]["status"] != "partial_ready":
        errors.append("domain stream status mismatch")
    if readiness["structure_cache"]["coordinate_features_scope"] != "sample_only":
        errors.append("structure scope mismatch")
    return {"ok": not errors, "errors": errors, "strict_ready_streams": board["ready_streams"], "domain_unresolved": domain["invalid_interval_rows"]}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--base", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    result = verify(a.base); a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False)); return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
