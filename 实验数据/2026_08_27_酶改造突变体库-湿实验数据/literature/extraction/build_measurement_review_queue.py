#!/usr/bin/env python3
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

REVIEW_FIELDS=['review_priority','review_lane','required_checks','reviewer','review_decision','reviewed_at','authorization_receipt']

def classify(row):
    numbering=(row['numbering_status']+' '+row['mutation_composition']).lower()
    if 'conflict' in numbering or row['human_review_status'].lower().startswith('blocked_numbering'):
        return 'P0','numbering_conflict','resolve reported position against source construct sequence; verify WT residue; document chosen numbering basis'
    composition=row['mutation_composition']
    if '/' in composition or 'engineered' in composition.lower() or row['parent_variant'] not in {'','WT',row['enzyme_name']}:
        return 'P1','construct_background','verify complete construct composition; verify direct parent; confirm signal peptide/tag/truncation boundaries'
    return 'P2','sequence_numbering','bind source construct sequence; verify WT residue and position; confirm assay context and license receipt'

def build_queue(registry):
    with registry.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    group_fields=('source_sha256','parent_variant','variant','mutation_composition','numbering_status','human_review_status')
    groups={}
    for row in rows:groups.setdefault(tuple(row[f] for f in group_fields),[]).append(row)
    queue=[]
    for key,members in groups.items():
        first=members[0];priority,lane,checks=classify(first);task_id='litreview-'+hashlib.sha256('\x1f'.join(key).encode()).hexdigest()[:16]
        contexts=sorted({f"pH={r['assay_ph'] or 'NA'};T={r['assay_temperature_c'] or 'NA'};substrate={r['assay_substrate'] or 'NA'}" for r in members})
        queue.append({'review_task_id':task_id,'candidate_batches':'|'.join(sorted({r['candidate_batch'] for r in members})),'pmid':first['pmid'],'doi':first['doi'],'pmcid':first['pmcid'],'family':first['family'],'enzyme_name':first['enzyme_name'],'parent_variant':first['parent_variant'],'variant':first['variant'],'mutation_composition':first['mutation_composition'],'numbering_precheck_id':first['numbering_precheck_id'],'numbering_status':first['numbering_status'],'human_review_status':first['human_review_status'],'source_path':first['source_path'],'source_sha256':first['source_sha256'],'measurement_count':str(len(members)),'measurement_ids':'|'.join(sorted(r['measurement_id'] for r in members)),'metrics':'|'.join(sorted({r['metric'] for r in members})),'source_locators':'|'.join(sorted({r['source_locator'] for r in members})),'assay_contexts':'|'.join(contexts),'training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false','review_priority':priority,'review_lane':lane,'required_checks':checks,'reviewer':'','review_decision':'','reviewed_at':'','authorization_receipt':''})
    queue.sort(key=lambda r:(r['review_priority'],r['candidate_batches'],r['review_task_id']))
    return queue

def write_outputs(rows,output,report_output):
    if not rows:raise ValueError('empty review queue')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lanes=Counter(r['review_lane'] for r in rows);priorities=Counter(r['review_priority'] for r in rows)
    report={'status':'open_empty_human_review_queue','review_task_count':len(rows),'linked_measurement_count':sum(int(r['measurement_count']) for r in rows),'lane_counts':dict(lanes),'priority_counts':dict(priorities),'reviewed_rows':sum(bool(r['review_decision']) for r in rows),'authorized_rows':sum(bool(r['authorization_receipt']) for r in rows),'training_eligible_rows':sum(r['training_eligible']=='true' for r in rows)}
    report_output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return report

def write_json_queue(rows,json_output):
    json_output.parent.mkdir(parents=True,exist_ok=True)
    json_output.write_text(json.dumps({'status':'open_empty_human_review_queue','rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--json-output',type=Path);a=p.parse_args();rows=build_queue(a.registry);report=write_outputs(rows,a.output,a.report)
    if a.json_output:write_json_queue(rows,a.json_output)
    print(json.dumps(report,ensure_ascii=False))
