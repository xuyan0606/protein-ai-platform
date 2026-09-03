# 任务计划：全项目低侵入稳态修复与可插拔治理

## 目标
在不破坏现有能力的前提下，系统性修复项目中的认证、会话、代理和扩展边界问题，并为后续可插拔功能集成建立稳定结构。

## 当前阶段
阶段 117（in_progress）

## 各阶段

### 阶段 1：项目理解与风险发现
- [x] 读取项目结构与关键模块
- [x] 明确当前已修复项、未闭环项和高风险点
- [x] 将发现记录到 findings.md
- **状态：** complete

### 阶段 2：架构边界与可插拔面审计
- [x] 审计后端 API、认证、代理、工具注册边界
- [x] 审计前端会话、鉴权、路由、错误恢复边界
- [x] 确定低侵入修复策略与扩展点
- **状态：** complete

### 阶段 3：实现稳态修复
- [x] 增量修复确认问题
- [x] 为关键路径增加容错与兼容层
- [x] 保持后续功能接入方式清晰可扩展
- **状态：** complete

### 阶段 4：测试与回归验证
- [x] 运行针对性静态检查和服务验证
- [x] 验证核心登录、会话、对话、wiki 访问链路
- [x] 记录回归结果与残余风险
- [x] 将占位 `gromacs_md` 切换为真实 GROMACS 管线接口，并验证其在无 `gmx` 运行时时明确失败而非伪造结果
- [x] 修复 OIDC 入口、`pa_token` cookie 会话恢复、fallback planner 和工具错误文案回归
- [x] 完成前端生产构建与后端全量单测回归
- **状态：** complete

### 阶段 5：交付与后续集成建议
- [x] 输出已完成修复与验证结果
- [x] 输出可插拔扩展建议
- [x] 标注仍建议后续治理的点
- [x] 制定真实分子动力学（MD）基建落地方案：将 `gromacs_md` 从占位模拟切换为真实异步流水线，补齐 PDB 入参、Celery/Worker 长任务、MinIO 工件存储、轨迹与指标可视化链路
- [x] 为 backend live runtime 安装 GROMACS，并验证真实前处理链可执行
- [x] 为 `/pdb` 页面接入异步真实 MD 任务提交与状态轮询最小闭环
- [x] 更新 README、frontend README 与工具/数据库扩展路线图，沉淀当前真实能力边界
- **状态：** complete

### 阶段 6：后续治理全面启动
- [x] 真实 MD artifact manifest：将轨迹、日志、`.xvg`、`.csv`、参数模板分组返回，便于前端下载和后续复现实验
- [x] 真实 MD 长任务治理：补齐任务终态收敛、取消结果确认、资源队列、并发限制和超时策略
- [x] 匿名浏览器噪音清理（第一层）：登录页仅在存在本地凭据或 OIDC next 时恢复会话；顶层 `/wiki/*` 文档导航先回 SPA 鉴权，避免匿名直打 Outline
- [x] 高质量本地数据灌库（第一层）：`local_annotations` 支持目录化 InterPro / M-CSA / SignalP fixture 合并输入，且 `/pdb` 页面可直接对主链序列触发 `annotation_bundle`
- [x] 结构位点映射与搜索（第一层）：新增 `residue_mapping_sifts` 与 `structure_search_foldseek` 工具合同，补齐 PDB 专用 API，并在 `/pdb` 页面提供直接触发、结果展示与“curated 优先 / inferred 兜底”的保护位点、signal peptide、InterPro/Pfam 区段 3D 高亮入口
- [x] 非浏览器 live smoke：补 `frontend/tests/http-smoke.mjs` 并验证 `/login`、`/home`、`/data`、`/api/health`、`/wiki/home` 顶层/嵌入分流
- [x] 结构检索后端第二层接线：`structure_search_foldseek` 支持远端 `FOLDSEEK_API_URL` 与本地 `FOLDSEEK_BINARY + DB path` 双入口
- [x] 真实 residue mapping 第二层接线：`residue_mapping_sifts` 支持本地 `SIFTS_MAPPING_PATH`，命中时优先返回 JSON/CSV/TSV 映射文件
- [x] 结构 overlay UX 第二层：`/pdb` 结构卡支持 curated / inferred / signal / domain 图例、图层开关和可见计数，便于解释叠加结果
- [x] 真实浏览器控制台复核：主机权限下 Playwright `public-smoke` / `live-smoke` 均通过
- [x] 真实结构数据 smoke harness：新增 `backend/scripts/smoke_structure_data.py`，配置真实 Foldseek/SIFTS 数据后可一键验证
- [x] 结构 smoke demo 基线：`smoke_structure_data.py` 支持 `SIFTS_SMOKE_USE_DEMO=1` 与 `FOLDSEEK_SMOKE_USE_DEMO=1`，可在无外部数据目录时验证 bundled mapping 文件源与 Foldseek `summary_only` 降级路径
- [x] 结构 smoke demo 自动回归：`test_config_validation.py` 现会实际执行 demo smoke，并断言 `PASS sifts` / `PASS foldseek-demo`
- [x] 结构 smoke 就绪度脚本：`structure_smoke_readiness.py` 可直接判断当前机器是 `demo-ready` 还是 `live-ready`
- [x] 真实注释导出兼容层：`local_annotations` 现支持 `base/interpro/mcsa/signalp` 的 JSON/CSV/TSV 输入
- [x] 部署数据目录产品化（第一层）：统一 `deploy_data` 目录约定、Docker 挂载与 autodiscovery，让真实 `SIFTS/Foldseek/annotations/smoke query` 可按标准路径接入
- [x] 阿里云托管部署准备（第一层）：补齐 OSS `secure/region` 配置、新增 `aliyun app/gpu` 分角色 compose 与 env 模板、重写 `deploy-aliyun.sh` 为 `App-01/App-02/GPU-01` 方案
- [x] 产品化待建清单全面启动（第一层）：新增数据就绪度 API 与 `/data` 可视化入口，补 MD 结构化解释，补工具任务审计摘要
- [x] 产品化待建清单全面启动（第二层）：新增 deploy_data 更新记录、MD 协议模板 API、运维摘要 API，并在 `/data` 增加更新记录与监控入口
- [x] MD 参数模板前端接入：`/pdb` 页面支持选择 MD 协议模板，提交前通过后端 resolve 生成真实 GROMACS 参数，并在结果参数中追溯 `protocol_id`
- [x] MD 结果解释层深化：补证据等级、结论摘要、质量门控和复核建议，并在 MD 报告页展示
- [x] 任务审计持久化第一层：新增 `tool_task_audits` 数据库表、提交/轮询/取消落库、当前用户审计列表和详情接口
- [x] 监控告警第一层：`/api/ops/summary` 增加健康检查、告警列表和前端监控页展示
- [x] 权限角色第一层：用户新增 `role`，鉴权返回角色，补 `require_admin` 和管理员任务审计查询接口
- [x] 封装交付第一层：新增只读环境预检脚本、Makefile 入口和 README 验证说明
- [x] 管理后台第一层：新增管理员用户列表、角色更新、审计 CSV 导出和 `/admin` 前端入口
- [x] 部署包第一层：新增白名单式源码部署包生成脚本、Makefile 入口、checksum 和 README 说明
- [x] 部署初始化第一层：新增本地/阿里云 env 初始化向导，默认不覆盖现有配置并支持 dry-run
- [x] 备份恢复第一层：修复 PostgreSQL dump/restore 格式不匹配，新增 `.dump + sha256`、dry-run 和恢复确认
- [x] 升级编排第一层：新增升级 readiness、local/aliyun dry-run 和本地升级编排脚本
- [x] 发布版本第一层：新增根 `VERSION=0.1.0`，后端 health/FastAPI 与前端 package 版本统一
- [x] 产品化文档第一层：新增管理员、研发用户、数据导入和故障处理手册
- [x] 备份恢复演练第一层：新增备份文件校验和临时库恢复演练脚本，默认不触碰主库
- [x] 真实备份恢复演练第一层：生成真实 PostgreSQL 备份、校验 checksum/pg_restore list，并恢复到临时库验证后清理
- [x] 真实数据层：导入并定期更新真实 `annotations / SIFTS / Foldseek DB / PDB / AlphaFold`
- [x] 真实数据层第一批：补 `deploy_data/live_manifest.json` 定期更新总控、plan-only 安全预览、更新记录 manifest 和 Makefile/手册入口
- [x] 真实数据层第二批本机可做部分：增强 manifest-aware plan-only 检查、缺失项/下一步动作和版本比对输出
- [x] 科为博 lipase 数据库接入层：将 `/Users/xuyan/lipase-db/lipase.db` 作为脂肪酶文献证据、突变体、底物、指标、gap 和后续用户调用数据的项目数据库源接入平台
- [x] 科为博 lipase 数据库接入层第一步：只读 introspection、schema 映射、数据质量报告、备份/快照策略和 ingestion dry-run
- [x] 科为博 lipase 数据库接入层第二步：新增后端 service/API，将 paper/variant/mutation/claim/metric/substrate/gap 暴露到 `/data` 与工具调用上下文
- [x] 科为博 lipase 数据库接入层第三步第一批：将 lipase 证据接入突变推荐、PDB 安全展示入口、MD ranking 解释和用户调用审计摘要
- [x] 科为博 lipase 数据库接入层第三步第二批：在 PDB 页面增加用户确认编号体系后的结构位点映射与 viewer 高亮
- [x] 科为博 lipase 数据库接入层第四步第一层：平台侧 curation queue 支持新增文献、实验记录、用户调用反馈和人工审核状态
- [x] 科为博 lipase 数据库接入层第四步第二层：将 accepted curation records 纳入受控导入批次和人工审核发布流程
- [x] MD 科学参数层第二层：补力场/水模型 rationale、系统准备检查、cutoff/constraint/replicate policy 和协议 review
- [x] MD 结果解释层第二层：补能量项、氢键项、XVG/EDR 缺失证据判读和前端展示
- [x] MD 科学参数层第三层第一步：补 ligand/cofactor/protonation/disulfide 结构预处理自动检查，并在 MD 结果解释和前端报告中展示
- [x] MD 科学参数层第三层第二步：补 WT/突变体重复模拟一致性评估合同、解释层门控和前端报告展示
- [x] MD 科学参数层第四层第一批：补多 replicate 运行计划、plan-only 合同、批量 replicate 汇总和前端 ranking 门控展示
- [ ] MD 科学参数层第四层第二批：继续补真实自动多 replicate 任务提交、突变体结构生成/拓扑处理和真实长任务批量汇总
- [x] MD 科学参数层第四层第二批第一步：补受控真实多 replicate 批量提交 API、dry-run/确认令牌、WT 提交、缺失突变体结构 blocked 合同和任务审计落库
- [x] MD 科学参数层第四层第二批第二步：补已完成 replicate 任务审计批量汇总 API、真实指标提取、pending/failed/缺指标 ranking gate 和跨用户隔离测试
- [x] MD 科学参数层第四层第二批第三步：补保守 point-mutant PDB 准备 API、对象存储输出、链歧义/源残基不匹配阻断和拓扑验证边界
- [x] MD 科学参数层第四层第二批第四步：补真实 `pdb2gmx` 拓扑预检 API、GROMACS 缺失/force field/water model 阻断和 warning taxonomy 输出
- [x] MD 科学参数层第四层第二批第五步：打通 mutant prepare 可选拓扑预检结果、`mutant_input.topology_validation` 和 replicate submit 严格拓扑门控
- [x] MD 科学参数层第四层第二批第六步：补 host 侧 MD topology smoke/live gate 脚本和 Makefile 入口，明确当前机器 GROMACS runtime unavailable
- [ ] MD 科学参数层第四层第二批第七步：等待用户提供阿里云 NVIDIA GPU/GROMACS 服务器后，执行真实 topology live gate、真实 WT/mutant replicate 长任务和真实 batch ranking report
- [ ] 底物/配体预处理与对接层：接入真实 2D SDF -> 3D 构象、PDBQT、Vina 对接、ACPYPE/Antechamber 小分子拓扑和 GROMACS 复合物 MD 前置流水线
- [x] 底物/配体预处理与对接层第一步：确认 `Structure2D_COMPOUND_CID_5478883.sdf` 为 2D SDF，补只读 ligand toolchain smoke/live gate、Makefile 入口和 IT 流程手册
- [ ] 底物/配体预处理与对接层第二步：安装/容器化 OpenBabel 或 RDKit、AutoDock Vina、ACPYPE/AmberTools，并把 2D->3D/PDBQT/对接/拓扑拆成可审计异步任务
- [x] 底物/配体预处理与对接层第二步第一批：新增 `ligand_preprocess` 异步工具、`ligand_cpu` 队列、SDF 脱敏审计、真实 OpenBabel 3D 生成入口和工具缺失时的受控 blocked 合同
- [x] 底物/配体预处理与对接层第二步第一批增强：补 `prepare_pdbqt / vina_docking / ligand_topology` 参数 schema、缺参/缺 runtime blocked 合同、API 调用测试、artifact owner 权限测试和 `/pdb` Ligand Preflight 状态卡
- [x] 底物/配体预处理与对接层第二步第一批容器化准备：补 ligand worker Docker/compose runtime boundary、scratch volume 和 `ligand-runtime-check`
- [x] 底物/配体预处理与对接层第二步第二批第一层：在 `protein-ai-ligand-worker:local` 中真实打通 2D SDF -> 3D SDF -> PDBQT -> Vina docking，并补畸形 SDF、Vina box、超时和 antechamber-only 拓扑门控回归
- [x] 底物/配体预处理与对接层第二步第二批：在容器/服务器中安装 OpenBabel/RDKit/Vina/ACPYPE/AmberTools 后，打开真实 PDBQT、Vina docking 和 ligand topology 阶段
- [x] MD 分析解析层第一步：补真实 GROMACS energy/hbond XVG 解析、CSV 导出和保守缺失证据门控
- [x] MD 分析解析层第二步：补 protein-solvent hbond 独立解析尝试、能量项 legend 兼容和 topology warning 结构化解析
- [x] MD 分析解析层第三步第一批：补 named group selection、energy term selection 合同和 topology warning 分类词表
- [x] MD 分析解析层第三步第二批：继续用真实 GROMACS 多体系输出校准 selection fallback、能量项别名和 warning 分类词表
- [x] 任务审计层第二层：补耗时统计、慢任务标记、失败分类和 CSV 导出字段
- [x] 任务审计层第三层：补运行环境版本、审计摘要统计、失败分类趋势、最近失败列表和 CSV runtime 字段
- [x] 任务审计层第四层：补按时间范围/工具/状态/队列/失败分类/失败-only/慢任务-only 筛选、失败日期趋势和只读告警联动摘要
- [x] 用户权限层第一层：项目级 ACL，支持 owner/editor/viewer、成员管理、列表/详情/序列/批量任务权限边界
- [x] 用户权限层第二层：文件、Wiki、发布、报告生成、会话绑定接口接入项目 ACL
- [x] 用户权限层第三层：聊天新建/绑定项目接入项目写权限，避免 viewer/non-member 绕过 ACL 写入项目分析内容
- [x] 用户权限层第四层第一批：补用户禁用/锁定、鉴权拒绝、管理员状态管理和前端管理入口
- [x] 用户权限层第四层第二批第一批：补访客/共享 viewer 只读边界、项目 action policy 和前端 permissions 消费
- [x] 用户权限层第四层第二批第二批第一批：补组织/团队权限模型、项目组织授权继承策略和权限变更审计表
- [x] 用户权限层第四层第二批第二批第二批：继续补组织管理 API/UI、组织授权操作入口和审计查询页面
- [x] 数据管理后台第一层：管理员只读查看 PDB、AlphaFold、SIFTS、注释库、Foldseek DB 状态和更新记录
- [x] 数据管理后台第二层：补真实导入 dry-run/确认触发、更新历史筛选、失败原因和数据版本对比
- [x] 数据管理后台第二层增强：PDB / AlphaFold / Foldseek DB / SIFTS / annotations / smoke readiness 增加版本、数量、更新时间、缺失项，并在 `/data` 状态卡展示
- [x] 监控告警第二层：补 Redis 可达性、队列 backlog、Celery worker ping/active task 运行态监控
- [x] 监控告警第三层第一批：补慢请求内存窗口、HTTP 5xx 趋势、任务失败趋势和外部通知配置状态
- [x] 监控告警第三层第二批：补真实外部通知发送、通知重试、告警静默/升级策略，默认关闭并由管理员显式 dispatch
- [x] 自动化测试增强第一层：新增验收矩阵入口，覆盖文件下载权限、MD 白盒 artifact、数据后台、OSS 兼容预检，并可选接真实浏览器回归/MD 黑盒/live gate
- [x] 自动化测试增强第一层增强：新增 ligand 合同黑盒、ligand artifact 权限绑定、data readiness metadata 和 acceptance matrix ligand gate 回归
- [x] 自动化测试增强第二层本机可做部分：补 live browser/MD blackbox/OSS-MinIO 的 plan-only 与 skipped/blocked contract gate
- [x] 自动化测试增强第二层 OSS live 第一层：使用受控临时对象完成真实 OSS upload/download/delete round-trip，并确认删除
- [ ] 自动化测试增强第二层：在 live 服务上实际执行真实浏览器回归、MD 黑盒长任务和 OSS/MinIO 端到端下载兼容测试（OSS/MinIO 子项已完成，MD 黑盒仍待）
- [x] 封装交付层第二层：新增只读发布回滚计划生成器，识别部署包/备份并标记 destructive 步骤
- [x] 封装交付层第三层第一批：补自动化升级验收、非破坏性回滚计划、打包 dry-run 和 restore drill dry-run 总控编排
- [x] 封装交付层第三层第一批增强：`run_release_acceptance.py` 默认验收矩阵纳入 ligand contract/toolchain smoke，发布验收本轮通过
- [x] 封装交付层第三层第二批本机可做部分：维护窗口回滚、异地备份恢复、外部存储恢复验证均新增 plan-only / blocker gate 和 runbook
- [x] 封装交付层第三层第二批安全加固：`restore_drill.sh` 加载 `.env` 后二次拒绝生产库名，发布 gate 同时要求部署包和备份存在
- [x] 封装交付层第三层第二批非破坏性演练：完成备份 checksum/pg_restore list 校验、临时库 restore drill 和维护窗口 blocker 归档
- [x] 封装交付层第三层第二批 OSS offsite/shadow 真实演练：受控 `drills/` 前缀上传 offsite 备份、读回 SHA256 校验、restore-shadow marker copy/readback 并归档
- [x] 封装交付层第三层第二批线上 readiness 加固：补 ECS 宿主机 Python 3.6 运维脚本兼容、`current` symlink 资产发现、benchmark bundle `HEAD` 支持，并完成线上 `HEAD 200` / `GET Range 206` 验证
- [x] 封装交付层第三层第二批继续推进：生成最新线上数据库备份、完成 OSS drills shadow 演练、补 `benchmark_bundle_head_live` acceptance gate 并在公网验证 `HEAD 200` / `GET Range 206`
- [x] 封装交付层第三层第二批异地恢复闭环：从 OSS `drills/` 对象下载并校验 sidecar，恢复到临时独立 PostgreSQL，完成表/用户 sanity check 后清理临时容器
- [ ] 封装交付层第三层第二批：继续补维护窗口内真实回滚演练、异地备份演练和外部存储恢复验证
- [x] 产品化文档第二层第一批：补发布验收/权限矩阵/告警 dispatch 手册、真实数据样例清单和故障回滚演练记录模板
- [x] 产品化文档第二层第二批本机可做部分：补截图版操作手册文字占位版和演练记录归档模板
- [x] Matvenus 外部会话复盘辅助工具：新增离线 session JSON 提取脚本、脱敏策略、手册和定向测试，等待用户导出真实 JSON 后复盘分析思路
- [x] Matvenus 输出格式与字体样式学习迁移：从公开 message-list/markdown 资源提取消息结构、Markdown 样式和字体规则，并迁移到本平台 MarkdownView
- [x] Matvenus 真实会话读取与分析方法沉淀：通过当前 Chrome 登录态读取 `SD改造+数据反馈` stream-events，生成复盘稿、日报、设计文档和 stream_events 提取器回归测试
- [x] Matvenus 可借鉴方法接入本平台 agent：新增统一酶工程报告协议，接入科学合成提示词和 SOP/清单类普通回复，并用测试保护预测-实验冲突重构、活力-稳定性权衡和 Go/No-Go 输出
- [x] Matvenus 全部历史会话批量调研：读取当前登录态下 14 个会话列表与 stream-events，生成逐会话复盘、总报告和多会话人工归纳，并将编号门控、上位性检查、文献溯源要求补入 agent 协议
- [x] Matvenus 调研高优先级产品化第一层：新增湿实验反馈记录 API、组合突变上位性检查工具、残基编号确认门控工具、Alembic 表迁移、agent 协议提示和定向回归测试
- [x] Matvenus 调研高优先级产品化第二层第一批：`/data` 页面新增实验反馈录入、Go/Watch/No-Go 汇总、validated single mutant 展示、最近记录列表和前端 API client 接线
- [x] Matvenus 调研高优先级产品化第二层第二批：实验反馈页支持一键把 validated single mutants 送入 `mutation_epistasis_check`，展示组合风险、缺失证据和梯度实验计划
- [x] Matvenus 调研高优先级产品化第二层第三批：组合检查 UI 支持人工补充结构距离、机制标签和同一区域分组证据，避免只靠湿实验反馈做组合判断
- [x] 产品化文档第二层第二批本机可做部分：生成真实浏览器自动截图、截图 manifest、截图版操作手册更新和本机截图/ligand gate 演练记录归档
- [x] 产品化文档第二层第二批 admin 验证补强：使用临时 admin 登录态完成 `/admin` 真实浏览器深测，可作为后台截图和操作手册的验证证据
- [x] 剩余待建清单本机可做收口：新增统一只读 readiness 总控，聚合真实数据、GPU/GROMACS、ligand runtime、OSS/MinIO、admin 截图和维护窗口演练外部依赖状态
- [x] 剩余待建清单本机可做收口第二批：OSS/MinIO readiness 支持阿里云 OSS 变量别名，修复导出 HTML 报告 XSS 风险并完成线上 smoke
- [x] 阿里云 OSS 凭据修复：更新本地/ECS `.env.aliyun.app` OSS 配置、重建线上运行容器并通过 runtime 对象写入/读回/删除 smoke
- [x] 线上多用户隔离配置：创建/更新 `kwb01`-`kwb04` 普通研究员账号，并通过黑盒/白盒验证普通用户只能管理自己的会话、项目、文件和任务记录
- [x] chat/agent 前端切账号残留修复：按当前 `user.id` 清空并同步 chat store，避免同一浏览器切换账号后显示上一用户会话
- [ ] 产品化文档第二层第二批剩余部分：在维护窗口后归档真实回滚/异地备份/外部存储恢复演练记录
- **状态：** complete

