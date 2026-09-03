# 编号人工审核正式化

来源：ProteinMCP workflow skill 模式的 KWB 本地化版本。

## 输入

- `queue_row`
- `evidence_source`
- `reviewer_decision`
- `correction_if_wrong`

## 步骤

1. 从 UI 或 packet 查看 WT/突变位点/证据
2. 正确则写 accept，错误则写 corrected_position 与 notes
3. 运行 validate_numbering_curation_decisions
4. 运行 apply_numbering_curation，但训练 gate 继续另行判断

## 输出

- `numbering_curation_decision.jsonl`

## Validator

- `scripts/validate_numbering_curation_decisions.py`
- `scripts/apply_numbering_curation.py`

## 禁止动作

- 不写训练标签。
- 不写 production 配置。
- 不把工具分数当真实湿实验标签。
- 不把草稿或 UI 选择自动提升为 formal reviewed decision。
- `safe_for_model_claim=false` 和 `release_ready=false` 由硬门槛统一控制。
