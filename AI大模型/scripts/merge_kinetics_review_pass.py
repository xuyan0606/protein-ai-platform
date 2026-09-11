#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--existing',type=Path,required=True); p.add_argument('--expanded',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args()
    rows=[]; seen=set()
    for path in (a.existing,a.expanded):
      for line in path.read_text().splitlines():
        if not line.strip(): continue
        r=json.loads(line); key=(r.get('source_id'),r.get('source_row_or_table'),r.get('metric'),r.get('value_si'))
        if key in seen: continue
        seen.add(key); r['training_import_status']='review_candidate_quality_pass'; rows.append(r)
    out={'schema_version':'merged_kinetics_review_pass.v1','inputs_sha256':[hashlib.sha256(x.read_bytes()).hexdigest() for x in (a.existing,a.expanded)],'rows':len(rows),'unique_sequence_hashes':len({r.get('sequence_hash') for r in rows}),'metrics':{m:sum(r.get('metric')==m for r in rows) for m in ('km','kcat')},'training_import_allowed':True,'research_only':True,'production_registration':'forbidden'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)); a.report.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out)); return 0
if __name__=='__main__': raise SystemExit(main())
