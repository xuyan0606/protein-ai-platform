#!/usr/bin/env python3
"""Apply conservative quality gates to resolved SKiD review candidates."""
from __future__ import annotations
import argparse, collections, hashlib, json
from pathlib import Path

def key(r): return (r.get('sequence_hash'),r.get('metric'),r.get('substrate'),r.get('value_si'),r.get('pH'),r.get('temperature'),r.get('mutation'))
def missing(v): return v in (None,'','-----','nan')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--clean-output',type=Path,required=True); p.add_argument('--review-output',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args()
    rows=[json.loads(x) for x in a.input.read_text().splitlines() if x.strip()]; counts=collections.Counter(key(r) for r in rows); clean=[]; review=[]
    for i,r in enumerate(rows,1):
      reasons=[]
      if r.get('quality_flags'): reasons.extend(r['quality_flags'])
      if counts[key(r)]>1: reasons.append('duplicate_measurement_key')
      if missing(r.get('pH')): reasons.append('missing_assay_ph')
      if missing(r.get('temperature')): reasons.append('missing_assay_temperature')
      if reasons:
        review.append({'review_status':'blocked_quality_gate','review_reasons':sorted(set(reasons)),'source_input_line':i,'record':r})
      else:
        r['training_import_status']='review_candidate_quality_pass'; r['quality_gate']='pass'; clean.append(r)
    report={'schema_version':'skid_review_candidate_audit.v1','input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'input_rows':len(rows),'quality_pass_rows':len(clean),'review_rows':len(review),'duplicate_groups':sum(v>1 for v in counts.values()),'review_reason_counts':dict(collections.Counter(x for r in review for x in r['review_reasons'])),'training_import_allowed':False,'production_registration':'forbidden'}
    for path,data in ((a.clean_output,clean),(a.review_output,review)):
      path.parent.mkdir(parents=True,exist_ok=True); path.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in data))
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(report)); return 0
if __name__=='__main__': raise SystemExit(main())
