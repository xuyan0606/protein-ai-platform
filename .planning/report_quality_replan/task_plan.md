# 酶工程报告质量重构计划

## 目标

把平台从“工具堆叠式报告”改成“证据驱动的酶工程分析系统”。核心要求：

- 策略先判断输入对象能支持什么分析，不能先套模板。
- 报告只输出证据能支撑的结论，不能把弱证据、启发式结果或后台未完成任务写成事实。
- 比活力、热稳定性、底物特异性、pH、表达等目标必须拆开处理，不能用一套通用突变表覆盖。
- 报告语言统一中文，字段名、标题、表格和结论对实验人员可读。
- 没有身份、编号、底物、活性中心证据时，明确阻断具体突变建议。

## 当前状态

- 状态：阶段 1-22 已完成本地代码/文档/自动 gate 收口；增强 release acceptance 已纳入 compose 备份校验；生产配置 gate 已 fail-closed 拦截 `CHANGE_ME` / `<fill>` 占位；阿里云 app/GPU 配置已通过生产配置校验；当前新 release 已部署并恢复公网健康，但人工门输入和外部证据仍未闭合
- 代码执行：仅本地修改，未部署
- 部署：未部署
- 已知风险：工作区存在大量既有未提交变更；正式域名/HTTPS、GPU/GROMACS 节点和真实维护窗口演练依赖外部基础设施，不能用本地代码测试冒充已完成。

## 阶段 1：质量问题审计

状态：完成

任务：

- 收集 5-10 个失败案例，包括 PDB、FASTA、无序列、单目标、多目标和续问场景。
- 对每个案例标注：用户目标、输入证据、实际报告问题、应该阻断还是应该输出候选。
- 形成失败类型清单：策略错误、工具错误、证据门控错误、报告格式错误、上下文续问错误、前端展示错误。

验收：

- 每个失败类型至少有一个可复现输入。
- 每个失败案例有“期望输出第一屏”和“禁止输出内容”。

## 阶段 2：报告质量契约

状态：完成

任务：

- 定义统一报告结构：第一屏结论、输入证据审计、身份/编号状态、目标拆解、可分析边界、候选表或阻断原因、实验路线。
- 定义候选表放行条件：身份确认、编号确认、催化/关键位点确认、目标 assay 证据满足。
- 定义阻断报告格式：不能只写 No-Go，要告诉用户缺什么、为什么缺、下一步怎么补。
- 定义语言规范：中文标题、中文字段、少量必要英文缩写保留并解释。
- 定义报告顺序契约：任务理解 → 输入与结构证据 → 结构同源与编号映射 → 改造策略及说明 → Physicochemical Properties → Enzyme Foundation Profile → 保护位点 → Objective Module Gate → 突变位点探索清单 → 位点突变逻辑 / 风险 / 实验动作 → 探索性验证建议。
- 定义工具来源解释：用户追问“通过哪些工具得到结果”时，必须列出使用过的工具、每个工具的作用、哪些工具只是背景、哪些工具被门控阻断。

验收：

- 任一报告都能回答：对象是谁、证据来自哪里、能否给突变、为什么、下一步做什么。
- 报告中没有无解释的英文模板段落。

## 阶段 3：策略生成重构

状态：完成

任务：

- [x] 策略确认先做输入审计，而不是先承诺输出候选突变。
- [x] 多目标必须拆解：例如“比活力 + 热稳定性”要同时列出协同点和冲突点。
- [x] 策略必须给出门控条件：通过时输出什么，未通过时输出什么。
- [x] PDB-only、FASTA-only、PDB+FASTA、带 UniProt、带底物/实验条件五类输入分流。

验收：

- [x] 策略文本不再出现“最终必须输出候选位点”这类无条件承诺。
- [x] 策略和后续报告不会互相矛盾。

## 阶段 4：证据与工具执行重构

状态：完成

任务：

- 区分输入质控工具、身份工具、目标工具、候选工具、解释工具。
- 未完成的异步任务不得进入结论层。
- 启发式工具必须带能力标签，报告中只能作为背景，不得作为事实或排序核心。
- mutation_priority_score、mutation_scan、protssn_score 等候选工具必须受统一候选表门控控制。

验收：

- 身份/编号未过时，候选工具不输出表格。
- kcat 启发式估算不会出现在摘要结论或候选依据里。

## 阶段 5：报告生成器重构

状态：完成

任务：

- [x] 从“按工具结果拼章节”改成“按科学问题拼报告”。
- [x] 按文档指定顺序输出核心章节，避免把突变位点和逻辑放到中间。
- [x] 第一屏优先写：当前是否可下单、主要证据、主要缺口、下一步。
- [x] 候选表分三类：可排单、探索性复核、禁止输出。
- [x] 所有表格列数控制在 5-7 列，长逻辑拆到位点详情。
- [x] 报告增加“本次使用工具”或“结果来源工具”小节，专门回答用户对分析链路的追问。

