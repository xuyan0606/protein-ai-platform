"""BRENDA enzyme database REST API client.

BRENDA (BRaunschweig ENzyme DAtabase) is the main collection of enzyme and
metabolism information.  This client wraps the public REST API at:
    https://www.brenda-enzymes.org/api/

Endpoints used:
    /api/enzyme                 — search enzymes by name / EC number
    /api/enzyme/{ec_number}     — detailed info for a specific EC entry

Data returned includes: EC number, recommended name, synonyms, organism
sources, cofactors, KM/Ki/kcat values (when available), reaction, pathway,
and literature references.

Rate limiting: BRENDA allows ~10 req/s without an API key.  This client
applies a conservative 0.5 s delay between consecutive calls and respects
429 Retry-After headers.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BRENDA_BASE_URL = "https://www.brenda-enzymes.org"
BRENDA_API_SEARCH = f"{BRENDA_BASE_URL}/api/enzyme"
BRENDA_API_DETAIL = f"{BRENDA_BASE_URL}/api/enzyme"  # detail is /api/enzyme/{ec}
BRENDA_TIMEOUT = 30.0
BRENDA_RATE_LIMIT_DELAY = 0.5  # seconds between requests
_EC_PATTERN = re.compile(r"^\d{1,2}\.\d{1,3}(\.\d{1,3})?(\.\d{1,3})?$")


class BRENDAError(Exception):
    """Raised on BRENDA API failures."""


class BRENDA:
    """Async BRENDA REST client with rate-limit awareness."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._last_request_ts: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(BRENDA_TIMEOUT),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ProteinAI-Platform/2.0 (enzyme-data-agent)",
                },
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < BRENDA_RATE_LIMIT_DELAY:
            await asyncio.sleep(BRENDA_RATE_LIMIT_DELAY - elapsed)
        self._last_request_ts = time.monotonic()

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search BRENDA by enzyme name, gene name, or EC number.

        Args:
            query: Free-text name, gene symbol, or EC number (e.g. "2.7.1.1").
            max_results: Maximum number of results to return (capped at 20).

        Returns:
            List of BRENDA enzyme dicts with keys: ec_number, name, synonyms,
            reaction, organisms, cofactors, km_values, kcat_values, references.
        """
        query = query.strip()
        if not query:
            return []

        max_results = min(max_results, 20)
        await self._rate_limit()

        client = await self._get_client()

        # BRENDA search API — query parameter
        params: dict[str, str] = {
            "q": query,
        }

        try:
            resp = await client.get(BRENDA_API_SEARCH, params=params)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                logger.warning("BRENDA rate limited, waiting %ds", retry_after)
                await asyncio.sleep(retry_after)
                resp = await client.get(BRENDA_API_SEARCH, params=params)

            if resp.status_code == 404:
                # No results — BRENDA returns 404 for empty search
                return []

            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise BRENDAError(f"BRENDA search request failed: {e}") from e

        data = resp.json()
        if not isinstance(data, list):
            # Single result wraps in dict
            data = [data] if isinstance(data, dict) else []

        results: list[dict[str, Any]] = []
        for item in data[:max_results]:
            results.append(self._parse_enzyme_entry(item))

        return results

    async def get_by_ec(
        self,
        ec_number: str,
    ) -> dict[str, Any] | None:
        """Fetch a single BRENDA enzyme entry by EC number.

        Args:
            ec_number: EC number, e.g. "1.1.1.1" or "2.7.1".

        Returns:
            Parsed enzyme dict or None if not found.
        """
        ec_number = ec_number.strip()
        if not _EC_PATTERN.match(ec_number):
            return None

        await self._rate_limit()
        client = await self._get_client()

        url = f"{BRENDA_API_DETAIL}/{ec_number}"
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                await asyncio.sleep(retry_after)
                resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise BRENDAError(f"BRENDA detail request failed: {e}") from e

        data = resp.json()
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return None

        return self._parse_enzyme_entry(data)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Internal parsing ───────────────────────────────────────────────

    @staticmethod
    def _parse_enzyme_entry(raw: dict[str, Any]) -> dict[str, Any]:
        """Normalise a raw BRENDA JSON object into a clean enzyme dict."""
        # BRENDA API field names vary across versions; handle common variants
        ec_number = (
            raw.get("ecNumber")
            or raw.get("ec_number")
            or raw.get("ec")
            or ""
        )

        name = (
            raw.get("recommendedName")
            or raw.get("recommended_name")
            or raw.get("name")
            or ""
        )

        # Synonyms
        synonyms = raw.get("synonyms", [])
        if isinstance(synonyms, str):
            synonyms = [s.strip() for s in synonyms.split(";") if s.strip()]

        # Reaction
        reaction = (
            raw.get("reaction")
            or raw.get("catalyzedReaction")
            or ""
        )

        # Organism sources
        organisms_raw = raw.get("organisms", []) or raw.get("organism", [])
        if isinstance(organisms_raw, str):
            organisms_raw = [organisms_raw]
        organisms = [
            (o.get("name") if isinstance(o, dict) else str(o))
            for o in organisms_raw[:10]
        ]

        # Cofactors
        cofactors = raw.get("cofactors", []) or raw.get("cofactor", [])
        if isinstance(cofactors, str):
            cofactors = [c.strip() for c in cofactors.split(",") if c.strip()]

        # Kinetic data — KM
        km_values = []
        km_raw = raw.get("kmValues", []) or raw.get("km_values", []) or raw.get("km", [])
        if isinstance(km_raw, list):
            for kv in km_raw[:10]:
                if isinstance(kv, dict):
                    km_values.append({
                        "substrate": kv.get("substrate", ""),
                        "value": kv.get("value", kv.get("kmValue", "")),
                        "unit": kv.get("unit", "mM"),
                        "organism": kv.get("organism", ""),
                    })
                elif isinstance(kv, str):
                    km_values.append({"substrate": "", "value": kv, "unit": "mM", "organism": ""})

        # Kinetic data — kcat
        kcat_values = []
        kcat_raw = raw.get("kcatValues", []) or raw.get("kcat_values", []) or raw.get("kcat", [])
        if isinstance(kcat_raw, list):
            for kv in kcat_raw[:10]:
                if isinstance(kv, dict):
                    kcat_values.append({
                        "substrate": kv.get("substrate", ""),
                        "value": kv.get("value", kv.get("kcatValue", "")),
                        "unit": kv.get("unit", "1/s"),
                        "organism": kv.get("organism", ""),
                    })
                elif isinstance(kv, str):
                    kcat_values.append({"substrate": "", "value": kv, "unit": "1/s", "organism": ""})

        # References
        references = []
        refs_raw = raw.get("references", []) or raw.get("literature", [])
        if isinstance(refs_raw, list):
            for ref in refs_raw[:5]:
                if isinstance(ref, dict):
                    references.append({
                        "pmid": ref.get("pubmedId", ref.get("pmid", "")),
                        "title": ref.get("title", ""),
                        "doi": ref.get("doi", ""),
                    })

        # Pathway / system
        pathway = raw.get("pathway", "") or raw.get("metabolicPathway", "")
        if isinstance(pathway, list):
            pathway = "; ".join(str(p) for p in pathway[:3])

        return {
            "source": "BRENDA",
            "ec_number": ec_number,
            "name": name,
            "synonyms": synonyms,
            "reaction": reaction,
            "organisms": organisms,
            "cofactors": cofactors,
            "km_values": km_values,
            "kcat_values": kcat_values,
            "pathway": pathway,
            "references": references,
        }


# ── Convenience function for synchronous contexts ──────────────────────

def format_brenda_context(enzyme: dict[str, Any]) -> str:
    """Format a BRENDA enzyme dict as a natural-language context string for LLM injection."""
    lines: list[str] = []

    ec = enzyme.get("ec_number", "")
    name = enzyme.get("name", "")
    lines.append(f"EC {ec}: {name}" if ec and name else name or ec)

    synonyms = enzyme.get("synonyms", [])
    if synonyms:
        lines.append(f"Synonyms: {', '.join(synonyms[:5])}")

    reaction = enzyme.get("reaction", "")
    if reaction:
        lines.append(f"Reaction: {reaction}")

    organisms = enzyme.get("organisms", [])
    if organisms:
        lines.append(f"Organisms: {', '.join(organisms[:5])}")

    cofactors = enzyme.get("cofactors", [])
    if cofactors:
        lines.append(f"Cofactors: {', '.join(cofactors[:5])}")

    pathway = enzyme.get("pathway", "")
    if pathway:
        lines.append(f"Pathway: {pathway}")

    km_values = enzyme.get("km_values", [])
    if km_values:
        lines.append("KM values:")
        for kv in km_values[:5]:
            sub = f" ({kv['substrate']})" if kv.get("substrate") else ""
            org = f" [{kv['organism']}]" if kv.get("organism") else ""
            lines.append(f"  - {kv['value']} {kv.get('unit', 'mM')}{sub}{org}")

    kcat_values = enzyme.get("kcat_values", [])
    if kcat_values:
        lines.append("kcat values:")
        for kv in kcat_values[:5]:
            sub = f" ({kv['substrate']})" if kv.get("substrate") else ""
            org = f" [{kv['organism']}]" if kv.get("organism") else ""
            lines.append(f"  - {kv['value']} {kv.get('unit', '1/s')}{sub}{org}")

    refs = enzyme.get("references", [])
    if refs:
        lines.append("References:")
        for r in refs[:3]:
            pmid = r.get("pmid", "")
            title = r.get("title", "")
            if pmid and title:
                lines.append(f"  - PMID:{pmid} {title[:100]}")

    return "\n".join(lines)
