"""BLAST sequence search via NCBI BLAST+ REST API with polling and XML parsing.

Dedicated BLAST tool separate from sequence_search — this one is focused on
raw BLAST with full control over program, database, and result parsing.

Supports: blastp, blastx, tblastn, blastn
Databases: nr, swissprot, pdb, refseq_protein
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from app.core.config import settings
from app.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_BLAST_SUBMIT_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
_POLL_INITIAL = 3.0
_POLL_MAX = 60.0
_POLL_BACKOFF = 1.5
_MAX_POLL_ATTEMPTS = 30

# Valid program / database combos
_VALID_PROGRAMS = {"blastp", "blastx", "tblastn", "blastn"}
_VALID_DATABASES = {"nr", "swissprot", "pdb", "refseq_protein"}

# Database -> BLAST PUT database parameter mapping
_DATABASE_MAP: dict[str, str] = {
    "nr": "nr",
    "swissprot": "swissprot",
    "pdb": "pdb",
    "refseq_protein": "refseq_protein",
}


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------

def _tag_text(block: str, tag: str) -> str | None:
    """Extract text content of an XML tag (first occurrence in block)."""
    # Try <tag>value</tag>
    ot = f"<{tag}>"
    ct = f"</{tag}>"
    start = block.find(ot)
    if start != -1:
        end = block.find(ct, start)
        if end != -1:
            return block[start + len(ot):end].strip()

    # Try <tag ...>value</tag> (tag with attributes)
    pattern = rf"<{tag}\b[^>]*>(.*?)</{tag}>"
    m = re.search(pattern, block, re.DOTALL)
    if m:
        return m.group(1).strip()

    return None


def _parse_blast_xml_full(xml: str, max_hits: int) -> list[dict[str, Any]]:
    """Parse BLAST XML into a list of structured hit dicts."""
    hits: list[dict[str, Any]] = []

    # Split by <Hit> blocks
    hit_blocks = re.split(r"<Hit>", xml)
    if len(hit_blocks) < 2:
        return hits

    # Extract iteration-level stats
    iter_block = xml

    for block in hit_blocks[1:]:  # skip preamble before first <Hit>
        hit_num_str = _tag_text(block, "Hit_num")
        hit_id = _tag_text(block, "Hit_id") or ""
        hit_def = _tag_text(block, "Hit_def") or ""
        hit_acc = _tag_text(block, "Hit_accession") or ""
        hit_len_str = _tag_text(block, "Hit_len")

        # Collect all HSPs for this hit
        hsp_blocks = re.split(r"<Hsp>", block)
        hsps: list[dict] = []

        for hsp_block in hsp_blocks[1:]:
            hsp_num = _tag_text(hsp_block, "Hsp_num")
            hsp_bit = _tag_text(hsp_block, "Hsp_bit-score")
            hsp_score = _tag_text(hsp_block, "Hsp_score")
            hsp_evalue = _tag_text(hsp_block, "Hsp_evalue")
            hsp_query_from = _tag_text(hsp_block, "Hsp_query-from")
            hsp_query_to = _tag_text(hsp_block, "Hsp_query-to")
            hsp_hit_from = _tag_text(hsp_block, "Hsp_hit-from")
            hsp_hit_to = _tag_text(hsp_block, "Hsp_hit-to")
            hsp_identity = _tag_text(hsp_block, "Hsp_identity")
            hsp_positive = _tag_text(hsp_block, "Hsp_positive")
            hsp_gaps = _tag_text(hsp_block, "Hsp_gaps")
            hsp_align_len = _tag_text(hsp_block, "Hsp_align-len")
            hsp_qseq = _tag_text(hsp_block, "Hsp_qseq")
            hsp_hseq = _tag_text(hsp_block, "Hsp_hseq")
            hsp_midline = _tag_text(hsp_block, "Hsp_midline")

            align_len = int(hsp_align_len) if hsp_align_len else 0
            identity = int(hsp_identity) if hsp_identity else 0
            positive = int(hsp_positive) if hsp_positive else 0
            gaps = int(hsp_gaps) if hsp_gaps else 0

            hsps.append({
                "hsp_num": int(hsp_num) if hsp_num else 1,
                "bit_score": float(hsp_bit) if hsp_bit else 0.0,
                "score": int(hsp_score) if hsp_score else 0,
                "e_value": hsp_evalue or "N/A",
                "query_from": int(hsp_query_from) if hsp_query_from else 0,
                "query_to": int(hsp_query_to) if hsp_query_to else 0,
                "hit_from": int(hsp_hit_from) if hsp_hit_from else 0,
                "hit_to": int(hsp_hit_to) if hsp_hit_to else 0,
                "identity": identity,
                "positive": positive,
                "gaps": gaps,
                "alignment_length": align_len,
                "identity_percent": round(identity / align_len * 100, 1) if align_len else 0.0,
                "query_seq": hsp_qseq or "",
                "hit_seq": hsp_hseq or "",
                "midline": hsp_midline or "",
            })

        # Extract organism from defline: "... [Organism Name]"
        organism = "Unknown"
        bracket = hit_def.rfind("[")
        if bracket != -1:
            organism = hit_def[bracket + 1:].rstrip("]").strip()

        # Best identity from best HSP
        best_identity = 0.0
        best_evalue = "N/A"
        if hsps:
            best_hsp = hsps[0]
            best_identity = best_hsp["identity_percent"]
            best_evalue = best_hsp["e_value"]

        hits.append({
            "hit_num": int(hit_num_str) if hit_num_str else 0,
            "accession": hit_acc,
            "id": hit_id,
            "definition": hit_def,
            "organism": organism,
            "hit_length": int(hit_len_str) if hit_len_str else 0,
            "best_identity_percent": best_identity,
            "best_e_value": best_evalue,
            "hsps": hsps[:3],  # top 3 HSPs only
            "total_hsps": len(hsps),
        })

        if len(hits) >= max_hits:
            break

    return hits


# ---------------------------------------------------------------------------
# BLAST runner
# ---------------------------------------------------------------------------

async def _run_blast(
    sequence: str,
    program: str,
    database: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Submit a BLAST job, poll until complete, parse results."""

    blast_db = _DATABASE_MAP.get(database, database)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        # --- Submit ---
        submit_params: dict[str, str] = {
            "CMD": "Put",
            "PROGRAM": program,
            "DATABASE": blast_db,
            "QUERY": sequence,
            "FORMAT_TYPE": "XML",
            "HITLIST_SIZE": str(max_results),
            "ALIGNMENTS": str(max_results),
            "DESCRIPTIONS": str(max_results),
        }
        if settings.NCBI_API_KEY:
            submit_params["NCBI_API_KEY"] = settings.NCBI_API_KEY

        submit_resp = await client.post(_BLAST_SUBMIT_URL, data=submit_params)
        submit_resp.raise_for_status()
        body = submit_resp.text

        # Check for rate limit / errors
        if "Message ID#24" in body or "too many" in body.lower():
            retry_after = submit_resp.headers.get("Retry-After", "30")
            raise RuntimeError(
                f"RATE_LIMITED: NCBI BLAST rate limit exceeded. "
                f"Retry-After: {retry_after}s. Set NCBI_API_KEY for higher quotas."
            )

        # Extract RID
        rid_match = re.search(r"RID\s*=\s*(\S+)", body)
        if not rid_match:
            raise RuntimeError(
                "BLAST_FAILED: Could not extract Request ID (RID) from submission. "
                f"Response preview: {body[:300]}"
            )
        rid = rid_match.group(1)

        # Extract RTOE (estimated time)
        rtoe_match = re.search(r"RTOE\s*=\s*(\d+)", body)
        rtoe = int(rtoe_match.group(1)) if rtoe_match else 30

    # --- Poll ---
    delay = _POLL_INITIAL
    for attempt in range(1, _MAX_POLL_ATTEMPTS + 1):
        await asyncio.sleep(delay)

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            poll_params = {
                "CMD": "Get",
                "RID": rid,
                "FORMAT_TYPE": "XML",
            }
            poll_resp = await client.get(_BLAST_SUBMIT_URL, params=poll_params)
            text = poll_resp.text

        # Check for completion
        if "Status=READY" in text:
            # Check if there are no hits
            if "<Hit>" not in text:
                return []
            return _parse_blast_xml_full(text, max_results)

        if "Status=FAILED" in text:
            error_msg = _tag_text(text, "error") or "Unknown BLAST error"
            raise RuntimeError(f"BLAST_FAILED: job RID={rid} failed: {error_msg}")

        # Exponential backoff
        delay = min(delay * _POLL_BACKOFF, _POLL_MAX)

    raise TimeoutError(
        f"BLAST_TIMEOUT: Job RID={rid} exceeded {_MAX_POLL_ATTEMPTS} polling "
        f"attempts (~{_MAX_POLL_ATTEMPTS * _POLL_MAX}s). Query may be too complex "
        "or NCBI servers overloaded. Retry with a shorter sequence."
    )


