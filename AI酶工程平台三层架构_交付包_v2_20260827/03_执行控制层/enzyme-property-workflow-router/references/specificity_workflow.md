# WF-SPECIFICITY 特异性目标专用流程

## 适用范围

适用于底物偏好、底物谱拓宽/收窄、区域选择性、立体选择性和副反应抑制等目标。

## 必须先明确

- 目标底物和非目标底物集合。
- 想提升的是哪种选择性：底物选择性、区域选择性、立体选择性或副产物抑制。
- 反应条件、辅因子和评价指标。
- 必须保持的活性、稳定性和表达约束。
- 序列、结构、底物结构和已有特异性数据。

输入遵循 `references/input_policy.md`：允许用户自然语言、段落、附件输入，先抽取已知信息。只有完全无法定义目标底物与非目标底物边界这类阻断设计的硬缺口才返回 `NEEDS_INPUT`；其余缺口先记录并继续。

## 流程图

```text
特异性目标
  -> SP-01 目标和输入门控
  -> SP-02 工具能力检查
  -> SP-03 身份和反应类型确认
  -> SP-04 目标/非目标底物确认
  -> SP-05 催化位点和结合位点确认
  -> SP-06 特异性候选生成
  -> SP-07 候选排序
  +-> SP-08 竞争性姿态比较（满足条件时）
  +-> SP-09 活性保持检查（声明活性约束时）
  +-> SP-10 稳定性保持检查（声明稳定性约束时）
  -> SP-11 证据闸门
  -> SP-12 输出候选和验证建议
```

## 步骤—工具组总表

| 步骤 | 任务 | 首选工具 | 直接替补 | 降级替补/条件工具 |
|---|---|---|---|---|
| SP-01 | 输入盘点与用户确认 | 内部 `intake_review`（非平台工具） | 无 | 首轮输出缺口并等待用户确认 |
| SP-02 | 工具能力检查 | `tool_capability_audit` | 无 | 无；失败即 `NEEDS_REVIEW` |
| SP-03 | 身份和反应类型 | `enzyme_identity_profile` | 无 | `sequence_search`、`blast_search`、`lookup_protein`、`enzyme_function`、`annotation_bundle`、`protein_benchmark`、InterPro 工具 |
| SP-04 | 目标/非目标底物 | `search_substrate` | 无 | `get_kinetic_params`、`literature_live_search`、`external_connectivity_check`、`external_research_evidence` |
| SP-05 | 催化位点和结合位点 | `catalytic_site_lookup`、`residue_numbering_gate` | 无 | `residue_mapping_sifts`、`structure_search_foldseek`、注释/文献工具 |
| SP-06 | 特异性候选生成 | `mutation_priority_score` | 无 | `mutation_scan`、`ligandmpnn_design`（条件） |
| SP-07 | 候选排序 | `mutation_priority_score` | 无 | `protssn_score`、`esm1v_predict`、`esm2_predict` |
| SP-08 | 竞争性姿态比较 | `ligand_preprocess`、`diffdock_docking` | 无 | `boltz1_predict` 仅作结构线索 |
| SP-09 | 活性保持检查 | `kcat_predict`、`get_kinetic_params` | 无 | 无；只作约束 |
| SP-10 | 稳定性保持检查 | `rosetta_ddg`、`get_stability_data` | 无 | 无；只作约束 |
| SP-11 | 证据闸门 | `scientific_claim_gate` | 无 | 无；失败即 `NEEDS_REVIEW` |

替补的详细等级和切换规则见 `references/tool_fallback_matrix.md`。

## 工具级步骤

### SP-01 输入盘点与用户确认

- **状态**：`MUST`
- **执行方式**：内部 `intake_review`，不调用平台工具。
- **首轮输出**：已收到的目标底物、非目标底物、评价指标、序列/结构和反应条件；缺口等级、影响和建议补充项。
- **用户动作**：等待用户补充，或明确“按现有信息继续”。确认后再调用 `enzyme_objective_module_plan`。
- **阻断**：主目标无法判断，或没有序列、结构或可追溯参考对象；底物、off-target 和评价指标缺失时先提示，不自动结束任务。

### SP-02 工具能力检查

- **状态**：`MUST`
- **工具**：`tool_capability_audit`
- **规则**：对接、结构预测和排序工具都不能直接当成特异性实验证据。

### SP-03 身份和反应类型确认

