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
from typing import Any

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates Markdown reports from agent execution data."""

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

        # Build citations
        citations_block = ""
        if citations:
            cit_lines = ["## 参考文献\n"]
            for c in citations:
                pmid = c.get("pmid", "?")
                title = c.get("title", "Untitled")
                authors = c.get("authors", [])
                year = c.get("year", "?")
                first_author = authors[0] + " et al." if len(authors) > 1 else (authors[0] if authors else "Unknown")
                cit_lines.append(f"- [PMID:{pmid}] {first_author} ({year}). {title}")
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
            f"pipeline: {pipeline_json}\n"
            f"tags: {tags_str}\n"
            f"---\n"
        )

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

        return "\n".join(lines)
