"""Markdown report generator — produces .md files from Agent execution results.

Generates structured Markdown with YAML front matter for:
- Individual agent conversation reports
- Batch analysis summaries
- Sequence analysis reports
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
import platform
from typing import Any

from app.core.config import settings
from app.services.platform_manifest import collect_platform_manifest
from app.services.report_evidence_contract import make_evidence_record
from app.services.report_manifest import build_report_manifest, manifest_sha256


REPORT_SCHEMA_VERSION = "1.1"
_EXTERNAL_EVIDENCE_TOOLS = frozenset(
    {
        "annotation_bundle",
        "blast_search",
        "literature_live_search",
        "residue_mapping_sifts",
        "sequence_search",
        "structure_search_foldseek",
    }
)
from app.services.report_quality_contract import (
    assess_enzyme_report_completion,
    is_structured_enzyme_report,
    merge_workflow_and_report_status,
)
from app.services.task_evidence import parse_tool_payload
from app.services.thermostability_report import render_thermostability_results
from app.core.tool_outcome import normalize_tool_result

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates Markdown reports from agent execution data."""

    _CRITICAL_GATE_TOOLS = frozenset({
        "enzyme_objective_module_plan",
        "enzyme_identity_profile",
        "residue_numbering_gate",
        "mutation_priority_score",
    })

    @staticmethod
    def _safe_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value.strip():
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _evidence_status(status: Any) -> str:
        """Map tool lifecycle states into the conservative report contract."""
        value = str(status or "not_available").strip().lower()
        if value in {"completed", "completed_no_hit", "completed_with_hits"}:
            return value
        if value in {"submitted", "running", "pending", "waiting", "queued", "degraded"}:
            return "waiting"
        if value in {"failed", "blocked", "canceled", "cancelled", "error"}:
            return "failed"
        if value in {"not_run", "skipped"}:
            return "not_run"
        return "not_available"

    @classmethod
    def _evidence_records(cls, plan: list[dict], tool_results: list[dict]) -> list[dict[str, Any]]:
        """Create one traceable evidence row per planned or executed tool."""
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        entries = list(tool_results) + [item for item in plan if isinstance(item, dict)]
        for item in entries:
            tool = str(item.get("tool_name") or item.get("tool") or "unknown")
            if tool in seen:
                continue
            seen.add(tool)
            payload = cls._safe_payload(item.get("result"))
            raw_status = item.get("status")
            payload_status = payload.get("evidence_status") or payload.get("status")
            status = cls._evidence_status(
                (payload_status or raw_status)
                if str(raw_status or "").lower() in {"completed", "submitted", "waiting"}
                else raw_status
            )
            evidence_type = "database_evidence" if tool in _EXTERNAL_EVIDENCE_TOOLS else "computed_result"
            source = item.get("evidence_source")
            if not isinstance(source, dict):
                source = payload.get("evidence_source") if isinstance(payload.get("evidence_source"), dict) else {}
            source_name = source.get("source") or source.get("mode") or tool
            record = make_evidence_record(
                evidence_type=evidence_type,
                status=status,
                source=str(source_name),
                value={
                    "tool": tool,
                    "raw_status": str(item.get("status") or "not_available"),
                    "live_query_executed": bool(source.get("live_query_executed")),
                },
            ).to_dict()
            record["evidence_id"] = f"tool:{tool}"
            rows.append(record)
        return rows

    @classmethod
    def _evidence_summary(cls, records: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {"completed": 0, "waiting": 0, "failed": 0, "not_run": 0, "not_available": 0}
        for record in records:
            status = str(record.get("status") or "not_available")
            if status in {"completed_no_hit", "completed_with_hits"}:
                status = "completed"
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(records),
            "completed": counts["completed"],
            "waiting": counts["waiting"],
            "failed": counts["failed"],
            "not_run": counts["not_run"],
            "not_available": counts["not_available"],
        }

    @staticmethod
    def _report_manifest_markdown(manifest: dict[str, Any]) -> str:
        return "\n".join(
            [
                "### Report Reproducibility Manifest",
                "",
                f"- report_schema_version: `{manifest['report_schema_version']}`",
                f"- report_revision_id: `{manifest['report_revision_id']}`",
                "",
                "```json",
                json.dumps(manifest["manifest"], ensure_ascii=False, indent=2),
                "```",
            ]
        ) + "\n"

    @staticmethod
    def _evidence_contract_markdown(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
        rows = [
            "### Evidence Contract",
            "",
            "| Evidence ID | Type | Status | Render status | Source |",
            "|---|---|---|---|---|",
        ]
        for record in records:
            rows.append(
                "| {id} | {type} | {status} | {render} | {source} |".format(
                    id=str(record.get("evidence_id") or "").replace("|", "/"),
                    type=str(record.get("evidence_type") or ""),
                    status=str(record.get("status") or ""),
                    render=str(record.get("render_status") or "").replace("|", "/"),
                    source=str(record.get("source") or "").replace("|", "/"),
                )
            )
        rows.extend(
            [
                "",
                "```json",
                json.dumps(summary, ensure_ascii=False, indent=2),
                "```",
            ]
        )
        return "\n".join(rows) + "\n"

    @classmethod
    def _display_tool_status(cls, result: dict[str, Any]) -> str:
        """Return the scientific terminal status, not a scheduler wrapper state.

        Background workers may report ``completed`` after returning a nested
        tool payload whose actual status is ``blocked`` or ``failed``.  Wiki
        exports must preserve that inner boundary just like the chat report.
        ``submitted`` remains a receipt and is never upgraded to evidence.
        """
        outer = str(result.get("status") or "unknown").strip().lower()
        if outer in {"submitted", "pending", "running", "queued"}:
            return "submitted"
        if outer not in {"completed", "success"}:
            return outer or "unknown"
        raw_payload = result.get("result")
        if raw_payload is None or raw_payload == "":
            raw_payload = result.get("result_preview")
        payload = parse_tool_payload(raw_payload)
        outcome = normalize_tool_result(payload) if payload else None
        if outcome and outcome.status != "completed":
            return outcome.status
        if not cls._has_tool_result_payload(raw_payload):
            return "failed"
        return outcome.status if outcome else "completed"

    @classmethod
    def _has_tool_result_payload(cls, value: Any) -> bool:
        """Reject scheduler receipts that say completed without a tool output."""
        if value is None:
            return False
        if isinstance(value, str):
            if not value.strip():
                return False
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Some legacy tools return plain text instead of JSON.
                return True
            return cls._has_tool_result_payload(parsed)
        if isinstance(value, dict):
            if "result" in value:
                return cls._has_tool_result_payload(value.get("result"))
            if "raw_result" in value:
                return cls._has_tool_result_payload(value.get("raw_result"))
            payload_keys = set(value) - {
                "status", "reason", "blocked_reason", "error", "error_code",
                "claim_eligible", "duration", "duration_seconds",
                "duration_ms", "task_id", "status_url", "cancel_url",
                "artifacts_url", "queue", "submitted_at", "note",
                # These are bounded scheduler/UI previews, not tool output.
                # They may be useful for display but cannot establish a
                # completed scientific result on their own.
                "result_preview", "result_summary",
            }
            return bool(payload_keys)
        if isinstance(value, (list, tuple)):
            return bool(value)
        return True

    @classmethod
    def _critical_gate_status(cls, tool_results: list[dict[str, Any]]) -> str:
        """Catch critical gate failures without treating absent traces as passes."""
        # A conversation can contain an earlier blocked attempt followed by a
        # rerun.  Evaluate the latest record for each gate so an old attempt
        # cannot permanently poison the current report, while still keeping a
        # missing current trace fail-closed below.
        latest: dict[str, dict[str, Any]] = {}
        for result in tool_results:
            if not isinstance(result, dict):
                continue
            tool_name = str(result.get("tool_name") or result.get("tool") or "")
            if tool_name in cls._CRITICAL_GATE_TOOLS:
                latest[tool_name] = result

        # A single successful gate cannot stand in for the rest.  A structured
        # enzyme-engineering report may only be marked as having cleared its
        # execution gates when the complete candidate-generation gate set was
        # recorded in this report's execution trace.
        if not cls._CRITICAL_GATE_TOOLS.issubset(latest):
            return "NEEDS_REVIEW" if latest else "NOT_RECORDED"

        for tool_name, result in latest.items():
            status = cls._display_tool_status(result)
            if status != "completed":
                return "NEEDS_REVIEW"

            payload = parse_tool_payload(result.get("result"))
            if tool_name == "enzyme_objective_module_plan":
                if (
                    str(payload.get("status") or "").lower() != "ready"
                    or payload.get("candidate_output_allowed") is not True
                ):
                    return "NEEDS_REVIEW"
            elif tool_name == "residue_numbering_gate":
                if str(payload.get("status") or "").lower() not in {"ready", "allowed"}:
                    return "NEEDS_REVIEW"
            elif tool_name == "enzyme_identity_profile":
                guardrail = payload.get("guardrail")
                # ``identified`` alone is only a family claim.  Candidate
                # generation requires the explicit guardrail and confirmed
                # protected positions; a missing guardrail is incomplete
                # evidence, never an implicit pass.
                if (
                    not isinstance(guardrail, dict)
                    or str(guardrail.get("status") or "").lower() != "ready"
                    or payload.get("identity_status") != "identified"
                    or not isinstance(payload.get("protected_positions"), list)
                    or not payload.get("protected_positions")
                ):
                    return "NEEDS_REVIEW"
            elif tool_name == "mutation_priority_score":
                # The scoring tool historically omitted a top-level status;
                # shape and terminal normalization are therefore checked
                # together.  A scheduler receipt or arbitrary preview text
                # must not unlock a candidate report.
                has_candidate_payload = any(
                    isinstance(payload.get(key), list)
                    for key in ("tier_1_candidates", "tier_2_candidates", "all_positions")
                )
                if (
                    str(payload.get("status") or "").lower().startswith(("blocked", "failed", "degraded"))
                    or not has_candidate_payload
                ):
                    return "NEEDS_REVIEW"
        return "NO_BLOCKED_GATE_RECORDED"

    @classmethod
    def _collect_evidence_sources(cls, tool_results: list[dict]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for result in tool_results:
            tool = result.get("tool_name") or result.get("tool") or "unknown"
            payload = cls._safe_payload(result.get("result"))
            if not payload:
                payload = cls._safe_payload(result.get("result_preview"))

            direct = result.get("evidence_source")
            if not isinstance(direct, dict):
                direct = payload.get("evidence_source") if isinstance(payload.get("evidence_source"), dict) else None
            if isinstance(direct, dict):
                rows.append({"tool": tool, "subsource": "-", **direct})

            def collect_nested(value: Any, path: str) -> None:
                if isinstance(value, dict):
                    nested_source = value.get("evidence_source")
                    if isinstance(nested_source, dict):
                        rows.append({"tool": tool, "subsource": path or "-", **nested_source})
                    for key, child in value.items():
                        if key != "evidence_source":
                            child_path = f"{path}.{key}" if path else str(key)
                            collect_nested(child, child_path)
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        collect_nested(child, f"{path}[{index}]")

            for key, nested in payload.items():
                if key != "evidence_source":
                    collect_nested(nested, str(key))
        return rows

    @classmethod
    def _evidence_sources_markdown(cls, tool_results: list[dict]) -> str:
        rows = cls._collect_evidence_sources(tool_results)
        if not rows:
            return ""
        lines = [
            "## 联网/证据源状态\n",
            "| 工具 | 子源 | 状态 | 模式 | 本轮联网 | 来源 | 说明 |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            live = "是" if row.get("live_query_executed") else "否"
            reason = str(row.get("reason") or "")
            lines.append(
                "| {tool} | {subsource} | {status} | {mode} | {live} | {source} | {reason} |".format(
                    tool=str(row.get("tool") or ""),
                    subsource=str(row.get("subsource") or "-"),
                    status=str(row.get("status") or "unknown"),
                    mode=str(row.get("mode") or ""),
                    live=live,
                    source=str(row.get("source") or ""),
                    reason=reason.replace("|", "/")[:180],
                )
            )
        manifest = [
            {
                key: row.get(key) or ""
                for key in (
                    "tool",
                    "subsource",
                    "status",
                    "mode",
                    "source",
                    "endpoint",
                    "checked_at",
                    "reason",
                )
            }
            for row in rows
        ]
        lines.extend(
            [
                "",
                "## Evidence Manifest",
                "",
                "```json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
                "```",
            ]
        )
        return "\n".join(lines) + "\n"

    @classmethod
    def _collect_literature_results(cls, tool_results: list[dict]) -> list[dict[str, Any]]:
        papers: list[dict[str, Any]] = []
        for result in tool_results:
            tool = result.get("tool_name") or result.get("tool") or ""
            if tool != "literature_live_search":
                continue
            payload = cls._safe_payload(result.get("result"))
            if not payload:
                payload = cls._safe_payload(result.get("result_preview"))
            results = payload.get("results")
            if isinstance(results, list):
                papers.extend(item for item in results if isinstance(item, dict))
        return papers

    @staticmethod
    def _markdown_cell(value: Any, fallback: str = "") -> str:
        text = str(value or fallback).replace("|", "/").replace("\n", " ").strip()
        return text

    @classmethod
    def _literature_markdown(cls, papers: list[dict[str, Any]]) -> str:
        if not papers:
            return ""
        lines = [
            "### 联网文献证据\n",
            "| # | PMID | DOI | 标题 | 来源 | 发表时间 |",
            "|---|---|---|---|---|---|",
        ]
        for index, paper in enumerate(papers, 1):
            lines.append(
                "| {index} | {pmid} | {doi} | {title} | {source} | {published} |".format(
                    index=index,
                    pmid=cls._markdown_cell(paper.get("pmid"), "-"),
                    doi=cls._markdown_cell(paper.get("doi"), "-"),
                    title=cls._markdown_cell(paper.get("title"), "Untitled"),
                    source=cls._markdown_cell(paper.get("source"), "-"),
                    published=cls._markdown_cell(
                        paper.get("published") or paper.get("year"),
                        "-",
                    ),
                )
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _normalize_doi(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _normalize_pmid(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _year(value: Any) -> str:
        text = str(value or "").strip()
        return text[:4] if len(text) >= 4 and text[:4].isdigit() else text

    @classmethod
    def _merge_citation_entry(cls, existing: dict[str, Any], incoming: dict[str, Any]) -> None:
        for key in ("PMID", "DOI", "title", "source", "year", "url"):
            if not existing.get(key) and incoming.get(key):
                existing[key] = incoming[key]
        tools = existing.setdefault("evidence_tool", [])
        incoming_tools = incoming.get("evidence_tool")
        if not isinstance(incoming_tools, list):
            incoming_tools = [incoming_tools] if incoming_tools else []
        for tool in incoming_tools:
            if tool and tool not in tools:
                tools.append(tool)

    @classmethod
    def _collect_citation_manifest(
        cls,
        citations: list[dict] | None,
        tool_results: list[dict],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        key_to_index: dict[str, int] = {}

        def add(raw: dict[str, Any], evidence_tool: str) -> None:
            doi = cls._normalize_doi(raw.get("doi") or raw.get("DOI"))
            pmid = cls._normalize_pmid(raw.get("pmid") or raw.get("PMID"))
            entry = {
                "PMID": pmid,
                "DOI": doi,
                "title": str(raw.get("title") or raw.get("name") or "").strip(),
                "source": str(raw.get("source") or raw.get("journal") or raw.get("container_title") or "").strip(),
                "year": cls._year(raw.get("year") or raw.get("published") or raw.get("publication_year")),
                "url": str(raw.get("url") or raw.get("link") or "").strip(),
                "evidence_tool": [evidence_tool],
            }
            keys = []
            if doi:
                keys.append(f"doi:{doi}")
            if pmid:
                keys.append(f"pmid:{pmid}")
            index = next((key_to_index[key] for key in keys if key in key_to_index), None)
            if index is None:
                index = len(entries)
                entries.append(entry)
            else:
                cls._merge_citation_entry(entries[index], entry)
            for key in keys:
                key_to_index[key] = index

        for citation in citations or []:
            if isinstance(citation, dict):
                add(citation, "citations")
        for paper in cls._collect_literature_results(tool_results):
            add(paper, "literature_live_search")

        return entries

    @staticmethod
    def _citation_manifest_markdown(entries: list[dict[str, Any]]) -> str:
        if not entries:
            return ""
        return "\n".join(
            [
                "### Citation Manifest",
                "",
                "```json",
                json.dumps(entries, ensure_ascii=False, indent=2),
                "```",
            ]
        ) + "\n"

    @staticmethod
    def _platform_manifest_markdown() -> str:
        return "\n".join(
            [
                "## Platform/Data Manifest",
                "",
                "```json",
                json.dumps(collect_platform_manifest(), ensure_ascii=False, indent=2),
                "```",
            ]
        ) + "\n"

    def generate_conversation_report(
        self,
        *,
        project_name: str,
        conversation_title: str,
        user_message: str,
        research_notes: str,
        plan: list[dict],
        tool_results: list[dict],
        final_report: str,
        citations: list[dict] | None = None,
        tags: list[str] | None = None,
        task_contract: dict[str, Any] | None = None,
    ) -> str:
        """Generate a full Markdown report for a conversation analysis.

        Returns: Complete Markdown string with YAML front matter.
        """
        thermal_report = render_thermostability_results(tool_results)
        if thermal_report and thermal_report.strip() not in str(final_report or ""):
            final_report = str(final_report or "").rstrip() + "\n\n" + thermal_report

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        date_short = datetime.now().strftime("%Y-%m-%d")

        evidence_records = self._evidence_records(plan, tool_results)
        evidence_summary = self._evidence_summary(evidence_records)
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        manifest = build_report_manifest(
            inputs={
                "user_message": str(user_message or ""),
                "research_notes": str(research_notes or ""),
                "tool_results": json.dumps(tool_results, ensure_ascii=False, sort_keys=True, default=str),
                "final_report": str(final_report or ""),
            },
            report_schema_version=REPORT_SCHEMA_VERSION,
            tools=[
                {
                    "name": str(item.get("tool_name") or item.get("tool") or "unknown"),
                    "status": str(item.get("status") or "not_available"),
                    "version": item.get("version") or item.get("tool_version") or "",
                }
                for item in plan
                if isinstance(item, dict)
            ],
            models=(
                [{
                    "provider": str(getattr(settings, "LLM_PROVIDER", "") or ""),
                    "model": str(getattr(settings, "LLM_MODEL", "") or ""),
                }]
                + [
                    {
                        "provider": str(item.get("provider") or ""),
                        "model": str(item.get("model") or item.get("model_id") or ""),
                    }
                    for item in tool_results
                    if isinstance(item, dict)
                    and (item.get("model") or item.get("model_id") or item.get("provider"))
                ]
            ),
            databases=[
                {
                    "name": str(source.get("source") or ""),
                    "endpoint": str(source.get("endpoint") or ""),
                    "status": str(source.get("status") or ""),
                }
                for item in tool_results
                if isinstance(item, dict)
                for source in [
                    item.get("evidence_source")
                    if isinstance(item.get("evidence_source"), dict)
                    else self._safe_payload(item.get("result")).get("evidence_source")
                ]
                if isinstance(source, dict) and source.get("source")
            ],
            runtime={"python": platform.python_version(), "generator": self.__class__.__name__},
            generated_at=generated_at,
        )
        revision_id = manifest_sha256(manifest)
        manifest_bundle = {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "report_revision_id": revision_id,
            "manifest": manifest,
        }

        structured_enzyme_report = is_structured_enzyme_report(final_report)
        completion = assess_enzyme_report_completion(final_report)
        report_quality_status = str(completion.get("final_status") or "NEEDS_REVIEW")
        workflow_status = str((task_contract or {}).get("final_status") or "UNKNOWN").upper()
        execution_gate_status = self._critical_gate_status(tool_results)
        # A structured report without a recorded critical gate is incomplete,
        # even if its Markdown headings happen to satisfy the presentation
        # contract.  Missing trace evidence must not be rendered as READY.
        unresolved_gate = execution_gate_status in {"NEEDS_REVIEW", "NOT_RECORDED"}
        merged_status = merge_workflow_and_report_status(
            report_quality_status,
            "NEEDS_REVIEW" if unresolved_gate else (
                workflow_status if workflow_status != "UNKNOWN" else None
            ),
        )
        report_status = "READY" if merged_status in {"READY", "COMPLETED"} else "NEEDS_REVIEW"
        # Build pipeline summary
        pipeline_lines = []
        for i, step in enumerate(plan, 1):
            step_status = str(step.get("status") or "unknown").lower()
            status_icon = {
                "completed": "✅",
                "submitted": "⏳",
                "blocked": "⚠️",
                "failed": "❌",
                "timeout": "❌",
            }.get(step_status, "◻️")
            tool = step.get("tool_name", "unknown")
            duration = step.get("duration", "?")
            pipeline_lines.append(f"{i}. {status_icon} **{tool}** — {step.get('description', '')} ({duration}s)")

        # Build tool results section
        results_lines = []
        for r in tool_results:
            tool = r.get("tool_name", "unknown")
            status = self._display_tool_status(r)
            raw_result = r.get("result")
            result_str = (
                str(raw_result)[:500]
                if raw_result is not None and str(raw_result).strip()
                else "No tool payload was persisted."
            )
            results_lines.append(f"### {tool} ({status})\n```json\n{result_str}\n```")

        # Build citations, including structured results from live literature search.
        citations_block = ""
        literature_papers = self._collect_literature_results(tool_results)
        literature_block = self._literature_markdown(literature_papers)
        citation_manifest = self._citation_manifest_markdown(self._collect_citation_manifest(citations, tool_results))
        if citations or literature_block or citation_manifest:
            cit_lines = ["## 参考文献\n"]
            if citations:
                for c in citations:
                    pmid = c.get("pmid", "?")
                    title = c.get("title", "Untitled")
                    authors = c.get("authors", [])
                    year = c.get("year", "?")
                    first_author = authors[0] + " et al." if len(authors) > 1 else (authors[0] if authors else "Unknown")
                    cit_lines.append(f"- [PMID:{pmid}] {first_author} ({year}). {title}")
            if literature_block:
                if citations:
                    cit_lines.append("")
                cit_lines.append(literature_block.rstrip())
            if citation_manifest:
                if citations or literature_block:
                    cit_lines.append("")
                cit_lines.append(citation_manifest.rstrip())
            citations_block = "\n".join(cit_lines) + "\n"

        # YAML front matter
        tags_str = json.dumps(tags or [], ensure_ascii=False)
        pipeline_names = [s.get("tool_name", "") for s in plan]
        pipeline_json = json.dumps(pipeline_names, ensure_ascii=False)

        front_matter = (
            f"---\n"
            f'project: "{project_name}"\n'
            f'title: "{conversation_title}"\n'
            f"date: {now}\n"
            f"report_schema_version: {REPORT_SCHEMA_VERSION}\n"
            f"report_revision_id: {revision_id}\n"
            f"evidence_summary: {json.dumps(evidence_summary, ensure_ascii=False, sort_keys=True)}\n"
            f'report_status: "{report_status}"\n'
            f'report_quality_status: "{report_quality_status}"\n'
            f'workflow_status: "{workflow_status}"\n'
            f'execution_gate_status: "{execution_gate_status}"\n'
            f"pipeline: {pipeline_json}\n"
            f"tags: {tags_str}\n"
            f"---\n"
        )

        def appendix_heading_block(block: str) -> str:
            text = block.strip()
            if not text:
                return ""
            if text.startswith("## "):
                text = "#" + text
            text = text.replace("\n## ", "\n### ")
            return text + "\n"

        if structured_enzyme_report:
            sections = [
                front_matter,
                final_report.strip() + "\n",
            ]
            if workflow_status not in {"UNKNOWN", "READY", "COMPLETED"}:
                status_note = (
                    f"任务状态为 {workflow_status}；报告按阶段性结果复核。"
                )
            elif unresolved_gate:
                status_note = "执行轨迹中的关键身份/目标门控未通过或缺少可核验结果，应按阶段报告复核。"
            elif report_quality_status != "READY":
                status_note = "报告仍有内容缺项或科学目标门控未通过，应按阶段报告复核。"
            else:
                status_note = "报告交付项检查通过；这不代表生物学结论或候选已经实验验证。"
            sections.append(
                "## 报告交付状态\n\n"
                f"- 状态：{report_status}\n"
                f"- 任务状态：{workflow_status}\n"
                f"- 报告完整性状态：{report_quality_status}\n"
                f"- 执行门控状态：{execution_gate_status}\n"
                f"- 说明：{status_note}\n"
            )
            appendix_sections: list[str] = []
            if research_notes:
                appendix_sections.append(f"### 研究背景\n\n{research_notes.strip()}\n")
            if pipeline_lines:
                appendix_sections.append("### 分析管线\n\n" + "\n".join(pipeline_lines) + "\n")

            appendix_sections.append(self._evidence_contract_markdown(evidence_records, evidence_summary))
            appendix_sections.append(self._report_manifest_markdown(manifest_bundle))

            evidence_block = appendix_heading_block(self._evidence_sources_markdown(tool_results))
            if evidence_block:
                appendix_sections.append(evidence_block)

            platform_block = appendix_heading_block(self._platform_manifest_markdown())
            if platform_block:
                appendix_sections.append(platform_block)

            if citations_block:
                appendix_sections.append(appendix_heading_block(citations_block))

            if results_lines:
                appendix_sections.append("### 工具执行结果\n\n" + "\n\n".join(results_lines) + "\n")

            if appendix_sections:
                sections.append("## 附录：发布与原始执行信息\n\n" + "\n".join(appendix_sections))

            return "\n".join(sections)

        # Assemble report
        sections = [
            front_matter,
            f"# {conversation_title}\n",
            f"> 酶蛋白AI平台 · {date_short} · {project_name}\n",
            f"## 用户提问\n\n{user_message}\n",
        ]

        if research_notes:
            sections.append(f"## 研究背景 (PI Research)\n\n{research_notes}\n")

        if pipeline_lines:
            sections.append("## 分析管线\n\n" + "\n".join(pipeline_lines) + "\n")

        sections.append(f"## 分析报告\n\n{final_report}\n")

        sections.append(self._evidence_contract_markdown(evidence_records, evidence_summary))
        sections.append(self._report_manifest_markdown(manifest_bundle))

        evidence_block = self._evidence_sources_markdown(tool_results)
        if evidence_block:
            sections.append(evidence_block)

        sections.append(self._platform_manifest_markdown())

        if citations_block:
            sections.append(citations_block)

        if results_lines:
            sections.append("## 附录：工具执行结果\n\n" + "\n\n".join(results_lines) + "\n")

        return "\n".join(sections)

    def generate_batch_summary(
        self,
        *,
        project_name: str,
        batch_id: str,
        tool_name: str,
        sequences: list[dict],
        results: list[dict],
    ) -> str:
        """Generate a summary Markdown report for a batch analysis job."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        date_short = datetime.now().strftime("%Y-%m-%d")

        lines = [
            f"---\nproject: \"{project_name}\"\nbatch_id: {batch_id}\ndate: {now}\n---\n",
            f"# 批量分析汇总: {tool_name}\n",
            f"> {date_short} · {project_name} · {len(sequences)} 个序列\n",
            "## 序列列表\n",
            "| # | 名称 | 长度 | 状态 |",
            "|---|------|------|------|",
        ]

        for i, seq in enumerate(sequences, 1):
            name = seq.get("name", f"seq_{i}")
            length = len(seq.get("sequence", ""))
            status = "✅" if i <= len(results) else "—"
            lines.append(f"| {i} | {name} | {length} aa | {status} |")

        lines.append("\n## 结果汇总\n")
        for i, r in enumerate(results):
            name = sequences[i].get("name", f"seq_{i+1}") if i < len(sequences) else f"seq_{i+1}"
            lines.append(f"### {name}\n```json\n{json.dumps(r, ensure_ascii=False, default=str)[:500]}\n```\n")

        evidence_block = self._evidence_sources_markdown([
            {"tool": tool_name, "status": "completed", "result": item}
            for item in results
        ])
        if evidence_block:
            lines.append(evidence_block)

        return "\n".join(lines)
