# 2026-07-10 日报

## 今日完成

### 1. 解决聊天长 Markdown 展示不全
- 修复普通聊天流式输出按空白拆分导致 Markdown 换行、表格和分隔线被破坏的问题。
- 文档型请求提高普通回复 token 预算，避免 SOP、清单、表格类内容被截断。
- 前端 Markdown table 改为单层 table + 横向滚动容器，避免嵌套 table 造成 DOM 异常。

### 2. 学习并迁移 Matvenus 输出样式
- 读取 Matvenus 公开前端资源，确认其消息布局、Markdown 字体、标题、代码块、引用和表格样式。
- 将本平台 `MarkdownView` 调整为更接近 Matvenus 的系统字体、紧凑标题、浅灰代码块、细边框表格和 relaxed 正文行高。

### 3. 读取真实 Matvenus 会话
- 通过当前 Chrome 登录态调用 Matvenus API：
  - `/session/{id}` 获取会话元数据。
  - `/session/{id}/stream-events` 获取完整会话事件。
- 会话：`SD改造+数据反馈`
- 已生成复盘稿：`matvenus-session-08b460.review.md`
- 已新增抓取脚本：`scripts/fetch_matvenus_session.py`

### 4. 沉淀 Matvenus 分析方法
- 扩展 `scripts/extract_matvenus_session.py`，支持 `stream_events` 聚合。
- 新增 `stream_events` 回归测试。
- 更新设计文档：`docs/designs/2026-07-10-matvenus-analysis-style-study.md`
- 提炼可迁移流程：
  - 输入预检
  - 全扫描候选池
  - 禁改区识别
  - 用户指定突变复核
  - 实验反馈后的机制重构
  - 周边补偿突变设计
  - 梯度实验方案输出

### 5. 将可借鉴方法接入本平台 agent
- 新增 `ENZYME_ENGINEERING_REPORT_PROTOCOL`，作为后端统一酶工程报告协议。
- 科学评审/报告合成提示词已接入该协议。
- 普通 SOP/清单类长文档回复也会复用该协议，避免只输出泛泛清单。
- 新增回归测试，防止后续改动丢失“预测-实验冲突重构”和“活力-稳定性权衡”处理逻辑。

### 6. 批量调研 Matvenus 全部历史会话
- 读取当前登录态下 14 个 Matvenus 会话。
- 批量抓取全部 `stream-events`，生成 14 个逐会话 review。
- 生成总报告：`matvenus-research/summary.md`
- 生成人工归纳文档：`docs/designs/2026-07-10-matvenus-multi-session-study.md`
- 将新增教训补入 agent 协议：
  - 残基编号映射门控
  - 组合突变上位性检查
  - 成功率/倍数/阳性率类结论强制证据溯源

### 7. Matvenus 调研高优先级产品化第一层
- 新增湿实验反馈记录能力：`/api/data/experiment-feedback` 支持提交、列表和汇总。
- 新增 `mutation_epistasis_check` 工具，组合突变前检查同一区域、近距离、重复机制和单点 No-Go 风险。
- 新增 `residue_numbering_gate` 工具，缺少编号映射或用户确认时阻断结构/文献位点投射。
- 新增 `experiment_feedback_records` 数据表和 Alembic 迁移，升级链保持单 head。
- agent 酶工程报告协议已提示优先使用湿实验反馈，并在组合/结构投射前调用对应门控。

### 8. 实验反馈 UI 第一层
- `/data` 页面新增“实验反馈”标签。
- 支持录入变体、突变、活性保留、活性倍数、ΔTm、可溶表达、SEC 单体比例、降解观察和备注。
- 提交后由后端统一生成 Go/Watch/No-Go 判断。
- 页面展示决策汇总、组合设计策略、validated single mutants 和最近反馈记录。
- 前端 API client 已补 `submit/list/summarizeExperimentFeedback`。

### 9. 组合突变上位性检查 UI 第一层
- 实验反馈页新增“运行组合上位性检查”按钮。
- 自动筛选当前用户 `Go` 且单点的 validated single mutants。
- 调用 `mutation_epistasis_check`，展示 Go/Watch/No-Go recommendation、pairwise risk、缺失证据和梯度实验计划。
- 支持人工补充结构距离、机制标签和同一区域分组证据。
- 不输入结构距离或机制标签时不会伪造结论；缺失结构距离会在结果中提示。

