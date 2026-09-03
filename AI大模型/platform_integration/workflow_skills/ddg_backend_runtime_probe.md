# ddG 后端探测与 smoke

来源：ProteinMCP workflow skill 模式的 KWB 本地化版本。

## 输入

- `backend_name`
- `runtime_path`
- `license_receipt`
- `smoke_case`

## 步骤

1. 执行 license/config 路径检查
2. 执行 executable/module probe
3. 执行最小 smoke case 并写 receipt
4. 只在 validator 通过后更新 staging 状态

## 输出

- `ddg_runtime_probe_receipt.json`

## Validator

- `scripts/build_ddg_executable_probe.py`
- `scripts/validate_ddg_backend_runtime_receipts.py`

## 禁止动作

- 不写训练标签。
- 不写 production 配置。
- 不把工具分数当真实湿实验标签。
- 不把草稿或 UI 选择自动提升为 formal reviewed decision。
- `safe_for_model_claim=false` 和 `release_ready=false` 由硬门槛统一控制。
