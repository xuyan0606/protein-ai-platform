# 项目经验记忆：酶蛋白 AI 平台

更新时间：2026-07-09

## 1. 项目定位

本项目是“酶蛋白 AI 平台”，核心路径包括：

- 蛋白结构数据：PDB、AlphaFold、SIFTS、Foldseek DB、annotations。
- PDB 页面能力：结构上传、结构检索、残基映射、annotation bundle、MD 提交与结果查看。
- MD 能力：GROMACS 真实流水线、artifact manifest、XVG/CSV 解析、结果解释、replicate ranking。
- 产品化能力：用户/项目 ACL、管理后台、任务审计、运维监控、部署包、备份恢复、阿里云托管部署。
- 底物/配体能力：2D SDF 预处理、3D 构象生成、PDBQT、Vina docking、小分子 topology、复合物 MD。

核心原则：真实能力必须真实执行；缺工具链时返回明确 `blocked/unavailable`，不能用模拟结果冒充科学计算。

## 1.1 酶改造分析默认流程

用户已在 2026-07-29 明确：以后平台流程按“AI酶改造平台：人工分析流程（简版 v1）”分析。

平台酶改造任务不得直接根据用户目标给突变建议，应先认识这条酶，再按目标选择分析路径，最后整合工具和证据形成结果。默认主流程：

1. 输入整理
2. 基础核验
3. 结构获取
4. 最小基础画像
5. 目标识别与任务拆解
6. 目标相关深分析
7. 证据检索与工具执行
8. 候选策略生成
9. 结果输出

第一批优先跑通子流程为热稳定性和底物特异性。缺少结构、底物、编号映射或工具运行环境时，应输出结构状态或 blocked 原因，不能伪造结果。

## 2. 沟通与执行经验

用户常用“继续”“全部开始”表示希望自动推进待建清单，不希望停在方案讨论。正确做法：

- 先读 `task_plan.md`、`findings.md`、`progress.md`。
- 明确当前可做项和受阻项。
- 能做的直接实现、测试、记录。
- 不能做的要保守阻断，并写清楚缺什么、下一步要什么环境。

用户要求“0 bug”“仔细测试、黑盒白盒测试”时，不要承诺绝对 0 bug。应执行针对性测试、主回归、构建、验收，并明确残余边界。

用户要求“写入记忆”时，不能依赖模型全局记忆；应写入项目内持久文件：

- `AGENTS.md`：后续 agent 的短记忆和硬边界。
- `docs/project-experience-memory.md`：详细经验。
- `findings.md`：结构化发现。
- `progress.md`：执行日志。
- `task_plan.md`：待建清单状态。

## 3. 环境与工具边界

当前本机情况：

- MacBook Pro M1 Pro，16GB。
- 没有 `gmx` / `gmx_mpi`。
- 没有 `obabel`。
- 没有 `vina`。
- 没有 `acpype`。
- 没有 `antechamber`。
- backend `.venv` 中未检测到 `rdkit`。

因此本机可做：

- 代码开发。
- 单元测试。
- 前端 build。
- release acceptance。
- smoke script。
- 工具缺失时的受控 blocked 合同。
- 文档、部署模板、Dockerfile、compose 定义。

本机不可声称：

- 真实 GROMACS topology live gate 通过。
- 真实 WT/mutant 多 replicate 长 MD 完成。
- 真实 Vina docking 完成。
- 真实 ACPYPE/Antechamber 小分子 topology 完成。
- 真实 GPU 部署完成。

## 4. 端口与图像约束

端口：

- Codex 只能用 `4200-4299`。
- 当前项目入口默认 `http://localhost:4200`。
- 不要占用 Hermes `4000-4099`、Claude Code `4100-4199`、Open Claw `4300-4399`。

图像：

- 不要调用 `view_image`。
- 需要图片信息时用：

```bash
sips -g all <image_path>
file <image_path>
mdls <image_path>
ls -lh <image_path>
```

## 5. 真实数据层经验

用户已明确真实数据层顺序：

```text
PDB -> AlphaFold -> Foldseek DB
```

不要把 PostgreSQL、Redis、MinIO、ChromaDB、Celery Worker 理解成可替代 PDB/AlphaFold/Foldseek DB。它们是平台基础设施：

- PostgreSQL：业务数据、用户、项目、任务审计。
- Redis：队列、缓存。
- MinIO/OSS：文件和 artifact。
- ChromaDB：向量检索。
- Celery Worker：异步任务执行。
- PDB/AlphaFold/Foldseek DB：结构数据源和结构检索库。

真实数据已有路径约定：

- `deploy_data/pdb`
- `deploy_data/alphafold`
- `deploy_data/foldseek`
- `deploy_data/sifts`
- `deploy_data/annotations`
- `deploy_data/smoke`

真实数据更新已有脚本/入口：

