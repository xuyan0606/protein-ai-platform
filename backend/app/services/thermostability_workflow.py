"""Deterministic single-substitution review; no inferred experimental benefit."""
from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from itertools import product
from typing import Any

from app.services.candidate_decision import decide_candidate_output
from app.services.pdb_parser import _AA3TO1
from app.services.structure_records import pdb_records, is_protein_atom

AA = "ACDEFGHIKLMNPQRSTVWY"
MUTATION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]{0,3})([ACDEFGHIKLMNPQRSTVWY])$")
METALS = {"ZN", "CA", "MG", "MN", "FE", "CU", "CO", "NI", "CD"}


def _strict_integer(value: Any) -> int:
    """Accept exact integer coordinates; never truncate a float or accept bool."""
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        return int(value.strip())
    raise ValueError("Residue coordinates must be exact integers.")


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def assay_gaps(objective: dict) -> list[str]:
    gaps = []
    if objective.get('parsing_conflicts'):
        gaps.append('clarify_conflicting_assay_values')
    for key in ('baseline_residual_activity_pct', 'target_residual_activity_pct'):
        if key in objective and (_number(objective[key]) is None or not 0 <= _number(objective[key]) <= 100):
            gaps.append(key)
    endpoint = objective.get("endpoint")
    if not isinstance(endpoint, str) or endpoint not in {"tm", "half_life", "residual_activity"}:
        gaps.append("endpoint")
    retention = _number(objective.get("min_activity_retention_pct"))
    if retention is None or not 0 < retention <= 100:
        gaps.append("min_activity_retention_pct")
    ph = _number(objective.get("ph"))
    ph_range = objective.get('ph_range')
    valid_range = (isinstance(ph_range, list) and len(ph_range) == 2
                   and all(_number(v) is not None for v in ph_range)
                   and 0 <= _number(ph_range[0]) <= _number(ph_range[1]) <= 14)
    if (ph is None or not 0 <= ph <= 14) and not valid_range:
        gaps.append("ph")
    for key in ("method", "substrate", "buffer", "cofactors"):
        if str(objective.get(key) or "").strip().lower() in {'', '未知', '不清楚', '未测', 'unknown', '待定'}:
            gaps.append(key)
    if isinstance(endpoint, str) and endpoint in {"half_life", "residual_activity"}:
        temp = _number(objective.get("temperature_c"))
        if temp is None or not -20 <= temp <= 150:
            gaps.append("temperature_c")
    duration = _number(objective.get("duration_min"))
    if endpoint == "residual_activity" and (duration is None or duration <= 0):
        gaps.append("duration_min")
    return gaps


def _key(atom: dict) -> tuple:
    return atom["chain_id"], atom["residue_number"], atom.get("insertion_code") or None