# ===================================================================
# Main blast_search
# ===================================================================

async def blast_search(
    sequence: str,
    program: str = "blastp",
    database: str = "nr",
    max_results: int = 10,
) -> dict:
    """Run NCBI BLAST search with polling and XML result parsing.

    Args:
        sequence: Query sequence (amino-acid for blastp/tblastn,
                  nucleotide for blastx/blastn).
        program: BLAST program — "blastp", "blastx", "tblastn", or "blastn".
        database: Target database — "nr", "swissprot", "pdb", "refseq_protein".
        max_results: Maximum number of hit descriptions/alignments.

    Returns:
        Dict with query info and list of BLASTHit results.
    """
    seq = sequence.strip().upper()
    if not seq:
        raise ValueError("EMPTY_SEQUENCE: sequence must not be empty")

    if program not in _VALID_PROGRAMS:
        raise ValueError(
            f"INVALID_PROGRAM: '{program}'. Must be one of: {_VALID_PROGRAMS}"
        )

    if database not in _VALID_DATABASES:
        raise ValueError(
            f"INVALID_DATABASE: '{database}'. Must be one of: {_VALID_DATABASES}"
        )

    if len(seq) < 5:
        raise ValueError(
            "SEQUENCE_TOO_SHORT: BLAST requires at least 5 residues for meaningful results"
        )

    hits = await _run_blast(
        sequence=seq,
        program=program,
        database=database,
        max_results=max_results,
    )

    return {
        "query_length": len(seq),
        "program": program,
        "database": database,
        "results_count": len(hits),
        "query_preview": seq[:80] + ("..." if len(seq) > 80 else ""),
        "results": hits,
    }


