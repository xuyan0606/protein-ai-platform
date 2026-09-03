#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e):return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def val(s):
 p=re.split(r'\s*[±()]\s*',s.strip()); nums=re.findall(r'[-+]?\d+(?:\.\d+)?',s); return (nums[0],nums[1] if len(nums)>1 else '') if nums else ('','')
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/phytase/PMC9181005.xml'); p=rootdir/rel; root=ET.parse(p).getroot(); ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')}; m={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}; t=root.find(".//table-wrap[@id='ijms-23-06346-t001']")
 if t is None: raise ValueError('missing table')
 h=[txt(c) for c in t.findall('.//thead/tr')[0] if c.tag in {'th','td'}]
 if h!=['AppA Variant','Km (µM)','kcat (s−1)','kcat/Km (µM−1s−1)']: raise ValueError('header drift')
 comps={'HAT':'D304A','HET':'D304E','HAE':'D304A/T305E','HDE':'T305E'}; data={}
 for tr in t.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if len(c)!=4: raise ValueError(f'malformed {c!r}')
  data[c[0]]=c[1:]
 if set(data)!=set(['HDT',*comps]): raise ValueError('variant drift')
 rows=[]
 for v,comp in comps.items():
  for i,(metric,unit) in enumerate([('Km','µM'),('kcat','s−1'),('kcat_per_Km','µM−1s−1')]):
   wt,we=val(data['HDT'][i]); mv,me=val(data[v][i]); rows.append({**{f:'' for f in FIELDNAMES},**m,'measurement_id':f"litm-{m['pmid']}-{v.lower()}-{metric.lower()}",'family':'phytase','enzyme_name':'AppA','parent_variant':'HDT','variant':v,'mutation_composition':comp,'metric':metric,'mutant_value':mv,'mutant_error':me,'wt_value':wt,'wt_error':we,'unit':unit,'assay_substrate':'InsP6','assay_note':'Table 1; kinetic measurement; HDT comparator','source_locator':'Table 1','numbering_status':'direct_construct_site_review_pending','human_review_status':'pending_construct_sequence_review','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'})
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