### 阶段 7：阿里云上线环境准备
- [x] 读取现有阿里云部署文档、compose 和 env 模板
- [x] 记录当前服务器/RDS/Redis/OSS 拓扑风险，不在文档中保存明文密码
- [x] 生成上线环境准备清单、上线变量模板和缺口清单
- [x] 本机运行发布 readiness、打包 dry-run、compose config dry-run
- [x] 远端 ECS 连通性、系统版本、Docker/Compose、磁盘、端口和安全组预检
- [x] 确认 RDS/Redis/OSS 网络访问策略与白名单
- [x] 准备部署包与上传/部署步骤，等待最终域名、数据库账号和 OSS AccessKey 确认
- [x] ECS 构建前端/后端镜像，并修复 OIDC runtime secret 挂载导致的后端启动前导入失败
- [x] 补 Redis ACL/密码 URL 支持、release 安装脚本和 current 子目录防错检查
- [x] ECS 启动试运行 app stack，完成 RDS/Redis/OSS/DashScope smoke、Outline migration、Alembic stamp 和公网 health 验证
- [x] 创建管理员账号并完成登录、Wiki OIDC、文件上传、工具调用账号级 smoke
- [x] ECS 升配后恢复 nginx 证书挂载并完成 HTTP/HTTPS 入口复验
- [x] 不等正式域名，切换为公网 IP 80 直接上线入口并完成 smoke
- [x] 恢复线上 `/data` 数据资产：同步 `deploy_data` 和 `lipase.db` 到 ECS 持久目录，readiness 恢复 `live-ready`
- [x] 导入本地结构化酶蛋白 SQLite 大库到线上 RDS：`enzyme_records=280036`，domain 数据 725449 行
- [ ] 绑定正式域名和 HTTPS 证书，将临时 HTTP 4200 入口切换到生产 80/443
- **状态：** complete

### 阶段 17：酶身份画像与关键残基证据链调研
- [x] 复盘同一 388 aa-SD-WT 案例中 MatVenus 与本平台的完整输出差异
- [x] 核验 UniProt Q69IF8、InterPro IPR001461、PROSITE PS00141/PS51767、M-CSA 官方证据定义
- [x] 确认当前短 motif -> EC 误判、家族未聚合、催化位点未门控和候选数量虚高的根因
- [x] 形成 `enzyme_identity_profile` 最小产品契约、证据等级和编号映射要求
- [x] 按契约实现第一版身份画像聚合工具，并接入 activity/thermostability 候选排序前置门控
- [x] 第一层同步优化：将 `protein_benchmark` 降级为身份画像通过后的解释模块，新增 `scientific_claim_gate` 最小 claim 级报告门控
- [x] 第一层同步优化扩展：新增酶目标模块决策树、工具能力状态审计、人类靶点/抗体专项输入合同门控
- [x] 第一层输出优化：`enzyme_objective_module_plan` 接入 agent，突变位点主表前置展示，目标证据不足时保留探索性排单并显式标注风险
- [x] 第一层报告优化：`scientific_claim_gate` 接入综合报告链路，fallback/LLM 报告均获得 Claim Audit Gate 约束
- [x] 第一层能力真实性 payload：AlphaFold2 / RFdiffusion / ProteinMPNN / DiffDock MVP 输出显式标记 proxy 和非真实推理
- [x] 第一层回归验收：补 388 aa-SD-WT 正式主表、未知家族、家族冲突、编号/身份未确认和探索性主表测试，并完成前端真实浏览器主表截图验收
- [x] 联网证据源/live gate 第一层：annotation bundle、BLAST、sequence search 外部证据明确区分 live/degraded/blocked，并记录接口、查询状态和失败原因
- [x] 联网证据源/live gate 第二层第一批：新增平台工具 `interpro_live_lookup` 与 `literature_live_search`，并将 live/degraded/blocked 状态接入 Claim Gate、报告生成器和前端工具卡
- [x] 联网证据源/live gate 第二层第二批：补 InterProScan 序列提交、文献缓存/stale fallback、报告 Evidence Manifest 和联网文献表结构化导出
- [x] 联网证据源/live gate 第二层第三批：继续补 InterProScan 结果轮询/解析、数据资产/platform manifest 版本锁定、NCBI API key/速率策略和报告引用格式增强
- [x] MatVenus 第一屏酶改造报告格式产品化：fallback 报告和前端突变卡均将突变位点主表、编号映射、突变逻辑、实验动作和 Go/Watch/No-Go 前置，Claim/Evidence 继续作为审计附录
- [x] P0-3 候选行结构证据落地：`mutation_priority_score` 候选行携带 PDB CA geometry evidence，fallback report 与前端候选卡显示 CA B-factor、最近催化 CA 距离、8A CA 接触数和结构风险，并将 structural protection guardrails 合并为 No-Go/风险门控
- [x] P0-2/P0-3 结构特征增强：`build_site_structure_function_features` 增加 PDB `HELIX/SHEET` 二级结构注释、CA 接触环境分类、relSASA/pocket 未计算状态，并同步到候选表、报告和前端卡片
- [x] P0-2 relSASA：使用 Biopython `ShrakeRupley` 计算输入 PDB 的残基级 SASA，按最大 ASA 参考表输出 `rel_sasa`、来源和失败降级状态，并同步到候选表/报告/前端
- [x] P0-2 非聚合 HETATM 几何：输出输入 PDB 中非水、非聚合 HETATM 重原子到残基的最近距离和组件标识；仅供人工复核，不识别底物/辅因子角色或口袋
- [x] P0-2 多模型一致性：结构特征的 CA、HETATM 和 HELIX/SHEET 解析统一限于首个 PDB `MODEL`，与 residue SASA 的首模型来源一致
- [x] P0-2 主链二面角：输出输入 PDB 的 phi/psi、首末端和缺失原子/肽键断裂状态；不做 Ramachandran 异常判定，不参与候选评分
- [x] P0-4 续问路径增强第一批：Venus 对标差距、候选位点解释、预测-实验不一致和指定突变追问进入受控复核分支，不重新规划工具、不生成新候选表
- [x] P1 并行只读摸底：编号映射、催化机制、reaction profile 和 WT baseline 已有底层能力，但仍缺统一 registry/profile/service 化收口
- [x] P1-4 编号映射统一 schema 第一批：`residue_mapping_sifts` 输出 `numbering_registry_rows`，`residue_numbering_gate` 直接消费统一 rows，并保留旧 `mappings` 兼容
- [x] P1-3 催化机制 profile 第一批：统一输出 catalytic role、first shell/second shell 状态、role-derived mechanistic step、pending numbering 和保护位点；未知结构/第二 shell 不外推
- [x] P1-1 Reaction Profile 第一批：本地 `ReactionEquation` 仅按 protein EC 与 Rhea EC 精确交集聚合，缺精确关联时 fail-closed 为 `partial`
- [x] P1-2 WT baseline registry 第一批：`wt_baseline_registry` 仅接受精确同条件、显式 WT、QC 通过的本地/调用方授权反馈；claim gate 仅在 status=`ready` 时放行依赖 baseline 的 claim
- [x] P2/P3 并行只读拆解：residue feature table 正式化与 DBTL 项目闭环已完成本地摸底，并按独立写入面拆分执行
- [x] P2-1 residue feature table contract 第一批：输出版本化 schema、PDB/user/UniProt 显式坐标、verified projection eligibility，inferred mapping 只保留几何证据
- [x] P3 DBTL trace 第一批：新增只读项目 trace envelope/API，串联 checkpoint、反馈和 calibration，并通过项目 ACL 与 round filter
- **状态：** complete

### 阶段 51：全部待建项并行收口
- [x] 建立本轮待建项分工、执行日志和外部阻塞边界
- [x] 并行推进本机可完成的测试、runner、文档和数据证据任务
- [x] 为 GPU、HTTPS、维护窗口和真实长任务生成 fail-closed 执行包
- [x] 合并子任务结果，运行回归并更新待建清单
- [x] 确认未部署状态并输出执行结果
- **状态：** complete

### 阶段 52：P2-2 / P3 第二批本机并行收口
- [x] P2-2 新增结构化多目标 objective score contract，不改变 legacy composite/tier
- [x] P2-2 将 objective score 透传到 all_positions、候选行和 experiment_design_table
- [x] P2-2 对未知分量、高风险位点和保护位点保持 fail-closed
- [x] P3 DBTL trace 去重 WT feedback、显式保留 unresolved calibration linkage
- [x] P3 formal decision 冲突继续降级为 unknown/conflict
- [x] 串行完成 focused tests、工具 API、结构工具、agent binder 和项目 ACL/trace 回归
- [x] 运行本机 pytest runner plan-only，确认不联网、不打印 secrets、不执行破坏动作
- [x] 运行全量 pytest runner 实测并处理剩余回归
- **状态：** complete

### 阶段 53：P2-3 候选表生成器 contract 第一批
- [x] 新增 `candidate_table_generation_v1` 输出合同
- [x] 候选行显式透传 `candidate_status`
- [x] all_positions 保留 blocked 行可追溯，候选输出不提升 blocked 行
- [x] 生成合同声明输入来自 residue feature table 与 objective score，不新增总分
- [x] 保持 legacy `composite_priority` / `tier` / 候选数量策略不变
- [x] 完成 focused tests、评分 API 子集、agent binder 和静态检查
- [x] 运行全量 pytest runner 实测
- **状态：** complete

### 阶段 54：P3-1 DBTL 项目数据模型 contract 第一批
- [x] 在现有只读 trace 中新增 `dbtl_project_model_v1`
- [x] 结构化暴露 Project、Round、WT Baseline、Variant、Prediction、Experiment Feedback、Formal Decision
- [x] 输出 entity counts 与 `missing_entities`
- [x] formal decision 冲突不升级，继续显示 unknown/conflict
- [x] 不新增数据库表、不迁移、不写库
- [x] 完成 DBTL trace、项目 ACL 和静态检查
- [x] 运行全量 pytest runner 实测
- **状态：** complete

### 阶段 55：P3-2/P3-3 实验反馈导入与下一轮库设计 contract 第一批
- [x] P3-2 新增 `experiment_feedback_import_v1`
- [x] 导入 contract 记录 assay condition、metric groups、QC、replicate、formal decision、training eligibility
- [x] 缺 QC、重复数、完整条件、formal decision 或指标时只允许存储审计，不允许训练或升级 claim
- [x] P3-3 新增 `next_round_library_design_v1`
- [x] 下一轮库设计输出单点池、组合池、探索池、plate layout、assay required 和高阶组合阻断规则
- [x] 保持 feedback planner 不训练模型、不推断高阶上位性、不提升远端噪声候选
- [x] 完成 focused tests、tools/data 全文件回归和静态检查
- [x] 运行全量 pytest runner 实测
- **状态：** complete

### 阶段 56：P3 DBTL trace 学习就绪度与下一轮库预览接线
- [x] 在只读 DBTL trace 中新增 `dbtl_learning_readiness_v1`
- [x] trace 聚合 `experiment_feedback_import_v1` contract，输出训练可用记录数、claim eligible 计数和缺失原因计数
- [x] trace 聚合 `next_round_library_design_v1`，在有反馈记录时给出下一轮 single point / combination / exploration / plate layout 预览
- [x] round filter 下只消费当前 round 的 feedback records，空 round 保持 `missing_feedback` 和空下一轮库设计
- [x] 修复 checkpoint 循环误引用 feedback `record` 的作用域错误
- [x] 保持只读、不新增表、不迁移、不训练模型、不升级湿实验 claim
- [x] 完成 DBTL trace、项目 ACL、反馈导入/下一轮 planner、静态检查和全量 pytest runner 实测
- **状态：** complete

### 阶段 57：DBTL trace 报告/agent 摘要合同第一批
- [x] 在只读 DBTL trace 中新增 `dbtl_trace_summary_v1`
- [x] 摘要聚合 project memory、learning readiness、next-round library status、formal decision status 和关键计数
- [x] 输出 `required_actions`，明确 round、WT baseline、feedback、formal decision、training contract 和 singleton validation 缺口
- [x] 输出报告合同，强制标注计算假设，禁止把 trace 摘要写成已训练或湿实验验证
- [x] 空 round / 空项目记忆保持 fail-closed，不生成下一轮库设计
- [x] 完成 DBTL trace、项目 ACL、反馈导入/下一轮 planner 和静态检查
- [x] 运行全量 pytest runner 实测
- **状态：** complete

