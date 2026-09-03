# KWB-EnzymeDesigner v1.6.0 Structure Workflow Gate

状态：本地结构工作流门控完成，未修改生产平台，未同步服务器。

## 目标

把结构来源优先级、编号校验和 task_id 会话隔离变成可执行的本地规划器，避免模型回答顺序与事件流顺序不一致。

## 门控规则

- 上传 PDB/mmCIF：先解析结构、确认链和编号，再进入结构分析；不先提交 ESMFold。
- 已有 PDB/AlphaFold/ESMFold：走结构引用解析和编号门控，不重复预测。
- 仅序列：可先运行序列级分析，但口袋、距离、催化网络、暴露度和 KWB 结构结论等待预测结构。
- 编号未确认：结构依赖步骤为 `blocked`，不能输出结构位点结论。
- 所有结果引用必须匹配 `session_id`、`conversation_id`、`request_turn_id`。
- task_id 按当前会话和轮次生成，旧轮次引用会被忽略。

## 新增产物

- `platform_integration/structure_workflow_gate.py`
- `scripts/run_structure_workflow_gate.py`
- `reports/structure_workflow_gate_demo.json`

## 验证

- 上传结构优先级断言：通过。
- 编号未确认阻断断言：通过。
- 仅序列等待结构预测断言：通过。
- 旧 task_ref 隔离断言：通过。
- turn-scoped task_id 断言：通过。

## 边界

这只是本地规划和回归 gate，不代表生产后端已经接入。当前 GPT-5.6 主控和 KWB 专业工具的架构关系不变。
