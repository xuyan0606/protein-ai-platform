"""Bounded packing probes from measured coordinate features, never efficacy claims."""
from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict, deque


def _substitution_type(row: dict) -> str:
    code = row['mutation']
    return f'{code[0]}>{code[-1]}'


def select_diverse_candidates(rows: list[dict], budget: int, *, unique_positions: bool = True,
                              exclude_adverse_ddgun: bool = True) -> tuple[list[dict], dict]:
    """Constrain automatic probe enrichment without changing independent scores.

    One substitution type can occupy at most a third (rounded up) of the
    requested automatic screen. Insufficient diversity produces a shortfall;
    it never authorizes invented alternatives or relaxed protection filters.
    Explicit-only requests retain their requested substitution distribution.
    """
    automatic = any(any(s.get('kind') == 'coordinate_packing_probe' for s in r.get('sources', [])) for r in rows)
    cap = max(1, math.ceil(budget / 3)) if automatic else budget
    selected, seen, counts, adverse = [], set(), Counter(), []
    decisions = []
    for row in rows:
        kind = _substitution_type(row)
        generated = any(s.get('kind') == 'coordinate_packing_probe' for s in row.get('sources', []))
        ddgun = (row.get('scores') or {}).get('ddgun') or {}
        ddg = ddgun.get('ddg')
        if generated and type(ddg) in (int, float) and math.isfinite(ddg) and ddg < 0:
            adverse.append({'mutation': row['mutation'], 'predicted_ddg': ddg,
                            'reason': 'adverse_ddgun_not_used_for_diversity_backfill' if exclude_adverse_ddgun
                                      else 'adverse_ddgun_retained_for_manual_review'})
            if exclude_adverse_ddgun:
                decisions.append({'mutation':row['mutation'],'decision':'not_displayed','reason':'adverse_ddgun_policy'})
                continue
        reason = ('display_budget_exhausted' if len(selected)>=budget else
                  'position_already_selected' if unique_positions and row['position'] in seen else
                  'substitution_type_cap' if counts[kind]>=cap else None)
        if reason:
            decisions.append({'mutation':row['mutation'],'decision':'not_displayed','reason':reason})
            continue
        selected.append(row)
        seen.add(row['position'])
        counts[kind] += 1
        decisions.append({'mutation':row['mutation'],'decision':'displayed','reason':'within_display_budget'})
    return selected, {
        'rule_version': 'automatic_probe_substitution_cap_v1',
        'substitution_cap_applied': automatic, 'max_per_substitution_type': cap,
        'pool_substitution_counts': dict(Counter(_substitution_type(r) for r in rows)),
        'selected_substitution_counts': dict(counts), 'shortfall': max(0, budget - len(selected)),
        'model_hard_filter_applied': exclude_adverse_ddgun,
        'adverse_ddgun_exclusions': adverse if exclude_adverse_ddgun else [],
        'adverse_ddgun_review': [] if exclude_adverse_ddgun else adverse,
        'candidate_decisions': decisions,
        'decision_counts': dict(Counter(r['decision'] for r in decisions)),
        'meaning': '候选覆盖约束，不是成功率或效能评分；不足时不放宽上限补位。',
    }


def _alanine_valine_geometry(key: tuple, atoms: dict, environment: list[dict]) -> dict | None:
    """Screen three idealized valine chi1 rotamers against fixed heavy atoms.

    This rejects severe overlaps; it is neither rotamer refinement nor cavity
    detection. CA/CB are 1-3 bonded neighbours of CG and are not nonbonded tests.
    """
    def unit(vector):
        length = math.sqrt(sum(x*x for x in vector))
        return tuple(x/length for x in vector) if length > 1e-8 else None

    ca, cb, n = (atoms[name]['coordinates'] for name in ('CA', 'CB', 'N'))
    axis = unit(tuple(a-b for a, b in zip(ca, cb)))
    if axis is None:
        return None
    reference = tuple(a-b for a, b in zip(n, ca))
    projection = sum(a*b for a, b in zip(reference, axis))
    u = unit(tuple(a-projection*b for a, b in zip(reference, axis)))
    if u is None:
        return None
    v = (axis[1]*u[2]-axis[2]*u[1], axis[2]*u[0]-axis[0]*u[2], axis[0]*u[1]-axis[1]*u[0])
    neighbours = []
    for atom in environment:
        atom_key = (atom['chain_id'], atom['residue_number'], atom.get('insertion_code') or None)
        if atom_key == key and atom['atom_name'] in {'CA', 'CB'}:
            continue
        if math.dist(cb, atom['coordinates']) > 5.5:
            continue
        element = atom['element'] or atom['atom_name'].lstrip('0123456789')[:1]
        radius = {'C': 1.70, 'N': 1.55, 'O': 1.52, 'S': 1.80, 'P': 1.80}.get(element, 1.80)
        neighbours.append((atom['coordinates'], radius))
    theta = math.radians(109.5)
    clearances = []
    for chi in (-60, 60, 180):
        methyls = []
        for phase in (chi, chi + 120):
            phi = math.radians(phase)
            methyls.append(tuple(cb[i] + 1.53 * (math.cos(theta)*axis[i] + math.sin(theta)*(
                math.cos(phi)*u[i] + math.sin(phi)*v[i])) for i in range(3)))
        clearance = min((math.dist(cg, xyz)-1.70-radius for cg in methyls for xyz, radius in neighbours), default=None)
        clearances.append(clearance)
    passing = [value for value in clearances if value is None or value >= -0.6]
    return {'method': 'three_idealized_valine_chi1_fixed_environment_v1',
            'rotamers_tested': 3, 'rotamers_without_severe_overlap': len(passing),
            'severe_vdw_overlap_cutoff_angstrom': 0.6,
            'best_minimum_vdw_clearance_angstrom': round(max(x for x in clearances if x is not None), 3)
                if any(x is not None for x in clearances) else None,
            'environment': 'first_model_nonwater_heavy_atoms_including_other_chains',
            'mutant_relaxed': False, 'cavity_detected': False}


