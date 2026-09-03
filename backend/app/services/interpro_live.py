"""InterPro live API client with explicit opt-in and blocked fallbacks."""

from __future__ import annotations

import os
from collections import Counter
from typing import Any
from urllib.parse import quote

import httpx

from app.services.evidence_source_status import blocked_evidence_source, evidence_source_status

_DEFAULT_BASE_URL = "https://www.ebi.ac.uk/interpro/api"
_DEFAULT_TIMEOUT_SECONDS = 20.0
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
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


def _coerce_terms(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, list):
        terms: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("accession") or item.get("id") or item.get("name") or item.get("label") or "").strip()
            else:
                text = str(item).strip()
            if text:
                terms.append(text)
        return terms
    text = str(value).strip()
    return [text] if text else []


def _extract_regions(record: dict[str, Any]) -> list[dict[str, int]]:
    regions: list[dict[str, int]] = []
    for key in ("locations", "fragments", "regions", "matches"):
        value = record.get(key)
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            candidates = [item]
            for nested_key in ("location", "fragment", "match", "protein_location"):
                nested = item.get(nested_key)
                if isinstance(nested, dict):
                    candidates.append(nested)
            for candidate in candidates:
                start = _first_int(candidate, ("start", "begin", "from", "start_position", "protein_start", "startPos"))
                end = _first_int(candidate, ("end", "to", "finish", "stop", "end_position", "protein_end", "endPos"))
                if start is not None and end is not None:
                    regions.append({"start": start, "end": end})
                    break
    unique: dict[tuple[int, int], dict[str, int]] = {}
    for region in regions:
        unique[(region["start"], region["end"])] = region
    return sorted(unique.values(), key=lambda item: (item["start"], item["end"]))


def _extract_records(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if not isinstance(payload, dict):
        return [], None

    for key in ("results", "entries", "data", "proteins"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)], payload
        if isinstance(value, dict):
            nested_records, nested_meta = _extract_records(value)
            if nested_records:
                return nested_records, nested_meta or value

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("results", "entries", "data", "proteins"):
            value = metadata.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)], metadata

    return [], payload


