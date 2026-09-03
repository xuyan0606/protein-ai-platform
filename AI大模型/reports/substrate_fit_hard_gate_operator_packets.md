# Substrate-Fit Hard-Gate Operator Packets

Generated: 2026-09-03T07:33:45.286239+00:00

These packets organize substrate_fit label/source review. They do not approve schema, source, or labels.

## Summary

- Packet rows: 13
- Action packets: 6
- Source packets: 7
- Ready candidate rows: 0
- Completion ready rows: 0
- Safe for model claim: false

## Sources

| source | artifact | observed | candidates | ready | blocker |
|---|---|---:|---:|---:|---|
| local_feedback_substrate_context | datasets/feedback/experiment_feedback.local.jsonl | 7 | 0 | 0 | context-only feedback is not a substrate_fit assay label unless assay_type, substrate identity, outcome, provenance, and numbering are reviewed. |
| plate_level_substrate_fit_intake | datasets/feedback/experiment_feedback_plate.local.jsonl | 0 | 0 | 0 | plate rows require assay_type=substrate_fit, substrate_smiles, reviewed status, usable QC, and raw signal. |
| wet_lab_metric_candidates | datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl | 445 | 0 | 0 | current wet-lab metric candidates are activity/stability focused; generic activity cannot be relabeled as substrate_fit. |
| wet_lab_authorization_worklist | datasets/feedback/wet_lab_mutant_library_feedback_authorization_worklist.jsonl | 12 | 0 | 0 | authorization is metric-level and currently contains no approved substrate_fit metric rows. |
| substrate_fit_benchmark_scorecards | reports/benchmark_score_cache_manifest.json | 3 | 0 | 0 | benchmarks validate model claims; they are not KWB training labels and substrate_fit scorecards are not present. |
| substrate_relevant_feature_adapters | reports/advanced_feature_cache_manifest.json | 3 | 0 | 0 | feature/proxy adapters can provide evidence after gates, but cannot be promoted into supervised substrate_fit labels. |
| external_license_and_use_gates | reports/external_license_review_decision_validation_report.json | 19 | 0 | 0 | external substrate/function/ligand sources remain blocked without explicit human/legal decisions. |

## Policy

Fail-closed substrate-fit operator packets only. They do not define an approved schema, approve external sources, convert activity/benchmark/proxy rows into labels, write training rows, train models, unlock model claims, deploy services, sync production, or release artifacts.
