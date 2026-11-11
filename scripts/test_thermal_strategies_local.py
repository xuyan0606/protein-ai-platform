#!/usr/bin/env python3
"""Offline structure acceptance; exports real rule outputs, never model scores."""
import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))


async def evaluate(path, output, *, run_thermompnn=False):
    from app.services.structure_records import pdb_records, is_protein_atom
    from app.services.pdb_parser import _AA3TO1
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    data=path.read_text()
    atoms,models,_=pdb_records(data)
    chain=next(a['chain_id'] for a in atoms if is_protein_atom(a,_AA3TO1))
    residues={}
    for a in atoms:
        if a['model_id']==models[0] and a['chain_id']==chain and is_protein_atom(a,_AA3TO1) and a['occupancy']>0 and a['altloc'] in {'','A'}:
            residues.setdefault((a['residue_number'],a.get('insertion_code')), _AA3TO1[a['component_id']])
    sequence=''.join(residues.values())
    start=time.perf_counter()
    result=await thermostability_candidate_workflow(sequence,pdb_data=data,chain_id=chain,
        analysis_mode='exploration',offline=not run_thermompnn,run_ddgun=False,run_esm=False,
        run_thermompnn=run_thermompnn)
    elapsed=time.perf_counter()-start
    target=output/path.stem
    target.mkdir(parents=True,exist_ok=True)
    (target/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    (target/'report.md').write_text(result['report_markdown'])
    for artifact in result.get('review_exports',{}).values():
        (target/artifact['filename']).write_text(artifact['content'],encoding=artifact['encoding'])
    with (target/'strategy-status.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','name','tier','trigger_status','status','raw_count','filtered_count','pending_geometry_count','reason']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(result['strategy_runs'])
    with (target/'strategy-mutations.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['strategy_id','mutation_input_1based','author_coordinates','rationale','geometry_status','ddgun','esm','selected'])
        for run in result['strategy_runs']:
            for candidate in run['raw_candidates']:
                score=run.get('candidate_scores',{}).get(candidate['mutation'],{})
                writer.writerow([run['id'],candidate['mutation'],json.dumps(candidate.get('author_coordinates'),ensure_ascii=False),
                    candidate.get('rationale'),candidate.get('validation_status','see_source_geometry'),
                    json.dumps(score.get('ddgun')),json.dumps(score.get('esm_preference')),candidate['mutation'] in run.get('selected_mutations',[])])
    summary={'input':path.name,'input_sha256':hashlib.sha256(data.encode()).hexdigest(),'residues':len(sequence),
        'elapsed_seconds':round(elapsed,3),'strategy_count':len(result['strategy_runs']),
        'raw_hypotheses_by_strategy':{r['id']:r['raw_count'] for r in result['strategy_runs']},
        'status_by_strategy':{r['id']:r['status'] for r in result['strategy_runs']},
        'screened_singles':result.get('candidate_counts',{}).get('screened',0),
        'formal_candidates':len(result['candidates']),
        'real_model_inference_executed':result.get('branches',{}).get('thermompnn',{}).get('status')=='completed',
        'thermompnn_status':result.get('branches',{}).get('thermompnn',{}).get('status'),
        'thermompnn_coverage':result.get('branches',{}).get('thermompnn',{}).get('candidate_coverage')}
    assert summary['strategy_count']==17
    assert not result['candidate_output_allowed'] and not result['experimental_plan']
    assert all(r['status']!='failed' for r in result['strategy_runs'])
    if run_thermompnn:
        assert summary['real_model_inference_executed'], result['branches']['thermompnn']
        assert summary['thermompnn_coverage']['complete']
    (target/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdb',action='append',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--thermompnn-url',help='Optional real local model service; only loopback ports 4200–4299.')
    args=parser.parse_args()
    if args.thermompnn_url:
        from urllib.parse import urlsplit
        parsed=urlsplit(args.thermompnn_url)
        if (parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1'}
                or parsed.port not in range(4200,4300) or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {'','/'}):
            parser.error('Use an http loopback service in ports 4200–4299.')
        os.environ['THERMOMPNN_SERVICE_URL']=args.thermompnn_url.rstrip('/')
    for path in args.pdb:
        print(json.dumps(await evaluate(path,args.output,run_thermompnn=bool(args.thermompnn_url)),ensure_ascii=False))


if __name__=='__main__':
    asyncio.run(main())
