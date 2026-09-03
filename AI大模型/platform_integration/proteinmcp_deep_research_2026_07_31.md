# ProteinMCP 深度学习研究记录

日期：2026-07-31

目标：研究 `charlesxu90/ProteinMCP` 对 KWB-EnzymeDesigner 顶级模型与酶蛋白 AI 平台的可借鉴设计。本文只做本地研发建议，不代表已安装、已接入或已通过生产许可。

## 来源

- GitHub: `https://github.com/charlesxu90/ProteinMCP`
- README raw: `https://raw.githubusercontent.com/charlesxu90/ProteinMCP/main/README.md`
- MCP catalog raw: `https://raw.githubusercontent.com/charlesxu90/ProteinMCP/main/tool-mcps/README.md`
- Protein Science paper: `https://doi.org/10.1002/pro.70547`
- PMC full text: `https://pmc.ncbi.nlm.nih.gov/articles/PMC13140703/`
- bioRxiv preprint: `https://doi.org/10.64898/2026.03.11.711149`
- 临时源码审计：`/private/tmp/proteinmcp-source-audit`，审计后删除。

## 关键事实

ProteinMCP 是一个面向蛋白工程的 agentic AI framework，核心不是单个模型，而是把多个蛋白设计工具用 MCP 统一成可由 LLM agent 调度的工具生态。论文和 README 显示其公开目标包括：

1. 统一管理 38 个 MCP servers。
2. 支持 `pmcp avail/install/status/uninstall/create` 这类 MCP 生命周期命令。
3. 支持 `pskill` workflow skill，把复杂流程封装为可复用命令。
4. 典型 workflow 包括 fitness modeling、binder design、nanobody design。
5. fitness modeling workflow 同时比较 MSA/PLMC/EV+OneHot/ESM/ProtTrans 等路线，再聚合和可视化结果。
6. MCP creation pipeline 可从 GitHub 或本地 repo 包装工具，生成隔离环境、server、README 和注册信息。

## 最值得 KWB 学的地方

### 1. 工具不是散装脚本，而是 MCP 生命周期资产

ProteinMCP 把工具分为 Python 本地 env 和 Docker/GPU 两类，并提供安装、状态、卸载、创建和注册流程。KWB 当前已经有很多 fail-closed 脚本和 adapter，但还缺一个统一生命周期层。

KWB 可落地设计：

- 新增 `kwb_tool_lifecycle_registry.jsonl`。
- 每个工具记录 `runtime_type`、`install_status`、`license_status`、`probe_status`、`smoke_status`、`production_allowed`。
- Rosetta/PyRosetta/FoldX/ThermoMPNN/MMseqs2/InterPro/structure cache 都纳入同一 registry。
- 不直接接入生产，只先做 local-only lifecycle board。

### 2. workflow skill 比长 prompt 更适合标准实验流程

ProteinMCP 用 skill 封装 fitness modeling/binder design/nanobody design。KWB 已有很多 Markdown runbook 和 operator packet，但还没有面向操作员的一键 skill 层。

KWB 可落地设计：

- `skills/enzyme_mutation_prioritization.md`
- `skills/wet_lab_feedback_intake_review.md`
- `skills/ddg_backend_runtime_probe.md`
- `skills/five_head_training_gate_review.md`

每个 skill 固定输入、工具顺序、输出报告、禁止动作和 validator。

### 3. fitness modeling 应该多路线集成比较，而不是押一个模型

ProteinMCP 的 fitness modeling 同时跑 co-evolutionary 和 PLM 路线。KWB 当前有 MSA、structure graph、ThermoMPNN proxy、baseline scaffold，但缺一个 head-level ensemble comparison 合同。

KWB 可落地设计：

- 对每个 head 建 `candidate_model_family`：
  - mutation: rule/baseline/PLM embedding/MSA conservation/structure graph
  - stability: ThermoMPNN proxy/physics ddG/FoldX/Rosetta/FireProt reviewed labels
  - activity: wet-lab authorized numeric metrics/assay-aware models
  - substrate: substrate identity + docking/structure pocket features
  - assay: condition-aware QC and batch effect model
- 输出只允许 `model_family_comparison_report`，在真实标签不足前不产生 claimable model。

