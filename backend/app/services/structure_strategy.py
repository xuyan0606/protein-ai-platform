"""Plan uploaded-structure work from the question, parsed entities and runtimes.

Planning is reproducible. Deep mode permits more evidence gathering; it does
not authorize unrelated tools, remote jobs or mutation design by itself.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil
from typing import Any

from app.core.config import settings
from app.ml.config import ml_settings
from app.services.structure_intent import parse_structure_intent
from app.services.evidence_scope import evidence_scope
from app.services.property_workflow_governance import PropertyWorkflowRouter


GLYCANS = frozenset({'NAG', 'NDG', 'BMA', 'MAN', 'FUC', 'FUL', 'GAL', 'GLC', 'SIA', 'NAN', 'G6D'})
SOLVENTS = frozenset({'HOH', 'WAT', 'DOD', 'GOL', 'EDO', 'PEG', 'MPD', 'SO4', 'PO4', 'ACT'})
IONS = frozenset({'NA', 'K', 'CL', 'CA', 'MG', 'ZN', 'MN', 'FE', 'CU', 'CO', 'NI', 'CD'})


def _executable(value: str) -> bool:
    path = shutil.which(value) if value else None
    return bool(path and Path(path).name not in {'true', 'false', 'echo', 'printf'} and os.access(path, os.X_OK))


def structure_runtime_capabilities() -> dict[str, bool]:
    # This is a local readiness check, never a download or a claim of inference.
    binary = settings.FOLDSEEK_BINARY or 'foldseek'
    db = settings.FOLDSEEK_DATABASE_PDB or settings.FOLDSEEK_DATABASE_ROOT
    foldseek = bool(settings.FOLDSEEK_API_URL) or bool(
        _executable(binary) and db and Path(db).exists()
    )
    pocket = any(_executable(os.getenv(key, '') or default) for key, default in (
        ('P2RANK_BINARY', 'prank'), ('FPOCKET_BINARY', 'fpocket'),
    ))
    # Merely installing torch is not proof that the ESM weights are available.
    cache = Path(os.getenv('TORCH_HOME', str(Path.home() / '.cache/torch'))) / 'hub/checkpoints'
    model_name = ml_settings.ESM2_MODEL
    esm2 = (all(importlib.util.find_spec(name) is not None for name in ('torch', 'esm'))
            and (cache / f'{model_name}.pt').is_file()
            and (cache / f'{model_name}-contact-regression.pt').is_file())
    return {'foldseek': foldseek, 'pocket': pocket, 'esm2': esm2}


def theoretical_template_evidence(preflight: dict[str, Any]) -> dict[str, Any] | None:
    """Return header-declared template evidence for theoretical/homology models."""
    theoretical = preflight.get('theoretical_model') if isinstance(preflight.get('theoretical_model'), dict) else {}
    if not theoretical.get('is_theoretical'):
        return None
    return {
        'source': theoretical.get('source') or 'theoretical model',
        'is_theoretical': True,
        'templates': theoretical.get('templates') or [],
        'template_sequence_identity': theoretical.get('template_sequence_identity'),
        'template_coverage': theoretical.get('template_coverage'),
        'gmqe': theoretical.get('gmqe'),
        'qmean': theoretical.get('qmean'),
        'qmean_z': theoretical.get('qmean_z'),
        'provenance': 'model_header_declared',
    }


def select_structure_strategy(
    question: str, preflight: dict[str, Any], *, object_name: str,
    pdb_id: str = '', uniprot_id: str = '', depth: str = 'standard',
    tools: set[str], runtimes: dict[str, bool],
) -> dict[str, Any]:
    """Return executable rows plus the reasons and work deliberately deferred."""
    intent = parse_structure_intent(question)
    offline, lower = intent['offline'], intent['positive_text']
    chains = [c for c in preflight.get('chains', []) if isinstance(c, dict) and c.get('sequence')]
    if intent['chain_ids']:
        missing = set(intent['chain_ids']) - {str(c.get('chain_id')) for c in chains}
        matched = [c for c in chains if str(c.get('chain_id')) in intent['chain_ids']]
        if missing:
            return {'steps': [], 'logic': [], 'deferred': [], 'error': f'结构中没有请求的链 {", ".join(sorted(missing))}；可用链：' + ', '.join(str(c.get('chain_id')) for c in chains)}
        chains = matched
    if not chains:
        return {'steps': [], 'logic': [], 'deferred': [], 'error': '预读没有得到可用蛋白链；请核对结构文件。'}

    quality = any(x in lower for x in ('质控', '质量', '缺失', '坐标编号', 'quality', 'missing residues'))
    stability = any(x in lower for x in ('稳定性', '热稳定', '耐热', '二硫键', '盐桥', 'stability', 'thermostab', 'disulfide', 'salt bridge'))
    homology = any(x in lower for x in ('blast', '同源', '保守', '家族', 'homolog', 'conservation', 'family'))
    pocket = any(x in lower for x in ('口袋', '通道', 'pocket', 'p2rank', 'fpocket', 'tunnel'))
    contacts = pocket or any(x in lower for x in ('配体', '底物', '糖基化', '糖链', 'ligand', 'glycan', 'substrate'))
    interfaces = any(x in lower for x in ('界面', '复合物', '寡聚', 'interface', 'complex', 'oligomer'))
    properties = any(x in lower for x in ('理化', '序列性质', '溶解', '等电', '分子量', 'physicochem', 'solubility', 'sequence properties'))
    function = any(x in lower for x in ('功能', '催化', '活性', 'function', 'catalytic', 'activity', 'esm-2', 'esm2'))
    site_design = any(x in lower for x in ('分析位点', '位点分析', '可突变', '突变位点', 'site-directed', 'mutation site'))
    function = function or site_design
    if site_design:
        pocket = True
        contacts = True
    generic = not any((quality, stability, homology, contacts, interfaces, properties, function))
    deep = depth == 'deep' or any(x in lower for x in ('深度', '深入', '全面', 'deep', 'comprehensive'))
    title_parts = [name for flag, name in (
        (quality, '结构质量与编号'), (stability, '稳定性结构网络'), (homology, '家族与同源证据'),
        (contacts, '组分接触与口袋核验'), (interfaces, '链界面'), (properties, '序列性质'), (function, '功能证据'),
    ) if flag]
    title = '、'.join(title_parts) if title_parts else '结构、构建体与功能背景分析'
    result: dict[str, Any] = {'title': title, 'steps': [], 'logic': [], 'deferred': [],
                              'chain_ids': [c['chain_id'] for c in chains], 'intent': intent,
                              'forbidden_tools': intent['forbidden_tools'], 'offline': offline}
    rows, logic, deferred = result['steps'], result['logic'], result['deferred']

    def add(tool: str, reason: str, params: dict[str, Any]) -> None:
        if tool in intent['forbidden_tools']:
            deferred.append(f'{tool} 已按用户限制排除。')
            return
        if tool not in tools:
            deferred.append(f'{tool} 未注册，暂不执行：{reason}')
            return
        scope = evidence_scope({**params, 'content_sha256': preflight.get('content_sha256'),
                                'model_scope': preflight.get('model_scope')})
        supported = {
            'structure_search_foldseek': ['quality', 'homology'], 'residue_mapping_sifts': ['quality', 'function'],
            'predict_properties': ['properties'], 'build_site_structure_function_features': ['quality', 'stability'],
            'disulfide_saltbridge_scan': ['stability'], 'enzyme_identity_profile': ['function', 'homology'],
            'annotation_bundle': ['function', 'homology'], 'blast_search': ['homology', 'function'],
            'ligand_contact_analysis': ['contacts'], 'pocket_residue_lookup': ['pocket'],
            'structure_pocket_interface_analysis': ['interfaces'], 'enzyme_function': ['function'],
        }.get(tool, [])
        contract = {
            'answers': supported,
            'why': reason,
            'requires': ('同一上传对象中的蛋白链坐标与明确的编号范围。' if tool not in {'predict_properties', 'blast_search', 'enzyme_function', 'annotation_bundle'}
                         else '同一输入链的可追溯序列；外部查询还需用户允许联网。'),
            'skip_when': '用户已排除该工具、输入范围不相符或所需运行能力不可用。',
            'on_failure': '保留其他独立可用结果，标记本步骤缺口，不用替代结果冒充完成。',
        }
        rows.append({'tool_name': tool, 'description': reason,
                     'params': {**params, 'evidence_scope': scope, 'analysis_contract': contract,
                                'execution_policy': {'forbidden_tools': intent['forbidden_tools'], 'offline': offline}}})

    identity = generic or function or homology
    structure_homology = homology and any(x in lower for x in ('foldseek', '结构同源', 'structure homolog'))
    verified_reference = bool(preflight.get('reference_binding', {}).get('verified'))
    theoretical = preflight.get('theoretical_model') if isinstance(preflight.get('theoretical_model'), dict) else {}
    template_evidence = theoretical_template_evidence(preflight)
    activity_identity_intake = (
        not verified_reference and not (template_evidence or {}).get('templates')
        and 'activity' in PropertyWorkflowRouter.route(question).get('optimization_targets', [])
    )
    identity = identity or activity_identity_intake
    if template_evidence is not None:
        if template_evidence['templates']:
            deferred.append(
                '结构文件自称理论/同源模型，模板 '
                + '、'.join(str(t.get('template_id')) for t in template_evidence['templates'] if isinstance(t, dict))
                + ' 只作为家族同源证据；坐标编号沿用模型文件作者编号，不视为模板或目标 UniProt 编号。'
            )
        else:
            deferred.append('结构文件自称理论/同源模型，但未解析到模板条目；身份证据只能依靠序列级检索。')
    if (pdb_id or uniprot_id) and not verified_reference:
        deferred.append('参考编号目前只是候选提示；尚未验证它与上传链的对应，不据此投影参考功能位点。')
    mode = 'annotation_only' if not offline and identity and pdb_id and verified_reference else 'input_only'
    if structure_homology and not offline and runtimes.get('foldseek'):
        mode = 'homology'
    elif structure_homology and not offline:
        deferred.append('Foldseek 检索后端未就绪，暂不执行结构同源检索；本地坐标解析仍可完成。')
    add('structure_search_foldseek',
        '核对上传结构的来源、分辨率、构建体、组分和坐标质量；'
        + {'input_only': '只解析输入，不执行同源检索。',
           'annotation_only': '查询该 PDB 条目的官方注释，不执行 Foldseek 搜索。',
           'homology': '按需求检索结构同源模板。'}[mode],
        {'pdb_object_name': object_name, **({'pdb_id': pdb_id} if pdb_id and verified_reference else {}), 'search_mode': mode,
         **({'database': 'pdb', 'max_results': 5} if mode == 'homology' else {})})
    logic.append(f'针对链 {", ".join(str(c["chain_id"]) for c in chains)} 开展{title}；以本文件实际链和坐标序列绑定后续计算。')
    components = [c for c in preflight.get('nonpolymer_components', []) if isinstance(c, dict)]
    component_ids = {str(c.get('component_id') or '').upper() for c in components}
    non_solvent = component_ids - SOLVENTS
    glycans = non_solvent & GLYCANS
    other_components = non_solvent - GLYCANS - IONS

    for chain in chains:
        chain_id, sequence = str(chain['chain_id']), str(chain['sequence'])
        base = {'pdb_object_name': object_name, 'chain_id': chain_id}
        seq = {'sequence': sequence, **base, 'sequence_provenance': 'pdb_coordinate_derived'}
        add('residue_mapping_sifts', f'链 {chain_id}：建立坐标序列与作者编号对应，避免把构建体编号直接当成 UniProt 编号。',
            {**base, 'input_sequence': sequence, 'sequence_provenance': 'pdb_coordinate_derived',
             **({'pdb_id': pdb_id} if pdb_id and verified_reference else {})})
        if generic or quality or stability or contacts:
            add('build_site_structure_function_features', f'链 {chain_id}：计算局部暴露度、主链几何和原始 B-factor 分布，定位需复核区域。', base)
        if generic or stability or properties:
            add('predict_properties', f'链 {chain_id}：由当前构建体序列计算分子量、pI 和组成基线；不据此预测 Tm。', seq)
        if stability or (generic and deep and (sequence.count('C') >= 2 or preflight.get('disulfide_count'))):
            if chain.get('ca_only'):
                deferred.append(f'链 {chain_id} 只有 CA 坐标，无法计算侧链盐桥或 SG 二硫键几何。')
            else:
                add('disulfide_saltbridge_scan', f'链 {chain_id}：核对二硫键与带电侧链几何网络，作为稳定性结构解释。', base)
        if identity:
            if uniprot_id and verified_reference and not offline:
                add('annotation_bundle', f'链 {chain_id}：核对显式 UniProt 参考的审校记录；投影前仍须验证序列映射。', {**seq, 'uniprot_id': uniprot_id})
            add('enzyme_identity_profile', f'链 {chain_id}：结合结构条目核验身份与已有功能证据；不以模体猜测替代审校位点。',
                {**seq, 'structure_id': pdb_id if verified_reference and pdb_id else 'uploaded_pdb_coordinate_model',
                 **({'uniprot_id': uniprot_id} if uniprot_id and verified_reference else {}),
                 **({'template_evidence': template_evidence} if template_evidence else {})})
        if (homology or activity_identity_intake or (generic and deep and not verified_reference)) and not offline:
            add('blast_search', f'链 {chain_id}：提交序列同源检索补齐家族背景；结果异步返回，不能当作本轮已完成证据。',
                {**seq, 'program': 'blastp', 'database': 'swissprot', 'max_results': 8 if deep else 5})
        if (contacts or (generic and deep)) and non_solvent:
            description = f'链 {chain_id}：检查组分 {", ".join(sorted(non_solvent))} 的坐标接触。'
            if glycans:
                description += '区分糖链/糖基化连接与普通接触，不把糖链邻域认作催化口袋。'
            else:
                description += '先核实组分角色，不把未知配体直接当作底物。'
            add('ligand_contact_analysis', description, base)
        if pocket:
            if runtimes.get('pocket'):
                add('pocket_residue_lookup', f'链 {chain_id}：使用可用的 P2Rank/fpocket 预测口袋，独立于糖链或添加剂邻域；结果仍需功能核验。', {**base, 'engine': 'auto'})
            else:
                deferred.append(f'链 {chain_id} 的 P2Rank/fpocket 后端未就绪，暂不执行口袋预测；不会用任意组分周边残基冒充口袋或通道。')
        elif (generic and deep) and other_components:
            deferred.append(f'链 {chain_id} 的非糖组分角色尚未确认；暂不把其邻域作为底物口袋，也不从残基簇推断通道。')
        if any(x in lower for x in ('esm-2', 'esm2')):
            if runtimes.get('esm2'):
                add('enzyme_function', f'链 {chain_id}：执行 ESM-2 特征与模体背景分析，预测不替代功能实验证据。', seq)
            else:
                deferred.append('ESM-2 运行依赖或本地权重未就绪，暂不执行模型推理，不输出模型已运行的声明。')

    if len(chains) > 1 and (interfaces or generic):
        add('structure_pocket_interface_analysis', '检查所选蛋白链之间的原子接触界面；不依赖配体存在，也不据此判定生理寡聚态。',
            {'pdb_object_name': object_name, 'chain_scope': result['chain_ids'], 'analysis_scope': 'interfaces'})
    elif interfaces:
        deferred.append('所选输入只有一条蛋白链，不执行链间界面计算；不能据此排除晶体对称相关的生物学组装。')
    if not non_solvent:
        deferred.append('结构中未解析到非水组分，不执行空的配体接触分析。')
    if not any(r['tool_name'] == 'blast_search' for r in rows):
        deferred.append('本轮未选择 BLAST：' + ('用户要求仅本地分析。' if offline else '当前问题无需额外的后台序列同源检索。'))
    if identity and not uniprot_id:
        deferred.append('未绑定已验证的 UniProt 参考，暂不调用只会返回通用启发式结果的 annotation_bundle；官方交叉引用需后续映射核验。')
    if not deep:
        logic.append('按当前分析深度控制计算范围；只有目标需要的后台检索才会进入计划。')
    logic.extend(row['description'] for row in rows[1:])
    return result
