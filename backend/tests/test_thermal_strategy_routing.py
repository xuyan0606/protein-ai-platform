"""Strategy receipts distinguish absence, missing evidence, and failures."""
import importlib.util

import pytest


def api():
    assert importlib.util.find_spec('app.services.thermal_strategy_router'), '17-strategy router is missing'
    from app.services import thermal_strategy_router
    return thermal_strategy_router


@pytest.mark.parametrize('trigger', ['hit', 'not_hit', 'unknown'])
def test_all_seventeen_routes_obey_tier_semantics(trigger):
    router = api()
    calls = []
    def generate(context, rule):
        calls.append(rule['id'])
        return []
    rules = router.load_rules()
    tags = {r['feature']: {'status': trigger, 'reason': 'synthetic fixture'} for r in rules if r['tier'] != 'postprocess'}
    receipt = router.route_strategies(tags, {}, generators={r['id']: generate for r in rules})
    assert len(receipt) == 17
    for row in receipt:
        if row['tier'] == 'postprocess':
            assert row['id'] not in calls
        elif row['tier'] == 'T1' and trigger != 'unknown':
            assert row['id'] in calls
            assert row['status'] == 'completed_zero_candidates'
        elif row['tier'] == 'T2' and trigger == 'not_hit':
            assert row['id'] not in calls and row['status'] == 'not_triggered'
        elif trigger == 'unknown':
            assert row['id'] not in calls and row['status'] == 'blocked_missing_evidence'
        else:
            assert row['id'] in calls


def test_failure_is_isolated_and_missing_generator_is_not_success():
    router = api()
    def fail(context, rule):
        raise RuntimeError('synthetic failure')
    tags = {r['feature']: {'status': 'hit', 'reason': 'fixture'} for r in router.load_rules() if r['tier'] != 'postprocess'}
    result = router.route_strategies(tags, {}, generators={'S01': fail})
    assert result[0]['status'] == 'failed'
    assert result[1]['status'] == 'not_implemented'
    assert all(r['raw_candidates'] == [] for r in result)


def test_sequence_motif_strategy_generates_real_hypotheses_without_assay():
    from app.services.thermostability_workflow import build_screen
    result = build_screen('ANGSTNSTMG', analysis_mode='exploration')
    rows = result.get('strategy_runs', [])
    assert len(rows) == 17, 'exploration omits the 17-strategy receipt'
    chemical = next(r for r in rows if r['id'] == 'S12')
    assert chemical['trigger_status'] == 'hit'
    assert {r['mutation'] for r in chemical['raw_candidates']} == {'N2Q', 'N6Q'}
    assert not result['candidates'] and not result['experimental_plan']
    assert {'N2Q','N6Q'} <= {r['mutation'] for r in result['preliminary_candidates']}
    assert all('pending_mutant_geometry' in r['risks'] for r in result['preliminary_candidates'])


def test_report_shows_seventeen_statuses_and_actual_strategy_mutations():
    from app.services.thermostability_workflow import build_screen
    from app.services.thermostability_report import render_thermostability_report
    report = render_thermostability_report(build_screen('ANGSTNSTMG', analysis_mode='exploration'))
    assert '策略运行明细' in report
    for i in range(1, 18):
        assert f'S{i:02d}' in report
    assert 'N2Q' in report and 'N6Q' in report


def test_structure_feature_hash_mismatch_never_triggers_structural_generation():
    router = api()
    result = router.assess_strategies('ANGSTNATMG', '', {}, {}, set(), {'structure_sha256': 'foreign', 'features': []}, {}, 'unknown', [])
    assert result['profile']['hydrophobic_patch']['status'] == 'unknown'
    assert result['profile']['flexibility_hotspot']['status'] == 'unknown'


def test_no_chemical_motif_is_not_triggered_instead_of_failure():
    from app.services.thermostability_workflow import build_screen
    rows = build_screen('AAAA', analysis_mode='exploration').get('strategy_runs', [])
    assert len(rows) == 17
    assert next(r for r in rows if r['id'] == 'S12')['status'] == 'not_triggered'


