#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_INPUT=ROOT/'reports/sci_pre_audit_human_dispatch_20260902.json'
DEFAULT_OUTPUT=ROOT/'reports/sci_pre_audit_table_triage_20260902.json'
MEASUREMENT=re.compile(r'\b(?:kcat|km|kcat/km|tm|half[ -]?life|activity|stability|catalytic|conversion rate|affinity)\b',re.I)
CONTEXT=re.compile(r'\b(?:primer|sequence|mutation spectrum|property|interacting distance|construction)\b',re.I)
def triage_packet(packet):
 text=packet.get('source_evidence',{}).get('raw_text','')
 mh=sorted(set(m.group(0).lower() for m in MEASUREMENT.finditer(text))); ch=sorted(set(m.group(0).lower() for m in CONTEXT.finditer(text)))
 status='likely_measurement_table' if len(mh)>=2 else ('likely_context_table' if ch and not mh else 'unclear')
 return {'packet_id':packet.get('packet_id',''),'pmcid':packet.get('pmcid',''),'table_locator':packet.get('table_locator',''),'row_count':packet.get('row_count',0),'triage_status':status,'measurement_terms':mh,'context_terms':ch,'human_verification_required':True,'formal_decision':None,'training_import_allowed':False}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,default=DEFAULT_INPUT); p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); a=p.parse_args()
 src=json.loads(a.input.read_text(encoding='utf-8')); rows=[triage_packet(x) for x in src.get('packets',[])]
 out={'packet_count':len(rows),'tables':rows,'human_verification_required':True,'formal_intake_authorized':False,'training_import_allowed':False,'safe_for_model_claim':False,'release_ready':False}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'packet_count':len(rows),'measurement_tables':sum(x['triage_status']=='likely_measurement_table' for x in rows),'context_tables':sum(x['triage_status']=='likely_context_table' for x in rows)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
