#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
from urllib.request import Request, urlopen

def fetch(acc):
    url=f'https://rest.uniprot.org/uniprotkb/{acc}.fasta'; req=Request(url,headers={'User-Agent':'KWB-SKiD-audit/1.0'})
    with urlopen(req,timeout=30) as r: text=r.read().decode('utf-8')
    seq=''.join(x.strip() for x in text.splitlines() if not x.startswith('>'))
    return url,seq
def main():
    p=argparse.ArgumentParser(); p.add_argument('--queue',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--limit',type=int,default=50); a=p.parse_args(); q=json.loads(a.queue.read_text())['queue'][:a.limit]; out=[]
    for item in q:
      acc=item['accession']; row={'accession':acc,'source_url':f'https://rest.uniprot.org/uniprotkb/{acc}.fasta','status':'fetch_failed'}
      try:
        url,seq=fetch(acc); row.update(source_url=url,sequence=seq,sequence_sha256=hashlib.sha256(seq.encode()).hexdigest(),sequence_length=len(seq),status='resolved_exact_accession')
      except Exception as exc: row['error']=type(exc).__name__+': '+str(exc)
      out.append(row); time.sleep(0.05)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in out)); print(json.dumps({'requested':len(q),'resolved':sum(x['status']=='resolved_exact_accession' for x in out)})); return 0
if __name__=='__main__': raise SystemExit(main())
