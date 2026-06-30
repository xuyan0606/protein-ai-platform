"""SABIO-RK kinetics database REST API client.

SABIO-RK (System for the Analysis of BIOchemical networks - Reaction Kinetics)
is a curated database of enzyme kinetic data.  This client wraps the public
REST API at:
    https://sabiork.h-its.org/sabioREST/

Endpoints used:
    /sabioREST/search?q=<query>           — search reactions/enzymes
    /sabioREST/kineticLaws/<entry_id>     — kinetic law details

Data returned includes: EC number, substrate, product, kinetic parameters
(KM, kcat, Vmax), experimental conditions (pH, temperature), organism,
and literature references.

Rate limiting: SABIO-RK allows ~5 req/s.  This client applies a 0.8 s delay
between consecutive calls and respects 429 Retry-After headers.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SABIO_BASE_URL = "https://sabiork.h-its.org"
SABIO_API_SEARCH = f"{SABIO_BASE_URL}/sabioREST/search"
SABIO_API_KINETIC_LAWS = f"{SABIO_BASE_URL}/sabioREST/kineticLaws"
SABIO_TIMEOUT = 30.0
SABIO_RATE_LIMIT_DELAY = 0.8  # seconds between requests
_EC_PATTERN = re.compile(r"^\d{1,2}\.\d{1,3}(\.\d{1,3})?(\.\d{1,3})?$")


class SABIOError(Exception):
    """Raised on SABIO-RK API failures."""


class SABIOClient:
    """Async SABIO-RK REST client with rate-limit awareness."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._last_request_ts: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(SABIO_TIMEOUT),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ProteinAI-Platform/2.0 (enzyme-data-agent)",
                },
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < SABIO_RATE_LIMIT_DELAY:
            await asyncio.sleep(SABIO_RATE_LIMIT_DELAY - elapsed)
        self._last_request_ts = time.monotonic()

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search SABIO-RK by enzyme name, EC number, or substrate.

        Args:
            query: Free-text name, EC number, or substrate (e.g. "1.1.1.1").
            max_results: Maximum number of results to return (capped at 15).

        Returns:
            List of SABIO kinetic entry dicts with keys: entry_id, ec_number,
            organism, substrates, products, kinetic_parameters, conditions, references.
        """
        query = query.strip()
        if not query:
            return []

        max_results = min(max_results, 15)
        await self._rate_limit()

        client = await self._get_client()

        # SABIO search API
        params: dict[str, str] = {
            "q": query,
            "format": "json",
        }

        try:
            resp = await client.get(SABIO_API_SEARCH, params=params)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                logger.warning("SABIO-RK rate limited, waiting %ds", retry_after)
                await asyncio.sleep(retry_after)
                resp = await client.get(SABIO_API_SEARCH, params=params)

            if resp.status_code == 404:
                return []

            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SABIOError(f"SABIO-RK search request failed: {e}") from e

        data = resp.json()
        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else []

        results: list[dict[str, Any]] = []
        for item in data[:max_results]:
            results.append(self._parse_search_entry(item))

        return results

    async def get_kinetic_law(
        self,
        entry_id: str | int,
    ) -> dict[str, Any] | None:
        """Fetch detailed kinetic law data for a SABIO entry.

        Args:
            entry_id: SABIO entry ID (numeric).

        Returns:
            Parsed kinetic law dict or None if not found.
        """
        await self._rate_limit()
        client = await self._get_client()

        url = f"{SABIO_API_KINETIC_LAWS}/{entry_id}"
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
            raise SABIOError(f"SABIO-RK kinetic law request failed: {e}") from e

        data = resp.json()
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return None

        return self._parse_kinetic_law(data)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Internal parsing ───────────────────────────────────────────────

    @staticmethod
    def _parse_search_entry(raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a SABIO search result entry."""
        entry_id = str(raw.get("id", raw.get("entryId", "")))
        ec_number = raw.get("ecNumber", raw.get("ec", ""))
        organism = raw.get("organism", "")

        # Substrates and products
        substrates = raw.get("substrates", [])
        if isinstance(substrates, str):
            substrates = [s.strip() for s in substrates.split(";") if s.strip()]
        products = raw.get("products", [])
        if isinstance(products, str):
            products = [p.strip() for p in products.split(";") if p.strip()]

        # Reaction equation
        reaction = raw.get("reaction", raw.get("equation", ""))

        # Basic kinetic parameters (if included in search result)
        kinetic_params = []
        params_raw = raw.get("kineticParameters", []) or raw.get("parameters", [])
        if isinstance(params_raw, list):
            for p in params_raw[:8]:
                if isinstance(p, dict):
                    kinetic_params.append({
                        "name": p.get("name", p.get("parameter", "")),
                        "value": p.get("value", ""),
                        "unit": p.get("unit", ""),
                        "substrate": p.get("substrate", ""),
                    })

        # Experimental conditions
        conditions = {}
        cond_raw = raw.get("conditions", raw.get("experimentalConditions", {}))
        if isinstance(cond_raw, dict):
            conditions = {
                "pH": cond_raw.get("pH", ""),
                "temperature": cond_raw.get("temperature", ""),
                "temperature_unit": cond_raw.get("temperatureUnit", "°C"),
                "buffer": cond_raw.get("buffer", ""),
            }

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

        return {
            "source": "SABIO-RK",
            "entry_id": entry_id,
            "ec_number": ec_number,
            "organism": organism,
            "reaction": reaction,
            "substrates": substrates,
            "products": products,
            "kinetic_parameters": kinetic_params,
            "conditions": conditions,
            "references": references,
        }

    @staticmethod
    def _parse_kinetic_law(raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a detailed SABIO kinetic law entry."""
        entry_id = str(raw.get("id", raw.get("kineticLawId", "")))
        ec_number = raw.get("ecNumber", raw.get("ec", ""))
        organism = raw.get("organism", "")

        # Kinetic parameters (more detailed than search results)
        kinetic_params = []
        params_raw = raw.get("parameters", []) or raw.get("kineticParameters", [])
        if isinstance(params_raw, list):
            for p in params_raw[:15]:
                if isinstance(p, dict):
                    kinetic_params.append({
                        "name": p.get("name", p.get("parameter", "")),
                        "value": p.get("value", ""),
                        "unit": p.get("unit", ""),
                        "substrate": p.get("substrate", ""),
                        "type": p.get("type", ""),  # KM, kcat, Vmax, Ki, etc.
                    })

        # Experimental conditions (more detailed)
        conditions = {}
        cond_raw = raw.get("conditions", raw.get("experimentalConditions", {}))
        if isinstance(cond_raw, dict):
            conditions = {
                "pH": cond_raw.get("pH", ""),
                "temperature": cond_raw.get("temperature", ""),
                "temperature_unit": cond_raw.get("temperatureUnit", "°C"),
                "buffer": cond_raw.get("buffer", ""),
                "ionic_strength": cond_raw.get("ionicStrength", ""),
            }

        # Enzyme concentration (if available)
        enzyme_conc = raw.get("enzymeConcentration", raw.get("enzyme_conc", ""))

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
                        "year": ref.get("year", ""),
                    })

        return {
            "source": "SABIO-RK",
            "entry_id": entry_id,
            "ec_number": ec_number,
            "organism": organism,
            "kinetic_parameters": kinetic_params,
            "conditions": conditions,
            "enzyme_concentration": enzyme_conc,
            "references": references,
        }


# ── Convenience function for synchronous contexts ──────────────────────

def format_sabio_context(entry: dict[str, Any]) -> str:
    """Format a SABIO-RK entry as a natural-language context string for LLM injection."""
    lines: list[str] = []

    entry_id = entry.get("entry_id", "")
    ec = entry.get("ec_number", "")
    organism = entry.get("organism", "")

    header = f"SABIO-RK Entry {entry_id}"
    if ec:
        header += f" (EC {ec})"
    if organism:
        header += f" — {organism}"
    lines.append(header)

    # Reaction
    reaction = entry.get("reaction", "")
    if reaction:
        lines.append(f"Reaction: {reaction}")

    # Substrates / products
    substrates = entry.get("substrates", [])
    products = entry.get("products", [])
    if substrates:
        lines.append(f"Substrates: {', '.join(substrates[:5])}")
    if products:
        lines.append(f"Products: {', '.join(products[:5])}")

    # Kinetic parameters
    params = entry.get("kinetic_parameters", [])
    if params:
        lines.append("Kinetic parameters:")
        for p in params[:8]:
            name = p.get("name", "")
            value = p.get("value", "")
            unit = p.get("unit", "")
            sub = f" ({p['substrate']})" if p.get("substrate") else ""
            ptype = f" [{p['type']}]" if p.get("type") else ""
            lines.append(f"  - {name}{ptype}: {value} {unit}{sub}")

    # Experimental conditions
    conditions = entry.get("conditions", {})
    if conditions:
        cond_parts = []
        if conditions.get("pH"):
            cond_parts.append(f"pH {conditions['pH']}")
        if conditions.get("temperature"):
            temp_unit = conditions.get("temperature_unit", "°C")
            cond_parts.append(f"{conditions['temperature']}{temp_unit}")
        if conditions.get("buffer"):
            cond_parts.append(f"buffer: {conditions['buffer']}")
        if cond_parts:
            lines.append(f"Conditions: {', '.join(cond_parts)}")

    # Enzyme concentration
    enzyme_conc = entry.get("enzyme_concentration", "")
    if enzyme_conc:
        lines.append(f"Enzyme concentration: {enzyme_conc}")

    # References
    refs = entry.get("references", [])
    if refs:
        lines.append("References:")
        for r in refs[:3]:
            pmid = r.get("pmid", "")
            title = r.get("title", "")
            year = r.get("year", "")
            if pmid and title:
                year_str = f" ({year})" if year else ""
                lines.append(f"  - PMID:{pmid}{year_str} {title[:100]}")

    return "\n".join(lines)
