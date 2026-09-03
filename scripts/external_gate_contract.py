"""Pure contracts for externally dependent production gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class GateStatus(str, Enum):
    PLANNED = "planned"
    BLOCKED = "blocked"
    ARMED = "armed"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True)
class GateContract:
    name: str
    priority: str
    lane: str
    required_inputs: tuple[str, ...]
    secret_inputs: tuple[str, ...]
    command_id: str
    destructive: bool = False
    terminal_statuses: tuple[str, ...] = ("passed",)


@dataclass(frozen=True)
class InputEvaluation:
    gate: str
    status: GateStatus
    missing: tuple[str, ...]


def gate_contracts() -> dict[str, GateContract]:
    rows = (
        GateContract(
            "production_https",
            "P0",
            "infra_dns_tls",
            ("PUBLIC_BASE_URL", "FRONTEND_URL", "OIDC_ISSUER"),
            (),
            "production_https_strict",
        ),
        GateContract(
            "foldseek_live",
            "P0",
            "structure_runtime",
            ("FOLDSEEK_RUNTIME", "FOLDSEEK_DATABASE_ROOT"),
            (),
            "foldseek_live_readiness",
        ),
        GateContract(
            "gpu_md",
            "P0",
            "md_runtime",
            ("GPU_RUNNER", "WT_PDB_INPUT", "MUTANT_PDB_INPUT", "MD_VALIDATION_WINDOW", "ALLOW_MD_BLACKBOX_SUBMIT"),
            ("MD_BLACKBOX_PASSWORD",),
            "gpu_md_live",
        ),
        GateContract(
            "ligand_runtime",
            "P1",
            "ligand_runtime",
            ("LIGAND_RUNTIME_IMAGE",),
            (),
            "ligand_runtime_live",
        ),
        GateContract(
            "oss_minio",
            "P0",
            "storage",
            ("OSS_ENDPOINT", "OSS_BUCKET"),
            ("OSS_ACCESS_KEY", "OSS_SECRET_KEY"),
            "oss_minio_round_trip",
        ),
        GateContract(
            "admin_screenshot",
            "P1",
            "browser_auth",
            ("FRONTEND_BASE_URL",),
            ("SCREENSHOT_EMAIL", "SCREENSHOT_PASSWORD"),
            "admin_authenticated_screenshot",
        ),
        GateContract(
            "maintenance_restore",
            "P1",
            "maintenance",
            (
                "MAINTENANCE_WINDOW_ID",
                "ALLOW_PRODUCTION_DRILL",
                "OFFSITE_BACKUP_TARGET",
                "OFFSITE_RESTORE_TARGET",
                "EXTERNAL_STORAGE_BACKUP_REF",
                "EXTERNAL_STORAGE_RESTORE_TARGET",
            ),
            (),
            "maintenance_restore_manual",
            destructive=True,
        ),
    )
    return {row.name: row for row in rows}


def _present(values: Mapping[str, object], name: str) -> bool:
    value = values.get(name)
    return value is not None and bool(str(value).strip())


def evaluate_inputs(gate_name: str, values: Mapping[str, object]) -> InputEvaluation:
    contract = gate_contracts()[gate_name]
    missing = tuple(
        name
        for name in (*contract.required_inputs, *contract.secret_inputs)
        if not _present(values, name)
    )
    if missing:
        status = GateStatus.BLOCKED
    elif contract.destructive:
        status = GateStatus.MANUAL_REQUIRED
    else:
        status = GateStatus.ARMED
    return InputEvaluation(gate=gate_name, status=status, missing=missing)
