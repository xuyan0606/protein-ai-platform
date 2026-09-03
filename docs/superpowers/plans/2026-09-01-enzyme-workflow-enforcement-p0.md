# 酶性质工作流强制执行（P0）实现计划

> **面向 AI 代理的工作者：** 按 TDD 逐项实现；每个任务先写失败测试，再实现最小代码并运行指定测试。

**目标：** 在聊天主链路强制执行酶性质任务的意图和输入门控，并输出统一任务契约。

**架构：** 新增无副作用运行态服务，复用 `PropertyWorkflowRouter` 的性质路由结果。`AgentOrchestrator.stream_chat` 在旧 LLM router 前执行该服务，并将契约嵌入 SSE state。

**技术栈：** Python 3、FastAPI、pytest、现有 `AgentOrchestrator`。

---

### 任务 1：运行态契约服务

**文件：**
- 创建：`backend/app/services/enzyme_workflow_runtime.py`
- 测试：`backend/tests/test_enzyme_workflow_runtime.py`

- [x] 编写分类和契约失败测试。
- [x] 运行 `python -m pytest backend/tests/test_enzyme_workflow_runtime.py -q`，确认因模块缺失失败。
- [x] 实现 `evaluate_enzyme_workflow_runtime(message, history, session_id)`。
- [x] 重跑同一命令，确认通过。

### 任务 2：聊天前置门控与 SSE 契约

**文件：**
- 修改：`backend/app/core/agent_graph.py`
- 修改：`backend/tests/test_property_workflow_governance.py`

- [x] 编写 `plan_only` 下普通概念问答和缺序列任务不进入 `_plan_cb` 的失败测试。
- [x] 运行 `python -m pytest backend/tests/test_property_workflow_governance.py -q`，确认新增断言失败。
- [x] 将运行态契约写入 `ChatSnapshot`，在旧 router 前消费 `NON_EXECUTION`、`FOLLOW_UP` 和 `NEEDS_INPUT`。
- [x] 重跑该测试文件，确认通过。

### 任务 3：回归与边界验证

**文件：**
- 测试：`backend/tests/test_enzyme_workflow_runtime.py`
- 测试：`backend/tests/test_property_workflow_governance.py`

- [x] 运行两份定向测试及相关现有测试。
- [x] 运行 `python -m py_compile backend/app/services/enzyme_workflow_runtime.py backend/app/core/agent_graph.py`。
- [x] 对照设计逐项核对状态字段、无工具门控和续问不重跑的验收结果。

### 任务 4：确认执行 trace 与策略兼容性

**文件：**
- 修改：`backend/app/core/agent_graph.py`
- 修改：`backend/app/services/property_workflow_governance.py`
- 修改：`backend/tests/test_property_workflow_governance.py`

- [x] 确认 `execute_confirmed` 仅在签名严格匹配的 checkpoint 下进入执行，并为结果逐步写入 `task_contract.trace[]`。
- [x] 补充确认执行 trace 回归用例；测试夹具使用完整、已签名的计划，覆盖真实 checkpoint 边界。
- [x] 将声明工具硬拦截限定到已有完整 allow/deny 策略的 `WF-STABILITY`；未迁移的工作流继续按 legacy 路径执行，并在契约中明示策略尚未启用。
- [x] 回归：`test_enzyme_workflow_runtime.py`、`test_property_workflow_governance.py`、`test_agent_binder.py` 共 `184 passed`。

### 后续迁移边界

- [ ] 为 `WF-ACTIVITY`、`WF-PH`、`WF-SPECIFICITY`、`WF-EXPRESSION` 分别补齐经业务确认的工具 allow/deny catalog，再逐项启用同等硬拦截。
- [ ] 将真实会话 `conv_78`、`conv_225`、`conv_226` 的脱敏 dump 固化为回归样本。
- [x] 先固化脱敏的运行态症状回归：`继续`、`再说人话`、`这个什么意思` 在已有任务中均识别为 `FOLLOW_UP`；已有蛋白上下文中的解释性问句识别为 `NON_EXECUTION`。
- [ ] 接入完整的步骤级 workflow adapter、用户可见的降级文案及最终报告完成门槛校验。
- [x] 接入第一层最终报告完成门槛：结构化酶报告缺少证据、候选位点、优先级、风险或实验动作时，`task_contract.final_status=NEEDS_REVIEW` 并输出 `report_quality_violations[]`。
- [x] 工具失败/阻断在结果收集层写入 `fallback_trace[]`，最终报告增加“执行降级提示”，明确主工具未完成及降级原因。
- [x] 增加序列哈希身份一致性护栏：同一序列出现冲突身份时标记 `NEEDS_REVIEW`，保留首次身份，不强行覆盖。
- [x] 强化 `/api/health`：返回服务标识、版本、已注册工具数量和用户可见状态消息，启动或部分不可用时不返回空响应。
- [x] 补齐 supplementary steps 的 trace/fallback 留痕：复审阶段追加、参数缺失、超时和异常均记录到同一任务契约。
- [x] 在 `/api/tools` 响应加入运行时工具 manifest（数量、名称 SHA-256、来源和版本），作为线上工具基线的机器可比单一事实源。
- [x] 将明确的设计/对接工具边界扩展到 `WF-ACTIVITY`、`WF-PH`、`WF-SPECIFICITY`、`WF-EXPRESSION`；未迁移的分析工具保持兼容，设计工具命中时先进入 `NEEDS_REVIEW`。
- [x] 修正身份一致性缓存键为序列 hash + 模型版本 + 证据版本，避免跨版本结果被错误判为冲突。
