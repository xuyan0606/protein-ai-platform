# Biomni 源码级深度学习：KWB 酶蛋白大模型可用架构

日期：2026-07-31

## 结论

Biomni 不是一个“单一深度学习模型”，而是一个 biomedical agent operating system：LLM agent + tool registry + resource retriever + data lake + software environment + know-how + benchmark + license mode。KWB 不应照搬 Biomni 的全权限执行方式，而应吸收它的 action-space 和 retriever 架构，改造成酶蛋白专用、fail-closed、可审计、商业合规的研发系统。

## 源码级观察

### 1. A1 agent 初始化

Biomni `A1` 初始化时做几件关键事：

- 读取默认配置和用户传参；
- 按 `commercial_mode` 选择 academic 或 commercial data/library description；
- 检查并下载 data lake；
- 建立 `ToolRegistry`；
- 建立 `ToolRetriever`；
- 加载 know-how；
- 生成 system prompt；
- 编译 LangGraph workflow。

KWB 对应建设：

- `KWBEnzymeAgentConfig`：区分 local-only、commercial-safe、research-only、production-blocked。
- `enzyme_data_lake_dict`：只描述本地已审计数据，不自动下载。
- `enzyme_tool_registry`：只注册 allowlisted 工具。
- `enzyme_resource_retriever`：只做资源选择，不直接执行。
- `enzyme_know_how_loader`：加载编号核实、ddG、湿实验、QC、报告规则。

### 2. ToolRegistry

Biomni 的 `ToolRegistry` 非常轻量，只要求：

- `name`
- `description`
- `required_parameters`

然后提供按 id/name 查询、注册和删除。

KWB 不够用，需要扩展字段：

- `tool_id`
- `name`
- `category`: database/tool/software/know_how/benchmark/pipeline
- `input_schema`
- `output_schema`
- `runtime_readiness_report`
- `license_status`
- `human_confirmation_required`
- `can_write_formal_decision`
- `can_write_training_rows`
- `safe_for_model_claim`
- `allowed_execution_mode`: read_only/local_script/external_binary/manual_only
- `required_artifacts`
- `validator_script`

核心原则：工具注册不是“能调用就行”，而是必须知道它能不能改变训练数据、能不能进入 claim、是否需要人工确认。

### 3. ToolRetriever

Biomni `ToolRetriever` 是 prompt-based retrieval：把 tools、data lake、libraries、know-how 列出来，让 LLM 返回索引。

优点：

- 简单；
- 易扩展；
- 不需要 embedding index；
- 能同时选工具、数据、库、know-how。

风险：

- LLM 可能过度选择；
- 只有索引解析，没有 hard policy；
- 不区分“可执行”和“只读建议”。

KWB 改造：

1. 第一层：LLM/规则选择候选资源。
2. 第二层：policy filter 强制过滤：
   - 未授权 license；
   - 未 ready runtime；
   - 会写 formal decision；
   - 会写 training rows；
   - 会触发外部下载/网络；
   - release/customer/order claim。
3. 第三层：生成 tool call plan，等待用户确认后执行。
4. 第四层：所有输出进入 `reports/`、`datasets/governance/`、manifest、validator。

### 4. CodeAct 执行循环

Biomni 要求模型输出 `<execute>...</execute>` 或 `<solution>...</solution>`，然后执行 Python/R/Bash/CLI。执行结果回写 `<observation>`，LangGraph 再继续推理。

优点：

- 适合科研任务；
- 能组合数据库、脚本、图表、统计和外部软件；
- 过程可形成 research log。

KWB 必须保守改造：

- 不允许任意 `<execute>`；
- 只允许调用已注册、已验证的 KWB scripts/tools；
- 不允许 agent 自由 Bash；
- 不允许直接写 formal human decision；
- 不允许直接写 training rows；
- 不允许绕过 `run_safe_training_pipeline.py`；
- 每次执行要有 receipt、artifact、validator。

