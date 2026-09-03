# 进度记录

## 2026-08-15

- 用户明确反馈报告质量、策略质量、上下文能力和格式都不合格。
- 已停止继续盲目修复业务代码。
- 创建独立规划目录 `.planning/report_quality_replan/`。
- 创建 `task_plan.md`、`findings.md`、`progress.md`，用于后续质量重构。
- 当前没有部署。

## 未决事项

- 决定是否回滚上一轮未部署的止损改动。
- 需要收集失败案例形成评测集。
- 需要先定义报告质量契约，再进入代码修改。

## 2026-08-15 修复质量审查

- 按用户要求只做审查，不继续修代码。
- 运行 `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q`，结果为 `123 passed, 1 failed`。
- 失败测试为新增的双目标策略测试，说明上一轮止损改动没有达到可合入标准。
- 发现策略文案出现明显错误：“门控未过时”，应为“门控未通过时”。
- 发现更严重的问题：双目标只改了策略文本，执行计划仍然把 `objectives` 压成单个 `eng_goal`，后续 `enzyme_objective_module_plan` 和 `mutation_priority_score` 仍只按单目标运行。
- 结论：上一轮修复质量不合格，应暂停并按重构计划处理。

## 2026-08-15 文档反馈整合

- 已读取 `/Users/keweibo/Desktop/未命名文件夹/AI平台反馈V5.doc`。
- 文档补充了三条强约束：固定报告顺序、压缩英文模板段落、解释结果对应的工具链。
- 这些约束已写入 `task_plan.md` 和 `findings.md`，后续整改必须同时覆盖策略、执行、报告和前端展示。

## 2026-08-15 最小闭环修正

- 修复策略确认文案中的错误表达“门控未过时”，统一为“门控未通过时”。
- 调整后端 fallback 报告结构：移除核心报告里的独立“结论卡片 / 状态摘要”和 “Go / Watch / No-Go” 章节；把决策状态合并到突变位点清单，把决策规则合并到“探索性验证建议”。
- 身份/编号门控未通过时，固定输出“突变位点探索清单（未放行）”“位点突变逻辑 / 风险 / 实验动作”“探索性验证建议”，但不输出具体突变表。
- 将突变核心块放到 `Objective Module Gate` 之后；附录子标题降为 `###`，不再污染主报告目录。
- 对有突变门控/候选的报告，压缩 EC/kcat 等背景段落，避免启发式结果被误读为比活力或候选排序依据。
- 修正 Wiki 发布包装层：结构化酶工程报告不再被“用户提问 / 研究背景 / 分析管线 / 分析报告”外壳重新包裹；发布流程、证据源和原始工具结果降到附录。
- 前端移除 `ChatInput.tsx` 中未使用的 `updateLastAssistant`，恢复 lint 质量门。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py backend/app/tools/enzyme_objective_module_plan.py backend/app/tools/mutation_priority_score.py`：通过。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q`：124 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_publish.py -q`：26 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py -q`：150 passed。
- `npm run lint`：通过。
- `npm run build`：通过。

### 仍未完成

- 已建立首批 7 个报告质量失败案例；后续需要继续补真实用户样本和续问样本。
- 尚未完整重构续问质量复核模式。
- 尚未部署；当前只是本地代码和测试收口。

## 2026-08-15 阶段 1 评测集落地

- 新增 `backend/tests/enzyme_report_quality_cases.json`，先落地 7 个报告质量回归用例。
- 新增 `TestEnzymeReportQualityEvalSet.test_report_quality_contract_cases`，用参数化测试检查 required/forbidden/ordered_headings。
- 覆盖失败模式：PDB-only 身份阻断、多目标比活力+热稳定性、可排单候选报告顺序、后台 BLAST submitted、kcat 启发式边界、蛋白设计中文主导、弱 Foldseek 不升级身份。
- 阶段 1 状态改为完成；阶段 7 状态改为进行中。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases -q`：7 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py -q`：157 passed。

### 下一步

- 阶段 2：把报告质量契约从测试隐含规则整理成文档/常量，避免后续实现者只看测试不知道科学边界。
- 阶段 6：做续问质量复核模式，用户指出“不准/格式乱/继续深度检查”时进入错误归因，而不是重新生成候选。

## 2026-08-15 阶段 2 契约首版

- 新增 `backend/app/services/report_quality_contract.py`：
  - `CORE_SECTION_ORDER`：反馈 V5 要求的核心章节顺序。
  - `DEFAULT_FORBIDDEN_PHRASES`：默认禁止旧结构、英文 fallback、启发式 kcat 结论词。
  - `validate_report_quality_contract`：统一检查 required/forbidden/ordered_headings。
- 修改 `TestEnzymeReportQualityEvalSet`，从手写断言改为调用统一 contract。
- 新增 `backend/tests/test_report_quality_contract.py`，验证 missing/forbidden/order 三类违规都能被识别，并保留默认 forbidden 的显式 opt-out。
- 阶段 2 状态改为进行中：契约已抽象为代码，但还没有接到运行时发布门禁。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_report_quality_contract.py backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet -q`：75 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_report_quality_contract.py -q`：160 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/services/report_quality_contract.py backend/app/core/agent_graph.py backend/app/services/report_generator.py`：通过。

## 2026-08-15 阶段 6 续问质量复核首版

- 新增 `_is_report_quality_review_followup`，识别“不准/不准确/格式乱/表格乱/质量差/越改越差/继续深度检查”等质量复核续问。
- 新增 `_summarize_history_for_quality_review`，从近期历史中提取对象、工具状态和阻断线索。
- 新增 `_build_report_quality_review_reply`，确定性输出“报告质量复核”，明确不重新执行工具、不重新生成候选突变表。
- 在 `stream_chat` 中加入早期短路：质量复核续问优先于普通路由、规划和 LLM 回复。
- 新增回归测试，确保质量复核续问不调用 planner、不调用 LLM；确认执行和新序列任务不会误判为质量复核。
- 阶段 6 状态改为进行中：首版已能阻断默认分析流程，但仍需接入真实结构化 snapshot/tool_results。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "report_quality_review or same_problem_synthesis_followup" -q`：4 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_report_quality_contract.py -q`：162 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py backend/app/services/report_quality_contract.py backend/app/services/report_generator.py`：通过。

## 2026-08-15 阶段 6 策略记忆增强

- 新增 `_load_recent_strategy_memory_records`，将策略记忆读取统一为结构化 records，再分别用于普通续问摘要、规划上下文和质量复核。
- 新增 `_summarize_strategy_memory_for_quality_review`，从 `plan_payload` 提取工具状态，从 `evidence_state` 提取缺失证据/阻断摘要，从 `artifacts` 提取 handoff 数量。
- 质量复核分支现在在检测到质量投诉时优先读取同项目策略记忆；即便历史消息没有完整报告，只要有结构化策略记忆也能进入复核。
- 保留历史文本提取作为 fallback，避免没有数据库会话或没有项目上下文时失效。
- 新增回归测试：有结构化策略记忆时不调用 planner/LLM，回复中展示对象、工具状态、缺失证据、revision 和 artifact_handoffs。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "report_quality_review" -q`：3 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_report_quality_contract.py -q`：163 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py backend/app/services/report_quality_contract.py backend/app/services/report_generator.py`：通过。

## 2026-08-15 阶段 6 执行摘要回写

- 新增 `AgentOrchestrator.get_checkpoint_execution_summary`，从 snapshot 输出 `step_results`、`final_report_preview`、`report_headings` 和 research notes 摘要。
- 新增 `mark_strategy_checkpoint_completed`，确认执行流结束后将 checkpoint 标记为 `completed`，并保存执行证据摘要和 artifacts。
- 修改 chat SSE 收尾逻辑：`execute_confirmed` 完成后不再只标记 `executing`，而是回写 completed evidence_state。
- 质量复核现在可展示工具结果摘要，例如 `blast_search(submitted): task_id=...`，并展示报告章节线索。
- 更新旧测试预期：没有服务端 active checkpoint 时，不再信任客户端传来的 confirmed_plan/signature/fingerprint。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "report_quality_review or checkpoint_execution_summary" -q`：5 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_llm_gateway.py -k "checkpoint_completed_summary or execute_confirmed" -q`：2 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：184 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py backend/app/api/chat.py backend/app/services/strategy_checkpoint.py`：通过。

## 2026-08-15 阶段 7 发布质量门槛接入