### 阶段 58：DBTL trace 前端可视化接入第一批
- [x] 为项目详情页新增 DBTL 标签页，直接消费 `/api/projects/{id}/dbtl/trace`
- [x] 在 DBTL 视图中展示 project memory、learning readiness、next-round status、formal decision 和关键 counts
- [x] 在 DBTL 视图中展示 required actions、missing entities 和 raw trace 摘要
- [x] 前端 API client 增加 `getProjectDbtlTrace()` 与 `ProjectDbtlTrace`/`ProjectDbtlTraceSummary` 类型
- [x] 完成 TypeScript build 与 ESLint 针对性验证
- **状态：** complete

### 阶段 59：项目列表 DBTL 状态入口第一批
- [x] 项目列表页后台拉取每个可见项目的 DBTL trace summary
- [x] 项目卡片显示 DBTL 状态 chip，展示 summary status 并通过 title 透出 learning / next-round 状态
- [x] 项目列表先加载项目，再异步补齐 DBTL 状态，避免 DBTL 请求阻塞基础项目列表
- [x] 保持 DBTL 状态读取失败时静默降级，不影响项目列表可用性
- [x] 完成 TypeScript build 与 ESLint 针对性验证
- **状态：** complete

### 阶段 60：P0 全部启动与收口
- [x] 指定突变复核器已接入测试回归，确认 trade-off、保护位点和 unknown 字段 fail-closed
- [x] 位点结构-功能特征表已接入 relSASA、HELIX/SHEET、非聚合 HETATM 距离和主链二面角等结构证据
- [x] 多目标候选表已能携带结构证据、风险门控和实验动作，避免只输出总分
- [x] 续问路径已覆盖 Venus 对标差距、候选解释、预测-实验不一致和指定突变追问
- [x] `backend/tests/test_project_dbtl_trace.py` 与 `backend/tests/test_requested_mutation_review.py` 通过
- [x] `frontend` 生产构建与 ESLint 通过
- **状态：** complete

### 阶段 61：P1-1/P1-3 第一批合同收口
- [x] P1-1 Reaction Profile 收紧底物范围门控：仅在反应两侧都存在时才允许 substrate_scope 支持
- [x] P1-1 Reaction Profile 回归补充：确认 exact local EC 交集、partial 反应和报告 contract 字段
- [x] P1-3 catalytic mechanism profile 仍保持 source_coordinate / pending_numbering / report_boundary 的本地只读合同，不外推第二 shell
- [x] P1-2 WT baseline registry 主链接入与报告 contract 收口：`wt_baseline_registry` 与工具包装器统一输出 `report_contract`，保持 exact-condition / no-fallback / ready-missing-conflict 边界
- [x] 运行关键回归、py_compile 和 diff-check，确认相关回归通过
- **状态：** complete

### 阶段 62：P1 今日完整收口验收
- [x] P1-4 编号映射统一 schema 已验收：`numbering_registry_rows`、`residue_numbering_gate`、低置信/未确认映射继续阻断或 warning
- [x] P1-3 催化机制映射已验收：first shell / protected / pending numbering / second shell unknown / report contract 均存在
- [x] P1-1 反应层适配器已验收：本地 exact EC-Rhea 聚合，缺精确匹配 fail-closed，substrate scope 必须反应两侧齐全
- [x] P1-2 酶学条件 baseline registry 已验收：精确同条件 WT、QC、ready/missing/conflict、claim gate 绑定
- [x] 运行 P1 关键回归：`23 passed, 192 deselected`
- [x] 本阶段仍保持本地只读边界：未联网、未部署、未写库、未执行 live Rhea/BRENDA/SABIO/M-CSA 查询
- **状态：** complete

### 阶段 63：P2 第一批合同收口
- [x] P2-1 residue feature table contract 保持可验收：`projection_eligibility`、`schema_version`、`report_boundary` 与结构特征表边界清晰
- [x] P2-2 objective score contract 增补聚合层：保留分量级输出，不引入新的总分
- [x] P2-3 candidate table generation 保持 row contract / output groups / no wet-lab claim 边界
- [x] P2 scorecard 聚合合同验收：将 residue feature table、objective score、candidate table generation 统一成可报告 contract
- [x] 关键回归通过：`5 passed, 126 deselected`
- **状态：** complete

### 阶段 64：P2-1 residue feature table 合同增强
- [x] `site_structure_function_features` 新增 `feature_table_contract`
- [x] 合同明确 `ca_geometry / mapping_projection / secondary_structure / rel_sasa / nonpolymer_proximity / backbone_torsion / pocket_channel_interface` 字段状态
- [x] `pocket_channel_interface` 明确保持 `not_computed`，报告不得声明口袋、通道或界面已识别
- [x] missing PDB / no feature 路径继续输出 blocked contract
- [x] 结构工具与候选表相关回归通过：`5 passed, 142 deselected`
- **状态：** complete

### 阶段 65：P2 合同前端可见化
- [x] 结构特征卡显示 `feature_table_contract` 状态和字段级 field_state
- [x] 突变评分卡显示 `p2_engineering_scorecard_contract` 组件状态、blocked reasons 和 must-not-claim
- [x] 前端不新增科学结论，只展示后端合同边界
- [x] ESLint 与生产构建通过
- **状态：** complete

### 阶段 66：P2 合同进入报告导出/打印
- [x] `mutation_score` HTML 报告导出显示 `p2_engineering_scorecard_contract`
- [x] 报告导出显示 `candidate_table_generation` 的输入合同、输出分组和 boundary
- [x] 报告导出显示 `objective_score_contract` 的证据等级、aggregation、assay required 和 blocking reason
- [x] 下载/打印报告继续只展示合同边界，不新增算法、不改候选排序、不升级科学 claim
- [x] `frontend/src/lib/report.ts` ESLint 与生产构建通过
- **状态：** complete

### 阶段 67：P3 feedback 下一轮约束可视化第一批
- [x] 复核 P3 feedback 主链：`dbtl_trace` 已能聚合 feedback 并生成 `next_round_library_design`
- [x] 项目详情 DBTL 页新增 `Next Round Constraints` 面板
- [x] 展示 validated single-mutant pool、combination pool、assay gate、higher-order 阻断、plate layout、exploration pool 和 boundary
- [x] 后端补回归：有效单点 feedback 进入下一轮单点池和排板约束
- [x] 主线程复验：DBTL trace 测试、前端 ESLint 和生产构建通过
- [x] 本阶段保持只读展示/合同边界，不新增训练、不写生产数据、不升级 wet-lab claim
- **状态：** complete

### 阶段 68：P2 residue distance graph 第一批
- [x] `site_structure_function_features` 新增 `residue_distance_graph_v1`
- [x] 距离图限定为返回特征行的 CA-CA 几何边，按 `contact_radius_angstrom` 输出 edge list
- [x] 每个 feature row 新增最近 CA 邻居距离和邻居位置
- [x] `feature_table_contract.field_state` 新增 `residue_distance_graph`
- [x] 前端结构特征卡显示 Distance Graph 状态、node/edge/radius 和最近 CA 邻居列
- [x] 明确距离图不是 pocket/channel/interface、binding 或 function assignment
- [x] 结构工具测试、py_compile、前端 ESLint 和生产构建通过
- **状态：** complete

### 阶段 69：P2 residue distance graph 透传到候选表
- [x] `mutation_priority_score` 候选行新增最近 CA 邻居证据字段
- [x] 候选逻辑显示最近 CA 邻居距离，作为结构邻域解释，不改 composite score
- [x] 候选输出和 experiment design 表同步透传最近 CA 邻居字段
- [x] 新增回归：结构邻居证据进入候选行，但不改变排序/decision contract
- [x] 后端相关测试 21 passed，py_compile 通过，前端生产构建通过
- **状态：** complete

### 阶段 70：P2 候选卡显示最近 CA 邻居证据
- [x] `MutationScoreCard` 的结构证据 chip 显示最近 CA 邻居位置和距离
- [x] 候选主表与详情卡的结构证据字段对齐
- [x] 仅补解释层，不改变候选排序、分数或门控
- [x] 前端 ESLint 与生产构建通过
- **状态：** complete

### 阶段 71：P2/P3 residue distance graph 接入组合检查
- [x] `mutation_epistasis_check` 支持直接消费 `residue_distance_graph_v1`
- [x] 缺显式 pairwise 距离时，可由图中 CA edge 推导突变对距离
- [x] `feedback_iteration_planner` 支持 `residue_distance_graph` 并记录 `structural_distance_source`
- [x] `/api/data/experiment-feedback/iteration-plan` request model 支持 `residue_distance_graph`
- [x] `DataBrowser` 组合上位性检查支持粘贴距离图 JSON
- [x] 新增回归覆盖 epistasis checker 和 feedback planner 的距离图路径
- [x] 后端相关测试、py_compile、前端 ESLint 和生产构建通过
- **状态：** complete

### 阶段 72：DBTL 下一轮约束显示结构距离来源
- [x] `next_round_library_design` 增加 `structural_distance_source`
- [x] `trace_summary` 增加 `next_round_structural_distance_source`
- [x] 项目详情 DBTL 的 `Next Round Constraints` 面板显示 structural distance source
- [x] 回归覆盖 trace 默认 `none` 来源和 planner 使用 `residue_distance_graph_v1` 来源
- [x] DBTL trace 测试、feedback planner 测试、py_compile、前端 ESLint 和生产构建通过
- **状态：** complete

### 阶段 73：组合上位性检查报告合同
- [x] `mutation_epistasis_check` 输出 `report_contract`
- [x] 每个 pairwise risk 输出 `distance_source`
- [x] 合同记录 mechanism tags、pairwise distance、distance graph、same region、single mutant feedback 输入状态
- [x] 合同明确禁止声明 trained epistasis model、validated combination effect、higher-order safety 和 CA 距离推出 pocket/channel/interface
- [x] `DataBrowser` 上位性结果卡显示报告合同和 pair distance source
- [x] 后端相关测试、py_compile、前端 ESLint 和生产构建通过
- **状态：** complete

### 阶段 74：组合上位性检查合同进入离线报告导出
- [x] `frontend/src/lib/report.ts` 新增 `mutation_epistasis` HTML 报告模板
- [x] 导出报告展示 report contract、evidence inputs、distance source、missing evidence、must-not-claim 和 boundary
- [x] `DataBrowser` 上位性结果卡提供下载入口，blocked 与 ok 结果都可导出
- [x] 增加静态回归，防止导出路径漏掉组合检查合同字段
- [x] 运行前端 ESLint、生产构建、相关 pytest 和 diff-check
- **状态：** complete

### 阶段 75：下一轮库设计组合证据合同摘要
- [x] `feedback_iteration_planner` 在 `next_round_library_design` 中输出组合证据合同摘要
- [x] 合同摘要保留 epistasis recommendation、distance source、evidence inputs、missing evidence 和 must-not-claim
- [x] DBTL trace summary 暴露下一轮组合证据合同状态
- [x] 项目详情 DBTL 面板展示组合证据合同状态和禁止声明边界
- [x] 补后端/前端回归并运行验证
- **状态：** complete

### 阶段 76：DBTL trace 离线报告导出
- [x] `frontend/src/lib/report.ts` 新增 `project_dbtl_trace` HTML 报告模板
- [x] 报告导出 project model、learning readiness、next round library、combination evidence contract、required actions 和 trace summary boundary
- [x] 项目详情 DBTL 页新增下载入口
- [x] 补静态回归，防止 DBTL 导出漏掉合同字段
- [x] 运行前端 ESLint、生产构建、相关 pytest 和 diff-check
- **状态：** complete

### 阶段 77：项目列表 DBTL 组合证据状态入口
- [x] 项目列表 DBTL 状态聚合 `next_round_structural_distance_source`
- [x] 项目列表 DBTL 状态聚合 `next_round_combination_evidence_status`
- [x] 项目卡片 tooltip 显示 learning、next round、distance source 和 combination evidence
- [x] 项目卡片 chip 文案补充组合证据状态，便于从列表判断项目是否可进入组合设计复核
- [x] 补静态回归并运行前端验证
- **状态：** complete

### 阶段 78：湿实验反馈页下一轮设计预览入口
- [x] 在湿实验反馈页增加 iteration plan 预览状态块
- [x] 预览块直接展示 next round library、combination evidence contract 和 recommended pair/promotion boundary
- [x] 复用现有 iteration-plan API，不新增写路径
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 79：湿实验下一轮设计预览离线报告导出
- [x] `frontend/src/lib/report.ts` 新增 `feedback_iteration_plan` HTML 报告模板
- [x] 报告展示 planner mode、data quality、next round library、combination evidence contract、required measurements 和 scientific boundary
- [x] 湿实验反馈页 `IterationPlanCard` 增加下载入口
- [x] 补静态回归并运行前端验证
- **状态：** complete

### 阶段 80：湿实验反馈页项目范围过滤
- [x] 在湿实验反馈页增加 project scope filter
- [x] project scope 同时作用于 feedback list、summary 和 iteration plan
- [x] 输入项和结果都显式标出当前 project scope
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 81：湿实验反馈页可见项目选择器
- [x] 湿实验反馈页加载当前用户可见项目列表
- [x] 项目选择器写入同一 `projectFilter`，保留手动 project_id 输入兼容
- [x] 当前范围提示显示项目名和项目 ID
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 82：湿实验反馈提交绑定当前项目范围
- [x] 湿实验反馈提交 payload 带上当前 `projectFilter`
- [x] 成功提示显示项目绑定状态
- [x] 保留无项目范围时的全局反馈兼容
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 83：湿实验反馈结果随范围/证据变更自动失效
- [x] 项目、酶、决策筛选变化时清空旧组合检查结果和下一轮设计预览
- [x] 手工结构距离、机制标签、同一区域和距离图变化时清空旧结果
- [x] 反馈记录列表变化时清空旧结果，避免提交或刷新后沿用旧单点池
- [x] 仅清空结果态，不清空用户录入的证据表单
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 84：湿实验反馈加载期阻断旧记录触发新分析
- [x] 反馈列表加载期间阻断组合上位性检查函数入口
- [x] 反馈列表加载期间阻断下一轮设计预览函数入口
- [x] 组合检查按钮在加载期间禁用，避免用旧 validated single-mutant pool
- [x] 下一轮设计预览按钮在加载期间禁用，避免用旧 records
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 85：湿实验反馈分析结果绑定生成范围
- [x] 为组合检查和下一轮设计预览生成 `analysis_scope`
- [x] 异步请求返回时校验 scope key，范围变化后丢弃过期响应
- [x] 结果卡展示项目、酶、决策、记录数、通过单点数和人工证据输入状态
- [x] 离线 HTML 报告导出 `Analysis Scope`
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 86：湿实验反馈分析 scope 指纹精确化
- [x] `analysis_scope` 纳入反馈记录 ID fingerprint
- [x] `analysis_scope` 纳入通过单点突变 fingerprint
- [x] scope key 使用 fingerprint 区分同记录数但不同反馈池
- [x] 离线 HTML 报告导出 fingerprint，便于审计复核
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 87：湿实验反馈分析 scope 时间戳与哈希归档
- [x] 结果生成时写入 `generated_at`
- [x] 结果生成时写入稳定 `scope_hash`
- [x] 结果卡展示生成时间和 scope hash
- [x] 离线 HTML 报告导出 `generated_at` 与 `scope_hash`
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 88：湿实验反馈分析报告文件名带 scope 审计标识
- [x] `downloadReport()` 默认文件名识别 `analysis_scope`
- [x] scope 报告文件名带 `scope_hash`
- [x] scope 报告文件名带 `generated_at` 时间戳
- [x] 文件名只使用白名单字符，不拼入 project 名称或用户输入
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 89：湿实验反馈分析 scope fingerprint 顺序稳定化
- [x] 通过单点突变 fingerprint 使用去重后排序集合
- [x] 反馈记录 fingerprint 使用记录 ID 排序后拼接
- [x] scope hash 不再受列表/API 返回顺序影响
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 90：湿实验反馈分析 scope schema version 固化
- [x] `FeedbackAnalysisScope` 增加 `schema_version`
- [x] scope snapshot 默认写入 `feedback_analysis_scope_v1`
- [x] 页面结果卡展示 scope schema
- [x] 离线 HTML 报告导出 schema version
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 91：湿实验反馈分析 scope hash 策略显式化
- [x] `FeedbackAnalysisScope` 增加 `hash_input_policy`
- [x] scope snapshot 默认写入稳定 JSON 输入策略说明
- [x] 页面结果卡展示 hash policy
- [x] 离线 HTML 报告导出 hash input policy
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 92：湿实验反馈分析 scope fingerprint 页面可见化
- [x] 页面结果卡展示反馈池 fingerprint
- [x] 页面结果卡展示通过单点池 fingerprint
- [x] scope 摘要值支持长字符串换行，避免布局溢出
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 93：湿实验反馈分析 scope 科学边界显式化
- [x] `FeedbackAnalysisScope` 增加 `scientific_boundary`
- [x] scope snapshot 默认写入审计元数据非科学证据声明
- [x] 页面结果卡展示 scope boundary
- [x] 离线 HTML 报告导出 scientific boundary
- [x] 补静态回归与前端验证
- **状态：** complete

### 阶段 94：P1 remote pytest runner readiness 收口
- [x] `remote_pytest_runner` 在 CI backend-test 与本地 fail-closed mirror runner 均存在时标记 ready
- [x] ready 项不再进入 remaining backlog external input packet
- [x] 重新生成 external input packet、validation report、gate execution plan、dispatch checklist、operator manifest、go/no-go summary 和 execution tickets
- [x] 剩余 operator tickets 从 8 张降为 7 张，`remote_pytest_runner` 从 P1 阻塞清单移除
- [x] 补静态回归与脚本验证
- **状态：** complete

