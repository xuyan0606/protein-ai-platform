"""Auditable strategy routing. Generated hypotheses are not validated designs."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev


def configuration():
    return json.loads(Path(__file__).with_name('thermal_strategy_rules.json').read_text())


def load_rules():
    return configuration()['strategies']


class MissingEvidence(Exception):
    pass


def route_strategies(profile, context, *, generators=None):
    generators = GENERATORS if generators is None else generators
    rows = []
    config = configuration()
    for rule in config['strategies']:
        tag = profile.get(rule['feature'], {'status': 'unknown', 'reason': rule.get('dependency', '缺少特征证据')})
        row = {**rule, 'configured': True, 'evaluation_status': 'evaluated',
               'trigger_status': tag['status'], 'evidence': tag,
               'raw_candidates': [], 'filtered_candidates': [], 'raw_count': 0, 'filtered_count': 0,
               'generator_status': 'not_run', 'status': 'blocked_missing_evidence',
               'reason': tag.get('reason', ''), 'test_level': 'deterministic_rule_only',
               'rule_version': config['version'], 'excluded_candidates': [],
               'implementation_status': 'implemented' if rule['id'] in generators else 'not_implemented'}
        rows.append(row)
        if rule['tier'] == 'postprocess':
            row.update(status='not_run', reason='在候选合并后记录每个突变的几何覆盖；本行不生成突变')
            continue
        if tag['status'] == 'unknown':
            continue
        if rule['tier'] == 'T2' and tag['status'] == 'not_hit':
            row['status'] = 'not_triggered'
            continue
        generator = generators.get(rule['id'])
        if generator is None:
            row.update(status='not_implemented', reason=rule.get('dependency', '生成器未实现'))
            continue
        try:
            context['_excluded'] = []
            raw = generator(context, rule)
            row.update(raw_candidates=raw, raw_count=len(raw), generator_status='completed',
                       status='completed_candidates' if raw else 'completed_zero_candidates',
                       excluded_candidates=context['_excluded'])
            if raw:
                row['reason'] = '已生成待复核假设；几何校验、功能保护和独立评分另行记录'
            elif context['_excluded']:
                row['reason'] = '特征命中，但所有替换被保护/结构约束排除；详见逐项排除原因'
        except MissingEvidence as exc:
            row.update(status='blocked_missing_evidence', generator_status='blocked', reason=str(exc))
        except TimeoutError:
            row.update(status='timed_out', generator_status='timed_out', reason='生成器超时，保留其他策略结果')
        except Exception as exc:
            row.update(status='failed', generator_status='failed', reason=f'生成器失败：{type(exc).__name__}')
    return rows


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _tag(items, reason, *, complete=True):
    return {'status': 'hit' if items else 'not_hit' if complete else 'unknown',
            'items': items, 'reason': reason, 'coverage_complete': complete}


def _pairs(rows, distance):
    """Spatially bounded CA pair enumeration, deterministic input position order."""
    grid = defaultdict(list)
    for pos, xyz in sorted(rows.items()):
        cell = tuple(math.floor(v / distance) for v in xyz)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other, coordinate in grid[(cell[0]+dx, cell[1]+dy, cell[2]+dz)]:
                        gap = math.dist(xyz, coordinate)
                        if gap <= distance:
                            yield other, pos, gap
        grid[cell].append((pos, xyz))


def _components(positions, pairs, minimum):
    links = {p: set() for p in positions}
    for p, q, _ in pairs:
        links[p].add(q)
        links[q].add(p)
    groups, seen = [], set()
    for p in sorted(positions):
        if p in seen:
            continue
        stack, group = [p], []
        while stack:
            q = stack.pop()
            if q in seen:
                continue
            seen.add(q)
            group.append(q)
            stack.extend(sorted(links[q] - seen, reverse=True))
        if len(group) >= minimum:
            groups.append(sorted(group))
    return groups


def assess_strategies(sequence, pdb_data, mapping, risks, protected, features, objective, structure_source, packing):
    settings = configuration()
    limits = settings['thresholds']
    profile = {r['feature']: {'status': 'unknown', 'reason': r.get('dependency', '上游结构或上下文证据缺失')} for r in load_rules()}
    digest = hashlib.sha256(pdb_data.encode()).hexdigest()
    reverse = {key: pos for pos, key in mapping.items()}
    validated = bool(pdb_data and features and features.get('structure_sha256') == digest)
    rows = {}
    for row in (features or {}).get('features', []) if validated else []:
        key = (row.get('chain_id'), row.get('pdb_residue_no'), row.get('insertion_code') or None)
        pos = reverse.get(key)
        if pos and row.get('wild_type') == sequence[pos-1]:
            rows[pos] = row
    complete = bool(mapping) and len(rows) == len(sequence)
    exposed = {p: r for p, r in rows.items() if _finite(r.get('rel_sasa'))
               and r.get('rel_sasa_status') == 'computed_from_input_pdb'
               and 0 <= r['rel_sasa'] <= 1}
    sasa_complete = complete and len(exposed) == len(sequence)
    coords = {p: tuple(r['ca_coord'][k] for k in ('x', 'y', 'z')) for p, r in rows.items()
              if isinstance(r.get('ca_coord'), dict) and all(_finite(r['ca_coord'].get(k)) for k in ('x', 'y', 'z'))}
    surface = {p for p, r in exposed.items() if r['rel_sasa'] > limits['surface_rsa']}
    profile['hydrophobic_core'] = _tag([p for p, r in exposed.items() if r['rel_sasa'] <= limits['core_rsa']
        and sequence[p-1] in 'AVILMFYW'], 'RSA核心阈值与输入WT核对；不等同空腔检测', complete=sasa_complete)
    pairs = list(_pairs(coords, limits['saltbridge_max_angstrom']))
    charge_pairs = [[p, q, round(d, 3)] for p, q, d in pairs
                    if p in surface and q in surface and limits['saltbridge_min_angstrom'] <= d
                    and (sequence[p-1] in 'DEKR' or sequence[q-1] in 'DEKR')]
    profile['charge_pair'] = _tag(charge_pairs, '表面CA距离4–8Å仅供生成探针，不代表侧链已成盐桥', complete=sasa_complete and len(coords) == len(sequence))
    acidic = {p for p in surface if sequence[p-1] in 'DE' and p in coords}
    clusters = _components(acidic, [(p,q,d) for p,q,d in pairs if p in acidic and q in acidic], 2)
    profile['surface_charge'] = _tag(clusters, '表面酸性残基空间簇；与S04异号离子对机制分开', complete=sasa_complete and len(coords) == len(sequence))
    hydrophobic = {p for p in surface if exposed[p]['rel_sasa'] > limits['patch_rsa'] and sequence[p-1] in 'AVILMFWY' and p in coords}
    patches = _components(hydrophobic, [(p,q,d) for p,q,d in pairs if p in hydrophobic and q in hydrophobic], limits['patch_min_residues'])
    profile['hydrophobic_patch'] = _tag(patches, '表面疏水残基按CA空间连通簇初筛；功能表位仍需复核', complete=sasa_complete and len(coords) == len(sequence))
    motifs = [i+1 for i in range(len(sequence)-2) if sequence[i] == 'N' and sequence[i+1] != 'P' and sequence[i+2] in 'ST']
    profile['glycosylation_motif'] = _tag([p for p in motifs if p in surface], 'N-X-S/T且表面暴露；motif不证明实际糖基化', complete=not motifs or all(p in exposed for p in motifs))
    chemical = [i+1 for i in range(len(sequence)-1) if sequence[i:i+2] in {'NG','NS','NT','DG'}]
    profile['deamidation_site'] = _tag(chemical, '序列化学敏感基序；仅为降解风险假设，不推断耐热收益')
    oxidizable = [p for p in surface if sequence[p-1] in 'MCWY']
    profile['oxidation_site'] = _tag(oxidizable, '表面氧化敏感残基；是否为瓶颈需工艺证据', complete=sasa_complete)
    for feature in ('hydrophobic_core', 'charge_pair', 'surface_charge', 'hydrophobic_patch', 'oxidation_site'):
        coverage = {'expected_positions': len(sequence), 'rsa_positions': len(exposed)}
        if feature in {'charge_pair', 'surface_charge', 'hydrophobic_patch'}:
            coverage['ca_positions'] = len(coords)
        tag = profile[feature]
        tag['coverage'] = coverage
        if not tag['coverage_complete']:
            missing = [f'RSA已核验{len(exposed)}/{len(sequence)}个位点']
            if 'ca_positions' in coverage:
                missing.append(f'CA坐标已核验{len(coords)}/{len(sequence)}个位点')
            tag['reason'] += '；证据覆盖不完整：' + '，'.join(missing)
    if str(objective.get('protease', '')).lower() in {'trypsin', '胰蛋白酶'}:
        sites = [i+1 for i, wt in enumerate(sequence[:-1]) if wt in 'KR' and sequence[i+1] != 'P']
        profile['proteolysis_site'] = _tag(sites, '用户指定胰蛋白酶：K/R后切割且下一残基非Pro的规则初筛')
    loop_rows = {p:r for p,r in rows.items() if r.get('secondary_structure') in {'loop','turn','coil'}
                 and r.get('secondary_structure_source') in {'dssp','mkdssp','curated'}
                 and _finite(r.get('phi_deg')) and -90 <= r['phi_deg'] <= -40}
    ss_complete = complete and all(
        r.get('secondary_structure') not in {None,'unknown','unannotated_or_loop'}
        and r.get('secondary_structure_source') in {'dssp','mkdssp','curated','pdb_helix_sheet_records'}
        and (r.get('secondary_structure') not in {'loop','turn','coil'} or _finite(r.get('phi_deg')))
        for r in rows.values())
    profile['pro_compatible_loop'] = _tag(sorted(loop_rows), '需有来源的loop/turn及Pro适配phi；不把未注释区当loop', complete=ss_complete)
    helices = [p for p in sorted(rows) if p+4 in rows and all(
        rows.get(q, {}).get('secondary_structure') in {'helix','alpha_helix','H'} for q in range(p,p+5))]
    profile['helix_pair'] = _tag(helices, '连续α螺旋i/i+4初筛；侧链取向未验证',
        complete=ss_complete)
    if structure_source.lower() in {'experimental', 'xray', 'x-ray'} and any(
            line.startswith('EXPDTA') and 'X-RAY' in line.upper() for line in pdb_data.splitlines()):
        bvalues = {p:r['b_factor'] for p,r in rows.items() if _finite(r.get('b_factor')) and r['b_factor'] >= 0}
        if len(bvalues) == len(sequence) and bvalues:
            window = limits['bfactor_window']
            cutoff = mean(bvalues.values()) + limits['bfactor_sigma']*pstdev(bvalues.values())
            hotspots = set()
            for p in range(1, len(sequence)-window+2):
                if mean(bvalues[q] for q in range(p,p+window)) > cutoff:
                    hotspots.update(range(p,p+window))
            profile['flexibility_hotspot'] = _tag(sorted(hotspots), '来源已核对的X射线B因子滑窗阈值；仍受晶体环境影响')
    else:
        profile['flexibility_hotspot'] = {'status':'unknown', 'reason':'没有已核对的实验B因子来源；模型原始字段/pLDDT不可当柔性'}
    atoms, environment = {}, []
    if pdb_data:
        from app.services.structure_records import pdb_records
        records, models, _ = pdb_records(pdb_data)
        for atom in records:
            key = (atom['chain_id'], atom['residue_number'], atom.get('insertion_code') or None)
            if atom['model_id'] == models[0] and atom['occupancy'] > 0 and atom['altloc'] in {'','A'}:
                if key in reverse:
                    atoms.setdefault(reverse[key], {})[atom['atom_name']] = atom['coordinates']
                if atom.get('element') not in {'H','D'} and atom['component_id'] not in {'HOH','WAT','DOD'}:
                    environment.append(atom)
    cavity_receipt = {'status':'blocked','reason':'missing_or_unverified_structure_features'}
    if validated and environment:
        from app.services.thermal_cavity import detect_enclosed_cavities
        cavity_receipt = detect_enclosed_cavities(environment, spacing=limits['cavity_grid_spacing_angstrom'],
            minimum_volume=limits['cavity_minimum_volume_angstrom3'], max_grid_points=limits['cavity_max_grid_points'])
        if cavity_receipt['status']=='completed':
            voids=[]
            for cavity in cavity_receipt['cavities']:
                voids.append({**cavity,'lining_positions':sorted(reverse[tuple(key)] for key in cavity['lining_residue_keys'] if tuple(key) in reverse)})
            profile['buried_cavity'] = _tag(voids, '实际封闭vdW网格体积；可扩侧链仍需逐突变几何验证')
            profile['buried_cavity']['detector'] = {k:v for k,v in cavity_receipt.items() if k!='cavities'}
        else:
            profile['buried_cavity'] = {'status':'unknown','reason':cavity_receipt.get('reason','cavity_detector_failed')}
    cb = {p:a['CB'] for p,a in atoms.items() if 'CB' in a and sequence[p-1] != 'C'}
    disulfides = [[p,q,round(d,3)] for p,q,d in _pairs(cb, limits['disulfide_cb_max_angstrom'])
                 if abs(p-q)>2 and d >= limits['disulfide_cb_min_angstrom']]
    profile['cys_pair_candidate'] = _tag(disulfides, '实际Cβ距离初筛；未验证S–S二面角、应变或折叠',
        complete=bool(mapping) and all(sequence[p-1] in 'CG' or 'CB' in atoms.get(p,{}) for p in mapping))
    context = dict(sequence=sequence, mapping=mapping, risks=risks, protected=protected, rows=rows, coords=coords,
                   profile=profile, objective=objective, packing=packing, structure_sha256=digest,
                   sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest(), thresholds=limits)
    runs = route_strategies(profile, context)
    generated = {}
    for run in runs:
        for candidate in run['raw_candidates']:
            code = candidate['mutation']
            if code not in generated:
                generated[code] = {**candidate, 'sources': list(candidate['sources'])}
            else:
                generated[code]['sources'].extend(candidate['sources'])
    baseline = {p['mutation'] for p in packing}
    run = runs[-1]
    pending = [r for code,r in generated.items() if code not in baseline]
    run.update(status='partial' if generated else 'completed_zero_candidates', evaluation_status='evaluated',
               generator_status='not_applicable', trigger_status='hit' if generated else 'not_hit',
               checked_count=sum(1 for c in generated.values() if any(s.get('geometry_screen',{}).get('rotamers_without_severe_overlap',0)>0 for s in c['sources'])),
               pending_count=sum(1 for c in generated.values() if not any(s.get('geometry_screen',{}).get('rotamers_without_severe_overlap',0)>0 for s in c['sources'])),
               reason='A→V沿用固定环境预筛；其余突变缺少通用构象/能量优化，列入待校验清单，不宣称clash通过')
    return {'profile':profile, 'strategy_runs':runs, 'generated':list(generated.values()),
            'pending_geometry':pending, 'rule_version':settings['version'], 'cavity_receipt':cavity_receipt,
            'rule_config_sha256':hashlib.sha256(json.dumps(settings,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'effective_thresholds':limits}


def _hypothesis(context, rule, changes, rationale):
    seq = context['sequence']
    substitutions = []
    coordinates = []
    for pos, mt in changes:
        reason = ('known_functional_protection' if pos in context['protected'] else
                  'structure_risk:' + ','.join(sorted(context['risks'][pos])) if context['risks'].get(pos) else
                  'missing_structure_mapping' if context['mapping'] and pos not in context['mapping'] else None)
        feature = context['rows'].get(pos, {})
        distance = feature.get('nearest_nonpolymer_heteroatom_distance_angstrom')
        if feature.get('is_catalytic') or feature.get('is_protected') or (_finite(distance) and distance <= 6):
            reason = 'protected_feature_or_ligand_neighbourhood'
        if reason:
            context.setdefault('_excluded', []).append({'mutation':':'.join(f'{seq[p-1]}{p}{m}' for p,m in changes), 'reason':reason})
            return None
        if seq[pos-1] == mt:
            continue
        substitutions.append(f'{seq[pos-1]}{pos}{mt}')
        key = context['mapping'].get(pos)
        coordinates.append({'input_position':pos, 'chain_id':key[0], 'author_residue_number':key[1], 'insertion_code':key[2]} if key else {'input_position':pos, 'mapping_status':'unmapped'})
    if not substitutions:
        return None
    return {'mutation':':'.join(substitutions), 'mutations':substitutions, 'positions':[p for p,_ in changes],
            'author_coordinates':coordinates, 'rationale':rationale, 'validation_status':'pending_mutant_geometry',
            'risks':['unverified_thermal_and_activity_effect','incomplete_functional_protection'],
            'sources':[{'kind':'strategy_hypothesis', 'strategy_id':rule['id'],
                'reference':rule['feature'], 'sequence_sha256':context['sequence_sha256'],
                'structure_sha256':context['structure_sha256'], 'geometry_screen':{'method':'not_evaluated','mutant_relaxed':False}}]}


def _generate(context, rule):
    sid, seq = rule['id'], context['sequence']
    items = context['profile'][rule['feature']].get('items',[])
    changes = []
    if sid == 'S01':
        alternatives={'G':('A','V'),'A':('V','L','I'),'S':('V','L')}
        result=[]
        for cavity in items:
            for p in cavity['lining_positions']:
                feature=context['rows'].get(p,{})
                if not _finite(feature.get('rel_sasa')) or feature['rel_sasa']>=.2:
                    continue
                for mt in alternatives.get(seq[p-1],()):
                    row=_hypothesis(context,rule,[(p,mt)],context['profile'][rule['feature']]['reason'])
                    if row:
                        row['cavity_evidence']={k:v for k,v in cavity.items() if k!='lining_residue_keys'}
                        result.append(row)
                    if len(result)>=context['thresholds']['max_hypotheses_per_strategy']:
                        return result
        return result
    if sid == 'S02':
        result = []
        for row in context['packing']:
            if row['position'] not in items:
                continue
            pos = row['position']
            key = context['mapping'].get(pos)
            coordinate = ({'input_position': pos, 'chain_id': key[0],
                           'author_residue_number': key[1], 'insertion_code': key[2]}
                          if key else {'input_position': pos, 'mapping_status': 'unmapped'})
            result.append({**row, 'author_coordinates': [coordinate],
                           'validation_status': row.get('validation_status', 'see_source_geometry'),
                           'sources': [{**s, 'strategy_id': sid} for s in row['sources']]})
        return result
    if sid in {'S06','S07'}:
        eligible = set(context['profile']['pro_compatible_loop'].get('items',[]))
        if sid == 'S06' and items and context['profile']['pro_compatible_loop']['status'] == 'unknown':
            raise MissingEvidence('热点已找到，但缺有来源的二级结构/Pro主链构象证据')
        changes = [[(p,'P')] for p in items if p in eligible and seq[p-1] not in 'PG']
    elif sid == 'S03':
        changes = [[(p,'C'),(q,'C')] for p,q,_ in items]
    elif sid == 'S04':
        for p,q,_ in items:
            for a,b in ((p,q),(q,p)):
                if seq[a-1] in 'DE' and seq[b-1] not in 'DEKR':
                    changes.append([(b,'K')])
                elif seq[a-1] in 'KR' and seq[b-1] not in 'DEKR':
                    changes.append([(b,'E')])
    elif sid == 'S08':
        changes = [[(p,'E'),(p+4,'K')] for p in items if seq[p-1]!='E' and seq[p+3]!='K']
    elif sid == 'S09':
        # User strategy: expand a same-sign surface network, never silently
        # substitute acid neutralization (which is a different mechanism).
        centres={p for group in items for p in group}
        for p,feature in sorted(context['rows'].items()):
            if (seq[p-1] not in 'AGSTNQ' or not _finite(feature.get('rel_sasa'))
                    or feature['rel_sasa'] <= context['thresholds']['surface_rsa']):
                continue
            if p in context['coords'] and any(math.dist(context['coords'][p],context['coords'][q])
                    <= context['thresholds']['patch_distance_angstrom'] for q in centres):
                changes.append([(p,'E')])
    elif sid == 'S10':
        alternatives = {'A':'S','V':'T','I':'T','L':'Q','M':'Q','F':'Y','W':'Y','Y':'S'}
        changes = [[(p,alternatives[seq[p-1]])] for group in items for p in group]
    elif sid == 'S11':
        if context['objective'].get('glycosylation_removal_allowed') is not True:
            raise MissingEvidence('表面motif已命中；需确认表达宿主和糖基化依赖后才生成去除设计')
        changes = [[(p,'Q')] for p in items]
    elif sid == 'S12':
        changes = [[(p, 'Q' if seq[p-1]=='N' else 'E')] for p in items]
    elif sid == 'S13':
        changes = [[(p,{'M':'L','C':'S','W':'F','Y':'F'}[seq[p-1]])] for p in items]
    elif sid == 'S14':
        changes = [[(p,'Q')] for p in items]
    result, seen = [], set()
    for change in changes:
        row = _hypothesis(context, rule, change, context['profile'][rule['feature']]['reason'])
        if row and row['mutation'] not in seen:
            seen.add(row['mutation'])
            if sid in {'S04','S09'}:
                ph = context['objective'].get('ph')
                ph_range=context['objective'].get('ph_range')
                valid_range=isinstance(ph_range,list) and len(ph_range)==2 and all(_finite(v) for v in ph_range)
                acidic=(_finite(ph) and ph < context['thresholds']['acidic_ph_threshold'] or
                         valid_range and min(ph_range)<context['thresholds']['acidic_ph_threshold'])
                row['ph_context'] = ph if _finite(ph) else ph_range if valid_range else 'unknown'
                row['route_weight'] = context['thresholds']['acidic_charge_weight'] if acidic else 1.0
                row['weight_scope']='route_priority_only_not_a_calibrated_energy_or_success_probability'
                row['risks'].append('protonation_not_modelled')
                if sid=='S09':
                    row['risks'].append('same_sign_charge_may_destabilize_fold_or_alter_activity')
            if sid in {'S06','S07'}:
                row['risks'].extend(['conservation_not_evaluated','pro_backbone_hbond_not_evaluated'])
            result.append(row)
        if len(result) >= context['thresholds']['max_hypotheses_per_strategy']:
            break
    return result


GENERATORS = {f'S{i:02d}': _generate for i in (1,2,3,4,6,7,8,9,10,11,12,13,14)}