def structural(sequence, coordinates=None, **extra):
    import hashlib
    from app.services.pdb_parser import _AA3TO1
    names = {v:k for k,v in _AA3TO1.items()}
    lines, mapping, features = [], {}, []
    for p, wt in enumerate(sequence,1):
        x,y,z = (coordinates or {}).get(p, (p*4.,0.,0.))
        for atom,dx in [('N',-1.),('CA',0.),('C',1.),('O',1.5),('CB',0.5)]:
            lines.append(f'ATOM  {len(lines)+1:5d} {atom:^4} {names[wt]:3} A{p+10:4d}    {x+dx:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C')
        mapping[p] = ('A',p+10,None)
        features.append(dict(chain_id='A',pdb_residue_no=p+10,wild_type=wt,rel_sasa=.8,
            rel_sasa_status='computed_from_input_pdb',rel_sasa_source='biopython_shrake_rupley_tien_max_asa',
            atom_count=5,ca_coord=dict(x=x,y=y,z=z),secondary_structure='loop',
            secondary_structure_source='dssp',phi_deg=-65.,psi_deg=130.,**extra))
    pdb = '\n'.join(lines)+'\nEND\n'
    evidence = dict(structure_sha256=hashlib.sha256(pdb.encode()).hexdigest(), features=features)
    return pdb,mapping,evidence


@pytest.mark.parametrize('strategy,sequence,expected', [
    ('S03','AAAA','A1C:A4C'), ('S04','DAA','A2K'),
    ('S07','AAAA','A1P'), ('S09','DDAA','A3E'),
    ('S10','LLL','L1Q'), ('S12','NGAA','N1Q'), ('S13','MAAA','M1L'),
])
def test_individual_generators_use_real_features_and_author_numbering(strategy,sequence,expected):
    router = api()
    coords = {1:(0.,0.,0.),2:(4.,0.,0.),3:(0.,4.,0.),4:(0.,0.,5.)}
    pdb,mapping,evidence = structural(sequence,coords)
    receipt = router.assess_strategies(sequence,pdb,mapping,{},set(),evidence,{},'swiss-model',[])
    run = next(r for r in receipt['strategy_runs'] if r['id']==strategy)
    assert run['trigger_status']=='hit'
    assert expected in {r['mutation'] for r in run['raw_candidates']}
    assert all(r['validation_status']=='pending_mutant_geometry' for r in run['raw_candidates'])
    assert all(r['author_coordinates'][0]['author_residue_number']>=11 for r in run['raw_candidates'])


def test_protected_positions_are_removed_from_every_strategy_including_pairs():
    router=api()
    pdb,mapping,evidence=structural('DNGM')
    receipt=router.assess_strategies('DNGM',pdb,mapping,{}, {1,2,3,4}, evidence,{},'unknown',[])
    assert not receipt['generated']
    assert all(not r['raw_candidates'] for r in receipt['strategy_runs'])


def test_model_bfactor_never_triggers_flexibility_and_unknown_ss_is_not_loop():
    router=api()
    pdb,mapping,evidence=structural('AAAA')
    for r in evidence['features']:
        r.update(secondary_structure='unknown',secondary_structure_source='not_available',b_factor=99.)
    receipt=router.assess_strategies('AAAA',pdb,mapping,{},set(),evidence,{},'alphafold',[])
    assert receipt['profile']['flexibility_hotspot']['status']=='unknown'
    assert receipt['profile']['pro_compatible_loop']['status']=='unknown'


def test_fully_assigned_helix_without_pro_compatible_loop_is_known_negative():
    router=api()
    pdb,mapping,evidence=structural('AAAAA')
    for row in evidence['features']:
        row.update(secondary_structure='helix',secondary_structure_source='pdb_helix_sheet_records')
    receipt=router.assess_strategies('AAAAA',pdb,mapping,{},set(),evidence,{},'unknown',[])
    pro=next(r for r in receipt['strategy_runs'] if r['id']=='S07')
    assert pro['status']=='completed_zero_candidates'


def test_arbitrary_loop_label_without_source_does_not_claim_negative_pro_screen():
    router=api()
    pdb,mapping,evidence=structural('AAAA')
    for row in evidence['features']:
        row.update(secondary_structure_source='not_available',phi_deg=None)
    receipt=router.assess_strategies('AAAA',pdb,mapping,{},set(),evidence,{},'unknown',[])
    assert receipt['profile']['pro_compatible_loop']['status']=='unknown'


def test_already_annotated_helix_ion_pair_does_not_turn_into_a_single_design():
    router=api()
    pdb,mapping,evidence=structural('EAAAK')
    for row in evidence['features']:
        row.update(secondary_structure='helix',secondary_structure_source='dssp')
    receipt=router.assess_strategies('EAAAK',pdb,mapping,{},set(),evidence,{},'unknown',[])
    row=next(r for r in receipt['strategy_runs'] if r['id']=='S08')
    assert row['raw_count']==0


