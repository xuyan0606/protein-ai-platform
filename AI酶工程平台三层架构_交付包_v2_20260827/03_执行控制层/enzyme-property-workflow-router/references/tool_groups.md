# 58 工具同功能分组与替补判定

## 目的

把平台当前 58 个唯一注册工具逐一按真实功能归组，明确哪些真能互为替补、哪些是降级替补、哪些没有替补。此表是 `tool_fallback_matrix.md` 的细化版：前者按“流程步骤任务”分组，本表按“工具本体”分组。两者结合使用。正式运行时仍以线上 `/api/tools` 为准。

## 分组原则

- **等价替补（DIRECT）**：输出语义和主要用途一致，可接替首选工具，结论等级不变。
- **降级替补（DEGRADED）**：能补一部分信息，但证据等级或覆盖度不同，结论必须降级标注。
- **不可替补（NONE）**：没有同功能工具；失败必须停止或返回缺口，不得静默换工具。
- **不互替**：名字相近但职责不同，不能因为首选失败就互相替换。例如结构预测不能替实测数据，对接不能替动力学预测。

## 完整分组

### GROUP-A 目标与证据治理（单职责，无替补）

| 工具 | 功能 | 替补 |
|---|---|---|
| `enzyme_objective_module_plan` | 把性质目标拆成指标、约束、验证要求 | NONE |
| `intake_review`（内部控制阶段） | 盘点已知输入、缺口等级和建议补充项；不调用平台工具 | NONE |
| `tool_capability_audit` | 判断工具是预测/检索/代理/真实 runtime | NONE |
| `scientific_claim_gate` | 审查结论是否超过证据支持 | NONE |

说明：`intake_review` 是内部会话阶段，不是平台注册工具；`tool_capability_audit` 和 `scientific_claim_gate` 是平台治理工具。输入盘点不能用其他性质工具替代。

### GROUP-B 同源与参考检索

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `sequence_search` | 同源序列/蛋白数据库检索 | 与 `blast_search` 等价（DIRECT） |
| `blast_search` | 序列相似性同源搜索 | 与 `sequence_search` 等价（DIRECT） |
| `lookup_protein` | 按 accession 精确取标准记录 | 不等价；仅当已有编号时可补 `sequence_search` 的“取标准序列”用途（DEGRADED） |
| `list_ec_proteins` | 按 EC 构建参考集 | 不等价；家族比较辅助 |

说明：真正互为等价替补的是 `sequence_search` 与 `blast_search`。`lookup_protein` 是精确获取不是搜索，`list_ec_proteins` 是参考集构建，二者不能替同源搜索。

### GROUP-C 身份、家族与注释整合

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `enzyme_identity_profile` | 整合身份/家族/关键残基画像 | 组内核，其余为降级辅助 |
| `protein_benchmark` | 与已知家族比较保守位点 | 身份确认后辅助（DEGRADED） |
| `annotation_bundle` | 汇总已有注释 | 身份辅助（DEGRADED） |
| `interpro_annotation` | 已有 InterPro 注释 | 身份辅助（DEGRADED） |
| `interpro_live_lookup` | 实时 InterPro 检索 | 身份辅助（DEGRADED） |
| `interproscan_sequence_submit` | 提交 InterProScan 异步任务 | 必须与 `interproscan_sequence_status` 配对，本身不可替身份确认 |
| `interproscan_sequence_status` | 取 InterProScan 结果 | 仅提交后可用 |
| `enzyme_function` | 功能/EC 假设 | 身份辅助（DEGRADED） |

说明：这些工具没有等价替补。它们只能互相补身份线索，不能自动升级为身份确认；至少需要两类独立证据或用户可靠 accession。

### GROUP-D 底物检索

| 工具 | 功能 | 替补 |
|---|---|---|
| `search_substrate` | 底物身份、同义词、化学表示 | NONE |

说明：无平台工具等价替补。用户提供的 SMILES/InChI 可作为 `user_supplied` 输入，但不是工具结果。