- `scripts/run_deploy_data_update.py`
- `scripts/check_deploy_data.py`
- `scripts/refresh_live_deploy_data.py`
- `scripts/download_rcsb_structures.py`
- `scripts/download_alphafold_models.py`
- `scripts/download_sifts_mappings.py`
- `scripts/build_foldseek_db.py`

## 6. MD/GROMACS 经验

已经完成的重要能力：

- `gromacs_md` 从占位切换为真实 GROMACS 管线接口。
- 没有 GROMACS 时明确返回 `GROMACS_NOT_INSTALLED/unavailable`。
- 已有 artifact manifest，把 trajectory、analysis、topology、parameters、logs 分类。
- 已有 energy/hbond XVG 解析和 CSV 导出。
- 已有 protocol review、missing evidence、quality gates、replicate consistency。
- 已有 mutant prepare、topology validate、replicate submit、replicate summary。

必须遵守：

- 真实长 MD 等用户提供阿里云 NVIDIA GPU/GROMACS 服务器后再做。
- 本机不继续尝试真实 WT/mutant 多 replicate 长任务。
- `make backend-md-topology-live-gate` 只有在安装真实 GROMACS 的节点上才应通过。

等待服务器后执行顺序：

```text
确认 NVIDIA driver / CUDA / NVIDIA Container Toolkit
-> 确认 GROMACS GPU 版
-> make backend-md-topology-live-gate
-> mutant prepare + validate_topology=true
-> require_mutant_topology_validation=true 提交 WT/mutant replicate
-> /api/tools/md/replicates/{batch_id}/summary
-> 真实 batch ranking report
```

## 7. 2D SDF / 配体链路经验

用户提供底物：

```text
/Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/Structure2D_COMPOUND_CID_5478883.sdf
```

已确认：

- 文件存在。
- SDF header 包含 `2D`。
- V2000。
- 单分子记录。
- `atom_count=111`。
- `bond_count=110`。
- 元素组成：C 34、H 63、N 5、O 9。
- 所有原子 Z 坐标为 `0.0`。
- `is_2d_sdf=true`。

科学结论：

- 2D SDF 只是平面结构式，不是可对接或可 MD 的 3D 构象。
- 不能直接进 Vina。
- 不能直接和 3D 蛋白一起进 GROMACS。
- ChimeraX 只适合看结构、标 pocket box，不适合批量 2D -> 3D 构象生成。

必须流水线：

```text
2D SDF
-> OpenBabel/RDKit 生成 3D + 加氢 + 几何优化
-> 质子化/电荷分配
-> PDBQT
-> AutoDock Vina docking
-> 酶-底物 3D 复合物
-> ACPYPE/Antechamber 生成 GAFF2/ITP
-> GROMACS 体系组装、溶剂化、平衡、生产 MD
```

已新增能力：

- `backend/scripts/smoke_ligand_toolchain.py`
- `make backend-ligand-toolchain-smoke`
- `make backend-ligand-toolchain-live-gate`
- `backend/app/tools/ligand_preprocess.py`
- `ligand_cpu` 队列
- `docker/Dockerfile.ligand-worker`
- `docs/manuals/ligand-docking-md-workflow.md`

当前真实状态：

- `ligand_preprocess` 对真实 SDF 返回 `blocked`。
- `preflight` 缺：
  - `conformer_generation`
  - `pdbqt_preparation`
  - `vina_docking`
  - `ligand_topology`
  - `gromacs_md`
- `generate_3d` 阻断原因：`openbabel_not_installed`。

## 8. Docker / 阿里云部署经验

当前目标拓扑：

```text
ECS-App-01 / ECS-App-02
  -> Nginx / Frontend / Backend / CPU Worker / Outline / ChromaDB
  -> RDS PostgreSQL
  -> Cloud Redis
  -> OSS

ECS-GPU-01
  -> md-worker      queue=md_cpu
  -> ligand-worker  queue=ligand_cpu
  -> same RDS / Redis / OSS
```

重要边界：

- 阿里云 GPU 服务器尚未提供。
- 不要创建真实 `docker/.env.aliyun.gpu`。
- 不要启动 `docker-up-aliyun-gpu`。
- 只保留 `.env.aliyun.gpu.example` 模板和 compose/Dockerfile 定义。

部署资产：

- `docker/docker-compose.aliyun-app.yml`
- `docker/docker-compose.aliyun-gpu.yml`
- `docker/.env.aliyun.app.example`
- `docker/.env.aliyun.gpu.example`
- `docker/Dockerfile.ligand-worker`
- `deploy-aliyun.sh`
- `docs/aliyun-managed-deployment.md`

安全经验：

- `docker compose config` 会展开 `.env` 明文，可能泄露 API key、DB 密码、OSS key。
- Makefile 的 `docker-config-*` 目标应使用 `config --quiet`。
- 不要把 compose 渲染出的明文配置贴到回复或日志里。

