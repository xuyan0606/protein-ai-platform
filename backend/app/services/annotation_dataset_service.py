"""Reusable service for local annotation dataset ingestion and synchronization."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import (
    CatalyticResidue,
    CatalyticSite,
    DomainArchitecture,
    ECNumber,
    EnzymeECLink,
    EnzymeInterProLink,
    EnzymeRecord,
    InterProEntry,
    PfamDomain,
    SignalPeptidePrediction,
    Taxonomy,
)


def _sequence_hash(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("utf-8")).hexdigest()


def _normalize_taxonomy_payload(payload: dict) -> dict:
    normalized = dict(payload)
    alias_map = {
        "kingdom": "superkingdom",
        "class_name": "tax_class",
        "taxonomy_class_name": "tax_class",
        "order_name": "order_",
        "taxonomy_order_name": "order_",
        "order": "order_",
    }
    for source, target in alias_map.items():
        if normalized.get(source) not in (None, "") and normalized.get(target) in (None, ""):
            normalized[target] = normalized[source]
    if normalized.get("species") not in (None, "") and normalized.get("scientific_name") in (None, ""):
        normalized["scientific_name"] = normalized["species"]

    allowed = {
        "ncbi_taxid",
        "scientific_name",
        "common_name",
        "lineage",
        "superkingdom",
        "phylum",
        "tax_class",
        "order_",
        "family",
        "genus",
    }
    return {key: value for key, value in normalized.items() if key in allowed and value not in (None, "")}


class AnnotationDatasetService:
    """Encapsulates local annotation dataset upsert logic behind one reusable class."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_records(self, records: list[dict]) -> tuple[int, int]:
        created = 0
        updated = 0

        for record in records:
            is_created = await self.upsert_bundle(record)
            if is_created:
                created += 1
            else:
                updated += 1

        await self.session.commit()
        return created, updated

    async def upsert_bundle(self, record: dict) -> bool:
        taxonomy = await self._get_or_create_taxonomy(record.get("taxonomy") or {})
        enzyme_payload = dict(record["enzyme"])
        sequence = enzyme_payload["sequence"].strip().upper()
        enzyme_payload["sequence"] = sequence
        enzyme_payload["seq_length"] = len(sequence)
        enzyme_payload["taxonomy_id"] = taxonomy.id if taxonomy else None

        row = await self.session.execute(
            select(EnzymeRecord).where(EnzymeRecord.uniprot_id == enzyme_payload["uniprot_id"])
        )
        enzyme = row.scalar_one_or_none()
        is_created = enzyme is None

        if enzyme is None:
            enzyme = EnzymeRecord(**enzyme_payload)
            self.session.add(enzyme)
            await self.session.flush()
        else:
            for key, value in enzyme_payload.items():
                setattr(enzyme, key, value)
            await self.session.flush()

        hydrated_row = await self.session.execute(
            select(EnzymeRecord)
            .options(
                selectinload(EnzymeRecord.ec_numbers).selectinload(EnzymeECLink.ec_number),
                selectinload(EnzymeRecord.domains).selectinload(DomainArchitecture.domain),
                selectinload(EnzymeRecord.interpro_links).selectinload(EnzymeInterProLink.interpro_entry),
                selectinload(EnzymeRecord.catalytic_sites).selectinload(CatalyticSite.residues),
                selectinload(EnzymeRecord.signal_peptide_predictions),
            )
            .where(EnzymeRecord.id == enzyme.id)
        )
        hydrated = hydrated_row.scalar_one()

        await self._sync_ec_numbers(hydrated, record.get("ec_numbers") or [])
        await self._sync_pfam_domains(hydrated, record.get("pfam_domains") or [])
        await self._sync_interpro_annotations(hydrated, record.get("interpro_annotations") or [])
        await self._sync_catalytic_sites(hydrated, record.get("catalytic_sites") or [])
        await self._sync_signal_prediction(hydrated, record.get("signal_peptide_prediction"))

        return is_created

    async def _get_or_create_taxonomy(self, payload: dict) -> Taxonomy | None:
        payload = _normalize_taxonomy_payload(payload)
        if not payload:
            return None

        if payload.get("ncbi_taxid") is not None:
            row = await self.session.execute(
                select(Taxonomy).where(Taxonomy.ncbi_taxid == payload["ncbi_taxid"])
            )
            taxonomy = row.scalar_one_or_none()
            if taxonomy:
                for key, value in payload.items():
                    setattr(taxonomy, key, value)
                await self.session.flush()
                return taxonomy

        row = await self.session.execute(
            select(Taxonomy).where(Taxonomy.scientific_name == payload["scientific_name"])
        )
        taxonomy = row.scalar_one_or_none()
        if taxonomy:
            for key, value in payload.items():
                setattr(taxonomy, key, value)
            await self.session.flush()
            return taxonomy

        taxonomy = Taxonomy(**payload)
        self.session.add(taxonomy)
        await self.session.flush()
        return taxonomy

    async def _sync_ec_numbers(self, enzyme: EnzymeRecord, payloads: list[dict]) -> None:
        existing_by_ec = {
            link.ec_number.ec_number: link
            for link in enzyme.ec_numbers
            if link.ec_number is not None
        }
        wanted = {item["ec_number"] for item in payloads}

        for item in payloads:
            ec_row = await self.session.execute(select(ECNumber).where(ECNumber.ec_number == item["ec_number"]))
            ec = ec_row.scalar_one_or_none()
            ec_values = {k: v for k, v in item.items() if k != "is_primary"}
            if ec is None:
                ec = ECNumber(**ec_values)
                self.session.add(ec)
                await self.session.flush()
            else:
                for key, value in ec_values.items():
                    setattr(ec, key, value)
                await self.session.flush()

            link = existing_by_ec.get(item["ec_number"])
            if link is None:
                self.session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=bool(item.get("is_primary"))))
            else:
                link.is_primary = bool(item.get("is_primary"))

        for ec_number, link in existing_by_ec.items():
            if ec_number not in wanted:
                await self.session.delete(link)

    async def _sync_pfam_domains(self, enzyme: EnzymeRecord, payloads: list[dict]) -> None:
        existing = {
            (arch.domain.pfam_id if arch.domain else None, arch.start_pos, arch.end_pos): arch
            for arch in enzyme.domains
        }
        wanted: set[tuple[str | None, int, int]] = set()

        for item in payloads:
            domain_row = await self.session.execute(select(PfamDomain).where(PfamDomain.pfam_id == item["pfam_id"]))
            domain = domain_row.scalar_one_or_none()
            domain_values = {
                "pfam_id": item["pfam_id"],
                "name": item.get("name"),
                "description": item.get("description"),
            }
            if domain is None:
                domain = PfamDomain(**domain_values)
                self.session.add(domain)
                await self.session.flush()
            else:
                for key, value in domain_values.items():
                    setattr(domain, key, value)
                await self.session.flush()

            key = (domain.pfam_id, item["start_pos"], item["end_pos"])
            wanted.add(key)
            arch = existing.get(key)
            if arch is None:
                self.session.add(
                    DomainArchitecture(
                        enzyme_id=enzyme.id,
                        domain_id=domain.id,
                        start_pos=item["start_pos"],
                        end_pos=item["end_pos"],
                        evalue=item.get("evalue"),
                    )
                )
            else:
                arch.evalue = item.get("evalue")

        for key, arch in existing.items():
            if key not in wanted:
                await self.session.delete(arch)

    async def _sync_interpro_annotations(self, enzyme: EnzymeRecord, payloads: list[dict]) -> None:
        existing = {
            (
                link.interpro_entry.interpro_id if link.interpro_entry else None,
                link.start_pos,
                link.end_pos,
            ): link
            for link in enzyme.interpro_links
        }
        wanted: set[tuple[str | None, int | None, int | None]] = set()

        for item in payloads:
            entry_row = await self.session.execute(
                select(InterProEntry).where(InterProEntry.interpro_id == item["interpro_id"])
            )
            entry = entry_row.scalar_one_or_none()
            entry_values = {
                "interpro_id": item["interpro_id"],
                "entry_type": item.get("entry_type"),
                "name": item.get("name"),
                "description": item.get("description"),
                "source_db": item.get("source_db"),
                "go_terms": item.get("go_terms"),
            }
            if entry is None:
                entry = InterProEntry(**entry_values)
                self.session.add(entry)
                await self.session.flush()
            else:
                for key, value in entry_values.items():
                    setattr(entry, key, value)
                await self.session.flush()

            key = (entry.interpro_id, item.get("start_pos"), item.get("end_pos"))
            wanted.add(key)
            link = existing.get(key)
            if link is None:
                self.session.add(
                    EnzymeInterProLink(
                        enzyme_id=enzyme.id,
                        interpro_entry_id=entry.id,
                        start_pos=item.get("start_pos"),
                        end_pos=item.get("end_pos"),
                        score=item.get("score"),
                        evidence=item.get("evidence"),
                    )
                )
            else:
                link.score = item.get("score")
                link.evidence = item.get("evidence")

        for key, link in existing.items():
            if key not in wanted:
                await self.session.delete(link)

    async def _sync_catalytic_sites(self, enzyme: EnzymeRecord, payloads: list[dict]) -> None:
        existing_sources = {item.get("source") for item in payloads}
        for site in list(enzyme.catalytic_sites):
            if site.source in existing_sources:
                await self.session.delete(site)
        await self.session.flush()

        for item in payloads:
            site = CatalyticSite(
                enzyme_id=enzyme.id,
                source=item.get("source", "local_demo"),
                mechanism_name=item.get("mechanism_name"),
                reaction_text=item.get("reaction_text"),
                evidence_json=item.get("evidence_json"),
            )
            self.session.add(site)
            await self.session.flush()

            for residue in item.get("residues") or []:
                self.session.add(
                    CatalyticResidue(
                        site_id=site.id,
                        residue_pos=residue["residue_pos"],
                        residue_aa=residue.get("residue_aa"),
                        role=residue.get("role"),
                        confidence=residue.get("confidence"),
                        pdb_chain=residue.get("pdb_chain"),
                        pdb_residue_no=str(residue["pdb_residue_no"]) if residue.get("pdb_residue_no") is not None else None,
                    )
                )

    async def _sync_signal_prediction(self, enzyme: EnzymeRecord, payload: dict | None) -> None:
        if not payload:
            return

        sequence_hash = _sequence_hash(enzyme.sequence.upper())
        model_name = payload.get("model", "local_annotation_seed")
        row = await self.session.execute(
            select(SignalPeptidePrediction).where(
                SignalPeptidePrediction.enzyme_id == enzyme.id,
                SignalPeptidePrediction.sequence_hash == sequence_hash,
                SignalPeptidePrediction.model_name == model_name,
            )
        )
        prediction = row.scalar_one_or_none()

        raw_json = {
            "found": True,
            "query": {"uniprot_id": enzyme.uniprot_id, "sequence_length": enzyme.seq_length},
            **payload,
            "cache": {"hit": True, "source": "database"},
        }

        if prediction is None:
            self.session.add(
                SignalPeptidePrediction(
                    enzyme_id=enzyme.id,
                    sequence_hash=sequence_hash,
                    has_signal=payload.get("has_signal_peptide"),
                    cleavage_site=payload.get("cleavage_site"),
                    model_name=model_name,
                    raw_json=raw_json,
                )
            )
        else:
            prediction.has_signal = payload.get("has_signal_peptide")
            prediction.cleavage_site = payload.get("cleavage_site")
            prediction.raw_json = raw_json
