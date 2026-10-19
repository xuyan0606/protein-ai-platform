"""Regressions captured by uploading real PDBs through the chat UI/API."""
import asyncio
import json
import pytest
from app.core.agent_graph import AgentOrchestrator
from app.tools.registry import ToolRegistry

@pytest.fixture
def orch():
    ToolRegistry.discover()
    return AgentOrchestrator()

def result(tool, payload, status='completed'):
    return {'tool_name':tool, 'status':status, 'result':json.dumps(payload)}

def test_negative_tool_list_does_not_cancel_positive_clause(orch):
    text='只做结构解析、编号映射、理化性质；不要调用 BLAST、InterProScan、annotation_bundle、enzyme_identity_profile、protein_benchmark、enzyme_function、protssn_score、build_site_structure_function_features。'
    forbidden=orch._extract_forbidden_tools(text)
    assert 'predict_properties' not in forbidden
    assert 'residue_mapping_sifts' not in forbidden
    assert {'blast_search','annotation_bundle','enzyme_identity_profile','protein_benchmark','enzyme_function','build_site_structure_function_features','interproscan_sequence_submit','protssn_score'} <= forbidden

def test_property_goal_is_not_measured_assay_context(orch):
    assert orch._extract_assay_context('比较这两个PDB的比活力和热稳定性') == {}
    measured = orch._extract_assay_context('底物：可溶淀粉；比活力 120 U/mg；Tm 72 ℃；残余活性 65%')
    assert measured['specific_activity'] is True
    assert measured['protein_normalized'] is True
    assert measured['tm'] is True
    assert measured['residual_activity'] is True

def test_report_does_not_claim_failed_tools_completed_or_missing_existing_identity(orch):
    report=orch._build_fallback_report('深度分析这个PDB的比活力、热稳定性',[
        result('structure_search_foldseek',{'query_structure':{'total_residues':481,'chains':[{'chain_id':'A','residue_count':481}]}}),
        result('enzyme_identity_profile',{'identity_status':'identified','family_candidates':[{'name':'ALPHA-AMYLASE'}],'numbering':{'status':'verified_for_input_sequence'}}),
        result('blast_search',{'reason':'queue unavailable'},'failed'),
    ])
    assert '本轮工具均已完成' not in report
    assert '当前没有序列级身份画像' not in report
    assert '上面的 PDB 坐标预筛位点' not in report
    assert '编号=verified_for_input_sequence' not in report

def test_analysis_only_status_summary_uses_canonical_tool_evidence_state(orch):
    report = orch._build_fallback_report('深度分析这个PDB', [
        result('structure_search_foldseek', {
            'status': 'completed',
            'query_structure': {'total_residues': 481, 'chains': [{'chain_id': 'A', 'residue_count': 481}]},
        }),
        # A successful queue wrapper can still contain a tool-level rejection.
        result('build_site_structure_function_features', {
            'status': 'blocked', 'reason': 'invalid chain',
        }),
        result('blast_search', {'status': 'submitted', 'task_id': 'blast-1'}, 'submitted'),
        result('protein_benchmark', {'reason': 'upstream unavailable'}, 'failed'),
    ])

    assert '- **分析状态**：已完成 1 项；等待 1 项；失败或受阻 2 项。' in report
    assert '- **待处理工具**：blast_search, build_site_structure_function_features, protein_benchmark。' in report
    assert '已完成 2 项；等待 1 项；失败或受阻 1 项' not in report


def test_degraded_foldseek_keeps_uploaded_coordinate_facts_without_similarity_claim(orch):
    report = orch._build_fallback_report('分析上传的 4HHB.cif', [
        result('structure_search_foldseek', {
            'status': 'degraded', 'backend': 'summary_only', 'results_count': 0,
            'query_structure': {'chain_count': 4, 'total_residues': 574, 'total_atoms': 4558},
        }),
    ])
    assert '链数=4；残基数=574；原子数=4558' in report
    assert 'Foldseek 同源检索降级' in report
    assert '| structure_search_foldseek | blocked |' in report

def test_full_pdb_analysis_only_has_no_empty_candidate_scoring(orch):
    plan=orch._generate_fallback_plan('深度分析这个pdb,我要你把能分析的内容都给我显示。\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/current.pdb]',analysis_depth='deep')
    names={step.tool_name for step in plan}
    assert 'predict_properties' in names
    assert not names & {'mutation_priority_score','mutation_scan','protssn_score','enzyme_objective_module_plan'}
    explanation='\n'.join(orch._build_objective_decomposition_lines('深度分析这个pdb,我要你把能分析的内容都给我显示。'))
    assert '先补充目标和 assay' not in explanation

