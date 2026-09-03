# KWB-EnzymeDesigner v2.0.0 Analysis Constraint Policy

## Purpose

This model card records a local-only analysis policy for enzyme engineering
requests. The policy makes property prediction, database fusion, important
mutation-site selection, ddG thresholding, Rosetta status disclosure, human
review and wet-lab workflow explicit.

## Capability Boundary

Allowed:

- Produce a structured tool plan before execution.
- Require user confirmation before running analysis tools.
- Rank mutation sites after input validation and numbering gates.
- Separate wet-lab, reviewed database, public database, prediction and weak
  evidence.
- Report ddG sign convention and thresholds.
- Provide a wet-lab validation workflow.

Forbidden:

- Claim Rosetta/PyRosetta/FoldX ddG execution in this local pipeline.
- Promote weak evidence to training labels.
- Convert model output into experiment feedback.
- Recommend order-ready sequences without governance, IP/FTO and biosecurity
  review.
- Project residue positions onto structures without numbering confirmation.

## Tool Flow

Default visible flow:

`predict_properties -> annotation_bundle -> structure_search_foldseek -> residue_mapping_sifts -> residue_numbering_gate -> mutation_priority_score -> mutation_epistasis_check`

`gromacs_md` is optional and asynchronous. It requires reviewed parameters,
runtime availability, topology readiness, user confirmation and task audit.

## ddG Policy

Negative ΔΔG is interpreted as more stable; positive ΔΔG as less stable.

- `< -1.0 kcal/mol`: stabilizing hypothesis
- `-1.0` to `+1.0 kcal/mol`: neutral/manual review
- `> +1.0` to `+2.0 kcal/mol`: Watch/manual review
- `> +2.0 kcal/mol`: No-Go unless reviewed compensating evidence exists

## Release State

This policy improves analysis governance. It does not unblock model-quality
claims, customer delivery, Rosetta execution, wet-lab validation, MSA features
or supervised label readiness.
