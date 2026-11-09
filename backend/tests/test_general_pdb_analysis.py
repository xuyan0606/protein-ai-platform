"""Generic PDB contracts; fixtures deliberately do not depend on a PDB ID."""
from __future__ import annotations

import pytest

from app.services.structure_strategy import select_structure_strategy


TOOLS = {
    'structure_search_foldseek', 'residue_mapping_sifts', 'predict_properties',
    'enzyme_identity_profile', 'blast_search', 'build_site_structure_function_features',
    'disulfide_saltbridge_scan', 'ligand_contact_analysis',
    'structure_pocket_interface_analysis', 'pocket_residue_lookup', 'annotation_bundle',
}


def strategy(question, chains=('A',), **kwargs):
    return select_structure_strategy(
        question, {'chains': [{'chain_id': c, 'sequence': 'ACDEFGHIKLMNPQRSTVWY'} for c in chains]},
        object_name='uploads/unknown-model.pdb', tools=TOOLS, runtimes={}, **kwargs,
    )


@pytest.mark.parametrize('question', [
    '不要 BLAST，但要分析热稳定性', '不要 BLAST 但要分析热稳定性',
    "Do not use BLAST but analyze thermal stability",
])
def test_excluded_tool_keeps_positive_goal(question):
    result = strategy(question)
    names = {s['tool_name'] for s in result['steps']}
    assert 'disulfide_saltbridge_scan' in names
    assert 'blast_search' not in names


def test_deep_analysis_cannot_reintroduce_forbidden_blast():
    assert 'blast_search' not in {s['tool_name'] for s in strategy('不要 BLAST，给我深度分析')['steps']}


def test_chain_pair_is_not_reduced_to_first_regex_match():
    result = strategy('分析链 A 和链 B 的界面', chains=('A', 'B', 'C'))
    assert result['chain_ids'] == ['A', 'B']
    interface = next(s for s in result['steps'] if s['tool_name'] == 'structure_pocket_interface_analysis')
    assert interface['params']['chain_scope'] == ['A', 'B']


def test_reference_hint_does_not_authorize_annotation_of_unverified_upload():
    result = strategy('分析功能', pdb_id='2XYZ')
    parser = next(s for s in result['steps'] if s['tool_name'] == 'structure_search_foldseek')
    assert parser['params']['search_mode'] == 'input_only'
    assert 'pdb_id' not in parser['params']


def test_qualified_continuation_reuses_existing_structure():
    from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
    result = evaluate_enzyme_workflow_runtime(
        '继续分析热稳定性', history=[{'role': 'user', 'content': '分析 2XYZ 的热稳定性'}],
    )
    assert result['intent'] == 'FOLLOW_UP'
    assert result['workflow_id'] == 'WF-STABILITY'
    assert result['input_gaps'] == []


def test_constraint_update_reuses_existing_input_and_keeps_goal():
    from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
    result = evaluate_enzyme_workflow_runtime(
        '不要 BLAST 但要分析热稳定性',
        history=[{'role': 'user', 'content': '分析 2XYZ 的热稳定性'}],
    )
    assert result['workflow_id'] == 'WF-STABILITY'
    assert result['input_gaps'] == []
    assert 'blast_search' in result['forbidden_tools']


def atom(serial, residue='ALA', chain='A', number=100, insertion='', record='ATOM', name='CA'):
    return (f'{record:<6}{serial:5d} {name:^4} {residue:>3} {chain:1}{number:4d}{insertion:1}   '
            f'{float(serial):8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{20.:6.2f}          {name[0]:>2}')


def test_parser_keeps_insertion_codes_and_first_model_serial():
    from app.services.pdb_parser import parse_pdb
    pdb = '\n'.join(['MODEL        7', atom(1), atom(2, insertion='A'), 'ENDMDL',
                     'MODEL        8', atom(3, residue='GLY'), 'ENDMDL'])
    result = parse_pdb(pdb)
    assert result['total_residues'] == 2
    assert result['chains'][0]['sequence'] == 'AA'
    assert [r['insertion_code'] for r in result['chains'][0]['residues']] == [None, 'A']
    assert result['model_scope'] == {'selected_model': 7, 'available_models': [7, 8], 'policy': 'first_model'}
    assert len(result['content_sha256']) == 64