def test_thermostability_deep_plan_includes_real_structure_network_scan(orch):
    plan = orch._generate_fallback_plan(
        '深度分析这个PDB的比活力、热稳定性及全部可分析结构证据。\n'
        '[Attached files:\nname: 1BLI.pdb, object_name: uploads/current.pdb]',
        analysis_depth='deep',
    )
    names = [step.tool_name for step in plan]
    assert 'disulfide_saltbridge_scan' in names

def test_report_surfaces_structure_stability_network_evidence(orch):
    report = orch._build_fallback_report('深度分析这个PDB的热稳定性', [
        result('structure_search_foldseek', {'query_structure': {
            'total_residues': 10, 'chains': [{'chain_id': 'A', 'residue_count': 10}],
        }}),
        result('disulfide_saltbridge_scan', {
            'status': 'completed', 'disulfide_bonds': [{'chain_id': 'A', 'residue_1': 2, 'residue_2': 8, 'sg_distance_angstrom': 2.03}],
            'salt_bridges': [{'chain_id': 'A', 'residue_1': 3, 'residue_1_name': 'LYS', 'residue_2': 6, 'residue_2_name': 'ASP', 'distance_angstrom': 3.1}],
        }),
    ])
    assert '## 热稳定性结构线索' in report
    assert '二硫键几何接触' in report
    assert '盐桥几何接触' in report
    assert '不能量化其能量贡献或证明耐热性提升' in report

def test_deep_report_shows_all_scanned_contacts_and_activity_boundary(orch):
    contacts = [{'residue_1': f'A:{i}', 'residue_1_name': 'LYS',
                 'residue_2': f'A:{i + 20}', 'residue_2_name': 'ASP',
                 'distance_angstrom': 2.8} for i in range(1, 16)]
    report = orch._build_fallback_report('深度分析这个PDB的比活力、热稳定性', [
        result('disulfide_saltbridge_scan', {'status': 'completed', 'residue_count': 40,
                                            'disulfide_bonds': [], 'salt_bridges': contacts}),
    ])
    assert 'LYS A:15 ↔ ASP A:35' in report
    assert '## 比活力分析' in report
    assert 'U/mg' in report

def test_matching_sequence_supplement_preserves_current_goal_and_object(orch):
    seq='DTTITQNQTGYDNGYFYSFWTDAPGTVSMTLHSGGSYSTSWRNTGNFVAGKGWSTGGRRTVTYNASFNPSGNAYLTLYGWTRNPLVEYYIVESWGTYRPTGTYKGTVTTDGGTYDIYETWRYNAPSIEGTRTFQQFWSVRQQKRTSGTITIGNHFDAWARAGMNLGSHDYQIMATEGYQSSGSSTVSISEGGNP'
    history=[{'role':'user','content':'深度分析这个pdb比活力、热稳定性\n[Attached files:\nname: 13.pdb, object_name: uploads/current.pdb]'},
             {'role':'user','content':seq}]
    context=orch._build_context_for_message(seq,history[:-1])
    assert 'uploads/current.pdb' in context
    assert '比活力' in context and '热稳定性' in context

def test_explicit_multi_upload_is_not_silently_first_file_only(orch):
    from app.core.agent_graph import PlanStep
    task='比较这两个PDB\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/hash_a.pdb\nname: 13.pdb, object_name: uploads/hash_b.pdb]'
    plan=[PlanStep(1,'structure_search_foldseek','a',{'pdb_object_name':'uploads/hash_a.pdb'}),PlanStep(2,'structure_search_foldseek','b',{'pdb_object_name':'uploads/hash_b.pdb'})]
    assert orch._foreign_uploaded_objects_in_plan(task,plan)==[]
    report=orch._build_fallback_report(task,[
      {**result('structure_search_foldseek',{'query_structure':{'total_residues':481,'chains':[{'chain_id':'A','residue_count':481}]}}),'pdb_object_name':'uploads/hash_a.pdb','input_id':'pdb:0'},
      {**result('structure_search_foldseek',{'query_structure':{'total_residues':194,'chains':[{'chain_id':'A','residue_count':194}]}}),'pdb_object_name':'uploads/hash_b.pdb','input_id':'pdb:1'},
    ])
    assert '481' in report and '194' in report
    assert '结构 1: 1BLI.pdb' in report and '结构 2: 13.pdb' in report
    assert 'hash_a' not in report and 'hash_b' not in report

