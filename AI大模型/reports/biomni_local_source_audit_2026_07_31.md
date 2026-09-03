# Biomni 本地源码审计：安装判断与新增可借鉴点

日期：2026-07-31

## 本轮实际操作

用户允许“需要安装就安装”。本轮采取最小必要动作：

- `git clone https://github.com/snap-stanford/Biomni.git cache/external/Biomni` 尝试失败，环境把 GitHub 访问转到 SSH 端口，连接被关闭。
- 改用 GitHub zip 源码包下载。
- 源码包已保存到：`cache/external/biomni-main-20260731.zip`
- sha256：`158873d40c1675f05ac857afa055e24dcd0035817d7f60d5b4bd7249adf3740f`
- 大小：约 1.0MB
- 项目中文路径下直接 unzip 遇到 Biomni 内部协议文件名编码问题，因此在 `/private/tmp/biomni-src/Biomni-main` 解压审计。

本轮没有执行：

- 没有安装 Biomni Python package；
- 没有创建 conda env；
- 没有运行 A1/ReAct agent；
- 没有下载 Biomni datalake；
- 没有启动 MCP；
- 没有执行 Biomni 工具。

## 是否需要完整安装

当前不需要完整安装。

理由：

1. 当前目标是学习架构并迁移到 KWB，源码审计已足够。
2. Biomni full E1 官方环境需要 Ubuntu 22.04、30GB 以上磁盘、10 小时以上 setup。
3. Biomni A1 初始化默认会检查/下载 data lake；这与 KWB 当前 fail-closed 策略冲突。
4. README 明确提醒 Biomni 会执行 LLM 生成代码并拥有系统权限；KWB 不能直接运行这种模式。
5. KWB 已有本地 action/tool contract，下一步应做 controlled planning，而不是安装 Biomni 全栈。

推荐安装策略：

- 当前：只保留源码 zip 和审计报告；
- 如果后续必须运行：先建隔离目录/容器，只装 base/reduced env；
- 禁止直接运行 full E1；
- 禁止默认下载 data lake；
- 禁止运行 A1 agent 的任意 code execution；
- 禁止开放 MCP 执行。

## 本地源码结构

源码核心目录：

- `biomni/agent`：A1、ReAct 等 agent；
- `biomni/model`：retriever；
- `biomni/tool`：工具函数和 tool descriptions；
- `biomni/task`：task abstraction；
- `biomni/eval`：BiomniEval1；
- `biomni/know_how`：know-how loader 和少量文档；
- `biomni_env`：多套 conda 环境；
- `docs`：配置、MCP、known conflicts。

## 新增可借鉴点

### 1. A1 自动 data lake 下载必须反向改造

Biomni A1 初始化时会创建 `biomni_data/benchmark` 和 `biomni_data/data_lake`，然后在未传入 `expected_data_lake_files` 时自动检查并下载 S3 data lake/benchmark。

KWB 借鉴方式：

- 建 `kwb_data_lake_readiness_manifest`；
- 只读本地已有 artifact；
- 不允许 agent 初始化时自动下载；
- 所有下载必须由用户明确授权，并写入 source/license/checksum manifest。

### 2. Custom tool 注入机制要改成 contract 注册

Biomni `A1.add_tool()` 会：

- inspect 函数源码；
- 用 LLM 生成 API schema；
- 注册到 ToolRegistry；
- 加入 module2api；
- 注入 builtins，供执行环境使用。

KWB 借鉴方式：

- 不能让 LLM 自动生成可执行 schema 后直接注册；
- 新工具必须走 `enzyme_tool_contracts.jsonl`；
- schema 可以由 LLM 草拟，但必须 validator 通过；
- 不注入 builtins；
- 不允许 agent 添加能写 formal/training/release 的工具。

### 3. MCP 动态发现很强，但默认不能开

Biomni `add_mcp()` 支持：

- 读取 YAML MCP server config；
- 自动 discover MCP tools；
- 为每个 server 创建 module namespace；
- 为 MCP tool 创建同步 wrapper；
- 注册进 tool registry。

KWB 借鉴方式：

- 先做 `kwb_mcp_export_manifest.json`；
- 只暴露 read-only 工具；
- MCP import 默认禁用；
- 每个外部 MCP server 必须有 license/security/network review；
- MCP tool 不能写 formal/training/release。

### 4. ReAct timeout wrapper 值得迁移

Biomni ReAct 给每个 tool 包 multiprocessing timeout：

