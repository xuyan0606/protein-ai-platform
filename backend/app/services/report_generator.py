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

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates Markdown reports from agent execution data."""

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
    ) -> str:
        """Generate a full Markdown report for a conversation analysis.

        Returns: Complete Markdown string with YAML front matter.
        """
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

        # Build pipeline summary
        pipeline_lines = []
        for i, step in enumerate(plan, 1):
            status_icon = "✅" if step.get("status") == "completed" else "❌"
            tool = step.get("tool_name", "unknown")
            duration = step.get("duration", "?")
            pipeline_lines.append(f"{i}. {status_icon} **{tool}** — {step.get('description', '')} ({duration}s)")

        # Build tool results section
        results_lines = []
        for r in tool_results:
            tool = r.get("tool_name", "unknown")
            status = r.get("status", "unknown")
            result_str = str(r.get("result", ""))[:500]
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
            f"pipeline: {pipeline_json}\n"
            f"tags: {tags_str}\n"
            f"---\n"
        )

        is_structured_enzyme_report = (
            final_report.lstrip().startswith("# 酶蛋白工程分析报告")
            or "## 任务理解" in final_report[:1000]
        )

        def appendix_heading_block(block: str) -> str:
            text = block.strip()
            if not text:
                return ""
            if text.startswith("## "):
                text = "#" + text
            text = text.replace("\n## ", "\n### ")
            return text + "\n"

        if is_structured_enzyme_report:
            sections = [
                front_matter,
                final_report.strip() + "\n",
            ]
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
