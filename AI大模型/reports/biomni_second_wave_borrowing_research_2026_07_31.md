# Biomni 第二波深度学习：KWB 还可以借鉴什么

日期：2026-07-31

## 来源

- Biomni README: https://github.com/snap-stanford/biomni
- DETAILS: https://raw.githubusercontent.com/snap-stanford/Biomni/main/DETAILS.md
- A1 agent 源码: https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/agent/a1.py
- ReAct agent 源码: https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/agent/react.py
- ToolRetriever 源码: https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/model/retriever.py
- MCP 文档: https://raw.githubusercontent.com/snap-stanford/Biomni/main/docs/mcp_integration.md
- 配置文档: https://raw.githubusercontent.com/snap-stanford/Biomni/main/docs/configuration.md
- 环境文档: https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni_env/README.md
- dependency conflicts: https://raw.githubusercontent.com/snap-stanford/Biomni/main/docs/known_conflicts.md
- contribution guide: https://raw.githubusercontent.com/snap-stanford/Biomni/main/CONTRIBUTION.md

## 1. Plan -> Execute -> Observe -> Reflect -> Solution 协议

Biomni A1 的 system prompt 要求先写计划，每步完成后更新 checklist；执行用 `<execute>`，观察回写，再最终输出 `<solution>`。

KWB 可借鉴：

- 建 `enzyme_agent_execution_protocol.md`；
- 固定 5 段：
  1. plan；
  2. tool call proposal；
  3. controlled execution receipt；
  4. observation/reflection；
  5. guarded conclusion；
- 每步必须带 artifact path 和 validator。

KWB 改造边界：

- 不允许任意 `<execute>`；
- 只能执行 `enzyme_tool_contracts.jsonl` allowlisted 工具；
- 所有高风险工具必须先给用户确认。

## 2. Checkpoint / memory

Biomni A1 使用 LangGraph `MemorySaver`，说明它有 conversation/state checkpoint 思路。

KWB 可借鉴：

- 建 `enzyme_agent_state_checkpoint.jsonl`；
- 每次工具规划/执行记录：
  - request_id；
  - selected_action_ids；
  - selected_tool_contract_ids；
  - blocked_actions；
  - executed_actions；
  - artifact outputs；
  - validator outputs；
  - claim/release status snapshot。

价值：

- 防止 agent 忘记上一轮失败原因；
- 支撑“继续推进”自动恢复；
- 后续可做 agent behavior benchmark。

## 3. Timeout 和 tool isolation

Biomni ReAct 给每个 tool 包 timeout wrapper，超时后 terminate/kill 子进程。

KWB 可借鉴：

- 给每个 local script contract 增加：
  - timeout_seconds；
  - max_runtime_class；
  - retry_policy；
  - failure_artifact；
  - kill_policy；
- 对外部工具如 Rosetta/FoldX/MMseqs/ThermoMPNN 建 runtime-specific timeout。

KWB 不能照搬：

- 不能只 kill process 就算安全；
- 还要检查文件输出、formal 文件写权限、训练行数、claim gate。

## 4. MCP 双向集成

Biomni 同时支持：

- 添加外部 MCP server；
- 把 Biomni 工具暴露成 MCP server。

KWB 可借鉴：

- 第一阶段：只做 `KWB MCP export manifest`，不启动 server；
- 第二阶段：只暴露 read-only 工具：
  - 查询 action space；
  - 查询 tool contract；
  - 查询 readiness；
  - 查询报告；
  - 查询人工 backlog；
- 第三阶段：在用户授权后才允许执行 local validators。

KWB 禁区：

- 不暴露 formal decision 写入；
- 不暴露 training import；
- 不暴露 customer/order/release 动作；
- 不默认连接外部 MCP。

## 5. 配置一致性

Biomni 文档强调 `default_config` 会影响 agent 和 database queries，而 direct parameter 只影响当前 agent reasoning。

KWB 可借鉴：

- 建 `kwb_agent_runtime_config_report.json`；
- 固定：
  - controller_llm；
  - database_query_llm；
  - retrieval_llm；
  - execution_mode；
  - commercial_mode；
  - network_policy；
  - download_policy；
  - formal_write_policy；
  - training_write_policy。

价值：

- 避免“agent 用一个模型、数据库查询用另一个模型”造成不可复现；
- 避免外部网络/下载策略混乱。

## 6. Environment tiering

