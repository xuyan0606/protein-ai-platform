"""Coordinate evidence must reach exploratory proposals and real score branches."""
import hashlib

import pytest

from app.services.thermostability_workflow import build_screen


def structure():
    # Three separated complete leucines, author numbers 4/5/6, input 1/2/3.
    lines = []
    for pos in range(3):
        for j, name in enumerate(['N', 'CA', 'C', 'O', 'CB', 'CG', 'CD1', 'CD2']):
            lines.append(f'ATOM  {len(lines)+1:5d} {name:^4} LEU A{pos+4:4d}    '
                         f'{pos*20.+j:8.3f}{float(j%2):8.3f}{0.:8.3f}  1.00 20.00           C')
    return '\n'.join(lines)+'\nEND\n'


def features(pdb):
    return {'structure_sha256': hashlib.sha256(pdb.encode()).hexdigest(),
            'features': [{'chain_id': 'A', 'pdb_residue_no': p+4, 'wild_type': 'L',
                          'rel_sasa': 0.1, 'rel_sasa_status': 'computed_from_input_pdb',
                          'rel_sasa_source': 'biopython_shrake_rupley_tien_max_asa',
                          'contact_count_ca_8a': 8, 'atom_count': 8,
                          'nearest_nonpolymer_heteroatom_distance_angstrom': None}
                         for p in range(3)]}


def test_structure_proposals_validate_wt_author_mapping_and_protection_without_assay():
    pdb = structure()
    result = build_screen('LLL', pdb_data=pdb, structure_features=features(pdb),
                          identity_profile={'protected_positions': [2]}, analysis_mode='exploration')
    rows = result['preliminary_candidates']
    assert {r['position'] for r in rows} == {1, 3}
    assert all(r['wild_type'] == 'L' and r['mutation'][0] == 'L' for r in rows)
    assert {r['structure_position']['residue_number'] for r in rows} == {4, 6}
    assert all(r['sources'][0]['structure_sha256'] == hashlib.sha256(pdb.encode()).hexdigest() for r in rows)
    assert all(r['sources'][0]['features']['rel_sasa'] == 0.1 for r in rows)
    assert not result['candidates'] and not result['experimental_plan']


@pytest.mark.parametrize('change', ['foreign_structure', 'wrong_wt', 'ligand', 'ca_only'])
def test_invalid_or_sensitive_structure_evidence_cannot_propose_sites(change):
    pdb = structure()
    evidence = features(pdb)
    if change == 'foreign_structure':
        evidence['structure_sha256'] = 'foreign'
    for row in evidence['features']:
        if change == 'wrong_wt': row['wild_type'] = 'M'
        if change == 'ligand': row['nearest_nonpolymer_heteroatom_distance_angstrom'] = 3
        if change == 'ca_only': row['atom_count'] = 1
    result = build_screen('LLL', pdb_data=pdb, structure_features=evidence, analysis_mode='exploration')
    assert not result.get('preliminary_candidates')


@pytest.mark.asyncio
async def test_exploration_actually_scores_provided_hypotheses_without_releasing_experiments(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    async def score(sequence, codes):
        assert sequence == 'ACDEG' and codes == ['A1V']
        return {'status': 'completed', 'algorithm_commit': 'test-algorithm', 'database_version': 'test-db',
                'predictions': [{'mutation': 'A1V', 'ddg': 0.7, 'unit': 'kcal/mol'}]}
    monkeypatch.setattr('app.tools.thermostability_adapters.ddgun_predict', score)
    result = await thermostability_candidate_workflow('ACDEG', mutations=['A1V'],
                    analysis_mode='exploration', run_ddgun=True)
    assert result['branches']['ddgun']['status'] == 'completed'
    row = result['preliminary_candidates'][0]
    assert row['scores']['ddgun']['ddg'] == 0.7
    assert row['scores']['ddgun']['algorithm_commit'] == 'test-algorithm'
    assert result['candidates'] == [] and result['experimental_plan'] == {}
