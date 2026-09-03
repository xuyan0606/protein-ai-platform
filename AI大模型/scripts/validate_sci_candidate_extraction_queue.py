#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'datasets/curation/sci_all_candidate_measurement_extraction_queue_20260902.jsonl'
REPORT=ROOT/'reports/sci_candidate_extraction_queue_validation_20260902.json'
def main():
 p=argparse.ArgumentParser(); p.add_argument('--queue',type=Path,default=QUEUE); p.add_argument('--root',type=Path,default=ROOT); p.add_argument('--report',type=Path,default=REPORT); a=p.parse_args()
 rows=[json.loads(x) for x in a.queue.read_text(encoding='utf-8').splitlines() if x.strip()]; failures=[]
 for i,r in enumerate(rows,1):
  if not r.get('pmcid'): failures.append({'row':i,'error':'pmcid_missing'})
  if not r.get('table_locator'): failures.append({'row':i,'error':'table_locator_missing'})
  if not (a.root/str(r.get('source_path',''))).is_file(): failures.append({'row':i,'error':'source_missing'})
  if r.get('status')!='pending_human_extraction': failures.append({'row':i,'error':'status_not_pending'})
  if r.get('training_import_allowed') is not False: failures.append({'row':i,'error':'training_guard'})
 report={'queue_rows':len(rows),'failures':failures,'success':not failures,'training_import_allowed':False,'safe_for_model_claim':False,'release_ready':False}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'queue_rows':len(rows),'failures':len(failures),'success':report['success']},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
