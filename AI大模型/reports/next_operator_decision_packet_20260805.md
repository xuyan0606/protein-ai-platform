# Next Operator Decision Packet - 2026-08-05

Scope: local-only operator packet. This file does not approve, reject, unlock,
train, release, deliver, or change any model claim.

## 1. Benchmark Decisions

### KWB strict mutation holdout

- Review packets: `datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl`
- Formal decisions: `datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl`
- Template: `datasets/curation/kwb_venus15b_strict_holdout_review_decisions.template.jsonl`
- Current packet rows: 3
- Candidate review keys:
  - `kwb_venus15b_strict_candidate::D105N`
  - `kwb_venus15b_strict_candidate::E331Q`
  - `kwb_venus15b_strict_candidate::S265T`
- Allowed decisions:
  - `approve_strict_holdout`
  - `reject_candidate`
  - `needs_more_info`
- Required checks before approval:
  - real Venus-15B wet-lab result, not design/prediction
  - sequence position, PDB chain A position, and WT residue match
  - measurement, batch/control, unit, and assay condition reviewed
  - no training/benchmark leakage
  - reviewer, reviewed_at, review_basis, and acceptance_receipt recorded

### Reviewed substrate identity set

- Review packets: `datasets/curation/substrate_identity_review_packets.jsonl`
- Formal decisions: `datasets/curation/substrate_identity_review_decisions.jsonl`
- Template: `datasets/curation/substrate_identity_review_decisions.template.jsonl`
- Current packet rows: 9
- Normalized identities observed:
  - `starch_slurry`
  - `corn_whole_flour`
- Allowed decisions:
  - `approve_reviewed_substrate_identity`
  - `reject_substrate_identity`
  - `needs_more_info`
- Required checks before approval:
  - source text explicitly names the substrate or process substrate
  - representation type confirmed as mixture/process substrate when applicable
  - no invented single-molecule SMILES for process mixtures
  - pH/temperature/time/protocol scope reviewed
  - suitability for substrate_fit evaluation or label semantics recorded

## 2. Release / Claim Decisions

### Model-quality first blockers

- Numbering decisions: `datasets/curation/numbering_curation_decisions.jsonl`
  - Current milestone state from reports: 4 valid reviewed rows, 96 more needed for the 100-row model-claim milestone.
- Plate feedback: `datasets/feedback/experiment_feedback_plate.local.jsonl`
  - Current model-quality state: plate training eligible rows are 0.

### Governance decisions

- External license decisions: `datasets/governance/external_license_review_decisions.jsonl`
- Biosecurity decisions: `datasets/governance/biosecurity_screening_decisions.jsonl`
- Sequence IP/FTO decisions: `datasets/governance/sequence_ip_fto_decisions.jsonl`
- Workstream acceptance: `datasets/governance/workstream_acceptance_decisions.jsonl`
- Operator action completion: `datasets/governance/operator_review_action_decisions.jsonl`

Current report evidence:

- `reports/operator_review_status_report.json`
  - external license customer-delivery approval rows: 0
  - biosecurity decision rows: 0
  - workstream acceptance: 0/6
  - operator action completion: 0/6
- `reports/local_release_manifest_fail_closed_consistency_validation_report.json`
- `reports/claim_readiness_matrix_fail_closed_policy_validation_report.json`
- `reports/model_artifact_claim_guard_validation_report.json`
- `reports/local_release_guard_coverage_validation_report.json`
- `reports/local_release_safety_guard_link_validation_report.json`
- `reports/report_positive_claim_gate_quarantine_validation_report.json`
- `reports/human_decision_backlog_report.json`
  - open items: 11
  - missing rows: 1188

## 3. Validation Order After Decisions

Run only after the corresponding formal decision files are populated.

Benchmark hard-gate packet and bridge validation:

```bash
cd AI大模型
python3 scripts/build_benchmark_acquisition_plan.py
python3 scripts/build_benchmark_matrix_report.py
python3 scripts/build_benchmark_coverage_dashboard.py
python3 scripts/validate_benchmark_coverage_dashboard.py
python3 scripts/build_hard_gate_review_packets.py
python3 scripts/validate_hard_gate_review_packets.py
python3 scripts/build_benchmark_hard_gate_operator_packets.py
python3 scripts/build_hard_gate_decision_benchmark_bridge.py
python3 scripts/validate_hard_gate_decision_benchmark_bridge.py
python3 scripts/build_benchmark_readiness_packet.py
python3 scripts/validate_benchmark_readiness_packet.py
```

Related benchmark evidence:

- `reports/benchmark_acquisition_plan_report.json`
- `reports/benchmark_matrix_report.json`
- `reports/benchmark_coverage_dashboard.json`
- `reports/benchmark_coverage_dashboard_validation_report.json`
- `reports/benchmark_score_cache_manifest.json`
- `reports/benchmark_score_cache_validation_report.json`
- `reports/hard_gate_decision_benchmark_bridge_report.json`
- `reports/hard_gate_decision_benchmark_bridge_validation_report.json`
- `reports/benchmark_readiness_packet_report.json`
- `reports/benchmark_readiness_packet_validation_report.json`
- `reports/benchmark_readiness_packets.md`
- `reports/benchmark_hard_gate_operator_packets.md`

The bridge step is required because formal hard-gate decisions do not directly become benchmark score-cache artifacts. Only complete formal decisions with receipts may flow through the bridge into benchmark intake.

Governance and release validation:

```bash
cd AI大模型
python3 scripts/validate_numbering_curation_decisions.py
python3 scripts/validate_external_license_review_decisions.py
python3 scripts/validate_biosecurity_screening_decisions.py
python3 scripts/validate_sequence_ip_fto_decisions.py
python3 scripts/validate_workstream_acceptance_decisions.py
python3 scripts/validate_operator_review_action_decisions.py
python3 scripts/validate_model_artifact_claim_guard_report.py
python3 scripts/validate_local_release_guard_coverage.py
python3 scripts/validate_local_release_safety_guard_links.py
python3 scripts/validate_report_positive_claim_gate_quarantine.py
python3 scripts/validate_claim_readiness_matrix_fail_closed_policy.py
python3 scripts/validate_local_release_manifest_fail_closed_consistency.py
```

Benchmark refresh should only happen after formal benchmark decisions exist:

```bash
cd AI大模型
python3 scripts/validate_no_review_draft_training_leakage.py
python3 scripts/validate_benchmark_score_cache.py
```

## 4. Non-Bypass Rules

- Do not copy template rows into formal decisions as approvals.
- Do not use draft packets as reviewed decisions.
- Do not invent SMILES for `starch_slurry` or `corn_whole_flour`.
- Do not promote PyRosetta/Rosetta smoke results to training labels.
- Do not mark `safe_for_model_claim`, `customer_ready`, or `release_ready` true from this packet.
