"""GROMACS — real minimal molecular dynamics pipeline.

This tool intentionally does not fabricate MD metrics. It requires a real PDB
structure and a working GROMACS executable (`gmx` or `gmx_mpi`). If either is
missing, it returns an explicit actionable error instead of simulated results.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote
import uuid
from pathlib import Path
from typing import Any

from app.tools.registry import ToolRegistry
from app.tools.tool_capability_contract import merge_capability_contract

_WATER_MODELS = ["tip3p", "tip4p", "tip4pew", "tip5p", "spc", "spce", "opc"]
_FORCE_FIELDS = [
    "amber99sb-ildn",
    "amber99sb",
    "amber03",
    "charmm27",
    "gromos54a7",
    "gromos53a6",
    "oplsaa",
]
_FORCE_FIELD_ALIASES = {
    "opls-aa": "oplsaa",
}
_WATER_RESIDUES = {"HOH", "WAT", "H2O", "SOL", "TIP3", "TIP4", "SPC"}
_COMMON_IONS = {
    "AL",
    "BA",
    "BR",
    "CA",
    "CD",
    "CL",
    "CO",
    "CS",
    "CU",
    "FE",
    "HG",
    "IOD",
    "K",
    "LI",
    "MG",
    "MN",
    "NA",
    "NI",
    "RB",
    "SR",
    "ZN",
}
_COMMON_COFACTORS = {
    "ACP",
    "ADP",
    "AMP",
    "ATP",
    "B12",
    "COA",
    "FAD",
    "FMN",
    "GDP",
    "GMP",
    "GTP",
    "HEB",
    "HEC",
    "HEM",
    "NAP",
    "NAD",
    "NDP",
    "PLP",
    "SAM",
    "SAH",
    "THF",
}
_AA_ONE_TO_THREE = {
    "A": "ALA",
    "R": "ARG",
    "N": "ASN",
    "D": "ASP",
    "C": "CYS",
    "Q": "GLN",
    "E": "GLU",
    "G": "GLY",
    "H": "HIS",
    "I": "ILE",
    "L": "LEU",
    "K": "LYS",
    "M": "MET",
    "F": "PHE",
    "P": "PRO",
    "S": "SER",
    "T": "THR",
    "W": "TRP",
    "Y": "TYR",
    "V": "VAL",
}
_AA_THREE_TO_ONE = {value: key for key, value in _AA_ONE_TO_THREE.items()}
_BACKBONE_ATOMS = {"N", "CA", "C", "O", "OXT"}
_MINIMAL_SIDECHAIN_ATOMS = {
    "ALA": {"CB"},
    "GLY": set(),
}
_HISTIDINE_NAMES = {"HIS", "HID", "HIE", "HIP", "HSD", "HSE", "HSP"}
_ENERGY_TERM_SELECTION_CANDIDATES = [
    ["Potential", "Kinetic-En.", "Total-Energy"],
    ["Potential-Energy", "Kinetic-Energy", "Total Energy"],
    ["Potential Energy", "Kinetic En.", "Total-Energy"],
]
_ENERGY_TERM_SELECTIONS = _ENERGY_TERM_SELECTION_CANDIDATES[0]
_ANALYSIS_GROUP_SELECTION_CANDIDATES = {
    "rms": [["Backbone", "Backbone"], ["Protein", "Protein"], ["4", "4"]],
    "rmsf": [["Backbone"], ["Protein"], ["4"]],
    "gyrate": [["Protein"], ["Backbone"], ["1"]],
    "sasa": [["Protein"], ["Backbone"], ["1"]],
    "hbond_intra_protein": [["Protein", "Protein"], ["Backbone", "Backbone"], ["1", "1"]],
    "hbond_protein_solvent": [["Protein", "SOL"], ["Protein", "Water"], ["Protein", "non-Protein"], ["1", "13"]],
}
_ANALYSIS_GROUP_SELECTIONS = {
    key: candidates[0]
    for key, candidates in _ANALYSIS_GROUP_SELECTION_CANDIDATES.items()
}
_TOPOLOGY_WARNING_TAXONOMY = {
    "charge_balance": {
        "severity": "warning",
        "keywords": ["charge", "neutral", "net charge", "charge group"],
    },
    "missing_atoms_or_parameters": {
        "severity": "warning",
        "keywords": ["missing", "atom", "parameter", "not found", "unknown residue", "atomtype"],
    },
    "force_field_parameterization": {
        "severity": "warning",
        "keywords": ["no default", "proper dihedral", "improper", "bond type", "angle type", "cmap"],
    },
    "ligand_or_cofactor_topology": {
        "severity": "warning",
        "keywords": ["ligand", "cofactor", "hetatm", "residue type"],
    },
    "protonation_or_termini": {
        "severity": "warning",
        "keywords": ["protonation", "histidine", "terminus", "terminal"],
    },
    "constraint_or_lincs": {
        "severity": "warning",
        "keywords": ["constraint", "lincs", "settle"],
    },
    "box_or_pbc": {
        "severity": "warning",
        "keywords": ["periodic", "pbc", "box", "cut-off", "cutoff"],
    },
    "solvent_or_ion_setup": {
        "severity": "warning",
        "keywords": ["solvent", "water", "ion", "genion", "replaced"],
    },
}


_IONS_MDP = """integrator = steep
emtol = 1000.0
emstep = 0.01
nsteps = 500
cutoff-scheme = Verlet
coulombtype = PME
rcoulomb = 1.0
rvdw = 1.0
pbc = xyz
"""

_MINIM_MDP = """integrator = steep
emtol = 1000.0
emstep = 0.01
nsteps = 5000
cutoff-scheme = Verlet
coulombtype = PME
rcoulomb = 1.0
rvdw = 1.0
pbc = xyz
"""

_NVT_MDP = """define = -DPOSRES
integrator = md
nsteps = {nvt_steps}
dt = 0.002
tcoupl = V-rescale
tc-grps = Protein Non-Protein
tau_t = 0.1 0.1
ref_t = {temperature_k} {temperature_k}
pcoupl = no
constraints = h-bonds
constraint_algorithm = lincs
cutoff-scheme = Verlet
coulombtype = PME
rcoulomb = 1.0
rvdw = 1.0
pbc = xyz
gen_vel = yes
gen_temp = {temperature_k}
gen_seed = {run_seed}
"""

_NPT_MDP = """define = -DPOSRES
integrator = md
nsteps = {npt_steps}
dt = 0.002
tcoupl = V-rescale
tc-grps = Protein Non-Protein
tau_t = 0.1 0.1
ref_t = {temperature_k} {temperature_k}
pcoupl = C-rescale
pcoupltype = isotropic
tau_p = 2.0
ref_p = {pressure_bar}
compressibility = 4.5e-5
constraints = h-bonds
constraint_algorithm = lincs
cutoff-scheme = Verlet
coulombtype = PME
rcoulomb = 1.0
rvdw = 1.0
pbc = xyz
gen_vel = no
"""

_MD_MDP = """integrator = md
nsteps = {md_steps}
dt = 0.002
nstxout-compressed = 500
nstenergy = 500
nstlog = 500
tcoupl = V-rescale
tc-grps = Protein Non-Protein
tau_t = 0.1 0.1
ref_t = {temperature_k} {temperature_k}
pcoupl = C-rescale
pcoupltype = isotropic
tau_p = 2.0
ref_p = {pressure_bar}
compressibility = 4.5e-5
constraints = h-bonds
constraint_algorithm = lincs
cutoff-scheme = Verlet
coulombtype = PME
rcoulomb = 1.0
rvdw = 1.0
pbc = xyz
gen_vel = no
"""


def _find_gmx() -> str | None:
    configured = os.getenv("GROMACS_BIN", "").strip()
    if configured and shutil.which(configured):
        return configured
    return shutil.which("gmx") or shutil.which("gmx_mpi")


def _installed_force_fields() -> list[str]:
    roots: list[Path] = []
    gmxlib = os.getenv("GMXLIB", "").strip()
    if gmxlib:
        roots.append(Path(gmxlib))
    roots.extend(
        [
            Path("/usr/share/gromacs/top"),
            Path("/usr/local/share/gromacs/top"),
        ]
    )

    seen: set[str] = set()
    installed: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for ff_dir in sorted(root.glob("*.ff")):
            name = ff_dir.name[:-3]
            if name not in seen:
                installed.append(name)
                seen.add(name)
    return installed


def _resolve_force_field(requested: str) -> tuple[str | None, list[str]]:
    installed = _installed_force_fields()
    if not installed:
        installed = list(_FORCE_FIELDS)

    normalized = requested.strip()
    if normalized in installed:
        return normalized, installed

    alias = _FORCE_FIELD_ALIASES.get(normalized)
    if alias and alias in installed:
        return alias, installed

    return None, installed


def _run(
    cmd: list[str],
    cwd: Path,
    *,
    input_text: str | None = None,
    timeout: int = 1800,
) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    output = proc.stdout or ""
    if proc.returncode != 0:
        joined = " ".join(cmd)
        tail = output[-4000:]
        raise RuntimeError(f"GROMACS command failed ({proc.returncode}): {joined}\n{tail}")
    return output


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _parse_xvg_series(path: Path) -> list[tuple[float, float]]:
    if not path.exists():
        return []
    rows: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return rows


def _parse_xvg_multi_series(path: Path) -> list[list[float]]:
    if not path.exists():
        return []
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        try:
            rows.append([float(part) for part in stripped.split()])
        except ValueError:
            continue
    return rows


def _parse_xvg_legends(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    legends: dict[int, str] = {}
    pattern = re.compile(r'@\s+s(\d+)\s+legend\s+"([^"]+)"')
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.search(line)
        if match:
            legends[int(match.group(1)) + 1] = match.group(2).strip()
    return legends


def _last_value(rows: list[tuple[float, float]]) -> float | None:
    return rows[-1][1] if rows else None


def _mean_value(rows: list[tuple[float, float]]) -> float | None:
    if not rows:
        return None
    return sum(v for _, v in rows) / len(rows)


def _max_value(rows: list[tuple[float, float]]) -> float | None:
    if not rows:
        return None
    return max(v for _, v in rows)


def _write_csv(path: Path, rows: list[tuple[float, float]], x_label: str, y_label: str) -> None:
    lines = [f"{x_label},{y_label}"]
    lines.extend(f"{x},{y}" for x, y in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_multi_csv(path: Path, rows: list[list[float]], headers: list[str]) -> None:
    lines = [",".join(headers)]
    lines.extend(",".join(str(value) for value in row[: len(headers)]) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mean_column(rows: list[list[float]], column: int) -> float | None:
    values = [row[column] for row in rows if len(row) > column]
    return sum(values) / len(values) if values else None


def _last_column(rows: list[list[float]], column: int) -> float | None:
    for row in reversed(rows):
        if len(row) > column:
            return row[column]
    return None


def _normalize_energy_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _find_legend_column(legends: dict[int, str], aliases: set[str], fallback: int) -> int:
    normalized_aliases = {_normalize_energy_label(alias) for alias in aliases}
    for column, label in legends.items():
        normalized = _normalize_energy_label(label)
        if normalized in normalized_aliases:
            return column
    return fallback


def _parse_energy_terms(path: Path) -> dict[str, float | None]:
    rows = _parse_xvg_multi_series(path)
    legends = _parse_xvg_legends(path)
    potential_col = _find_legend_column(legends, {"Potential", "Potential-Energy", "Potential Energy", "Epot"}, 1)
    kinetic_col = _find_legend_column(legends, {"Kinetic-En.", "Kinetic-Energy", "Kinetic Energy", "Ekin"}, 2)
    total_col = _find_legend_column(legends, {"Total-Energy", "Total Energy", "Etot", "Total"}, 3)
    return {
        "potential_energy_kjmol": _mean_column(rows, potential_col),
        "kinetic_energy_kjmol": _mean_column(rows, kinetic_col),
        "total_energy_kjmol": _mean_column(rows, total_col),
    }


def _selection_input(selections: list[str]) -> str:
    return "\n".join(selections) + "\n"


def _analysis_selection_input(key: str, candidate_index: int = 0) -> str:
    candidates = _ANALYSIS_GROUP_SELECTION_CANDIDATES[key]
    selections = candidates[min(candidate_index, len(candidates) - 1)]
    return _selection_input(selections)


def _energy_selection_input(candidate_index: int = 0) -> str:
    candidates = _ENERGY_TERM_SELECTION_CANDIDATES
    selections = candidates[min(candidate_index, len(candidates) - 1)]
    return "\n".join(selections) + "\n\n"


def _selection_candidate_inputs(key: str) -> list[str]:
    return [_selection_input(candidate) for candidate in _ANALYSIS_GROUP_SELECTION_CANDIDATES[key]]


def _energy_selection_candidate_inputs() -> list[str]:
    return ["\n".join(candidate) + "\n\n" for candidate in _ENERGY_TERM_SELECTION_CANDIDATES]


def _build_analysis_selection_plan() -> dict[str, Any]:
    """Return the named GROMACS analysis selections used by this pipeline."""
    return {
        "version": 2,
        "group_selections": {key: list(value) for key, value in _ANALYSIS_GROUP_SELECTIONS.items()},
        "energy_terms": list(_ENERGY_TERM_SELECTIONS),
        "group_selection_candidates": {
            key: [list(candidate) for candidate in candidates]
            for key, candidates in _ANALYSIS_GROUP_SELECTION_CANDIDATES.items()
        },
        "energy_term_candidates": [list(candidate) for candidate in _ENERGY_TERM_SELECTION_CANDIDATES],
        "inputs": {
            key: _analysis_selection_input(key)
            for key in _ANALYSIS_GROUP_SELECTIONS
        } | {"energy": _energy_selection_input()},
        "fallback_inputs": {
            key: _selection_candidate_inputs(key)
            for key in _ANALYSIS_GROUP_SELECTIONS
        } | {"energy": _energy_selection_candidate_inputs()},
        "fallback_policy": {
            "mode": "ordered",
            "stop_on_first_success": True,
            "numeric_groups_are_last_resort": True,
        },
        "notes": [
            "Named selections are preferred over numeric group ids because GROMACS index ordering can differ by topology.",
            "Fallback candidates are ordered from most portable named groups to last-resort numeric groups.",
            "If all candidates fail, inspect make_ndx/index output and record the system-specific group names before rerunning.",
        ],
    }


def _run_step_with_selection_fallback(
    run_step,
    *,
    step_number: int,
    name: str,
    cmd: list[str],
    candidate_inputs: list[str],
    workdir: Path,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Run a GROMACS analysis command with ordered selection fallbacks."""
    failures: list[str] = []
    for index, input_text in enumerate(candidate_inputs):
        try:
            run_step(step_number, name, cmd, input_text=input_text, timeout=timeout)
            resolution = {
                "step": name,
                "status": "primary" if index == 0 else "fallback",
                "selected_index": index,
                "attempt_count": index + 1,
                "selected_input": input_text,
            }
            if failures:
                resolution["failures"] = failures
                (workdir / f"{name}.selection_fallback.log.txt").write_text(
                    "\n\n".join(failures),
                    encoding="utf-8",
                    errors="replace",
                )
            return resolution
        except Exception as exc:
            failures.append(f"candidate[{index}] input={input_text!r}\n{exc}")
    (workdir / f"{name}.selection_fallback.log.txt").write_text(
        "\n\n".join(failures),
        encoding="utf-8",
        errors="replace",
    )
    raise RuntimeError(f"All selection candidates failed for {name}: {len(failures)} attempt(s)")


