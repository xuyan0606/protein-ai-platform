# KWB-EnzymeDesigner v0.6.0 Data Integrity Gate

状态：本地数据完整性门控完成，监督模型质量声明继续阻断。

## 目标

防止错误编号和不可解析结构数据污染监督训练。

## 关键结果

- 输入增强监督标签：500 行
- 编号验证通过：25 行
- verified ratio：0.05
- mismatch：475 行
- 主要错误：`wild_type_mismatch_current_sequence`

## 结构数据状态

- `domain_architecture`：1942 行区间无效，不能用于位点级 domain 特征。
- `pdb_structures`：113836 条路径记录，但本地结构文件存在数为 0，不能直接做坐标解析。

## 编号修复判断

`numbering_repair_suggestions.json` 显示 mismatch 无单一主导 offset：

- +1：26 条
- -2：23 条
- -3：23 条
- ±20 内无 WT 匹配：109 条

结论：不能用简单偏移自动修复，需要 UniProt 版本、isoform 或文献编号回源。

## 产物

- `reports/mutation_label_integrity_report.json`
- `datasets/curated/enzyme_mutation_training_table_verified.jsonl`
- `reports/numbering_repair_suggestions.json`
- `datasets/label_curation_plan.md`
- `datasets/curated/enzyme_mutation_site_sequence_features.jsonl`

## 建模结论

当前应把未验证标签降级为 weak evidence，不进入强监督训练。下一步先做数据治理，再做更复杂模型。
