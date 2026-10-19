#!/usr/bin/env python3
"""Fail-closed report/release version alignment gate.

This gate is intentionally separate from the image provenance verifier.  A
release can have valid Git and image digests while still serving a different
report schema or frontend bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
REPORT_SCHEMA_VERSION = "1.1"
WET_LAB_SCHEMA_VERSION = "wet_lab_plan_v1"


def _sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(item.read_bytes())
    return digest.hexdigest()


def _schema_from_source(root: Path) -> str | None:
    path = root / "backend/app/services/report_generator.py"
    match = re.search(r'^REPORT_SCHEMA_VERSION\s*=\s*["\']([^"\']+)', path.read_text(encoding="utf-8")) if path.is_file() else None
    return match.group(1) if match else None


def check_alignment(
    *,
    root: Path,
    manifest_path: Path,
    frontend_bundle: Path | None = None,
    images: list[str] | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "blocked", "failures": ["release manifest cannot be read as JSON"], "warnings": []}

    from release_provenance import _validate_manifest, verify_manifest
    # Alignment drift should be reported by the dedicated checks below, while
    # malformed core provenance still blocks further verification.
    core_failures = [
        item for item in _validate_manifest(payload)
        if not item.startswith("alignment.") and item != "alignment fields do not match schema v1"
    ]
    failures.extend(core_failures)
    if core_failures:
        return {"status": "blocked", "failures": failures, "warnings": warnings}

    alignment = payload.get("alignment")
    if not isinstance(alignment, dict):
        failures.append("manifest alignment section is missing")
        alignment = {}
    expected_report = str(alignment.get("report_schema_version") or "")
    expected_wet_lab = str(alignment.get("wet_lab_schema_version") or "")
    if expected_report != REPORT_SCHEMA_VERSION:
        failures.append(f"report schema differs from required {REPORT_SCHEMA_VERSION}: {expected_report or 'missing'}")
    source_report = _schema_from_source(root)
    if source_report != expected_report:
        failures.append(f"report schema differs from release: source={source_report or 'missing'} manifest={expected_report or 'missing'}")
    if expected_wet_lab != WET_LAB_SCHEMA_VERSION:
        failures.append(f"wet-lab schema differs from required {WET_LAB_SCHEMA_VERSION}: {expected_wet_lab or 'missing'}")

    model_failures = []
    from check_model_selection_alignment import check_alignment as check_model_alignment
    model_failures = check_model_alignment(root)
    if model_failures:
        failures.append("model selection mismatch: " + ", ".join(model_failures))

    bundle_path = frontend_bundle or (root / "frontend/dist")
    expected_bundle = str(alignment.get("frontend_bundle_sha256") or "")
    if not expected_bundle:
        failures.append("frontend bundle hash is missing from manifest alignment")
    elif bundle_path.is_dir():
        actual_bundle = _sha256_tree(bundle_path)
        if actual_bundle != expected_bundle:
            failures.append("frontend bundle hash differs from release manifest")
    elif bundle_path.is_file():
        actual_bundle = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if actual_bundle != expected_bundle:
            failures.append("frontend bundle hash differs from release manifest")
    else:
        warnings.append(f"frontend bundle path unavailable for local verification: {bundle_path}")

    rollback = payload.get("rollback")
    if not isinstance(rollback, dict) or not rollback.get("target_release_id") or not rollback.get("manifest_sha256"):
        failures.append("rollback target is missing")

    # ``images`` is optional because a source checkout cannot infer the
    # running container image.  Deployment callers can pass the runtime
    # ``SERVICE=REPOSITORY@sha256:...`` set to bind the report gate to the
    # same immutable image identity as the provenance gate.
    provenance = verify_manifest(root=root, manifest_path=manifest_path, images=images, offline=offline)
    if provenance.get("status") != "verified":
        failures.extend(str(item) for item in provenance.get("failures", []))
    return {
        "status": "blocked" if failures else "verified",
        "release_id": payload.get("release_id"),
        "report_schema_version": expected_report,
        "wet_lab_schema_version": expected_wet_lab,
        "failures": list(dict.fromkeys(failures)),
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frontend-bundle", type=Path)
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        metavar="SERVICE=REPOSITORY@sha256:DIGEST",
        help="optional runtime image set to compare with the release manifest",
    )
    parser.add_argument("--offline", action="store_true", help="verify an extracted release without a Git checkout")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    result = check_alignment(
        root=root,
        manifest_path=manifest,
        frontend_bundle=args.frontend_bundle,
        images=args.image or None,
        offline=args.offline,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{result['status']}: {', '.join(result['failures']) if result['failures'] else 'aligned'}")
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
