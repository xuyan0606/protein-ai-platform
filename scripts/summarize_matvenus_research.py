#!/usr/bin/env python3
"""Summarize a batch of Matvenus review Markdown files."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


KEYWORDS = {
    "input_preflight": ["预检", "参数", "输入", "FASTA", "PDB", "结构"],
    "candidate_ranking": ["Top", "候选", "优先", "推荐", "排名", "筛选"],
    "no_go": ["不推荐", "禁区", "不能突变", "失活", "No-Go", "负面"],
    "wet_lab_feedback": ["湿实验", "实测", "实验数据", "反馈", "保持率", "酶活"],
    "tradeoff": ["权衡", "trade-off", "活性", "稳定性", "负协同", "上位性"],
    "gradient_plan": ["梯度", "第一层", "第二层", "优先级S", "优先级A", "分步"],
    "docking_md": ["对接", "DiffDock", "GROMACS", "分子动力学", "MD", "Rosetta"],
    "go_no_go": ["Go", "No-Go", "淘汰", "进入下一轮", "下一步"],
}


def _read_index(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("index.json must be a list")
    return [item for item in payload if isinstance(item, dict)]


def _message_count(text: str) -> str:
    match = re.search(r"Messages: `([0-9]+)`", text)
    return match.group(1) if match else "?"


def _tool_names(text: str) -> list[str]:
    before = text.split("## Conversation", 1)[0]
    return list(dict.fromkeys(re.findall(r"- `([^`]+)`", before)))


def _headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") and not line.startswith("# Matvenus Session Review"):
            title = line.lstrip("#").strip()
            if title and not re.match(r"\d+\.\s+(Human|Agent)", title):
                headings.append(title)
    return list(dict.fromkeys(headings))[:12]


def _first_human_prompt(text: str) -> str:
    match = re.search(r"### \d+\. Human[^\n]*\n\n(.+?)(?=\n\n### \d+\.|\Z)", text, re.S)
    if not match:
        return ""
    return _compact(match.group(1), 260)


def _last_agent_excerpt(text: str) -> str:
    matches = list(re.finditer(r"### \d+\. Agent[^\n]*\n\n(.+?)(?=\n\n### \d+\.|\Z)", text, re.S))
    if not matches:
        return ""
    return _compact(matches[-1].group(1), 520)


def _compact(text: str, limit: int) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\|[^\n]*\|", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _keyword_hits(text: str) -> list[str]:
    hits = []
    for label, words in KEYWORDS.items():
        if any(word.lower() in text.lower() for word in words):
            hits.append(label)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("research_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("matvenus-research/summary.md"))
    args = parser.parse_args()

    index = _read_index(args.research_dir / "index.json")
    review_dir = args.research_dir / "reviews"
    reviews = sorted(review_dir.glob("*.review.md"))

    rows: list[dict[str, Any]] = []
    keyword_counter: Counter[str] = Counter()
    tool_counter: Counter[str] = Counter()

    for idx, item in enumerate(index, start=1):
        candidates = list(review_dir.glob(f"{idx:02d}-*.review.md"))
        if not candidates:
            continue
        path = candidates[0]
        text = path.read_text(encoding="utf-8")
        tools = _tool_names(text)
        hits = _keyword_hits(text)
        keyword_counter.update(hits)
        tool_counter.update(tools)
        rows.append(
            {
                "idx": idx,
                "id": item.get("id"),
                "title": item.get("title"),
                "created_at": item.get("created_at"),
                "messages": _message_count(text),
                "tools": tools,
                "headings": _headings(text),
                "first_prompt": _first_human_prompt(text),
                "last_excerpt": _last_agent_excerpt(text),
                "hits": hits,
                "path": path,
            }
        )

    lines = [
        "# Matvenus 多会话调研总报告",
        "",
        "## 范围",
        "",
        f"- 会话列表：`{args.research_dir / 'index.json'}`",
        f"- Review 数量：`{len(reviews)}`",
        f"- 汇总会话：`{len(rows)}`",
        "",
        "## 工具调用概览",
        "",
    ]
    for tool, count in tool_counter.most_common():
        lines.append(f"- `{tool}`：{count} 个会话")

    lines.extend(["", "## 主题模式统计", ""])
    for label, count in keyword_counter.most_common():
        lines.append(f"- `{label}`：{count} 个会话")

    lines.extend(["", "## 会话索引", ""])
    lines.append("| # | 标题 | 消息数 | 工具 | 主题标签 |")
    lines.append("|---|------|--------|------|----------|")
    for row in rows:
        tools = ", ".join(f"`{tool}`" for tool in row["tools"]) or "-"
        hits = ", ".join(f"`{hit}`" for hit in row["hits"]) or "-"
        lines.append(f"| {row['idx']:02d} | {row['title']} | {row['messages']} | {tools} | {hits} |")

    lines.extend(["", "## 单会话摘要", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['idx']:02d}. {row['title']}",
                "",
                f"- Session ID: `{row['id']}`",
                f"- Created: `{row['created_at']}`",
                f"- Review: `{row['path']}`",
                f"- Messages: `{row['messages']}`",
                f"- Tools: {', '.join(f'`{tool}`' for tool in row['tools']) or '-'}",
                f"- First prompt: {row['first_prompt'] or '-'}",
                "",
                "Key headings:",
            ]
        )
        if row["headings"]:
            for heading in row["headings"]:
                lines.append(f"- {heading}")
        else:
            lines.append("- -")
        lines.extend(["", "Last agent excerpt:", "", row["last_excerpt"] or "-", ""])

    lines.extend(
        [
            "## 横向可借鉴点",
            "",
            "1. 预检优先：高频先确认输入、工具参数、PDB/FASTA 适配和计算成本，再启动任务。",
            "2. 候选分层：不是只给 Top 排名，而是拆成双收益、单目标收益、风险/禁改、指定突变复核和组合方案。",
            "3. 实验反馈闭环：遇到湿实验和预测冲突时，会重新解释机制并调整下一轮策略。",
            "4. 组合突变按梯度推进：先最低成本单点/双点验证，再根据数据进入更高阶组合。",
            "5. 输出偏实验执行：常用表格、优先级、避坑提醒、下一步实验计划，适合直接给实验人员用。",
            "",
            "## 需要警惕",
            "",
            "- 多处使用高置信度、成功率、倍数提升等强表述；迁移到本平台时必须标注为计算假设，除非有实验证据。",
            "- 某些会话会在用户追问后修正判断，这说明初始预测不可直接作为最终实验决策。",
            "- 对接、MD、Rosetta 等工具建议应绑定真实输入、参数和产物，不应只停留在概念流程。",
        ]
    )

    args.output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {args.output} sessions={len(rows)} reviews={len(reviews)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