### 4. 自动包装工具值得学，但必须比 ProteinMCP 更严格

ProteinMCP 的 `pmcp create` 思路很强：给 repo URL 和目标函数，自动建环境、找 use cases、生成 MCP wrapper、测试、写文档。KWB 可以借鉴，但不能直接让 agent 任意包装并执行湿实验/生产/外部工具。

KWB fail-closed 改造：

- 只允许在 `sandboxed_tool_staging/` 创建 wrapper。
- 每个 wrapper 必须生成：
  - source checksum
  - license review status
  - environment lock
  - smoke result
  - structured output schema
  - forbidden writes
  - production_allowed=false
- 只有 validator 通过后才进入 `kwb_tool_lifecycle_registry`。

### 5. MCP catalog 可以变成 KWB 工具雷达

ProteinMCP 的 MCP catalog 覆盖结构预测、蛋白设计、binder design、MD、fitness modeling、sequence analysis、databases。KWB 不应全量安装，但可以作为雷达表。

优先借鉴排序：

1. MMseqs2/MSA：已基本落地，继续巩固。
2. InterPro/domain：已落地 1785/1942，继续补 157 blocked。
3. Rosetta MCP：可作为 Rosetta 后端集成模板，但先走 license/runtime/probe。
4. ESM/ProtTrans：可做 feature-only embedding cache，不作为训练标签。
5. ProteinMPNN/LigandMPNN/RFdiffusion2：暂不进入酶改造主线，除非做设计候选生成。
6. AMBER/GROMACS：只做结构稳定性辅助证据，不进入模型 claim。
7. PubMed/UniProt/PDB/InterPro MCP：适合补 reviewed evidence retrieval。

### 6. 分层架构值得学习

ProteinMCP 论文将系统分为 user interface、orchestration、MCP server、computation 层。KWB 当前也有这些能力，但边界还散在多个报告里。

KWB 建议统一成四层：

1. Operator UI：numbering review、wet-lab review、future skill launcher。
2. Orchestration：safe pipeline、active stage matrix、enzyme agent eligibility。
3. Tool/MCP adapter：MMseqs2、InterPro、ThermoMPNN、Rosetta/FoldX probes。
4. Computation/cache：MSA cache、structure cache、domain cache、ddG cache、benchmark cache。

### 7. 我们不能照搬的地方

1. ProteinMCP 偏科研自动化，KWB 现在要工业酶改造质量声明，必须更严格。
2. 不能把 agent 成功执行 workflow 等同于模型质量 ready。
3. 不能把 GitHub 工具安装成功等同于 license/production approval。
4. 不能把 ESM/ProtTrans/PLMC 的预测分数当真实实验标签。
5. 不能让 MCP 自动写 reviewed numbering、wet-lab authorization 或 production sync。

## 源码级审计补充

本轮已按用户授权重新下载源码 zip，静态阅读后删除。源码级审计确认：ProteinMCP 的主要工程价值在 `src/mcp/`、`src/skill/`、`src/prompts/` 和 `tool-mcps/` 四类目录，不需要安装即可提取架构模式。

### 已核实源码模块

- `src/mcp/mcp.py`：定义 MCP runtime/scope/status 和 `MCP` dataclass，状态包含 not installed、installed、registered、both。
- `src/mcp/mcp_manager.py`：用 YAML 管理 local/public/installed MCP registry，并处理相对路径。
- `src/mcp/install_mcp.py`：把 install 与 register 分开，支持 `info/status/install/uninstall/search` 运营入口。
- `src/mcp/status_cache.py`：用 300 秒 TTL 和 `fcntl` 文件锁缓存状态探测结果。
- `src/mcp/mcp_creator.py`：8 步自动创建 MCP pipeline，包含 clone、环境建立、用例执行、脚本生成、MCP wrapper、Claude/Gemini 集成测试和 README 生成。
- `src/skill/skill.py`、`src/skill/skill_manager.py`：把 workflow skill 安装为 Markdown 命令，并并行检查/安装依赖 MCP，注册阶段保持顺序执行。
- `workflow-skills/fitness_modeling.md`：将 MSA、PLMC、EV+OneHot、ESM、ProtTrans 组织成可复现 fitness modeling workflow。
- `mcp-skills/mcp_creation_validator.md`：提供 Docker、GitHub Actions、依赖、权限、缓存目录和集成测试 checklist。
- `src/prompts/step6_wrap_mcp_prompt.md`、`step7_test_integration_prompt.md`、`step8_create_readme_prompt.md`：把工具包装、联调、文档生成固化为明确步骤。

