"""Domain data models for the 6-category 10-database integration.

UniProt Swiss-Prot + Pfam       → EnzymeRecord, Taxonomy, PfamDomain, DomainArchitecture
RCSB PDB + AlphaFold            → PDBStructure, AlphaFoldStructure
BRENDA + OED                    → KineticParameter
ProThermDB                      → StabilityRecord
PubChem + Rhea                  → SubstrateCompound, ReactionEquation
EnzEngDB                        → DirectedEvolutionEntry
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# =============================================================================
# 1. Taxonomy — organism classification
# =============================================================================
class Taxonomy(Base):
    __tablename__ = "taxonomy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ncbi_taxid: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    scientific_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    common_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lineage: Mapped[str | None] = mapped_column(Text, nullable=True)  # kingdom → species
    superkingdom: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phylum: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_class: Mapped[str | None] = mapped_column(String(200), nullable=True)
    order_: Mapped[str | None] = mapped_column("order_", String(200), nullable=True)
    family: Mapped[str | None] = mapped_column(String(200), nullable=True)
    genus: Mapped[str | None] = mapped_column(String(200), nullable=True)

    enzymes: Mapped[list[EnzymeRecord]] = relationship("EnzymeRecord", back_populates="taxonomy")


# =============================================================================
# 2. EnzymeRecord — central protein aggregation table (UniProt primary key)
# =============================================================================
class EnzymeRecord(Base):
    __tablename__ = "enzyme_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uniprot_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    entry_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    seq_length: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    gene_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    function_annotation: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalytic_activity: Mapped[str | None] = mapped_column(Text, nullable=True)
    cofactors: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Organism link
    taxonomy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("taxonomy.id"), nullable=True)
    taxonomy: Mapped[Taxonomy | None] = relationship("Taxonomy", back_populates="enzymes")

    # Sequence embedding (pgvector in production, nullable for SQLite dev)
    embedding: Mapped[bytes | None] = mapped_column(nullable=True)

    # Metadata
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)   # Swiss-Prot vs TrEMBL
    source_db: Mapped[str] = mapped_column(String(50), default="uniprot")
    source_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ec_numbers: Mapped[list[EnzymeECLink]] = relationship("EnzymeECLink", back_populates="enzyme", cascade="all, delete-orphan")
    domains: Mapped[list[DomainArchitecture]] = relationship("DomainArchitecture", back_populates="enzyme", cascade="all, delete-orphan")
    pdb_structures: Mapped[list[PDBStructure]] = relationship("PDBStructure", back_populates="enzyme", cascade="all, delete-orphan")
    alphafold_structures: Mapped[list[AlphaFoldStructure]] = relationship("AlphaFoldStructure", back_populates="enzyme", cascade="all, delete-orphan")
    kinetic_params: Mapped[list[KineticParameter]] = relationship("KineticParameter", back_populates="enzyme", cascade="all, delete-orphan")
    stability_records: Mapped[list[StabilityRecord]] = relationship("StabilityRecord", back_populates="enzyme", cascade="all, delete-orphan")
    evolution_entries: Mapped[list[DirectedEvolutionEntry]] = relationship("DirectedEvolutionEntry", back_populates="enzyme", cascade="all, delete-orphan")
    xrefs: Mapped[list[DatabaseCrossRef]] = relationship("DatabaseCrossRef", back_populates="enzyme", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_enzyme_seq_len", "seq_length"),
        Index("ix_enzyme_source", "source_db"),
    )


# =============================================================================
# 3. EC Numbers — hierarchical Enzyme Commission classification
# =============================================================================
class ECNumber(Base):
    __tablename__ = "ec_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ec_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "Oxidoreductases"
    level1: Mapped[str | None] = mapped_column(String(5), nullable=True)     # EC 1.-.-.-
    level2: Mapped[str | None] = mapped_column(String(10), nullable=True)    # EC 1.1.-.-
    level3: Mapped[str | None] = mapped_column(String(15), nullable=True)    # EC 1.1.1.-

    enzymes: Mapped[list[EnzymeECLink]] = relationship("EnzymeECLink", back_populates="ec_number", cascade="all, delete-orphan")


class EnzymeECLink(Base):
    """Many-to-many: one enzyme can have multiple EC numbers."""

    __tablename__ = "enzyme_ec_links"
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), primary_key=True)
    ec_id: Mapped[int] = mapped_column(Integer, ForeignKey("ec_numbers.id", ondelete="CASCADE"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="ec_numbers")
    ec_number: Mapped[ECNumber] = relationship("ECNumber", back_populates="enzymes")


# =============================================================================
# 4. Pfam domains — protein family domain annotation
# =============================================================================
class PfamDomain(Base):
    __tablename__ = "pfam_domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pfam_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    clan: Mapped[str | None] = mapped_column(String(50), nullable=True)

    architectures: Mapped[list[DomainArchitecture]] = relationship("DomainArchitecture", back_populates="domain")


class DomainArchitecture(Base):
    """Junction: protein X has domain Y at positions [start, end]."""

    __tablename__ = "domain_architecture"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False)
    domain_id: Mapped[int] = mapped_column(Integer, ForeignKey("pfam_domains.id", ondelete="CASCADE"), nullable=False)
    start_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    end_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    evalue: Mapped[float | None] = mapped_column(Float, nullable=True)

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="domains")
    domain: Mapped[PfamDomain] = relationship("PfamDomain", back_populates="architectures")

    __table_args__ = (
        UniqueConstraint("enzyme_id", "domain_id", "start_pos", name="uq_domain_arch"),
    )


# =============================================================================
# 5. PDB structures — experimentally determined 3D structures
# =============================================================================
class PDBStructure(Base):
    __tablename__ = "pdb_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pdb_id: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)   # X-ray, NMR, Cryo-EM
    resolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    chain_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    deposited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pdb_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # MinIO / S3 path

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="pdb_structures")


# =============================================================================
# 6. AlphaFold structures — predicted structures (Swiss-Prot subset)
# =============================================================================
class AlphaFoldStructure(Base):
    __tablename__ = "alphafold_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    model_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    plddt_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    plddt_per_residue: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pae_matrix_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cif_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # MinIO path

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="alphafold_structures")


# =============================================================================
# 7. Kinetic parameters — BRENDA + OED enzyme kinetics data
# =============================================================================
class KineticParameter(Base):
    __tablename__ = "kinetic_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False)
    source_db: Mapped[str] = mapped_column(String(20), nullable=False)   # brenda, oed
    param_type: Mapped[str] = mapped_column(String(30), nullable=False)   # Kcat, Km, Ki, Kcat/Km, Vmax, IC50
    substrate_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    substrate_smiles: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    mutant: Mapped[str | None] = mapped_column(String(20), nullable=True)  # wild-type / mutation code
    organism_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    literature_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)  # PMID or DOI
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="kinetic_params")

    __table_args__ = (
        Index("ix_kp_type", "param_type"),
        Index("ix_kp_source", "source_db"),
    )


# =============================================================================
# 8. Stability records — ProThermDB mutation thermodynamics
# =============================================================================
class StabilityRecord(Base):
    __tablename__ = "stability_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False)
    mutation: Mapped[str] = mapped_column(String(20), nullable=False)     # e.g. "A23G"
    mutation_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    wild_type: Mapped[str] = mapped_column(String(5), nullable=False)
    mutant: Mapped[str] = mapped_column(String(5), nullable=False)
    ddg: Mapped[float | None] = mapped_column(Float, nullable=True)       # ΔΔG (kcal/mol)
    dtm: Mapped[float | None] = mapped_column(Float, nullable=True)       # ΔTm (°C)
    dcp: Mapped[float | None] = mapped_column(Float, nullable=True)       # ΔCp
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str | None] = mapped_column(String(100), nullable=True)  # DSC, CD, fluorescence
    literature_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_db: Mapped[str] = mapped_column(String(20), default="protherm")

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="stability_records")

    __table_args__ = (
        Index("ix_stab_mut", "mutation_pos"),
    )


# =============================================================================
# 9. Substrate compounds — PubChem chemical data
# =============================================================================
class SubstrateCompound(Base):
    __tablename__ = "substrate_compounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pubchem_cid: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    iupac_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    molecular_formula: Mapped[str | None] = mapped_column(String(100), nullable=True)
    molecular_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    smiles: Mapped[str | None] = mapped_column(Text, nullable=True)
    inchi: Mapped[str | None] = mapped_column(Text, nullable=True)
    inchikey: Mapped[str | None] = mapped_column(String(30), nullable=True)
    xlogp: Mapped[float | None] = mapped_column(Float, nullable=True)
    tpsa: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotatable_bonds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hbd: Mapped[int | None] = mapped_column(Integer, nullable=True)  # H-bond donors
    hba: Mapped[int | None] = mapped_column(Integer, nullable=True)  # H-bond acceptors
    fingerprint_fp2: Mapped[bytes | None] = mapped_column(nullable=True)  # RDKit fingerprint

    source_db: Mapped[str] = mapped_column(String(20), default="pubchem")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =============================================================================
# 10. Reaction equations — Rhea enzyme-catalyzed reactions
# =============================================================================
class ReactionEquation(Base):
    __tablename__ = "reaction_equations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rhea_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    equation: Mapped[str | None] = mapped_column(Text, nullable=True)           # textual description
    reaction_side: Mapped[str | None] = mapped_column(String(20), nullable=True)  # bidirectional, L→R, R→L
    reactants: Mapped[list | None] = mapped_column(JSON, nullable=True)          # [{"cid": ..., "name": ..., "stoichiometry": ...}]
    products: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cofactors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ec_numbers: Mapped[list | None] = mapped_column(JSON, nullable=True)         # associated EC numbers
    is_balanced: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_transport: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_db: Mapped[str] = mapped_column(String(20), default="rhea")


# =============================================================================
# 11. Directed evolution entries — EnzEngDB experimental data
# =============================================================================
class DirectedEvolutionEntry(Base):
    __tablename__ = "directed_evolution_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False)
    experiment_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mutagenesis_method: Mapped[str | None] = mapped_column(String(100), nullable=True)  # error-prone PCR, DNA shuffling, etc.
    selection_pressure: Mapped[str | None] = mapped_column(String(200), nullable=True)
    library_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_variant: Mapped[str | None] = mapped_column(Text, nullable=True)
    mutations_introduced: Mapped[list | None] = mapped_column(JSON, nullable=True)
    initial_activity: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_activity: Mapped[float | None] = mapped_column(Float, nullable=True)
    fold_improvement: Mapped[float | None] = mapped_column(Float, nullable=True)
    improvement_metric: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Kcat/Km, thermostability, etc.
    organism_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    literature_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="evolution_entries")

    __table_args__ = (
        Index("ix_evo_method", "mutagenesis_method"),
    )


# =============================================================================
# 12. Database cross-references — links between EnzymeRecord and source DBs
# =============================================================================
class DatabaseCrossRef(Base):
    __tablename__ = "database_crossrefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False)
    source_db: Mapped[str] = mapped_column(String(50), nullable=False)   # uniprot, pdb, pfam, brenda, protherm, enzengdb
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. PDB ID, Pfam accession
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    enzyme: Mapped[EnzymeRecord] = relationship("EnzymeRecord", back_populates="xrefs")

    __table_args__ = (
        UniqueConstraint("enzyme_id", "source_db", name="uq_xref_enzyme_db"),
        Index("ix_xref_db", "source_db"),
        Index("ix_xref_source_id", "source_id"),
    )


# =============================================================================
# KV store — simple key-value persistence (ingestion state, metadata)
# =============================================================================
class KVStore(Base):
    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
