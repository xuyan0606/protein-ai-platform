#!/usr/bin/env python3
"""Extract frozen ESM-2 mean-pooled embeddings for research-only sequences."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import torch
import esm

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--weights',type=Path,required=True); p.add_argument('--batch-size',type=int,default=4); a=p.parse_args()
    rows=[json.loads(x) for x in a.input.read_text(encoding='utf-8').splitlines() if x.strip()]
    sequences={str(r['sequence_hash']):r['protein_sequence'] for r in rows if r.get('sequence_hash') and r.get('protein_sequence')}
    model, alphabet=esm.pretrained.esm2_t6_8M_UR50D(); model.eval(); batch_converter=alphabet.get_batch_converter(); layer=model.num_layers
    keys=sorted(sequences); vectors=[]
    with torch.no_grad():
      for start in range(0,len(keys),a.batch_size):
        batch=[(k,sequences[k]) for k in keys[start:start+a.batch_size]]; _,_,tokens=batch_converter(batch)
        out=model(tokens,repr_layers=[layer],return_contacts=False)['representations'][layer]
        for i,(_,seq) in enumerate(batch):
          vectors.append(out[i,1:len(seq)+1].mean(0).cpu().numpy().astype('float32'))
    matrix=np.stack(vectors) if vectors else np.empty((0,model.embed_dim),dtype='float32')
    a.output.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(a.output,sequence_hash=np.array(keys),embedding=matrix)
    meta=a.output.with_suffix('.json'); meta.write_text(json.dumps({'schema_version':'frozen_esm2_embedding.v1','research_only':True,'model':'esm2_t6_8M_UR50D','embedding_dimension':int(matrix.shape[1]),'sequence_count':len(keys),'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'weights_sha256':hashlib.sha256(a.weights.read_bytes()).hexdigest(),'weights_path':str(a.weights),'pooling':'mean_residue_tokens','training_run_started':False,'production_registration':'forbidden'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'completed','sequence_count':len(keys),'dimension':int(matrix.shape[1])})); return 0
if __name__=='__main__': raise SystemExit(main())
