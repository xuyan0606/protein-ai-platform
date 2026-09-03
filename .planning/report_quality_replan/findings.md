# 报告质量问题发现

## 用户反馈

- 报告质量差，不只是单个 PDB。
- 策略也差，不知道在分析什么。
- 上下文能力差。
- 报告格式差，中英文混合。
- 用户要求停止盲目修复，重新规划。

## 已确认的系统性问题

1. 策略层模板化

策略根据目标词直接套“热稳定性”或“比活力”模板，没有先判断输入对象证据是否足够。联合目标会被压成单一主目标，导致分析方向偏离。

2. 策略承诺与报告门控冲突

策略中会写“最终必须输出候选突变位点”，但报告阶段又因为身份/编号不确定输出 No-Go。用户看到的是前后矛盾。

3. 工具层堆叠

PDB-only 情况下会跑一串工具，部分工具结果只是启发式或后台 submitted，但报告仍然把它们堆成章节。

4. 证据门控不统一

候选表门控有所加强，但报告后半部分仍会输出 kcat、功能预测、理化性质等内容，容易被用户理解成结论证据。

5. 报告生成按工具拼接

报告结构是“哪个工具有结果就输出哪个章节”，不是围绕科学问题组织。这导致报告长、散、重复、第一屏没有真正结论。

6. 语言与格式不合格

章节标题和字段名有大量英文，表格列过多，长文本塞进表格，Wiki 可读性差。

7. 续问处理不够

用户指出错误时，系统仍倾向于继续补报告，而不是进入质量复核和错误归因模式。

## HM.pdb 案例中的代表性错误

- 把弱结构命中或模板注释升级成酶身份。
- 把 inferred mapping 写得像 SIFTS/UniProt 编号证据。
- 把 `kcat_predict` 当成可支持比活力分析的证据。
- 输出过泛的表面电荷突变候选。
- 热稳定性和比活力目标没有真正拆开。

## AI平台反馈V5 文档补充约束

- 报告顺序需要固定为：任务理解 → 输入与结构证据 → 结构同源与编号映射 → 改造策略及说明 → Physicochemical Properties → Enzyme Foundation Profile → 保护位点 → Objective Module Gate → 突变位点探索清单 → 位点突变逻辑 / 风险 / 实验动作 → 探索性验证建议。
- `Physicochemical Properties` 后面的英文内容需要大幅压缩，不能让英文模板主导整份报告。
- 用户追问“通过哪些工具得到结果”时，平台必须显式列出工具链、每个工具的作用、哪些结果只是背景、哪些结果被门控阻断。
- 有些问题会触发默认执行流程，这个默认流程不能继续吞掉输入识别和报告结构问题。
- 这意味着整改不只是翻译标题，而是要把策略承诺、执行门控、报告顺序和工具来源说明一起重构。

## 2026-08-15 最小闭环修正发现

- 旧报告生成器把“结论卡片”和 “Go / Watch / No-Go” 插在候选表之前，破坏了反馈文档要求的核心顺序。
- 身份门控阻断时旧报告会输出“突变候选输出门控”独立章节，导致固定报告结构缺少“突变位点探索清单”和“位点突变逻辑 / 风险 / 实验动作”的占位解释。
- 附录内部使用 `##` 标题会污染 Wiki 目录，让证据审计看起来像核心章节。
- 突变设计报告中继续展示 EC/kcat 等背景段落容易被误读为候选依据；本轮对有 `mutation_priority_score` 的报告压缩这些背景，不让它们进入核心展示。
- 测试中保留了旧英文标题和错误文案断言，会把报告质量问题重新锁回代码；已同步为中文契约断言。

## 2026-08-15 报告质量评测集

- 新增 `backend/tests/enzyme_report_quality_cases.json`，用数据化方式记录 7 个报告质量失败模式。
- 评测覆盖：PDB-only 身份阻断、多目标门控、候选报告固定顺序、BLAST submitted 边界、kcat 启发式边界、蛋白设计中文标题、弱 Foldseek 降级。
- 每个用例以 `required`、`forbidden` 和可选 `ordered_headings` 表达质量契约，比整段快照更稳定。
- 发现一个评测设计错误：forbidden 短语不能与“不要把 BLAST 结果写成已完成证据”这类否定说明重叠；已改为更具体的禁止项。

