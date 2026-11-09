"""Evidence-gated enzyme identity and key-residue profiling.

This is intentionally conservative.  Short motifs are recorded as clues, but
they do not establish an enzyme family or EC number on their own.  The profile
is the shared contract consumed by downstream mutation-ranking tools.
"""

from __future__ import annotations

import re
import hashlib
from typing import Any

from app.tools.registry import ToolRegistry

_AA = set("ACDEFGHIKLMNPQRSTVWY")

# Evidence tiers name what backs a family candidate.  Confidence is capped by
# the tier, so a producer cannot lift a heuristic above the identity threshold
# by declaring a high number for it.  Only curated annotations and theoretical
# model template homology may reach `identified`; motif hits stay candidates.
_TIER_CAPS = {"curated": 0.95, "template": 0.75, "motif": 0.60, "unverified": 0.50}
_QUALIFYING_TIERS = frozenset({"curated", "template"})
_IDENTITY_THRESHOLD = 0.7

# The A1 catalytic dyad has one Asp in each lobe, roughly 180 residues apart.
# A pair closer than this minimum cannot be the dyad even when both residues
# sit inside a D(T/S)G(T/S) motif.
_A1_DYAD_MIN_SEPARATION = 100
_A1_DYAD_TARGET_SEPARATION = 180


def _tiered_confidence(tier: str, declared: float | None) -> float:
    cap = _TIER_CAPS.get(tier, _TIER_CAPS["unverified"])
    return round(min(cap, float(declared or 0.0)), 3)


def _motif_hits(sequence: str, pattern: str) -> list[dict[str, Any]]:
    return [
        {
            "pattern": pattern,
            "position": match.start() + 1,
            "end": match.end(),
            "matched_sequence": match.group(),
        }
        for match in re.finditer(pattern, sequence)
    ]


def _evidence(
    source: str,
    level: str,
    claim: str,
    confidence: float,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "source": source,
        "evidence_level": level,
        "claim": claim,
        "confidence": round(float(confidence), 3),
    }
    if details:
        payload["details"] = details
    return payload


