#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e):return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def val(s):
 p=re.split(r'\s*±\s*',s.strip());return p[0].replace(',',''),p[1].replace(',','')
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/mannanase/PMC5457547.xml');p=rootdir/rel;root=ET.parse(p).getroot();ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')};m={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};t=root.find(".//table-wrap[@id='Tab1']")
 heads=[[txt(c) for c in tr if c.tag in {'th','td'}] for tr in t.findall('.//thead/tr')]
 if heads!=[['Substrate','Specific activity (U mg−1; mean ± SD)'],['mRmMan5Aa','RmMan5Ab'],['pH 4.5, 65 °C','pH 4.5, 65 °C','pH 7.0, 55 °C']]:raise ValueError('header drift')
 rows=[]
 for tr in t.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if len(c)!=4:raise ValueError(f'malformed {c!r}')
  mv,me=val(c[1]);wv,we=val(c[2]);slug=re.sub(r'[^a-z0-9]+','-',c[0].lower()).strip('-');rows.append({**{f:'' for f in FIELDNAMES},**m,'measurement_id':f"litm-{m['pmid']}-mrmman5a-t1-{slug}",'family':'mannanase','enzyme_name':'RmMan5A','parent_variant':'RmMan5A','variant':'mRmMan5A','mutation_composition':'Y233H/K264M/N343S','metric':'specific_activity','mutant_value':mv,'mutant_error':me,'wt_value':wv,'wt_error':we,'unit':'U mg−1','assay_ph':'4.5','assay_temperature_c':'65','assay_substrate':c[0],'assay_note':'Table 1; matched pH 4.5/65 C comparator only; RmMan5A pH 7.0/55 C column excluded','source_locator':'Table 1','numbering_status':'sequence_accession_only','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'})
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