## 2026-08-15 报告质量契约抽象

- 新增 `backend/app/services/report_quality_contract.py`，集中定义核心章节顺序、默认禁止短语和验证函数。
- `CORE_SECTION_ORDER` 明确对应反馈 V5 的主线顺序；`DEFAULT_FORBIDDEN_PHRASES` 锁住旧英文/旧结构残留，如“结论卡片”、`Go / Watch / No-Go`、英文 fallback 文案和启发式 kcat 结论词。
- 评测集现在通过 `validate_report_quality_contract` 统一验证 required/forbidden/ordered_headings，而不是在测试里散落手写断言。
- 该 contract 当前是测试门槛，尚未接入运行时发布前阻断；后续阶段 7 可把它接到 release acceptance 或 Wiki publish QA。

## 2026-08-15 续问质量复核模式

- 新增质量投诉/复核类续问检测：不准、不准确、表格乱、格式乱、质量差、越改越差、继续深度检查等。
- 该模式必须有上一轮上下文或历史报告线索；明确新任务、确认执行、重跑工具等消息不会进入质量复核。
- 质量复核路径在 `stream_chat` 中早于普通路由和工具规划，确定性返回“报告质量复核”，不调用 LLM、不生成 plan、不执行工具。
- 回复会从历史里提取对象线索、工具状态线索和阻断/风险线索，并明确本轮不重新生成候选突变表。
- 质量复核现在优先读取结构化策略记忆中的 `plan_payload`、`evidence_state`、`artifacts`；历史文本正则只作为 fallback。
- 确认执行完成后，checkpoint 会回写 `step_results`、`final_report_preview`、`report_headings` 和 `artifacts`，质量复核可展示工具结果摘要和报告章节线索。
- 后续仍需要接入更完整的 claim gate 明细，才能逐条说明哪些声明被 allowed/downgraded/blocked。

## 2026-08-15 发布质量门槛

- `report_quality_contract` 已从测试辅助升级为发布前门槛：结构化酶工程报告在发布到 Wiki/项目文件前会校验核心章节顺序和默认禁止短语。
- 门槛只作用于结构化酶工程报告：包含 `# 酶蛋白工程分析报告`，或同时包含 `## 任务理解` 与 `## Objective Module Gate`。普通 Markdown、文献摘要和批量汇总不受该门槛阻断。
- `publish_report` 在访问 DB、上传存储、调用 Outline、创建 ProjectFile 之前先执行质量校验；违规时抛出 `ReportQualityGateError`，避免半发布状态。
- 手动项目发布和直接 Wiki collection 发布会把质量门槛错误转换为 HTTP 400，错误信息列出具体缺失章节或禁止文本。
- 自动发布路径复用服务层门槛；若报告质量不合格，会被现有自动发布异常处理捕获并跳过发布，不影响聊天主流程。

## 2026-08-15 策略确认页输入审计

- 策略确认页原先把输入证据藏在“本轮定制化依据”里，用户先看到改造套路和工具清单，容易误解为平台已经能给候选突变。
- 新增显式 `输入证据审计`：分流 PDB-only、PDB+FASTA、FASTA-only、FASTA+UniProt、PDB ID-only、UniProt-only 和 insufficient-input。
- PDB-only 会明确写出：坐标序列只能标记为 PDB-coordinate-derived，缺少独立 FASTA/UniProt 实证映射，不能把坐标顺序编号冒充成熟蛋白或 UniProt 编号。
- 新增显式 `目标拆解`：比活力、热稳定性、底物特异性、pH 和可溶表达分线解释各自的证据要求；比活力+热稳定性同时写协同点和冲突点。
- 策略输出措辞由“预期输出/最终输出候选”改为“候选输出边界”：门控通过才输出候选表，门控未通过只输出缺口、保护区和补证据路线。

## 2026-08-15 多目标工具门控

