"""Deterministic constraints and scopes shared by structure planning/execution.

These are execution guardrails, not a claim to understand arbitrary scientific
language. A model may add structured goals; it may never erase these exclusions.
"""
from __future__ import annotations

import re
from typing import Any

_BOUNDARY = re.compile(r'[，,；;。！？!\n]|但是|但|而且|而是|\bbut\b|\bhowever\b', re.I)
_NEGATIVE = re.compile(r'禁止|不要|不允许|不得|无需|暂不|不做|不设计|不分析|排除|忽略|(?<![分区识鉴差级告])别|do\s+not|don[\x27’]t|without|forbid|no\s+', re.I)
# "只保留 A 链" is an inclusion; only an explicit exclusion prefix makes the
# label out of scope.
_ONLY_KEEP = re.compile(r'只\s*保留|仅\s*保留|只\s*看|仅\s*看|只分析|仅分析', re.I)
_GOALS = {
    'quality': ('质控', '质量', '缺失', '坐标编号', 'quality', 'missing residues'),
    'stability': ('稳定性', '热稳定', '耐热', '二硫键', '盐桥', 'stability', 'thermostab', 'disulfide', 'salt bridge'),
    'homology': ('blast', '同源', '保守', '家族', 'homolog', 'conservation', 'family'),
    'pocket': ('口袋', '通道', 'pocket', 'fpocket', 'p2rank', 'tunnel'),
    'contacts': ('配体', '底物', '糖基化', '糖链', 'ligand', 'glycan', 'substrate'),
    'interfaces': ('界面', '复合物', '寡聚', 'interface', 'complex', 'oligomer'),
    'properties': ('理化', '序列性质', '溶解', '等电', '分子量', 'physicochem', 'solubility', 'sequence properties'),
    'function': ('功能', '催化', '活性', 'function', 'catalytic', 'activity', 'esm-2', 'esm2'),
}
_TOOLS = {
    'blast_search': ('blast', '序列检索', '序列搜索', '同源检索', '联网检索'),
    'sequence_search': ('sequence_search',),
    'structure_search_foldseek': ('foldseek',),
    'predict_properties': ('predict_properties',),
    'annotation_bundle': ('annotation_bundle',),
    'enzyme_identity_profile': ('enzyme_identity_profile',),
    'residue_mapping_sifts': ('residue_mapping_sifts', 'sifts'),
    'ligand_contact_analysis': ('ligand_contact_analysis',),
    'structure_pocket_interface_analysis': ('structure_pocket_interface_analysis',),
    'build_site_structure_function_features': ('build_site_structure_function_features',),
    'disulfide_saltbridge_scan': ('disulfide_saltbridge_scan',),
    'pocket_residue_lookup': ('pocket_residue_lookup', 'p2rank', 'fpocket'),
    'enzyme_function': ('enzyme_function', 'esm-2', 'esm2'),
}


# `\b` never fires between a CJK character and an ASCII letter, so CJK-adjacent
# chain labels need an explicit not-ASCII-alphanumeric lookbehind instead.
_CHAIN_LIST = r'[A-Za-z0-9_]+(?:\s*[/、,，和与&+]\s*[A-Za-z0-9_]+)*'
_CHAIN_PATTERNS = (
    re.compile(r'(?<![A-Za-z0-9_])chains?\s+(' + _CHAIN_LIST + r')', re.I),
    re.compile(r'链\s*(' + _CHAIN_LIST + r')'),
    re.compile(r'(?<![A-Za-z0-9_])(' + _CHAIN_LIST + r')\s*链'),
)
# Chain labels are often separated by list punctuation that also opens a new
# clause, so polarity is read from the text right before each label rather than
# from the whole comma-delimited clause.
_CHAIN_CLAUSE_BOUNDARY = re.compile(r'[；;。！？!\n]|但是|但|而且|而是|\bbut\b|\bhowever\b', re.I)
# A revision turn is sent as "<saved task>\n\n[用户修改策略要求]\n<edit>". The
# saved task's chains were already narrowed or widened by this edit, so chain
# scope must come from the edit alone; the full text would re-add the old chain.
_REVISION_SPLIT = re.compile(r'\[用户修改策略要求\]')


