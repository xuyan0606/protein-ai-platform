"""Prevent automatic A>V probe enrichment from masquerading as broad screening."""
from collections import Counter
import copy
import hashlib
import math

import pytest

from app.services import thermal_structure_hypotheses as hypotheses


NAMES = {
    'A': ('ALA', ['N', 'CA', 'C', 'O', 'CB']),
    'V': ('VAL', ['N', 'CA', 'C', 'O', 'CB', 'CG1', 'CG2']),
    'I': ('ILE', ['N', 'CA', 'C', 'O', 'CB', 'CG1', 'CG2', 'CD1']),
    'L': ('LEU', ['N', 'CA', 'C', 'O', 'CB', 'CG', 'CD1', 'CD2']),
    'M': ('MET', ['N', 'CA', 'C', 'O', 'CB', 'CG', 'SD', 'CE']),
}


def atom(serial, name, residue, pos, xyz, chain='A'):
    return (f'ATOM  {serial:5d} {name:^4} {residue} {chain}{pos:4d}    '
            f'{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 20.00           C')


def fixture(sequence, blocked=False):
    lines, features, mapping = [], [], {}
    backbone = {'N': (1.2, 0., -.6), 'CA': (0., 0., 0.),
                'C': (-1.2, 0., -.6), 'O': (-2.1, 0., -1.), 'CB': (0., 0., 1.53)}
    for pos, aa in enumerate(sequence, 1):
        name, atoms = NAMES[aa]
        for j, label in enumerate(atoms):
            xyz = backbone.get(label, (1.4, float(j), 2.))
            xyz = (xyz[0] + pos * 20, xyz[1], xyz[2])
            lines.append(atom(len(lines) + 1, label, name, pos, xyz))
        features.append({'chain_id': 'A', 'pdb_residue_no': pos, 'wild_type': aa,
            'rel_sasa': .1, 'rel_sasa_status': 'computed_from_input_pdb',
            'rel_sasa_source': 'biopython_shrake_rupley_tien_max_asa',
            'contact_count_ca_8a': 8, 'atom_count': len(atoms)})
        mapping[pos] = ('A', pos, None)
    if blocked:
        # A dense external carbon shell around the added valine methyl positions.
        # Any ordinary valine rotamer has a severe clash; no cavity is implied.
        for i in range(12):
            angle = i * math.pi / 6
            lines.append(atom(len(lines) + 1, 'CA', 'GLY', i + 100,
                              (20 + 1.44 * math.cos(angle), 1.44 * math.sin(angle), 2.04), 'B'))
    pdb = '\n'.join(lines) + '\nEND\n'
    evidence = {'structure_sha256': hashlib.sha256(pdb.encode()).hexdigest(), 'features': features}
    return pdb, mapping, evidence


def probes(sequence, limit=60, blocked=False):
    pdb, mapping, evidence = fixture(sequence, blocked)
    return hypotheses.packing_probes(sequence, pdb, mapping, {}, set(), evidence, limit)


def test_dense_environment_does_not_generate_alanine_to_valine_probe():
    assert not probes('A', blocked=True)


def test_open_alanine_probe_records_actual_geometric_screen_without_cavity_claim():
    rows = probes('A')
    assert len(rows) == 1 and rows[0]['mutation'] == 'A1V'
    geometry = rows[0]['sources'][0]['geometry_screen']
    assert geometry['rotamers_tested'] == 3
    assert geometry['rotamers_without_severe_overlap'] > 0
    assert geometry['mutant_relaxed'] is False
    assert geometry['cavity_detected'] is False


def test_generation_limit_is_balanced_across_available_substitution_types():
    rows = probes('A' * 30 + 'VILM' * 5, limit=12)
    counts = Counter(r['mutation'][0] + '>' + r['mutation'][-1] for r in rows)
    assert len(rows) == 12
    assert counts['A>V'] <= 4
    assert len(counts) >= 4
    assert any(r['mutation'].startswith('L') and r['mutation'].endswith('V') for r in rows)


def test_balanced_generation_preserves_coverage_across_input_sequence():
    rows = probes('L' * 80, limit=12)
    positions = {r['position'] for r in rows}
    assert min(positions) <= 5
    assert max(positions) >= 75
    assert len(positions) >= 4


def candidate(code, score, generated=True):
    return {'mutation': code, 'position': int(code[1:-1]), 'risks': [],
        'scores': {'ddgun': {'ddg': score}, 'esm_preference': {'score': score}},
        'pareto_layer': 1,
        'sources': [{'kind': 'coordinate_packing_probe' if generated else 'explicit_unscored_hypothesis'}]}


