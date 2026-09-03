#!/usr/bin/env python3
"""Project evidence-only registry rows into a human construct-review queue."""
import argparse, csv, json
from pathlib import Path

FIELDS = ["measurement_id","construct_accession","construct_fasta","parent_accession","parent_sequence","mature_chain_start","mature_chain_end","signal_peptide_length","mutation_notation","numbering_scheme","numbering_verified","condition_comparable","reviewer","reviewed_at","review_basis","authorization_received","authorization_receipt","review_status"]

def build(registry):
    out=[]; seen=set()
    with registry.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            mid=row['measurement_id']
            if mid in seen: continue
            seen.add(mid)
            out.append({k: (mid if k=='measurement_id' else row.get('variant','') if k=='mutation_notation' else 'pending' if k=='review_status' else '') for k in FIELDS})
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();rows=build(a.registry);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    report={'success':True,'rows':len(rows),'reviewed_rows':0,'authorization_received_rows':0,'training_import_allowed_rows':0,'safe_for_model_claim':False,'status':'open_empty_human_input_queue'};a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