### GROUP-E 实测数据检索

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `get_kinetic_params` | 读取 Km/kcat/Vmax/催化效率 | 不等价；与 `get_stability_data` 不同性质 |
| `get_stability_data` | 读取 Tm/半衰期/残余活性 | 不等价；与 `get_kinetic_params` 不同性质 |

说明：动力学数据和稳定性数据互不替补，都不能被预测工具代替。

### GROUP-F 文献与外部证据

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `literature_live_search` | 实时文献检索 | 与 `external_research_evidence` 不等价，前者检索后者整合 |
| `external_research_evidence` | 把检索结果整理成证据包 | 依赖检索结果，不独立替检索 |
| `external_connectivity_check` | 外部源健康检查 | 不是生物学证据，不可替任何分析 |

### GROUP-G 结构预测与复合物假设

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `esmfold_folding` | 从序列预测单链结构 | 与 `alphafold2_folding`、`rosettafold_folding` 等价（DIRECT） |
| `alphafold2_folding` | AF2 路径结构预测 | 与 `esmfold_folding`、`rosettafold_folding` 等价（DIRECT） |
| `rosettafold_folding` | RoseTTAFold 路径结构预测 | 与 `esmfold_folding`、`alphafold2_folding` 等价（DIRECT） |
| `alphafold_folding` | 结构获取或外部检索入口 | 不等价；必须区分“数据库检索”与“真实推理”，真推理时降级为候选 |
| `rosettafold_allatom` | 全原子结构精化 | 不等价；承接初始预测后的精化，不可替初始预测 |
| `boltz1_predict` | 复合物/配体复合物结构 | 不等价；只在需要复合物假设时进入，不可替单链折叠 |

说明：真正互为等价替补的是 `esmfold_folding`、`alphafold2_folding`、`rosettafold_folding` 三者（都是单链结构假设）。`alphafold_folding` 可能是检索不是推理，`rosettafold_allatom` 是精化，`boltz1_predict` 是复合物，三者都不与初始预测等价。

### GROUP-H 结构模板搜索

| 工具 | 功能 | 替补 |
|---|---|---|
| `structure_search_foldseek` | 结构相似模板搜索 | NONE |

说明：结构相似性不能证明酶身份，也无等价替补。

### GROUP-I 编号与映射

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `residue_numbering_gate` | 编号/链/偏移/保护位点门控 | NONE；硬门控 |
| `residue_mapping_sifts` | PDB-UniProt 编号映射 | 不等价；只提供映射，不能替最终门控 |

### GROUP-J 催化位点识别

| 工具 | 功能 | 替补 |
|---|---|---|
| `catalytic_site_lookup` | 催化残基与活性中心识别 | NONE |

说明：无等价替补；注释/文献工具只能补位点线索。

### GROUP-K 突变候选生成与排序

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `mutation_scan` | 宽候选池生成与风险初筛 | 不等价；是 `mutation_priority_score` 的上游，不能替排序 |
| `mutation_priority_score` | 目标导向候选排序 | 不等价；是排序核心，不能被单点扫描替 |

说明：二者是上下游关系，不是替补。辅助分数（`kcat_predict`、`protssn_score`、`esm1v_predict`、`esm2_predict`）只能补排序，不能替 `mutation_priority_score`。

### GROUP-L 稳定性约束评分

| 工具 | 功能 | 替补 |
|---|---|---|
| `rosetta_ddg` | Rosetta ΔΔG，需真实 runtime | NONE |

说明：无等价替补；`mutation_scan`/`gromacs_md` 只能作风险线索，不能称为 Rosetta 结果。

### GROUP-M 组合互作

| 工具 | 功能 | 替补 |
|---|---|---|
| `mutation_epistasis_check` | 多突变组合冲突判断 | NONE |

说明：`mutation_priority_score` 只能排单点，不能替组合互作。

### GROUP-N 迭代反馈

