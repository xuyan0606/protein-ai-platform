#!/usr/bin/env python3
"""Audit the downloaded SKiD workbook without promoting rows to training."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    source_sha=sha256(a.input); results=[]
    for sheet, metric, value_col, unit in [('kcat_dataset','kcat','kcat_value (1/s)','s-1'),('Km_dataset','km','Km_value (mM)','mM')]:
        df=pd.read_excel(a.input,sheet_name=sheet)
        ids=df['UniProt_ID'].dropna().astype(str).str.strip()
        values=pd.to_numeric(df[value_col],errors='coerce')
        records=[]
        for idx,row in df.iterrows():
            accession=str(row.get('UniProt_ID') or '').strip()
            value=values.iloc[idx]
            records.append({'source_id':f'SKiD_{metric}_{row.get("Entry_ID")}', 'source_row_or_table':f'{sheet}:excel_row_{idx+2}', 'source_file_sha256':source_sha, 'license':'CC BY 4.0', 'license_status':'research_attribution_required', 'metric':metric, 'uniprot_id':accession or None, 'value':None if pd.isna(value) else float(value), 'unit':unit, 'substrate':None if pd.isna(row.get('Substrate')) else str(row.get('Substrate')), 'pH':None if pd.isna(row.get('pH')) else str(row.get('pH')), 'temperature':None if pd.isna(row.get('Temperature')) else str(row.get('Temperature')), 'mutation':None if pd.isna(row.get('Mutation')) or str(row.get('Mutation'))=='-----' else str(row.get('Mutation')), 'reference':None if pd.isna(row.get('References')) else str(row.get('References')), 'protein_sequence':None, 'training_import_status':'not_promoted_pending_sequence_and_quality_audit'})
        results.append({'sheet':sheet,'metric':metric,'rows':len(df),'unique_uniprot_ids':int(ids.nunique()),'non_numeric_values':int(values.isna().sum()),'missing_ph':int(df['pH'].isna().sum() + (df['pH'].astype(str).str.strip()=='-----').sum()),'missing_temperature':int(df['Temperature'].isna().sum() + (df['Temperature'].astype(str).str.strip()=='-----').sum()),'mutant_rows':int((df['Mutant'].astype(str).str.lower()=='yes').sum()),'records':records})
    flat=[r for x in results for r in x.pop('records')]
    out={'schema_version':'skid_kinetics_source_audit.v1','source_file':str(a.input),'source_file_sha256':source_sha,'license':'CC BY 4.0','research_only':True,'training_import_allowed':False,'production_registration':'forbidden','sheets':results,'raw_records':flat}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'rows':len(flat),'metrics':[x['metric'] for x in results]})); return 0
if __name__=='__main__': raise SystemExit(main())
