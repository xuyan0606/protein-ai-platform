# 湿实验反馈授权导入审核

来源：ProteinMCP workflow skill 模式的 KWB 本地化版本。

## 输入

- `wet_lab_candidate_rows`
- `source_file_receipt`
- `metric_unit`
- `authorization_decision`

## 步骤

1. 核实来源、突变编号、单位、重复和批次
2. 区分 qualitative feedback 与 numeric training import
3. 生成 preflight，不直接写训练表
4. 运行授权 validator 和 apply-plan builder

## 输出

- `wet_lab_feedback_authorization_receipt.json`

## Validator

- `scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`
- `scripts/build_wet_lab_mutant_library_feedback_preflight.py`

## 禁止动作

- 不写训练标签。
- 不写 production 配置。
- 不把工具分数当真实湿实验标签。
- 不把草稿或 UI 选择自动提升为 formal reviewed decision。
- `safe_for_model_claim=false` 和 `release_ready=false` 由硬门槛统一控制。
