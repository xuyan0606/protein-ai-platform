# KWB-EnzymeCase 数据对象

`KWB-EnzymeCase` 是 KWB-EnzymeDesigner 的统一样本对象。它既用于训练数据，也用于 benchmark、工具调用、报告生成和实验反馈闭环。

## 设计目标

- 把“一个酶改造任务”表达成可训练、可检索、可评测的结构化对象。
- 支持序列级、预测结构级、实验结构级三种证据层。
- 支持成功样本和失败样本。
- 支持私有实验数据、公开数据库、文献和工具结果并存。
- 支持同一项目多轮实验优化。

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `case_id` | string | yes | 样本唯一 ID |
| `project_id` | string | no | 平台项目 ID |
| `case_type` | enum | yes | `stability` / `activity` / `substrate_fit` / `expression` / `multi_objective` |
| `objective` | object | yes | 本轮改造目标 |
| `enzyme` | object | yes | 酶基础信息 |
| `structure` | object | no | 结构来源和质量 |
| `substrate` | object | no | 底物和反应信息 |
| `assay_condition` | object | no | 实验条件 |
| `mutations` | array | no | 已知突变、候选突变或实验突变 |
| `evidence` | array | no | 证据来源 |
| `tool_results` | array | no | 平台工具结果摘要 |
| `labels` | object | no | 训练标签 |
| `quality` | object | yes | 数据质量和可用性 |
| `audit` | object | yes | 来源、版本、审核信息 |

## `objective`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `primary_goal` | string | yes | 主目标，如 `increase thermostability` |
| `secondary_goals` | array[string] | no | 次目标 |
| `constraints` | array[string] | no | 约束，如保留活性、不改催化残基 |
| `success_metric` | string | no | 成功指标，如 `Tm +5C`、`activity >= 80% WT` |

## `enzyme`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `name` | string | yes | 酶名称 |
| `family` | string | no | 家族，如 GH13、lipase |
| `ec_number` | string | no | EC 编号 |
| `organism` | string | no | 来源物种 |
| `uniprot_id` | string | no | UniProt ID |
| `sequence` | string | no | 氨基酸序列 |
| `sequence_md5` | string | no | 序列 MD5，便于去重 |
| `numbering_system` | string | no | 编号体系说明 |

## `structure`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `source_type` | enum | no | `uploaded_pdb` / `pdb` / `alphafold` / `esmfold` / `none` |
| `object_name` | string | no | 平台文件对象 |
| `pdb_id` | string | no | PDB ID |
| `chain_id` | string | no | 链 ID |
| `confidence` | number | no | 结构置信度或平均 pLDDT |
| `numbering_verified` | boolean | no | 是否完成编号确认 |
| `residue_mapping_ref` | string | no | SIFTS/比对映射引用 |
| `quality_flags` | array[string] | no | 缺失残基、低置信度、链歧义等 |

## `substrate`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `name` | string | no | 底物名称 |
| `smiles` | string | no | SMILES |
| `sdf_object` | string | no | SDF 文件对象 |
| `reaction` | string | no | 反应描述 |
| `pocket_residues` | array[integer] | no | 已知或推断口袋位点 |

## `assay_condition`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `ph` | number/string | no | pH |
| `temperature_c` | number/string | no | 温度 |
| `buffer` | string | no | buffer |
| `expression_system` | string | no | 表达体系 |
| `assay_method` | string | no | 检测方法 |
| `replicates` | integer | no | 重复数 |

## `mutations`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `code` | string | yes | 突变码，如 `A128P` |
| `position` | integer | no | 位点 |
| `wild_type` | string | no | WT 残基 |
| `mutant` | string | no | 突变残基 |
| `source` | enum | no | `candidate` / `literature` / `experiment` / `model` |
| `status` | enum | no | `untested` / `go` / `watch` / `no_go` / `failed` |
| `rationale` | string | no | 推荐理由 |
| `risk_flags` | array[string] | no | 风险标记 |

## `evidence`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `evidence_id` | string | yes | 证据 ID |
| `source` | enum | yes | `kwb_private` / `literature` / `uniprot` / `pdb` / `alphafold` / `brenda` / `tool` |
| `source_ref` | string | no | DOI、数据库 ID、任务 ID |
| `evidence_type` | enum | yes | `experimental` / `curated` / `predicted` / `inferred` |
| `summary` | string | yes | 简述 |
| `confidence` | number | no | 0-1 |

## `tool_results`

保存工具结果摘要，不保存大型 artifact 原文。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `tool_name` | string | yes | 工具名 |
| `status` | enum | yes | `completed` / `failed` / `blocked` |
| `result_ref` | string | no | 任务或文件引用 |
| `summary` | object | no | 可训练的结构化摘要 |
| `quality_flags` | array[string] | no | 工具质量标记 |

## `labels`

用于训练和评测。

| 字段 | 类型 | 说明 |
|---|---|---|
| `activity_relative_to_wt` | number | 相对 WT 活性 |
| `stability_delta_tm_c` | number | Tm 变化 |
| `half_life_fold_change` | number | 半衰期倍数 |
| `expression_relative_to_wt` | number | 表达量相对值 |
| `substrate_fit_label` | enum | `improved` / `neutral` / `worse` / `unknown` |
| `assay_success` | boolean | 是否达到目标 |
| `decision` | enum | `go` / `watch` / `no_go` |

## `quality`

| 字段 | 类型 | 说明 |
|---|---|---|
| `data_quality_score` | number | 0-100 |
| `usable_for_training` | boolean | 是否可训练 |
| `usable_for_benchmark` | boolean | 是否可进入 benchmark |
| `missing_fields` | array[string] | 缺失字段 |
| `warnings` | array[string] | 风险提醒 |

## `audit`

| 字段 | 类型 | 说明 |
|---|---|---|
| `created_at` | string | ISO 时间 |
| `updated_at` | string | ISO 时间 |
| `source_owner` | string | 数据归属 |
| `review_status` | enum | `draft` / `reviewed` / `accepted` / `rejected` |
| `data_version` | string | 数据版本 |

## 数据质量评分建议

| 条件 | 分数 |
|---|---:|
| 有实验标签 | +25 |
| 有明确序列 | +15 |
| 有实验结构或高置信预测结构 | +15 |
| 有明确 assay 条件 | +15 |
| 有底物/反应信息 | +10 |
| 有证据来源和审核状态 | +10 |
| 有失败样本原因 | +10 |

低于 50 分：只用于证据展示。  
50-75 分：可用于弱监督或辅助评测。  
75 分以上：可进入训练集或核心 benchmark。

