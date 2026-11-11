"""The structural predictor is independent, complete, and bound to input coordinates."""
import hashlib
import inspect

import pytest

from app.tools.thermostability_workflow import thermostability_candidate_workflow


def enabled():
    assert 'run_thermompnn' in inspect.signature(thermostability_candidate_workflow).parameters


def pdb():
    return '\n'.join(f'ATOM  {i:5d}  CA  ALA A{p:4d}    {i*10.:8.3f}{0.:8.3f}{0.:8.3f}  1.00 20.00           C'
                      for i,p in enumerate((11,12,14,15),1))+'\nEND\n'


@pytest.mark.asyncio
async def test_structural_scores_have_explicit_sequence_to_author_mapping(monkeypatch):
    enabled()
    calls=[]
    async def predict(pdb_data,mutations,sequence='',chain_id='A'):
        assert sequence=='AAAA' and mutations==['A1V']
        numbers=[int(line[22:26]) for line in pdb_data.splitlines() if line.startswith('ATOM')]
        assert numbers==[1,2,3,4], 'model sees exact contiguous input coordinates, not gapped author numbering'
        calls.append(pdb_data)
        return {'status':'completed','model':'ThermoMPNN','model_version':'fixture',
            'input_sha256':hashlib.sha256(pdb_data.encode()).hexdigest(), 'model_sha256':'a'*64,
            'chain_id':'A','predictions':[{'mutation':'A1V','ddg_pred':-.5}]}
    monkeypatch.setattr('app.tools.thermompnn_predict.thermompnn_predict',predict)
    result=await thermostability_candidate_workflow('AAAA',pdb_data=pdb(),mutations=['A1V'],
        analysis_mode='exploration',run_thermompnn=True)
    assert calls
    assert result['branches']['thermompnn']['status']=='completed'
    row=result['preliminary_candidates'][0]
    assert row['scores']['thermompnn']['ddg_pred']==-.5
    assert 'esm_evolutionary_preference' not in row['missing_evidence']
    assert row['structure_position']['residue_number']==11
    assert result['branches']['thermompnn']['coordinate_mapping'][2]['author_residue_number']==14
    assert 'ThermoMPNN' in result['report_markdown']
    import csv,io
    exports=result.get('review_exports',{})
    assert exports['strategy_status']['content_type']=='text/csv'
    assert len(list(csv.DictReader(io.StringIO(exports['strategy_status']['content']))))==17
    rows=list(csv.DictReader(io.StringIO(exports['independent_scores']['content'])))
    assert rows[0]['mutation']=='A1V' and rows[0]['thermompnn_raw_ddg']=='-0.5'
    assert rows[0]['pdb_author_position']=='A:11'


@pytest.mark.asyncio
async def test_missing_structural_predictor_is_explicit_and_keeps_other_results(monkeypatch):
    enabled()
    monkeypatch.delenv('THERMOMPNN_SERVICE_URL',raising=False)
    result=await thermostability_candidate_workflow('AAAA',pdb_data=pdb(),mutations=['A1V'],
        analysis_mode='exploration',run_thermompnn=True)
    assert result['branches']['thermompnn']['status']=='blocked'
    assert result['preliminary_candidates'][0]['mutation']=='A1V'


@pytest.mark.asyncio
async def test_offline_thermompnn_is_never_called(monkeypatch):
    enabled()
    async def fail(*args,**kwargs):
        raise AssertionError('offline call')
    monkeypatch.setattr('app.tools.thermompnn_predict.thermompnn_predict',fail)
    result=await thermostability_candidate_workflow('AAAA',pdb_data=pdb(),mutations=['A1V'],
        analysis_mode='exploration',offline=True,run_thermompnn=True)
    assert result['branches']['thermompnn']['status']=='skipped'


def test_signed_or_current_forbidden_predictor_is_removed_from_plan():
    from app.core.agent_graph import AgentOrchestrator,PlanStep
    step=PlanStep(1,'thermostability_candidate_workflow','thermal',
        {'run_thermompnn':True,'execution_policy':{'forbidden_tools':['thermompnn_predict']}})
    AgentOrchestrator._apply_thermostability_execution_policy(step)
    assert step.params['run_thermompnn'] is False


@pytest.mark.parametrize('change',['missing','nan','duplicate','foreign_hash'])
@pytest.mark.asyncio
async def test_untrusted_structural_predictions_are_not_used(monkeypatch,change):
    enabled()
    async def predict(pdb_data,*args,**kwargs):
        rows=[{'mutation':'A1V','ddg_pred':-.5}]
        if change=='missing': rows=[]
        if change=='nan': rows[0]['ddg_pred']=float('nan')
        if change=='duplicate': rows*=2
        return {'status':'completed','model':'ThermoMPNN','model_version':'fixture','model_sha256':'a'*64,
            'chain_id':'A','input_sha256':'b'*64 if change=='foreign_hash' else hashlib.sha256(pdb_data.encode()).hexdigest(),
            'predictions':rows}
    monkeypatch.setattr('app.tools.thermompnn_predict.thermompnn_predict',predict)
    result=await thermostability_candidate_workflow('AAAA',pdb_data=pdb(),mutations=['A1V'],
        analysis_mode='exploration',run_thermompnn=True)
    assert result['branches']['thermompnn']['status']=='blocked'
    assert result['preliminary_candidates'][0]['scores'].get('thermompnn') is None
    import json
    json.dumps(result,allow_nan=False)


