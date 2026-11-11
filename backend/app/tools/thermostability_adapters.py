"""Fail-closed adapters for separately deployed, versioned scientific services.

These clients run no local surrogate and never convert ΔΔG into Tm/activity.
See docs/manuals/thermostability-adapters.md for the exact wire protocol.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.tools.registry import ToolRegistry
from app.services.thermostability_limits import service_timeout, tool_timeout

_AMINO = set("ACDEFGHIKLMNPQRSTVWY")
_MUTATION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]{0,4})([ACDEFGHIKLMNPQRSTVWY])$")
_MAX_SEQUENCE = 4000
_MAX_TEXT = 8_000_000
_MAX_RESPONSE = 16_000_000
_DIRECTION = "positive=increased unfolding stability"
_RESIDUES = dict(zip(
    "ALA CYS ASP GLU PHE GLY HIS ILE LYS LEU MET ASN PRO GLN ARG SER THR VAL TRP TYR".split(),
    "ACDEFGHIKLMNPQRSTVWY",
))


def _hash(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sequence(value: str) -> str:
    if not isinstance(value, str) or len(value) > _MAX_TEXT:
        raise ValueError("Sequence must be a bounded amino acid string.")
    value = "".join(value.split()).upper()
    if not 1 <= len(value) <= _MAX_SEQUENCE or set(value) - _AMINO:
        raise ValueError(f"Sequence requires 1–{_MAX_SEQUENCE} canonical amino acids.")
    return value


def _number(value: Any, lower: float | None = None, upper: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite numeric result.")
    if (lower is not None and value < lower) or (upper is not None and value > upper):
        raise ValueError("Numeric result is outside the protocol bounds.")
    return float(value)


def _pdb(value: str, sequence: str, chain: str) -> list[float | None]:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > _MAX_TEXT:
        raise ValueError("A bounded PDB structure is required.")
    if not isinstance(chain, str) or not re.fullmatch(r"[A-Za-z0-9]", chain):
        raise ValueError("chain_id must be one alphanumeric PDB chain identifier.")
    residues: dict[tuple[str, str], str] = {}
    confidence: dict[tuple[str, str], float | None] = {}
    model_count = 0
    for line in value.splitlines():
        if line.startswith("MODEL"):
            model_count += 1
            if model_count > 1:
                break
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  ") or len(line) < 54 or line[21] != chain:
            continue
        if line[12:16].strip() != "CA" or line[16] not in (" ", "A"):
            continue
        aa = _RESIDUES.get(line[17:20])
        if aa is None:
            raise ValueError("PDB chain contains an unsupported residue.")
        try:
            for coordinate in (line[30:38], line[38:46], line[46:54]):
                _number(float(coordinate))
        except (ValueError, TypeError) as exc:
            raise ValueError("PDB has invalid CA coordinates.") from exc
        key = (line[22:26], line[26])
        if key not in residues and (line[26] != " " or line[22:26].strip() != str(len(residues) + 1)):
            raise ValueError("blocked_numbering_mapping_required: selected PDB chain must have contiguous author numbering 1..L without insertions; remap externally first.")
        if key in residues and residues[key] != aa:
            raise ValueError("PDB contains ambiguous residue identities.")
        residues[key] = aa
        try:
            confidence[key] = _number(float(line[60:66]))
        except (ValueError, TypeError):
            confidence[key] = None
    if "".join(residues.values()) != sequence:
        raise ValueError("PDB selected-chain CA sequence must match the complete input sequence; remap externally first.")
    return list(confidence.values())


def _alignment(value: str, sequence: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > _MAX_TEXT:
        raise ValueError("A bounded local FASTA/A3M alignment is required.")
    rows: list[str] = []
    current: list[str] = []
    seen_header = False
    for line in value.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">"):
            seen_header = True
            if current:
                rows.append("".join(current))
                current = []
        else:
            if not seen_header:
                raise ValueError("Alignment must use FASTA/A3M headers.")
            current.append("".join(char for char in line if not char.islower()).replace(".", ""))
    if current:
        rows.append("".join(current))
    if not rows or rows[0].replace("-", "") != sequence or len(rows[0]) != len(sequence):
        raise ValueError("Alignment first row must match the complete ungapped input sequence.")
    if any(len(row) != len(sequence) or set(row) - (_AMINO | {"-"}) for row in rows):
        raise ValueError("Alignment rows must have consistent canonical columns.")


def _base(model: str, sequence: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "blocked", "model": model, "model_version": None,
        "algorithm_commit": None, "database_version": None,
        "sequence_sha256": _hash(sequence), "input_sha256": _hash(payload) if payload else None,
        "predictions": [], "evidence": None, "manual_review_required": True,
    }


def _blocked(result: dict[str, Any], reason: str) -> dict[str, Any]:
    return {**result, "status": "blocked", "blocked_reason": reason}


async def _request(prefix: str, endpoint: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], str]:
    url = os.getenv(f"{prefix}_SERVICE_URL", "").strip().rstrip("/")
    if not url:
        raise ValueError(f"{prefix}_SERVICE_URL is not configured.")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{prefix}_SERVICE_URL must be an HTTP(S) service base URL without credentials/query/fragment.")
    token = os.getenv(f"{prefix}_SERVICE_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    timeout = service_timeout(prefix, timeout)
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10., pool=10.), follow_redirects=False, trust_env=False) as client:
        async with client.stream("POST", f"{url}{endpoint}", json=payload, headers=headers) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > _MAX_RESPONSE:
                    raise ValueError("Model service response exceeds 16 MB.")
    raw = bytes(chunks)
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Model service response must be a JSON object.")
    return result, hashlib.sha256(raw).hexdigest()


def _envelope(result: dict[str, Any], model: str, payload: dict[str, Any], raw_hash: str) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("status") != "completed" or result.get("model") != model:
        raise ValueError("Service must confirm completed status and the requested model identity.")
    for field in ("model_version", "database_version"):
        value = result.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 200 or value.strip().lower() in {"unknown", "unspecified", "latest", "n/a"}:
            raise ValueError(f"Service must report an explicit {field} (use 'not_used:<reason>' where applicable).")
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", str(result.get("algorithm_commit", ""))):
        raise ValueError("Service algorithm_commit must identify the pinned source commit.")
    if result.get("sequence_sha256") != _hash(payload["sequence"]) or result.get("input_sha256") != _hash(payload):
        raise ValueError("Service input sequence/request hash does not match this request.")
    evidence = result.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("raw_result") in (None, "", {}, []):
        raise ValueError("Service must retain nonempty raw result evidence.")
    if evidence.get("raw_result_sha256") != _hash(evidence["raw_result"]):
        raise ValueError("Raw model result evidence hash mismatch.")
    return {
        **_base(model, payload["sequence"], payload), "status": "completed",
        "model_version": result["model_version"], "algorithm_commit": result["algorithm_commit"],
        "database_version": result["database_version"], "evidence_level": "model_inference",
        "evidence": {"raw_result": evidence["raw_result"], "raw_result_sha256": evidence["raw_result_sha256"],
                     "raw_http_response_sha256": raw_hash},
    }


async def ddgun_predict(sequence: str, mutations: list[str], pdb_data: str = "", chain_id: str = "A") -> dict[str, Any]:
    """Run DDGun sequence/3D ΔΔG inference; fail closed on incomplete evidence."""
    base = _base("DDGun", "")
    try:
        sequence = _sequence(sequence)
        base = _base("DDGun", sequence)
        if not isinstance(mutations, list) or not 1 <= len(mutations) <= 500 or any(not isinstance(m, str) or len(m) > 16 for m in mutations):
            raise ValueError("Supply 1–500 distinct single mutations.")
        candidates = [m.strip().upper() for m in mutations]
        if len(set(candidates)) != len(candidates):
            raise ValueError("Duplicate mutation candidates are not allowed.")
        for mutation in candidates:
            match = _MUTATION.fullmatch(mutation)
            if not match or int(match[2]) > len(sequence) or sequence[int(match[2]) - 1] != match[1] or match[1] == match[3]:
                raise ValueError(f"Mutation {mutation[:40]} must change a matching WT residue at a 1-based sequence position.")
        if not isinstance(pdb_data, str) or len(pdb_data.encode()) > _MAX_TEXT:
            raise ValueError("pdb_data must be a PDB string of at most 8 MB.")
        if not isinstance(chain_id, str) or not re.fullmatch(r"[A-Za-z0-9]", chain_id):
            raise ValueError("chain_id must be one alphanumeric PDB chain identifier.")
        if pdb_data.strip():
            _pdb(pdb_data, sequence, chain_id)
        payload = {"sequence": sequence, "mutations": candidates, "pdb_data": pdb_data,
                   "chain_id": chain_id, "mode": "3d" if pdb_data.strip() else "sequence"}
        base = _base("DDGun", sequence, payload)
        response, raw_hash = await _request("DDGUN", "/predict", payload, 180.)
        base["rejected_response_sha256"] = raw_hash
        returned = response.get('predictions')
        if isinstance(returned,list):
            # Diagnostics remain separate from validated predictions, even if
            # units, provenance or completeness checks below reject the reply.
            base['raw_predictions'] = [{k:(str(v) if isinstance(v,float) and not math.isfinite(v) else v)
                for k,v in r.items() if k in {'mutation','ddg_kcal_mol'} and isinstance(v,(str,int,float,bool))}
                for r in returned[:500] if isinstance(r,dict)]
            base['raw_predictions_validation_status'] = 'unverified_do_not_rank'
            base['raw_predictions_truncated'] = len(returned)>500
            base['candidate_coverage'] = {'requested':len(candidates),'returned':len(returned),'complete':False}
        verified = _envelope(response, "DDGun", payload, raw_hash)
        if response.get("units") != "kcal/mol" or response.get("sign_convention") != _DIRECTION or response.get("mode") != payload["mode"]:
            raise ValueError("DDGun requires raw kcal/mol, requested mode, and positive=increased unfolding stability.")
        control = response.get("wild_type")
        if not isinstance(control, dict) or control.get("mutation") != "WT" or abs(_number(control.get("ddg_kcal_mol"))) > 1e-8:
            raise ValueError("DDGun requires a zero WT ΔΔG control.")
        predictions = response.get("predictions")
        if not isinstance(predictions, list) or len(predictions) != len(candidates):
            raise ValueError("DDGun must return every requested candidate exactly once.")
        by_mutation = {}
        for item in predictions:
            if not isinstance(item, dict) or item.get("mutation") not in candidates or item["mutation"] in by_mutation:
                raise ValueError("DDGun returned duplicate or unrequested mutations.")
            ddg = _number(item.get("ddg_kcal_mol"))
            by_mutation[item["mutation"]] = {"mutation": item["mutation"], "ddg_kcal_mol": ddg,
                                             "ddg": ddg, "unit": "kcal/mol", "direction": _DIRECTION}
        return {**verified, "mode": payload["mode"], "units": "kcal/mol", "sign_convention": _DIRECTION,
                "wild_type": {"mutation": "WT", "ddg_kcal_mol": 0.0},
                "predictions": [by_mutation[m] for m in candidates],
                "candidate_coverage": {"requested": len(candidates), "returned": len(predictions), "complete": True},
                "scientific_boundary": "DDGun estimates mutation unfolding stability ΔΔG; no Tm, catalytic activity, or experimental-success inference."}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        return _blocked(base, str(exc))
    except httpx.HTTPError as exc:
        return _blocked(base, f"DDGun service unavailable: {type(exc).__name__}.")


async def colabfold_predict(sequence: str, msa_policy: str = "local") -> dict[str, Any]:
    """Predict structure only after upstream structure retrieval is unsuitable.

    The caller owns that retrieval gate. Local MSA is the default and sends an
    explicit no-public-search instruction to the configured folding service.
    """
    base = _base("ColabFold", "")
    try:
        sequence = _sequence(sequence)
        base = _base("ColabFold", sequence)
        if msa_policy not in ("local", "public"):
            raise ValueError("msa_policy must be local or explicitly authorized public.")
        alignment = ""
        service_local_search = False
        if msa_policy == "local":
            path = os.getenv("COLABFOLD_LOCAL_MSA_PATH", "").strip()
            service_local_search = not path and os.getenv('COLABFOLD_MSA_SOURCE') == 'service_local_search'
            if not path and not service_local_search:
                raise ValueError("COLABFOLD_LOCAL_MSA_PATH is required for local MSA; public search is disabled.")
            if not service_local_search:
                try:
                    with Path(path).open("rb") as handle:
                        raw = handle.read(_MAX_TEXT + 1)
                    if len(raw) > _MAX_TEXT:
                        raise ValueError("Local alignment exceeds 8 MB.")
                    alignment = raw.decode("utf-8")
                except (OSError, UnicodeError) as exc:
                    raise ValueError("Configured local MSA could not be read.") from exc
                _alignment(alignment, sequence)
        elif os.getenv("COLABFOLD_ALLOW_PUBLIC_MSA", "").lower() != "true":
            raise ValueError("Public MSA requires operator authorization COLABFOLD_ALLOW_PUBLIC_MSA=true.")
        payload = {"sequence": sequence, "msa_policy": msa_policy, "alignment": alignment,
                   "allow_public_msa": msa_policy == "public"}
        if service_local_search:
            payload['msa_source'] = 'service_local_search'
        base = _base("ColabFold", sequence, payload)
        response, raw_hash = await _request("COLABFOLD", "/predict", payload, 300.)
        base["rejected_response_sha256"] = raw_hash
        verified = _envelope(response, "ColabFold", payload, raw_hash)
        if response.get("msa_policy") != msa_policy:
            raise ValueError("ColabFold service must confirm the requested MSA policy.")
        if service_local_search and (response.get('msa_source') != 'service_local_search'
                or type(response.get('msa_depth')) is not int or response['msa_depth'] < 1
                or not re.fullmatch('[0-9a-f]{64}', str(response.get('msa_sha256') or ''))):
            raise ValueError('ColabFold must retain the actual local MSA search provenance.')
        chain_id = response.get("chain_id")
        pdb_confidence = _pdb(response.get("pdb_data"), sequence, chain_id)
        confidence = response.get("plddt")
        if not isinstance(confidence, list) or len(confidence) != len(sequence):
            raise ValueError("ColabFold requires one pLDDT value per input residue.")
        confidence = [_number(value, 0., 100.) for value in confidence]
        if any(abs(_number(bfactor, 0., 100.) - plddt) > .020000001
               for bfactor, plddt in zip(pdb_confidence, confidence)):
            raise ValueError("ColabFold pLDDT disagrees with selected-chain PDB CA B factors (tolerance 0.02).")
        return {**verified, "pdb_data": response["pdb_data"], "chain_id": chain_id,
                **{key: response[key] for key in ('msa_source', 'msa_depth', 'msa_sha256', 'msa_database') if key in response},
                "plddt": confidence, "mean_plddt": sum(confidence) / len(confidence), "msa_policy": msa_policy,
                "sequence_coverage": 1.0,
                "scientific_boundary": "Predicted structure and confidence support review; pLDDT is not thermostability or catalytic activity."}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        return _blocked(base, str(exc))
    except httpx.HTTPError as exc:
        return _blocked(base, f"ColabFold service unavailable: {type(exc).__name__}.")


async def evcouplings_analyze(sequence: str, msa_quality: dict[str, Any], alignment: str = "") -> dict[str, Any]:
    """Return optional evolutionary coupling evidence; insufficient MSA skips."""
    base = {**_base("EVcouplings", ""), "couplings": []}
    try:
        sequence = _sequence(sequence)
        base = {**_base("EVcouplings", sequence), "couplings": []}
        if not isinstance(msa_quality, dict):
            return {**base, "status": "skipped", "skipped_reason": "MSA quality is missing; optional couplings were not run."}
        if not isinstance(alignment, str) or len(alignment.encode()) > _MAX_TEXT:
            raise ValueError("Alignment must be a string of at most 8 MB.")
        try:
            neff = _number(msa_quality.get("neff"), 0.)
            coverage = _number(msa_quality.get("coverage"), 0., 1.)
            count = _number(msa_quality.get("sequence_count"), 0.)
            if not count.is_integer() or neff > count:
                raise ValueError("Invalid MSA sequence count/neff.")
        except ValueError:
            return {**base, "status": "skipped", "skipped_reason": "MSA quality is missing or invalid; optional couplings were not run."}
        quality = {"neff": neff, "coverage": coverage, "sequence_count": int(count)}
        base["input_sha256"] = _hash({"sequence": sequence, "msa_quality": quality, "alignment": alignment})
        if neff < max(50., .5 * len(sequence)) or coverage < .8 or count < 50:
            return {**base, "status": "skipped", "skipped_reason": "MSA requires neff >= max(50, sequence_length/2), coverage >= 0.8 and sequence_count >= 50."}
        _alignment(alignment, sequence)
        payload = {"sequence": sequence, "msa_quality": quality, "alignment": alignment}
        base["input_sha256"] = _hash(payload)
        response, raw_hash = await _request("EVCOUPLINGS", "/couplings", payload, 180.)
        base["rejected_response_sha256"] = raw_hash
        verified = _envelope(response, "EVcouplings", payload, raw_hash)
        rows = response.get("couplings")
        if not isinstance(rows, list) or not rows or len(rows) > 50_000:
            raise ValueError("EVcouplings must return 1–50000 residue pairs.")
        pairs = set()
        couplings = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("EVcouplings pair must be an object.")
            i, j = row.get("position_i"), row.get("position_j")
            if type(i) is not int or type(j) is not int or not 1 <= i < j <= len(sequence) or (i, j) in pairs:
                raise ValueError("EVcouplings pair positions must be unique ordered 1-based sequence indices.")
            pairs.add((i, j))
            couplings.append({"position_i": i, "position_j": j, "score": _number(row.get("score"))})
        return {**verified, "couplings": couplings, "msa_quality": quality,
                "scientific_boundary": "Evolutionary couplings are optional sequence association evidence, not mutation ΔΔG, Tm, or activity predictions."}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        return _blocked(base, str(exc))
    except httpx.HTTPError as exc:
        return _blocked(base, f"EVcouplings service unavailable: {type(exc).__name__}.")


for _name, _handler, _description, _properties, _required, _timeout in (
    ("ddgun_predict", ddgun_predict, "Run real DDGun sequence/3D mutation unfolding ΔΔG through a versioned service.",
     {"sequence": {"type": "string"}, "mutations": {"type": "array", "items": {"type": "string"}},
      "pdb_data": {"type": "string", "default": ""}, "chain_id": {"type": "string", "default": "A"}}, ["sequence", "mutations"], 210),
    ("colabfold_predict", colabfold_predict, "Use configured ColabFold only when no suitable retrieved structure exists; requires explicit MSA policy.",
     {"sequence": {"type": "string"}, "msa_policy": {"type": "string", "enum": ["local", "public"], "default": "local"}}, ["sequence"], 330),
    ("evcouplings_analyze", evcouplings_analyze, "Optional real EVcouplings evidence; insufficient MSA skips without blocking the main analysis.",
     {"sequence": {"type": "string"}, "msa_quality": {"type": "object"}, "alignment": {"type": "string", "default": ""}}, ["sequence", "msa_quality"], 210),
):
    ToolRegistry.register(name=_name, handler=_handler, description=_description,
                          parameters={"type": "object", "properties": _properties, "required": _required},
                          is_async=True, category="stability", timeout_seconds=tool_timeout(_name, _timeout))