### 阶段 95：P0/P1 remaining backlog 优先级汇总收口
- [x] go/no-go summary 增加 `priority_summary`，按 P0/P1 汇总剩余 item、missing input、ready、armed 和 blocked 计数
- [x] Markdown 总结增加 Priority Summary 表，管理层可直接看到 P0=4、P1=3 的外部阻塞状态
- [x] execution tickets、operator manifest 和 go/no-go summary 重新生成并校验 source-bound/current
- [x] 补回归测试固定 P0/P1 当前清单与 fail-closed 边界
- **状态：** complete（只读建设完成；formal domain/GPU/MD/live storage/admin screenshot/maintenance drill 仍需外部输入，不标记 live 完成）

### 阶段 96：P0/P1 execution tickets 优先级汇总收口
- [x] `remaining-backlog-execution-tickets` JSON 增加 `priority_summary`
- [x] execution tickets Markdown 顶部增加 Priority Summary 表
- [x] validator 校验 priority summary keys、ticket count、blocked count 和 armed count
- [x] 回归测试固定 P0=4、P1=3 的 ticket 汇总
- [x] 重新生成 execution tickets、validation report 和 operator packet manifest
- **状态：** complete（只读建设完成；7 张 ticket 仍 blocked，0 armed，不执行 live gate）

### 阶段 97：P0/P1 external input packet 优先级汇总收口
- [x] external input packet 每个 item 增加 `priority`
- [x] external input packet JSON/Markdown 增加 `priority_summary`
- [x] external input validation report 和 values template 保留 priority summary
- [x] 回归测试固定 P0=4、P1=3 以及 P0/P1 缺输入行数
- [x] 从 external input packet 到 validation、execution plan、dispatch、go/no-go、tickets、manifest 全链路重新生成并校验
- **状态：** complete（只读建设完成；P0 仍需 19 个输入字段，P1 仍需 12 个输入字段，0 armed）

### 阶段 98：P2/P3/P4 roadmap 与 readiness packet 第一批
- [x] 新增只读 `p2-p3-p4-roadmap` 生成器
- [x] 固化 P2 已有 residue feature、objective score、candidate table generation 三类本地合同
- [x] 固化 P3 已有 DBTL trace、feedback import/next-round library 两类本地合同
- [x] 将 P4 定义为生产级闭环治理层，状态 `defined_not_started`
- [x] 输出 JSON/Markdown roadmap，并接入 Makefile 和配置回归测试
- **状态：** complete（只读建设完成；P4 不声明已运行、训练或生产闭环）

### 阶段 99：P2 候选行 feature completeness hardening 第一批
- [x] 候选行新增 `candidate_feature_completeness_v1`
- [x] 每个候选位点输出 `available_features` 与 `missing_feature_reasons`
- [x] 缺 `pocket/channel/interface`、conservation、ddG/packing、MD RMSF 时显式 fail-closed 展示缺口
- [x] 字段透传到 tier candidates 和 experiment design table，不改变 legacy ranking 或 objective score
- [x] 补 P2 定向回归并重跑 P2/P3/P4 合同组合测试
- **状态：** complete（本地合同增强完成；真实 pocket/conservation/ddG/MD 仍需外部计算证据）

### 阶段 100：P3 DBTL required action contract hardening 第一批
- [x] DBTL trace summary 的 `required_actions` 增加 `category` 和 `priority`
- [x] 新增 `dbtl_required_action_contract_v1` 汇总 action count、category、priority
- [x] action 分类覆盖 data_entry、assay_qc、formal_decision、combination_gate、general
- [x] DBTL HTML 报告导出 Required Actions 时显示 category / priority
- [x] 补 DBTL trace 与前端报告静态回归
- **状态：** complete（只读合同增强完成；不写库、不训练、不执行 assay）

### 阶段 101：P4 closed-loop readiness contract 第一批
- [x] DBTL trace summary 新增 `p4_closed_loop_readiness_v1`
- [x] P4 gates 覆盖 active learning batch、model calibration registry、combination evidence、manufacturing constraints、live gate approval
- [x] 当前 P4 readiness 保守 blocked，live gate approval 永远不能由 trace 自动放行
- [x] DBTL HTML 报告导出 P4 Closed Loop Readiness 区块
- [x] roadmap 将 P4 更新为 1 项 ready local contract，但生产执行仍由外部审批和数据门槛阻断
- **状态：** complete（本地合同建立；不训练、不执行 live gate、不验证制造约束）

### 阶段 102：P3/P4 DBTL 页面可见化
- [x] 前端 API 类型补齐 `required_action_contract` 与 `p4_closed_loop_readiness`
- [x] 项目详情 DBTL Required Actions 显示 action category / priority
- [x] 项目详情 DBTL 页新增 P4 Closed Loop Readiness 面板
- [x] P4 gates、blocked count、required action count、must-not-claim 在页面可见
- [x] 补前端静态回归、TypeScript 和 ESLint 验证
- **状态：** complete（只读展示完成；页面不提供训练、live gate 或制造审批入口）

### 阶段 103：P4 项目列表状态入口
- [x] 项目列表 DBTL 状态聚合 `p4_status`
- [x] 项目列表 DBTL 状态聚合 `p4_blocked_gate_count`
- [x] 项目卡片 DBTL chip title 显示 P4 状态和 blocked gates
- [x] 项目卡片 DBTL chip 文案显示 P4 当前状态
- [x] 补静态回归、TypeScript 和 ESLint 验证
- **状态：** complete（只读状态入口完成；不阻塞项目列表基础加载）

### 阶段 49：HM.pdb deep 专业检索性能与 checkpoint 回归修复
- [x] 核实 deep HM.pdb 同步 BLAST 与 SC synthesis timeout 导致确认执行 120s+ 的根因
- [x] 将 `blast_search` 接入 Celery 异步工具集合和 default worker profile
- [x] 报告层区分 BLAST submitted / completed / failed，避免把后台任务当失败或完成证据
- [x] 将上传 PDB + Foldseek/SIFTS/BLAST 纳入确定性报告快路径，避免等待 SC LLM timeout
- [x] 补 scheduler、agent binder、uploaded PDB、checkpoint、BLAST 相关本地回归
- [x] 部署线上并通过 deep HM.pdb smoke、Wiki/checkpoint smoke 和容器健康/日志复核
- **状态：** complete

### 阶段 8：AI 酶改造模型整改
- [x] P0：修复普通问答/模型元问题误进 `sequence_search` 的路由风险
- [x] P0：缺少序列、结构、明确蛋白目标时先追问，不进入工具链
- [x] P0：`sequence_search` 空结果不再被完整报告模板掩盖
- [x] P1 第一批：fallback 报告增加事实/推断/不确定性/实验验证证据分层
- [x] P1 第一批：收紧 protein design 路由，避免“设计实验方案”误判为 binder/protein design
- [x] P1 输出体验：修复聊天流式 Markdown 表格按纯文本显示的问题，并容错模型输出的轻微坏表格
- [x] P1 输出体验增强：聊天 Markdown 表格归一化支持模型输出的断行首列、粘连分隔行和 `| | 下一行` 坏表格，统一渲染为类似 Excel 的 HTML 网格表
- [x] P2 第一批：建立酶改造任务专用评测集，覆盖分类、追问、工具调用、证据分层和输出结构
- [x] P2 第二批第一轮：扩充湿实验反馈、结构编号、文献证据、组合突变和上传 PDB 场景
- [x] P2 第三批第一层：新增真实线上 AI 聊天黑盒脚本，覆盖缺信息追问、无目标 binder、结构编号缺失等低成本端到端场景；默认不打印凭据，需显式 live 凭据执行
- [x] P2 第三批第二层：使用正式普通研究员账号在维护窗口执行线上 AI 黑盒 live gate，并归档真实流式响应摘要

### 阶段 30：Venus/MatVenus 策略执行机制深度调研与修复
- [x] 调研已归档 Venus/MatVenus 会话、raw stream-events、review 复盘和设计文档，提炼策略确认、同题续跑、阶段状态和严格执行机制
- [x] 调研国内外 AI 蛋白/蛋白设计平台，重点比较任务编排、策略确认、工具/模型能力、结果交付和实验反馈闭环
- [x] 对照本平台 `agent_graph`、前端确认按钮、会话 history 和既有回归测试，定位“确认后重新开流程/同一问题误判”的真实根因
- [x] 先形成修复设计，不直接改业务代码；明确哪些能力借鉴 Venus，哪些不能照搬
- [x] 按设计最小侵入修复，并增加同题续跑、策略复用、确认严格执行和新任务边界回归
- [x] 运行针对性测试，必要时做前端黑盒验证
- [x] 中期服务端 `strategy_checkpoints` 持久化第一层：plan-only 策略落库、awaiting checkpoint supersede、execute_confirmed 缺 payload 时从服务端 active checkpoint 恢复
- [x] 长期 `WetLabCalibration` 第一层：按项目/assay/轮次从湿实验反馈生成保守校准摘要、命中率、证据等级和持久化 run
- [x] 中期服务端 `strategy_checkpoints` 第二层第一批：跨刷新前端恢复 active checkpoint UI，并在 SSE/API 状态中暴露 `next_action`、`artifacts`
- [x] 中期服务端 `strategy_checkpoints` 第二层第二批：补 revision 历史查询 API 和前端最小审计展示
- [x] 中期服务端 `strategy_checkpoints` 第二层第三批：补阶段级 artifact handoff UI 和更完整的 Venus 风格执行时间线
- [x] 同一问题续问第一批：解释/整理型追问使用上一轮同一蛋白上下文合成答复，不重新启动工具策略；新序列、执行、重跑请求继续 fail-closed 或走新策略
- [x] 长期 `WetLabCalibration` 第二层第一批：把同项目校准摘要接入候选排序、fallback 报告 ClaimGate 和同项目执行上下文，且保持“项目级校准不等于具体候选湿实验验证”的边界
- **状态：** complete
- [x] P2 第四批：修复酶改造分析流程固定化，按目标路由热稳定性/比活力/底物特异性/可溶性表达工具链，执行层支持负向约束 fail-closed 和只抽取短路，并修复序列抽取边界
- [x] P2 第五批：固化用户确认的人工分析流程 v1，平台默认按输入整理、基础核验、结构获取、最小基础画像、目标拆解、目标深分析、证据执行、候选策略、结果输出执行
- [x] P2 第六批：补齐策略确认后执行门控，默认只出工具策略和流程，用户确认后才执行，用户修改策略时重新生成计划不执行
- **状态：** complete

### 阶段 31：策略治理配置中心与黑盒验收
- [x] 第一批：将同题续问、新任务、执行确认、合成追问等策略 token 集中到 `agent_policy` 服务，支持 `AGENT_STRATEGY_POLICY_JSON` 配置扩展
- [x] 第一批：新增只读 `/api/chat/strategy-policy` 策略审计接口和前端 API client
- [x] 第一批：补 env 示例、配置扩展测试和只读策略接口测试
- [x] 第二批：新增本地/线上黑盒脚本，覆盖“确认执行不重启、解释型续问不重跑、新序列开新策略、手输确认 fail-closed”
- [x] 第三批：管理后台只读展示当前策略、配置解析错误和风险提示
- **状态：** complete

### 阶段 32：已执行策略状态闭环与同项目续问记忆
- [x] 第一批：修复结构化 confirmed payload 执行后服务端 active checkpoint 未关闭的问题，执行成功后将匹配 checkpoint 标记为 executing
- [x] 第一批：黑盒脚本新增“确认执行后 active checkpoint 必须清空、history 不得仍为 awaiting”的合同断言
- [x] 第一批：前端流式结束后刷新 strategy checkpoint history，避免 UI 继续展示过期 awaiting 状态
- [x] 第二批：补同项目 recent strategy memory 只读接口，跨会话展示最近已执行策略、artifact handoff 和校准上下文
- [x] 第三批：在同项目续问中注入 recent strategy memory，并继续保持新序列/新结构边界 fail-closed
- **状态：** complete

### 阶段 33：策略 memory UI 展示与会话边界验收
- [x] 将 recent strategy memory 接入会话状态，在进入/切换会话时加载
- [x] 切换用户、新建、删除会话和接口失败时清空或降级，避免旧 memory 串用
- [x] 在 Pipeline/ThinkingChain 中只读展示 revision、状态、工具、artifact handoff 和证据预览
- [x] 明确 UI 证据边界：历史策略背景不等于本轮执行，项目校准不等于候选直接实验验证
- [x] 运行前端 lint/build、后端定向测试和 git diff 检查
- [x] 启动本地服务后执行策略黑盒 smoke；未启动或缺少外部条件时明确记录，不伪造通过
- **状态：** complete

### 阶段 34：发布前运行态硬化与完整本地验收
- [x] 修复后端 Docker 构建对 Foldseek 外部下载的硬失败依赖，默认保持 best-effort 并让工具层 fail-closed
- [x] 完成本地 backend/frontend 镜像重建，避免只靠容器源码热同步作为验收运行态
- [x] 修复本地 Redis AOF 损坏导致的反复重启，恢复 worker/md-worker/ligand-worker 健康或记录真实 blocker
- [x] 复跑 health、策略黑盒 smoke、关键后端定向测试和前端 lint/build
- [x] 记录线上同步边界：本地完整验收通过后再发布，不把本地热同步状态直接当线上发布证据
- **状态：** complete

### 阶段 35：线上同步前发布边界与最小发布准备
- [x] 汇总 Stage 30-34 变更范围，区分必须上线的策略修复、UI 展示和运行态 Docker 修复
- [x] 生成或复用现有发布包/同步流程，先做非破坏性 dry-run 与 checksum/关键文件清单
- [x] 明确线上发布前置条件：当前线上健康、回滚包/备份可用、不能输出密钥、不能跳过 smoke
- [x] 若发布条件齐备，按现有发布流程同步并重建服务；若缺外部条件，记录 blocker 而不伪造上线
- [x] 发布后执行公网 health、策略黑盒最小 smoke 和服务健康复核
- **状态：** complete

### 阶段 36：探索性候选突变表深度调研与稳定输出优化
- [x] 调研公开 AI 蛋白/酶工程平台和一手论文中 zero-shot / low-evidence 候选输出的证据分级、实验批次和安全边界
- [x] 审计本平台当前候选突变主表、fallback 报告、ClaimGate 和 `mutation_priority_score` 生成路径，定位“有时无位点表”的触发条件
- [x] 设计探索性候选突变表合同：在证据不足但序列/目标足够时输出低置信候选、风险、禁止升级条件和下一步实验，而不是空表或高置信伪结论
- [x] 最小侵入实现后端兜底与报告格式优化，保持 `computational_hypothesis / blocked / wet_lab_calibrated / experimental_supported` 边界
- [x] 增加回归测试：身份未确认、结构缺失、编号不确定、无湿实验反馈时仍有探索性表；无序列/无明确目标时继续追问或 blocked
- [x] 运行后端定向测试、前端 lint/build 或必要 smoke；如通过再按发布流程同步线上
- **状态：** complete

### 阶段 37：探索性候选突变表第二层展示与报告边界增强
- [x] 将探索性候选的 `blocked_upgrade_conditions` 显式展示到 fallback 报告和前端候选表，避免只埋在 JSON 中
- [x] 增加报告级回归测试，确认探索性表包含“不能升级/需补证据”边界，不输出 Go/P1 高置信语义
- [x] 运行定向后端测试、前端 lint/build 和必要线上同步
- **状态：** complete

### 阶段 38：探索性候选综合上下文与压缩结果边界增强
- [x] 审计 LLM 综合前的工具结果压缩逻辑，确认探索性候选边界不会被截断
- [x] 将 `candidate_table_boundary` 纳入 `mutation_priority_score` compact payload，保留 no-wet-lab-claim 与升级条件
- [x] 增加回归测试，确认 compact payload 包含候选表状态、总边界和行级升级条件
- [x] 运行定向测试、diff 检查，并按需要同步线上
- **状态：** complete

### 阶段 39：探索性候选 LLM 综合提示显式边界增强
- [x] 在 SC 综合提示中新增突变候选专用边界上下文，显式写明探索性候选不得进入 summary/conclusion 当作湿实验事实
- [x] 覆盖 `candidate_table_status / candidate_table_boundary / blocked_upgrade_conditions / objective_missing_evidence`
- [x] 增加回归测试，确认 LLM prompt 中含探索性边界、升级条件和禁止湿实验化规则
- [x] 运行定向测试、diff 检查，并按需要同步线上
- **状态：** complete

### 阶段 40：策略确认 checkpoint 恢复与坏 payload 容错修复
- [x] 复现并解释点击“确认执行上述分析策略”时报 `confirmed_plan must be a list` 与 `strategy_signature does not match confirmed_plan` 的原因
- [x] 修复前端确认按钮：优先使用服务端 active checkpoint，拒绝本地 stale/corrupted plan 直接执行
- [x] 修复前端状态恢复/SSE 归一化：`plan` 与 `step_results` 必须是数组，否则降级为空
- [x] 修复后端确认执行链路：存在 active checkpoint 时服务端 checkpoint 为权威来源，覆盖旧客户端 payload
- [x] 增加回归测试覆盖 stale client payload、坏恢复状态和确认后 checkpoint 状态
- [x] 运行后端定向测试、前端 build、diff 检查，并同步本机 Docker 服务
- **状态：** complete

