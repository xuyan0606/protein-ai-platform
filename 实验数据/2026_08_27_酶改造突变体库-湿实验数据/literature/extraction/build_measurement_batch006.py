#!/usr/bin/env python3
import argparse,csv,hashlib,re,xml.etree.ElementTree as ET
from pathlib import Path
FIELDNAMES=['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']
VARIANTS={'Q24A':'Q24A','K104A':'K104A','K143A':'K143A','XynA-VT':'V3C/T30C','XynA-NT':'N36C/T188C','XynA-SN':'S109C/N153C','XynA-Spy':'SpyTag-Nterm/XynA/SpyCatcher-Cterm'}
def text_content(e): return ' '.join(''.join(e.itertext()).replace('\u00a0',' ').split())
def table_rows(root,tid):
 t=root.find(f".//table-wrap[@id='{tid}']")
 if t is None: raise ValueError(f'missing table {tid}')
 return [[text_content(c) for c in tr if c.tag in {'td','th'}] for tr in t.findall('.//tbody/tr')]
def require_headers(root,tid):
 t=root.find(f".//table-wrap[@id='{tid}']"); actual=[[text_content(c) for c in tr if c.tag in {'td','th'}] for tr in t.findall('.//thead/tr')]
 expected=[['','XynA','Q24A','K104A','K143A','XynA-VT','XynA-NT','XynA-SN','XynA-Spy']]
 if actual!=expected: raise ValueError(f'{tid}: header drift')
def split_value(raw):
 raw=raw.strip(); raw=re.sub(r'(?<=\d)\s+[a-z]+$','',raw,flags=re.I); raw=re.sub(r'^nd\s+[a-z]+$','nd',raw,flags=re.I)
 if raw.lower().startswith('nd') or raw.startswith('>') or '–' in raw: return raw,''
 p=re.split(r'\s*±\s*',raw)
 if len(p) not in (1,2): raise ValueError(f'malformed value: {raw!r}')
 return p[0].replace(',','.'),p[1].replace(',','.') if len(p)==2 else ''
def source_metadata(rootdir,rel):
 path=rootdir/rel; root=ET.parse(path).getroot(); ids={x.attrib.get('pub-id-type'):(x.text or '').strip() for x in root.findall('.//article-id')}
 return {'root':root,'pmid':ids['pmid'],'doi':ids['doi'],'pmcid':ids['pmcid'],'source_path':str(rel),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def measurement_row(meta,**values):
 row={f:'' for f in FIELDNAMES}; row.update({'pmid':meta['pmid'],'doi':meta['doi'],'pmcid':meta['pmcid'],'source_path':meta['source_path'],'source_sha256':meta['source_sha256'],'training_eligible':'false','formal_decision_written':'false','safe_for_model_claim':'false'}); row.update(values); return row
def build_rows(data_root):
 rel=Path('literature/raw_fulltext_xml/xylanase/PMC9957083.xml'); meta=source_metadata(data_root,rel); root=meta['root']
 for tid in ('foods-12-00879-t001','foods-12-00879-t002','foods-12-00879-t003'): require_headers(root,tid)
 variants=list(VARIANTS); idx={v:i for i,v in enumerate(['XynA',*variants],1)}; rows=[]
 for cells in table_rows(root,'foods-12-00879-t001'):
  key=cells[0].split('(')[0].strip().replace(' ','_').lower(); metric={'thermostability':'thermostability_65c_30min','t1/260°c':'half_life_60C','t1/270°c':'half_life_70C','tm':'Tm'}.get(key,key); unit='°C' if metric=='Tm' else ('%' if metric.startswith('thermostability') else ('min' if metric.startswith('half_life') else '')); wt,we=split_value(cells[1])
  for v in variants:
   mv,me=split_value(cells[idx[v]]); rows.append(measurement_row(meta,measurement_id=f"litm-{meta['pmid']}-{v.lower()}-{metric}",family='xylanase',enzyme_name='XynA',parent_variant='XynA',variant=v,mutation_composition=VARIANTS[v],metric=metric,mutant_value=mv,mutant_error=me,wt_value=wt,wt_error=we,unit=unit,assay_note='Table 1; construct-specific optimum/stability values; means/SD or threshold as reported; n=3 where reported',source_locator='Table 1',numbering_status='sequence_accession_only',human_review_status='pending_construct_sequence_review'))
 for cells in table_rows(root,'foods-12-00879-t002'):
  substrate,unit=cells[0].rsplit(' (',1); unit=unit.rstrip(')'); wt,we=split_value(cells[1])
  for v in variants:
   mv,me=split_value(cells[idx[v]]); rows.append(measurement_row(meta,measurement_id=f"litm-{meta['pmid']}-{v.lower()}-specific-activity-{substrate.lower().replace(' ','-')}",family='xylanase',enzyme_name='XynA',parent_variant='XynA',variant=v,mutation_composition=VARIANTS[v],metric='specific_activity',mutant_value=mv,mutant_error=me,wt_value=wt,wt_error=we,unit=unit,assay_substrate=substrate,assay_note='Table 2; mean of three replicates; optimum conditions are construct-specific',source_locator='Table 2',numbering_status='sequence_accession_only',human_review_status='pending_construct_sequence_review'))
 for cells in table_rows(root,'foods-12-00879-t003'):
  metric,unit=cells[0].split(' (',1); unit=unit.rstrip(')'); wt,we=split_value(cells[1])
  for v in variants:
   mv,me=split_value(cells[idx[v]]); rows.append(measurement_row(meta,measurement_id=f"litm-{meta['pmid']}-{v.lower()}-{metric.lower().replace(' ','-')}",family='xylanase',enzyme_name='XynA',parent_variant='XynA',variant=v,mutation_composition=VARIANTS[v],metric=metric,mutant_value=mv,mutant_error=me,wt_value=wt,wt_error=we,unit=unit,assay_substrate='beechwood xylan',assay_note='Table 3; mean of three replicates; optimal reaction conditions not tabulated per construct',source_locator='Table 3',numbering_status='sequence_accession_only',human_review_status='pending_construct_sequence_review'))
 if len(rows)!=len({r['measurement_id'] for r in rows}): raise ValueError('duplicate measurement_id')
 return rows
def write_csv(rows,output):
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=FIELDNAMES); w.writeheader(); w.writerows(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--data-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); rows=build_rows(a.data_root); write_csv(rows,a.output); print({'rows':len(rows),'output':str(a.output)})
