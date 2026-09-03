#!/usr/bin/env python3
"""Build local PyRosetta install/import evidence without approving ddG use."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_python_module_discovery import add_local_module_paths, module_probe_row


AI_ROOT = Path(__file__).resolve().parents[1]
INSTALL_PATH = AI_ROOT / "cache" / "external" / "PyRosetta" / "python"
WHEEL_PATH = AI_ROOT / "cache" / "external" / "PyRosetta" / "wheels" / "pyrosetta-2026.29+releasequarterly.80a0635615-cp39-cp39-macosx_12_0_arm64.whl"
OUT = AI_ROOT / "reports" / "pyrosetta_local_install_probe_report.json"
OUT_MD = AI_ROOT / "reports" / "pyrosetta_local_install_probe.md"


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def package_version(dist_prefix: str) -> str | None:
    for dist in sorted(INSTALL_PATH.glob(f"{dist_prefix}*.dist-info")):
        metadata = dist / "METADATA"
        if not metadata.exists():
            continue
        for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    return None


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def import_probe() -> dict[str, Any]:
    added_paths = add_local_module_paths([INSTALL_PATH])
    result: dict[str, Any] = {
        "attempted": INSTALL_PATH.exists(),
        "succeeded": False,
        "added_sys_paths": added_paths,
        "pyrosetta_file": None,
        "error": None,
        "pyrosetta_init_executed": False,
        "ddg_protocol_executed": False,
    }
    if not result["attempted"]:
        result["error"] = "install_path_missing"
        return result
    try:
        import pyrosetta  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local licensed install.
        result["error"] = f"{type(exc).__name__}: {exc}"
    else:
        result["succeeded"] = True
        result["pyrosetta_file"] = getattr(pyrosetta, "__file__", None)
    return result


def build_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# PyRosetta Local Install Probe",
            "",
            f"Created: `{report['created_at']}`",
            "",
            "| Check | Value |",
            "| --- | --- |",
            f"| Wheel present | {report['wheel']['present']} |",
            f"| Wheel size bytes | {report['wheel']['size_bytes']} |",
            f"| Install path present | {report['install']['path_exists']} |",
            f"| PyRosetta package version | {report['install']['pyrosetta_package_version']} |",
            f"| NumPy package version | {report['install']['numpy_package_version']} |",
            f"| Module spec available | {report['module_spec']['available']} |",
            f"| Import succeeded | {report['import_probe']['succeeded']} |",
            f"| Formal runtime receipt written | {report['formal_runtime_receipt_written']} |",
            f"| Approved for physical ddG runtime | {report['approved_for_physical_ddg_runtime']} |",
            f"| Physics ddG ready | {report['physics_ddg_ready']} |",
            "",
            "## Boundary",
            "",
            "- This is install/import evidence only.",
            "- It does not approve PyRosetta license use, enable backend config, run a ddG protocol, write a formal runtime receipt, or open model/release claims.",
            "",
        ]
    )


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    module_spec = module_probe_row("pyrosetta", [INSTALL_PATH])
    license_file = INSTALL_PATH / "pyrosetta" / "LICENSE.PyRosetta.md"
    report = {
        "created_at": created_at,
        "local_only": True,
        "backend": "pyrosetta",
        "intended_scope": "technical install/import evidence under component authorization matrix; platform is not non-commercial-only and verified legal scope remains a separate gate",
        "official_download_source": "RosettaCommons PyRosetta quarterly release mirror",
        "wheel": {
            "path": rel(WHEEL_PATH),
            "present": WHEEL_PATH.exists(),
            "size_bytes": WHEEL_PATH.stat().st_size if WHEEL_PATH.exists() else 0,
            "sha256": sha256(WHEEL_PATH),
        },
        "install": {
            "path": rel(INSTALL_PATH),
            "path_exists": INSTALL_PATH.exists(),
            "pyrosetta_package_version": package_version("pyrosetta-"),
            "numpy_package_version": package_version("numpy-"),
            "license_file": rel(license_file),
            "license_file_present": license_file.exists(),
            "license_file_sha256": sha256(license_file),
        },
        "module_spec": module_spec,
        "import_probe": import_probe(),
        "python_executable": sys.executable,
        "formal_license_decision_written": False,
        "formal_runtime_receipt_written": False,
        "backend_config_enabled": False,
        "approved_for_physical_ddg_runtime": False,
        "ready_for_ddg_smoke": False,
        "ddg_protocol_executed": False,
        "physics_ddg_ready": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "remaining_hard_gates": [
            "formal external license decision must approve local evaluation",
            "formal runtime receipt must be reviewed and valid",
            "backend config enablement must be reviewed",
            "reviewed smoke plan and smoke artifacts must exist with sha256",
            "ready execution-plan row must exist for a reviewed structure/mutation",
        ],
        "policy": "PyRosetta install/import evidence only; not a license approval, not a physical ddG run, not a training label source, and not a release claim.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(build_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "wheel_present": report["wheel"]["present"],
                "install_path_exists": report["install"]["path_exists"],
                "pyrosetta_package_version": report["install"]["pyrosetta_package_version"],
                "numpy_package_version": report["install"]["numpy_package_version"],
                "module_spec_available": report["module_spec"]["available"],
                "import_succeeded": report["import_probe"]["succeeded"],
                "physics_ddg_ready": False,
                "output": str(OUT),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
