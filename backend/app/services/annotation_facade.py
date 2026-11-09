"""Facade for annotation lookup combining curated data and heuristic fallback."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import SignalPeptidePrediction
from app.services.annotation_query_service import (
    AnnotationQueryService,
    build_catalytic_mechanism_profile,
    build_catalytic_mechanism_report_contract,
)
from app.services.evidence_source_status import blocked_evidence_source, evidence_source_status
from app.services.interpro_live import InterProLiveClient

_MOTIF_HINTS: list[dict[str, Any]] = [
    {
        "label": "Lipase/Esterase alpha/beta hydrolase",
        "interpro_id": "IPR000073",
        "entry_type": "family",
        "pattern": "GXSXG",
        "go_terms": ["GO:0016787 hydrolase activity", "GO:0016298 lipase activity"],
        "notes": "Classical alpha/beta hydrolase catalytic motif.",
    },
    {
        "label": "GH13 alpha-amylase family",
        "interpro_id": "IPR006046",
        "entry_type": "family",
        "pattern": "G[FWY]R[LI][DN]A[AV]K[HN]",
        "go_terms": ["GO:0004556 alpha-amylase activity", "GO:0016798 hydrolase activity"],
        "notes": "GH13 catalytic barrel signature.",
    },
    {
        "label": "Serine protease catalytic motif",
        "interpro_id": "IPR001254",
        "entry_type": "site",
        "pattern": "GDSGG",
        "go_terms": ["GO:0008236 serine-type peptidase activity"],
        "notes": "Conserved catalytic motif of S1 serine proteases.",
    },
]

_HYDROPHOBIC = set("AILMFWVPGC")
_POSITIVE = set("RK")
_CLEAVAGE_SMALL = set("ASTVG")


class AnnotationFacade:
    """Unified entry point for annotation tools and future structure/topology add-ons."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.query = AnnotationQueryService(session)

    async def resolve_interpro_annotation(
        self,
        sequence: str = "",
        uniprot_id: str = "",
        *,
        live: bool = False,
        live_base_url: str | None = None,
        live_timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if live:
            return await self._resolve_interpro_annotation_live(
                sequence=sequence,
                uniprot_id=uniprot_id,
                live_enabled=True,
                live_base_url=live_base_url,
                live_timeout_seconds=live_timeout_seconds,
            )

        return await self._resolve_interpro_annotation_local(sequence=sequence, uniprot_id=uniprot_id)

    async def resolve_interpro_live_annotation(
        self,
        sequence: str = "",
        uniprot_id: str = "",
        *,
        enabled: bool | None = None,
        live_base_url: str | None = None,
        live_timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return await self._resolve_interpro_annotation_live(
            sequence=sequence,
            uniprot_id=uniprot_id,
            live_enabled=enabled,
            live_base_url=live_base_url,
            live_timeout_seconds=live_timeout_seconds,
        )

    async def _resolve_interpro_annotation_local(
        self,
        sequence: str = "",
        uniprot_id: str = "",
    ) -> dict[str, Any]:
        enzyme, seq = await self._resolve_enzyme_and_sequence(sequence, uniprot_id, with_annotations=True)
        if not seq:
            return {
                "found": False,
                "error": "Provide sequence or uniprot_id",
                "evidence_source": blocked_evidence_source("InterPro", "missing sequence or UniProt accession"),
            }

        curated_entries: list[dict[str, Any]] = []
        pfam_entries: list[dict[str, Any]] = []
        if enzyme:
            annotation_payload = self.query.build_annotations_payload(enzyme)
            curated_entries = annotation_payload["annotations"]
            pfam_entries = [
                {
                    "interpro_id": None,
                    "name": domain["name"] or domain["pfam_id"],
                    "entry_type": "domain",
                    "source": "pfam",
                    "pfam_id": domain["pfam_id"],
                    "regions": [{"start": domain["start_pos"], "end": domain["end_pos"]}],
                    "score": domain["evalue"],
                }
                for domain in annotation_payload["pfam_domains"]
            ]

        inferred_entries = self._infer_annotations_from_sequence(seq)
        all_entries = curated_entries + pfam_entries + inferred_entries

        return {
            "found": len(all_entries) > 0,
            "query": {"uniprot_id": uniprot_id or None, "sequence_length": len(seq)},
            "evidence_source": evidence_source_status(
                source="InterPro",
                status="degraded",
                mode="local_import_or_heuristic",
                live_query_executed=False,
                reason="No live InterPro API query is executed in this tool path.",
                details={
                    "curated_interpro_count": len(curated_entries),
                    "pfam_domain_count": len(pfam_entries),
                    "heuristic_count": len(inferred_entries),
                },
            ),
            "summary": {
                "curated_interpro_count": len(curated_entries),
                "pfam_domain_count": len(pfam_entries),
                "heuristic_count": len(inferred_entries),
            },
            "annotations": all_entries,
            "note": (
                "Phase 1 result merges local InterPro links, existing Pfam domain "
                "architecture, and motif heuristics. Curated InterPro ingestion can "
                "be added later for full annotation coverage."
            ),
        }

    async def _resolve_interpro_annotation_live(
        self,
        sequence: str = "",
        uniprot_id: str = "",
        *,
        live_enabled: bool | None,
        live_base_url: str | None = None,
        live_timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        enzyme, seq = await self._resolve_enzyme_and_sequence(sequence, uniprot_id, with_annotations=True)
        accession = (enzyme.uniprot_id if enzyme is not None else uniprot_id.strip().upper()).strip()
        if not accession:
            return {
                "found": False,
                "error": "Provide uniprot_id or a sequence that matches a curated protein record",
                "evidence_source": blocked_evidence_source(
                    "InterPro",
                    "live InterPro lookup requires a UniProt accession or an exact local sequence match",
                ),
            }

        live_client = InterProLiveClient(
            enabled=live_enabled,
            base_url=live_base_url,
            timeout_seconds=live_timeout_seconds,
        )
        return await live_client.resolve_annotations(sequence=seq, uniprot_id=accession)

    async def resolve_catalytic_site_lookup(
        self,
        sequence: str = "",
        uniprot_id: str = "",
    ) -> dict[str, Any]:
        enzyme, seq = await self._resolve_enzyme_and_sequence(sequence, uniprot_id, with_annotations=True)
        if not seq:
            return {
                "found": False,
                "error": "Provide sequence or uniprot_id",
                "evidence_source": blocked_evidence_source("catalytic_site_lookup", "missing sequence or UniProt accession"),
                "mechanism_profile": self._blocked_mechanism_profile("missing sequence or UniProt accession"),
            }

        curated_sites: list[dict[str, Any]] = []
        if enzyme:
            curated_payload = self.query.build_catalytic_sites_payload(enzyme)
            curated_sites = curated_payload["sites"]

        inferred = self._infer_catalytic_residues(seq) if not curated_sites else []
        protected_positions = sorted(
            {item["position"] for site in curated_sites for item in site["residues"]}
            | {item["position"] for item in inferred}
        )
        coordinate_status = self._coordinate_status(enzyme, sequence)
        mechanism_profile = build_catalytic_mechanism_profile(
            curated_sites,
            protected_positions,
            coordinate_status=coordinate_status,
        )

        return {
            "found": bool(curated_sites or inferred),
            "query": {"uniprot_id": uniprot_id or None, "sequence_length": len(seq)},
            "evidence_source": evidence_source_status(
                source="catalytic_site_lookup",
                status="degraded",
                mode="local_database_or_heuristic",
                live_query_executed=False,
                reason="No live UniProt/M-CSA query is executed in this tool path.",
                details={
                    "curated_site_count": len(curated_sites),
                    "heuristic_guardrail_count": len(inferred),
                },
            ),
            "curated_sites": curated_sites,
            "inferred_guardrails": inferred,
            "protected_positions": protected_positions,
            "mechanism_profile": mechanism_profile,
            "mutation_guidance": {
                "avoid_positions": protected_positions,
                "rule": "Do not mutate protected catalytic or catalytic-adjacent positions before manual review.",
            },
            "note": (
                "Curated M-CSA-style catalytic sites will override heuristic guardrails "
                "when local data is available. Current inference is conservative and "
                "designed to reduce high-risk engineering suggestions."
            ),
        }

    async def resolve_signal_peptide_prediction(
        self,
        sequence: str = "",
        uniprot_id: str = "",
    ) -> dict[str, Any]:
        enzyme, seq = await self._resolve_enzyme_and_sequence(sequence, uniprot_id, with_annotations=True)
        if not seq:
            return {
                "found": False,
                "error": "Provide sequence or uniprot_id",
                "evidence_source": blocked_evidence_source("signal_peptide", "missing sequence or UniProt accession"),
            }

        if enzyme is not None:
            cached_payload = self.query.build_signal_peptide_payload(enzyme)
            if cached_payload is not None:
                payload = dict(cached_payload)
                payload.update(
                    {
                        "found": True,
                        "query": {"uniprot_id": uniprot_id or None, "sequence_length": len(seq)},
                        "cache": {"hit": True, "source": "database"},
                        "evidence_source": evidence_source_status(
                            source="signal_peptide",
                            status="degraded",
                            mode="local_database_cache",
                            live_query_executed=False,
                            reason="No live SignalP runtime/API query is executed in this tool path.",
                        ),
                    }
                )
                return payload

        seq_hash = self._sequence_hash(seq)
        cached_row = (
            await self.session.execute(
                select(SignalPeptidePrediction)
                .where(SignalPeptidePrediction.sequence_hash == seq_hash)
                .order_by(SignalPeptidePrediction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if cached_row and cached_row.raw_json:
            payload = dict(cached_row.raw_json)
            payload.update(
                {
                    "found": True,
                    "query": {"uniprot_id": uniprot_id or None, "sequence_length": len(seq)},
                    "cache": {"hit": True, "source": "database"},
                    "evidence_source": evidence_source_status(
                        source="signal_peptide",
                        status="degraded",
                        mode="local_database_cache",
                        live_query_executed=False,
                        reason="No live SignalP runtime/API query is executed in this tool path.",
                    ),
                }
            )
            return payload

        prediction = self._predict_signal_peptide(seq)
        payload = {
            "found": True,
            "query": {"uniprot_id": uniprot_id or None, "sequence_length": len(seq)},
            **prediction,
            "cache": {"hit": False, "source": "fresh_prediction"},
            "evidence_source": evidence_source_status(
                source="signal_peptide",
                status="degraded",
                mode="heuristic_prediction",
                live_query_executed=False,
                reason="Heuristic signal peptide prediction; not live SignalP inference.",
            ),
        }

        self.session.add(
            SignalPeptidePrediction(
                enzyme_id=enzyme.id if enzyme else None,
                sequence_hash=seq_hash,
                has_signal=prediction["has_signal_peptide"],
                cleavage_site=prediction["cleavage_site"],
                model_name=prediction["model"],
                raw_json=payload,
            )
        )
        await self.session.flush()
        return payload

    async def resolve_annotation_bundle(
        self,
        sequence: str = "",
        uniprot_id: str = "",
    ) -> dict[str, Any]:
        enzyme, seq = await self._resolve_enzyme_and_sequence(sequence, uniprot_id, with_annotations=True)
        if not seq:
            return {
                "found": False,
                "error": "Provide sequence or uniprot_id",
                "evidence_source": blocked_evidence_source("annotation_bundle", "missing sequence or UniProt accession"),
            }

        resolved_uniprot_id = enzyme.uniprot_id if enzyme is not None else uniprot_id
        interpro = await self.resolve_interpro_annotation(sequence=seq, uniprot_id=resolved_uniprot_id)
        catalytic = await self.resolve_catalytic_site_lookup(sequence=seq, uniprot_id=resolved_uniprot_id)
        signal = await self.resolve_signal_peptide_prediction(sequence=seq, uniprot_id=resolved_uniprot_id)
        supplied_sequence = sequence.strip().upper()
        curated_sequence = str(getattr(enzyme, "sequence", "") or "").upper()
        coordinate_status = "not_available"
        coordinate_note = "No curated protein record was resolved for this query."
        if enzyme is not None:
            coordinate_status = self._coordinate_status(enzyme, supplied_sequence)
            coordinate_note = (
                "Curated residue positions are valid for the input sequence."
                if coordinate_status == "verified"
                else "Curated residue positions refer to the UniProt record and require sequence mapping before use."
            )

        return {
            "found": True,
            "query": {
                "uniprot_id": resolved_uniprot_id or None,
                "sequence_length": len(seq),
                "has_curated_enzyme": enzyme is not None,
            },
            "evidence_source": evidence_source_status(
                source="annotation_bundle",
                status="degraded",
                mode="local_database_or_heuristic_bundle",
                live_query_executed=False,
                version=enzyme.source_version if enzyme and enzyme.source_version else None,
                reason="Annotation bundle used local/imported records and heuristics; no live UniProt/InterPro/M-CSA/SignalP query was executed.",
                details={
                    "has_curated_enzyme": enzyme is not None,
                    "interpro_status": interpro.get("evidence_source", {}).get("status"),
                    "catalytic_status": catalytic.get("evidence_source", {}).get("status"),
                    "signal_status": signal.get("evidence_source", {}).get("status"),
                },
            ),
            "protein": {
                "uniprot_id": enzyme.uniprot_id if enzyme else None,
                "protein_name": enzyme.protein_name if enzyme else None,
                "gene_name": enzyme.gene_name if enzyme else None,
                "function_annotation": enzyme.function_annotation if enzyme else None,
                "catalytic_activity": enzyme.catalytic_activity if enzyme else None,
                "cofactors": enzyme.cofactors if enzyme else None,
                "ec_numbers": [
                    {
                        "ec": link.ec_number.ec_number,
                        "name": link.ec_number.name,
                        "primary": link.is_primary,
                    }
                    for link in (enzyme.ec_numbers if enzyme else [])
                    if link.ec_number is not None
                ],
            },
            "record_provenance": {
                "source_db": enzyme.source_db if enzyme else None,
                "source_version": enzyme.source_version if enzyme else None,
                "is_reviewed": bool(enzyme.is_reviewed) if enzyme else False,
                "record_status": (
                    "reviewed_record"
                    if enzyme and enzyme.is_reviewed
                    else "imported_or_unreviewed_record"
                    if enzyme else "no_record"
                ),
            },
            "coordinate_system": {
                "curated_record": "uniprot_sequence" if enzyme is not None else None,
                "query_record": "input_sequence",
                "status": coordinate_status,
                "note": coordinate_note,
            },
            "interpro": interpro,
            "catalytic_sites": catalytic,
            "signal_peptide": signal,
        }

    async def _resolve_enzyme_and_sequence(
        self,
        sequence: str,
        uniprot_id: str,
        *,
        with_annotations: bool,
    ) -> tuple[Any | None, str]:
        seq = sequence.strip().upper()
        enzyme = None
        if uniprot_id:
            enzyme = (
                await self.query.get_enzyme_with_annotations(uniprot_id)
                if with_annotations
                else await self.query.get_enzyme(uniprot_id)
            )
            if enzyme and not seq:
                seq = enzyme.sequence.upper()
        elif seq and with_annotations:
            enzyme = await self.query.get_enzyme_by_exact_sequence_with_annotations(seq)
        return enzyme, seq

    @staticmethod
    def _coordinate_status(enzyme: Any | None, supplied_sequence: str) -> str:
        if enzyme is None:
            return "not_available"
        curated_sequence = str(getattr(enzyme, "sequence", "") or "").strip().upper()
        query_sequence = supplied_sequence.strip().upper()
        return "verified" if not query_sequence or query_sequence == curated_sequence else "mapping_required"

    @staticmethod
    def _blocked_mechanism_profile(reason: str) -> dict[str, Any]:
        report_contract = build_catalytic_mechanism_report_contract(
            status="blocked",
            coordinate_status="not_available",
            assignments=[],
            pending_numbering=[],
            blocked_reason=reason,
        )
        return {
            "schema_version": "catalytic_mechanism_profile_v1",
            "status": "blocked",
            "coordinate_status": "not_available",
            "source_coordinate": {
                "coordinate_system": "uniprot_sequence",
                "status": "unavailable",
                "positions": [],
            },
            "user_coordinate": {
                "coordinate_system": "user_sequence",
                "status": "unavailable",
                "positions": [],
            },
            "mechanism_names": [],
            "reaction_texts": [],
            "catalytic_residues": [],
            "first_shell_positions": [],
            "second_shell_positions": [],
            "second_shell_status": "unknown_not_annotated_in_local_model",
            "protected_positions": [],
            "pending_numbering": [],
            "evidence_level": "NONE",
            "report_contract": report_contract,
            "report_boundary": f"Mechanism profile blocked: {reason}.",
        }

    @staticmethod
    def _find_motif_positions(sequence: str, pattern: str) -> list[tuple[int, int]]:
        if pattern == "GXSXG":
            hits: list[tuple[int, int]] = []
            for idx in range(len(sequence) - 4):
                window = sequence[idx:idx + 5]
                if window[0] == "G" and window[2] == "S" and window[4] == "G":
                    hits.append((idx + 1, idx + 5))
            return hits

        import re

        return [(m.start() + 1, m.end()) for m in re.finditer(pattern, sequence)]

    @classmethod
    def _infer_annotations_from_sequence(cls, sequence: str) -> list[dict[str, Any]]:
        inferred: list[dict[str, Any]] = []
        for hint in _MOTIF_HINTS:
            positions = cls._find_motif_positions(sequence, hint["pattern"])
            if not positions:
                continue
            inferred.append(
                {
                    "interpro_id": hint["interpro_id"],
                    "name": hint["label"],
                    "entry_type": hint["entry_type"],
                    "source": "heuristic",
                    "go_terms": hint["go_terms"],
                    "regions": [{"start": start, "end": end} for start, end in positions[:5]],
                    "notes": hint["notes"],
                }
            )
        return inferred

    @staticmethod
    def _infer_catalytic_residues(sequence: str) -> list[dict[str, Any]]:
        seq = sequence.upper()
        inferred: list[dict[str, Any]] = []

        for idx in range(len(seq) - 4):
            window = seq[idx:idx + 5]
            if window[0] == "G" and window[2] == "S" and window[4] == "G":
                ser_pos = idx + 3
                inferred.append(
                    {
                        "position": ser_pos,
                        "residue": "S",
                        "role": "nucleophile",
                        "confidence": 0.86,
                        "source": "heuristic",
                        "evidence": "GXSXG alpha/beta hydrolase motif",
                    }
                )
                break

        if "GHRL" not in seq and len(seq) >= 250:
            acidic_positions = [i + 1 for i, aa in enumerate(seq) if aa in {"D", "E"}]
            if len(acidic_positions) >= 3:
                trio = acidic_positions[:3]
                inferred.extend(
                    [
                        {
                            "position": trio[0],
                            "residue": seq[trio[0] - 1],
                            "role": "candidate catalytic acid/base",
                            "confidence": 0.35,
                            "source": "heuristic",
                            "evidence": "acidic residue cluster in enzyme-length scaffold",
                        },
                        {
                            "position": trio[1],
                            "residue": seq[trio[1] - 1],
                            "role": "candidate catalytic nucleophile/stabilizer",
                            "confidence": 0.30,
                            "source": "heuristic",
                            "evidence": "acidic residue cluster in enzyme-length scaffold",
                        },
                    ]
                )

        for pos in range(max(0, len(seq) - 120), len(seq)):
            if seq[pos] == "H":
                inferred.append(
                    {
                        "position": pos + 1,
                        "residue": "H",
                        "role": "candidate proton shuttle",
                        "confidence": 0.28,
                        "source": "heuristic",
                        "evidence": "C-terminal histidine candidate in catalytic relay",
                    }
                )
                break

        unique: dict[tuple[int, str], dict[str, Any]] = {}
        for item in inferred:
            unique[(item["position"], item["role"])] = item
        return sorted(unique.values(), key=lambda item: (-item["confidence"], item["position"]))

    @staticmethod
    def _predict_signal_peptide(sequence: str) -> dict[str, Any]:
        seq = sequence.upper()
        n_window = seq[:5]
        core_window = seq[6:24]

        positive_count = sum(1 for aa in n_window if aa in _POSITIVE)
        hydrophobic_count = sum(1 for aa in core_window if aa in _HYDROPHOBIC)
        hydrophobic_ratio = hydrophobic_count / max(len(core_window), 1)

        cleavage_idx = None
        for idx in range(15, min(len(seq) - 2, 31)):
            tri = seq[idx - 2:idx + 1]
            if len(tri) == 3 and tri[0] in _CLEAVAGE_SMALL and tri[2] in _CLEAVAGE_SMALL:
                cleavage_idx = idx
                break

        has_signal = positive_count >= 1 and hydrophobic_ratio >= 0.55 and cleavage_idx is not None
        confidence = min(
            0.95,
            round(0.22 + positive_count * 0.12 + hydrophobic_ratio * 0.6 + (0.18 if cleavage_idx else 0.0), 2),
        )

        regions = {
            "n_region": {"start": 1, "end": min(5, len(seq)), "positive_residues": positive_count},
            "h_region": {"start": 7, "end": min(24, len(seq)), "hydrophobic_ratio": round(hydrophobic_ratio, 3)},
            "c_region": {"start": max(1, (cleavage_idx or 20) - 4), "end": cleavage_idx or None},
        }

        return {
            "has_signal_peptide": has_signal,
            "confidence": confidence,
            "predicted_type": "Sec/SPI" if has_signal else "none",
            "cleavage_site": (
                f"{seq[cleavage_idx - 1]}{cleavage_idx}|{seq[cleavage_idx]}"
                if has_signal and cleavage_idx and cleavage_idx < len(seq)
                else None
            ),
            "regions": regions,
            "model": "heuristic_signalp_phase1",
            "note": "Phase 1 heuristic based on positively charged N-region, hydrophobic core, and small-residue cleavage motif.",
        }

    @staticmethod
    def _sequence_hash(sequence: str) -> str:
        return hashlib.sha256(sequence.encode("utf-8")).hexdigest()