Biomni full E1 需要很长 setup 和较大磁盘；还提供 reduced/base/Python3.10 环境，并记录 known conflicts。

KWB 可借鉴：

- 建 KWB runtime tier：
  - `tier0_read_only_metadata`
  - `tier1_local_python_validators`
  - `tier2_local_bioinformatics_runtime`
  - `tier3_gpu_or_heavy_model_runtime`
  - `tier4_license_manual_runtime`
- 每个 runtime 都要有：
  - install status；
  - version；
  - checksum；
  - smoke；
  - conflict notes；
  - license status。

这比把 Rosetta/FoldX/ThermoMPNN/MMseqs/PLM 全塞到一个大环境更稳。

## 7. Contribution governance

Biomni contribution guide 把新增 tool、data、software、benchmark 分成不同流程。

KWB 可借鉴：

- 建 `enzyme_contribution_governance.md`；
- 对新增能力分别要求：
  - new tool：contract + validator + smoke；
  - new data：source/license/checksum/no overlap；
  - new software：runtime manifest + conflict report；
  - new benchmark：task interface + split/leakage guard；
  - new know-how：source/reviewer/applicability。

价值：

- 后续多 agent 或多人协作时不会乱加工具/数据；
- 顶级模型研发可持续扩展。

## 8. Structured output extraction / result formatting

Biomni 有 `result_formatting`，用结构化输出从 agent log 中抽取 task result。

KWB 可借鉴：

- 建 `enzyme_agent_result_schema`：
  - selected_variants；
  - property_predictions；
  - evidence_level；
  - ddg_results；
  - human_review_required；
  - experimental_plan；
  - forbidden_claims；
  - artifact_refs。

每次用户问“推荐突变位点”时，最终结果必须满足 schema，不允许散文式输出直接进入平台。

## 9. Research log / PDF / audit package

Biomni 支持保存 conversation history/PDF，工具执行也强调打印清晰 research log。

KWB 可借鉴：

- 每次分析生成：
  - `analysis_trace.jsonl`；
  - `tool_call_receipts.jsonl`；
  - `evidence_bundle.md`；
  - `user_facing_report.md`；
- 平台上给用户看到“为什么推荐/为什么阻断”。

这能提升客户信任，也能避免模型黑箱。

## 10. Prompt-based resource retrieval 的改造

Biomni retriever 是“宁可多选一些资源”，适合开放科研探索。

KWB 应反过来：

- 对 read-only resources 可以 generous；
- 对 executable tools 必须 conservative；
- 对 formal/training/release 工具必须 blocked unless authorized；
- retriever 输出必须分 4 类：
  - recommended_read_only；
  - executable_after_user_confirmation；
  - blocked_requires_human_decision；
  - forbidden_for_current_request。

## 11. Custom resources 优先级

Biomni prompt 会把 custom tools/data/software/know-how 放在 priority section。

KWB 可借鉴：

- 用户上传结构、真实湿实验、客户项目背景应被放在 priority context；
- 但优先级不等于可信训练标签；
- 仍必须经过 numbering/QC/license gate。

## 12. Biomni-R0 的借鉴方式

Biomni-R0 是基于 agent interaction data 的 biology reasoning model。

KWB 可借鉴：

- 不急着训练大模型；
- 先收集 KWB agent interaction traces：
  - tool planning；
  - blocked reason；
  - validation result；
  - human correction；
  - final report；
- 将来可训练 KWB tool-use planner，而不是直接训练 wet-lab label predictor。

## 推荐下一步 P0

1. `enzyme_agent_execution_protocol.md`
2. `enzyme_agent_state_checkpoint.schema.json`
3. `enzyme_resource_retrieval_plan.schema.json`
4. `build_enzyme_resource_retrieval_plan.py`
5. `validate_enzyme_resource_retrieval_plan.py`

这一步不需要下载、不运行外部工具、不写训练数据，是 Biomni 第二波最适合 KWB 立即落地的方向。

## 仍然不能做的事

- 不能完整安装 Biomni E1；
- 不能自动下载 Biomni data lake；
- 不能开放任意 Python/R/Bash 执行；
- 不能接入外部 MCP 执行动作；
- 不能把 Biomni-R0 当成 KWB 专用模型完成；
- 不能绕过 KWB reviewed numbering、真实实验反馈、ddG 后端、benchmark score cache 和 release gate。
