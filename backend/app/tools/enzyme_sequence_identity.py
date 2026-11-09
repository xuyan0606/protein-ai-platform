"""Bounded RCSB/UniProt identity investigation independent of NCBI job polling."""
from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

import httpx

from app.tools.registry import ToolRegistry


async def _resolve(sequence: str, uniprot_id: str) -> dict:
    digest = hashlib.sha256(sequence.encode()).hexdigest()
    result: dict[str, Any] = {'status': 'partial', 'sequence_sha256': digest,
        'query': {'sequence_sha256': digest, 'sequence_length': len(sequence)},
        'references': [], 'evidence_bundle': {}, 'evidence_level': 'research_only_identity_investigation',
        'method': 'RCSB sequence search -> UniProt sequence verification -> InterPro family and UniProt functional features',
        'limitations': ['Sequence similarity alone does not establish catalytic function or measured thermostability.']}
    accessions = [uniprot_id] if uniprot_id else []
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=True) as client:
        if not accessions:
            query = {'query': {'type': 'terminal', 'service': 'sequence', 'parameters': {
                'evalue_cutoff': 1e-5, 'identity_cutoff': 0.85, 'sequence_type': 'protein', 'value': sequence}},
                'return_type': 'polymer_entity', 'request_options': {'paginate': {'start': 0, 'rows': 2}}}
            response = await client.post('https://search.rcsb.org/rcsbsearch/v2/query', json=query)
            if response.status_code == 204:
                result['limitations'].append('RCSB has no qualifying structure reference; this is not a no-hit result for UniProt or BLAST.')
                return result
            response.raise_for_status()
            for hit in response.json().get('result_set', [])[:2]:
                entity_id = str(hit.get('identifier') or '')
                if not re.fullmatch(r'[0-9A-Za-z]{4}_[0-9]+', entity_id):
                    continue
                pdb, entity = entity_id.split('_')
                response = await client.get(f'https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb}/{entity}')
                response.raise_for_status()
                record = response.json()
                refs = record.get('rcsb_polymer_entity_container_identifiers', {}).get('reference_sequence_identifiers', [])
                result['references'].append({'pdb_entity': entity_id, 'name': record.get('rcsb_polymer_entity', {}).get('pdbx_description'), 'search_score': hit.get('score')})
                for ref in refs:
                    accession = str(ref.get('database_accession') or '')
                    if ref.get('database_name') == 'UniProt' and re.fullmatch(r'[A-Z0-9]{6,10}', accession) and accession not in accessions:
                        accessions.append(accession)
        for accession in accessions[:2]:
            response = await client.get(f'https://rest.uniprot.org/uniprotkb/{accession}.json')
            response.raise_for_status()
            protein = response.json()
            reference_sequence = protein.get('sequence', {}).get('value', '').upper()
            offset = reference_sequence.find(sequence)
            exact = offset >= 0 and reference_sequence.count(sequence) == 1
            description = protein.get('proteinDescription', {}).get('recommendedName') or {}
            name = (description.get('fullName') or {}).get('value')
            result['references'].append({'uniprot_id': accession, 'protein_name': name,
                'reviewed': protein.get('entryType') == 'UniProtKB reviewed (Swiss-Prot)',
                'input_sequence_verified': exact, 'input_start_in_reference': offset+1 if exact else None})
            if not exact:
                result['limitations'].append(f'{accession}: reference differs from input; functional positions were not transferred.')
                continue
            from app.services.interpro_live import InterProLiveClient
            interpro = await InterProLiveClient(enabled=True, timeout_seconds=8.0).resolve_annotations(uniprot_id=accession, sequence=sequence)
            annotations = []
            for item in interpro.get('annotations', []):
                # Use family-level records only when their annotated span covers
                # at least 80% of this input. Domain-only matches remain domains.
                row = dict(item)
                if row.get('entry_type') == 'family':
                    regions = row.get('regions') or []
                    covered = set()
                    for region in regions:
                        start, end = region.get('start'), region.get('end')
                        if type(start) is int and type(end) is int:
                            covered.update(range(max(start, offset+1), min(end, offset+len(sequence))+1))
                    if len(covered) / len(sequence) < 0.8:
                        continue
                annotations.append(row)
            residues = []
            for feature in protein.get('features', []):
                if feature.get('type') not in {'Active site', 'Binding site'}:
                    continue
                location = feature.get('location') or {}
                start = (location.get('start') or {}).get('value')
                end = (location.get('end') or {}).get('value')
                if type(start) is not int or start != end or not offset < start <= offset+len(sequence):
                    continue
                if not feature.get('evidences'):
                    continue
                pos = start-offset
                residues.append({'position': pos, 'residue': sequence[pos-1],
                    'role': feature.get('description') or feature['type'], 'confidence': 0.9,
                    'reference_position': start, 'evidences': feature['evidences']})
            reviewed = protein.get('entryType') == 'UniProtKB reviewed (Swiss-Prot)'
            bundle = {'query': {'uniprot_id': accession, 'sequence_sha256': digest},
                'coordinate_system': {'status': 'verified', 'method': 'unique_exact_input_subsequence', 'reference_start': offset+1},
                'record_provenance': {'source_db': 'UniProt', 'is_reviewed': reviewed, 'record_status': 'reviewed_record' if reviewed else 'unreviewed_record'},
                'protein': {'uniprot_id': accession, 'protein_name': name,
                    'ec_numbers': [{'ec': x['value'], 'primary': True} for x in description.get('ecNumbers', []) if x.get('value')]},
                'interpro': {**interpro, 'annotations': annotations},
                'catalytic_sites': {'curated_sites': [{'source': f'UniProt:{accession}', 'residues': residues}]}}
            result.update(evidence_bundle=bundle, uniprot_id=accession,
                sequence_mapping={'status': 'verified', 'reference_start': offset+1, 'input_length': len(sequence)})
            return result
    return result


async def enzyme_sequence_identity(sequence: str, uniprot_id: str = '') -> dict:
    seq = ''.join(sequence.split()).upper()
    if not 10 <= len(seq) <= 4000 or set(seq) - set('ACDEFGHIKLMNPQRSTVWY'):
        return {'status': 'blocked', 'reason': 'Invalid protein sequence', 'evidence_bundle': {}}
    uid = uniprot_id.strip().upper()
    if uid and not re.fullmatch(r'[A-Z0-9]{6,10}', uid):
        return {'status': 'blocked', 'reason': 'Invalid UniProt accession', 'evidence_bundle': {}}
    try:
        return await asyncio.wait_for(_resolve(seq, uid), timeout=35)
    except (httpx.HTTPError, asyncio.TimeoutError, ValueError, TypeError) as exc:
        return {'status': 'partial', 'evidence_level': 'research_only_identity_investigation',
            'query': {'sequence_sha256': hashlib.sha256(seq.encode()).hexdigest()},
            'evidence_bundle': {}, 'references': [], 'limitations': [f'External reference lookup unavailable: {type(exc).__name__}; exploratory analysis may continue.']}


ToolRegistry.register(name='enzyme_sequence_identity',
    description='Investigate enzyme identity via bounded RCSB sequence search, verified UniProt references and InterPro family evidence. Exact sequence mapping required before functional-site transfer; independent of NCBI BLAST jobs.',
    handler=enzyme_sequence_identity, is_async=True, category='data', timeout_seconds=40,
    parameters={'type': 'object', 'properties': {'sequence': {'type': 'string'}, 'uniprot_id': {'type': 'string'}}, 'required': ['sequence']})