- 在 `backend/app/services/report_quality_contract.py` 新增 `is_structured_enzyme_report` 和 `validate_publishable_enzyme_report`。
- 在 `backend/app/services/publish_service.py` 新增 `ReportQualityGateError`，并在 `publish_report` 开头执行结构化酶工程报告质量校验。
- 修改 `backend/app/api/publish.py`：手动项目发布和直接 Wiki collection 发布遇到质量门槛错误时返回 HTTP 400。
- 新增/更新测试：
  - `backend/tests/test_report_quality_contract.py`：覆盖普通 Markdown 不阻断、结构化酶报告缺章节阻断、固定核心顺序通过。
  - `backend/tests/test_publish.py`：覆盖违规结构化酶报告在 DB 访问前被阻断，普通 Markdown 不被酶报告门槛误伤。
  - `backend/tests/test_publish_api.py`：覆盖 API 把质量门槛错误返回为 400。
- 阶段 2 状态改为完成；阶段 7 继续进行中。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_report_quality_contract.py backend/tests/test_publish.py::TestPublishServiceUtils -q`：10 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_report_quality_contract.py backend/tests/test_publish.py backend/tests/test_publish_api.py -q`：38 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：194 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/services/report_quality_contract.py backend/app/services/publish_service.py backend/app/api/publish.py`：通过。

## 2026-08-15 阶段 3 策略确认页重构首版

- 在 `backend/app/core/agent_graph.py` 新增策略输入审计辅助逻辑：
  - `_strategy_input_mode`
  - `_build_input_evidence_audit_lines`
  - `_objective_label`
  - `_build_objective_decomposition_lines`
- `_build_plan_confirmation_reply` 现在在改造策略前先输出 `输入证据审计` 和 `目标拆解`。
- PDB-only 策略页明确写出 PDB-coordinate-derived 边界、独立 FASTA/UniProt 映射缺口，以及身份/编号/催化关键位点未确认前不输出位点级突变候选表。
- 多目标策略页明确写出比活力线、热稳定线、协同点、冲突点和门控输出条件。
- 将通用策略的无条件“最终输出可进入实验设计的候选位点”改为条件式候选输出边界，避免策略与后续 No-Go/blocked 报告矛盾。
- 更新 `backend/tests/test_agent_binder.py`：
  - 多目标策略确认必须包含 `输入证据审计`、`目标拆解`、协同/冲突和候选输出边界。
  - PDB-only 策略确认必须先审计输入，再进入改造策略，并明确不可下单边界。
- 阶段 3 状态改为进行中。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "plan_confirmation" -q`：5 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q`：138 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：195 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py`：通过。

## 2026-08-15 阶段 3/4 多目标执行门控修正

- 修改 `backend/app/tools/enzyme_objective_module_plan.py`：
  - 新增 `objective_modules`，保留每个目标模块的 required_evidence、candidate_mechanisms、validation_metrics 和 forbidden_shortcuts。
  - 新增 `combined_required_evidence` 和 `combined_validation_metrics`。
  - 多目标时合并 forbidden shortcuts，避免主目标 activity 覆盖 thermostability 的禁止捷径。
- 修改 `backend/app/tools/mutation_priority_score.py`：
  - 新增 objective signal 规范化和合并逻辑。
  - 识别 activity + thermostability 后返回 `multi_objective=True`、`ranking_mode=activity_stability`。
  - 双目标策略、expected_effect 和 experiment_action 同时要求比活力/kcat/Km 与 Tm/热半衰期/热处理残余活性验证。
- 更新 `backend/tests/test_tools_api.py`：
  - 覆盖 `enzyme_objective_module_plan` 多目标模块输出。
  - 覆盖 `mutation_priority_score` 的 `activity_stability` 排序模式和双指标实验动作。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_tools_api.py -k "enzyme_objective_module_plan or activity_stability_ranking_mode" -q`：4 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_tools_api.py -q`：119 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：195 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/tools/enzyme_objective_module_plan.py backend/app/tools/mutation_priority_score.py backend/app/core/agent_graph.py`：通过。

## 2026-08-15 阶段 5 多目标报告展示补齐

- 修改 `backend/app/core/agent_graph.py` 的 `Objective Module Gate` 输出：
  - 显示 `多目标门控` 状态。
  - 展开 `objective_modules` 为 `目标模块明细`。
  - 展示 `combined_required_evidence` 和 `combined_validation_metrics`。
- 新增 `backend/tests/test_agent_binder.py::test_fallback_report_surfaces_multi_objective_gate_details`：
  - 验证报告中出现 specific_activity 和 thermostability 两条模块。
  - 验证合并验证指标同时包含 specific activity 与 thermal half-life。
  - 验证 mutation 策略和实验动作仍显示双指标共同验证。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "multi_objective_gate_details or fallback_report_shows_exploratory" -q`：2 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q`：139 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_tools_api.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：315 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py backend/app/tools/enzyme_objective_module_plan.py backend/app/tools/mutation_priority_score.py`：通过。

## 2026-08-15 阶段 5 工具来源说明表格化

- 修改 `backend/app/core/agent_graph.py` 的 `工具来源说明`：
  - 从一行工具链改成 5 列表格：工具、状态、作用、证据层级、报告用途。
  - submitted 工具明确标注“不作为完成证据”。
  - failed/blocked 工具明确标注“只记录失败/阻断原因”。
  - `kcat_predict` 标注为启发式背景，不能证明比活力或突变增益。
  - `mutation_priority_score` / `mutation_scan` / `protssn_score` 显示候选输出受 `candidate_table_status` 和身份/目标门控约束。
- 新增 `backend/tests/test_agent_binder.py::test_fallback_report_explains_tool_sources_and_boundaries`。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "tool_sources_and_boundaries or multi_objective_gate_details" -q`：2 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q`：140 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_tools_api.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：316 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py`：通过。

## 2026-08-15 阶段 4 启发式/候选工具边界收口

- 修改 `backend/app/tools/kcat_predict.py`：
  - 移除源头输出中的“中高催化效率 / 典型工业酶”等过强定性词。
  - `efficiency_assessment` 改为未校准的启发式 kcat 区间标签，并明确不能代表真实比活力。
  - `report_boundary` 改为中文，明确不得写成校准 kcat、kcat/Km、比活力提升或突变增益证据。
- 修改 `backend/app/tools/mutation_scan.py`：
  - 新增 `capability_status=proxy`、`evidence_level=DESIGN_HYPOTHESIS`、`candidate_table_status=requires_identity_numbering_objective_gate` 和中文 `report_boundary`。
  - 明确扫描结果只能作为替换空间/理化风险辅助，门控未过不得生成可排单候选表。
- 修改 `backend/app/tools/protssn_score.py`：
  - 推荐语从“优先改造候选/可考虑改造”改为“门控通过后复核/仅作辅助评分”。
  - 新增 `candidate_table_status` 并强化中文 `report_boundary`。
- 修改 `backend/app/tools/tool_capability_audit.py`：
  - 新增 `mutation_scan` 能力审计条目，标记为 proxy，边界为“不是候选表”。
- 更新 `backend/tests/test_tools_api.py`：
  - 覆盖 kcat 禁止过强词、mutation_scan 统一边界字段、protssn 不输出强推荐语、能力审计包含 mutation_scan。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_tools_api.py -k "proxy_predictors_do_not_claim_real_inference or tool_capability_audit_labels_proxy" -q`：2 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_tools_api.py -q`：119 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "tool_sources_and_boundaries or report_quality_contract_cases or fallback_report" -q`：17 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/tools/kcat_predict.py backend/app/tools/mutation_scan.py backend/app/tools/protssn_score.py backend/app/tools/tool_capability_audit.py`：通过。

## 2026-08-15 阶段 5 第一屏摘要补齐

- 修改 `backend/app/core/agent_graph.py`：
  - 在 `## 任务理解` 下增加固定第一屏摘要字段：能否下单、主要证据、主要缺口、下一步。
  - 不新增顶级章节，避免破坏反馈 V5 的核心章节顺序。
  - 可排单场景显示“可以进入单点验证设计”；门控阻断场景显示阻断类型和补证据路线。
  - 缺口来源同时读取 `enzyme_objective_module_plan.missing_evidence` 和 `mutation_priority_score.objective_gate.missing_evidence`。
- 更新 `backend/tests/test_agent_binder.py`：
  - 可排单候选报告必须在第一屏给出“可以进入单点验证设计”和 P1/P2 单点下一步。
  - 身份/编号阻断报告必须在第一屏给出“不能直接下单”、具体目标缺口和补 FASTA/同源身份等下一步。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "mutation_scan_does_not_overwrite_priority_candidate_table or suppresses_candidates_when_identity_gate_is_blocked" -q`：2 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q`：140 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_report_quality_contract.py backend/tests/test_publish.py backend/tests/test_publish_api.py -q`：38 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py`：通过。

## 2026-08-15 阶段 7 PDB-only 深度报告专项回归