def structure_context(sequence: str, pdb_data: str, chain_id: str,
                      mapping_rows: list[dict], source: str) -> tuple[dict, dict, dict, list[str]]:
    semantics = "plddt_not_flexibility" if source.lower() in {"alphafold", "alphafold2", "colabfold", "esmfold"} else "raw_not_interpreted"
    summary = {"source": source, "bfactor_semantics": semantics,
               "status": "not_available", "chain_id": chain_id,
               "limitations": ["Coordinates alone do not establish biological assembly or catalytic function."]}
    if not pdb_data:
        return summary, {}, {}, []
    if len(pdb_data.encode()) > 4_000_000:
        return summary, {}, {}, ["structure_size_limit_exceeded"]
    atoms, models, connections = pdb_records(pdb_data)
    if len(atoms) > 30000:
        return summary, {}, {}, ["structure_atom_limit_exceeded"]
    atoms = [a for a in atoms if a["model_id"] == models[0] and a["occupancy"] > 0 and a["altloc"] in {"", "A"}]
    residues = {}
    for a in atoms:
        if a["chain_id"] == chain_id and is_protein_atom(a, _AA3TO1):
            residues.setdefault(_key(a), _AA3TO1[a["component_id"]])
    if not residues:
        return summary, {}, {}, ["selected_structure_chain_missing"]
    mapping = {}
    if mapping_rows:
        for row in mapping_rows:
            try:
                pos = _strict_integer(row["source_position"])
                target = (row.get("target_chain_id") or chain_id, _strict_integer(row["target_position"]),
                          row.get("target_insertion_code") or None)
            except (KeyError, ValueError, TypeError):
                return summary, {}, {}, ["invalid_structure_mapping"]
            if (not isinstance(target[0], str) or (target[2] is not None and (not isinstance(target[2], str) or len(target[2]) > 1))):
                return summary, {}, {}, ["invalid_structure_mapping"]
            if (not 1 <= pos <= len(sequence) or pos in mapping or target in mapping.values()
                    or target[0] != chain_id or residues.get(target) != sequence[pos - 1]
                    or row.get("confidence") not in ("exact", "sifts", "curated", "high")
                    or row.get("user_confirmed") is not True
                    or row.get("source_scheme", "input_sequence") not in ("input_sequence", "user_sequence")
                    or row.get("gap_status", "present") not in ("present", "mapped")
                    or row.get("missing_in_structure") or row.get("has_gap")):
                return summary, {}, {}, ["invalid_structure_mapping"]
            mapping[pos] = target
    elif "".join(residues.values()) == sequence:
        mapping = dict(enumerate(residues, 1))
    else:
        return summary, {}, {}, ["structure_numbering_mapping_required"]
    reverse = {target: pos for pos, target in mapping.items()}
    risks: dict[int, set[str]] = {pos: set() for pos in mapping}
    if semantics == "plddt_not_flexibility":
        for atom in atoms:
            pos = reverse.get(_key(atom))
            if pos and atom["atom_name"] == "CA":
                confidence = _number(atom.get("b_factor"))
                if confidence is None or not 0 <= confidence <= 100:
                    risks[pos].add("structure_confidence_unknown")
                elif confidence < 70:
                    risks[pos].add("low_structure_confidence_requires_review")
    other = [a for a in atoms if a["chain_id"] != chain_id or not is_protein_atom(a, _AA3TO1)]
    cells = defaultdict(list)
    for neighbor in other:
        cells[tuple(math.floor(x / 5) for x in neighbor["coordinates"])].append(neighbor)
    checks = 0
    for atom in atoms:
        pos = reverse.get(_key(atom))
        if pos is None or atom["element"] == "H":
            continue
        cell = tuple(math.floor(x / 5) for x in atom["coordinates"])
        nearby = (neighbor for delta in product((-1, 0, 1), repeat=3)
                  for neighbor in cells.get(tuple(c+d for c, d in zip(cell, delta)), []))
        for neighbor in nearby:
            checks += 1
            if checks > 200000:
                return summary, {}, {}, ["structure_contact_complexity_limit_exceeded"]
            if neighbor["element"] == "H":
                continue
            distance = math.dist(atom["coordinates"], neighbor["coordinates"])
            component = neighbor["component_id"]
            if component in METALS and distance <= 3.0:
                risks[pos].add("metal_coordination_geometry")
            elif component not in {"HOH", "WAT", "DOD"} and not is_protein_atom(neighbor, _AA3TO1) and distance <= 4.0:
                risks[pos].add("ligand_contact")
            elif is_protein_atom(neighbor, _AA3TO1) and distance <= 5.0:
                risks[pos].add("cross_chain_contact_requires_assembly_review")
    for conn in connections:
        if conn.get("connection_type") == "disulf":
            for partner in (conn["partner_1"], conn["partner_2"]):
                pos = reverse.get(_key(partner))
                if pos:
                    risks[pos].add("existing_disulfide")
    sulfur = [a for a in atoms if a["component_id"] == "CYS" and a["atom_name"] == "SG"]
    if len(sulfur) > 500:
        return summary, {}, {}, ["structure_disulfide_complexity_limit_exceeded"]
    for i, first in enumerate(sulfur):
        for second in sulfur[i+1:]:
            if _key(first) != _key(second) and 1.8 <= math.dist(first["coordinates"], second["coordinates"]) <= 2.3:
                for a in (first, second):
                    if _key(a) in reverse:
                        risks[reverse[_key(a)]].add("existing_disulfide")
    summary.update(status="mapped", mapped_positions=len(mapping),
                   structure_sha256=hashlib.sha256(pdb_data.encode()).hexdigest(),
                   mapping_method="confirmed_explicit" if mapping_rows else "exact_selected_chain_sequence")
    return summary, mapping, risks, []