## 9. 测试经验

常用回归：

```bash
cd backend && .venv/bin/pytest tests/test_config_validation.py -q
cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_ops_api.py tests/test_config_validation.py -q
cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q
cd frontend && npm run build
python3 scripts/run_release_acceptance.py
make backend-ligand-toolchain-smoke
make backend-md-topology-smoke
```

注意：

- 后端主回归和 release acceptance 要串行跑。
- 不要并行跑会共享 SQLite 测试库的 pytest 命令。
- 前端 3Dmol 已改为本地 vendor runtime 加载；build 不应再出现 3Dmol `eval` 或大 chunk warning。
- release acceptance 默认会跳过 backup verify，这是已知行为；不要说真实异地备份已完成。

## 10. 权限、审计、运维经验

已建立：

- 用户角色。
- 管理员用户管理。
- 项目级 ACL。
- 项目文件/Wiki/发布 ACL。
- 聊天绑定 ACL。
- 组织/团队权限模型。
- 任务审计落库。
- 管理员审计查询/CSV 导出。
- 运维 summary。
- Redis/队列/Celery worker 监控。
- 慢请求、失败趋势、外部通知 dispatch。

审计脱敏：

- `pdb_data` 已脱敏。
- `sdf_data` 已脱敏。
- token/password/secret 类字段必须脱敏。

## 11. 当前待建重点

仍待建或等待外部条件：

- 真实 PDB / AlphaFold / Foldseek DB live 数据导入和定期更新。
- OpenBabel/RDKit/Vina/ACPYPE/AmberTools 的真实容器构建与 live gate。
- 真实 PDBQT 阶段。
- 真实 Vina docking 阶段。
- 真实 ligand topology 阶段。
- 阿里云 GPU/GROMACS 服务器到位后的真实 topology live gate。
- 真实 WT/mutant replicate 长任务和 ranking report。
- live 服务上的真实浏览器回归、MD 黑盒长任务、OSS/MinIO 端到端下载兼容测试。
- 真实维护窗口回滚演练、异地备份演练、外部存储恢复验证。
- 真实浏览器截图补齐。

本机已补：

- 截图版操作手册文字占位版：`docs/manuals/screenshot-operation-placeholder-manual.md`。
- 已执行演练记录归档模板：`docs/manuals/drill-record-template.md` 已覆盖维护窗口边界、截图归档、lipase curation 发布、回滚和异地备份专项字段。

注意：

- 当前仍没有真实截图文件。
- 当前仍没有执行真实维护窗口回滚演练。
- 当前仍没有执行真实异地备份恢复演练。
- Lipase curation 平台 publish 不等于直接写原始 `/Users/xuyan/lipase-db/lipase.db`；staged SQLite 校验和生产替换必须维护窗口执行。

## 12. 对后续 agent 的执行建议

如果用户说“继续”：

1. 先读 `task_plan.md` 当前未完成项。
2. 优先做不依赖 GPU/外部服务器的代码、测试、文档、封装。
3. 遇到真实工具链缺失，返回 blocked 合同，不伪造结果。
4. 每完成一批，更新 `task_plan.md`、`findings.md`、`progress.md`。
5. 跑针对性测试和必要主回归。
6. 最终回复只说实际完成和实际测试结果。

如果用户提供阿里云 GPU 服务器：

1. 不要先跑长 MD。
2. 先确认驱动、CUDA、NVIDIA Container Toolkit。
3. 再确认 GROMACS/OpenBabel/Vina/ACPYPE/AmberTools。
4. 再跑 live gate。
5. 最后才提交真实长任务。

## 13. 2026-07-18 线上状态唤醒记录

触发词：

- 用户下次说“酶蛋白AI平台”时，先读取本文件、`progress.md`、`findings.md`、`task_plan.md`，再继续。

当前线上入口：

- 公网 IP：`http://120.27.108.138`
- 主要页面：
  - `/login`
  - `/chat/agent`
  - `/data`
  - `/kb`
  - `/benchmarks/venus-15b`

当前线上 release：

- 最新部署 release：`20260718T090825Z-25679eb`
- 线上前端 bundle：`assets/index-B3VXmsvH.js`
- 已重建并重启：`frontend`、`nginx`

当前服务健康状态：

- backend healthy
- frontend healthy
- nginx healthy
- worker healthy
- ligand-worker healthy
- chromadb healthy
- outline healthy

账号与隔离状态：

- 4 个普通研究员账号已建立并设为 `researcher`。
- 普通账号 admin API 返回 403。
- 用户隔离已验证：
  - 会话列表隔离。
  - 会话详情隔离。
  - 项目列表隔离。
  - 项目详情隔离。