- 扩展 `backend/tests/enzyme_report_quality_cases.json` 的 HM/PDB-only 身份阻断用例：
  - 第一屏必须显示不能直接下单，且阻断原因为身份/编号门控未通过。
  - 主要证据必须区分上传结构解析、`local_sifts_style_inference` 编号推断和 kcat 启发式背景。
  - 必须显示“结构/编号边界不能单独确认酶身份”和“kcat 不能证明比活力或突变增益”。
  - 下一步必须指向补 FASTA/同源身份等证据，而不是生成通用突变表。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases -q`：7 passed。

## 2026-08-15 阶段 5/7 Markdown 表格渲染收口

- 修改 `frontend/src/components/chat/MarkdownView.tsx`：
  - Markdown 表格改为 `w-max min-w-full`，外层保留 `overflow-x-auto`。
  - `th/td` 增加最小宽度、最大宽度、正常换行和 `overflow-wrap:anywhere`，减少宽表被挤成窄列的问题。
- 修改 `frontend/tests/smoke-check.mjs`：
  - 更新过期断言：不再要求 `Go / Watch / No-Go` 连写文本。
  - 更新顺序断言：改造策略说明应在候选突变表之前。
  - 候选表不再默认取第一个 table，而是按 `位点/编号` 表头定位。
  - 增加 Markdown 表格布局检查：外层横向滚动、单元格最小/最大宽度和 overflow-wrap 必须存在。

### 本轮验证

- `npm run lint`：通过。
- `npm run build`：通过。
- `node tests/smoke-check.mjs`：Smoke check passed。首次运行因沙箱内 Chrome 启动失败，已按权限提升运行；后续失败均为 smoke 旧断言，与本次表格样式无关，已修正。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_tools_api.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：316 passed。

## 2026-08-15 阶段 6 质量复核 claim gate 明细

- 修改 `backend/app/core/agent_graph.py`：
  - `get_checkpoint_execution_summary` 现在从已完成 step 的 compact result 中构建压缩 claim audit，并写入 `evidence_state.claim_audit`。
  - 新增 `_compact_claim_audit_summary`，只保存 summary/body gate 状态、allowed/downgraded/blocked 计数和 claim id 列表。
  - `_summarize_strategy_memory_for_quality_review` 读取 `claim_audit` / `claim_audit_summary`。
  - `_build_report_quality_review_reply` 增加 `## 科学声明审计` 小节，展示摘要/结论门控、允许进入摘要、降级为正文假设、禁止写成事实的声明。
- 更新 `backend/tests/test_agent_binder.py`：
  - 质量复核回复必须展示 `MUTATION_SITE_TABLE=DESIGN_HYPOTHESIS`、`KCAT_PREDICT_REAL_RUNTIME=RUNTIME_UNVERIFIED` 等门控明细。
  - checkpoint 执行摘要必须能从 mutation/kcat compact result 中生成 claim audit。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "report_quality_review_uses_checkpoint_step_results or checkpoint_execution_summary_contains_step_results" -q`：2 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "report_quality_review or checkpoint_execution_summary or claim_audit" -q`：8 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m py_compile backend/app/core/agent_graph.py`：通过。

## 2026-08-15 阶段 7 评测集扩展与策略分流回归

- 扩展 `backend/tests/enzyme_report_quality_cases.json`：
  - 新增 `fasta_only_identity_unresolved_blocks_candidate_table`，覆盖只有 FASTA、身份未确认、目标证据不足时不输出候选表。
  - 新增 `identified_sequence_ready_candidate_table_is_submittable`，覆盖身份/编号/目标门控通过时第一屏显示可进入单点验证设计，并输出可排单候选表。
  - 报告质量用例从 7 个扩展到 9 个。
- 更新 `backend/tests/test_agent_binder.py`：
  - 新增 PDB + FASTA 策略确认分流测试：必须先检查 PDB 链与 FASTA 一致性、成熟蛋白/标签边界。
  - 新增 FASTA + UniProt 策略确认分流测试：必须核对 UniProt 记录是否匹配输入序列、成熟链/信号肽边界，不能混入 PDB-only 的坐标顺序编号警告。

### 本轮验证

- `python3 -m json.tool backend/tests/enzyme_report_quality_cases.json >/tmp/enzyme_report_quality_cases.checked.json`：通过。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases -q`：9 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "plan_confirmation" -q`：7 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_tools_api.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：320 passed。

## 2026-08-15 阶段 7 发布验收矩阵接入报告质量门槛

- 修改 `scripts/run_acceptance_matrix.py`：
  - 新增 `enzyme_report_quality_contract` 步骤，类别为 `report_quality`。
  - 该步骤运行报告质量契约、9 个报告质量用例、质量复核 claim gate、checkpoint claim audit、PDB+FASTA 和 FASTA+UniProt 策略分流回归。
- 修改 `backend/tests/test_config_validation.py`：
  - acceptance matrix 脚本文本和 plan-only JSON 输出都必须包含 `enzyme_report_quality_contract`。

### 本轮验证

- `python3 scripts/run_acceptance_matrix.py --plan-only --json`：通过，输出包含 `enzyme_report_quality_contract`。
- `cd backend && .venv/bin/python -m pytest tests/test_report_quality_contract.py tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_review_uses_checkpoint_step_results_and_report_preview tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_checkpoint_execution_summary_contains_step_results_and_report_headings tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_pdb_plus_fasta_as_consistency_gate tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_fasta_plus_uniprot_before_numbering_claims -q`：17 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_config_validation.py -k "acceptance_matrix_script_plan_includes_risk_gates" -q`：1 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_tools_api.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：320 passed。

## 2026-08-15 阶段 4 背景工具能力合同统一

- 修改/确认 `backend/app/tools/annotation_bundle.py`：
  - 返回 `capability_status=evidence_synthesis`、`evidence_level=ANNOTATION_SYNTHESIS`。
  - 增加中文 `report_boundary`，明确聚合证据不能默认写成实时 UniProt/InterPro/M-CSA/SignalP 查询。
- 修改/确认 `backend/app/tools/enzyme_function.py`：
  - 身份档案派生路径标记为 `foundation_dependent_prediction` / `IDENTITY_PROFILE_DERIVED`。
  - 模体/embedding fallback 路径标记为 `proxy` / `DESIGN_HYPOTHESIS`，不得写成已确认 EC。
- 修改/确认 `backend/app/tools/protein_benchmark.py`：
  - 未传入已通过门控的 `enzyme_identity_profile` 时返回 blocked。
  - 明确其是已确认家族后的解释器，不是身份识别器。
- 修改/确认 `backend/app/core/agent_graph.py`：
  - `工具来源说明` 优先展示上述工具 payload 里的中文 `report_boundary`。
- 更新测试：
  - `backend/tests/test_tools_api.py` 增加 protein_benchmark/enzyme_function 能力字段断言。
  - `backend/tests/test_data_tools.py` 增加 annotation_bundle 能力字段断言。
  - `backend/tests/test_agent_binder.py` 增加工具来源表动态边界断言。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_data_tools.py::TestAnnotationTools::test_interpro_annotation_curated -q`：1 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_data_tools.py::TestAnnotationTools -q`：4 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_data_tools.py -q`：17 passed。
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py backend/tests/test_tools_api.py backend/tests/test_publish.py backend/tests/test_publish_api.py backend/tests/test_report_quality_contract.py backend/tests/test_llm_gateway.py -q`：320 passed。

## 2026-08-15 阶段 4 结构/编号/理化背景工具边界

- 修改 `backend/app/tools/structure_search_foldseek.py`：
  - completed hit 返回 `structure_similarity_search` / `STRUCTURE_SIMILARITY`。
  - degraded/summary-only 返回 `structure_input_qc` / `STRUCTURE_INPUT_QC`。
  - 中文边界明确：弱 TM-score、模板 RCSB 注释和结构摘要不能单独确认输入酶身份、催化残基、底物口袋或 UniProt 编号。
- 修改 `backend/app/tools/residue_mapping_sifts.py`：
  - 本地映射文件与坐标顺序推断使用不同 capability/evidence 标签。
  - 坐标顺序推断明确不是外部 SIFTS/UniProt 实证映射。
- 修改 `backend/app/tools/predict_properties.py`：
  - 标记为 `physicochemical_baseline` / `BACKGROUND_BASELINE`。
  - 明确理化性质不能替代 Tm、半衰期、残余活性和动力学实验。
- 修改 `backend/app/core/agent_graph.py`：
  - 工具来源表读取上述工具源头 `report_boundary`。

### 本轮验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_structure_tools.py -q`：7 passed。
- 相关能力合同专项：5 passed。
- 工具来源表专项：1 passed。
- 核心后端回归（含结构/数据工具）：345 passed。

## 2026-08-15 阶段 8 能力边界固定入口

- 扩展 `backend/app/tools/tool_capability_audit.py`：
  - 新增 structure_search_foldseek、residue_mapping_sifts、predict_properties、enzyme_function、enzyme_objective_module_plan、blast_search。
  - 新增 `summary.tool_count`、`summary.unknown_count`、`summary.status_counts`。
