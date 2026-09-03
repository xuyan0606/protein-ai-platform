# WF-ACTIVITY 活性目标专用流程

## 1. 适用范围

适用于以下主目标：

- 提高酶活性
- 提高 `kcat`
- 降低 `Km`
- 提高催化效率 `kcat/Km`
- 提高特定反应条件下的转化率或反应速率

如果用户真正想改变的是底物选择性、表达量或稳定性，应切换到对应主流程，不能继续套用本流程。

## 2. 先把“活性”说具体

开始前必须明确：

- 活性指标：`kcat`、`Km`、`kcat/Km`、初始反应速率、转化率等。
- 底物：名称、结构式或可靠的化学标识。
- 反应：产物、辅因子、pH、温度、离子、溶剂等关键条件。
- 方向：提高、降低、保持或在多个底物间比较。
- 约束：必须保持的稳定性、表达量、特异性、关键催化残基和不能突变的位点。
- 现有结构：实验结构、可信预测结构，或没有结构。
- 现有数据：野生型和突变体的实测活性数据，以及测定方法和条件。

输入遵循 `references/input_policy.md`：允许用户自然语言、段落、附件输入，先抽取已知信息。只有完全无法判断活性指标、底物身份或目标序列这类阻断生成的硬缺口才返回 `NEEDS_INPUT`；其余缺口先记录并继续，不要求补齐固定表单后才能启动。

## 3. 流程总图

```text
输入活性目标
    |
    v
ACT-01 目标和输入门控
    | 失败 -> NEEDS_INPUT
    v
ACT-02 工具能力检查
    |
    v
ACT-03 酶身份/家族确认
    | 失败 -> NEEDS_REVIEW
    v
ACT-04 底物和反应上下文确认
    |
    v
ACT-05 催化位点与编号确认
    | 失败 -> NEEDS_REVIEW
    v
ACT-06 活性候选生成
    |
    v
ACT-07 候选排序
    |
    +--> ACT-08 多突变组合检查（有组合时）
    |
    +--> ACT-09 结构/底物姿态分析（满足条件时）
    |
    +--> ACT-10 稳定性保持检查（声明了稳定性约束时）
    |
    v
ACT-11 活性结论和证据闸门
    |
    v
ACT-12 输出候选与实验验证建议
```

## 4. 步骤—工具组总表

| 步骤 | 任务 | 首选工具 | 直接替补 | 降级替补/条件工具 |
|---|---|---|---|---|
| ACT-01 | 输入盘点与用户确认 | 内部 `intake_review`（非平台工具） | 无 | 首轮输出缺口并等待用户确认 |
| ACT-02 | 工具能力检查 | `tool_capability_audit` | 无 | 无；失败即 `NEEDS_REVIEW` |
| ACT-03 | 身份和家族 | `enzyme_identity_profile` | 无 | `sequence_search`、`blast_search`、`lookup_protein`、`list_ec_proteins`、`protein_benchmark`、`annotation_bundle`、InterPro 工具、`enzyme_function` |
| ACT-04 | 底物和反应上下文 | `search_substrate` | 无 | `get_kinetic_params`、文献证据工具；结果标降级 |
| ACT-05 | 催化位点和编号 | `catalytic_site_lookup`、`residue_numbering_gate` | 无 | 注释/文献/家族工具只能补位点线索；`residue_mapping_sifts` 只能做映射 |
| ACT-06 | 活性候选生成 | `mutation_priority_score` | 无 | `mutation_scan`、`enzyme_function`、`kcat_predict`、`protssn_score`、`esm1v_predict`、`esm2_predict` |
| ACT-07 | 候选排序 | `mutation_priority_score` | 无 | `kcat_predict`、`protssn_score`、`esm1v_predict`、`esm2_predict`；结果标降级 |
| ACT-08 | 多突变互作 | `mutation_epistasis_check` | 无 | 无；失败时只保留单点候选 |
| ACT-09 | 配体准备/对接 | `ligand_preprocess`、`diffdock_docking` | 无 | `boltz1_predict` 仅作复合物结构线索 |
| ACT-10 | 稳定性保持 | `rosetta_ddg` | 无 | `mutation_scan`、`mutation_priority_score`、`gromacs_md` 只能作风险线索 |
| ACT-11 | 证据闸门 | `scientific_claim_gate` | 无 | 无；失败即 `NEEDS_REVIEW` |

