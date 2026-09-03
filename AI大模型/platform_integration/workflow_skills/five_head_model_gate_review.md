# 五头模型训练门控复核

来源：ProteinMCP workflow skill 模式的 KWB 本地化版本。

## 输入

- `training_label_import_contract`
- `wet_lab_authorization_contract`
- `benchmark_coverage`
- `physics_ddg_state`

## 步骤

1. 检查五个 head 的 training-import-eligible rows
2. 检查 benchmark ready_for_model_claim
3. 检查 physics ddG 是否为 Rosetta/PyRosetta/FoldX 真实后端
4. 输出 model-quality hard-gate 状态，不训练、不声明

## 输出

- `five_head_gate_review_report.json`

## Validator

- `scripts/validate_five_head_training_execution_contract_report.py`
- `scripts/validate_model_quality_hard_gate_contract.py`

## 禁止动作

- 不写训练标签。
- 不写 production 配置。
- 不把工具分数当真实湿实验标签。
- 不把草稿或 UI 选择自动提升为 formal reviewed decision。
- `safe_for_model_claim=false` 和 `release_ready=false` 由硬门槛统一控制。
