# 工具组与替补规则

## 目的

平台的 58 个工具中，有些是同一类任务的不同实现，有些只是上下游辅助，不能因为名字相近就互相替代。本文件按流程步骤任务定义工具组、替补等级和切换规则。按工具本体的完整同功能分组与等价/降级/不可替补判定见 `references/tool_groups.md`。输入盘点阶段属于内部控制阶段，不作为工具替补组执行。

## 替补等级

| 等级 | 含义 | 输出处理 |
|---|---|---|
| `DIRECT` | 任务语义和主要输出基本一致，可以接替首选工具 | 保持原步骤状态；记录实际工具名 |
| `DEGRADED` | 只能完成部分目标或证据等级不同 | 步骤标记 `degraded`；最终结论降低为预测/线索/待验证 |
| `NONE` | 没有可靠替代品 | 工具失败后标记 `blocked`，不得静默换工具 |

## 全局切换规则

1. 每个步骤先读取当前 `/api/tools`，确认工具仍注册、参数 schema 可用、同步/异步状态正确。
2. 首选工具出现 `failed`、`blocked`、`missing_required`、超时或返回不可用产物时，才触发替补。
3. 先尝试 `DIRECT`，再考虑 `DEGRADED`；不得跳过直接替补去调用降级替补。
4. 替补工具必须在当前流程该步骤的白名单中；不在白名单中的工具即使功能相似也不能调用。
5. 替补前后记录 `step_id`、`tool_group`、`primary_tool`、`selected_tool`、`fallback_level`、`fallback_reason`、输入版本和输出版本。
6. 替补工具不能改变步骤目标。不能用“结构预测”替代“实测稳定性数据”，不能用“对接”替代“动力学预测”，不能用“活性预测”替代“特异性比较”。
7. `MUST` 步骤只有在直接替补完成同一门控/同一输出后才能继续；降级替补只能继续到明确允许降级的后续步骤。
8. 关键门控、编号校验、证据闸门和实验数据读取没有直接替补时，失败必须停止，不得生成完整方案。
9. 同一工具连续失败不重复盲试；记录失败原因，按替补顺序切换一次。所有候选都失败时返回 `NEEDS_REVIEW` 或 `NEEDS_INPUT`。
10. 替补成功不等于结果等价。最终报告必须说明是否使用替补，以及它改变了什么证据边界。

## 工具组

### G01 目标拆解

- **任务**：把用户目标拆成指标、约束和验证要求。
- **首选**：`enzyme_objective_module_plan`
- **直接替补**：无。
- **降级替补**：无。目标拆解失败时必须返回 `NEEDS_REVIEW`，不得用输入完整性工具替代。
- **失败动作**：`NEEDS_INPUT`，不得自行猜指标。

### G02 输入盘点与用户确认

- **任务**：在调用性质工具前盘点已知输入、缺口等级、影响和建议补充项。
- **执行方式**：内部 `intake_review`，不调用平台工具。
- **直接替补**：无。
- **降级替补**：无；LLM 负责自然语言抽取，后端契约负责状态校验。
- **失败动作**：主目标或对象无法判断时等待用户反馈；其他缺口先记录，不自动阻断。

### G03 工具能力审计

- **任务**：判断工具是实时、缓存、代理、预测还是真实 runtime。
- **首选**：`tool_capability_audit`
- **直接替补**：无。
- **失败动作**：`NEEDS_REVIEW`；不能在能力边界不明时输出报告级结论。

### G04 身份与家族确认

- **任务**：建立酶身份、家族、参考序列和保守位点。
- **首选**：`enzyme_identity_profile`
- **直接替补**：无。
- **降级替补**：`sequence_search`、`blast_search`、`lookup_protein`、`annotation_bundle`、`interpro_annotation`、`interpro_live_lookup`、`interproscan_sequence_submit` + `interproscan_sequence_status`、`protein_benchmark`、`enzyme_function`。
- **降级规则**：只能形成“身份候选/家族线索”，不能自动升级为身份确认；至少需要两类相互独立的证据或用户提供可靠 accession。

### G05 底物标准化

- **任务**：确认底物身份、同义词和化学表示。
- **首选**：`search_substrate`
- **直接替补**：无。
- **降级替补**：用户提供的标准 SMILES、InChI 或可靠 accession 可作为输入，但不是平台工具结果；需要在记录中标为 `user_supplied`。
- **失败动作**：`NEEDS_INPUT`。

### G06 动力学数据检索

- **任务**：读取已有 Km、kcat、Vmax、催化效率及测定条件。
- **首选**：`get_kinetic_params`
- **直接替补**：无。
- **降级替补**：`literature_live_search` + `external_research_evidence` 可提取论文数据，但必须保留原始引文和测定条件；`kcat_predict` 只能做预测，不能替代数据检索。

### G07 稳定性数据检索

