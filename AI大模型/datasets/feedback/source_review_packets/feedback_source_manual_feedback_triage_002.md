# feedback_source_manual_feedback_triage_002

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_manual_feedback_triage_002.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | manual_feedback_triage | 90 | .md | 4136 | AI酶工程平台三层架构_交付包_v2_20260827/03_执行控制层/enzyme-property-workflow-router/references/input_policy.md | assay, ph, 实验, 底物, 活性, 温度, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | manual_feedback_triage | 90 | .md | 8154 | AI酶工程平台三层架构_交付包_v2_20260827/03_执行控制层/enzyme-property-workflow-router/references/specificity_workflow.md | ddg, mutation, stability, substrate, 实验, 底物, 活性, 稳定, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | manual_feedback_triage | 90 | .json | 2466 | backend/tests/property_workflow_shadow_cases.json | activity, expression, ph, stability, 底物, 活性, 热稳定, 稳定, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 4 | manual_feedback_triage | 90 | .md | 4776 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/16B-database-提高稳定性与比活力/00_先看这个_数据库使用说明.md | activity, expression, mutant, stability, 实验, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 5 | manual_feedback_triage | 80 | .md | 7672 | AI酶工程平台三层架构_交付包_v2_20260827/03_执行控制层/enzyme-property-workflow-router/references/expression_workflow.md | ddg, expression, mutation, ph, stability, 实验, 活性, 稳定 | confirm_source_then_extract_or_keep_unvalidated |
| 6 | manual_feedback_triage | 80 | .md | 5594 | AI酶工程平台三层架构_交付包_v2_20260827/03_执行控制层/enzyme-property-workflow-router/references/strategy_bindings.md | activity, assay, expression, ph, screening, stability, substrate, 实验 | confirm_source_then_extract_or_keep_unvalidated |
| 7 | manual_feedback_triage | 80 | .md | 9039 | Fanzor无实验训练数据突变挖掘_深度学习方法论.md | ph, 实验, 底物, 活性, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 8 | manual_feedback_triage | 80 | .json | 3307 | backend/tests/enzyme_agent_eval_cases.json | mutation, stability, 实验, 活性, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 9 | manual_feedback_triage | 80 | .md | 12127 | docs/manuals/2026-07-10-daily-report.md | mutant, mutation, tm, 实验, 活性, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 10 | manual_feedback_triage | 80 | .csv | 36267 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/15B_database-提高低pH条件下酶活及稳定性/03_相对2A派生分析表.csv | activity, ph, stability, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 11 | manual_feedback_triage | 80 | .csv | 79479 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/15B_database-提高低pH条件下酶活及稳定性/04_原始测量事实表.csv | activity, ph, stability, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 12 | manual_feedback_triage | 80 | .csv | 23419 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/16B-database-提高稳定性与比活力/04_原始测量事实表.csv | activity, assay, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 13 | manual_feedback_triage | 70 | .md | 9169 | AI酶工程平台三层架构_交付包_v2_20260827/02_路由层/三层文件工具名对齐与IT交接清单_20260826.md | ddg, mutation, ph, stability, 实验, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 14 | manual_feedback_triage | 70 | .md | 11696 | docs/superpowers/plans/2026-09-03-kwb-five-head-training-upgrade.md | activity, assay, ddg, ph, tm, 实验, 突变 | confirm_source_then_extract_or_keep_unvalidated |
| 15 | manual_feedback_triage | 70 | .csv | 3634 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/15B_database-提高低pH条件下酶活及稳定性/01_突变体总体判断总表.csv | activity, ph, stability, 实验, 突变 | confirm_source_then_extract_or_keep_unvalidated |
| 16 | manual_feedback_triage | 70 | .csv | 5443 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/16B-database-提高稳定性与比活力/01_突变体总体判断总表.csv | activity, expression, stability, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 17 | manual_feedback_triage | 60 | .txt | 1053 | Venus-15B淀粉酶项目/淀粉酶背景.txt | ph, 实验, 活性, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 18 | manual_feedback_triage | 60 | .json | 33252 | docs/manuals/release-worktree-manifest-2026-08-17.json | mutation, ph, tm, 实验, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 19 | manual_feedback_triage | 60 | .md | 6611 | docs/superpowers/plans/2026-09-01-enzyme-platform-remediation-wave.md | activity, expression, ph, 实验, 活性, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 20 | manual_feedback_triage | 60 | .md | 4849 | docs/superpowers/plans/2026-09-01-enzyme-workflow-enforcement-p0.md | activity, expression, ph, stability, 实验, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 21 | manual_feedback_triage | 60 | .md | 3127 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/16B-database-提高稳定性与比活力/给IT的数据交付说明.md | activity, expression, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 22 | manual_feedback_triage | 60 | .csv | 156838 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/4G_database-提高比活力/04_原始测量事实表.csv | activity, assay, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 23 | manual_feedback_triage | 50 | .md | 6406 | AI酶工程平台三层架构_交付包_v2_20260827/02_路由层/待接入能力说明与IT对接API清单_20260826.md | ddg, ph, 活性, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 24 | manual_feedback_triage | 50 | .md | 11403 | docs/superpowers/specs/2026-08-26-gelu-only-preregistered-pretraining-design.md | 实验, 活性, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 25 | manual_feedback_triage | 50 | .md | 6931 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/15B_database-提高低pH条件下酶活及稳定性/给IT的数据交付说明.md | 实验, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
