"""Execute pinned, unmodified biofold/DDGun; never supply fallback scores.

The service process may use modern Python. DDGUN_PYTHON points to the separate
legacy-compatible scientific environment (Python 3.6 / Biopython 1.76).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import time
from typing import Any

COMMIT = "bcf112c616bcd4eb9b18f193ec08cc704eb761b5"
SIGN = "positive=increased unfolding stability"
AMINO = "ACDEFGHIKLMNPQRSTVWY"


def digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


def _safe_path(value: str | Path) -> Path:
    # Preserve venv executable symlinks; resolving them would lose its PATH.
    path = Path(os.path.abspath(value))
    # Upstream constructs internal shell commands. Never place untrusted shell
    # characters (including whitespace) into those commands.
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)):
        raise ValueError("DDGun runtime paths must contain only safe ASCII path characters")
    return path


def _validate(payload: dict) -> tuple[str, list[str], str, str]:
    sequence = payload.get("sequence")
    if not isinstance(sequence, str) or not 1 <= len(sequence) <= 4000 or set(sequence) - set(AMINO):
        raise ValueError("DDGun requires 1–4000 canonical uppercase residues")
    mutations = payload.get("mutations")
    if not isinstance(mutations, list) or not 1 <= len(mutations) <= 500 or any(not isinstance(m, str) for m in mutations):
        raise ValueError("DDGun requires 1–500 single substitutions")
    if len(set(mutations)) != len(mutations):
        raise ValueError("Duplicate mutations")
    for mutation in mutations:
        match = re.fullmatch(r"([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]{0,4})([ACDEFGHIKLMNPQRSTVWY])", mutation)
        if not match or int(match[2]) > len(sequence) or sequence[int(match[2]) - 1] != match[1] or match[1] == match[3]:
            raise ValueError("Mutation must change a matching WT residue at a 1-based position")
    chain = payload.get("chain_id")
    if not isinstance(chain, str) or not re.fullmatch(r"[A-Za-z0-9]", chain):
        raise ValueError("Invalid PDB chain")
    pdb = payload.get("pdb_data")
    if not isinstance(pdb, str) or len(pdb.encode()) > 8_000_000:
        raise ValueError("Invalid PDB text")
    mode = payload.get("mode")
    if mode not in ("sequence", "3d") or (mode == "3d") != bool(pdb.strip()):
        raise ValueError("DDGun mode must agree with PDB presence")
    if mode == "3d":
        residues: dict[int, str] = {}
        codes = dict(zip("ALA CYS ASP GLU PHE GLY HIS ILE LYS LEU MET ASN PRO GLN ARG SER THR VAL TRP TYR".split(), AMINO))
        models = 0
        for line in pdb.splitlines():
            if line.startswith("MODEL"):
                models += 1
                if models > 1:
                    break
            if line.startswith("ENDMDL"):
                break
            if not line.startswith("ATOM  ") or len(line) < 54 or line[21] != chain or line[12:16].strip() != "CA" or line[16] not in (" ", "A"):
                continue
            position = int(line[22:26])
            if line[26] != " " or (position not in residues and position != len(residues) + 1):
                raise ValueError("PDB chain requires complete contiguous 1..L numbering")
            aa = codes.get(line[17:20])
            if aa is None or (position in residues and residues[position] != aa):
                raise ValueError("Unsupported/ambiguous PDB residue")
            if not all(math.isfinite(float(line[start:start + 8])) for start in (30, 38, 46)):
                raise ValueError("Invalid PDB coordinates")
            residues[position] = aa
        if "".join(residues.values()) != sequence:
            raise ValueError("PDB chain sequence must match the entire input sequence")
    return sequence, mutations, mode, chain


def _parse_output(text: str, mode: str, expected: list[str]) -> dict[str, float]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("#"):
        raise ValueError("DDGun output header missing")
    header = lines[0].lstrip("#").split()
    score_column = "T_DDG[3D]" if mode == "3d" else "T_DDG[SEQ]"
    if score_column not in header or "VARIANT" not in header:
        raise ValueError("Unexpected DDGun output schema")
    results = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != len(header):
            raise ValueError("Malformed DDGun output row")
        mutation = parts[header.index("VARIANT")]
        score = float(parts[header.index(score_column)])
        if mutation not in expected or mutation in results or not math.isfinite(score):
            raise ValueError("Incomplete, duplicate or invalid DDGun result")
        effect = parts[-1]
        if effect != ("Increase" if score > 0 else "Decrease" if score < 0 else "Neutral"):
            raise ValueError("DDGun score/sign label disagreement")
        results[mutation] = score
    if set(results) != set(expected):
        raise ValueError("DDGun did not return all mutations and WT control")
    return results


def _first_model_pdb(pdb: str) -> str:
    """Match the adapter's first-model policy in the actual scientific input."""
    lines = []
    models = 0
    for line in pdb.splitlines():
        if line.startswith("MODEL"):
            models += 1
            if models > 1:
                break
            continue
        if line.startswith("ENDMDL") or line.strip() == "END":
            break
        if line.startswith("ATOM  ") and len(line) > 16 and line[16] not in (" ", "A"):
            continue
        lines.append(line)
    return "\n".join(lines) + "\nEND\n"