def test_analysis_report_shows_structure_quality_without_mutation_workflow(orch):
    report = orch._build_fallback_report('深度分析这个PDB', [
        {**result('structure_search_foldseek', {'status': 'completed', 'query_structure': {
            'total_residues': 481, 'method': 'X-RAY DIFFRACTION', 'resolution': 1.9,
            'r_factor': 0.154, 'space_group': 'P 61',
            'compound_annotation': {'molecule': 'ALPHA-AMYLASE', 'ec': '3.2.1.1', 'engineered': 'YES'},
            'b_factor_stats': {'mean': 21.1},
            'chains': [{'chain_id': 'A', 'residue_count': 481}],
        }}), 'pdb_object_name': 'uploads/a.pdb'},
    ])
    assert '# 蛋白性质分析报告' in report
    assert '分辨率=1.9 Å' in report
    assert 'R-factor=0.154' in report
    assert 'engineered=YES' in report
    assert '单点构建' not in report
    assert '候选表门控' not in report

def test_report_explains_file_annotation_and_blocked_identity_gate(orch):
    report = orch._build_fallback_report('深度分析 1BLI.pdb', [
        result('structure_search_foldseek', {'query_structure': {
            'compound_annotation': {'molecule': 'ALPHA-AMYLASE', 'ec': '3.2.1.1'},
            'total_residues': 481, 'chains': [{'chain_id': 'A', 'residue_count': 481}],
        }}),
        result('enzyme_identity_profile', {
            'identity_status': 'unresolved',
            'family_candidates': [{'name': 'GH13 alpha-amylase family', 'confidence': 0.25,
                                   'source': 'short motif heuristic'}],
        }),
        result('protein_benchmark', {
            'status': 'blocked',
            'foundation_gate': {'status': 'blocked', 'message': 'Confirm family and protected positions first.'},
        }, 'blocked'),
    ])
    assert '候选依据**：short motif heuristic' in report
    assert '当前状态=unresolved' in report
    assert 'Confirm family and protected positions first.' in report
    assert '原因/摘要=blocked' not in report

    multiline = orch._build_fallback_report('分析 1BLI.pdb', [
        result('blast_search', {'error': 'Retry limit exceeded\nwhile connecting'}, 'failed'),
    ])
    assert '原因/摘要=Retry limit exceeded while connecting' in multiline


def test_rcsb_entity_name_is_not_labeled_as_confirmed_family(orch):
    report = orch._build_fallback_report('分析 1BLI.pdb', [
        result('structure_search_foldseek', {'query_structure': {
            'total_residues': 481, 'chains': [{'chain_id': 'A', 'residue_count': 481}],
            'compound_annotation': {'molecule': 'ALPHA-AMYLASE'},
        }}),
        result('enzyme_identity_profile', {
            'identity_status': 'identified',
            'family_candidates': [{'name': 'BACILLUS LICHENIFORMIS ALPHA-AMYLASE',
                                   'source': 'RCSB query entry',
                                   'status': 'direct_experimental_structure_identity',
                                   'confidence': 0.95}],
        }),
        result('protein_benchmark', {'family': {
            'name': 'BACILLUS LICHENIFORMIS ALPHA-AMYLASE',
        }}),
    ])
    assert '结构实体注释**：BACILLUS LICHENIFORMIS ALPHA-AMYLASE' in report
    assert '家族候选**：BACILLUS LICHENIFORMIS ALPHA-AMYLASE' not in report
    assert 'RCSB 结构实体名称，不等于家族鉴定' in report
    assert 'EC**: 未确认' in report

def test_multichain_report_explains_scope_and_per_chain_coverage(orch):
    report = orch._build_fallback_report('深度分析 7DVJ.pdb', [
        result('structure_search_foldseek', {'query_structure': {
            'title': 'STRUCTURE OF BETA-MANNANASE WITH MANNOBIOSE',
            'total_residues': 633, 'seqres_length': 696,
            'seqres_by_chain': {'A': 348, 'B': 348},
            'chains': [
                {'chain_id': 'A', 'residue_count': 310},
                {'chain_id': 'B', 'residue_count': 323},
            ],
        }}),
    ])
    assert 'PDB 标题**：STRUCTURE OF BETA-MANNANASE WITH MANNOBIOSE' in report
    assert '链A SEQRES=348 aa、坐标=310 aa' in report
    assert '链B SEQRES=348 aa、坐标=323 aa' in report
    assert '默认使用链 A 的坐标序列' in report
    assert '不能由总数差直接推断原因' in report


