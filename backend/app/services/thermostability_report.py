"""Render the thermal workflow contract without upgrading hypotheses to evidence."""
from __future__ import annotations

import html
import json
from typing import Any

from app.services.task_evidence import parse_tool_payload

SCHEMA = 'thermostability_candidates_v1'


def thermal_evidence_summary(result: dict) -> dict:
    """Keep selected rows and score receipts intact; omit bulky duplicate output."""
    compact = {k: v for k, v in result.items() if k not in {'report_markdown', 'screened_candidates'}}
    compact['branches'] = {name: {k: v for k, v in branch.items()
                                 if k not in {'predictions', 'mutations', 'couplings', 'pdb_data', 'alignment', 'evidence'}}
                           for name, branch in (result.get('branches') or {}).items() if isinstance(branch, dict)}
    return compact


def _cell(value: Any, fallback: str = '未提供') -> str:
    if value is None or value == '' or value == []:
        return fallback
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return html.escape(str(value)).replace('|', '/').replace('\r', ' ').replace('\n', ' ')


def _items(value: Any) -> list:
    return value if isinstance(value, list) else []


def render_thermostability_report(result: dict) -> str:
    """Render schema v1 candidates, gaps, score provenance and WT handoff."""
    if not isinstance(result, dict) or result.get('schema_version') != SCHEMA:
        return ''
    if result.get('analysis_mode') == 'exploration':
        return _render_exploration(result)
    status = str(result.get('status') or 'unknown')
    allow_candidates = status in {'ready_for_review', 'partial'}
    candidates = [r for r in _items(result.get('candidates')) if isinstance(r, dict)] if allow_candidates else []
    summary = {
        'needs_input': '等待补充输入；尚未生成可复核候选。',
        'blocked': '流程已阻断；尚未形成可复核候选。',
        'no_candidates': '当前来源未产生通过保护条件的候选。',
        'ready_for_review': '已形成待人工复核的单点突变假设，尚未经实验验证。',
        'partial': '部分分支不可用；以下仅为保留证据支持的待复核假设。',
    }.get(status, '流程尚未形成可交付的候选结论。')
    lines = ['## 热稳定性候选流程', '',
             f'- schema：`{SCHEMA}`', f'- 流程状态：{_cell(status)}；{summary}',
             f'- sequence_sha256：`{_cell(result.get("sequence_sha256"))}`',
             f'- 编号体系：{_cell(result.get("coordinate_system"))}',
             '- 人工复核：必须完成；预测分数不能证明实测热稳定性提高或活性保持。']
    if result.get('scientific_boundary'):
        lines.append('- 科学边界：' + _cell(result['scientific_boundary']))
    if result.get('objective'):
        objective = result['objective']
        lines.extend(['', '### 用户提供的实验目标', ''])
        if objective.get('endpoint') == 'residual_activity':
            def number(key: str) -> str:
                value = objective.get(key)
                return f'{value:g}' if isinstance(value, (int, float)) and not isinstance(value, bool) else '待补充'
            comparison = '≥' if objective.get('target_comparator') == '>=' else ''
            lines.append(f"热处理：{number('temperature_c')}℃，{number('duration_min')} min；"
                         f"残余活性基线：{number('baseline_residual_activity_pct')}%；"
                         f"目标：{comparison}{number('target_residual_activity_pct')}%。")
        lines.append(_cell(objective))
    if result.get('foundation'):
        lines.extend(['', '### 身份与候选前置条件', '', _cell(result['foundation']),
                      '身份、保护位点和编号未确认时，不能放行突变候选。'])
    gaps = _items(result.get('required_inputs'))
    if gaps:
        lines.extend(['', '### 待补充输入（required_inputs）', '', *['- ' + _cell(item) for item in gaps]])
    blockers = _items(result.get('blockers'))
    issues = _items(result.get('source_issues'))
    if blockers or issues:
        lines.extend(['', '### 阻断与来源缺口', '', *['- ' + _cell(item) for item in blockers + issues]])
    branches = result.get('branches')
    lines.extend(['', '### 可选计算分支', '', '| 分支 | 状态 | 原因/限制 |', '|---|---|---|'])
    if isinstance(branches, dict) and branches:
        for name, branch in branches.items():
            branch = branch if isinstance(branch, dict) else {}
            reason = branch.get('blocked_reason') or branch.get('reason') or branch.get('limitations')
            lines.append(f'| {_cell(name)} | {_cell(branch.get("status"), "unknown")} | {_cell(reason, "—")} |')
    else:
        lines.append('| 未记录 | 未记录 | 不推断任何分支已经运行 |')
    lines.extend(['', '### 单点候选（待复核）', ''])
    if candidates:
        lines.extend(['| 突变 | 输入序列位置 | 全长位置 | 结构作者编号 | 来源 | 风险 | 缺失证据 |',
                      '|---|---|---|---|---|---|---|'])
        for row in candidates:
            position = row.get('structure_position')
            author = (f'{position.get("chain_id", "?")}:{position.get("residue_number", "?")}{position.get("insertion_code") or ""}'
                      if isinstance(position, dict) else None)
            lines.append('| ' + ' | '.join(_cell(v) for v in [row.get('mutation'), row.get('position'),
                row.get('full_length_position'), author, row.get('sources'), row.get('risks'), row.get('missing_evidence')]) + ' |')
        lines.extend(['', '### 独立评分（不得相加）', '',
                      '| 突变 | DDGun ΔΔG | DDGun 方法/单位/方向/版本 | ESM 偏好 | ESM 模型/方法/方向 | Pareto 层 |',
                      '|---|---|---|---|---|---|'])
        for row in candidates:
            scores = row.get('scores') if isinstance(row.get('scores'), dict) else {}
            ddg = scores.get('ddgun') if isinstance(scores.get('ddgun'), dict) else {}
            esm = scores.get('esm_preference') if isinstance(scores.get('esm_preference'), dict) else {}
            ddg_info = {k: ddg[k] for k in ['method', 'unit', 'direction', 'algorithm_commit', 'database_version'] if k in ddg}
            esm_info = {k: esm[k] for k in ['model', 'method', 'direction', 'meaning'] if k in esm}
            lines.append('| ' + ' | '.join(_cell(v, '未计算') for v in [row.get('mutation'),
                ddg.get('ddg', ddg.get('ddg_kcal_mol')), ddg_info or None, esm.get('score'),
                esm_info or None, row.get('pareto_layer')]) + ' |')
        lines.append('\nESM 表示进化偏好，不能当作热稳定性预测；Pareto 层不表示实验证实的成功概率。')
    else:
        lines.append('本轮没有可展示的候选；补齐输入或解除阻断后重新评估。')
    plan = result.get('experimental_plan')
    lines.extend(['', '### 实验验证与 WT 对照', ''])
    if isinstance(plan, dict) and allow_candidates:
        lines.extend([f'- 对照：{_cell(plan.get("controls"))}；突变体与 WT 使用相同底物、缓冲液、pH、温度及处理时间。',
                      f'- 首轮单点集合：{_cell(plan.get("single_mutants"))}',
                      f'- 重复设计：{_cell(plan.get("replicates"))}',
                      f'- 选择规则：{_cell(plan.get("selection_policy"))}',
                      f'- 成功判据：{_cell(plan.get("success_criterion"))}',
                      f'- 组合设计：{_cell(plan.get("combination_design"))}'])
    else:
        lines.append('- WT 对照与活性保持检测必须在补齐实验目标后预先确定；本轮尚未形成可执行的实验候选集合。')
    if result.get('ranking_boundary'):
        lines.append('- 排序边界：' + _cell(result['ranking_boundary']))
    rejected = [r for r in _items(result.get('rejected')) if isinstance(r, dict)]
    if rejected:
        lines.extend(['', '### 已排除条目', '', '| 条目 | 排除原因 |', '|---|---|'])
        lines.extend(f'| {_cell(row.get("mutation"))} | {_cell(row.get("reasons"))} |' for row in rejected)
    return '\n'.join(lines) + '\n'


