#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
F=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def t(e): return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def v(s):
 p=re.split(r'\s*±\s*',s); return p[0],p[1] if len(p)>1 else ''
def build_rows(root):
 rel=Path('literature/raw_fulltext_xml/phytase/PMC11380507.xml');p=root/rel;r=ET.parse(p).getroot();ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in r.findall('.//article-id')};src={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};rows=[[t(x) for x in tr if x.tag in {'td','th'}] for tr in r.find(".//table-wrap[@id='T2']").findall('.//tr')];wt=rows[1];spec=[('specific_activity','U/mg'),('Km','μM'),('kcat','s−1'),('kcat_per_Km','μM−1 s−1'),('half_life_55C','min'),('half_life_80C','min'),('T50_30','°C'),('Tm','°C'),('pepsin_resistance','%'),('trypsin_resistance','%')];out=[]
 for row in rows[2:]:
  for i,(m,u) in enumerate(spec,1):
   mv,me=v(row[i]);wv,we=v(wt[i]);out.append({**{x:'' for x in F},**src,'measurement_id':f"litm-{ids['pmid']}-yiappa-{row[0].lower().replace('/','-')}-{m}",'family':'phytase','enzyme_name':'YiAPPA','parent_variant':'YiAPPA','variant':row[0],'mutation_composition':row[0],'metric':m,'mutant_value':mv,'mutant_error':me,'wt_value':wv,'wt_error':we,'unit':u,'assay_substrate':'phytate','assay_note':'Table 2; YiAPPA comparator','source_locator':'Table 2','numbering_status':'sequence_accession_only','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'})
 return out
def write_csv(rs,o):
 o.parent.mkdir(parents=True,exist_ok=True)
 with o.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=F);w.writeheader();w.writerows(rs)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