@pytest.mark.parametrize(
    ('task_status', 'payload_status', 'evidence_status', 'expected_text', 'hits'),
    [
        ('submitted', 'submitted', 'submitted', '已提交后台专业库检索任务', []),
        ('waiting', 'waiting', 'waiting', 'NCBI 仍在处理，当前不能判定无命中', []),
        ('failed', 'failed', 'failed', 'NCBI 查询失败或降级，当前不能判定无命中', []),
        ('completed', 'completed', 'completed_no_hit', 'NCBI 已明确返回完成且本次参数下无命中', []),
        ('completed', 'completed', 'completed_with_hits', 'P12345', [{
            'accession': 'P12345', 'description': 'beta-mannanase homolog',
            'hsps': [{'alignment_length': 300, 'query_from': 1, 'query_to': 300,
                     'identity_percent': 91.2, 'e_value': 1e-80}],
        }]),
    ],
)
def test_blast_report_renders_all_task_and_evidence_states(
    orch, task_status, payload_status, evidence_status, expected_text, hits
):
    report = orch._build_fallback_report('深度分析 7DVJ.pdb', [
        result('structure_search_foldseek', {'query_structure': {
            'title': 'STRUCTURE OF BETA-MANNANASE',
            'total_residues': 310,
            'chains': [{'chain_id': 'A', 'residue_count': 310}],
        }}),
        result('blast_search', {
            'status': payload_status,
            'evidence_status': evidence_status,
            'database': 'nr',
            'program': 'blastp',
            'results_count': len(hits),
            'results': hits,
            'task_id': 'RID-TEST-123',
            'queue': 'default',
            'status_url': '/api/tools/tasks/RID-TEST-123',
            'evidence_source': {
                'checked_at': '2026-10-17T12:00:00Z',
                'endpoint': 'https://blast.ncbi.nlm.nih.gov/Blast.cgi',
                'details': {'rid': 'RID-TEST-123', 'database': 'nr'},
            },
        }, status=task_status),
    ])

    assert expected_text in report
    if evidence_status != 'waiting':
        assert 'NCBI 仍在处理，当前不能判定无命中' not in report
    if evidence_status != 'completed_no_hit':
        assert 'NCBI 已明确返回完成且本次参数下无命中' not in report
    if evidence_status in {'waiting', 'failed'}:
        assert '不能判定无命中' in report
    assert 'checked_at=2026-10-17T12:00:00Z' in report
    assert 'RID-TEST-123' in report


def test_7dvj_report_renders_wet_lab_plan_without_experimental_claims(orch):
    report = orch._build_fallback_report('深度分析 7DVJ.pdb，并给出湿实验下一步建议', [
        result('structure_search_foldseek', {'status': 'completed', 'query_structure': {
            'title': 'STRUCTURE OF BETA-MANNANASE BAMAN113A WITH MANNOBIOSE',
            'compound_annotation': {'molecule': 'beta-mannanase', 'ligand': 'mannobiose'},
            'engineered_mutations': [{
                'chain_id': 'A', 'reference_residue_aa': 'E', 'reference_position': 142,
                'pdb_residue_aa': 'A', 'pdb_residue_no': 142,
            }],
            'total_residues': 633,
            'chains': [{'chain_id': 'A', 'residue_count': 310}, {'chain_id': 'B', 'residue_count': 323}],
        }}),
    ])
    assert '## 湿实验验证计划' in report
    assert 'A:E142A' in report
    assert '天然相关 β-1,4-mannan 底物' in report
    assert 'WT' in report and 'PDB_CONSTRUCT' in report
    assert '表达/纯化 QC' in report and 'kcat/Km' in report
    assert 'Go / Watch / No-Go' in report
    assert '直接湿实验数据=not_available' in report
    assert '提高活性' not in report
    assert '已验证候选' not in report

def test_equal_length_seqres_and_repeated_ligands_are_not_misdescribed(orch):
    report = orch._build_fallback_report('深度分析 3WP6.pdb', [
        result('structure_search_foldseek', {'query_structure': {
            'total_residues': 228, 'seqres_length': 228,
            'chains': [{'chain_id': 'A', 'residue_count': 228}],
            'nonpolymer_components': [
                {'component_id': 'XYP', 'chain_id': 'B', 'residue_number': 1},
                {'component_id': 'XYP', 'chain_id': 'B', 'residue_number': 2},
            ],
        }}),
    ])
    assert '两者长度相同' in report
    assert '长度差可能来自' not in report
    assert 'XYP B:1；XYP B:2' in report
    assert '背景任务终态返回后' not in report

def test_site_feature_report_marks_preview_scope(orch):
    report = orch._build_fallback_report('深度分析这个 PDB', [
        result('structure_search_foldseek', {'query_structure': {
            'total_residues': 12, 'chains': [{'chain_id': 'A', 'residue_count': 12}],
        }}),
        result('build_site_structure_function_features', {
            'status': 'completed', 'feature_count': 12,
            'features': [{'position': n, 'wild_type': 'A'} for n in range(1, 13)],
        }),
    ])
    assert '预览前 8/12 行' in report
    assert '工具卡可下载本轮返回的全部位点特征' in report


