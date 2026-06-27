"""UniProt Swiss-Prot ingestor.

Downloads enzyme entries from UniProt REST API (reviewed + EC annotation),
parses sequence/function/taxonomy/EC/Pfam/PDB cross-references, and stores
into EnzymeRecord + related tables.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import (
    EnzymeRecord,
    Taxonomy,
    ECNumber,
    EnzymeECLink,
    DatabaseCrossRef,
)

logger = logging.getLogger(__name__)

UNIPROT_REST = "https://rest.uniprot.org/uniprotkb"
# Enzymes with EC annotation, reviewed (Swiss-Prot), page size 500
SEARCH_QUERY = "reviewed:true AND ec:*"
PAGE_SIZE = 500


@register("uniprot")
class UniProtIngestor(BaseIngestor):
    """Download enzyme entries from UniProtKB and store in domain tables."""

    source_name = "uniprot"
    chunk_size = 100

    def _download_raw(self) -> None:
        """Not used — run() handles download+store incrementally."""
        raise NotImplementedError

    async def run(self, force: bool = False) -> IngestReport:
        """Override: download and store page-by-page to avoid memory build-up."""
        from app.data.base_ingestor import IngestReport, IngestStatus

        report = IngestReport(source=self.source_name, started_at=datetime.now(timezone.utc))
        try:
            report.status = IngestStatus.DOWNLOADING
            url = f"{UNIPROT_REST}/search?query={SEARCH_QUERY}&format=json&size={PAGE_SIZE}&fields=accession,id,sequence,protein_name,gene_names,organism_name,cc_function,cc_catalytic_activity,ec,ft_domain,protein_families,organism_id,lineage"
            page = 0

            while url:
                logger.info("uniprot page %d: %s", page, url)
                data = None
                for attempt in range(3):
                    try:
                        resp = await self.http.get(url)
                        if resp.status_code == 429:
                            await asyncio.sleep(5.0 * (attempt + 1))
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                        break
                    except Exception as e:
                        logger.warning("uniprot page %d attempt %d: %s", page, attempt, e)
                        if attempt < 2:
                            await asyncio.sleep(3.0 * (attempt + 1))
                        else:
                            logger.error("uniprot page %d failed after 3 attempts: %s", page, e)
                            report.status = IngestStatus.FAILED
                            report.errors.append(f"page {page}: {e}")
                            report.finished_at = datetime.now(timezone.utc)
                            return report
                if data is None:
                    continue  # retry loop exhausted, should not reach here

                results = data.get("results", [])
                page += 1
                logger.info("  got %d entries", len(results))

                # Store this page's entries in batches
                if results:
                    report.status = IngestStatus.STORING
                    batch_size = self.chunk_size
                    for i in range(0, len(results), batch_size):
                        batch = results[i:i + batch_size]
                        try:
                            created, updated = await self._store_batch(batch)
                            report.items_created += created
                            report.items_updated += updated
                        except Exception as e:
                            report.items_failed += len(batch)
                            report.errors.append(f"store batch: {e}")

                # Follow Link header for next page
                url = None
                link_hdr = resp.headers.get("Link", "")
                m = re.search(r'<(https?://[^>]+)>;\s*rel="next"', link_hdr)
                if m:
                    url = m.group(1)
                await asyncio.sleep(self.request_delay)

            report.status = IngestStatus.COMPLETED
        except Exception as e:
            report.status = IngestStatus.FAILED
            report.errors.append(str(e))
        finally:
            report.finished_at = datetime.now(timezone.utc)
        return report

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for entry in batch:
            try:
                c, u = await self._store_entry(entry)
                created += c
                updated += u
            except Exception:
                logger.exception("failed to store entry %s", entry.get("primaryAccession"))
        await self.db.commit()
        return created, updated

    # ------------------------------------------------------------------
    # Single-entry store
    # ------------------------------------------------------------------

    async def _store_entry(self, entry: dict) -> tuple[int, int]:
        acc = entry["primaryAccession"]
        seq_data = entry.get("sequence", {})
        sequence = seq_data.get("value", "") if seq_data else ""
        if not sequence:
            return 0, 0

        # --- Taxonomy ---
        org_data = entry.get("organism", {})
        tax_id = org_data.get("taxonId")
        sci_name = org_data.get("scientificName", "Unknown")

        tax_row = await self._upsert_taxonomy(tax_id, sci_name, org_data)

        # --- EnzymeRecord ---
        name = _extract_protein_name(entry)
        gene = _extract_gene_name(entry)
        func_anno = _extract_comment(entry, "FUNCTION")
        cat_act = _extract_comment(entry, "CATALYTIC ACTIVITY")
        ec_list = _extract_ec_numbers(entry)

        rec = EnzymeRecord(
            uniprot_id=acc,
            entry_name=entry.get("uniProtkbId"),
            sequence=sequence,
            seq_length=len(sequence),
            protein_name=name,
            gene_name=gene,
            description=func_anno[:2000] if func_anno else None,
            function_annotation=func_anno,
            catalytic_activity=cat_act,
            taxonomy_id=tax_row.id if tax_row else None,
            is_reviewed=True,
            source_db="uniprot",
            updated_at=datetime.now(timezone.utc),
        )

        # Upsert enzyme record
        is_new = await self._upsert(
            EnzymeRecord, self._orm_values(rec),
            index_elements=["uniprot_id"],
            update_keys=["sequence", "seq_length", "protein_name", "gene_name",
                         "function_annotation", "catalytic_activity", "taxonomy_id", "updated_at"],
        )

        # Get enzyme ID
        row = await self.db.execute(
            select(EnzymeRecord.id).where(EnzymeRecord.uniprot_id == acc)
        )
        enzyme_id = row.scalar()

        # --- EC numbers ---
        if ec_list:
            await self._link_ec(enzyme_id, ec_list)

        # --- Cross-references ---
        await self._store_xrefs(enzyme_id, acc, entry)

        return (1, 0) if is_new else (0, 1)

    async def _upsert_taxonomy(self, tax_id: int | None, sci_name: str, org_data: dict) -> Taxonomy | None:
        if not tax_id:
            return None
        row = await self.db.execute(
            select(Taxonomy).where(Taxonomy.ncbi_taxid == tax_id)
        )
        existing = row.scalar()
        if existing:
            return existing

        lineage_list = org_data.get("lineage", [])
        lineage_str = ", ".join(lineage_list) if lineage_list else None

        tax = Taxonomy(
            ncbi_taxid=tax_id,
            scientific_name=sci_name,
            common_name=org_data.get("commonName"),
            lineage=lineage_str,
        )
        self.db.add(tax)
        await self.db.flush()
        return tax

    async def _link_ec(self, enzyme_id: int, ec_list: list[str]) -> None:
        for ec_str in ec_list:
            row = await self.db.execute(
                select(ECNumber).where(ECNumber.ec_number == ec_str)
            )
            ec = row.scalar()
            if not ec:
                ec = ECNumber(
                    ec_number=ec_str,
                    level1=ec_str.split(".")[0] if "." in ec_str else ec_str,
                    level2=".".join(ec_str.split(".")[:2]) if ec_str.count(".") >= 2 else None,
                    level3=".".join(ec_str.split(".")[:3]) if ec_str.count(".") >= 3 else None,
                )
                self.db.add(ec)
                await self.db.flush()

            # Check existing link
            link_row = await self.db.execute(
                select(EnzymeECLink).where(
                    EnzymeECLink.enzyme_id == enzyme_id, EnzymeECLink.ec_id == ec.id
                )
            )
            if not link_row.scalar():
                self.db.add(EnzymeECLink(enzyme_id=enzyme_id, ec_id=ec.id, is_primary=(ec_str == ec_list[0])))

    async def _store_xrefs(self, enzyme_id: int, acc: str, entry: dict) -> None:
        """Store PDB, Pfam cross-references from UniProt dbReferences."""
        for ref in entry.get("uniProtKBCrossReferences", []):
            db_type = ref.get("database", "").lower()
            db_id = ref.get("id", "")
            if not db_type or not db_id:
                continue

            xref = DatabaseCrossRef(
                enzyme_id=enzyme_id,
                source_db=db_type,
                source_id=db_id,
                source_url=_xref_url(db_type, db_id),
                last_synced=datetime.now(timezone.utc),
            )
            await self._upsert(
                DatabaseCrossRef, self._orm_values(xref),
                index_elements=["enzyme_id", "source_db"],
                update_keys=["source_id", "last_synced"],
            )

    @staticmethod
    def _orm_values(obj) -> dict:
        """Extract column values from an ORM object for insert statements."""
        return {
            c.name: getattr(obj, c.name)
            for c in obj.__table__.columns
            if getattr(obj, c.name) is not None
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_protein_name(entry: dict) -> str | None:
    pd = entry.get("proteinDescription", {})
    rec = pd.get("recommendedName", {}) or pd.get("submissionNames", [{}])[0]
    return rec.get("fullName", {}).get("value")


def _extract_gene_name(entry: dict) -> str | None:
    genes = entry.get("genes", [])
    if genes:
        gn = genes[0].get("geneName", {})
        return gn.get("value")
    return None


def _extract_comment(entry: dict, comment_type: str) -> str | None:
    for c in entry.get("comments", []):
        if c.get("commentType") == comment_type:
            texts = c.get("texts", [])
            if texts:
                return texts[0].get("value")
    return None


def _extract_ec_numbers(entry: dict) -> list[str]:
    ecs = []
    pd = entry.get("proteinDescription", {})
    for rec in pd.get("recommendedName", {}).get("ecNumbers", []):
        ecs.append(rec.get("value", ""))
    return [e for e in ecs if e]


def _xref_url(db_type: str, db_id: str) -> str | None:
    prefixes = {
        "pdb": f"https://www.rcsb.org/structure/{db_id}",
        "pfam": f"https://pfam.xfam.org/family/{db_id}",
        "brenda": f"https://www.brenda-enzymes.org/enzyme.php?ecno={db_id}",
    }
    return prefixes.get(db_type)

