"""Portable review CSV payloads; delivery/storage handled by the caller."""
import csv
import io
import json
import math


def review_exports(result):
    exports={}
    def emit(name,fields,rows):
        stream=io.StringIO(newline='')
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
        exports[name]={'filename':name+'.csv','content_type':'text/csv','encoding':'utf-8-sig',
                       'content':stream.getvalue(),'row_count':len(rows)}
    runs=result.get('strategy_runs',[])
    emit('strategy_status',['id','name','tier','trigger_status','implementation_status','status',
        'raw_count','filtered_count','pending_geometry_count','reason'],runs)
    mutations=[]
    for run in runs:
        for row in run['raw_candidates']:
            mutations.append({'strategy_id':run['id'],'mutation':row['mutation'],
                'author_coordinates':json.dumps(row.get('author_coordinates'),ensure_ascii=False),
                'rationale':row.get('rationale'),'geometry_status':row.get('validation_status','see_source_geometry'),
                'selected':row['mutation'] in run.get('selected_mutations',[])})
    emit('strategy_mutations',['strategy_id','mutation','author_coordinates','rationale','geometry_status','selected'],mutations)
    scores=[]
    decisions={r['mutation']:r for r in (result.get('selection_audit') or {}).get('candidate_decisions',[])}
    def raw_returns(branch, mutation, field):
        receipt=result.get('branches',{}).get(branch) or {}
        rows=receipt.get('raw_predictions') or receipt.get('predictions') or []
        values=[r.get(field,r.get('ddg_kcal_mol')) for r in rows if isinstance(r,dict) and r.get('mutation')==mutation]
        # Invalid non-finite returns are diagnostic strings, never JSON NaN or usable scores.
        values=[str(v) if isinstance(v,float) and not math.isfinite(v) else v for v in values]
        return json.dumps(values,ensure_ascii=False)
    for row in result.get('screened_candidates',result.get('preliminary_candidates',result.get('candidates',[]))):
        values=row.get('scores',{})
        coordinate=row.get('structure_position') or {}
        scores.append({'mutation':row['mutation'],
            'pdb_author_position':f'{coordinate.get("chain_id","?")}:{coordinate.get("residue_number","?")}{coordinate.get("insertion_code") or ""}',
            'strategy_ids':';'.join(sorted({s['strategy_id'] for s in row.get('sources',[]) if s.get('strategy_id')})),
            'display_decision':decisions.get(row['mutation'],{}).get('decision','not_evaluated'),
            'display_reason':decisions.get(row['mutation'],{}).get('reason',''),
            'ddgun_ddg':(values.get('ddgun') or {}).get('ddg'),
            'thermompnn_raw_ddg':(values.get('thermompnn') or {}).get('ddg_pred'),
            'ddgun_raw_returned':raw_returns('ddgun',row['mutation'],'ddg'),
            'thermompnn_raw_returned':raw_returns('thermompnn',row['mutation'],'ddg_pred'),
            'ddgun_score_used':values.get('ddgun') is not None,
            'thermompnn_score_used':values.get('thermompnn') is not None,
            'esm_preference':(values.get('esm_preference') or {}).get('score'),
            'ddgun_status':result.get('branches',{}).get('ddgun',{}).get('status'),
            'thermompnn_status':result.get('branches',{}).get('thermompnn',{}).get('status'),
            'geometry_status':(row.get('strategy_context') or {}).get('validation_status','see_source_geometry'),
            'risks':';'.join(row.get('risks',[]))})
    emit('independent_scores',['mutation','pdb_author_position','strategy_ids','display_decision','display_reason','ddgun_ddg','thermompnn_raw_ddg',
        'ddgun_raw_returned','thermompnn_raw_returned','ddgun_score_used','thermompnn_score_used',
        'esm_preference','ddgun_status','thermompnn_status','geometry_status','risks'],scores)
    return exports