def test_report_distinguishes_unmapped_sequence_only_hypotheses():
    from app.services.thermostability_workflow import build_screen
    from app.services.thermostability_report import render_thermostability_report
    report=render_thermostability_report(build_screen('NGAA',analysis_mode='exploration'))
    assert '未映射' in report


def test_glycosylation_motif_is_not_evidence_that_removal_is_safe():
    router=api()
    pdb,mapping,evidence=structural('NAT')
    receipt=router.assess_strategies('NAT',pdb,mapping,{},set(),evidence,{},'unknown',[])
    row=next(r for r in receipt['strategy_runs'] if r['id']=='S11')
    assert row['trigger_status']=='hit' and row['status']=='blocked_missing_evidence'
    assert not row['raw_candidates']
    allowed=router.assess_strategies('NAT',pdb,mapping,{},set(),evidence,{'glycosylation_removal_allowed':True},'unknown',[])
    assert 'N1Q' in {r['mutation'] for r in allowed['generated']}


def test_acidic_ph_downweights_but_does_not_disable_charge_hypotheses():
    router=api()
    pdb,mapping,evidence=structural('DDAA')
    receipt=router.assess_strategies('DDAA',pdb,mapping,{},set(),evidence,{'ph':4.5},'unknown',[])
    charges=next(r for r in receipt['strategy_runs'] if r['id']=='S09')['raw_candidates']
    assert charges and all(r['route_weight']==.5 for r in charges)
    assert all(r['mutation'][-1]=='E' for r in charges), 'user strategy requests same-sign charge expansion, not acid neutralization'


def test_surface_charge_never_relabels_neutralization_as_same_sign_expansion():
    router=api()
    pdb,mapping,evidence=structural('DDAA')
    receipt=router.assess_strategies('DDAA',pdb,mapping,{},set(),evidence,{},'unknown',[])
    run=next(r for r in receipt['strategy_runs'] if r['id']=='S09')
    assert {r['mutation'] for r in run['raw_candidates']} <= {'A3E','A4E'}
    assert run['raw_candidates']


def test_acidic_ph_range_is_not_ignored_by_charge_weighting():
    router=api()
    pdb,mapping,evidence=structural('DDAA')
    receipt=router.assess_strategies('DDAA',pdb,mapping,{},set(),evidence,{'ph_range':[4.,4.5]},'unknown',[])
    charges=next(r for r in receipt['strategy_runs'] if r['id']=='S09')['raw_candidates']
    assert charges and all(r['route_weight']==.5 for r in charges)
    assert receipt['rule_config_sha256']


def test_risky_strategy_metadata_survives_conversion_to_scoring_candidate():
    from app.services.thermostability_workflow import build_screen
    pdb,_,evidence=structural('DDAA')
    result=build_screen('DDAA',pdb_data=pdb,structure_features=evidence,
                         objective={'ph':4.5},analysis_mode='exploration')
    for row in result['preliminary_candidates']:
        if any(s.get('strategy_id') in {'S04','S09'} for s in row['sources']):
            assert 'protonation_not_modelled' in row['risks']
            assert row['strategy_context']['route_weight']==.5


def test_timeout_is_distinct_from_failure():
    router=api()
    def timeout(context,rule):
        raise TimeoutError()
    result=router.route_strategies({'hydrophobic_core':{'status':'hit'}},{},generators={'S02':timeout})
    assert result[1]['status']=='timed_out'


def test_ca_only_input_cannot_claim_disulfide_absence():
    router=api()
    pdb,mapping,evidence=structural('AAAA')
    pdb='\n'.join(line for line in pdb.splitlines() if line[12:16].strip()!='CB')+'\n'
    import hashlib
    evidence['structure_sha256']=hashlib.sha256(pdb.encode()).hexdigest()
    receipt=router.assess_strategies('AAAA',pdb,mapping,{},set(),evidence,{},'unknown',[])
    assert receipt['profile']['cys_pair_candidate']['status']=='unknown'


def test_helix_pair_stays_paired_and_does_not_turn_into_two_single_predictions():
    router=api()
    pdb,mapping,evidence=structural('AAAAA')
    for row in evidence['features']:
        row['secondary_structure']='helix'
    receipt=router.assess_strategies('AAAAA',pdb,mapping,{},set(),evidence,{},'unknown',[])
    helix=next(r for r in receipt['strategy_runs'] if r['id']=='S08')
    assert [r['mutation'] for r in helix['raw_candidates']]==['A1E:A5K']


