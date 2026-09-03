# Substrate Fit Label Gap Plan

Generated: 2026-09-03T07:32:23.594682+00:00

This is a fail-closed audit scaffold. It does not import labels, run training, connect to the safe pipeline, or unlock model claims.

## Summary

- Status: blocked
- Current substrate_fit training rows: 0
- Minimum required rows: 100
- Ready candidate rows: 0
- Missing rows to minimum: 100
- Safe for model claim: false

## Candidate Sources

| source | observed | candidates | ready | status | blocker |
|---|---:|---:|---:|---|---|
| local_feedback_substrate_context | 7 | 0 | 0 | blocked | context-only feedback is not a substrate_fit assay label unless assay_type, substrate identity, outcome, provenance, and numbering are reviewed. |
| plate_level_substrate_fit_intake | 0 | 0 | 0 | blocked | plate rows require assay_type=substrate_fit, substrate_smiles, reviewed status, usable QC, and raw signal. |
| wet_lab_metric_candidates | 445 | 0 | 0 | blocked | current wet-lab metric candidates are activity/stability focused; generic activity cannot be relabeled as substrate_fit. |
| wet_lab_authorization_worklist | 12 | 0 | 0 | blocked | authorization is metric-level and currently contains no approved substrate_fit metric rows. |
| substrate_fit_benchmark_scorecards | 3 | 0 | 0 | blocked | benchmarks validate model claims; they are not KWB training labels and substrate_fit scorecards are not present. |
| substrate_relevant_feature_adapters | 3 | 0 | 0 | blocked | feature/proxy adapters can provide evidence after gates, but cannot be promoted into supervised substrate_fit labels. |
| external_license_and_use_gates | 19 | 0 | 0 | blocked | external substrate/function/ligand sources remain blocked without explicit human/legal decisions. |

## Forbidden Shortcuts

| shortcut | observed | allowed | reason |
|---|---:|---|---|
| generic_activity_to_substrate_fit | 1 | false | activity with a substrate context is not a substrate-fit label without an explicit substrate_fit assay definition. |
| activity_or_stability_metric_relabel | 12 | false | numeric activity/stability candidates cannot be reinterpreted as substrate selectivity or fit. |
| benchmark_dataset_as_training_label | 3 | false | PDBbind/CASF/D3R/PoseBusters-style assets are evaluation gates, not KWB supervised labels. |
| affinity_or_pose_prediction_as_ground_truth | 3 | false | Boltz/Chai/AlphaFold-style complex or affinity predictions may become features only after gates. |
| function_or_ec_proxy_as_substrate_fit | 3 | false | CatPred/CLEAN/EC-style function proxies do not supply substrate-fit labels. |
| license_inference | 8 | false | missing external source/tool decisions must remain blocked and cannot be inferred from availability. |
| model_claim_unlock | 0 | false | current labels, candidates, benchmark scorecards, and legal gates do not permit a substrate_fit model claim. |

## Actions

| action | priority | blocker | training unlocked | model claim |
|---|---|---|---|---|
| substrate-fit-label-schema-p0 | P0 | no approved substrate_fit label schema/source | false | false |
| audit-existing-feedback-context-p0 | P0 | context-only rows are not substrate_fit labels | false | false |
| build-substrate-fit-plate-intake-p0 | P0 | no reviewed plate-level substrate_fit rows | false | false |
| separate-proxies-from-labels-p0 | P0 | proxy rows are not supervised substrate_fit ground truth | false | false |
| external-substrate-source-legal-p1 | P1 | missing substrate-relevant legal/source decisions | false | false |
| substrate-fit-claim-remains-locked-p0 | P0 | label gap and evaluation scorecard gap both remain open | false | false |

## Policy

Substrate_fit labels require explicit substrate identity, reviewed assay context, provenance, QC, and legal/use gates. This scaffold quantifies gaps only and never converts candidates, proxies, benchmarks, or context-only activity rows into labels.
