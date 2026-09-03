# 酶突变优先级分析

来源：ProteinMCP workflow skill 模式的 KWB 本地化版本。

## 输入

- `protein_sequence_or_id`
- `candidate_mutations`
- `reviewed_numbering_status`
- `feature_refs`

## 步骤

1. 检查 reviewed numbering 和 protected catalytic no-go
2. 读取 validated feature index 中的 MSA/structure/domain input-only 特征
3. 汇总 stability/activity/substrate/assay 风险证据
4. 输出人工复核候选，不写 formal decision

## 输出

- `mutation_prioritization_review_packet.json`

## Validator

- `scripts/validate_advanced_model_feature_contract_report.py`
- `scripts/validate_model_quality_hard_gate_contract.py`

## 禁止动作

- 不写训练标签。
- 不写 production 配置。
- 不把工具分数当真实湿实验标签。
- 不把草稿或 UI 选择自动提升为 formal reviewed decision。
- `safe_for_model_claim=false` 和 `release_ready=false` 由硬门槛统一控制。
