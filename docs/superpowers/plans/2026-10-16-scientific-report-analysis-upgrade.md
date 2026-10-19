# 科学报告分析升级实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在不改变现有页面布局的前提下，补齐结构功能证据、外部数据库证据、结论证据绑定、可执行湿实验建议、报告版本复现和生产版本一致性门禁。

**架构：** 保留现有 `ReportGenerator`、`report_quality_contract` 和 Agent 工具结果协议；新增统一的证据对象、报告 manifest 和版本一致性校验，先在后端生成结构化报告数据，再由 Markdown/前端消费。实验结论继续 fail-closed：缺失实验数据时只能输出假设与测定计划，不能升级为已验证结论。版本治理独立于报告正文，发布前比较源码、报告 schema、模型、前端 bundle 和生产镜像 digest。

**技术栈：** Python 3.12、FastAPI、SQLAlchemy、现有工具注册/AgentOrchestrator、Markdown 报告生成、pytest、Vite/React（只增加数据展示字段，不改既有布局样式）。

---

## 文件职责

- 修改：`backend/app/services/report_generator.py`，将结构化报告的证据、状态、版本和复现信息统一写入 front matter/附录。
- 修改：`backend/app/services/report_quality_contract.py`，增加证据状态、结论类别和报告版本契约。
- 创建：`backend/app/services/report_evidence_contract.py`，定义 `experimental_fact`、`database_evidence`、`computed_result`、`inference`、`hypothesis` 五类证据及缺失/失败状态。
- 创建：`backend/app/services/report_manifest.py`，生成输入文件、工具、模型、数据库、运行时间和 revision manifest，并计算稳定哈希。
- 修改：`backend/app/core/agent_graph.py`，将结构/配体/同源/实验上下文汇总为报告 evidence blocks；保留当前工具失败和等待状态。
- 修改：`backend/app/tools/structure_search_foldseek.py`、`backend/app/tools/site_structure_function_features.py`，补充配体接触、口袋/通道、链界面和可追溯结构几何字段。
- 创建：`backend/app/tools/ligand_contact_analysis.py`，从上传结构和配体坐标计算残基接触、距离、链/配体实例和证据状态。
- 创建：`backend/app/tools/structure_pocket_interface_analysis.py`，输出口袋/通道和链界面几何线索，明确不等同于结合能或催化证明。
- 修改：`backend/app/tools/blast_search.py`、`backend/app/services/blast_report_revision.py`，统一 `waiting`、`failed`、`no_hit`、`completed` 状态及原始 RID/查询时间。
- 修改：`backend/app/services/publish_service.py`、`backend/app/api/publish.py`，发布报告时保存 manifest/revision 标识并拒绝未通过质量契约的结构化报告。
- 修改：`frontend/src/lib/report.ts`、`frontend/src/components/analysis/PDBAnalysisCard.tsx`、`frontend/src/components/analysis/SiteStructureFunctionFeaturesCard.tsx`，仅增加证据状态、来源和“待验证”字段的消费，不改变现有页面布局和 CSS。
- 创建：`scripts/check_report_version_alignment.py`，比较源码 schema、报告 generator、模型 ID、前端 bundle manifest、生产 release 和镜像 digest。
- 修改：`scripts/check_upgrade_readiness.py`、`scripts/build_release_worktree_manifest.py`，把报告版本一致性作为发布阻断门。
- 创建：`backend/tests/test_report_evidence_contract.py`、`backend/tests/test_report_manifest.py`、`backend/tests/test_ligand_contact_analysis.py`、`backend/tests/test_pocket_interface_analysis.py`、`backend/tests/test_report_revision_states.py`。
- 修改：`backend/tests/test_report_quality_contract.py`、`backend/tests/test_report_user_scenarios.py`、`backend/tests/test_publish_api.py`、`backend/tests/test_config_validation.py`。
- 创建：`scripts/tests/test_check_report_version_alignment.py`。
- 创建：`docs/manuals/report-analysis-evidence-contract.md`、`docs/manuals/report-version-release-gate.md`。
- 修改：`progress.md`、`docs/project-experience-memory.md`，记录每个阶段的验证证据、线上 release、回滚点和已知边界。

## 版本管理原则

