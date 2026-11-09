"""Question-level coverage from scoped results, separate from tool completion."""
from __future__ import annotations

import math

from app.services.evidence_scope import payload_dict
from app.services.structure_intent import parse_structure_intent
from app.services.task_evidence import result_status

_QUESTIONS = {
    'quality': ('结构质量', {'structure_search_foldseek', 'build_site_structure_function_features'}, '本轮未执行 clashscore、Ramachandran/侧链 rotamer 离群统计；已计算主链角度不等于通过几何验证。完整质量判断仍需相应的结构验证记录。'),
    'stability': ('热稳定性', {'disulfide_saltbridge_scan', 'build_site_structure_function_features', 'predict_properties'}, '结构网络仅提供解释线索；Tm、半衰期及稳定性变化需要指定条件的实测对照。'),
    'function': ('催化与功能', {'enzyme_identity_profile', 'annotation_bundle', 'residue_mapping_sifts'}, '功能位点解释需核实参考身份、注释依据和逐残基映射。'),
    'homology': ('家族与同源证据', {'blast_search', 'structure_search_foldseek'}, '阴性检索不确认家族；命中需要核对覆盖、相似性和功能一致性。'),
    'contacts': ('配体与连接', {'ligand_contact_analysis'}, '声明连接与几何邻近分别列出；组分角色及结合效应需要独立依据。'),
    'interfaces': ('链间界面', {'structure_pocket_interface_analysis'}, '当前坐标中的接触不自动证明生理组装。'),
    'pocket': ('口袋与通道', {'pocket_residue_lookup'}, '口袋预测与通道分析分别核验，不以配体邻域替代。'),
    'properties': ('序列理化性质', {'predict_properties'}, '结果适用于本轮所选构建体的序列。'),
}


def _metric(value: object, *, fraction: bool = False) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    valid_range = 0 <= value <= 1 if fraction else value > 0
    if not valid_range:
        return None
    return value


def _structure_quality(structure: dict) -> tuple[str, str]:
    """Interpret source metadata without inventing validation scores or pass/fail."""
    facts = [f"已解析 {structure.get('total_residues', '?')} 个残基、{structure.get('total_atoms', '?')} 个原子"]
    method = str(structure.get('method') or '').upper()
    limits = []
    if any(token in method for token in ('THEORETICAL', 'PREDICT', 'HOMOLOGY MODEL')):
        facts.append('来源为预测/建模结构，实验分辨率和晶体 R-factor 不用于评价此模型')
        limits.append('本轮没有经来源核实的模型置信度/PAE 证据；原始 B-factor 不能自行当作置信度。')
    elif 'X-RAY' in method:
        resolution = _metric(structure.get('resolution'))
        r_factor = _metric(structure.get('r_factor'), fraction=True)
        if resolution is not None:
            facts.append(f'X射线分辨率={resolution:g} Å，数值越小表示可分辨的空间细节越细；不反映所有局部缺陷')
        else:
            limits.append('分辨率缺失或无效。')
        if r_factor is not None:
            facts.append(f'R-factor={r_factor:g}，描述模型与用于精修的衍射数据的拟合偏差；单独不能排除过拟合')
        else:
            limits.append('R-factor 缺失或无效。')
        r_free = _metric(structure.get('r_free'), fraction=True)
        if r_free is not None:
            facts.append(f'R-free={r_free:g}，对应未参与精修的检验集；需结合数据质量与局部密度拟合核验')
        else:
            limits.append('本轮输出未提供有效 R-free，无法核对独立检验集拟合及其与 R-factor 的差异。')
        limits.append('还需电子密度与逐残基密度拟合依据；不能只凭分辨率或 R-factor 给整体质量评级。')
    elif 'NMR' in method:
        facts.append('来源为 NMR 结构，晶体 R-factor 不适用于本次质量评价')
        limits.append('需核对实验约束违反、结构集合一致性；首模型计算不代表集合评价。')
    elif 'ELECTRON MICROSCOPY' in method or 'CRYO-EM' in method:
        facts.append('来源为电镜结构，晶体 R-factor 不适用于本次质量评价')
        limits.append('需核对重构图分辨率、局部分辨率、FSC 和模型与密度图的拟合。')
    else:
        facts.append('结构方法未提供或尚无匹配的质量解释规则')
        limits.append('先核实实验或建模来源，再选择对应质量指标；不能自行套用晶体阈值。')
    b_stats = structure.get('b_factor_stats')
    if isinstance(b_stats, dict):
        mean = b_stats.get('mean')
        if isinstance(mean, (int, float)) and not isinstance(mean, bool) and math.isfinite(mean):
            facts.append(f'原文件蛋白原子 B-factor 均值={mean:g}，不是独立的逐链统计；含义依赖结构来源与文件约定')
    return '；'.join(facts), ''.join(limits)


