#!/usr/bin/env python3
import argparse,csv,hashlib,json,re
from pathlib import Path

def batch_number(path):
    match=re.fullmatch(r'measurement_candidates_batch(\d{3})\.csv',path.name)
    if not match:raise ValueError(f'invalid batch filename: {path.name}')
    return int(match.group(1))

def build_registry(extraction_dir):
    rows=[]
    paths=sorted(extraction_dir.glob('measurement_candidates_batch[0-9][0-9][0-9].csv'),key=batch_number)
    expected_fields=None
    for path in paths:
        batch=f'batch{batch_number(path):03d}'
        with path.open(encoding='utf-8',newline='') as f:
            reader=csv.DictReader(f)
            if expected_fields is None:expected_fields=reader.fieldnames
            elif reader.fieldnames!=expected_fields:raise ValueError(f'field drift: {path.name}')
            for row in reader:
                if any(row[k]!='false' for k in ('training_eligible','formal_decision_written','safe_for_model_claim')):raise ValueError(f'governance violation: {row["measurement_id"]}')
                rows.append({'candidate_batch':batch,**row})
    rows.sort(key=lambda r:(int(r['candidate_batch'][-3:]),r['measurement_id']))
    if len(rows)!=len({r['measurement_id'] for r in rows}):raise ValueError('duplicate measurement_id')
    return rows

def write_outputs(rows,output,manifest_output):
    if not rows:raise ValueError('empty registry')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    manifest={'registry_path':str(output),'registry_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'batch_count':len({r['candidate_batch'] for r in rows}),'row_count':len(rows),'unique_measurement_ids':len({r['measurement_id'] for r in rows}),'pmcid_count':len({r['pmcid'] for r in rows}),'training_eligible_rows':sum(r['training_eligible']=='true' for r in rows),'formal_decision_rows':sum(r['formal_decision_written']=='true' for r in rows),'safe_for_model_claim_rows':sum(r['safe_for_model_claim']=='true' for r in rows),'registry_status':'evidence_only_review_draft'}
    manifest_output.parent.mkdir(parents=True,exist_ok=True);manifest_output.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--extraction-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();report=write_outputs(build_registry(a.extraction_dir),a.output,a.manifest);print(json.dumps(report,ensure_ascii=False))
