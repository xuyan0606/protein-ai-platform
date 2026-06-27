"""Data query API — unified access to 10 integrated databases.

Endpoints:
  GET  /search              cross-database full-text search
  GET  /protein/{id}        aggregated protein detail
  GET  /protein/{id}/kinetics
  GET  /protein/{id}/stability
  GET  /protein/{id}/structures
  GET  /protein/{id}/evolution
  GET  /ec/{ec_number}      EC number lookup
  GET  /substrate/{q}       compound search
  GET  /reaction/{rhea_id}  reaction lookup
  GET  /stats               database statistics
  POST /ingest/{source}     trigger data ingestion
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.domain import (
    EnzymeRecord,
    ECNumber,
    EnzymeECLink,
    PDBStructure,
    AlphaFoldStructure,
    KineticParameter,
    StabilityRecord,
    SubstrateCompound,
    ReactionEquation,
    DirectedEvolutionEntry,
    DatabaseCrossRef,
    Taxonomy,
    PfamDomain,
    DomainArchitecture,
    KVStore,
)

router = APIRouter(tags=["Data"])


# =============================================================================
# Search
# =============================================================================
@router.get("/search")
async def search_data(
    q: str = Query(..., min_length=2, description="Search query"),
    category: str | None = Query(None, description="Filter: protein, substrate, reaction, ec"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Cross-database search: protein name, EC number, substrate, reaction."""
    results: dict[str, list[dict]] = {}

    if not category or category == "protein":
        query = (
            select(EnzymeRecord.uniprot_id, EnzymeRecord.protein_name, EnzymeRecord.gene_name, EnzymeRecord.description)
            .where(
                (EnzymeRecord.protein_name.ilike(f"%{q}%"))
                | (EnzymeRecord.gene_name.ilike(f"%{q}%"))
                | (EnzymeRecord.uniprot_id.ilike(f"%{q}%"))
                | (EnzymeRecord.description.ilike(f"%{q}%"))
            )
            .limit(limit)
        )
        rows = await session.execute(query)
        results["proteins"] = [
            {"uniprot_id": r[0], "name": r[1], "gene": r[2], "description": (r[3] or "")[:200]}
            for r in rows.fetchall()
        ]

    if not category or category == "substrate":
        query = select(SubstrateCompound).where(
            SubstrateCompound.name.ilike(f"%{q}%")
            | (SubstrateCompound.iupac_name.ilike(f"%{q}%"))
        ).limit(limit)
        rows = await session.execute(query)
        results["substrates"] = [
            {"cid": s.pubchem_cid, "name": s.name, "formula": s.molecular_formula, "smiles": s.smiles}
            for s in rows.scalars()
        ]

    if not category or category == "reaction":
        query = select(ReactionEquation.rhea_id, ReactionEquation.equation).where(
            ReactionEquation.equation.ilike(f"%{q}%")
        ).limit(limit)
        rows = await session.execute(query)
        results["reactions"] = [{"rhea_id": r[0], "equation": r[1]} for r in rows.fetchall()]

    if not category or category == "ec":
        query = select(ECNumber.ec_number, ECNumber.name).where(
            ECNumber.ec_number.like(f"%{q}%") | (ECNumber.name.ilike(f"%{q}%"))
        ).limit(limit)
        rows = await session.execute(query)
        results["ec_numbers"] = [{"ec": r[0], "name": r[1]} for r in rows.fetchall()]

    return {"query": q, "results": results}


