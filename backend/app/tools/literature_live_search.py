"""Live literature lookup through PubMed E-utilities and Crossref REST."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.services.evidence_source_status import evidence_source_status
from app.services.ncbi_api import (
    NCBIRateLimitError,
    ncbi_evidence_details,
    ncbi_request_params,
    rate_limit_from_response,
    retry_after_from_exception,
)
from app.services.tool_cache import get_cached_result, set_cached_result
from app.tools.registry import ToolRegistry


PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
LITERATURE_SOURCE = "PubMed E-utilities; Crossref REST"
LITERATURE_TIMEOUT_SECONDS = 12.0


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _clamp_max_results(value: int | None) -> int:
    try:
        parsed = int(value or 10)
    except (TypeError, ValueError):
        parsed = 10
    return min(max(parsed, 1), 25)


def _pubmed_term(*, query: str, doi: str, pmid: str) -> str:
    if pmid:
        return pmid
    if doi:
        return f"{doi}[doi]"
    return query


def _normalize_authors(authors: Any) -> list[str]:
    if not isinstance(authors, list):
        return []
    names: list[str] = []
    for author in authors[:8]:
        if isinstance(author, str):
            names.append(author)
        elif isinstance(author, dict):
            name = author.get("name") or " ".join(
                part for part in [author.get("given"), author.get("family")] if part
            )
            if name:
                names.append(str(name))
    return names


def _crossref_date(message: dict[str, Any]) -> str:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = message.get(key, {}).get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list):
            return "-".join(str(part) for part in parts[0])
    return ""


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in results:
        key = (
            _clean(item.get("doi")).lower()
            or _clean(item.get("pmid")).lower()
            or _clean(item.get("title")).lower()
        )
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(item)
    return unique


def _literature_cache_params(*, query: str, doi: str, pmid: str, max_results: int) -> dict[str, Any]:
    return {
        "query": query,
        "doi": doi,
        "pmid": pmid,
        "max_results": max_results,
    }


def _endpoint_summary() -> str:
    return f"{PUBMED_ESEARCH_URL}; {CROSSREF_WORKS_URL}"


def _retry_after_from_exception(exc: Exception) -> str | None:
    return retry_after_from_exception(exc)


def _structured_error(source: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, NCBIRateLimitError):
        return exc.as_details()
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    retry_after = _retry_after_from_exception(exc)
    if status_code == 429 or retry_after:
        details: dict[str, Any] = {
            "code": "RATE_LIMITED" if status_code == 429 else "RETRY_AFTER",
            "source": source,
        }
        if status_code is not None:
            details["status_code"] = status_code
        if retry_after:
            details["retry_after"] = retry_after
        return details
    details = {
        "code": "REQUEST_FAILED",
        "source": source,
        "type": type(exc).__name__,
    }
    if status_code is not None:
        details["status_code"] = status_code
    return details


def _reason_from_errors(errors: dict[str, str], error_details_by_source: dict[str, dict[str, Any]]) -> str:
    if any(error.get("code") in {"RATE_LIMITED", "RETRY_AFTER"} for error in error_details_by_source.values()):
        return "RATE_LIMITED"
    return "; ".join(f"{source}: {error}" for source, error in errors.items())


def _cache_hit_payload(cached: dict[str, Any]) -> dict[str, Any]:
    previous_source = cached.get("evidence_source") if isinstance(cached.get("evidence_source"), dict) else None
    cached["evidence_source"] = evidence_source_status(
        source=LITERATURE_SOURCE,
        status="degraded",
        mode="cache_hit",
        live_query_executed=False,
        endpoint=_endpoint_summary(),
        reason="Returned cached literature result; no live PubMed or Crossref query executed in this request.",
        details=ncbi_evidence_details(
            "pubmed",
            extra={"previous_evidence_source": previous_source} if previous_source else None,
        ),
    )
    return cached


def _stale_cache_payload(
    stale: dict[str, Any],
    *,
    errors: dict[str, str],
    retry_after_by_source: dict[str, str],
    error_details_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    previous_source = stale.get("evidence_source") if isinstance(stale.get("evidence_source"), dict) else None
    stale["status"] = "degraded"
    stale["warning"] = "Live literature lookup failed; returned stale cached literature result."
    stale["errors"] = errors
    stale["sources_queried"] = []
    stale.setdefault("cache", {})
    stale["cache"]["stale"] = True
    details: dict[str, Any] = {
        "attempted_live_query": True,
        "partial_errors": errors,
        "previous_evidence_source": previous_source,
        "error_details_by_source": error_details_by_source,
    }
    stale["evidence_source"] = evidence_source_status(
        source=LITERATURE_SOURCE,
        status="degraded",
        mode="stale_cache_after_live_failure",
        live_query_executed=False,
        endpoint=_endpoint_summary(),
        reason=_reason_from_errors(errors, error_details_by_source),
        details=ncbi_evidence_details(
            "pubmed",
            extra=details,
            retry_after_by_source=retry_after_by_source or None,
        ),
    )
    return stale


class PubMedEUtilitiesClient:
    """Small PubMed E-utilities client; tests monkeypatch this class."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=LITERATURE_TIMEOUT_SECONDS)
        return self._client

    async def search(
        self,
        *,
        query: str = "",
        doi: str = "",
        pmid: str = "",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        client = await self._get_client()
        term = _pubmed_term(query=query, doi=doi, pmid=pmid)
        if pmid:
            ids = [pmid]
        else:
            response = await client.get(
                PUBMED_ESEARCH_URL,
                params=ncbi_request_params("pubmed", {
                    "db": "pubmed",
                    "retmode": "json",
                    "retmax": max_results,
                    "term": term,
                }),
            )
            rate_limit_error = rate_limit_from_response(
                response,
                source="pubmed",
                message="PubMed ESearch returned HTTP 429",
            )
            if rate_limit_error:
                raise rate_limit_error
            response.raise_for_status()
            ids = response.json().get("esearchresult", {}).get("idlist", [])

        if not ids:
            return []

        summary_response = await client.get(
            PUBMED_ESUMMARY_URL,
            params=ncbi_request_params("pubmed", {
                "db": "pubmed",
                "retmode": "json",
                "id": ",".join(str(item) for item in ids[:max_results]),
            }),
        )
        rate_limit_error = rate_limit_from_response(
            summary_response,
            source="pubmed",
            message="PubMed ESummary returned HTTP 429",
        )
        if rate_limit_error:
            raise rate_limit_error
        summary_response.raise_for_status()
        payload = summary_response.json().get("result", {})
        results: list[dict[str, Any]] = []
        for uid in payload.get("uids", []):
            record = payload.get(str(uid), {})
            article_ids = record.get("articleids") if isinstance(record, dict) else []
            doi_value = ""
            if isinstance(article_ids, list):
                for article_id in article_ids:
                    if isinstance(article_id, dict) and article_id.get("idtype") == "doi":
                        doi_value = str(article_id.get("value") or "")
                        break
            results.append(
                {
                    "source": "pubmed",
                    "pmid": str(uid),
                    "doi": doi_value,
                    "title": str(record.get("title") or ""),
                    "journal": str(record.get("fulljournalname") or record.get("source") or ""),
                    "published": str(record.get("pubdate") or ""),
                    "authors": _normalize_authors(record.get("authors")),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                }
            )
        return results

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class CrossrefClient:
    """Small Crossref REST client; tests monkeypatch this class."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=LITERATURE_TIMEOUT_SECONDS)
        return self._client

    async def search(
        self,
        *,
        query: str = "",
        doi: str = "",
        pmid: str = "",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        client = await self._get_client()
        if doi:
            response = await client.get(f"{CROSSREF_WORKS_URL}/{quote(doi, safe='')}")
            response.raise_for_status()
            items = [response.json().get("message", {})]
        else:
            response = await client.get(
                CROSSREF_WORKS_URL,
                params={"query.bibliographic": query or pmid, "rows": max_results},
            )
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])

        results: list[dict[str, Any]] = []
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            titles = item.get("title") if isinstance(item.get("title"), list) else []
            container = item.get("container-title") if isinstance(item.get("container-title"), list) else []
            results.append(
                {
                    "source": "crossref",
                    "pmid": "",
                    "doi": str(item.get("DOI") or ""),
                    "title": str(titles[0] if titles else ""),
                    "journal": str(container[0] if container else ""),
                    "published": _crossref_date(item),
                    "authors": _normalize_authors(item.get("author")),
                    "url": str(item.get("URL") or ""),
                }
            )
        return results

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


async def literature_live_search(
    query: str = "",
    doi: str = "",
    pmid: str = "",
    max_results: int = 10,
) -> dict[str, Any]:
    """Search PubMed and Crossref for live literature evidence."""

    query_clean = _clean(query)
    doi_clean = _clean(doi)
    pmid_clean = _clean(pmid)
    limit = _clamp_max_results(max_results)
    cache_params = _literature_cache_params(
        query=query_clean,
        doi=doi_clean,
        pmid=pmid_clean,
        max_results=limit,
    )

    if not any([query_clean, doi_clean, pmid_clean]):
        return {
            "status": "blocked",
            "query": query_clean,
            "doi": doi_clean,
            "pmid": pmid_clean,
            "max_results": limit,
            "results_count": 0,
            "results": [],
            "evidence_source": evidence_source_status(
                source=LITERATURE_SOURCE,
                status="blocked",
                mode="input_or_runtime_blocked",
                live_query_executed=False,
                reason="MISSING_LITERATURE_QUERY: provide at least one of query, doi, or pmid.",
            ),
        }

    cached = await get_cached_result("literature_live_search", cache_params)
    if cached is not None:
        return _cache_hit_payload(cached)

    pubmed = PubMedEUtilitiesClient()
    crossref = CrossrefClient()
    errors: dict[str, str] = {}
    retry_after_by_source: dict[str, str] = {}
    error_details_by_source: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    sources_queried: list[str] = []

    try:
        try:
            results.extend(
                await pubmed.search(
                    query=query_clean,
                    doi=doi_clean,
                    pmid=pmid_clean,
                    max_results=limit,
                )
            )
            sources_queried.append("pubmed")
        except Exception as exc:
            errors["pubmed"] = str(exc)
            error_details_by_source["pubmed"] = _structured_error("pubmed", exc)
            retry_after = _retry_after_from_exception(exc)
            if retry_after:
                retry_after_by_source["pubmed"] = retry_after

        try:
            results.extend(
                await crossref.search(
                    query=query_clean,
                    doi=doi_clean,
                    pmid=pmid_clean,
                    max_results=limit,
                )
            )
            sources_queried.append("crossref")
        except Exception as exc:
            errors["crossref"] = str(exc)
            error_details_by_source["crossref"] = _structured_error("crossref", exc)
            retry_after = _retry_after_from_exception(exc)
            if retry_after:
                retry_after_by_source["crossref"] = retry_after
    finally:
        await pubmed.close()
        await crossref.close()

    results = _dedupe_results(results)[:limit]
    if sources_queried:
        details: dict[str, Any] = {
            "max_results": limit,
            "sources_queried": sources_queried,
            "partial_errors": errors,
            "error_details_by_source": error_details_by_source,
        }
        payload = {
            "status": "completed",
            "query": query_clean,
            "doi": doi_clean,
            "pmid": pmid_clean,
            "max_results": limit,
            "results_count": len(results),
            "results": results,
            "sources_queried": sources_queried,
            "errors": errors,
            "evidence_source": evidence_source_status(
                source=LITERATURE_SOURCE,
                status="live",
                mode="pubmed_crossref_rest",
                live_query_executed=True,
                endpoint=_endpoint_summary(),
                details=ncbi_evidence_details(
                    "pubmed",
                    extra=details,
                    retry_after_by_source=retry_after_by_source or None,
                ),
            ),
        }
        await set_cached_result("literature_live_search", cache_params, payload)
        return payload

    stale = await get_cached_result("literature_live_search", cache_params, allow_stale=True)
    if stale is not None:
        return _stale_cache_payload(
            stale,
            errors=errors,
            retry_after_by_source=retry_after_by_source,
            error_details_by_source=error_details_by_source,
        )

    details: dict[str, Any] = {
        "attempted_live_query": True,
        "max_results": limit,
        "error_details_by_source": error_details_by_source,
    }

    return {
        "status": "degraded",
        "query": query_clean,
        "doi": doi_clean,
        "pmid": pmid_clean,
        "max_results": limit,
        "results_count": 0,
        "results": [],
        "sources_queried": [],
        "errors": errors,
        "warning": "Live literature lookup failed and no cached literature result is available.",
        "evidence_source": evidence_source_status(
            source=LITERATURE_SOURCE,
            status="degraded",
            mode="live_query_failed",
            live_query_executed=False,
            endpoint=_endpoint_summary(),
            reason=_reason_from_errors(errors, error_details_by_source),
            details=ncbi_evidence_details(
                "pubmed",
                extra=details,
                retry_after_by_source=retry_after_by_source or None,
            ),
        ),
    }


ToolRegistry.register(
    name="literature_live_search",
    description=(
        "Live literature search for biomedical references using PubMed "
        "E-utilities and Crossref REST. Accepts a keyword query, DOI, or PMID "
        "and returns normalized citation metadata with evidence source status."
    ),
    handler=literature_live_search,
    is_async=True,
    category="data",
    timeout_seconds=30,
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword, title, author, or biomedical topic to search.",
            },
            "doi": {
                "type": "string",
                "description": "Digital Object Identifier for exact article lookup.",
            },
            "pmid": {
                "type": "string",
                "description": "PubMed identifier for exact article lookup.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 25,
                "default": 10,
                "description": "Maximum number of normalized literature results to return.",
            },
        },
    },
    errors=[
        {
            "reason": "invalid_input",
            "code": "MISSING_LITERATURE_QUERY",
            "when": "query, doi, and pmid are all empty",
            "recovery": "Provide at least one of query, doi, or pmid.",
        },
        {
            "reason": "connection_error",
            "code": "LITERATURE_LIVE_SEARCH_DEGRADED",
            "when": "PubMed and Crossref live requests both fail",
            "recovery": "Retry later, reduce max_results, or provide a DOI/PMID for exact lookup.",
        },
    ],
)
