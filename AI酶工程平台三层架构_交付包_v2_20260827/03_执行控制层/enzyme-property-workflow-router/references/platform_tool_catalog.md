# Protein AI Platform Tool Catalog

## Scope and evidence

- Platform entry: `http://120.27.108.138/chat/agent`
- Tool registry endpoint: `GET /api/tools` (requires platform authentication)
- Tool call endpoint: `POST /api/tools/{tool_name}/call`
- Async submit endpoint: `POST /api/tools/{tool_name}/submit`
- Async task status: `GET /api/tools/tasks/{task_id}`
- Public capability boundary endpoint: `GET /api/data/tool-capabilities`
- Registry count confirmed by IT on 2026-08-27: **58 tools**.
- The 58 tools' required parameters and JSON Schema were confirmed against the current backend.
- The 13 tools marked asynchronous in this delivery package were confirmed against the live Celery asynchronous set.
- `is_async` metadata remains an execution hint, not a sufficient source of truth. The executor must still handle `call`/`submit` response status and use the actual backend response when selecting the invocation path.
- Capability labels such as `proxy`, `real_runtime_gated`, and `evidence_synthesis` come from `/api/data/tool-capabilities` when available.

## Invocation rules

1. Before every task, fetch the current registry and use the exact registered `name` and `parameters` schema.
2. Do not substitute an old UI label for a registered tool name. Examples: use `structure_search_foldseek`, `esmfold_folding`, and `soluble_mpnn_design` exactly as registered.
3. For synchronous tools, call `POST /api/tools/{name}/call` with `{"params": {...}}`.
4. For asynchronous tools, submit with `POST /api/tools/{name}/submit`, then poll `GET /api/tools/tasks/{task_id}` until terminal status.
5. Record `tool_name`, `category`, `is_async`, input hash, output artifact, runtime status, and evidence status.
6. A `200` response is not automatically report-grade. Inspect returned evidence, provenance, runtime artifacts, and capability boundary.
7. Distinguish these outcomes: `completed`, `missing_required`, `async_required`, `blocked`, `degraded`, and `failed`.
8. Never present a proxy, cache hit, plan-only result, or external lookup as experimental validation.

## Complete registry

### Analysis, governance, and input gates

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `scientific_claim_gate` | false | Review whether a scientific claim is sufficiently supported before it enters the final report. Use for claims such as “mutation improves activity” or “candidate is validated”. | Claim text, target property, evidence records, assay context | Pass/block decision, missing evidence, claim wording. Governance gate; does not generate experimental evidence. |
| `predict_properties` | false | Calculate sequence-derived physicochemical baseline values. Use for background profiling and triage, not as proof of thermostability, activity, or mutation gain. | Protein sequence, optional construct metadata | Property vector and calculation method. `background_baseline`; assay data required for target claims. |
| `enzyme_identity_profile` | false | Establish enzyme family/identity profile, candidate families, key residues, and numbering guardrails before design. | Sequence, optional accession/structure | Family candidates, key residues, evidence table, identity status. `evidence_synthesis`; short motifs alone are not family proof. |
| `protein_benchmark` | false | Compare a protein against known enzyme families and explain conserved motifs or family-level context. | Sequence plus `enzyme_identity_profile` result; optional family set | Benchmark metrics and family explanation. Must pass the identity guardrail first. |
| `enzyme_objective_module_plan` | false | Translate a target property into objective-specific evidence, validation, and candidate-output requirements. Use at the beginning of a property-specific workflow. | Primary property, secondary constraints, assay context, available inputs | Objective modules, missing evidence, validation requirements, candidate decision. Does not prove improvement. |
| `tool_capability_audit` | false | Report the actual capability boundary of tools used in a task. Use before selecting report-grade evidence. | Tool names or current registry | Capability status, required artifacts, report action. Distinguishes proxy, live, gated, and synthesis tools. |
| `bio_specialty_input_gate` | false | Legacy non-enzyme biology gate for membrane-protein, receptor-ligand, pathway, and antibody-humanization tasks. **Do not use for the five enzyme-property workflows.** | Supported non-enzyme biology task inputs | Scope-limited input assessment; not an enzyme-engineering intake gate. |

