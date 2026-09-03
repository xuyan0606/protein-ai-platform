#!/usr/bin/env python3
import argparse
import csv
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

FIELDNAMES = ['measurement_id','pmid','doi','pmcid','family','enzyme_name','parent_variant','variant','mutation_composition','metric','mutant_value','mutant_error','wt_value','wt_error','unit','assay_ph','assay_temperature_c','assay_substrate','assay_note','source_path','source_sha256','source_locator','numbering_precheck_id','numbering_status','human_review_status','training_eligible','formal_decision_written','safe_for_model_claim']


def text_content(e):
    return ' '.join(''.join(e.itertext()).replace('\u00a0', ' ').split())


def source_metadata(rootdir, rel):
    path = rootdir / rel
    root = ET.parse(path).getroot()
    ids = {x.attrib.get('pub-id-type'): (x.text or '').strip() for x in root.findall('.//article-id')}
    return {'root': root, 'pmid': ids['pmid'], 'doi': ids['doi'], 'pmcid': ids['pmcid'],
            'source_path': str(rel), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def measurement_row(meta, **values):
    row = {f: '' for f in FIELDNAMES}
    row.update({'pmid': meta['pmid'], 'doi': meta['doi'], 'pmcid': meta['pmcid'],
                'source_path': meta['source_path'], 'source_sha256': meta['source_sha256'],
                'training_eligible': 'false', 'formal_decision_written': 'false',
                'safe_for_model_claim': 'false'})
    row.update(values)
    return row


def split_value(raw):
    raw = raw.strip()
    if not raw:
        return '', ''
    parts = re.split(r'\s*[±]\s*', raw)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], '')


def expanded_rows(table):
    """Expand JATS rowspan/colspan while retaining blank cells as values."""
    grid, pending = [], {}
    for tr in table.findall('.//tbody/tr'):
        row, col = [], 0
        cells = list(tr)
        for cell in cells:
            while col in pending and pending[col][0] > 0:
                row.append(pending[col][1]); pending[col] = (pending[col][0] - 1, pending[col][1]); col += 1
            value = text_content(cell)
            colspan, rowspan = int(cell.attrib.get('colspan', '1')), int(cell.attrib.get('rowspan', '1'))
            for offset in range(colspan):
                row.append(value)
                if rowspan > 1:
                    pending[col + offset] = (rowspan - 1, value)
            col += colspan
        while pending:
            if col in pending:
                row.append(pending[col][1]); pending[col] = (pending[col][0] - 1, pending[col][1]); col += 1
            elif col > max(pending):
                break
            else:
                row.append(''); col += 1
        grid.append(row)
    return grid


def build_rows(data_root):
    rel = Path('literature/raw_fulltext_xml/amylase/PMC5738361.xml')
    meta = source_metadata(data_root, rel)
    root = meta['root']
    t1 = root.find(".//table-wrap[@id='Tab1']")
    t2 = root.find(".//table-wrap[@id='Tab2']")
    if t1 is None or t2 is None:
        raise ValueError('missing Tab1/Tab2')
    h1 = [text_content(c) for c in t1.findall('.//thead/tr')[0] if c.tag in {'th', 'td'}]
    if h1 != ['', 'FSA (°C)', 'EH-CC-E204G (°C)']:
        raise ValueError('Tab1 header drift')
    rows = []
    for cells in expanded_rows(t1):
        if len(cells) != 3:
            raise ValueError(f'Tab1 malformed row: {cells!r}')
        condition, wt_raw, mut_raw = cells
        wt, wt_err = split_value(wt_raw); mut, mut_err = split_value(mut_raw)
        key = condition if condition != '−' else 'no metal'
        rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-eh-cc-e204g-tm-{len(rows)+1}",
            family='amylase', enzyme_name='FSA', parent_variant='EH-CC', variant='EH-CC-E204G',
            mutation_composition='engineered_EH-CC_background/E204G', metric='Tm', mutant_value=mut,
            mutant_error=mut_err, wt_value=wt, wt_error=wt_err, unit='°C', assay_substrate=key,
            assay_note='Table 1; DSC temperature; three replicate measurements with systematic error reported in text',
            source_locator='Table 1', numbering_status='sequence_accession_only', human_review_status='pending_construct_sequence_review'))
    h2 = [text_content(c) for c in t2.findall('.//thead/tr')[0] if c.tag in {'th', 'td'}]
    if h2 != ['Metal ion', 'Site', 'Parameter', 'FSA', 'EH-CC-E204G']:
        raise ValueError(f'Tab2 header drift: {h2!r}')
    current_metal = None
    for i, cells in enumerate(expanded_rows(t2)):
        if len(cells) != 5:
            raise ValueError(f'Tab2 expansion malformed row: {cells!r}')
        metal, site, parameter, wt_raw, mut_raw = cells
        if metal:
            current_metal = metal
        if not current_metal:
            raise ValueError(f'Tab2 missing metal context: {cells!r}')
        wt, wt_err = split_value(wt_raw); mut, mut_err = split_value(mut_raw)
        metric = 'binding_Kd' if parameter.startswith('K d') else 'binding_DeltaH' if parameter.startswith('ΔH') else parameter
        unit = 'μM' if metric == 'binding_Kd' else 'kcal/mol' if metric == 'binding_DeltaH' else ''
        metal_id = re.sub(r'[^a-z0-9]+', '-', current_metal.lower()).strip('-')
        rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-eh-cc-e204g-{metric.lower()}-{metal_id}-{site.lower().replace(' ', '-')}",
            family='amylase', enzyme_name='FSA', parent_variant='EH-CC', variant='EH-CC-E204G',
            mutation_composition='engineered_EH-CC_background/E204G', metric=metric, mutant_value=mut,
            mutant_error=mut_err, wt_value=wt, wt_error=wt_err, unit=unit, assay_substrate=current_metal,
            assay_note=f'Table 2; {site}', source_locator='Table 2', numbering_status='sequence_accession_only',
            human_review_status='pending_construct_sequence_review'))
    if len(rows) != len({r['measurement_id'] for r in rows}):
        raise ValueError('duplicate measurement_id')
    return rows


def write_csv(rows, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader(); writer.writerows(rows)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--data-root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); rows = build_rows(args.data_root); write_csv(rows, args.output); print({'rows': len(rows), 'output': str(args.output)})
