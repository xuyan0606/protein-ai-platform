#!/usr/bin/env python3
"""Join audited SKiD rows with resolved UniProt sequences; remain review-only."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from normalize_literature_measurements import normalize_row

def main():
    p=argparse.ArgumentParser(); p.add_argument('--audit',type=Path,required=True); p.add_argument('--sequences',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    seqs={}
    for line in a.sequences.read_text().splitlines():
      r=json.loads(line)
      if r.get('status')=='resolved_exact_accession' and r.get('sequence'): seqs[r['accession']]=r
    out=[]
    audit=json.loads(a.audit.read_text())
    for raw in audit['raw_records']:
      evidence=seqs.get(raw.get('uniprot_id'))
      if not evidence: continue
      row=dict(raw); row['protein_sequence']=evidence['sequence']; row['sequence_source_url']=evidence['source_url']; row['sequence_source_file_sha256']=evidence['sequence_sha256']; row['sequence_provenance']='UniProt REST exact accession; fetched batch audit';
      n=normalize_row(row); n['training_import_status']='review_candidate_only'; n['promotion_blockers']=['manual_source_review','condition_quality_review','duplicate_and_family_split_review']; out.append(n)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in out)); print(json.dumps({'rows':len(out),'unique_sequences':len({x.get("sequence_hash") for x in out})})); return 0
if __name__=='__main__': raise SystemExit(main())
