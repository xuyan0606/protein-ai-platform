"""Shared, conservative language handling for heat-challenge objectives.

Residual activity after heating is an endpoint, not a separate kinetics goal.
Only explicitly supplied assay values are retained; missing values stay absent.
"""
from __future__ import annotations

import re
import json

RESIDUAL = r'(?:剩余|残余)(?:酶活(?:性)?|活性)|(?:residual|remaining|retained)\s+(?:enzyme\s+)?activity|热处理后(?:的)?(?:酶活(?:性)?|活性)|activity\s+(?:remaining\s+)?after\s+(?:heating|heat treatment)'
THERMAL = r'耐热|热稳定|温度稳定|热处理|加热|thermostability|thermal stability|\bheat(?:ing| treatment)?\b|melting temperature|(?<![a-z])tm(?![a-z])|半衰期|half[- ]life'


def goal_text(text: str) -> str:
    text = re.split(r'(?:^|\n)\s*\[Attached files:', str(text or ''), maxsplit=1, flags=re.I)[0]
    text = re.sub(r'^\s*>[^\n]*', ' ', text, flags=re.M)
    # A protein sequence can contain HEAT, TM, KM, etc. It is never a goal.
    return re.sub(r'(?<![a-z])[ACDEFGHIKLMNPQRSTVWY]{20,}(?![a-z])', ' ', text, flags=re.I)


def activity_goal_text(text: str) -> str:
    text = goal_text(text)
    if re.search(THERMAL, text, re.I) or re.search(r'\d\s*(?:℃|°\s*c|度)', text, re.I):
        text = re.sub(RESIDUAL, '热处理指标', text, flags=re.I)
        # Assay descriptions and untreated-activity floors are thermal context,
        # rather than authorization to optimize a second property.
        text = re.sub(r'(?:酶活|活性)测定方法\s*[:：=]\s*[^，,;；。\n]+', '测定方法', text, flags=re.I)
        text = re.sub(r'(?:未加热|未处理|untreated)\s*(?:酶活(?:性)?|活性|activity)\s*'
                      r'(?:需要|要求|至少|不低于|保持|保留|比例|retain|retention|≥|>=|[:：=为]|\s)*\s*'
                      r'(?:\d+(?:\.\d+)?\s*%|未知|unknown)', '未处理保持要求', text, flags=re.I)
    return text


def property_goal_text(text: str) -> str:
    """Labelled assay values describe the experiment, not design objectives."""
    text = goal_text(text)
    # The durable assay receipt is data, including substrate names. Its JSON
    # values must not become new optimization objectives on a later turn.
    text = re.sub(r'\[Prior thermal assay: \{[^\n]*\}\]', ' ', text)
    return re.sub(r'(?:测定底物|底物|substrate|酶活测定方法|测定方法|method|缓冲液|buffer|辅因子|cofactors)'
                  r'\s*[:：=]\s*[^，,;；。\n]+', '测定信息', text, flags=re.I)


def is_heat_objective(text: str) -> bool:
    return bool(re.search(THERMAL, text, re.I) or (
        re.search(RESIDUAL, text, re.I) and re.search(r'\d\s*(?:℃|°\s*c|度)', text, re.I)))


