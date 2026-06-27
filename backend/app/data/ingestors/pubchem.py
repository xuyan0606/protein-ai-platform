"""PubChem compound ingestor.

Searches PubChem PUG-REST API for enzyme substrates and cofactors,
retrieves molecular properties (SMILES, InChI, molecular weight, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, insert

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import SubstrateCompound

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
# Common enzyme substrate/cofactor names to seed the database
SEED_COMPOUNDS = [
    ("ATP", "5957"), ("ADP", "6022"), ("AMP", "6083"),
    ("NADH", "439153"), ("NAD+", "5892"), ("NADPH", "5884"), ("NADP+", "5886"),
    ("glucose", "5793"), ("pyruvate", "1060"), ("acetyl-CoA", "6302"),
    ("FAD", "643975"), ("FMN", "643976"),
    ("heme", "53629513"), ("chlorophyll", "5351404"),
    ("PLP", "1051"), ("TPP", "1130"), ("SAM", "34755"),
    ("citrate", "311"), ("malate", "525"), ("succinate", "1110"),
    ("tryptophan", "6305"), ("tyrosine", "6057"), ("phenylalanine", "6140"),
    ("lysine", "5962"), ("arginine", "6322"), ("histidine", "6274"),
    ("serine", "5951"), ("threonine", "6288"), ("cysteine", "5862"),
    ("methionine", "6137"), ("aspartate", "5960"), ("glutamate", "33032"),
    ("asparagine", "6267"), ("glutamine", "5961"), ("glycine", "750"),
    ("alanine", "5950"), ("valine", "6287"), ("leucine", "6106"),
    ("isoleucine", "6306"), ("proline", "145742"),
]


@register("pubchem")
class PubChemIngestor(BaseIngestor):
    """Seed and populate substrate compound data from PubChem."""

    source_name = "pubchem"
    chunk_size = 10

    async def _download_raw(self) -> Path:
        """Fetch compound properties for seed substrates from PubChem REST."""
        all_compounds = []

        for name, cid_str in SEED_COMPOUNDS:
            cid = int(cid_str)
            try:
                # Get compound properties
                prop_url = f"{PUBCHEM_BASE}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChI,InChIKey,XLogP,TPSA,Complexity,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,IUPACName/JSON"
                resp = await self.http.get(prop_url)
                if resp.status_code == 429:
                    await asyncio.sleep(5.0)
                    continue
                if resp.status_code != 200:
                    logger.warning("pubchem: CID %d (%s) returned %d", cid, name, resp.status_code)
                    continue

                data = resp.json()
                props = data.get("PropertyTable", {}).get("Properties", [])
                if props:
                    p = props[0]
                    all_compounds.append({
                        "pubchem_cid": cid,
                        "name": name,
                        "iupac_name": p.get("IUPACName"),
                        "molecular_formula": p.get("MolecularFormula"),
                        "molecular_weight": p.get("MolecularWeight"),
                        "smiles": p.get("CanonicalSMILES") or p.get("ConnectivitySMILES"),
                        "inchi": p.get("InChI"),
                        "inchikey": p.get("InChIKey"),
                        "xlogp": p.get("XLogP"),
                        "tpsa": p.get("TPSA"),
                        "rotatable_bonds": p.get("RotatableBondCount"),
                        "hbd": p.get("HBondDonorCount"),
                        "hba": p.get("HBondAcceptorCount"),
                    })

                logger.info("pubchem: CID %d (%s) fetched (total %d)", cid, name, len(all_compounds))
                await asyncio.sleep(self.request_delay)
            except Exception:
                logger.exception("pubchem: CID %d (%s) failed", cid, name)

        out = self.cache_dir / "pubchem_compounds.json"
        out.write_text(json.dumps(all_compounds, ensure_ascii=False))
        logger.info("pubchem: downloaded %d compounds to %s", len(all_compounds), out)
        return out

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for c in batch:
            try:
                comp = SubstrateCompound(
                    pubchem_cid=c["pubchem_cid"],
                    name=c["name"],
                    iupac_name=c.get("iupac_name"),
                    molecular_formula=c.get("molecular_formula"),
                    molecular_weight=c.get("molecular_weight"),
                    smiles=c.get("smiles"),
                    inchi=c.get("inchi"),
                    inchikey=c.get("inchikey"),
                    xlogp=c.get("xlogp"),
                    tpsa=c.get("tpsa"),
                    rotatable_bonds=c.get("rotatable_bonds"),
                    hbd=c.get("hbd"),
                    hba=c.get("hba"),
                    source_db="pubchem",
                    created_at=datetime.now(timezone.utc),
                )
                is_new = await self._upsert(
                    SubstrateCompound, self._orm_values(comp),
                    index_elements=["pubchem_cid"],
                    update_keys=["smiles", "molecular_weight"],
                )
                if is_new:
                    created += 1
                else:
                    updated += 1
            except Exception:
                logger.exception("pubchem store failed: %s", c.get("name"))
        await self.db.commit()
        return created, updated

    @staticmethod
    def _orm_values(obj) -> dict:
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if getattr(obj, c.name) is not None}