### 对 KWB 可直接借鉴的源码模式

1. `kwb_tool_lifecycle_registry` 应采用对象级状态机：`not_installed -> installed -> probed -> smoke_passed -> registered_for_review`，但不能自动进入 production。
2. KWB 工具安装要拆成三段：下载/安装、探测/smoke、注册/暴露给 agent；注册前必须通过 license、checksum、schema、forbidden writes。
3. 状态探测要加 TTL cache 和文件锁，避免 Rosetta/FoldX/MMseqs2/InterPro 这类慢探测在 UI 和 pipeline 中重复执行。
4. workflow skill 可以落地为本地 Markdown + JSON receipt，而不是长 prompt；每个 skill 必须写输入、步骤、输出、禁止动作、validator。
5. 长任务要区分 sync API 与 submit API；Rosetta/FoldX 大批量 ddG、MSA 批处理、benchmark 批评分应采用 submit/status/result/log 结构。
6. 自动 wrapper create 只能进入 `sandboxed_tool_staging/`，不得直接修改正式 registry、训练表、reviewed decision 或生产配置。
7. ProteinMCP 的 MCP catalog 可作为工具雷达，优先跟踪 Rosetta、MMseqs2、InterPro、ESM/ProtTrans、AMBER/GROMACS，但 KWB 只允许逐项 license/probe/smoke 后进入本地审查。

### 源码级风险结论

ProteinMCP 的 `run_claude_with_streaming()` 会调用 Claude Code CLI 并使用 `--dangerously-skip-permissions`，`pmcp create` 又会执行 repo 用例和生成 wrapper。这类能力适合科研探索，但不适合直接进入 KWB 的真实实验、训练导入、编号审核或生产同步。KWB 若借鉴，只能加一层更严格的 staging gate，并把所有执行结果写 receipt。

## 推荐落地路线

### R1：ProteinMCP-inspired tool lifecycle registry

产物：

- `datasets/governance/kwb_tool_lifecycle_registry.jsonl`
- `reports/kwb_tool_lifecycle_registry_report.json`
- `scripts/build_kwb_tool_lifecycle_registry.py`
- `scripts/validate_kwb_tool_lifecycle_registry.py`

目标：统一显示每个工具的 runtime、license、probe、smoke、safe flags。

### R2：ProteinMCP-inspired workflow skills

产物：

- `platform_integration/workflow_skills/enzyme_mutation_prioritization.md`
- `platform_integration/workflow_skills/wet_lab_feedback_intake_review.md`
- `platform_integration/workflow_skills/ddg_backend_runtime_probe.md`

目标：把当前散落 runbook 变成固定步骤、固定输入输出、固定 validator 的 operator workflow。

### R3：MCP wrapper staging gate

产物：

- `schemas/mcp_wrapper_staging.schema.json`
- `datasets/governance/mcp_wrapper_staging_queue.jsonl`
- `reports/mcp_wrapper_staging_gate_report.json`

目标：允许后续包装 Rosetta/FoldX/ESM/ProtTrans 等工具，但只能进入 staging，不能直接进入 production 或 model claim。

### R4：fitness-model family comparison contract

产物：

- `reports/five_head_model_family_comparison_contract.json`
- `datasets/governance/model_family_comparison_matrix.jsonl`

目标：借鉴 ProteinMCP 的 fitness modeling 多路线比较，但在 KWB 中保持 `claimable_model=false`，直到 reviewed labels 和 benchmark 满足。

## 当前结论

ProteinMCP 对 KWB 最有价值的不是某个单一蛋白模型，而是三件工程化能力：

1. MCP 工具生命周期管理。
2. Workflow skill 化。
3. 多模型/多工具 workflow 的统一比较与可复现报告。

KWB 应该吸收这些架构能力，但继续保持现有 fail-closed 规则：任何工具接入、workflow 执行或模型分数都不能替代 reviewed numbering、湿实验授权、physics ddG、benchmark 和 release gate。
