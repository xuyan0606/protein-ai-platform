#!/usr/bin/env python3
import argparse,csv,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
def txt(e):return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def make(m,mid,metric,mv,wv,unit,loc,temp='',note=''):
 return {**{f:'' for f in FIELDNAMES},**m,'measurement_id':mid,'family':'amylase','enzyme_name':'A. oryzae glucoamylase','parent_variant':'Parent','variant':'M-60(5)','mutation_composition':'unresolved:L203I_vs_L103I','metric':metric,'mutant_value':mv.replace('‒','-'),'wt_value':wv.replace('‒','-'),'unit':unit,'assay_ph':'5.0' if loc=='Table 1' else '','assay_temperature_c':temp or ('50' if loc=='Table 1' else ''),'assay_substrate':'soluble starch' if loc=='Table 1' else '','assay_note':note,'source_locator':loc,'numbering_status':'conflict_L203I_vs_L103I','human_review_status':'blocked_numbering_conflict','training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'}
def build_rows(rootdir):
 rel=Path('literature/raw_fulltext_xml/amylase/PMC12007714.xml');p=rootdir/rel;root=ET.parse(p).getroot();ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')};m={'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};rows=[]
 t1=root.find(".//table-wrap[@id='pone.0319261.t001']"); metrics=[('Vmax','U mg-1'),('Km','mg ml-1'),('Vmax_per_Km','ratio'),('kcat','s-1'),('kcat_per_Km','ratio'),('activation_DeltaH','kJ mol-1'),('activation_DeltaG','kJ mol-1'),('activation_DeltaS','J mol-1 K-1')]
 body=t1.findall('.//tbody/tr')
 if len(body)!=8:raise ValueError('Table 1 row drift')
 for tr,(metric,unit) in zip(body,metrics):
  c=[txt(x) for x in tr if x.tag in {'td','th'}];rows.append(make(m,f"litm-{m['pmid']}-m60-t1-{metric.lower()}",metric,c[2],c[1],unit,'Table 1',note='Table 1; numbering conflict retained'))
 t2=root.find(".//table-wrap[@id='pone.0319261.t002']"); metrics2=[('thermal_Kd','min-1'),('half_life','min'),('thermal_DeltaH','kJ mol-1'),('thermal_DeltaG','kJ mol-1'),('thermal_DeltaS','J mol-1 K-1')]
 for tr in t2.findall('.//tbody/tr'):
  c=[txt(x) for x in tr if x.tag in {'td','th'}]
  if c==['P','M']*5:continue
  if len(c)!=12:raise ValueError(f'Table 2 row drift {c!r}')
  temp=c[0]
  for i,(metric,unit) in enumerate(metrics2):
   wt,mut=c[2+i*2],c[3+i*2];rows.append(make(m,f"litm-{m['pmid']}-m60-t2-{temp}-{metric.lower()}",metric,mut,wt,unit,'Table 2',temp,'Table 2; irreversible thermal stability; numbering conflict retained'))
 return rows
def write_csv(rows,out):
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rs=build_rows(a.data_root);write_csv(rs,a.output);print({'rows':len(rs),'output':str(a.output)})
