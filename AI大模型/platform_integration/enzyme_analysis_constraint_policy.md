# Enzyme Analysis Constraint Policy

This local-only policy fixes the analysis order for enzyme engineering requests.
It is intended for GPT orchestration, KWB-EnzymeDesigner tool output, and human
review. It does not execute Rosetta, GROMACS, docking, synthesis, or wet-lab work.

## Required Order

1. Validate inputs: sequence, PDB/mmCIF, UniProt/PDB id, substrate, objective,
   assay condition and residue numbering.
2. Predict basic properties first with `predict_properties` when a sequence is
   available.
3. Fuse database evidence with explicit source tiers using `annotation_bundle`
   and local evidence services.
4. If structure-dependent claims are requested, run structure lookup/mapping
   before mutation claims: `structure_search_foldseek`, `residue_mapping_sifts`,
   then `residue_numbering_gate`.
5. Rank important mutation sites with `mutation_priority_score`.
6. For combinations, run `mutation_epistasis_check` before recommending a
   multi-mutant.
7. Optional stability or MD validation must stay blocked unless runtime,
   topology, numbering and user confirmation are all available.
8. Output an experiment workflow and Go/Watch/No-Go decision block.

## Tool Display Contract

Before execution, the platform should show the intended tools and parameter
summary. After confirmation, every tool call should be visible with:

- step order
- tool name
- input summary
- parameter summary
- blocked/executed status
- runtime or database readiness
- result preview
- evidence level
- manual review requirement

## Database Fusion Rules

Evidence tiers:

- Tier 0: KWB wet-lab feedback
- Tier 1: reviewed local database evidence with confirmed numbering
- Tier 2: public database evidence with version and mapping
- Tier 3: computational predictions
- Tier 4: weak or unreviewed evidence

Forbidden merges:

- Do not promote weak evidence to training labels without reviewed numbering.
- Do not collapse prediction, public literature and wet-lab feedback into one
  confidence class.
- Do not project database residue positions onto a PDB without
  `residue_numbering_gate`.
- Do not treat model output as experiment feedback.

## Mutation Site Rules

- Tier 1: `composite_priority >= 7.0` and no high-risk review gate is active.
- Tier 2: `5.0 <= composite_priority < 7.0`, useful but review-dependent.
- Tier 3: `< 5.0` or low-confidence sequence-only support.
- No-Go by default: catalytic residues, metal/cofactor binding residues,
  disulfide cysteines, fully conserved family residues, numbering mismatch,
  known wet-lab No-Go, and severe predicted destabilization.

First experimental round should prefer 6-10 single mutants. Combination mutants
must start from validated single mutants and pass epistasis review.

## Delta-Delta-G Thresholds

Sign convention: negative ΔΔG means predicted stabilization; positive ΔΔG means
predicted destabilization.

- Stabilizing: `< -1.0 kcal/mol`
- Neutral: `-1.0` to `+1.0 kcal/mol`
- Watch: `> +1.0` to `+2.0 kcal/mol`
- No-Go: `> +2.0 kcal/mol`, unless a reviewed compensating mechanism exists

The `-1.0` to `+2.0` range requires manual review against activity, expression,
active-site distance and evidence tier.

## Rosetta Status

Current local status: Rosetta/PyRosetta/FoldX ΔΔG execution is not integrated.
The broader platform has RosettaFold structure-prediction modules, but that is
not Rosetta mutant ΔΔG calculation.

Allowed claim: the system can report heuristic ΔΔG or external-tool readiness.
Forbidden claim: the system must not say Rosetta ddG was executed unless a
licensed/runtime-verified adapter ran and produced auditable artifacts.

Future adapter gates:

- license review approved
- binary or PyRosetta runtime available
- PDB chain and residue numbering verified
- mutation list validated
- ddG output artifacts include parameters and checksum

## Experiment Workflow

1. Select 6-10 single mutants with Go/Watch rationale.
2. Review residue numbering and active-site guardrails.
3. Prepare primer/mutagenesis plan outside the model.
4. Run PCR or synthesis, cloning, and sequence verification.
5. Perform small-scale expression and soluble fraction check.
6. Purify or normalize clarified lysate.
7. Run WT-referenced activity assay.
8. Run thermal challenge or DSF/Tm assay.
9. Add pH/temperature profile when process condition shift is the objective.
10. Record replicate, QC and plate/well-level feedback.
11. Combine mutants only after validated single-mutant evidence and epistasis
    review.
