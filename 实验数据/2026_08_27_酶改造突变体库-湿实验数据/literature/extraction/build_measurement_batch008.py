#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e): return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def split(v):
 p=re.split(r'\s*±\s*',v.strip()); return (p[0],p[1]) if len(p)==2 else (p[0],'')
def meta(rootdir,rel):
 path=rootdir/rel; root=ET.parse(path).getroot(); ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')}; return {'root':root,'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def row(m,**kw):
 r={f:'' for f in FIELDNAMES}; r.update({'pmid':m['pmid'],'doi':m['doi'],'pmcid':m['pmcid'],'source_path':m['source_path'],'source_sha256':m['source_sha256'],'training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'}); r.update(kw); return r
def build_rows(data_root):
 m=meta(data_root,Path('literature/raw_fulltext_xml/xylanase/PMC8546418.xml')); root=m['root']; t=root.find(".//table-wrap[@id='tbl1']")
 if t is None: raise ValueError('missing tbl1')
 h=[txt(c) for c in t.findall('.//thead/tr')[0] if c.tag in {'th','td'}]
 if h != ['Enzyme','Km (mg/ml)','kcat (/s)','kcat/Km (ml/mg/s)']: raise ValueError('header drift')
 rows=[]
 for cells in t.findall('.//tbody/tr'):
  c=[txt(x) for x in cells if x.tag in {'td','th'}]
  if len(c)!=4: raise ValueError(f'malformed row: {c!r}')
  variant=c[0]; composition='' if variant=='XynLC9' else variant
  for metric,raw,unit in [('Km',c[1],'mg/ml'),('kcat',c[2],'/s'),('kcat_per_Km',c[3],'ml/mg/s')]:
   value,error=split(raw); rows.append(row(m,measurement_id=f"litm-{m['pmid']}-{variant.lower().replace('/','-')}-{metric.lower()}",family='xylanase',enzyme_name='XynLC9',parent_variant='XynLC9',variant=variant,mutation_composition=composition,metric=metric,mutant_value=value,mutant_error=error,unit=unit,assay_substrate='xylan',assay_note='Table 1; kinetic measurement; mean ± error as reported',source_locator='Table 1',numbering_status='sequence_accession_only',human_review_status='pending_construct_sequence_review'))
 if len(rows)!=len({r['measurement_id'] for r in rows}): raise ValueError('duplicate measurement_id')
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f: csv.DictWriter(f,fieldnames=FIELDNAMES).writeheader(); csv.DictWriter(f,fieldnames=FIELDNAMES).writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--data-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); rs=build_rows(a.data_root); write_csv(rs,a.output); print({'rows':len(rs),'output':str(a.output)})
