# KWB-EnzymeDesigner v0.9.0 Curation Operations

状态：本地编号回源运营工作包完成。

## 目标

把编号回源治理推进到可执行批次：

- 选择高优先级 P0 记录。
- 生成 JSONL 和 Markdown 工作包。
- 校验回源决策。
- 安全应用决策。
- 汇总 curation dashboard。

## 产物

- `scripts/build_curation_batches.py`
- `datasets/curation/batches/p0_batch_001.jsonl`
- `datasets/curation/batches/p0_batch_001.md`
- `scripts/validate_numbering_curation_decisions.py`
- `scripts/build_curation_dashboard.py`
- `reports/curation_batch_report.json`
- `reports/numbering_curation_validation_report.json`
- `reports/curation_dashboard.json`

## 当前结果

- P0 可回源记录：213
- 已生成批次：5
- 覆盖记录：125
- 当前真实决策：0
- apply 后强监督标签：25

## 安全门控

`map_to_canonical` 必须满足：

- canonical fields 完整。
- canonical UniProt 当前序列存在。
- canonical position 在范围内。
- canonical WT 与当前序列该位点一致。
- confidence >= 0.5。

否则保留 weak evidence，不提升为强监督标签。
