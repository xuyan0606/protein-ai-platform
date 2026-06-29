"""Shared agent communication schemas — typed structured output for inter-agent data.

All agents (Data, Literature, Coordinator) use these types for structured data exchange.
This replaces ad-hoc dict/string passing with typed dataclasses that have:
- Consistent serialization (to_dict / from_dict)
- Standard formatting for LLM prompt injection
- Cross-agent type safety

Usage:
    from app.core.agent_schemas import Citation, EnzymeReference, PipelineExperience
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


# ─── Common Types ───────────────────────────────────────────────────────

@dataclass
class Citation:
    """A single literature citation with structured metadata."""

    pmid: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: int | None = None
    doi: str | None = None
    abstract_snippet: str = ""
    relevance: float = 0.0  # 0-1, from semantic search or citation count

    def format_short(self) -> str:
        """One-line citation for LLM prompt injection."""
        author_str = self.authors[0] + " et al." if len(self.authors) > 1 else (self.authors[0] if self.authors else "Unknown")
        year_str = f" ({self.year})" if self.year else ""
        return f"[PMID:{self.pmid}] {author_str}{year_str}. {self.title}"

    def format_with_abstract(self) -> str:
        """Full citation with abstract snippet."""
        lines = [self.format_short()]
        if self.abstract_snippet:
            lines.append(f"  Abstract: {self.abstract_snippet[:200]}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnzymeReference:
    """Structured reference to an enzyme from the knowledge graph."""

    uniprot_id: str
    name: str = ""
    ec_numbers: list[str] = field(default_factory=list)
    organism: str = ""
    similarity: float = 0.0  # ESM-2 cosine similarity (0-1)
    kinetics_summary: str = ""
    structure_available: bool = False

    def format_short(self) -> str:
        """One-line reference for LLM prompt injection."""
        ec = f" (EC {', '.join(self.ec_numbers)})" if self.ec_numbers else ""
        sim = f" [sim={self.similarity:.2f}]" if self.similarity > 0 else ""
        return f"{self.uniprot_id} ({self.name}){ec}{sim}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineExperience:
    """A past execution experience from MLEvolve retrospective memory."""

    task_type: str
    protein_family: str
    pipeline: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    total_duration: float = 0.0
    round_number: int = 1
    recommended_pipeline: list[str] = field(default_factory=list)

    def format_short(self) -> str:
        """One-line experience summary for LLM prompt injection."""
        status = "✓" if self.success_rate >= 0.8 else "⚠"
        pipeline_preview = " → ".join(self.pipeline[:5])
        if len(self.pipeline) > 5:
            pipeline_preview += "…"
        return f"{status} [{pipeline_preview}] ({self.success_rate:.0%} success, {self.total_duration:.0f}s)"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Source Result Envelope ─────────────────────────────────────────────

@dataclass
class SourceResult:
    """Standard envelope for any knowledge source result.

    Wraps data from any source (KG, PubMed, ESM-2, ChromaDB, Experience)
    with consistent metadata for the Coordinator to merge.
    """

    source: str  # "knowledge_graph" | "pubmed" | "europe_pmc" | "esm2_vector" | "chromadb" | "experience"
    status: str = "success"  # "success" | "error" | "timeout" | "empty"
    context_text: str = ""  # Formatted text for LLM injection
    citations: list[Citation] = field(default_factory=list)
    enzyme_refs: list[EnzymeReference] = field(default_factory=list)
    experiences: list[PipelineExperience] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)  # Source-specific raw data
    elapsed: float = 0.0
    error: str | None = None

    @property
    def has_data(self) -> bool:
        return bool(self.context_text or self.citations or self.enzyme_refs or self.experiences)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "context_text": self.context_text[:500],
            "citations": [c.to_dict() for c in self.citations],
            "enzyme_refs": [e.to_dict() for e in self.enzyme_refs],
            "experiences": [e.to_dict() for e in self.experiences],
            "elapsed": self.elapsed,
            "error": self.error,
        }


# ─── Formatting Utilities ──────────────────────────────────────────────

def format_section_header(title: str, source: str = "") -> str:
    """Standard section header for LLM prompt injection.

    Example: "--- ENZYME KNOWLEDGE GRAPH (knowledge_graph) ---"
    """
    source_tag = f" ({source})" if source else ""
    return f"--- {title}{source_tag} ---"


def format_citations_block(citations: list[Citation], max_items: int = 5) -> str:
    """Format a list of citations as a block for LLM injection."""
    if not citations:
        return ""
    lines = [format_section_header("RELATED LITERATURE", "pubmed/europe_pmc")]
    for c in citations[:max_items]:
        lines.append(c.format_with_abstract())
    return "\n".join(lines)


def format_enzyme_refs_block(refs: list[EnzymeReference], max_items: int = 5) -> str:
    """Format a list of enzyme references as a block for LLM injection."""
    if not refs:
        return ""
    lines = [format_section_header("RELATED ENZYMES", "knowledge_graph/esm2")]
    for r in refs[:max_items]:
        lines.append(f"- {r.format_short()}")
    return "\n".join(lines)


def format_experiences_block(exps: list[PipelineExperience], max_items: int = 3) -> str:
    """Format past experiences as a block for LLM injection."""
    if not exps:
        return ""
    lines = [format_section_header("PAST EXPERIENCES", "mlevolve_memory")]
    for e in exps[:max_items]:
        lines.append(f"- {e.format_short()}")
    return "\n".join(lines)