1. 报告功能版本使用独立 `report_schema_version`，不把 Git 分支名当作功能版本。
2. 每个线上 release 必须同时记录：Git revision、worktree manifest SHA、backend/frontend image digest、LLM provider/model、report schema version、数据库 migration head。
3. 生产只允许从通过 `check_report_version_alignment.py` 的 release 目录切换；失败时不得更新 `current`。
4. 报告正文不得写入密钥；manifest 只保存变量名、是否设置、哈希或非敏感摘要。
5. 页面样式冻结。报告字段只允许通过现有组件的数据接口接入；不得顺带调整 logo、布局、字体、间距或 CSS。

### 任务 1：冻结报告证据和版本协议

**文件：**
- 创建：`backend/app/services/report_evidence_contract.py`
- 创建：`backend/app/services/report_manifest.py`
- 修改：`backend/app/services/report_quality_contract.py`
- 测试：`backend/tests/test_report_evidence_contract.py`、`backend/tests/test_report_manifest.py`
- 文档：`docs/manuals/report-analysis-evidence-contract.md`

- [x] **步骤 1：编写失败测试**

  测试以下行为：五类 evidence type 有固定枚举；`waiting`、`failed`、`not_run` 不得渲染为完成；推断和假设必须带 `derived_from`；manifest 必须包含输入哈希、报告 schema、工具版本和运行时间；密钥值不得出现在序列化结果中。

- [x] **步骤 2：运行测试验证失败**

  运行：`cd backend && python -m pytest tests/test_report_evidence_contract.py tests/test_report_manifest.py -q`

  预期：因新模块和契约字段尚不存在而失败。

- [x] **步骤 3：实现最小协议**

  定义不可变 dataclass/TypedDict 和纯函数：`make_evidence_record(...)`、`normalize_evidence_status(...)`、`build_report_manifest(...)`、`manifest_sha256(...)`。输入哈希使用 SHA-256；工具/数据库/模型来源只保存公开标识和状态；禁止把 token、Authorization、Cookie 写入 manifest。

- [x] **步骤 4：运行测试验证通过**

  运行同一 pytest 命令，预期全部通过，并增加对 JSON 稳定排序和重复生成哈希一致性的断言。

- [x] **步骤 5：更新契约文档**

  在 `docs/manuals/report-analysis-evidence-contract.md` 写出字段、状态转换、允许的结论措辞和禁止的升级路径；文档示例使用假数据。

### 任务 2：报告生成器接入证据和复现 manifest

**文件：**
- 修改：`backend/app/services/report_generator.py`
- 修改：`backend/app/services/publish_service.py`、`backend/app/api/publish.py`
- 修改：`backend/tests/test_publish.py`、`backend/tests/test_publish_api.py`、`backend/tests/test_report_quality_contract.py`

- [x] **步骤 1：编写失败测试**

  覆盖结构化报告：front matter 包含 `report_schema_version`、`report_revision_id` 和 `evidence_summary`；附录包含 manifest；等待中的 BLAST 显示“等待/未完成”而非“无命中”；缺少湿实验数据时输出 `hypothesis` 和实验动作，不能输出 `experimentally_validated`。

- [x] **步骤 2：运行测试验证失败**

  运行：`cd backend && python -m pytest tests/test_publish.py tests/test_publish_api.py tests/test_report_quality_contract.py -q`

  预期：新增字段和状态断言失败。

- [x] **步骤 3：实现最小接入**

  在 `ReportGenerator.generate_conversation_report` 中调用证据协议和 manifest；报告正文保持现有核心章节顺序；把证据表放入现有发布/原始执行信息附录，避免改变已冻结的页面结构。

- [x] **步骤 4：运行定向回归**

  运行同一命令，预期已有报告质量、发布和 API 测试全部通过；再运行 `python -m pytest tests/test_report_user_scenarios.py -q`。

### 任务 3：补齐结构功能证据工具

**文件：**
- 创建：`backend/app/tools/ligand_contact_analysis.py`
- 创建：`backend/app/tools/structure_pocket_interface_analysis.py`
- 修改：`backend/app/tools/structure_search_foldseek.py`、`backend/app/tools/site_structure_function_features.py`、工具注册文件
- 测试：`backend/tests/test_ligand_contact_analysis.py`、`backend/tests/test_pocket_interface_analysis.py`、`backend/tests/test_structure_tools.py`

- [x] **步骤 1：编写失败测试**

  使用小型 PDB fixture 验证：每个配体实例独立列出；接触残基带链、编号、距离和接触类型；多链结构不把总数差解释为缺失原因；没有配体/坐标不完整时返回明确 `not_available`；口袋/通道和界面结果明确标记为几何线索，禁止输出结合能或催化证明。