# =============================================================================
# Protein detail (aggregated view)
# =============================================================================
@router.get("/protein/{uniprot_id}")
async def get_protein(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Aggregated protein detail: sequence, function, taxonomy, ECs, structures, etc."""
    row = await session.execute(
        select(EnzymeRecord)
        .options(
            selectinload(EnzymeRecord.taxonomy),
            selectinload(EnzymeRecord.ec_numbers).selectinload(EnzymeECLink.ec_number),
            selectinload(EnzymeRecord.pdb_structures),
            selectinload(EnzymeRecord.alphafold_structures),
        )
        .where(EnzymeRecord.uniprot_id == uniprot_id)
    )
    enzyme = row.scalar()
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    # Count related records
    kp_count = await session.scalar(
        select(func.count(KineticParameter.id)).where(KineticParameter.enzyme_id == enzyme.id)
    )
    stab_count = await session.scalar(
        select(func.count(StabilityRecord.id)).where(StabilityRecord.enzyme_id == enzyme.id)
    )
    evo_count = await session.scalar(
        select(func.count(DirectedEvolutionEntry.id)).where(DirectedEvolutionEntry.enzyme_id == enzyme.id)
    )

    return {
        "uniprot_id": enzyme.uniprot_id,
        "entry_name": enzyme.entry_name,
        "protein_name": enzyme.protein_name,
        "gene_name": enzyme.gene_name,
        "sequence": enzyme.sequence,
        "seq_length": enzyme.seq_length,
        "function": enzyme.function_annotation,
        "catalytic_activity": enzyme.catalytic_activity,
        "cofactors": enzyme.cofactors,
        "organism": _taxonomy_dict(enzyme.taxonomy),
        "ec_numbers": [
            {"ec": link.ec_number.ec_number, "name": link.ec_number.name, "primary": link.is_primary}
            for link in enzyme.ec_numbers
        ],
        "pdb_structures": [
            {"pdb_id": s.pdb_id, "method": s.method, "resolution": s.resolution}
            for s in enzyme.pdb_structures
        ],
        "alphafold": {
            "plddt_mean": enzyme.alphafold_structures[0].plddt_mean,
            "model_url": enzyme.alphafold_structures[0].model_url,
        } if enzyme.alphafold_structures else None,
        "counts": {
            "kinetic_params": kp_count or 0,
            "stability_records": stab_count or 0,
            "evolution_entries": evo_count or 0,
            "pdb_structures": len(enzyme.pdb_structures),
        },
    }


# =============================================================================
# Kinetics sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/kinetics")
async def get_protein_kinetics(
    uniprot_id: str,
    param_type: str | None = Query(None, description="Filter: Kcat, Km, Ki, Kcat/Km"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Kinetic parameters (BRENDA/OED) for a protein."""
    enzyme = await _find_enzyme(session, uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    query = select(KineticParameter).where(KineticParameter.enzyme_id == enzyme.id)
    if param_type:
        query = query.where(KineticParameter.param_type == param_type)
    query = query.order_by(KineticParameter.param_type).limit(limit)

    rows = await session.execute(query)
    return {
        "uniprot_id": uniprot_id,
        "parameters": [
            {
                "type": kp.param_type,
                "substrate": kp.substrate_name,
                "value": kp.value,
                "unit": kp.unit,
                "ph": kp.ph,
                "temp_c": kp.temperature_c,
                "mutant": kp.mutant,
                "organism": kp.organism_name,
                "source": kp.source_db,
                "reference": kp.literature_ref,
            }
            for kp in rows.scalars()
        ],
    }


# =============================================================================
# Stability sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/stability")
async def get_protein_stability(
    uniprot_id: str,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Stability records (ProThermDB) for a protein."""
    enzyme = await _find_enzyme(session, uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    rows = await session.execute(
        select(StabilityRecord)
        .where(StabilityRecord.enzyme_id == enzyme.id)
        .order_by(StabilityRecord.mutation_pos)
        .limit(limit)
    )
    return {
        "uniprot_id": uniprot_id,
        "records": [
            {
                "mutation": s.mutation,
                "position": s.mutation_pos,
                "wt": s.wild_type,
                "mt": s.mutant,
                "ddg": s.ddg,
                "dtm": s.dtm,
                "ph": s.ph,
                "temp_c": s.temperature_c,
                "method": s.method,
                "reference": s.literature_ref,
            }
            for s in rows.scalars()
        ],
    }


# =============================================================================
# Structures sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/structures")
async def get_protein_structures(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """PDB and AlphaFold structures for a protein."""
    enzyme = await _find_enzyme(session, uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    pdb_rows = await session.execute(
        select(PDBStructure).where(PDBStructure.enzyme_id == enzyme.id)
    )
    af_rows = await session.execute(
        select(AlphaFoldStructure).where(AlphaFoldStructure.enzyme_id == enzyme.id)
    )

    return {
        "uniprot_id": uniprot_id,
        "pdb": [
            {"pdb_id": s.pdb_id, "title": s.title, "method": s.method, "resolution": s.resolution,
             "chains": s.chain_ids, "deposited": s.deposited_at.isoformat() if s.deposited_at else None}
            for s in pdb_rows.scalars()
        ],
        "alphafold": [
            {"plddt_mean": s.plddt_mean, "model_url": s.model_url}
            for s in af_rows.scalars()
        ],
    }


# =============================================================================
# Evolution sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/evolution")
async def get_protein_evolution(
    uniprot_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Directed evolution entries (EnzEngDB) for a protein."""
    enzyme = await _find_enzyme(session, uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    rows = await session.execute(
        select(DirectedEvolutionEntry)
        .where(DirectedEvolutionEntry.enzyme_id == enzyme.id)
        .order_by(DirectedEvolutionEntry.fold_improvement.desc().nullslast())
        .limit(limit)
    )
    return {
        "uniprot_id": uniprot_id,
        "experiments": [
            {
                "name": e.experiment_name,
                "method": e.mutagenesis_method,
                "selection": e.selection_pressure,
                "library_size": e.library_size,
                "rounds": e.rounds,
                "best_variant": e.best_variant,
                "mutations": e.mutations_introduced,
                "fold_improvement": e.fold_improvement,
                "metric": e.improvement_metric,
                "reference": e.literature_ref,
            }
            for e in rows.scalars()
        ],
    }


# =============================================================================
# EC number lookup
# =============================================================================
@router.get("/ec/{ec_number:path}")
async def get_ec_number(
    ec_number: str,
    session: AsyncSession = Depends(get_session),
):
    """Look up an EC number and its linked proteins."""
    row = await session.execute(
        select(ECNumber).where(ECNumber.ec_number == ec_number)
    )
    ec = row.scalar()
    if not ec:
        raise HTTPException(404, f"EC {ec_number} not found")

    # Get linked proteins
    link_rows = await session.execute(
        select(EnzymeECLink, EnzymeRecord)
        .join(EnzymeRecord, EnzymeECLink.enzyme_id == EnzymeRecord.id)
        .where(EnzymeECLink.ec_id == ec.id)
        .limit(50)
    )
    proteins = [
        {"uniprot_id": r[1].uniprot_id, "name": r[1].protein_name, "primary": r[0].is_primary}
        for r in link_rows.fetchall()
    ]

    return {
        "ec_number": ec.ec_number,
        "name": ec.name,
        "category": ec.category,
        "proteins": proteins,
        "protein_count": len(proteins),
    }


# =============================================================================
# Substrate lookup
# =============================================================================
@router.get("/substrate/{query}")
async def get_substrate(
    query: str,
    session: AsyncSession = Depends(get_session),
):
    """Search for a substrate compound by name or PubChem CID."""
    # Try exact CID match first
    try:
        cid = int(query)
        row = await session.execute(select(SubstrateCompound).where(SubstrateCompound.pubchem_cid == cid))
        compound = row.scalar()
        if compound:
            return _compound_dict(compound)
    except ValueError:
        pass

    # Fuzzy name search
    rows = await session.execute(
        select(SubstrateCompound)
        .where(
            SubstrateCompound.name.ilike(f"%{query}%")
            | SubstrateCompound.inchikey.ilike(f"%{query}%")
        )
        .limit(10)
    )
    compounds = [_compound_dict(c) for c in rows.scalars()]
    return {"query": query, "results": compounds}


# =============================================================================
# Reaction lookup
# =============================================================================
@router.get("/reaction/{rhea_id}")
async def get_reaction(
    rhea_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Look up a Rhea reaction by ID."""
    row = await session.execute(
        select(ReactionEquation).where(ReactionEquation.rhea_id == rhea_id)
    )
    rxn = row.scalar()
    if not rxn:
        raise HTTPException(404, f"Rhea reaction {rhea_id} not found")

    return {
        "rhea_id": rxn.rhea_id,
        "equation": rxn.equation,
        "reaction_side": rxn.reaction_side,
        "reactants": rxn.reactants,
        "products": rxn.products,
        "cofactors": rxn.cofactors,
        "ec_numbers": rxn.ec_numbers,
        "is_balanced": rxn.is_balanced,
        "is_transport": rxn.is_transport,
    }


# =============================================================================
# Statistics
# =============================================================================
@router.get("/stats")
async def get_data_stats(
    session: AsyncSession = Depends(get_session),
):
    """Summary statistics for all integrated databases."""
    tables = [
        ("enzyme_records", EnzymeRecord),
        ("taxonomy", Taxonomy),
        ("ec_numbers", ECNumber),
        ("pdb_structures", PDBStructure),
        ("alphafold_structures", AlphaFoldStructure),
        ("kinetic_parameters", KineticParameter),
        ("stability_records", StabilityRecord),
        ("substrate_compounds", SubstrateCompound),
        ("reaction_equations", ReactionEquation),
        ("directed_evolution_entries", DirectedEvolutionEntry),
        ("pfam_domains", PfamDomain),
        ("domain_architecture", DomainArchitecture),
        ("database_crossrefs", DatabaseCrossRef),
    ]

    stats = {}
    for name, model in tables:
        count = await session.scalar(select(func.count()).select_from(model))
        stats[name] = count

    # Ingestion status
    rows = await session.execute(
        select(KVStore.key, KVStore.value).where(KVStore.key.like("ingest:%"))
    )
    ingest_state = {r[0]: r[1][:12] for r in rows.fetchall()}

    return {"counts": stats, "ingestion_hashes": ingest_state}


# =============================================================================
# Vector search
# =============================================================================
@router.get("/vector/search")
async def vector_search(
    q: str = Query(..., min_length=10, description="Protein sequence to search similar enzymes"),
    top_k: int = Query(20, ge=1, le=100),
):
    """Semantic enzyme search via ESM-2 embeddings + Zvec vector store."""
    try:
        from app.ml.vector_search import EnzymeVectorSearch
        vs = EnzymeVectorSearch()
        try:
            results = vs.search_by_sequence(q, top_k=top_k)
            return {"query_length": len(q), "results": results, "indexed_enzymes": vs.count()}
        finally:
            vs.close()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Vector search failed: {e}")


# =============================================================================
# Trigger ingestion
# =============================================================================
@router.post("/ingest/{source}")
async def trigger_ingestion(
    source: str,
    force: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Trigger data ingestion for a specific source (uniprot, pdb, pubchem, etc.)."""
    from app.data.ingestor_registry import ingest_source

    try:
        report = await ingest_source(source, session, force=force)
        return report.to_dict()
    except KeyError:
        raise HTTPException(404, f"Unknown data source: {source}")


# =============================================================================
# Helpers
# =============================================================================

async def _find_enzyme(session: AsyncSession, uniprot_id: str) -> EnzymeRecord | None:
    row = await session.execute(
        select(EnzymeRecord.id, EnzymeRecord.uniprot_id).where(EnzymeRecord.uniprot_id == uniprot_id)
    )
    r = row.first()
    return r if r else None


def _taxonomy_dict(tax: Taxonomy | None) -> dict | None:
    if tax is None:
        return None
    return {
        "taxid": tax.ncbi_taxid,
        "name": tax.scientific_name,
        "common": tax.common_name,
        "lineage": tax.lineage,
    }


def _compound_dict(c: SubstrateCompound) -> dict:
    return {
        "cid": c.pubchem_cid,
        "name": c.name,
        "iupac": c.iupac_name,
        "formula": c.molecular_formula,
        "weight": c.molecular_weight,
        "smiles": c.smiles,
        "inchi": c.inchi,
        "inchikey": c.inchikey,
        "xlogp": c.xlogp,
        "tpsa": c.tpsa,
    }
