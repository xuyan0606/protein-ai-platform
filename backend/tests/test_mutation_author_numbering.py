"""Actual scorer output must retain input positions and PDB author insertion codes."""
import pytest

from app.tools.mutation_priority_score import mutation_priority_score
from app.core.agent_graph import AgentOrchestrator, PlanStep


async def score(mapping):
    return await mutation_priority_score(
        sequence='MKTIIALSYIFCLVFADYKDDDDK', chain_id='B',
        sequence_provenance='pdb_coordinate_derived', pdb_coordinate_mapping=mapping,
        identity_profile={'identity_status': 'identified', 'guardrail': {'status': 'ready'}},
        objective_module_plan={'status': 'ready', 'candidate_output_allowed': True},
        include_lipase_evidence=False,
    )


@pytest.mark.parametrize('row', [
    {'source_position': 2, 'source_scheme': 'coordinate_sequence', 'target_position': 105,
     'target_scheme': 'pdb_author', 'target_chain_id': 'B', 'target_insertion_code': 'A',
     'target_residue_aa': 'K'},
    {'user_sequence_position': 2, 'pdb_residue_no': 105, 'chain_id': 'B',
     'insertion_code': 'A', 'residue_aa': 'K'},
])
async def test_non_one_start_author_mapping_is_retained_by_actual_scorer(row):
    result = await score([row])
    site = next(item for item in result['all_positions'] if item['position'] == 2)
    assert site['pdb_position'] == 'B:105A'
    assert site['user_position'] == 2
    assert site['uniprot_position'] is None


@pytest.mark.parametrize('row', [
    {'source_position': 2, 'target_position': 105, 'target_chain_id': 'C', 'target_residue_aa': 'K'},
    {'source_position': 2, 'target_position': 105, 'target_chain_id': 'B', 'target_residue_aa': 'A'},
    {'pdb_residue_no': 2, 'chain_id': 'B', 'residue_aa': 'K'},
    {'uniprot_position': 2, 'pdb_residue_no': 105, 'chain_id': 'B', 'residue_aa': 'K'},
    {'source_position': 2, 'source_scheme': 'uniprot', 'target_position': 105,
     'target_chain_id': 'B', 'target_residue_aa': 'K'},
])
async def test_other_chain_wrong_wt_or_missing_source_does_not_create_a_mapping(row):
    result = await score([row])
    site = next(item for item in result['all_positions'] if item['position'] == 2)
    assert site['pdb_position'] is None


@pytest.mark.parametrize('author_number', [0, -2])
async def test_zero_and_negative_author_numbers_are_preserved(author_number):
    result = await score([{'coordinate_sequence_position': 2, 'pdb_residue_no': author_number,
                           'chain_id': 'B', 'residue_aa': 'K'}])
    site = next(item for item in result['all_positions'] if item['position'] == 2)
    assert site['pdb_position'] == f'B:{author_number}'


async def test_conflicting_author_mappings_do_not_choose_one_arbitrarily():
    result = await score([
        {'coordinate_sequence_position': 2, 'pdb_residue_no': author_number,
         'chain_id': 'B', 'residue_aa': 'K'} for author_number in [105, 106, 105]
    ])
    site = next(item for item in result['all_positions'] if item['position'] == 2)
    assert site['pdb_position'] is None


@pytest.mark.parametrize('change', [None, {'found': False}, {'status': 'blocked'},
                                  {'source': 'coordinate_order'}, {'mapping_count': 1},
                                  {'numbering_registry_status': 'blocked'}])
def test_coordinate_candidate_requires_terminal_exact_mapping(change):
    params = {'pdb_object_name': 'uploads/user_9/test.pdb', 'chain_id': 'B'}
    candidate = PlanStep(2, 'mutation_priority_score', 'rank', {**params, 'sequence': 'MK'})
    payload = {'found': True, 'status': 'completed', 'source': 'input_sequence_exact_coordinate_mapping',
               'mapping_count': 2, 'numbering_registry_status': 'ready', 'sequence_match': {'status': 'exact'}}
    payload.update(change or {})
    mapping = PlanStep(1, 'residue_mapping_sifts', 'map', params, status='completed', result=payload)
    assert AgentOrchestrator._coordinate_mapping_gate_passed(candidate, [mapping]) is (change is None)


def test_other_chain_mapping_cannot_satisfy_coordinate_candidate_gate():
    candidate = PlanStep(2, 'mutation_priority_score', 'rank', {
        'pdb_object_name': 'uploads/user_9/test.pdb', 'chain_id': 'B', 'sequence': 'MK'})
    mapping = PlanStep(1, 'residue_mapping_sifts', 'map', {
        'pdb_object_name': 'uploads/user_9/test.pdb', 'chain_id': 'C'}, status='completed', result={
        'found': True, 'status': 'completed', 'source': 'input_sequence_exact_coordinate_mapping',
        'mapping_count': 2, 'numbering_registry_status': 'ready', 'sequence_match': {'status': 'exact'}})
    assert not AgentOrchestrator._coordinate_mapping_gate_passed(candidate, [mapping])


