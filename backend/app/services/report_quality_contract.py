"""Report quality contract for enzyme engineering outputs.

The contract is intentionally small and deterministic.  It captures the user
visible rules that must survive refactors: Chinese-first structure, evidence
boundaries, candidate gating, and stable section order.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.services.report_evidence_contract import (
    EVIDENCE_TYPES,
    make_evidence_record,
)


REPORT_SCHEMA_VERSION = "1.1"


CORE_SECTION_ORDER: tuple[str, ...] = (
    "## 任务理解",
    "## 输入与结构证据",
    "## 结构同源与编号映射",
    "## 改造策略及说明",
    "## Physicochemical Properties",
    "## Enzyme Foundation Profile",
    "## 保护位点",
    "## Objective Module Gate",
    "## 突变位点探索清单",
    "## 位点突变逻辑 / 风险 / 实验动作",
    "## 探索性验证建议",
)

DEFAULT_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "## 结论卡片 / 状态摘要",
    "## Go / Watch / No-Go",
    "This fallback report is generated",
    "## Protein Design Results",
    "中高催化效率",
    "典型工业酶",
)

IDENTITY_BLOCKED_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "## 突变位点主表（实验排单）",
    "K288E",
    "E275Q",
)


@dataclass(frozen=True)
class ReportQualityViolation:
    """Single contract violation with a stable machine-readable code."""

    code: str
    message: str


def validate_evidence_records(records: Iterable[dict] | None) -> list[ReportQualityViolation]:
    """Validate structured evidence before it is rendered or published.

    This is intentionally separate from the legacy Markdown quality gate so
    historical reports remain readable while new producers can fail closed.
    """
    violations: list[ReportQualityViolation] = []
    for index, record in enumerate(records or ()):
        if not isinstance(record, dict):
            violations.append(ReportQualityViolation("invalid_evidence_record", f"evidence[{index}] must be an object"))
            continue
        evidence_type = record.get("evidence_type")
        status = record.get("status")
        if evidence_type not in EVIDENCE_TYPES:
            violations.append(ReportQualityViolation("invalid_evidence_type", f"evidence[{index}] has unsupported type"))
            continue
        try:
            make_evidence_record(
                evidence_type=evidence_type,
                status=str(status or ""),
                source=record.get("source"),
                derived_from=record.get("derived_from"),
                value=record.get("value"),
            )
        except ValueError as exc:
            violations.append(ReportQualityViolation("invalid_evidence_record", f"evidence[{index}]: {exc}"))
    return violations


def is_structured_enzyme_report(report: str) -> bool:
    """Return True for platform-rendered enzyme engineering reports."""
    text = str(report or "")
    if "# 酶蛋白工程分析报告" in text:
        return True
    return "## 任务理解" in text and "## Objective Module Gate" in text


def _iter_text(items: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(item) for item in (items or ()) if str(item))


def validate_report_quality_contract(
    report: str,
    *,
    required: Iterable[str] | None = None,
    forbidden: Iterable[str] | None = None,
    ordered_headings: Iterable[str] | None = None,
    include_default_forbidden: bool = True,
) -> list[ReportQualityViolation]:
    """Validate a rendered report against explicit and default quality rules."""
    text = str(report or "")
    violations: list[ReportQualityViolation] = []

    for item in _iter_text(required):
        if item not in text:
            violations.append(
                ReportQualityViolation(
                    code="missing_required_text",
                    message=f"missing required text: {item}",
                )
            )

    forbidden_items = list(_iter_text(forbidden))
    if include_default_forbidden:
        forbidden_items.extend(DEFAULT_FORBIDDEN_PHRASES)
    for item in forbidden_items:
        if item in text:
            violations.append(
                ReportQualityViolation(
                    code="forbidden_text_present",
                    message=f"forbidden text present: {item}",
                )
            )

    cursor = -1
    for heading in _iter_text(ordered_headings):
        index = text.find(heading)
        if index < 0:
            violations.append(
                ReportQualityViolation(
                    code="missing_ordered_heading",
                    message=f"missing ordered heading: {heading}",
                )
            )
            continue
        if index <= cursor:
            violations.append(
                ReportQualityViolation(
                    code="heading_order_broken",
                    message=f"heading appears out of order: {heading}",
                )
            )
        cursor = index

    return violations


def validate_publishable_enzyme_report(report: str) -> list[ReportQualityViolation]:
    """Validate a structured enzyme report before Wiki/project publication.

    Non-enzyme Markdown is intentionally out of scope.  The publish gate should
    not block literature notes, generic chat exports, or batch summaries.
    """
    if not is_structured_enzyme_report(report):
        return []
    return validate_report_quality_contract(
        report,
        ordered_headings=CORE_SECTION_ORDER,
    )


def assess_enzyme_report_completion(report: str) -> dict[str, object]:
    """Return a conservative delivery status for a rendered enzyme report.

    A report is not marked READY merely because Markdown was produced.  The
    minimum business deliverable must expose evidence, candidate sites,
    priority, risk, and an experimental next action.  Non-enzyme reports stay
    outside this gate.
    """
    if re.search(r"^# 比活力改造：身份检索阶段进展\s*$", str(report or ""), re.MULTILINE):
        return {
            "final_status": "NEEDS_REVIEW",
            "violations": [ReportQualityViolation(
                code="pending_identity_search",
                message="identity search and assay evidence are incomplete; this is an interim progress report",
            )],
        }
    if not is_structured_enzyme_report(report):
        return {"final_status": "READY", "violations": []}

    text = str(report or "")
    # A rendered report can be structurally complete while its scientific
    # workflow is still blocked.  Do not let the presence of words such as
    # "证据" and "实验" promote a No-Go report to READY.  These checks are
    # intentionally anchored to the report's decision fields so a general
    # explanation of gating rules does not trip the terminal status.
    blocked_scientific_gate = False
    objective_gate = re.search(
        r"^##\s+Objective Module Gate\s*(.*?)(?=^##\s+|\Z)",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if objective_gate:
        gate_text = objective_gate.group(1)
        gate_status = re.search(
            r"(?:\*\*)?状态(?:\*\*)?\s*[:：]\s*(blocked|failed)",
            gate_text,
            flags=re.IGNORECASE,
        )
        candidate_disallowed = re.search(
            r"(?:\*\*)?是否允许输出候选表(?:\*\*)?\s*[:：]\s*(?:false|否|no)",
            gate_text,
            flags=re.IGNORECASE,
        )
        blocked_scientific_gate = bool(gate_status or candidate_disallowed)

    # Fallback reports may omit the gate section when the workflow is stopped
    # before objective planning.  Their explicit orderability decision still
    # carries the same meaning and must remain reviewable.
    explicit_blocked_decision = re.search(
        r"(?:能否下单|当前决策|主表状态|候选计数)[^\n]*(?:不能直接下单|无法生成候选表|No[- ]Go|正式候选\s*=\s*0|blocked)",
        text,
        flags=re.IGNORECASE,
    )
    execution_gate_notice = re.search(
        r"(?:按门控阻止执行|候选生成未执行并保持阻止)",
        text,
        flags=re.IGNORECASE,
    )
    blocked_scientific_gate = blocked_scientific_gate or bool(explicit_blocked_decision or execution_gate_notice)

    requirements = {
        "evidence": ("证据", "依据", "## 输入与结构证据"),
        "candidate_sites": ("候选", "位点", "突变位点"),
        "priority": ("优先级", "Tier 1", "Tier 2"),
        "risk": ("风险", "No-Go", "不确定性"),
        "experimental_action": ("实验", "验证建议", "实验动作"),
    }
    violations: list[ReportQualityViolation] = []
    empty_markers = r"(?:无|未提供|未知|待补|未评估|未确定|不可用)"
    for key, markers in requirements.items():
        if not any(marker.lower() in text.lower() for marker in markers):
            violations.append(
                ReportQualityViolation(
                    code=f"missing_completion_{key}",
                    message=f"missing completion requirement: {key}",
                )
            )
            continue
        label_patterns = {
            "evidence": r"(?:证据|依据)\s*[:：]\s*" + empty_markers,
            "candidate_sites": r"候选(?:位点|突变)?\s*[:：]\s*" + empty_markers,
            "priority": r"优先级\s*[:：]\s*" + empty_markers,
            "experimental_action": r"实验(?:动作|建议)?\s*[:：]\s*" + empty_markers,
        }
        pattern = label_patterns.get(key)
        if pattern and re.search(pattern, text, re.I):
            violations.append(
                ReportQualityViolation(
                    code=f"empty_completion_{key}",
                    message=f"empty completion requirement: {key}",
                )
            )

    if blocked_scientific_gate:
        violations.append(
            ReportQualityViolation(
                code="blocked_scientific_gate",
                message="scientific objective gate is blocked or candidate output is disallowed",
            )
        )
    return {
        "final_status": "READY" if not violations else "NEEDS_REVIEW",
        "violations": violations,
    }


def merge_workflow_and_report_status(
    report_status: str,
    workflow_status: str | None,
) -> str:
    """Keep upstream task gates from being erased by a complete Markdown body."""
    workflow = str(workflow_status or "").strip().upper()
    if workflow and workflow not in {"READY", "COMPLETED"}:
        return workflow
    report = str(report_status or "NEEDS_REVIEW").strip().upper()
    return report if report in {"READY", "NEEDS_REVIEW"} else "NEEDS_REVIEW"


def validate_multi_pdb_report(
    report: str,
    pdb_ids: Iterable[str],
) -> list[ReportQualityViolation]:
    """Check the minimum audit boundary for a report covering multiple PDBs.

    This is deliberately a presentation gate, not a scientific validity claim:
    it verifies that every requested input is visible and that missing assay
    data is stated explicitly. Tool completion alone cannot satisfy this gate.
    """
    text = str(report or "")
    normalized_ids = []
    for value in pdb_ids:
        normalized = str(value or "").strip().upper()
        if normalized:
            normalized_ids.append(normalized)

    violations: list[ReportQualityViolation] = []
    for pdb_id in dict.fromkeys(normalized_ids):
        if not re.search(rf"(?<![A-Z0-9]){re.escape(pdb_id)}(?![A-Z0-9])", text, re.I):
            violations.append(
                ReportQualityViolation(
                    code="missing_pdb_input",
                    message=f"missing PDB input in report: {pdb_id}",
                )
            )

    # Mentioning an input in prose is not evidence that it was audited. Require
    # a dedicated row in the per-input table and validate both tool-state cells.
    audit_rows: list[list[str]] = []
    in_audit_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("|") or not stripped.endswith("|"):
            in_audit_table = False
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if (
            len(cells) >= 5
            and cells[0].casefold() == "pdb"
            and "输入键" in cells[1]
            and "结构调用/结果" in cells[2]
            and "编号映射调用/结果" in cells[3]
        ):
            in_audit_table = True
            continue
        if in_audit_table and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if in_audit_table and len(cells) >= 5:
            audit_rows.append(cells)

    status_cell = re.compile(
        r"^(?:unknown|completed|failed|blocked|submitted|pending|running|not_submitted|timeout)"
        r"(?:/(?:unknown|completed|failed|blocked|submitted|pending|running|not_submitted|timeout))*$",
        re.I,
    )
    unused_rows = set(range(len(audit_rows)))
    for pdb_id in normalized_ids:
        matching_index = next(
            (
                index
                for index in sorted(unused_rows)
                if audit_rows[index][0].strip().upper() == pdb_id
            ),
            None,
        )
        if matching_index is None:
            violations.append(
                ReportQualityViolation(
                    code="missing_pdb_audit_row",
                    message=f"missing per-input structure/mapping audit row: {pdb_id}",
                )
            )
            continue
        unused_rows.remove(matching_index)
        cells = audit_rows[matching_index]
        if len(cells) < 5 or not cells[1]:
            violations.append(
                ReportQualityViolation(
                    code="invalid_pdb_audit_row",
                    message=f"per-input audit row lacks an input key or status columns: {pdb_id}",
                )
            )
            continue
        for column, label in ((2, "structure"), (3, "mapping")):
            value = cells[column].strip()
            if not value or value in {"—", "-", "NA", "N/A"}:
                violations.append(
                    ReportQualityViolation(
                        code=f"missing_{label}_status",
                        message=f"missing {label} tool status in per-input audit row: {pdb_id}",
                    )
                )
            elif not status_cell.fullmatch(value):
                violations.append(
                    ReportQualityViolation(
                        code=f"invalid_{label}_status",
                        message=f"invalid {label} tool status in per-input audit row: {pdb_id}",
                    )
                )

    assay_boundary = (
        "没有提供可核验的比活力、kcat/Km、Tm、热半衰期或残余活性实测值"
        "|没有提供可核验的比活力、kcat/Km、稳定性终点、Tm、热半衰期或残余活性实测值"
        "|未提供.*(?:specific activity|kcat/Km|稳定性终点|Tm|热半衰期|残余活性)"
        "|未执行.*(?:比活力|稳定性|热稳定性|specific activity|thermostability)"
    )
    if not re.search(assay_boundary, text, re.I):
        violations.append(
            ReportQualityViolation(
                code="missing_assay_boundary",
                message="report does not state whether specific activity and stability measurements were provided",
            )
        )

    if "本轮工具均已完成" in text and re.search(r"(?:completed/)(?:failed|blocked)|(?:失败|阻断|未提交)", text, re.I):
        violations.append(
            ReportQualityViolation(
                code="contradictory_completion_claim",
                message="report claims all tools completed while also showing failed or blocked input status",
            )
        )
    return violations
