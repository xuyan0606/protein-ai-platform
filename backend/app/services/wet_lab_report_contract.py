"""Structured wet-lab validation plan for scientific reports.

The contract deliberately describes planned measurements separately from
observed results.  Report producers can safely render this plan even when a
PDB-only analysis has no assay data.
"""

from __future__ import annotations

from typing import Any, Mapping


WET_LAB_SCHEMA_VERSION = "wet_lab_plan_v1"
PLANNED = "planned"
NOT_AVAILABLE = "not_available"


def _engineered_mutation_labels(structure_data: Mapping[str, Any] | None) -> list[str]:
    query = structure_data.get("query_structure", {}) if isinstance(structure_data, Mapping) else {}
    mutations = query.get("engineered_mutations") if isinstance(query, Mapping) else None
    labels: list[str] = []
    for item in mutations or []:
        if not isinstance(item, Mapping):
            continue
        chain = item.get("chain_id", "?")
        wild_type = item.get("reference_residue_aa") or item.get("pdb_residue_aa") or "?"
        position = item.get("reference_position") or item.get("pdb_residue_no") or "?"
        mutant = item.get("pdb_residue_aa") or "?"
        labels.append(f"{chain}:{wild_type}{position}{mutant}")
    return labels


def _substrate_scope(structure_data: Mapping[str, Any] | None) -> str:
    query = structure_data.get("query_structure", {}) if isinstance(structure_data, Mapping) else {}
    annotation = query.get("compound_annotation", {}) if isinstance(query, Mapping) else {}
    if not isinstance(annotation, Mapping):
        return "按已确认酶功能选择天然相关底物（身份未确认时先不指定底物）"
    identity = " ".join(str(annotation.get(key) or "") for key in ("molecule", "name", "description")).lower()
    if "mannanase" in identity or "甘露聚糖酶" in identity:
        return "天然相关 β-1,4-mannan 底物（先核对构建体酶身份）"
    return "按已确认酶功能选择天然相关底物（身份未确认时先不指定底物）"


def build_wet_lab_plan(
    *,
    structure_data: Mapping[str, Any] | None = None,
    user_mutations: list[str] | None = None,
) -> dict[str, Any]:
    """Build a conservative, machine-readable validation plan.

    No field in the returned plan represents an observed assay result.  This
    makes the plan suitable for PDB-only reports and prevents planned work
    from being promoted to experimental evidence by a renderer.
    """
    engineered = _engineered_mutation_labels(structure_data)
    substrate = _substrate_scope(structure_data)
    constructs = [
        {"id": "WT", "purpose": "天然/工程基线", "status": PLANNED,
         "required": ["表达量", "可溶比例", "SEC 单体比例", "活性", "Tm", "热失活半衰期"]},
        {"id": "PDB_CONSTRUCT", "purpose": "复现上传结构构建体", "status": PLANNED,
         "mutation_annotation": engineered or ["突变需核对"],
         "required": ["表达量", "可溶比例", "SEC 单体比例", "活性", "Tm", "热失活半衰期"]},
    ]
    if engineered:
        constructs.append({
            "id": "BACK_MUTATION_IF_NEEDED",
            "purpose": "必要时回补/逆突变，区分构建体效应",
            "status": PLANNED,
            "mutation_annotation": engineered,
            "required": ["与 WT 同批 QC", "天然相关底物动力学", "Tm", "热失活半衰期"],
        })
    if user_mutations:
        constructs.append({
            "id": "USER_SPECIFIED_MUTANTS",
            "purpose": "用户指定突变体的单点验证",
            "status": PLANNED,
            "mutation_annotation": [str(item) for item in user_mutations[:12]],
            "required": ["与 WT 同批 QC", "目标 assay", "稳定性复测"],
        })
    constructs.append({
        "id": "NEGATIVE_CONTROL",
        "purpose": "空载体/无酶背景控制",
        "status": PLANNED,
        "required": ["底物自发反应背景", "检测体系背景"],
    })

    return {
        "schema_version": WET_LAB_SCHEMA_VERSION,
        "status": PLANNED,
        "evidence_status": NOT_AVAILABLE,
        "observed_results_available": False,
        "constructs": constructs,
        "qc_assays": [
            {"name": name, "status": PLANNED}
            for name in ("表达量", "可溶比例", "SDS-PAGE", "SEC 单体比例", "LC-MS/intact mass", "降解/聚集")
        ],
        "functional_assays": [
            {"name": name, "status": PLANNED}
            for name in (substrate, "初始速率线性区间", "kcat", "Km", "kcat/Km", "pH-活性曲线", "温度-活性曲线")
        ],
        "assay_design": {
            "status": PLANNED,
            "replicates": "至少 3 次独立生物重复；技术重复与生物重复分别记录",
            "controls": ["同批 WT", "无酶/空载体", "底物空白"],
            "required_context": ["底物来源及聚合度", "pH", "温度", "反应时间", "酶浓度", "蛋白归一化"],
        },
        "stability_assays": [
            {"name": name, "status": PLANNED}
            for name in ("DSF/DSC Tm", "热处理后残余活性", "热失活半衰期", "储存稳定性", "聚集/浑浊度")
        ],
        "decision_gates": {
            "go": "单点相对 WT 在目标 assay 中重复改善，且表达、SEC 单体比例和基础活性未显著下降。",
            "watch": "只有计算/结构假设，或只改善单项性质；继续单点复核，不进入组合或放大验证。",
            "no_go": "编号冲突、命中保护位点、明显失活/聚集，或无法获得可溶蛋白。",
        },
        "boundary": "本计划是待执行的湿实验设计；当前没有直接湿实验数据，不能把 planned 写成已完成或已验证。",
    }


