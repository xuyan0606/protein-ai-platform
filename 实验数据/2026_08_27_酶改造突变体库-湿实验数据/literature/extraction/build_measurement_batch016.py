#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e):return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def val(s):
 p=re.split(r'\s*±\s*',s.strip());return p[0],p[1] if len(p)==2 else ''
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/acid_protease/PMC6167268.xml');p=rootdir/rel;root=ET.parse(p).getroot();ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')};m={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};t=root.find(".//table-wrap[@id='Tab4']")
 h=[txt(c) for c in t.findall('.//thead/tr')[0] if c.tag in {'th','td'}]
 if h!=['Sample','MCA (U µg−1)','Proteolytic activity PA (U µg−1)','Ratio MCA/PA']:raise ValueError('header drift')
 data={}
 for tr in t.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if len(c)!=4:raise ValueError(f'malformed {c!r}')
  data[c[0]]=c[1:]
 wt=data['MCAP-3 (non-mutated)'];mut=data['MutMCAP-8 (mutated)'];rows=[]
 for i,(metric,unit) in enumerate([('milk_clotting_activity','U µg−1'),('proteolytic_activity','U µg−1'),('MCA_per_PA','ratio')]):
  wv,we=val(wt[i]);mv,me=val(mut[i]);rows.append({**{f:'' for f in FIELDNAMES},**m,'measurement_id':f"litm-{m['pmid']}-mutmcap-8-{metric}",'family':'acid_protease','enzyme_name':'MCAP','parent_variant':'MCAP-3','variant':'MutMCAP-8','mutation_composition':'N331Q','metric':metric,'mutant_value':mv,'mutant_error':me,'wt_value':wv,'wt_error':we,'unit':unit,'assay_note':'Table 4; purified enzyme; MCAP-3 comparator; SyMCAP-6 and M. mihei excluded','source_locator':'Table 4','numbering_status':'direct_cds_translation_match','human_review_status':'pending_signal_peptide_expression_background_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'})
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