def test_parser_normalizes_blank_chain_consistently():
    from app.services.pdb_parser import parse_pdb
    result = parse_pdb(atom(1, chain=' '))
    assert result['chains'][0]['chain_id'] == '_'


def link_record(left=('ND2', 'ASN', 'A', 74), right=('C1', 'NAG', 'B', 1)):
    chars = list(' ' * 80)
    def put(start, end, value): chars[start:end] = list(str(value).rjust(end-start))
    chars[:6] = list('LINK  ')
    for base, endpoint in [(0, left), (30, right)]:
        name, residue, chain, number = endpoint
        put(12+base, 16+base, name);put(17+base, 20+base, residue)
        put(21+base, 22+base, chain);put(22+base, 26+base, number)
    put(73, 78, '1.45')
    return ''.join(chars)


def test_pdb_link_retains_endpoints_without_assuming_all_links_covalent():
    from app.services.pdb_parser import parse_pdb
    result = parse_pdb('\n'.join([link_record(), atom(1)]))
    row = result['connections'][0]
    assert row['source_record'] == 'LINK'
    assert row['connection_type'] == 'unknown'
    assert row['partner_1']['residue_number'] == 74
    assert row['partner_2']['component_id'] == 'NAG'


@pytest.mark.asyncio
async def test_ligand_contact_retains_declared_link_separately_from_proximity():
    from app.tools.ligand_contact_analysis import ligand_contact_analysis
    pdb = '\n'.join([link_record(), atom(1, 'ASN', number=74, name='ND2'),
                     atom(2, 'NAG', 'B', 1, record='HETATM', name='C1')])
    result = await ligand_contact_analysis(pdb_data=pdb, chain_id='A')
    assert result['declared_connections'][0]['source_record'] == 'LINK'
    assert result['contacts'][0]['declared_connection_type'] == 'unknown'
    assert result['contacts'][0]['contact_type'] != 'covale'


def test_parameter_bridge_never_takes_latest_other_chain_identity():
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    completed = [PlanStep(i, 'enzyme_identity_profile', 'identity',
        {'pdb_object_name': 'uploads/model.pdb', 'chain_id': chain}, 'completed',
        {'identity_label': label}) for i, chain, label in [(1, 'A', 'protein-A'), (2, 'B', 'protein-B')]]
    step = PlanStep(3, 'protein_benchmark', 'family', {'pdb_object_name': 'uploads/model.pdb', 'chain_id': 'A'})
    result = AgentOrchestrator()._bridge_step_params(step, completed)
    assert result.params['identity_profile']['identity_label'] == 'protein-A'


def test_parameter_bridge_rejects_other_file_even_with_same_chain():
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    completed = [PlanStep(1, 'enzyme_identity_profile', 'identity',
        {'pdb_object_name': 'uploads/other.pdb', 'chain_id': 'A'}, 'completed', {'identity_label': 'other'})]
    result = AgentOrchestrator()._bridge_step_params(
        PlanStep(2, 'protein_benchmark', 'family', {'pdb_object_name': 'uploads/current.pdb', 'chain_id': 'A'}), completed)
    assert 'identity_profile' not in result.params


def test_explicitly_scoped_dependency_cannot_use_unattributed_result():
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    step = PlanStep(2, 'protein_benchmark', 'family', {'pdb_object_name': 'uploads/current.pdb', 'chain_id': 'A'})
    completed = [PlanStep(1, 'enzyme_identity_profile', 'identity', {}, 'completed', {'identity_label': 'unbound'})]
    assert 'identity_profile' not in AgentOrchestrator()._bridge_step_params(step, completed).params


def test_multichain_report_keeps_both_chain_property_results():
    import json
    from app.core.agent_graph import AgentOrchestrator
    records = [{'tool_name': 'predict_properties', 'status': 'completed', 'chain_id': chain,
        'pdb_object_name': 'uploads/model.pdb',
        'result': json.dumps({'length': length, 'molecular_weight': 1000*length, 'isoelectric_point': 5.5})}
        for chain, length in [('A', 111), ('B', 222)]]
    report = AgentOrchestrator()._build_fallback_report('分析结构质量', records)
    assert '链 A' in report and '链 B' in report
    assert '111' in report and '222' in report