### 10. 当前本机可做待建项收口
- 新增 `scripts/capture_manual_screenshots.mjs` 和 `make manual-screenshots`。
- 生成真实浏览器自动截图和 manifest：
  - `docs/manuals/screenshots/manifest.json`
  - `auth-login.png`
  - `data-readiness.png`
  - `data-experiment-feedback.png`
  - `lipase-evidence-browser.png`
  - `ops-summary-alerts.png`
  - `admin-users.png`，未登录状态下最终为登录页保护截图
- 更新截图版操作手册和演练记录模板。
- 新增本机演练归档：`docs/manuals/drill-records/2026-07-10-local-screenshot-ligand-gate.md`。
- 运行 ligand 本机 smoke，确认输入 SDF 是 2D，当前缺完整工具链并安全阻断。
- 运行 ligand worker compose config，配置校验通过。

### 11. 剩余待建清单统一 readiness
- 新增 `scripts/check_remaining_backlog_readiness.py`，统一聚合剩余待建项状态。
- 新增 Makefile 入口：
  - `make remaining-backlog-readiness`
  - `make remaining-backlog-readiness-json`
- 当前总控结论：`external_required=5, ready=1`。
- 已 ready：
  - `real_deploy_data`
- 仍需外部条件：
  - `gpu_gromacs_md_live`：缺 NVIDIA/GROMACS runtime 和真实长任务环境。
  - `ligand_runtime_live`：缺 OpenBabel/RDKit、Vina、ACPYPE/AmberTools、GROMACS。
  - `oss_minio_live_e2e`：缺 live credentials 和 bucket 权限。
  - `admin_authenticated_screenshots`：缺 admin 登录态。
  - `maintenance_window_drills`：缺维护窗口、演练授权、异地备份目标和外部存储恢复目标。

### 12. 继续测试与导入器修复
- 继续执行本机非破坏性测试，覆盖后端重点回归、前端构建、readiness、验收矩阵、发布验收和后端全量。
- 发现测试运行方式问题：后端全量 pytest 与验收矩阵/发布验收不能并行跑，否则会同时 drop/create 同一个 SQLite 测试库，造成 `no such table` 或 `table already exists` 假失败。
- 串行重跑后确认验收矩阵恢复通过。
- 修复 `local_annotations` 导入器对真实数据 taxonomy 字段的兼容：
  - `kingdom -> superkingdom`
  - `class_name -> tax_class`
  - `order_name/order -> order_`
  - 过滤模型不支持字段
- 修复 `test_local_annotations_ingestor`，让它显式使用 bundled demo fixture，不再受本机 `deploy_data/annotations` 自动发现影响。
- 新增 taxonomy alias 回归断言。

## Matvenus 会话关键收获

- 外部 agent 先用 VenusX / VenusREM 做功能位点与突变扫描，再用表格输出双收益位点、单稳定性位点和单活性位点。
- 对 P338T 的处理值得迁移：当实验反馈显示“比活力升、稳定性降”时，不直接否定该位点，而是重新定义为活力-稳定性权衡问题。
- 推荐策略从“回退 P338T”变成“保留 P338T 活性收益，再在周边做稳定性补偿”。
- 多会话横向结论显示，Matvenus 的核心可借鉴流程是“输入预检 -> 禁改区 -> 候选分层 -> 实验批次 -> 湿实验反馈闭环”。
- 不能照搬的点是过强的成功率/倍数表达、残基编号映射风险、统计结论缺少即时溯源和工具参数重复失败。
- 输出格式上，表格 + 机制解释 + 梯度实验方案，比单纯排名更适合给实验人员执行。

## 验证结果