- 新增只读 API：`GET /api/data/tool-capabilities`。
- 修改 `frontend/src/lib/api.ts`：
  - 新增能力矩阵类型和 `getToolCapabilities()`。
- 修改 `frontend/src/pages/DataBrowser.tsx`：
  - 新增“能力边界”标签页。
  - 支持 `/data?tab=capabilities` 直达并同步 URL。
  - 展示能力状态、科学边界、最低产物和报告动作；unknown 工具显示发布阻断。
- 修改 `frontend/src/pages/HomePage.tsx`：
  - 新增“能力边界”固定入口。

### 本轮验证

- 能力 API/工具审计专项：1 passed。
- `npm run lint`：通过。
- `npm run build`：通过。
- `py_compile backend/app/api/data.py backend/app/tools/tool_capability_audit.py`：通过。
## 2026-08-17 阶段 9/10 HM gate 与 release acceptance 收口

- 修复 `scripts/check_upgrade_readiness.py`：
  - `production.config` 校验现在同时读取 `docker/.env` 与 `docker/.env.aliyun.app`；
  - 与 `scripts/run_acceptance_matrix.py` 的生产配置 gate 口径一致，避免升级就绪使用不完整 env 导致误报 critical。
- 更新 `backend/tests/test_config_validation.py`：
  - 保留 acceptance matrix 双 env-file 断言；
  - 新增 upgrade readiness 脚本也必须包含 `docker/.env` 与 `docker/.env.aliyun.app` 的断言。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 阶段 9 标记为进行中，HM.pdb deep gate 与 smoke 边界已完成，SOP 仍待补；
  - 阶段 10 标记为进行中，默认 release acceptance 自动门槛已通过，proxy blocker / 多用户隔离 / Wiki checkpoint 固定门槛仍待继续收口。

### 本轮验证

- `cd backend && ./.venv/bin/python -m pytest -q tests/test_config_validation.py -k 'acceptance_matrix_script_plan_includes_risk_gates or acceptance_and_nightly_include_production_config_gate or release_acceptance_script_plan_includes_delivery_gates'`：3 passed。
- `./backend/.venv/bin/python scripts/check_upgrade_readiness.py --json`：
  - `production.config`：ok，`ready; critical=0; warning=0; checks=11`；
  - summary：`ready-with-manual-gates`，仅因 git 工作区 dirty 需要人工确认。
- `./backend/.venv/bin/python scripts/run_release_acceptance.py --json`：
  - summary：`passed-with-manual-gates`；
  - failed=0，blocked=0，manual_required=3，skipped=1，total=9；
  - `upgrade_readiness`：passed；
  - `acceptance_matrix`：passed，内部 `production_config_gate` passed，`hm_pdb_deep_quality_gate` passed。

### 剩余上线门

- 自动代码门禁当前无 failed/blocked。
- 仍需人工输入/真实环境确认：
  - `MAINTENANCE_WINDOW_ID` 与 `ALLOW_PRODUCTION_DRILL=true`；
  - `OFFSITE_BACKUP_TARGET` 与 `OFFSITE_RESTORE_TARGET`；
  - `EXTERNAL_STORAGE_BACKUP_REF` 与 `EXTERNAL_STORAGE_RESTORE_TARGET`。
- 默认 release acceptance 中 `backup_verify` 仍按设计 skipped，需要显式 `--include-backup-verify` 才会运行 pg_restore/checksum verification。

## 2026-08-17 阶段 9 PDB-only SOP 收口

- 新增 `docs/manuals/pdb-only-enzyme-analysis-sop.md`：
  - 明确 PDB-only 默认只支持结构质控、结构相似性、坐标编号推断和探索性复核窗口；
  - 明确不能直接输出可排单候选突变，不能确认酶身份、催化残基、底物口袋、UniProt 编号、比活力提升或热稳定性提升；
  - 固定 `structure_search_foldseek`、`residue_mapping_sifts`、`blast_search`、`predict_properties`、`kcat_predict` 的报告用途和禁止写法；
  - 写入 HM.pdb 发布 gate 必须覆盖的 5 个边界。
- 更新 `docs/manuals/productization-acceptance-manual.md`，在发布验收章节链接 PDB-only SOP。
- 更新 `backend/tests/test_hm_pdb_deep_quality_gate.py`：
  - HM 专项 gate 现在同时验证报告边界和 SOP 文档边界；
  - `hm_pdb_deep_quality_gate` 在 acceptance matrix 中显示 `2 passed`。
- 更新 `.planning/report_quality_replan/task_plan.md`：阶段 9 标记为完成。

### 本轮验证

- `cd backend && ./.venv/bin/python -m pytest -q tests/test_hm_pdb_deep_quality_gate.py tests/test_report_quality_contract.py tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases`：15 passed。
- `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --json`：`passed-with-skips`，failed=0，blocked=0，skipped=7，total=18。
- `./backend/.venv/bin/python scripts/run_release_acceptance.py --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=1，total=9。

## 2026-08-17 阶段 10 工具能力 release blocker 接入

- 修改 `scripts/run_acceptance_matrix.py`：
  - 新增 `tool_capability_audit_gate`，类别为 `report_quality`；
  - 该 gate 运行 `/api/data/tool-capabilities` 能力边界测试和 `tool_capability_audit` 工具合同测试；
  - 任一报告级工具能力为 unknown 时，对应测试会失败，从而阻断默认 acceptance matrix / release acceptance。
- 更新 `backend/tests/test_config_validation.py`：
  - acceptance matrix 脚本文本和 plan-only JSON 输出必须包含 `tool_capability_audit_gate`。
- 发现并确认一次并发验证噪音：
  - 同时并行跑 `run_acceptance_matrix.py --json` 和 `run_release_acceptance.py --json` 时出现测试库竞争，分别表现为 data/file/ligand gate 瞬时失败；
  - 串行重跑后均通过，结论为已知并行测试环境竞争，不是本轮代码回归。

### 本轮验证

- `cd backend && ./.venv/bin/python -m pytest -q tests/test_data_api.py::TestBenchmarkEndpoints::test_tool_capabilities_endpoint_exposes_scientific_boundaries tests/test_tools_api.py::test_tool_capability_audit_labels_proxy_and_runtime_gated_tools tests/test_config_validation.py -k 'acceptance_matrix_script_plan_includes_risk_gates or acceptance_and_nightly_include_production_config_gate'`：2 passed。
- `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --plan-only --json`：planned=12，total=19，包含 `tool_capability_audit_gate`。
- 串行 `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --json`：`passed-with-skips`，failed=0，blocked=0，skipped=7，total=19。
- 串行 `./backend/.venv/bin/python scripts/run_release_acceptance.py --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=1，total=9。

## 2026-08-17 阶段 10 多用户隔离与 Wiki checkpoint 固定门槛

- 新增 `backend/tests/test_publish_api.py::test_collection_publish_preserves_active_strategy_checkpoint`：
  - 本地模拟 `/api/wiki/publish`，带 `conversation_id` 发布 Wiki 内容；
  - 发布后 active strategy checkpoint 仍保持 `awaiting_confirmation`；
  - `strategy_signature` / `task_fingerprint` 不被 Wiki 发布覆盖或丢失。
- 修改 `scripts/run_acceptance_matrix.py`：
  - 新增 `user_isolation_contract`，覆盖项目不可发现、聊天项目绑定写权限、viewer 发布拒绝、非成员文件拒绝、工具任务/审计跨用户拒绝、实验反馈用户隔离；
  - 新增 `wiki_checkpoint_contract`，覆盖 Wiki 发布不破坏 active checkpoint、确认执行恢复服务端 checkpoint、stale/malformed client payload fail-closed、checkpoint 响应脱敏和 history revision。
- 更新 `backend/tests/test_config_validation.py`：
  - acceptance matrix 脚本文本和 plan-only JSON 输出必须包含 `user_isolation_contract` 与 `wiki_checkpoint_contract`。
- 注意：
  - 曾并行运行两个后端 pytest gate，触发 SQLite schema 竞争；串行重跑后全部通过。
  - 默认发布验收必须串行，或 CI 显式隔离 `TEST_DATABASE_URL`。

### 本轮验证

- 串行用户隔离专项：7 passed。
- 串行 Wiki checkpoint 专项：7 passed。
- `cd backend && ./.venv/bin/python -m pytest -q tests/test_config_validation.py -k 'acceptance_matrix_script_plan_includes_risk_gates'`：1 passed。
- `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --plan-only --json`：planned=14，total=21，包含 `user_isolation_contract` 与 `wiki_checkpoint_contract`。
- `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --json`：`passed-with-skips`，failed=0，blocked=0，skipped=7，total=21。
- `./backend/.venv/bin/python scripts/run_release_acceptance.py --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=1，total=9。

## 2026-08-17 阶段 10 CI 并行测试库隔离规则

- 修改 `backend/tests/conftest.py`：
  - 测试数据库 URL 支持 `TEST_DATABASE_URL` 覆盖；
  - 默认仍保持 `sqlite+aiosqlite:///./test_protein_ai.db`，本地单进程用法不变。