def _render_exploration(result: dict) -> str:
    labels = {'endpoint': '热稳定性评价指标', 'temperature_c': '热处理温度（℃）',
              'duration_min': '热处理时间（分钟）', 'baseline_residual_activity_pct': '当前残余酶活（%）',
              'target_residual_activity_pct': '目标残余酶活（%）', 'min_activity_retention_pct': '未加热酶活保持比例（%）',
              'ph': '测定pH', 'ph_range': '测定pH范围', 'method': '酶活测定方法', 'substrate': '测定底物', 'buffer': '缓冲液', 'cofactors': '辅因子'}
    objective = result.get('objective') or {}
    lines = ['## 热稳定性探索分析', '', '已完成当前资料范围内的探索整理，可继续分析。实验条件为可选信息，未知时也可继续。']
    if any(key in objective for key in labels):
        lines.extend(['', '### 已记录的目标与条件', '', '| 项目 | 当前信息 |', '|---|---|'])
    endpoints = {'residual_activity': '热处理残余酶活', 'half_life': '热失活半衰期', 'tm': 'Tm'}
    for key, label in labels.items():
        if key not in objective:
            continue
        value = objective.get(key)
        if key == 'endpoint':
            value = endpoints.get(value, value)
        lines.append(f'| {label} | {_cell(value, "未知（按用户说明保留）")} |')
    foundation = result.get('foundation') or {}
    identity = {'identified': '已有身份依据', 'candidate': '目前为身份线索', 'unresolved': '正在调查，尚未确认'}
    lines.extend(['', '### 身份与结构进展', '',
                  '- 酶身份：' + identity.get(foundation.get('identity_status'), '尚未确认；继续调查'),
                  '- 保护位点不完整时保留功能风险，已知催化位点、金属配位及已有二硫键仍需避开。'])
    structure = result.get('structure') or {}
    references = result.get('identity_references') or []
    for ref in references:
        if isinstance(ref, dict):
            label = ref.get('uniprot_id') or ref.get('pdb_entity')
            name = ref.get('protein_name') or ref.get('name')
            verified = '输入序列已核对' if ref.get('input_sequence_verified') else '参考线索；不直接等同输入酶身份'
            lines.append(f'- 参考：{_cell(label)}，{_cell(name)}；{verified}。')
    if structure.get('status') == 'mapped':
        lines.append(f'- 已核对结构链 {_cell(structure.get("chain_id"))}，映射 {_cell(structure.get("mapped_positions"))} 个输入位置。')
    lines.extend(['', '### 当前可继续的改造方向', '', *['- ' + _cell(x) for x in result.get('analysis_directions', [])]])
    preliminary = result.get('preliminary_candidates') or []
    if preliminary:
        counts = result.get('candidate_counts') or {}
        lines.extend(['', '### 工具支持的初步候选（研究假设，未验证）', '',
                      f'本轮筛查 {_cell(counts.get("screened"), str(len(preliminary)))} 个替换，展示 {len(preliminary)} 个位点。'
                      f'请求数量缺口：{_cell(counts.get("shortfall"), "未记录")}。',
                      '突变代码采用输入序列从1起的编号；作者编号单独列出，不能互换。', '',
                      '| 输入编号突变 | PDB作者编号 | 实际结构证据 | DDGun ΔΔG (kcal/mol) | ESM偏好 | 待验证风险 |',
                      '|---|---|---|---|---|---|'])
        for row in preliminary:
            coordinate = row.get('structure_position') or {}
            author = f'{coordinate.get("chain_id", "?")}:{coordinate.get("residue_number", "?")}{coordinate.get("insertion_code") or ""}'
            sources = row.get('sources') or []
            features = next((s.get('features') for s in sources if s.get('features')), None)
            scores = row.get('scores') or {}
            ddg, esm = scores.get('ddgun') or {}, scores.get('esm_preference') or {}
            lines.append('| ' + ' | '.join(_cell(v, '未计算') for v in [row.get('mutation'), author, features,
                ddg.get('ddg'), esm.get('score'), row.get('risks')]) + ' |')
        lines.extend(['', '候选生成依据：埋藏疏水位点的保守侧链堆积探针；可及面积和接触数是坐标计算结果，替换方向仍是待检验假设。',
                      'DDGun正值表示预测展开稳定性增加，负值表示预测不利；ESM仅表示进化偏好。均不证明95℃残余酶活改善，侧链碰撞与功能影响仍需复核。'])
    else:
        lines.extend(['', '当前尚无证据支持具体替换；先按以上方向分析，不虚构突变位点或改善幅度。'])
    if result.get('rejected'):
        lines.extend(['', '已排除已知保护位点或与输入野生型不符的突变：' + '、'.join(_cell(x.get('mutation')) for x in result['rejected'])])
    lines.extend(['', '### 实际评分分支', '', '| 分支 | 状态 | 说明 |', '|---|---|---|'])
    for name, branch in (result.get('branches') or {}).items():
        lines.append(f'| {_cell(name)} | {_cell(branch.get("status"))} | '
                     f'{_cell(branch.get("blocked_reason") or branch.get("reason") or branch.get("scientific_boundary"), "见工具回执")} |')
    for name, branch in (result.get('branches') or {}).items():
        if branch.get('algorithm_commit'):
            lines.append(f'\n{name}：算法版本 `{_cell(branch["algorithm_commit"])}`；数据库 `{_cell(branch.get("database_version"))}`。\n')
    if result.get('prior_blast_tasks'):
        lines.append('\n沿用本任务已有BLAST回执，未重复提交：' + _cell(result['prior_blast_tasks']))
    lines.extend(['', '### 如何继续', '',
                  '可直接说“继续做结构层面的热稳定性分析，实验条件未知”，或分轮补充已知信息；系统保留已有条件。',
                  '建议先做WT对照与热处理梯度，再确定评价指标和目标。BLAST尚在等待时先使用已完成分析，结果回来后补充身份依据。',
                  '', '### 结论范围', '', _cell(result.get('scientific_boundary'))])
    return '\n'.join(lines) + '\n'