### 阶段 9：线上平台全面测试与同步修复
- [x] 建立本轮测试范围：本地代码走查、白盒测试、黑盒测试、线上健康检查、同步发布边界
- [x] 本地静态代码走查：重点检查认证、会话、权限隔离、API 错误处理、前端路由和安全配置
- [x] 本地白盒测试：运行后端定向测试、前端构建/静态检查、项目已有验收矩阵
- [x] 线上黑盒测试：访问 `http://120.27.108.138/home` 及关键公开入口，验证状态码、跳转、页面可用性和基础安全响应头
- [x] 阶段 18：将 MatVenus 多轮迭代经验转为证据门控的第二轮规划器，并完成服务/API/工具回归
- [x] 阶段 19：审计外部蛋白研发示例提示词，区分真实运行时、代理/MVP、部分可用与缺失能力，并形成建设优先级
- [x] 阶段 20：基于官方公开资料定义模型工件、科学边界、人类靶点数据合同和跨域下一阶段执行计划
- [x] 如发现缺陷，先在本地最小改动修复并完成回归
- [x] 本地验证通过后，按项目部署脚本/文档同步到线上并做线上 smoke
- [x] 修复本机 `backend/.venv` 旧路径问题，恢复后端 pytest 定向回归
- [x] 修复 `npm run lint` 退出码失败，保留既有前端 warning 债务可见
- [x] 完成 Playwright Chromium 安装并执行线上真实浏览器 public/live smoke
- [x] 通过 ECS Cloud Assistant 添加本机公钥，恢复 ECS root SSH 公钥直登
- [x] 前端 warning 专项治理第一批：清零 `no-explicit-any`，修复 Hooks refs/immutability/exhaustive-deps/preserve-memoization 类警告，保留 Fast Refresh 和页面加载 `set-state-in-effect` 重构债
- [x] 前端 warning 专项治理第二批：将 analysis 类型守卫与 `extractBatchCompare` 拆到非组件 `resultGuards.ts`，清零 Fast Refresh warning；当前 lint 为 0 errors / 11 warnings
- [x] 自动化测试增强第三批第一层：新增 `smoke_ai_blackbox_live.py`、`smoke_file_download_live.py`，并接入 `run_acceptance_matrix.py` 的 opt-in live gate
- [x] 线上同步第二批：同步前端 warning 治理和新增 smoke 脚本，重建线上 `protein-ai-frontend:aliyun`，恢复 compose env 口径后通过 HTTP/public/live smoke
- [x] 前端 warning 专项治理第三批：重构 11 个 `react-hooks/set-state-in-effect` 页面生命周期 warning，`npm run lint` 达到 0 errors / 0 warnings
- [x] 自动化测试增强第三批第二层：使用专用普通 researcher live-gate 账号执行 AI 黑盒 live gate 和文件 upload/download/delete E2E live gate，均通过

### 阶段 41：策略 checkpoint 线上失败复测、上线与性能验证
- [x] 代码走查：确认前端 active checkpoint 恢复、后端 bad/stale payload 兜底、checkpoint 状态关闭、Wiki 发布不破坏策略状态
- [x] 白盒测试：后端定向/全量相关测试、前端 build、diff check
- [x] 黑盒测试：本机与线上 API/UI 复现用户 exact flow，覆盖发布 Wiki 后确认、坏 payload、stale payload
- [x] 性能测试：健康接口、checkpoint active/history、确认执行请求的轻量延迟与并发 smoke
- [x] 上线同步：构建/同步前后端修复到 ECS，重启 frontend/backend/worker/md-worker/nginx，并做容器内代码实证
- [x] 记录最终结论，若仍失败则回滚或给出阻塞原因
- **状态：** complete
- [x] 线上同步第三批：同步生命周期重构到 ECS，修正一次误路径 rsync，补同步 `frontend/src/lib/api.ts` 依赖后 Docker 构建通过，重启 frontend/nginx 并通过线上 HTTP/public/live smoke
- **状态：** complete

### 阶段 42：PDB-only 比活力报告质量修复
- [x] 代码走查：定位附件 object_name/hash 被误解析为残基位点，以及结构工具完成后 fallback 报告未解释证据的根因
- [x] 修复位点/突变提取：清洗附件元数据、路径和 URL，避免 `aa49405d` 这类哈希片段进入编号门控
- [x] 修复 fallback plan：PDB-only 活性请求默认只做结构检索和 SIFTS 映射；无显式位点时不加 residue_numbering_gate，无 MD 请求时不跑 GROMACS
- [x] 修复 fallback report：中文优先展示结构证据、SIFTS 映射、失败工具原因、不能下结论事项和下一步专业分析建议
- [x] 增加回归测试：覆盖用户 HM.pdb object_name exact hash、显式 M204H 编号门控、GROMACS failed 报告边界
- [x] 本地白盒测试：`test_agent_binder.py` 103 passed，`test_structure_tools.py` 7 passed，`py_compile agent_graph.py` passed
- [x] 线上同步与黑盒复测：发布后用 PDB-only “提高蛋白比活力”流程确认报告不再泛化、不再出现假位点 `49405`
- **状态：** complete

### 阶段 43：Wiki 发布链路与策略 checkpoint 联动复测
- [x] 复核线上 Outline API 配置，定位 `OUTLINE_API_TOKEN` 缺失导致 Wiki collection 读取/真实发布失败
- [x] 在线上 Outline 创建后端专用 API key，写入 ECS `docker/.env.aliyun.app` 并重启 backend/worker/md-worker/nginx
- [x] 补部署模板与生产配置 gate：`OUTLINE_API_TOKEN` / `OUTLINE_API_URL` 缺失时生产检查报 critical
- [x] 补并运行配置回归测试，确认模板和生产检查覆盖 Outline API token
- [x] 新增并运行 live smoke：真实发布临时 Wiki 文档后，再用 malformed payload 确认执行原策略，active checkpoint 仍保持权威
- [x] 复核线上容器健康和日志，确认无旧 checkpoint 错误、Wiki 401 或 Outline token 缺失错误
- **状态：** complete

### 阶段 44：Wiki 后确认执行性能与 Python 兼容收口
- [x] 走查线上慢路径，确认 123s 主要来自酶工程执行后的 SC synthesis LLM timeout，而非 Wiki 发布或 checkpoint 恢复
- [x] 后端增加酶工程报告级工具结果的确定性合成捷径，避免 mutation scoring 已有结果后仍等待 LLM synthesis timeout
- [x] 补白盒测试，断言酶工程 `mutation_priority_score` 已产出时 `_synthesize_sc()` 不再调用 `_call_llm`
- [x] 修复 live smoke 脚本 Python 3.6/3.9 兼容性，移除 PEP604/PEP585 类型标注和 `dataclasses` 依赖
- [x] 本地回归：py_compile 通过，agent binder 相关 15 个测试通过
- [x] 线上黑盒：Wiki publish 后 malformed payload 确认执行 19/19 通过，execute 耗时 1.56s，小于 45s 性能门限
- [x] 线上容器与日志复核：backend/worker/md-worker/nginx 均 healthy，未见旧 checkpoint/Wiki/SC timeout 错误
- **状态：** complete

### 阶段 45：PDB-only 比活力 deep 模式默认 MD 回归修复
- [x] 按用户质疑重新评估报告专业性，确认“证据不足不发布具体突变”正确，但 PDB-only 比活力策略默认提交 10ns GROMACS 不专业
- [x] 联网核实 Foldseek/TM-score、GROMACS RMSD/RMSF 和比活力/kcat/Km 的科学边界
- [x] 代码走查确认回归触发条件：前端深度模式会让 PDB-only 请求满足 `wants_deep`，旧逻辑因此追加 `gromacs_md`
- [x] 收紧后端计划规则：PDB-only 活性/比活力请求即使 deep 模式也不默认提交 MD，只有用户明确要求 MD/RMSD/RMSF/GROMACS 才提交
- [x] 补白盒测试：deep PDB-only 比活力不含 MD，显式 MD 请求仍保留 MD，热稳定性 deep 模式原能力不回退
- [x] 补强 `smoke_uploaded_pdb_strategy_live.py`：支持 `--analysis-depth`，并降级为 Python 3.6/3.9 兼容
- [x] 同步并重建线上 backend，执行 deep/standard HM.pdb 黑盒与 Wiki checkpoint 黑盒回归
- [x] 线上日志与容器复核通过，无旧 checkpoint、Wiki、SC timeout 错误
- **状态：** complete

### 阶段 46：深度模式 PDB-only 位点预筛输出修复
- [x] 接受用户反馈：深度模式不能只输出“不能给位点”，必须给可审查的结构候选位点/区域
- [x] 增加 PDB 坐标探索性位点预筛生成逻辑，基于当前链长度/坐标编号给出低置信位点窗口和替换方向
- [x] 报告边界调整：不再写“不能给具体突变位点”，改为“不能给高置信具体突变”，并输出低置信 PDB 位点预筛表
- [x] 保留科学边界：探索性位点不是 UniProt/文献编号，不是湿实验验证候选，必须经 FASTA、底物、催化残基、口袋和编号门控升级
- [x] 补白盒测试与 live smoke 断言，要求 deep HM.pdb 报告包含 `PDB坐标探索性位点预筛`
- [x] 同步并重建线上 backend，deep HM.pdb smoke 21/21 通过，Wiki checkpoint smoke 19/19 通过
- **状态：** complete

### 阶段 47：深度模式 HM.pdb 位点表专业性加固
- [x] 复核用户反馈：仅“有位点表”仍不够，深度报告必须体现不同催化效率机制，而不是同质化残基刷屏
- [x] 调整 PDB-only 探索位点生成器：按残基化学性质和局部窗口打分，同时强制覆盖带电门控、极性/水网络、柔性环/构象熵、疏水体积/通道等机制类别
- [x] 修复疏水位点方向中的无效自替换，例如不再输出 `V171V` 或 `A205A`
- [x] 报告表格新增“机制类别”，每行保留 PDB 窗口、代表位点、探索性替换方向、结构逻辑、风险和升级条件
- [x] 本地使用真实 HM.pdb 解析 SEQRES 299 aa，确认输出 8 个可人工审查窗口：D159、S142、G129、V171、D117、S189、G91、A205
- [x] 线上部署 backend 并复测 deep HM.pdb 黑盒：21/21 通过，仅执行 Foldseek/SIFTS，无 gromacs_md，无 checkpoint 失败
- [x] Wiki publish checkpoint 黑盒回归：19/19 通过，发布后 active checkpoint 存活，确认执行 1.64s
- [x] 线上报告片段抽样确认：用户实际可见机制多样化位点表，且无旧 “先不输出突变清单” 矛盾文案
- **状态：** complete

### 阶段 48：专业数据库检索与 GPT-5.6 Sol 路由核实
- [x] 按用户要求确认 `GPT-5.6 Sol` / `gpt-5.6-sol`：平台已有 `gpt56-sol` 模型路由，作为 KuaPao 中转模型别名处理；匿名模型列表保持 401 权限边界
- [x] 使用 RCSB 官方 Data API 核实 Foldseek 命中：`3BH4/1QHO/1BLI/6TOY` 均为 Bacillus alpha-amylase 相关高分辨率结构，`3BH4` SIFTS 指向 UniProt `P00692`
- [x] 使用 UniProt 官方 API 核实 `P00692`：Alpha-amylase, EC 3.2.1.1, Ca/Na cofactor，含 active site / binding site 注释
- [x] 对 HM 序列与 P00692 做本地局部比对，确认直接序列相似性极弱，不能投射 P00692 催化残基到 HM
- [x] 使用 NCBI BLAST PDB/nr 专业库人工核实 HM 序列：PDB top hits 为 `1WKY_A/3JUG_A/2WHJ_A/2WHL_A` 等 beta-mannanase；nr top hit 为 Paenibacillus GH5 protein，299 aa 覆盖、291/299 identity、E=0
- [x] 修复平台 deep PDB-only 计划：在 Foldseek/SIFTS 后追加 `blast_search(database=pdb)`，从 residue mapping 恢复 PDB 序列后查 NCBI PDB 序列库
- [x] `structure_search_foldseek` 增强：对 top PDB hit best-effort 查询 RCSB 官方标题、实验方法、分辨率、聚合物实体和 UniProt/SIFTS 引用
- [x] 报告增强：新增 `RCSB/PDB 专业库命中注释` 与 `序列级专业库检索（BLAST）` 段，明确序列级 BLAST 权重高于弱结构折叠相似
- [x] 本地测试：上传 PDB 相关 11 个测试通过，覆盖 RCSB 注释、BLAST mannanase 命中和 no MD
- [x] 线上部署与 deep smoke：23/23 通过，deep HM.pdb 工具为 `structure_search_foldseek/residue_mapping_sifts/blast_search`，无 MD、无 checkpoint failure，执行 120.76s <= 180s 专业检索预算
- [x] 线上报告抽样：当前 BLAST 工具在同步预算内可能 degraded；报告会显示 degraded 边界，不伪造 beta-mannanase。人工 NCBI 结果已记录为下一步接入本地 PDB/mmseqs/BLAST 缓存的依据
- **状态：** complete

### 阶段 10：聊天流式 SSE 保活与长任务断流治理
- [x] 复现与定位 `/api/chat/stream` 长时间无输出导致的浏览器断流/`ERR_INCOMPLETE_CHUNKED_ENCODING`
- [x] 在后端 SSE 层加入 heartbeat 注释帧，避免长工具调用期间连接长时间静默
- [x] 增加 heartbeat 回归测试，覆盖短暂停顿后仍可正常结束的流式响应
- [x] 线上同步 backend 并重新验证公开入口健康
- [x] 禁用线上千问/DashScope 默认路由，生产默认切换到 `kuaPao/gpt-5.5`
- [x] 修复自动标题未继承当前聊天模型的问题
- [x] 修复 sync LLM provider timeout 和 agent coroutine timeout，避免 synthesize 阶段无限等待
- [x] 线上 live gate 复测默认短请求和 `gpt55` 蛋白稳定性长请求，均 HTTP 200 且无 SSE error，长请求已 done
- [x] 复查上传 PDB 后的真实浏览器长请求：确认 chat 流误入 7200s `gromacs_md` 风险
- [x] 将聊天入口 `gromacs_md` 强制改为 plan-only，不在 SSE 请求内执行真实 GROMACS
- [x] plan-only MD 结果跳过 LLM 综合，直接输出确定性 Markdown 报告
- [x] 线上真实上传 PDB + MD/热稳定性 live gate 通过：HTTP 200、75s、done=1、error=0
- **状态：** complete

### 阶段 11：P0 审计闭环、关键测试与基线冻结
- [x] P0-1：对照 `backend/.audit-report.md` 建立逐项状态矩阵，区分已修、未修、已修未测和需回归验证
- [x] P0-2：补关键测试覆盖 auth、files、chat/SSE、OIDC、async task status/cancel
- [x] 补安全修复：`/api/chat/models`、`/api/tools`、工具详情、diagnostics、MD protocol metadata 统一要求登录
- [x] 补安全修复：项目名输入去空白并拒绝尖括号，阻断 `<script>` 项目名进入 DB/Wiki 模板
- [x] 本地定向回归：`python3 -m py_compile ...` 通过；P0 新测试 11 passed；组合定向 pytest 51 passed / 5 warnings
- [x] P0-3：冻结当前评测对象为 `HEAD=25679eb0886ac1be69bb251cd9359d61483fdc1e` 加本轮 P0 working tree diff；未创建 commit
- [x] 线上回归验证：chat/SSE、文件上传、慢工具 async submit/status/cancel、auth/OIDC/工具模型元数据匿名 401、普通登录态工具 metadata 200、文件下载 E2E、OIDC provider round-trip 均已复测；完整 Outline 前端 callback 仍可在正式域名/HTTPS 后做最终联调
- **状态：** in_progress

### 阶段 12：前端 / SSE / 会话一致性深评
- [x] 新增 `frontend/tests/chat-sse-deep-live.mjs`，覆盖 `/chat/agent` baseline 流式、PDB 附件、`gromacs_md` async submitted、task 信息展示、logout 清理、console/5xx 监控
- [x] 新增 `frontend/tests/chat-session-deep-live.mjs`，覆盖 restoreSession、坏 access token 后 refresh/retry、切用户隔离、stale saved conversation 清理
- [x] 修复 `restoreSession` 竞态：并发 `syncConversations()` 改为共享 Promise，避免恢复逻辑早于列表同步完成
- [x] 修复刷新水合误清当前会话：`auth null -> current user` 不再按切用户清理
- [x] 修复会话 ID 类型不一致：前端 store 在 API 边界统一将 conversation id 转为 string
- [x] 修复 token refresh 边界：本地 access token 无法解析 `exp` 时主动 refresh，不再长期保留坏 token
- [x] 线上部署第七版前端 bundle `index-BVil8ddL.js` 并通过 HTTP/public/live smoke、chat/SSE live gate、session live gate
- [x] 新增并同步 `frontend/tests/workbench-deep-live.mjs`，覆盖 HomePage 快捷分析/上传入口、ProjectDetailPage Sequences/Results/Wiki、以及 `/benchmarks`、`/benchmarks/venus-15b`、`/pdb`、`/wiki`、`/data`、`/admin` 次级页面 smoke
- [x] 工作台深评线上回归通过：HTTP/public/live smoke、chat/SSE、session、workbench deep live gate 均 passed；ECS `backend/frontend/nginx/worker/md-worker` healthy
- [x] 管理后台登录态深测：新增并执行 Playwright `admin-deep-live.mjs`，覆盖 `/admin` 关键区块、任务审计 CSV 下载、deploy_data dry-run 导入计划、控制台/HTTP 错误监控
- **状态：** complete

