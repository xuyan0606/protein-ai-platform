#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path

AA='ACDEFGHIKLMNPQRSTVWY'
def read_fasta(path):
    s=''.join(x.strip() for x in Path(path).read_text().splitlines() if not x.startswith('>')).upper()
    if not s or any(c not in AA for c in s): raise ValueError('invalid FASTA')
    return s
def map_mutation(parent, construct, notation):
    m=re.fullmatch(r'([A-Z])(\d+)([A-Z])',notation or '')
    if not m:return {'status':'blocked_numbering_conflict','reason':'invalid_mutation_notation'}
    wt,pos,mut=m.group(1),int(m.group(2)),m.group(3)
    if len(parent)!=len(construct) or parent!=construct:return {'status':'blocked_sequence_mismatch','reason':'parent_construct_not_exact'}
    if pos<1 or pos>len(parent) or parent[pos-1]!=wt:return {'status':'blocked_numbering_conflict','reason':'wild_type_residue_mismatch','position':pos,'observed':parent[pos-1] if 0<pos<=len(parent) else None}
    return {'status':'verified','position':pos,'parent_residue':wt,'construct_residue':mut,'sequence_identity':1.0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--construct',type=Path,required=True);p.add_argument('--mutation',required=True);p.add_argument('--output',type=Path);a=p.parse_args();r=map_mutation(read_fasta(a.parent),read_fasta(a.construct),a.mutation);print(json.dumps(r,ensure_ascii=False));
 if a.output:a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 raise SystemExit(0 if r['status']=='verified' else 1)