def test_standard_plan_prefers_structural_predictor_to_evolutionary_preference():
    from app.core.agent_graph import AgentOrchestrator
    plan=AgentOrchestrator()._thermal_engineering_plan('提高热稳定性','AAAA', 'uploads/user_1/input.pdb','standard')
    workflow=next(s for s in plan if s.tool_name=='thermostability_candidate_workflow')
    assert workflow.params.get('run_thermompnn') is True
    assert workflow.params['run_esm'] is False


@pytest.mark.asyncio
async def test_structural_scores_rank_in_their_own_direction_without_adding_ddgun(monkeypatch):
    enabled()
    async def predict(pdb_data,mutations,**kwargs):
        return {'status':'completed','model':'ThermoMPNN','model_version':'fixture','model_sha256':'a'*64,
            'chain_id':'A','input_sha256':hashlib.sha256(pdb_data.encode()).hexdigest(),
            'predictions':[{'mutation':c,'ddg_pred':1. if c=='A1V' else -1.} for c in mutations]}
    monkeypatch.setattr('app.tools.thermompnn_predict.thermompnn_predict',predict)
    result=await thermostability_candidate_workflow('AAAA',pdb_data=pdb(),mutations=['A1V','A2V'],
        analysis_mode='exploration',run_thermompnn=True,assay_budget=1)
    assert result['preliminary_candidates'][0]['mutation']=='A2V'
    assert result['branches']['thermompnn']['sign_convention']=='negative=predicted_stabilizing'


@pytest.mark.asyncio
async def test_strategy_and_score_exports_use_owned_user_report_storage(monkeypatch):
    from app.core.agent_graph import AgentOrchestrator,PlanStep
    result=await thermostability_candidate_workflow('NGAA',analysis_mode='exploration')
    calls=[]
    async def upload(content,filename,content_type='',folder=''):
        calls.append((content,filename,content_type,folder))
        return {'download_url':'/api/files/uploads/user_7/reports/'+filename}
    monkeypatch.setattr('app.services.storage.upload_file',upload)
    step=PlanStep(1,'thermostability_candidate_workflow','thermal',{},result=result,status='completed')
    await AgentOrchestrator._attach_site_features_artifact(step,{'id':7})
    assert len(calls)==3
    assert all(x[2]=='text/csv' and x[3]=='uploads/user_7/reports' for x in calls)
    assert all(x[0].startswith(b'\xef\xbb\xbf') for x in calls)
    assert all(x['download_status']=='ready' for x in step.result['review_exports'].values())
    assert '/api/files/uploads/user_7/reports/' in step.result['report_markdown']


@pytest.mark.asyncio
async def test_export_storage_failure_does_not_lose_computed_results(monkeypatch):
    from app.core.agent_graph import AgentOrchestrator,PlanStep
    result=await thermostability_candidate_workflow('NGAA',analysis_mode='exploration')
    async def upload(*args,**kwargs):
        raise RuntimeError('storage failure')
    monkeypatch.setattr('app.services.storage.upload_file',upload)
    step=PlanStep(1,'thermostability_candidate_workflow','thermal',{},result=result,status='completed')
    await AgentOrchestrator._attach_site_features_artifact(step,{'id':7})
    assert all(x['download_status']=='storage_failed' for x in step.result['review_exports'].values())
    assert step.result['strategy_runs'][11]['raw_count']==1


def test_confirmation_text_describes_actual_multi_strategy_and_model_execution():
    from app.core.agent_graph import AgentOrchestrator
    checkpoint=AgentOrchestrator._build_strategy_checkpoint('提高酶的热稳定性')
    text=' '.join(checkpoint['logic'])
    assert '17' in text and 'T1' in text and 'T2' in text
    assert 'ThermoMPNN' in text
    assert 'DDGun和ESM' not in text


@pytest.mark.asyncio
async def test_partial_ddgun_returns_are_exported_for_review_but_not_used_for_ranking(monkeypatch):
    import csv
    import io
    async def predict(sequence, mutations):
        return {'status':'completed','predictions':[{'mutation':'A1V','ddg':.7}]}
    monkeypatch.setattr('app.tools.thermostability_adapters.ddgun_predict',predict)
    result=await thermostability_candidate_workflow('AAAA',mutations=['A1V','A2V'],
        analysis_mode='exploration',run_ddgun=True)
    assert result['branches']['ddgun']['status']=='blocked'
    assert all(r['scores']['ddgun'] is None for r in result['screened_candidates'])
    rows=list(csv.DictReader(io.StringIO(result['review_exports']['independent_scores']['content'])))
    first=next(r for r in rows if r['mutation']=='A1V')
    assert first['ddgun_raw_returned']=='[0.7]'
    assert first['ddgun_score_used']=='False'
    assert '实际评分覆盖' in result['report_markdown']


@pytest.mark.asyncio
async def test_unrequested_models_do_not_make_a_strategy_look_scored():
    result=await thermostability_candidate_workflow('NGAA',analysis_mode='exploration')
    report=result['report_markdown']
    assert '可送单点评分' in report
    assert 'DDGun 0/1（not_requested）' in report
    assert 'ThermoMPNN 0/1（not_requested）' in report
    assert '送入单点评分池；分数返回见实际评分覆盖' in report
