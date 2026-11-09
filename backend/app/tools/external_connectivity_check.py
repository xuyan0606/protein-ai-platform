"""Read-only live connectivity check for official scientific APIs."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.services.evidence_source_status import evidence_source_status
from app.tools.registry import ToolRegistry


CONNECTIVITY_TIMEOUT_SECONDS = 8.0
CONNECTIVITY_ENDPOINTS: tuple[tuple[str, str, dict[str, str]], ...] = (
    (
        "UniProt REST",
        "https://rest.uniprot.org/uniprotkb/search",
        {"query": "accession:P69905", "format": "json", "size": "1"},
    ),
    (
        "NCBI E-utilities",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi",
        {"db": "protein", "retmode": "json"},
    ),
    (
        "InterPro API",
        "https://www.ebi.ac.uk/interpro/api/entry/InterPro/IPR000001/",
        {},
    ),
)


async def _probe_endpoint(
    client: httpx.AsyncClient,
    name: str,
    url: str,
    params: dict[str, str],
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return {
            "source": name,
            "endpoint": url,
            "status": "live",
            "http_status": response.status_code,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        response = getattr(exc, "response", None)
        payload: dict[str, Any] = {
            "source": name,
            "endpoint": url,
            "status": "blocked",
            "error_type": type(exc).__name__,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
        status_code = getattr(response, "status_code", None)
        if status_code is not None:
            payload["http_status"] = status_code
        return payload


async def external_connectivity_check() -> dict[str, Any]:
    """Attempt current read-only requests against official protein data APIs."""
    headers = {"User-Agent": "KWB-Protein-AI-Platform/connectivity-check"}
    async with httpx.AsyncClient(
        timeout=CONNECTIVITY_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers=headers,
    ) as client:
        probes = await asyncio.gather(*(
            _probe_endpoint(client, name, url, params)
            for name, url, params in CONNECTIVITY_ENDPOINTS
        ))

    live_count = sum(probe.get("status") == "live" for probe in probes)
    total_count = len(probes)
    if live_count == total_count:
        mode = "official_api_connectivity_check"
        reason = "All configured official scientific API probes succeeded in this request."
    elif live_count > 0:
        mode = "partial_official_api_connectivity"
        reason = f"{live_count} of {total_count} official scientific API probes succeeded in this request."
    else:
        mode = "official_api_connectivity_blocked"
        reason = "No official scientific API probe succeeded in this request."

    live = live_count > 0
    return {
        "status": "live" if live else "blocked",
        "connected": live,
        "summary": {
            "successful_probes": live_count,
            "total_probes": total_count,
            "all_reachable": live_count == total_count,
        },
        "probes": probes,
        "evidence_source": evidence_source_status(
            source="Official scientific APIs",
            status="live" if live else "blocked",
            mode=mode,
            live_query_executed=live,
            endpoint="; ".join(url for _, url, _ in CONNECTIVITY_ENDPOINTS),
            reason=reason,
            details={"attempted_live_query": True, "successful_probes": live_count, "total_probes": total_count},
        ),
        "boundary": (
            "This proves current outbound access only for the successful probes. "
            "It does not prove that every external database, generic web page, GPU runtime, or local Foldseek database is available."
        ),
    }


ToolRegistry.register(
    name="external_connectivity_check",
    description=(
        "Perform a current read-only connectivity check against official UniProt, NCBI, and InterPro APIs. "
        "Use this for questions such as '你联网了吗' instead of claiming network status from model memory."
    ),
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
    handler=external_connectivity_check,
    category="research",
    timeout_seconds=30,
    annotations={
        "read_only": True,
        "external_network": True,
        "destructive": False,
    },
)