建议命名：`KWBControlledCodeAct`。

### 5. Know-how library

Biomni know-how 的价值很高：把实验协议、最佳实践、troubleshooting 做成可检索文档，还记录 author/license/commercial metadata。

KWB 应先建 8 类 know-how：

1. 编号核实 SOP；
2. 结构链映射 SOP；
3. MSA/conservation 解释规则；
4. Rosetta/PyRosetta/FoldX/ThermoMPNN ddG 阈值和禁区；
5. 湿实验授权和 QC SOP；
6. Plate-level feedback SOP；
7. 五头模型训练和评估 SOP；
8. 客户交付/订购/IP/生物安全禁区。

这些 know-how 不能只是说明文档，应进入 resource retriever，让 agent 在生成突变建议时自动引用对应规则。

### 6. Commercial mode / license mode

Biomni 用 `commercial_mode=True` 自动过滤非商业数据描述。KWB 需要更严格：

- `commercial_safe`: 只允许商业可用、授权明确的数据/工具；
- `research_only`: 允许研究调研，但不能训练或客户交付；
- `manual_review_required`: 人工 license decision 未完成；
- `blocked`: 禁止调用和进入 claim。

每个外部数据源和工具都必须有 license row，不能靠 README 口头判断。

### 7. Environment strategy

Biomni full E1 环境安装时间长、磁盘大、依赖冲突多。KWB 不应复制一个大环境，而应采用 tool-isolated runtime：

- `runtime/mmseqs2`
- `runtime/thermompnn`
- `runtime/rosetta`
- `runtime/foldx`
- `runtime/structure`
- `runtime/benchmark`

每个 runtime 独立 readiness report、license gate、smoke artifact。

### 8. Benchmark abstraction

Biomni `base_task` 很简单：`get_example`、`get_iterator`、`evaluate`、`output_class`、`get_prompt_from_input`。

KWB 应做酶蛋白版本：

- `MutationRankingTask`
- `StabilityPredictionTask`
- `ActivityRiskTask`
- `SubstrateFitTask`
- `AssaySuccessTask`
- `ReportFaithfulnessTask`
- `ToolPlanCorrectnessTask`

每个 task 必须绑定 data version、split policy、leakage guard、metric、claim threshold。

## KWB 可落地模块优先级

### P0：先做架构底座

1. `enzyme_action_space_registry.jsonl`
2. `enzyme_tool_contracts.jsonl`
3. `enzyme_resource_retrieval_plan_report.json`
4. `enzyme_know_how_index.jsonl`
5. `validate_enzyme_tool_contracts.py`

这些不需要人工授权，不会改变训练标签。

### P1：接入受控执行

1. `KWBControlledCodeAct` adapter；
2. 只允许执行 allowlisted scripts；
3. 每次执行必须生成 receipt；
4. receipt 必须进入 data lake/local release；
5. blocked 工具只能展示计划，不能运行。

### P2：任务级 benchmark

1. 定义五头 benchmark task interface；
2. 把已有 strict/claim/benchmark/feedback gate 接进去；
3. 没有真实标签的 head 输出 blocked eval，不输出虚假分数。

## 不应做的事

1. 不应完整安装 Biomni E1。
2. 不应下载 Biomni 11GB datalake 后直接训练。
3. 不应开放 Biomni 式全权限 Python/R/Bash 执行。
4. 不应把 Biomni-R0 当成 KWB 专用模型完成。
5. 不应跳过 KWB 当前 reviewed numbering、真实实验反馈、ddG backend、benchmark cache、release gate。

## 推荐下一步执行

下一步最实际的是 P0：创建 KWB enzyme action space 和 tool contract。它能把当前散落的 200+ scripts、reports、validators 统一成一个 agent 可检索、可审计、可执行规划的资源层，并且不需要人工确认、不需要下载、不改变 hard gates。