# ===================================================================
# Registration
# ===================================================================

ToolRegistry.register(
    name="blast_search",
    description=(
        "Run NCBI BLAST sequence alignment (blastp, blastx, tblastn, blastn) "
        "against protein databases (nr, swissprot, pdb, refseq_protein). "
        "Polls NCBI servers with exponential backoff and returns structured "
        "alignment results with e-values, identities, and organism info."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Query sequence (amino acid for blastp, nucleotide for blastn/blastx)",
            },
            "program": {
                "type": "string",
                "enum": ["blastp", "blastx", "tblastn", "blastn"],
                "description": "BLAST program to use",
                "default": "blastp",
            },
            "database": {
                "type": "string",
                "enum": ["nr", "swissprot", "pdb", "refseq_protein"],
                "description": "Database to search against",
                "default": "nr",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of results to return",
                "default": 10,
            },
        },
        "required": ["sequence"],
    },
    handler=blast_search,
    is_async=True,
    category="search",
    timeout_seconds=600,
    errors=[
        {
            "reason": "invalid_input",
            "code": "EMPTY_SEQUENCE",
            "when": "sequence is empty or whitespace-only",
            "recovery": "Provide a valid amino acid or nucleotide sequence.",
        },
        {
            "reason": "invalid_input",
            "code": "SEQUENCE_TOO_SHORT",
            "when": "sequence length is < 5 residues",
            "recovery": "Provide at least 5 residues for meaningful BLAST results.",
        },
        {
            "reason": "invalid_input",
            "code": "INVALID_PROGRAM",
            "when": "BLAST program is not one of: blastp, blastx, tblastn, blastn",
            "recovery": "Choose a valid BLAST program type.",
        },
        {
            "reason": "invalid_input",
            "code": "INVALID_DATABASE",
            "when": "database is not one of: nr, swissprot, pdb, refseq_protein",
            "recovery": "Choose a valid NCBI database.",
        },
        {
            "reason": "connection_error",
            "code": "BLAST_FAILED",
            "when": "NCBI BLAST submission or processing failed",
            "recovery": (
                "Check the sequence is appropriate for the selected program. "
                "For nucleotide queries with blastp, use blastx or tblastn instead."
            ),
        },
        {
            "reason": "timeout",
            "code": "BLAST_TIMEOUT",
            "when": "BLAST job did not complete within the polling window",
            "recovery": (
                "Try a shorter query sequence, restrict the database to swissprot "
                "for faster results, or retry later."
            ),
        },
        {
            "reason": "rate_limited",
            "code": "RATE_LIMITED",
            "when": "NCBI rate limit exceeded (HTTP 429 or Message ID#24)",
            "recovery": (
                "Wait and retry. Set NCBI_API_KEY in config for higher rate limits "
                "(10x higher with API key)."
            ),
        },
    ],
)