验收：

- [x] PDB-only 且身份不明时：输出结构审计和证据缺口，不输出突变候选。
- [x] 身份明确且目标证据满足时：输出可执行候选表和实验批次。
- [x] 全文中文为主，格式稳定可发布到 Wiki。
- [x] 用户追问分析来源时，能在同一报告里清晰定位工具链，不再出现“无法识别”或默认流程吞没问题。

## 阶段 6：上下文与续问重构

状态：完成

任务：

- [x] 续问必须读取上一轮真实结果状态，不重新套策略。
- [x] 用户指出“报告不准/格式乱/继续深度检查”时进入质量复核模式，而不是继续生成新候选。
- [x] 记录当前对象、已完成工具、未完成任务、阻断原因和用户反馈。

验收：

- [x] 续问能明确引用上一轮的对象和失败点。
- [x] 不会把旧报告中的错误结论继续复述。

## 阶段 7：评测与发布门槛

状态：完成

任务：

- [x] 建立报告质量评测集。
- [x] 增加单测、快照测试和人工审查清单。
- [x] 上线前跑失败案例回归。

验收：

- [x] 每次发布必须通过：策略一致性、候选门控、中文报告格式、异步任务处理、续问上下文五类测试。

## 阶段 8：能力边界固定入口

状态：完成

任务：

- [x] 在后端提供只读工具能力审计 API。
- [x] 在 `/data` 增加“能力边界”固定标签页，展示 live、proxy、blocked、runtime-gated 等状态。
- [x] 明确 AlphaFold2、RFdiffusion、ProteinMPNN、DiffDock、kcat、ProtSSN、MD/配体工具的科学边界和最低产物要求。
- [x] 首页增加可发现入口，避免用户只能在工具卡片或报告尾部看到能力状态。

验收：

- [x] 用户无需运行分析即可查看当前平台能力边界。
- [x] proxy 工具不能以官方模型/真实运行状态展示。
- [x] blocked/runtime-gated 工具显示缺失条件和升级所需产物。

## 阶段 9：HM.pdb 标准样板与发布 Gate

状态：完成

任务：

- [x] 将 HM.pdb PDB-only deep 分析固化为发布必跑回归。
- [x] 新增《PDB-only 比活力/热稳定性分析 SOP》，明确输入审计、身份门控、编号门控、候选边界和实验闭环。
- [x] smoke 必须验证：弱 Foldseek 不确认身份、坐标顺序推断不冒充 SIFTS、submitted BLAST 不进入结论、启发式 kcat 不支持比活力、身份阻断时不输出候选表。

验收：

- [x] 发布验收矩阵包含 HM.pdb deep gate。
- [x] SOP 与代码门控和报告顺序一致。

## 阶段 10：Release Blocker 与运维约束

状态：完成

任务：

- [x] 将“报告级工具缺少 capability audit 条目”设为默认 acceptance matrix gate。
- [x] 固定默认 release acceptance 串行运行，并确认本地默认矩阵 `failed=0 / blocked=0`。
- [x] 将 HM deep smoke 纳入发布固定门槛。
- [x] 将多用户隔离、Wiki checkpoint 纳入固定发布门槛。
- [x] CI 并行必须使用独立 `TEST_DATABASE_URL`。

验收：

- [x] 任一报告级工具能力状态为 unknown 时，发布验收失败。
- [x] 默认 `run_release_acceptance.py --json` 无 failed/blocked，仅剩人工发布门。
- [x] 默认 acceptance matrix 覆盖用户隔离和 Wiki checkpoint 状态机。
- [x] SQLite 共用测试库不会被并行 release job 同时使用。

## 阶段 11：外部基础设施验收包

状态：完成

任务：

- [x] 正式域名 + HTTPS + OIDC callback 验收清单。
- [x] GPU/GROMACS 节点从驱动/CUDA到 topology live gate、mutant prepare、replicate、batch summary 的分阶段清单。
- [x] 维护窗口真实备份/回滚/恢复演练归档模板。
- [x] 数据更新制度：PDB 周更、AlphaFold/SIFTS/annotations 月更、Foldseek 月更或季度更新，并在 `/data` 显示最近成功更新时间。

验收：

- [x] 每项外部依赖都有负责人、输入、命令/操作、通过标准、失败回滚和证据归档位置。
- [x] 未实际完成的外部动作保持 blocked/pending，不得写成已上线。

