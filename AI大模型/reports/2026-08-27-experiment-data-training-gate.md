# 2026-08-27 实验数据训练前置门

## 结论

当前监督训练仍保持 `blocked`：

- `ready_for_training_import_rows=0`
- `ready_for_feedback_intake_rows=0`
- `training_execution_allowed=false`
- `safe_for_model_claim=false`
- `release_ready=false`

本次没有修改 `datasets/feedback/experiment_feedback.local.jsonl`，没有消耗 sealed evaluation attempt，也没有启动监督训练。

## 只读盘点

输入目录：

`实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据`

| 数据库 | 原始测量 | 总体判断 | 单条判读 | 派生分析 |
|---|---:|---:|---:|---:|
| 15B 低 pH 酶活/稳定性 | 198 | 44 | 190 | 190 |
| 16B 稳定性/比活力 | 99 | 33 | 66 | 66 |
| 4G 比活力 | 641 | 23 | 315 | 189 |

审计脚本结果：

- 历史反馈源 4 条，`training_eligible_rows=0`；阻断原因包括缺少条件/重复/QC 上下文、预测或咨询源主导、缺少明确突变 token。
- 授权校验：12 条候选中 8 条授权记录格式有效，4 条候选仍缺授权；这 8 条仅允许进入 feedback preflight，不允许直接追加训练表。
- human preflight：3 个 lane 的包结构有效，但 `ready_for_training_import_rows=0`。
- wet-lab preflight：8 条记录，`ready_for_feedback_intake_rows=0`。
- review-draft 泄漏校验通过：514 条 draft 未进入任何训练/导入表；严格监督表和 claim-eligible 表均为 0 条。
- 多头训练就绪校验：5 个 head 均未达到 100 条严格标签门槛，`training_execution_allowed=false`。

## 下一解锁条件

1. 对缺失的 4 条候选补齐可验证的人工授权回执。
2. 对 8 条已授权候选补齐人工复核、编号/母本序列核验、实验条件、重复和 QC 证据，并重新运行 preflight。
3. 只有 preflight 明确产生可训练行、来源哈希和 owner 回执后，另行建立新的监督训练预注册实验；不得复用 GELU-only 实验结果。

## 证据复核

原始 CSV 与说明文件已在本地计算 SHA-256。复核命令：

```bash
find '实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据' -type f -print0 \
  | xargs -0 shasum -a 256
```

哈希只用于本地来源绑定，不代表数据已获训练授权或已形成模型质量证据。
