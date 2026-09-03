# KWB-EnzymeDesigner 特征字典

## 目标

把 `KWB-EnzymeCase` 转换成可训练、可评测、可解释的结构化特征。

## 特征分组

### 1. 输入完整性特征

| 特征 | 类型 | 说明 |
|---|---|---|
| `has_sequence` | bool | 是否有序列 |
| `sequence_length` | int | 序列长度 |
| `has_structure` | bool | 是否有结构 |
| `structure_source_uploaded_pdb` | bool | 上传结构 |
| `structure_source_predicted` | bool | AlphaFold/ESMFold |
| `numbering_verified` | bool | 编号是否确认 |
| `has_substrate` | bool | 是否有底物 |
| `has_assay_condition` | bool | assay 条件是否足够 |

### 2. 突变特征

| 特征 | 类型 | 说明 |
|---|---|---|
| `mutation_position` | int | 位点 |
| `wild_type` | string | WT 氨基酸 |
| `mutant` | string | 突变氨基酸 |
| `is_proline_mutation` | bool | 是否突变为 Pro |
| `is_charge_mutation` | bool | 是否涉及 D/E/K/R |
| `is_glycine_or_proline_origin` | bool | WT 是否为 G/P |
| `has_prior_go` | bool | 历史反馈是否 go |
| `has_prior_no_go` | bool | 历史反馈是否 no_go/failed |

### 3. 结构/安全特征

| 特征 | 类型 | 说明 |
|---|---|---|
| `risk_protected_catalytic` | bool | 催化保护 |
| `risk_near_active_site` | bool | 活性中心附近 |
| `risk_near_pocket` | bool | 口袋附近 |
| `risk_numbering_uncertain` | bool | 编号不确定 |
| `risk_low_structure_confidence` | bool | 结构置信度低 |

### 4. 证据特征

| 特征 | 类型 | 说明 |
|---|---|---|
| `kwb_private_records` | int | 私有记录数 |
| `public_database_records` | int | 公开数据库/文献记录数 |
| `tool_result_count` | int | 工具结果数量 |
| `has_ligand_tool_result` | bool | 是否有配体工具结果 |
| `has_md_tool_result` | bool | 是否有 MD 结果 |
| `has_annotation_result` | bool | 是否有注释结果 |

### 5. Assay 特征

| 特征 | 类型 | 说明 |
|---|---|---|
| `assay_has_ph` | bool | 有 pH |
| `assay_has_temperature` | bool | 有温度 |
| `assay_has_expression_system` | bool | 有表达体系 |
| `assay_completeness` | int | assay 完整度 |

### 6. 监督 mutation 表新增特征

| 特征 | 类型 | 说明 |
|---|---|---|
| `position_fraction` | number | 突变位点在序列中的相对位置 |
| `charge_delta` | number | 突变前后电荷变化 |
| `charge_abs_delta` | number | 电荷变化绝对值 |
| `hydropathy_delta` | number | Kyte-Doolittle 疏水性变化 |
| `volume_delta` | number | 氨基酸体积变化 |
| `volume_abs_delta` | number | 体积变化绝对值 |
| `method_cd` | bool | CD/圆二色谱 assay |
| `method_calorimetry` | bool | DSC/量热 assay |
| `method_fluorescence` | bool | 荧光 assay |
| `method_denaturation` | bool | 变性 assay |
| `method_thermal_shift` | bool | thermal shift/Tm assay |

## 标签

### 可训练标签

| 标签 | 类型 | 说明 |
|---|---|---|
| `label_decision` | enum | `go` / `watch` / `no_go` |
| `label_assay_success` | bool/null | 是否达到目标 |
| `label_activity_relative_to_wt` | number/null | 相对 WT 活性 |
| `label_stability_delta_tm_c` | number/null | Tm 变化 |
| `label_substrate_fit` | enum/null | `improved` / `neutral` / `worse` |

### 不能直接作为训练标签

- GPT 报告中的自然语言判断。
- 未经验证的 docking score。
- 未经验证的 MD 单次短模拟结论。
- 没有来源的文献摘要。
- 模型自己生成的推断。
- 当前 stability label 由 dTm/ddG 规则派生时，`label_stability_delta_tm_c` 和 `label_ddg` 不得作为输入特征。

这些可以作为特征或证据，但不能当实验标签。

## 第一版 baseline

第一版 baseline 使用规则打分，不训练神经网络：

```text
features -> weighted score -> go/watch/no_go
```

后续小模型训练时，优先训练：

1. `mutation_rank_head`
2. `stability_head`
3. `activity_risk_head`