替补的详细等级和切换规则见 `references/tool_fallback_matrix.md`。

## 5. 工具级步骤

### ACT-01 输入盘点与用户确认

- **状态**：`MUST`
- **执行方式**：内部 `intake_review`，不调用平台工具。
- **首轮输出**：已收到的活性指标、底物、反应条件、序列/参考编号、结构和已有数据；缺口等级、影响和建议补充项。
- **用户动作**：等待用户补充，或明确“按现有信息继续”。确认后再调用 `enzyme_objective_module_plan`。
- **阻断条件**：主目标无法判断，或没有目标序列、结构或可追溯参考对象；缺少 assay 或底物信息时先提示，不自动结束任务。

### ACT-02 工具能力检查

- **状态**：`MUST`
- **工具**：`tool_capability_audit`
- **输入**：本次计划中的工具名
- **输出**：每个工具的运行状态、能力类型、所需产物、证据等级
- **阻断条件**：计划把 proxy、cache、plan-only 结果当成活性实验证据
- **平台动作**：删除不合格证据用途，保留为“预测/排序”时才能继续

### ACT-03 酶身份和家族确认

- **状态**：`MUST`
- **首选工具**：`enzyme_identity_profile`
- **直接替补**：无
- **降级替补**：`sequence_search`、`blast_search`、`lookup_protein`、`list_ec_proteins`、`protein_benchmark`、`annotation_bundle`、`interpro_annotation`、`interpro_live_lookup`、`interproscan_sequence_submit` + `interproscan_sequence_status`、`enzyme_function`
- **切换条件**：首选工具失败、结果缺失或身份不完整时，按降级组补证据；至少保留两类独立证据，结论标为身份候选，不能直接升级为身份确认。
- **默认顺序**：
  1. `enzyme_identity_profile`
  2. 身份不清或缺参考时，调用 `sequence_search` 或 `blast_search`
  3. 有 accession 时，调用 `lookup_protein`
  4. 需要家族对照时，调用 `protein_benchmark` 或 `list_ec_proteins`
- **输出**：身份状态、家族、参考序列、关键保守位点、编号依据
- **阻断条件**：身份与目标反应明显不一致；无法建立可靠参考；编号体系不清
- **平台动作**：阻断后不得进入催化位点和突变设计

### ACT-04 底物和反应上下文确认

- **状态**：`MUST`
- **首选工具**：`search_substrate`
- **直接替补**：无
- **降级替补**：`get_kinetic_params`、`literature_live_search`、`external_connectivity_check`、`external_research_evidence`
- **切换条件**：首选工具失败或底物名称存在歧义时，切换到降级组补证据；仍必须保留标准化底物记录。
- **调用条件**：
  - 用户未提供可靠底物标识，或名称存在歧义：必须调用 `search_substrate`
  - 需要同源或目标已有动力学数据：调用 `get_kinetic_params`
  - 需要机制、已知活性突变或测定条件证据：调用 `literature_live_search`
  - 使用实时外部检索：先做 `external_connectivity_check`
  - 有外部检索结果需要写进报告：调用 `external_research_evidence`
- **输出**：标准底物记录、反应条件、已有动力学数据、文献证据和来源状态
- **阻断条件**：底物身份无法确认；反应类型与酶身份冲突

### ACT-05 催化位点与残基编号确认