- **任务**：读取 Tm、半衰期、残余活性和条件性稳定性数据。
- **首选**：`get_stability_data`
- **直接替补**：无。
- **降级替补**：`literature_live_search` + `external_research_evidence` 可提供文献数据；`rosetta_ddg`、`gromacs_md`、`predict_properties` 均不能替代实测数据读取。

### G08 结构获取与结构假设

- **任务**：从序列或已有记录获得结构，用于后续位点、口袋或构象分析。
- **首选顺序**：已有可信实验结构；没有时使用平台结构工具。
- **直接替补**：`esmfold_folding`、`alphafold_folding`、`alphafold2_folding`、`rosettafold_folding` 可互作结构假设替补，但必须记录模型和产物来源。
- **降级替补**：`rosettafold_allatom`、`boltz1_predict` 可提供特定结构/复合物假设；`structure_search_foldseek` 只能找结构模板，不能直接替代折叠预测。
- **失败动作**：跳过依赖结构的可选步骤；不得把序列结果伪装成结构结果。

### G09 编号与保护位点

- **任务**：统一链、成熟链偏移、PDB/UniProt 编号并保护关键残基。
- **首选**：`residue_numbering_gate`
- **直接替补**：无。
- **降级替补**：`residue_mapping_sifts` 只能提供映射，不能替代最终编号门控。
- **失败动作**：`NEEDS_REVIEW`；禁止突变设计和突变报告。

### G10 催化/活性位点识别

- **任务**：确认催化残基、活性中心和结合区域。
- **首选**：`catalytic_site_lookup`
- **直接替补**：无。
- **降级替补**：`enzyme_function`、`annotation_bundle`、`interpro_annotation`、`literature_live_search`、`protein_benchmark` 可提供位点线索，但不能自动当作催化位点确认。
- **失败动作**：活性和特异性流程停止候选设计；稳定性/表达流程只能把相关步骤标记为未确认。

### G11 候选生成与优先级排序

- **任务**：生成或排序点突变候选。
- **首选排序**：`mutation_priority_score`
- **直接替补**：无。
- **降级替补**：`mutation_scan`、`kcat_predict`、`protssn_score`、`esm1v_predict`、`esm2_predict` 可提供候选或辅助排序；不能把单一辅助分数当最终排序依据。
- **特殊工具**：`proteinmpnn_design`、`ligandmpnn_design`、`soluble_mpnn_design`、`esm_if1_design` 只能在对应设计场景进入白名单，不能泛化替代点突变排序。

### G12 多突变互作

- **任务**：判断多突变组合的互作、冲突和组合风险。
- **首选**：`mutation_epistasis_check`
- **直接替补**：无。
- **降级替补**：`mutation_priority_score` 只能分别排序单点，不能替代组合互作判断。
- **失败动作**：只输出单点候选，或将组合标记为 `NEEDS_REVIEW`。

### G13 稳定性约束评分

- **任务**：评估候选突变对结构稳定性的影响。
- **首选**：真实 runtime 可用时的 `rosetta_ddg`
- **直接替补**：无。
- **降级替补**：`mutation_scan`、`mutation_priority_score`、`gromacs_md` 可提供风险线索，但不能称为 Rosetta ΔΔG。
- **失败动作**：删除“稳定性已评估”的表述，保留为未评估或预测风险。

### G14 配体准备与对接

- **配体准备首选**：`ligand_preprocess`；无直接替补。
- **对接首选**：`diffdock_docking`；无直接替补。
- **降级替补**：`boltz1_predict` 可在支持复合物假设时提供结构线索，但不能称为 DiffDock 对接结果。
- **失败动作**：跳过姿态分析，不得用普通活性预测替代。

### G15 表达/可溶性设计

- **任务**：在保留功能约束下生成表达或可溶性候选。
- **首选**：`soluble_mpnn_design`
- **条件替补**：`proteinmpnn_design`、`esm_if1_design` 仅在有结构骨架且明确允许结构条件设计时使用。
- **降级替补**：`mutation_scan` + `mutation_priority_score` 只能做保守候选筛选，不能等价替代表达设计。
- **失败动作**：输出候选筛选结果但标为降级，不得写成完整表达设计。

### G16 分泌信号预测

- **任务**：预测信号肽和切割位点。
- **首选**：`signal_peptide_predict`
- **直接替补**：无。
- **失败动作**：分泌步骤 `blocked`；不能用普通表达或结构工具推断信号肽结论。

### G17 证据闸门

- **任务**：审查结论是否超过证据支持范围。
- **首选**：`scientific_claim_gate`
- **直接替补**：无。
- **失败动作**：`NEEDS_REVIEW`；不得输出 `READY`。

## 替补追踪格式

```yaml
fallback_trace:
  - step_id: ACT-03
    tool_group: G04
    primary_tool: enzyme_identity_profile
    selected_tool: blast_search
    fallback_level: DEGRADED
    fallback_reason: primary_failed
    evidence_change: identity_candidate_only
```
