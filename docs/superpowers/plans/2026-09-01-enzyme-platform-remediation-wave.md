# 酶改造 AI 平台全量整改波次实现计划

> **面向 AI 代理的工作者：** 使用 `executing-plans` 逐项实施。每项先写失败测试，再实现最小代码；外部环境任务只能生成就绪度检查，不得伪造执行成功。

**目标：** 启动治理、工具、可靠性和运行能力四个整改工作包，并让每一项具有可验证状态。

**架构：** 后端任务契约继续作为治理事实源；工具 manifest 和缺失台账形成工具基线；前端流式 hook 消费统一错误状态；运行依赖通过只读诊断检查验证。

**技术栈：** Python、FastAPI、pytest、React/TypeScript、Vitest。

---

### 任务 1：真实会话症状回归

**文件：**
- 创建：`backend/tests/enzyme_workflow_regression_cases.json`
- 修改：`backend/tests/test_enzyme_workflow_runtime.py`

- [x] 写脱敏 `conv_78`、`conv_225`、`conv_226` 的运行态案例，覆盖续问、输入补充、目标切换和解释问答。
- [x] 在 pytest 中参数化读取案例，断言任务契约字段。
- [x] 运行：`./backend/.venv/bin/python -m pytest backend/tests/test_enzyme_workflow_runtime.py -q` -> `15 passed`。

### 任务 2：缺失工具台账与运行时对账

**文件：**
- 创建：`backend/app/services/tool_baseline_manifest.py`
- 修改：`backend/app/api/tools.py`
- 创建：`backend/tests/test_tool_baseline_manifest.py`

- [x] 编写失败测试，定义 catalog 与运行时 registry 的对账结果。
- [x] 实现确定性台账，输出 `available`、`degraded`、`pending_reconnect`、`not_applicable`。
- [x] 将台账摘要加入 `/api/tools` manifest。
- [x] 运行：`./backend/.venv/bin/python -m pytest backend/tests/test_tool_baseline_manifest.py -q` -> 当前 4 条基线测试均通过；另有完整工具 API 回归 `134 passed`。
- [x] 修正台账降级语义：仅在实际存在可用替补工具时标记 `fallback_level=DEGRADED`；无替补的缺失工具保持 `pending_reconnect` 且 `fallback_level=null`，避免将不可执行项伪装为已降级可用。工具台账与 API 回归 `137 passed`。
- [x] 分离配置候选与实际替补：`configured_fallback_tool` 保留待接回时的候选诊断信息；`fallback_tool` 仅在候选在线时返回，避免调用方误把离线候选当作可执行降级。工具台账与 API 回归 `138 passed`。
- [x] 固化 `/api/tools` baseline entry 字段契约，要求每行同时提供配置候选、实际替补和降级级别字段；完整工具 API 回归 `134 passed`。

### 任务 3：前端服务不可达提示

**文件：**
- 修改：`frontend/src/hooks/useChatStream.ts`
- 修改：`frontend/src/stores/chat.ts`
- 创建或修改：`frontend/tests/useChatStream.test.ts`

- [x] 检查现有前端测试能力：当前无 Vitest/Jest 入口，避免为单条文案无授权引入测试框架。
- [x] 统一连接拒绝、reader 中断、网络错误和非 OK 响应为“服务暂不可用，请稍后重试”。
- [x] 运行：`npm run build` -> passed。

### 任务 4：运行依赖就绪度

**文件：**
- 创建：`backend/app/services/model_runtime_readiness.py`
- 修改：`backend/app/api/tools.py`
- 创建：`backend/tests/test_model_runtime_readiness.py`

- [x] 写 torch/transformers 不可用时返回 `blocked` 的失败测试。
- [x] 实现只读导入检查，输出 ESM-2 运行状态、原因和建议动作。
- [x] 加入工具 diagnostics，不下载权重、不安装依赖。
- [x] 运行：`./backend/.venv/bin/python -m pytest backend/tests/test_model_runtime_readiness.py -q` -> `1 passed`。

### 任务 5：全量本地回归和交接

**文件：**
- 修改：`docs/superpowers/plans/2026-09-01-enzyme-platform-remediation-wave.md`
- 修改：`progress.md`

- [x] 运行后端相关回归、前端 lint/build、`py_compile` 和 `git diff --check`：后端相关回归 `213 passed in 34.58s`。
- [x] 将外部依赖、模型安装与线上验收明确记录为 `blocked` 或 `ready_for_operator`。

### 任务 6：其余性质工作流的执行目录强制

**文件：**
- 修改：`backend/app/services/property_workflow_governance.py`
- 修改：`backend/tests/test_property_workflow_governance.py`

- [x] 将 `WF-ACTIVITY`、`WF-PH`、`WF-SPECIFICITY`、`WF-EXPRESSION` 从临时设计工具黑名单升级为交付包定义的显式工具目录。
- [x] 对未声明工具和各流程禁用工具 fail-closed；仍允许文档定义的条件工具（例如活性流程的 `diffdock_docking`、特异性流程的 `ligandmpnn_design`、表达流程的 `signal_peptide_predict`）。
- [x] 运行：`./backend/.venv/bin/python -m pytest backend/tests/test_property_workflow_governance.py -q` -> `26 passed in 2.32s`。
- [x] 完整相关回归（agent、治理、运行态、报告质量、ops、工具基线、模型 readiness、remediation readiness、工具 API）-> `348 passed in 53.62s`。

### 任务 7：身份一致性持久化契约

**文件：**
- 创建：`backend/app/models/identity_consistency.py`
- 创建：`backend/app/services/identity_consistency_store.py`
- 创建：`backend/alembic/versions/c7e5a1b2d9f0_add_identity_consistency_records.py`
- 创建：`backend/tests/test_identity_consistency_persistence.py`

- [x] 增加按用户、序列哈希、模型版本和证据版本隔离的身份一致性记录表。
- [x] 增加最新记录写入/读取服务和唯一约束，支持冲突审计。
- [x] Alembic head 收敛为 `c7e5a1b2d9f0`；持久化回归 `17 passed`。
- [x] 将同步身份判定点接入 orchestrator 的异步数据库写入；数据库不可用时保留进程内缓存并记录 warning，避免阻断已有分析。
- [ ] 在目标部署环境执行迁移并完成跨进程读写 smoke；本地测试不替代生产迁移验收。
- [x] 修正 Alembic 元数据导入，纳入 `strategy_checkpoint` 与 `identity_consistency` 模型；配置与持久化回归 `122 passed in 6.23s`，本地 `alembic heads` 为单一 `c7e5a1b2d9f0`。
- [x] 身份记录重复写入按版本化唯一键幂等返回已有记录，避免重复运行产生 `IntegrityError` 告警；身份持久化与运行态回归 `19 passed`。

### 任务 8：报告交付门槛空值拦截

**文件：**
- 修改：`backend/app/services/report_quality_contract.py`
- 修改：`backend/tests/test_report_quality_contract.py`

- [x] 对证据、候选位点、优先级和实验动作中的显式空值（如“无”“未提供”“未评估”）执行 `NEEDS_REVIEW` 拦截。
- [x] 保持普通报告不受影响，并通过发布与 agent 回归：`206 passed in 7.47s`。
