# Biomni 对 KWB 酶蛋白大模型研发可迁移点

日期：2026-07-31

## 来源

- 微信文章：用户提供 `https://mp.weixin.qq.com/s/qILWUo2cbrs6nZb0BJLsuA?scene=1`，当前浏览器无法直接打开。
- GitHub：`https://github.com/snap-stanford/biomni`
- README raw：`https://raw.githubusercontent.com/snap-stanford/Biomni/main/README.md`
- 论文/PMC：`https://pmc.ncbi.nlm.nih.gov/articles/PMC12157518/`
- license info：`https://raw.githubusercontent.com/snap-stanford/Biomni/main/license_info.md`
- environment README：`https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni_env/README.md`

## 可直接借鉴

1. 生物医学 action space 方法：
   - Biomni 从文献中抽取 task、tool、database、software，再由人工专家验证。
   - KWB 应建立“酶改造 action space”：MSA、编号核实、结构链映射、ddG、底物 docking、实验设计、QC、反馈导入、模型训练、报告生成。

2. 工具元数据和注册表：
   - Biomni 用 tool registry + declarative tool schema 管理工具。
   - KWB 应把现有脚本、外部工具、数据库查询统一成 `tool_contract.jsonl`，字段包括输入、输出、依赖、license、是否需要人工确认、是否能进入训练。

3. 检索式工具选择：
   - Biomni 使用 LLM-based retriever 选择 tools/data lake/libraries/know-how，避免把全部工具塞进上下文。
   - KWB 可做 enzyme-specific resource retriever：按用户任务选择 UniProt/PDB/InterPro/MSA/ddG/wet-lab/FireProt/benchmark 等资源。

4. CodeAct / code-based execution：
   - Biomni 用代码作为统一动作接口，能组合 Python、R、Bash、数据库、软件工具。
   - KWB 当前已有 fail-closed pipeline，适合进一步包装成受控 CodeAct：只允许 allowlisted scripts/tools，所有输出必须进入 reports 和 manifests。

5. Know-how library：
   - Biomni 有可检索 protocol、best practice、troubleshooting 文档，并记录 license/commercial metadata。
   - KWB 应建设“酶改造 know-how library”：编号核实规则、突变风险规则、ddG 阈值、湿实验 SOP、plate QC、客户交付禁区。

6. Benchmark/task 统一接口：
   - Biomni 有 `task/base_task.py` 风格的 benchmark abstraction。
   - KWB 应把 mutation ranking、stability、activity、substrate_fit、assay_success 都做成统一 benchmark task 接口，先评估再声明。

7. 商业许可模式：
   - Biomni 有 `commercial_mode` 思路，用于过滤非商业/需授权数据。
   - KWB 应把现有 license gate 升级为 runtime policy：默认 commercial-safe，只读 license-approved 数据和工具。

## 需要改造后使用

1. Biomni-A1 agent 架构：
   - 可借鉴 LangGraph/ReAct/CodeAct 结构。
   - 不能照搬“全权限执行代码”；KWB 必须保留 sandbox、allowlist、人工确认和 fail-closed gates。

2. Biomni datalake：
   - 默认数据湖约 11GB，完整 E1 环境至少 30GB 且 setup 可能超过 10 小时。
   - KWB 不建议全量安装；优先只接入酶相关子集：UniProt、PDB、InterPro、AlphaFold/structure、protein sequence/task benchmark。

3. Biomni-R0：
   - 可作为“生物工具调用 reasoning model”对标候选。
   - 不能替代 KWB-EnzymeDesigner 的酶蛋白专用监督模型；更适合作 agent planner 或 tool-use benchmark baseline。

4. MCP 支持：
   - 可借鉴 MCP 暴露/接入工具的方式。
   - KWB 应先做内部 tool contract，再决定是否通过 MCP 暴露给 GPT 主控或平台。

## 暂不建议直接采用

1. 不建议在当前机器直接完整安装 Biomni E1：
   - 环境重、依赖多、下载大、license 混杂，不符合当前 fail-closed 研发节奏。

2. 不建议把 Biomni 数据湖直接用于训练：
   - 多个数据源存在 non-commercial、custom license 或需要商业许可。
   - 只能先做 license/source registry，不得直接混入 KWB training rows。

3. 不建议开放 Biomni 式全权限代码执行：
   - Biomni README 明确提醒 agent 会以系统权限执行代码、访问文件/网络/命令。
   - KWB 应继续保持可审计、受限、按工具白名单执行。

## 推荐下一步

1. 建 `enzyme_action_space_registry`：
   - 把 KWB 现有 action 分成 tool/database/software/know-how/benchmark 五类。

2. 建 `enzyme_tool_contract`：
   - 每个工具必须有 schema、test case、runtime readiness、license gate、human gate、output artifact contract。

3. 建 `enzyme_resource_retriever`：
   - 输入用户任务，输出应调用的工具、数据、SOP、benchmark；不直接执行。

4. 建 `biomni_comparison_readiness_report`：
   - 对照 Biomni 的 E1/A1/R0/Eval/Know-how 五块，评估 KWB 缺口。

5. 只在用户明确允许下载时，再做最小化源码缓存：
   - 先 clone/read-only，不安装 E1、不下载 11GB datalake、不运行全权限 agent。

## 对 KWB 顶级模型的价值判断

Biomni 对 KWB 最有价值的不是某个单独工具，而是系统工程范式：统一 action space、工具/数据/软件/know-how 检索、代码化执行、benchmark 化评估、license-aware 数据模式。KWB 需要把这些范式收敛到酶蛋白改造专用领域，并继续坚持 reviewed numbering、真实实验反馈、ddG 后端、benchmark score cache、release gate 的 fail-closed 边界。
