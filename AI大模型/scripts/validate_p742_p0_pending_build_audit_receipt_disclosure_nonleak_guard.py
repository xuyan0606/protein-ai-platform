#!/usr/bin/env python3
"""Validate P742 audit receipt disclosure/non-leak guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
from build_p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard import FIELDS
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p741_p0_pending_build_audit_receipt_retrieval_access_guard.jsonl"; BOARD=ROOT/"datasets/governance/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard.jsonl"; REPORT=ROOT/"reports/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard_report.json"; OUT=ROOT/"reports/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard_validation_report.json"
def main()->int:
    source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); guards=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
    def fail(c,x,o,e):
        if x: failures.append({"check":c,"observed":o,"expected":e})
    fail("source_rows",len(source)!=5,len(source),5); fail("guard_rows",len(guards)!=5,len(guards),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary"); fail("coverage",{r.get("source_p741_id") for r in guards}!={r.get("retrieval_guard_id") for r in source},"mismatch","exact")
    for f in FIELDS: fail(f"report_{f}",report.get(f"{f}_rows")!=0,report.get(f"{f}_rows"),0); fail(f"summary_{f}",summary.get(f"{f}_rows")!=0,summary.get(f"{f}_rows"),0)
    for i,row in enumerate(guards,1):
        fail(f"row_{i}_status",row.get("guard_status")!="empty_no_receipt_to_disclose",row.get("guard_status"),"empty_no_receipt_to_disclose")
        for f in FIELDS: fail(f"row_{i}_{f}",row.get(f) is not False,row.get(f),False)
    result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P742","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"disclosure_guard_rows":len(guards),**{f"{f}_rows":0 for f in FIELDS},"policy":"Validation only; no receipt exists to disclose."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"disclosure_guard_rows":len(guards),"sensitive_data_exposed_rows":0,"unauthorized_export_detected_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
