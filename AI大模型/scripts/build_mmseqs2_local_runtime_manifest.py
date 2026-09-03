#!/usr/bin/env python3
"""Build a local manifest for the downloaded MMseqs2 runtime package."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = AI_ROOT / "cache" / "external" / "MMseqs2"
ARCHIVE = Path("/private/tmp/mmseqs-osx-universal.tar.gz")
MANIFEST_OUT = AI_ROOT / "reports" / "mmseqs2_local_runtime_manifest.json"
REPORT_OUT = AI_ROOT / "reports" / "mmseqs2_local_runtime_report.json"

IMPORTANT_REL_PATHS = ["LICENSE.md", "README.md", "userguide.pdf", "bin/mmseqs"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_probe(command: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=AI_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "not_found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "probe_timeout"}
    except OSError as exc:
        return {"returncode": 126, "stdout": "", "stderr": f"os_error:{exc}"}
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MMseqs2 local runtime manifest")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    binary = args.source_root / "bin" / "mmseqs"
    files = [path for path in sorted(args.source_root.rglob("*")) if path.is_file()] if args.source_root.exists() else []
    missing_important = [rel for rel in IMPORTANT_REL_PATHS if not (args.source_root / rel).exists()]
    version_probe = run_probe([str(binary), "version"]) if binary.exists() else {"returncode": 127, "stdout": "", "stderr": "binary_missing"}
    help_probe = run_probe([str(binary), "--help"]) if binary.exists() else {"returncode": 127, "stdout": "", "stderr": "binary_missing"}
    file_probe = run_probe(["file", str(binary)]) if binary.exists() else {"returncode": 127, "stdout": "", "stderr": "binary_missing"}
    binary_version = version_probe["stdout"].splitlines()[0] if version_probe["returncode"] == 0 else None
    is_universal_macos = "Mach-O universal binary" in file_probe.get("stdout", "")
    supports_arm64 = "arm64" in file_probe.get("stdout", "")

    manifest = {
        "manifest_id": "kwb_mmseqs2_local_runtime_manifest",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "tool_id": "mmseqs2",
        "source_url": "https://mmseqs.com/latest/mmseqs-osx-universal.tar.gz",
        "source_root": str(args.source_root.relative_to(AI_ROOT) if args.source_root.is_absolute() else args.source_root),
        "archive_path": str(args.archive),
        "archive_sha256": sha256(args.archive) if args.archive.exists() else None,
        "binary_path": str(binary.relative_to(AI_ROOT) if binary.is_absolute() else binary),
        "binary_sha256": sha256(binary) if binary.exists() else None,
        "binary_version": binary_version,
        "file_count": len(files),
        "missing_important_files": missing_important,
        "version_probe": version_probe,
        "help_probe_returncode": help_probe["returncode"],
        "file_probe": file_probe,
        "is_universal_macos_binary": is_universal_macos,
        "supports_arm64": supports_arm64,
        "license_path": "cache/external/MMseqs2/LICENSE.md",
        "safe_for_model_claim": False,
        "policy": "Runtime package evidence only. Homolog database and cache validation are still required before MSA/conservation feature generation.",
    }
    report = {
        "created_at": manifest["created_at"],
        "local_only": True,
        "tool_id": "mmseqs2",
        "source_present": args.source_root.exists(),
        "binary_present": binary.exists(),
        "binary_executable_probe_ok": version_probe["returncode"] == 0,
        "binary_version": binary_version,
        "binary_sha256": manifest["binary_sha256"],
        "archive_sha256": manifest["archive_sha256"],
        "file_count": len(files),
        "missing_important_files": missing_important,
        "is_universal_macos_binary": is_universal_macos,
        "supports_arm64": supports_arm64,
        "ready_as_local_binary_runtime": binary.exists() and version_probe["returncode"] == 0 and not missing_important,
        "ready_for_msa_search": False,
        "ready_for_model_claim": False,
        "remaining_blockers": [
            "homolog database is not configured",
            "MSA/conservation cache validation is not ready",
            "external license/customer delivery decisions are not complete",
        ],
        "manifest": str(args.manifest.relative_to(AI_ROOT) if args.manifest.is_absolute() else args.manifest),
        "policy": manifest["policy"],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "binary_present": report["binary_present"],
        "binary_executable_probe_ok": report["binary_executable_probe_ok"],
        "binary_version": report["binary_version"],
        "ready_as_local_binary_runtime": report["ready_as_local_binary_runtime"],
        "ready_for_msa_search": report["ready_for_msa_search"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
