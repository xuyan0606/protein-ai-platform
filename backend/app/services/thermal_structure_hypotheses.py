"""Bounded packing probes from measured coordinate features, never efficacy claims."""
from __future__ import annotations

import hashlib
import math


def packing_probes(sequence: str, pdb_data: str, mapping: dict, risks: dict,
                   protected: set, evidence: dict | None, limit: int = 60) -> list[dict]:
    """Propose one conservative hydrophobic substitution per buried position.

    SASA and contacts select sites for a model screen, not stabilizing changes.
    Larger/smaller side chains still need rotamer/clash and function review.
    No B-factor interpretation, inferred conservation, or invented ddG is used.
    """
    digest = hashlib.sha256(pdb_data.encode()).hexdigest()
    if not evidence or evidence.get('structure_sha256') != digest:
        return []
    reverse = {key: pos for pos, key in mapping.items()}
    atoms = {}
    from app.services.structure_records import pdb_records
    records, models, _ = pdb_records(pdb_data)
    for atom in records:
        if atom['model_id'] != models[0] or atom['occupancy'] <= 0 or atom['altloc'] not in {'', 'A'}:
            continue
        key = (atom['chain_id'], atom['residue_number'], atom.get('insertion_code') or None)
        atoms.setdefault(key, set()).add(atom['atom_name'])
    expected = {'A': {'N', 'CA', 'C', 'O', 'CB'},
                'V': {'N', 'CA', 'C', 'O', 'CB', 'CG1', 'CG2'},
                'I': {'N', 'CA', 'C', 'O', 'CB', 'CG1', 'CG2', 'CD1'},
                'L': {'N', 'CA', 'C', 'O', 'CB', 'CG', 'CD1', 'CD2'},
                'M': {'N', 'CA', 'C', 'O', 'CB', 'CG', 'SD', 'CE'}}
    alternatives = {'A': 'V', 'V': 'I', 'I': 'V', 'L': 'I', 'M': 'L'}
    probes = {}
    for row in evidence.get('features') or []:
        if not isinstance(row, dict):
            continue
        key = (row.get('chain_id'), row.get('pdb_residue_no'), row.get('insertion_code') or None)
        pos = reverse.get(key)
        if not pos or pos in protected or risks.get(pos):
            continue
        wt = sequence[pos-1]
        if wt not in alternatives or row.get('wild_type') != wt:
            continue
        sasa, contacts = row.get('rel_sasa'), row.get('contact_count_ca_8a')
        if (row.get('rel_sasa_status') != 'computed_from_input_pdb'
                or row.get('rel_sasa_source') != 'biopython_shrake_rupley_tien_max_asa'
                or type(sasa) not in (int, float) or not math.isfinite(sasa) or not 0 <= sasa <= .2
                or type(contacts) is not int or contacts < 6
                or row.get('atom_count', 0) < len(expected[wt])
                or not expected[wt].issubset(atoms.get(key, set()))
                or row.get('is_catalytic') or row.get('is_protected')):
            continue
        distance = row.get('nearest_nonpolymer_heteroatom_distance_angstrom')
        if isinstance(distance, (int, float)) and distance <= 6:
            continue
        code = f'{wt}{pos}{alternatives[wt]}'
        probes[pos] = {'mutation': code, 'rationale': '埋藏疏水位点的保守侧链堆积探针；方向由独立评分复核，不代表已发现空腔或增稳。',
                       'sources': [{'kind': 'coordinate_packing_probe',
                                    'reference': 'build_site_structure_function_features',
                                    'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest(),
                                    'structure_sha256': digest, 'rule_version': 'buried_hydrophobic_probe_v1',
                                    'features': {k: row.get(k) for k in ('rel_sasa', 'rel_sasa_source',
                                        'contact_count_ca_8a', 'atom_count', 'secondary_structure',
                                        'nearest_nonpolymer_heteroatom_distance_angstrom')}}]}
    # Deterministic spatially diverse pool; no uncalibrated heuristic score.
    positions = sorted(probes)
    if len(positions) > limit:
        positions = [positions[round(i*(len(positions)-1)/(limit-1))] for i in range(limit)]
    return [probes[p] for p in positions]
