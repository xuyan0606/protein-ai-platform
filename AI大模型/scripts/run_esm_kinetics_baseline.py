#!/usr/bin/env python3
"""Evaluate frozen ESM-2 embeddings on grouped kinetics folds."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

def score(y,p):
    e=y-p; return {'rmse_log10':float(np.sqrt(np.mean(e*e))),'mae_log10':float(np.mean(np.abs(e))),'n':int(len(y))}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--splits',type=Path,required=True); p.add_argument('--embeddings',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    rows=[json.loads(x) for x in a.input.read_text(encoding='utf-8').splitlines() if x.strip()]; split=json.loads(a.splits.read_text()); emb=np.load(a.embeddings); lookup={str(k):v for k,v in zip(emb['sequence_hash'],emb['embedding'])}
    results=[]
    for metric in ('km','kcat'):
      data=[r for r in rows if r.get('metric')==metric and not r.get('quality_flags') and r.get('value_si') is not None and str(r.get('sequence_hash')) in lookup]
      y=np.log10(np.array([float(r['value_si']) for r in data], dtype=np.float64)); X=np.stack([lookup[str(r['sequence_hash'])] for r in data]).astype(np.float64); groups=[str(r['sequence_hash']) for r in data]; folds=[]
      for fold in range(split['folds']):
        tr=np.array([i for i,g in enumerate(groups) if split['assignments'].get(g)!=fold]); te=np.array([i for i,g in enumerate(groups) if split['assignments'].get(g)==fold])
        if not len(tr) or not len(te): continue
        center=X[tr].mean(axis=0); scale=X[tr].std(axis=0); scale=np.maximum(scale,1e-3)
        Xtr=np.clip((X[tr]-center)/scale,-20,20); Xte=np.clip((X[te]-center)/scale,-20,20)
        ridge=Ridge(alpha=10.0).fit(Xtr,y[tr]); rf=RandomForestRegressor(n_estimators=200,max_depth=4,min_samples_leaf=2,random_state=20260911,n_jobs=1).fit(Xtr,y[tr])
        folds.append({'fold':fold,'train_n':int(len(tr)),'test_n':int(len(te)),'ridge':score(y[te],ridge.predict(Xte)),'random_forest':score(y[te],rf.predict(Xte))})
      results.append({'metric':metric,'rows':len(data),'folds':folds})
    out={'schema_version':'esm_kinetics_baseline.v1','research_only':True,'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'split_sha256':hashlib.sha256(a.splits.read_bytes()).hexdigest(),'embedding_file_sha256':hashlib.sha256(a.embeddings.read_bytes()).hexdigest(),'embedding_model':'esm2_t6_8M_UR50D','results':results,'training_run_started':False,'production_registration':'forbidden'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':'completed','metrics':[x['metric'] for x in results]}))
if __name__=='__main__': main()