def test_partial_sasa_cannot_claim_no_patch():
    router=api()
    pdb,mapping,evidence=structural('LLL')
    evidence['features'][0]['rel_sasa']=None
    receipt=router.assess_strategies('LLL',pdb,mapping,{},set(),evidence,{},'unknown',[])
    assert receipt['profile']['hydrophobic_patch']['status']=='unknown'


def test_shared_mutation_preserves_multiple_strategy_sources():
    router=api()
    pdb,mapping,evidence=structural('NSAA')
    receipt=router.assess_strategies('NSAA',pdb,mapping,{},set(),evidence,{'glycosylation_removal_allowed':True},'unknown',[])
    # Direct generator union for S11/S12 is covered with an exposed NST motif.
    pdb,mapping,evidence=structural('NST')
    receipt=router.assess_strategies('NST',pdb,mapping,{},set(),evidence,{'glycosylation_removal_allowed':True},'unknown',[])
    candidate=next(r for r in receipt['generated'] if r['mutation']=='N1Q')
    assert {s['strategy_id'] for s in candidate['sources']}=={'S11','S12'}


@pytest.mark.parametrize('sid',[f'S{i:02d}' for i in range(1,17)])
def test_each_route_retains_exact_generator_output_and_does_not_run_others(sid):
    router=api()
    rules=router.load_rules()
    rule=next(r for r in rules if r['id']==sid)
    candidate={'mutation':'A1V','sources':[{'strategy_id':sid}]}
    calls=[]
    def generate(context, current):
        calls.append(current['id'])
        return [candidate]
    result=router.route_strategies({rule['feature']:{'status':'hit'}},{},generators={sid:generate})
    run=next(r for r in result if r['id']==sid)
    assert calls==[sid]
    assert run['raw_candidates']==[candidate] and run['raw_count']==1
    assert run['filtered_count']==0  # dispatch does not imply geometric acceptance


def test_pending_hypotheses_are_not_described_as_no_specific_mutations():
    from app.services.thermostability_workflow import build_screen
    from app.services.thermostability_report import render_thermostability_report
    result=build_screen('NGAA',analysis_mode='exploration')
    report=render_thermostability_report(result)
    assert '当前尚无证据支持具体替换' not in report
    assert '几何未验证' in report
    assert report.index('工具支持的初步候选') < report.index('原始假设清单')
    assert '95℃' not in report