class InterProLiveClient:
    """Minimal InterPro API client that never fakes live status."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.enabled = _env_bool("INTERPRO_LIVE_ENABLED") if enabled is None else bool(enabled)
        configured_base = (base_url or os.getenv("INTERPRO_LIVE_BASE_URL", _DEFAULT_BASE_URL)).strip()
        self.base_url = configured_base.rstrip("/") or _DEFAULT_BASE_URL
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _env_float(
            "INTERPRO_LIVE_TIMEOUT_SECONDS",
            _DEFAULT_TIMEOUT_SECONDS,
        )
        self.user_agent = os.getenv(
            "INTERPRO_LIVE_USER_AGENT",
            "ProteinAI-Platform/1.0 (interpro-live)",
        )

    async def resolve_annotations(self, *, sequence: str = "", uniprot_id: str = "") -> dict[str, Any]:
        accession = uniprot_id.strip().upper()
        sequence_length = len(sequence.strip()) or None
        if not self.enabled:
            return self._empty_blocked(accession or None, sequence_length, "live InterPro lookup is disabled by configuration")
        if not accession:
            return self._empty_blocked(
                None,
                sequence_length,
                "live InterPro lookup requires a UniProt accession",
            )

        request_path = f"/entry/interpro/protein/uniprot/{quote(accession, safe='')}"
        request_url = f"{self.base_url}{request_path}"
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                headers=headers,
            ) as client:
                response = await client.get(request_url)
        except httpx.HTTPError as exc:
            return self._blocked(accession, sequence_length, request_url, request_path, exc, live_query_executed=True)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self._blocked(accession, sequence_length, request_url, request_path, exc, live_query_executed=True)

        if response.status_code == 404:
            return self._blocked(
                accession,
                sequence_length,
                request_url,
                request_path,
                RuntimeError("InterPro returned 404 for this accession"),
                live_query_executed=True,
            )

        if response.status_code == 204:
            payload = None
        else:
            try:
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as exc:
                return self._blocked(accession, sequence_length, request_url, request_path, exc, live_query_executed=True)
            except ValueError as exc:
                return self._blocked(accession, sequence_length, request_url, request_path, exc, live_query_executed=True)

        records, metadata = _extract_records(payload)
        annotations = [self._normalize_record(record) for record in records]
        type_counts = Counter(item["entry_type"] or "unknown" for item in annotations)

        return {
            "found": bool(annotations),
            "query": {
                "uniprot_id": accession,
                "sequence_length": sequence_length,
                "endpoint": request_path,
            },
            "summary": {
                "annotation_count": len(annotations),
                "raw_record_count": len(records),
                "entry_type_counts": dict(type_counts),
            },
            "annotations": annotations,
            "evidence_source": evidence_source_status(
                source="InterPro",
                status="live",
                mode="interpro_api",
                live_query_executed=True,
                endpoint=self.base_url,
                reason="Official InterPro API query completed.",
                details={
                    "request_path": request_path,
                    "annotation_count": len(annotations),
                    "raw_record_count": len(records),
                    "metadata_keys": sorted(metadata.keys()) if isinstance(metadata, dict) else [],
                },
            ),
            "note": "Live InterPro API response; no local fallback was used.",
        }

    def _empty_blocked(
        self,
        accession: str | None,
        sequence_length: int | None,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "found": False,
            "query": {"uniprot_id": accession, "sequence_length": sequence_length},
            "annotations": [],
            "summary": {"annotation_count": 0, "raw_record_count": 0, "entry_type_counts": {}},
            "evidence_source": blocked_evidence_source("InterPro", reason),
            "note": "Live InterPro query was not attempted.",
        }

    def _blocked(
        self,
        accession: str,
        sequence_length: int | None,
        request_url: str,
        request_path: str,
        exc: Exception,
        *,
        live_query_executed: bool,
    ) -> dict[str, Any]:
        return {
            "found": False,
            "query": {
                "uniprot_id": accession or None,
                "sequence_length": sequence_length,
                "endpoint": request_path,
            },
            "annotations": [],
            "summary": {"annotation_count": 0, "raw_record_count": 0, "entry_type_counts": {}},
            "evidence_source": evidence_source_status(
                source="InterPro",
                status="blocked",
                mode="interpro_api",
                live_query_executed=live_query_executed,
                endpoint=self.base_url,
                reason=f"InterPro live query failed: {exc.__class__.__name__}",
                details={
                    "request_url": request_url,
                    "request_path": request_path,
                    "error": str(exc),
                },
            ),
            "note": "Live InterPro query was blocked or failed before usable evidence was returned.",
        }

    @staticmethod
    def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        source = _first_string(record, ("source_database", "source_db", "sourceDB", "source")) or _first_string(
            metadata if isinstance(metadata, dict) else {},
            ("source_database", "source_db", "sourceDB", "source"),
        ) or "interpro"
        go_terms_source = record.get("go_terms")
        if not go_terms_source and isinstance(metadata, dict):
            go_terms_source = metadata.get("go_terms")

        annotation = {
            "interpro_id": _first_string(record, ("interpro_id", "accession", "entry_id", "id"))
            or _first_string(metadata if isinstance(metadata, dict) else {}, ("accession", "id")),
            "name": _first_string(record, ("name", "label", "description"))
            or _first_string(metadata if isinstance(metadata, dict) else {}, ("name", "label", "description")),
            "entry_type": _first_string(record, ("entry_type", "type"))
            or _first_string(metadata if isinstance(metadata, dict) else {}, ("entry_type", "type")),
            "source": "interpro_live",
            "source_database": source,
            "go_terms": _coerce_terms(go_terms_source),
            "regions": _extract_regions(record),
            "evidence": "interpro_live_api",
        }
        if not annotation["regions"]:
            annotation.pop("regions", None)
        if not annotation["go_terms"]:
            annotation.pop("go_terms", None)
        return annotation
