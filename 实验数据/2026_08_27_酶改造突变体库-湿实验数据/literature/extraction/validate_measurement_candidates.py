#!/usr/bin/env python3
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

FIELDS=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
GOVERNANCE=('training_eligible','formal_decision_written','safe_for_model_claim')

def validate(data_root, extraction_dir):
    failures=[]; rows=[]; paths=sorted(extraction_dir.glob('measurement_candidates_batch*.csv'))
    for path in paths:
        with path.open(encoding='utf-8',newline='') as f:
            reader=csv.DictReader(f)
            if reader.fieldnames!=FIELDS:
                failures.append({'check':'field_contract','file':path.name})
                continue
            for line,row in enumerate(reader,2):
                row['_file']=path.name;row['_line']=line;rows.append(row)
                if any(row[k]!='false' for k in GOVERNANCE):failures.append({'check':'governance_false','file':path.name,'line':line})
                source=data_root/row['source_path']
                if not source.is_file():failures.append({'check':'source_exists','file':path.name,'line':line})
                elif hashlib.sha256(source.read_bytes()).hexdigest()!=row['source_sha256']:failures.append({'check':'source_sha256','file':path.name,'line':line})
    ids=Counter(r['measurement_id'] for r in rows)
    for key,count in ids.items():
        if not key or count>1:failures.append({'check':'measurement_id_unique','measurement_id':key,'count':count})
    semantic_fields=[f for f in FIELDS if f not in {'measurement_id','source_sha256'}]
    semantic=Counter(tuple(r[f] for f in semantic_fields) for r in rows)
    for key,count in semantic.items():
        if count>1:failures.append({'check':'semantic_row_unique','count':count})
    return {'success':not failures,'batch_count':len(paths),'row_count':len(rows),'unique_measurement_ids':len(ids),'pmcid_count':len({r['pmcid'] for r in rows}),'failure_count':len(failures),'failures':failures}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--extraction-dir',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();report=validate(a.data_root,a.extraction_dir)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));raise SystemExit(0 if report['success'] else 1)
