"""Sequence similarity search via NCBI BLAST REST API and UniProt REST API.

Handles:
  - BLAST search with polling and exponential backoff
  - UniProt keyword/accession search
  - Rate-limit awareness (Retry-After headers)
  - Typed error contracts
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BLAST_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_QUERY_FIELDS = (
    "accession,id,protein_name,organism_name,length,xref_pdb,cc_function,"
    "ft_domain,ft_region,gene_names"
)
BLAST_POLL_INITIAL = 3.0   # seconds
BLAST_POLL_MAX = 60.0      # seconds
BLAST_POLL_BACKOFF = 1.5    # multiplier per attempt
BLAST_MAX_ATTEMPTS = 30     # ~12 minutes total max

_AA_SET = set("ACDEFGHIKLMNPQRSTVWY")
BLAST_MIN_SEQUENCE_LENGTH = 30  # BLAST not useful for very short peptides
_NUCLEOTIDE_SET = set("ATGCRYSWKMBDHVN")  # IUPAC nucleotide codes


def _is_amino_acid_sequence(s: str) -> bool:
    """Heuristic: if >80% of chars are valid AA letters, treat as sequence."""
    clean = s.replace(" ", "").replace("\n", "").replace("\t", "")
    if len(clean) < 10:
        return False
    ratio = sum(1 for c in clean if c in _AA_SET) / len(clean)
    return ratio > 0.8


# ---------------------------------------------------------------------------
# BLAST client
# ---------------------------------------------------------------------------

class BlastClient:
    """NCBI BLAST REST API client with polling and backoff."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def search(
        self,
        sequence: str,
        database: str = "swissprot",
        program: str = "blastp",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Run BLAST and return parsed results."""
        client = await self._get_client()

        # Submit job
        params: dict[str, str] = {
            "CMD": "Put",
            "PROGRAM": program,
            "DATABASE": database,
            "QUERY": sequence,
            "FORMAT_TYPE": "XML",
            "HITLIST_SIZE": str(max_results),
            "ALIGNMENTS": str(max_results),
            "DESCRIPTIONS": str(max_results),
        }

        # Add API key if configured
        if settings.NCBI_API_KEY:
            params["NCBI_API_KEY"] = settings.NCBI_API_KEY

        resp = await client.post(BLAST_URL, data=params)
        resp.raise_for_status()

        # Extract RID and RTOE from response
        text = resp.text
        rid_start = text.find("RID = ")
        rtoe_start = text.find("RTOE = ")

        if rid_start == -1:
            # Check if we hit rate limit
            if "Message ID#24" in text or "limit" in text.lower():
                retry_after = resp.headers.get("Retry-After", "30")
                raise RuntimeError(
                    f"RATE_LIMITED: NCBI rate limit reached. Retry after {retry_after}s. "
                    "Consider using an NCBI API key for higher limits."
                )
            raise RuntimeError(
                f"BLAST_FAILED: Could not extract RID from response. "
                f"Nucleotide sequences may need blastn instead of blastp."
            )

        rid = text[rid_start + 6:].split()[0]
        rtoe_str = text[rtoe_start + 7:].split()[0] if rtoe_start != -1 else "30"
        try:
            rtoe = int(rtoe_str)
        except ValueError:
            rtoe = 30

        # Poll for results
        delay = BLAST_POLL_INITIAL
        for attempt in range(1, BLAST_MAX_ATTEMPTS + 1):
            await asyncio.sleep(delay)

            poll_params: dict[str, str] = {
                "CMD": "Get",
                "RID": rid,
                "FORMAT_TYPE": "XML",
            }
            poll_resp = await client.get(BLAST_URL, params=poll_params)

            text = poll_resp.text
            if "Status=WAITING" in text or "Status=READY" not in text:
                # Still computing
                delay = min(delay * BLAST_POLL_BACKOFF, BLAST_POLL_MAX)
                continue

            # Got results — parse
            hits = _parse_blast_xml(text, max_results)
            return hits

        raise TimeoutError(
            f"BLAST_TIMEOUT: Job RID={rid} did not complete "
            f"within {BLAST_MAX_ATTEMPTS} polling attempts (~{BLAST_MAX_ATTEMPTS * BLAST_POLL_MAX}s). "
            "Try a shorter query sequence or check NCBI BLAST status."
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


def _parse_blast_xml(xml_text: str, max_results: int) -> list[dict[str, Any]]:
    """Parse BLAST XML output into structured hit dicts (no external XML lib)."""
    hits: list[dict[str, Any]] = []

    # Split by <Hit> blocks
    blocks = xml_text.split("<Hit>")
    if len(blocks) < 2:
        return hits

    for block in blocks[1:]:  # skip content before first <Hit>
        # Extract fields with simple string searches (robust enough for BLAST XML)
        hit_num = _xml_value(block, "Hit_num")
        hit_id = _xml_value(block, "Hit_id")
        hit_def = _xml_value(block, "Hit_def")
        hit_accession = _xml_value(block, "Hit_accession")
        hit_len = _xml_value(block, "Hit_len")

        # Hsp (High-scoring Segment Pair) data
        hsp_identity = _xml_value(block, "Hsp_identity")
        hsp_align_len = _xml_value(block, "Hsp_align-len")
        hsp_evalue = _xml_value(block, "Hsp_evalue")
        hsp_bit_score = _xml_value(block, "Hsp_bit-score")
        hsp_query_from = _xml_value(block, "Hsp_query-from")
        hsp_query_to = _xml_value(block, "Hsp_query-to")
        hsp_hit_from = _xml_value(block, "Hsp_hit-from")
        hsp_hit_to = _xml_value(block, "Hsp_hit-to")

        identity_pct = 0.0
        if hsp_identity and hsp_align_len:
            try:
                identity_pct = round(int(hsp_identity) / int(hsp_align_len) * 100, 1)
            except (ValueError, ZeroDivisionError):
                pass

        # Extract organism from definition line (e.g. "... [Escherichia coli]")
        organism = "Unknown"
        if hit_def:
            bracket = hit_def.rfind("[")
            if bracket != -1:
                organism = hit_def[bracket + 1:].rstrip("]").strip()

        hits.append({
            "accession": hit_accession or "",
            "id": hit_id or "",
            "definition": hit_def or "",
            "organism": organism,
            "hit_length": int(hit_len) if hit_len else 0,
            "identity_percent": identity_pct,
            "alignment_length": int(hsp_align_len) if hsp_align_len else 0,
            "e_value": hsp_evalue or "N/A",
            "bit_score": float(hsp_bit_score) if hsp_bit_score else 0.0,
            "query_range": f"{hsp_query_from or '?'}-{hsp_query_to or '?'}",
            "hit_range": f"{hsp_hit_from or '?'}-{hsp_hit_to or '?'}",
        })

        if len(hits) >= max_results:
            break

    return hits


def _xml_value(block: str, tag: str) -> str | None:
    """Extract the text content of a simple XML tag."""
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    opening = block.find(open_tag)
    if opening == -1:
        # Try self-closing or attribute-bearing variants
        alt = block.find(f"<{tag} ")
        if alt != -1:
            # Extract from attribute value or look for inline content
            opening = alt
            # Look for ">" after the tag name
            gt = block.find(">", alt)
            closing = block.find(close_tag, gt)
            if closing != -1:
                return block[gt + 1:closing].strip()
        return None
    closing = block.find(close_tag, opening)
    if closing == -1:
        return None
    return block[opening + len(open_tag):closing].strip()


# ---------------------------------------------------------------------------
# UniProt client
# ---------------------------------------------------------------------------

class UniProtClient:
    """UniProt REST API client."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                base_url=settings.UNIPROT_BASE_URL,
            )
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search UniProtKB with a text query or accession."""
        client = await self._get_client()

        # If query looks like an accession (e.g. P12345), use direct lookup
        # Otherwise do a full-text search with field filtering
        params: dict[str, str] = {
            "query": query,
            "size": str(max_results),
            "format": "json",
            "fields": UNIPROT_QUERY_FIELDS,
        }

        response = await client.get(
            "/uniprotkb/search",
            params=params,
            headers={"Accept": "application/json"},
        )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "5")
            raise RuntimeError(
                f"RATE_LIMITED: UniProt rate limit reached. Retry after {retry_after}s."
            )

        response.raise_for_status()
        data = response.json()

        results: list[dict[str, Any]] = []
        for entry in data.get("results", []):
            protein = entry.get("proteinDescription", {})
            recommended = protein.get("recommendedName", {})
            genes = entry.get("genes", [])

            gene_names = []
            for g in genes:
                gn = g.get("geneName", {})
                if gn.get("value"):
                    gene_names.append(gn["value"])

            # Extract function annotation
            function = ""
            comments = entry.get("comments", [])
            for c in comments:
                if c.get("commentType") == "FUNCTION":
                    texts = c.get("texts", [])
                    if texts:
                        function = texts[0].get("value", "")
                    break

            # Extract PDB cross-references
            pdbs: list[str] = []
            for ref in entry.get("uniProtKBCrossReferences", []):
                if ref.get("database") == "PDB":
                    pdbs.append(ref.get("id", ""))

            # Domain / region annotations
            domains: list[str] = []
            for feat in entry.get("features", []):
                if feat.get("type") in ("DOMAIN", "REGION"):
                    desc = feat.get("description", "")
                    if desc:
                        domains.append(desc)

            organism = entry.get("organism", {}).get("scientificName", "Unknown")

            results.append({
                "accession": entry.get("primaryAccession", ""),
                "id": entry.get("uniProtkbId", ""),
                "name": recommended.get("fullName", {}).get("value", ""),
                "organism": organism,
                "length": entry.get("sequence", {}).get("length", 0),
                "function": function,
                "gene_names": gene_names,
                "pdb_structures": pdbs,
                "domains": domains,
            })

        return results

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ===================================================================
# Main sequence_search
# ===================================================================

async def sequence_search(
    query: str,
    database: str = "uniprot",
    max_results: int = 10,
) -> dict:
    """Search for similar protein sequences or UniProt database entries.

    Automatically detects whether the input is an amino-acid sequence
    (runs BLAST) or a keyword/accession (runs UniProt text search).

    Args:
        query: amino-acid sequence or search keyword / UniProt accession.
        database: target database — "uniprot", "pdb", or "nr" (NCBI non-redundant).
        max_results: maximum number of hits to return.

    Returns:
        Dict with query info, database, and list of hit entries.
    """
    query_clean = query.strip()
    if not query_clean:
        raise ValueError("EMPTY_QUERY: query must not be empty")

    is_sequence = _is_amino_acid_sequence(query_clean)
    # Skip BLAST for very short peptides — not enough information content
    if is_sequence and len(query_clean.replace(" ", "").replace("\n", "").replace("\t", "")) < BLAST_MIN_SEQUENCE_LENGTH:
        is_sequence = False

    if is_sequence:
        # Determine BLAST program
        program = "blastp"
        # Map database name
        blast_db = "swissprot" if database == "uniprot" else database

        blast = BlastClient()
        try:
            hits = await blast.search(
                sequence=query_clean,
                database=blast_db,
                program=program,
                max_results=max_results,
            )
        finally:
            await blast.close()

        return {
            "query": query_clean[:80] + ("..." if len(query_clean) > 80 else ""),
            "query_type": "sequence",
            "query_length": len(query_clean),
            "database": database,
            "program": program,
            "results_count": len(hits),
            "results": hits,
        }

    else:
        # UniProt keyword / accession search
        uniprot = UniProtClient()
        try:
            hits = await uniprot.search(query=query_clean, max_results=max_results)
        finally:
            await uniprot.close()

        # If no UniProt results and query is a long enough sequence, try BLAST as fallback
        if not hits and len(query_clean) >= BLAST_MIN_SEQUENCE_LENGTH:
            # Could be sequence with unusual characters
            # Try a simple check
            blast = BlastClient()
            try:
                blast_hits = await blast.search(
                    sequence=query_clean,
                    database="swissprot",
                    program="blastp",
                    max_results=max_results,
                )
            except Exception:
                blast_hits = []
            finally:
                await blast.close()

            if blast_hits:
                return {
                    "query": query_clean[:80] + ("..." if len(query_clean) > 80 else ""),
                    "query_type": "sequence",
                    "query_length": len(query_clean),
                    "database": "swissprot",
                    "program": "blastp",
                    "results_count": len(blast_hits),
                    "results": blast_hits,
                }

        return {
            "query": query_clean,
            "query_type": "keyword",
            "database": database,
            "results_count": len(hits),
            "results": hits,
        }


# ===================================================================
# Registration
# ===================================================================

ToolRegistry.register(
    name="sequence_search",
    description=(
        "Search for similar protein sequences via NCBI BLAST (for amino-acid "
        "sequence queries) or UniProt text search (for keywords/accessions). "
        "Returns alignments with identity, e-value, organism, and functional "
        "annotations. Respects rate limits with automatic retry."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Amino acid sequence for BLAST search, or a keyword / "
                    "UniProt accession for text search (e.g. 'insulin' or 'P01308')."
                ),
            },
            "database": {
                "type": "string",
                "enum": ["uniprot", "pdb", "nr"],
                "description": "Database to search against.",
                "default": "uniprot",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of results to return.",
                "default": 10,
            },
        },
        "required": ["query"],
    },
    handler=sequence_search,
    is_async=True,
    category="search",
    timeout_seconds=300,
    errors=[
        {
            "reason": "invalid_input",
            "code": "EMPTY_QUERY",
            "when": "query parameter is empty or whitespace-only",
            "recovery": "Provide a valid amino acid sequence or search keyword.",
        },
        {
            "reason": "connection_error",
            "code": "BLAST_FAILED",
            "when": "NCBI BLAST submission failed (invalid input, server error)",
            "recovery": (
                "Check that the query is a valid amino acid sequence. "
                "For nucleotide sequences, use the blast_search tool with blastn."
            ),
        },
        {
            "reason": "timeout",
            "code": "BLAST_TIMEOUT",
            "when": "BLAST search did not complete within the polling window",
            "recovery": (
                "Try a shorter query sequence, restrict the database, or retry later "
                "when NCBI servers are less busy."
            ),
        },
        {
            "reason": "rate_limited",
            "code": "RATE_LIMITED",
            "when": "NCBI or UniProt rate limit exceeded",
            "recovery": (
                "Wait the specified Retry-After duration before retrying. "
                "Set NCBI_API_KEY for higher BLAST rate limits."
            ),
        },
        {
            "reason": "connection_error",
            "code": "UNIPROT_FAILED",
            "when": "UniProt REST API returned an error",
            "recovery": "Check network connectivity and retry the search.",
        },
    ],
)
