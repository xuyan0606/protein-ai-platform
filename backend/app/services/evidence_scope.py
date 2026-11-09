"""Bind dependencies and report sections to actual inputs, never tool names alone."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def payload_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value) if isinstance(value, str) else {}
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def evidence_scope(values: dict | None) -> dict:
    values = values or {}
    scope = dict(values.get('evidence_scope') or {})
    for key in ('pdb_object_name', 'input_id', 'content_sha256', 'chain_id', 'model_id'):
        if values.get(key) is not None and values.get(key) != '':
            scope[key] = values[key]
    model = values.get('model_scope')
    if isinstance(model, dict) and model.get('selected_model') is not None:
        scope['model_id'] = model['selected_model']
    chains = values.get('chain_scope')
    if isinstance(chains, list):
        scope['chain_scope'] = sorted(map(str, chains))
        if len(chains) == 1:
            scope.setdefault('chain_id', str(chains[0]))
    sequence = next((values[k] for k in ('sequence', 'query_sequence', 'input_sequence', 'protein_sequence') if values.get(k)), None)
    if isinstance(sequence, str):
        scope['sequence_sha256'] = hashlib.sha256(''.join(sequence.split()).upper().encode()).hexdigest()
    elif values.get('input_sequence_sha256'):
        scope['sequence_sha256'] = values['input_sequence_sha256']
    return scope


def record_scope(record: dict) -> dict:
    return {**evidence_scope(payload_dict(record.get('result'))), **evidence_scope(record)}


def scopes_match(required: dict, provided: dict, *, file_level: bool = False) -> bool:
    """Missing provenance cannot satisfy an explicitly scoped requirement."""
    for key in ('pdb_object_name', 'input_id', 'content_sha256', 'chain_id', 'model_id'):
        if key not in required:
            continue
        if key == 'chain_id' and file_level and not provided.get(key):
            continue
        if str(required[key]) != str(provided.get(key)):
            return False
    if required.get('chain_scope') and required['chain_scope'] != provided.get('chain_scope'):
        return False
    if required.get('sequence_sha256') and provided.get('sequence_sha256'):
        return required['sequence_sha256'] == provided['sequence_sha256']
    return True


def matching_steps(target: Any, steps: list) -> list:
    required = evidence_scope(target.params)
    result = []
    for step in steps:
        provided = {**evidence_scope(payload_dict(step.result)), **evidence_scope(step.params)}
        if scopes_match(required, provided, file_level=step.tool_name == 'structure_search_foldseek'):
            result.append(step)
    return result


def partition_chain_results(records: list[dict]) -> tuple[dict[str, list[dict]], list[dict], list[dict]]:
    """Separate repeated chain results before a legacy single-chain renderer runs."""
    chains = {str(record_scope(r)['chain_id']) for r in records
              if record_scope(r).get('chain_id') not in {None, '', 'all'}}
    for record in records:
        structure = payload_dict(record.get('result')).get('query_structure')
        if isinstance(structure, dict):
            chains.update(str(c['chain_id']) for c in structure.get('chains', []) if isinstance(c, dict) and c.get('chain_id'))
    if len(chains) < 2:
        return {}, records, []
    groups = {chain: [] for chain in sorted(chains)}
    shared, unknown = [], []
    for record in records:
        scope = record_scope(record)
        if str(scope.get('chain_id')) in groups:
            groups[str(scope['chain_id'])].append(record)
        elif record.get('tool_name') == 'structure_search_foldseek':
            payload = payload_dict(record.get('result'))
            structure = payload.get('query_structure')
            for chain in groups:
                if not isinstance(structure, dict):
                    continue
                selected = [c for c in structure.get('chains', []) if str(c.get('chain_id')) == chain]
                if not selected:
                    continue
                scoped_structure = {**structure, 'chains': selected,
                    'chain_count': len(selected),
                    'total_residues': sum(c.get('residue_count', 0) for c in selected),
                    'total_atoms': (sum(c['atom_count'] for c in selected)
                                    if all(c.get('atom_count') is not None for c in selected) else '未知')}
                seqres = (structure.get('seqres_by_chain') or {}).get(chain)
                if seqres is not None:
                    scoped_structure['seqres_by_chain'] = {chain: seqres}
                    scoped_structure['seqres_length'] = len(seqres) if isinstance(seqres, str) else seqres
                    scoped_structure['seqres_sequence'] = seqres if isinstance(seqres, str) else ''
                else:
                    for key in ('seqres_length', 'seqres_sequence', 'seqres_by_chain'):
                        scoped_structure.pop(key, None)
                groups[chain].append({**record, 'chain_id': chain,
                    'result': json.dumps({**payload, 'query_structure': scoped_structure}, ensure_ascii=False)})
        elif scope.get('chain_scope') and len(scope['chain_scope']) > 1:
            shared.append(record)
        else:
            unknown.append(record)
    return groups, shared, unknown
