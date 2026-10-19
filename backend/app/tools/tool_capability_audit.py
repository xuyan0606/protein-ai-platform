"""Runtime/capability audit for tool outputs.

This is a product-safety layer: it prevents tool names from being interpreted as
proof that official model weights, databases, or command-line runtimes ran.
"""

from __future__ import annotations

from typing import Any

from app.tools.registry import ToolRegistry


_CAPABILITIES: dict[str, dict[str, Any]] = {
    "kwb_enzyme_designer": {
        "capability_status": "production_gate_boundary",
        "license_class": "local_only",
        "commercial_use_status": "pending_model_release",
        "boundary": "Production inference is unavailable until audited data, model, evaluation, release, and deployment gates pass; blocked responses never substitute proxy scores.",
        "minimum_artifacts": ["production gate report", "validated model package", "inference receipt", "prediction evidence manifest"],
    },
    "structure_search_foldseek": {
        "capability_status": "structure_similarity_search",
        "license_class": "open_local",
        "commercial_use_status": "verify_database_terms",
        "boundary": "Foldseek/structure hits support structural similarity only; weak TM-score or template annotations do not confirm the input enzyme identity.",
        "minimum_artifacts": ["query structure summary", "hit table", "TM-score/alignment coverage", "template provenance"],
    },
    "residue_mapping_sifts": {
        "capability_status": "numbering_evidence_gated",
        "boundary": "Coordinate-order inference is not external SIFTS/UniProt mapping; mutation ordering requires chain, missing-residue, mature-chain, and source checks.",
        "minimum_artifacts": ["mapping source", "chain", "PDB residue", "sequence/UniProt position", "mapping confidence"],
    },
    "predict_properties": {
        "capability_status": "background_baseline",
        "boundary": "Sequence-derived physicochemical values are background only and do not prove thermostability, specific activity, identity, or mutation gain.",
        "minimum_artifacts": ["input sequence provenance", "calculation method", "assay measurements for target claims"],
    },
    "annotation_bundle": {
        "capability_status": "evidence_synthesis",
        "boundary": "Aggregates curated/local annotations and conservative predictions; not a live BLAST/InterProScan substitute.",
        "minimum_artifacts": ["record provenance", "coordinate status", "source versions when available"],
    },
    "enzyme_identity_profile": {
        "capability_status": "evidence_synthesis",
        "boundary": "Foundation profile and guardrail; short motifs are clues, not family proof.",
        "minimum_artifacts": ["family candidates", "key residues", "numbering status", "evidence table"],
    },
    "catalytic_site_lookup": {
        "capability_status": "curated_or_motif_guardrail",
        "boundary": "Curated UniProt/M-CSA/local catalytic-site records may define protected residues after numbering verification; motif-only inference is a risk guardrail, not confirmed catalysis.",
        "minimum_artifacts": ["source provenance", "coordinate system", "mapped positions", "curated-versus-inferred status"],
    },
    "build_site_structure_function_features": {
        "capability_status": "residue_geometry_feature_table",
        "boundary": "Returns auditable PDB residue geometry, exposure, contacts, torsions, and ligand proximity; it does not identify enzyme function or prove mutation gain.",
        "minimum_artifacts": ["PDB/model provenance", "chain", "residue numbering", "CA features", "mapping confidence", "nonpolymer proximity"],
    },
    "pocket_residue_lookup": {
        "capability_status": "real_runtime_gated",
        "license_class": "open_local",
        "commercial_use_status": "verify_backend_and_database_terms",
        "boundary": "Only residues parsed from a completed P2Rank/fpocket run are geometric pocket evidence; missing executables or failed runs remain blocked.",
        "minimum_artifacts": ["engine/version", "input structure hash", "raw output artifact", "parsed pocket residue coordinates"],
    },
    "protein_benchmark": {
        "capability_status": "foundation_dependent_explainer",
        "boundary": "Explains confirmed families only after enzyme_identity_profile guardrail is ready.",
        "minimum_artifacts": ["identity_profile reference", "foundation_gate"],
    },
    "enzyme_function": {
        "capability_status": "foundation_or_proxy_prediction",
        "boundary": "Identity-profile-derived classification may support background interpretation; motif/embedding fallback is a design hypothesis, not a confirmed EC.",
        "minimum_artifacts": ["identity profile or proxy label", "prediction source", "confidence/limitations"],
    },
    "enzyme_objective_module_plan": {
        "capability_status": "objective_gate",
        "boundary": "Defines objective-specific evidence and validation requirements; it does not prove that a mutation improves the objective.",
        "minimum_artifacts": ["objective modules", "assay context", "missing evidence", "candidate output decision"],
    },
    "blast_search": {
        "capability_status": "external_service_or_cache",
        "license_class": "external_service_only",
        "commercial_use_status": "service_terms_and_rate_limits_apply",
        "boundary": "Only a completed live query or traceable cache result supports homolog evidence; submitted or degraded status must not enter conclusions.",
        "minimum_artifacts": ["query provenance", "database/program", "terminal status", "hit identity/coverage/e-value", "evidence source"],
    },
    "mutation_priority_score": {
        "capability_status": "proxy_ranker",
        "boundary": "Rule/model-assisted candidate ranking; not wet-lab evidence and not a Rosetta/ddG/pKa calculation.",
        "minimum_artifacts": ["identity_gate", "protected positions", "ranking rationale"],
    },
    "mutation_scan": {
        "capability_status": "proxy",
        "boundary": "Broad substitution scan for physicochemical risk triage; not a candidate table without identity, numbering, protected-site, and objective gates.",
        "minimum_artifacts": ["sequence provenance", "positions scanned", "candidate gate status", "scoring method"],
    },
    "kcat_predict": {
        "capability_status": "proxy",
        "boundary": "Heuristic/statistical estimate; must not be presented as calibrated quantitative kcat without model card and validation artifacts.",
        "minimum_artifacts": ["model card or proxy label", "training/validation scope", "input hash"],
    },
    "protssn_score": {
        "capability_status": "proxy",
        "boundary": "Sequence/structure-neighborhood scoring proxy unless real model/runtime artifact is attached.",
        "minimum_artifacts": ["runtime type", "model version", "score provenance"],
    },
    "alphafold2_folding": {
        "capability_status": "proxy",
        "boundary": "Current local entry is not official AlphaFold2 inference unless MSA, weights, logs, and structure artifacts are present.",
        "minimum_artifacts": ["model version", "MSA/template provenance", "PDB/mmCIF", "PAE/pLDDT", "logs"],
    },
    "alphafold_folding": {
        "capability_status": "proxy_or_external_lookup",
        "boundary": "Must distinguish AlphaFold DB lookup from true folding inference.",
        "minimum_artifacts": ["source", "database version or runtime logs", "structure artifact"],
    },
    "esmfold_folding": {
        "capability_status": "runtime_unverified",
        "boundary": "Can support structure interpretation only when runtime/model version and output PDB are recorded.",
        "minimum_artifacts": ["model version", "PDB", "pLDDT", "logs"],
    },
    "rfdiffusion_design": {
        "capability_status": "proxy",
        "boundary": "Not report-grade RFdiffusion unless official checkpoint, run_inference config, PDB/TRB/trajectory artifacts exist.",
        "minimum_artifacts": ["checkpoint hash", "Hydra config", "backbone PDB", "TRB", "trajectory", "GPU runtime"],
    },
    "proteinmpnn_design": {
        "capability_status": "proxy",
        "boundary": "Not report-grade ProteinMPNN unless official weights and protein_mpnn_run.py outputs are recorded.",
        "minimum_artifacts": ["checkpoint/model", "fixed/designed chains", "FASTA", "scores", "seed", "logs"],
    },
    "diffdock_docking": {
        "capability_status": "proxy",
        "boundary": "DiffDock confidence is pose confidence, not affinity; current simplified entry must not be called real DiffDock without artifacts.",
        "minimum_artifacts": ["model version", "3D ligand source", "pose ensemble", "confidence", "logs"],
    },
    "ligand_preprocess": {
        "capability_status": "real_runtime_gated",
        "boundary": "Real OpenBabel/Vina/ACPYPE stages only when runtimes exist; missing runtimes must return blocked.",
        "minimum_artifacts": ["stage results", "tool versions", "PDBQT/pose/topology files", "logs"],
    },
    "rosetta_ddg": {
        "capability_status": "real_runtime_gated",
        "license_class": "academic_or_commercial_license",
        "commercial_use_status": "blocked_without_commercial_authorization",
        "boundary": "Real Rosetta only when runtime and structure are available; local estimate is explicitly non-Rosetta.",
        "minimum_artifacts": ["Rosetta binary", "mutation file", "scorefile", "logs"],
    },
    "gromacs_md": {
        "capability_status": "real_runtime_gated",
        "license_class": "open_local",
        "commercial_use_status": "allowed_with_runtime_and_input_provenance",
        "boundary": "Real MD only when GROMACS preprocessing and mdrun artifacts exist; plan-only is not MD evidence.",
        "minimum_artifacts": ["MDP", "TPR", "XTC/TRR", "EDR/XVG", "stdout/stderr", "runtime versions"],
    },
    "hmmer": {
        "capability_status": "real_runtime_gated",
        "license_class": "open_local",
        "commercial_use_status": "allowed_with_database_terms",
        "boundary": "Profile-HMM evidence requires a real HMMER runtime and versioned profile database; short motifs are not a substitute.",
        "minimum_artifacts": ["hmmscan/hmmsearch command", "HMM database version", "domtblout", "input hash", "logs"],
    },
    "interproscan": {
        "capability_status": "real_runtime_gated",
        "license_class": "open_data_restricted",
        "commercial_use_status": "verify_member_database_terms",
        "boundary": "InterProScan completion and member-database provenance are required; submitted REST jobs are not annotation evidence.",
        "minimum_artifacts": ["software version", "member database versions", "TSV/XML result", "input hash", "logs"],
    },
    "dbcan": {
        "capability_status": "real_runtime_gated",
        "license_class": "open_data_restricted",
        "commercial_use_status": "verify_cazy_and_hmm_terms",
        "boundary": "dbCAN supports CAZyme annotation only; family hits do not by themselves establish substrate or catalytic residues.",
        "minimum_artifacts": ["run_dbcan version", "HMM dataset version", "domain result", "input hash", "manual review flag"],
    },
    "foldx": {
        "capability_status": "real_runtime_gated",
        "license_class": "academic_or_commercial_license",
        "commercial_use_status": "blocked_without_commercial_authorization",
        "boundary": "FoldX ddG may be used only with an authorized runtime and raw energy output; local estimates must not be labeled FoldX.",
        "minimum_artifacts": ["FoldX binary/version", "license receipt", "RepairPDB/BuildModel output", "raw score files", "logs"],
    },
    "caver": {
        "capability_status": "real_runtime_gated",
        "license_class": "verify_specific_distribution",
        "commercial_use_status": "blocked_until_distribution_terms_verified",
        "boundary": "Tunnel claims require a real CAVER run with trajectory/structure inputs and parsed tunnel artifacts.",
        "minimum_artifacts": ["CAVER distribution/version", "config", "tunnel output", "input hash", "logs"],
    },
}