def _warning_keyword_matches(message: str, keyword: str) -> bool:
    normalized_message = message.lower()
    normalized_keyword = keyword.lower()
    if re.search(r"[^a-z0-9]", normalized_keyword):
        return normalized_keyword in normalized_message
    if normalized_keyword == "ion":
        return re.search(r"\bions?\b", normalized_message) is not None
    return re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized_message) is not None


def _classify_topology_warning(message: str) -> dict[str, str]:
    lower = message.lower()
    for category, rule in _TOPOLOGY_WARNING_TAXONOMY.items():
        if any(_warning_keyword_matches(lower, keyword) for keyword in rule["keywords"]):
            return {"category": category, "severity": str(rule["severity"])}
    return {"category": "unclassified", "severity": "info"}


def _parse_hbond_counts(path: Path) -> dict[str, int | None]:
    rows = _parse_xvg_multi_series(path)
    value = _last_column(rows, 1)
    count = int(round(value)) if value is not None else None
    return {
        "intra_protein_hbonds": count,
        "protein_solvent_hbonds": None,
    }


def _parse_hbond_count(path: Path) -> int | None:
    rows = _parse_xvg_multi_series(path)
    value = _last_column(rows, 1)
    return int(round(value)) if value is not None else None


def _scan_topology_warnings(workdir: Path) -> dict[str, Any]:
    warning_patterns = [
        re.compile(r"\bWARNING\b[:\s-]*(.+)", re.I),
        re.compile(r"\bNOTE\b[:\s-]*(.+)", re.I),
    ]
    entries: list[dict[str, str]] = []
    files = sorted(workdir.glob("*.log.txt"))
    for path in files:
        if not any(token in path.name for token in ("pdb2gmx", "grompp")):
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for idx, line in enumerate(lines):
            line_number = idx + 1
            stripped = line.strip()
            for pattern in warning_patterns:
                match = pattern.search(stripped)
                if match:
                    message = match.group(1).strip() or stripped
                    if message.endswith(":") and idx + 1 < len(lines):
                        detail = lines[idx + 1].strip()
                        if detail and not any(p.search(detail) for p in warning_patterns):
                            message = f"{message} {detail}"
                    entries.append(
                        {
                            "file": path.name,
                            "line": str(line_number),
                            "message": message[:500],
                            **_classify_topology_warning(message),
                        }
                    )
                    break

    risk_flags: list[str] = []
    if entries:
        risk_flags.append("gromacs_topology_warnings_present")
    if any("charge" in item["message"].lower() for item in entries):
        risk_flags.append("topology_charge_warning")
    if any("missing" in item["message"].lower() for item in entries):
        risk_flags.append("topology_missing_atom_or_parameter_warning")
    for category in sorted({item.get("category") for item in entries if item.get("category") and item.get("category") != "unclassified"}):
        risk_flags.append(f"topology_{category}_warning")

    warnings = [f"{len(entries)} GROMACS topology/preprocessing warning(s) detected; inspect grompp/pdb2gmx logs."] if entries else []
    return {
        "version": 1,
        "warning_count": len(entries),
        "risk_flags": risk_flags,
        "warnings": warnings,
        "entries": entries[:50],
    }


def _save_artifacts(workdir: Path, artifact_names: list[str], job_id: str) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in artifact_names:
        path = workdir / name
        if not path.exists() or not path.is_file():
            continue
        data = path.read_bytes()
        stored = _sync_upload_file(
            data,
            filename=name,
            content_type=_content_type(name),
            folder=f"md/{job_id}",
        )
        artifacts.append(
            {
                "name": name,
                "size": len(data),
                "object_name": stored.get("object_name"),
                "download_url": (
                    f"{stored.get('download_url')}?filename={quote(name)}"
                    if stored.get("download_url")
                    else None
                ),
            }
        )
    return artifacts


def _artifact_category(name: str) -> str:
    """Classify MD artifacts by how users and downstream reports consume them."""
    if name.endswith(".log.txt") or name.endswith(".log"):
        return "logs"
    if name.endswith(".mdp"):
        return "parameters"
    if name in {"md.xtc", "md.edr"}:
        return "trajectory"
    if name.endswith(".xvg") or name.endswith(".csv"):
        return "analysis"
    if name.endswith(".tpr") or name.endswith(".top") or name.endswith(".itp"):
        return "topology"
    if name.endswith((".pdb", ".gro", ".cif")):
        return "structures"
    return "other"