### 阶段 13：部署 / 运维 / 发布准备度深评
- [x] 建立发布准备度评测范围：升级 readiness、验收矩阵、部署包 dry-run、回滚计划、备份/恢复 dry-run、线上只读健康与资源状态
- [x] 运行本地非破坏性 release acceptance / upgrade readiness / rollback plan / package dry-run，并记录 passed、skipped、blocked 项
- [x] 运行线上 ECS 只读检查：compose 健康、镜像/容器版本、磁盘、端口、关键 API health、worker 队列状态和近期错误日志
- [x] 修复低风险发布脚本问题：部署包排除 `.venv* / venv*`，备份 checksum 改为相对文件名，旧绝对路径 checksum 校验兼容
- [x] 发布准备度回归：配置测试 95 passed；deploy-live-gate passed；release acceptance 带 backup verify 为 0 failed / 3 blocked / 0 skipped
- [x] 输出发布准备度结论：当前可作为非破坏性评测基线；生产回滚、异地备份恢复、外部存储恢复仍需维护窗口和独立目标参数
- **状态：** complete

### 阶段 14：中文酶名 + 已上传结构输入不再固定追问
- [x] 复现用户截图问题：中文输入包含酶名、结构已上传、目标、底物、反应条件和表达体系，仍被早期缺信息模板拦截
- [x] 修复 agent context：history 中的附件 `object_name` 写入 protein context，planner fallback 可使用历史上传结构
- [x] 修复中文命名识别：`酶的名称：...`、`蛋白名称：...`、`目标酶：...` 视为具体蛋白输入，并提取干净检索 query
- [x] 增加回归测试：历史已上传 PDB + 当前中文任务必须生成 `structure_search_foldseek`；中文酶名无附件时进入 `sequence_search` 而非固定追问
- [x] 本地回归：`test_agent_binder.py` 53 passed；线上容器行为断言和公网 SSE 黑盒均通过
- [x] 线上同步：重建 `protein-ai-backend:aliyun`，重启 backend/worker/md-worker/nginx，服务 healthy
- [x] 继续查询同类问题并修复：`酶名称/蛋白/蛋白质/目标酶`、`UniProt编号/PDB编号/PDB:`、JSON 风格附件 metadata、`酶名+突变+目标` 均不再固定追问；无真实目标/附件的模糊输入仍追问
- [x] 本轮同类问题回归：新增 11 个边界断言；本地 `test_agent_binder.py` 64 passed；线上容器白盒断言、公网 `/api/chat/stream` 黑盒、health 和日志检查均通过
- **状态：** complete

### 阶段 15：除正式域名外的产品化改进继续推进
- [x] 生产配置强校验：新增脱敏 `check_production_config.py`，接入 upgrade readiness、acceptance matrix 和 Makefile；无正式域名阶段用 `--skip-domain-https` 不阻断
- [x] 慢工具入口：chat 请求新增 `analysis_depth=fast|standard|deep`，前端输入区新增快/标准/深度分段控件；深度模式允许上传 PDB-only 任务进入异步 `gromacs_md`
- [x] 任务中心第一版：新增普通用户 `/tasks` 页面，展示本人异步工具审计、状态、队列、取消和 artifact 下载入口；chat 顶栏增加任务入口
- [x] 夜间 live gate 总控：新增 `run_nightly_live_gates.py`，默认只跑生产配置、HTTP/public/live smoke、benchmark bundle HEAD/Range、acceptance matrix readonly；账号/OSS 写入 gate 保持显式 opt-in
- [x] 维护窗口 runbook：新增 `maintenance-window-production-drill-runbook.md`，明确当前不做正式域名/HTTPS、不做无窗口生产停服回滚
- [x] 本地验证：Python 编译通过；agent 深度/固定追问相关 15 passed；生产配置 gate tests 2 passed；frontend lint 0 warning；frontend build passed；nightly readonly live gate passed-with-skips
- [x] 线上同步部署：同步 backend/frontend/scripts/docs，远端备份 `/opt/protein-ai-platform/backups/codex-pre-domain-skip-improvements-20260723T054001Z`，重建 backend/frontend，重启 backend/worker/md-worker/frontend/nginx
- [x] 线上验证：ECS 容器 healthy；公网 HTTP smoke passed；nightly readonly live gate `passed-with-skips` 且 0 failed；容器内深度 PDB plan 包含 `structure_search_foldseek` + `gromacs_md`；`/tasks` SPA 路由 200
- **状态：** complete

### 阶段 16：结构工作流优先级与门控整改
- [x] 复核专项测试结论：附件上传和 ESMFold 能力可用，问题在结构工作流顺序和执行门控
- [x] Planner 整改：有上传 PDB/mmCIF 时，先 `structure_search_foldseek` 解析结构，再 `residue_mapping_sifts` 做结构-序列/编号映射；有明确突变/位点时再进 `residue_numbering_gate`
- [x] Planner 整改：上传结构时优先使用附件结构，不再同时提交 `esmfold_folding` 预测替代结构；仅序列且结构相关任务时，先基础理化分析，再等待 `esmfold_folding`，再进入 benchmark/mutation 等结构相关推断
- [x] Executor 整改：包含结构门控的计划强制顺序执行；结构门控失败/blocked 时，后续 `gromacs_md` 等结构依赖工具不提交、不执行，并在 step result 写明 gate 未通过
- [x] Synthesis 整改：给模型注入当前轮证据分层约束，明确区分序列级、预测结构、上传/实验结构、编号/映射门控，并禁止引用当前 tool results 之外的旧 task_id
- [x] 回归测试：新增上传 PDB + 序列顺序、序列-only ESMFold 等待、结构 gate 失败阻断 GROMACS；`test_agent_binder.py` 全量 68 passed
- **状态：** complete

### 阶段 17：剩余待建项总启动与外部输入收口
- [x] 剩余待建 readiness 总控补齐正式域名/HTTPS、MD 黑盒 live gate、远端 pytest runner 三类缺口
- [x] Nightly live gates 接入 MD 黑盒 opt-in 计划入口，默认不提交新长任务
- [x] MD 黑盒验证脚本支持从环境变量读取 live 参数，且未显式允许时不创建新任务
- [x] 上线前串行复测：验收矩阵、发布验收、后端全量、前端 lint/build、关键业务链路和线上只读 smoke 均通过，当前无新增 warning
- [x] 整项目重新测试：后端全量、后端/根脚本 compileall、前端 lint/build/组件 smoke、环境/生产配置/结构/配体/MD smoke、验收矩阵、发布验收和线上只读 nightly gate 均完成
- [ ] 正式域名与 HTTPS：绑定正式域名、配置 TLS 证书、切换 `PUBLIC_BASE_URL`，并移除生产配置里的 `--skip-domain-https`
- [ ] MD 黑盒长任务：接入 `verify_md_blackbox.py` 作为 nightly opt-in gate，先跑 resume 再跑 fresh submit
- [x] 远端 test-runner：给生产运行镜像外补齐可跑 pytest 的非生产 runner，避免把测试依赖塞回线上容器
- [ ] 维护窗口演练归档：把真实回滚/异地备份/外部存储恢复演练记录补进 `docs/manuals/drill-records/`
- **状态：** in_progress

### 阶段 18：多酶数据库 Google 文献补证据
- [x] 读取现有 7 个 SQLite 酶库 schema、记录量和插入脚本，明确安全写入格式
- [x] 通过 Google/网页检索每个非 lipase 酶库的可核验论文候选，优先记录 DOI/PMID/标题/年份/关键指标
- [x] 将外部检索结果仅写入 `findings.md`，避免不可信网页内容进入计划文件
- [x] 按现有简化三表 schema 生成可回滚的增量插入脚本或 dry-run 报告
- [x] 试点写入一个数据库并执行 SQLite 完整性、去重和记录量校验
- [x] 根据试点结果决定是否批量扩展到其它酶库
- **状态：** complete

### 阶段 19：Lipase evidence schema 补证据与持续批量化
- [x] 读取 `lipase.db` 11 表 evidence schema 和当前样例，明确与简化三表库的差异
- [x] 通过 Google/网页检索 lipase 工程文献，筛选可写入 `papers / variants / variant_mutations / evidence_claims / metrics` 的高可信摘要级证据
- [x] 生成 lipase 专用 dry-run/backup/apply 脚本，不复用简化库三表写入逻辑
- [x] 正式写入 lipase 试点 evidence 并完成完整性与幂等校验
- [x] 建立下一轮持续批量候选队列，按 family 分批补全文/补充材料级证据
- **状态：** complete

### 阶段 20：平台多酶数据库只读接入第一层
- [x] 后端配置自动发现 `/酶数据库` 根目录，不破坏现有 `LIPASE_DB_PATH`
- [x] 新增通用简化三表酶库只读 service，覆盖 status/search/papers/variants/measurements
- [x] 在 `/api/data` 暴露多酶库 API，保留 lipase 专用 API
- [x] 添加或执行定向校验，确认 6 个简化库可读且 SQLite 完整性通过
- [x] 记录当前第一层边界：只读 API 已接，前端统一酶库 UI 后续继续
- **状态：** complete

### 阶段 21：前端多酶证据库入口第一层
- [x] 前端 API client 增加多酶库 status/search/papers/variants/measurements 方法
- [x] `/data` 页面增加“酶库”family 切换入口，保留原 lipase 专用 tab
- [x] 展示每个 family 的 papers/variants/measurements 计数与只读状态
- [x] 支持按 family 搜索 papers/variants/measurements
- [x] 运行前端 lint/build 或定向类型校验
- **状态：** complete

### 阶段 22：酶库元数据深挖与缺口收敛
- [x] 统计 7 个酶库 DOI/PMID 缺口，明确优先深挖方向
- [x] 通过 Google/网页优先核验 mannanase 和 phytase 的高可信 DOI 缺口
- [x] 生成 dry-run/backup/apply 元数据深挖脚本
- [x] 正式补齐首批 DOI 并完成完整性校验
- [x] 继续深挖 acid_protease 大量缺 DOI 记录和 xylanase 大量缺 PMID 记录（xylanase 已修正首批错误 DOI/重复记录）
- [x] xylanase 第二批 Google/PubMed/DOI 校验：回填 6 个 PMID，修正 7 个错配 DOI，完整性 ok
- [x] acid_protease 第七批 Google/PubMed/DOI 校验：补 9 个 DOI，修正/回填 6 个 PMID，完整性 ok
- [x] acid_protease 第八批 Google/PubMed/DOI 校验：补 `AP002` PMID，修正 `AP535` 错配 DOI/题名/期刊，完整性 ok
- [x] acid_protease 第九批 DOI 质量清理：回填 `AP613/AP540/AP541` PMID，修正 `AP540` DOI，清空 `AP532/AP541` 错配 DOI，完整性 ok
- [x] acid_protease 第十批 PMID->DOI 反查：回填 18 个 DOI，清空 14 个无效/错配 DOI，净 DOI 缺口 49 -> 45，完整性 ok
- [x] acid_protease 第十一批 DOI 回填并完成备份/完整性校验
- [x] acid_protease 第十二批纠错：修正 AP119 DOI、AP113 PMID，补 AP111/AP201/AP202 DOI，完成备份/完整性校验
- [x] xylanase 第三批 DOI->PMID live 核验：新增 dry-run/apply 脚本，回填 `XYN73` PMID，识别多条 DOI 错配风险，完整性 ok
- [x] xylanase 全量 52 条“已有 DOI、缺 PMID”记录 live 盘点：仅 `XYN73` 达到双源题名匹配并回填，其余转入 DOI identity reconciliation 队列
- [x] xylanase DOI identity repair：修正 `XYN54/60/62/65/69/71` 错 DOI，并回填 7 条 verified PMID（含 `XYN66`），完整性 ok
- [x] xylanase 缺 DOI 收敛：补 `XYN51/64/70` verified DOI，回填 `XYN70` PMID，剩余 `XYN67/68` 为专利来源保持空 DOI
- [x] xylanase 第六批边界清理：将 7 条 live 确认为错配 DOI 的论文和 12 条 measurement 标记为 hold/non-exportable，导出安全泄漏保持 0
- [x] 平台酶库质量摘要第一层：`/data` 多酶库状态增加 DOI/PMID 缺口、hold 文献/measurement、可导出 measurement 和专利来源提示
- [x] acid_protease 第十三/十四批 DOI/PMID 深挖：补 `AP615/AP623` DOI+PMID，纠正 `AP211/AP214` JBC DOI，确认 `AP308` PMID 错配需重查，完整性 ok
- [x] acid_protease 第十五批：修正 `AP308` 错配 PMID，补 DOI `10.1016/j.bbapap.2009.08.017` 和 PMID `19715777`，完整性 ok
- [x] xylanase 第七批：补 `XYN78` PMID，修正 `XYN79` DOI/PMID/year，保持 payload boundary 不放行导出，完整性 ok
- [x] acid_protease 第十六批：补 `AP206/AP406/AP409/AP541` JBC DOI，边界不变，DOI 缺口降至 20，完整性 ok
- [x] acid_protease 第十七批：补 `AP616` PMID `10931195`，并由并行 worker 补 `AP307` DOI `10.1016/j.enzmictec.2006.08.029`；边界不变，缺口降至 DOI 19 / PMID 23，完整性 ok
- [x] acid_protease 第十八批：补 hold 行 `AP603` DOI `10.1016/j.ijbiomac.2026.150240` 与 PMID `41539511`，保持 hold/non_exportable，不放行导出，完整性 ok
- [x] acid_protease 剩余缺口三组只读核验：JBC/哺乳动物组、植物/真菌/酵母组、边界/低证据组均完成；除 AP603 外无其它可直接写入候选
- [x] acid_protease residual decision manifest：固化剩余缺口 keep_blank / needs_manual / hold 决策，并补入 AP517/AP521 漏列，避免重复回填弱匹配 DOI/PMID
- [x] acid_protease AP533 export boundary 修复：第十九批将未闭合 paper identity 的 AP533 从 `open/high/A + conf=A` 降级为 `metadata_source_conflict_hold_boundary`，泄漏计数归零
- [x] xylanase residual decision manifest：固化专利行、confirmed DOI/no PMID、non-hold manual、hold/boundary 和 already-resolved 分类，避免把专利/边界/错配 DOI 自动写成可导出文献证据
- [x] export-safe 显式策略第一层：平台查询统一排除 `hold/boundary/non_exportable/patent/preprint` marker，并在 metadata_quality 暴露 patent/preprint/boundary/policy-excluded 计数
- [x] export-safe policy API/UI 暴露：`metadata_quality.export_policy` 返回 patent/preprint 处理口径，`/data` 酶库状态卡显示 policy excluded、boundary、preprint、patent 计数
- [x] patent/preprint 独立数据对象第一层：新增策略设计文档和 SQLite 旁路 sidecar manifest，平台 status 汇总 `metadata_policy_decisions`
- [x] patent/preprint policy decisions 流程入口第一层：新增管理员 dry-run preview API，输出人工 curation/升级脚本所需 manifest 和 export_payload，不写库
- [x] 将 patent/preprint policy decisions 接入可编辑 curation queue 或正式升级脚本发布流程（第一层：dry-run review package + actual publish fail-closed）
- [x] 将 patent/preprint policy decisions 接入正式人工 curation queue 记录表，支持逐条 review/备注/批次归档但仍不写外部 SQLite
- [x] 将 enzyme metadata curation queue 接入 `/data` 管理面板，支持管理员查看 queued/accepted/batched/archived 状态
- [x] 继续深挖 acid_protease 剩余 DOI 缺口、xylanase 非 PubMed 期刊条目和跨库高价值新 paper（本轮只读核验：无可写候选）
- [ ] 下一批 live 强证据核验：acid unresolved identity 候选发现、xylanase `han2019/sun2014nterm`、跨库高价值新 paper，保持 no-write until strong identity
- **状态：** in_progress

### 阶段 23：酶身份与功能位点基础画像闭环
- [x] 将本地 InterPro / EC / M-CSA / SignalP 证据标准化为可审计基础画像
- [x] 在身份画像中区分家族确认与位点编号确认，避免把未映射的 UniProt 位点直接用于用户序列
- [x] 将 `annotation_bundle -> enzyme_identity_profile` 设为酶工程候选推荐的硬前序
- [x] 补家族、催化位点、保护位点和 agent 编排的回归测试
- **状态：** complete

### 阶段 24：live 强证据元数据核验
- [x] 吸收 acid_protease 子 agent live 核验结果：无可写 DOI/PMID 候选，保持 no-write until strong identity
- [x] xylanase `han2019/sun2014nterm` live 强证据复核：PubMed/Crossref/DOI resolver 只读报告，不写库
- [x] 跨家族高价值新 paper 发现：只输出 candidate list 与 strong/weak 状态，不写库
- [x] 汇总可写/禁写/下一批脚本范围；若出现强候选，只生成 dry-run 脚本，不直接 apply
- [x] 完成 sidecar JSON、SQLite integrity 和计划文件一致性检查
- [x] 生成跨家族新 paper 候选 manifest：`new_paper_candidates_20260805.json/md`，仍保持 no external SQLite mutation
- [x] 生成 dry-run-only importer 草案，读取候选 manifest 并拒绝无人工 allowlist 的 apply
- **状态：** complete