- 之前双目标只在策略文字中出现，工具层仍以单个 `objective` / `engineering_goal` 为主，容易造成“策略说双目标，执行按单目标排序”。
- `enzyme_objective_module_plan` 现在保留 `objective_modules`，为每个规范化目标输出独立模块摘要；同时聚合 `combined_required_evidence`、`combined_validation_metrics` 和合并后的 `forbidden_shortcuts`。
- `mutation_priority_score` 现在会合并 `objective_signals` 与 `objective_module_plan.objective_signals`，识别 `activity + thermostability` 后返回 `ranking_mode=activity_stability`。
- activity+thermostability 模式下，策略、预期效果和实验动作都会同时要求比活力/kcat/Km 与 Tm/热半衰期/热处理残余活性验证，避免只按 activity 文案输出。

## 2026-08-15 多目标报告展示

- 工具层返回多目标信息后，报告层仍可能只显示单个 `目标模块` 和 `目标拆解`，用户看不到每个目标的证据要求。
- `Objective Module Gate` 现在会显示 `多目标门控`、`目标模块明细`、`合并证据要求` 和 `合并验证指标`。
- 报告层会把 specific_activity 与 thermostability 的验证指标同时展示，避免双目标报告在视觉上退化成单目标 activity 或 thermostability。

## 2026-08-15 工具来源说明

- 旧版 `工具来源说明` 只把工具串成一行，用户无法判断每个工具在报告中承担什么角色。
- 报告现在输出 5 列工具来源表：工具、状态、作用、证据层级、报告用途。
- submitted 工具明确写成“后台任务已提交；当前不作为完成证据”。
- `kcat_predict` 明确写成启发式动力学背景，不能证明比活力或突变增益。
- 候选工具会显示 candidate_table_status 约束，避免用户把被身份/编号/目标门控阻断的候选当成可排单结果。

## 2026-08-15 启发式/候选工具边界收口

- `kcat_predict` 源头输出仍包含“中高催化效率 / 典型工业酶”这类定性词；即使报告契约禁止这些词，工具卡片或原始结果仍可能污染用户判断。
- `mutation_scan` 原先没有 `capability_status`、`evidence_level`、`report_boundary` 和候选表门控状态，容易被当作可直接排序的突变表来源。
- `protssn_score` 原先的单突变推荐语包含“优先改造候选”，在身份/编号/目标门控未通过时措辞过强。
- 已将三者统一降级为 proxy / DESIGN_HYPOTHESIS，并明确：只能作为启发式背景或候选表门控后的辅助评分，不能单独证明比活力、热稳定性或突变增益。
- `tool_capability_audit` 已补充 `mutation_scan` 能力条目，避免工具能力查询时把扫描工具显示为 unknown。

## 2026-08-15 第一屏摘要发现

- 旧报告即使后文有门控说明，用户第一屏仍需要滚动查找“到底能不能下单、缺什么、下一步是什么”，这会放大长报告和表格混乱问题。
- 不能新增独立顶级“第一屏结论”章节，否则会破坏反馈 V5 的固定核心章节顺序；更合适的位置是在 `## 任务理解` 下增加固定摘要字段。
- `mutation_priority_score.objective_gate.missing_evidence` 是身份阻断报告的重要缺口来源；第一版只读 `enzyme_objective_module_plan.missing_evidence` 会漏掉该路径，已补齐。

## 2026-08-15 Markdown/Wiki 表格渲染发现

- `MarkdownView` 已有表格归一化和外层横向滚动，但表格使用 `min-w-full` 会让宽表优先挤压列宽，导致长机制逻辑列变成很窄的高列。
- 更合适的策略是保留横向滚动，同时给单元格设置最小宽度、最大宽度和 `overflow-wrap:anywhere`，让宽表自然横向展开但不溢出。
- 前端 smoke 中仍保留旧报告顺序断言：要求候选表在改造策略前、要求 `Go / Watch / No-Go` 连写文本。该断言与反馈 V5 的新报告顺序不一致，已更新为策略说明先于候选表，并按表头定位候选表。

## 2026-08-15 质量复核 claim gate 发现