- 修改 `.github/workflows/ci.yml`：
  - backend pytest job 显式设置 `TEST_DATABASE_URL=sqlite+aiosqlite:///./test_protein_ai_ci_${{ github.run_id }}_${{ github.job }}.db`；
  - 后续如果拆分多个 backend pytest job，每个 job 可自然使用不同文件。
- 修改 `docs/manuals/productization-acceptance-manual.md`：
  - 明确 CI 并行拆分后端 pytest 时必须为每个 job 设置独立 `TEST_DATABASE_URL` 和隔离存储目录。
- 修改 `backend/tests/test_config_validation.py`：
  - 锁定 workflow、conftest 和验收手册中的 `TEST_DATABASE_URL` 约束。
- 清理本轮临时生成的 `backend/test_protein_ai_isolated_gate.db`。
- 阶段 10 已完成。

### 本轮验证

- `cd backend && ./.venv/bin/python -m pytest -q tests/test_config_validation.py -k 'ci_pytest_uses_isolated_test_database_url or productization_manuals_exist'`：2 passed。
- `TEST_DATABASE_URL='sqlite+aiosqlite:///./test_protein_ai_isolated_gate.db' ./.venv/bin/python -m pytest -q tests/test_publish_api.py::test_collection_publish_preserves_active_strategy_checkpoint tests/test_project_acl.py::test_non_member_cannot_discover_project`：2 passed。
- `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --json`：`passed-with-skips`，failed=0，blocked=0，skipped=7，total=21。
- `./backend/.venv/bin/python scripts/run_release_acceptance.py --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=1，total=9。

## 2026-08-17 阶段 11 外部基础设施验收包

- 新增 `docs/manuals/external-infrastructure-acceptance-checklist.md`：
  - 统一要求每项外部依赖记录负责人、输入、命令/操作、通过标准、失败回滚和证据归档位置；
  - 覆盖正式域名 + HTTPS + OIDC callback；
  - 覆盖 GPU/GROMACS 节点，从驱动/CUDA/GROMACS 到 topology live gate、mutant prepare、replicate、batch summary；
  - 覆盖维护窗口真实回滚演练、异地备份恢复演练、外部对象存储恢复验证；
  - 覆盖数据更新制度：PDB 每周、AlphaFold/SIFTS/annotations 每月、Foldseek DB 每月或季度；
  - 明确 `manual_required` / `pending` 不得写成已上线。
- 更新 `docs/manuals/productization-acceptance-manual.md`，链接外部基础设施验收清单。
- 更新 `backend/tests/test_config_validation.py`，锁定外部验收手册关键字段。
- 更新 `.planning/report_quality_replan/task_plan.md`，阶段 11 验收包标记为完成；真实外部动作仍等待对应输入后执行。

### 本轮验证

- `cd backend && ./.venv/bin/python -m pytest -q tests/test_config_validation.py -k 'productization_manuals_exist or ci_pytest_uses_isolated_test_database_url or acceptance_matrix_script_plan_includes_risk_gates'`：3 passed。

## 2026-08-17 阶段 3/5/6/7/8 收口复核

- 复核阶段 3 策略生成重构：
  - 策略确认页已先输出输入证据审计和目标拆解；
  - 比活力 + 热稳定性会列协同点、冲突点和候选输出边界；
  - PDB-only、PDB+FASTA、FASTA+UniProt 分流已有专项断言；
  - 无条件“最终必须输出候选位点”类承诺已由测试禁止。
- 复核阶段 5 报告生成器重构：
  - fallback 报告按固定科学问题顺序输出；
  - 第一屏展示能否下单、主要证据、主要缺口、下一步；
  - PDB-only 身份未过时阻断候选表，身份/编号/目标门控通过时输出可排单候选；
  - 工具来源说明以 5 列表格展示工具、状态、作用、证据层级和报告用途。
- 复核阶段 6 上下文与续问重构：
  - 质量投诉/继续深度检查进入“报告质量复核”；
  - 复核读取策略 checkpoint、工具 step_results、final_report_preview、report_headings 和 claim_audit；
  - 不重新规划、不调用 LLM、不继续生成新候选表。
- 复核阶段 7 评测与发布门槛：
  - 报告质量评测集、发布质量 contract、HM.pdb deep gate、工具能力 gate、用户隔离 gate、Wiki checkpoint gate 已进入默认 acceptance matrix；
  - release acceptance 自动门槛 failed=0 / blocked=0。
- 复核阶段 8 能力边界固定入口：
  - 后端 `GET /api/data/tool-capabilities`、前端 `/data?tab=capabilities` 和首页入口均已存在；
  - capability audit 明确 proxy、blocked、runtime-gated、real_runtime_gated 等状态及报告边界；
  - `tool_capability_audit_gate` 已作为默认发布门槛。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 阶段 3、5、6、7、8 全部标记为完成；
  - 当前状态改为阶段 1-11 已完成本地代码/文档/自动 gate 收口；
  - 保留真实上线边界：外部基础设施/人工发布门仍需真实输入后执行。

### 本轮验证

- `./backend/.venv/bin/python -m pytest -q backend/tests/test_report_quality_contract.py backend/tests/test_hm_pdb_deep_quality_gate.py backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases backend/tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_splits_activity_and_thermostability_objectives backend/tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_pdb_only_before_strategy backend/tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_pdb_plus_fasta_as_consistency_gate backend/tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_fasta_plus_uniprot_before_numbering_claims backend/tests/test_agent_binder.py::TestBinderSkillsAndReport::test_fallback_report_surfaces_multi_objective_gate_details backend/tests/test_agent_binder.py::TestBinderSkillsAndReport::test_fallback_report_explains_tool_sources_and_boundaries backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_review_uses_checkpoint_step_results_and_report_preview backend/tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_checkpoint_execution_summary_contains_step_results_and_report_headings backend/tests/test_data_api.py::TestBenchmarkEndpoints::test_tool_capabilities_endpoint_exposes_scientific_boundaries backend/tests/test_tools_api.py::test_tool_capability_audit_labels_proxy_and_runtime_gated_tools`：25 passed。
- `./backend/.venv/bin/python scripts/run_acceptance_matrix.py --json`：`passed-with-skips`，failed=0，blocked=0，skipped=7，total=21。
- `./backend/.venv/bin/python scripts/run_release_acceptance.py --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=1，total=9。

### 仍未上线

- 当前只是本地自动门槛通过，未部署生产。
- 仍需人工发布门：
  - `MAINTENANCE_WINDOW_ID` 与 `ALLOW_PRODUCTION_DRILL=true`；
  - `OFFSITE_BACKUP_TARGET` 与 `OFFSITE_RESTORE_TARGET`；
  - `EXTERNAL_STORAGE_BACKUP_REF` 与 `EXTERNAL_STORAGE_RESTORE_TARGET`。
- `backup_verify` 默认仍为 skipped；如要进入真实发布前终验，应显式运行 `run_release_acceptance.py --include-backup-verify --json` 并补齐人工门输入。

## 2026-08-17 阶段 12 发布交接终验

- 尝试运行增强 release acceptance：
  - `./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --json`
  - 结果 failed=1，失败项为 `backup_verify`；
  - 根因：本机缺少 `pg_restore`，脚本提示安装 PostgreSQL client tools 或使用 `--compose`。
- 尝试运行 compose 备份校验：
  - 沙箱内 `./scripts/verify_backup.sh --compose backups/protein_ai_20260708T001139Z.dump` 因 Docker socket 权限失败；
  - 提权后同一只读命令通过：`checksum ok`，`pg_restore_list ok`，`summary ok`。
- 重跑完整增强 release acceptance：
  - `./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`
  - 结果 `passed-with-manual-gates`；
  - failed=0，blocked=0，manual_required=3，skipped=0，total=9；
  - `backup_verify` passed。
- 新增 `docs/manuals/release-handoff-2026-08-17.md`：
  - 记录自动门槛结果、compose 备份校验方式、剩余人工门和上线前执行口径。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 新增阶段 12 并标记完成；
  - 当前状态更新为增强 release acceptance 已纳入备份校验且 failed=0 / blocked=0 / skipped=0。

### 仍未上线

- 生产部署仍未执行。
- 仍需三个人工门：
  - 维护窗口 + 生产演练授权；
  - 异地备份目标 + 独立恢复目标；
  - 外部存储备份引用 + shadow 恢复目标。

## 2026-08-17 阶段 13 人工发布门输入包