def render_wet_lab_plan_markdown(plan: Mapping[str, Any]) -> str:
    """Render the contract without implying observed results."""
    lines = [
        "## 湿实验验证计划",
        "",
        f"- **schema_version**：{plan.get('schema_version', WET_LAB_SCHEMA_VERSION)}",
        f"- **状态**：{plan.get('status', PLANNED)}；直接湿实验数据={plan.get('evidence_status', NOT_AVAILABLE)}；已完成结果={plan.get('observed_results_available', False)}。",
        f"- **边界**：{plan.get('boundary', '')}",
        "",
        "### 构建体矩阵",
        "",
        "| 构建体 | 目的 | 结构/突变注释 | 状态 |",
        "|---|---|---|---|",
    ]
    for item in plan.get("constructs", []):
        annotation = "; ".join(map(str, item.get("mutation_annotation", []))) or "—"
        lines.append(f"| {item.get('id', 'N/A')} | {item.get('purpose', 'N/A')} | {annotation} | {item.get('status', PLANNED)} |")
    lines.extend(["", "### QC、功能和稳定性读出", ""])
    for heading, key in (("表达/纯化 QC", "qc_assays"), ("功能 assay", "functional_assays"), ("稳定性 assay", "stability_assays")):
        lines.append(f"**{heading}**：" + "；".join(f"{item.get('name', 'N/A')} ({item.get('status', PLANNED)})" for item in plan.get(key, [])) + "。")
    assay_design = plan.get("assay_design", {})
    lines.append("**重复和对照**：" + str(assay_design.get("replicates", "待定义")) + "；" + "、".join(map(str, assay_design.get("controls", []))) + "。")
    gates = plan.get("decision_gates", {})
    lines.extend([
        "",
        "### Go / Watch / No-Go",
        "",
        f"- **Go**：{gates.get('go', '待定义')}",
        f"- **Watch**：{gates.get('watch', '待定义')}",
        f"- **No-Go**：{gates.get('no_go', '待定义')}",
        "",
    ])
    return "\n".join(lines)