- 质量投诉续问此前只能展示对象、工具状态和缺口，不能逐条说明哪些科学声明被 allowed/downgraded/blocked。
- `final_report_preview` 只能作为文本线索，不适合作为 claim gate 的结构化依据；checkpoint 应保存压缩后的 claim audit。
- 复核回复需要单独展示“科学声明审计”，并明确：只有 SUPPORTED 声明可进入摘要/结论；DESIGN_HYPOTHESIS、MISSING、RUNTIME_UNVERIFIED 只能写成边界或验证需求。

## 2026-08-15 背景工具能力合同统一发现

- `annotation_bundle`、`enzyme_function`、`protein_benchmark` 这类背景工具原先容易被报告层当作确定身份或候选依据；需要在源头返回 `capability_status`、`evidence_level` 和中文 `report_boundary`。
- `protein_benchmark` 的定位应是“已确认家族后的解释器”，不是身份识别器；当 `enzyme_identity_profile` 未通过身份、编号和保护位点门控时，必须返回 blocked，并禁止输出家族特异工程建议。
- `enzyme_function` 需要区分两种证据：来自已通过身份档案的派生判断，可以标为 `IDENTITY_PROFILE_DERIVED`；仅靠模体/embedding fallback 时，只能是 `DESIGN_HYPOTHESIS`，不得写成已确认 EC。
- `annotation_bundle` 聚合本地/审校注释和预测证据，不能默认写成当轮实时 UniProt/InterPro/M-CSA/SignalP 查询；只有 evidence_source 显示 live 且 live_query_executed=true 时才能升级为实时查询证据。
- 先前出现过一次 `test_interpro_annotation_curated` 报 `no such table: pdb_structures`，复跑单测、整类和全 `test_data_tools.py` 均通过，判断为一次性测试库 schema 状态/残留，不是本轮能力字段改动导致。

## 2026-08-15 能力边界固定入口发现

- 后端已有 `tool_capability_audit`，但此前只能由 Agent 调用，用户无法在分析前主动查看平台能力边界。
- `/data` 已有数据就绪度与运维状态，最适合增加固定“能力边界”标签页；这样数据是否就绪和工具是否真实运行可以在同一区域核对。
- 能力审计原清单缺少结构搜索、编号映射、理化性质、功能预测、目标门控和 BLAST；这些恰好是报告误读风险较高的背景工具。
- 能力状态不应只分 real/proxy：结构相似检索、编号证据门控、背景基线、目标门控也需要独立状态和报告动作。
- 首页需要可发现入口；`/data?tab=capabilities` 可以直接落到能力矩阵，避免用户必须先运行工具才看到 proxy/blocked 标签。
## 2026-08-17 release acceptance 生产配置来源发现

- 平台生产配置实际跨 `docker/.env` 与 `docker/.env.aliyun.app` 两个 env 文件：基础安全/通用配置在前者，阿里云 app 部署变量在后者。
- `run_acceptance_matrix.py` 已按双 env-file 校验生产配置，因此默认 acceptance matrix 可以得到 `production_config_gate=passed`。
- `check_upgrade_readiness.py` 之前只把 `docker/.env.aliyun.app` 传给 `check_production_config.py`，导致 full release acceptance 的 `upgrade_readiness -> production.config` 与 acceptance matrix 口径不一致，并可能误报 critical。
- 修复原则：所有发布/升级入口必须复用相同的生产配置来源顺序，先基础 `docker/.env`，再 role-specific `docker/.env.aliyun.app` 覆盖。
- 当前 release readiness 结论应拆分：
  - 自动门禁：已通过，无 failed/blocked；
  - 人工发布门：维护窗口、异地备份恢复、外部存储恢复验证仍需真实输入，不能写成已完成上线。

## 2026-08-17 PDB-only SOP 发现

- HM.pdb 类问题不能只靠单测保护；实验人员需要在发布手册里看到 PDB-only 输入到底能做什么、不能做什么。
- 最重要的产品边界是“探索性结构复核”和“可排单突变候选”分层：前者可以基于 PDB 坐标窗口输出，后者必须等身份、编号、目标 assay、WT 基线和保护位点门控通过。
- 文档 gate 应跟代码 gate 绑定：`test_hm_pdb_deep_quality_gate.py` 同时检查报告输出边界和 SOP 中的关键禁止项，避免后续代码和操作标准漂移。

