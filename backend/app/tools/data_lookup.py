"""Agent tools for querying the integrated enzyme databases.

Provides lookup_protein, search_substrate, get_kinetic_params, get_stability_data,
and list_ec_proteins — all backed by the domain data tables.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.registry import ToolRegistry
from app.core.database import session_scope


@asynccontextmanager
async def _use_session(external: AsyncSession | None) -> AsyncGenerator[AsyncSession, None]:
    """Yield the external test session or create one from the app engine."""
    if external is not None:
        yield external
    else:
        async with session_scope() as s:
            yield s


async def lookup_protein(
    uniprot_id: str = "",
    gene_name: str = "",
    ec_number: str = "",
    _session: AsyncSession | None = None,
) -> dict:
    """Look up a protein/enzyme in the integrated database by UniProt ID, gene name, or EC number."""
    async with _use_session(_session) as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.domain import EnzymeRecord, EnzymeECLink, ECNumber

        # By UniProt ID
        if uniprot_id:
            row = await session.execute(
                select(EnzymeRecord)
                .options(
                    selectinload(EnzymeRecord.taxonomy),
                    selectinload(EnzymeRecord.ec_numbers).selectinload(EnzymeECLink.ec_number),
                )
                .where(EnzymeRecord.uniprot_id == uniprot_id)
            )
            enzyme = row.scalar()
            if not enzyme:
                return {"found": False, "query": {"uniprot_id": uniprot_id}}
            return _enzyme_summary(enzyme)

        # By gene name
        if gene_name:
            rows = await session.execute(
                select(EnzymeRecord).where(EnzymeRecord.gene_name.ilike(f"%{gene_name}%")).limit(10)
            )
            enzymes = rows.scalars().all()
            return {
                "found": len(enzymes) > 0,
                "query": {"gene_name": gene_name},
                "results": [_enzyme_brief(e) for e in enzymes],
            }

        # By EC number
        if ec_number:
            ec_row = await session.execute(
                select(ECNumber).where(ECNumber.ec_number == ec_number)
            )
            ec = ec_row.scalar()
            if not ec:
                return {"found": False, "query": {"ec_number": ec_number}}

            link_rows = await session.execute(
                select(EnzymeECLink.enzyme_id).where(EnzymeECLink.ec_id == ec.id)
            )
            enzyme_ids = [r[0] for r in link_rows.fetchall()[:20]]
            enzymes = []
            for eid in enzyme_ids:
                e_row = await session.execute(select(EnzymeRecord).where(EnzymeRecord.id == eid))
                e = e_row.scalar()
                if e:
                    enzymes.append(_enzyme_brief(e))

            return {
                "found": True,
                "query": {"ec_number": ec_number},
                "ec_name": ec.name,
                "protein_count": len(enzymes),
                "results": enzymes,
            }

        return {"found": False, "error": "Provide uniprot_id, gene_name, or ec_number"}


async def search_substrate(
    query: str = "",
    cid: int = 0,
    _session: AsyncSession | None = None,
) -> dict:
    """Search for a substrate compound by name or PubChem CID."""
    async with _use_session(_session) as session:
        from sqlalchemy import select
        from app.models.domain import SubstrateCompound

        if cid:
            row = await session.execute(
                select(SubstrateCompound).where(SubstrateCompound.pubchem_cid == cid)
            )
            c = row.scalar()
            if not c:
                return {"found": False, "query": {"cid": cid}}
            return {"found": True, "compound": _compound_dict(c)}

        if query:
            rows = await session.execute(
                select(SubstrateCompound)
                .where(SubstrateCompound.name.ilike(f"%{query}%"))
                .limit(10)
            )
            compounds = [_compound_dict(c) for c in rows.scalars()]
            return {"found": len(compounds) > 0, "query": query, "results": compounds}

        return {"found": False, "error": "Provide query or cid"}


async def get_kinetic_params(
    uniprot_id: str = "",
    param_type: str = "",
    _session: AsyncSession | None = None,
) -> dict:
    """Get kinetic parameters (Kcat, Km, Ki, Kcat/Km) for a protein from BRENDA/OED."""
    async with _use_session(_session) as session:
        from sqlalchemy import select
        from app.models.domain import EnzymeRecord, KineticParameter

        if not uniprot_id:
            return {"found": False, "error": "Provide uniprot_id"}

        enz_row = await session.execute(
            select(EnzymeRecord.id).where(EnzymeRecord.uniprot_id == uniprot_id)
        )
        enzyme_id = enz_row.scalar()
        if not enzyme_id:
            return {"found": False, "uniprot_id": uniprot_id}

        query = select(KineticParameter).where(KineticParameter.enzyme_id == enzyme_id)
        if param_type:
            query = query.where(KineticParameter.param_type == param_type)
        query = query.limit(50)

        rows = await session.execute(query)
        params = [
            {
                "type": kp.param_type,
                "substrate": kp.substrate_name,
                "value": kp.value,
                "unit": kp.unit,
                "ph": kp.ph,
                "temp_c": kp.temperature_c,
                "mutant": kp.mutant,
                "source": kp.source_db,
            }
            for kp in rows.scalars()
        ]

        # Aggregate summary
        summary = {}
        for p in params:
            pt = p["type"]
            if pt not in summary:
                summary[pt] = {"count": 0, "min": None, "max": None, "values": []}
            summary[pt]["count"] += 1
            if p["value"] is not None:
                summary[pt]["values"].append(p["value"])

        for pt in summary:
            vals = summary[pt]["values"]
            if vals:
                summary[pt]["min"] = min(vals)
                summary[pt]["max"] = max(vals)
                summary[pt]["median"] = sorted(vals)[len(vals) // 2]
            del summary[pt]["values"]

        return {
            "found": True,
            "uniprot_id": uniprot_id,
            "total_records": len(params),
            "parameters": params,
            "summary": summary,
        }


async def get_stability_data(
    uniprot_id: str = "",
    _session: AsyncSession | None = None,
) -> dict:
    """Get mutation stability data (ΔΔG, ΔTm) for a protein from ProThermDB."""
    async with _use_session(_session) as session:
        from sqlalchemy import select
        from app.models.domain import EnzymeRecord, StabilityRecord

        if not uniprot_id:
            return {"found": False, "error": "Provide uniprot_id"}

        enz_row = await session.execute(
            select(EnzymeRecord.id).where(EnzymeRecord.uniprot_id == uniprot_id)
        )
        enzyme_id = enz_row.scalar()
        if not enzyme_id:
            return {"found": False, "uniprot_id": uniprot_id}

        rows = await session.execute(
            select(StabilityRecord)
            .where(StabilityRecord.enzyme_id == enzyme_id)
            .order_by(StabilityRecord.mutation_pos)
            .limit(100)
        )
        records = [
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
            }
            for s in rows.scalars()
        ]

        # Count stabilizing vs destabilizing
        stabilizing = sum(1 for r in records if r["ddg"] and r["ddg"] > 0)
        destabilizing = sum(1 for r in records if r["ddg"] and r["ddg"] < 0)

        return {
            "found": True,
            "uniprot_id": uniprot_id,
            "total_records": len(records),
            "stabilizing": stabilizing,
            "destabilizing": destabilizing,
            "records": records,
        }


async def list_ec_proteins(
    ec_number: str = "",
    top_level: str = "",
    _session: AsyncSession | None = None,
) -> dict:
    """List proteins/enzymes under an EC class or top-level EC category."""
    async with _use_session(_session) as session:
        from sqlalchemy import select, func
        from app.models.domain import ECNumber, EnzymeECLink, EnzymeRecord

        if ec_number:
            ec_row = await session.execute(
                select(ECNumber).where(ECNumber.ec_number == ec_number)
            )
            ec = ec_row.scalar()
            if not ec:
                return {"found": False, "query": {"ec_number": ec_number}}

            link_rows = await session.execute(
                select(EnzymeECLink.enzyme_id, EnzymeRecord.uniprot_id, EnzymeRecord.protein_name)
                .join(EnzymeRecord, EnzymeECLink.enzyme_id == EnzymeRecord.id)
                .where(EnzymeECLink.ec_id == ec.id)
                .limit(50)
            )
            proteins = [
                {"uniprot_id": r[1], "name": r[2]}
                for r in link_rows.fetchall()
            ]
            return {"found": True, "ec_number": ec_number, "ec_name": ec.name, "proteins": proteins}

        if top_level:
            # e.g. "1" for oxidoreductases
            ec_rows = await session.execute(
                select(ECNumber.ec_number, ECNumber.name)
                .where(ECNumber.level1 == top_level)
                .limit(100)
            )
            ecs = [{"ec": r[0], "name": r[1]} for r in ec_rows.fetchall()]
            return {"found": True, "top_level": top_level, "ec_classes": ecs}

        return {"found": False, "error": "Provide ec_number or top_level"}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _enzyme_summary(enzyme) -> dict:
    return {
        "found": True,
        "uniprot_id": enzyme.uniprot_id,
        "entry_name": enzyme.entry_name,
        "protein_name": enzyme.protein_name,
        "gene_name": enzyme.gene_name,
        "sequence": enzyme.sequence,
        "seq_length": enzyme.seq_length,
        "function": enzyme.function_annotation,
        "catalytic_activity": enzyme.catalytic_activity,
        "organism": enzyme.taxonomy.scientific_name if enzyme.taxonomy else None,
        "ec_numbers": [
            {"ec": link.ec_number.ec_number, "name": link.ec_number.name, "primary": link.is_primary}
            for link in enzyme.ec_numbers
        ],
    }


def _enzyme_brief(enzyme) -> dict:
    return {
        "uniprot_id": enzyme.uniprot_id,
        "name": enzyme.protein_name,
        "gene": enzyme.gene_name,
        "length": enzyme.seq_length,
    }


def _compound_dict(c) -> dict:
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


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
ToolRegistry.register(
    name="lookup_protein",
    description="查询蛋白质/酶的综合信息：序列、功能、EC号、结构、动力学参数等。数据来自UniProt、PDB、BRENDA、ProThermDB等10个数据库",
    parameters={
        "type": "object",
        "properties": {
            "uniprot_id": {"type": "string", "description": "UniProt accession (e.g. P00519)"},
            "gene_name": {"type": "string", "description": "Gene name (e.g. ABL1)"},
            "ec_number": {"type": "string", "description": "EC number (e.g. 1.1.1.1)"},
        },
    },
    handler=lookup_protein,
    category="data",
    timeout_seconds=30,
)

ToolRegistry.register(
    name="search_substrate",
    description="查询底物/辅因子化合物的化学信息：SMILES、分子式、InChI、logP等。数据来自PubChem",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "化合物名称或CID"},
            "cid": {"type": "integer", "description": "PubChem Compound ID"},
        },
    },
    handler=search_substrate,
    category="data",
    timeout_seconds=30,
)

ToolRegistry.register(
    name="get_kinetic_params",
    description="获取酶的动力学参数：Kcat、Km、Ki、Kcat/Km等。数据来自BRENDA和OED数据库",
    parameters={
        "type": "object",
        "properties": {
            "uniprot_id": {"type": "string", "description": "UniProt accession"},
            "param_type": {"type": "string", "description": "参数类型过滤：Kcat, Km, Ki, Kcat/Km"},
        },
        "required": ["uniprot_id"],
    },
    handler=get_kinetic_params,
    category="data",
    timeout_seconds=30,
)

ToolRegistry.register(
    name="get_stability_data",
    description="获取蛋白质突变稳定性的热力学数据：ΔΔG、ΔTm。数据来自ProThermDB",
    parameters={
        "type": "object",
        "properties": {
            "uniprot_id": {"type": "string", "description": "UniProt accession"},
        },
        "required": ["uniprot_id"],
    },
    handler=get_stability_data,
    category="data",
    timeout_seconds=30,
)

ToolRegistry.register(
    name="list_ec_proteins",
    description="列出某个EC分类下的所有蛋白质/酶",
    parameters={
        "type": "object",
        "properties": {
            "ec_number": {"type": "string", "description": "完整EC编号 (e.g. 1.1.1.1)"},
            "top_level": {"type": "string", "description": "EC大类 (1-7)"},
        },
    },
    handler=list_ec_proteins,
    category="data",
    timeout_seconds=30,
)