def build_screen(sequence: str, objective: dict | None = None,
                 identity_profile: dict | None = None, objective_module_plan: dict | None = None,
                 mutations: list[str] | None = None, candidate_sources: list[dict] | None = None,
                 candidate_positions: list[int] | None = None, pdb_data: str = "",
                 structure_source: str = "unknown", chain_id: str = "A",
                 mapping_rows: list[dict] | None = None, protected_sites: list[dict] | None = None,
                 assay_budget: int = 12, full_length_start: int | None = None,
                 analysis_mode: str = "strict", identity_reference_result: dict | None = None,
                 structure_features: dict | None = None) -> dict:
    """Return candidates as experimental hypotheses with explicit input coordinates."""
    sequence = "".join(sequence.split()).upper() if isinstance(sequence, str) else ""
    digest = hashlib.sha256(sequence.encode()).hexdigest()
    result = {"schema_version": "thermostability_candidates_v1", "status": "blocked",
              "sequence_sha256": digest, "coordinate_system": "input_sequence_1based",
              "candidates": [], "rejected": [], "source_issues": [], "blockers": [],
              "scientific_boundary": "Single-mutant hypotheses; no predicted score establishes measured thermal or activity improvement.",
              "manual_review_required": True, "evidence_level": "design_hypothesis"}
    if (not sequence or set(sequence) - set(AA) or len(sequence) > 4000
            or not isinstance(assay_budget, int) or isinstance(assay_budget, bool) or not 1 <= assay_budget <= 384
            or (full_length_start is not None and (not isinstance(full_length_start, int)
                or isinstance(full_length_start, bool) or full_length_start < 1))):
        result["blockers"] = ["invalid_sequence_or_budget_or_sample_boundary"]
        return result
    objects = [objective, identity_profile, objective_module_plan]
    lists = [mutations, candidate_sources, candidate_positions, mapping_rows, protected_sites]
    if (any(o is not None and not isinstance(o, dict) for o in objects)
            or any(v is not None and not isinstance(v, list) for v in lists)
            or not isinstance(pdb_data, str) or not isinstance(structure_source, str)
            or not isinstance(chain_id, str) or len(chain_id) != 1
            or any(not isinstance(s, dict) for s in (candidate_sources or []) + (mapping_rows or []) + (protected_sites or []))
            or len(candidate_sources or []) > 150 or len(mapping_rows or []) > 4000
            or len(protected_sites or []) > 4000 or len(mutations or []) > 500):
        result["blockers"] = ["invalid_or_oversized_evidence_inputs"]
        return result
    result["objective"] = objective or {}
    if isinstance(identity_reference_result, dict) and identity_reference_result.get('query', {}).get('sequence_sha256') == digest:
        result['identity_references'] = identity_reference_result.get('references', [])
    identity = identity_profile or {}
    result['foundation'] = {'identity_status': identity.get('identity_status') or 'unresolved',
        'guardrail_status': (identity.get('guardrail') or {}).get('status') or 'not_ready',
        'objective_module_status': (objective_module_plan or {}).get('status') or 'not_ready'}
    gaps = assay_gaps(objective or {})
    if analysis_mode == 'exploration':
        return _explore(result, sequence, identity, objective_module_plan or {}, mutations or [],
                        candidate_sources or [], pdb_data, chain_id, mapping_rows or [], structure_source,
                        protected_sites or [], gaps, structure_features)
    if gaps:
        result.update(status="needs_input", required_inputs=gaps)
        return result
    decision = decide_candidate_output(identity, objective_module_plan)
    result["candidate_decision"] = decision
    result["blockers"] = list(decision["blockers"])
    module = objective_module_plan or {}
    signals = module.get("objective_signals")
    if module.get("objective") != "thermostability" and (not isinstance(signals, list) or "thermostability" not in signals):
        result["blockers"].append("thermostability_objective_module_required")
    query = identity.get("query") if isinstance(identity.get("query"), dict) else {}
    if query.get("sequence_sha256") != digest:
        result["blockers"].append("identity_sequence_mismatch")
    if result["blockers"]:
        return result
    structure, mapping, risks, blockers = structure_context(sequence, pdb_data, chain_id, mapping_rows or [], structure_source)
    result["structure"] = structure
    if blockers:
        result["blockers"] = blockers
        return result
    sources = list(candidate_sources or [])
    if mutations:
        sources.append({"kind": "explicit", "reference": "user_supplied_substitutions", "sequence_sha256": digest, "mutations": mutations})
    if candidate_positions:
        try:
            positions = sorted(set(candidate_positions))
            if any(not isinstance(p, int) or isinstance(p, bool) or p < 1 or p > len(sequence) for p in positions):
                raise ValueError
        except (TypeError, ValueError):
            result["blockers"] = ["invalid_scan_positions"]
            return result
        if len(positions) * 19 > 500:
            result["blockers"] = ["scan_limit_exceeded_500_substitutions"]
            return result
        sources.append({"kind": "bounded_scan", "reference": "explicit_positions_all_19_alternatives",
                        "sequence_sha256": digest,
                        "mutations": [f"{sequence[p-1]}{p}{a}" for p in positions for a in AA if a != sequence[p-1]]})
    union: dict[str, list[dict]] = {}
    for source in sources:
        if not isinstance(source.get("mutations"), list) or len(source["mutations"]) > 500:
            result["blockers"] = ["invalid_or_oversized_source_mutations"]
            return result
        if source.get("sequence_sha256") != digest:
            result["source_issues"].append("source_sequence_mismatch")
            continue
        if not source.get("reference") or not source.get("kind"):
            result["source_issues"].append("source_provenance_required")
            continue
        for raw in source.get("mutations", []):
            code = str(raw).strip().upper()
            evidence = {"kind": source["kind"], "reference": source["reference"]}
            if code not in union:
                union[code] = []
            if evidence not in union[code]:
                union[code].append(evidence)
    if len(union) > 500:
        result["blockers"] = ["candidate_limit_exceeded_500_substitutions"]
        return result
    protected = identity.get("protected_positions", [])
    if not isinstance(protected, list) or any(not isinstance(p, int) or isinstance(p, bool) or not 1 <= p <= len(sequence) for p in protected):
        result["blockers"] = ["invalid_identity_protected_positions"]
        return result
    hard = {p: {"identity_protected"} for p in protected}
    for item in protected_sites or []:
        try:
            pos = _strict_integer(item["position"])
        except (KeyError, TypeError, ValueError):
            result["blockers"] = ["invalid_functional_protection"]
            return result
        if not 1 <= pos <= len(sequence) or not item.get("reference"):
            result["blockers"] = ["invalid_functional_protection"]
            return result
        kind = str(item.get("kind") or "functional_review")
        if kind in {"catalytic", "essential_metal", "existing_disulfide", "essential_function"}:
            hard.setdefault(pos, set()).add(kind)
        else:
            risks.setdefault(pos, set()).add(kind)
    for pos, flags in risks.items():
        protected = flags & {"metal_coordination_geometry", "existing_disulfide"}
        if protected:
            hard.setdefault(pos, set()).update(protected)
    rows = []
    for code, evidence in union.items():
        match = MUTATION.fullmatch(code)
        if not match:
            result["rejected"].append({"mutation": code, "reasons": ["invalid_substitution"]})
            continue
        wt, raw_pos, mt = match.groups()
        pos = int(raw_pos)
        reasons = []
        if pos > len(sequence) or sequence[pos-1] != wt or wt == mt:
            reasons.append("wt_or_position_mismatch")
        reasons.extend(sorted(hard.get(pos, set())))
        if pdb_data and pos not in mapping:
            reasons.append("candidate_not_mapped_to_structure")
        if reasons:
            result["rejected"].append({"mutation": code, "reasons": reasons, "sources": evidence})
            continue
        target = mapping.get(pos)
        flags = set(risks.get(pos, set()))
        if any(s["kind"] == "local_experimental_dtm" for s in evidence):
            flags.add("reported_assay_transfer_requires_review")
        rows.append({"mutation": code, "position": pos, "wild_type": wt, "mutant": mt,
                     "full_length_position": pos + full_length_start - 1 if full_length_start is not None else None,
                     "structure_position": {"chain_id": target[0], "residue_number": target[1], "insertion_code": target[2]} if target else None,
                     "sources": evidence, "risks": sorted(flags),
                     "scores": {"ddgun": None, "esm_preference": None},
                     "missing_evidence": ["experimental_thermal_and_activity_measurements", "complete_functional_protection_review"],
                     "manual_review_required": True, "evidence_level": "design_hypothesis"})
    rows.sort(key=lambda r: (r["position"], r["mutant"]))
    result.update(status="ready_for_review" if rows else "no_candidates", candidates=rows,
                  candidate_counts={"generated": len(union), "eligible": len(rows), "rejected": len(result["rejected"])},
                  sample_boundary={"full_length_start": full_length_start, "input_length": len(sequence)},
                  experimental_plan={"controls": ["WT"], "single_mutants": [r["mutation"] for r in rows[:assay_budget]],
                                     "selection_policy": "deterministic_position_order_pending_evidence_review",
                                     "replicates": "predefine from assay variability; use matched WT conditions",
                                     "objective": objective, "combination_design": "after_single_mutant_feedback"})
    if not union:
        result["required_inputs"] = ["explicit_substitutions_or_candidate_sources_or_bounded_positions"]
    return result


