# WF-EXPRESSION 表达目标专用流程

## 适用范围

适用于表达量、可溶性、折叠、分泌、聚集倾向和宿主适配等目标。

## 必须先明确

- 宿主和表达系统。
- 表达评价：总表达量、可溶性比例、活性蛋白比例、分泌量或聚集量。
- 标签、信号肽、前导肽和构建边界。
- 必须保持的催化活性、稳定性和特异性。
- 序列、结构、现有表达数据和失败表型。

输入遵循 `references/input_policy.md`：允许用户自然语言、段落、附件输入，先抽取已知信息。只有完全无法判断主目标或没有任何序列/参考编号这类阻断路由的硬缺口才返回 `NEEDS_INPUT`；其余缺口先记录并继续。

## 流程图

```text
表达目标
  -> EX-01 目标和输入门控
  -> EX-02 工具能力检查
  -> EX-03 身份和构建边界确认
  -> EX-04 表达瓶颈确认
  -> EX-05 表达候选设计
  -> EX-06 候选排序
  +-> EX-07 信号肽分析（要求分泌时）
  +-> EX-08 结构折叠分析（需要时）
  +-> EX-09 活性/稳定性保持检查（声明约束时）
  -> EX-10 证据闸门
  -> EX-11 输出候选和验证建议
```

## 步骤—工具组总表

| 步骤 | 任务 | 首选工具 | 直接替补 | 降级替补/条件工具 |
|---|---|---|---|---|
| EX-01 | 输入盘点与用户确认 | 内部 `intake_review`（非平台工具） | 无 | 首轮输出缺口并等待用户确认 |
| EX-02 | 工具能力检查 | `tool_capability_audit` | 无 | 无；失败即 `NEEDS_REVIEW` |
| EX-03 | 身份和构建边界 | `enzyme_identity_profile` | 无 | `sequence_search`、`lookup_protein`、`annotation_bundle`；`residue_numbering_gate` 必须补充 |
| EX-04 | 表达瓶颈确认 | `predict_properties` | 无 | `get_stability_data`、`annotation_bundle`、`literature_live_search` |
| EX-05 | 表达候选设计 | `soluble_mpnn_design` | 无 | `proteinmpnn_design`、`esm_if1_design`（条件）；`mutation_scan` + `mutation_priority_score`（降级） |
| EX-06 | 候选排序 | `mutation_priority_score` | 无 | `protssn_score`、`esm1v_predict`、`esm2_predict` |
| EX-07 | 信号肽分析 | `signal_peptide_predict` | 无 | 无；失败即 `blocked` |
| EX-08 | 结构折叠分析 | `esmfold_folding`、`alphafold_folding`、`rosettafold_folding`、`rosettafold_allatom`、`structure_search_foldseek` | 无 | 无；按条件启用 |
| EX-09 | 活性/稳定性保持 | `catalytic_site_lookup`、`kcat_predict`、`get_kinetic_params`、`rosetta_ddg`、`get_stability_data` | 无 | `enzyme_function` 只能作活性线索 |
| EX-10 | 证据闸门 | `scientific_claim_gate` | 无 | 无；失败即 `NEEDS_REVIEW` |

替补的详细等级和切换规则见 `references/tool_fallback_matrix.md`。

## 工具级步骤

### EX-01 输入盘点与用户确认

- **状态**：`MUST`
- **执行方式**：内部 `intake_review`，不调用平台工具。
- **首轮输出**：已收到的宿主、表达指标、序列/结构、构建边界和失败表型；缺口等级、影响和建议补充项。
- **用户动作**：等待用户补充，或明确“按现有信息继续”。确认后再调用 `enzyme_objective_module_plan`。
- **阻断**：主目标无法判断，或没有序列、结构或可追溯参考对象；宿主、表达指标和构建边界缺失时先提示，不自动结束任务。

### EX-02 工具能力检查

- **状态**：`MUST`
- **工具**：`tool_capability_audit`
- **规则**：明确哪些结果是表达预测，哪些是实验数据；不能把可溶性评分写成实测可溶性。

### EX-03 身份和构建边界确认

