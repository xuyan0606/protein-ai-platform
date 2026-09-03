# Wet-Lab Head Authorization Gap Plan

Generated: 2026-09-03T07:33:44.719852+00:00

Fail-closed executor plan only. It neither writes human authorization decisions nor imports training labels.

## Current State

- Worklist actions: 12
- Authorization rows / authorized candidates: 8 / 8
- Preflight rows / apply-plan rows / applied rows: 8 / 8 / 0
- Safe for training import: false

## Head Paths

| head | candidates | current rows | missing to minimum | schema gap |
|---|---:|---:|---:|---|
| activity_risk | 9 | 6 | 94 | Current head contract also requires activity_risk_label. This plan does not derive that label from the wet-lab ratio. |
| stability | 3 | 0 | 100 | Current head contract expects label_stability_delta_tm_c or label_ddg. An 85C/3min relative-retention metric is not automatically converted to either target. |

## Per-Metric Actions

| order | variant | metric | head | outcome | ratio | priority | missing authorization fields |
|---:|---|---|---|---|---:|---|---|
| 1 | E331Q | pH4.8绝对酶活(U/mL) | activity_risk | watch | 1.07315 | critical_tradeoff_review | authorization_decision_row, authorization_decision, qc_decision, reviewer, reviewed_at, authorization_basis, source_trace_reviewed, numbering_reviewed, unit_condition_reviewed, batch_control_reviewed, replicate_policy_reviewed |
| 2 | E331Q | pH6.0绝对酶活(U/mL) | activity_risk | watch | 0.756963 | critical_tradeoff_review | authorization_decision_row, authorization_decision, qc_decision, reviewer, reviewed_at, authorization_basis, source_trace_reviewed, numbering_reviewed, unit_condition_reviewed, batch_control_reviewed, replicate_policy_reviewed |
| 3 | E331Q | 热稳定性_85C_3min(%) | stability | no_go | 0.607477 | critical_tradeoff_review | authorization_decision_row, authorization_decision, qc_decision, reviewer, reviewed_at, authorization_basis, source_trace_reviewed, numbering_reviewed, unit_condition_reviewed, batch_control_reviewed, replicate_policy_reviewed |
| 4 | E331Q | 酸性保持率_pH4.8/pH6.0(%) | activity_risk | go | 1.40816 | critical_tradeoff_review | authorization_decision_row, authorization_decision, qc_decision, reviewer, reviewed_at, authorization_basis, source_trace_reviewed, numbering_reviewed, unit_condition_reviewed, batch_control_reviewed, replicate_policy_reviewed |
| 5 | D105N | pH4.8绝对酶活(U/mL) | activity_risk | go | 1.39444 | medium_mixed_benefit_review |  |
| 6 | D105N | pH6.0绝对酶活(U/mL) | activity_risk | go | 1.15004 | medium_mixed_benefit_review |  |
| 7 | D105N | 热稳定性_85C_3min(%) | stability | watch | 1.04673 | medium_mixed_benefit_review |  |
| 8 | D105N | 酸性保持率_pH4.8/pH6.0(%) | activity_risk | go | 1.20408 | medium_mixed_benefit_review |  |
| 9 | S265T | pH4.8绝对酶活(U/mL) | activity_risk | watch | 1.01759 | standard_multi_property_review |  |
| 10 | S265T | pH6.0绝对酶活(U/mL) | activity_risk | watch | 0.961366 | standard_multi_property_review |  |
| 11 | S265T | 热稳定性_85C_3min(%) | stability | watch | 0.757009 | standard_multi_property_review |  |
| 12 | S265T | 酸性保持率_pH4.8/pH6.0(%) | activity_risk | watch | 1.04082 | standard_multi_property_review |  |

## Human Authorization Contract

- Each metric is independent. Choose one of `approved_for_feedback_intake`, `rejected`, or `needs_more_info`; this plan does not select one.
- An approval requires QC pass/pass-with-conditions, five completed review flags, reviewer, timestamp, and basis. `allow_append_to_experiment_feedback_local` remains `false`.
- After a valid decision, run the authorization validator, preflight builder, and apply-plan builder. A separate explicit apply action and a separate reviewed head-target mapping remain required.

## Guardrails

- Activity metrics can become feedback evidence for `activity_risk`, but `activity_risk_label` is still not derived here.
- The 85C/3min thermal metrics can become feedback evidence for `stability`, but they are not automatically translated into `label_stability_delta_tm_c` or `label_ddg`.
- None of these actions changes a training table, head row count, model claim, safe pipeline, or manifest.
