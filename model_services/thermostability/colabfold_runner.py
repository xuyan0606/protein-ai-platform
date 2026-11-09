"""CPU ColabFold with supplied MSA only; no search or runtime downloads."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

AA3 = dict(zip('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(), 'ARNDCQEGHILKMFPSTWYV'))
BASE = Path('/opt/protein-ai-platform/model-services/thermostability')


def validate_local_msa(payload):
    if payload.get('msa_policy') != 'local' or payload.get('allow_public_msa') is not False:
        raise ValueError('This deployment permits local MSA only; public search is disabled.')
    sequence = payload['sequence']
    if not isinstance(sequence, str) or not 2 <= len(sequence) <= 400 or set(sequence)-set(AA3.values()):
        raise ValueError('CPU ColabFold requires a standard amino acid sequence of length 2–400.')
    alignment=payload.get('alignment','')
    if not isinstance(alignment,str) or len(alignment.encode()) > 8*1024*1024:
        raise ValueError('Invalid local alignment.')
    rows=[]
    for line in alignment.splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('>'): rows.append('')
        elif rows: rows[-1]+=''.join(c for c in line if not c.islower() and c != '.')
        else: raise ValueError('Alignment must be FASTA/A3M.')
    if not rows or rows[0]!=sequence or any(len(r)!=len(sequence) or set(r)-set('ARNDCQEGHILKMFPSTWYV-X') for r in rows):
        raise ValueError('Alignment query, alphabet or column count mismatch.')
    if len(rows)>10000: raise ValueError('CPU alignment supports at most 10000 sequences.')
    return ''.join(f'>{"query" if i==0 else "hit_"+str(i)}\n{r}\n' for i,r in enumerate(rows))


def normalize_pdb(pdb, sequence):
    atoms=[]; residues={}; ca={}; names={}; chain=None
    for line in pdb.splitlines():
        if line.startswith('ENDMDL'): break
        if not line.startswith('ATOM  '): continue
        if chain is None: chain=line[21]
        if line[21] != chain: raise ValueError('Expected a single monomer chain.')
        key=(line[22:26],line[26:27])
        if key not in residues: residues[key]=len(residues)+1
        pos=residues[key]
        name=AA3.get(line[17:20])
        if name is None or (pos in names and names[pos]!=name): raise ValueError('Invalid predicted residue.')
        names[pos]=name
        if line[12:16].strip()=='CA':
            if pos in ca: raise ValueError('Duplicate predicted CA.')
            value=float(line[60:66])
            if not 0<=value<=100: raise ValueError('Invalid pLDDT B factor.')
            ca[pos]=value
        atoms.append(line[:21]+'A'+f'{pos:4d}'+' '+line[27:])
    if ''.join(names.values())!=sequence or sorted(ca)!=list(range(1,len(sequence)+1)):
        raise ValueError('Predicted PDB does not cover query exactly.')
    return '\n'.join(atoms+['TER','END','']), [ca[i] for i in range(1,len(sequence)+1)]


def resolve_alignment(payload, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if payload.get('alignment'):
        alignment = validate_local_msa(payload)
        source = 'supplied_local_alignment'
        database = 'not_used:supplied_alignment'
    else:
        # Validate policy and input bounds before launching any process. The
        # temporary one-row value is validation only, never inference evidence.
        sequence = payload.get('sequence', '')
        validate_local_msa({**payload, 'alignment': '>query\n' + sequence + '\n'})
        if payload.get('msa_source') != 'service_local_search':
            raise ValueError('A local alignment or explicit service_local_search is required.')
        database_path = Path(os.environ['COLABFOLD_HHBLITS_DATABASE'])
        if not Path(str(database_path) + '_hhm.ffindex').is_file():
            raise RuntimeError('Configured local HHblits database is unavailable.')
        query, output = workdir/'query.fasta', workdir/'query.a3m'
        query.write_text('>query\n' + sequence + '\n')
        command = [os.environ['COLABFOLD_HHBLITS_BINARY'], '-i', str(query), '-d', str(database_path),
                   '-oa3m', str(output), '-n', '1', '-e', '0.001', '-cpu', '2', '-maxmem', '4', '-v', '0']
        with (workdir/'msa-search.log').open('w') as logfile:
            subprocess.run(command, check=True, stdout=logfile, stderr=subprocess.STDOUT, timeout=300)
        if not output.is_file() or output.stat().st_size > 8_000_000:
            raise RuntimeError('Local MSA search did not produce a bounded alignment.')
        alignment = validate_local_msa({**payload, 'alignment': output.read_text()})
        source = 'service_local_search'
        database = os.getenv('COLABFOLD_HHBLITS_DATABASE_VERSION', database_path.name)
    return alignment, {'msa_source': source, 'msa_depth': alignment.count('>'),
        'msa_sha256': hashlib.sha256(alignment.encode()).hexdigest(), 'msa_database': database}


def run_colabfold(payload, workdir):
    workdir=Path(workdir); workdir.mkdir(parents=True,exist_ok=True)
    alignment, msa_metadata = resolve_alignment(payload, workdir/'msa')
    data=Path(os.environ.get('COLABFOLD_DATA_DIR',str(BASE/'colabfold-data')))
    params=data/'params'/'params_model_3_ptm.npz'
    marker=data/'params'/'download_finished.txt'
    if not params.is_file() or not marker.is_file():
        raise RuntimeError('Pinned AlphaFold2 parameters are not installed; runtime downloads are disabled.')
    source=Path(os.environ.get('COLABFOLD_SOURCE_DIR',str(BASE/'colabfold-src')))
    commit=(source/'ALGORITHM_COMMIT').read_text().strip()
    if len(commit)!=40: raise RuntimeError('Missing fixed ColabFold algorithm commit.')
    query=workdir/'query.a3m'; query.write_text(alignment)
    out=workdir/'prediction'; out.mkdir(exist_ok=True)
    command=[sys.executable,'-m','colabfold.batch',str(query),str(out),'--data',str(data),
             '--model-type','alphafold2_ptm','--num-models','1','--model-order','3','--num-recycle','1',
             '--num-seeds','1','--random-seed','0','--num-relax','0','--host-url','http://127.0.0.1:9',
             '--max-msa','64:128','--rank','plddt']
    env={**os.environ,'JAX_PLATFORMS':'cpu','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2',
         'MKL_NUM_THREADS':'2','TF_NUM_INTRAOP_THREADS':'2','TF_NUM_INTEROP_THREADS':'1',
         'XLA_FLAGS':'--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=2'}
    log=workdir/'colabfold.log'
    with log.open('w') as handle:
        subprocess.run(command,check=True,stdout=handle,stderr=subprocess.STDOUT,env=env,timeout=2400)
    predictions=sorted(out.glob('*unrelaxed_rank_001*.pdb'))
    if len(predictions)!=1: raise RuntimeError('ColabFold did not produce one ranked prediction.')
    pdb,confidence=normalize_pdb(predictions[0].read_text(),payload['sequence'])
    version=importlib.metadata.version('colabfold')
    evidence={'command':command,'stdout':log.read_text(),'unmodified_pdb':predictions[0].read_text(),
              'normalization':'Single monomer author chain A; residue IDs remapped to continuous 1..L; confidence read from CA B factors.',
              'alignment_sha256':hashlib.sha256(alignment.encode()).hexdigest(),
              'parameters_sha256':hashlib.sha256(params.read_bytes()).hexdigest()}
    evidence['msa'] = msa_metadata
    search_log = workdir/'msa/msa-search.log'
    if search_log.is_file():
        evidence['msa_search_log'] = search_log.read_text()[:100000]
    return {'result':{'msa_policy':'local','pdb_data':pdb,'chain_id':'A','plddt':confidence,
                       **msa_metadata,
                       'scientific_boundary':'Single-model CPU structure prediction; pLDDT is not Tm, stability or activity.'},
            'raw_result':json.dumps(evidence,sort_keys=True,allow_nan=False),'model_version':f'ColabFold {version}; AlphaFold2-ptm model_3; recycles=1; seed=0',
            'algorithm_commit':commit,'database_version':'Local MSA '+msa_metadata['msa_database']+'; SHA256 '+msa_metadata['msa_sha256']+'; AF2 params 2021-07-14'}
