#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e):return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def val(s):
 p=re.split(r'\s*±\s*',s.strip()); return (p[0].replace(',',''),p[1].replace(',','')) if len(p)==2 else (p[0].replace(',',''),'')
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/mannanase/PMC5457547.xml'); p=rootdir/rel; root=ET.parse(p).getroot(); ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')}; m={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}; t=root.find(".//table-wrap[@id='Tab2']")
 if t is None: raise ValueError('missing Tab2')
 h=[txt(c) for c in t.findall('.//thead/tr')[0] if c.tag in {'th','td'}]
 if h!=['Procedure','V max (μmol min‒1 mg−1)','K m (mg mL‒1)','k cat (s‒1)','k cat/K m (mg s‒1 mL‒1)']: raise ValueError('header drift')
 substrate=''; data={}
 for tr in t.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if len(c)==1: substrate=c[0]; continue
  if len(c)!=5: raise ValueError(f'malformed {c!r}')
  data[(substrate,c[0])]=c[1:]
 rows=[]
 for sub in ('LBG','Guar gum'):
  if (sub,'mRmMan5A') not in data or (sub,'RmMan5A') not in data: raise ValueError('missing pairing')
  for i,(metric,unit) in enumerate([('Vmax','μmol min−1 mg−1'),('Km','mg mL−1'),('kcat','s−1'),('kcat_per_Km','mg s−1 mL−1')]):
   wt,we=val(data[(sub,'RmMan5A')][i]); mv,me=val(data[(sub,'mRmMan5A')][i]); rows.append({**{f:'' for f in FIELDNAMES},**m,'measurement_id':f"litm-{m['pmid']}-mrmman5a-{sub.lower().replace(' ','-')}-{metric.lower()}",'family':'mannanase','enzyme_name':'RmMan5A','parent_variant':'RmMan5A','variant':'mRmMan5A','mutation_composition':'Y233H/K264M/N343S','metric':metric,'mutant_value':mv,'mutant_error':me,'wt_value':wt,'wt_error':we,'unit':unit,'assay_substrate':sub,'assay_note':'Table 2; kinetic measurement; RmMan5A comparator','source_locator':'Table 2','numbering_status':'sequence_accession_only','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'})
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
