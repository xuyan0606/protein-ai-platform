"""Chain-scope parsing regressions reproduced against production on 2026-10-24."""
import pytest

from app.services.structure_intent import parse_structure_intent
from app.services.structure_strategy import select_structure_strategy

TOOLS = {
    'structure_search_foldseek', 'residue_mapping_sifts', 'predict_properties',
    'enzyme_identity_profile', 'blast_search', 'build_site_structure_function_features',
    'disulfide_saltbridge_scan', 'ligand_contact_analysis',
    'structure_pocket_interface_analysis', 'pocket_residue_lookup', 'annotation_bundle',
}


@pytest.mark.parametrize("message,expected", [
    ("分析A链和B链的热稳定性，仅本地分析，禁止联网", ["A", "B"]),
    ("分析热稳定性，只分析 B 链，不要 BLAST。", ["B"]),
    ("仅保留B链、不分析A/C/D链", ["B"]),
    ("只看B链，不要分析A、C、D链", ["B"]),
    ("请分析B链，不分析A链", ["B"]),
    ("分析A、B链", ["A", "B"]),
    ("保留chain B，不要chain A", ["B"]),
    ("分析A,C链的稳定性", ["A", "C"]),
    ("分析B链。", ["B"]),
    ("分析p53的热稳定性", []),
    ("分析A链和B链", ["A", "B"]),
])
def test_chain_scope_excludes_negated_chains(message, expected):
    assert parse_structure_intent(message)["chain_ids"] == expected


def test_chain_scope_keeps_shorter_chain_outside_separator_list():
    # 'A' must not be swallowed by the longer separator group A/C/D.
    assert parse_structure_intent("仅保留A链、不分析A/C/D链")["chain_ids"] == ["A"]


def test_strategy_keeps_only_preserved_chain_from_production_message():
    result = select_structure_strategy(
        "仅保留B链、不分析A/C/D链，分析热稳定性和界面",
        {'chains': [{'chain_id': c, 'sequence': 'ACDEFGHIKLMNPQRSTVWY'} for c in 'ABCD']},
        object_name='uploads/4ABCD.pdb', tools=TOOLS, runtimes={},
    )
    assert result['chain_ids'] == ['B']
    for step in result['steps']:
        assert step['params'].get('chain_scope') in (None, ['B'])


@pytest.mark.parametrize("message", [
    "仅本地分析，不要 BLAST",
    "不要 BLAST，仅保留 B 链",
    "禁止联网检索，但可本地分析",
])
def test_sequence_search_is_forbidden_when_blast_is_forbidden(message):
    forbidden = parse_structure_intent(message)["forbidden_tools"]
    assert "blast_search" in forbidden
    assert "sequence_search" in forbidden


def test_sequence_search_constraint_blocks_execution():
    from app.services.structure_intent import execution_constraint_error
    constraints = parse_structure_intent("禁止 BLAST，仅本地分析")
    error = execution_constraint_error("sequence_search", {}, constraints)
    assert error and "排除" in error


def test_live_revision_message_narrows_contract_to_chain_B():
    from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
    message = "修改策略：只分析 B 链，不要 BLAST，仍然分析热稳定性，不设计突变。"
    contract = evaluate_enzyme_workflow_runtime(message, [
        {'role': 'user', 'content': '分析 A 链和 B 链的热稳定性，仅本地分析，禁止联网。'},
    ])
    assert contract['chain_ids'] == ['B']
    assert 'sequence_search' in contract['forbidden_tools']


def test_negation_in_previous_comma_clause_does_not_exclude_chain():
    # Observed live on 2026-10-24: the "不要" belongs to BLAST, but reading
    # polarity from the whole clause dropped chain B and the plan fell back to
    # all four chains.
    intent = parse_structure_intent("不要 BLAST，仅本地分析，检查 B 链结构质量。")
    assert intent["chain_ids"] == ["B"]
    assert "blast_search" in intent["forbidden_tools"]
    assert "sequence_search" in intent["forbidden_tools"]


@pytest.mark.parametrize("edit,expected", [
    ("修改策略：只分析 B 链，不要 BLAST，仍然分析热稳定性，不设计突变。", ["B"]),
    ("改成只分析 A 链", ["A"]),
    ("只保留 B 链、不分析 A/C/D 链", ["B"]),
    ("仍然只看 B 链", ["B"]),
])
def test_server_composed_revision_reads_chains_from_edit_only(edit, expected):
    # app/api/chat.py prefixes the saved task to a revision; the saved chains
    # must not come back through the parser.
    composed = "分析 A 链和 B 链的热稳定性，仅本地分析，禁止联网。\n\n[用户修改策略要求]\n" + edit
    assert parse_structure_intent(composed)["chain_ids"] == expected


def test_server_composed_revision_keeps_full_text_tool_constraints():
    composed = (
        "分析 A 链和 B 链的热稳定性，仅本地分析，禁止联网。\n\n"
        "[用户修改策略要求]\n仍然分析热稳定性，不设计突变。"
    )
    intent = parse_structure_intent(composed)
    assert intent["chain_ids"] == ["A", "B"]
    assert intent["offline"] is True
    from app.services.structure_intent import execution_constraint_error
    assert execution_constraint_error("sequence_search", {}, intent)