@pytest.mark.asyncio
async def test_full_site_features_are_saved_for_authenticated_download(orch, monkeypatch):
    from app.core.agent_graph import PlanStep
    from app.services import storage

    uploaded = {}

    async def fake_upload(content, filename, **kwargs):
        uploaded.update(content=json.loads(content), filename=filename, kwargs=kwargs)
        return {'download_url': '/api/files/uploads/user_7/reports/features.json'}

    monkeypatch.setattr(storage, 'upload_file', fake_upload)
    step = PlanStep(1, 'build_site_structure_function_features', 'features',
                    result={'status': 'completed', 'feature_count': 25,
                            'features': [{'position': n} for n in range(1, 26)]})
    await orch._attach_site_features_artifact(step, {'id': 7})

    assert len(uploaded['content']['features']) == 25
    assert uploaded['kwargs']['folder'] == 'uploads/user_7/reports'
    compact = json.loads(orch._compact_result(step.tool_name, step.result))
    assert len(compact['features']) == 20
    assert compact['feature_count'] == 25
    assert compact['full_features_download_url'].startswith('/api/files/uploads/user_7/')


@pytest.mark.asyncio
async def test_missing_user_does_not_claim_full_site_feature_download(orch):
    from app.core.agent_graph import PlanStep

    step = PlanStep(1, 'build_site_structure_function_features', 'features',
                    result={'status': 'completed', 'feature_count': 25,
                            'features': [{'position': n} for n in range(1, 26)]})
    await orch._attach_site_features_artifact(step, None)
    compact = json.loads(orch._compact_result(step.tool_name, step.result))
    report = orch._build_fallback_report('深度分析这个 PDB', [
        result('structure_search_foldseek', {'query_structure': {
            'total_residues': 25, 'chains': [{'chain_id': 'A', 'residue_count': 25}],
        }}),
        result(step.tool_name, compact),
    ])
    assert len(compact['features']) == 20
    assert '完整数据未保存' in report
    assert '完整位点特征可从对应工具卡下载' not in report

def test_request_orchestrators_do_not_share_snapshot(orch):
    from app.core.agent_graph import ChatSnapshot
    first=orch.for_request(); second=orch.for_request()
    first._snapshot=ChatSnapshot(stage='execute',final_report='protein A')
    second._snapshot=ChatSnapshot(stage='done',final_report='protein B')
    assert first._snapshot.final_report=='protein A'
    assert orch._snapshot is None

def test_followup_uses_latest_uploaded_protein(orch):
    history = [
        {'role': 'user', 'content': '提高热稳定性\n[Attached files:\nname: old.pdb, object_name: uploads/old.pdb]'},
        {'role': 'assistant', 'content': '旧结构分析报告'},
        {'role': 'user', 'content': '深度分析新结构\n[Attached files:\nname: new.pdb, object_name: uploads/new.pdb]'},
        {'role': 'assistant', 'content': '新结构分析报告'},
    ]
    context = orch._build_context_for_message('继续，说说这个蛋白的比活力、热稳定性', history)
    assert 'uploads/new.pdb' in context
    assert 'uploads/old.pdb' not in context
    assert orch._is_same_problem_synthesis_followup('继续，说说这个蛋白的比活力、热稳定性', context)

def test_llm_unavailable_followup_summarizes_latest_report_only(orch):
    history = [
        {'role': 'user', 'content': 'old\n[Attached files:\nobject_name: uploads/old.pdb]'},
        {'role': 'assistant', 'content': '# 蛋白性质分析报告\n- **上传结构摘要**：残基数=388。'},
        {'role': 'user', 'content': 'new\n[Attached files:\nobject_name: uploads/new.pdb]'},
        {'role': 'assistant', 'content': '# 蛋白性质分析报告\n- **上传结构摘要**：残基数=481。'},
    ]
    reply = orch._history_report_reply(history, '继续，说说这个蛋白的比活力、热稳定性')
    assert '残基数=481' in reply and '残基数=388' not in reply
    assert 'U/mg' in reply and 'Tm' in reply

@pytest.mark.asyncio
async def test_explicit_pdb_id_does_not_restore_previous_checkpoint(orch):
    context = await orch._load_recent_strategy_planning_context(
        current_user={'id': 1}, audit_session=object(), conversation_id=1,
        message='深度分析 1BLI PDB',
    )
    assert context == ''