- 子进程运行 tool；
- 超时 terminate；
- 仍不退出则 SIGKILL；
- 返回 timeout error。

KWB 借鉴方式：

- 每个 tool contract 增加 `timeout_seconds`、`kill_policy`、`failure_artifact`；
- local script 可统一包装；
- 外部 runtime 需要独立 timeout；
- 超时必须生成 receipt/report，不能只返回字符串。

### 5. Persistent Python REPL 对 KWB 是高风险设计

Biomni `run_python_repl` 使用全局 `_persistent_namespace`，不同执行之间变量保留。

KWB 判断：

- 对开放科研方便；
- 对生产/客户/训练极不安全；
- 会造成状态污染和不可复现。

KWB 只能借鉴“可保存执行上下文”的思想，不能使用共享 REPL。应改为：

- 每次工具执行独立 process/workdir；
- 输入/输出通过 artifact；
- checkpoint 只记录元数据，不保留可变 Python namespace。

### 6. Tool call parsing 可以用于审计

Biomni utils 会解析 `<execute>` 代码块中的 import/call，关联 tool execution result。

KWB 借鉴方式：

- 对 agent 生成的计划做 static parse；
- 先识别将要调用哪些 tool contract；
- 再按 policy 分成 read-only/executable/blocked/forbidden；
- 生成 `enzyme_resource_retrieval_plan_report.json`。

### 7. Result formatting 可迁移为结构化报告

Biomni ReAct 有 `result_formatting()`，用 structured output 从 agent log 提取任务结果。

KWB 借鉴方式：

- 定义 `enzyme_agent_result_schema.json`；
- 所有突变推荐必须结构化；
- 字段必须包括 variant、evidence、ddG、uncertainty、manual_review_required、experimental_plan、forbidden_claims、artifact_refs。

### 8. BiomniEval1 task/eval 很轻，但接口方向正确

Biomni `base_task` 只有：

- `get_example`
- `get_iterator`
- `evaluate`
- `output_class`
- `get_prompt_from_input`

`BiomniEval1` 从 HuggingFace parquet 加载 benchmark，然后按 task_name 调 `_compute_reward`。

KWB 借鉴方式：

- 做 `kwb_enzyme_eval_task_base.py`；
- 每个五头 task 都要有：
  - prompt/input；
  - expected structured output；
  - evaluator；
  - split；
  - leakage guard；
  - claim threshold。

### 9. Know-how loader 简单但适合迁移

Biomni know-how loader 会读取 markdown、抽取 title/overview/metadata/short_description。

本地源码中当前 know-how 文档很少，主要是 `sgRNA_design_guide.md` 和 `single_cell_annotation.md`，与酶蛋白改造不直接匹配。

KWB 借鉴方式：

- 自建 `enzyme_know_how/`；
- markdown 必须带 metadata：
  - applicability；
  - license；
  - reviewer；
  - source；
  - effective_date；
  - forbidden_use；
  - required_validators。

### 10. Known conflicts 证明必须 runtime 分层

Biomni 单独记录 `known_conflicts.md`，例如 hyperimpute、Bedrock support、cnvkit、panhumanpy 等需要独立环境或手动安装。

KWB 借鉴方式：

- 建 `kwb_runtime_conflict_registry.jsonl`；
- Rosetta/FoldX/PyRosetta/MMseqs/ThermoMPNN/PLM/benchmark 各自独立 runtime；
- 不追求一个环境装完所有东西。

## 对 KWB 下一步的具体建议

最值得立即落地：

1. `enzyme_agent_execution_protocol.md`
2. `schemas/enzyme_agent_state_checkpoint.schema.json`
3. `schemas/enzyme_resource_retrieval_plan.schema.json`
4. `scripts/build_enzyme_resource_retrieval_plan.py`
5. `scripts/validate_enzyme_resource_retrieval_plan.py`
6. `datasets/governance/enzyme_agent_state_checkpoints.jsonl`
7. `reports/enzyme_resource_retrieval_plan_report.json`

这些模块只做 planning/retrieval/checkpoint，不执行工具、不写训练、不需要安装 Biomni。

## 当前结论

Biomni 源码确认了两个方向：

1. 它的开放科研 agent 架构很强，值得 KWB 学习；
2. 它的默认执行/下载/共享 REPL/MCP 能力对 KWB 当前目标太开放，必须转成 contract-first、read-only-first、fail-closed-first 的酶蛋白专用 agent。

因此下一步不是完整安装 Biomni，而是把 KWB 的 controlled resource retrieval 和 execution protocol 做出来。
