"""Deterministic runtime gate for enzyme-property chat requests.

Unlike the legacy shadow router this module is consumed by the chat path.  It
is intentionally side-effect free so each decision can be regression-tested
and stored as part of a task trace later.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.property_workflow_governance import PropertyWorkflowRouter
from app.services.structure_intent import parse_structure_intent


from app.services.enzyme_task_context import (
    active_task_history, continuation_request, explicit_new_task,
    protein_reference, reanalyze_current, structure_objects, task_sequence, user_task_text,
)
_CONTINUATION = re.compile(r"^(?:继续(?:分析.*)?|再说|再说人话|这个什么意思|什么意思|展开|详细说说)[。！？!？\s]*$", re.I)
_TARGET_CHANGE = re.compile(r"(?:改成|改为|换成|目标改|改目标)", re.I)
_SEQUENCE = re.compile(r"(?<![A-Z])[ACDEFGHIKLMNPQRSTVWY]{20,}(?![A-Z])", re.I)
_ACCESSION = re.compile(r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z0-9]{3}[0-9])\b", re.I)
_PDB = re.compile(r"\b[0-9][A-Za-z0-9]{3}\b")
_ENZYME_CONCEPT = re.compile(r"酶|蛋白|活性|稳定性|耐热|pH|催化|比活力|特异性|表达|enzyme|protein", re.I)


def mutation_turn_kind(message: str) -> str | None:
    """Separate requests for new substitutions from discussion of existing ones."""
    text = re.split(r'\[Attached files:', str(message or ''), maxsplit=1, flags=re.I)[0]
    positive = parse_structure_intent(text)['positive_text']
    tool_backed_action = re.search(
        r'(?:对应|匹配|结合|根据|按照|按|使用|调用|用).{0,24}工具.{0,20}'
        r'(?:做一下|执行一下|实际执行|运行一下|重新计算|重新分析|跑一遍)',
        positive, re.I)
    tool_site_request = re.search(
        r'(?:调用|使用|用)工具.{0,16}(?:给我|输出|生成|计算).{0,24}(?:位点|突变|候选)',
        positive, re.I)
    if tool_backed_action or tool_site_request:
        return 'extension'
    site_execution = re.search(r'(?:调用工具|结合工具结果|直到|继续|必须|请|给我).*(?:输出|计算|生成).*(?:位点|突变)|'
                               r'(?:输出|计算|生成)\s*\d+\s*个?\s*(?:突变|位点)', text, re.I)
    if not site_execution and not re.search(r'突变|替换.*氨基酸|mutat|substitut|\b[ACDEFGHIKLMNPQRSTVWY]\d+[ACDEFGHIKLMNPQRSTVWY]\b', text, re.I):
        return None
    if re.search(r'(?:调用工具|结合工具结果|直到|继续|必须|请|给我).*(?:输出|计算|生成).*(?:位点|突变)|'
                 r'(?:输出|计算|生成)\s*\d+\s*个?\s*(?:突变|位点)', positive, re.I):
        return 'extension'
    # Explicit new work takes precedence over an explanation in another clause.
    if re.search(r'(?:新增|增加|补充|生成|计算|设计|筛选|预测|推荐|寻找)(?!的).*(?:突变|候选|替换)|'
                 r'(?:哪些|什么).*(?:位点|氨基酸).*(?:突变|替换)|'
                 r'(?:哪些|什么).*突变.*氨基酸|'
                 r'\b(?:generate|calculate|design|predict|add|recommend)\b.*\b(?:mutations?|substitutions?|candidates?)\b', positive, re.I):
        return 'extension'
    if re.search(r'解释|为什么|依据|风险|整理|复述|已有|上面|刚才|报告|explain|why|existing|summari', text, re.I):
        return 'review'
    return None


def _history_has_concrete_mutation_rows(history: list[dict[str, Any]] | None) -> bool:
    """Return true only when the assistant already showed concrete substitutions."""
    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") != "assistant":
            continue
        content = str(item.get("content") or "")
        if re.search(r"突变位点(?:主表|探索清单)|推荐突变|mutation candidates", content, re.I):
            if re.search(r"\b[ACDEFGHIKLMNPQRSTVWY][1-9]\d*[ACDEFGHIKLMNPQRSTVWY]\b", content):
                return True
        # Only the latest assistant answer can be the result being continued.
        return False
    return False


def conversation_review_text(message: str) -> str | None:
    """Identify questions about a reply/system behavior, including legacy UI wrappers.

    The latest edit text is the current speech act. The original task in an
    edit wrapper is background, not renewed execution authorization.
    """
    text = str(message or '').rsplit('[用户修改策略要求]', 1)[-1].strip()
    if '[用户修改策略要求]' in str(message or ''):
        # Older browsers appended the original file to every presumed edit.
        # It is not a newly supplied object in this legacy wrapper.
        text = re.split(r'\[Attached files:', text, maxsplit=1)[0].strip()
    text = re.sub(r'^修改分析策略\s*[:：]\s*', '', text)
    if not text or _SEQUENCE.search(text) or 'object_name:' in text or '[Attached files:' in text:
        return None
    if _TARGET_CHANGE.search(text) or re.search(r'新任务|换一个|另一个|重新(?:运行|计算|分析|做)|重跑', text):
        return None
    if re.search(r'(?:^|[，,；;\n])\s*(?:请|帮我|给我|现在|我要)?(?:分析|计算|运行|检索|扫描|设计|执行|预测)', text):
        return None
    if re.search(r'(?:^|[.,;?!\n])\s*(?:then\s+)?(?:please\s+)?(?:rerun|recompute|reanaly[sz]e|analy[sz]e|calculate|run|execute|predict|search)\b', text, re.I):
        return None
    reference = re.search(r'你|您|上面|刚才|之前|这份|这个|结论|报告|上下文|\b(?:your|you|previous|report)\b', text, re.I)
    question = re.search(
        r'对还是不对|对不对|是否(?:正确|有依据|可靠)|(?:分析|回答|结论|报告).{0,12}(?:对吗|正确|准确|靠谱)|'
        r'(?:可靠吗|可信吗|可信度|靠谱吗|准不准|准吗|够吗|全吗|完整吗)|'
        r'(?:分析|报告|结论|结果|策略|流程|工具).{0,16}(?:够|深入|深度|彻底|完整|最终|最).{0,12}(?:么|吗|呢|[？?]|$)'
        r'|(?:最终|最深度|最深|最深入|最彻底).{0,16}(?:么|吗|呢|[？?]|$)'
        r'|只会|只能|为什么|怎么回事|解释|上下文.{0,8}(?:不对|错误|有误)|'
        r'\b(?:correct|accurate|why|explain|only execute|only run)\b', text, re.I,
    )
    return text if reference and question else None


def _has_target(text: str) -> bool:
    if PropertyWorkflowRouter.route(text).get("primary_property") is not None:
        return True
    # Keep an explicit user objective even when assay values or restrictions
    # make the policy router return no canonical property label.
    return bool(re.search(
        r"热稳定|热耐受|耐热|稳定性|半衰期|熔解温度|\bTm\b|thermal stability|thermostab|"
        r"比活力|酶活|催化效率|\bkcat\b|specific activity|\bactivity\b|"
        r"底物特异性|特异性|\bspecificity\b|pH\s*(?:适应|耐受|稳定|范围)|"
        r"可溶性|表达量|solubility|expression",
        str(text or ""), re.I,
    ))


def _history_task_text(history: list[dict[str, Any]] | None) -> str:
    messages = [
        str(item.get("content") or "")
        for item in active_task_history(history)
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    # Scope the active goal to the current object. Re-uploading that same object
    # can retain context; a different object or explicit new task is a boundary.
    object_pattern = r'object_name:\s*([^,\s\]]+)'
    latest_object = next((match[1] for item in reversed(messages)
                          if (match := re.search(object_pattern, item))), None)
    boundary = 0
    for index, item in enumerate(messages):
        match = re.search(object_pattern, item)
        if explicit_new_task(item):
            boundary = index
        if match and latest_object and match[1] != latest_object:
            boundary = index + 1
    messages = messages[boundary:]
    # The latest explicit goal is the active task, not a later control utterance
    # such as “continue”. Preserve the source message verbatim (minus file
    # metadata) because its assay values and restrictions are part of the goal.
    for index in range(len(messages) - 1, -1, -1):
        if is_thermal_assay_update(messages[index], [{'role': 'user', 'content': t} for t in messages[:index]]):
            continue
        if _has_target(messages[index]) and not _CONTINUATION.match(messages[index].strip()):
            source = re.split(r'\[Attached files:', messages[index], maxsplit=1, flags=re.I)[0].strip()
            active = '\n'.join([source, *messages[index + 1:]])
            if latest_object:
                active += '\n[已上传结构]'
            # A goal edit retains its input and restrictions, not earlier goals.
            start = next((i for i in range(index, -1, -1) if _known_inputs(messages[i])), index)
            if not _known_inputs(active) and start < index:
                input_source = messages[start]
                inputs = [m.group(0) for pattern in (_SEQUENCE, _ACCESSION, _PDB)
                          for m in pattern.finditer(input_source)]
                if 'structure' in _known_inputs(input_source):
                    inputs.append('[已上传结构]')
                active += '\n' + ' '.join(inputs)
            for prior in messages[start:index]:
                restrictions = parse_structure_intent(prior)
                active += ''.join('\n不要 ' + tool for tool in restrictions['forbidden_tools'])
                if restrictions['offline']:
                    active += '\n仅本地分析'
            return active
    return "\n".join(messages[-1:])


def _known_inputs(text: str) -> list[str]:
    clean = user_task_text(text)
    known = []
    if task_sequence(text):
        known.append("sequence")
    reference = protein_reference(text)
    if reference.startswith("accession:"):
        known.append("accession")
    if reference.startswith("pdb:"):
        known.append("structure_reference")
    if structure_objects(text) or "上传" in clean or "[已上传结构]" in text or re.search(r"\.(?:pdb|cif|ent)\b", clean, re.I):
        known.append("structure")
    return known


def _latest_task_goal(history: list[dict[str, Any]] | None) -> tuple[dict[str, Any], str]:
    selected: dict[str, Any] = {}
    source = ''
    prior: list[str] = []
    for item in active_task_history(history):
        if item.get("role") != "user":
            continue
        text = str(item.get('content') or '')
        route = PropertyWorkflowRouter.route(user_task_text(text))
        if route.get('workflow_id') and not (selected.get('workflow_id') == 'WF-STABILITY'
                                             and _thermal_assay_answer(text, prior)):
            selected = route
            source = user_task_text(text)
        prior.append(user_task_text(text))
    return selected, source


def latest_task_route(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    return _latest_task_goal(history)[0]


def latest_task_goal_text(history: list[dict[str, Any]] | None) -> str:
    """Use the same goal source in the runtime contract and executable plan."""
    return _latest_task_goal(history)[1]


def is_thermal_assay_update(message: str, history: list[dict] | None) -> bool:
    """Recognize answers to optional condition prompts within the active task.

    An explicit computation/goal/input change continues through normal routing.
    Supplying data alone never authorizes a new computation.
    """
    if latest_task_route(history).get('workflow_id') != 'WF-STABILITY':
        return False
    prior = [user_task_text(str(row.get('content') or '')) for row in active_task_history(history)
             if row.get('role') == 'user']
    return _thermal_assay_answer(message, prior)


def _thermal_assay_answer(message: str, prior: list[str]) -> bool:
    from app.services.engineering_goal_semantics import merge_thermal_assay
    text = user_task_text(message)
    if (explicit_new_task(text) or task_sequence(message) or structure_objects(message)
            or protein_reference(text) or mutation_turn_kind(text) == 'extension'):
        return False
    if re.search(r'重新(?:分析|计算|运行|评估)|重跑|(?:继续|开始|执行|调用|帮我|请).{0,12}'
                 r'(?:分析|计算|运行|评估|工具)|(?:^|[，,；;。\n])\s*(?:分析|计算|运行|评估)'
                 r'|提高(?:表达|比活力|活性|可溶)|改变(?:底物|特异性)|改造目标|目标改为'
                 r'|(?:rerun|recompute|reanaly[sz]e|execute|run tools)\b'
                 r'|为什么|是否|怎么|解释|[？?]|吗', text, re.I):
        return False
    before = merge_thermal_assay(prior)
    # Parsing with the known endpoint allows terse but labelled percentages.
    endpoint = {'residual_activity': '剩余酶活', 'half_life': '半衰期', 'tm': 'Tm'}.get(before.get('endpoint'), '')
    values = merge_thermal_assay([endpoint, text])
    values.pop('endpoint', None)
    has_label = re.search(r'评价指标|测定指标|(?:实验)?条件.{0,10}(?:未知|不清楚|未测|不补充)', text)
    return bool(values or has_label)


def _contract(
    *,
    intent: str,
    session_id: str | int | None,
    route: dict[str, Any],
    intake_status: str,
    final_status: str,
    known_inputs: list[str],
    input_gaps: list[str],
    route_reason: str,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "session_id": str(session_id) if session_id is not None else None,
        "intake_status": intake_status,
        "workflow_id": route.get("workflow_id"),
        "route_reason": route_reason,
        "route_confidence": route.get("route_confidence", "high" if route.get("workflow_id") else "low"),
        "primary_property": route.get("primary_property"),
        "optimization_targets": route.get("optimization_targets", []),
        "preservation_constraints": route.get("preservation_constraints", []),
        "known_inputs": known_inputs,
        "input_gaps": input_gaps,
        "final_status": final_status,
        "trace": [],
        "fallback_trace": [],
    }


def _evaluate_enzyme_workflow_runtime(
    message: str,
    history: list[dict[str, Any]] | None = None,
    session_id: str | int | None = None,
) -> dict[str, Any]:
    """Classify a chat turn and return the enforceable P0 task contract."""
    text = user_task_text(message).strip()
    scoped = active_task_history(history)
    prior_texts = [str(item.get("content") or "") for item in scoped if item.get("role") == "user"]
    parsed = parse_structure_intent(text)
    route = PropertyWorkflowRouter.route(parsed["positive_text"] or text)
    current_inputs = _known_inputs(message)
    prior_route = latest_task_route(scoped)
    last_upload = max((i for i, t in enumerate(prior_texts) if structure_objects(t)), default=0)
    concrete_prior_texts = prior_texts[last_upload:]
    prior_sequence = next((task_sequence(t) for t in reversed(concrete_prior_texts) if task_sequence(t)), None)
    prior_reference = next((protein_reference(t) for t in reversed(concrete_prior_texts) if protein_reference(t)), "")
    sequence = task_sequence(message)
    reference = protein_reference(message)
    foreign_input = bool((sequence and prior_sequence and sequence != prior_sequence)
                         or (reference and prior_reference and reference != prior_reference))
    new_task = explicit_new_task(text) or foreign_input
    if new_task:
        scoped = []
        prior_texts = []
        prior_route = {}
    prior_inputs = [] if new_task else list(dict.fromkeys(k for t in concrete_prior_texts for k in _known_inputs(t)))
    known = current_inputs or prior_inputs
    is_followup = (continuation_request(text) or bool(parsed["forbidden_tools"] or parsed["offline"])) and not new_task
    # A named reference is a follow-up only if it matches the current object.
    concrete_update = bool(sequence or structure_objects(message) or (reference and reference != prior_reference))

    def result(intent, selected_route, inputs, reason, gaps=None):
        gaps = gaps or []
        return _contract(intent=intent, session_id=session_id, route=selected_route,
                         intake_status="WAITING_FOR_USER_INPUT" if gaps else "READY_FOR_ANALYSIS",
                         final_status="NEEDS_INPUT" if gaps else "READY", known_inputs=inputs,
                         input_gaps=gaps, route_reason=reason)

    # Preserve online review/extension handling inside the candidate's active
    # object boundary, so old uploads and goals cannot authorize new work.
    mutation_turn = mutation_turn_kind(text)
    if not new_task and mutation_turn == 'review':
        return _contract(intent="NON_EXECUTION", session_id=session_id, route={},
                         intake_status="NOT_APPLICABLE", final_status="READY",
                         known_inputs=[], input_gaps=[], route_reason="existing_candidate_review")
    if not new_task and mutation_turn == 'extension' and _history_has_concrete_mutation_rows(scoped):
        if re.search(r"列出|整理|汇总|展示|报告中增加|再给我看|list|summari[sz]e|show", text, re.I):
            return _contract(intent="NON_EXECUTION", session_id=session_id, route={},
                             intake_status="NOT_APPLICABLE", final_status="READY",
                             known_inputs=[], input_gaps=[], route_reason="existing_candidate_review")
    if mutation_turn == 'extension':
        selected_route = route if route.get('optimization_targets') else prior_route
        inputs = current_inputs if new_task else known
        gaps = [] if inputs else ['enzyme_sequence_or_structure_or_accession']
        if not selected_route.get('optimization_targets'):
            gaps.append('optimization_target')
        return result("NEW_TASK" if new_task or not scoped else "TASK_EXTENSION",
                      selected_route, inputs, "mutation_candidate_request", gaps)
    if not new_task and conversation_review_text(message):
        return _contract(intent="NON_EXECUTION", session_id=session_id, route={},
                         intake_status="NOT_APPLICABLE", final_status="READY",
                         known_inputs=[], input_gaps=[], route_reason="conversation_review")

    if not new_task and is_thermal_assay_update(message, scoped):
        return result('INPUT_UPDATE', prior_route, known, 'thermal_assay_update')

    if not new_task and _TARGET_CHANGE.search(text) and parsed['goals']:
        return result("TARGET_CHANGE", route, known, "explicit_target_change",
                      [] if known else ["enzyme_sequence_or_structure_or_accession"])

    if route.get("optimization_targets") and not route.get("workflow_id"):
        return result("NEW_TASK", route, current_inputs or prior_inputs, "primary_property_requires_selection",
                      ["primary_property"])

    if (is_followup and prior_route and not concrete_update
            and (not route.get("workflow_id") or route.get("workflow_id") == prior_route.get("workflow_id"))):
        contract = result("FOLLOW_UP", prior_route, known, "continuation_of_existing_task")
        if reanalyze_current(text):
            contract["requires_reanalysis"] = True
        return contract

    if not new_task and route.get("intent") == "NON_EXECUTION" and re.search(r"酶|蛋白|活性|稳定性|耐热|pH|催化|比活力|特异性|表达|enzyme|protein", text, re.I):
        return _contract(intent="NON_EXECUTION", session_id=session_id, route=route,
                         intake_status="NOT_APPLICABLE", final_status="READY",
                         known_inputs=current_inputs, input_gaps=[], route_reason="conceptual_question")

    if not new_task and prior_route:
        if route.get("workflow_id") and (re.search(r"改成|改为|换成|目标改|改目标", text)
                                          or route["workflow_id"] != prior_route["workflow_id"]):
            return result("TARGET_CHANGE", route, known, "explicit_target_change",
                          [] if known else ["enzyme_sequence_or_structure_or_accession"])
        if current_inputs:
            return result("INPUT_UPDATE", route if route.get("workflow_id") else prior_route,
                          current_inputs, "new_input_for_existing_task")
        if route.get("workflow_id") and known:
            return result("TARGET_CHANGE", route, known, "goal_for_current_object")

    if route.get("workflow_id"):
        inputs = current_inputs if new_task else known
        if inputs:
            return result("NEW_TASK", route, inputs, "explicit_property_goal")
        intake_route = {**route, "workflow_id": None, "route_confidence": "low"}
        return result("NEW_TASK", intake_route, [], "property_goal_requires_enzyme_identity",
                      ["enzyme_sequence_or_structure_or_accession"])

    # A concrete analysis/extraction request needs no engineering objective.
    # Preserve production's structure-only analysis and explicit no-tool path.
    if current_inputs and re.search(r"分析|抽取|提取|analy[sz]e|extract", text, re.I):
        return result("NEW_TASK", route, current_inputs, "concrete_input_analysis")

    if new_task or current_inputs or (is_followup and scoped):
        gaps = ["optimization_target"]
        inputs = current_inputs if new_task else known
        if not inputs:
            gaps.append("enzyme_sequence_or_structure_or_accession")
        return result("NEW_TASK", route, inputs, "task_requires_target_and_identity", gaps)

    return _contract(intent="NON_EXECUTION", session_id=session_id, route=route,
                     intake_status="NOT_APPLICABLE", final_status="READY",
                     known_inputs=current_inputs, input_gaps=[], route_reason="outside_enzyme_workflow_scope")


def evaluate_enzyme_workflow_runtime(
    message: str, history: list[dict[str, Any]] | None = None,
    session_id: str | int | None = None,
) -> dict[str, Any]:
    contract = _evaluate_enzyme_workflow_runtime(message, history, session_id)
    current = parse_structure_intent(message)
    inherited = parse_structure_intent(_history_task_text(history)) if contract['intent'] in {'FOLLOW_UP', 'INPUT_UPDATE', 'TARGET_CHANGE', 'TASK_EXTENSION'} else {}
    contract['forbidden_tools'] = sorted(set(current['forbidden_tools']) | set(inherited.get('forbidden_tools', [])))
    contract['offline'] = current['offline'] or inherited.get('offline', False)
    contract['chain_ids'] = current['chain_ids'] or inherited.get('chain_ids', [])
    contract['task_relation'] = (
        'ASSAY_UPDATE' if contract['route_reason'] == 'thermal_assay_update'
        else 'CONSTRAINT_UPDATE' if contract['intent'] == 'FOLLOW_UP' and (current['forbidden_tools'] or current['offline'])
        else contract['intent']
    )
    return contract