def _extract_chains(text: str) -> tuple[list[str], dict[str, int], dict[str, int]]:
    wanted: list[str] = []
    excluded: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    mentions: list[tuple[int, list[str]]] = []
    for pattern in _CHAIN_PATTERNS:
        for match in pattern.finditer(text):
            mentions.append((match.start(), re.split(r'\s*[/、,，和与&+]\s*', match[1])))
    for start, labels in sorted(mentions):
        prefix = text[max([0] + [m.end() for m in _CHAIN_CLAUSE_BOUNDARY.finditer(text, 0, start)]):start]
        # A negation in the previous comma clause ("不要 BLAST，检查 B 链") does
        # not describe this mention, so polarity reads only the nearest clause.
        prefix = re.split(r'[，,]', prefix)[-1]
        negative = bool(_NEGATIVE.search(_ONLY_KEEP.sub('', prefix)))
        for chain in labels:
            # Only single-character IDs are chain labels; longer runs are words.
            if len(chain) > 2:
                continue
            first_seen.setdefault(chain, start)
            if negative:
                excluded.setdefault(chain, start)
            elif chain not in wanted:
                wanted.append(chain)
    return wanted, excluded, first_seen


def parse_structure_intent(question: str) -> dict[str, Any]:
    # Uploaded JSON includes words such as alpha/engineered; it is input data,
    # never an instruction about pH, mutations, chain selection or tools.
    question = re.split(r'\[Attached files:', question, maxsplit=1, flags=re.I)[0]
    clauses = [c.strip() for c in _BOUNDARY.split(question) if c.strip()]
    positive = ' '.join(c for c in clauses if not _NEGATIVE.search(c)).lower()
    negative = ' '.join(c for c in clauses if _NEGATIVE.search(c)).lower()
    forbidden = {tool for tool, aliases in _TOOLS.items() if any(a in negative for a in (tool, *aliases))}
    # Explicit tool identifiers are constraints even if not in the friendly alias list.
    forbidden.update(re.findall(r'\b[a-z][a-z0-9]+_[a-z0-9_]+\b', negative))
    # sequence_search wraps the same NCBI BLAST client; excluding BLAST must
    # exclude it too, or the alias silently runs the forbidden search.
    if 'blast_search' in forbidden:
        forbidden.add('sequence_search')
    chain_text = _REVISION_SPLIT.split(question, maxsplit=1)[1] if _REVISION_SPLIT.search(question) else question
    wanted, excluded, first_seen = _extract_chains(chain_text)
    if not (wanted or excluded) and chain_text is not question:
        # An edit that says nothing about chains keeps the saved task's scope.
        wanted, excluded, first_seen = _extract_chains(question)
    # A chain mentioned twice ("只保留 A 链…不分析 A/C/D 链") is decided by its
    # first mention: the preserved chain wins, the never-analyzed ones drop out.
    requested_chains = [chain for chain in wanted if excluded.get(chain, float('inf')) > first_seen[chain]]
    return {
        'goals': [name for name, aliases in _GOALS.items() if any(a in positive for a in aliases)],
        'forbidden_tools': sorted(forbidden),
        'offline': bool(re.search(r'(?:禁止|不要|不得|不允许)联网|不联网|离线|仅本地|只在本地|no external|offline|local only|do not (?:access the internet|use (?:the )?network)', question, re.I)),
        'chain_ids': requested_chains,
        'positive_text': positive,
        'deep': bool(re.search(r'深度|深入|全面|deep|comprehensive', positive)),
    }


def execution_constraint_error(tool: str, params: dict, constraints: dict) -> str | None:
    policy = params.get('execution_policy') or {}
    forbidden = set(constraints.get('forbidden_tools') or []) | set(policy.get('forbidden_tools') or [])
    if tool in forbidden:
        return f'{tool} 已被用户排除，未执行。'
    if constraints.get('offline') or policy.get('offline'):
        local = {'predict_properties', 'residue_mapping_sifts', 'enzyme_identity_profile', 'enzyme_objective_module_plan',
                 'build_site_structure_function_features', 'disulfide_saltbridge_scan',
                 'ligand_contact_analysis', 'structure_pocket_interface_analysis', 'pocket_residue_lookup'}
        if tool == 'structure_search_foldseek' and params.get('search_mode') == 'input_only':
            return None
        if tool not in local:
            return f'仅本地分析限制下，未执行可能访问外部服务的 {tool}。'
    return None