def _aligned_mapping_step(sequence_length, change=None):
    params = {'pdb_object_name': 'uploads/user_9/test.pdb', 'chain_id': 'B'}
    payload = {
        'found': True, 'status': 'completed', 'source': 'input_sequence_global_alignment',
        'mapping_count': sequence_length, 'numbering_registry_status': 'ready',
        'coordinate_systems': ['user_sequence', 'pdb_author'],
        'sequence_match': {'status': 'aligned', 'identity': 23 / 24, 'coverage': 1.0},
        'unmapped_input_positions': [],
    }
    payload.update(change or {})
    return PlanStep(1, 'residue_mapping_sifts', 'map', params, status='completed', result=payload)


@pytest.mark.parametrize('change', [
    None,
    # A truncated FASTA covers one position fewer than the model has residues.
    {'mapping_count': 23},
    {'found': False},
    {'status': 'blocked'},
    {'numbering_registry_status': 'blocked'},
    {'source': 'coordinate_order'},
    {'sequence_match': {'status': 'exact'}},
    # Half-mapped input would silently renumber the clone.
    {'unmapped_input_positions': [3]},
    {'coordinate_systems': ['coordinate_sequence', 'pdb_author']},
])
def test_aligned_fasta_candidate_requires_ready_alignment_mapping(change):
    sequence = 'MKTIIALSYIFCLVFADYKDDDDK'
    candidate = PlanStep(2, 'mutation_priority_score', 'rank', {
        'pdb_object_name': 'uploads/user_9/test.pdb', 'chain_id': 'B', 'sequence': sequence,
        'sequence_provenance': 'user_fasta_aligned'})
    mapping = _aligned_mapping_step(len(sequence), change)
    assert AgentOrchestrator._coordinate_mapping_gate_passed(candidate, [mapping]) is (change is None)


async def test_aligned_substitution_site_keeps_its_author_coordinate():
    # The input FASTA has I at position 4 where the structure has L — the very
    # reason the alignment path exists. The projection is valid and the author
    # number must survive; dropping it would erase the bracketed coordinate the
    # user came for.
    result = await score([{
        'source_scheme': 'user_sequence', 'source_position': 4,
        'source_residue_aa': 'I', 'target_scheme': 'pdb_author',
        'target_position': 104, 'target_chain_id': 'B', 'target_residue_aa': 'L',
    }])
    site = next(item for item in result['all_positions'] if item['position'] == 4)
    assert site['pdb_position'] == 'B:104'


async def test_row_without_source_residue_still_requires_wild_type_match():
    # Position 6 of the model is A; a row claiming I there cannot be tied to the
    # input residue, so the conservative wild-type check stays in force.
    result = await score([{
        'source_position': 6, 'target_position': 106,
        'target_chain_id': 'B', 'target_residue_aa': 'I',
    }])
    site = next(item for item in result['all_positions'] if item['position'] == 6)
    assert site['pdb_position'] is None


async def test_unrequested_chain_filter_does_not_drop_the_mapping():
    # Without an explicit chain the scorer must accept the rows' own chain; the
    # old "A" default silently discarded chain-B mappings while the gate passed.
    result = await mutation_priority_score(
        sequence='MKTIIALSYIFCLVFADYKDDDDK',
        sequence_provenance='user_fasta_aligned',
        pdb_coordinate_mapping=[{
            'source_scheme': 'user_sequence', 'source_position': 4,
            'source_residue_aa': 'I', 'target_scheme': 'pdb_author',
            'target_position': 104, 'target_chain_id': 'B', 'target_residue_aa': 'I',
        }],
        identity_profile={'identity_status': 'identified', 'guardrail': {'status': 'ready'}},
        objective_module_plan={'status': 'ready', 'candidate_output_allowed': True},
        include_lipase_evidence=False,
    )
    site = next(item for item in result['all_positions'] if item['position'] == 4)
    assert site['pdb_position'] == 'B:104'


def test_plan_contract_reports_sequence_structure_conflict():
    from app.services.tool_orchestration_contract import validate_tool_plan

    plan = [{'tool_name': 'predict_properties', 'params': {}}]
    base = {'has_sequence': True, 'has_pdb': True}
    clean = validate_tool_plan(plan, evidence=base)
    assert clean['allowed'] is True

    conflicted = validate_tool_plan(plan, evidence={**base, 'sequence_structure_conflict': True})
    assert conflicted['allowed'] is False
    assert 'sequence_structure_conflict' in {item['code'] for item in conflicted['violations']}

    unavailable = validate_tool_plan(plan, evidence={**base, 'pdb_sequence_unavailable': True})
    assert 'pdb_sequence_unavailable' in {item['code'] for item in unavailable['violations']}


def test_aligned_fasta_candidate_gate_rejects_missing_mapping_step():
    candidate = PlanStep(2, 'mutation_priority_score', 'rank', {
        'pdb_object_name': 'uploads/user_9/test.pdb', 'chain_id': 'B',
        'sequence': 'MKTIIALSYIFCLVFADYKDDDDK', 'sequence_provenance': 'user_fasta_aligned'})
    assert not AgentOrchestrator._coordinate_mapping_gate_passed(candidate, [])