- `admin`、`kwb01`、`kwb02`、`kwb03`、`kwb04` 当前 `/api/conversations` 均为 0 条。
- 2026-07-18 已清理 14 条上线测试 chat conversations。
- 清理前备份在 ECS backend 容器内：`/tmp/protein-ai-chat-cleanup-20260718T090703Z.json`。
- 不要把用户密码写入任何文件或回复。

`/chat/agent` 已修复内容：

- 前端用户域状态隔离：
  - `ownerUserId`
  - `resetUserScopedState()`
  - auth 用户切换时清空聊天状态
  - `protein-ai:user-scoped-reset`
- 登录/注册前会先清本地 token、清当前会话 ID，并请求 `/auth/logout` 清服务端 cookie。
- 退出登录会等待服务端 cookie 清理完成后再跳转。
- 旧 `currentConversationId` 返回 404 时，前端会移除旧列表项。
- 客户端状态版本：`20260718-user-scope-v3`

数据资产状态：

- 线上 RDS 已导入结构化酶蛋白数据：
  - enzyme records：280036
  - domain 数据：725449 行
  - PDB structures：113836
  - AlphaFold structures：14527
- `/data` 已恢复主要统计。
- Lipase DB 仍需确认线上 `LIPASE_DB_PATH` 指向实际存在的 `lipase.db`。

模型与前端显示状态：

- 模型展示按要求改为：
  - GPT-5.5
  - GPT-5.6
  - GPT-5.6 sol
- 不再显示不需要的供应商字样。
- 聊天 Markdown 表格流式显示已修复。

OSS 状态：

- 阿里云 OSS env 已在线上 current release 生效。
- OSS runtime smoke 已通过：写入、读回校验、删除。
- 不要在日志、文档、回复中输出 OSS AccessKey。

测试验收状态：

- `cd frontend && npm run build` 通过，前端构建告警已清除。
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/http-smoke.mjs` 通过。
- `scripts/smoke_user_isolation.py --base-url http://120.27.108.138` 通过。
- `frontend/tests/live-user-switch-isolation.mjs` 通过。
- `FRONTEND_BASE_URL=http://120.27.108.138 python3 scripts/run_release_acceptance.py` 当前口径为通过并保留人工门禁：
  - 0 failed
  - 3 manual_required
  - 1 skipped
- manual_required 均是需要维护窗口或恢复目标的真实演练门禁，不是代码失败。

仍待办：

- 正式域名和 HTTPS 证书绑定。
- Lipase DB 线上路径一致性修复。
- GPU/长任务 worker 容量规划。
- OpenBabel/RDKit/Vina/ACPYPE/AmberTools/GROMACS 真实 runtime 完整验证。
- 生产回滚演练，需要维护窗口 ID 和明确授权。
- 异地备份恢复演练，需要异地备份目标和独立恢复目标。
- 外部存储恢复验证，需要备份引用和 shadow restore 目标。
- `/data` 页面首屏统计加载速度继续优化。

下次恢复建议：

1. 不要重新问账号密码。
2. 不要从零开始部署。
3. 先检查线上 health 和当前 bundle。
4. 如果用户反馈 `/chat/agent` 仍有旧内容，先查 `/api/conversations` 对当前登录账号返回值，再判断是否是浏览器旧标签页、cookie 或账号自身历史数据。
5. 继续开发时先跑针对性测试，再跑必要发布验收。

## 2026-09-03 五头模型训练记忆

- 唯一当前模型状态入口为 `AI大模型/reports/model_status.json`；不要再从单个旧 readiness 报告推断整体模型状态。
- 无标签连续预训练 v6 已覆盖 12,830 条序列，但始终是 pretraining-only，不得用于监督或生产声明。
- 五头真实标签当前为 0/0/6/0/0；activity-risk 的 6 行只有 2 个 mutation group、0 个显式重复。
- `AI大模型/scripts/train_research_multitask.py` 是共享 encoder + 独立 head 的研究训练入口；`smoke` 只验证代码路径，`research` 保持每头独立阈值。
- `AI大模型/scripts/train_production_multitask.py` 需要 production gate、execution contract 和五头数据集同时就绪；当前正确结果是 blocked。
- 当前 research smoke checkpoint 不能接入 `backend/app/tools/kwb_enzyme_designer.py`，不能改 production gate，也不能用于客户交付。
- 研究训练数值特征必须遵守 exclusion contract：不得把 `activity_relative_to_wt`、`activity_risk_label`、`label_value`、`label_decision`、`label_ddg`、`label_stability_delta_tm_c`、`substrate_fit_label`、`assay_success` 写入 feature vector；显式 `features` 字典也要过滤这些键。回执/checkpoint 应带 `feature_schema`、`excluded_feature_fields`、`feature_schema_sha256`。
- smoke `final_loss` 只证明路径可跑，不是性能指标；不得据此放松 production gate 或模型 claim。