def run_ddgun(payload: dict, workdir: Path) -> dict:
    """Return the exact adapter envelope; any missing dependency fails closed.

    Required environment: DDGUN_SOURCE_DIR, DDGUN_PYTHON, DDGUN_HHBLITS,
    DDGUN_DB_PREFIX, DDGUN_DATABASE_VERSION. Source integrity is verified against
    DDGUN_SOURCE_MANIFEST (default SOURCE_MANIFEST.json under source directory).
    """
    base = {"status": "blocked", "model": "DDGun", "predictions": [],
            "model_version": None, "algorithm_commit": None, "database_version": None,
            "sequence_sha256": digest(payload.get("sequence", "")), "input_sha256": digest(payload),
            "evidence": None, "manual_review_required": True}
    try:
        sequence, mutations, mode, chain = _validate(payload)
        timeout = int(os.environ.get("DDGUN_TIMEOUT_SECONDS", "3600"))
        if not 1 <= timeout <= 14400:
            raise ValueError("DDGun timeout must be 1–14400 seconds")
        source = _safe_path(os.environ["DDGUN_SOURCE_DIR"])
        python = _safe_path(os.environ["DDGUN_PYTHON"])
        hhblits = _safe_path(os.environ["DDGUN_HHBLITS"])
        database = _safe_path(os.environ["DDGUN_DB_PREFIX"])
        version = os.environ["DDGUN_DATABASE_VERSION"].strip()
        if not version or version.lower() in ("latest", "unknown", "unspecified", "n/a") or len(version) > 200:
            raise ValueError("Explicit DDGun database version required")
        if version.startswith("validation_only:") and os.environ.get("DDGUN_ALLOW_VALIDATION_DATABASE") != "1":
            raise ValueError("Validation-only DDGun databases are disabled for production requests")
        manifest_file = Path(os.environ.get("DDGUN_SOURCE_MANIFEST", str(source / "SOURCE_MANIFEST.json")))
        manifest = json.loads(manifest_file.read_text())
        if manifest.get("algorithm_commit") != COMMIT:
            raise ValueError("Unsupported DDGun source commit")
        required = {"ddgun_seq.py", "ddgun_3d.py", "tools/ali2prof.py", "tools/hsspTools.py", "tools/pdbTools.py", "tools/dsspTools.py", "data/aaindex1.pkl", "data/aaindex2.pkl", "data/aaindex3.pkl"}
        if not required.issubset(manifest.get("files", {})):
            raise ValueError("Incomplete DDGun source integrity manifest")
        for relative in required:
            if hashlib.sha256((source / relative).read_bytes()).hexdigest() != manifest["files"][relative]:
                raise ValueError("DDGun source integrity check failed: " + relative)
        if mode == "3d":
            dssp_binary = "utils/dssp/dssp-2.0.4-linux-amd64"
            expected = manifest.get("files", {}).get(dssp_binary)
            if not expected or hashlib.sha256((source / dssp_binary).read_bytes()).hexdigest() != expected or not (source / "utils/dssp/dsspcmbi").samefile(source / dssp_binary):
                raise ValueError("DDGun bundled DSSP integrity check failed")
        if not python.is_file() or not hhblits.is_file():
            raise ValueError("DDGun Python/HHblits executable missing")
        if mode == "sequence":
            # Upstream sequence CLI validates -s but its pipeline's bound default
            # still uses utils/hh-suite/bin/hhblits. Pin both to the same binary.
            default_hhblits = source / "utils/hh-suite/bin/hhblits"
            if not default_hhblits.is_file() or not default_hhblits.samefile(hhblits):
                raise ValueError("DDGun sequence mode requires utils/hh-suite linked to the configured HHsuite installation")
        database_files = {}
        for suffix in ("_a3m.ffindex", "_a3m.ffdata", "_hhm.ffindex", "_hhm.ffdata", "_cs219.ffindex", "_cs219.ffdata"):
            if not Path(str(database) + suffix).is_file():
                raise ValueError("DDGun HHblits database incomplete: " + suffix)
            database_files[suffix] = Path(str(database) + suffix).stat().st_size
        workdir = _safe_path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        # Refuse reused directories: upstream automatically trusts cached profiles.
        if any(workdir.iterdir()):
            raise ValueError("DDGun requires a new empty run directory")
        control = sequence[0] + "1" + sequence[0]
        mutations_file = workdir / "mutations.txt"
        mutations_file.write_text("\n".join([*mutations, control]) + "\n")
        (workdir / "request.json").write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
        query = workdir / ("query.pdb" if mode == "3d" else "query.fasta")
        query.write_text(_first_model_pdb(payload["pdb_data"]) if mode == "3d" else ">query\n" + sequence + "\n")
        output = workdir / "predictions.tsv"
        command = [str(python), str(source / ("ddgun_3d.py" if mode == "3d" else "ddgun_seq.py")), str(query)]
        if mode == "3d":
            command.append(chain)
        command.extend([str(mutations_file), "-s", str(hhblits), "-d", str(database), "--outdir", str(workdir), "-o", str(output)])
        if hasattr(os, "sched_getaffinity"):
            taskset = shutil.which("taskset")
            if not taskset:
                raise ValueError("Linux DDGun requires taskset to enforce its two-CPU budget")
            affinity = ",".join(str(cpu) for cpu in sorted(os.sched_getaffinity(0))[:2])
            command = [taskset, "--cpu-list", affinity, *command]
        env = {**os.environ, "PATH": str(python.parent) + os.pathsep + os.environ.get("PATH", ""), "HHLIB": str(hhblits.parent.parent), "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1"}
        started = time.monotonic()
        with (workdir / "stdout.log").open("w") as stdout, (workdir / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise ValueError("DDGun exceeded execution timeout; raw logs retained")
        metadata = {"command": command, "returncode": returncode, "elapsed_seconds": round(time.monotonic() - started, 3), "algorithm_commit": COMMIT, "database_version": version}
        (workdir / "execution.json").write_text(json.dumps(metadata, indent=2))
        if returncode:
            raise ValueError("DDGun process failed (exit " + str(returncode) + "); raw logs retained")
        raw_output = output.read_text()
        results = _parse_output(raw_output, mode, [*mutations, control])
        if abs(results[control]) > 1e-8:
            raise ValueError("DDGun independently calculated WT control is nonzero")
        artifacts = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in workdir.iterdir() if file.is_file()}
        raw_result = {**metadata, "stdout": (workdir / "stdout.log").read_text(), "stderr": (workdir / "stderr.log").read_text(), "predictions_tsv": raw_output, "wild_type_identity_mutation": control, "source_manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(), "hhblits_binary_sha256": hashlib.sha256(hhblits.read_bytes()).hexdigest(), "database_component_bytes": database_files, "artifact_sha256": artifacts}
        result = {**base, "status": "completed", "model_version": "DDGun-2019-bcf112c", "algorithm_commit": COMMIT, "database_version": version, "mode": mode, "units": "kcal/mol", "sign_convention": SIGN, "wild_type": {"mutation": "WT", "ddg_kcal_mol": results[control]}, "predictions": [{"mutation": m, "ddg_kcal_mol": results[m]} for m in mutations], "evidence": {"raw_result": raw_result, "raw_result_sha256": digest(raw_result)}}
        (workdir / "response.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return result
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        return {**base, "blocked_reason": str(exc)}
