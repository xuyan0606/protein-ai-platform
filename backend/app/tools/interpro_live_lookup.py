"""Tool wrapper for live InterPro lookup."""

from __future__ import annotations

from app.services.evidence_source_status import evidence_source_status
from app.services.interpro_live import InterProLiveClient
from app.tools.registry import ToolRegistry


def _clean(value: str | None) -> str:
    return (value or "").strip()


async def interpro_live_lookup(
    uniprot_id: str = "",
    sequence: str = "",
    max_results: int = 50,
) -> dict[str, Any]:
    """Query live InterPro API for a UniProt accession.

    Sequence-only InterProScan submission is intentionally not implemented in
    this synchronous MVP; returning blocked is more accurate than pretending a
    UniProt-entry lookup covers arbitrary sequences.
    """

    accession = _clean(uniprot_id)
    seq = _clean(sequence)
    try:
        limit = max(1, min(int(max_results or 50), 200))
    except (TypeError, ValueError):
        limit = 50

    if not accession:
        return {
            "status": "blocked",
            "found": False,
            "query": {"uniprot_id": None, "sequence_length": len(seq) if seq else 0},
            "results_count": 0,
            "results": [],
            "evidence_source": evidence_source_status(
                source="InterPro API",
                status="blocked",
                mode="input_or_runtime_blocked",
                live_query_executed=False,
                reason=(
                    "MISSING_UNIPROT_ID: InterPro live lookup currently requires a UniProt accession. "
                    "Sequence-only InterProScan submission is not enabled in this synchronous tool."
                ),
            ),
        }

    client = InterProLiveClient(enabled=True)
    payload = await client.resolve_annotations(sequence=seq, uniprot_id=accession)
    evidence = payload.get("evidence_source") if isinstance(payload.get("evidence_source"), dict) else {}
    annotations = payload.get("annotations") if isinstance(payload.get("annotations"), list) else []
    return {
        **payload,
        "status": "completed" if evidence.get("status") == "live" else "blocked",
        "results_count": len(annotations[:limit]),
        "results": annotations[:limit],
    }


ToolRegistry.register(
    name="interpro_live_lookup",
    description=(
        "Live InterPro API lookup for UniProt accessions. Returns InterPro "
        "family/domain/site entries with evidence source status. Sequence-only "
        "InterProScan submission is not enabled in this synchronous MVP."
    ),
    handler=interpro_live_lookup,
    is_async=True,
    category="data",
    timeout_seconds=30,
    parameters={
        "type": "object",
        "properties": {
            "uniprot_id": {"type": "string", "description": "UniProt accession to query in InterPro."},
            "sequence": {
                "type": "string",
                "description": "Optional protein sequence for length tracking; not used for live InterProScan.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 50,
                "description": "Maximum number of InterPro matches to return.",
            },
        },
    },
    errors=[
        {
            "reason": "invalid_input",
            "code": "MISSING_UNIPROT_ID",
            "when": "uniprot_id is empty",
            "recovery": "Provide a UniProt accession, or use local annotation_bundle for sequence-only fallback.",
        },
        {
            "reason": "connection_error",
            "code": "INTERPRO_LIVE_LOOKUP_DEGRADED",
            "when": "InterPro API request fails",
            "recovery": "Retry later, check accession validity, or use local annotation_bundle as degraded evidence.",
        },
    ],
)
