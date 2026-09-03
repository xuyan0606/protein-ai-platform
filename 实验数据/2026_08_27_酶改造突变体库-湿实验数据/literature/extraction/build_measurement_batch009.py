#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e): return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def meta(rootdir,rel):
 p=rootdir/rel; root=ET.parse(p).getroot(); ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')}; return {'root':root,'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def row(m,**kw):
 r={f:'' for f in FIELDNAMES}; r.update({'pmid':m['pmid'],'doi':m['doi'],'pmcid':m['pmcid'],'source_path':m['source_path'],'source_sha256':m['source_sha256'],'training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'}); r.update(kw); return r
def val(s):
 s=s.strip().replace(',',''); p=re.split(r'\s*±\s*',s); return (p[0],p[1]) if len(p)==2 else (p[0],'')
def build_rows(data_root):
 m=meta(data_root,Path('literature/raw_fulltext_xml/xylanase/PMC11430584.xml')); t=m['root'].find(".//table-wrap[@id='biomolecules-14-01188-t001']")
 if t is None: raise ValueError('missing table')
 h=[txt(c) for c in t.findall('.//thead/tr')[0] if c.tag in {'th','td'}]
 exp=['Xylanase','Substrate','Vmax (μmol min−1 mg−1)','Km (mg mL−1)','Kcat (s−1)','Kcat/Km (mL mg−1 s−1)']
 if h!=exp: raise ValueError(f'header drift: {h!r}')
 raw=[]
 current_variant=''
 for tr in t.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if len(c)==6: current_variant=c[0]
  elif len(c)==5 and current_variant: c=[current_variant]+c
  else: raise ValueError(f'malformed row: {c!r}')
  raw.append(c)
 wt=[c for c in raw if c[0]=='Xynst']; mut=[c for c in raw if c[0]=='W6F/Q7H']
 if len(wt)!=4 or len(mut)!=4 or [c[1] for c in wt] != [c[1] for c in mut]: raise ValueError('variant/substrate pairing drift')
 rows=[]
 for w,u in zip(wt,mut):
  for i,(metric,unit) in enumerate([('Vmax','μmol min−1 mg−1'),('Km','mg mL−1'),('kcat','s−1'),('kcat_per_Km','mL mg−1 s−1')],2):
   wtval,wte=val(w[i]); mv,mve=val(u[i]); slug=re.sub(r'[^a-z0-9]+','-',u[1].lower()).strip('-')
   rows.append(row(m,measurement_id=f"litm-{m['pmid']}-w6f-q7h-{slug}-{metric.lower()}",family='xylanase',enzyme_name='Xynst',parent_variant='Xynst',variant='W6F/Q7H',mutation_composition='W6F/Q7H',metric=metric,mutant_value=mv,mutant_error=mve,wt_value=wtval,wt_error=wte,unit=unit,assay_substrate=u[1],assay_note='Table 1; substrate-specific kinetic measurement; parent comparator Xynst',source_locator='Table 1',numbering_status='sequence_accession_only',human_review_status='pending_construct_sequence_review'))
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=FIELDNAMES); w.writeheader(); w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--data-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); rs=build_rows(a.data_root); write_csv(rs,a.output); print({'rows':len(rs),'output':str(a.output)})
