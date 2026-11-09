"""Explain saved thermal results without converting a plan into scientific evidence."""
from __future__ import annotations

import math
import re

from app.services.enzyme_task_context import active_task_history, user_task_text, requested_candidate_count
from app.services.enzyme_workflow_runtime import mutation_turn_kind
from app.services.thermostability_report import SCHEMA, _cell


def _number(value) -> str:
    return f'{value:g}' if type(value) in (int, float) and math.isfinite(value) else '未记录'


def thermal_assay_update_reply(message: str, history: list[dict]) -> str:
    """Acknowledge durable user data without reinterpreting an old tool result."""
    from app.services.engineering_goal_semantics import merge_thermal_assay
    scoped = active_task_history([*(history or []), {'role': 'user', 'content': message}])
    texts = [user_task_text(str(row.get('content') or '')) for row in scoped if row.get('role') == 'user']
    objective = merge_thermal_assay(texts)
    count = next((n for text in reversed(texts) if (n := requested_candidate_count(text)) is not None), None)
    lines = ['已将补充信息并入当前热稳定性项目，沿用原结构和改造目标'
             + (f'，候选数量仍为{count}个。' if count else '。'), '',
             '当前已记录的条件：', '', '| 项目 | 当前信息 |', '|---|---|']
    labels = {'endpoint': '评价指标', 'temperature_c': '热处理温度（℃）', 'duration_min': '热处理时间（分钟）',
              'baseline_residual_activity_pct': '当前残余酶活（%）', 'target_residual_activity_pct': '目标残余酶活（%）',
              'min_activity_retention_pct': '未加热酶活保持比例（%）', 'ph': '测定pH', 'ph_range': '测定pH范围',
              'method': '测定方法', 'substrate': '测定底物', 'buffer': '缓冲液', 'cofactors': '辅因子'}
    for key, label in labels.items():
        if key in objective:
            value = objective[key]
            if key == 'endpoint':
                value = {'residual_activity': '热处理残余酶活', 'half_life': '半衰期', 'tm': 'Tm'}.get(value, value)
            lines.append(f'| {label} | {_cell(value, "未知（按用户说明保留）")} |')
    if not objective:
        lines.append('| 实验条件 | 允许未知，继续沿用原任务 |')
    if objective.get('parsing_conflicts'):
        lines.append('\n同一条信息中存在多个不同数值，已保留冲突，未擅自选取：' + _cell(objective['parsing_conflicts']))
    lines.extend(['', '本轮仅更新条件，没有重新识别身份或启动工具。已有计算回执保持原样，不能当作已按新条件重算。'
                  '未提供的条件仍可留空；后续要求继续计算时，将使用上述最新条件。'])
    return '\n'.join(lines)