### Search and evidence retrieval

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `sequence_search` | true | Search sequence/protein databases for homologs, accessions, and sequence evidence. Use for identity and family evidence. | Sequence, accession, query, database | Hits, identity/coverage/e-value or database evidence, provenance. Live status must be checked. |
| `blast_search` | true | Run homology search for sequence similarity. Use when a direct similarity search is needed. | Query sequence, database/program, search parameters | Hit table with identity, coverage, e-value, provenance. Async workflow; submitted/degraded results cannot support conclusions. |
| `lookup_protein` | true | Retrieve a protein record by identifier or accession. Use to obtain canonical sequence and metadata. | Accession, identifier, database | Protein record, sequence, annotations, cross-references. Verify source and version. |
| `list_ec_proteins` | true | List proteins associated with an EC number or enzyme function. Use for reference set construction. | EC number, organism/database filters | Protein list and metadata. Not evidence that the input sequence has the EC function. |
| `search_substrate` | true | Search substrate/compound records. Use for substrate identity, synonyms, and ligand preparation inputs. | Substrate name, identifier, SMILES/InChI, database | Compound records and identifiers. Confirm chemical identity before docking. |
| `literature_live_search` | true | Search current literature for mechanism, mutation, assay, or property evidence. Use for evidence-backed design rationale. | Scientific query, optional filters | Literature records with PMID/DOI/title and evidence source. Check live/cache/degraded status. |
| `external_research_evidence` | false | Consolidate or govern external research evidence used in a report. Use to attach provenance and evidence status to claims. | Search results, citations, claim context | Evidence bundle, provenance, source status, claim support. Governance tool; not a substitute for primary retrieval. |
| `external_connectivity_check` | true | Check connectivity and health of external data sources before relying on live evidence. | Target service/source, optional timeout or query type | Connectivity status, latency/error, live/degraded assessment. Use as a health check, not as biological evidence. |

### Structure prediction and structural search

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `esmfold_folding` | true | Predict a protein structure from sequence using an ESMFold path. Use when no trustworthy structure is available. | Amino-acid sequence, optional model/runtime settings | PDB/mmCIF, confidence metrics, logs. `runtime_unverified` unless model/runtime and artifact are recorded. |
| `alphafold_folding` | true | Retrieve or produce an AlphaFold-family structure path. Use only after distinguishing database lookup from true inference. | Sequence/accession, optional model/template settings | Structure artifact or external lookup, confidence/provenance. `proxy_or_external_lookup`; do not call it true inference without artifacts. |
| `alphafold2_folding` | false | AlphaFold2-related structure prediction or proxy entry. Use for structural hypothesis generation only when runtime artifacts are present. | Sequence, MSA/template/runtime inputs | Structure, confidence, logs. `proxy`; requires model version, MSA/template provenance, PDB/mmCIF, PAE/pLDDT, and logs for report-grade claims. |
| `rosettafold_folding` | false | Predict a protein structure using a RoseTTAFold-family path. | Sequence, optional MSA/template/runtime inputs | Structure and confidence/provenance. Verify runtime and structure artifact. |
| `rosettafold_allatom` | false | Generate or refine an all-atom structural hypothesis. Use when atom-level geometry is needed. | Sequence/structure, optional templates and constraints | All-atom structure and confidence/provenance. Treat as prediction unless artifacts and validation are present. |
| `boltz1_predict` | false | Predict protein structure or protein-complex structure using a Boltz-family path. | Protein sequence, ligand/partner inputs, optional constraints | Structure/complex hypothesis and confidence. Verify model/runtime and artifact before report-grade use. |
| `structure_search_foldseek` | true | Search for structurally similar templates using Foldseek or configured local/remote endpoint. | PDB/mmCIF text or stored structure object | Structural hit table, TM-score/alignment coverage, template provenance. Structural similarity does not confirm enzyme identity. |
| `residue_mapping_sifts` | true | Map PDB residue numbering to UniProt/reference numbering. Use before reporting mutation positions. | PDB structure, chain, UniProt accession, starting position | Mapping table, missing-residue/mature-chain notes, mapping confidence. Coordinate order alone is not external SIFTS evidence. |

