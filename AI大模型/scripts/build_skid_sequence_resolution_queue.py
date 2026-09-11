#!/usr/bin/env python3
"""Build a deterministic UniProt sequence-resolution queue from SKiD audit output."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import defaultdict

def main():
    p=argparse.ArgumentParser(); p.add_argument('--audit',type=Path,required=True); p.add_argument('--resolved',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--limit',type=int,default=250); a=p.parse_args()
    audit=json.loads(a.audit.read_text()); resolved={json.loads(x)['accession'] for x in a.resolved.read_text().splitlines() if x.strip()}
    stats=defaultdict(lambda:{'rows':0,'metrics':set(),'complete_conditions':0,'wildtype':0})
    for r in audit['raw_records']:
      acc=r.get('uniprot_id');
      if not acc or acc in resolved: continue
      s=stats[acc]; s['rows']+=1; s['metrics'].add(r['metric']); s['complete_conditions']+=int(r.get('pH') not in (None,'-----') and r.get('temperature') not in (None,'-----')); s['wildtype']+=int(not r.get('mutation'))
    queue=[]
    for acc,s in stats.items():
      queue.append({'accession':acc,'row_count':s['rows'],'metrics':sorted(s['metrics']),'complete_condition_rows':s['complete_conditions'],'wildtype_rows':s['wildtype'],'priority_score':s['rows']+2*s['wildtype']+s['complete_conditions'],'status':'pending_uniprot_resolution','training_import_allowed':False})
    queue.sort(key=lambda x:(-x['priority_score'],x['accession'])); queue=queue[:a.limit]
    out={'schema_version':'skid_sequence_resolution_queue.v1','source_file_sha256':audit['source_file_sha256'],'resolved_accessions_excluded':len(resolved),'candidate_accessions_total':len(stats),'queue_limit':a.limit,'queue':queue,'training_import_allowed':False,'policy':'Queue only; sequence resolution and quality review precede any training import.'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'queued':len(queue),'candidate_accessions_total':len(stats)})); return 0
if __name__=='__main__': raise SystemExit(main())