@pytest.mark.parametrize('payload, expected', [
    ({'status': 'blocked'}, 'unavailable'), ({'status': 'not_available'}, 'unavailable'),
    ({'status': 'submitted', 'task_id': 'receipt'}, 'pending'),
    ({'status': 'completed', 'results_count': 0, 'hits': []}, 'empty'),
    ({'status': 'partial', 'features': [1]}, 'partial'),
    ({'status': 'completed', 'features': [1]}, 'usable'),
    ({'status': 'completed', 'search_executed': False, 'results_count': 0, 'query_structure': {'total_atoms': 1}}, 'usable'),
])
def test_execution_success_does_not_imply_usable_evidence(payload, expected):
    from app.services.task_evidence import result_status
    assert result_status('completed', payload)['result_status'] == expected


def test_blocked_result_cannot_satisfy_orchestration_gate():
    from app.services.tool_orchestration_contract import evidence_from_completed_tasks
    assert not evidence_from_completed_tasks([{'tool_name': 'enzyme_identity_profile',
        'status': 'completed', 'result': {'status': 'blocked'}}]).get('identity_ready')


def test_execution_checks_user_exclusions_and_local_only_separately():
    from app.services.structure_intent import execution_constraint_error
    assert execution_constraint_error('blast_search', {}, {'forbidden_tools': ['blast_search']})
    assert execution_constraint_error('annotation_bundle', {}, {'offline': True})
    assert execution_constraint_error('structure_search_foldseek', {'search_mode': 'input_only'}, {'offline': True}) is None


def test_blocked_payload_is_not_cached_and_cached_objects_are_isolated():
    from app.core.agent_graph import AgentOrchestrator
    key = 'general-pdb-regression'
    AgentOrchestrator._tool_cache.pop(key, None)
    AgentOrchestrator._cache_put(key, {'status': 'blocked'})
    assert AgentOrchestrator._cache_get(key) is None
    AgentOrchestrator._cache_put(key, {'features': [1]})
    first = AgentOrchestrator._cache_get(key)
    first['features'].append(2)
    assert AgentOrchestrator._cache_get(key)['features'] == [1]
    AgentOrchestrator._tool_cache.pop(key, None)


def test_question_coverage_does_not_claim_thermal_stability_from_properties():
    from app.services.structure_questions import question_answers
    rows = [{'tool_name': 'predict_properties', 'status': 'completed', 'result': {'length': 100, 'isoelectric_point': 5.5}}]
    answer = question_answers('分析热稳定性', rows)[0]
    assert answer['status'] == 'unresolved'
    assert answer['evidence_ids'] == []


def test_question_summary_uses_total_count_after_feature_preview_compaction():
    import json
    from app.core.agent_graph import AgentOrchestrator
    from app.services.structure_questions import question_answers
    payload = {'status': 'completed', 'feature_count': 317,
               'features': [{'position': index} for index in range(317)]}
    compact = AgentOrchestrator._compact_result('build_site_structure_function_features', payload)
    assert len(json.loads(compact)['features']) == 20
    answer = question_answers('分析热稳定性', [{
        'tool_name': 'build_site_structure_function_features', 'status': 'completed', 'result': compact,
    }])[0]
    assert '317 个位点' in answer['answer']


def test_ca_only_input_skips_sidechain_geometry_and_explains_why():
    result = select_structure_strategy('分析热稳定性', {'chains': [
        {'chain_id': 'LONG', 'sequence': 'ACDEFGHIKLMNPQRSTVWY', 'ca_only': True}]},
        object_name='uploads/ca-only.pdb', tools=TOOLS, runtimes={})
    assert 'disulfide_saltbridge_scan' not in {r['tool_name'] for r in result['steps']}
    assert any('CA' in line for line in result['deferred'])