### Catalytic analysis, mutation analysis, and engineering

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `catalytic_site_lookup` | true | Identify or retrieve catalytic residues and active-site evidence. Use before activity or substrate-specific design. | Sequence/accession, optional structure, EC/family context | Catalytic residues, site evidence, numbering/provenance. Requires correct identity and numbering context. |
| `mutation_scan` | false | Broadly scan substitutions for physicochemical risk and candidate triage. Use to generate a conservative candidate pool. | Sequence, positions/substitutions, constraints | Scan scores and risk flags. `proxy`; not a final candidate table without identity, numbering, protected-site, and objective gates. |
| `mutation_priority_score` | true | Rank mutation candidates using rules/model-assisted prioritization. Use after identity, numbering, and objective gates pass. | Sequence/structure, candidate mutations, target objective, protected residues | Ranked candidates, rationale, protected-site status. `proxy_ranker`; not wet-lab evidence or Rosetta/ddG/pKa. |
| `rosetta_ddg` | true | Estimate mutation stability change using Rosetta when the real runtime is available. Use as a stability constraint or ranking signal. | Structure, mutation file, Rosetta settings | ΔΔG scorefile, labels, logs. `real_runtime_gated`; local estimates must not be called Rosetta. |
| `mutation_epistasis_check` | true | Evaluate interaction/epistasis and conflict among multiple mutations. Use before selecting mutation combinations. | WT sequence/structure, mutation list or combinations, objective context | Pairwise/combination interaction assessment, conflict flags, single-mutant recommendation. |
| `residue_numbering_gate` | true | Validate that residue numbering, chain mapping, mature-chain offsets, and protected positions are consistent. Use before any mutation report. | Sequence, structure, accession, candidate positions | Numbering pass/block, mapping warnings, coordinate references. Treat a block as a hard stop. |
| `feedback_iteration_planner` | true | Convert experimental measurements or failed-round feedback into the next design iteration. | WT/mutant results, assay data, failed candidates, constraints | Next-round objective, candidate changes, validation plan. Requires real feedback; not a substitute for experiment data. |

### Activity and property prediction

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `enzyme_function` | false | Predict or classify enzyme function/EC context from identity profile and sequence evidence. Use for background functional interpretation. | Sequence, identity profile, motifs/annotations | Function/EC hypothesis with confidence and limitations. `foundation_or_proxy_prediction`; not confirmed EC without evidence. |
| `kcat_predict` | false | Estimate catalytic turnover (`kcat`) or related activity tendency. Use for hypothesis ranking only. | Sequence, family/identity context, substrate/reaction context | Estimated kcat or activity score. `proxy`; not calibrated quantitative kcat without model card and validation artifacts. |
| `protssn_score` | false | Score sequence/structure neighborhood plausibility or variant compatibility. Use as a mutation-ranking auxiliary signal. | Sequence, structure/neighborhood, candidate substitutions | Scores and ranking features. `proxy` unless model/runtime artifacts are attached. |

### Sequence and generative protein design

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `proteinmpnn_design` | true | Design sequences compatible with a supplied backbone using ProteinMPNN. Use for structure-conditioned sequence design. | Backbone PDB, fixed/designed chains, design positions, model/checkpoint | Designed FASTA, scores, seed, logs. `proxy` unless official checkpoint and `protein_mpnn_run.py` outputs are recorded. |
| `soluble_mpnn_design` | false | Design sequences with a solubility/expression-oriented ProteinMPNN-style objective. Use for expression/solubility optimization. | Backbone/structure, sequence, fixed positions, design constraints | Candidate sequences and scores. `proxy`; must preserve catalytic and structural constraints. |
| `ligandmpnn_design` | false | Design protein sequences conditioned on a ligand or ligand-binding environment. Use for ligand-aware design. | Protein structure, ligand/complex structure, fixed/design chains | Designed sequences and compatibility scores. Confirm ligand and structural artifacts. |
| `rfdiffusion_design` | true | Generate new protein backbones or structural scaffolds with RFdiffusion. Use for de novo design or scaffold generation, not routine point mutation work. | Conditioning structure/contig/config, checkpoint | Backbone PDB, trajectory/TRB, config, scores. `proxy` unless checkpoint, config, PDB/TRB/trajectory, and GPU runtime are recorded. |
| `esm_if1_design` | false | Inverse-folding sequence design from a backbone structure. | Backbone structure, fixed/design positions | Candidate sequences and scores. Use as a design hypothesis and cross-check with structural constraints. |
| `esm3_generate` | false | Generate or edit protein sequences using an ESM3-family generative path. | Prompt/sequence/structure constraints | Generated sequence candidates and generation metadata. Treat as generative hypotheses. |
| `esm2_predict` | false | Generate ESM2-family sequence representations or property/variant predictions. | Sequence, optional variant positions | Embeddings/scores/prediction outputs. Use as a prediction auxiliary, not direct experimental evidence. |
| `esm1v_predict` | false | Predict variant effects with an ESM-1v-style zero-shot sequence model. | WT sequence and mutation(s) | Variant effect scores/ranking. Use for prioritization and compare with other evidence. |
| `progen2_generate` | false | Generate protein sequence candidates with a ProGen2-family model. | Sequence context, target family/constraints | Generated sequence candidates and scores. Use only with identity, structure, and objective gates. |
| `evodiff_generate` | false | Generate or edit protein sequences using an evolutionary diffusion path. | Sequence/context/constraints | Sequence candidates and generation metadata. Generative hypothesis; requires downstream screening. |
| `chroma_design` | false | Generate protein designs using a Chroma-family generative design path. | Structure/design constraints | Design candidates and structural/sequence outputs. Requires downstream folding and objective validation. |

