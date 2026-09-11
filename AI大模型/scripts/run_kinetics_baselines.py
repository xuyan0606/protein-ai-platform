#!/usr/bin/env python3
"""Run transparent research baselines on the auditable kinetics subset."""
from __future__ import annotations
import argparse, hashlib, json, math, re
from pathlib import Path
import numpy as np

def metrics(y,p):
    err=y-p; rmse=float(np.sqrt(np.mean(err*err))); mae=float(np.mean(np.abs(err))); r2=float(1-np.sum(err*err)/np.sum((y-y.mean())**2)) if len(y)>1 and np.sum((y-y.mean())**2)>0 else None
    return {'rmse_log10':rmse,'mae_log10':mae,'r2':r2,'n':int(len(y))}

def parse_numeric(value):
    """Parse a scalar or range conservatively; return None when unavailable."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    text = re.sub(r"(?<=\d)\s*[-\u2013]\s*(?=\d)", " ", str(value))
    matches = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
    if not matches:
        return None
    numbers = [float(x) for x in matches]
    return float(np.mean(numbers))

def condition_matrix(data):
    values = np.array([
        [parse_numeric(r.get('pH')), parse_numeric(r.get('temperature'))]
        for r in data
    ], dtype=float)
    return values

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--splits',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    rows=[json.loads(x) for x in a.input.read_text(encoding='utf-8').splitlines() if x.strip()]; sp=json.loads(a.splits.read_text(encoding='utf-8')); results=[]
    for metric in ('km','kcat'):
      data=[r for r in rows if r.get('metric')==metric and not r.get('quality_flags') and r.get('value_si') is not None]
      ys=np.log10(np.array([float(r['value_si']) for r in data],dtype=float)); groups=[str(r.get('sequence_hash') or r.get('uniprot_id') or r.get('source_id') or r.get('record_id')) for r in data]
      folds=[]; conditions=condition_matrix(data)
      for fold in range(sp['folds']):
        tr=np.array([i for i,g in enumerate(groups) if sp['assignments'].get(g)!=fold]); te=np.array([i for i,g in enumerate(groups) if sp['assignments'].get(g)==fold])
        if len(te)==0 or len(tr)==0: continue
        median=float(np.median(ys[tr])); ridge=None
        Xconditions=conditions.copy()
        for column in range(Xconditions.shape[1]):
          train_values=Xconditions[tr, column]
          fill=float(np.nanmedian(train_values)) if np.isfinite(train_values).any() else 0.0
          Xconditions[~np.isfinite(Xconditions[:, column]), column]=fill
        X=np.column_stack([np.ones(len(data)), Xconditions[:, 0]/14, Xconditions[:, 1]/100])
        try: ridge=np.linalg.solve(X[tr].T@X[tr]+0.1*np.eye(X.shape[1]),X[tr].T@ys[tr])
        except np.linalg.LinAlgError: ridge=None
        foldres={'fold':fold,'train_n':int(len(tr)),'test_n':int(len(te)),'median':metrics(ys[te],np.full(len(te),median)),'ridge':metrics(ys[te],X[te]@ridge) if ridge is not None else None}
        folds.append(foldres)
      results.append({'metric':metric,'rows':len(data),'folds':folds,
                      'condition_parse':{
                        'ph_numeric':int(np.isfinite(conditions[:, 0]).sum()),
                        'temperature_numeric':int(np.isfinite(conditions[:, 1]).sum()),
                        'temperature_ranges_averaged':int(sum(isinstance(r.get('temperature'), str) and len(re.findall(r"(?<!\d)[-+]?\d+(?:\.\d*)?|(?<!\d)\.\d+", re.sub(r"(?<=\d)\s*[-\u2013]\s*(?=\d)", " ", r.get('temperature')))) > 1 for r in data)),
                      },
                      'tree_model':{'status':'unavailable','reason':'scikit-learn not installed; no substitute implemented'}})
    out={'schema_version':'kinetics_baseline_report.v1','research_only':True,'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'split_sha256':hashlib.sha256(a.splits.read_bytes()).hexdigest(),'training_run_started':False,'production_registration':'forbidden','results':results}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'metrics':[x['metric'] for x in results]})); return 0
if __name__=='__main__': main()