def _select_catalytic_dyad(
    motif_hits: list[dict[str, Any]], sequence_length: int
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Pick the D(T/S)G(T/S) pair that can physically be the A1 catalytic dyad.

    Only one pair is chosen.  Requiring the two Asp to sit in different lobes
    and roughly 180 residues apart rejects motif hits that merely repeat the
    consensus outside the active site; extra hits remain recorded as motifs
    but are never protected as catalytic.
    """
    candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    half = sequence_length / 2.0
    for first_index, first in enumerate(motif_hits):
        for second in motif_hits[first_index + 1:]:
            start, end = int(first["position"]), int(second["position"])
            if start > half or end <= half:
                continue
            separation = end - start
            if separation < _A1_DYAD_MIN_SEPARATION:
                continue
            candidates.append((abs(separation - _A1_DYAD_TARGET_SEPARATION), first, second))
    if not candidates:
        return None
    _, first, second = min(candidates, key=lambda item: item[0])
    return first, second


def _profile_peptidase_a1(sequence: str) -> dict[str, Any] | None:
    """Identify the A1 family from its two catalytic Asp motifs.

    A single D(T/S)G(T/S) hit is not enough.  The duplicated catalytic motif,
    separated across the two lobes, is the minimum sequence-level gate here.
    This stays a motif-tier candidate: it never establishes family identity or
    catalytic residue numbers on its own.
    """
    motif_hits = _motif_hits(sequence, r"D[TS]G[TS]")
    if len(motif_hits) < 2:
        return None
    dyad = _select_catalytic_dyad(motif_hits, len(sequence))
    if dyad is None:
        return None
    dyad_positions = {int(dyad[0]["position"]), int(dyad[1]["position"])}

    catalytic = []
    for hit in dyad:
        position = int(hit["position"])
        catalytic.append({
            "position": position,
            "residue": "D",
            "role": "candidate catalytic acid of the A1 dyad; activates nucleophilic water",
            "status": "protected",
            "protection_basis": "motif_heuristic",
            "evidence_tier": "motif",
            "evidence": [
                _evidence(
                    "PROSITE PS00141 / InterPro IPR001461 rule",
                    "L2",
                    "D(T/S)G(T/S) catalytic motif",
                    _TIER_CAPS["motif"],
                    details={"motif": hit["matched_sequence"]},
                )
            ],
        })
    unassigned = [hit for hit in motif_hits if int(hit["position"]) not in dyad_positions]

    # A1 peptidases generally have an aromatic flap residue in the N-terminal
    # lobe.  This is supportive only; it is not used as a hard gate.
    aromatic_positions = [
        index + 1
        for index, residue in enumerate(sequence[: max(1, len(sequence) // 2)])
        if residue in {"Y", "F"}
    ]
    flap_candidates = [
        {
            "position": position,
            "residue": sequence[position - 1],
            "role": "candidate flap/substrate-binding aromatic residue",
            "status": "protected_pending_structure_review",
            "evidence": [
                _evidence(
                    "InterPro IPR001461 family description",
                    "L2",
                    "N-terminal flap Tyr/Phe is commonly involved in substrate binding",
                    0.55,
                )
            ],
        }
        for position in aromatic_positions
        if 70 <= position <= 180
    ][:8]

    return {
        "family": {
            "name": "Peptidase A1 / aspartic peptidase family",
            "accession": "IPR001461",
            "superfamily": "Aspartic peptidase A1",
            "entry_type": "family",
            "confidence": _TIER_CAPS["motif"],
            "source": "short motif heuristic",
            "status": "motif_only",
            "evidence_tier": "motif",
            "evidence": [
                _evidence(
                    "PROSITE PS00141",
                    "L2",
                    "Two D(T/S)G(T/S) catalytic motifs detected",
                    _TIER_CAPS["motif"],
                    details={
                        "dyad": [int(hit["position"]) for hit in dyad],
                        "unassigned_hits": [int(hit["position"]) for hit in unassigned],
                    },
                ),
                _evidence(
                    "InterPro IPR001461",
                    "L2",
                    "Aspartic peptidase A1 family architecture and catalytic dyad",
                    _TIER_CAPS["motif"],
                ),
            ],
        },
        "ec": {
            "ec": "3.4.23.-",
            "name": "Aspartic endopeptidase",
            "confidence": _TIER_CAPS["motif"],
            "status": "motif-level family candidate; exact substrate specificity unresolved",
            "evidence_tier": "motif",
            "evidence": [
                _evidence("UniProt/Rhea-compatible family mapping", "L1/L2", "A1 aspartic peptidase activity", _TIER_CAPS["motif"])
            ],
        },
        "motifs": [
            {
                **hit,
                "role": (
                    "catalytic Asp motif"
                    if int(hit["position"]) in dyad_positions
                    else "motif occurrence outside the inferred dyad; not assigned catalytic"
                ),
                "source": "PROSITE PS00141 / InterPro IPR001461",
                "evidence_level": "L2",
                "dyad_member": int(hit["position"]) in dyad_positions,
            }
            for hit in motif_hits
        ],
        "key_residues": catalytic + flap_candidates,
    }


def _profile_other_sequence_clues(sequence: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return weak motif clues and non-confident family candidates."""
    motifs: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    gxsxg = _motif_hits(sequence, r"G.S.G")
    for hit in gxsxg[:8]:
        motifs.append({
            **hit,
            "role": "possible serine hydrolase motif",
            "source": "short motif heuristic",
            "evidence_level": "L5",
            "confidence": 0.25,
            "interpretation": "motif-only clue; not sufficient to call lipase/esterase",
        })
    if gxsxg:
        candidates.append({
            "name": "alpha/beta hydrolase-like serine hydrolase",
            "accession": None,
            "entry_type": "family",
            "confidence": 0.25,
            "status": "motif_only_unresolved",
            "evidence": [_evidence("short motif heuristic", "L5", "GXSXG-like motif", 0.25)],
        })

    return motifs, candidates


def _normalize_annotation_bundle(
    sequence: str,
    evidence_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Convert annotation_bundle's database-facing payload into profile evidence.

    Family identity and residue coordinates have different evidence requirements:
    a curated InterPro family call can identify a sequence even when a separately
    supplied sequence is not yet mapped to a UniProt record, while catalytic
    residue numbers may not be reused until that mapping is verified.
    """
    result: dict[str, Any] = {
        "family_candidates": [],
        "ec_candidates": [],
        "functional_domains": [],
        "key_residues": [],
        "evidence_table": [],
        "cofactors": [],
        "signal_peptide": None,
        "conflicts": [],
        "coordinate_status": "not_available",
        "has_curated_evidence": False,
    }
    coordinate = evidence_bundle.get("coordinate_system")
    if isinstance(coordinate, dict):
        result["coordinate_status"] = str(coordinate.get("status") or "not_available")

    interpro = evidence_bundle.get("interpro")
    annotations = interpro.get("annotations", []) if isinstance(interpro, dict) else []
    provenance = evidence_bundle.get("record_provenance")
    reviewed_record = bool(provenance.get("is_reviewed")) if isinstance(provenance, dict) else False
    record_source = (
        str(provenance.get("source_db") or "local_annotation_record")
        if isinstance(provenance, dict) else "local_annotation_record"
    )
    for annotation in annotations if isinstance(annotations, list) else []:
        if not isinstance(annotation, dict):
            continue
        source = str(annotation.get("source") or "annotation_bundle")
        entry_type = str(annotation.get("entry_type") or "").lower()
        name = str(annotation.get("name") or annotation.get("interpro_id") or "Unnamed annotation")
        is_curated = source.lower() not in {"heuristic", "short motif heuristic"}
        confidence = 0.90 if is_curated and entry_type == "family" else (
            0.60 if is_curated and entry_type == "homologous_superfamily" else (
                0.55 if is_curated and entry_type == "domain" else 0.25
            )
        )
        level = "L2" if is_curated else "L5"
        evidence = _evidence(
            f"{source}:{annotation.get('interpro_id') or name}",
            level,
            f"{entry_type or 'annotation'} annotation: {name}",
            confidence,
            details={
                "interpro_id": annotation.get("interpro_id"),
                "regions": annotation.get("regions") or (
                    [{"start": annotation.get("start_pos"), "end": annotation.get("end_pos")}]
                    if annotation.get("start_pos") or annotation.get("end_pos") else []
                ),
                "upstream_evidence": annotation.get("evidence"),
            },
        )
        result["evidence_table"].append(evidence)
        if is_curated:
            result["has_curated_evidence"] = True

        regions = annotation.get("regions")
        if not isinstance(regions, list):
            regions = [{"start": annotation.get("start_pos"), "end": annotation.get("end_pos")}]
        normalized_regions = [
            {"start": int(region["start"]), "end": int(region["end"])}
            for region in regions
            if isinstance(region, dict)
            and str(region.get("start") or "").isdigit()
            and str(region.get("end") or "").isdigit()
        ]
        if entry_type in {"domain", "homologous_superfamily"}:
            result["functional_domains"].append(
                {
                    "name": name,
                    "accession": annotation.get("interpro_id") or annotation.get("pfam_id"),
                    "type": entry_type,
                    "regions": normalized_regions,
                    "source": source,
                    "evidence_level": level,
                    "confidence": confidence,
                }
            )
        if entry_type in {"family", "homologous_superfamily"}:
            result["family_candidates"].append(
                {
                    "name": name,
                    "accession": annotation.get("interpro_id"),
                    "superfamily": name if entry_type == "homologous_superfamily" else None,
                    "entry_type": entry_type,
                    "confidence": _tiered_confidence("curated" if is_curated else "motif", confidence),
                    "source": source,
                    "status": "curated" if is_curated else "heuristic",
                    "evidence_tier": "curated" if is_curated else "motif",
                    "evidence": [evidence],
                }
            )

    protein = evidence_bundle.get("protein")
    if isinstance(protein, dict):
        ec_numbers = protein.get("ec_numbers", [])
        for ec in ec_numbers if isinstance(ec_numbers, list) else []:
            if not isinstance(ec, dict) or not ec.get("ec"):
                continue
            confidence = (0.96 if ec.get("primary") else 0.90) if reviewed_record else (
                0.84 if ec.get("primary") else 0.78
            )
            evidence = _evidence(
                f"{record_source}:{protein.get('uniprot_id') or 'annotation_record'}",
                "L1" if reviewed_record else "L2",
                f"Database EC assignment {ec['ec']}",
                confidence,
                details={
                    "primary": bool(ec.get("primary")),
                    "name": ec.get("name"),
                    "record_status": provenance.get("record_status") if isinstance(provenance, dict) else "unknown",
                },
            )
            result["ec_candidates"].append(
                {
                    "ec": ec["ec"],
                    "name": ec.get("name") or "Curated enzyme activity",
                    "confidence": confidence,
                    "status": "reviewed_record" if reviewed_record else "database_annotation",
                    "source": record_source,
                    "evidence": [evidence],
                }
            )
            result["evidence_table"].append(evidence)
        cofactors = protein.get("cofactors")
        if isinstance(cofactors, list):
            result["cofactors"] = cofactors
        elif cofactors:
            result["cofactors"] = [cofactors]

    catalytic = evidence_bundle.get("catalytic_sites")
    curated_sites = catalytic.get("curated_sites", []) if isinstance(catalytic, dict) else []
    coordinates_verified = result["coordinate_status"] == "verified"
    for site in curated_sites if isinstance(curated_sites, list) else []:
        if not isinstance(site, dict):
            continue
        source = str(site.get("source") or "curated_catalytic_site")
        for residue in site.get("residues", []) if isinstance(site.get("residues"), list) else []:
            if not isinstance(residue, dict):
                continue
            try:
                position = int(residue.get("position"))
            except (TypeError, ValueError):
                continue
            observed = sequence[position - 1] if 1 <= position <= len(sequence) else None
            curated_aa = str(residue.get("residue") or "").upper() or None
            aa_matches = curated_aa is None or curated_aa == observed
            status = "protected" if coordinates_verified and aa_matches else "protected_pending_numbering_confirmation"
            if curated_aa and observed and not aa_matches:
                result["conflicts"].append(
                    {
                        "type": "curated_residue_identity_mismatch",
                        "position": position,
                        "curated_residue": curated_aa,
                        "input_sequence_residue": observed,
                        "resolution": "Do not use this curated position for engineering until sequence mapping is resolved.",
                    }
                )
            evidence = _evidence(
                source,
                "L1" if reviewed_record else "L2",
                f"Curated catalytic residue: {residue.get('role') or 'functional residue'}",
                float(residue.get("confidence") or 0.9),
                details={
                    "mechanism_name": site.get("mechanism_name"),
                    "reaction_text": site.get("reaction_text"),
                    "coordinate_status": result["coordinate_status"],
                },
            )
            result["key_residues"].append(
                {
                    "position": position,
                    "residue": observed or curated_aa,
                    "role": str(residue.get("role") or "curated catalytic residue"),
                    "status": status,
                    "source": source,
                    "evidence": [evidence],
                }
            )
            result["evidence_table"].append(evidence)

    signal = evidence_bundle.get("signal_peptide")
    if isinstance(signal, dict):
        result["signal_peptide"] = {
            "has_signal_peptide": signal.get("has_signal_peptide"),
            "cleavage_site": signal.get("cleavage_site"),
            "confidence": signal.get("confidence"),
            "model": signal.get("model"),
            "evidence_level": "L1" if signal.get("cache", {}).get("source") == "database" else "L4",
        }
    return result


def enzyme_identity_profile(
    sequence: str,
    uniprot_id: str = "",
    structure_id: str = "",
    chain_id: str = "A",
    evidence_bundle: dict[str, Any] | None = None,
    structure_evidence: dict[str, Any] | None = None,
    residue_mapping: dict[str, Any] | None = None,
    template_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an evidence-gated enzyme identity profile from a protein sequence."""
    seq = "".join(sequence.split()).upper()
    if len(seq) < 10:
        raise ValueError(f"SEQUENCE_TOO_SHORT: {len(seq)} residues; minimum 10 required")
    invalid = sorted(set(seq) - _AA)
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(invalid)}")

    family_candidates: list[dict[str, Any]] = []
    ec_candidates: list[dict[str, Any]] = []
    motifs: list[dict[str, Any]] = []
    key_residues: list[dict[str, Any]] = []
    functional_domains: list[dict[str, Any]] = []
    cofactors: list[Any] = []
    signal_peptide: dict[str, Any] | None = None
    normalized_bundle: dict[str, Any] = {}
    missing_evidence: list[str] = []
    direct_structure_annotation: dict[str, Any] | None = None
    structure_ligands: list[dict[str, Any]] = []

    a1 = _profile_peptidase_a1(seq)
    if a1:
        family_candidates.append(a1["family"])
        ec_candidates.append(a1["ec"])
        motifs.extend(a1["motifs"])
        key_residues.extend(a1["key_residues"])

    weak_motifs, weak_families = _profile_other_sequence_clues(seq)
    motifs.extend(weak_motifs)
    family_candidates.extend({**entry, "evidence_tier": "motif"} for entry in weak_families)

    # annotation_bundle is the canonical upstream contract.  The older compact
    # family_candidates/key_residues shape remains supported for integrations.
    if evidence_bundle:
        normalized_bundle = _normalize_annotation_bundle(seq, evidence_bundle)
        family_candidates.extend(normalized_bundle["family_candidates"])
        ec_candidates.extend(normalized_bundle["ec_candidates"])
        key_residues.extend(normalized_bundle["key_residues"])
        functional_domains.extend(normalized_bundle["functional_domains"])
        cofactors.extend(normalized_bundle["cofactors"])
        signal_peptide = normalized_bundle["signal_peptide"]
        for entry in evidence_bundle.get("family_candidates", []):
            if isinstance(entry, dict):
                source = str(entry.get("source") or "supplied_evidence")
                # Caller-supplied candidates are only curated when they name a
                # database source; anything else stays at the motif tier.
                tier = "motif" if source.lower() in {"heuristic", "short motif heuristic", "supplied_evidence"} else "curated"
                family_candidates.append({
                    **entry,
                    "source": source,
                    "confidence": _tiered_confidence(tier, entry.get("confidence")),
                    "evidence_tier": tier,
                })
        for residue in evidence_bundle.get("key_residues", []):
            if isinstance(residue, dict):
                key_residues.append({**residue, "source": residue.get("source", "supplied_evidence")})

    query_annotation = (
        structure_evidence.get("query_rcsb_annotation")
        if isinstance(structure_evidence, dict) else None
    )
    query_hits = query_annotation.get("hits", []) if isinstance(query_annotation, dict) else []
    if isinstance(query_hits, list) and query_hits and isinstance(query_hits[0], dict):
        direct_structure_annotation = query_hits[0]
        entity_description = str(direct_structure_annotation.get("entity_description") or "").strip()
        title = str(direct_structure_annotation.get("title") or "").strip()
        identity_name = entity_description or title
        if identity_name:
            structure_identity_evidence = _evidence(
                f"RCSB query entry:{direct_structure_annotation.get('pdb_id') or structure_id}",
                "L1",
                f"Official PDB polymer identity: {identity_name}",
                0.95,
                details={
                    "title": title or None,
                    "entity_description": entity_description or None,
                    "reference_sequence_identifiers": direct_structure_annotation.get("reference_sequence_identifiers") or [],
                },
            )
            family_candidates.append({
                "name": identity_name,
                "accession": direct_structure_annotation.get("pdb_id") or structure_id,
                "entry_type": "family",
                "confidence": _tiered_confidence("curated", 0.95),
                "source": "RCSB query entry",
                "status": "direct_experimental_structure_identity",
                "evidence_tier": "curated",
                "evidence": [structure_identity_evidence],
            })
        structure_ligands = [
            item for item in direct_structure_annotation.get("nonpolymer_entities", [])
            if isinstance(item, dict)
        ]

        # Mutations encoded in an official PDB title describe the experimental
        # construct. Map author numbering to input-sequence numbering before
        # protecting the position from routine design.
        mapping_rows = residue_mapping.get("numbering_registry_rows", []) if isinstance(residue_mapping, dict) else []
        for wt, author_position_text, mutant in re.findall(r"\b([A-Z])(-?\d+)([A-Z])\b", title.upper()):
            author_position = int(author_position_text)
            source_position = None
            mapped_aa = None
            for row in mapping_rows if isinstance(mapping_rows, list) else []:
                if not isinstance(row, dict) or row.get("source_scheme") != "user_sequence":
                    continue
                try:
                    if int(row.get("target_position")) != author_position:
                        continue
                    source_position = int(row.get("source_position"))
                except (TypeError, ValueError):
                    continue
                mapped_aa = str(row.get("target_residue_aa") or "").upper()
                break
            if source_position and 1 <= source_position <= len(seq) and (not mapped_aa or mapped_aa == mutant):
                key_residues.append({
                    "position": source_position,
                    "residue": seq[source_position - 1],
                    "pdb_author_position": author_position,
                    "wild_type_residue": wt,
                    "construct_residue": mutant,
                    "role": "structure-reported construct substitution; protect pending WT functional review",
                    "status": "protected",
                    "source": "RCSB query entry title + exact input/PDB mapping",
                    "evidence": [_evidence(
                        f"RCSB query entry:{direct_structure_annotation.get('pdb_id') or structure_id}",
                        "L1",
                        f"Experimental construct reports {wt}{author_position}{mutant}",
                        0.98,
                    )],
                })

    template_basis: dict[str, Any] | None = None
    if isinstance(template_evidence, dict) and template_evidence.get("is_theoretical"):
        templates = [t for t in template_evidence.get("templates") or [] if isinstance(t, dict) and t.get("template_id")]
        identity_fraction = template_evidence.get("template_sequence_identity")
        coverage_fraction = template_evidence.get("template_coverage")
        try:
            identity_fraction = float(identity_fraction) if identity_fraction is not None else None
            coverage_fraction = float(coverage_fraction) if coverage_fraction is not None else None
        except (TypeError, ValueError):
            identity_fraction = coverage_fraction = None
        template_basis = {
            "source": str(template_evidence.get("source") or "theoretical model"),
            "templates": [str(t.get("template_id")) for t in templates],
            "template_sequence_identity": identity_fraction,
            "template_coverage": coverage_fraction,
            "gmqe": template_evidence.get("gmqe"),
            "qmean": template_evidence.get("qmean"),
            "qmean_z": template_evidence.get("qmean_z"),
            "status": "insufficient",
        }
        if templates:
            # A homology model is evidence that the target resembles its
            # template, never proof it is the same protein: confidence is
            # computed from identity/coverage and capped well below curated
            # family calls so downstream gates can weigh the basis.
            confidence = 0.0
            if identity_fraction is not None:
                confidence = min(0.75, max(0.55, round(identity_fraction, 3)))
            calls_family = identity_fraction is not None and identity_fraction >= 0.7 and (
                coverage_fraction is None or coverage_fraction >= 0.8
            )
            for template in templates:
                template_id = str(template.get("template_id"))
                evidence = _evidence(
                    f"theoretical model template:{template_id}",
                    "L3",
                    f"Homology model built on template {template_id} "
                    f"(identity={identity_fraction}, coverage={coverage_fraction})",
                    confidence,
                    details={
                        "template_id": template_id,
                        "template_sequence_identity": identity_fraction,
                        "template_coverage": coverage_fraction,
                        "gmqe": template_basis["gmqe"],
                        "qmean": template_basis["qmean"],
                    },
                )
                if calls_family:
                    family_candidates.append({
                        "name": f"Template-implied family ({template_id})",
                        "accession": template_id,
                        "superfamily": None,
                        "entry_type": "family",
                        "confidence": _tiered_confidence("template", confidence),
                        "source": template_basis["source"],
                        "status": "template_homology",
                        "evidence_tier": "template",
                        "evidence": [evidence],
                    })
                    template_basis["status"] = "qualifies"
                template_basis.setdefault("evidence", []).append(evidence)
            if not calls_family:
                template_basis["status"] = "below_threshold"

    family_candidates.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)

    ec_candidates.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)

    # Single identity resolution: a candidate qualifies only when its evidence
    # tier is eligible AND its (capped) confidence reaches the threshold.  The
    # tier check is what stops a heuristic from ever naming an identity, no
    # matter what score the producer declares for it.
    top_family = next(
        (
            item for item in family_candidates
            if item.get("entry_type") == "family"
            and item.get("evidence_tier") in _QUALIFYING_TIERS
            and float(item.get("confidence", 0.0)) >= _IDENTITY_THRESHOLD
        ),
        None,
    )
    motif_family = next(
        (item for item in family_candidates if item.get("evidence_tier") == "motif"),
        None,
    )
    if top_family is not None:
        identity_status = "identified"
        identity_basis = "template_homology" if top_family.get("evidence_tier") == "template" else "curated_family"
    elif motif_family is not None:
        identity_status = "candidate"
        identity_basis = "motif_heuristic"
    else:
        identity_status = "unresolved"
        identity_basis = "none"
    if identity_basis != "curated_family" and not normalized_bundle.get("has_curated_evidence"):
        missing_evidence.append("No direct InterProScan/Pfam/HMMER result was supplied for this sequence.")
    if template_basis is not None:
        if template_basis["status"] == "below_threshold":
            missing_evidence.append(
                "Homology-model template identity/coverage is below the family-call threshold "
                "(identity >= 0.7 and coverage >= 0.8); template similarity supports a family candidate, not an identity call."
            )
        elif template_basis["status"] == "qualifies":
            missing_evidence.append(
                "Family identity rests on theoretical-model template homology; confirm the target protein record "
                "(UniProt accession or experimental structure cross-reference) before treating it as curated family evidence."
            )
        if not template_basis.get("templates"):
            missing_evidence.append("The theoretical model declares no parsable template identifier; identity must come from sequence-level search.")
    if not uniprot_id:
        missing_evidence.append("No UniProt accession was supplied; curated protein-level feature evidence is unavailable.")
    if not structure_id:
        missing_evidence.append("No structure identifier was supplied; residue exposure and pocket geometry remain unverified.")
    if any(item.get("evidence_level") == "L5" for item in motifs):
        missing_evidence.append("Short motif hits require family/domain or homolog confirmation before functional claims.")

    protected_positions = sorted({
        int(item["position"])
        for item in key_residues
        if item.get("status") == "protected" and str(item.get("position", "")).isdigit()
    })
    evidence_table: list[dict[str, Any]] = []
    for item in family_candidates:
        evidence_table.extend(item.get("evidence", []))
    for item in ec_candidates:
        evidence_table.extend(item.get("evidence", []))
    for item in motifs:
        if item.get("evidence_level") == "L5":
            evidence_table.append(_evidence("short motif heuristic", "L5", item["interpretation"], item["confidence"]))
    evidence_table.extend(normalized_bundle.get("evidence_table", []))
    if template_basis is not None:
        evidence_table.extend(template_basis.get("evidence", []))

    conflicts = []
    best_family = next(
        (item for item in family_candidates if item.get("entry_type") == "family" and item.get("evidence_tier") != "motif"),
        motif_family,
    )
    if best_family and any(candidate.get("name", "").lower().find("hydrolase") >= 0 for candidate in family_candidates[1:]):
        competing = next(candidate for candidate in family_candidates[1:] if "hydrolase" in candidate.get("name", "").lower())
        dominant = best_family.get("evidence_tier") == "curated"
        conflicts.append({
            "type": "family_evidence_conflict",
            "resolution": (
                "Curated/domain-level A1 evidence outranks motif-only serine hydrolase clue."
                if dominant
                else "Motif-level clues disagree on family; neither may name the protein until a curated domain/family source resolves it."
            ),
        })

    coordinate_status = normalized_bundle.get("coordinate_status")
    mapping_status = residue_mapping.get("numbering_registry_status") if isinstance(residue_mapping, dict) else None
    # Coordinate-order numbering is useful for local reasoning, but it is not
    # external annotation evidence. Only an explicitly verified coordinate
    # mapping may unlock the verified status used by candidate gating.
    if mapping_status == "ready":
        numbering_status = "verified_for_input_sequence"
    elif mapping_status in {"uniprot_only_requires_input_alignment", "inferred_requires_confirmation"}:
        numbering_status = "inferred_for_input_sequence"
    elif coordinate_status == "mapping_required":
        numbering_status = "external_annotation_mapping_required"
    elif not evidence_bundle or coordinate_status == "verified":
        numbering_status = "verified_for_input_sequence"
    else:
        numbering_status = "inferred_for_input_sequence"
    guardrail_ready = identity_status == "identified" and numbering_status == "verified_for_input_sequence"

    return {
        "profile_version": "1.1",
        "query": {
            "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest(),
            "sequence_length": len(seq),
            "uniprot_id": uniprot_id or None,
            "structure_id": structure_id or None,
            "chain_id": chain_id or "A",
            "coordinate_system": "input_sequence",
            "template_frame": "isolated" if template_basis is not None else None,
        },
        "identity_status": identity_status,
        "identity_basis": identity_basis,
        "template_evidence": template_basis,
        "family_candidates": family_candidates,
        "ec_candidates": ec_candidates,
        "functional_domains": functional_domains,
        "motifs": motifs,
        "key_residues": key_residues,
        "protected_positions": protected_positions,
        "cofactors": cofactors,
        "signal_peptide": signal_peptide,
        "numbering": {
            "coordinate_system": "input_sequence",
            "mapping_basis": (
                "exact input sequence matched to PDB author coordinates"
                if mapping_status == "ready"
                else "annotation_bundle curated record matched to input sequence"
                if coordinate_status == "verified"
                else "sequence positions; structure/UniProt mapping not supplied"
                if not evidence_bundle else "curated annotation coordinates require mapping to input sequence"
            ),
            "status": numbering_status,
        },
        "direct_structure_annotation": direct_structure_annotation,
        "structure_ligands": structure_ligands,
        "evidence_table": evidence_table,
        "confidence_summary": {
            "family": float(top_family.get("confidence", 0.0)) if top_family else 0.0,
            "ec": float(ec_candidates[0].get("confidence", 0.0)) if ec_candidates else 0.0,
            "catalytic_sites": round(
                min(1.0, sum(1 for item in key_residues if item.get("role", "").startswith("catalytic")) / 2),
                3,
            ),
        },
        "conflicts": conflicts,
        "missing_evidence": missing_evidence,
        "guardrail": {
            "status": "ready" if guardrail_ready else "blocked",
            "rule": (
                "Do not promote motif-only or unresolved identity results to P1 mutation candidates; "
                "do not use external curated residue numbers until sequence mapping is verified."
            ),
        },
    }