- **状态**：`MUST`
- **首选工具**：`catalytic_site_lookup`
- **直接替补**：无
- **降级替补**：`enzyme_function`、`annotation_bundle`、`interpro_annotation`、`literature_live_search`、`protein_benchmark`
- **条件工具**：`residue_numbering_gate`
- **切换条件**：首选工具失败时，先用降级组补位点线索，再进入编号门控；无法确认时停止设计。
- **补充工具**：`residue_mapping_sifts`
- **顺序**：
  1. `catalytic_site_lookup`
  2. 有结构坐标与报告编号不一致风险时，先 `residue_mapping_sifts`
  3. `residue_numbering_gate`
- **输入**：身份结果、序列、结构、底物/反应上下文
- **输出**：催化残基、结合区域、保护位点、统一编号和编号置信度
- **阻断条件**：催化位点无法解释；结构链或成熟链偏移未解决；保护位点存在编号冲突
- **平台动作**：阻断后禁止所有突变生成和排序

### ACT-06 活性候选生成

- **状态**：`MUST`
- **首选工具**：`mutation_priority_score`
- **直接替补**：无
- **降级替补**：`mutation_scan`、`enzyme_function`、`kcat_predict`、`protssn_score`、`esm1v_predict`、`esm2_predict`
- **切换条件**：首选工具失败时，降级组只能形成保守候选池和辅助分数，不能直接宣布候选已优选。
- **推荐顺序**：
  1. 以催化残基和保护位点为约束建立候选空间
  2. `mutation_scan` 生成宽候选池（只有需要宽搜时）
  3. `mutation_priority_score` 按活性目标排序
  4. `kcat_predict`、`protssn_score`、`esm1v_predict` 或 `esm2_predict` 只作为辅助分数
- **必须固定的约束**：催化残基默认保护；编号必须来自 ACT-05；不能把预测分数当成实测活性
- **输出**：候选突变表、排序依据、保护位点、每个候选的证据来源
- **阻断条件**：候选未绑定目标指标；候选触碰保护位点；工具只返回错误或空结果

### ACT-07 候选排序

- **状态**：`MUST`
- **首选工具**：`mutation_priority_score`
- **直接替补**：无
- **降级替补**：`kcat_predict`、`protssn_score`、`esm1v_predict`、`esm2_predict`
- **切换条件**：首选工具失败时，降级组只能给出辅助排序；结果必须标记 `degraded`，不得把单一模型分数写成活性结论。
- **规则**：必须给出统一排序规则；辅助模型之间冲突时保留冲突，不得偷偷平均或挑选有利结果
- **输出**：优先级、入选理由、风险、未决问题
- **禁止**：用 `predict_properties`、单个语言模型分数或单个生成式模型结果直接宣布“活性提高”

### ACT-08 多突变组合检查

- **状态**：`OPTIONAL`
- **工具**：`mutation_epistasis_check`
- **触发条件**：候选包含两个或以上突变，或用户明确要求组合设计
- **输入**：WT 序列/结构、单突变候选、组合列表、活性目标和保护位点
- **输出**：互作风险、冲突组合、建议保留的组合
- **跳过条件**：只输出单点候选
- **跳过记录**：`single_mutant_only`

### ACT-09 结构和底物姿态分析

- **状态**：`OPTIONAL`
- **工具**：`ligand_preprocess`、`diffdock_docking`
- **触发条件**：同时满足：
  1. 底物结构已确认；
  2. 有可信实验结构，或结构预测产物达到流程设定的最低质量；
  3. 需要解释活性位点几何、底物姿态或突变对结合空间的影响
- **前置条件**：没有结构时，可先调用 `esmfold_folding`、`alphafold_folding` 或其他结构工具获得结构假设；结构工具本身仍是条件步骤
- **顺序**：`ligand_preprocess` -> `diffdock_docking`
- **输出**：配体准备产物、对接姿态、位点几何解释
- **跳过条件**：底物无可靠结构、无可信结构、或目标只是序列层候选排序
- **跳过记录**：具体写明缺哪个前置条件
- **边界**：对接姿态不能直接证明活性提升；对接置信度不能当作结合自由能或实测动力学