### 阶段 25：新 paper 全文 curation 与家族 importer
- [x] 对 `new_paper_candidates_20260805.json` 中 strong/medium 候选逐篇完成当前可访问证据核查（xylanase/lipase/amylase）
- [x] 抽取已可见的突变位点、突变逻辑、实验条件和指标，并标记 WT baseline/source table/figure 缺口（amylase 不入 variant importer；xylanase/lipase 保持全文门控）
- [x] 为 xylanase/lipase/amylase 分别生成 family-specific dry-run importer，带 full-text evidence allowlist（主线程已完成 allowlist 合同与 proposal_id 稳定性修复）
- [x] 补 importer fail-closed 回归测试，覆盖 duplicate、allowlist 身份错配、reject/background、abstract-only 和 `--apply`
- [x] 建立合法全文 intake 边界：incoming 目录、四篇论文 manifest、文件哈希/缺口验收脚本；无 PDF 时保持 blocked
- [x] 建立人工 source locator review queue 与 payload draft template，承接 table/figure/page/metric 抽取但不自动 approval
- [x] 建立 PDF evidence draft extractor：登记 PDF 哈希、文本抽取器、表图/突变关键词提示并保持人工复核门控
- [x] 建立 approved-apply 受控执行器：仅在全文、source locator、payload、stable identity 和正式 approval 全部闭合后执行 dry-run/backup/apply/integrity
- [ ] 每个 importer 必须执行 `dry-run -> backup -> apply -> PRAGMA integrity_check`，且 apply 前人工确认
- [x] 生成 11 个 human decision workstream 的 reviewer input package，明确字段、证据引用和零正式 decision 写入策略
- [x] 从现有 review sources 生成逐行 pending row index，提供稳定待审 ID、来源和字段键，不写 decision rows
- [x] 将 pending row index 切分为 deterministic reviewer batches，支持分批处理并保持零正式 decision 写入
- [x] 将 reviewer batches 排成 P0 优先队列，按人工风险和缺口量排序，便于逐批关闭
- [x] 生成 batch session board 与校验器，支持 reviewer 分配和关闭条件追踪但不写正式 decision
- [ ] 将入库候选继续标为 boundary，直到 variant/measurement source table 完整闭合
- **状态：** in_progress（curation/importer hardening complete；full-text/source table/figure 与人工 apply approval 仍 blocked，未写外部 SQLite，未释放 export-safe）

### 阶段 26：平台联网触发与单次回复一致性修复
- [x] 复现并定位一次提问出现多段/重复助手回复的前后端原因
- [x] 核验“联网了吗”等联网意图是否触发真实 live 工具，以及当前运行环境是否允许外部查询
- [x] 低侵入修复联网意图路由与回复去重/幂等边界
- [x] 增加后端与前端定向回归测试，并执行构建/相关 smoke
- [x] 记录真实联网能力边界，不把缓存、本地数据或失败查询声称为 live
- **状态：** complete（本地代码与真实官方 API 探测已验证；若公网 ECS 使用旧镜像，仍需在下一次发布时部署）

### 阶段 27：联网修复全量验收与公网发布
- [x] 串行运行后端全量回归，避免 SQLite 测试库并发冲突
- [x] 运行前端生产构建、定向 lint、发布验收与联网 live smoke
- [x] 仅在测试全部通过后，按现有 ECS 发布流程同步版本化发布包并重建相关服务
- [x] 验证公网容器健康、HTTP smoke、登录态聊天联网确认与单次回复行为
- [x] 记录发布版本、线上证据和回滚边界
- **状态：** complete

### 阶段 28：剩余待建清单 1-8 启动
- [x] 读取 `remaining-backlog-readiness` 的当前结果并确认 8 个 external_required 项的边界
- [x] 生成 1-8 外部输入包和 Makefile 入口，固定每项 required fields 与 validation commands
- [x] 生成 operator values template 与 fail-closed validation report，要求 secret-reference-only，不打印密钥、不联网、不执行破坏性动作
- [x] 将输入模板/验证接入 Makefile，并用定向 pytest 固定 `network_io=not_executed`、`destructive_actions=not_executed`、`secrets_printed=false`
- [x] 生成 remaining backlog gate execution plan/runbook，只有输入齐全的 item 才 armed，命令计划全程脱敏且不执行 live gate
- `formal_domain_https`：已启动，等待正式域名、TLS 证书和 OIDC/前端环境变量切换输入
- `gpu_gromacs_md_live`：已启动，等待 GPU/GROMACS runtime、真实 WT/mutant 输入和长任务容量
- `md_blackbox_live_e2e`：已启动，等待已有 task id 或新提交许可，以及 live 账号凭据
- `ligand_runtime_live`：已启动，等待 conformer/pdbqt/Vina/topology/GROMACS runtime
- `oss_minio_live_e2e`：已启动，等待 OSS/MinIO 凭据与 live bucket 权限
- `admin_authenticated_screenshots`：已启动，等待管理员截图凭据
- `maintenance_window_drills`：已启动，等待维护窗口 ID、演练许可与外部存储目标
- `remote_pytest_runner`：已收口为 ready，仓库内 GitHub Actions backend-test 与本地 fail-closed mirror runner 均已具备
- [x] 2026-08-20 重新运行只读 readiness、external input packet 和 values validator，确认当前 9 项 backlog 中 2 项 ready、7 项 external_required；7 项 operator input row 均保持缺失，不执行 live gate
- [x] 2026-08-19 生成并核对 `docs/manuals/remaining-backlog-external-input-packet.json`、`.md`、`remaining-backlog-external-input-values.template.json` 和 `remaining-backlog-external-input-validation-report.json`
- [x] 2026-08-19 刷新 `docs/manuals/remaining-backlog-gate-execution-plan.json` 和 `.md`，确认 `armed_rows=0`、`blocked_rows=8`，没有 live gate 被执行
- [x] 2026-08-19 新增 operator dispatch checklist，把 8 个待补输入分成 infra_dns_tls、md_runtime、storage、qa_admin、release_ops、ligand_runtime、ci_runner 7 条派发 lane
- [x] 2026-08-19 新增 dispatch checklist validator 和 Makefile 校验入口，确认派发板 source-bound/current、无 secret 泄漏、无 live command plan、0 failures
- [x] 2026-08-19 新增 remaining backlog operator packet manifest 和 freshness check，记录 17 个脚本/交付物 sha256，当前 `ready-for-operator-review`
- [x] 2026-08-19 新增 remaining backlog go/no-go summary，聚合 external input validation、gate execution plan、dispatch validation 和 operator packet manifest，当前决策 `defer_waiting_for_external_inputs`
- [x] 2026-08-19 新增 remaining backlog execution tickets，把 8 个待建项逐项落成 ticket；当前 `ticket_count=8`、`blocked_ticket_count=8`、`armed_ticket_count=0`
- [x] 2026-08-19 新增 execution tickets validator 和 Makefile 校验入口，确认 8 张 ticket source-bound/current、无 secret 泄漏、无 live command、0 failures
- **状态：** in_progress

### 阶段 29：定制化策略与对话边界修复
- [x] 明确用户反馈：同类目标不能输出同一套通用策略，确认策略后必须严格按策略执行
- [x] 增加当前消息与历史上下文的边界判断：新序列/新结构/新 UniProt/PDB/明确“新任务”不继承上一轮蛋白上下文
- [x] 增加序列特异策略摘要：序列指纹、长度、疏水/带电/Gly/Pro/Cys、motif、糖基化和 assay context 进入策略确认
- [x] 确认执行时剥离 `[用户确认]` 控制标记，避免确认文本改变 deterministic plan
- [x] 补充回归测试覆盖不同序列策略差异、确认执行计划稳定性和新任务隔离旧结构上下文
- [x] 运行 agent binder 定向全量回归
- **状态：** complete

### 阶段 104：P2 candidate feature completeness 前端可见化
- [x] 为突变候选前端类型补 `candidate_feature_completeness_v1` 合同字段
- [x] 在候选主表和候选卡展示 `feature_completeness`、`missing_feature_reasons` 与 P2 证据覆盖状态
- [x] 在 HTML 下载/打印报告的候选表增加 P2 Evidence 列
- [x] 用静态断言固定后端合同、前端卡片和报告导出字段
- [x] 完成前端 lint、TypeScript、后端定向 pytest 和 diff whitespace 检查
- **状态：** complete

### 阶段 105：P2 candidate readiness summary 报告级收口
- [x] 后端新增 `p2_candidate_readiness_summary_v1`，按候选输出汇总 feature completeness、candidate status 和 missing feature reasons
- [x] 前端 P2 合同状态区展示候选证据 readiness、reported/all 计数、top missing reasons 和 report action
- [x] HTML 下载/打印报告新增 Candidate Readiness Summary 区块
- [x] P2/P3/P4 roadmap 将 readiness summary 纳入 candidate table generation evidence token，并刷新 JSON/Markdown
- [x] 完成后端定向 pytest、前端 lint、TypeScript、脚本编译和 diff whitespace 检查
- **状态：** complete

### 阶段 106：P2 objective score readiness summary 收口
- [x] 后端新增 `p2_objective_score_readiness_summary_v1`，按分目标组件统计 unknown/missing 状态、assay required 和 blocking reasons
- [x] 前端 P2 合同状态区展示目标分量 readiness、unknown components、blocking reasons 和 no-composite 边界
- [x] HTML 下载/打印报告新增 Objective Readiness Summary 区块
- [x] P2/P3/P4 roadmap 将 objective readiness summary 纳入 objective score contract evidence token，并刷新 JSON/Markdown
- [x] 完成后端定向 pytest、前端 lint、TypeScript、脚本编译和 diff whitespace 检查
- **状态：** complete

### 阶段 107：P2 experiment design schedulability policy 收口
- [x] 后端新增 `experiment_design_schedulability_policy_v1`，明确 blocked、No-Go、保护位点和无推荐突变行不进入 experiment design table
- [x] 复用 `_is_experiment_design_schedulable()` 过滤 `experiment_design_table`，blocked 行继续保留在 `all_positions` 追溯
- [x] 前端 P2 合同状态区展示排单门控、blocked excluded 计数和 trace 边界
- [x] HTML 下载/打印报告新增 Experiment Design Policy 表
- [x] P2/P3/P4 roadmap 将 schedulability policy 纳入 candidate table generation evidence token，并刷新 JSON/Markdown
- [x] 完成后端定向 pytest、前端 lint、TypeScript、脚本编译和 diff whitespace 检查
- **状态：** complete

### 阶段 108：P3 project memory readiness rollup 收口
- [x] 后端新增 `dbtl_project_memory_readiness_v1`，按 round、ready WT baseline、variant、prediction、experiment feedback、formal decision 六类实体汇总项目记忆完整度
- [x] `trace_summary.project_memory_readiness` 输出 entity status、ready/missing 计数、readiness fraction、must-not-claim 和只读边界
- [x] 项目详情 DBTL 页新增 Project Memory Readiness 面板
- [x] HTML 下载/打印报告新增 Project Memory Readiness 区块
- [x] P2/P3/P4 roadmap 将 memory readiness 纳入 `dbtl_trace_contract` evidence token，并刷新 JSON/Markdown
- [x] 完成后端定向 pytest、前端 lint、TypeScript、脚本编译和 diff whitespace 检查
- **状态：** complete

### 阶段 109：P3 feedback readiness summary 收口
- [x] 后端新增 `dbtl_feedback_readiness_summary_v1`，从现有 `dbtl_learning_readiness_v1` 与 feedback import contracts 汇总反馈记录、训练可用数量、QC、replicate、assay condition、formal decision 和 measured metric 覆盖
- [x] `trace_summary.feedback_readiness` 输出 next-round constraint status、top missing training evidence、must-not-claim 和只读边界
- [x] 项目详情 DBTL 页新增 Feedback Readiness 面板
- [x] HTML 下载/打印报告新增 Feedback Readiness 区块
- [x] P2/P3/P4 roadmap 将 feedback readiness 纳入 `feedback_import_and_next_round_contract` evidence token，并刷新 JSON/Markdown
- [x] 完成后端定向 pytest、综合 P2/P3/P4 pytest、前端 lint、TypeScript、脚本编译和 diff whitespace 检查
- **状态：** complete

### 阶段 110：P4 detailed closed-loop contracts 收口
- [x] 后端在 `p4_closed_loop_readiness_v1` 下新增 `p4_active_learning_batch_contract_v1`，基于 P3 learning readiness 检查训练批次可审查性，默认不执行训练
- [x] 后端新增 `p4_model_calibration_registry_contract_v1`，基于现有 calibration runs 汇总 registry 可追溯字段，默认不重训、不升级 claim
- [x] 后端新增 `p4_manufacturing_constraint_schema_v1`，定义制造/工艺约束 required fields，缺少 process owner evidence 时 blocked
- [x] 项目详情 DBTL 页和 HTML 下载/打印报告展示 P4 三个详细合同状态、blocked reasons 和只读边界
- [x] P2/P3/P4 roadmap 将三个 P4 合同纳入 `industrial_closed_loop_readiness` evidence token，并刷新 JSON/Markdown
- [x] 完成后端定向 pytest、综合 P2/P3/P4 pytest、前端 lint、TypeScript、脚本编译和 diff whitespace 检查
- **状态：** complete

### 阶段 111：P0-P4 重新查缺补漏总控
- [x] 新增 `scripts/build_p0_p4_gap_audit.py`，统一扫描 P0/P1/P2/P3/P4 本地合同证据、local gaps、external blockers 和 remaining backlog
- [x] 生成 `docs/manuals/p0-p4-gap-audit.json` 与 `docs/manuals/p0-p4-gap-audit.md`
- [x] Makefile 新增 `p0-p4-gap-audit` 入口，便于后续一条命令刷新总查缺表
- [x] 审计结果确认 P0=`4/4 ready_local_contract`、P1=`4/4 ready_local_contract`、P2=`3/3 ready_local_contract`、P3=`2/2 ready_local_contract`、P4=`1/1 ready_local_contract`
- [x] 审计结果确认 remaining backlog 仍为 `2 ready / 7 external_required`，live gate 未执行
- [x] 补 `test_p0_p4_gap_audit_is_read_only_and_source_bound`，固定只读、无网络、无破坏性动作、无 secrets 输出和 P0-P4 source-bound tokens
- [x] 完成脚本编译、后端综合 pytest 和 diff whitespace 检查
- **状态：** complete

### 阶段 112：P0-P4 SOP/status export 收口
- [x] 新增 `scripts/build_p0_p4_status_export.py`，从 `p0-p4-gap-audit.json` 生成更短的研发复盘/SOP/status 页面
- [x] 新增 `docs/manuals/p0-p4-status-export.json` 与 `docs/manuals/p0-p4-status-export.md`
- [x] Makefile 新增 `p0-p4-status-export` 入口
- [x] status export 按 P0-P4 输出 ready/item 计数、local followups、external blockers、must-not-claim 和 remaining backlog external followups
- [x] 补 `test_p0_p4_status_export_is_read_only_and_consumes_gap_audit`，固定 schema、只读边界、五阶段顺序和 external_required 不能被清零
- [x] 完成脚本编译、Makefile 入口、后端综合 pytest 和 diff whitespace 检查
- **状态：** complete

### 阶段 113：P0-P4 local gap closure 状态回填
- [x] `p0-p4-gap-audit` 新增 `local_gap_status`，把 local gaps 拆成 `covered_by_status_export` 与 `open`
- [x] `phase_summary` 新增 `open_local_gap_count` 与 `covered_local_gap_count`
- [x] `p0-p4-status-export` 改为只展示 open local followups，同时保留 covered local followups 计数
- [x] 重新生成 `p0-p4-gap-audit.json/md` 与 `p0-p4-status-export.json/md`
- [x] 当前 open/covered 结果：P0=`0/4`、P1=`0/4`、P2=`4/2`、P3=`2/2`、P4=`1/1`
- [x] 完成 Makefile 入口、脚本编译、后端综合 pytest 和 diff whitespace 检查
- **状态：** complete

### 阶段 114：P2/P3/P4 合同收口与报告校验
- [x] 补齐 `p2_structure_feature_gap_summary_v1`、`p2_objective_assay_gap_summary_v1`、`dbtl_readiness_bridge_v1` 和 `p4_operator_review_contract_v1` 的静态合同展示
- [x] 修复 `frontend/src/lib/report.ts` 中 `renderProjectDbtlTrace()` 的作用域错误，并补齐 P4/P3 审计 token
- [x] 更新 `frontend/src/lib/api.ts` 的 `dbtl_project_memory_readiness_v1` / `dbtl_feedback_readiness_summary_v1` 类型约束
- [x] 重新生成 `p2-p3-p4-roadmap.json/md`、`p0-p4-gap-audit.json/md`、`p0-p4-status-export.json/md`
- [x] 后端定向测试、前端 `lint` 与 `build` 通过
- **状态：** complete

### 阶段 115：P0-P4 合同级状态导出收口
- [x] `p0-p4-gap-audit` 不再通过泛化关键词把 local gap 标成 covered，改用 `STATUS_EXPORT_COVERED_LOCAL_GAPS` 显式白名单
- [x] covered 状态改为 `covered_by_contract_status_export`，明确只是合同状态可见化，不表示真实能力或外部门禁完成
- [x] `p0-p4-status-export` 新增 `contract_status_items`，逐合同输出 `contract_name`、`evidence_tokens`、local/covered followups、external blockers、must-not-claim、read_only 和 approval gate
- [x] P2/P3/P4 合同状态导出均保持 `approval_required=true` 与 `blocked_until_explicit_review`
- [x] 重新生成 `p0-p4-gap-audit.json/md`、`p0-p4-status-export.json/md` 和 `p2-p3-p4-roadmap.json/md`
- [x] 定向配置测试、P2 objective、P3 DBTL、feedback import 回归和 diff whitespace 检查通过
- [x] 后端全量 `make pytest-runner-json` 复验，结果 `827 passed`
- **状态：** complete

### 阶段 116：P0-P4 合同到 remaining backlog ticket 最终桥接
- [x] 新增只读桥接生成器，读取当前 `p0-p4-status-export`、go/no-go 和 execution tickets
- [x] 为每条合同输出 ticket 关联、映射覆盖状态和未映射 blocker，保留无对应 ticket 的 contract followup
- [x] 输出 ticket 反向影响合同索引，并做源文件 checksum/source-bound 校验
- [x] 增加 Makefile 生成/校验入口，并把桥接产物与 P0-P4 status export 纳入 operator packet manifest
- [x] 增加定向回归测试，验证数量、映射、只读安全边界和 stale 检测
- [x] 串行重跑 P0-P4、remaining backlog operator 包与桥接流水线
- **状态：** complete