@pytest.mark.asyncio
async def test_new_strategy_singles_are_scored_but_pairs_are_not_sent_to_single_model(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    calls=[]
    async def score(sequence,codes):
        calls.extend(codes)
        assert all(':' not in code for code in codes)
        return {'status':'completed','predictions':[{'mutation':c,'ddg':.7} for c in codes]}
    monkeypatch.setattr('app.tools.thermostability_adapters.ddgun_predict',score)
    result=await thermostability_candidate_workflow('NGAA',analysis_mode='exploration',run_ddgun=True)
    assert calls==['N1Q']
    assert result['preliminary_candidates'][0]['scores']['ddgun']['ddg']==.7
    assert not result['candidate_output_allowed']
    chemical=next(r for r in result['strategy_runs'] if r['id']=='S12')
    assert chemical['scoring_coverage']['ddgun']=={'requested':1,'returned':1,'complete':True}
    assert chemical['selected_mutations']==['N1Q']


def test_protection_exclusion_is_explained_in_strategy_receipt():
    from app.services.thermostability_workflow import build_screen
    result=build_screen('NGAA',identity_profile={'protected_positions':[1]},analysis_mode='exploration')
    chemical=next(r for r in result['strategy_runs'] if r['id']=='S12')
    assert chemical['status']=='completed_zero_candidates'
    assert chemical['excluded_candidates']==[{'mutation':'N1Q','reason':'known_functional_protection'}]


def test_hydrophobic_core_threshold_is_consistent_with_generator():
    from app.services.thermal_strategy_router import assess_strategies
    pdb,mapping,features=structural('LLL')
    for r in features['features']:
        r['rel_sasa']=.19
    packing=[{'mutation':'L1V','position':1,'sources':[{'kind':'coordinate_packing_probe'}]}]
    result=assess_strategies('LLL',pdb,mapping,{},set(),features,{},'unknown',packing)
    row=next(r for r in result['strategy_runs'] if r['id']=='S02')
    assert row['trigger_status']=='not_hit'
    assert not row['raw_candidates']


def test_baseline_strategy_raw_candidates_always_have_author_numbering():
    router=api()
    pdb,mapping,evidence=structural('LLL')
    for r in evidence['features']:
        r['rel_sasa']=.05
    packing=[{'mutation':'L1V','position':1,'sources':[{'kind':'coordinate_packing_probe'}]}]
    result=router.assess_strategies('LLL',pdb,mapping,{},set(),evidence,{},'unknown',packing)
    row=next(r for r in result['strategy_runs'] if r['id']=='S02')['raw_candidates'][0]
    assert row['author_coordinates'][0]['author_residue_number']==11


def test_partial_feature_coverage_is_explained_not_just_an_unknown_boolean():
    router=api()
    pdb,mapping,evidence=structural('LLL')
    evidence['features'][0]['rel_sasa']=None
    result=router.assess_strategies('LLL',pdb,mapping,{},set(),evidence,{},'unknown',[])
    feature=result['profile']['hydrophobic_patch']
    assert feature['coverage']=={'expected_positions':3,'rsa_positions':2,'ca_positions':3}


@pytest.mark.asyncio
async def test_development_review_keeps_adverse_model_hypotheses_instead_of_hard_filtering(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    pdb,mapping,evidence=structural('LLL')
    for r in evidence['features']:
        r['rel_sasa']=.05
        r['secondary_structure']='unknown'
        r['secondary_structure_source']='not_available'
    async def features(**kwargs):
        return {'status':'completed',**evidence}
    async def score(sequence,codes):
        return {'status':'completed','predictions':[{'mutation':c,'ddg':-.4} for c in codes]}
    monkeypatch.setattr('app.tools.site_structure_function_features.build_site_structure_function_features',features)
    monkeypatch.setattr('app.tools.thermostability_adapters.ddgun_predict',score)
    monkeypatch.setattr('app.services.thermal_structure_hypotheses.packing_probes',
        lambda *a,**kw:[{'mutation':'L1V','position':1,'sources':[{'kind':'coordinate_packing_probe'}]}])
    result=await thermostability_candidate_workflow('LLL',pdb_data=pdb,analysis_mode='exploration',run_ddgun=True)
    assert 'L1V' in {r['mutation'] for r in result['preliminary_candidates']}
    assert result['selection_audit']['model_hard_filter_applied'] is False
    assert result['selection_audit']['adverse_ddgun_exclusions']==[]
    assert result['selection_audit']['adverse_ddgun_review'][0]['mutation']=='L1V'


def test_cavity_generator_requires_measured_volume_and_retains_cavity_evidence():
    router=api()
    rule=next(r for r in router.load_rules() if r['id']=='S01')
    tag={'status':'hit','reason':'enclosed grid fixture','items':[{'cavity_id':'void_1',
        'volume_angstrom3':24.,'centroid_angstrom':[1.,2.,3.],'lining_positions':[1]}]}
    context=dict(sequence='A',mapping={1:('A',11,None)},risks={},protected=set(),
        rows={1:{'rel_sasa':.05}},profile={'buried_cavity':tag},objective={},packing=[],
        sequence_sha256='sequence',structure_sha256='structure',thresholds=router.configuration()['thresholds'])
    row=router.route_strategies({'buried_cavity':tag},context)[0]
    assert row['status']=='completed_candidates'
    candidate=row['raw_candidates'][0]
    assert candidate['mutation']=='A1V'
    assert candidate['cavity_evidence']['volume_angstrom3']==24.
    assert candidate['validation_status']=='pending_mutant_geometry'


@pytest.mark.asyncio
async def test_failed_feature_tool_preserves_explicit_scores_and_seventeen_receipts(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    pdb,_,_=structural('AAAA')
    async def fail(**kwargs):
        raise ValueError('controlled failure')
    monkeypatch.setattr('app.tools.site_structure_function_features.build_site_structure_function_features',fail)
    result=await thermostability_candidate_workflow('AAAA',pdb_data=pdb,mutations=['A1V'],analysis_mode='exploration')
    assert len(result['strategy_runs'])==17
    assert result['structure_feature_receipt']['status']=='failed'
    assert result['preliminary_candidates'][0]['mutation']=='A1V'


@pytest.mark.asyncio
async def test_missing_ddgun_prediction_is_reported_without_losing_other_results(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    async def incomplete(*args):
        return {'status':'completed','predictions':[]}
    monkeypatch.setattr('app.tools.thermostability_adapters.ddgun_predict',incomplete)
    result=await thermostability_candidate_workflow('AAAA',mutations=['A1V'],analysis_mode='exploration',run_ddgun=True)
    assert result['branches']['ddgun']['status']=='blocked'
    assert result['preliminary_candidates'][0]['scores']['ddgun'] is None