- [x] **步骤 2：运行测试验证失败**

  运行：`cd backend && python -m pytest tests/test_ligand_contact_analysis.py tests/test_pocket_interface_analysis.py -q`

- [x] **步骤 3：实现几何分析**

  使用现有 PDB 解析器和坐标数据，采用固定距离阈值并在结果中记录阈值、坐标覆盖率、配体 component/instance、chain scope 和计算时间；不得使用字符串猜测残基或把 B-factor 当稳定性证据。

- [x] **步骤 4：注册并接入深度分析计划**

  已注册两个几何工具；只有用户请求深度结构分析且输入包含结构坐标时加入，纯序列或 standard PDB 计划不会加入；工具失败状态保留在报告证据表，报告仍输出已完成的结构事实。

- [x] **步骤 5：运行结构回归**

  运行：`cd backend && python -m pytest tests/test_structure_tools.py tests/test_report_user_scenarios.py -q`。

### 任务 4：统一外部数据库与 BLAST 状态

**文件：**
- 修改：`backend/app/tools/blast_search.py`、`backend/app/services/blast_report_revision.py`
- 修改：`backend/app/services/evidence_source_status.py`
- 测试：`backend/tests/test_report_revision_states.py`、`backend/tests/test_blast_resume.py`

- [x] **步骤 1：编写失败测试**

  固定四种状态：`submitted/waiting`、`failed`、`completed_no_hit`、`completed_with_hits`；验证 NCBI 暂未返回不能生成“无同源命中”；续查保持原 RID；报告修订保留原始报告和新证据版本。

- [x] **步骤 2：运行测试验证失败**

  运行：`cd backend && python -m pytest tests/test_report_revision_states.py tests/test_blast_resume.py -q`

- [x] **步骤 3：实现状态映射**

  统一工具结果、后台任务、证据表和 Markdown 文案的状态词；每次外部查询保存 checked_at、endpoint、数据库标识和 RID，不保存密钥。

- [x] **步骤 4：运行回归**

  运行上述 pytest，并用受控 fixture 验证 waiting、失败、无命中和有命中四条报告路径。

### 任务 5：生成可执行的湿实验建议

**文件：**
- 修改：`backend/app/core/agent_graph.py`
- 修改：`backend/app/services/report_quality_contract.py`
- 修改：`backend/tests/test_report_user_scenarios.py`、`backend/tests/test_agent_binder.py`
- 文档：`docs/manuals/report-analysis-evidence-contract.md`

- [x] **步骤 1：编写失败测试**

  对 7DVJ 类输入验证报告必须区分 WT、E142A 和回补对照；必须输出表达/SEC、动力学、pH/温度、Tm/热失活和 Go/No-Go 入口；没有实测数据时禁止输出“提高活性/提高 Tm/已验证候选”。

- [x] **步骤 2：运行测试验证失败**

  运行：`cd backend && python -m pytest tests/test_report_user_scenarios.py tests/test_agent_binder.py -q -k 'report or wet_lab or assay'`

- [x] **步骤 3：实现最小报告模板**

  从结构事实和构建体差异生成实验矩阵；测定项目必须包含读出、对照、重复和升级条件；仅在输入含 assay context 或已保存实验记录时填入定量值。

- [x] **步骤 4：运行质量回归**

  Python 3.12 报告/策略回归通过；API 级 BLAST 持久化用例仍要求 OIDC signing key，因此保留为发布环境门。

  运行同一测试命令和 `cd backend && python -m pytest tests/test_report_quality_contract.py -q`，预期不得破坏现有 fail-closed 门控。

### 任务 6：版本一致性门和发布流程

**文件：**
- 创建：`scripts/check_report_version_alignment.py`
- 创建：`scripts/tests/test_check_report_version_alignment.py`
- 修改：`scripts/check_upgrade_readiness.py`、`scripts/build_release_worktree_manifest.py`
- 文档：`docs/manuals/report-version-release-gate.md`
- 版本管理审计输入：`output/version-management-audit-20261017.md`

- [x] **步骤 1：编写失败测试**

  用假 manifest 验证以下情况必须阻断：Git revision 与 release manifest 不同；报告 schema 不同；frontend bundle 与 release manifest 不同；生产 LLM model 不是 `gpt-6-sol`；backend/frontend 镜像 digest 与 release 记录不同；回滚目标缺失。

