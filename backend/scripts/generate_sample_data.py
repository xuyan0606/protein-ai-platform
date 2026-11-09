"""Generate enriched sample data for BRENDA/ProThermDB/EnzEngDB tables.

Creates realistic kinetic parameters, stability records, and directed evolution
entries based on ACTUAL enzymes in the database (real UniProt IDs, EC numbers,
sequences). This fills the frontend Data Browser with meaningful demo data.

Usage:
    python scripts/generate_sample_data.py [--enzymes 100]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import session_scope
from app.models.domain import (
    EnzymeRecord, ECNumber, EnzymeECLink,
    KineticParameter, StabilityRecord, DirectedEvolutionEntry,
    PDBStructure, SubstrateCompound,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

random.seed(42)

# Realistic enzyme kinetics templates
KINETIC_TYPES = [
    ("KM", "uM", (0.5, 500.0)),
    ("KM", "mM", (0.01, 50.0)),
    ("KCAT", "1/s", (1.0, 10000.0)),
    ("KCAT/KM", "1/(mM*s)", (10.0, 100000.0)),
    ("KI", "uM", (0.01, 100.0)),
    ("VMAX", "umol/min/mg", (1.0, 1000.0)),
    ("IC50", "uM", (0.1, 200.0)),
    ("EC50", "uM", (0.01, 50.0)),
]

COMMON_SUBSTRATES = [
    "ATP", "NADH", "NADPH", "glucose", "pyruvate", "lactate",
    "acetyl-CoA", "malonyl-CoA", "glutamate", "aspartate",
    "AMP", "ADP", "GTP", "FAD", "FMN", "PLP",
]

ORGANISMS = [
    "Escherichia coli", "Homo sapiens", "Saccharomyces cerevisiae",
    "Bacillus subtilis", "Pseudomonas putida", "Thermus thermophilus",
    "Aspergillus niger", "Pichia pastoris", "Rattus norvegicus",
    "Arabidopsis thaliana",
]

STABILITY_METHODS = [
    "CD spectroscopy", "Differential scanning calorimetry",
    "Fluorescence", "Urea denaturation", "GdnHCl denaturation",
    "Thermal denaturation",
]

EVO_METHODS = [
    "Error-prone PCR", "DNA shuffling", "site-saturation mutagenesis",
    "CASTing", "Phage display", "FACS screening",
]

EVO_SELECTIONS = [
    "Thermostability", "Activity on non-native substrate",
    "Solvent tolerance", "pH tolerance", "Catalytic efficiency",
]

AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")


async def main(num_enzymes: int = 100):
    async with session_scope() as db:
        # Get enzymes that have EC numbers and sequences
        rows = await db.execute(
            select(EnzymeRecord.id, EnzymeRecord.uniprot_id, EnzymeRecord.seq_length,
                   EnzymeRecord.protein_name, EnzymeRecord.gene_name)
            .where(
                EnzymeRecord.sequence.isnot(None),
                EnzymeRecord.sequence != "",
                EnzymeRecord.seq_length >= 50,
            )
            .order_by(EnzymeRecord.id)
            .limit(num_enzymes * 2)  # fetch extra to have enough with EC
        )
        enzymes = rows.fetchall()
        logger.info("Fetched %d enzyme candidates", len(enzymes))

        # Get EC links for these enzymes
        enzyme_ids = [e[0] for e in enzymes]
        ec_rows = await db.execute(
            select(EnzymeECLink.enzyme_id, ECNumber.ec_number)
            .join(ECNumber, ECNumber.id == EnzymeECLink.ec_id)
            .where(EnzymeECLink.enzyme_id.in_(enzyme_ids))
        )
        ec_map = {}
        for eid, ec in ec_rows:
            ec_map.setdefault(eid, []).append(ec)

        # Get PDB structures for these enzymes
        pdb_rows = await db.execute(
            select(PDBStructure.enzyme_id)
            .where(PDBStructure.enzyme_id.in_(enzyme_ids))
            .distinct()
        )
        has_pdb = {r[0] for r in pdb_rows}

        # Filter to enzymes with EC numbers
        candidates = [(eid, uid, slen, name, gene)
                      for eid, uid, slen, name, gene in enzymes
                      if eid in ec_map]
        logger.info("Enzymes with EC: %d, with PDB: %d", len(candidates),
                     sum(1 for e in candidates if e[0] in has_pdb))

        used = candidates[:num_enzymes]
        logger.info("Generating data for %d enzymes", len(used))

    # =========================================================================
    # Generate Kinetic Parameters
    # =========================================================================
    kinetic_count = 0
    async with session_scope() as db:
        for enzyme_id, uniprot_id, slen, name, gene in used:
            ecs = ec_map.get(enzyme_id, [])
            if not ecs:
                continue

            # 3-8 kinetic parameters per enzyme
            n_params = random.randint(3, 8)
            for _ in range(n_params):
                ktype, unit, (lo, hi) = random.choice(KINETIC_TYPES)
                substrate = random.choice(COMMON_SUBSTRATES)
                value = round(random.uniform(lo, hi), 3)
                ph = round(random.choice([5.0, 6.0, 6.5, 7.0, 7.4, 7.5, 8.0, 8.5]), 1)
                temp = random.choice([25.0, 30.0, 37.0, 42.0, 55.0, 65.0])

                kp = KineticParameter(
                    enzyme_id=enzyme_id,
                    param_type=ktype,
                    value=value,
                    unit=unit,
                    substrate_name=substrate,
                    substrate_smiles="",
                    ph=ph,
                    temperature_c=temp,
                    organism_name=random.choice(ORGANISMS),
                    source_db="BRENDA",
                    literature_ref=f"PMID:{30000000 + random.randint(1, 99999)}",
                )
                db.add(kp)
                kinetic_count += 1

        await db.commit()
    logger.info("Created %d kinetic parameters", kinetic_count)

    # =========================================================================
    # Generate Stability Records
    # =========================================================================
    stab_count = 0
    async with session_scope() as db:
        for enzyme_id, uniprot_id, slen, name, gene in used:
            if enzyme_id not in has_pdb:
                continue

            # 2-5 mutations per enzyme
            n_muts = random.randint(2, 5)
            for _ in range(n_muts):
                pos = random.randint(1, slen)
                wt = random.choice(AMINO_ACIDS)
                mt = random.choice([a for a in AMINO_ACIDS if a != wt])
                ddg = round(random.uniform(-5.0, 5.0), 2)
                dtm = round(ddg * random.uniform(0.5, 2.0), 1)

                sr = StabilityRecord(
                    enzyme_id=enzyme_id,
                    mutation=f"{wt}{pos}{mt}",
                    mutation_pos=pos,
                    wild_type=wt,
                    mutant=mt,
                    ddg=ddg,
                    dtm=dtm,
                    ph=round(random.choice([5.0, 6.5, 7.0, 7.4, 8.0]), 1),
                    temperature_c=random.choice([25.0, 30.0, 37.0, 42.0]),
                    method=random.choice(STABILITY_METHODS),
                    source_db="ProThermDB",
                    literature_ref=f"PMID:{31000000 + random.randint(1, 99999)}",
                )
                db.add(sr)
                stab_count += 1

        await db.commit()
    logger.info("Created %d stability records", stab_count)

    # =========================================================================
    # Generate Directed Evolution entries
    # =========================================================================
    evo_count = 0
    async with session_scope() as db:
        for enzyme_id, uniprot_id, slen, name, gene in used[:len(used)//5]:
            # 1 experiment per 5 enzymes (fewer evo data points)
            method = random.choice(EVO_METHODS)
            rounds = random.randint(2, 8)
            fold = round(random.uniform(2.0, 500.0), 1)
            lib_size = random.choice([1e4, 1e5, 5e5, 1e6, 1e7])

            # Generate a plausible "best variant" string
            n_mutations = random.randint(1, 5)
            mutations = []
            for _ in range(n_mutations):
                pos = random.randint(1, slen)
                wt = random.choice(AMINO_ACIDS)
                mt = random.choice([a for a in AMINO_ACIDS if a != wt])
                mutations.append(f"{wt}{pos}{mt}")

            de = DirectedEvolutionEntry(
                enzyme_id=enzyme_id,
                experiment_name=f"Directed evolution of {gene or name}",
                mutagenesis_method=method,
                rounds=rounds,
                fold_improvement=fold,
                library_size=int(lib_size),
                selection_pressure=random.choice(EVO_SELECTIONS),
                improvement_metric=random.choice(["kcat/KM", "Tm", "IC50", "Vmax"]),
                initial_activity=round(random.uniform(0.01, 1.0), 4),
                final_activity=round(fold * random.uniform(0.01, 1.0), 4),
                best_variant=", ".join(mutations),
                mutations_introduced=n_mutations,
                organism_name=random.choice(ORGANISMS),
                literature_ref=f"PMID:{32000000 + random.randint(1, 99999)}",
            )
            db.add(de)
            evo_count += 1

        await db.commit()
    logger.info("Created %d directed evolution entries", evo_count)

    logger.info("Done. Total: kinetics=%d, stability=%d, evolution=%d",
                kinetic_count, stab_count, evo_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--enzymes", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(main(num_enzymes=args.enzymes))
