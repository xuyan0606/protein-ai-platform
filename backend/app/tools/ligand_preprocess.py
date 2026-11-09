"""Ligand preprocessing and docking/MD readiness pipeline.

The tool is conservative by design: it can inspect 2D SDF input anywhere, but
only performs real conversion when the required command-line tools exist.
Missing OpenBabel/Vina/ACPYPE/GROMACS returns a structured blocked result
instead of fabricated 3D, docking, or topology artifacts.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import signal
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.services import storage
from app.tools.registry import ToolRegistry


_VALID_STAGES = {"preflight", "generate_3d", "prepare_pdbqt", "vina_docking", "ligand_topology"}

_STAGE_REQUIRED_PARAMETERS = {
    "prepare_pdbqt": ["ligand_3d input", "ph", "protonation_policy", "charge_model"],
    "vina_docking": ["ligand_pdbqt input", "receptor_pdbqt input", "pocket_center", "pocket_size"],
    "ligand_topology": ["ligand_3d input", "net_charge", "ligand_force_field"],
}


def _command_status(*names: str) -> dict[str, Any]:
    resolved = {name: shutil.which(name) for name in names}
    return {"available": any(bool(path) for path in resolved.values()), "commands": resolved}


def _toolchain_status() -> dict[str, Any]:
    return {
        "openbabel": _command_status("obabel"),
        "vina": _command_status("vina"),
        "acpype": _command_status("acpype"),
        "antechamber": _command_status("antechamber"),
        "gromacs": _command_status("gmx", "gmx_mpi"),
    }


def _parse_v2000_sdf(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    counts_index = None
    for index, line in enumerate(lines[:80]):
        if "V2000" in line:
            counts_index = index
            break
    if counts_index is None:
        return {"format": "unknown", "parse_status": "unsupported", "error": "V2000 counts line not found"}

    counts_line = lines[counts_index]
    try:
        atom_count = int(counts_line[0:3])
        bond_count = int(counts_line[3:6])
    except ValueError:
        parts = counts_line.split()
        try:
            atom_count = int(parts[0])
            bond_count = int(parts[1])
        except (IndexError, ValueError):
            return {"format": "V2000", "parse_status": "unsupported", "error": "Malformed V2000 counts line"}

    atom_lines = lines[counts_index + 1 : counts_index + 1 + atom_count]
    z_values: list[float] = []
    element_counts: dict[str, int] = {}
    parse_errors: list[str] = []
    for line in atom_lines:
        try:
            z_value = float(line[20:30])
            element = line[31:34].strip() or "?"
        except ValueError:
            parts = line.split()
            try:
                z_value = float(parts[2])
                element = parts[3]
            except (IndexError, ValueError):
                parse_errors.append(line[:80])
                continue
        z_values.append(z_value)
        element_counts[element] = element_counts.get(element, 0) + 1

    nonzero_z = [value for value in z_values if abs(value) > 1e-4]
    header_dimension = "2d" if any("2D" in line.upper() for line in lines[:6]) else (
        "3d" if any("3D" in line.upper() for line in lines[:6]) else "unknown"
    )
    inferred_dimension = "3d" if nonzero_z else "2d"
    return {
        "format": "V2000",
        "parse_status": "parsed" if not parse_errors else "parsed_with_errors",
        "atom_count": atom_count,
        "bond_count": bond_count,
        "parsed_atom_count": len(z_values),
        "element_counts": element_counts,
        "header_dimension": header_dimension,
        "inferred_dimension": inferred_dimension,
        "is_2d_sdf": inferred_dimension == "2d",
        "all_z_zero": len(z_values) > 0 and not nonzero_z,
        "z_min": min(z_values) if z_values else None,
        "z_max": max(z_values) if z_values else None,
        "parse_error_count": len(parse_errors),
        "parse_errors_preview": parse_errors[:3],
    }


def _sdf_can_continue(inspection: dict[str, Any]) -> bool:
    return (
        inspection.get("parse_status") == "parsed"
        and isinstance(inspection.get("atom_count"), int)
        and inspection.get("atom_count") == inspection.get("parsed_atom_count")
        and int(inspection.get("atom_count") or 0) > 0
    )


async def _load_sdf_text(sdf_data: str | None, sdf_object_name: str | None, sdf_path: str | None) -> tuple[str, dict[str, Any]]:
    if sdf_data and sdf_data.strip():
        return sdf_data, {"input_type": "sdf_data", "size_bytes": len(sdf_data.encode("utf-8"))}
    if sdf_object_name and sdf_object_name.strip():
        data = await storage.download_file(sdf_object_name)
        return data.decode("utf-8", errors="replace"), {
            "input_type": "sdf_object_name",
            "sdf_object_name": sdf_object_name,
            "size_bytes": len(data),
        }
    if sdf_path and sdf_path.strip():
        path = Path(sdf_path).expanduser()
        if not path.exists():
            raise ValueError(f"SDF path not found: {sdf_path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        return text, {"input_type": "sdf_path", "sdf_path": str(path), "size_bytes": path.stat().st_size}
    raise ValueError("Provide sdf_data, sdf_object_name, or sdf_path")


def _progress(progress_callback: Any, progress: int, message: str, stage: str, current_step: int, total_steps: int) -> None:
    if callable(progress_callback):
        progress_callback(progress, message, stage, current_step, total_steps)


def _content_type(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".sdf"):
        return "chemical/x-mdl-sdfile"
    if lower.endswith(".mol2"):
        return "chemical/x-mol2"
    if lower.endswith(".pdbqt"):
        return "chemical/x-pdbqt"
    if lower.endswith(".pdb"):
        return "chemical/x-pdb"
    if lower.endswith(".itp") or lower.endswith(".top"):
        return "text/plain"
    return "application/octet-stream"


async def _save_artifact(data: bytes, *, filename: str, job_id: str, category: str) -> dict[str, Any]:
    stored = await storage.upload_file(
        data,
        filename=filename,
        content_type=_content_type(filename),
        folder=f"ligands/{job_id}",
    )
    return {
        "name": filename,
        "size": len(data),
        "category": category,
        "object_name": stored.get("object_name"),
        "download_url": f"{stored.get('download_url')}?filename={quote(filename)}" if stored.get("download_url") else None,
    }


def _artifact_manifest(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    total_size = 0
    for artifact in artifacts:
        category = str(artifact.get("category") or "other")
        groups.setdefault(category, []).append(artifact)
        try:
            total_size += int(artifact.get("size") or 0)
        except (TypeError, ValueError):
            pass
    return {
        "version": 1,
        "total_count": len(artifacts),
        "total_size": total_size,
        "groups": groups,
        "counts": {key: len(value) for key, value in groups.items()},
    }


def _run_command(command: list[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    """Run a tool in its own process group so timeouts cannot orphan workers.

    ACPYPE launches AmberTools helpers (notably ``sqm``).  Killing only the
    parent leaves those helpers running and can keep a worker busy indefinitely.
    ``start_new_session`` is available on POSIX; the fallback keeps tests and
    non-POSIX development environments usable.
    """
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=(os.name == "posix"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        stdout, stderr = process.communicate()
        stdout = stdout or exc.stdout or ""
        stderr = stderr or exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        timeout_message = f"Command timed out after {timeout_seconds} seconds"
        return subprocess.CompletedProcess(
            command,
            124,
            stdout,
            "\n".join(part for part in (stderr, timeout_message) if part),
        )
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


async def _run_obabel_gen3d(
    *,
    sdf_text: str,
    job_id: str,
    timeout_seconds: int,
    store_outputs: bool,
) -> dict[str, Any]:
    obabel = shutil.which("obabel")
    if not obabel:
        return {
            "stage": "generate_3d",
            "status": "blocked",
            "blocked_reason": "openbabel_not_installed",
            "required_tool": "obabel",
            "command_preview": "obabel ligand_2d.sdf -O ligand_3d.sdf --gen3d -h",
        }
    with tempfile.TemporaryDirectory(prefix="ligand-preprocess-") as tmp:
        workdir = Path(tmp)
        input_path = workdir / "ligand_2d.sdf"
        output_path = workdir / "ligand_3d.sdf"
        input_path.write_text(sdf_text, encoding="utf-8")
        command = [obabel, str(input_path), "-O", str(output_path), "--gen3d", "-h"]
        completed = await asyncio.to_thread(_run_command, command, workdir, timeout_seconds)
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        if completed.returncode != 0 or not output_path.exists():
            result = {
                "stage": "generate_3d",
                "status": "failed",
                "returncode": completed.returncode,
                "error": output[-4000:] if output else "OpenBabel did not create ligand_3d.sdf",
            }
            if completed.returncode == 124:
                result["failed_reason"] = "command_timeout"
            return result

        generated = output_path.read_text(encoding="utf-8", errors="replace")
        inspection = _parse_v2000_sdf(generated)
        if not _sdf_can_continue(inspection) or inspection.get("inferred_dimension") != "3d":
            return {
                "stage": "generate_3d",
                "status": "failed",
                "returncode": completed.returncode,
                "error": "OpenBabel output is not a complete 3D V2000 SDF",
                "inspection": inspection,
                "command": "obabel ligand_2d.sdf -O ligand_3d.sdf --gen3d -h",
            }
        artifacts: list[dict[str, Any]] = []
        if store_outputs:
            artifacts.append(
                await _save_artifact(
                    generated.encode("utf-8"),
                    filename="ligand_3d.sdf",
                    job_id=job_id,
                    category="structures",
                )
            )
        return {
            "stage": "generate_3d",
            "status": "completed",
            "returncode": completed.returncode,
            "output_sdf": {"included": not store_outputs, "text": generated if not store_outputs else None},
            "_pipeline_sdf_text": generated,
            "inspection": inspection,
            "artifacts": artifacts,
            "command": "obabel ligand_2d.sdf -O ligand_3d.sdf --gen3d -h",
        }


async def _load_stage_text(data: str | None, object_name: str | None, path_value: str | None, label: str) -> str:
    if data and data.strip():
        return data
    if object_name and object_name.strip():
        return (await storage.download_file(object_name)).decode("utf-8", errors="replace")
    if path_value and path_value.strip():
        path = Path(path_value).expanduser()
        if not path.exists():
            raise ValueError(f"{label} path not found: {path_value}")
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Provide {label}_data, {label}_object_name, or {label}_path")


async def _run_obabel_pdbqt(
    *,
    ligand_3d_text: str,
    job_id: str,
    ph: float,
    charge_model: str,
    timeout_seconds: int,
    store_outputs: bool,
) -> dict[str, Any]:
    obabel = shutil.which("obabel")
    if not obabel:
        return _blocked_stage(
            "prepare_pdbqt",
            "pdbqt_preparation_runtime_not_available",
            ["obabel or meeko"],
            "Run this stage in the ligand worker runtime with OpenBabel installed.",
            command_preview="obabel ligand_3d.sdf -O ligand.pdbqt -p <pH> --partialcharge gasteiger",
        )

    with tempfile.TemporaryDirectory(prefix="ligand-pdbqt-") as tmp:
        workdir = Path(tmp)
        input_path = workdir / "ligand_3d.sdf"
        output_path = workdir / "ligand.pdbqt"
        input_path.write_text(ligand_3d_text, encoding="utf-8")
        command = [
            obabel,
            str(input_path),
            "-O",
            str(output_path),
            "-p",
            str(ph),
            "--partialcharge",
            charge_model,
        ]
        completed = await asyncio.to_thread(_run_command, command, workdir, timeout_seconds)
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        if completed.returncode != 0 or not output_path.exists():
            return _failed_result(
                "prepare_pdbqt",
                completed,
                output,
                "OpenBabel did not create ligand.pdbqt",
                "obabel ligand_3d.sdf -O ligand.pdbqt -p <pH> --partialcharge <charge_model>",
            )

        pdbqt = output_path.read_text(encoding="utf-8", errors="replace")
        artifacts: list[dict[str, Any]] = []
        if store_outputs:
            artifacts.append(
                await _save_artifact(
                    pdbqt.encode("utf-8"),
                    filename="ligand.pdbqt",
                    job_id=job_id,
                    category="docking",
                )
            )
        return {
            "stage": "prepare_pdbqt",
            "status": "completed",
            "returncode": completed.returncode,
            "output_pdbqt": {"included": not store_outputs, "text": pdbqt if not store_outputs else None},
            "_pipeline_pdbqt_text": pdbqt,
            "artifacts": artifacts,
            "command": "obabel ligand_3d.sdf -O ligand.pdbqt -p <pH> --partialcharge <charge_model>",
        }


def _axis_value(values: dict[str, float], axis: str) -> str:
    if axis not in values:
        raise ValueError(f"Missing Vina box value: {axis}")
    return str(values[axis])


def _failed_result(stage: str, completed: subprocess.CompletedProcess[str], output: str, fallback: str, command: str) -> dict[str, Any]:
    result = {
        "stage": stage,
        "status": "failed",
        "returncode": completed.returncode,
        "error": output[-4000:] if output else fallback,
        "command": command,
    }
    if completed.returncode == 124:
        result["failed_reason"] = "command_timeout"
    return result


async def _run_vina_docking(
    *,
    ligand_pdbqt_text: str,
    receptor_pdbqt_text: str,
    pocket_center: dict[str, float],
    pocket_size: dict[str, float],
    vina_exhaustiveness: int,
    vina_num_modes: int,
    job_id: str,
    timeout_seconds: int,
    store_outputs: bool,
) -> dict[str, Any]:
    vina = shutil.which("vina")
    if not vina:
        return _blocked_stage(
            "vina_docking",
            "vina_runtime_not_available",
            ["vina"],
            "Run this stage in the ligand worker runtime with AutoDock Vina installed.",
        )

    with tempfile.TemporaryDirectory(prefix="ligand-vina-") as tmp:
        workdir = Path(tmp)
        ligand_path = workdir / "ligand.pdbqt"
        receptor_path = workdir / "receptor.pdbqt"
        output_path = workdir / "docked_poses.pdbqt"
        ligand_path.write_text(ligand_pdbqt_text, encoding="utf-8")
        receptor_path.write_text(receptor_pdbqt_text, encoding="utf-8")
        command = [
            vina,
            "--receptor",
            str(receptor_path),
            "--ligand",
            str(ligand_path),
            "--center_x",
            _axis_value(pocket_center, "x"),
            "--center_y",
            _axis_value(pocket_center, "y"),
            "--center_z",
            _axis_value(pocket_center, "z"),
            "--size_x",
            _axis_value(pocket_size, "x"),
            "--size_y",
            _axis_value(pocket_size, "y"),
            "--size_z",
            _axis_value(pocket_size, "z"),
            "--exhaustiveness",
            str(vina_exhaustiveness),
            "--num_modes",
            str(vina_num_modes),
            "--out",
            str(output_path),
        ]
        completed = await asyncio.to_thread(_run_command, command, workdir, timeout_seconds)
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        if completed.returncode != 0 or not output_path.exists():
            return _failed_result(
                "vina_docking",
                completed,
                output,
                "Vina did not create docked_poses.pdbqt",
                "vina --receptor receptor.pdbqt --ligand ligand.pdbqt --center_* --size_* --out docked_poses.pdbqt",
            )

        docked = output_path.read_text(encoding="utf-8", errors="replace")
        artifacts: list[dict[str, Any]] = []
        if store_outputs:
            artifacts.extend([
                await _save_artifact(
                    docked.encode("utf-8"),
                    filename="docked_poses.pdbqt",
                    job_id=job_id,
                    category="docking",
                ),
                await _save_artifact(
                    output.encode("utf-8"),
                    filename="vina.log",
                    job_id=job_id,
                    category="logs",
                ),
            ])
        return {
            "stage": "vina_docking",
            "status": "completed",
            "returncode": completed.returncode,
            "output_pdbqt": {"included": not store_outputs, "text": docked if not store_outputs else None},
            "vina_output": output[-4000:],
            "artifacts": artifacts,
            "command": "vina --receptor receptor.pdbqt --ligand ligand.pdbqt --center_* --size_* --out docked_poses.pdbqt",
        }


def _acpype_binary() -> str | None:
    found = shutil.which("acpype")
    if found:
        return found
    candidate = Path("/opt/venv/bin/acpype")
    return str(candidate) if candidate.exists() else None


async def _run_ligand_topology(
    *,
    ligand_3d_text: str,
    net_charge: int,
    ligand_force_field: str,
    job_id: str,
    timeout_seconds: int,
    store_outputs: bool,
) -> dict[str, Any]:
    acpype = _acpype_binary()
    obabel = shutil.which("obabel")
    if not acpype:
        return _blocked_stage(
            "ligand_topology",
            "ligand_topology_runtime_not_available",
            ["acpype", "AmberTools"],
            "Run this stage in a ligand worker runtime with ACPYPE/AmberTools installed.",
        )
    if not obabel:
        return _blocked_stage(
            "ligand_topology",
            "mol2_conversion_runtime_not_available",
            ["obabel"],
            "Convert the optimized 3D ligand to MOL2 before topology generation.",
        )

    with tempfile.TemporaryDirectory(prefix="ligand-topology-") as tmp:
        workdir = Path(tmp)
        sdf_path = workdir / "ligand_3d.sdf"
        mol2_path = workdir / "ligand.mol2"
        sdf_path.write_text(ligand_3d_text, encoding="utf-8")
        mol2_command = [obabel, str(sdf_path), "-O", str(mol2_path), "--partialcharge", "gasteiger"]
        mol2_completed = await asyncio.to_thread(_run_command, mol2_command, workdir, timeout_seconds)
        mol2_output = "\n".join(part for part in (mol2_completed.stdout, mol2_completed.stderr) if part).strip()
        if mol2_completed.returncode != 0 or not mol2_path.exists():
            return _failed_result(
                "ligand_topology",
                mol2_completed,
                mol2_output,
                "OpenBabel did not create ligand.mol2",
                "obabel ligand_3d.sdf -O ligand.mol2 --partialcharge gasteiger",
            )

        command = [
            acpype,
            "-i",
            str(mol2_path),
            "-b",
            "ligand",
            "-c",
            "gas",
            "-n",
            str(net_charge),
            "-a",
            ligand_force_field,
            "-o",
            "gmx",
        ]
        completed = await asyncio.to_thread(_run_command, command, workdir, timeout_seconds)
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        acpype_dir = workdir / "ligand.acpype"
        artifact_paths = [path for path in acpype_dir.rglob("*") if path.is_file()] if acpype_dir.exists() else []
        topology_paths = [
            path for path in artifact_paths
            if path.suffix.lower() in {".itp", ".top", ".gro"} and path.stat().st_size > 0
        ]
        if completed.returncode != 0 or not topology_paths:
            return _failed_result(
                "ligand_topology",
                completed,
                output,
                "ACPYPE did not create topology artifacts",
                "acpype -i ligand.mol2 -b ligand -c gas -n <net_charge> -a <ligand_force_field> -o gmx",
            )

        artifacts: list[dict[str, Any]] = []
        if store_outputs:
            for path in artifact_paths:
                if path.suffix.lower() in {".itp", ".top", ".gro", ".mol2"}:
                    artifacts.append(
                        await _save_artifact(
                            path.read_bytes(),
                            filename=path.name,
                            job_id=job_id,
                            category="topology",
                        )
                    )
        return {
            "stage": "ligand_topology",
            "status": "completed",
            "returncode": completed.returncode,
            "artifact_count": len(topology_paths),
            "topology_artifact_names": sorted(path.name for path in topology_paths),
            "topology_artifact_manifest": [
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in sorted(topology_paths, key=lambda item: item.name)
            ],
            "evidence_level": "executed_topology_artifacts",
            "artifacts": artifacts,
            "command": "acpype -i ligand.mol2 -b ligand -c gas -n <net_charge> -a <ligand_force_field> -o gmx",
        }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return bool(value)
    return True


def _missing_box_axes(value: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [label]
    missing = []
    for axis in ("x", "y", "z"):
        if axis not in value or value[axis] is None or (isinstance(value[axis], str) and not value[axis].strip()):
            missing.append(f"{label}.{axis}")
            continue
        try:
            numeric = float(value[axis])
        except (TypeError, ValueError):
            missing.append(f"{label}.{axis}_number")
            continue
        if label == "pocket_size" and numeric <= 0:
            missing.append(f"{label}.{axis}_positive")
    return missing


def _missing_parameter_names(stage: str, params: dict[str, Any]) -> list[str]:
    if stage == "prepare_pdbqt":
        missing = []
        if not any(_present(params.get(key)) for key in ("ligand_3d_data", "ligand_3d_object_name", "ligand_3d_path")):
            missing.append("ligand_3d input")
        for key in ("ph", "protonation_policy", "charge_model"):
            if not _present(params.get(key)):
                missing.append(key)
        return missing
    if stage == "vina_docking":
        missing = []
        if not any(_present(params.get(key)) for key in ("ligand_pdbqt_data", "ligand_pdbqt_object_name", "ligand_pdbqt_path")):
            missing.append("ligand_pdbqt input")
        if not any(_present(params.get(key)) for key in ("receptor_pdbqt_data", "receptor_pdbqt_object_name", "receptor_pdbqt_path")):
            missing.append("receptor_pdbqt input")
        missing.extend(_missing_box_axes(params.get("pocket_center"), "pocket_center"))
        missing.extend(_missing_box_axes(params.get("pocket_size"), "pocket_size"))
        for key in ("vina_exhaustiveness", "vina_num_modes"):
            try:
                if int(params.get(key)) <= 0:
                    missing.append(f"{key}_positive")
            except (TypeError, ValueError):
                missing.append(f"{key}_integer")
        return missing
    if stage == "ligand_topology":
        missing = []
        if not any(_present(params.get(key)) for key in ("ligand_3d_data", "ligand_3d_object_name", "ligand_3d_path")):
            missing.append("ligand_3d input")
        for key in ("net_charge", "ligand_force_field"):
            if not _present(params.get(key)):
                missing.append(key)
        return missing
    return []


def _blocked_stage(
    stage: str,
    reason: str,
    required_tools: list[str],
    next_action: str,
    *,
    missing_parameters: list[str] | None = None,
    command_preview: str | None = None,
    provided_inputs: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "blocked",
        "blocked_reason": reason,
        "required_tools": required_tools,
        "required_parameters": _STAGE_REQUIRED_PARAMETERS.get(stage, []),
        "missing_parameters": missing_parameters or [],
        "provided_inputs": provided_inputs or {},
        "command_preview": command_preview,
        "next_action": next_action,
    }


def _valid_topology_evidence(stage: dict[str, Any]) -> bool:
    manifest = stage.get("topology_artifact_manifest") or []
    names = stage.get("topology_artifact_names") or []
    if stage.get("status") != "completed" or stage.get("evidence_level") != "executed_topology_artifacts":
        return False
    if not manifest or int(stage.get("artifact_count") or 0) != len(manifest):
        return False
    manifest_names: list[str] = []
    for entry in manifest:
        name = str(entry.get("name") or "")
        sha256 = str(entry.get("sha256") or "").lower()
        if Path(name).suffix.lower() not in {".itp", ".top", ".gro"}:
            return False
        if int(entry.get("size") or 0) <= 0 or len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            return False
        manifest_names.append(name)
    return sorted(names) == sorted(manifest_names)


def _stage_readiness(stage_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = {}
    blocked: list[str] = []
    failed: list[str] = []
    ready_or_completed: list[str] = []
    for item in stage_results:
        stage = str(item.get("stage") or "unknown")
        status = str(item.get("status") or "unknown")
        by_stage[stage] = {
            "status": status,
            "blocked_reason": item.get("blocked_reason"),
            "missing_parameters": item.get("missing_parameters") or [],
            "required_tools": item.get("required_tools") or [],
            "artifact_count": int(item.get("artifact_count") or 0),
            "topology_artifact_names": item.get("topology_artifact_names") or [],
            "topology_artifact_manifest": item.get("topology_artifact_manifest") or [],
            "evidence_level": item.get("evidence_level"),
            "artifacts": item.get("artifacts") or [],
        }
        if status == "blocked":
            blocked.append(stage)
        elif status == "failed":
            failed.append(stage)
        elif status in {"ready", "completed"}:
            ready_or_completed.append(stage)
    return {
        "version": 1,
        "ready_or_completed": ready_or_completed,
        "blocked": blocked,
        "failed": failed,
        "by_stage": by_stage,
        "can_enter_docking": all(
            by_stage.get(stage, {}).get("status") in {"ready", "completed"}
            for stage in ("prepare_pdbqt", "vina_docking")
        ),
        "can_enter_gromacs_complex_md": _valid_topology_evidence(by_stage.get("ligand_topology", {})),
        "gromacs_complex_md_blocked_reason": (
            None
            if _valid_topology_evidence(by_stage.get("ligand_topology", {}))
            else "topology_evidence_incomplete"
        ),
    }


async def ligand_preprocess(
    sdf_data: str | None = None,
    sdf_object_name: str | None = None,
    sdf_path: str | None = None,
    stages: list[str] | None = None,
    ligand_name: str | None = None,
    ligand_3d_data: str | None = None,
    ligand_3d_object_name: str | None = None,
    ligand_3d_path: str | None = None,
    ligand_pdbqt_data: str | None = None,
    ligand_pdbqt_object_name: str | None = None,
    ligand_pdbqt_path: str | None = None,
    receptor_pdbqt_data: str | None = None,
    receptor_pdbqt_object_name: str | None = None,
    receptor_pdbqt_path: str | None = None,
    ph: float | None = 7.4,
    protonation_policy: str | None = "physiological_pH_manual_review",
    charge_model: str | None = "gasteiger",
    pocket_center: dict[str, float] | None = None,
    pocket_size: dict[str, float] | None = None,
    vina_exhaustiveness: int = 8,
    vina_num_modes: int = 9,
    ligand_force_field: str | None = "gaff2",
    net_charge: int | None = 0,
    store_outputs: bool = True,
    timeout_seconds: int = 300,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Inspect and optionally preprocess a ligand for docking and GROMACS."""
    requested_stages = stages or ["preflight"]
    invalid = [stage for stage in requested_stages if stage not in _VALID_STAGES]
    if invalid:
        raise ValueError(f"Invalid ligand preprocessing stage(s): {invalid}. Valid stages: {sorted(_VALID_STAGES)}")

    job_id = uuid.uuid4().hex
    _progress(progress_callback, 5, "Loading ligand SDF", "load_input", 1, 5)
    sdf_text, input_summary = await _load_sdf_text(sdf_data, sdf_object_name, sdf_path)
    sdf_inspection = _parse_v2000_sdf(sdf_text)
    if not _sdf_can_continue(sdf_inspection):
        return {
            "status": "blocked",
            "blocked_reason": "invalid_or_unsupported_sdf",
            "job_id": job_id,
            "input": input_summary,
            "sdf": sdf_inspection,
            "artifacts": [],
            "artifact_manifest": _artifact_manifest([]),
        }

    _progress(progress_callback, 20, "Checking ligand toolchain", "preflight", 2, 5)
    toolchain = _toolchain_status()
    stage_params = {
        "ligand_name": ligand_name,
        "ligand_3d_data": ligand_3d_data,
        "ligand_3d_object_name": ligand_3d_object_name,
        "ligand_3d_path": ligand_3d_path,
        "ligand_pdbqt_data": ligand_pdbqt_data,
        "ligand_pdbqt_object_name": ligand_pdbqt_object_name,
        "ligand_pdbqt_path": ligand_pdbqt_path,
        "receptor_pdbqt_data": receptor_pdbqt_data,
        "receptor_pdbqt_object_name": receptor_pdbqt_object_name,
        "receptor_pdbqt_path": receptor_pdbqt_path,
        "ph": ph,
        "protonation_policy": protonation_policy,
        "charge_model": charge_model,
        "pocket_center": pocket_center,
        "pocket_size": pocket_size,
        "vina_exhaustiveness": vina_exhaustiveness,
        "vina_num_modes": vina_num_modes,
        "ligand_force_field": ligand_force_field,
        "net_charge": net_charge,
    }
    stage_results: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    generated_ligand_3d_text: str | None = None
    generated_ligand_pdbqt_text: str | None = None
    if "preflight" in requested_stages:
        missing = []
        if not toolchain["openbabel"]["available"]:
            missing.extend(["conformer_generation", "pdbqt_preparation"])
        if not toolchain["vina"]["available"]:
            missing.append("vina_docking")
        if not (toolchain["acpype"]["available"] or _acpype_binary()):
            missing.append("ligand_topology")
        if not toolchain["gromacs"]["available"]:
            missing.append("gromacs_md")
        stage_results.append({
            "stage": "preflight",
            "status": "ready" if not missing else "blocked",
            "missing_requirements": missing,
        })

    if "generate_3d" in requested_stages:
        _progress(progress_callback, 40, "Generating 3D ligand conformer with OpenBabel", "generate_3d", 3, 5)
        result = await _run_obabel_gen3d(
            sdf_text=sdf_text,
            job_id=job_id,
            timeout_seconds=timeout_seconds,
            store_outputs=store_outputs,
        )
        pipeline_sdf = result.pop("_pipeline_sdf_text", None)
        if isinstance(pipeline_sdf, str) and pipeline_sdf:
            generated_ligand_3d_text = pipeline_sdf
        stage_results.append(result)
        artifacts.extend(result.get("artifacts") if isinstance(result.get("artifacts"), list) else [])

    if "prepare_pdbqt" in requested_stages:
        if generated_ligand_3d_text and not any(_present(stage_params.get(key)) for key in ("ligand_3d_data", "ligand_3d_object_name", "ligand_3d_path")):
            stage_params["ligand_3d_data"] = generated_ligand_3d_text
            ligand_3d_data = generated_ligand_3d_text
        missing_parameters = _missing_parameter_names("prepare_pdbqt", stage_params)
        missing_tools = [] if toolchain["openbabel"]["available"] else ["obabel or meeko"]
        if missing_parameters or missing_tools:
            stage_results.append(_blocked_stage(
                "prepare_pdbqt",
                "missing_parameters" if missing_parameters else "pdbqt_preparation_runtime_not_available",
                missing_tools,
                "Provide 3D ligand input plus pH/protonation/charge policy, then run in the ligand worker runtime.",
                missing_parameters=missing_parameters,
                command_preview="obabel ligand_3d.sdf -O ligand.pdbqt -p <pH> --partialcharge gasteiger",
                provided_inputs={
                    "ligand_3d": any(_present(stage_params.get(key)) for key in ("ligand_3d_data", "ligand_3d_object_name", "ligand_3d_path")),
                    "ph": _present(ph),
                    "protonation_policy": _present(protonation_policy),
                    "charge_model": _present(charge_model),
                },
            ))
        else:
            ligand_3d_text = await _load_stage_text(ligand_3d_data, ligand_3d_object_name, ligand_3d_path, "ligand_3d")
            result = await _run_obabel_pdbqt(
                ligand_3d_text=ligand_3d_text,
                job_id=job_id,
                ph=ph if ph is not None else 7.4,
                charge_model=charge_model or "gasteiger",
                timeout_seconds=timeout_seconds,
                store_outputs=store_outputs,
            )
            pipeline_pdbqt = result.pop("_pipeline_pdbqt_text", None)
            if isinstance(pipeline_pdbqt, str) and pipeline_pdbqt:
                generated_ligand_pdbqt_text = pipeline_pdbqt
            stage_results.append(result)
            artifacts.extend(result.get("artifacts") if isinstance(result.get("artifacts"), list) else [])
    if "vina_docking" in requested_stages:
        if generated_ligand_pdbqt_text and not any(_present(stage_params.get(key)) for key in ("ligand_pdbqt_data", "ligand_pdbqt_object_name", "ligand_pdbqt_path")):
            stage_params["ligand_pdbqt_data"] = generated_ligand_pdbqt_text
            ligand_pdbqt_data = generated_ligand_pdbqt_text
        missing_parameters = _missing_parameter_names("vina_docking", stage_params)
        missing_tools = [] if toolchain["vina"]["available"] else ["vina"]
        if missing_parameters or missing_tools:
            stage_results.append(_blocked_stage(
                "vina_docking",
                "missing_parameters" if missing_parameters else "vina_runtime_not_available",
                missing_tools,
                "Provide ligand/receptor PDBQT and ChimeraX-derived pocket box, then run Vina in ligand worker.",
                missing_parameters=missing_parameters,
                command_preview=(
                    "vina --receptor receptor.pdbqt --ligand ligand.pdbqt "
                    "--center_x <x> --center_y <y> --center_z <z> "
                    "--size_x <x> --size_y <y> --size_z <z>"
                ),
                provided_inputs={
                    "ligand_pdbqt": any(_present(stage_params.get(key)) for key in ("ligand_pdbqt_data", "ligand_pdbqt_object_name", "ligand_pdbqt_path")),
                    "receptor_pdbqt": any(_present(stage_params.get(key)) for key in ("receptor_pdbqt_data", "receptor_pdbqt_object_name", "receptor_pdbqt_path")),
                    "pocket_center": _present(pocket_center),
                    "pocket_size": _present(pocket_size),
                },
            ))
        else:
            ligand_pdbqt_text = await _load_stage_text(ligand_pdbqt_data, ligand_pdbqt_object_name, ligand_pdbqt_path, "ligand_pdbqt")
            receptor_pdbqt_text = await _load_stage_text(receptor_pdbqt_data, receptor_pdbqt_object_name, receptor_pdbqt_path, "receptor_pdbqt")
            result = await _run_vina_docking(
                ligand_pdbqt_text=ligand_pdbqt_text,
                receptor_pdbqt_text=receptor_pdbqt_text,
                pocket_center=pocket_center or {},
                pocket_size=pocket_size or {},
                vina_exhaustiveness=vina_exhaustiveness,
                vina_num_modes=vina_num_modes,
                job_id=job_id,
                timeout_seconds=timeout_seconds,
                store_outputs=store_outputs,
            )
            stage_results.append(result)
            artifacts.extend(result.get("artifacts") if isinstance(result.get("artifacts"), list) else [])
    if "ligand_topology" in requested_stages:
        if generated_ligand_3d_text and not any(_present(stage_params.get(key)) for key in ("ligand_3d_data", "ligand_3d_object_name", "ligand_3d_path")):
            stage_params["ligand_3d_data"] = generated_ligand_3d_text
            ligand_3d_data = generated_ligand_3d_text
        missing_parameters = _missing_parameter_names("ligand_topology", stage_params)
        topology_runtime_ready = bool(toolchain["acpype"]["available"] or _acpype_binary())
        missing_tools = [] if topology_runtime_ready else ["acpype", "AmberTools"]
        if missing_parameters or missing_tools:
            stage_results.append(_blocked_stage(
                "ligand_topology",
                "missing_parameters" if missing_parameters else "ligand_topology_runtime_not_available",
                missing_tools,
                "Provide optimized 3D ligand, net charge, and GAFF2/AmberTools runtime before GROMACS complex MD.",
                missing_parameters=missing_parameters,
                command_preview="acpype -i ligand_3d.mol2 -b ligand -c gas -n <net_charge>",
                provided_inputs={
                    "ligand_3d": any(_present(stage_params.get(key)) for key in ("ligand_3d_data", "ligand_3d_object_name", "ligand_3d_path")),
                    "net_charge": _present(net_charge),
                    "ligand_force_field": _present(ligand_force_field),
                },
            ))
        else:
            ligand_3d_text = await _load_stage_text(ligand_3d_data, ligand_3d_object_name, ligand_3d_path, "ligand_3d")
            result = await _run_ligand_topology(
                ligand_3d_text=ligand_3d_text,
                net_charge=net_charge if net_charge is not None else 0,
                ligand_force_field=ligand_force_field or "gaff2",
                job_id=job_id,
                timeout_seconds=timeout_seconds,
                store_outputs=store_outputs,
            )
            stage_results.append(result)
            artifacts.extend(result.get("artifacts") if isinstance(result.get("artifacts"), list) else [])

    blocked = [item for item in stage_results if item.get("status") == "blocked"]
    failed = [item for item in stage_results if item.get("status") == "failed"]
    status = "failed" if failed else ("blocked" if blocked else "completed")
    stage_readiness = _stage_readiness(stage_results)
    _progress(progress_callback, 100, "Ligand preprocessing contract finished", "finished", 5, 5)
    return {
        "status": status,
        "job_id": job_id,
        "input": input_summary,
        "sdf": sdf_inspection,
        "toolchain": toolchain,
        "stage_results": stage_results,
        "stage_readiness": stage_readiness,
        "stage_contract": {
            "version": 1,
            "requested_stages": requested_stages,
            "parameters": {
                "ligand_name": ligand_name,
                "ph": ph,
                "protonation_policy": protonation_policy,
                "charge_model": charge_model,
                "pocket_center": pocket_center,
                "pocket_size": pocket_size,
                "vina_exhaustiveness": vina_exhaustiveness,
                "vina_num_modes": vina_num_modes,
                "ligand_force_field": ligand_force_field,
                "net_charge": net_charge,
            },
            "required_parameters": {
                stage: _STAGE_REQUIRED_PARAMETERS[stage]
                for stage in requested_stages
                if stage in _STAGE_REQUIRED_PARAMETERS
            },
        },
        "artifacts": artifacts,
        "artifact_manifest": _artifact_manifest(artifacts),
        "scientific_boundary": {
            "input_2d_sdf_can_enter_md_directly": False,
            "requires_3d_conformer_before_docking": True,
            "requires_ligand_topology_before_gromacs": True,
        },
        "next_steps": [
            "Install/package OpenBabel or RDKit for 2D->3D conformer generation.",
            "Define protonation/charge policy and PDBQT preparation runtime.",
            "Provide receptor preprocessing and ChimeraX pocket box parameters for Vina.",
            "Install/package ACPYPE/Antechamber before GROMACS complex MD.",
        ],
    }


