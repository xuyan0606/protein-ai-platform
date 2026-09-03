#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "datasets/curation/sci_open_measurement_extraction_templates_20260902.jsonl"
OUTPUT = ROOT / "reports/sci_measurement_extraction_validation_20260902.json"

def validate_row(row: dict, root: Path) -> dict:
    errors=[]
    if not row.get("pmcid"): errors.append("pmcid_missing")
    source=str(row.get("source_path", "")); path=root/source
    if not source or not path.is_file(): errors.append("source_missing")
    if not row.get("table_locator"): errors.append("table_locator_missing")
    for field in ("construct","measurement_type","unit","assay_condition","source_quote","reviewer","reviewed_at"):
        if not row.get(field): errors.append(f"{field}_missing")
    if row.get("value") is None: errors.append("value_missing")
    try: datetime.fromisoformat(str(row.get("reviewed_at")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        if "reviewed_at_missing" not in errors: errors.append("reviewed_at_invalid")
    if row.get("status") != "reviewed": errors.append("status_not_reviewed")
    if row.get("training_import_allowed") is not False: errors.append("training_import_guard")
    return {"pmcid":row.get("pmcid"),"valid":not errors,"errors":errors}

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--input",type=Path,default=INPUT); parser.add_argument("--root",type=Path,default=ROOT); parser.add_argument("--output",type=Path,default=OUTPUT); args=parser.parse_args()
    rows=[json.loads(x) for x in args.input.read_text(encoding="utf-8").splitlines() if x.strip()]
    records=[validate_row(row,args.root) for row in rows]; report={"input_rows":len(rows),"valid_rows":sum(r["valid"] for r in records),"invalid_rows":sum(not r["valid"] for r in records),"records":records,"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({k:report[k] for k in ("input_rows","valid_rows","invalid_rows")},ensure_ascii=False)); return 0 if report["invalid_rows"]==0 else 1
if __name__ == "__main__": raise SystemExit(main())