def test_condition_contract_and_exclusions_participate_in_plan_signature():
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    selected = strategy('不要 BLAST，分析热稳定性')['steps']
    assert all(row['params']['analysis_contract']['on_failure'] for row in selected)
    a = [PlanStep(1, selected[0]['tool_name'], selected[0]['description'], selected[0]['params'])]
    import copy
    b = copy.deepcopy(a)
    b[0].params['execution_policy']['forbidden_tools'] = []
    assert AgentOrchestrator._plan_signature(a) != AgentOrchestrator._plan_signature(b)


def test_mmcif_preserves_long_chain_ids_and_typed_connections():
    from app.services.pdb_parser import parse_pdb
    cif = '''data_generic
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_entity_id
_atom_site.label_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
_atom_site.auth_seq_id
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_atom_id
_atom_site.pdbx_PDB_model_num
ATOM 1 C CA . ALA AA 1 1 ? 0 0 0 1 20 100 ALA LONG CA 1
#
loop_
_struct_conn.id
_struct_conn.conn_type_id
_struct_conn.ptnr1_auth_asym_id
_struct_conn.ptnr1_auth_seq_id
_struct_conn.ptnr1_label_comp_id
_struct_conn.ptnr1_label_atom_id
_struct_conn.ptnr2_auth_asym_id
_struct_conn.ptnr2_auth_seq_id
_struct_conn.ptnr2_label_comp_id
_struct_conn.ptnr2_label_atom_id
metal1 metalc LONG 100 ALA CA Z 1 ZN ZN
#
'''
    result = parse_pdb(cif)
    assert result['chains'][0]['chain_id'] == 'LONG'
    assert result['chains'][0]['residues'][0]['label_asym_id'] == 'AA'
    assert result['connections'][0]['connection_type'] == 'metalc'


def test_free_amino_acid_and_nucleic_acid_are_not_protein_polymer():
    from app.services.pdb_parser import parse_pdb
    from app.tools.ligand_contact_analysis import _parse_atoms
    pdb = '\n'.join([atom(1), atom(2, 'GLY', 'L', 1, record='HETATM'),
                     atom(3, 'DA', 'N', 1, name='P')])
    profile = parse_pdb(pdb)
    assert [c['chain_id'] for c in profile['chains']] == ['A']
    rows, _, _ = _parse_atoms(pdb)
    assert [r['chain_id'] for r in rows if r['record'] == 'ATOM'] == ['A']
    assert next(r for r in rows if r['chain_id'] == 'L')['record'] == 'HETATM'
    assert next(r for r in rows if r['chain_id'] == 'N')['record'] != 'HETATM'
    assert {r['component_id'] for r in profile['nonpolymer_components']} == {'GLY'}
    assert profile['other_polymer_components'][0]['component_id'] == 'DA'


def test_malformed_cif_connection_keeps_coordinates_and_explicit_warning():
    from app.services.structure_records import cif_records
    _, _, connections = cif_records({'_struct_conn.id': ['broken'],
        '_struct_conn.ptnr1_auth_seq_id': ['not-a-number']})
    assert connections[0]['validation_status'] == 'invalid'
    assert connections[0]['warning']


def test_mapping_preserves_coordinate_order_first_model_and_long_cif_chain():
    from app.tools.residue_mapping_sifts import _iter_pdb_residues
    pdb = '\n'.join(['MODEL        7', atom(1, number=100), atom(2, 'GLY', number=99),
                     'ENDMDL', 'MODEL        8', atom(3, 'CYS', number=101), 'ENDMDL'])
    assert [r['pdb_residue_no'] for r in _iter_pdb_residues(pdb)] == [100, 99]
    cif = '''data_order
loop_
_atom_site.id
_atom_site.group_PDB
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_seq_id
_atom_site.auth_atom_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
1 ATOM ALA LONG 100 CA 0 0 0
#
'''
    assert _iter_pdb_residues(cif, 'LONG')[0]['residue_aa'] == 'A'


def test_pocket_projection_cannot_drop_insertion_code():
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    completed = [
        PlanStep(1, 'residue_mapping_sifts', '', {}, 'completed', {'mappings': [
            {'chain_id': 'A', 'pdb_residue_no': 100, 'user_sequence_position': 1}]}),
        PlanStep(2, 'pocket_residue_lookup', '', {}, 'completed', {'residue_positions': [
            {'chain_id': 'A', 'pdb_residue_no': 100, 'insertion_code': 'A'}]}),
    ]
    result = AgentOrchestrator()._bridge_step_params(PlanStep(3, 'mutation_priority_score', '', {}), completed)
    assert 'user_sequence_position' not in result.params['pocket_residue_positions'][0]


