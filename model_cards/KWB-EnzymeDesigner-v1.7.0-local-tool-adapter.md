# KWB-EnzymeDesigner v1.7.0 Local Tool Adapter

状态：本地适配器完成，未修改生产平台，未同步服务器。

## 目标

把 GPT-5.6 主控未来需要调用的 KWB 工具边界在本地跑通：先执行结构工作流 gate，再决定是否调用 KWB-EnzymeDesigner，最后返回结构化结果和可审计事件。

## 新增产物

- `platform_integration/kwb_tool_adapter_local.py`
- `scripts/run_local_tool_adapter_demo.py`
- `reports/local_tool_adapter_demo.json`

## 行为

- 上传结构且编号已确认：调用规则 MVP，不调用 ESMFold。
- 上传结构但编号未确认：返回 `blocked`，不返回模型候选。
- 仅序列且预测结构未完成：返回 `pending_structure`，只允许序列级结论。
- 当前轮 ESMFold 完成并带有结构结果：允许调用 KWB。
- 每个事件带当前轮 `task_id`、依赖关系和 `local_only` 审计标记。

## 验证

- 上传结构调用 KWB 且不触发 ESMFold：通过。
- 编号未确认阻断 KWB：通过。
- 仅序列等待预测：通过。
- 预测结构完成后调用 KWB：通过。

## 边界

该适配器直接调用本地规则 MVP，仅用于验证调用顺序和返回合同；不代表后端 ToolRegistry、GPT-5.6 或线上平台已经接入。