def thermal_objective(text: str) -> dict:
    saved = re.findall(r'\[Prior thermal assay: (\{[^\n]*\})\]', str(text or ''))
    if saved:
        plain = re.sub(r'\[Prior thermal assay: \{[^\n]*\}\]', '', text)
        objective = thermal_objective(plain)
        for value in saved:
            try:
                data = json.loads(value)
            except ValueError:
                continue
            if isinstance(data, dict):
                objective.update(data)
                conflicts = objective.get('parsing_conflicts', {})
                for key in data:
                    if key != 'parsing_conflicts':
                        conflicts.pop(key, None)
                if not conflicts:
                    objective.pop('parsing_conflicts', None)
        return objective
    text = goal_text(text)
    if not is_heat_objective(text):
        return {}
    objective = {}
    if re.search(RESIDUAL, text, re.I):
        objective['endpoint'] = 'residual_activity'
    elif re.search(r'半衰期|half[- ]life', text, re.I):
        objective['endpoint'] = 'half_life'
    elif re.search(r'熔解温度|melting temperature|(?<![a-z])tm(?![a-z])', text, re.I):
        objective['endpoint'] = 'tm'

    def assign(key: str, values: list[float]) -> None:
        existing = objective.get('parsing_conflicts', {}).get(key, [])
        distinct = sorted(set(values + existing + ([objective[key]] if key in objective else [])))
        if len(distinct) == 1:
            objective[key] = distinct[0]
        elif distinct:
            objective.pop(key, None)
            objective.setdefault('parsing_conflicts', {})[key] = distinct

    # Associate heating temperature and duration, excluding a separately
    # labelled activity-assay temperature. Multiple challenge conditions ask
    # for clarification instead of silently taking the first number.
    challenge = re.sub(r'(?:活性测定温度|测活温度|assay temperature)\s*[:：=为]?\s*\d+(?:\.\d+)?\s*(?:℃|°\s*c|度)', '', text, flags=re.I)
    assign('temperature_c', [float(m[1]) for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:℃|°\s*c|度)', challenge, re.I)])
    durations = []
    for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(minutes?|mins?|分钟|小时|hours?|hrs?|秒|seconds?|secs?)(?![a-z])', challenge, re.I):
        value, unit = float(match[1]), match[2].lower()
        durations.append(value * (60 if unit.startswith(('h', '小')) else 1/60 if unit.startswith(('s', '秒')) else 1))
    assign('duration_min', durations)
    for key, pattern in (
        ('baseline_residual_activity_pct', r'(?:目前|当前|原来|基线|baseline|currently|current)[^，,;；。\n%]{0,24}?(\d+(?:\.\d+)?)\s*%'),
        ('target_residual_activity_pct', r'(?:希望|目标|至少|达到|提高到|提升到|target|at least)[^，,;；。\n%]{0,32}?(\d+(?:\.\d+)?)\s*%'),
    ):
        if objective.get('endpoint') == 'residual_activity':
            assign(key, [float(m[1]) for m in re.finditer(pattern, text, re.I)])
    transition = re.search(r'(?:从|from)\s*(\d+(?:\.\d+)?)\s*%\s*(?:提高|提升|增加|increase)?\s*'
                           r'(?:到|至|to)\s*(?:至少|不低于|≥|>=|at least)?\s*(\d+(?:\.\d+)?)\s*%', text, re.I)
    if transition and objective.get('endpoint') == 'residual_activity':
        assign('baseline_residual_activity_pct', [float(transition[1])])
        assign('target_residual_activity_pct', [float(transition[2])])
    if 'target_residual_activity_pct' in objective:
        objective['target_comparator'] = '>=' if re.search(r'以上|至少|不低于|≥|>=|at least', text, re.I) else 'target'
    ph_values = list(re.finditer(r'(?<![a-z])pH\s*(?:改为|改成|调整为|[:：=为])?\s*(\d+(?:\.\d+)?)'
                                r'(?:\s*[-–—~～至到]\s*(\d+(?:\.\d+)?))?', text, re.I))
    ranges = [list(map(float, m.groups())) for m in ph_values if m[2] is not None]
    singles = [float(m[1]) for m in ph_values if m[2] is None]
    if ranges:
        if all(v == ranges[0] for v in ranges) and not singles:
            objective['ph_range'] = ranges[0]
        else:
            objective.setdefault('parsing_conflicts', {})['ph'] = [*singles, *ranges]
    else:
        assign('ph', singles)
    for key, pattern in (
        ('min_activity_retention_pct', r'(?:未加热|未处理|untreated)[^，,;；。\n]{0,24}?(\d+(?:\.\d+)?)\s*%'),
    ):
        assign(key, [float(m[1]) for m in re.finditer(pattern, text, re.I)])
    for key, label in (('substrate', '底物|substrate'), ('method', '酶活测定方法|测定方法|method'), ('buffer', '缓冲液|buffer'), ('cofactors', '辅因子|cofactors')):
        match = re.search(r'(?:' + label + r')\s*[:：=]\s*([^，,;；。\n]+)', text, re.I)
        if match:
            objective[key] = match[1].strip()
    if re.search(r'(?:无需|不需要|无)\s*辅因子|辅因子\s*(?:不需要|无需|为无)', text):
        objective['cofactors'] = '无'
    if re.search(r'pH\s*[:：=为]?\s*(?:未知|不清楚|未测|unknown)', text, re.I):
        objective['ph'] = None
    return objective


def merge_thermal_assay(texts: list[str]) -> dict:
    """Merge only explicit user values, one turn at a time; later edits win."""
    merged: dict = {}
    for text in texts:
        # Short replies such as “当前40%，希望85%” describe the endpoint the
        # user already selected. Never infer that endpoint from percentages.
        endpoint_hint = {'residual_activity': '剩余酶活', 'half_life': '半衰期', 'tm': 'Tm'}.get(merged.get('endpoint'), '')
        explicit = thermal_objective('提高热稳定性\n' + text)
        values = explicit if explicit.get('endpoint') else thermal_objective('提高热稳定性\n' + endpoint_hint + '\n' + text)
        for key, value in values.items():
            if key != 'parsing_conflicts':
                if key in {'ph', 'ph_range'}:
                    merged.pop('ph_range' if key == 'ph' else 'ph', None)
                merged[key] = value
                merged.get('parsing_conflicts', {}).pop(key, None)
        for key, choices in values.get('parsing_conflicts', {}).items():
            merged.pop(key, None)
            merged.setdefault('parsing_conflicts', {})[key] = choices
    if not merged.get('parsing_conflicts'):
        merged.pop('parsing_conflicts', None)
    return merged