## 2026-08-17 acceptance/release 并发运行发现

- `run_release_acceptance.py` 内部会执行 `run_acceptance_matrix.py`；如果外部同时再并行跑一份 acceptance matrix，会让多组 pytest 同时访问同一测试数据库/测试存储上下文。
- 并发症状可能表现为 data_admin、file download、ligand preprocess 等看似无关 gate 瞬时失败；串行重跑通过时，应优先判断为测试环境竞争。
- 发布验证口径：release acceptance、acceptance matrix、后端主回归必须串行，或 CI 为每个 job 注入独立 `TEST_DATABASE_URL` 和隔离存储目录。

## 2026-08-17 用户隔离与 Wiki checkpoint gate 发现

- 多用户隔离默认 gate 应优先覆盖本地可稳定验证的安全边界：项目不可发现、项目写权限、发布权限、文件访问、工具任务和实验反馈隔离。
- 真实线上账号切换、浏览器 localStorage/session 残留和前端状态清空仍由 `frontend/tests/live-user-switch-isolation.mjs` 这类 live smoke 覆盖，不应混入默认本地矩阵。
- Wiki checkpoint 默认 gate 可以本地验证状态机：发布请求带 `conversation_id` 时不得覆盖 active checkpoint；确认执行必须优先使用服务端 active checkpoint，而不是 stale/malformed client payload。
- 真实 Outline collection、document 创建、发布后确认执行完整链路仍由 `scripts/smoke_wiki_publish_checkpoint_live.py` 覆盖，需要 live Wiki/Outline 服务。

## 2026-08-17 CI 测试库隔离发现

- 后端测试 fixture 原先硬编码 `sqlite+aiosqlite:///./test_protein_ai.db`，即使 CI job 设置环境变量也无法隔离数据库。
- 现在 `TEST_DATABASE_URL` 是测试 fixture 的第一优先级；CI 可用独立 SQLite 文件或独立数据库 URL 隔离并行 job。
- 这只解决 pytest job 之间的数据库竞争；如果未来并行跑需要文件/对象存储的 live smoke，还必须同时隔离存储目录或 bucket/prefix。

## 2026-08-17 外部基础设施验收包发现

- 外部基础设施验收包的完成标准是“每项依赖都有可执行、可复验、可回滚、可归档的标准”，不是“外部动作已经执行”。
- 需要继续保持状态语言严格：
  - 自动代码门禁通过：可以写 passed；
  - 维护窗口、恢复目标、正式域名、GPU 节点未提供：只能写 `manual_required` / `pending`；
  - 没有真实 topology/replicate artifact 时，不能写 GPU/GROMACS 能力已上线。
- 数据更新制度需要和 `/data` 最近成功更新时间保持一致；如果 manifest 仍是 demo/old，不得把周更/月更制度写成已经按期执行。

## 2026-08-17 自动门槛收口与上线边界发现

- 阶段 3/5/6/7/8 已经具备可复验 gate：策略分流、报告顺序、候选阻断、工具来源说明、质量复核 checkpoint/claim audit、能力边界固定入口都能被本地自动测试覆盖。
- 默认 acceptance matrix 当前可作为“本地自动发布门槛”口径：`failed=0 / blocked=0 / total=21`，但其中 7 个 live/外部 gate 默认 skipped，不代表真实线上链路已完成。
- 默认 release acceptance 当前可作为“代码包可进入人工发布审批”的口径：`failed=0 / blocked=0 / manual_required=3 / skipped=1 / total=9`。
- 不能把 `passed-with-manual-gates` 写成“已上线”：维护窗口演练、异地备份恢复、外部对象存储恢复验证仍缺真实输入；`backup_verify` 默认 skipped，也应在正式发布终验时显式打开。
- 发布状态表达应固定为：
  - 本地自动门禁：通过；
  - 生产部署：未执行；
  - 真实上线：等待人工发布门和外部基础设施验收。