# Conservative coverage for tools that are registered but do not yet have a
# bespoke scientific audit entry.  These entries describe boundaries and
# required artifacts; they do not make proxy or runtime-unverified outputs
# report-grade evidence.
_CAPABILITIES.update({
    "disulfide_saltbridge_scan": {"capability_status": "structure_geometry_feature_table", "boundary": "Reports coordinate-derived disulfide, salt-bridge, and histidine contacts; it does not prove catalytic function or solution-state stability.", "minimum_artifacts": ["PDB/model provenance", "chain", "residue coordinates", "distance thresholds", "contact table"]},
    "bio_specialty_input_gate": {"capability_status": "input_gate", "boundary": "Validates input completeness only; it does not establish enzyme identity or function.", "minimum_artifacts": ["normalized input", "missing-input report"]},
    "boltz1_predict": {"capability_status": "runtime_unverified", "boundary": "Structure prediction hypothesis unless model/runtime/version and raw structure artifacts are recorded.", "minimum_artifacts": ["model version", "input hash", "structure artifact", "confidence", "logs"]},
    "chroma_design": {"capability_status": "proxy", "boundary": "Generative design hypothesis; does not establish foldability, activity, or safety.", "minimum_artifacts": ["model/checkpoint", "condition", "seed", "sequences", "scores"]},
    "esm1v_predict": {"capability_status": "proxy", "boundary": "Sequence likelihood/risk proxy; not an experimental fitness measurement.", "minimum_artifacts": ["model version", "input hash", "mutation list", "scores"]},
    "esm2_predict": {"capability_status": "proxy", "boundary": "Embedding or prediction proxy; claims require model/version and validation scope.", "minimum_artifacts": ["model version", "mode", "input hash", "scores"]},
    "esm3_generate": {"capability_status": "proxy", "boundary": "Generative sequence hypothesis; must not be presented as validated function.", "minimum_artifacts": ["model version", "prompt/constraints", "seed", "sequences"]},
    "esm_if1_design": {"capability_status": "proxy", "boundary": "Structure-conditioned sequence hypothesis; does not prove stability or activity.", "minimum_artifacts": ["model version", "structure hash", "seed", "FASTA", "scores"]},
    "evodiff_generate": {"capability_status": "proxy", "boundary": "Generative sequence hypothesis requiring downstream structural and experimental validation.", "minimum_artifacts": ["model version", "conditioning", "seed", "FASTA"]},
    "external_connectivity_check": {"capability_status": "connectivity_only", "boundary": "Connectivity proves reachability only, not scientific result or database correctness.", "minimum_artifacts": ["endpoint", "timestamp", "status", "runtime"]},
    "external_research_evidence": {"capability_status": "external_service_only", "boundary": "Research retrieval is evidence only with source identity, provenance, and reproducible response.", "minimum_artifacts": ["source", "query", "retrieval timestamp", "citation/provenance"]},
    "feedback_iteration_planner": {"capability_status": "decision_support", "boundary": "Plans follow-up experiments from feedback; it does not validate the underlying assay or model.", "minimum_artifacts": ["feedback records", "objective", "decision rationale"]},
    "get_kinetic_params": {"capability_status": "data_lookup", "boundary": "Lookup output requires source and assay context; absence is not evidence of absence.", "minimum_artifacts": ["source", "assay context", "record provenance"]},
    "get_stability_data": {"capability_status": "data_lookup", "boundary": "Stability lookup requires assay conditions and provenance; values are not transferable without context.", "minimum_artifacts": ["source", "temperature/pH context", "record provenance"]},
    "interpro_annotation": {"capability_status": "evidence_synthesis", "boundary": "Local annotation is not equivalent to a completed live InterProScan job and needs dataset/version provenance.", "minimum_artifacts": ["dataset version", "input hash", "annotation records"]},
    "interpro_live_lookup": {"capability_status": "external_service_only", "boundary": "Only completed live response with member-database provenance supports annotation evidence.", "minimum_artifacts": ["request", "terminal response", "database/version", "raw result"]},
    "interproscan_sequence_status": {"capability_status": "external_service_only", "boundary": "Pending job status is a receipt, not annotation evidence; only finished results may be interpreted.", "minimum_artifacts": ["job id", "terminal status", "raw result", "database/version"]},
    "interproscan_sequence_submit": {"capability_status": "external_service_only", "boundary": "Submission creates a job only and must not enter report conclusions.", "minimum_artifacts": ["job id", "input hash", "submission timestamp"]},
    "ligandmpnn_design": {"capability_status": "proxy", "boundary": "Ligand-conditioned sequence hypothesis; requires structure, ligand provenance, and downstream validation.", "minimum_artifacts": ["model version", "protein/ligand hash", "seed", "FASTA", "scores"]},
    "ligand_contact_analysis": {"capability_status": "structure_geometry_feature_table", "boundary": "Reports coordinate-derived ligand contacts and distances; contact geometry is not binding energy, catalytic proof, or experimental affinity.", "minimum_artifacts": ["PDB/model provenance", "ligand component", "chain", "contact cutoff", "contact table"]},
    "list_ec_proteins": {"capability_status": "data_lookup", "boundary": "EC listing is catalog evidence, not identity confirmation for the current sequence.", "minimum_artifacts": ["database/source", "query", "retrieved records"]},
    "literature_live_search": {"capability_status": "external_service_only", "boundary": "Search hits are not evidence until the cited source and claim context are verified.", "minimum_artifacts": ["query", "citation", "retrieval timestamp", "claim mapping"]},
    "lookup_protein": {"capability_status": "data_lookup", "boundary": "Identifier lookup supports candidate identity only; sequence/structure concordance remains required.", "minimum_artifacts": ["identifier", "source", "retrieved record", "sequence concordance"]},
    "mutation_epistasis_check": {"capability_status": "decision_support", "boundary": "Epistasis check is a consistency/risk analysis, not proof of combination performance.", "minimum_artifacts": ["mutation set", "distance/mechanism inputs", "feedback provenance", "decision rationale"]},
    "progen2_generate": {"capability_status": "proxy", "boundary": "Generative sequence hypothesis; no functional claim without downstream validation.", "minimum_artifacts": ["model version", "conditioning", "seed", "FASTA"]},
    "residue_numbering_gate": {"capability_status": "numbering_evidence_gated", "boundary": "Validates numbering consistency; it does not identify catalytic function or mutation benefit.", "minimum_artifacts": ["mapping source", "chain", "requested positions", "gate result"]},
    "rosettafold_allatom": {"capability_status": "runtime_unverified", "boundary": "All-atom structure hypothesis unless official runtime, model, and raw artifacts are present.", "minimum_artifacts": ["model/version", "input entities", "structure artifact", "logs"]},
    "rosettafold_folding": {"capability_status": "runtime_unverified", "boundary": "Folding hypothesis unless official runtime, model, and confidence artifacts are present.", "minimum_artifacts": ["model/version", "sequence hash", "structure artifact", "confidence", "logs"]},
    "scientific_claim_gate": {"capability_status": "claim_gate", "boundary": "Checks claim contracts; it does not create missing scientific evidence.", "minimum_artifacts": ["claims", "required schemas", "gate decision", "blocking reasons"]},
    "search_substrate": {"capability_status": "data_lookup", "boundary": "Substrate search provides catalog candidates; identity, reaction context, and assay compatibility require review.", "minimum_artifacts": ["query", "source", "retrieved records", "reaction context"]},
    "sequence_search": {"capability_status": "external_service_or_cache", "boundary": "Sequence hits support homology hypotheses only with terminal response and database provenance.", "minimum_artifacts": ["query hash", "database/program", "terminal status", "hit table"]},
    "signal_peptide_predict": {"capability_status": "proxy", "boundary": "Signal peptide prediction is a localization hypothesis, not proof of secretion or processing.", "minimum_artifacts": ["model/version", "sequence hash", "prediction", "confidence"]},
    "soluble_mpnn_design": {"capability_status": "proxy", "boundary": "Solubility-conditioned design hypothesis; requires structure and wet-lab validation.", "minimum_artifacts": ["model version", "input hash", "seed", "FASTA", "scores"]},
    "tool_capability_audit": {"capability_status": "governance", "boundary": "Reports capability metadata; it does not validate tool outputs.", "minimum_artifacts": ["tool name", "capability row", "audit timestamp"]},
    "structure_pocket_interface_analysis": {"capability_status": "structure_geometry_feature_table", "boundary": "Reports coordinate-derived pocket/interface and channel clues; it does not establish binding energy, mechanism, or mutation benefit.", "minimum_artifacts": ["PDB/model provenance", "chain/interface scope", "distance thresholds", "feature table"]},
    "wt_baseline_registry": {"capability_status": "data_registry", "boundary": "Registers compatible WT baselines; it does not generalize assay performance across conditions.", "minimum_artifacts": ["assay context", "preparation/batch", "QC status", "source records"]},
})


