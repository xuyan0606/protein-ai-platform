#!/usr/bin/env python3
"""Recover PMC XML only when it exactly matches the recorded evidence hash."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "datasets/curation/literature_measurement_source_recovery_requests.jsonl"
REPORT = ROOT / "reports/literature_measurement_source_recovery_execution_report.json"


def target_path(root: Path, source_path: str) -> Path:
    candidate = (root / source_path).resolve()
    if not source_path or root.resolve() not in candidate.parents:
        raise ValueError("source_path must be a non-empty relative path inside --root")
    return candidate


def fetch_pmc_xml(pmcid: str) -> bytes:
    urls = (
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/?report=xml",
    )
    errors = []
    for url in urls:
        try:
            request = Request(url, headers={"User-Agent": "KWB-literature-recovery/1.0"})
            with urlopen(request, timeout=30) as response:
                return response.read()
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("; ".join(errors))


def recover_request(request: dict[str, Any], root: Path, fetcher: Callable[[str], bytes]) -> dict[str, Any]:
    source_path = str(request.get("source_path", ""))
    result = {"request_id": request.get("request_id"), "source_path": source_path, "status": "unavailable"}
    try:
        target = target_path(root, source_path)
        pmcid = next((str(value) for value in request.get("pmcids", []) if str(value)), "")
        if not pmcid:
            result["status"] = "missing_pmcid"
            return result
        payload = fetcher(pmcid)
    except Exception as exc:  # Network errors are evidence failures, not exceptions to bypass.
        result.update(status="fetch_failed", detail=str(exc))
        return result

    actual_sha256 = hashlib.sha256(payload).hexdigest()
    expected_sha256 = {str(value) for value in request.get("expected_sha256", [])}
    result["actual_sha256"] = actual_sha256
    if actual_sha256 not in expected_sha256:
        result["status"] = "hash_mismatch"
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        handle.write(payload)
        temporary_path = Path(handle.name)
    os.replace(temporary_path, target)
    result["status"] = "recovered"
    return result


def load_requests(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=Path, default=REQUESTS)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--fetch", action="store_true", help="Fetch public PMC XML; default is dry-run only.")
    args = parser.parse_args()
    requests = load_requests(args.requests)
    if args.fetch:
        records = [recover_request(request, args.root, fetch_pmc_xml) for request in requests]
    else:
        records = [{"request_id": request.get("request_id"), "source_path": request.get("source_path"), "status": "dry_run"} for request in requests]
    counts = {status: sum(record["status"] == status for record in records) for status in sorted({record["status"] for record in records})}
    report = {"request_count": len(records), "status_counts": counts, "records": records,
              "formal_intake_authorized": False, "training_import_allowed": False,
              "safe_for_model_claim": False, "release_ready": False,
              "policy": "Only exact SHA-256 matches are atomically restored; recovery never promotes evidence."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"request_count": len(records), "status_counts": counts}, ensure_ascii=False))
    if not args.fetch:
        return 0
    return 0 if counts.get("recovered", 0) == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