## 2026-08-17 备份校验终验发现

- 本机没有 `pg_restore`，所以直接打开 `--include-backup-verify` 会失败；这不是备份内容失败，而是本地 PostgreSQL client 缺失。
- `verify_backup.sh --compose` 可复用 compose postgres 服务里的 `pg_restore --list`，仍然是只读校验，不执行真实恢复。
- 沙箱内访问 Docker socket 会失败，需要显式授权后运行；授权后备份 checksum 与 `pg_restore_list` 均通过。
- 当前最严格的本地发布终验口径应使用：
  - `run_release_acceptance.py --include-backup-verify --backup-verify-compose --json`
  - 结果为 `passed-with-manual-gates`，failed=0 / blocked=0 / skipped=0 / manual_required=3。
- 真实生产上线仍不能自动推进：剩余 manual gates 是组织/外部环境输入，不是代码能自行补齐的问题。

## 2026-08-17 人工门输入包发现

- 剩余 3 个 manual gate 需要一个比 remaining-backlog 更窄的最终发布输入包；否则操作员容易把 backlog 字段 `REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET` 与 release acceptance 实际字段 `OFFSITE_BACKUP_TARGET` / `OFFSITE_RESTORE_TARGET` 混用。
- 最终发布输入模板应直接对应 `run_release_acceptance.py` 参数，而不是让操作员从手册里拼命令。
- 占位符必须 fail-closed：`<fill>`、`<fill-independent-restore-target>`、`ALLOW_PRODUCTION_DRILL=false` 都不能算作可上线输入。
- 校验脚本只应做字段完整性和最终命令生成；不能联网、不能执行 live gate、不能执行 rollback/restore，也不能打印云访问密钥或数据库密码。

## 2026-08-17 人工门证据归档发现

- 只提供人工输入模板仍不够；外部演练完成后必须有统一证据模板，否则 `manual_required` 容易被口头关闭。
- 证据模板需要同时绑定三类事实：
  - release acceptance 机器输出；
  - 维护窗口/回滚/备份/恢复命令输出；
  - 审批人与 go/no-go/defer 决策。
- 外部存储恢复验证必须要求 shadow bucket/prefix 和应用只读 smoke 证据，不能把生产路径切换当作验证手段。
- 证据模板本身不是上线凭据；只有实际填写、归档并经复核后，才能把状态从“等待人工发布门”推进到生产上线决策。

## 2026-08-17 操作员包发现

- 发布材料已经足够多，继续拆散到多个手册会增加误操作风险；需要一个一页式操作员包作为入口。
- 操作员包应优先展示当前状态和边界，而不是只列命令：生产未部署、manual_required 未关闭、go/no-go 仍待证据。
- 最关键的防误操作点是顺序约束：先输入模板校验，再增强 release acceptance，再真实外部演练，再证据归档，最后才做 go/no-go/defer。
- shadow restore 是外部存储恢复验证的硬边界，必须出现在操作员包中，防止把恢复演练直接打到生产路径。

## 2026-08-17 操作员包机器清单发现

- 人读文档之外，还需要机器清单记录关键交接文件 SHA-256；否则多人传递时很难确认看到的是同一版操作员包。
- manifest 只能证明文件齐备和当前状态边界，不能升级发布状态；它必须保留 `production_deployed=false` 和 `manual_required=3`。
- manifest 生成必须保持只读，不运行 release acceptance、不访问网络、不执行 Docker/restore/rollback。

## 2026-08-17 操作员包机器清单新鲜度发现

- 仅有 manifest 生成命令时，操作员可能继续使用已过期清单；交接包文档变更后，旧 hash 不应被默认为有效。
- `--check` 应比较当前文件的存在状态、SHA-256、发布状态和安全字段，但忽略 `created_at`，这样检查不会因为时间戳变化产生假失败。
- 检查必须只读：缺失 manifest、非法 JSON 或 hash 漂移都返回非零，不自动覆盖旧文件。
- 新鲜度检查仍不能证明生产已部署；当前发布状态继续保持 `production_deployed=false`、`manual_required=3`。