| 工具 | 功能 | 替补 |
|---|---|---|
| `feedback_iteration_planner` | 根据真实实验反馈规划下一轮 | NONE |

### GROUP-O 活性与变体辅助预测

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `kcat_predict` | kcat/活性倾向预估 | 不等价；活性专项，其他是通用变体效应 |
| `protssn_score` | 序列/结构邻域兼容性 | 与 `esm1v_predict`、`esm2_predict` 互相部分降级替补 |
| `esm1v_predict` | 零样本变体效应 | 与 `protssn_score`、`esm2_predict` 互相部分降级替补 |
| `esm2_predict` | 表征/变体预测 | 与 `protssn_score`、`esm1v_predict` 互相部分降级替补 |

说明：这四个都是候选排序的辅助分数，可以互为 DE GRADED 替补，但都不能单独作为活性结论，也不能互称等价。

### GROUP-P 生成式与条件设计

| 工具 | 功能 | 替补关系 |
|---|---|---|
| `proteinmpnn_design` | 给定骨架设计序列 | 与 `esm_if1_design` 等价（DIRECT，都是逆折叠） |
| `esm_if1_design` | 逆折叠骨架到序列 | 与 `proteinmpnn_design` 等价（DIRECT） |
| `soluble_mpnn_design` | 可溶性/表达导向设计 | NONE；专门表达场景 |
| `ligandmpnn_design` | 配体环境设计 | NONE；专门配体口袋场景 |
| `rfdiffusion_design` | 从头骨架生成 | NONE；与其他序列设计不等价 |
| `esm3_generate` | 生成式序列编辑 | 与 `progen2_generate`、`evodiff_generate`、`chroma_design` 部分降级替补 |
| `progen2_generate` | 家族序列生成 | 与 `esm3_generate`、`evodiff_generate`、`chroma_design` 部分降级替补 |
| `evodiff_generate` | 进化扩散生成 | 与 `esm3_generate`、`progen2_generate`、`chroma_design` 部分降级替补 |
| `chroma_design` | 生成式结构设计 | 与 `esm3_generate`、`progen2_generate`、`evodiff_generate` 部分降级替补 |

说明：逆折叠类 `proteinmpnn_design`/`esm_if1_design` 互为等价替补。四个生成式模型只能互相降级替补，且都需下游筛选。专门场景工具（`soluble_mpnn_design`、`ligandmpnn_design`、`rfdiffusion_design`）没有等价替补。

### GROUP-Q 配体准备

| 工具 | 功能 | 替补 |
|---|---|---|
| `ligand_preprocess` | 配体格式/质子化/拓扑准备 | NONE |

### GROUP-R 对接

| 工具 | 功能 | 替补 |
|---|---|---|
| `diffdock_docking` | 蛋白-配体对接姿态 | NONE |

### GROUP-S 分子动力学

| 工具 | 功能 | 替补 |
|---|---|---|
| `gromacs_md` | MD 模拟与动态稳定性 | NONE |

### GROUP-T 信号肽预测

| 工具 | 功能 | 替补 |
|---|---|---|
| `signal_peptide_predict` | 信号肽与切割位点预测 | NONE |

### GROUP-U 基线理化属性

| 工具 | 功能 | 替补 |
|---|---|---|
| `predict_properties` | 序列衍生理化基线 | NONE |

## 真正互为等价替补的工具对/组

- `sequence_search` ↔ `blast_search`
- `esmfold_folding` ↔ `alphafold2_folding` ↔ `rosettafold_folding`
- `proteinmpnn_design` ↔ `esm_if1_design`

其余工具均不是等价替补。降级替补和不可替补边界见上表与 `tool_fallback_matrix.md`。

## 不可替补的硬边界（禁止偷换）

- 结构预测 ≠ 实测稳定性数据
- 对接姿态 ≠ 动力学预测
- 活性预测 ≠ 特异性比较
- 生成式设计 ≠ 点突变排序
- 文献检索 ≠ 实验验证
- 代理/缓存/计划结果 ≠ 真实 runtime 结果
