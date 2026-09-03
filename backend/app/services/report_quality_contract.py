"""Report quality contract for enzyme engineering outputs.

The contract is intentionally small and deterministic.  It captures the user
visible rules that must survive refactors: Chinese-first structure, evidence
boundaries, candidate gating, and stable section order.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


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
    if not is_structured_enzyme_report(report):
        return {"final_status": "READY", "violations": []}

    text = str(report or "")
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
    return {
        "final_status": "READY" if not violations else "NEEDS_REVIEW",
        "violations": violations,
    }