ToolRegistry.register(
    name="ligand_preprocess",
    description=(
        "Ligand preprocessing gate for docking and GROMACS MD. Inspects 2D SDF input, "
        "checks OpenBabel/Vina/ACPYPE/GROMACS readiness, and performs real 2D->3D "
        "OpenBabel conversion only when the runtime is installed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sdf_data": {"type": "string", "description": "Raw SDF text."},
            "sdf_object_name": {"type": "string", "description": "Stored SDF object name."},
            "sdf_path": {"type": "string", "description": "Local SDF path for controlled host-side execution."},
            "ligand_name": {"type": "string", "description": "Human-readable ligand/substrate name."},
            "ligand_3d_data": {"type": "string", "description": "Optimized 3D ligand text for PDBQT/topology stages."},
            "ligand_3d_object_name": {"type": "string", "description": "Stored optimized 3D ligand object name."},
            "ligand_3d_path": {"type": "string", "description": "Local optimized 3D ligand path."},
            "ligand_pdbqt_data": {"type": "string", "description": "Prepared ligand PDBQT text for Vina."},
            "ligand_pdbqt_object_name": {"type": "string", "description": "Stored ligand PDBQT object name."},
            "ligand_pdbqt_path": {"type": "string", "description": "Local ligand PDBQT path."},
            "receptor_pdbqt_data": {"type": "string", "description": "Prepared receptor PDBQT text for Vina."},
            "receptor_pdbqt_object_name": {"type": "string", "description": "Stored receptor PDBQT object name."},
            "receptor_pdbqt_path": {"type": "string", "description": "Local receptor PDBQT path."},
            "stages": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(_VALID_STAGES)},
                "description": "Pipeline stages to run. Defaults to preflight.",
            },
            "ph": {"type": "number", "description": "Target pH for protonation policy.", "default": 7.4},
            "protonation_policy": {"type": "string", "description": "Named protonation policy for reproducibility."},
            "charge_model": {"type": "string", "description": "Partial charge model, e.g. gasteiger or am1-bcc."},
            "pocket_center": {
                "type": "object",
                "description": "Vina box center from ChimeraX.",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
            },
            "pocket_size": {
                "type": "object",
                "description": "Vina box size.",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
            },
            "vina_exhaustiveness": {"type": "integer", "description": "Vina exhaustiveness.", "default": 8},
            "vina_num_modes": {"type": "integer", "description": "Number of Vina poses to retain.", "default": 9},
            "ligand_force_field": {"type": "string", "description": "Ligand topology force field family, e.g. gaff2.", "default": "gaff2"},
            "net_charge": {"type": "integer", "description": "Ligand net charge for topology generation.", "default": 0},
            "store_outputs": {"type": "boolean", "description": "Store generated artifacts in object storage.", "default": True},
            "timeout_seconds": {"type": "integer", "description": "Per-command timeout.", "default": 300},
        },
        "required": [],
    },
    handler=ligand_preprocess,
    is_async=True,
    category="molecular_dynamics",
    timeout_seconds=1800,
    errors=[
        {
            "reason": "invalid_input",
            "code": "INVALID_LIGAND_INPUT",
            "when": "SDF input is missing or unsupported",
            "recovery": "Provide sdf_data, sdf_object_name, or sdf_path containing V2000 SDF.",
        },
        {
            "reason": "runtime",
            "code": "LIGAND_TOOLCHAIN_MISSING",
            "when": "OpenBabel/Vina/ACPYPE/GROMACS runtime is missing",
            "recovery": "Install or containerize the required scientific toolchain before enabling live stages.",
        },
    ],
)
