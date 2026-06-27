"""Enzyme Knowledge Graph — virtual graph layer over PostgreSQL tables.

Provides graph-traversal-style queries by joining across the 15 domain tables.
No separate graph database needed — SQLAlchemy relationships simulate 1-2 hop traversal.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    EnzymeRecord,
    ECNumber,
    EnzymeECLink,
    Taxonomy,
    PDBStructure,
    AlphaFoldStructure,
    PfamDomain,
    DomainArchitecture,
    KineticParameter,
    StabilityRecord,
    ReactionEquation,
    DirectedEvolutionEntry,
    DatabaseCrossRef,
)

logger = logging.getLogger(__name__)


class EnzymeKnowledgeGraph:
    """Virtual knowledge graph over enzyme domain tables."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    def query_enzyme_context(self, uniprot_id: str) -> dict[str, Any]:
        """Get full enzyme context (1-2 hop graph traversal).

        Returns a structured dict with all related data:
        - enzyme basic info
        - EC classification
        - organism taxonomy
        - structures (PDB + AlphaFold)
        - kinetics parameters
        - stability records
        - Pfam domains
        - directed evolution experiments
        - database cross-references
        - literature references (from kinetics/stability/evolution)
        """
        enzyme = self.db.execute(
            select(EnzymeRecord)
            .options(
                selectinload(EnzymeRecord.ec_numbers).selectinload(
                    EnzymeECLink.ec_number
                ),
                selectinload(EnzymeRecord.taxonomy),
                selectinload(EnzymeRecord.pdb_structures),
                selectinload(EnzymeRecord.alphafold_structures),
                selectinload(EnzymeRecord.kinetic_params),
                selectinload(EnzymeRecord.stability_records),
                selectinload(EnzymeRecord.domains).selectinload(
                    DomainArchitecture.domain
                ),
                selectinload(EnzymeRecord.evolution_entries),
                selectinload(EnzymeRecord.xrefs),
            )
            .where(EnzymeRecord.uniprot_id == uniprot_id)
        ).scalar_one_or_none()

        if not enzyme:
            return {}

        return self._build_context(enzyme)

    def query_by_name(self, protein_name: str) -> EnzymeRecord | None:
        """Find enzyme by protein name or gene name (fuzzy match)."""
        return self.db.execute(
            select(EnzymeRecord)
            .where(
                or_(
                    EnzymeRecord.protein_name.ilike(f"%{protein_name}%"),
                    EnzymeRecord.gene_name.ilike(f"%{protein_name}%"),
                    EnzymeRecord.uniprot_id == protein_name,
                )
            )
            .limit(1)
        ).scalar_one_or_none()

    def query_by_ec(self, ec_number: str) -> list[dict[str, Any]]:
        """Query all enzymes under an EC number."""
        links = (
            self.db.execute(
                select(EnzymeECLink)
                .options(
                    selectinload(EnzymeECLink.enzyme),
                    selectinload(EnzymeECLink.ec_number),
                )
                .join(ECNumber)
                .where(ECNumber.ec_number == ec_number)
            )
            .scalars()
            .all()
        )

        return [
            self._build_context(link.enzyme) for link in links if link.enzyme
        ]

    def query_enzymes_by_reaction(self, rhea_id: int) -> list[dict[str, Any]]:
        """Find enzymes that catalyze a specific reaction.

        Currently a stub — ReactionEquation stores ec_numbers as JSON,
        so the link back to EnzymeRecord requires EC-number matching.
        """
        reactions = (
            self.db.execute(
                select(ReactionEquation).where(
                    ReactionEquation.rhea_id == rhea_id
                )
            )
            .scalars()
            .all()
        )
        # TODO: link reactions to enzymes via EC numbers stored in
        #       ReactionEquation.ec_numbers (JSON list)
        return []

    # ------------------------------------------------------------------
    # Natural-language serialisation
    # ------------------------------------------------------------------

    def to_natural_language(self, context: dict[str, Any]) -> str:
        """Convert knowledge graph context to LLM-readable natural language."""
        if not context:
            return ""

        parts: list[str] = []

        # --- Basic info ---
        e = context.get("enzyme", {})
        if e:
            parts.append(
                f"## Enzyme: {e.get('protein_name', e.get('uniprot_id', 'Unknown'))}"
            )
            parts.append(f"- UniProt ID: {e.get('uniprot_id', 'N/A')}")
            if e.get("gene_name"):
                parts.append(f"- Gene: {e['gene_name']}")
            parts.append(f"- Sequence length: {e.get('seq_length', 'N/A')} aa")
            if e.get("function_annotation"):
                parts.append(f"- Function: {e['function_annotation']}")
            if e.get("catalytic_activity"):
                parts.append(
                    f"- Catalytic activity: {e['catalytic_activity']}"
                )

        # --- Taxonomy ---
        tax = context.get("taxonomy")
        if tax:
            parts.append("\n### Organism")
            sci = tax.get("scientific_name", "N/A")
            common = tax.get("common_name")
            parts.append(
                f"- {sci} ({common})" if common else f"- {sci}"
            )
            if tax.get("lineage"):
                parts.append(f"- Lineage: {tax['lineage']}")

        # --- EC numbers ---
        ecs = context.get("ec_numbers", [])
        if ecs:
            parts.append("\n### EC Classification")
            for ec in ecs:
                label = ec["ec_number"]
                if ec.get("name"):
                    label += f": {ec['name']}"
                parts.append(f"- {label}")

        # --- Structures ---
        pdbs = context.get("pdb_structures", [])
        afs = context.get("alphafold_structures", [])
        if pdbs or afs:
            parts.append("\n### Structures")
            if pdbs:
                pdb_ids = ", ".join(p["pdb_id"] for p in pdbs[:5])
                suffix = (
                    f" (+{len(pdbs) - 5} more)" if len(pdbs) > 5 else ""
                )
                parts.append(f"- PDB: {pdb_ids}{suffix}")
            if afs:
                plddts = [
                    a["plddt_mean"] for a in afs if a.get("plddt_mean")
                ]
                if plddts:
                    parts.append(
                        f"- AlphaFold: mean pLDDT {max(plddts):.1f}"
                    )

        # --- Kinetics ---
        kinetics = context.get("kinetics", [])
        if kinetics:
            parts.append(f"\n### Kinetics ({len(kinetics)} records)")
            for k in kinetics[:5]:
                line = f"- {k['param_type']}: {k['value']} {k.get('unit', '')}"
                if k.get("substrate"):
                    line += f" (substrate: {k['substrate']})"
                if k.get("literature_ref"):
                    line += f" [ref: {k['literature_ref']}]"
                parts.append(line)
            if len(kinetics) > 5:
                parts.append(f"  ... and {len(kinetics) - 5} more records")

        # --- Stability ---
        stability = context.get("stability_records", [])
        if stability:
            parts.append(
                f"\n### Stability ({len(stability)} mutations)"
            )
            stabilizing = sum(
                1
                for s in stability
                if s.get("ddg") is not None and s["ddg"] < 0
            )
            destabilizing = sum(
                1
                for s in stability
                if s.get("ddg") is not None and s["ddg"] > 0
            )
            parts.append(
                f"- Stabilizing: {stabilizing}, "
                f"Destabilizing: {destabilizing}"
            )
            for s in stability[:3]:
                ddg_str = (
                    f"ΔΔG={s['ddg']:.2f}" if s.get("ddg") is not None else ""
                )
                dtm_str = (
                    f"ΔTm={s['dtm']:.1f}°C"
                    if s.get("dtm") is not None
                    else ""
                )
                parts.append(f"- {s['mutation']}: {ddg_str} {dtm_str}")

        # --- Domains ---
        domains = context.get("domains", [])
        if domains:
            parts.append("\n### Pfam Domains")
            for d in domains:
                label = f"- {d['pfam_id']}: {d.get('name', '')}"
                if d.get("start_pos") is not None:
                    label += f" (pos {d['start_pos']}-{d['end_pos']})"
                parts.append(label)

        # --- Evolution ---
        evolution = context.get("evolution", [])
        if evolution:
            parts.append("\n### Directed Evolution")
            for ev in evolution[:3]:
                line = f"- {ev.get('method', 'N/A')}"
                if ev.get("fold_improvement"):
                    line += f": {ev['fold_improvement']}x improvement"
                if ev.get("literature_ref"):
                    line += f" [ref: {ev['literature_ref']}]"
                parts.append(line)

        # --- Literature refs ---
        lit_refs = context.get("literature_refs", [])
        if lit_refs:
            parts.append(
                f"\n### Literature References ({len(lit_refs)} unique)"
            )
            for ref in lit_refs[:10]:
                parts.append(f"- {ref}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_context(self, enzyme: EnzymeRecord) -> dict[str, Any]:
        """Build structured context dict from an EnzymeRecord with loaded
        relationships."""
        lit_refs: set[str] = set()

        # --- Basic enzyme info ---
        enzyme_info: dict[str, Any] = {
            "uniprot_id": enzyme.uniprot_id,
            "entry_name": enzyme.entry_name,
            "protein_name": enzyme.protein_name,
            "gene_name": enzyme.gene_name,
            "seq_length": enzyme.seq_length,
            "function_annotation": enzyme.function_annotation,
            "catalytic_activity": enzyme.catalytic_activity,
            "cofactors": enzyme.cofactors,
            "is_reviewed": enzyme.is_reviewed,
        }

        # --- Taxonomy ---
        taxonomy: dict[str, Any] | None = None
        if enzyme.taxonomy:
            taxonomy = {
                "scientific_name": enzyme.taxonomy.scientific_name,
                "common_name": enzyme.taxonomy.common_name,
                "lineage": enzyme.taxonomy.lineage,
                "ncbi_taxid": enzyme.taxonomy.ncbi_taxid,
            }

        # --- EC numbers ---
        ec_numbers: list[dict[str, Any]] = []
        for link in enzyme.ec_numbers:
            if link.ec_number:
                ec_numbers.append(
                    {
                        "ec_number": link.ec_number.ec_number,
                        "name": link.ec_number.name,
                        "category": link.ec_number.category,
                        "is_primary": link.is_primary,
                    }
                )

        # --- PDB structures ---
        pdb_structures: list[dict[str, Any]] = []
        for pdb in enzyme.pdb_structures:
            pdb_structures.append(
                {
                    "pdb_id": pdb.pdb_id,
                    "method": pdb.method,
                    "resolution": pdb.resolution,
                    "chain_ids": pdb.chain_ids,
                }
            )

        # --- AlphaFold structures ---
        alphafold_structures: list[dict[str, Any]] = []
        for af in enzyme.alphafold_structures:
            alphafold_structures.append(
                {
                    "model_url": af.model_url,
                    "plddt_mean": af.plddt_mean,
                }
            )

        # --- Kinetics ---
        kinetics: list[dict[str, Any]] = []
        for kp in enzyme.kinetic_params:
            kinetics.append(
                {
                    "param_type": kp.param_type,
                    "substrate": kp.substrate_name,
                    "value": kp.value,
                    "unit": kp.unit,
                    "ph": kp.ph,
                    "temperature_c": kp.temperature_c,
                    "mutant": kp.mutant,
                    "source_db": kp.source_db,
                    "literature_ref": kp.literature_ref,
                }
            )
            if kp.literature_ref:
                lit_refs.add(kp.literature_ref)

        # --- Stability ---
        stability_records: list[dict[str, Any]] = []
        for sr in enzyme.stability_records:
            stability_records.append(
                {
                    "mutation": sr.mutation,
                    "position": sr.mutation_pos,
                    "wt": sr.wild_type,
                    "mt": sr.mutant,
                    "ddg": sr.ddg,
                    "dtm": sr.dtm,
                    "ph": sr.ph,
                    "temperature_c": sr.temperature_c,
                    "method": sr.method,
                    "literature_ref": sr.literature_ref,
                }
            )
            if sr.literature_ref:
                lit_refs.add(sr.literature_ref)

        # --- Domains ---
        domains: list[dict[str, Any]] = []
        for da in enzyme.domains:
            if da.domain:
                domains.append(
                    {
                        "pfam_id": da.domain.pfam_id,
                        "name": da.domain.name,
                        "clan": da.domain.clan,
                        "start_pos": da.start_pos,
                        "end_pos": da.end_pos,
                    }
                )

        # --- Directed evolution ---
        evolution: list[dict[str, Any]] = []
        for ev in enzyme.evolution_entries:
            evolution.append(
                {
                    "method": ev.mutagenesis_method,
                    "rounds": ev.rounds,
                    "fold_improvement": ev.fold_improvement,
                    "best_variant": ev.best_variant,
                    "literature_ref": ev.literature_ref,
                }
            )
            if ev.literature_ref:
                lit_refs.add(ev.literature_ref)

        # --- Cross-references ---
        xrefs: list[dict[str, Any]] = []
        for xref in enzyme.xrefs:
            xrefs.append(
                {
                    "source_db": xref.source_db,
                    "source_id": xref.source_id,
                    "source_url": xref.source_url,
                }
            )

        return {
            "enzyme": enzyme_info,
            "taxonomy": taxonomy,
            "ec_numbers": ec_numbers,
            "pdb_structures": pdb_structures,
            "alphafold_structures": alphafold_structures,
            "kinetics": kinetics,
            "stability_records": stability_records,
            "domains": domains,
            "evolution": evolution,
            "xrefs": xrefs,
            "literature_refs": sorted(lit_refs),
        }