def test_signed_policy_survives_runtime_contract_losing_exclusion():
    from app.services.structure_intent import execution_constraint_error
    assert execution_constraint_error('blast_search', {
        'execution_policy': {'forbidden_tools': ['blast_search']}}, {})
    assert execution_constraint_error('blast_search', {'execution_policy': {'offline': True}}, {})


@pytest.mark.asyncio
async def test_signed_stream_never_dispatches_excluded_tool(monkeypatch):
    import json
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    from app.tools.registry import ToolRegistry
    orch = AgentOrchestrator()
    plan = [PlanStep(1, 'external_connectivity_check', 'probe', {
        'execution_policy': {'forbidden_tools': ['external_connectivity_check']}})]
    calls = []

    async def dispatch(tool_name, params, **kwargs):
        calls.append(tool_name)
        raise AssertionError('Excluded tool reached dispatch')

    async def no_llm(*args, **kwargs):
        raise RuntimeError('Use local report')

    monkeypatch.setattr(ToolRegistry, 'execute', dispatch)
    monkeypatch.setattr(orch, '_call_llm', no_llm)
    events = [json.loads(event) async for event in orch.stream_chat(
        '确认执行上述分析策略', [], agent_control='execute_confirmed',
        confirmed_plan=[{'id': s.id, 'tool_name': s.tool_name, 'description': s.description,
                         'params': s.params} for s in plan],
        strategy_signature=orch._plan_signature(plan),
        task_fingerprint=orch._task_fingerprint('探测网络', ''))]
    assert not calls
    assert any('EXECUTION_SCOPE_VIOLATION' in json.dumps(event) for event in events)
    assert any(event.get('type') == 'done' for event in events)


def test_report_separates_different_models_of_same_file():
    import json
    from app.core.agent_graph import AgentOrchestrator
    records = [{'tool_name': 'predict_properties', 'status': 'completed', 'chain_id': 'A',
        'pdb_object_name': 'uploads/model.pdb', 'evidence_scope': {'model_id': model},
        'result': json.dumps({'length': length, 'isoelectric_point': 5.5})}
        for model, length in [(7, 111), (8, 222)]]
    report = AgentOrchestrator()._build_fallback_report('分析理化性质', records)
    assert '模型 7' in report and '模型 8' in report
    assert '111' in report and '222' in report


def test_continuation_after_goal_change_keeps_prior_input_but_not_old_goal():
    from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
    result = evaluate_enzyme_workflow_runtime('继续', history=[
        {'role': 'user', 'content': '分析 2XYZ 比活力，不要 BLAST'},
        {'role': 'user', 'content': '改成分析热稳定性'},
    ])
    assert result['workflow_id'] == 'WF-STABILITY'
    assert 'structure_reference' in result['known_inputs']
    assert 'blast_search' in result['forbidden_tools']


def test_new_structure_does_not_inherit_constraints_from_previous_task():
    from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
    result = evaluate_enzyme_workflow_runtime('分析 3XYZ 热稳定性', history=[
        {'role': 'user', 'content': '分析 2XYZ 比活力，不要 BLAST'}])
    assert result['intent'] == 'NEW_TASK'
    assert not result['forbidden_tools']


@pytest.mark.parametrize('value', [{}, 'invalid-json', '[]'])
def test_invalid_payload_cannot_become_usable_evidence(value):
    from app.services.task_evidence import result_status
    assert result_status('completed', value)['result_status'] == 'invalid'


def test_generic_deep_report_covers_selected_questions():
    from app.services.structure_questions import question_answers
    rows = [{'tool_name': 'disulfide_saltbridge_scan', 'status': 'completed',
             'result': {'status': 'completed', 'salt_bridges': []}}]
    answers = question_answers('给我深度分析', rows)
    assert next(a for a in answers if a['goal'] == 'stability')['status'] == 'partly_answered'
