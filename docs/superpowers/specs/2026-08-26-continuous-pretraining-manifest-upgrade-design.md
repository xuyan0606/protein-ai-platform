# 连续预训练资产 Manifest 升级设计

## 目标

将预训练资产包的当前基准从独立批次 `sequence_mlm_batch_0001.checkpoint.pt` 切换为已连续覆盖全部 12,830 条去重序列的 `sequence_mlm_continuous_full.checkpoint.pt`，同时保留旧批次产物作为历史证据。

## 范围

- 更新当前 checkpoint 选择清单，使其引用连续训练报告、连续 checkpoint、输入哈希和 checkpoint 哈希。
- 更新资产 manifest，使其绑定连续训练报告、连续 checkpoint、连续索引校验、连续碰撞审计、模型卡和发布隔离判定。
- 更新模型卡中的当前基准描述。
- 重新生成发布隔离判定并保持 `release_ready=false`、`safe_for_supervised_training=false`、`safe_for_model_claim=false`。
- 新增回归测试，阻止当前 manifest 再次引用 `sequence_mlm_batch_*.checkpoint.pt`。

## 不在范围内

- 不删除或覆盖任何旧 checkpoint、旧报告或旧索引。
- 不启动监督训练、微调、线上推理或生产发布。
- 不将 validation loss、embedding 相似度或无碰撞解释为生物学性能。

## 数据流

连续训练报告与 checkpoint → 连续基准选择清单 → 发布隔离门 → 哈希绑定资产 manifest → manifest 完整性验证。

旧 batch-0001 选择清单保留为历史文件或由新清单中的 `supersedes` 字段记录，不再作为当前资产包依赖。

## 失败策略

- 连续 checkpoint、训练报告、索引校验或碰撞审计任一缺失：构建失败。
- 文件大小或 SHA-256 不匹配：验证失败。
- manifest 引用独立批次 checkpoint：验证失败。
- 任一安全边界被改为 true 或发布状态被放宽：验证失败并保持 `release_ready=false`。

## 测试与验收

- 先新增失败测试，证明旧 manifest 会因引用 batch-0001 而失败。
- 实现最小升级逻辑后，定向测试和 AI 大模型全量单测通过。
- 运行 manifest 生成与验证，要求：缺件 0、哈希不一致 0、边界检查通过。
- 独立读取最终 manifest，确认包含连续 checkpoint 且不包含 `sequence_mlm_batch_*.checkpoint.pt`。