def render_thermostability_results(tool_results: list[dict]) -> str:
    """Render persisted tool payloads, including input-blocked workflow receipts."""
    blocks = []
    for record in tool_results:
        if not isinstance(record, dict) or (record.get('tool_name') or record.get('tool')) != 'thermostability_candidate_workflow':
            continue
        payload = parse_tool_payload(record.get('result'))
        if payload.get('schema_version') != SCHEMA:
            continue
        outer = str(record.get('status') or '')
        if outer in {'failed', 'timeout', 'submitted', 'pending', 'running', 'queued'}:
            payload = {**payload, 'status': outer, 'candidates': [], 'experimental_plan': {}}
        scope = {k: record[k] for k in ['input_id', 'pdb_object_name', 'chain_id'] if record.get(k) is not None}
        block = render_thermostability_report(payload)
        if scope:
            block = '输入范围：' + _cell(scope) + '\n\n' + block
        blocks.append(block)
    if blocks:
        for record in tool_results:
            if (record.get('tool_name') or record.get('tool')) != 'blast_search':
                continue
            payload = parse_tool_payload(record.get('result'))
            status = str(payload.get('status') or record.get('status') or 'unknown')
            task = payload.get('task_id')
            if status in {'submitted', 'pending', 'running', 'queued', 'waiting'}:
                blocks.append('同源身份证据仍在异步等待，尚不能作为已确认家族证据。任务：' + _cell(task))
            elif status in {'failed', 'degraded', 'timeout', 'canceled'}:
                blocks.append('同源检索当前未取得可用完成证据：' + _cell(status) + '；任务：' + _cell(task))
    return '\n'.join(blocks)