def _build_artifact_manifest(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a stable manifest grouped by artifact purpose."""
    groups: dict[str, list[dict[str, Any]]] = {
        "structures": [],
        "topology": [],
        "trajectory": [],
        "analysis": [],
        "parameters": [],
        "logs": [],
        "other": [],
    }
    total_size = 0
    for artifact in artifacts:
        name = str(artifact.get("name") or "")
        category = _artifact_category(name)
        normalized = dict(artifact)
        normalized["category"] = category
        groups.setdefault(category, []).append(normalized)
        try:
            total_size += int(artifact.get("size") or 0)
        except (TypeError, ValueError):
            pass

    return {
        "version": 1,
        "total_count": len(artifacts),
        "total_size": total_size,
        "groups": {key: value for key, value in groups.items() if value},
        "counts": {key: len(value) for key, value in groups.items() if value},
    }


def _build_md_interpretation(
    *,
    rmsd_final: float | None,
    rmsd_drift: float | None,
    mean_rmsf: float | None,
    max_rmsf: float | None,
    rg_initial: float | None,
    rg_final: float | None,
    sasa_initial: float | None,
    sasa_final: float | None,
    flexible_regions: list[dict[str, Any]],
    simulation_time_ns: float,
    protocol_review: dict[str, Any] | None = None,
    energetics: dict[str, float | None] | None = None,
    interactions: dict[str, int | None] | None = None,
    analysis_files: dict[str, bool] | None = None,
    structure_preparation: dict[str, Any] | None = None,
    replicate_consistency: dict[str, Any] | None = None,
    topology_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a conservative, structured interpretation from real MD metrics."""
    findings: list[str] = []
    warnings: list[str] = []
    next_steps: list[str] = []
    quality_gates: list[dict[str, Any]] = []
    missing_evidence: list[dict[str, str]] = []
    verdict = "needs_review"

    if simulation_time_ns < 1.0:
        warnings.append("Trajectory is shorter than 1 ns; treat conclusions as smoke-test evidence only.")
        next_steps.append("Use this run only as a pipeline smoke test; repeat with >= 1 ns for engineering screening.")
    elif simulation_time_ns < 10.0:
        next_steps.append("Use this run for candidate triage only; confirm selected variants with >= 10 ns and replicates.")
    else:
        next_steps.append("Review topology, protonation, cofactors, ligands, and replicate consistency before report-grade conclusions.")

    if protocol_review:
        for warning in protocol_review.get("review_warnings") or []:
            if isinstance(warning, str):
                warnings.append(warning)
        controls = protocol_review.get("scientific_controls") if isinstance(protocol_review.get("scientific_controls"), dict) else {}
        replicate_policy = controls.get("replicate_policy") if isinstance(controls.get("replicate_policy"), dict) else {}
        if replicate_policy.get("minimum_for_ranking"):
            next_steps.append(f"Use at least {replicate_policy['minimum_for_ranking']} replicates before ranking candidates.")

    if rmsd_drift is not None:
        abs_drift = abs(rmsd_drift)
        if abs_drift < 0.15:
            findings.append("RMSD drift is low after equilibration, consistent with a stable short trajectory.")
            verdict = "stable_short_run"
            quality_gates.append({"metric": "rmsd_drift_nm", "status": "pass", "value": round(abs_drift, 4), "limit": 0.15})
        elif abs_drift < 0.35:
            findings.append("RMSD drift is moderate; extend the trajectory before making engineering decisions.")
            verdict = "borderline"
            quality_gates.append({"metric": "rmsd_drift_nm", "status": "review", "value": round(abs_drift, 4), "limit": 0.35})
            next_steps.append("Inspect RMSD time series for late drift before comparing candidates.")
        else:
            findings.append("RMSD drift is high, suggesting conformational change or insufficient equilibration.")
            verdict = "unstable_or_unconverged"
            quality_gates.append({"metric": "rmsd_drift_nm", "status": "fail", "value": round(abs_drift, 4), "limit": 0.35})
            next_steps.append("Do not rank this candidate from the current run; extend equilibration or inspect structure preparation.")
    else:
        warnings.append("RMSD drift could not be calculated from the generated XVG series.")
        quality_gates.append({"metric": "rmsd_drift_nm", "status": "missing", "value": None, "limit": 0.15})

    if mean_rmsf is not None:
        if mean_rmsf < 0.2:
            findings.append("Mean RMSF is low, indicating limited average backbone flexibility.")
            quality_gates.append({"metric": "mean_rmsf_nm", "status": "pass", "value": round(mean_rmsf, 4), "limit": 0.2})
        elif mean_rmsf < 0.45:
            findings.append("Mean RMSF is moderate, with localized flexible regions requiring review.")
            quality_gates.append({"metric": "mean_rmsf_nm", "status": "review", "value": round(mean_rmsf, 4), "limit": 0.45})
        else:
            findings.append("Mean RMSF is high, indicating broad flexibility in this run.")
            quality_gates.append({"metric": "mean_rmsf_nm", "status": "fail", "value": round(mean_rmsf, 4), "limit": 0.45})
            next_steps.append("Map high-RMSF residues onto domains, termini, loops, and catalytic positions before accepting the structure.")
    else:
        warnings.append("RMSF could not be calculated from the generated XVG series.")
        quality_gates.append({"metric": "mean_rmsf_nm", "status": "missing", "value": None, "limit": 0.2})

    if rg_initial is not None and rg_final is not None:
        rg_change = rg_final - rg_initial
        if abs(rg_change) < 0.1:
            findings.append("Radius of gyration changed minimally, suggesting no large compaction or expansion.")
        elif rg_change > 0:
            findings.append("Radius of gyration increased, suggesting expansion during the trajectory.")
        else:
            findings.append("Radius of gyration decreased, suggesting compaction during the trajectory.")

    if sasa_initial is not None and sasa_final is not None:
        sasa_change = sasa_final - sasa_initial
        if abs(sasa_change) > max(5.0, abs(sasa_initial) * 0.05):
            direction = "increased" if sasa_change > 0 else "decreased"
            findings.append(f"SASA {direction} noticeably; inspect exposed or buried regions.")

    if flexible_regions:
        findings.append(f"Detected {len(flexible_regions)} high-mobility residue positions from RMSF.")
        next_steps.append("Review high-mobility residues against catalytic sites, binding interfaces, and engineered mutations.")

    if structure_preparation:
        for warning in structure_preparation.get("warnings") or []:
            if isinstance(warning, str):
                warnings.append(warning)
        for flag in structure_preparation.get("risk_flags") or []:
            if isinstance(flag, str):
                missing_evidence.append({"metric": flag, "reason": "structure_preparation_requires_review"})
                quality_gates.append({"metric": flag, "status": "review", "value": None, "limit": None})
        if structure_preparation.get("risk_flags"):
            next_steps.append("Resolve structure-preparation risk flags before using this run for production MD or candidate ranking.")

    if replicate_consistency:
        for warning in replicate_consistency.get("warnings") or []:
            if isinstance(warning, str):
                warnings.append(warning)
        if not replicate_consistency.get("ranking_allowed"):
            missing_evidence.append({"metric": "replicate_consistency", "reason": "replicates_insufficient_or_inconsistent"})
            quality_gates.append(
                {
                    "metric": "replicate_consistency",
                    "status": "review",
                    "value": replicate_consistency.get("group_count"),
                    "limit": replicate_consistency.get("minimum_replicates"),
                }
            )
        for step in replicate_consistency.get("recommended_next_steps") or []:
            if isinstance(step, str):
                next_steps.append(step)

    if topology_review:
        for warning in topology_review.get("warnings") or []:
            if isinstance(warning, str):
                warnings.append(warning)
        for flag in topology_review.get("risk_flags") or []:
            if isinstance(flag, str):
                missing_evidence.append({"metric": flag, "reason": "topology_warning_requires_review"})
                quality_gates.append({"metric": flag, "status": "review", "value": topology_review.get("warning_count"), "limit": 0})
        if topology_review.get("warning_count"):
            next_steps.append("Inspect GROMACS topology/preprocessing warnings before using this run for candidate ranking.")

    for metric, present in (analysis_files or {}).items():
        if not present:
            missing_evidence.append({"metric": metric, "reason": "analysis_file_missing_or_empty"})
            quality_gates.append({"metric": metric, "status": "missing", "value": None, "limit": None})

    for metric, value in (energetics or {}).items():
        if value is None:
            missing_evidence.append({"metric": metric, "reason": "energy_term_not_extracted"})

    for metric, value in (interactions or {}).items():
        if value is None:
            missing_evidence.append({"metric": metric, "reason": "hbond_analysis_not_extracted"})

    if missing_evidence:
        warnings.append("Some energy, hydrogen-bond, or analysis evidence is missing; interpretation should remain conservative.")
        next_steps.append("Extract energy terms and hydrogen-bond time series before making report-grade mechanistic claims.")

    confidence = "low" if simulation_time_ns < 1.0 else "medium"
    if warnings and confidence == "medium":
        confidence = "low"
    evidence_level = "smoke" if simulation_time_ns < 1.0 else ("screening" if simulation_time_ns < 10.0 else "review_candidate")
    conclusion = {
        "stable_short_run": "Current trajectory is consistent with short-run stability, but evidence remains limited by trajectory length.",
        "borderline": "Current trajectory is borderline; use only for triage until longer validation is available.",
        "unstable_or_unconverged": "Current trajectory is unstable or unconverged; do not use it as positive engineering evidence.",
        "needs_review": "Current trajectory needs manual review because key metrics are missing or ambiguous.",
    }[verdict]

    return {
        "verdict": verdict,
        "confidence": confidence,
        "evidence_level": evidence_level,
        "conclusion": conclusion,
        "findings": findings,
        "warnings": warnings,
        "recommended_next_steps": list(dict.fromkeys(next_steps)),
        "quality_gates": quality_gates,
        "missing_evidence": missing_evidence,
        "thresholds": {
            "stable_rmsd_drift_nm": 0.15,
            "borderline_rmsd_drift_nm": 0.35,
            "low_mean_rmsf_nm": 0.2,
            "moderate_mean_rmsf_nm": 0.45,
        },
        "metric_snapshot": {
            "rmsd_final_nm": round(rmsd_final, 4) if rmsd_final is not None else None,
            "rmsd_drift_nm": round(rmsd_drift, 4) if rmsd_drift is not None else None,
            "mean_rmsf_nm": round(mean_rmsf, 4) if mean_rmsf is not None else None,
            "max_rmsf_nm": round(max_rmsf, 4) if max_rmsf is not None else None,
        },
        "protocol_review": protocol_review,
        "structure_preparation": structure_preparation,
        "replicate_consistency": replicate_consistency,
        "topology_review": topology_review,
    }


def _sync_upload_file(data: bytes, filename: str, content_type: str, folder: str) -> dict:
    """Use storage.upload_file from this synchronous tool context."""
    import asyncio
    from app.services import storage

    return asyncio.run(
        storage.upload_file(
            data,
            filename=filename,
            content_type=content_type,
            folder=folder,
        )
    )


def _sync_download_file(object_name: str) -> bytes:
    """Use storage.download_file from this synchronous tool context."""
    import asyncio
    from app.services import storage

    return asyncio.run(storage.download_file(object_name))


def _content_type(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "pdb": "chemical/x-pdb",
        "gro": "text/plain",
        "xtc": "application/octet-stream",
        "tpr": "application/octet-stream",
        "edr": "application/octet-stream",
        "xvg": "text/plain",
        "csv": "text/csv",
        "log": "text/plain",
        "mdp": "text/plain",
    }.get(ext, "application/octet-stream")


def _load_pdb_text(pdb_data: str | None, pdb_object_name: str | None, pdb_path: str | None) -> str:
    if pdb_data and pdb_data.strip():
        return pdb_data
    if pdb_path:
        path = Path(pdb_path)
        if not path.exists():
            raise RuntimeError(f"PDB path not found: {pdb_path}")
        return path.read_text(encoding="utf-8", errors="replace")
    if pdb_object_name:
        return _sync_download_file(pdb_object_name).decode("utf-8", errors="replace")
    raise RuntimeError(
        "REAL_MD_REQUIRES_PDB: provide pdb_data, pdb_path, or pdb_object_name. "
        "A sequence alone is not enough for real molecular dynamics."
    )


def _validate_pdb(text: str) -> None:
    if not re.search(r"^(ATOM|HETATM)\s+", text, flags=re.M):
        raise RuntimeError("INVALID_PDB: input does not contain ATOM/HETATM records.")


def _detect_atom_count(text: str) -> int | None:
    count = 0
    for line in text.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            count += 1
    return count or None


def _residue_name(line: str) -> str:
    return line[17:20].strip().upper() if len(line) >= 20 else ""


def _chain_id(line: str) -> str:
    return line[21].strip() if len(line) >= 22 else ""


def _residue_id(line: str) -> str:
    chain = _chain_id(line) or "_"
    seq = line[22:26].strip() if len(line) >= 26 else ""
    insertion = line[26].strip() if len(line) >= 27 else ""
    return f"{chain}:{seq}{insertion}".rstrip()


def _atom_name(line: str) -> str:
    return line[12:16].strip().upper() if len(line) >= 16 else ""


def _aa_to_three(value: str) -> str | None:
    text = str(value or "").strip().upper()
    if len(text) == 1:
        return _AA_ONE_TO_THREE.get(text)
    return text if text in _AA_THREE_TO_ONE else None


def _parse_mutation_variant(value: Any) -> dict[str, Any]:
    """Parse conservative point-mutation labels such as M204H or A:M204H."""
    if isinstance(value, dict):
        raw = value.get("variant") or value.get("mutation") or value.get("name")
        explicit_chain = value.get("chain")
    else:
        raw = value
        explicit_chain = None
    text = str(raw or "").strip()
    match = re.match(
        r"^(?:(?P<chain>[A-Za-z0-9_]):)?(?P<source>[A-Za-z]{1,3})(?P<seq>-?\d+)(?P<insertion>[A-Za-z]?)(?P<target>[A-Za-z]{1,3})$",
        text,
    )
    if not match:
        raise ValueError(f"Unsupported mutation format: {text}. Use examples like M204H or A:M204H.")
    source_three = _aa_to_three(match.group("source"))
    target_three = _aa_to_three(match.group("target"))
    if not source_three or not target_three:
        raise ValueError(f"Unsupported amino-acid code in mutation: {text}")
    chain = str(explicit_chain or match.group("chain") or "").strip()
    return {
        "variant": text,
        "chain": "" if chain in {"", "_"} else chain,
        "residue_number": match.group("seq"),
        "insertion_code": match.group("insertion") or "",
        "source_residue": source_three,
        "target_residue": target_three,
        "source_one_letter": _AA_THREE_TO_ONE[source_three],
        "target_one_letter": _AA_THREE_TO_ONE[target_three],
    }


def _line_residue_number(line: str) -> str:
    return line[22:26].strip() if len(line) >= 26 else ""


def _line_insertion_code(line: str) -> str:
    return line[26].strip() if len(line) >= 27 else ""


def _matches_mutation_residue(line: str, mutation: dict[str, Any]) -> bool:
    if not line.startswith(("ATOM", "HETATM", "TER")):
        return False
    if _line_residue_number(line) != mutation["residue_number"]:
        return False
    if _line_insertion_code(line) != mutation.get("insertion_code", ""):
        return False
    chain = mutation.get("chain") or ""
    return not chain or _chain_id(line) == chain


def _mutant_keep_atoms(target_residue: str) -> set[str]:
    return set(_BACKBONE_ATOMS) | set(_MINIMAL_SIDECHAIN_ATOMS.get(target_residue, {"CB"}))


def _format_residue_name(line: str, residue_name: str) -> str:
    if len(line) < 20:
        return line
    return f"{line[:17]}{residue_name:>3}{line[20:]}"


def _prepare_point_mutant_pdb(pdb_text: str, variant: Any) -> dict[str, Any]:
    """Create a conservative coordinate candidate for one point mutant.

    This intentionally does not claim topology success. Non-backbone side-chain
    atoms are removed unless they are safe minimal atoms for the target residue;
    real GROMACS pdb2gmx validation must pass before production MD submission.
    """
    mutation = _parse_mutation_variant(variant)
    lines = pdb_text.splitlines()
    residue_keys: set[str] = set()
    observed_names: set[str] = set()
    for line in lines:
        if not line.startswith(("ATOM", "HETATM")) or not _matches_mutation_residue(line, mutation):
            continue
        residue_keys.add(_residue_id(line))
        observed_names.add(_residue_name(line))

    if not residue_keys:
        return {
            "variant": mutation["variant"],
            "status": "blocked",
            "blocked_reason": "mutation_residue_not_found",
            "mutation": mutation,
            "observed_residues": sorted(observed_names),
            "pdb_data": None,
            "metrics": {"matched_atom_count": 0, "removed_sidechain_atom_count": 0},
            "warnings": ["No ATOM/HETATM residue matched the requested mutation."],
        }
    if not mutation.get("chain") and len(residue_keys) > 1:
        return {
            "variant": mutation["variant"],
            "status": "blocked",
            "blocked_reason": "ambiguous_residue_without_chain",
            "mutation": mutation,
            "matched_residue_ids": sorted(residue_keys),
            "pdb_data": None,
            "metrics": {"matched_atom_count": 0, "removed_sidechain_atom_count": 0},
            "warnings": ["Multiple chains/residues match this mutation; specify chain, e.g. A:M204H."],
        }
    if mutation["source_residue"] not in observed_names:
        return {
            "variant": mutation["variant"],
            "status": "blocked",
            "blocked_reason": "source_residue_mismatch",
            "mutation": mutation,
            "matched_residue_ids": sorted(residue_keys),
            "observed_residues": sorted(observed_names),
            "pdb_data": None,
            "metrics": {"matched_atom_count": 0, "removed_sidechain_atom_count": 0},
            "warnings": [f"Requested source {mutation['source_residue']} does not match observed residue(s): {', '.join(sorted(observed_names))}."],
        }

    keep_atoms = _mutant_keep_atoms(mutation["target_residue"])
    output_lines: list[str] = []
    matched_atom_count = 0
    kept_atom_count = 0
    removed_sidechain_atom_count = 0
    target_atoms: set[str] = set()
    for line in lines:
        if not _matches_mutation_residue(line, mutation):
            output_lines.append(line)
            continue
        if line.startswith(("ATOM", "HETATM")):
            matched_atom_count += 1
            atom = _atom_name(line)
            if atom not in keep_atoms:
                removed_sidechain_atom_count += 1
                continue
            kept_atom_count += 1
            target_atoms.add(atom)
        output_lines.append(_format_residue_name(line, mutation["target_residue"]))

    missing_core_atoms = sorted(_BACKBONE_ATOMS.intersection({"N", "CA", "C", "O"}) - target_atoms)
    missing_minimal_sidechain_atoms = sorted(set(_MINIMAL_SIDECHAIN_ATOMS.get(mutation["target_residue"], {"CB"})) - target_atoms)
    warnings = [
        "Generated mutant PDB is coordinate-level only; run topology validation before real MD.",
        "Side-chain atoms incompatible with the target residue were removed instead of modelled.",
    ]
    if missing_core_atoms:
        warnings.append(f"Missing backbone atom(s) after mutation: {', '.join(missing_core_atoms)}.")
    if missing_minimal_sidechain_atoms:
        warnings.append(f"Missing target side-chain atom(s): {', '.join(missing_minimal_sidechain_atoms)}.")
    readiness = "requires_topology_validation"
    if missing_core_atoms:
        readiness = "blocked_missing_backbone_atoms"
    elif missing_minimal_sidechain_atoms:
        readiness = "requires_sidechain_rebuild_and_topology_validation"

    return {
        "variant": mutation["variant"],
        "status": "prepared" if not missing_core_atoms else "blocked",
        "blocked_reason": "missing_backbone_atoms" if missing_core_atoms else None,
        "mutation": mutation,
        "matched_residue_ids": sorted(residue_keys),
        "topology_readiness": readiness,
        "pdb_data": "\n".join(output_lines) + ("\n" if pdb_text.endswith("\n") else ""),
        "metrics": {
            "matched_atom_count": matched_atom_count,
            "kept_atom_count": kept_atom_count,
            "removed_sidechain_atom_count": removed_sidechain_atom_count,
            "missing_core_atoms": missing_core_atoms,
            "missing_minimal_sidechain_atoms": missing_minimal_sidechain_atoms,
        },
        "warnings": warnings,
    }


def _prepare_point_mutant_pdbs(pdb_text: str, variants: list[Any]) -> dict[str, Any]:
    _validate_pdb(pdb_text)
    prepared = [_prepare_point_mutant_pdb(pdb_text, variant) for variant in variants]
    return {
        "version": 1,
        "status": "prepared" if prepared and all(item.get("status") == "prepared" for item in prepared) else "blocked_or_partial",
        "count": len(prepared),
        "prepared_count": sum(1 for item in prepared if item.get("status") == "prepared"),
        "blocked_count": sum(1 for item in prepared if item.get("status") == "blocked"),
        "mutants": prepared,
        "topology_policy": {
            "coordinate_generation_only": True,
            "requires_gromacs_pdb2gmx_validation": True,
            "safe_for_ranking_without_validation": False,
        },
    }


def _validate_pdb_topology(
    pdb_text: str,
    *,
    force_field: str = "amber99sb-ildn",
    water_model: str = "tip3p",
    timeout: int = 120,
) -> dict[str, Any]:
    """Run a lightweight real GROMACS pdb2gmx topology precheck."""
    try:
        _validate_pdb(pdb_text)
    except Exception as exc:
        return {
            "version": 1,
            "status": "blocked",
            "error_code": "INVALID_PDB",
            "error": str(exc),
            "topology_validated": False,
            "safe_for_ranking": False,
        }
    gmx = _find_gmx()
    if not gmx:
        return {
            "version": 1,
            "status": "unavailable",
            "error_code": "GROMACS_NOT_INSTALLED",
            "error": "GROMACS executable not found. Install `gmx` or `gmx_mpi`, or set GROMACS_BIN.",
            "topology_validated": False,
            "safe_for_ranking": False,
            "required_runtime": ["GROMACS", "GROMACS force-field library"],
        }
    resolved_force_field, installed_force_fields = _resolve_force_field(force_field)
    if not resolved_force_field:
        return {
            "version": 1,
            "status": "blocked",
            "error_code": "FORCE_FIELD_UNAVAILABLE",
            "error": f"Unsupported or unavailable force_field: {force_field}",
            "requested_force_field": force_field,
            "supported_force_fields": installed_force_fields,
            "topology_validated": False,
            "safe_for_ranking": False,
        }
    if water_model not in _WATER_MODELS:
        return {
            "version": 1,
            "status": "blocked",
            "error_code": "WATER_MODEL_UNSUPPORTED",
            "error": f"Unsupported water_model: {water_model}",
            "supported_water_models": _WATER_MODELS,
            "topology_validated": False,
            "safe_for_ranking": False,
        }

    job_id = uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix=f"gromacs_topology_{job_id}_") as tmp:
        workdir = Path(tmp)
        _write(workdir / "input.pdb", pdb_text)
        cmd = [
            gmx,
            "pdb2gmx",
            "-f",
            "input.pdb",
            "-o",
            "processed.gro",
            "-p",
            "topol.top",
            "-ignh",
            "-ff",
            resolved_force_field,
            "-water",
            water_model,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=max(10, min(int(timeout or 120), 1800)),
                check=False,
            )
            output = proc.stdout or ""
        except subprocess.TimeoutExpired as exc:
            output = str(exc.stdout or "")[-4000:]
            (workdir / "01_pdb2gmx.log.txt").write_text(output, encoding="utf-8", errors="replace")
            return {
                "version": 1,
                "status": "blocked",
                "error_code": "PDB2GMX_TIMEOUT",
                "error": "GROMACS pdb2gmx timed out during topology precheck.",
                "topology_validated": False,
                "safe_for_ranking": False,
                "command": " ".join(cmd),
                "log_tail": output[-1000:],
            }
        (workdir / "01_pdb2gmx.log.txt").write_text(output, encoding="utf-8", errors="replace")
        topology_review = _scan_topology_warnings(workdir)
        outputs = {
            "processed_gro": (workdir / "processed.gro").exists(),
            "topol_top": (workdir / "topol.top").exists(),
        }
        topology_validated = proc.returncode == 0 and all(outputs.values())
        status = "validated" if topology_validated else "blocked"
        if topology_validated and topology_review.get("warning_count"):
            status = "validated_with_warnings"
        result: dict[str, Any] = {
            "version": 1,
            "status": status,
            "topology_validated": topology_validated,
            "safe_for_ranking": bool(topology_validated and not topology_review.get("risk_flags")),
            "engine": "GROMACS",
            "gromacs_executable": gmx,
            "force_field": resolved_force_field,
            "water_model": water_model,
            "return_code": proc.returncode,
            "command": " ".join(cmd),
            "outputs": outputs,
            "topology_review": topology_review,
            "log_tail": output[-1000:],
        }
        if proc.returncode != 0:
            result["error_code"] = "PDB2GMX_FAILED"
            result["error"] = "GROMACS pdb2gmx failed during topology precheck. Inspect log_tail/topology_review."
        return result


