"""Thermal workflow inputs must belong to the same sequence, input and chain."""
import copy
import hashlib

import pytest

from app.core.agent_graph import AgentOrchestrator, PlanStep, _PDB_REQUIRED_TOOLS, _SEQUENCE_REQUIRED_TOOLS


SEQUENCE = 'ACD'
SCOPE = {'sequence': SEQUENCE, 'input_id': 'pdb:current',
         'pdb_object_name': 'uploads/user_1/current.pdb', 'chain_id': 'B'}


def step(tool, params=None, result=None, status='completed'):
    return PlanStep(1, tool, tool, params=copy.deepcopy(SCOPE if params is None else params),
                    result=result, status=status)


def thermal(params=None):
    return step('thermostability_candidate_workflow', params, status='pending')


def pdb_chain(chain, residues):
    return '\n'.join(
        f'ATOM  {i:5d}  CA  {residue:3s} {chain}{i:4d}    '
        f'{float(i):8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{20.:6.2f}           C'
        for i, residue in enumerate(residues, 1)
    )


def test_hydrates_only_matching_identity_and_objective_without_inventing_assay():
    target = thermal({**SCOPE, 'objective': {'goal': 'thermostability', 'user_notes': 'no assay supplied'}})
    identity = {'query': {'sequence_sha256': hashlib.sha256(SEQUENCE.encode()).hexdigest()},
                'identity_status': 'identified'}
    objective = {'status': 'blocked', 'missing_evidence': ['assay']}
    previous = [step('enzyme_identity_profile', {**SCOPE, 'sequence': 'a c\nd'}, identity),
                step('enzyme_objective_module_plan', result=objective, status='blocked')]
    AgentOrchestrator()._bridge_step_params(target, previous)
    assert target.params['identity_profile'] == identity
    assert target.params['objective_module_plan'] == objective
    assert target.params['objective'] == {'goal': 'thermostability', 'user_notes': 'no assay supplied'}
    assert not any(key in target.params for key in ['assay_context', 'ph', 'temperature', 'tm'])
    target.params['identity_profile']['identity_status'] = 'changed'
    assert identity['identity_status'] == 'identified'


@pytest.mark.parametrize('replacement', [
    {'sequence': 'ACE'}, {'sequence': ''}, {'input_id': 'pdb:foreign'},
    {'input_id': None}, {'pdb_object_name': 'uploads/user_1/foreign.pdb'},
    {'chain_id': 'A'}, {'chain_id': None}, {'model_id': 2},
])
def test_foreign_or_missing_identity_scope_cannot_hydrate(replacement):
    target = thermal()
    previous = step('enzyme_identity_profile', {**SCOPE, **replacement}, {'identity_status': 'identified'})
    AgentOrchestrator._hydrate_step_params(target, [previous])
    assert 'identity_profile' not in target.params


def test_heuristic_scan_only_supplies_valid_hypotheses_without_ddg():
    target = thermal()
    scan = step('mutation_scan', result={'status': 'completed', 'results': [{
        'position': 1, 'top_stabilizing': [
            {'mutation': 'A1V', 'ddg_kcal_mol': -99, 'esm_score': 5},
            {'mutation': 'C1V'}, {'mutation': 'A1A'}, {'mutation': 'A4V'},
            {'mutation': 'A1X'}, {'mutation': 'A1V'},
        ],
    }]})
    foreign = step('mutation_scan', {**SCOPE, 'chain_id': 'A'}, {'results': [{
        'top_stabilizing': [{'mutation': 'C2A'}],
    }]})
    AgentOrchestrator._hydrate_step_params(target, [scan, foreign])
    assert target.params['candidate_sources'] == [{
        'kind': 'structure', 'reference': 'mutation_scan',
        'sequence_sha256': hashlib.sha256(SEQUENCE.encode()).hexdigest(),
        'mutations': ['A1V'], 'evidence_level': 'design_hypothesis',
    }]


def test_selects_current_chain_coordinates_and_rejects_other_input():
    source = pdb_chain('A', ['GLY', 'GLY', 'GLY']) + '\n' + pdb_chain('B', ['ALA', 'CYS', 'ASP'])
    target = thermal()
    structure_params = {key: value for key, value in SCOPE.items() if key not in {'sequence', 'chain_id'}}
    foreign = step('structure_search_foldseek', {**structure_params, 'input_id': 'pdb:foreign'},
                   {'pdb_content': pdb_chain('B', ['GLY', 'GLY', 'GLY'])})
    current = step('structure_search_foldseek', structure_params, {'pdb_content': source})
    AgentOrchestrator._hydrate_step_params(target, [current, foreign])
    from app.services.pdb_parser import parse_pdb
    parsed = parse_pdb(target.params['pdb_data'])
    assert [(chain['chain_id'], chain['sequence']) for chain in parsed['chains']] == [('A', 'GGG'), ('B', SEQUENCE)]
    assert target.params['chain_id'] == 'B'
    assert target.params['sequence'] == SEQUENCE


@pytest.mark.parametrize('change', [{'chain_id': 'Z'}, {'sequence': 'ACE'}])
def test_missing_chain_or_coordinate_sequence_mismatch_never_falls_back(change):
    target = thermal({**SCOPE, **change})
    structure_params = {key: value for key, value in SCOPE.items() if key not in {'sequence', 'chain_id'}}
    current = step('structure_search_foldseek', structure_params,
                   {'pdb_content': pdb_chain('B', ['ALA', 'CYS', 'ASP'])})
    AgentOrchestrator._hydrate_step_params(target, [current])
    assert 'pdb_data' not in target.params


def test_sequence_only_branch_has_no_pdb_requirement_or_foreign_identity():
    target = thermal({'sequence': SEQUENCE})
    AgentOrchestrator._hydrate_step_params(target, [step('enzyme_identity_profile', result={'identity_status': 'identified'})])
    assert 'identity_profile' not in target.params
    assert 'pdb_data' not in target.params
    assert 'thermostability_candidate_workflow' in _SEQUENCE_REQUIRED_TOOLS
    assert 'thermostability_candidate_workflow' not in _PDB_REQUIRED_TOOLS