### Docking, ligand preparation, and molecular dynamics

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `ligand_preprocess` | true | Prepare ligand files for docking or molecular dynamics, including OpenBabel/Vina/ACPYPE stages when available. | SMILES/SDF/MOL2, protonation/charge settings, target receptor context | PDBQT/pose/topology files, stage logs, tool versions. `real_runtime_gated`; missing runtimes must return blocked. |
| `diffdock_docking` | true | Predict protein-ligand docking poses with a DiffDock-family path. | Protein structure, ligand 3D structure, ligand identifier | Pose ensemble and confidence. `proxy`; pose confidence is not affinity. |
| `gromacs_md` | false | Run or validate molecular dynamics simulations for structural stability and flexibility. Use after structure preparation and protocol selection. | Protein/complex structure, MDP/protocol, topology, replicates | RMSD/RMSF, radius of gyration, trajectories, energy outputs, logs. `real_runtime_gated`; plan-only output is not MD evidence. |

### Annotation and biochemical data

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `annotation_bundle` | true | Aggregate curated/local sequence, domain, catalytic, and cross-reference annotations. Use as a broad evidence bundle before objective-specific analysis. | Sequence/accession, optional family or structure | Annotation bundle with provenance and coordinates. `evidence_synthesis`; not a live BLAST/InterProScan substitute. |
| `interpro_annotation` | true | Retrieve or interpret curated/local InterPro domain and family annotations. | Sequence/accession, optional coordinates | Domains, families, signatures, coordinates, provenance. Check whether result is local/cache or live. |
| `interpro_live_lookup` | true | Perform a live InterPro lookup. Use when current external domain evidence is required. | Sequence/accession/query | Live InterPro results and evidence status. Must record live query status and source. |
| `interproscan_sequence_submit` | true | Submit a sequence to an InterProScan workflow. | Sequence, optional analysis/database settings | Async job identifier and submission status. Must poll with the matching status tool. |
| `interproscan_sequence_status` | true | Retrieve the status and result of an InterProScan submission. | InterProScan job identifier | Job status, domain/signature results, terminal artifacts. Do not interpret a submitted state as completed evidence. |
| `get_kinetic_params` | true | Retrieve kinetic measurements such as Km, kcat, Vmax, or catalytic efficiency from the platform data layer. | Protein/EC/substrate identifiers, filters | Kinetic records, assay context, source/provenance. Data retrieval, not prediction. |
| `get_stability_data` | true | Retrieve stability measurements such as Tm, half-life, residual activity, or condition-specific stability. | Protein/variant identifiers, assay/condition filters | Stability records and assay context. Data retrieval, not prediction. |
| `search_substrate` | true | Retrieve substrate records for enzyme/reaction context and ligand preparation. | Substrate name/identifier/chemical representation | Compound records and identifiers. Validate chemical identity before downstream use. |

### Signal peptide and secretion-related prediction