- **状态**：`MUST`
- **首选工具**：`enzyme_identity_profile`
- **直接替补**：无
- **降级替补**：`sequence_search`、`blast_search`、`lookup_protein`、`enzyme_function`、`annotation_bundle`、`protein_benchmark`
- **切换条件**：首选工具失败或身份信息不完整时，允许调用降级工具组；至少保留两类独立证据，且结论标为身份候选。
- **输出**：酶身份、反应类型、关键位点和参考家族。

### SP-04 目标/非目标底物确认

- **状态**：`MUST`
- **首选工具**：`search_substrate`
- **直接替补**：无
- **降级替补**：`literature_live_search`、`get_kinetic_params`、`external_connectivity_check`、`external_research_evidence`
- **切换条件**：首选工具失败或底物名称歧义未消除时，切换到文献/数据降级组；仍必须保留目标和非目标底物的标准化记录。
- **规则**：目标底物和非目标底物都要有标准化记录；不能只定义目标，不定义比较对象。

### SP-05 催化位点和结合位点确认

- **状态**：`MUST`
- **首选工具**：`catalytic_site_lookup`
- **直接替补**：无
- **降级替补**：`enzyme_function`、`annotation_bundle`、`interpro_annotation`、`literature_live_search`、`protein_benchmark`
- **条件工具**：`residue_numbering_gate`
- **切换条件**：首选工具失败时，先补位点线索，再进入编号门控；无法确认时停止设计。
- **补充工具**：`residue_mapping_sifts`、`structure_search_foldseek`
- **输出**：活性位点、口袋位点、保护位点和编号映射。

### SP-06 特异性候选生成

- **状态**：`MUST`
- **首选工具**：`mutation_priority_score`
- **直接替补**：无
- **降级替补**：`mutation_scan`
- **条件工具**：`ligandmpnn_design`
- **切换条件**：首选排序失败时可用 `mutation_scan` 形成保守候选池，但标记 `degraded`；`ligandmpnn_design` 只有在明确做口袋重设计且有配体结构时才允许进入。
- **规则**：先围绕口袋和结合残基生成候选；不得用普通活性提升工具替代特异性候选逻辑。
- **禁止**：用普通活性提升工具直接替代特异性候选生成逻辑。

### SP-07 候选排序

- **状态**：`MUST`
- **首选工具**：`mutation_priority_score`
- **直接替补**：无
- **降级替补**：`protssn_score`、`esm1v_predict`、`esm2_predict`
- **切换条件**：首选工具失败时，降级工具只能提供辅助排序；必须保留目标/非目标底物比较依据，不能单独宣布特异性改变。
- **输出**：对目标底物有利、对非目标底物不利或更弱的候选排序。

### SP-08 竞争性姿态比较

- **状态**：`OPTIONAL`
- **工具顺序**：`ligand_preprocess` -> `diffdock_docking`
- **触发条件**：同时提供目标底物和非目标底物结构，且有可信结构。
- **规则**：必须做多底物比较；不能只看目标底物的 pose。
- **边界**：对接只能支持姿态解释，不能单独证明特异性改变。

### SP-09 活性保持检查

- **状态**：`OPTIONAL`
- **条件工具**：`kcat_predict`、`get_kinetic_params`
- **触发条件**：用户要求改变特异性但不能损失总体活性。

### SP-10 稳定性保持检查

- **状态**：`OPTIONAL`
- **条件工具**：`rosetta_ddg`、`get_stability_data`
- **触发条件**：用户要求特异性调整同时保持稳定性。

### SP-11 证据闸门

- **状态**：`MUST`
- **工具**：`scientific_claim_gate`
- **规则**：没有多底物实验数据时，只能写“特异性候选/待验证”。

### SP-12 输出候选和验证建议

- **状态**：`MUST`
- **输出**：目标底物与非目标底物对照、候选位点、排序依据、风险、建议测定矩阵。

## 禁用工具

默认禁用：`signal_peptide_predict`、`soluble_mpnn_design`、`rfdiffusion_design`、`chroma_design`、`progen2_generate`、`evodiff_generate`、`esm3_generate`。

原因：这些工具主要解决表达/分泌或从头生成，不是特异性默认流程。

## 最小工具链

```text
intake_review
 -> user_confirmation
 -> enzyme_objective_module_plan
 -> tool_capability_audit
 -> enzyme_identity_profile
 -> search_substrate
 -> catalytic_site_lookup
 -> residue_numbering_gate
 -> mutation_priority_score
 -> scientific_claim_gate
```