### 阶段 117：remaining backlog operator 包串行刷新入口
- [x] 新增 `make remaining-backlog-operator-packet-refresh`，统一串行刷新 P0-P4 状态、外部输入包、dispatch、go/no-go、execution tickets 和 bridge
- [x] 将最终 manifest build/check 固定在所有 validation 与 bridge 产物之后，避免 freshness 顺序错误
- [x] 增加 Makefile 顺序回归断言，覆盖 18 个刷新步骤且不执行 live gate
- [x] 在当前外部条件未到位状态下完整运行刷新入口，确认 `7 blocked / 0 armed`、bridge source-bound current、manifest current
- **状态：** complete

### 阶段 117：工程分析链路架构解耦与证据门控重构
- [ ] 审计并拆分当前 `agent_graph` 中的工具编排、证据判定、候选生成、后台任务调度和 Markdown 渲染职责
- [x] 建立可机读的候选决策第一层：`CandidateDecision` 独立授权候选生成；身份/目标门控失败时评分工具与渲染层均不得输出候选行
- [ ] 扩展可机读的证据状态与决策输出边界：工具只产出来源化事实；渲染层不得补推理或升级状态
- [ ] 将预测模型元数据、实验结构观测值和动态/稳定性结论分层，杜绝字段语义跨层解释
- [x] 将异步任务收据与终态科学证据分离；`submitted/running` 及伪完成 payload 不得参与本轮报告 claim/candidate 决策
- [x] 建立异步任务终态后的显式重算决策入口：认证用户只能用本人任务构建终态证据快照；轮询或任务完成绝不自动改写既有报告
- [x] 将已授权的证据快照持久化为不可变 `analysis_evidence_snapshots`；仅 `recompute_ready` 可写入，旧报告仍不覆盖
- [ ] 将快照接入持久化的分析/报告修订对象，并在新修订中重新执行 CandidateDecision（不能覆盖旧报告）
- [ ] 以 SWISS-MODEL 194 aa 输入为架构回归样本，验证无身份/口袋/实验依据时不生成具体替换建议，并完成线上黑盒验证
- [x] 完成专业工具部署/许可初筛，建立 `open_local`、`open_data_restricted`、`academic_or_commercial_license`、`external_service_only` 分类；未完成许可与 runtime receipt 的工具不得放行候选
- **状态：** in_progress

## 关键问题
1. 现有认证与会话实现是否已具备跨模块一致性和可恢复性。
2. 工具注册、代理转发、前端 API 调用是否存在不利于后续扩展的耦合点。
3. 哪些修复必须保持最小侵入，哪些需要抽象层来提升容错率。

## 已做决策
| 决策 | 理由 |
|------|------|
| 先建立持久化规划文件再做全项目审计 | 降低复杂任务上下文丢失和误修风险 |
| 优先做低侵入、可回归验证的修复 | 满足“谨慎修复、不影响项目”的要求 |
| 先读关键链路再决定是否继续扩大改动面 | 避免过早引入架构性扰动 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| 后端首次上线因 `Request | None` 依赖签名触发 FastAPI 启动失败 | 1 | 调整依赖函数签名并重新部署 |
| 整项目深度测试阶段发现匿名 `/wiki/home` 先触发 Outline 前端 401/异常再跳登录 | 2 | 先用 live 黑盒与日志确认现象，暂列为阶段 4 未闭环项 |
| 现有 Python 测试集一度无法执行 | 2 | 后续使用项目虚拟环境恢复执行，当前后端全量测试已通过 |
| 主机 Python 无法直接导入 backend 运行真实 MD 验证 | 1 | 改为容器内验证 `gromacs_md` 新签名和运行态返回 |
| 全量后端测试发现 fallback planner 与 ProtSSN 错误文案回归 | 1 | 修复 fallback tool discover 与错误文案来源后，全量测试通过 |
| 审计 CSV 导出测试首次因 CSV 内部引号转义导致断言假失败 | 1 | 改为断言脱敏语义而非未转义 JSON 字符串 |
| 部署包脚本首次按黑名单全仓遍历导致误包含 Venus 项目资料、`.venv` 等大型内容 | 2 | 改为根目录白名单加路径片段排除，dry-run 收敛到 365 个文件、约 3.4MB |
| 旧备份脚本生成 PostgreSQL custom dump 却使用 `.sql.gz` 扩展名，恢复脚本按 `gunzip | psql` 处理 | 1 | 统一新备份为 `.dump + pg_restore`，恢复脚本兼容旧 `.sql.gz` 纯 SQL |
| 线上测试要求包含敏感云凭据 | 1 | 不在计划、日志或回复中复述密钥；需要远端操作时优先使用受控脚本、避免命令行输出密钥 |
| ECS SSH 同步失败 | 1 | 远端 SSHD 当前不接受密码认证，只允许 publickey/gssapi；需通过阿里云 Workbench 执行同步命令或配置 SSH key 后重试 |
| 云助手热修复脚本首次构造失败 | 1 | 本地 Python 脚本内嵌三引号冲突，改用不冲突的 raw triple double 字符串后成功 |
| 远端同步 smoke 脚本后执行 node 失败 | 1 | ECS 宿主机没有 node；不影响服务，改用本机对公网入口运行增强版 HTTP smoke |
| 前端 lint 失败 | 1 | 失败来自大量既有 lint 债，包括 Fast Refresh、React hooks、any、未使用变量；本轮改动的 smoke 脚本已通过 `node --check` 和运行验证 |
| 升级 readiness 首次未识别 Alembic 类型标注赋值 | 1 | 增加 `ast.AnnAssign` 解析，当前能识别 5 个迁移和单一 head |
| ECS 前端 Docker build 首次失败 | 1 | 漏同步 `AnnotationBundleCard.tsx`，补同步后 Docker build 通过 |
| ECS compose 重启首次未带 env file | 1 | `docker compose` 插值变量为空导致 Outline unhealthy；改用 `--env-file docker/.env --env-file docker/.env.deploy-data --env-file docker/.env.aliyun.app` 恢复 backend/outline/nginx/frontend healthy |
| 升级 readiness 因前端版本仍为 `0.0.0` 持续 warning | 1 | 新增根 `VERSION` 文件，前端 package/lockfile 同步为 `0.1.0`，后端 health 读取统一版本 |
| restore drill dry-run 输出中使用字面量 `\t` 而非真实 tab | 1 | 改为 `printf` 输出，保持机器可读格式一致 |
| 真实备份校验首次失败，原因是 verify 脚本进入 docker 目录后相对路径失效 | 1 | 将备份路径解析为绝对路径后重跑校验通过 |
| ligand artifact owner 测试首次读取 `tool_name` 字段失败 | 1 | 在 `get_tool_artifact_owner()` 返回中补 `tool_name` 兼容别名，保留原 `tool` 字段 |
| 前端构建因 JSX 文本 `->` 被解析为标签符号失败 | 1 | 改为 JSX 表达式 `{'->'}` 后构建通过 |
| PDB lipase overlay 首次构建因本地 `AnalysisResult` 未声明 `lipaseEvidenceContext` 失败 | 1 | 为 PDB 页面本地分析结果类型补字段 |
| PDB lipase overlay 第二次构建因 `null` 传入卡片可选字段失败 | 1 | 合并传参时将空值归一为 `undefined` |
| 新增 lipase curation Alembic 迁移首次挂到旧 head，upgrade readiness 出现 2 个 warning | 1 | 将迁移 `down_revision` 改到当前 head `b9a4c2d7e8f1` 后恢复单 head |
| 编译命令首次使用错误 Alembic 相对路径 `../alembic/...` | 1 | 改从项目根执行 `python3 -m py_compile backend/alembic/...` |
| Matvenus 真实会话读取首次只拿到 `/session/{id}` 元数据 | 1 | 从前端 bundle 定位 `/session/{id}/stream-events`，读取完整事件流 |
| Python `cryptography` 在主机 Python 3.14 缺 `_cffi_backend` | 1 | 改为标准库 PBKDF2 + 系统 `openssl` 子进程解密 Chrome cookie |
| Chrome 新版 cookie 解密后带 host hash 前缀导致 UTF-8 解码失败 | 1 | 兼容 SHA256(host_key) 32 字节前缀后再解码 |
| Matvenus 提取器初版不识别 `stream_events` | 1 | 增加按 `msg_id` 聚合 `stream_events` 的解析逻辑和回归测试 |
| 定向 pytest 首次使用错误类名 `TestConfigValidation` | 1 | 定位实际类名 `TestRequirementsFiles` 后用正确节点重跑通过 |
| 并行运行后端全量 pytest 与验收/发布编排时 SQLite 测试库被多个进程同时 drop/create，出现缺表/表已存在假失败 | 2 | 改为串行执行数据库相关 pytest；后续若要并行需隔离测试 DB |
| `local_annotations` 导入真实 `deploy_data/annotations` 时 taxonomy 字段 `kingdom/class_name/order_name/species` 与模型字段不匹配 | 1 | 在 `AnnotationDatasetService` 增加 taxonomy alias 归一化，并让 bundled fixture 测试显式固定数据源 |
| ECS backend 镜像首次导入 `app.main` 失败，缺 `/app/oidc_private_key.pem` | 1 | OIDC key 改为 runtime secret 挂载，代码支持 `/run/secrets` 和显式路径，ECS 生成 shared/secrets key 后 smoke 通过 |
| 线上聊天表格黑盒验证首次等待不到 `<table>` | 1 | 页面实际返回欢迎语而非 Markdown 表格，改以本地组件 smoke 验证渲染层，线上用标准 smoke/live smoke 验证部署健康 |
| 代码走查发现下载 HTML 报告直接拼接 LLM/工具文本存在 XSS 风险 | 1 | 为 `report.ts` 和 `conversation-report.ts` 增加 HTML/属性转义，补恶意 payload 检查、定向 eslint、构建和线上 smoke |
| 线上黑盒发现 benchmark bundle 下载 URL 不支持 `HEAD` | 1 | 记录为低风险待办；当前 `GET` range 返回 206，不影响页面下载 |
| 本轮夜间 live gate 初次本机运行失败，Node/Python 访问公网返回 `EPERM`/空响应 | 1 | 提升网络权限后重跑，HTTP smoke、benchmark HEAD/Range 和 nightly readonly gate 均通过 |
| ECS 宿主机 `python3` 编译 `check_upgrade_readiness.py` 失败，因 `future annotations` 不兼容 Python 3.6 | 1 | 将脚本降级为 Python 3.6 兼容：移除 dataclass/PEP585/capture_output/text，远端 `py_compile` 通过 |
| 阶段 26 首次批量补丁因函数 docstring 与预期上下文不一致而未应用 | 1 | 重新读取精确行号后拆成小块补丁，业务代码修改成功 |
| 阶段 26 首轮 agent 定向测试 2 项失败 | 1 | 模型自身文献依据误触发 live search；具名蛋白文献检索缺 target resolve。分别增加 meta fail-closed 与 `sequence_search + literature_live_search` 组合计划 |
| 阶段 26 首次真实联网 smoke 使用了错误的虚拟环境相对路径 | 1 | 从 backend 目录改用 `./.venv/bin/python` 后成功执行；沙箱内按预期 blocked，授权的真实网络环境 3/3 live |
| 阶段 27 首轮后端全量回归 1 项失败 | 1 | `test_md_batch_replicate_summary_attaches_lipase_evidence` 得到 evidence_count=0；暂停公网发布，定位测试数据路径/证据挂载回归后重跑全量 |
| 阶段 27 ECS 首次 backend 镜像构建失败 | 1 | Docker Hub 拉取 `python:3.12-slim` 元数据返回 `insufficient_scope`；前端镜像已构建，`set -e` 阻止服务重启，线上旧容器仍健康。改查本地镜像缓存/离线构建路径，不重复同一拉取 |
| 阶段 27 构建失败记录补丁首次上下文不匹配 | 1 | 按实际阶段和错误表行号拆分补丁后更新规划记录 |
| 阶段 27 Playwright CLI 启动失败 | 1 | CLI 默认要求 `/Applications/Google Chrome.app`，本机无该路径；按项目既有 standalone Playwright Chromium live-smoke 体系执行 |
| 阶段 27 专项浏览器 smoke 首次失败 | 1 | Playwright 对持续 SSE 调用 `response.text()` 报 `Network.getResponseBody: No data found`；改用 POST 请求计数、流结束 UI、工具卡与最终答复渲染次数验收 |
| 阶段 27 发布包本地 checksum 首次校验目录错误 | 1 | checksum sidecar 使用 bundle basename；切到 `dist/packages` 后校验通过并核对关键文件清单 |
| 阶段 27 临时账号清理命令引号冲突 | 3 | 两次 Python `-c` 引号/复合语句失败、一次 JS `btoa` 不可用；最终使用本地 ASCII Base64 编码脚本，2 个临时账号均禁用 |
| 阶段 27 最终 nginx 状态统计首次 shell 引号失败/二次误匹配响应字节 | 2 | 避免嵌套 awk 引号，并把 grep 收紧为请求引号后的 HTTP 状态字段；真实 499/5xx=0 |
| 阶段 36 新发布包 checksum 首次在项目根校验失败 | 1 | checksum sidecar 使用包文件 basename；切到 `dist/packages` 后 `shasum -a 256 -c` 通过 |
| 阶段 36 包内容抽查首次调用不存在的 `scripts/inspect_deploy_bundle.py` | 1 | 改用 Python 标准库 `tarfile` 只读检查，结果 `entries=516 forbidden=0` |
| 阶段 36 远端 checksum 首次使用 `shasum` 失败 | 1 | ECS 为 Linux 环境，改用 `sha256sum -c` 后通过 |
| 阶段 89 前端构建首次失败，反馈记录 ID 为 number 不能直接 `localeCompare` | 1 | fingerprint 生成时先 `String(record.id)` 再排序拼接 |
| 阶段 94 remaining backlog 回归首次失败，旧测试仍期望 8 张 ticket | 1 | `remote_pytest_runner` 改为 ready 后 external tickets 应为 7，更新旧断言 |
| 阶段 94 operator packet manifest check 首次 stale | 1 | 重新生成 manifest 后 freshness check 恢复 current |

### 阶段 118：55 工具科学组合深度调研
- [x] 审计 55 工具注册、能力合同、输入输出和异步边界
- [x] 对照酶工程人工流程建立 identity/structure/objective/candidate/validation 证据链
- [x] 识别科学风险：工具冗余、证据冲突、代理结果升级、失败降级和许可边界
- [x] 输出深度调研报告和下一阶段 typed-DAG planner 修复清单
- **状态：** complete for first two implementation layers; typed-DAG expansion remains future work

### 阶段 119：KWB-EnzymeDesigner 五头训练升级
- [x] 深度审计标签、特征、预训练、训练入口、评测和生产门禁
- [x] 建立 `reports/model_status.json` 唯一状态事实源，分离规则、预训练、研究和生产状态
- [x] 以 TDD 实现共享编码器、五个独立 head 和缺失标签 mask 的研究训练内核
- [x] 将生产入口接入真实训练内核，同时保持 production/execution/dataset 三重 fail-closed
- [x] 用 6 行真实 activity-risk 导入标签执行 research smoke，并保存 checkpoint/hash 回执
- [x] 复核 12,830 条连续预训练资产，保持 `blocked_pretraining_only`
- [x] 运行新测试、预训练回归、Python 编译和 scoped diff check
- [ ] 为每个 head 补足至少 100 样本、3 个显式重复、10 个独立 group 后执行正式训练
- **状态：** local training framework complete; formal five-head training blocked by real-label thresholds

## 备注
- 仅将外部不可信内容写入 findings.md，不写入本计划。
- 每完成一个阶段立即更新状态和 progress.md。
- 当前阶段重点：阶段 6 已补上 `/pdb` 结构 overlay 的交互解释层与连续区段精度修正，浏览器 smoke 已通过，结构 smoke 现同时具备 live harness、完整 demo 基线、自动回归、就绪度脚本与 `deploy_data` 标准接入层；同时已新增阿里云托管拓扑的 `app/gpu` 分角色部署资产。产品化待建清单已全部纳入阶段 6，第一层已完成数据就绪度 API/页面、MD 结构化解释和任务审计摘要；第二层已完成更新记录、MD 协议模板、运维摘要只读入口，并已把 MD 协议模板接入 `/pdb` 真实任务提交；MD 报告已补证据等级、质量门控、复核建议、协议 review、缺失能量/氢键/XVG/EDR 证据判读；任务审计已落库并支持管理员导出、耗时统计、慢任务标记和失败分类；ops summary 已具备健康检查、告警列表、Redis 队列和 Celery worker 运行态；用户角色、管理员用户管理、项目级 ACL、项目文件/Wiki/发布 ACL、聊天绑定 ACL、数据资产管理后台和 `/admin` 管理入口已建立；封装预检、白名单部署包、初始化向导、备份恢复、备份校验、临时库恢复演练、真实备份恢复演练、升级编排脚本、只读回滚计划、统一版本号和第一版手册已可用。Matvenus 真实会话已读取并沉淀为复盘稿、样式/方法设计文档、日报和 stream_events 提取器。剩余待建项已有统一只读 readiness 总控，当前显示 `real_deploy_data` ready；阿里云 ligand worker 已上线并通过真实 topology 小分子 smoke；GPU 长任务容量、admin 登录态截图和维护窗口演练仍需外部条件。剩余重点是真实 GPU/MD 长任务运行态、admin 登录态截图、真实回滚/异地备份/外部存储恢复演练。
