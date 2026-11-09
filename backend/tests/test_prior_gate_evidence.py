"""Completed gates from an earlier turn may satisfy a follow-up plan, but only
for the same object.  These cases pin both the reuse and the scope boundary."""
import json

from app.core.agent_graph import AgentOrchestrator, PlanStep

SEQUENCE = 'MKTIIALSYIFCLVFADYKDDDDK'
OBJECT = 'uploads/user_9/test.pdb'


def _mapping_step_params(chain='B', object_name=OBJECT):
    return {'pdb_object_name': object_name, 'chain_id': chain}


def _checkpoint_mapping_entry(change=None):
    payload = {
        'found': True, 'status': 'completed',
        'source': 'input_sequence_exact_coordinate_mapping',
        'mapping_count': len(SEQUENCE), 'numbering_registry_status': 'ready',
        'sequence_match': {'status': 'exact'},
    }
    payload.update(change or {})
    return {
        'step': 1, 'tool': 'residue_mapping_sifts', 'status': 'completed',
        'raw_result': json.dumps(payload),
        'evidence_scope': {
            'pdb_object_name': OBJECT, 'chain_id': 'B',
            'sequence_sha256': AgentOrchestrator._step_sequence_sha256({'sequence': SEQUENCE}),
        },
    }


def _scan_step(chain='B', object_name=OBJECT):
    return PlanStep(1, 'mutation_scan', 'scan', {
        'pdb_object_name': object_name, 'chain_id': chain,
        'sequence': SEQUENCE, 'sequence_provenance': 'pdb_coordinate_derived',
    })


def test_checkpoint_summary_keeps_only_terminal_gate_payload():
    facts = AgentOrchestrator._gate_evidence_facts([
        _checkpoint_mapping_entry(),
        {'tool': 'residue_mapping_sifts', 'status': 'failed', 'raw_result': '{}'},
        {'tool': 'not_a_gate_tool', 'status': 'completed', 'raw_result': json.dumps({'found': True})},
        {'tool': 'enzyme_identity_profile', 'status': 'completed',
         'raw_result': json.dumps({'status': 'completed', 'identity_status': 'identified',
                                   'guardrail': {'status': 'ready'}})},
    ])
    assert [fact['tool'] for fact in facts] == ['residue_mapping_sifts', 'enzyme_identity_profile']
    mapping = facts[0]
    assert mapping['payload']['mapping_count'] == len(SEQUENCE)
    assert mapping['payload']['unmapped_count'] == 0
    assert 'sequence' not in mapping['payload']
    assert facts[1]['payload']['guardrail_status'] == 'ready'


def test_prior_scope_requires_a_shared_identity_key():
    mapping = AgentOrchestrator._gate_evidence_facts([_checkpoint_mapping_entry()])[0]
    assert AgentOrchestrator._prior_gate_fact([mapping], {'residue_mapping_sifts'}, _scan_step().params)
    # Chain-only overlap is not enough: without a shared object/sequence identity
    # a fact about any file could be mistaken for this turn's structure.
    assert not AgentOrchestrator._prior_gate_fact(
        [mapping], {'residue_mapping_sifts'}, {'chain_id': 'B'})
    assert not AgentOrchestrator._prior_gate_fact(
        [mapping], {'residue_mapping_sifts'}, _scan_step(chain='C').params)
    assert not AgentOrchestrator._prior_gate_fact(
        [mapping], {'residue_mapping_sifts'}, _scan_step(object_name='uploads/user_9/other.pdb').params)
    other_sequence = PlanStep(1, 'mutation_scan', 'scan', {
        'pdb_object_name': OBJECT, 'chain_id': 'B', 'sequence': 'MKTIIALSYIFCLVFADYKDDDD'} )
    assert not AgentOrchestrator._prior_gate_fact(
        [mapping], {'residue_mapping_sifts'}, other_sequence.params)


def test_prior_mapping_authorizes_scan_followup_without_rerunning_mapping():
    facts = AgentOrchestrator._gate_evidence_facts([_checkpoint_mapping_entry()])
    assert AgentOrchestrator._coordinate_mapping_gate_passed(
        _scan_step(), [], prior_facts=facts)


def test_prior_mapping_does_not_authorize_priorscore_needing_in_turn_rows():
    facts = AgentOrchestrator._gate_evidence_facts([_checkpoint_mapping_entry()])
    rank = PlanStep(1, 'mutation_priority_score', 'rank', {
        'pdb_object_name': OBJECT, 'chain_id': 'B', 'sequence': SEQUENCE,
        'sequence_provenance': 'pdb_coordinate_derived',
    })
    assert not AgentOrchestrator._coordinate_mapping_gate_passed(rank, [], prior_facts=facts)


def test_blocked_prior_mapping_does_not_authorize_scan():
    for change in ({'found': False}, {'numbering_registry_status': 'blocked'},
                   {'mapping_count': 1}, {'status': 'blocked'}):
        facts = AgentOrchestrator._gate_evidence_facts([_checkpoint_mapping_entry(change)])
        assert not AgentOrchestrator._coordinate_mapping_gate_passed(
            _scan_step(), [], prior_facts=facts), change


def test_failed_in_turn_mapping_is_not_rescued_by_prior_fact():
    facts = AgentOrchestrator._gate_evidence_facts([_checkpoint_mapping_entry()])
    failed = PlanStep(1, 'residue_mapping_sifts', 'map', _mapping_step_params(),
                      status='completed', result={'status': 'completed', 'found': False})
    assert not AgentOrchestrator._coordinate_mapping_gate_passed(
        _scan_step(), [failed], prior_facts=facts)


def test_prior_identity_authorizes_candidates_only_for_same_scope():
    facts = AgentOrchestrator._gate_evidence_facts([{
        'tool': 'enzyme_identity_profile', 'status': 'completed',
        'raw_result': json.dumps({'status': 'completed', 'identity_status': 'identified',
                                  'guardrail': {'status': 'ready'}}),
        'evidence_scope': {'pdb_object_name': OBJECT, 'chain_id': 'B'},
    }])
    assert AgentOrchestrator._identity_gate_passed(
        [], prior_facts=facts, scope_values=_scan_step().params)
    assert not AgentOrchestrator._identity_gate_passed(
        [], prior_facts=facts, scope_values=_scan_step(chain='C').params)
    assert not AgentOrchestrator._identity_gate_passed([], prior_facts=facts)


def test_preflight_seeds_gates_from_prior_evidence_of_same_object():
    facts = AgentOrchestrator._gate_evidence_facts([
        _checkpoint_mapping_entry(),
        {'tool': 'enzyme_identity_profile', 'status': 'completed',
         'raw_result': json.dumps({'status': 'completed', 'identity_status': 'identified',
                                   'guardrail': {'status': 'ready'}}),
         'evidence_scope': {'pdb_object_name': OBJECT, 'chain_id': 'B'}},
        {'tool': 'enzyme_objective_module_plan', 'status': 'completed',
         'raw_result': json.dumps({'status': 'ready', 'candidate_output_allowed': True}),
         'evidence_scope': {'pdb_object_name': OBJECT, 'chain_id': 'B'}},
    ])
    plan = [_scan_step()]
    assert AgentOrchestrator._prior_preflight_evidence(facts, plan) == {
        'has_residue_mapping': True, 'identity_ready': True, 'objective_ready': True,
    }
    assert AgentOrchestrator._prior_preflight_evidence(facts, [_scan_step(object_name='uploads/user_9/other.pdb')]) == {}
    assert AgentOrchestrator._prior_preflight_evidence(facts, []) == {}