- [x] **步骤 2：运行测试验证失败**

  运行：`python3 -m pytest scripts/tests/test_check_report_version_alignment.py -q`

- [x] **步骤 3：实现版本门**

  脚本只读比较 JSON/文本 manifest，输出不含密钥的差异列表；成功时输出唯一 release identity，失败时 exit code 非零；集成 `check_upgrade_readiness.py`，在部署脚本切换 `current` 前执行。

- [x] **步骤 4：加入版本管理 agent 审计结果**

  将子 agent 的分支、commit、release、镜像 digest、模型配置和漂移结论落到 `output/version-management-audit-20261017.md`，任何未解决漂移保持 release blocked。

- [x] **步骤 5：运行版本门回归**

  运行：`python3 -m pytest scripts/tests/test_check_report_version_alignment.py -q`、`python3 scripts/check_report_version_alignment.py --json`、`python3 scripts/check_upgrade_readiness.py --json`。

### 任务 7：前端证据状态和报告导出验收

**文件：**
- 修改：`frontend/src/lib/report.ts`、`frontend/src/components/analysis/PDBAnalysisCard.tsx`、`frontend/src/components/analysis/SiteStructureFunctionFeaturesCard.tsx`
- 测试：现有 `frontend/tests/pdb-upload-report-live-20261015.mjs` 及新增证据状态 fixture 测试

- [x] **步骤 1：编写失败 fixture 测试**

  验证 `waiting`、`failed`、`not_run`、`computed`、`experimental` 在现有报告区域显示不同状态和来源；文本超长不溢出；页面主布局和 CSS 哈希不变。

- [x] **步骤 2：实现数据消费**

  只扩展现有报告数据类型和状态文案，复用既有组件样式和间距；不新增侧栏、logo、workspace 或布局调整。

- [x] **步骤 3：运行前端验证**

  运行：`cd frontend && npm run build`；再运行已有 PDB 报告 Playwright/Node smoke；比较构建前后的 CSS 哈希和关键 DOM 结构。

### 任务 8：真实 7DVJ 验收、发布和回滚演练记录

**文件：**
- 创建：`output/report-analysis-upgrade-20261016/REPORT.md`
- 修改：`progress.md`、`docs/project-experience-memory.md`

- [x] **步骤 1：本地/容器验收**

  使用 7DVJ fixture 验证结构事实、E142A 构建体、BMA 接触、BLAST waiting/no-hit 区分、湿实验建议和 manifest。

- [x] **步骤 2：运行完整定向测试**

  运行后端报告/结构/发布测试、版本门测试、前端构建和报告浏览器 smoke；记录退出码、通过数和失败数。

- [ ] **步骤 3：生产发布前门禁**

  生成 release manifest，运行版本一致性脚本、配置探针、健康检查和回滚目标检查；失败不得切换 `current`。

  Chroma 升级还须验证 `backups/chroma/*.tar.gz` 与 SHA-256/JSON receipt，并在隔离环境使用目标镜像完成真实恢复和 collection 读取；当前仅完成自动归档机制，恢复演练仍未执行。

- [ ] **步骤 4：线上验收**

  上传 7DVJ，执行报告分析，验证报告版本、证据状态、下载/发布、Wiki 回读、无新增 5xx；不修改现有页面样式。

- [ ] **步骤 5：记录报告和残余风险**

  在 `output/report-analysis-upgrade-20261016/REPORT.md` 记录输入哈希、release identity、工具状态、证据缺口、测试结果和未完成外部依赖；同步进度和运行记忆。

## 验收标准

- 结构事实、数据库证据、计算结果、推断和假设在报告中可区分，且每项可追溯到来源或工具结果。
- BLAST waiting 不再被写成 no-hit；报告修订保留原始报告和新的证据版本。
- 配体接触、口袋/通道和链界面有可复现几何输出，并明确不能替代催化或热稳定性实验。
- 湿实验建议包含构建体、对照、读出、重复和 Go/No-Go 条件；无 assay 数据时不生成已验证定量结论。
- 每次 release 有唯一版本 identity，源码、报告 schema、模型、bundle、镜像和回滚目标一致，否则自动阻断。
- 前端 CSS、logo、布局、workspace 和现有页面样式保持不变。
- 线上真实 7DVJ 验收、健康检查、错误日志和回滚证据全部记录。
