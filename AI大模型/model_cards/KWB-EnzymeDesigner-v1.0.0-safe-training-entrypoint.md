# KWB-EnzymeDesigner v1.0.0 Safe Training Entrypoint

状态：本地安全训练入口完成，模型质量声明继续阻断。

## 目标

防止 weak evidence、未验证编号和带 integrity flags 的记录进入监督训练。

## 产物

- `scripts/build_repaired_supervised_table.py`
- `datasets/curated/enzyme_mutation_supervised_repaired_verified.jsonl`
- `reports/repaired_supervised_table_report.json`
- `reports/repaired_supervised_split_report.json`
- `reports/repaired_supervised_baseline_eval.json`
- `prototype/repaired_supervised_baseline_model.json`

## 当前结果

- repaired input rows：500
- strict supervised rows：25
- excluded rows：475
- groups：23
- label distribution：go 8、watch 9、no_go 8

## 训练入口规则

记录必须同时满足：

- `usable_as_supervised_label=true`
- `numbering_verified_by_sequence=true`
- `label_decision in {go, watch, no_go}`
- `integrity_flags` 为空

否则不得进入监督训练。

## 结论

训练入口已安全闭合，但强监督样本仍不足。下一步应通过 P0 curation batches 增加 verified/repaired 标签数。
