#!/usr/bin/env python3
import argparse,csv,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e): return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/mannanase/PMC9986629.xml');p=rootdir/rel;root=ET.parse(p).getroot();ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')};src={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};t=root.find(".//table-wrap[@id='T1']");trs=t.findall('.//tr');data=[]
 for tr in trs[1:]:
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if len(c)!=8: raise ValueError(f'malformed {c!r}')
  data.append(c)
 if len(data)!=7 or data[0][0]!='Anman': raise ValueError('variant drift')
 wt=data[0];metrics=[('specific_activity','U/mg'),('relative_activity','%'),('Km','mg/mL'),('kcat','s−1'),('kcat_per_Km','mL mg−1 s−1'),('half_life','min'),('Tm','°C')];out=[]
 for c in data[1:]:
  for i,(metric,unit) in enumerate(metrics,1): out.append({**{f:'' for f in FIELDNAMES},**src,'measurement_id':f"litm-{src['pmid']}-anman-{c[0].lower()}-{metric.lower()}",'family':'mannanase','enzyme_name':'Anman','parent_variant':'Anman','variant':c[0],'mutation_composition':c[0],'metric':metric,'mutant_value':c[i],'wt_value':wt[i],'unit':unit,'assay_substrate':'locust bean gum','assay_note':'Table 1; Anman mutant property matrix; WT comparator','source_locator':'Table 1','numbering_status':'sequence_accession_only','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'})
 return out
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=build_rows(a.data_root);write_csv(r,a.output);print({'rows':len(r),'output':str(a.output)})