## 2026-08-17 release acceptance 复验与 compose 修复发现

- `run_release_acceptance.py --include-backup-verify --backup-verify-compose` 失败时，先看备份校验里具体是 checksum 还是 compose/dockersock。
- 本次失败不是 backup 数据损坏，而是当前环境无法访问 Docker socket；在只读 `verify_backup.sh --compose` 下补做一次受控 Docker 权限执行后，checksum 与 `pg_restore --list` 都正常。
- 本地 `docker/docker-compose.yml` 的 ligand worker 原来还挂在 `upload_storage`，与 GPU compose 的 `ligand_scratch` 隔离语义不一致；这会让完整配置测试的 ligand volume 断言失败。
- 修复后，本地 compose 与 GPU compose 都以独立 ligand scratch volume 承载 ligand worker 存储，避免 chemistry runtime 与普通上传存储混用。

## 2026-08-17 交接记录清单新鲜度加固发现

- Handoff 文档是操作员最先看的交接入口之一；如果它不提示 manifest freshness check，操作员仍可能从 handoff 直接进入后续步骤而跳过 hash 复查。
- 修改 handoff 后，真实 `--check` 能检测到 manifest 文件 hash 漂移并返回非零，说明 freshness gate 对文档变更有效。
- manifest 检查不能只覆盖 hash 漂移；缺失 manifest、非法 JSON、结构错误也必须 fail-closed。

## 2026-08-17 人工门证据机器校验发现

- 输入完整不等于证据完整；三个人工门必须分别绑定终验 JSON、备份/恢复输出、独立恢复目标和 shadow storage smoke 证据。
- 外部存储恢复验证必须把 `production_path_switched=false` 作为机器校验条件，不能只依赖 Markdown 里的文字说明。
- 证据校验适合采用“记录引用，不读取外部系统”的模式：它能防止占位符和状态矛盾，同时不会把本地文件存在误判成云端恢复已完成。
- `ready-for-go` 只能由证据完整、release acceptance 全零、三个人工门通过、审批字段齐全且最终决策为 `go` 同时满足；空模板继续保持 `manual_required`。

## 2026-08-17 证据归档模板入口补齐发现

- Markdown 证据模板如果不直接暴露机器校验命令，操作员可能只补自然语言表格，导致证据记录无法被脚本复验。
- 证据归档流程应固定为：先生成/填写 JSON 证据记录，再运行只读校验，最后把人可读 Markdown 归档作为审阅材料。

## 2026-08-17 发布决策汇总与工作区清单发现

- go/no-go 需要把“输入是否齐全”“证据是否完整”“操作员包是否 current”聚合到一个可复核文件；否则操作员仍要跨多个 JSON 手动判断。
- dirty worktree 是 release acceptance 中的 manual gate，应输出 path-only 清单供人工复核，但不能输出 diff 内容或文件内容，避免泄漏代码/密钥。
- example-only 证据文件必须不能通过 `--require-go`，否则示例文件可能被误用为真实证据。

## 2026-08-17 生产配置 fail-closed 发现

- 当前 `docker/.env.aliyun.app` 仍包含 RDS/Redis 占位值；旧 production config gate 只把配置状态写在 JSON 中，未通过命令退出码阻断所有发布入口。
- `CHANGE_ME_*`、`<fill>`、`your-*` 这类占位在生产配置中应等同于 missing secret/endpoint，不应被当成“已配置”。
- go/no-go 汇总如果不聚合 production config gate，会把真实硬阻断隐藏成只剩人工门，容易误导操作员继续部署。
- 本地 Docker 栈 healthy 不等于生产配置可上线：本地 Redis 可恢复 worker 健康，但阿里云 app env 仍需要真实 RDS/Redis/OSS/LLM 配置和人工证据。

## 2026-08-17 用户提供云凭据后的配置收敛

