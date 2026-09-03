# Five-Head Benchmark Gap Plan

## Status

- Status: `blocked`
- Required benchmarks: `15`
- Acquisition-configured benchmarks: `12`
- Cache-validated benchmarks: `13`
- Missing cache validation: `2`
- Heads with complete scorecards: `3/5`
- Ready for model claim: `False`
- Safe for model claim: `False`
- Release ready: `False`

## Head Gaps

| Head | Required | Configured | Cache-valid | Download/cache | License | Human acceptance | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| mutation_rank | 3 | 1 | 2 | 1 | 1 | 2 | blocked |
| stability | 3 | 3 | 3 | 0 | 0 | 0 | ready |
| activity_risk | 3 | 3 | 3 | 0 | 0 | 0 | ready |
| substrate_fit | 3 | 2 | 2 | 1 | 1 | 1 | blocked |
| assay_success | 3 | 3 | 3 | 0 | 0 | 0 | ready |

## Metrics That Cannot Be Declared

- `mutation_rank`: mutation-rank benchmark scorecard, mutation ranking quality or Spearman/AUROC claim; blockers: acquisition_status:not_configured, benchmark dataset is not configured locally, benchmark_status_not_present, external predicted/reference data cannot substitute for wet-lab labels, head is not training-ready with reviewed labels, head_training_readiness_false.
- `stability`: stability benchmark scorecard, deltaTm/ddG stability prediction quality claim; blockers: benchmark dataset is not configured locally, external predicted/reference data cannot substitute for wet-lab labels, head is not training-ready with reviewed labels, head_training_readiness_false.
- `activity_risk`: activity-risk benchmark scorecard, activity retention or activity-risk calibration claim; blockers: benchmark dataset is not configured locally, external predicted/reference data cannot substitute for wet-lab labels, head is not training-ready with reviewed labels, head_training_readiness_false.
- `substrate_fit`: substrate-fit benchmark scorecard, substrate affinity, pose, or fit quality claim; blockers: acquisition_status:not_configured, benchmark dataset is not configured locally, benchmark_status_not_present, external predicted/reference data cannot substitute for wet-lab labels, head is not training-ready with reviewed labels, head_training_readiness_false.
- `assay_success`: assay-success benchmark scorecard, plate/QC success-rate prediction quality claim; blockers: benchmark dataset is not configured locally, external predicted/reference data cannot substitute for wet-lab labels, head is not training-ready with reviewed labels, head_training_readiness_false.

## Required Follow-Up

- `mutation_rank`: download/cache `1`, license/authorize `1`, human-accept `2`; do not treat this plan as approval or release evidence.
- `stability`: download/cache `0`, license/authorize `0`, human-accept `0`; do not treat this plan as approval or release evidence.
- `activity_risk`: download/cache `0`, license/authorize `0`, human-accept `0`; do not treat this plan as approval or release evidence.
- `substrate_fit`: download/cache `1`, license/authorize `1`, human-accept `1`; do not treat this plan as approval or release evidence.
- `assay_success`: download/cache `0`, license/authorize `0`, human-accept `0`; do not treat this plan as approval or release evidence.

## Policy

Fail closed: this benchmark gap plan remains blocked unless all five canonical heads have every required benchmark cache-validated, locally checksummed, license-reviewed, leakage-checked, human-accepted, and all source reports agree. It is an evaluation planning artifact only and never grants approval, a model claim, a training import, or release readiness.

Inputs are read-only reports and plan rows. This plan does not download data, approve a benchmark, run a model, change a manifest, or loosen any claim or release gate.