- `python3 -m py_compile scripts/fetch_matvenus_session.py scripts/extract_matvenus_session.py` 通过。
- Matvenus `/session/{id}` 抓取成功，HTTP 200。
- Matvenus `/session/{id}/stream-events` 抓取成功，HTTP 200。
- `matvenus-session-08b460.review.md` 成功生成，包含 14 条聚合消息。
- `cd backend && .venv/bin/pytest tests/test_agent_binder.py tests/test_matvenus_session_extractor.py -q` -> `26 passed`。
- `python3 scripts/batch_fetch_matvenus_sessions.py matvenus-sessions-list-page1-size50.json -o matvenus-research` -> 14 个会话全部成功。
- `python3 scripts/summarize_matvenus_research.py matvenus-research -o matvenus-research/summary.md` -> 成功生成总报告。
- `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_data_api.py -q` -> `85 passed, 81 warnings`。
- `python3 scripts/check_upgrade_readiness.py --json` -> `ready-with-manual-gates`，Alembic 单 head `9c8d7e6f5a41`，dirty worktree 作为人工发布门禁处理。
- `cd frontend && npm run build` -> 通过；3Dmol 改为本地 vendor runtime 加载，无 `eval` 或 chunk size 构建警告。
- `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `83 passed`。
- `cd backend && .venv/bin/pytest tests/test_config_validation.py::TestRequirementsFiles::test_lipase_db_readonly_service_and_api_are_wired tests/test_tools_api.py::test_mutation_epistasis_check_blocks_close_shared_mechanism_pair tests/test_tools_api.py::test_mutation_epistasis_check_allows_orthogonal_validated_pair -q` -> `3 passed`。
- `cd backend && .venv/bin/pytest tests/test_config_validation.py::TestRequirementsFiles::test_lipase_db_readonly_service_and_api_are_wired -q` -> `1 passed`。
- `FRONTEND_BASE_URL=http://127.0.0.1:4203 node scripts/capture_manual_screenshots.mjs` -> `manual_screenshots status=ok count=6`。
- `file docs/manuals/screenshots/*.png` -> 6 张 PNG，均为 `1440 x 1100`。
- `make backend-ligand-toolchain-smoke` -> `blocked_toolchain_missing`，符合本机未安装真实 ligand 工具链的预期。
- `make docker-config-ligand-worker` -> 通过。
- `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `84 passed`。
- `python3 -m py_compile scripts/check_remaining_backlog_readiness.py backend/tests/test_config_validation.py` -> 通过。
- `make remaining-backlog-readiness` -> `summary external_required`，`external_required=5, ready=1`。
- `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `85 passed`。
- `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_data_api.py -q` -> `85 passed`。
- `python3 scripts/run_acceptance_matrix.py --json` -> `passed-with-skips`。
- `python3 -m py_compile backend/app/services/annotation_dataset_service.py backend/tests/test_ingestors.py` -> 通过。
- `cd backend && .venv/bin/pytest tests/test_ingestors.py -q` -> `11 passed`。
- `cd backend && .venv/bin/pytest -q` -> `474 passed, 299 warnings`。
- `python3 scripts/run_release_acceptance.py --json` -> `passed-with-skips`。
- `git diff --check` -> 通过。

## 风险与边界

- Matvenus 会话中的突变收益、距离和成功率属于外部模型/工具预测，不能作为已验证实验事实。
- Chrome 登录态抓取脚本只适用于本机当前登录状态；不打印 token/cookie，也不持久化凭据。
- 真实实验设计仍需结合 PDB 编号、活性中心、保守性、SASA、SEC/Tm/活性实验共同验证。
- 实验反馈 UI 已能串联组合突变检查，但尚未与项目详情页、编号 mapping 状态和结构距离/机制标签自动串联。
- 后台截图未提供 admin 登录态，当前只能归档登录保护页，不能声称已完成管理员后台真实截图。
- ligand smoke 当前是安全阻断，不代表真实 docking/topology runtime 已可用。
- 剩余待建总控为只读 readiness，不会替代真实 GPU/GROMACS、ligand worker、OSS/MinIO live、admin 登录态和维护窗口演练。
- 后端 pytest、验收矩阵和发布验收需要串行执行，除非后续为每个进程隔离测试数据库。

## 明日建议

- 在项目页接入实验反馈，记录 `project_id` 并按项目汇总。
- 在结构位点投射相关入口展示 `residue_numbering_gate` 的阻断/放行状态。
- 将组合检查中的结构距离、same-region groups 和 mechanism tags 从结构 viewer 自动带入，并考虑保存为项目级证据。
- 使用 admin 测试账号重新生成后台截图；在维护窗口执行真实回滚/异地备份/外部存储恢复演练后补归档。
- 在具备工具链的容器或服务器执行 `ligand-runtime-check --require-live`。
- 在聊天输出中增加结构化 `step/report/tool_call/evidence` 事件，减少后续复盘成本。
- 针对 388 aa 酶生成本平台自己的 SOP 版实验清单和突变体登记表。