def _increment(counter: dict[str, int], key: str) -> None:
    if key:
        counter[key] = counter.get(key, 0) + 1


def _scan_structure_preparation(text: str) -> dict[str, Any]:
    """Detect structure-preparation risks before running GROMACS."""
    counts = {
        "atoms": 0,
        "hetatm": 0,
        "water_atoms": 0,
        "non_water_hetatm_atoms": 0,
        "alternate_location_atoms": 0,
        "missing_residue_records": 0,
        "ssbond_records": 0,
    }
    residue_counts: dict[str, int] = {}
    hetero_residue_counts: dict[str, int] = {}
    ion_counts: dict[str, int] = {}
    cofactor_counts: dict[str, int] = {}
    histidine_positions: set[str] = set()
    cysteine_positions: set[str] = set()
    alternate_locations: set[str] = set()
    warnings: list[str] = []
    risk_flags: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        record = line[:6].strip().upper()
        if record == "REMARK" and line[7:10].strip() == "465":
            counts["missing_residue_records"] += 1
            continue
        if record == "SSBOND":
            counts["ssbond_records"] += 1
            continue
        if record not in {"ATOM", "HETATM"}:
            continue

        counts["atoms"] += 1
        residue = _residue_name(line)
        residue_id = _residue_id(line)
        _increment(residue_counts, residue)

        alt_loc = line[16].strip() if len(line) >= 17 else ""
        if alt_loc:
            counts["alternate_location_atoms"] += 1
            alternate_locations.add(f"{residue}:{residue_id}:{alt_loc}")

        if residue in _HISTIDINE_NAMES:
            histidine_positions.add(residue_id)
        if residue == "CYS":
            cysteine_positions.add(residue_id)

        if record != "HETATM":
            continue

        counts["hetatm"] += 1
        if residue in _WATER_RESIDUES:
            counts["water_atoms"] += 1
            continue

        counts["non_water_hetatm_atoms"] += 1
        _increment(hetero_residue_counts, residue)
        if residue in _COMMON_IONS:
            _increment(ion_counts, residue)
        if residue in _COMMON_COFACTORS:
            _increment(cofactor_counts, residue)

    if counts["non_water_hetatm_atoms"] > 0:
        risk_flags.append("non_water_hetatm_present")
        warnings.append("PDB contains non-water HETATM records; ligand/cofactor topology may require manual parameterization.")
    if cofactor_counts:
        risk_flags.append("cofactor_like_residue_present")
        warnings.append("Common cofactor-like residues were detected; verify retained cofactors and force-field parameters before production MD.")
    if ion_counts:
        risk_flags.append("metal_or_ion_present")
        warnings.append("Metal/ion HETATM records were detected; verify coordination, charge state, and topology treatment.")
    if counts["alternate_location_atoms"] > 0:
        risk_flags.append("alternate_locations_present")
        warnings.append("Alternate atom locations were detected; choose a single conformer before report-grade MD.")
    if counts["missing_residue_records"] > 0:
        risk_flags.append("missing_residue_records_present")
        warnings.append("REMARK 465 missing-residue records were detected; model or justify missing regions before candidate ranking.")
    if histidine_positions:
        risk_flags.append("histidine_protonation_review")
        warnings.append("Histidine residues were detected; review HIS/HID/HIE/HIP protonation states for pH and active-site chemistry.")
    if cysteine_positions and counts["ssbond_records"] == 0:
        risk_flags.append("cysteine_disulfide_review")
        warnings.append("Cysteine residues were detected without SSBOND records; review disulfide assignments before production MD.")
    if counts["ssbond_records"] > 0:
        risk_flags.append("ssbond_records_present")
        warnings.append("SSBOND records were detected; verify disulfide topology generated by pdb2gmx.")

    return {
        "version": 1,
        "counts": counts,
        "risk_flags": risk_flags,
        "warnings": warnings,
        "hetero_residue_counts": hetero_residue_counts,
        "ion_counts": ion_counts,
        "cofactor_counts": cofactor_counts,
        "histidine_count": len(histidine_positions),
        "cysteine_count": len(cysteine_positions),
        "alternate_locations": sorted(alternate_locations)[:50],
    }


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def _mean(numbers: list[float]) -> float | None:
    return sum(numbers) / len(numbers) if numbers else None