- 新增 `docs/manuals/release-manual-gate-inputs.template.json`：
  - 覆盖 `MAINTENANCE_WINDOW_ID`、`ALLOW_PRODUCTION_DRILL`；
  - 覆盖 `OFFSITE_BACKUP_TARGET`、`OFFSITE_RESTORE_TARGET`；
  - 覆盖 `EXTERNAL_STORAGE_BACKUP_REF`、`EXTERNAL_STORAGE_RESTORE_TARGET`；
  - 默认 `BACKUP_VERIFY_COMPOSE=true`，匹配本机无 `pg_restore` 的终验路径。
- 新增 `scripts/validate_release_manual_gate_inputs.py`：
  - 只读校验人工门输入；
  - 空模板/占位符保持 `manual_required`；
  - 完整输入时生成最终 `run_release_acceptance.py --include-backup-verify --backup-verify-compose ... --json` 命令；
  - 明确 `network_io=not_executed`、`destructive_actions=not_executed`、`secrets_printed=false`。
- 更新 `Makefile`：
  - 新增 `release-manual-gate-template`；
  - 新增 `release-manual-gate-validate`。
- 更新文档：
  - `docs/manuals/productization-acceptance-manual.md` 增加人工门模板/校验入口；
  - `docs/manuals/release-handoff-2026-08-17.md` 增加同样入口。
- 更新 `backend/tests/test_config_validation.py`：
  - 锁定脚本只读边界、模板 fail-closed、完整输入 ready、最终命令参数、手册链接。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 新增阶段 13 并标记完成；
  - 当前状态改为人工门输入模板与只读校验入口已提供。

### 本轮验证

- `python3 -m json.tool docs/manuals/release-manual-gate-inputs.template.json`：通过。
- `python3 scripts/validate_release_manual_gate_inputs.py --values docs/manuals/release-manual-gate-inputs.template.json --output /tmp/release-manual-gate-report.json --json`：`manual_required`，missing_gate_count=3，network/destructive 均未执行。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'release_manual_gate_input_validator_is_read_only or productization_manuals_exist or release_acceptance_script_plan_includes_delivery_gates'`：3 passed。
- `rg -n "状态：进行中|\[ \]" .planning/report_quality_replan/task_plan.md`：无匹配，所有规划阶段已收口。
- `make release-manual-gate-validate`：`manual_required`，missing_gate_count=3，生成 `docs/manuals/release-manual-gate-input-validation-report.json`。
- `./backend/.venv/bin/python scripts/run_release_acceptance.py --plan-only --include-backup-verify --backup-verify-compose --json`：planned，failed=0，blocked=0，manual_required=3，skipped=0，total=9；真实 restore/rollback 均未执行。

### 仍未上线

- 生产部署仍未执行。
- 现在剩余动作已变成“填写模板并由人工审批/执行外部演练”，不是代码自动完成项。

## 2026-08-17 阶段 14 人工门证据归档模板

- 新增 `docs/manuals/release-manual-gate-evidence-template.md`：
  - 覆盖基本发布信息、发布包/备份/checksum、证据归档目录；
  - 固定增强 release acceptance 终验命令；
  - 覆盖维护窗口与回滚演练证据；
  - 覆盖异地备份恢复演练证据；
  - 覆盖外部存储 shadow 恢复验证证据；
  - 固定 go/no-go/defer 发布决策和签署字段。
- 更新 `docs/manuals/release-handoff-2026-08-17.md`：
  - 链接证据归档模板；
  - 明确只有证据按模板归档后才能从“可进入人工发布审批”升级为“可执行生产上线”。
- 更新 `docs/manuals/productization-acceptance-manual.md`：
  - 链接证据模板，要求人工演练完成后归档维护窗口、异地备份恢复和外部存储恢复证据。
- 更新 `backend/tests/test_config_validation.py`：
  - 锁定证据模板包含 `MAINTENANCE_WINDOW_ID`、`OFFSITE_BACKUP_TARGET`、`EXTERNAL_STORAGE_BACKUP_REF`、release acceptance JSON 和 go/no-go/defer 决策。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 新增阶段 14 并标记完成；
  - 当前状态改为人工门输入、只读校验入口和证据归档模板已提供。

### 本轮验证

- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'productization_manuals_exist or release_manual_gate_input_validator_is_read_only'`：2 passed。
- `rg -n "状态：进行中|\[ \]" .planning/report_quality_replan/task_plan.md`：无匹配。

### 仍未上线

- 生产部署仍未执行。
- 仍需人工填写输入模板、执行维护窗口/异地恢复/外部存储恢复，并按证据模板归档后再做 go/no-go 决策。

## 2026-08-17 阶段 15 发布操作员包

- 新增 `docs/manuals/release-operator-packet-2026-08-17.md`：
  - 记录当前状态：本地自动门槛通过、增强 release acceptance failed=0 / blocked=0 / skipped=0、生产未部署；
  - 按顺序列出操作员步骤：读交接、填输入模板、只读校验、增强终验、真实外部演练、证据归档、go/no-go/defer；
  - 汇总必要命令和必备文件；
  - 固定不能越过的边界：不得把 `manual_required` 写成已上线，不得无维护窗口执行 rollback/restore，不得直接恢复到生产 bucket/prefix；
  - 写明 go/no-go 最小条件。
- 更新 `docs/manuals/productization-acceptance-manual.md` 和 `docs/manuals/release-handoff-2026-08-17.md`：
  - 链接操作员包。
- 更新 `backend/tests/test_config_validation.py`：
  - 锁定操作员包包含 `manual_required`、`make release-manual-gate-validate`、`failed=0 / blocked=0`、`shadow bucket/prefix` 和 `go/no-go/defer`。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 新增阶段 15 并标记完成；
  - 当前状态改为人工门输入、只读校验入口、证据归档模板和操作员包已提供。

### 本轮验证

- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'productization_manuals_exist'`：1 passed。
- `rg -n "状态：进行中|\[ \]" .planning/report_quality_replan/task_plan.md`：无匹配。

### 仍未上线

- 生产部署仍未执行。
- 下一步只能由操作员填写人工门输入并完成真实外部演练/证据归档。

## 2026-08-17 阶段 16 操作员包机器清单

- 新增 `scripts/build_release_operator_packet_manifest.py`：
  - 只读检查操作员包关键文件；
  - 为每个文件记录路径、存在状态、字节数和 SHA-256；
  - 记录 release 状态：local automated gates passed、enhanced release acceptance passed-with-manual-gates、failed=0、blocked=0、skipped=0、manual_required=3、production_deployed=false；
  - 明确 `network_io=not_executed`、`destructive_actions=not_executed`、`secrets_printed=false`。
- 新增生成文件 `docs/manuals/release-operator-packet-manifest-2026-08-17.json`。
- 更新 `Makefile`：
  - 新增 `release-operator-packet-manifest`。
- 更新文档：
  - `docs/manuals/release-operator-packet-2026-08-17.md` 增加 manifest 命令和必备文件条目；
  - `docs/manuals/productization-acceptance-manual.md` 增加 manifest 生成入口。
- 更新 `backend/tests/test_config_validation.py`：
  - 锁定 manifest 脚本只读边界、关键文件、`production_deployed=false`、`manual_required=3` 和 checksum 输出。
- 更新 `.planning/report_quality_replan/task_plan.md`：
  - 新增阶段 16 并标记完成；
  - 当前状态改为操作员包机器清单已提供。

### 本轮验证

- `python3 scripts/build_release_operator_packet_manifest.py --json`：`ready-for-operator-review`，file_count=7，missing_files=[]。
- `make release-operator-packet-manifest`：`ready-for-operator-review`，file_count=7，missing_files=[]。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'release_operator_packet_manifest_is_read_only or productization_manuals_exist'`：2 passed。
- `rg -n "状态：进行中|\[ \]" .planning/report_quality_replan/task_plan.md`：无匹配。

### 仍未上线

- 生产部署仍未执行。
- 机器清单只证明交接包完整，不替代人工门输入、真实演练、证据归档和 go/no-go/defer 决策。

## 2026-08-17 阶段 17 操作员包机器清单新鲜度

- 更新 `scripts/build_release_operator_packet_manifest.py`：
  - 新增 `--check` 只读模式；
  - 读取已有 manifest，与当前关键文件存在状态、SHA-256、发布状态和安全字段比较；
  - 忽略生成时间 `created_at`，避免无意义的时间漂移；
  - 缺失、非法 JSON 或内容漂移均返回非零和 `stale-or-missing`。
- 更新 `Makefile`：
  - 新增 `release-operator-packet-manifest-check`。
- 更新文档：
  - 操作员包和产品化验收手册要求交接前运行 freshness check；
  - 明确 `stale-or-missing` 时先重新生成再复查。
- 重新生成 `docs/manuals/release-operator-packet-manifest-2026-08-17.json`，同步本轮文档 hash。
- 更新 `backend/tests/test_config_validation.py`：
  - 验证生成后 `--check` 返回 `current`；
  - 篡改文件 hash 后验证返回非零和 `stale-or-missing`；
  - 锁定两个手册包含新的 Makefile 入口。