def _explore(result: dict, sequence: str, identity: dict, module: dict, mutations: list,
             sources: list, pdb_data: str, chain_id: str, mapping_rows: list,
             structure_source: str, protected_sites: list, gaps: list, structure_features: dict | None = None) -> dict:
    """Unknowns permit analysis; invalid provenance and coordinates remain errors."""
    digest = result['sequence_sha256']
    query = identity.get('query') if isinstance(identity.get('query'), dict) else {}
    if query.get('sequence_sha256') and query['sequence_sha256'] != digest:
        result.update(status='blocked', blockers=['identity_sequence_mismatch'])
        return result
    structure, mapping, risks, invalid = structure_context(sequence, pdb_data, chain_id, mapping_rows, structure_source)
    if invalid:
        result.update(status='blocked', structure=structure, blockers=invalid)
        return result
    positions = identity.get('protected_positions', [])
    if not isinstance(positions, list) or any(type(p) is not int or not 1 <= p <= len(sequence) for p in positions):
        result['blockers'] = ['invalid_identity_protected_positions']
        return result
    protected = set(positions)
    for site in protected_sites:
        try:
            pos = _strict_integer(site.get('position'))
        except ValueError:
            result['blockers'] = ['invalid_functional_protection']
            return result
        if not 1 <= pos <= len(sequence) or not site.get('reference'):
            result['blockers'] = ['invalid_functional_protection']
            return result
        if site.get('kind') in {'catalytic', 'essential_metal', 'existing_disulfide', 'essential_function'}:
            protected.add(pos)
    protected.update(p for p, flags in risks.items() if flags & {'metal_coordination_geometry', 'existing_disulfide'})
    # Also avoid the spatial neighborhood of known protected functional sites.
    if structure_features:
        coords = {r.get('pdb_residue_no'): r.get('ca_coord') for r in structure_features.get('features', [])
                  if isinstance(r, dict) and r.get('chain_id') == chain_id}
        for pos, key in mapping.items():
            current = coords.get(key[1])
            if not isinstance(current, dict):
                continue
            for p in list(protected):
                other = coords.get(mapping.get(p, (None, None, None))[1])
                if isinstance(other, dict) and all(k in current and k in other for k in ('x', 'y', 'z')):
                    if math.dist([current[k] for k in ('x', 'y', 'z')], [other[k] for k in ('x', 'y', 'z')]) <= 8:
                        risks[pos].add('near_known_functional_site')
                        break
    from app.services.thermal_structure_hypotheses import packing_probes
    probe_audit = {}
    generated = packing_probes(sequence, pdb_data, mapping, risks, protected, structure_features,
                               audit=probe_audit) if pdb_data else []
    if probe_audit:
        result['probe_generation_audit'] = probe_audit
    generated_by_code = {r['mutation']: r for r in generated}
    codes = list(mutations)
    for source in sources:
        if not isinstance(source.get('mutations'), list) or len(source['mutations']) > 500:
            result['blockers'] = ['invalid_or_oversized_source_mutations']
            return result
        if source.get('sequence_sha256') != digest:
            result['source_issues'].append('source_sequence_mismatch')
        elif source.get('reference') and source.get('kind'):
            codes.extend(source['mutations'])
    codes.extend(generated_by_code)
    if len(codes) > 500:
        result['blockers'] = ['candidate_limit_exceeded_500_substitutions']
        return result
    preliminary = []
    for code in dict.fromkeys(str(x).strip().upper() for x in codes):
        match = MUTATION.fullmatch(code)
        reason = None
        if not match:
            reason = 'invalid_substitution'
        else:
            wt, raw, mt = match.groups()
            pos = int(raw)
            if pos > len(sequence) or sequence[pos-1] != wt or wt == mt:
                reason = 'wt_or_position_mismatch'
            elif pos in protected:
                reason = 'known_functional_protection'
            elif pdb_data and pos not in mapping:
                reason = 'candidate_not_mapped_to_structure'
        if reason:
            result['rejected'].append({'mutation': code, 'reasons': [reason]})
        else:
            coordinate = mapping.get(pos)
            preliminary.append({'mutation': code, 'position': pos, 'wild_type': wt, 'mutant': mt,
                                'structure_position': ({'chain_id': coordinate[0], 'residue_number': coordinate[1],
                                                        'insertion_code': coordinate[2]} if coordinate else None),
                                'sources': generated_by_code.get(code, {}).get('sources') or [
                                    {'kind': 'explicit_unscored_hypothesis', 'reference': 'provided_substitution', 'sequence_sha256': digest}],
                                'rationale': generated_by_code.get(code, {}).get('rationale', '输入替换；尚需工具独立评分与功能复核。'),
                                'scores': {'ddgun': None, 'esm_preference': None}, 'missing_evidence': [],
                                'manual_review_required': True,
                                'evidence_level': 'unverified_design_hypothesis',
                                'risks': sorted(risks.get(pos, set()) | {'incomplete_functional_protection', 'unverified_thermal_and_activity_effect'})})
    result.update(status='partial', analysis_mode='exploration', evidence_level='research_only_exploration',
                  candidate_output_allowed=False, structure=structure, preliminary_candidates=preliminary,
                  candidates=[], experimental_plan={},
                  evidence_gaps=list(dict.fromkeys(gaps + list(module.get('missing_evidence', [])))),
                  analysis_directions=[
                      '继续核对序列家族和参考酶；同源检索等待不妨碍已完成的局部分析。',
                      '优先复核表面电荷网络、环区刚性、疏水堆积及二硫键几何；仅提出与当前证据相符的改造方向。',
                      '避开已知催化位点、金属配位及已有二硫键；未确认区域保留功能风险。',
                      '实验条件未知时先规划WT对照和热处理梯度；获得实测反馈后再确定成功阈值。'],
                  scientific_boundary='探索结果不证明热稳定性或活性改善；未知条件不会被默认值填充，初步突变不等于可直接执行的实验集合。')
    return result
