# Strategy-to-Workflow Bindings

> 作用：把科学策略层 `strategy_id` 绑定到唯一 `workflow_id`、路由表步骤、执行器步骤、必须输入和禁止动作。

## 绑定原则

1. 一个 `strategy_id` 只能归属一个主 `workflow_id`。
2. `route_step_ids` 对齐旧 CSV 的阶段编号：`T/A/P/E/S`。
3. `executor_step_ids` 对齐 Skill 专用流程文件的执行编号：`ST/ACT/P/E/S`。
4. `pH` 独立成主线，不再挂在 `stability` 下。
5. 任何 `monitor_only` 性质不得自动升级为优化目标。
6. 绑定表只做编译中间层，不替代实验结论。

## 双编号绑定表

| strategy_id | property | workflow_id | route_step_ids | executor_step_ids | required_inputs | forbidden_when |
|---|---|---|---|---|---|---|
| STAB-CONSENSUS-01 | stability | WF-STABILITY | T2,T3,T4,T5 | ST-03,ST-04,ST-05,ST-06,ST-07,ST-11,ST-12 | homolog_msa,numbering_mapping,target_sequence | no_homologs,numbering_unclear,protected_region |
| STAB-ENERGY-01 | stability | WF-STABILITY | T2,T3,T4,T5 | ST-03,ST-05,ST-07,ST-09,ST-11,ST-12 | untrusted_structure,unclear_numbering,no_runtime_artifact |
| STAB-FLEX-01 | stability | WF-STABILITY | T2,T3,T4,T6 | ST-04,ST-07,ST-09,ST-10,ST-11,ST-12 | flexible_region_near_catalytic_channel |
| STAB-NETWORK-01 | stability | WF-STABILITY | T2,T3,T4 | ST-03,ST-05,ST-07,ST-11,ST-12 | geometry_not_supported,host_redox_incompatible |
| STAB-DIRECTED-01 | stability | WF-STABILITY | T1,T3,T6 | ST-04,ST-06,ST-07,ST-08,ST-11,ST-12 | no_screening_system |
| PH-PKA-01 | pH | WF-PH | P1,P2,P3,P4 | P-03,P-04,P-05,P-06,P-07,P-10,P-11,P-12 | catalytic_geometry_unconfirmed,no_complete_pH_curve |
| PH-NEAR-01 | pH | WF-PH | P1,P2,P3,P4 | P-03,P-04,P-05,P-06,P-07,P-10,P-11,P-12 | surface_pI_only,no_catalytic_context |
| PH-SURFACE-01 | pH | WF-PH | P1,P2,P3,P4 | P-04,P-05,P-06,P-07,P-10,P-11,P-12 | catalytic_site_redesign_only,aggregation_unchecked |
| PH-HOST-01 | pH | WF-PH | P1,P2,P4 | P-02,P-04,P-08,P-11,P-12 | bacterial_host_with_eukaryotic_glycosylation_assumption,unclear_construct |
| ACT-CATALYTIC-01 | activity | WF-ACTIVITY | A1,A2,A3,A4,A5,A6,A7 | ACT-01,ACT-03,ACT-04,ACT-05,ACT-06,ACT-07,ACT-08,ACT-11,ACT-12 | substrate,catalytic_residues,assay_context | substrate_undefined,no_protein_normalization |
| ACT-CHANNEL-01 | activity | WF-ACTIVITY | A2,A3,A4,A5,A6,A7 | ACT-05,ACT-06,ACT-07,ACT-08,ACT-09,ACT-11,ACT-12 | structure,substrate,assay_context | no_structure_or_complex_evidence |
| ACT-COMPLEX-01 | activity | WF-ACTIVITY | A3,A4,A5,A6,A7 | ACT-04,ACT-05,ACT-06,ACT-07,ACT-08,ACT-09,ACT-11,ACT-12 | complex_structure,substrate_pose,screening_system | no_complex,no_screening_system |
| EXP-SIGNAL-01 | expression | WF-EXPRESSION | E1,E2,E4 | EXP-01,EXP-02,EXP-04 | host,signal_peptide,mature_chain | cleavage_boundary_unclear |
| EXP-FOLD-01 | expression | WF-EXPRESSION | E1,E3,E4 | EXP-01,EXP-03,EXP-04 | soluble_or_expression_profile,construct_sequence | bottleneck_not_folding_or_aggregation |
| EXP-HOST-01 | expression | WF-EXPRESSION | E1,E3,E4 | EXP-01,EXP-03,EXP-04 | host_pathway,protease_profile | no_host_engineering_system |
| EXP-GLYCOSYLATION-01 | expression | WF-EXPRESSION | E2,E4 | EXP-02,EXP-04 | host,construct_sequence,glycosylation_site_candidates | non_eukaryotic_host,unclear_construct_boundary |
| SPEC-POCKET-01 | specificity | WF-SPECIFICITY | S1,S2,S4,S5 | SPEC-01,SPEC-02,SPEC-04,SPEC-05 | target_substrate,competing_substrate,structure | no_competing_substrate |
| SPEC-CHANNEL-01 | specificity | WF-SPECIFICITY | S1,S2,S4,S5 | SPEC-01,SPEC-02,SPEC-04,SPEC-05 | substrate,structure_or_complex | no_structure_or_entry_path_evidence |
| SPEC-COMPLEX-01 | specificity | WF-SPECIFICITY | S2,S3,S4,S5 | SPEC-02,SPEC-03,SPEC-04,SPEC-05 | complex_or_transition_state_model,screening_system | no_complex,no_screening_system |
| ACT-ML-01 | activity | WF-ACTIVITY | A2,A3,A4,A5,A6,A7 | ACT-03,ACT-05,ACT-06,ACT-07,ACT-11,ACT-12 | target_sequence,family_or_training_data,assay_context | no_model_applicability,no_target_sequence |
| EXP-SOLUBLE-01 | expression | WF-EXPRESSION | E1,E3,E4 | EXP-01,EXP-03,EXP-04,EXP-05,EXP-06,EXP-10,EXP-11 | construct_sequence,host,solubility_or_aggregation_profile | bottleneck_not_solubility_or_aggregation,unclear_construct_boundary |
| SPEC-ML-01 | specificity | WF-SPECIFICITY | S1,S2,S3,S4,S5 | SPEC-01,SPEC-02,SPEC-03,SPEC-04,SPEC-05,SPEC-06,SPEC-07,SPEC-11,SPEC-12 | target_substrate,competing_substrate,training_data_or_applicability | no_competing_substrate,no_model_applicability |

## 路由层消费方式

### 输入

- `primary_property`
- `secondary_properties`
- `preservation_constraints`
- `host_context`
- `available_inputs`
- `strategy_id`

### 输出

- `workflow_id`
- `route_step_ids`
- `executor_step_ids`
- `required_inputs`
- `forbidden_when`
- `validation_metrics`
- `route_reason`
- `route_confidence`

## 执行层规则

- 只允许执行绑定表里的 `executor_step_ids`。
- 路由记录同时保存 `route_step_ids`，便于与原 CSV 对账。
- 绑定表没写的策略动作，视为 `unplanned_action`。
- `pH` 策略只允许走 `WF-PH`。
- `stability` 不再吸收 pH 目标。
- 证据不足时直接输出缺口，不得用其他性质流程顶替。

## 推荐接线顺序

1. 科学策略层输出 `strategy_id`。
2. 路由层查 `strategy_bindings.md` 或对应 CSV。
3. 路由器选 `workflow_id` 和 `route_step_ids`。
4. 执行器转换为 `executor_step_ids` 并调用真实工具。
5. 记录工具、产物、替补级别和证据状态。
6. 证据闸门和 claim gate 做最终放行。