### ACT-10 稳定性保持检查

- **状态**：`OPTIONAL`
- **工具**：`rosetta_ddg`
- **触发条件**：用户明确要求“活性提高但稳定性不能下降”，且存在可用结构和真实 Rosetta runtime
- **输入**：结构、候选突变、Rosetta 配置和运行环境
- **输出**：真实 ΔΔG 产物、日志、候选稳定性风险
- **跳过条件**：没有稳定性约束；没有真实 runtime；没有结构或运行产物
- **跳过记录**：`no_stability_constraint`、`runtime_unavailable` 或 `structure_unavailable`
- **边界**：稳定性筛选只能作为约束，不能替代活性分析

### ACT-11 活性结论和证据闸门

- **状态**：`MUST`
- **工具**：`scientific_claim_gate`
- **输入**：候选表、所有工具输出、证据状态、实验数据（如有）
- **输出**：哪些可以写成预测、哪些只能写成候选建议、哪些缺实验验证
- **硬规则**：没有实测活性数据，最终结论只能写“预测候选/待实验验证”，不能写“活性已提高”

### ACT-12 输出候选与实验验证建议

- **状态**：`MUST`
- **工具**：无新增性质分析工具；使用前面步骤的结果
- **输出**：候选序列/突变、排序、依据、风险、建议测定指标和对照组
- **必须包含**：
  - WT 对照
  - 指标对应的测定建议
  - 候选与步骤的追溯关系
  - 未执行的可选步骤及跳过原因
  - 预测与实验验证的明确区分

## 5. 活性流程中的禁用工具

### 默认禁用

以下工具默认不进入活性主流程：

- `soluble_mpnn_design`
- `signal_peptide_predict`
- `rfdiffusion_design`
- `chroma_design`
- `progen2_generate`
- `evodiff_generate`
- `esm3_generate`
- `proteinmpnn_design`
- `esm_if1_design`

原因：这些工具主要解决表达、分泌、从头骨架或大范围序列生成问题，不是常规活性点突变流程的必要工具。

### 条件禁用

以下工具不是绝对不能调用，但在本流程中不能作为活性主判据：

- `predict_properties`：只能做背景理化特征。
- `rosetta_ddg`：只能做稳定性约束。
- `gromacs_md`：只能做动态行为补充，且需要真实 MD 产物。
- `diffdock_docking`：只能做姿态假设，不能直接证明活性提高。
- `kcat_predict`：只能做预测排序，不能代替实测 `kcat`。
- `protssn_score`、`esm1v_predict`、`esm2_predict`：只能做辅助评分。
- `structure_search_foldseek`：只能提供结构相似性，不能单独确认酶身份或催化功能。

## 6. 活性流程的最小工具链

当输入完整、身份明确、目标是普通活性点突变优化时，最小链条是：

```text
intake_review
 -> user_confirmation
 -> enzyme_objective_module_plan
 -> tool_capability_audit
 -> enzyme_identity_profile
 -> catalytic_site_lookup
 -> residue_numbering_gate
 -> mutation_priority_score
 -> scientific_claim_gate
```

如果底物身份不明确，在 `enzyme_identity_profile` 后插入：

```text
search_substrate
```

如果需要组合突变，在排序后插入：

```text
mutation_epistasis_check
```

如果需要底物姿态解释，在结构和底物都满足条件时插入：

```text
ligand_preprocess
 -> diffdock_docking
```

## 7. 活性流程输出状态

- `READY`：所有必选步骤完成，流程和策略一致，结论已通过证据闸门。
- `NEEDS_INPUT`：缺少活性指标、底物、序列、反应条件等关键输入。
- `NEEDS_REVIEW`：身份、编号、工具实际执行或策略追溯存在问题。
- `UNSUPPORTED`：当前工具能力无法支撑用户要求的活性任务。
