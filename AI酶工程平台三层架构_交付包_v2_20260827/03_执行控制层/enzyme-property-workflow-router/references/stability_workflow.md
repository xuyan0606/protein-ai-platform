# WF-STABILITY 稳定性目标专用流程

## 适用范围

适用于热稳定性、半衰期、溶剂耐受、蛋白酶耐受和残余活性保持等目标。明确的 pH 最适、目标 pH 活性、pH 稳态拓宽和酸/碱耐受任务走 `references/ph_workflow.md`。

## 必须先明确

- 稳定性指标：`Tm`、半衰期、残余活性、失活速率或特定条件下的保留率。
- 条件：温度、pH、盐、溶剂、蛋白酶、孵育时间等。
- 方向：提高、保持或降低。
- 必须保持的活性、表达量、特异性和固定残基。
- 序列、结构、已有稳定性数据和突变数据。

输入遵循 `references/input_policy.md`：允许用户自然语言、段落、附件输入，先抽取已知信息。只有完全无法判断主目标或没有任何序列/参考编号这类阻断路由的硬缺口才返回 `NEEDS_INPUT`；其余缺口先记录并继续，不要求补齐固定表单。

## 流程图

```text
稳定性目标
  -> ST-01 目标和输入门控
  -> ST-02 工具能力检查
  -> ST-03 身份和参考序列确认
  -> ST-04 稳定性数据与风险区域确认
  -> ST-05 编号和保护位点确认
  -> ST-06 稳定性候选生成
  -> ST-07 候选排序
  +-> ST-08 多突变互作检查（有组合时）
  +-> ST-09 结构/动力学补充（满足条件时）
  +-> ST-10 活性保持检查（声明活性约束时）
  -> ST-11 证据闸门
  -> ST-12 输出候选和验证建议
```

## 步骤—工具组总表

| 步骤 | 任务 | 首选工具 | 直接替补 | 降级替补/条件工具 |
|---|---|---|---|---|
| ST-01 | 输入盘点与用户确认 | 内部 `intake_review`（非平台工具） | 无 | 无；首轮输出缺口并等待用户确认 |
| ST-02 | 工具能力检查 | `tool_capability_audit` | 无 | 无；失败即 `NEEDS_REVIEW` |
| ST-03 | 身份和参考序列 | `enzyme_identity_profile` | 无 | `sequence_search`、`blast_search`、`lookup_protein`、`protein_benchmark`、`annotation_bundle` |
| ST-04 | 稳定性数据与风险 | `get_stability_data` | 无 | 文献证据工具、`predict_properties` |
| ST-05 | 编号和保护位点 | `residue_numbering_gate` | 无 | `residue_mapping_sifts` |
| ST-06 | 稳定性候选生成 | `mutation_scan` | 无 | `mutation_priority_score` |
| ST-07 | 候选排序 | `mutation_priority_score` | 无 | `mutation_scan`、`protssn_score`、`esm1v_predict`、`esm2_predict`、`rosetta_ddg` |
| ST-08 | 多突变互作 | `mutation_epistasis_check` | 无 | 无；失败只保留单点候选 |
| ST-09 | 结构/动力学补充 | `esmfold_folding`、`alphafold_folding`、`rosettafold_folding`、`rosettafold_allatom`、`structure_search_foldseek`、`gromacs_md` | 无 | 无；按条件启用 |
| ST-10 | 活性保持检查 | `catalytic_site_lookup`、`enzyme_function`、`kcat_predict`、`get_kinetic_params` | 无 | 无；只作约束 |
| ST-11 | 证据闸门 | `scientific_claim_gate` | 无 | 无；失败即 `NEEDS_REVIEW` |

替补的详细等级和切换规则见 `references/tool_fallback_matrix.md`。

## 工具级步骤

### ST-01 输入盘点与用户确认

- **状态**：`MUST`
- **执行方式**：内部 `intake_review`，不调用平台工具。
- **首轮输出**：已收到的信息、缺失信息、缺口等级、对分析的影响和建议优先补充项。
- **用户动作**：等待用户补充，或明确“按现有信息继续”。
- **阻断**：只有主目标无法判断，或没有序列、结构或可追溯参考对象时，才等待用户补充；缺少指标、条件或已有数据本身不阻断首轮盘点。

### ST-02 工具能力检查

- **状态**：`MUST`
- **工具**：`tool_capability_audit`
- **规则**：区分预测、历史数据、代理结果和真实 runtime；不得把预测当作稳定性实测。

### ST-03 身份和参考序列确认

- **状态**：`MUST`
- **首选工具**：`enzyme_identity_profile`
- **直接替补**：无
- **降级替补**：`sequence_search`、`blast_search`、`lookup_protein`、`protein_benchmark`、`annotation_bundle`
- **切换条件**：首选工具失败、结果缺失或需要补充身份线索；降级替补只形成身份候选，不得直接写成身份确认。
- **阻断**：身份不清、参考序列不一致或家族归属与目标不符。

