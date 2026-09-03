# 酶性质工作流强制执行（P0）设计

## 目标

将现有仅供观察的性质路由提升为聊天主链路的前置运行态守卫：普通问答不调工具，缺少酶改造关键输入时只追问，续问不重启工作流。

## 范围

本批只覆盖 P0：意图分类、输入门控和统一任务契约。不会更换工具算法、数据库 schema 或执行完整的五类性质工作流。

## 方案

新增纯函数服务 `enzyme_workflow_runtime`，输入当前消息、会话历史与已有性质路由结果，输出稳定的任务契约：`intent`、`session_id`、`intake_status`、`workflow_id`、`route_reason`、`route_confidence`、`known_inputs`、`input_gaps`、`final_status`、空的 `trace`/`fallback_trace`。

聊天编排器在调用旧 router 前消费该契约：

- `NON_EXECUTION` 直接由 LLM 回答，禁止计划/工具。
- `FOLLOW_UP` 在已有任务上下文下走现有同题续问路径，禁止重新规划。
- 新酶改造任务缺序列、PDB 或明确可检索标识时进入 `WAITING_FOR_USER_INPUT`，返回固定追问，禁止计划/工具。
- `READY_FOR_ANALYSIS` 保持现有计划确认和工具执行语义，但把运行态契约带入 SSE state，供前端和审计读取。

`TARGET_CHANGE`、`INPUT_UPDATE` 先以纯函数准确分类和 SSE 契约落地；本批不强制清除旧 checkpoint，后续路由锁定批次处理该行为。

## 失败与降级

本批前置守卫不调用任何外部工具，因此没有隐式降级；`fallback_trace=[]` 明示“无降级”。若输入不足，`final_status=NEEDS_INPUT`，而非“分析完成”。

## 验收

单元测试必须覆盖：概念问答、连续“继续”、补充 FASTA、改目标、缺序列的“提高比活力”、以及运行态契约的字段完整性。集成测试必须确认缺输入与普通问答在 `plan_only` 下均不调用 `_plan_cb` 或 `ToolRegistry.execute`。
