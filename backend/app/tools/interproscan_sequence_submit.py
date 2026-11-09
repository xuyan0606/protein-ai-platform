"""Minimal live InterProScan sequence submission and status tools."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from app.services.evidence_source_status import evidence_source_status
from app.tools.registry import ToolRegistry


INTERPROSCAN_BASE_ENDPOINT = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"
INTERPROSCAN_RUN_ENDPOINT = f"{INTERPROSCAN_BASE_ENDPOINT}/run"
INTERPROSCAN_STATUS_ENDPOINT = f"{INTERPROSCAN_BASE_ENDPOINT}/status"
INTERPROSCAN_RESULT_ENDPOINT = f"{INTERPROSCAN_BASE_ENDPOINT}/result"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
_PENDING_STATUSES = {"RUNNING", "QUEUED", "PENDING", "STARTED"}
_FINISHED_STATUSES = {"FINISHED", "DONE", "COMPLETED"}
_FAILED_STATUSES = {"FAILURE", "ERROR", "NOT_FOUND", "NOTFOUND", "FAILED"}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _job_endpoint(base: str, job_id: str) -> str:
    return f"{base}/{quote(job_id, safe='')}"


def _result_endpoint(job_id: str, result_type: str) -> str:
    return f"{INTERPROSCAN_RESULT_ENDPOINT}/{quote(job_id, safe='')}/{quote(result_type, safe='')}"


def _none_if_missing(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text != "-" else None


def _first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _none_if_missing(data.get(key))
        if value:
            return value
    return None


def _first_int(data: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_json_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]
    return [payload] if isinstance(payload.get("matches"), list) else []


def _normalize_interproscan_match(
    *,
    entry: dict[str, Any],
    signature: dict[str, Any],
    location: dict[str, Any],
    source: str,
) -> dict[str, Any] | None:
    interpro_accession = _first_string(entry, ("accession", "ac", "id"))
    if not interpro_accession:
        return None

    sig_library = signature.get("signatureLibraryRelease")
    sig_library = sig_library if isinstance(sig_library, dict) else {}
    database = (
        _first_string(sig_library, ("library", "database", "name"))
        or _first_string(signature, ("library", "database", "sourceDatabase", "source_database", "analysis"))
    )
    signature_accession = _first_string(signature, ("accession", "ac", "id"))
    signature_name = _first_string(signature, ("name", "description", "desc"))
    start = _first_int(location, ("start", "begin", "from"))
    end = _first_int(location, ("end", "stop", "to"))

    return {
        "interpro_accession": interpro_accession,
        "interpro_id": interpro_accession,
        "name": _first_string(entry, ("name", "description", "desc")) or signature_name,
        "entry_type": _first_string(entry, ("type", "entry_type", "entryType")),
        "start": start,
        "end": end,
        "signature": {
            "accession": signature_accession,
            "name": signature_name,
            "database": database,
        },
        "signature_accession": signature_accession,
        "signature_database": database,
        "database": database,
        "source": source,
    }


def _parse_interproscan_json(payload: Any) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for record in _extract_json_results(payload):
        matches = record.get("matches")
        if not isinstance(matches, list):
            continue
        for match in matches:
            if not isinstance(match, dict):
                continue
            signature = match.get("signature")
            if not isinstance(signature, dict):
                continue
            entry = signature.get("entry")
            if not isinstance(entry, dict):
                continue
            locations = match.get("locations")
            if not isinstance(locations, list) or not locations:
                locations = [{}]
            for location in locations:
                normalized = _normalize_interproscan_match(
                    entry=entry,
                    signature=signature,
                    location=location if isinstance(location, dict) else {},
                    source="interproscan_rest_json",
                )
                if normalized:
                    annotations.append(normalized)
    return annotations


def _parse_interproscan_tsv(text: str) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        columns = line.rstrip("\n").split("\t")
        if len(columns) < 13:
            continue
        interpro_accession = _none_if_missing(columns[11])
        if not interpro_accession:
            continue
        try:
            start = int(columns[6])
            end = int(columns[7])
        except (TypeError, ValueError):
            start = None
            end = None
        database = _none_if_missing(columns[3])
        signature_accession = _none_if_missing(columns[4])
        signature_name = _none_if_missing(columns[5])
        annotations.append(
            {
                "interpro_accession": interpro_accession,
                "interpro_id": interpro_accession,
                "name": _none_if_missing(columns[12]) or signature_name,
                "entry_type": None,
                "start": start,
                "end": end,
                "signature": {
                    "accession": signature_accession,
                    "name": signature_name,
                    "database": database,
                },
                "signature_accession": signature_accession,
                "signature_database": database,
                "database": database,
                "source": "interproscan_rest_tsv",
            }
        )
    return annotations


def _limit(value: int | str | None) -> int:
    try:
        return max(1, min(int(value or 100), 500))
    except (TypeError, ValueError):
        return 100


async def interproscan_sequence_submit(
    sequence: str = "",
    email: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Submit a protein sequence to EBI InterProScan REST and return the job id.

    This intentionally does not poll status or fetch/interpret results. A
    submitted job is only evidence that a live InterProScan run was accepted.
    """

    seq = _clean(sequence).replace(" ", "").replace("\n", "").replace("\r", "").upper()
    mail = _clean(email)
    job_title = _clean(title)

    if not seq:
        return {
            "status": "blocked",
            "job_id": None,
            "query": {"sequence_length": 0, "title": job_title or None},
            "results": [],
            "result_available": False,
            "message": "No usable InterProScan results are available because sequence is required before submission.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status="blocked",
                mode="input_or_runtime_blocked",
                live_query_executed=False,
                endpoint=INTERPROSCAN_RUN_ENDPOINT,
                reason="MISSING_SEQUENCE: provide a protein sequence to submit an InterProScan job.",
            ),
        }

    data: dict[str, str] = {"sequence": seq}
    if mail:
        data["email"] = mail
    if job_title:
        data["title"] = job_title

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(INTERPROSCAN_RUN_ENDPOINT, data=data)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return {
            "status": "blocked" if status_code and 400 <= status_code < 500 else "degraded",
            "job_id": None,
            "query": {"sequence_length": len(seq), "title": job_title or None, "email_provided": bool(mail)},
            "results": [],
            "result_available": False,
            "message": "No usable InterProScan results are available; live job submission was rejected by the API.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status="blocked" if status_code and 400 <= status_code < 500 else "degraded",
                mode="live_submission_failed",
                live_query_executed=False,
                endpoint=INTERPROSCAN_RUN_ENDPOINT,
                reason=f"INTERPROSCAN_SUBMISSION_REJECTED: HTTP {status_code or 'unknown'}",
                details={"attempted_live_query": True},
            ),
        }
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPError) as exc:
        return {
            "status": "degraded",
            "job_id": None,
            "query": {"sequence_length": len(seq), "title": job_title or None, "email_provided": bool(mail)},
            "results": [],
            "result_available": False,
            "message": "No usable InterProScan results are available; live job submission failed before a job id was returned.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status="degraded",
                mode="live_submission_failed",
                live_query_executed=False,
                endpoint=INTERPROSCAN_RUN_ENDPOINT,
                reason=f"INTERPROSCAN_SUBMISSION_FAILED: {type(exc).__name__}",
                details={"attempted_live_query": True},
            ),
        }

    job_id = response.text.strip()
    if not job_id:
        return {
            "status": "degraded",
            "job_id": None,
            "query": {"sequence_length": len(seq), "title": job_title or None, "email_provided": bool(mail)},
            "results": [],
            "result_available": False,
            "message": "No usable InterProScan results are available; live API accepted the request without returning a job id.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status="degraded",
                mode="live_submission_failed",
                live_query_executed=False,
                endpoint=INTERPROSCAN_RUN_ENDPOINT,
                reason="INTERPROSCAN_EMPTY_JOB_ID",
                details={"attempted_live_query": True},
            ),
        }

    return {
        "status": "submitted",
        "job_id": job_id,
        "query": {"sequence_length": len(seq), "title": job_title or None, "email_provided": bool(mail)},
        "results": [],
        "result_available": False,
        "message": "InterProScan job submitted; no InterProScan result has been fetched or interpreted by this MVP.",
        "evidence_source": evidence_source_status(
            source="EBI InterProScan REST",
            status="live",
            mode="interproscan_rest_submit",
            live_query_executed=True,
            endpoint=INTERPROSCAN_RUN_ENDPOINT,
            details={"result_polling_executed": False},
        ),
    }


