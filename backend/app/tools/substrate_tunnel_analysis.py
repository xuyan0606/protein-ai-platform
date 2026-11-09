"""Fail-closed adapter for structure-based substrate tunnel analysis."""

from __future__ import annotations

import os
import shutil
import csv
import tempfile
import subprocess
import hashlib
from pathlib import Path

from app.tools.registry import ToolRegistry


def substrate_tunnel_analysis(
    protein_pdb: str,
    start_point: list[float] | None = None,
    engine: str = "auto",
) -> dict:
    """Validate tunnel-analysis inputs and block when no validated engine exists."""
    pdb = protein_pdb.strip()
    atom_count = sum(line.startswith(("ATOM  ", "HETATM")) for line in pdb.splitlines())
    if atom_count == 0:
        raise ValueError("INVALID_PDB: no ATOM or HETATM records found")
    if start_point is not None and len(start_point) != 3:
        raise ValueError("INVALID_START_POINT: expected [x, y, z]")
    if engine not in {"auto", "caver", "p2rank", "fpocket"}:
        raise ValueError("UNSUPPORTED_ENGINE: use auto, caver, p2rank, or fpocket")
    if engine in {"p2rank", "fpocket"}:
        return {
            "status": "blocked_incompatible_engine",
            "engine_requested": engine,
            "atom_count": atom_count,
            "start_point": start_point,
            "tunnels": [],
            "blocked_reason": f"{engine} predicts binding pockets, not continuous substrate tunnels.",
            "required_action": "Use pocket_residue_lookup for pocket prediction or configure a validated CAVER adapter.",
            "alternative_path": {"status": "available_with_different_claim", "options": ["pocket_residue_lookup", "expert_structure_review"], "boundary": "Pocket prediction does not provide tunnel continuity, bottleneck radius, or transport path."},
        }

    configured = os.getenv("CAVER_BIN", "").strip()
    caver = Path(configured) if configured else None
    executable = str(caver) if caver and caver.is_file() else shutil.which("caver")
    home = Path(os.getenv("CAVER_HOME", "").strip()) if os.getenv("CAVER_HOME", "").strip() else None
    if executable is None and home:
        jar = home / "caver.jar"
        if jar.is_file():
            executable = str(jar)
    if executable and executable.endswith(".jar"):
        return _run_caver(pdb, Path(executable), start_point, atom_count, home)
    service_url = os.getenv("CAVER_SERVICE_URL", "").rstrip("/")
    if service_url:
        try:
            import json
            from urllib.request import Request, urlopen
            request = Request(f"{service_url}/predict", data=json.dumps({"pdb_data": pdb, "start_point": start_point}).encode(), headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=320) as response:
                return json.loads(response.read())
        except Exception as exc:
            return {"status": "blocked_engine_service", "engine_requested": engine, "atom_count": atom_count, "start_point": start_point, "tunnels": [], "blocked_reason": f"CAVER service failed: {type(exc).__name__}"}
    if executable is None:
        return {
            "status": "blocked_missing_engine",
            "engine_requested": engine,
            "atom_count": atom_count,
            "start_point": start_point,
            "tunnels": [],
            "blocked_reason": "No validated CAVER tunnel runtime was detected.",
            "required_action": "Install and validate CAVER, then configure its invocation adapter.",
            "alternative_path": {"status": "available_with_different_claim", "options": ["pocket_residue_lookup", "expert_structure_review"], "boundary": "Alternatives identify pockets or support review; they do not calculate continuous tunnels."},
        }
    return {
        "status": "blocked_adapter_not_configured",
        "engine_detected": "caver",
        "engine_executable": executable,
        "atom_count": atom_count,
        "start_point": start_point,
        "tunnels": [],
        "blocked_reason": "CAVER was detected but its validated invocation adapter is not configured.",
    }


def _run_caver(pdb: str, jar: Path, start_point: list[float] | None, atom_count: int, home: Path | None) -> dict:
    """Run the official CAVER command-line JAR and parse auditable outputs."""
    caver_home = home or jar.parent
    lib_dir = caver_home / "lib"
    try:
        atom_serial = next(int(line[6:11]) for line in pdb.splitlines() if line.startswith(("ATOM  ", "HETATM")))
        with tempfile.TemporaryDirectory(prefix="protein-ai-caver-") as directory:
            root = Path(directory)
            pdb_dir = root / "pdb"
            out_dir = root / "out"
            pdb_dir.mkdir()
            (pdb_dir / "input.pdb").write_text(pdb.rstrip() + "\n", encoding="utf-8")
            config = root / "config.txt"
            config.write_text(
                "\n".join((
                    "load_tunnels no", "load_cluster_tree no", "first_frame 1", "last_frame 1",
                    f"starting_point_atom {atom_serial}", "probe_radius 0.9", "clustering average_link",
                    "generate_summary yes", "generate_tunnel_characteristics yes", "generate_tunnel_profiles yes",
                    "compute_tunnel_residues yes", "compute_bottleneck_residues yes", "parallel no", ""
                )), encoding="utf-8"
            )
            classpath = str(lib_dir) if lib_dir.is_dir() else str(jar)
            subprocess.run(
                ["java", "-Xmx1200m", "-cp", classpath, "-jar", str(jar), "-home", str(caver_home),
                 "-pdb", str(pdb_dir), "-conf", str(config), "-out", str(out_dir)],
                text=True, capture_output=True, timeout=300, check=True,
            )
            characteristics = out_dir / "analysis" / "tunnel_characteristics.csv"
            tunnels: list[dict] = []
            if characteristics.is_file():
                with characteristics.open(newline="", encoding="utf-8", errors="replace") as stream:
                    tunnels = list(csv.DictReader(stream))
            if not tunnels:
                return {"status": "completed_caver_no_tunnels", "engine_detected": "caver", "atom_count": atom_count, "start_point": start_point, "tunnels": []}
            digest = hashlib.sha256(jar.read_bytes()).hexdigest()
            return {
                "status": "completed_caver_tunnel_analysis", "engine_detected": "caver",
                "engine_executable": str(jar), "engine_sha256": digest, "atom_count": atom_count,
                "start_point": start_point, "tunnels": tunnels,
                "artifact_manifest": {
                    "characteristics_sha256": hashlib.sha256(characteristics.read_bytes()).hexdigest(),
                    "tunnel_count": len(tunnels),
                },
            }
    except (OSError, StopIteration, subprocess.SubprocessError, ValueError) as exc:
        return {"status": "failed_caver_runtime", "engine_detected": "caver", "atom_count": atom_count, "start_point": start_point, "tunnels": [], "blocked_reason": f"CAVER execution failed: {type(exc).__name__}"}


ToolRegistry.register(
    name="substrate_tunnel_analysis",
    description="Validate a protein structure for tunnel analysis and fail closed unless a validated engine adapter is available.",
    parameters={
        "type": "object",
        "properties": {
            "protein_pdb": {"type": "string", "description": "Protein structure in PDB format"},
            "start_point": {
                "type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
            },
            "engine": {"type": "string", "enum": ["auto", "caver", "p2rank", "fpocket"], "default": "auto"},
        },
        "required": ["protein_pdb"],
    },
    handler=substrate_tunnel_analysis,
    category="structure_analysis",
    timeout_seconds=30,
)
