#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e):return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def val(s):
 p=re.split(r'\s*±\s*',s.strip());return (p[0].replace(',',''),p[1].replace(',','')) if len(p)==2 else (p[0].replace(',',''),'')
def base(m,variant,comp,metric,mv,me,wt,we,unit,locator,note):
 return {**{f:'' for f in FIELDNAMES},**m,'measurement_id':f"litm-{m['pmid']}-{variant.lower()}-{locator[-1]}-{metric.lower()}",'family':'phytase','enzyme_name':'A1 phytase','parent_variant':'Parent' if locator=='Table 2' else 'A1','variant':variant,'mutation_composition':comp,'metric':metric,'mutant_value':mv,'mutant_error':me,'wt_value':wt,'wt_error':we,'unit':unit,'assay_substrate':'phytate','assay_note':note,'source_locator':locator,'numbering_status':'sequence_accession_only','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'}
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/phytase/PMC10101328.xml');p=rootdir/rel;root=ET.parse(p).getroot();ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')};m={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 comps={}
 for tr in root.find(".//table-wrap[@id='T1']").findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}];comps[c[0]]=c[1]
 expected={'D7':'C75Y/R404H','E3':'C75Y','F8':'C75S/V132L','F9':'C75W/A84T/N176D','G10':'C75S/I300F'}
 if comps!=expected:raise ValueError('composition drift')
 t2=root.find(".//table-wrap[@id='T2']");h2=[txt(c) for c in t2.findall('.//thead/tr')[0] if c.tag in {'th','td'}]
 if h2!=['Strain','Parent','D7','E3','F8','F9','G10']:raise ValueError('T2 header drift')
 rows=[]
 for tr in t2.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}];metric,unit=('enzyme_activity','U/mL') if c[0].startswith('Enzyme activity') else ('enzyme_yield','mg/mL');wt,we=val(c[1])
  for i,v in enumerate(h2[2:],2):mv,me=val(c[i]);rows.append(base(m,v,comps[v],metric,mv,me,wt,we,unit,'Table 2','Table 2; Parent comparator'))
 t3=root.find(".//table-wrap[@id='T3']");data={}
 for tr in t3.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}];data[c[0]]=c[1:]
 for v in ('D7','E3','F8'):
  for i,(metric,unit) in enumerate([('Km','mM'),('Vmax','μmol min-1 μg-1'),('kcat','s-1'),('kcat_per_Km','s-1 mM-1')]):
   wt,we=val(data['A1'][i]);mv,me=val(data[v][i]);rows.append(base(m,v,comps[v],metric,mv,me,wt,we,unit,'Table 3','Table 3; A1 comparator'))
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
