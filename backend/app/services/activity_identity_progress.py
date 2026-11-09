"""A pending identity search is progress, rather than a mutation-design report."""
from __future__ import annotations

import html

from app.services.evidence_scope import payload_dict


def render_activity_identity_progress(records: list[dict]) -> str | None:
    payloads = {str(r.get('tool_name')): payload_dict(r.get('result')) for r in records}
    structure = payloads.get('structure_search_foldseek', {}).get('query_structure') or {}
    if not isinstance(structure, dict) or structure.get('chain_count') != 1:
        return None
    method = str(structure.get('method') or '').upper()
    if not any(x in method for x in ('THEORETICAL', 'HOMOLOGY', 'SWISS-MODEL')):
        return None
    identity = payloads.get('enzyme_identity_profile', {})
    if identity.get('identity_status') == 'identified':
        return None
    blast_record = next((r for r in records if r.get('tool_name') == 'blast_search'), None)
    if not blast_record or blast_record.get('status') not in {'submitted', 'waiting', 'running'}:
        return None
    blast = payloads.get('blast_search', {})
    if str(blast.get('status') or '').lower() in {'completed', 'failed', 'blocked', 'degraded', 'canceled'}:
        return None
    if any(payloads.get(tool, {}).get(key) for tool in ('mutation_priority_score', 'mutation_scan')
           for key in ('tier_1_candidates', 'tier_2_candidates', 'experiment_design_table')):
        return None
    chains = structure.get('chains') or []
    chain = chains[0] if chains and isinstance(chains[0], dict) else {}
    length = chain.get('residue_count') or structure.get('total_residues')
    if not isinstance(length, int) or length <= 0:
        return None
    def text(value):
        return html.escape(str(value)).replace('`', '').replace('\n', ' ').replace('\r', ' ')
    lines = [
        '# 比活力改造：身份检索阶段进展\n',
        '**当前还不能判断哪些突变能提高比活力。** 结构已提供可用于同源检索的链序列；'
        '当前缺口是酶身份、催化位点和底物测定条件，不能用通用打分替代这些证据。\n',
        '## 已完成的工作\n',
        f'- 已解析链 {text(chain.get("chain_id") or "未知")}：{length} aa，'
        f'{text(structure.get("total_atoms") or "未统计")} 个原子。该输入为理论/同源模型。',
        '- 已有 PDB 坐标派生序列，不需要重复上传 FASTA 才能继续同源检索；'
        '独立测序 FASTA 可用于后续核验完整构建体。',
    ]
    mapping = payloads.get('residue_mapping_sifts', {})
    if mapping.get('source') == 'input_sequence_exact_coordinate_mapping':
        lines.append('- 已建立链内序列与 PDB 作者编号对应；这不等于已建立 UniProt 编号或催化位点映射。')
    features = payloads.get('build_site_structure_function_features', {})
    if features.get('status') == 'completed':
        lines.append('- 已完成坐标几何与暴露度等局部结构检查；未把这些数据换算为活性增益。')
    lines += ['\n## 序列级专业库检索（BLAST）\n',
              '- 已提交，尚未获得完成结果。当前报告不把 BLAST 结果写成已完成证据；'
              '等待或连接重试不是无同源命中，也不是用户缺少序列。']
    if blast.get('task_id'):
        lines.append(f'- 后台任务：`{text(blast["task_id"])}`。可在任务中心查看；不必重复提交同一搜索。')
    lines += [
        '- 检索完成后，应结合覆盖度、序列映射和审校功能注释生成更新分析；'
        '原报告保留，同源相似性本身不授权催化位点或突变结论。\n',
        '## 需要你补充的实验信息\n',
        '1. 底物名称、反应类型，以及底物浓度。',
        '2. 比活力测定的 pH、温度、时间和活力单位定义。',
        '3. WT 当前比活力（U/mg）、蛋白浓度/纯度、目标值；尚无基线时可明确说明。\n',
        '## 下一阶段交付\n',
        '确认身份和催化保护区后，再结合目标底物审查口袋入口、二壳层和保守性，'
        '形成带机制依据与风险的候选。当前不执行缺少底物依据的启发式 kcat 或无身份依据的位点扫描，'
        '也不声称已找到可提高比活力的突变。详细坐标结果仍保留在工具卡中。',
    ]
    return '\n'.join(lines)