async def interproscan_sequence_status(
    job_id: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """Poll EBI InterProScan REST status and fetch parsed results once finished."""

    job = _clean(job_id)
    limit = _limit(max_results)
    if not job:
        return {
            "status": "blocked",
            "job_id": None,
            "ebi_status": None,
            "query": {"job_id": None},
            "results": [],
            "results_count": 0,
            "result_available": False,
            "message": "No usable InterProScan results are available because job_id is required for status polling.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status="blocked",
                mode="input_or_runtime_blocked",
                live_query_executed=False,
                endpoint=INTERPROSCAN_STATUS_ENDPOINT,
                reason="MISSING_JOB_ID: provide an InterProScan job id returned by interproscan_sequence_submit.",
            ),
        }

    status_url = _job_endpoint(INTERPROSCAN_STATUS_ENDPOINT, job)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            status_response = await client.get(status_url)
            status_response.raise_for_status()
            ebi_status = status_response.text.strip().upper()

            if ebi_status in _PENDING_STATUSES:
                return {
                    "status": "pending",
                    "job_id": job,
                    "ebi_status": ebi_status,
                    "query": {"job_id": job, "status_endpoint": status_url},
                    "results": [],
                    "results_count": 0,
                    "result_available": False,
                    "message": "InterProScan job is still running; no annotation results were fetched or returned.",
                    "evidence_source": evidence_source_status(
                        source="EBI InterProScan REST",
                        status="live",
                        mode="interproscan_rest_status",
                        live_query_executed=True,
                        endpoint=status_url,
                        details={"result_polling_executed": False},
                    ),
                }

            if ebi_status in _FAILED_STATUSES:
                return {
                    "status": "blocked",
                    "job_id": job,
                    "ebi_status": ebi_status,
                    "query": {"job_id": job, "status_endpoint": status_url},
                    "results": [],
                    "results_count": 0,
                    "result_available": False,
                    "message": "No usable InterProScan results are available because the live job did not finish successfully.",
                    "evidence_source": evidence_source_status(
                        source="EBI InterProScan REST",
                        status="blocked",
                        mode="interproscan_rest_status_failed",
                        live_query_executed=True,
                        endpoint=status_url,
                        reason=f"INTERPROSCAN_JOB_{ebi_status}",
                    ),
                }

            if ebi_status not in _FINISHED_STATUSES:
                return {
                    "status": "degraded",
                    "job_id": job,
                    "ebi_status": ebi_status or None,
                    "query": {"job_id": job, "status_endpoint": status_url},
                    "results": [],
                    "results_count": 0,
                    "result_available": False,
                    "message": "No usable InterProScan results are available because the live API returned an unrecognized job status.",
                    "evidence_source": evidence_source_status(
                        source="EBI InterProScan REST",
                        status="degraded",
                        mode="interproscan_rest_status_unknown",
                        live_query_executed=True,
                        endpoint=status_url,
                        reason=f"INTERPROSCAN_UNKNOWN_STATUS: {ebi_status or 'empty'}",
                    ),
                }

            result_url = _result_endpoint(job, "json")
            try:
                result_response = await client.get(result_url)
                result_response.raise_for_status()
                try:
                    payload = result_response.json()
                except AttributeError:
                    payload = json.loads(result_response.text)
                annotations = _parse_interproscan_json(payload)
                result_format = "json"
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError, ValueError, json.JSONDecodeError):
                result_url = _result_endpoint(job, "tsv")
                result_response = await client.get(result_url)
                result_response.raise_for_status()
                annotations = _parse_interproscan_tsv(result_response.text)
                result_format = "tsv"

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        evidence_status = "blocked" if status_code and 400 <= status_code < 500 else "degraded"
        return {
            "status": evidence_status,
            "job_id": job,
            "ebi_status": "NOT_FOUND" if status_code == 404 else None,
            "query": {"job_id": job, "status_endpoint": status_url},
            "results": [],
            "results_count": 0,
            "result_available": False,
            "message": "No usable InterProScan results are available; live status/result retrieval failed.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status=evidence_status,
                mode="interproscan_rest_poll_failed",
                live_query_executed=True,
                endpoint=INTERPROSCAN_BASE_ENDPOINT,
                reason=f"INTERPROSCAN_POLL_FAILED: HTTP {status_code or 'unknown'}",
                details={"attempted_live_query": True},
            ),
        }
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPError) as exc:
        return {
            "status": "degraded",
            "job_id": job,
            "ebi_status": None,
            "query": {"job_id": job, "status_endpoint": status_url},
            "results": [],
            "results_count": 0,
            "result_available": False,
            "message": "No usable InterProScan results are available; live status/result retrieval failed.",
            "evidence_source": evidence_source_status(
                source="EBI InterProScan REST",
                status="degraded",
                mode="interproscan_rest_poll_failed",
                live_query_executed=False,
                endpoint=INTERPROSCAN_BASE_ENDPOINT,
                reason=f"INTERPROSCAN_POLL_FAILED: {type(exc).__name__}",
                details={"attempted_live_query": True},
            ),
        }

    limited = annotations[:limit]
    return {
        "status": "completed",
        "job_id": job,
        "ebi_status": ebi_status,
        "query": {"job_id": job, "status_endpoint": status_url, "result_endpoint": result_url},
        "results": limited,
        "results_count": len(limited),
        "raw_results_count": len(annotations),
        "result_available": True,
        "result_format": result_format,
        "message": "InterProScan job finished and live results were parsed.",
        "evidence_source": evidence_source_status(
            source="EBI InterProScan REST",
            status="live",
            mode="interproscan_rest_result",
            live_query_executed=True,
            endpoint=INTERPROSCAN_BASE_ENDPOINT,
            details={
                "status_endpoint": status_url,
                "result_endpoint": result_url,
                "result_format": result_format,
                "results_count": len(limited),
                "raw_results_count": len(annotations),
            },
        ),
    }