ToolRegistry.register(
    name="enzyme_identity_profile",
    description=(
        "Build an evidence-gated enzyme identity profile before engineering. "
        "Returns family candidates, EC candidates, conserved motifs, catalytic/key "
        "residues, protected positions, numbering status, evidence conflicts, and "
        "missing evidence. Short motifs are not sufficient for a family call."
    ),
    handler=enzyme_identity_profile,
    category="analysis",
    timeout_seconds=60,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino acid sequence"},
            "uniprot_id": {"type": "string", "description": "Optional UniProt accession"},
            "structure_id": {"type": "string", "description": "Optional PDB or uploaded structure identifier"},
            "chain_id": {"type": "string", "description": "Structure chain identifier"},
            "evidence_bundle": {"type": "object", "description": "Optional curated evidence payload"},
            "structure_evidence": {"type": "object", "description": "Optional structure_search_foldseek payload, including direct query-entry annotation."},
            "residue_mapping": {"type": "object", "description": "Optional residue_mapping_sifts payload for coordinate guardrails."},
            "template_evidence": {
                "type": "object",
                "description": (
                    "Optional theoretical/homology model header evidence (templates, "
                    "template_sequence_identity, template_coverage, GMQE/QMEAN). Used as a "
                    "capped template_homology identity basis, never as curated annotation."
                ),
            },
        },
        "required": ["sequence"],
    },
    errors=[
        {
            "reason": "invalid_input",
            "code": "SEQUENCE_TOO_SHORT",
            "when": "sequence length < 10 residues",
            "recovery": "Provide a complete protein sequence.",
        },
        {
            "reason": "validation_failed",
            "code": "INVALID_AA",
            "when": "sequence contains non-standard amino-acid symbols",
            "recovery": "Remove FASTA headers and non-amino-acid characters, then retry.",
        },
    ],
)
