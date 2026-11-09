"""Real EVcouplings/PLMC evidence with independently checked local MSA quality."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path

BASE=Path('/opt/protein-ai-platform/model-services/thermostability')


def prepare_alignment(payload):
    sequence=payload['sequence']; text=payload.get('alignment','')
    if not isinstance(sequence,str) or not 2<=len(sequence)<=400 or set(sequence)-set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('CPU PLMC requires a standard amino acid sequence of length 2–400.')
    if not isinstance(text,str) or len(text.encode())>8*1024*1024: raise ValueError('Invalid alignment size.')
    rows=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('>'): rows.append('')
        elif rows: rows[-1]+=''.join(c for c in line if not c.islower() and c!='.')
        else: raise ValueError('Alignment must be FASTA/A3M.')
    if not rows or rows[0]!=sequence or any(len(r)!=len(sequence) or set(r)-set('ACDEFGHIKLMNPQRSTVWY-') for r in rows):
        raise ValueError('Alignment query/alphabet/length mismatch.')
    if len(rows)>10000: raise ValueError('CPU MSA supports at most 10000 sequences.')
    return ''.join(f'>{"query/1-"+str(len(sequence)) if i==0 else "hit_"+str(i)}\n{r}\n' for i,r in enumerate(rows)),rows


def verify_quality(rows, neff, length):
    coverage=sum(sum(c!='-' for c in r) for r in rows)/(len(rows)*length)
    quality={'neff':float(neff),'coverage':coverage,'sequence_count':len(rows),
             'method':'EVcouplings Alignment.set_weights identity_threshold=0.8 method=withgaps; coverage=mean non-gap fraction'}
    if not math.isfinite(neff) or neff<max(50.,length/2) or len(rows)<50 or coverage<.8:
        raise ValueError(f'Computed MSA quality insufficient: Neff={neff:.3f}, coverage={coverage:.3f}, sequences={len(rows)}.')
    return quality


def parse_couplings(text, length):
    result=[]; seen=set()
    for line in text.splitlines():
        if not line.strip(): continue
        fields=line.split()
        if len(fields)!=6: raise ValueError('Unexpected PLMC coupling columns.')
        i,j,score=int(fields[0]),int(fields[2]),float(fields[5])
        if not 1<=i<j<=length or (i,j) in seen or not math.isfinite(score): raise ValueError('Invalid PLMC pair/score.')
        seen.add((i,j)); result.append({'position_i':i,'position_j':j,'score':score})
    result.sort(key=lambda row:row['score'],reverse=True)
    if not result: raise ValueError('PLMC produced no couplings.')
    return result[:50000]


def run_evcouplings(payload, workdir):
    from evcouplings.align import Alignment
    from evcouplings.couplings.tools import run_plmc
    text,rows=prepare_alignment(payload)
    workdir=Path(workdir); workdir.mkdir(parents=True,exist_ok=True)
    path=workdir/'alignment.fasta'; path.write_text(text)
    with path.open() as handle: alignment=Alignment.from_file(handle,format='fasta')
    alignment.set_weights(identity_threshold=.8,method='withgaps',cpu=2)
    quality=verify_quality(rows,float(sum(alignment.weights)),len(payload['sequence']))
    source=Path(os.environ.get('EVCOUPLINGS_SOURCE_DIR',str(BASE/'evcouplings-src')))
    commit=(source/'ALGORITHM_COMMIT').read_text().strip()
    plmc=Path(os.environ.get('PLMC_BINARY',str(BASE/'plmc-src/bin/plmc')))
    plmc_commit=(plmc.parent.parent/'ALGORITHM_COMMIT').read_text().strip()
    if len(commit)!=40 or len(plmc_commit)!=40: raise RuntimeError('Fixed EVcouplings/PLMC provenance missing.')
    weights=workdir/'weights.txt'
    with weights.open('w') as handle: alignment.save_weights(handle)
    couplings=workdir/'couplings.txt'
    # Weight file uses the same Neff checked above, preventing caller quality substitution.
    fit=run_plmc(str(path),str(couplings),focus_seq='query',theta=.8,iterations=100,
                 lambda_h=.01,lambda_J=.01*20*(len(payload['sequence'])-1),cpu=2,
                 weight_file=str(weights),binary=str(plmc))
    if abs(fit.effective_samples-quality['neff'])>.11:
        raise RuntimeError('PLMC effective samples disagree with locally computed MSA weights.')
    coupling_text=couplings.read_text()
    log_path=Path(str(couplings)+'.log')
    logs='\n'.join(p.read_text() for p in sorted(workdir.glob('*.log')))
    evidence={'couplings':coupling_text,'log':logs,'computed_msa_quality':quality,
              'upstream_msa_quality':payload.get('msa_quality'),
              'optimization_status':fit.optimization_status,'plmc_commit':plmc_commit,
              'settings':{'theta':.8,'iterations':100,'lambda_h':.01,'lambda_J':.01*20*(len(payload['sequence'])-1),'cpu':2,'weights':'locally computed'},
              'alignment_sha256':hashlib.sha256(text.encode()).hexdigest()}
    return {'result':{'couplings':parse_couplings(coupling_text,len(payload['sequence'])),'msa_quality':quality,
                      'scientific_boundary':'Evolutionary statistical couplings are not mutation ddG, Tm or catalytic activity; optimization status is recorded in evidence.'},
            'raw_result':json.dumps(evidence,sort_keys=True,allow_nan=False),
            'model_version':'EVcouplings '+importlib.metadata.version('evcouplings')+'; PLMC '+plmc_commit,
            'algorithm_commit':commit,'database_version':'Supplied local MSA SHA256 '+hashlib.sha256(text.encode()).hexdigest()+'; no sequence search performed'}
