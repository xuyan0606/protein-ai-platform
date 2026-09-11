#!/usr/bin/env python3
"""Create deterministic group-level folds for research kinetics records."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--folds',type=int,default=5)
    a=p.parse_args(); rows=[json.loads(x) for x in a.input.read_text(encoding='utf-8').splitlines() if x.strip()]
    groups={}
    for r in rows:
        group=str(r.get('sequence_hash') or r.get('uniprot_id') or r.get('source_id') or r.get('record_id'))
        groups.setdefault(group,[]).append(r.get('record_id'))
    ordered=sorted(groups, key=lambda g: hashlib.sha256(g.encode()).hexdigest())
    assignments={g:i%a.folds for i,g in enumerate(ordered)}
    out={'schema_version':'kinetics_group_split.v1','input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'folds':a.folds,'group_count':len(groups),'row_count':len(rows),'assignments':assignments,'policy':'same sequence/accession group stays in one fold; research-only'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'rows':len(rows),'groups':len(groups),'folds':a.folds})); return 0
if __name__=='__main__': raise SystemExit(main())