def packing_probes(sequence: str, pdb_data: str, mapping: dict, risks: dict,
                   protected: set, evidence: dict | None, limit: int = 60,
                   audit: dict | None = None) -> list[dict]:
    """Propose a bounded, balanced set of hydrophobic repacking hypotheses.

    SASA and contacts select sites for a model screen, not stabilizing changes.
    Larger/smaller side chains still need rotamer/clash and function review.
    No B-factor interpretation, inferred conservation, or invented ddG is used.
    """
    digest = hashlib.sha256(pdb_data.encode()).hexdigest()
    if not evidence or evidence.get('structure_sha256') != digest:
        return []
    reverse = {key: pos for pos, key in mapping.items()}
    atoms, environment = {}, []
    from app.services.structure_records import pdb_records
    records, models, _ = pdb_records(pdb_data)
    for atom in records:
        if atom['model_id'] != models[0] or atom['occupancy'] <= 0 or atom['altloc'] not in {'', 'A'}:
            continue
        element = atom['element'] or atom['atom_name'].lstrip('0123456789')[:1]
        if element in {'H', 'D'} or atom['component_id'] in {'HOH', 'WAT', 'DOD'}:
            continue
        key = (atom['chain_id'], atom['residue_number'], atom.get('insertion_code') or None)
        atoms.setdefault(key, {})[atom['atom_name']] = atom
        environment.append(atom)
    expected = {'A': {'N', 'CA', 'C', 'O', 'CB'},
                'V': {'N', 'CA', 'C', 'O', 'CB', 'CG1', 'CG2'},
                'I': {'N', 'CA', 'C', 'O', 'CB', 'CG1', 'CG2', 'CD1'},
                'L': {'N', 'CA', 'C', 'O', 'CB', 'CG', 'CD1', 'CD2'},
                'M': {'N', 'CA', 'C', 'O', 'CB', 'CG', 'SD', 'CE'}}
    # Do not expand V to I without a corresponding mutant geometry screen.
    # Neutral-size/reduction probes are hypotheses, not automatic improvements.
    alternatives = {'A': ('V',), 'V': ('A',), 'I': ('V', 'L'), 'L': ('I', 'V'), 'M': ('L',)}
    probes, geometry_rejections = [], []
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
        geometry = {'method': 'not_evaluated', 'mutant_relaxed': False, 'cavity_detected': False}
        if wt == 'A':
            geometry = _alanine_valine_geometry(key, atoms[key], environment)
            if geometry is None or not geometry['rotamers_without_severe_overlap']:
                geometry_rejections.append({'mutation': f'A{pos}V', 'reason': 'no_valine_rotamer_without_severe_overlap'
                                            if geometry else 'degenerate_sidechain_frame', 'geometry_screen': geometry})
                continue
        for mt in alternatives[wt]:
            code = f'{wt}{pos}{mt}'
            probes.append({'mutation': code, 'position': pos,
                       'rationale': '埋藏疏水位点的侧链重排/尺寸探针；不是空腔检测或增稳结论，须复核突变构象与功能。',
                       'sources': [{'kind': 'coordinate_packing_probe',
                                    'reference': 'build_site_structure_function_features',
                                    'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest(),
                                    'structure_sha256': digest, 'rule_version': 'balanced_hydrophobic_probe_v2',
                                    'geometry_screen': geometry,
                                    'features': {k: row.get(k) for k in ('rel_sasa', 'rel_sasa_source',
                                        'contact_count_ca_8a', 'atom_count', 'secondary_structure',
                                        'nearest_nonpolymer_heteroatom_distance_angstrom')}}]})
    groups = defaultdict(list)
    for probe in sorted(probes, key=lambda r: (r['position'], r['mutation'])):
        groups[_substitution_type(probe)].append(probe)
    # Spread each type across the input sequence before round-robin sampling;
    # otherwise the 60-probe bound silently becomes an N-terminal scan.
    for kind, group in groups.items():
        indices = []
        spans = deque([(0, len(group)-1)])
        while spans:
            lo, hi = spans.popleft()
            if lo > hi:
                continue
            if not indices:
                indices.append(lo)
                if hi > lo:
                    indices.append(hi)
                spans.append((lo+1, hi-1))
            else:
                middle = (lo+hi)//2
                indices.append(middle)
                spans.extend([(lo, middle-1), (middle+1, hi)])
        groups[kind] = deque(group[i] for i in indices)
    balanced = []
    while any(groups.values()):
        for kind in sorted(groups):
            if groups[kind]:
                balanced.append(groups[kind].popleft())
    selected, selection = select_diverse_candidates(balanced, limit, unique_positions=False)
    if audit is not None:
        audit.update(selection, geometry_rejections=geometry_rejections, eligible_probes=len(probes),
                     returned_probes=len(selected))
    return selected