| Tool name | Async | Function and typical use | Typical inputs | Typical outputs / boundary |
|---|---:|---|---|---|
| `signal_peptide_predict` | true | Predict N-terminal signal peptide and secretion-related features. Use for expression/secretion workflows. | Protein sequence, host/context if supported | Signal peptide presence, cleavage site, confidence, prediction source. Treat as prediction until experimentally verified. |

## Property-oriented lookup map (not yet a workflow)

This map is for catalog navigation only. It does not prescribe the final platform workflow.

| Property or task | Candidate tools to inspect first | Tools that may be conditional | Tools that must not be used as sole proof |
|---|---|---|---|
| Activity / catalytic efficiency | `enzyme_objective_module_plan`, `enzyme_identity_profile`, `catalytic_site_lookup`, `enzyme_function`, `kcat_predict`, `mutation_priority_score`, `scientific_claim_gate` | `sequence_search`, `lookup_protein`, `get_kinetic_params`, `search_substrate`, `structure_search_foldseek`, `esmfold_folding`, `alphafold_folding`, `diffdock_docking`, `gromacs_md`, `mutation_epistasis_check` | `predict_properties`, `kcat_predict`, `protssn_score`, or any generative design tool alone |
| Stability / thermostability / solvent tolerance / protease tolerance | `enzyme_objective_module_plan`, `enzyme_identity_profile`, `mutation_scan`, `mutation_priority_score`, `rosetta_ddg`, `scientific_claim_gate` | `sequence_search`, `get_stability_data`, `esmfold_folding`, `structure_search_foldseek`, `gromacs_md`, `mutation_epistasis_check` | Sequence physicochemical values or proxy scores alone |
| pH optimum / target-pH activity / pH window / acid-base tolerance | `enzyme_objective_module_plan`, `enzyme_identity_profile`, `catalytic_site_lookup`, `mutation_priority_score`, `scientific_claim_gate` | `get_kinetic_params`, `get_stability_data`, `structure_search_foldseek`, `residue_mapping_sifts`, `esmfold_folding`, `gromacs_md`, `mutation_epistasis_check`, `annotation_bundle` | Surface pI, charge count, or proxy scores alone |
| Specificity / selectivity | `enzyme_objective_module_plan`, `enzyme_identity_profile`, `catalytic_site_lookup`, `search_substrate`, `mutation_priority_score`, `scientific_claim_gate` | `structure_search_foldseek`, structure prediction, `ligand_preprocess`, `diffdock_docking`, `mutation_epistasis_check`, `get_kinetic_params` | General activity gain alone |
| Solubility / expression / secretion | `enzyme_objective_module_plan`, `enzyme_identity_profile`, `predict_properties`, `soluble_mpnn_design`, `signal_peptide_predict`, `mutation_priority_score`, `scientific_claim_gate` | `esmfold_folding`, `protssn_score`, `annotation_bundle`, host-specific downstream tools if available | Activity or stability tools alone |
| Identity / annotation | `bio_specialty_input_gate`, `sequence_search`, `blast_search`, `enzyme_identity_profile`, `annotation_bundle` | `interpro_live_lookup`, InterProScan submit/status, `structure_search_foldseek`, `protein_benchmark`, `enzyme_function` | Short motif match or structure hit alone |
| Candidate combination / next iteration | `residue_numbering_gate`, `mutation_epistasis_check`, `feedback_iteration_planner`, `scientific_claim_gate` | `rosetta_ddg`, `gromacs_md`, objective-specific data retrieval | Unchecked multi-mutant ranking |

## What is confirmed versus pending

### Confirmed

- Exact registry names and total count: 58, confirmed by IT on 2026-08-27.
- Required parameters and JSON Schema for all 58 tools, confirmed against the current backend.
- The 13 asynchronous tools in this package, confirmed against the current Celery asynchronous set.
- Capability boundaries for 22 tools from the public `/api/data/tool-capabilities` response.
- API route pattern for synchronous calls, async submission, and task polling.

### Pending before workflow locking

- The current live parameter schema for every tool should be exported from `/api/tools` and versioned with the skill.
- Each tool needs a real input/output example from the current platform version.
- Each tool needs a verified runtime status under the current deployment.
- Property workflows should be locked only after selecting the target property and agreeing on mandatory, optional, and forbidden tools.