### 本轮验证

- `python3 -m py_compile scripts/build_release_operator_packet_manifest.py`：通过。
- `python3 scripts/build_release_operator_packet_manifest.py --check --json`：`current`，file_count=7，missing_files=[]。
- `make release-operator-packet-manifest-check`：通过，`current`。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'release_operator_packet_manifest_is_read_only or productization_manuals_exist'`：2 passed。
- `rg -n "状态：进行中|\[ \]" .planning/report_quality_replan/task_plan.md`：应保持无匹配。

### 仍未上线

- 生产部署仍未执行。
- 清单新鲜度检查只确认交接文件版本一致，不替代人工门输入、真实演练、证据归档和 go/no-go/defer 决策。

## 2026-08-18 酶平台专业化竞品调研

- 使用 planning-with-files-zh 恢复现有计划、发现和进度。
- 检查已有设计文档：
  - `docs/designs/2026-08-04-enzyme-foundation-and-objective-modules.md`
  - `docs/designs/2026-07-04-tool-and-database-expansion-roadmap.md`
  - `docs/designs/2026-07-10-matvenus-analysis-style-study.md`
  - `docs/designs/2026-08-11-ai-protein-platform-strategy-state-research.md`
- 联网核对国外平台/工具公开资料：Cradle、Arzeda、Schrodinger、AlphaFold、PROSS2、M-CSA、BRENDA；Rhea/Caver Web 部分页面存在 Cloudflare/SSL 抓取限制，保留 URL 作为后续复核来源。
- 检查当前后端工具和报告生成代码，确认已有能力和缺口。
- 新增文档：`docs/designs/2026-08-18-enzyme-platform-benchmark-roadmap.md`，包含竞品矩阵、当前差距、反超 Venus 的 7 个模块、P0-P3 优先级和上线验收门槛。

## 2026-08-18 新 release 公网恢复

- 新 release 先前失败的根因有两层：
  - `docker/.env.aliyun.app` 里的托管 PostgreSQL / Redis 端点解析到私网地址，ECS 上 TCP 连接超时；
  - `docker/ssl/server.crt` / `server.key` 在新 release 包里缺失，导致 nginx 因证书加载失败反复重启。
- 处理方式：
  - 将新 release 的 app env 切换为旧 release 已验证可达的公网端点；
  - 从旧 release 复制 `docker/ssl` 证书文件到新 release；
  - 重新 `./deploy-aliyun.sh app up`。
- 结果：
  - `backend / frontend / worker / md-worker / ligand-worker / nginx / outline / chromadb` 全部 healthy；
  - `http://120.27.108.138/nginx-health`、`http://120.27.108.138/api/health`、`http://120.27.108.138/wiki` 均通过。
- Outline migration 收口：
  - 直接执行 `yarn db:migrate` 不适用于当前镜像，因为镜像中没有全局 `yarn`；
  - 改用 `/opt/outline/node_modules/.bin/sequelize` 并指定 `NODE_ENV=production-ssl-disabled` 后，确认 schema 已是最新：`No migrations were executed, database schema was already up to date.`
- 当前状态：新 release 已恢复公网可用，但托管 RDS/Redis 的原始网络拓扑问题仍需单独修复或重新规划。

## 2026-08-17 阿里云配置终验与发布门复验

- 用户补充数据库密码候选后，`docker/.env.aliyun.app` / `docker/.env.aliyun.gpu` 已使用首选候选值渲染 RDS URL。
- 只读生产配置 gate 通过：`python3 scripts/check_production_config.py --mode production --require-production-safe --skip-domain-https --env-file docker/.env --env-file docker/.env.aliyun.app --json` 返回 `ready`，critical=0，warning=0，`secrets_printed=false`。
- 刷新 go/no-go：`python3 scripts/build_release_go_no_go_summary.py --json` 返回 `manual_required`，blocking_items 仅剩 `manual_gate_inputs`、`manual_gate_evidence`。
- 未授权沙箱内完整 release acceptance 首次失败：Playwright 浏览器进程被沙箱关闭，`verify_backup.sh --compose` 无权访问 Docker socket；这不是业务代码失败。
- 授权后重跑完整 release acceptance：
  - `FRONTEND_BASE_URL=http://127.0.0.1:4200 backend/.venv/bin/python scripts/run_release_acceptance.py --include-frontend --include-browser-smoke --include-live --include-backup-verify --backup-verify-compose --json`
  - 结果：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=0，total=9。
  - acceptance matrix、browser public smoke、browser live smoke、backup_verify、deploy-live-gate、backend-smoke-live 均通过。
- 生产部署仍未执行；剩余三个人工门为维护窗口/生产演练授权、异地备份恢复、外部对象存储 shadow restore 证据。

## 2026-08-17 阶段 22 生产配置阻断纳入 go/no-go

- 用户要求继续推进上线；先恢复本地运行栈中缺失的 Redis 服务。
- 通过 Docker 受控执行确认：
  - `./deploy-aliyun.sh app ps` 显示 backend、frontend、nginx、postgres、redis、minio、outline、worker、md-worker、ligand-worker 全部 healthy。
  - `curl http://127.0.0.1:4200/nginx-health` 返回 `ok`。
  - `curl http://127.0.0.1:4200/api/health` 返回 `{"status":"ok","version":"0.1.0"}`。
  - `FRONTEND_BASE_URL=http://127.0.0.1:4200 node frontend/tests/live-smoke.mjs` 返回 `Live smoke passed`。
- 加固 `scripts/check_production_config.py`：
  - 检测 `CHANGE_ME`、`change-me`、`changeme`、`<...>`、`your-*` 占位；
  - DB、Redis、对象存储、LLM provider key 中出现占位时在 production mode 标为 critical。
- 加固发布入口：
  - `scripts/run_acceptance_matrix.py`、`scripts/run_nightly_live_gates.py`、`Makefile` production config gate 均加入 `--require-production-safe`。
- 加固 `scripts/build_release_go_no_go_summary.py`：
  - 默认只读运行 production config gate；
  - go/no-go blocking_items 现在会包含 `production_config_gate`。
- 验证：
  - 定向测试：`5 passed`。
  - `make config-test`：`106 passed`。
  - 当前 `make production-config-gate-json` 按预期阻断：`docker/.env` 缺生产 DB/Redis/对象存储。
  - 当前增强 release acceptance 按预期失败：production config gate blocked，原因是 `docker/.env.aliyun.app` 中 DB/Redis 仍含占位。
  - `make release-go-no-go-summary`：`manual_required`，blocking_items=`production_config_gate, manual_gate_inputs, manual_gate_evidence`。

### 仍未上线

- 生产部署未执行。
- app 节点 env 仍需真实 RDS/Redis 值替换 `CHANGE_ME_*`。
- GPU 节点仍缺 `docker/.env.aliyun.gpu`。
- 三个人工门仍缺真实输入和证据归档。

## 2026-08-17 用户提供云账号信息后的配置收敛

- 用户提供了 ECS / RDS / Redis / OSS / AccessKey 信息后，已将本机托管服务配置写入：
  - `docker/.env.aliyun.app`
  - `docker/.env.aliyun.gpu`
- 已更新：
  - `PUBLIC_BASE_URL` 为 `http://120.27.108.138:4200`
  - Redis endpoint / user / password / app URL / outline URL
  - OSS endpoint / region / bucket / access key / secret key
  - app 与 GPU compose 配置均可渲染
- 仍未解决：
  - RDS PostgreSQL 真实登录密码未提供，`ALIYUN_APP_DATABASE_URL` / `ALIYUN_OUTLINE_DATABASE_URL` / `ALIYUN_OUTLINE_DATABASE_URL_TEST` 仍保留密码占位
  - 因此 `make production-config-gate-json` 仍返回 `blocked`，阻断项为 `DATABASE_URL`
- 验证：
  - `make docker-config-aliyun-app` 通过
  - `make docker-config-aliyun-gpu` 通过
  - `make release-go-no-go-summary` 仍为 `manual_required`

## 2026-08-17 阶段 19 人工门证据机器校验

- 新增 `scripts/validate_release_manual_gate_evidence.py`：
  - 校验发布包/备份引用、release acceptance 计数、三个人工门证据路径、shadow restore 和签署决策；
  - `production_path_switched` 必须显式为 `false`；
  - 布尔决策字段必须显式为 `true`；
  - 只读运行，不联网、不执行 release acceptance、不执行 restore/rollback、不切换生产路径。
- 新增 `docs/manuals/release-manual-gate-evidence-inputs.template.json` 和默认校验报告。
- 更新 `Makefile`：
  - `release-manual-gate-evidence-template`
  - `release-manual-gate-evidence-validate`