ToolRegistry.register(
    name="interproscan_sequence_submit",
    description=(
        "Submit a raw protein sequence to the EBI InterProScan REST /run endpoint "
        "and return the submitted job id. This MVP does not poll status or fetch "
        "InterProScan results."
    ),
    handler=interproscan_sequence_submit,
    is_async=True,
    category="data",
    timeout_seconds=45,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino-acid sequence to submit."},
            "email": {"type": "string", "description": "Optional email passed through to EBI Tools."},
            "title": {"type": "string", "description": "Optional InterProScan job title."},
        },
    },
    errors=[
        {
            "reason": "invalid_input",
            "code": "MISSING_SEQUENCE",
            "when": "sequence is empty",
            "recovery": "Provide a protein amino-acid sequence before submitting InterProScan.",
        },
        {
            "reason": "connection_error",
            "code": "INTERPROSCAN_SUBMISSION_FAILED",
            "when": "EBI InterProScan REST submission fails",
            "recovery": "Retry later or provide an already completed InterProScan result as external evidence.",
        },
    ],
)


ToolRegistry.register(
    name="interproscan_sequence_status",
    description=(
        "Poll an EBI InterProScan REST job id. Pending jobs return live status "
        "without annotations; finished jobs fetch and parse JSON results into "
        "InterPro accessions, names, entry types, locations, and signature databases."
    ),
    handler=interproscan_sequence_status,
    is_async=True,
    category="data",
    timeout_seconds=45,
    parameters={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "InterProScan job id returned by interproscan_sequence_submit.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 100,
                "description": "Maximum parsed InterPro annotation rows to return.",
            },
        },
    },
    errors=[
        {
            "reason": "invalid_input",
            "code": "MISSING_JOB_ID",
            "when": "job_id is empty",
            "recovery": "Submit a sequence first or provide an existing InterProScan job id.",
        },
        {
            "reason": "connection_error",
            "code": "INTERPROSCAN_POLL_FAILED",
            "when": "EBI InterProScan REST status or result retrieval fails",
            "recovery": "Retry later, verify the job id, or resubmit the sequence if the job has expired.",
        },
    ],
)