def test_high_ddgun_alanine_pool_cannot_take_nine_of_twelve_selected_positions():
    rows = [candidate(f'A{i}V', 100 - i) for i in range(1, 15)]
    rows += [candidate(f'L{i}I', 10.) for i in range(15, 19)]
    rows += [candidate(f'I{i}V', 10.) for i in range(19, 23)]
    before = copy.deepcopy(rows)
    selected, audit = hypotheses.select_diverse_candidates(rows, 12)
    assert len(selected) == 12
    assert Counter(r['mutation'][0] + '>' + r['mutation'][-1] for r in selected) == {
        'A>V': 4, 'L>I': 4, 'I>V': 4}
    assert len({r['position'] for r in selected}) == 12
    assert rows == before  # scores and Pareto evidence are not rewritten for diversity.
    assert audit['selected_substitution_counts']['A>V'] == 4


def test_single_route_reports_shortfall_instead_of_filling_with_repeated_probes():
    selected, audit = hypotheses.select_diverse_candidates(
        [candidate(f'A{i}V', 100 - i) for i in range(1, 20)], 12)
    assert len(selected) == 4
    assert audit['shortfall'] == 8
    assert audit['substitution_cap_applied'] is True


def test_intentionally_supplied_substitutions_are_not_subject_to_auto_probe_cap():
    selected, audit = hypotheses.select_diverse_candidates(
        [candidate(f'A{i}V', 100 - i, generated=False) for i in range(1, 13)], 12)
    assert len(selected) == 12
    assert audit['substitution_cap_applied'] is False


def test_diversity_does_not_backfill_with_ddgun_adverse_automatic_probes():
    rows = [candidate(f'A{i}V', 2.) for i in range(1, 13)]
    rows += [candidate('L20I', -1.), candidate('I21V', -2.)]
    selected, audit = hypotheses.select_diverse_candidates(rows, 12)
    assert len(selected) == 4
    assert audit['shortfall'] == 8
    assert {r['mutation'] for r in audit['adverse_ddgun_exclusions']} == {'L20I', 'I21V'}


@pytest.mark.parametrize('blocked', [False, True])
def test_valine_overlap_screen_is_invariant_to_rigid_motion(blocked):
    pdb, mapping, evidence = fixture('A', blocked)
    transformed = []
    for line in pdb.splitlines():
        if line.startswith('ATOM'):
            x, y, z = (float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54)))
            line = line[:30] + f'{-y+10:8.3f}{x-20:8.3f}{z+5:8.3f}' + line[54:]
        transformed.append(line)
    rotated = '\n'.join(transformed) + '\n'
    changed = {**evidence, 'structure_sha256': hashlib.sha256(rotated.encode()).hexdigest()}
    actual = hypotheses.packing_probes('A', rotated, mapping, {}, set(), changed)
    assert [r['mutation'] for r in actual] == ([] if blocked else ['A1V'])


@pytest.mark.parametrize('limit', [1, 2])
def test_small_generation_limits_are_bounded_and_do_not_divide_by_zero(limit):
    assert len(probes('LLL', limit)) <= limit


@pytest.mark.asyncio
async def test_actual_workflow_applies_diversity_after_scoring_and_reports_distribution(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    sequence = 'A' * 20 + 'L' * 10 + 'I' * 10
    pdb, _, evidence = fixture(sequence)

    async def features(**kwargs):
        return {**evidence, 'status': 'completed'}

    async def ddgun(seq, codes):
        # Favor A>V strongly to reproduce the old post-score enrichment.
        return {'status': 'completed', 'algorithm_commit': 'test', 'database_version': 'test',
                'predictions': [{'mutation': code, 'ddg': 10. if code[0] == 'A' else 1.,
                                 'unit': 'kcal/mol'} for code in codes]}

    monkeypatch.setattr('app.tools.site_structure_function_features.build_site_structure_function_features', features)
    monkeypatch.setattr('app.tools.thermostability_adapters.ddgun_predict', ddgun)
    result = await thermostability_candidate_workflow(sequence, pdb_data=pdb,
        analysis_mode='exploration', run_ddgun=True, assay_budget=12)
    selected = result['preliminary_candidates']
    assert len(selected) == 12
    assert sum(r['mutation'][0] == 'A' and r['mutation'][-1] == 'V' for r in selected) <= 4
    assert result['selection_audit']['selected_substitution_counts']['A>V'] <= 4
    assert result['probe_generation_audit']['returned_probes'] >= 12
    assert result['branches']['ddgun']['status'] == 'completed'
    assert result['candidates'] == [] and result['experimental_plan'] == {}
    assert '同类替换' in result['report_markdown']