def _sample_sd(numbers: list[float]) -> float | None:
    if len(numbers) < 2:
        return None
    mean = sum(numbers) / len(numbers)
    return (sum((value - mean) ** 2 for value in numbers) / (len(numbers) - 1)) ** 0.5


def _summarize_replicate_metric(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    values = [_coerce_float(row.get(metric)) for row in rows]
    clean_values = [value for value in values if value is not None]
    mean = _mean(clean_values)
    sd = _sample_sd(clean_values)
    cv = abs(sd / mean) if mean not in {None, 0} and sd is not None else None
    return {
        "count": len(clean_values),
        "mean": round(mean, 4) if mean is not None else None,
        "sd": round(sd, 4) if sd is not None else None,
        "cv": round(cv, 4) if cv is not None else None,
        "min": round(min(clean_values), 4) if clean_values else None,
        "max": round(max(clean_values), 4) if clean_values else None,
        "values": [round(value, 4) for value in clean_values],
    }


def _sign(value: float | None, tolerance: float = 0.02) -> int:
    if value is None or abs(value) <= tolerance:
        return 0
    return 1 if value > 0 else -1


def _build_replicate_consistency(
    *,
    wild_type_replicates: list[dict[str, Any]],
    mutant_replicates: list[dict[str, Any]] | None = None,
    minimum_replicates: int = 3,
) -> dict[str, Any]:
    """Assess whether WT/mutant MD metrics are repeatable enough for ranking."""
    minimum = max(1, int(minimum_replicates or 1))
    all_rows = [{"variant": "WT", **row} for row in wild_type_replicates]
    all_rows.extend(mutant_replicates or [])
    groups_by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        variant = str(row.get("variant") or row.get("mutation") or "WT")
        groups_by_variant.setdefault(variant, []).append(row)

    metric_names = ["rmsd_drift_nm", "mean_rmsf_nm", "rg_change_nm", "sasa_change_nm2"]
    warnings: list[str] = []
    next_steps: list[str] = []
    quality_gates: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    status = "consistent"

    if not groups_by_variant:
        return {
            "version": 1,
            "status": "no_replicates",
            "ranking_allowed": False,
            "minimum_replicates": minimum,
            "group_count": 0,
            "groups": [],
            "warnings": ["No replicate metrics were provided."],
            "recommended_next_steps": ["Run WT and mutant replicates before ranking candidates."],
            "quality_gates": [{"metric": "replicate_count", "status": "missing", "value": 0, "limit": minimum}],
        }

    for variant, rows in sorted(groups_by_variant.items()):
        metrics = {metric: _summarize_replicate_metric(rows, metric) for metric in metric_names}
        replicate_count = max((summary["count"] for summary in metrics.values()), default=len(rows))
        stable_calls = [row.get("is_stable") for row in rows if isinstance(row.get("is_stable"), bool)]
        stable_agreement = len(set(stable_calls)) <= 1 if stable_calls else None
        gate_status = "pass"

        if replicate_count < minimum:
            gate_status = "missing"
            status = "insufficient_replicates"
            warnings.append(f"{variant} has {replicate_count} replicate(s); ranking requires at least {minimum}.")
        else:
            for metric, summary in metrics.items():
                cv = summary.get("cv")
                sd = summary.get("sd")
                if cv is not None and cv > 0.25 and (sd is None or sd > 0.05):
                    gate_status = "review"
                    if status == "consistent":
                        status = "review"
                    warnings.append(f"{variant} {metric} varies across replicates; inspect trajectories before ranking.")
            if stable_agreement is False:
                gate_status = "review"
                if status == "consistent":
                    status = "review"
                warnings.append(f"{variant} stability classification is not consistent across replicates.")

        quality_gates.append({"metric": f"{variant}:replicate_count", "status": gate_status, "value": replicate_count, "limit": minimum})
        groups.append(
            {
                "variant": variant,
                "replicate_count": replicate_count,
                "status": gate_status,
                "metrics": metrics,
                "stable_agreement": stable_agreement,
            }
        )

    mutant_direction_warnings: list[str] = []
    for variant, rows in sorted(groups_by_variant.items()):
        if variant == "WT" or len(rows) < minimum:
            continue
        for metric in ("stability_delta", "rmsf_change_mean"):
            signs = {_sign(_coerce_float(row.get(metric))) for row in rows}
            signs.discard(0)
            if len(signs) > 1:
                mutant_direction_warnings.append(f"{variant} {metric} changes direction across replicates.")

    if mutant_direction_warnings:
        status = "inconsistent"
        warnings.extend(mutant_direction_warnings)
        quality_gates.append({"metric": "mutant_delta_direction", "status": "fail", "value": None, "limit": "same_sign"})

    ranking_allowed = status == "consistent"
    if not ranking_allowed:
        next_steps.append("Run enough WT and mutant replicates, then rank candidates only if metric direction and variance agree.")
    else:
        next_steps.append("Replicate consistency gates passed; candidate ranking can proceed with remaining topology and evidence checks.")

    return {
        "version": 1,
        "status": status,
        "ranking_allowed": ranking_allowed,
        "minimum_replicates": minimum,
        "group_count": len(groups),
        "groups": groups,
        "warnings": list(dict.fromkeys(warnings)),
        "recommended_next_steps": next_steps,
        "quality_gates": quality_gates,
    }


def _normalize_variant_name(variant: Any) -> str:
    if isinstance(variant, dict):
        value = variant.get("variant") or variant.get("mutation") or variant.get("name")
    else:
        value = variant
    text = str(value or "").strip()
    return text or "WT"


def _build_replicate_execution_plan(
    *,
    protocol_id: str | None,
    parameters: dict[str, Any],
    variants: list[Any] | None = None,
    replicate_count: int = 3,
    seed_base: int = 1000,
) -> dict[str, Any]:
    """Build a deterministic multi-replicate MD execution plan without running MD."""
    count = max(1, min(int(replicate_count or 1), 20))
    variant_names = ["WT"]
    for item in variants or []:
        name = _normalize_variant_name(item)
        if name != "WT" and name not in variant_names:
            variant_names.append(name)

    tasks: list[dict[str, Any]] = []
    for variant_index, variant in enumerate(variant_names):
        for replicate_index in range(1, count + 1):
            seed = int(seed_base) + variant_index * 1000 + replicate_index
            task_id = f"{variant.replace(' ', '_')}:rep{replicate_index}"
            tasks.append(
                {
                    "task_id": task_id,
                    "variant": variant,
                    "replicate_index": replicate_index,
                    "seed": seed,
                    "protocol_id": protocol_id,
                    "simulation_time_ns": parameters.get("simulation_time_ns"),
                    "equilibration_ps": parameters.get("equilibration_ps"),
                    "force_field": parameters.get("force_field"),
                    "water_model": parameters.get("water_model"),
                    "ensemble": parameters.get("ensemble"),
                    "requires_mutant_structure": variant != "WT",
                    "status": "planned",
                }
            )

    mutant_tasks = [task for task in tasks if task["variant"] != "WT"]
    warnings: list[str] = []
    if mutant_tasks:
        warnings.append("Mutant tasks require a prepared mutant PDB/topology before real execution; this planner does not mutate structures.")
    if count < 3:
        warnings.append("Replicate count is below ranking-grade; use at least 3 replicates before ranking candidates.")

    return {
        "version": 1,
        "status": "planned",
        "protocol_id": protocol_id,
        "replicate_count": count,
        "variant_count": len(variant_names),
        "total_tasks": len(tasks),
        "variants": variant_names,
        "tasks": tasks,
        "execution_order": "variant_then_replicate",
        "input_requirements": [
            "WT PDB structure prepared for GROMACS.",
            "Each mutant variant must have a prepared mutant PDB before execution.",
            "Use matched protocol parameters and analysis windows across WT/mutants.",
        ],
        "warnings": warnings,
    }


def _build_md_batch_replicate_summary(
    *,
    wild_type_replicates: list[dict[str, Any]],
    mutant_replicates: list[dict[str, Any]] | None = None,
    minimum_replicates: int = 3,
) -> dict[str, Any]:
    """Summarize WT/mutant replicate metrics for batch MD candidate review."""
    consistency = _build_replicate_consistency(
        wild_type_replicates=wild_type_replicates,
        mutant_replicates=mutant_replicates,
        minimum_replicates=minimum_replicates,
    )
    mutant_rows = mutant_replicates or []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in mutant_rows:
        variant = _normalize_variant_name(row)
        if variant != "WT":
            grouped.setdefault(variant, []).append(row)

    candidates: list[dict[str, Any]] = []
    for variant, rows in sorted(grouped.items()):
        stability = _summarize_replicate_metric(rows, "stability_delta")
        rmsf_change = _summarize_replicate_metric(rows, "rmsf_change_mean")
        rmsd_drift = _summarize_replicate_metric(rows, "rmsd_drift_nm")
        stability_mean = stability.get("mean")
        rmsf_mean = rmsf_change.get("mean")
        score = None
        candidate_gates: list[dict[str, Any]] = []
        blocked_reasons: list[str] = []
        if stability_mean is not None and rmsf_mean is not None:
            score = round((-float(stability_mean)) + (-float(rmsf_mean) * 0.5), 4)
            candidate_gates.append({"metric": "ranking_metrics", "status": "pass", "value": "stability_delta+rmsf_change_mean"})
        else:
            missing = [
                name
                for name, summary in (("stability_delta", stability), ("rmsf_change_mean", rmsf_change))
                if summary.get("mean") is None
            ]
            candidate_gates.append({"metric": "ranking_metrics", "status": "missing", "missing": missing})
            blocked_reasons.append("missing_ranking_metrics")

        topology_records = [
            row.get("topology_validation")
            for row in rows
            if isinstance(row.get("topology_validation"), dict)
        ]
        explicit_topology_flags = topology_records or any(
            key in row
            for row in rows
            for key in ("topology_validated", "safe_for_ranking", "topology_readiness")
        )
        if topology_records:
            validated = all(record.get("topology_validated") is True for record in topology_records)
            safe = all(record.get("safe_for_ranking") is True for record in topology_records)
            topology_status = "pass" if validated and safe else "blocked"
            candidate_gates.append(
                {
                    "metric": "mutant_topology_validation",
                    "status": topology_status,
                    "validated_count": sum(1 for record in topology_records if record.get("topology_validated") is True),
                    "safe_count": sum(1 for record in topology_records if record.get("safe_for_ranking") is True),
                    "total_count": len(topology_records),
                }
            )
            if topology_status != "pass":
                blocked_reasons.append("mutant_topology_not_safe_for_ranking")
        elif explicit_topology_flags:
            safe_flags = [row.get("safe_for_ranking") for row in rows if "safe_for_ranking" in row]
            validated_flags = [row.get("topology_validated") for row in rows if "topology_validated" in row]
            readiness_values = [row.get("topology_readiness") for row in rows if row.get("topology_readiness")]
            unsafe = any(value is False for value in safe_flags) or any(value is False for value in validated_flags)
            requires_review = any(value in {"requires_topology_validation", "requires_sidechain_rebuild_and_topology_validation"} for value in readiness_values)
            topology_status = "blocked" if unsafe or requires_review else "pass"
            candidate_gates.append(
                {
                    "metric": "mutant_topology_validation",
                    "status": topology_status,
                    "safe_for_ranking": False if unsafe or requires_review else True,
                    "readiness": readiness_values[:3],
                }
            )
            if topology_status != "pass":
                blocked_reasons.append("mutant_topology_not_safe_for_ranking")

        ranking_ready = bool(consistency.get("ranking_allowed") and score is not None and not blocked_reasons)
        candidates.append(
            {
                "variant": variant,
                "replicate_count": max(stability.get("count") or 0, rmsf_change.get("count") or 0, rmsd_drift.get("count") or 0),
                "stability_delta": stability,
                "rmsf_change_mean": rmsf_change,
                "rmsd_drift_nm": rmsd_drift,
                "ranking_score": score,
                "ranking_ready": ranking_ready,
                "quality_gates": candidate_gates,
                "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
            }
        )

    lipase_evidence_context = build_lipase_evidence_context(
        mutations=[item["variant"] for item in candidates],
        q="MD ranking stability",
        limit=50,
    ) if candidates else None
    exact_by_mutation: dict[str, list[dict[str, Any]]] = {}
    position_counts: dict[int, int] = {}
    if lipase_evidence_context:
        for match in lipase_evidence_context.get("exact_mutation_matches") or []:
            code = str(match.get("mutation_code") or "").upper()
            exact_by_mutation.setdefault(code, []).append(match)
        for match in lipase_evidence_context.get("position_matches") or []:
            try:
                position = int(match.get("position"))
            except (TypeError, ValueError):
                continue
            position_counts[position] = position_counts.get(position, 0) + 1
        for item in candidates:
            variant = str(item.get("variant") or "").upper()
            match = re.search(r"(?<![A-Z])([A-Z])(\d+)([A-Z])(?![A-Z])", variant)
            mutation_position = int(match.group(2)) if match else None
            item["lipase_evidence"] = {
                "source": "kwb_lipase_db",
                "exact_match_count": len(exact_by_mutation.get(variant, [])),
                "position_match_count": position_counts.get(mutation_position, 0) if mutation_position else 0,
                "matches": exact_by_mutation.get(variant, [])[:3],
                "interpretation": (
                    "exact KWB lipase literature evidence is available for this MD-ranked mutation"
                    if exact_by_mutation.get(variant)
                    else "no exact KWB lipase evidence found; treat MD ranking as computational evidence pending literature/assay review"
                ),
            }

    ranked = sorted(
        [item for item in candidates if item["ranking_score"] is not None and item.get("ranking_ready")],
        key=lambda item: item["ranking_score"],
        reverse=True,
    )
    blocked_candidates = [item for item in candidates if item.get("blocked_reasons")]
    recommended_next_steps = (
        ["Review top ranked variants against topology, active-site, KWB lipase literature evidence, and assay constraints before promotion."]
        if consistency.get("ranking_allowed") and ranked
        else consistency.get("recommended_next_steps", [])
    )
    if blocked_candidates:
        recommended_next_steps = list(recommended_next_steps) + [
            "Resolve blocked candidate gates, especially missing ranking metrics or mutant topology validation, before promotion."
        ]
    return {
        "version": 1,
        "status": "ranking_ready" if consistency.get("ranking_allowed") and ranked else "ranking_blocked",
        "ranking_allowed": bool(consistency.get("ranking_allowed") and ranked),
        "minimum_replicates": consistency.get("minimum_replicates"),
        "candidate_count": len(candidates),
        "blocked_candidate_count": len(blocked_candidates),
        "candidates": candidates,
        "ranked_candidates": ranked if consistency.get("ranking_allowed") else [],
        "lipase_evidence_context": lipase_evidence_context,
        "replicate_consistency": consistency,
        "recommended_next_steps": list(dict.fromkeys(recommended_next_steps)),
    }


def _build_protocol_review(protocol_id: str | None, parameters: dict[str, Any]) -> dict[str, Any]:
    from app.services.md_protocols import build_protocol_review

    return build_protocol_review(protocol_id, parameters)


def build_lipase_evidence_context(*args: Any, **kwargs: Any) -> Any:
    from app.services.lipase_db_status import build_lipase_evidence_context as _build

    return _build(*args, **kwargs)


def _simulation_steps(simulation_time_ns: float) -> int:
    # 0.002 ps timestep: 1 ns = 500,000 steps. Keep true units.
    return max(1, int(simulation_time_ns * 500_000))


def _equilibration_steps(equilibration_ps: float) -> int:
    return max(1, int(equilibration_ps / 0.002))


def _step_message(name: str) -> str:
    labels = {
        "01_pdb2gmx": "Preparing topology from uploaded structure",
        "02_editconf": "Building simulation box",
        "03_solvate": "Adding solvent molecules",
        "04_grompp_ions": "Preparing ionization input",
        "05_genion": "Neutralizing and salting the system",
        "06_grompp_minim": "Preparing energy minimization",
        "07_mdrun_minim": "Running energy minimization",
        "08_grompp_nvt": "Preparing NVT equilibration",
        "09_mdrun_nvt": "Running NVT equilibration",
        "10_grompp_npt": "Preparing NPT equilibration",
        "11_mdrun_npt": "Running NPT equilibration",
        "12_grompp_md": "Preparing production MD",
        "13_mdrun_md": "Running production MD",
        "14_rms": "Calculating RMSD trajectory",
        "15_rmsf": "Calculating RMSF profile",
        "16_gyrate": "Calculating radius of gyration",
        "17_sasa": "Calculating solvent-accessible area",
        "18_energy": "Extracting energy terms",
        "19_hbond": "Calculating hydrogen-bond counts",
    }
    return labels.get(name, name.replace("_", " "))


def _emit_progress(
    progress_callback,
    *,
    progress: int,
    message: str,
    stage: str,
    current_step: int,
    total_steps: int,
) -> None:
    if not callable(progress_callback):
        return
    progress_callback(
        max(0, min(100, int(progress))),
        message,
        stage,
        max(0, int(current_step)),
        max(0, int(total_steps)),
    )


def gromacs_md(
    sequence: str = "",
    pdb_data: str | None = None,
    pdb_object_name: str | None = None,
    pdb_path: str | None = None,
    protocol_id: str | None = None,
    simulation_time_ns: float = 0.1,
    temperature_k: float = 310.0,
    force_field: str = "amber99sb-ildn",
    water_model: str = "tip3p",
    pressure_bar: float = 1.0,
    salt_concentration_m: float = 0.15,
    ensemble: str = "npt",
    box_distance_nm: float = 1.0,
    equilibration_ps: float = 100.0,
    mdrun_threads: int = 1,
    upload_artifacts: bool = True,
    wild_type_replicates: list[dict[str, Any]] | None = None,
    mutant_replicates: list[dict[str, Any]] | None = None,
    replicate_plan_only: bool = False,
    replicate_count: int = 3,
    replicate_variants: list[Any] | None = None,
    replicate_seed_base: int = 1000,
    run_seed: int | None = None,
    batch_id: str | None = None,
    replicate_variant: str | None = None,
    replicate_index: int | None = None,
    progress_callback=None,
) -> dict[str, Any]:
    """Run a minimal real GROMACS MD workflow from a PDB structure."""
    planned_parameters = {
        "protocol_id": protocol_id,
        "simulation_time_ns": simulation_time_ns,
        "equilibration_ps": equilibration_ps,
        "temperature_k": temperature_k,
        "pressure_bar": pressure_bar,
        "salt_concentration_m": salt_concentration_m,
        "ensemble": ensemble,
        "force_field": force_field,
        "water_model": water_model,
        "mdrun_threads": mdrun_threads,
    }

    def with_contract(
        result: dict[str, Any],
        *,
        capability_status: str,
        runtime: dict[str, Any] | None = None,
        artifact_manifest: dict[str, Any] | None = None,
        logs: list[dict[str, Any]] | None = None,
        failure_reason: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        boundary = (
            "GROMACS MD is report-grade only when real gmx commands complete and topology, "
            "trajectory, analysis files, logs, and protocol controls are attached. Blocked or "
            "plan-only responses contain no simulated MD metrics."
        )
        return merge_capability_contract(
            result,
            capability_status=capability_status,
            model="GROMACS",
            version=None,
            checkpoint_or_weight=None,
            input_payload={
                "sequence": sequence,
                "pdb_data": pdb_data,
                "pdb_object_name": pdb_object_name,
                "pdb_path": pdb_path,
                **planned_parameters,
                "replicate_plan_only": replicate_plan_only,
                "replicate_count": replicate_count,
                "replicate_variants": replicate_variants,
                "replicate_seed_base": replicate_seed_base,
                "run_seed": run_seed,
                "batch_id": batch_id,
                "replicate_variant": replicate_variant,
                "replicate_index": replicate_index,
            },
            runtime=runtime,
            logs=logs,
            artifact_manifest=artifact_manifest,
            scientific_boundary=boundary,
            failure_reason=failure_reason,
        )

    if replicate_plan_only:
        plan = _build_replicate_execution_plan(
            protocol_id=protocol_id,
            parameters=planned_parameters,
            variants=replicate_variants,
            replicate_count=replicate_count,
            seed_base=replicate_seed_base,
        )
        return with_contract({
            "status": "planned",
            "is_real_md": False,
            "replicate_execution_plan": plan,
            "batch_replicate_summary": _build_md_batch_replicate_summary(
                wild_type_replicates=wild_type_replicates or [],
                mutant_replicates=mutant_replicates or [],
                minimum_replicates=replicate_count,
            ),
            "protocol_review": _build_protocol_review(protocol_id, planned_parameters),
            "note": "Replicate plan only; no GROMACS command was executed.",
        }, capability_status="blocked", failure_reason="plan_only_no_runtime_executed")

    gmx = _find_gmx()
    if not gmx:
        return with_contract({
            "status": "failed",
            "error_code": "GROMACS_NOT_INSTALLED",
            "error": "GROMACS executable not found. Install `gmx` or `gmx_mpi`, or set GROMACS_BIN.",
            "is_real_md": False,
            "required_runtime": [
                "GROMACS 2024+",
                "Force fields installed with GROMACS",
                "CPU build for minimal run or CUDA/OpenCL GPU build for production",
            ],
            "note": "No simulated/random MD metrics were generated.",
        }, capability_status="blocked", failure_reason="GROMACS_NOT_INSTALLED")

    if simulation_time_ns <= 0 or simulation_time_ns > 1000:
        return with_contract(
            {"status": "failed", "error": "simulation_time_ns must be > 0 and <= 1000.", "is_real_md": False},
            capability_status="blocked",
            failure_reason="invalid_simulation_time_ns",
        )
    resolved_force_field, installed_force_fields = _resolve_force_field(force_field)
    if not resolved_force_field:
        return with_contract({
            "status": "failed",
            "error": f"Unsupported or unavailable force_field: {force_field}",
            "supported": installed_force_fields,
            "is_real_md": False,
        }, capability_status="blocked", failure_reason="force_field_unavailable")
    if water_model not in _WATER_MODELS:
        return with_contract(
            {"status": "failed", "error": f"Unsupported water_model: {water_model}", "supported": _WATER_MODELS, "is_real_md": False},
            capability_status="blocked",
            failure_reason="water_model_unsupported",
        )
    if ensemble not in {"npt", "nvt", "nve"}:
        return with_contract(
            {"status": "failed", "error": "ensemble must be one of npt, nvt, nve.", "is_real_md": False},
            capability_status="blocked",
            failure_reason="ensemble_unsupported",
        )
    if mdrun_threads < 1 or mdrun_threads > 64:
        return with_contract(
            {"status": "failed", "error": "mdrun_threads must be between 1 and 64.", "is_real_md": False},
            capability_status="blocked",
            failure_reason="invalid_mdrun_threads",
        )

    try:
        pdb_text = _load_pdb_text(pdb_data, pdb_object_name, pdb_path)
        _validate_pdb(pdb_text)
        atom_count = _detect_atom_count(pdb_text)
        structure_preparation = _scan_structure_preparation(pdb_text)
    except Exception as exc:
        return with_contract({
            "status": "failed",
            "error_code": "INVALID_OR_MISSING_PDB",
            "error": str(exc),
            "is_real_md": False,
            "note": "No simulated/random MD metrics were generated.",
        }, capability_status="blocked", failure_reason="INVALID_OR_MISSING_PDB")

    job_id = uuid.uuid4().hex
    resolved_parameters = {
        "protocol_id": protocol_id,
        "simulation_time_ns": simulation_time_ns,
        "equilibration_ps": equilibration_ps,
        "temperature_k": temperature_k,
        "pressure_bar": pressure_bar,
        "salt_concentration_m": salt_concentration_m,
        "ensemble": ensemble,
        "force_field": resolved_force_field,
        "water_model": water_model,
        "mdrun_threads": mdrun_threads,
        "constraint_algorithm": "lincs",
        "constraints": "h-bonds",
        "coulombtype": "PME",
        "cutoff_scheme": "Verlet",
        "rcoulomb_nm": 1.0,
        "rvdw_nm": 1.0,
    }
    protocol_review = _build_protocol_review(protocol_id, resolved_parameters)
    if structure_preparation.get("warnings"):
        protocol_review = {
            **protocol_review,
            "structure_preparation_warnings": structure_preparation["warnings"],
            "review_warnings": list(protocol_review.get("review_warnings") or []) + structure_preparation["warnings"],
        }
    with tempfile.TemporaryDirectory(prefix=f"gromacs_md_{job_id}_") as tmp:
        workdir = Path(tmp)
        input_pdb = workdir / "input.pdb"
        _write(input_pdb, pdb_text)
        _write(workdir / "ions.mdp", _IONS_MDP)
        _write(workdir / "minim.mdp", _MINIM_MDP)
        _write(
            workdir / "nvt.mdp",
            _NVT_MDP.format(
                nvt_steps=_equilibration_steps(equilibration_ps),
                temperature_k=temperature_k,
                run_seed=int(run_seed) if run_seed is not None else -1,
            ),
        )
        _write(
            workdir / "npt.mdp",
            _NPT_MDP.format(
                npt_steps=_equilibration_steps(equilibration_ps),
                temperature_k=temperature_k,
                pressure_bar=pressure_bar,
            ),
        )
        _write(
            workdir / "md.mdp",
            _MD_MDP.format(
                md_steps=_simulation_steps(simulation_time_ns),
                temperature_k=temperature_k,
                pressure_bar=pressure_bar,
            ),
        )

        logs: list[dict[str, str]] = []
        total_steps = 20 if ensemble == "npt" else 18

        def run_step(
            step_number: int,
            name: str,
            cmd: list[str],
            input_text: str | None = None,
            timeout: int = 1800,
        ) -> None:
            start_progress = min(94, max(1, int(((step_number - 1) / total_steps) * 90) + 1))
            end_progress = min(95, max(start_progress, int((step_number / total_steps) * 90)))
            _emit_progress(
                progress_callback,
                progress=start_progress,
                message=_step_message(name),
                stage=name,
                current_step=step_number,
                total_steps=total_steps,
            )
            output = _run(cmd, workdir, input_text=input_text, timeout=timeout)
            (workdir / f"{name}.log.txt").write_text(output, encoding="utf-8", errors="replace")
            logs.append({"step": name, "command": " ".join(cmd), "log_file": f"{name}.log.txt"})
            _emit_progress(
                progress_callback,
                progress=end_progress,
                message=f"Completed: {_step_message(name)}",
                stage=name,
                current_step=step_number,
                total_steps=total_steps,
            )

        try:
            run_step(
                1,
                "01_pdb2gmx",
                [
                    gmx,
                    "pdb2gmx",
                    "-f",
                    "input.pdb",
                    "-o",
                    "processed.gro",
                    "-p",
                    "topol.top",
                    "-ignh",
                    "-ff",
                    resolved_force_field,
                    "-water",
                    water_model,
                ],
            )
            run_step(
                2,
                "02_editconf",
                [gmx, "editconf", "-f", "processed.gro", "-o", "boxed.gro", "-c", "-d", str(box_distance_nm), "-bt", "cubic"],
            )
            run_step(3, "03_solvate", [gmx, "solvate", "-cp", "boxed.gro", "-cs", "spc216.gro", "-o", "solvated.gro", "-p", "topol.top"])
            run_step(4, "04_grompp_ions", [gmx, "grompp", "-f", "ions.mdp", "-c", "solvated.gro", "-p", "topol.top", "-o", "ions.tpr", "-maxwarn", "2"])
            run_step(
                5,
                "05_genion",
                [
                    gmx,
                    "genion",
                    "-s",
                    "ions.tpr",
                    "-o",
                    "solv_ions.gro",
                    "-p",
                    "topol.top",
                    "-pname",
                    "NA",
                    "-nname",
                    "CL",
                    "-neutral",
                    "-conc",
                    str(salt_concentration_m),
                ],
                input_text="SOL\n",
            )
            run_step(6, "06_grompp_minim", [gmx, "grompp", "-f", "minim.mdp", "-c", "solv_ions.gro", "-p", "topol.top", "-o", "em.tpr", "-maxwarn", "2"])
            run_step(7, "07_mdrun_minim", [gmx, "mdrun", "-deffnm", "em", "-nt", str(mdrun_threads)], timeout=3600)
            run_step(8, "08_grompp_nvt", [gmx, "grompp", "-f", "nvt.mdp", "-c", "em.gro", "-r", "em.gro", "-p", "topol.top", "-o", "nvt.tpr", "-maxwarn", "2"])
            run_step(9, "09_mdrun_nvt", [gmx, "mdrun", "-deffnm", "nvt", "-nt", str(mdrun_threads)], timeout=3600)

            production_input = "nvt"
            production_step = 10
            if ensemble == "npt":
                run_step(10, "10_grompp_npt", [gmx, "grompp", "-f", "npt.mdp", "-c", "nvt.gro", "-r", "nvt.gro", "-t", "nvt.cpt", "-p", "topol.top", "-o", "npt.tpr", "-maxwarn", "2"])
                run_step(11, "11_mdrun_npt", [gmx, "mdrun", "-deffnm", "npt", "-nt", str(mdrun_threads)], timeout=3600)
                production_input = "npt"
                production_step = 12

            input_gro = f"{production_input}.gro"
            input_cpt = f"{production_input}.cpt"
            run_step(
                production_step,
                "12_grompp_md",
                [gmx, "grompp", "-f", "md.mdp", "-c", input_gro, "-t", input_cpt, "-p", "topol.top", "-o", "md.tpr", "-maxwarn", "2"],
            )
            run_step(production_step + 1, "13_mdrun_md", [gmx, "mdrun", "-deffnm", "md", "-nt", str(mdrun_threads)], timeout=max(3600, int(simulation_time_ns * 7200)))

            analysis_selection_plan = _build_analysis_selection_plan()
            analysis_selection_resolution: dict[str, Any] = {}
            analysis_selection_resolution["rms"] = _run_step_with_selection_fallback(
                run_step,
                step_number=production_step + 2,
                name="14_rms",
                cmd=[gmx, "rms", "-s", "md.tpr", "-f", "md.xtc", "-o", "rmsd.xvg"],
                candidate_inputs=analysis_selection_plan["fallback_inputs"]["rms"],
                workdir=workdir,
            )
            analysis_selection_resolution["rmsf"] = _run_step_with_selection_fallback(
                run_step,
                step_number=production_step + 3,
                name="15_rmsf",
                cmd=[gmx, "rmsf", "-s", "md.tpr", "-f", "md.xtc", "-o", "rmsf.xvg", "-res"],
                candidate_inputs=analysis_selection_plan["fallback_inputs"]["rmsf"],
                workdir=workdir,
            )
            analysis_selection_resolution["gyrate"] = _run_step_with_selection_fallback(
                run_step,
                step_number=production_step + 4,
                name="16_gyrate",
                cmd=[gmx, "gyrate", "-s", "md.tpr", "-f", "md.xtc", "-o", "gyrate.xvg"],
                candidate_inputs=analysis_selection_plan["fallback_inputs"]["gyrate"],
                workdir=workdir,
            )
            analysis_selection_resolution["sasa"] = _run_step_with_selection_fallback(
                run_step,
                step_number=production_step + 5,
                name="17_sasa",
                cmd=[gmx, "sasa", "-s", "md.tpr", "-f", "md.xtc", "-o", "sasa.xvg"],
                candidate_inputs=analysis_selection_plan["fallback_inputs"]["sasa"],
                workdir=workdir,
            )
            try:
                analysis_selection_resolution["energy"] = _run_step_with_selection_fallback(
                    run_step,
                    step_number=production_step + 6,
                    name="18_energy",
                    cmd=[gmx, "energy", "-f", "md.edr", "-o", "energy.xvg"],
                    candidate_inputs=analysis_selection_plan["fallback_inputs"]["energy"],
                    workdir=workdir,
                )
            except Exception as exc:
                (workdir / "18_energy.warning.log.txt").write_text(str(exc), encoding="utf-8", errors="replace")
            try:
                analysis_selection_resolution["hbond_intra_protein"] = _run_step_with_selection_fallback(
                    run_step,
                    step_number=production_step + 7,
                    name="19_hbond",
                    cmd=[gmx, "hbond", "-s", "md.tpr", "-f", "md.xtc", "-num", "hbonds.xvg"],
                    candidate_inputs=analysis_selection_plan["fallback_inputs"]["hbond_intra_protein"],
                    workdir=workdir,
                )
            except Exception as exc:
                (workdir / "19_hbond.warning.log.txt").write_text(str(exc), encoding="utf-8", errors="replace")
            try:
                analysis_selection_resolution["hbond_protein_solvent"] = _run_step_with_selection_fallback(
                    run_step,
                    step_number=production_step + 8,
                    name="20_hbond_solvent",
                    cmd=[gmx, "hbond", "-s", "md.tpr", "-f", "md.xtc", "-num", "hbonds_solvent.xvg"],
                    candidate_inputs=analysis_selection_plan["fallback_inputs"]["hbond_protein_solvent"],
                    workdir=workdir,
                )
            except Exception as exc:
                (workdir / "20_hbond_solvent.warning.log.txt").write_text(str(exc), encoding="utf-8", errors="replace")
        except Exception as exc:
            failure_log = workdir / "failure.log.txt"
            failure_log.write_text(str(exc), encoding="utf-8", errors="replace")
            artifacts = _save_artifacts(workdir, [p.name for p in workdir.glob("*.log.txt")], job_id) if upload_artifacts else []
            _emit_progress(
                progress_callback,
                progress=100,
                message=f"MD pipeline failed: {exc}",
                stage="failed",
                current_step=total_steps,
                total_steps=total_steps,
            )
            return with_contract({
                "status": "failed",
                "error_code": "GROMACS_PIPELINE_FAILED",
                "error": str(exc),
                "job_id": job_id,
                "is_real_md": True,
                "artifacts": artifacts,
                "artifact_manifest": _build_artifact_manifest(artifacts),
                "logs": logs,
            },
                capability_status="blocked",
                runtime={"engine": "GROMACS", "executable": gmx, "job_id": job_id},
                logs=logs,
                artifact_manifest=_build_artifact_manifest(artifacts),
                failure_reason={"code": "GROMACS_PIPELINE_FAILED", "message": str(exc)},
            )

        rmsd_rows = _parse_xvg_series(workdir / "rmsd.xvg")
        rmsf_rows = _parse_xvg_series(workdir / "rmsf.xvg")
        gyrate_rows = _parse_xvg_series(workdir / "gyrate.xvg")
        sasa_rows = _parse_xvg_series(workdir / "sasa.xvg")
        energy_rows = _parse_xvg_multi_series(workdir / "energy.xvg")
        hbond_rows = _parse_xvg_multi_series(workdir / "hbonds.xvg")
        solvent_hbond_rows = _parse_xvg_multi_series(workdir / "hbonds_solvent.xvg")

        _write_csv(workdir / "rmsd.csv", rmsd_rows, "time_ps", "rmsd_nm")
        _write_csv(workdir / "rmsf.csv", rmsf_rows, "residue", "rmsf_nm")
        _write_csv(workdir / "gyrate.csv", gyrate_rows, "time_ps", "rg_nm")
        _write_csv(workdir / "sasa.csv", sasa_rows, "time_ps", "sasa_nm2")
        if energy_rows:
            _write_multi_csv(workdir / "energy.csv", energy_rows, ["time_ps", "potential_energy_kjmol", "kinetic_energy_kjmol", "total_energy_kjmol"])
        if hbond_rows:
            _write_multi_csv(workdir / "hbonds.csv", hbond_rows, ["time_ps", "hbond_count"])
        if solvent_hbond_rows:
            _write_multi_csv(workdir / "hbonds_solvent.csv", solvent_hbond_rows, ["time_ps", "hbond_count"])

        rmsd_final = _last_value(rmsd_rows)
        rmsd_equilibrated = _mean_value(rmsd_rows[len(rmsd_rows) // 2 :]) if rmsd_rows else None
        rmsd_drift = None if rmsd_final is None or rmsd_equilibrated is None else rmsd_final - rmsd_equilibrated
        mean_rmsf = _mean_value(rmsf_rows)
        max_rmsf = _max_value(rmsf_rows)

        flexible_regions = [
            {
                "residues": str(int(pos)),
                "mean_rmsf_nm": round(value, 4),
                "interpretation": "high-mobility residue from real RMSF analysis",
            }
            for pos, value in rmsf_rows
            if max_rmsf is not None and value >= max(0.3, max_rmsf * 0.8)
        ][:25]

        artifact_names = [
            "input.pdb",
            "processed.gro",
            "solv_ions.gro",
            "em.gro",
            "nvt.gro",
            "npt.gro",
            "md.tpr",
            "md.xtc",
            "md.edr",
            "md.log",
            "rmsd.xvg",
            "rmsf.xvg",
            "gyrate.xvg",
            "sasa.xvg",
            "energy.xvg",
            "hbonds.xvg",
            "hbonds_solvent.xvg",
            "rmsd.csv",
            "rmsf.csv",
            "gyrate.csv",
            "sasa.csv",
            "energy.csv",
            "hbonds.csv",
            "hbonds_solvent.csv",
            "topol.top",
            "ions.mdp",
            "minim.mdp",
            "nvt.mdp",
            "npt.mdp",
            "md.mdp",
        ] + [p.name for p in workdir.glob("*.log.txt")]
        _emit_progress(
            progress_callback,
            progress=96,
            message="Packaging and uploading MD artifacts",
            stage="artifact_upload",
            current_step=total_steps,
            total_steps=total_steps,
        )
        artifacts = _save_artifacts(workdir, artifact_names, job_id) if upload_artifacts else []
        artifact_manifest = _build_artifact_manifest(artifacts)

        rg_initial = gyrate_rows[0][1] if gyrate_rows else None
        rg_final = _last_value(gyrate_rows)
        sasa_initial = sasa_rows[0][1] if sasa_rows else None
        sasa_final = _last_value(sasa_rows)
        energetics = _parse_energy_terms(workdir / "energy.xvg")
        interactions = {
            **_parse_hbond_counts(workdir / "hbonds.xvg"),
            "protein_solvent_hbonds": _parse_hbond_count(workdir / "hbonds_solvent.xvg"),
        }
        topology_review = _scan_topology_warnings(workdir)
        current_wt_replicate = {
            "replicate_id": job_id,
            "rmsd_drift_nm": round(rmsd_drift, 4) if rmsd_drift is not None else None,
            "mean_rmsf_nm": round(mean_rmsf, 4) if mean_rmsf is not None else None,
            "rg_change_nm": round(rg_final - rg_initial, 4) if rg_initial is not None and rg_final is not None else None,
            "sasa_change_nm2": round(sasa_final - sasa_initial, 4) if sasa_initial is not None and sasa_final is not None else None,
            "is_stable": bool(rmsd_drift is not None and abs(rmsd_drift) < 0.15),
        }
        controls = protocol_review.get("scientific_controls") if isinstance(protocol_review.get("scientific_controls"), dict) else {}
        replicate_policy = controls.get("replicate_policy") if isinstance(controls.get("replicate_policy"), dict) else {}
        minimum_replicates = int(replicate_policy.get("minimum_for_ranking") or 3)
        replicate_consistency = _build_replicate_consistency(
            wild_type_replicates=[*(wild_type_replicates or []), current_wt_replicate],
            mutant_replicates=mutant_replicates,
            minimum_replicates=minimum_replicates,
        )
        md_interpretation = _build_md_interpretation(
            rmsd_final=rmsd_final,
            rmsd_drift=rmsd_drift,
            mean_rmsf=mean_rmsf,
            max_rmsf=max_rmsf,
            rg_initial=rg_initial,
            rg_final=rg_final,
            sasa_initial=sasa_initial,
            sasa_final=sasa_final,
            flexible_regions=flexible_regions,
            simulation_time_ns=simulation_time_ns,
            protocol_review=protocol_review,
            energetics=energetics,
            interactions=interactions,
            analysis_files={
                "rmsd_xvg": bool(rmsd_rows),
                "rmsf_xvg": bool(rmsf_rows),
                "gyrate_xvg": bool(gyrate_rows),
                "sasa_xvg": bool(sasa_rows),
                "energy_edr": (workdir / "md.edr").exists(),
                "energy_xvg": bool(energy_rows),
                "hbonds_xvg": bool(hbond_rows),
                "hbonds_solvent_xvg": bool(solvent_hbond_rows),
            },
            structure_preparation=structure_preparation,
            replicate_consistency=replicate_consistency,
            topology_review=topology_review,
        )

        _emit_progress(
            progress_callback,
            progress=99,
            message="Finalizing MD report",
            stage="finalize",
            current_step=total_steps,
            total_steps=total_steps,
        )
        return with_contract({
            "status": "completed",
            "job_id": job_id,
            "is_real_md": True,
            "engine": "GROMACS",
            "gromacs_executable": gmx,
            "ensemble": ensemble.upper(),
            "pressure_bar": pressure_bar,
            "salt_concentration_m": salt_concentration_m,
            "wild_type": {
                "simulation_parameters": {
                    **resolved_parameters,
                    "sequence_length": len(sequence.strip()) if sequence else None,
                    "estimated_atom_count": atom_count,
                    "input_type": "pdb_object_name" if pdb_object_name else ("pdb_path" if pdb_path else "pdb_data"),
                    "pdb_object_name": pdb_object_name,
                    "run_seed": int(run_seed) if run_seed is not None else None,
                    "batch_id": batch_id,
                    "replicate_variant": replicate_variant,
                    "replicate_index": int(replicate_index) if replicate_index is not None else None,
                },
                "structural_stability": {
                    "rmsd_equilibrated_nm": round(rmsd_equilibrated, 4) if rmsd_equilibrated is not None else None,
                    "rmsd_final_nm": round(rmsd_final, 4) if rmsd_final is not None else None,
                    "rmsd_drift_nm": round(rmsd_drift, 4) if rmsd_drift is not None else None,
                    "mean_rmsf_nm": round(mean_rmsf, 4) if mean_rmsf is not None else None,
                    "is_stable": bool(rmsd_drift is not None and abs(rmsd_drift) < 0.15),
                },
                "compactness": {
                    "radius_of_gyration_initial_nm": round(rg_initial, 4) if rg_initial is not None else None,
                    "radius_of_gyration_final_nm": round(rg_final, 4) if rg_final is not None else None,
                    "rg_change_nm": round(rg_final - rg_initial, 4) if rg_initial is not None and rg_final is not None else None,
                    "sasa_initial_nm2": round(sasa_initial, 4) if sasa_initial is not None else None,
                    "sasa_final_nm2": round(sasa_final, 4) if sasa_final is not None else None,
                },
                "interactions": interactions,
                "energetics": {
                    "potential_energy_kjmol": round(energetics["potential_energy_kjmol"], 4) if energetics["potential_energy_kjmol"] is not None else None,
                    "kinetic_energy_kjmol": round(energetics["kinetic_energy_kjmol"], 4) if energetics["kinetic_energy_kjmol"] is not None else None,
                    "total_energy_kjmol": round(energetics["total_energy_kjmol"], 4) if energetics["total_energy_kjmol"] is not None else None,
                },
                "flexible_regions": flexible_regions,
                "structure_preparation": structure_preparation,
                "replicate_consistency": replicate_consistency,
                "topology_review": topology_review,
                "analysis_selection_resolution": analysis_selection_resolution,
                "interpretation": md_interpretation,
                "note": "Real GROMACS MD results parsed from generated XVG files.",
            },
            "interpretation": md_interpretation,
            "mutants": None,
            "replicate_consistency": replicate_consistency,
            "topology_review": topology_review,
            "analysis_selection_plan": analysis_selection_plan,
            "analysis_selection_resolution": analysis_selection_resolution,
            "artifacts": artifacts,
            "artifact_manifest": artifact_manifest,
            "logs": logs,
            "note": "Minimal real MD pipeline completed. For publication-grade conclusions, use longer trajectories and expert parameter review.",
        },
            capability_status="real_runtime",
            runtime={"engine": "GROMACS", "executable": gmx, "job_id": job_id},
            logs=logs,
            artifact_manifest=artifact_manifest,
            failure_reason=None,
        )


ToolRegistry.register(
    name="gromacs_md",
    description=(
        "Real GROMACS molecular dynamics pipeline from a PDB structure. Requires "
        "`gmx` or `gmx_mpi` in the runtime. Runs pdb2gmx, box setup, solvation, "
        "ionization, minimization, NVT/NPT equilibration, production MD, and "
        "RMSD/RMSF/Rg/SASA analysis. Does not generate simulated placeholder data."
    ),
    handler=gromacs_md,
    is_async=False,
    category="simulation",
    # Must stay within scheduler._TASK_PROFILES[gromacs_md].time_limit.
    timeout_seconds=5400,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Optional sequence metadata. Real MD requires PDB input.",
                "default": "",
            },
            "pdb_data": {
                "type": "string",
                "description": "Raw PDB text. Use this, pdb_path, or pdb_object_name.",
            },
            "pdb_object_name": {
                "type": "string",
                "description": "Uploaded storage object name for a PDB/CIF converted to PDB.",
            },
            "pdb_path": {
                "type": "string",
                "description": "Local path to a PDB file available inside the backend/worker container.",
            },
            "protocol_id": {
                "type": "string",
                "description": "Optional MD protocol template id used to produce these parameters.",
            },
            "simulation_time_ns": {
                "type": "number",
                "description": "Production MD length in nanoseconds. Default 0.1 for smoke testing.",
                "default": 0.1,
            },
            "temperature_k": {"type": "number", "description": "Temperature in Kelvin", "default": 310.0},
            "force_field": {
                "type": "string",
                "description": "GROMACS force field selection prompt value",
                "default": "amber99sb-ildn",
            },
            "water_model": {
                "type": "string",
                "description": "GROMACS water model selection prompt value",
                "default": "tip3p",
            },
            "pressure_bar": {"type": "number", "description": "Pressure in bar", "default": 1.0},
            "salt_concentration_m": {"type": "number", "description": "NaCl concentration", "default": 0.15},
            "ensemble": {"type": "string", "description": "npt, nvt, or nve", "default": "npt"},
            "box_distance_nm": {"type": "number", "description": "Box padding distance", "default": 1.0},
            "equilibration_ps": {"type": "number", "description": "NVT/NPT equilibration length in ps", "default": 100.0},
            "mdrun_threads": {
                "type": "integer",
                "description": "Threads passed to `gmx mdrun -nt`. Keep small on shared servers.",
                "default": 1,
                "minimum": 1,
                "maximum": 64,
            },
            "upload_artifacts": {"type": "boolean", "description": "Upload generated artifacts to storage", "default": True},
            "replicate_plan_only": {
                "type": "boolean",
                "description": "Return a multi-replicate execution plan without running GROMACS.",
                "default": False,
            },
            "replicate_count": {
                "type": "integer",
                "description": "Replicates per WT/mutant variant for plan-only and ranking gates.",
                "default": 3,
                "minimum": 1,
                "maximum": 20,
            },
            "replicate_variants": {
                "type": "array",
                "description": "Optional mutant variant names or objects used to build a replicate execution plan.",
                "items": {},
                "default": [],
            },
            "replicate_seed_base": {
                "type": "integer",
                "description": "Base seed for deterministic replicate plan generation.",
                "default": 1000,
            },
            "run_seed": {
                "type": "integer",
                "description": "Optional deterministic GROMACS gen_seed for this concrete replicate run.",
            },
            "batch_id": {
                "type": "string",
                "description": "Optional MD replicate batch id for audit/report traceability.",
            },
            "replicate_variant": {
                "type": "string",
                "description": "Optional variant label for this concrete replicate run.",
            },
            "replicate_index": {
                "type": "integer",
                "description": "Optional one-based replicate index for this concrete run.",
            },
            "wild_type_replicates": {
                "type": "array",
                "description": "Optional prior WT replicate metric rows for consistency review.",
                "items": {"type": "object"},
                "default": [],
            },
            "mutant_replicates": {
                "type": "array",
                "description": "Optional mutant replicate metric rows with variant/mutation and MD metrics for consistency review.",
                "items": {"type": "object"},
                "default": [],
            },
        },
        "required": [],
    },
)