## 阶段 12：发布交接终验

状态：完成

任务：

- [x] 显式运行带备份校验的 release acceptance。
- [x] 处理本机缺少 `pg_restore` 的环境差异，改用 compose postgres 执行只读 `pg_restore --list`。
- [x] 形成发布交接记录，写清楚自动门槛、人工门、备份校验方式和上线前执行口径。

验收：

- [x] `run_release_acceptance.py --include-backup-verify --backup-verify-compose --json` 返回 failed=0 / blocked=0 / skipped=0。
- [x] 交接文档不把 `manual_required` 写成已上线。

## 阶段 13：人工发布门输入包

状态：完成

任务：

- [x] 新增最终人工门 JSON 输入模板，覆盖维护窗口、生产演练授权、异地备份恢复和外部存储恢复验证。
- [x] 新增只读校验脚本，空模板 fail-closed，完整输入时生成最终 release acceptance 命令。
- [x] 增加 Makefile 入口和产品化手册/交接记录链接，避免人工门输入散落在口头说明中。

验收：

- [x] 校验脚本不会联网、不会部署、不会执行恢复或回滚。
- [x] 测试锁定模板、脚本、Makefile 和手册链接。
- [x] 模板占位值不会被误判为可上线输入。

## 阶段 14：人工门证据归档模板

状态：完成

任务：

- [x] 新增维护窗口、异地备份恢复、外部存储恢复验证的统一证据归档模板。
- [x] 在产品化验收手册和发布交接记录中链接证据模板。
- [x] 测试锁定证据模板必须包含三个人工门、release acceptance JSON、go/no-go 决策。

验收：

- [x] 人工门完成前不能只凭口头结论写成已上线。
- [x] 证据模板要求记录输出路径、checksum、shadow restore、应用只读 smoke 和签署信息。

## 阶段 15：发布操作员包

状态：完成

任务：

- [x] 新增一页式发布操作员包，串联交接记录、输入模板、校验命令、证据模板和 go/no-go 条件。
- [x] 在产品化验收手册和发布交接记录中链接操作员包。
- [x] 测试锁定操作员包必须保留 manual_required 边界、shadow restore 要求和 go/no-go/defer 决策。

验收：

- [x] 操作员无需从多份文档中拼接下一步命令。
- [x] 操作员包明确生产未部署，不能越过人工门和证据归档。

## 阶段 16：操作员包机器清单

状态：完成

任务：

- [x] 新增只读 manifest 生成脚本，记录操作员包关键文件、SHA-256、发布状态和下一步决策边界。
- [x] 新增 Makefile 入口，交接前一条命令生成机器清单。
- [x] 测试锁定 manifest 不联网、不执行破坏动作、不打印密钥，并确认关键文件齐备。

验收：

- [x] `make release-operator-packet-manifest` 返回 `ready-for-operator-review`。
- [x] manifest 记录 `production_deployed=false`、`manual_required=3`，不把待人工门状态写成已上线。

## 阶段 17：操作员包机器清单新鲜度

状态：完成

任务：

- [x] 为 manifest 生成脚本增加只读 `--check`，比较当前关键文件 hash、存在状态和发布边界。
- [x] 增加 Makefile 检查入口，并在操作员包和产品化验收手册中固定交接前检查命令。
- [x] 测试清单 current、缺失/过期 fail-closed 和手册入口。

验收：

- [x] `python3 scripts/build_release_operator_packet_manifest.py --check --json` 返回 `current`。
- [x] `make release-operator-packet-manifest-check` 返回成功且不改写 manifest。
- [x] 篡改 manifest hash 时检查返回非零，并报告 `stale-or-missing`。

## 阶段 18：交接记录清单新鲜度加固

状态：完成

任务：

- [x] 在发布交接记录中补充 `make release-operator-packet-manifest-check`，让 handoff、操作员包和产品化手册的交接口径一致。
- [x] 增强 manifest 单测，覆盖缺失 manifest 和非法 JSON 的 fail-closed 路径。
- [x] 修改 handoff 后先确认真实 manifest stale，再重新生成并复查 current。

验收：

- [x] `make release-operator-packet-manifest-check` 返回 `current`。
- [x] `backend/tests/test_config_validation.py` 返回 103 passed。
- [x] manifest 缺失、非法 JSON、hash 漂移都不会被误判为 current。

## 阶段 19：人工门证据机器校验

状态：完成

任务：

- [x] 新增机器可读证据记录模板，覆盖发布包、终验 JSON、三个人工门证据、shadow restore 和签署决策。
- [x] 新增只读证据校验脚本，空模板 fail-closed，完整且 `go` 的证据记录才返回 `ready-for-go`。
- [x] 增加 Makefile 入口、发布手册链接和操作员包 manifest 文件清单。
- [x] 测试 `production_path_switched=false`、布尔决策字段和禁止打印密钥/执行外部动作边界。