def thermal_evidence_reply(message: str, history: list[dict], *, fallback: bool = False) -> str | None:
    """Render provenance/logic questions from the latest result in the active task.

    Incomplete newer executions supersede older results. Unsupported model
    substitutions may use this same renderer, never an invented substitute list.
    """
    question = user_task_text(message).split('[对话解释约束]', 1)[0]
    if mutation_turn_kind(question) == 'extension':
        return None
    asks = bool(re.search(
        r'(?:位点|突变|候选).{0,35}(?:逻辑|依据|路线|工具|通识|LLM)|'
        r'(?:逻辑|依据|路线).{0,20}(?:位点|突变|候选)|'
        r'真正调用|实际调用|(?:哪些|什么)工具|工具.{0,16}(?:来源|做过|结果)|'
        r'解释.{0,16}(?:作者编号|[A-Z]\d+[A-Z])|'
        r'(?:为什么|为啥|怎么|为何).{0,16}(?:没|不|无).{0,12}(?:位点|候选|突变)|'
        r'(?:残基|位点|作者)?编号.{0,16}(?:对不上|不对|错误|不一致)', question, re.I))
    if not asks and not fallback:
        return None
    scoped = active_task_history([*(history or []), {'role': 'user', 'content': message}])[:-1]
    receipts = [e for row in scoped if row.get('role') == 'assistant'
                for e in row.get('tool_evidence') or [] if isinstance(e, dict)
                and e.get('tool_name') == 'thermostability_candidate_workflow']
    if not receipts:
        # Only intercept scientific receipt questions, never ordinary tool help.
        if asks and (re.search(r'位点|突变|候选|这些|这些结果', question) or fallback):
            return ('当前任务没有可核验的已执行热稳定性候选回执；不能把策略、历史助手建议或其他蛋白的结果当成这次的计算结果。'
                    '因此现在无法确认位点依据或工具评分，实验效果也未验证。')
        return None
    latest = receipts[-1]
    result = latest.get('result')
    if (latest.get('status') != 'completed' or not isinstance(result, dict)
            or result.get('schema_version') != SCHEMA
            or result.get('status') in {'blocked', 'needs_input', 'failed', 'pending', 'submitted', 'running'}):
        return ('当前任务最新的候选执行回执尚未提供可解释的已完成结果；不会用更早一轮候选替代本轮。'
                '目前不能确认具体替换及评分，实验效果也未验证。')
    digest = result.get('sequence_sha256')
    rows = [r for r in result.get('preliminary_candidates') or result.get('candidates') or []
            if isinstance(r, dict) and r.get('mutation') and not any(
                s.get('sequence_sha256') and digest and s['sequence_sha256'] != digest
                for s in r.get('sources') or [] if isinstance(s, dict))]
    branches = result.get('branches') or {}
    counts = result.get('candidate_counts') or {}
    features = result.get('structure_feature_receipt') or {}
    logic = bool(re.search(r'逻辑|路线|依据|为什么|为啥|编号', question))
    lines = [('按本任务保存的执行回执，候选的依据如下：' if logic else
              '按本任务保存的执行回执，确实完成的计算与未完成的部分如下：'), '']
    if re.search(r'编号.{0,16}(?:对不上|不对|错误|不一致)', question):
        lines.append('编号异议先核对已有结果：输入序列位置和PDB作者编号需要分别读取，不能用固定偏移替代序列比对。'
                     '下表仅解释原回执，不表示已与新的独立序列重新对齐。')
    if counts:
        lines.append(f'- 筛查 {_number(counts.get("screened"))} 个替换；请求 {_number(counts.get("requested_positions"))} 个位点，'
                     f'返回 {_number(counts.get("returned_positions"))} 个。'
                     f'数量缺口 {_number(counts.get("shortfall"))} 个，不能补造。')
        requested = next((n for item in reversed(scoped) if item.get('role') == 'user'
                          and (n := requested_candidate_count(item.get('content') or '')) is not None), None)
        if requested is not None and counts.get('requested_positions') != requested:
            lines.append(f'- 数量不一致：用户要求 {requested} 个，但这次工具回执请求的是 '
                         f'{_number(counts.get("requested_positions"))} 个，不能称为按用户数量完成。原回执保持原样；后续计算需按正确数量重新规划。')
    packing = any(s.get('kind') == 'coordinate_packing_probe' for r in rows
                  for s in r.get('sources') or [] if isinstance(s, dict))
    if packing:
        lines.append('- 候选生成走的是埋藏疏水位点的保守堆积探针路线：依据输入坐标计算的 SASA、接触数和野生型/作者编号映射提出研究假设。'
                     '这一步采用明确的启发式规则，不是直接从LLM通识给出名单，也不代表已经发现空腔或确定增稳。')
    elif rows:
        lines.append('- 候选来源按每行的来源记录解释；当前回执未记载结构堆积探针，不能假称使用过该路线。')
    if features.get('status') == 'completed':
        lines.append(f'- 结构特征回执覆盖 {_number(features.get("rows_evaluated"))} 个位置；未计算的局部几何、保守性或功能性质仍为未知。')
    for key, label in [('colabfold', 'ColabFold结构预测'), ('database', '数据库候选来源'), ('coevolution', '共进化')]:
        branch = branches.get(key) or {}
        if branch and branch.get('status') != 'not_requested':
            lines.append(f'- {label}：{_cell(branch.get("status"), "未记录")}；'
                         f'{_cell(branch.get("blocked_reason") or branch.get("reason"), "具体依据见保存回执")}。')
    for key, label in [('ddgun', 'DDGun'), ('esm', 'ESM')]:
        branch = branches.get(key) or {}
        status = branch.get('status') or '未记录'
        if status == 'completed':
            meaning = ('独立计算替换的预测展开稳定性 ΔΔG；正值表示预测展开稳定性增加，不能换算成Tm或残余酶活。'
                       if key == 'ddgun' else '完成进化偏好评分；不能作为实测热稳定性改善证据。')
            lines.append(f'- {label}：completed，{meaning}')
            version = branch.get('algorithm_commit') or branch.get('model')
            if version:
                lines.append(f'  版本/模型：{_cell(version)}；数据库：{_cell(branch.get("database_version"), "未记录")}。')
        else:
            reason = branch.get('blocked_reason') or branch.get('reason')
            lines.append(f'- {label}：{_cell(status)}，本回执不能支持已完成该评分的说法。'
                         + (f'原因：{_cell(reason)}。' if reason else ''))
    if rows:
        codes = set(re.findall(r'\b[A-Z][1-9]\d*[A-Z]\b', question))
        def aliases(row):
            position = row.get('structure_position') or {}
            author = f'{row.get("wild_type", "")}{position.get("residue_number", "")}{row.get("mutant", "")}'
            return {row['mutation'], author}
        selected = [r for r in rows if codes & aliases(r)] if codes else rows[:3]
        if selected:
            lines.extend(['', '| 输入序列突变 | PDB作者编号 | 坐标依据 | DDGun ΔΔG (kcal/mol) |', '|---|---|---|---|'])
            for row in selected:
                pos = row.get('structure_position') or {}
                author = f'{pos.get("chain_id", "?")}:{pos.get("residue_number", "?")}{pos.get("insertion_code") or ""}'
                local = next((s.get('features') for s in row.get('sources') or [] if isinstance(s, dict) and s.get('features')), {})
                ddgun = (row.get('scores') or {}).get('ddgun') or {}
                score = _number(ddgun.get('ddg')) if (branches.get('ddgun') or {}).get('status') == 'completed' else '未计算'
                lines.append('| ' + ' | '.join(_cell(v) for v in [row['mutation'], author,
                    f'SASA={_number(local.get("rel_sasa"))}；8Å接触数={_number(local.get("contact_count_ca_8a"))}', score]) + ' |')
            lines.append('输入序列编号和PDB作者编号分别列出；不能直接互换。以上只引用保存的候选。')
        elif codes:
            lines.append('所问替换未出现在当前回执中，不能为它编造位点依据或分数。')
    else:
        lines.append('- 当前回执没有具体候选行，不能据此补出突变名单。')
    blasts = [e for row in scoped for e in row.get('tool_evidence') or [] if isinstance(e, dict) and e.get('tool_name') == 'blast_search']
    if blasts:
        blast = blasts[-1]
        state = (blast.get('result') or {}).get('status') or blast.get('status') or 'unknown'
        if state != 'completed':
            lines.append(f'- BLAST：{_cell(state)}；保存回执中的等待/未完成状态不能作为已确认同源或家族证据，解释不会新建任务。')
        else:
            lines.append('- BLAST：保存回执为completed；具体命中仍需核对覆盖度、相似度及编号映射，不能自动转移功能位点。')
    lines.extend(['', '这些是未验证的研究假设。功能保护信息不完整时仍有活性风险；侧链碰撞、保守性、组合上位性及实验热稳定性/活性效果均需单独核实。'
                  '已完成的评分不代表达到目标热处理条件下的残余酶活要求。解释已有结果不启动新工具。'])
    return '\n'.join(lines)