### ST-04 稳定性数据与风险区域确认

- **状态**：`MUST`
- **首选工具**：`get_stability_data`
- **直接替补**：无
- **降级替补**：`literature_live_search` + `external_research_evidence`，用于提取文献中的稳定性数据；`predict_properties` 只能做基线线索。
- **切换条件**：首选工具无记录、失败或数据层不可用时，才切换降级替补，并在输出中标记为文献/预测证据。
- **调用条件**：有目标/同源稳定性数据时调用 `get_stability_data`；需要文献机制时调用文献工具。
- **输出**：已有测定、条件差异、稳定性风险线索。
- **阻断**：把不同测定条件的数据直接横向比较而未记录条件。

### ST-05 编号和保护位点确认

- **状态**：`MUST`
- **工具**：`residue_numbering_gate`
- **条件工具**：`residue_mapping_sifts`
- **调用条件**：有结构编号、成熟链偏移或 PDB/UniProt 映射时，先调用 `residue_mapping_sifts`。
- **输出**：统一编号、固定残基、催化残基和不可变区域。

### ST-06 稳定性候选生成

- **状态**：`MUST`
- **首选工具**：`mutation_scan`
- **直接替补**：无
- **降级替补**：`mutation_priority_score`
- **切换条件**：当宽候选池生成失败或只需要保守排序时，使用降级替补；不得直接跳到生成式设计工具。
- **规则**：先按保护位点和目标条件限制候选空间，再生成候选；不能直接让生成式设计工具自由改写整条序列。

### ST-07 候选排序

- **状态**：`MUST`
- **首选工具**：`mutation_priority_score`
- **直接替补**：无
- **降级替补**：`mutation_scan`、`protssn_score`、`esm1v_predict`、`esm2_predict`
- **条件辅助工具**：`rosetta_ddg`
- **切换条件**：首选排序失败时，可用降级工具生成风险排序，但最终标记 `degraded`；有可信结构且真实 Rosetta runtime 可用时，`rosetta_ddg` 才能作为稳定性排序辅助。
- **输出**：稳定性候选排名、风险、依据和证据类型。
- **硬规则**：没有实测数据时只能写“预测候选”，不能写“稳定性已提高”。

### ST-08 多突变互作检查

- **状态**：`OPTIONAL`
- **工具**：`mutation_epistasis_check`
- **触发条件**：候选含两个或以上突变。
- **跳过记录**：`single_mutant_only`。

### ST-09 结构/动力学补充

- **状态**：`OPTIONAL`
- **条件工具**：`esmfold_folding`、`alphafold_folding`、`rosettafold_folding`、`rosettafold_allatom`、`structure_search_foldseek`、`gromacs_md`
- **触发条件**：需要解释局部结构、柔性或动态行为，且有结构输入或可获得结构；`gromacs_md` 还必须有真实 runtime 和轨迹/日志产物。
- **边界**：结构预测或 MD 只能支持机制解释和风险评估，不能单独证明稳定性提升。

### ST-10 活性保持检查

- **状态**：`OPTIONAL`
- **条件工具**：`catalytic_site_lookup`、`enzyme_function`、`kcat_predict`、`get_kinetic_params`
- **触发条件**：用户明确要求稳定性提高但活性不能下降。
- **规则**：活性工具只能做保持约束；主目标仍是稳定性。

### ST-11 证据闸门

- **状态**：`MUST`
- **工具**：`scientific_claim_gate`
- **输出**：预测、数据检索和实验验证分层；列出不能支持的表述。

### ST-12 输出候选和验证建议

- **状态**：`MUST`
- **输出**：候选突变、稳定性条件、排序依据、风险、WT 对照、建议测定指标和追溯步骤。

## 禁用工具

默认禁用：`signal_peptide_predict`、`soluble_mpnn_design`、`ligandmpnn_design`、`diffdock_docking`、`rfdiffusion_design`、`chroma_design`、`progen2_generate`、`evodiff_generate`、`esm3_generate`。

原因：这些工具主要解决表达、底物结合或从头生成问题，不是稳定性主流程的默认工具。

## 最小工具链

```text
intake_review
 -> user_confirmation
 -> enzyme_objective_module_plan
 -> tool_capability_audit
 -> enzyme_identity_profile
 -> get_stability_data
 -> residue_numbering_gate
 -> mutation_scan
 -> mutation_priority_score
 -> scientific_claim_gate
```

没有稳定性数据库记录时，`get_stability_data` 必须返回“无记录/未检索到”，不能静默跳过并伪造数据。