def tool_capability_audit(tool_names: list[str] | None = None) -> dict[str, Any]:
    """Return capability status and minimum artifacts for selected tools."""
    names = tool_names if isinstance(tool_names, list) and tool_names else sorted(_CAPABILITIES)
    rows = []
    unknown = []
    for name in names:
        key = str(name)
        capability = _CAPABILITIES.get(key)
        if not capability:
            unknown.append(key)
            rows.append({
                "tool": key,
                "capability_status": "unknown",
                "boundary": "No capability audit entry exists yet; do not promote outputs as report-grade evidence.",
                "minimum_artifacts": ["capability audit entry"],
                "report_action": "block_report_grade_claims",
            })
            continue
        status = capability["capability_status"]
        rows.append({
            "tool": key,
            **capability,
            "report_action": (
                "allow_with_artifacts"
                if status in {
                    "real_runtime_gated",
                    "evidence_synthesis",
                    "foundation_dependent_explainer",
                    "foundation_or_proxy_prediction",
                    "objective_gate",
                    "structure_similarity_search",
                    "numbering_evidence_gated",
                    "background_baseline",
                    "external_service_or_cache",
                    "curated_or_motif_guardrail",
                    "residue_geometry_feature_table",
                }
                else "label_as_proxy_or_block_until_artifacts_exist"
            ),
        })
    status_counts: dict[str, int] = {}
    for row in rows:
        status_key = str(row.get("capability_status") or "unknown")
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
    return {
        "status": "ready" if not unknown else "partial",
        "capabilities": rows,
        "unknown_tools": unknown,
        "summary": {
            "tool_count": len(rows),
            "unknown_count": len(unknown),
            "status_counts": status_counts,
        },
        "rules": {
            "real_runtime": "Requires versioned runtime, command/config, logs, and output artifacts.",
            "proxy": "May support triage only; must not be phrased as official model inference.",
            "blocked": "Missing runtime or input evidence must block report-grade conclusions.",
        },
    }


ToolRegistry.register(
    name="tool_capability_audit",
    description=(
        "Return capability_status, scientific boundary, and minimum artifact requirements "
        "for protein R&D tools so reports distinguish real runtime, external service, proxy, and blocked states."
    ),
    parameters={
        "type": "object",
        "properties": {
            "tool_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of tool names to audit. Defaults to all audited tools.",
            }
        },
    },
    handler=tool_capability_audit,
    category="analysis",
    timeout_seconds=30,
)
