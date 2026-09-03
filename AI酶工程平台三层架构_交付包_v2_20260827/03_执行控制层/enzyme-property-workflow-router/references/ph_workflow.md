# WF-PH pH/酸碱适应目标专用流程

## 适用范围

适用于以下独立目标：

- `pH_optimum`：最适 pH 移动。
- `target_pH_activity`：目标 pH 下活性提升。
- `pH_window`：pH 活性稳域拓宽。
- `pH_stability`：酸/碱暴露后的残余活性保持。
- `acid_base_tolerance`：工艺酸碱条件耐受。

`pH` 不是 `stability` 的默认别名。只有用户明确要求 pH 耐受或 pH 稳定性时，才可选择 `WF-PH`；普通热稳定性、半衰期、溶剂耐受和蛋白酶耐受仍走 `WF-STABILITY`。

## 必须先区分的目标

- 最适 pH 是否移动。
- 目标 pH 下初始活性是否提高。
- 暴露后残余活性是否提高。
- pH 活性曲线是否拓宽。
- 原最适区和比活力是否作为保持约束。

单点 pH 活性不能代替完整 pH-活性曲线，也不能单独证明 pH 稳定性。

## 流程图

```text
pH 目标
  -> P-01 目标和输入门控
  -> P-02 宿主、构建体和成熟链核验
  -> P-03 催化残基与编号确认
  -> P-04 pH 目标数据和基线确认
  -> P-05 pKa/电荷机制定位
  -> P-06 候选策略选择
  -> P-07 候选排序和保护区审查
  +-> P-08 宿主糖基化/加工干扰排查（真核分泌宿主时）
  +-> P-09 结构/静电/动力学补充（满足条件时）
  -> P-10 单点优先与组合审查
  -> P-11 完整 pH 曲线和稳定性验收
  -> P-12 证据闸门与输出
```

## 步骤—工具组总表

| 步骤 | 任务 | 首选工具 | 直接替补/降级工具 | 状态 |
|---|---|---|---|---|
| P-01 | 输入盘点与用户确认 | 内部 `intake_review`（非平台工具） | 无；首轮输出缺口并等待用户确认 | MUST |
| P-02 | 宿主、构建体和成熟链 | `enzyme_identity_profile`, `annotation_bundle` | `signal_peptide_predict`, `interpro_annotation` | MUST |
| P-03 | 催化残基与编号 | `catalytic_site_lookup`, `residue_numbering_gate` | `residue_mapping_sifts`, `enzyme_function` | MUST |
| P-04 | pH 数据与基线 | `get_kinetic_params`, `get_stability_data` | `literature_live_search`, `external_research_evidence` | MUST |
| P-05 | pKa/电荷机制定位 | `structure_search_foldseek`, `predict_properties` | `esmfold_folding`, `alphafold_folding`, `protssn_score` | MUST |
| P-06 | 候选策略选择 | `mutation_priority_score`, `mutation_scan` | `esm1v_predict`, `esm2_predict` | MUST |
| P-07 | 候选排序和保护区 | `residue_numbering_gate`, `mutation_priority_score` | `protssn_score`, `esm1v_predict` | MUST |
| P-08 | 宿主糖基化/加工排查 | `annotation_bundle`, `signal_peptide_predict` | `enzyme_identity_profile` | OPTIONAL |
| P-09 | 结构/静电/动力学补充 | `gromacs_md`, `rosetta_ddg`, `kcat_predict` | `structure_search_foldseek`, `predict_properties` | OPTIONAL |
| P-10 | 单点与组合审查 | `mutation_epistasis_check` | `feedback_iteration_planner` | MUST |
| P-11 | pH 曲线和稳定性验收 | `get_kinetic_params`, `get_stability_data` | `feedback_iteration_planner` | MUST |
| P-12 | 证据闸门与输出 | `scientific_claim_gate` | 无；失败即 `NEEDS_REVIEW` | MUST |

## 关键规则

### P-01 输入盘点与用户确认

- **执行方式**：内部 `intake_review`，不调用平台工具。
- 首轮列出已收到的目标 pH、pH 范围、底物、反应条件、序列/结构和 assay 信息，以及缺口等级和影响。
- 等待用户补充，或明确“按现有信息继续”。用户确认后，才进入 P-02 及后续性质分析。
- 主目标无法判断、或没有序列/结构/可追溯参考对象时等待补充；其他缺口不阻断首轮盘点。

### P-02 宿主和加工核验

- 真核分泌宿主必须检查信号肽、成熟链、潜在 N-X-S/T 基序和糖基化混杂。
- N-X-S/T 只能标记为潜在糖基化位点，不能直接断言实际糖基化。
- 芽孢杆菌表达不能套用毕赤酵母 N-糖基化逻辑。

### P-03 催化残基和编号

- 催化残基、金属/辅因子位点、底物锚定区和成熟链编号必须可追溯。
- 编号未通过时，只输出缺口报告，不输出坐标级突变。

### P-04 pH 数据基线

至少区分：

- 完整 pH-活性曲线。
- 目标 pH 相对活性。
- pH 暴露后的残余活性。
- `kcat`、`Km` 或 `kcat/Km`。
- WT 与突变体同条件对照。

### P-05 候选策略顺序

默认优先级：

1. `PH-NEAR-01`：催化位点邻近残基和第二壳层。
2. `PH-SURFACE-01`：远端表面电荷和长程静电，仅在目标包含稳域/耐受时启用。
3. `PH-HOST-01`：真核分泌宿主的糖基化和加工干扰排查。
4. `PH-PKA-01`：直接催化 pKa 调谐，高风险，必须单点、强证据和明确回退方案。

### P-07 保护区

默认保护：

- 催化残基本身。
- 金属/辅因子配位位点。
- 已确认的底物锚定位点。
- 编号、链或结构归属不清的区域。

### P-08 宿主干扰

仅当 `host_context` 为真核分泌宿主且存在潜在糖基化基序时触发。输出必须把酶本身 pH 机制与宿主加工效应分开。

### P-10 组合规则

- 先做单点，再做组合。
- 单点必须有完整 pH 曲线和稳定性护栏。
- 组合必须有结构距离、机制互补或实验反馈依据。
- 只有 proxy 分数、没有结构或实验解释时禁止组合。

## 禁用动作

- 将普通热稳定性任务自动路由为 `WF-PH`。
- 将表面 pI 变化直接解释成最适 pH 改变。
- 只按加正电/加负电批量推荐位点。
- 以单点 pH 活性代替完整 pH 曲线。
- 未确认催化几何就直接改催化残基。
- 将预测分数、对接姿态或计划输出写成实验验证。
- 将毕赤酵母糖基化结论外推到地衣芽孢杆菌。

## 最小工具链

```text
intake_review
 -> user_confirmation
 -> enzyme_objective_module_plan
 -> enzyme_identity_profile
 -> catalytic_site_lookup
 -> residue_numbering_gate
 -> get_kinetic_params
 -> structure_search_foldseek
 -> mutation_priority_score
 -> mutation_epistasis_check
 -> scientific_claim_gate
```

## 最终验收

至少报告：

- pH-活性完整曲线。
- 目标 pH 相对活性。
- pH 暴露后残余活性。
- `kcat`、`Km` 或 `kcat/Km`。
- 热稳定性或结构稳定性护栏。
- 宿主、糖基化、成熟链和编号证据。
- 每个候选的 `strategy_id`、`step_id`、证据等级和风险。

没有当前项目实验数据时，候选状态只能是 `hypothesis_only` 或 `computational_priority`，不得写成 `experimentally_supported`。