- 更新发布交接记录、产品化验收手册和操作员包：
  - 先填写并校验证据 JSON，再按 Markdown 模板归档；
  - 证据校验为 `manual_required` 时不得做 go 决策。
- 更新 `scripts/build_release_operator_packet_manifest.py`：
  - 操作员包关键文件从 7 个扩展为 9 个，纳入证据模板和校验器。

### 本轮验证

- `python3 -m py_compile scripts/validate_release_manual_gate_evidence.py scripts/build_release_operator_packet_manifest.py`：通过。
- `make release-manual-gate-evidence-template`：生成模板，状态 `manual_required`。
- `make release-manual-gate-evidence-validate`：`manual_required`，`evidence_complete=false`，`ready_for_go=false`。
- 完整临时证据记录测试：返回 `ready-for-go`。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py`：104 passed。
- `python3 scripts/build_release_operator_packet_manifest.py --check --json`：`current`，file_count=9，missing_files=[]。
- 串行重跑 `./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=0，total=9。

### 仍未上线

- 生产部署仍未执行。
- 新校验器只确认人工证据记录是否完整，不替代真实外部演练、人工签署或生产上线授权。

## 2026-08-17 阶段 20 证据归档 Markdown 模板入口补齐

- 更新 `docs/manuals/release-manual-gate-evidence-template.md`：
  - 在用途说明后加入 `make release-manual-gate-evidence-template`；
  - 加入 `make release-manual-gate-evidence-validate`；
  - 避免操作员只填写 Markdown 表格而跳过机器可读 JSON 证据校验。
- 更新 `backend/tests/test_config_validation.py`：
  - 锁定证据 Markdown 模板必须包含机器模板生成与证据校验命令。
- 重新生成 `docs/manuals/release-operator-packet-manifest-2026-08-17.json`，同步证据模板 hash。

### 本轮验证

- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'release_manual_gate_evidence_validator_is_read_only or productization_manuals_exist'`：2 passed。
- `python3 scripts/build_release_operator_packet_manifest.py --json`：`ready-for-operator-review`，file_count=9，missing_files=[]。
- `make release-operator-packet-manifest-check`：`current`。
- 串行重跑 `./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=0，total=9。

## 2026-08-17 阶段 21 发布决策汇总与工作区清单

- 新增 `scripts/build_release_go_no_go_summary.py`：
  - 读取人工输入校验报告、人工证据校验报告和操作员包 manifest；
  - 输出 `docs/manuals/release-go-no-go-summary-2026-08-17.json` 和 `.md`；
  - 当前状态为 `manual_required`，阻断项为 `manual_gate_inputs` 与 `manual_gate_evidence`。
- 新增 `scripts/build_release_worktree_manifest.py`：
  - 只运行 `git status --short`；
  - 输出 path-only dirty worktree 清单，不输出 diff 内容；
  - 当前 dirty_file_count=372，作为人工发布门复核输入。
- 新增 `docs/manuals/release-manual-gate-evidence.schema.json`。
- 新增 `docs/manuals/release-manual-gate-evidence.example.json`：
  - 标记 `example_only=true`；
  - 最终决策为 `defer`，`--require-go` 不会通过。
- 更新 Makefile、发布交接记录、产品化验收手册、操作员包和证据模板，加入新命令和文件说明。
- 操作员包 manifest 关键文件从 9 个扩展为 13 个。

### 本轮验证

- `python3 -m py_compile scripts/build_release_go_no_go_summary.py scripts/build_release_worktree_manifest.py scripts/build_release_operator_packet_manifest.py scripts/validate_release_manual_gate_evidence.py`：通过。
- `make release-go-no-go-summary`：`manual_required`，blocking_items=`manual_gate_inputs, manual_gate_evidence`。
- `make release-worktree-manifest`：`manual_required`，dirty_file_count=372。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'release_manual_gate_evidence_validator_is_read_only or release_decision_summary_and_worktree_manifest_are_read_only or release_operator_packet_manifest_is_read_only or productization_manuals_exist'`：4 passed。
- `python3 scripts/build_release_operator_packet_manifest.py --json`：`ready-for-operator-review`，file_count=13，missing_files=[]。
- `make release-operator-packet-manifest-check`：`current`。
- 串行重跑 `./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`：`passed-with-manual-gates`，failed=0，blocked=0，manual_required=3，skipped=0，total=9。

### 仍未上线

- 生产部署仍未执行。
- 新工具只聚合和复核本地证据，不替代真实外部演练、人工签署或生产上线授权。

## 2026-08-17 release acceptance 复验与 compose 修复

- 复跑 `make release-operator-packet-manifest-check` 和 `scripts/build_release_operator_packet_manifest.py --check --json`，均返回 `current`。
- 先前完整 release acceptance 失败点定位为 `verify_backup.sh --compose` 访问 Docker socket 被拒绝，不是 backup checksum 或 `pg_restore --list` 本身失败。
- 通过受控 Docker 权限重跑只读备份校验，确认 checksum、custom dump 格式和 `pg_restore --list` 均通过。
- 修复 `docker/docker-compose.yml`：
  - `storage-init` 现在同时初始化 `upload_storage` 和 `ligand_scratch`；
  - 本地 `ligand-worker` 现在挂载 `ligand_scratch:/app/storage`，与阿里云 GPU compose 的隔离语义对齐。
- 重跑完整 `run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`，结果为 `passed-with-manual-gates`，`failed=0 / blocked=0 / manual_required=3 / skipped=0 / total=9`。
- 完整 `backend/tests/test_config_validation.py` 回归为 `103 passed`，`docker compose -f docker/docker-compose.yml config --quiet` 通过。

## 2026-08-17 阶段 18 交接记录清单新鲜度加固

- 更新 `docs/manuals/release-handoff-2026-08-17.md`：
  - 增加交接前执行 `make release-operator-packet-manifest-check` 的要求；
  - 使 handoff、操作员包和产品化验收手册对 manifest freshness 的口径一致。
- 更新 `backend/tests/test_config_validation.py`：
  - 在 manifest 测试中新增缺失 manifest fail-closed；
  - 新增非法 JSON fail-closed；
  - 保留 hash 漂移 `stale-or-missing` 断言。
- 修改 handoff 后先运行 `python3 scripts/build_release_operator_packet_manifest.py --check --json`，确认返回 `stale-or-missing` 且 `stale_sections=["files"]`。
- 重新生成 `docs/manuals/release-operator-packet-manifest-2026-08-17.json`。

### 本轮验证

- `python3 scripts/build_release_operator_packet_manifest.py --check --json`：修改 handoff 后按预期返回 `stale-or-missing`。
- `python3 scripts/build_release_operator_packet_manifest.py --json`：`ready-for-operator-review`。
- `make release-operator-packet-manifest-check`：`current`。
- `python3 -m py_compile scripts/build_release_operator_packet_manifest.py`：通过。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py -k 'release_operator_packet_manifest_is_read_only or productization_manuals_exist'`：2 passed。
- `./backend/.venv/bin/python -m pytest -q backend/tests/test_config_validation.py`：103 passed。

## 2026-08-17 线上回滚恢复

- 尝试将 `current` 切到新 release `20260817T055402Z-25679eb` 后，app 栈启动进入半可用状态：
  - `backend / frontend / outline` 能启动，但其余 worker 与 outline 依赖在健康检查阶段阻断；
  - ECS 到托管 `RDS / Redis` 的端口连通性超时，`worker / md-worker / ligand-worker` 因 Redis 不可达 unhealthy，`outline` 因 PostgreSQL 不可达 unhealthy。
- 立即回滚 `current` 到旧 release `20260815T022436Z-25679eb`，并重新 `./deploy-aliyun.sh app up`。
- 回滚后复验结果：
  - `backend / frontend / outline / nginx / worker / md-worker / ligand-worker / chromadb` 均 healthy；
  - 本机 `curl http://127.0.0.1/nginx-health` 与 `curl http://127.0.0.1/api/health` 通过；
  - 公网 `http://120.27.108.138/nginx-health`、`http://120.27.108.138/api/health`、`http://120.27.108.138/wiki` 均通过。
- 结论：线上可用入口已恢复，但新 release 仍被 ECS 到托管 RDS/Redis 的网络连通问题阻断，不能直接重新上线。

### 最终终验

- 串行重跑 `./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`：
  - status：`passed-with-manual-gates`
  - failed：0
  - blocked：0
  - manual_required：3
  - skipped：0
  - total：9
- `backup_verify` 继续通过 compose postgres 内只读 `pg_restore --list`。
- 生产部署仍未执行；当前结论仍是“可进入人工发布审批”，不是“已上线”。

### 仍未上线

- 生产部署仍未执行。
- 清单新鲜度检查只确认交接文件版本一致，不替代人工门输入、真实演练、证据归档和 go/no-go/defer 决策。