验收：

- [x] `make release-manual-gate-evidence-validate` 默认返回 `manual_required`，不执行网络、恢复或生产切换。
- [x] 完整临时证据记录测试返回 `ready-for-go`。
- [x] `backend/tests/test_config_validation.py` 返回 104 passed。
- [x] 操作员包 manifest 返回 `file_count=9`、`current`。

## 阶段 20：证据归档 Markdown 模板入口补齐

状态：完成

任务：

- [x] 在 `release-manual-gate-evidence-template.md` 顶部加入机器可读证据模板生成和校验命令。
- [x] 测试锁定 Markdown 证据模板必须包含 `release-manual-gate-evidence-template` 和 `release-manual-gate-evidence-validate`。
- [x] 重新生成操作员包 manifest，保持证据模板 hash 最新。

验收：

- [x] 证据 Markdown 模板不会绕过 JSON 机器校验。
- [x] 操作员包 manifest 返回 `file_count=9`、`current`。

## 阶段 21：发布决策汇总与工作区清单

状态：完成

任务：

- [x] 新增只读 go/no-go 汇总脚本，聚合人工输入、人工证据和操作员包 manifest。
- [x] 新增只读 dirty worktree 路径清单脚本，只记录路径和 git status，不输出 diff 内容。
- [x] 新增人工证据 JSON schema 和 example-only 示例，示例不能被 `--require-go` 误判通过。
- [x] 将 go/no-go 汇总、worktree 清单、schema/example 纳入 Makefile、操作员文档、测试和 manifest。

验收：

- [x] `make release-go-no-go-summary` 默认返回 `manual_required`。
- [x] `make release-worktree-manifest` 返回 dirty worktree 路径清单且不打印文件内容。
- [x] 操作员包 manifest 返回 `file_count=13`、`current`。
- [x] 新增本地工具不执行网络、部署、恢复或 rollback。

## 阶段 22：生产配置阻断纳入最终发布决策

状态：完成

任务：

- [x] 生产配置校验新增占位符检测，拦截 `CHANGE_ME`、`change-me`、`<fill>`、`your-*` 等生产占位。
- [x] acceptance matrix、nightly live gates 和 Makefile production config gate 统一加 `--require-production-safe`，critical 配置不再只报告而是阻断。
- [x] go/no-go 汇总器纳入只读 production config gate，默认检查 `docker/.env` 和 `docker/.env.aliyun.app`。
- [x] 测试锁定占位生产 env 会让 `production_config_gate` 出现在 `blocking_items`。

验收：

- [x] `make config-test` 返回 `106 passed`。
- [x] 当前 `make release-go-no-go-summary` 返回 `manual_required`，blocking_items 仅剩 `manual_gate_inputs`、`manual_gate_evidence`。
- [x] 本地 Docker app 栈 Redis 已恢复，backend/frontend/nginx/postgres/minio/outline/worker/md-worker/ligand-worker 均 healthy。
- [x] 生产部署仍未执行；当前阻断是维护窗口/生产演练授权、异地备份恢复、外部对象存储 shadow restore 三类人工门输入和证据缺失。

## 禁止事项

- 禁止再用弱 Foldseek 命中直接确认酶身份。
- 禁止把 inferred SIFTS 当作真实 UniProt 映射。
- 禁止把启发式 kcat 当作比活力证据。
- 禁止在身份/编号未过时输出通用突变表。
- 禁止中英文模板混排。
- 禁止为了“看起来完整”堆工具章节。

## 阶段 23：酶平台专业化竞品调研与反超路线

状态：完成

任务：

- [x] 对比 Venus 的实际优势：报告呈现、位点级解释、指定突变复核、实验反馈复盘。
- [x] 核对国外平台和工具链：Cradle、Arzeda、Schrodinger、AlphaFold、PROSS2、FireProt、M-CSA、BRENDA、SABIO-RK、Rhea、CAVER 等。
- [x] 形成从“报告系统”升级为“酶工程决策系统”的模块路线。
- [x] 明确当前代码已有能力和缺口：反应层、酶学条件 baseline、催化机制映射、位点结构-功能特征表、多目标评分器、指定突变复核、DBTL 项目记忆。
- [x] 新增路线文档：`docs/designs/2026-08-18-enzyme-platform-benchmark-roadmap.md`。

验收：

- [x] 不是泛泛竞品名单，而是能指导 P0-P3 开发优先级。
- [x] 每个反超方向都绑定酶工程证据层或实验闭环。