- **状态**：`MUST`
- **首选工具**：`enzyme_identity_profile`
- **直接替补**：无
- **降级替补**：`sequence_search`、`lookup_protein`、`annotation_bundle`
- **必须补充**：`residue_numbering_gate`
- **切换条件**：首选工具失败时，降级组只能建立身份候选；构建边界和保护位点仍必须通过编号门控。
- **输出**：目标序列、成熟链、催化残基、固定区域、标签/信号肽边界。

### EX-04 表达瓶颈确认

- **状态**：`MUST`
- **首选工具**：`predict_properties`
- **直接替补**：无
- **降级替补**：`get_stability_data`、`annotation_bundle`、`literature_live_search`
- **切换条件**：首选工具失败时，降级工具只能提供局部瓶颈线索；已有表达或稳定性数据必须保留测定条件和来源。
- **规则**：理化性质只能作为线索，不能直接当作表达实测。
- **输出**：聚集、折叠、表面性质、稳定性和构建设计风险。

### EX-05 表达候选设计

- **状态**：`MUST`
- **首选工具**：`soluble_mpnn_design`
- **直接替补**：无
- **条件替补**：`proteinmpnn_design`、`esm_if1_design`
- **降级替补**：`mutation_scan`、`mutation_priority_score`
- **切换条件**：首选工具失败时，优先用条件替补做结构约束设计；若仍不可用，降级组只允许保守筛选，不得扩大为全新序列生成。
- **调用条件**：有结构骨架且要做结构约束设计时，才调用 `proteinmpnn_design` 或 `esm_if1_design`。
- **规则**：固定催化残基和功能核心；不允许为提高可溶性任意改写催化中心。

### EX-06 候选排序

- **状态**：`MUST`
- **首选工具**：`mutation_priority_score`
- **直接替补**：无
- **降级替补**：`protssn_score`、`esm1v_predict`、`esm2_predict`
- **切换条件**：首选工具失败时，降级组只能提供辅助排序；必须保留表达目标、功能保持约束和冲突信息。
- **输出**：表达可行性排序、功能保持风险、候选序列和修改位置。

### EX-07 信号肽分析

- **状态**：`OPTIONAL`
- **工具**：`signal_peptide_predict`
- **触发条件**：用户明确要求分泌表达，或失败表型指向分泌/转运问题。
- **输出**：信号肽存在性、切割位点、置信度和候选边界。
- **跳过记录**：`non_secreted_expression`。

### EX-08 结构折叠分析

- **状态**：`OPTIONAL`
- **条件工具**：`esmfold_folding`、`alphafold_folding`、`rosettafold_folding`、`rosettafold_allatom`、`structure_search_foldseek`
- **触发条件**：没有可信结构，或需要检查候选是否保持整体折叠。
- **边界**：结构预测不能单独证明可溶性或表达量提高。

### EX-09 活性/稳定性保持检查

- **状态**：`OPTIONAL`
- **条件工具**：`catalytic_site_lookup`、`enzyme_function`、`kcat_predict`、`get_kinetic_params`、`rosetta_ddg`、`get_stability_data`
- **触发条件**：用户明确要求表达提高但活性或稳定性不能下降。
- **规则**：表达是主目标，活性/稳定性工具只能做约束。

### EX-10 证据闸门

- **状态**：`MUST`
- **工具**：`scientific_claim_gate`
- **规则**：没有表达实验数据时，只能写“表达候选/预测”，不能写“表达量已提高”。

### EX-11 输出候选和验证建议

- **状态**：`MUST`
- **输出**：候选序列、修改位点、宿主和构建条件、排序依据、功能风险、WT 对照和表达验证方案。

## 禁用工具

默认禁用：`rfdiffusion_design`、`chroma_design`、`progen2_generate`、`evodiff_generate`、`esm3_generate`、`diffdock_docking`、`gromacs_md`。

原因：从头骨架、配体对接和分子动力学不是表达主流程的默认步骤。

## 最小工具链

```text
intake_review
 -> user_confirmation
 -> enzyme_objective_module_plan
 -> tool_capability_audit
 -> enzyme_identity_profile
 -> predict_properties
 -> soluble_mpnn_design
 -> mutation_priority_score
 -> scientific_claim_gate
```
