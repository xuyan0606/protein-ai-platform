#!/usr/bin/env python3
import argparse,csv,json
from pathlib import Path
FIELDS=['measurement_id','construct_accession','construct_fasta','parent_accession','parent_sequence','mature_chain_start','mature_chain_end','signal_peptide_length','mutation_notation','numbering_scheme','numbering_verified','condition_comparable','reviewer','reviewed_at','review_basis','authorization_received','authorization_receipt','review_status']
def validate(path: Path):
 failures=[]; rows=0; ready=0; seen=set()
 with path.open(encoding='utf-8',newline='') as f:
  rd=csv.DictReader(f)
  if rd.fieldnames!=FIELDS:return {'success':False,'rows':0,'ready_rows':0,'status':'invalid_field_contract','failure_count':1}
  for i,r in enumerate(rd,2):
   rows+=1;mid=r.get('measurement_id','').strip()
   if not mid or mid in seen: failures.append({'check':'measurement_id_unique','line':i})
   seen.add(mid)
   if r.get('review_status') not in {'pending','reviewed','approved','rejected',''}: failures.append({'check':'review_status','line':i})
   if all(r.get(k)=='true' for k in ('numbering_verified','condition_comparable','authorization_received')) and r.get('reviewer') and r.get('reviewed_at') and r.get('authorization_receipt'): ready+=1
 return {'success':not failures,'rows':rows,'ready_rows':ready,'queued_rows':rows-ready,'status':'queued_blocked' if ready<rows else 'ready_for_review_import','failure_count':len(failures),'failures':failures,'training_import_allowed_rows':0,'safe_for_model_claim':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();r=validate(a.input)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['success'] else 1)
