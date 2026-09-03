#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e): return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def val(s):
 p=re.split(r'\s*±\s*',s.strip()); return (p[0],p[1]) if len(p)==2 else (p[0],'')
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/xylanase/PMC6659274.xml'); path=rootdir/rel; root=ET.parse(path).getroot(); ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')}; source={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 comps={'PjxA':'–','PTxA':'T10Y/N11H/N12D/Y15F/N30L','PjxA-DB':'T2C/T29C','PTxA-DB':'T2C/T10Y/N11H/N12D/Y15F/N30L/T29C'}
 t1=root.find(".//table-wrap[@id='Tab1']"); t2=root.find(".//table-wrap[@id='Tab2']"); r1=[]
 for tr in t1.findall('.//tr')[1:]:
  c=[txt(x) for x in tr if x.tag in {'td','th'}];
  if len(c)!=5: raise ValueError(f'malformed table1 {c!r}')
  r1.append(c)
 if {x[0] for x in r1} != set(comps): raise ValueError('variant drift')
 wt1=next(x for x in r1 if x[0]=='PjxA'); out=[]
 for c in r1:
  if c[0]=='PjxA': continue
  for metric,raw,wt,unit in [('half_life',c[2],wt1[2],'s/min'),('Tm',c[3],wt1[3],'°C')]:
   mv,me=val(raw); wv,we=val(wt); out.append(row(source,c[0],comps[c[0]],metric,mv,me,wv,we,unit,'Table 1','60','beechwood xylan'))
 trs=t2.findall('.//tr');
 for tr in trs[1:]:
  c=[txt(x) for x in tr if x.tag in {'td','th'}];
  if len(c)!=4: raise ValueError(f'malformed table2 {c!r}')
  variant=c[0]
  for metric,raw,unit in [('kcat',c[1],'1/s'),('Km',c[2],'mg/mL'),('kcat_per_Km',c[3],'mL/s·mg')]:
   mv,me=val(raw); out.append(row(source,variant,comps[variant],metric,mv,me,'','',''.join(unit),'Table 2','55','beechwood xylan'))
 return out
def row(source,variant,comp,metric,mv,me,wv,we,unit,locator,temp,substrate):
 return {**{f:'' for f in FIELDNAMES},**source,'measurement_id':f"litm-{source['pmid']}-pjxa-{variant.lower().replace('-','')}-{metric.lower()}",'family':'xylanase','enzyme_name':'PjxA','parent_variant':'PjxA','variant':variant,'mutation_composition':comp,'metric':metric,'mutant_value':mv,'mutant_error':me,'wt_value':wv,'wt_error':we,'unit':unit,'assay_temperature_c':temp,'assay_substrate':substrate,'assay_note':f'{locator}; recombinant xylanase comparator','source_locator':locator,'numbering_status':'sequence_accession_only','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'}
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=FIELDNAMES); w.writeheader(); w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