- 用户提供的 Redis / OSS / ECS 信息足以把 app 和 GPU compose 配置渲染为 valid。
- `PUBLIC_BASE_URL` 使用 `http://120.27.108.138:4200`，与当前对外入口一致。
- Redis 更适合通过单独的 `REDIS_USERNAME` / `REDIS_PASSWORD` / `REDIS_URL` 一起配置，避免 Compose 与应用层分别拼接时出现编码差异。
- PostgreSQL 这一步仍缺真实密码，不能把 `postgresql+asyncpg://...:CHANGE_ME_RDS_PASSWORD@...` 当作已可上线配置。
- 当前仍应把生产上线状态表达为“配置部分收敛完成，但 production config gate 仍阻断，不能部署”。

## 2026-08-17 自动门通过后的上线边界

- 用户补充数据库密码候选后，生产配置 gate 已返回 `ready`，说明配置占位符/必填项不再是当前硬阻断。
- 完整 release acceptance 在授权浏览器和 Docker socket 后返回 `passed-with-manual-gates`，自动失败项为 0。
- 当前阻断已经从“配置不完整”转为“人工证据不完整”：维护窗口与生产演练授权、异地备份恢复、外部对象存储 shadow restore。
- 在三个人工门未闭合前，可以表达为“自动门已过、可进入人工发布审批”，不能表达为“已上线”或执行生产切换。
- 公网健康检查 `http://120.27.108.138:4200/nginx-health` 当前无法连接，和“尚未完成生产上线”一致。

## 2026-08-17 ECS 上线阻断与回滚发现

- 新 release 使用的托管 RDS/Redis 地址在 ECS 上可以 DNS 解析，但 TCP 端口连接超时；这会直接导致 Celery worker 无法连接 broker/result backend，Outline 无法连接 PostgreSQL。
- 旧 release 依赖的旧 RDS/Redis 公网地址从 ECS 可连通，因此旧 release 能恢复完整 Docker health 与公网 smoke。
- 当前生产恢复策略应保持 fail-closed：新 release 不继续强推；先保持旧 release 对外服务可用，再修阿里云网络/VPC/白名单或迁移到同地域托管服务后重新执行新包上线。
- 应急本机依赖方案需要拉取 Redis/MinIO/pgvector 等镜像；当前 ECS 到 Docker Hub 下载不稳定，不能把它作为即时恢复路径的唯一依赖。

## 2026-08-18 新 release 恢复根因

- 新 release 的公开入口崩掉不只是托管服务网络问题，`docker/ssl` 里的证书文件也缺失，导致 nginx 反复因 `server.crt` 不存在而退出。
- 证书目录从旧 release 复制过来后，nginx 才能稳定起来；因此 release 包本身必须把 `docker/ssl/server.crt` 与 `server.key` 纳入可部署产物，不能假设宿主机上一定已有。
- 当前更合理的上线结论是：新 release 已可用，但它依赖的云端 RDS/Redis 拓扑仍和这台 ECS 不匹配，后续需单独修复网络或改回可达端点。

## 2026-08-18 国外酶/蛋白平台深度对标发现

- 之前的调研只能说明方向，不足以支撑“比 Venus 更专业”的研发排期；必须补成竞品矩阵、模块设计和验收门槛。
- Venus 的短期优势集中在报告呈现、位点级候选解释、指定突变复核和实验反馈复盘；它更像结构解释/报告专家。
- 国外平台的更深优势在闭环：Cradle 强调多目标优化、实验数据训练、自定义模型、板设计和同一 workspace 学习；Arzeda 强调 AI + 物理设计 + DBTL + 应用/制造条件；Schrodinger/Rosetta 强在物理建模和可复现参数；PROSS2/FireProt/FuncLib/HotSpot Wizard/CAVER 强在专项蛋白或酶工程方法。
- 要反超 Venus，平台必须把酶身份、反应、催化机制、结构因果、多目标评分、实验设计和反馈学习变成结构化数据，而不是只把报告写得更长。
- 当前代码已有身份画像、SIFTS 映射、催化保护、目标门控、候选排序和报告质量 gate；关键缺口是反应层、酶学条件 baseline、催化机制映射、位点结构-功能特征表、多目标酶评分器、指定突变复核器和 DBTL 项目记忆。
- 已新增深度路线文档：`docs/designs/2026-08-18-enzyme-platform-benchmark-roadmap.md`。