def question_answers(task: str, records: list[dict]) -> list[dict]:
    intent = parse_structure_intent(task)
    requested = intent['goals'] or ['quality', 'function', 'properties']
    if not intent['goals'] and intent['deep']:
        selected = {record.get('tool_name') for record in records}
        requested = list(dict.fromkeys(requested + [
            goal for goal, (_, providers, _) in _QUESTIONS.items() if selected & providers]))
    answers = []
    for goal in requested:
        title, providers, boundary = _QUESTIONS[goal]
        boundaries = [boundary]
        facts, evidence_ids, pending = [], [], False
        for i, record in enumerate(records, 1):
            tool = record.get('tool_name')
            if tool not in providers:
                continue
            payload = payload_dict(record.get('result'))
            quality = result_status(record.get('status', ''), payload)['result_status']
            pending |= quality == 'pending'
            if quality not in {'usable', 'partial', 'empty'}:
                continue
            fact = None
            if tool == 'structure_search_foldseek':
                structure = payload.get('query_structure') or {}
                if goal == 'quality' and structure:
                    fact, limitation = _structure_quality(structure)
                    boundaries.append(limitation)
                elif goal == 'homology' and payload.get('search_executed') is not False:
                    fact = f"结构检索返回 {payload.get('results_count', len(payload.get('results') or []))} 项结果"
            elif tool == 'disulfide_saltbridge_scan':
                fact = f"二硫键几何接触 {len(payload.get('disulfide_bonds') or [])} 对，盐桥几何接触 {len(payload.get('salt_bridges') or [])} 对"
            elif tool == 'ligand_contact_analysis':
                fact = f"配体实例 {len(payload.get('ligand_instances') or [])} 个，接触 {len(payload.get('contacts') or [])} 项，声明连接 {len(payload.get('declared_connections') or [])} 项"
            elif tool == 'structure_pocket_interface_analysis':
                fact = f"当前链范围返回 {len(payload.get('chain_interfaces') or [])} 个接触界面"
            elif tool == 'predict_properties':
                if goal == 'properties':
                    fact = f"序列长度 {payload.get('length', '?')} aa，pI {payload.get('isoelectric_point', '?')}，分子量 {payload.get('molecular_weight_kda', '?')} kDa"
                # Sequence baselines alone do not answer thermostability.
            elif tool == 'enzyme_identity_profile' and payload.get('identity_status') == 'identified':
                fact = '身份画像返回已识别状态；具体参考与编号依据见下文'
            elif tool == 'residue_mapping_sifts' and payload.get('found'):
                fact = f"建立 {payload.get('mapping_count', '?')} 项编号对应；来源 {payload.get('source', '未声明')}"
            elif tool == 'blast_search':
                fact = f"序列检索返回 {payload.get('results_count', len(payload.get('results') or []))} 项结果"
            elif tool == 'build_site_structure_function_features' and payload.get('features'):
                count = payload.get('feature_count', (payload.get('summary') or {}).get('feature_count'))
                if not isinstance(count, int) or isinstance(count, bool) or count < len(payload['features']):
                    count = len(payload['features'])
                fact = f"完成 {count} 个位点的结构特征计算"
                if goal == 'quality':
                    summary = payload.get('summary') or {}
                    ca_count = summary.get('ca_available_count')
                    if isinstance(ca_count, int) and not isinstance(ca_count, bool) and 0 <= ca_count <= count:
                        fact += f'，CA 可用={ca_count}'
                    boundaries.append('特征预览不代表全链逐位点核验；缺失残基、占有率和替代构象须结合原文件与完整结果逐项核对。')
            elif tool == 'pocket_residue_lookup' and payload.get('found'):
                fact = '已取得口袋方法输出，具体方法与残基见证据详情'
            if fact:
                facts.append(fact)
                evidence_ids.append(f'E{i}')
        answers.append({'goal': goal, 'question': title,
            'status': 'answered' if goal == 'properties' and facts else 'partly_answered' if facts else 'pending' if pending else 'unresolved',
            'answer': '；'.join(dict.fromkeys(facts)) or '本轮尚无可直接回答此问题的结果。',
            'evidence_ids': evidence_ids, 'boundary': ''.join(dict.fromkeys(boundaries))})
    return answers


def render_question_answers(task: str, records: list[dict]) -> str:
    labels = {'answered': '已回答', 'partly_answered': '部分回答', 'pending': '等待结果', 'unresolved': '尚未解决'}
    lines = ['## 按问题回答\n']
    for row in question_answers(task, records):
        refs = ', '.join(row['evidence_ids'])
        lines.extend([f"### {row['question']}：{labels[row['status']]}\n",
            row['answer'] + (f'（依据：{refs}）' if refs else '') + '\n', row['boundary'] + '\n'])
    return '\n'.join(lines) + '\n'
