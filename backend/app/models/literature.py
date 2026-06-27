"""Literature data models — PubMed/Europe PMC papers + enzyme-paper links."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Float, DateTime, JSON,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Paper(Base):
    """A scientific paper from PubMed/Europe PMC."""
    __tablename__ = "papers"

    pmid: Mapped[str] = mapped_column(String(20), primary_key=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of author names
    journal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    mesh_terms: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="pubmed")  # pubmed, europe_pmc
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    enzyme_links: Mapped[list[EnzymeLiteratureLink]] = relationship(
        "EnzymeLiteratureLink", back_populates="paper", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_paper_doi", "doi"),
        Index("ix_paper_year", "year"),
        Index("ix_paper_journal", "journal"),
    )


class EnzymeLiteratureLink(Base):
    """Many-to-many link between enzymes and papers."""
    __tablename__ = "enzyme_literature_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False
    )
    paper_pmid: Mapped[str] = mapped_column(
        String(20), ForeignKey("papers.pmid", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="general"
    )  # kinetics, stability, structure, evolution, function, general
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="manual"
    )  # brenda, protherm, enzengdb, pubmed_search, manual
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    enzyme: Mapped["EnzymeRecord"] = relationship("EnzymeRecord", backref="literature_links")
    paper: Mapped[Paper] = relationship("Paper", back_populates="enzyme_links")

    __table_args__ = (
        UniqueConstraint("enzyme_id", "paper_pmid", "relation_type", name="uq_enzyme_paper_relation"),
        Index("ix_litlink_enzyme", "enzyme_id"),
        Index("ix_litlink_paper", "paper_pmid"),
        Index("ix_litlink_type", "relation_type"),
    )
