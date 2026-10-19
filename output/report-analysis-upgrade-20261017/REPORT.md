# 报告短板优化验收报告

日期：2026-10-17
工作树：`4track-upgrade-20260627`
状态：代码优化完成，未发布线上

## 本轮完成

1. 深度 PDB 分析计划现在会在结构解析、编号映射和位点特征之后执行：
   - `ligand_contact_analysis`
   - `structure_pocket_interface_analysis`
2. 两个结构工具支持 `pdb_object_name`，可直接读取上传对象，不再因缺少内联 `pdb_data` 而返回 `MISSING_PDB`。
3. 报告输出新增配体实例、残基接触、口袋残基、通道线索和链界面摘要。
4. 所有几何结果明确标记 `GEOMETRY_ONLY`，报告保留“不能证明结合能、催化机制、Tm 或实验收益”的边界。
5. 前端工具卡可展示上述结构证据、状态和限制说明，沿用现有布局和样式。
6. BLAST 终态语义补齐：`waiting`、`failed`、`completed_no_hit`、`completed_with_hits` 分开处理；等待和失败不会渲染成“无同源命中”。
   报告正文现在同时显示 `evidence_status` 和对应判读说明。
7. 证据契约、报告 manifest、发布 provenance 和版本治理文件已纳入工作树；生产模型配置保持 `gpt-6-sol`。
8. 湿实验计划新增 `wet_lab_plan_v1` 结构化合同：构建体矩阵、表达/纯化 QC、天然相关底物动力学、pH/温度曲线、Tm/热失活/储存稳定性和 Go/Watch/No-Go 均明确标为 `planned`；没有直接实验数据时不会渲染成已完成结果。
9. 阿里云部署入口已接入 release manifest：默认要求 digest 固定镜像，验证当前 Compose 文件绑定，manifest 发布禁止重新 build，启动后核对服务的 `Config.Image` 和 `RepoDigests`。
10. 新增报告版本一致性门：release manifest 可绑定报告 schema `1.1`、湿实验 schema `wet_lab_plan_v1` 和前端构建 hash；就绪检查会在 manifest 存在时校验这些内容，并继续核对生产模型为 `gpt-6-sol`。
11. 修复 manifest API 兼容性：底层 `build_manifest()` 在未传前端构建产物时仍可生成基础 provenance manifest；真实发布 CLI 仍默认绑定 `frontend/dist` 并写入 alignment。
12. 修复对齐门诊断：schema 或前端 hash 漂移不会被基础 manifest 校验提前吞掉，会同时报告具体漂移项；基础 provenance 结构错误仍 fail-closed。
13. `build_release_worktree_manifest.py` 现在同时输出 `release_alignment` 摘要；缺少正式 manifest 时明确为 `manual_required`，并保留脏文件、网络、破坏性操作和密钥输出边界。
14. 新增版本门操作手册和审计记录，统一说明 manifest 生成、检查顺序、失败处理和当前未发布原因。
15. 增加前端证据状态 fixture：`waiting`、`failed`、`not_run`、`computed`、`experimental` 均可在现有工具卡区域区分显示；不调整产品布局和 CSS。
16. 增加 `frontend` 的 `smoke:evidence-status` 命令，便于发布前重复执行证据状态验收。
17. 增加 7DVJ 风格湿实验回归 fixture，强制区分 WT、PDB 构建体 E142A、必要时回补和无酶对照，并验证 β-1,4-mannan、动力学、稳定性和 Go/Watch/No-Go 计划均保持 `planned`，没有实验性结论升级。
18. 增加 BLAST 报告状态纯函数回归，覆盖 `submitted`、`waiting`、`failed`、`completed_no_hit`、`completed_with_hits`，并验证 checked_at、endpoint、database 和 RID 可追溯字段；修复前端 smoke 默认端口与 `vite.smoke.config.ts` 不一致的问题。
19. 将报告版本一致性门接入 `deploy-aliyun.sh` 和 `install_release_bundle.sh`；新增 `--offline` 校验模式，确保不含 `.git` 的发布包在切换 `current` 或启动 Compose 前仍完成 schema、bundle、模型和 rollback 对齐检查。对齐工具也支持传入运行时镜像集合，能检测 digest 漂移。
20. 将报告版本对齐加入 `run_release_acceptance.py`：缺少 manifest 时明确输出 `manual_required`，计划模式只生成待执行命令，不把缺失发布证据误判为通过。
21. 根据线上 Chroma 兼容性证据，将开发、默认和阿里云 Compose 的 Chroma 服务从可变 `latest` 固定到与后端 `chromadb==0.6.3` 对齐的 `chromadb/chroma:0.6.3`，并加入配置回归；已有线上数据卷切换前仍需单独做备份和兼容性验证。

## 验证结果

- Python 编译检查：通过。
- 结构几何、证据契约、manifest、报告质量契约、湿实验合同：`29 passed`。
- 发布 provenance 和部署脚本定向测试：`11 passed`。
- 报告版本一致性测试：`9 passed`，覆盖 Git revision、模型选择、前端 bundle、镜像 digest 和 rollback 漂移。
- release acceptance 对齐门测试：`3 passed`。
- 发布工作树摘要测试：`4 passed`（含版本对齐摘要和敏感信息边界）。
- 前端证据状态 smoke：通过。
- 既有结构功能卡 smoke：通过，完整残基特征下载通过。
- 湿实验合同回归：`4 passed`。
- BLAST 报告状态契约回归：`2 passed`。
- 版本门离线提取包回归：`3 passed`；部署入口回归：`4 passed`。
- release acceptance 对齐门测试：`3 passed`。
- 本轮合并定向回归：`36 passed`（结构、证据、报告、发布、部署和湿实验合同）。
- Python 3.12 报告/策略回归：`213 passed`。
- Python 3.12 结构工具回归：`36 passed`。
- Python 3.12 证据、manifest、报告质量和用户场景回归：`41 passed`。
- Python 3.12 BLAST 状态回归：`19 passed`；此前 API 用例缺少本机 OIDC 测试密钥，已在最终定向回归中通过临时测试密钥补齐验证。
- `scripts/check_upgrade_readiness.py --json` 已验证在无 manifest 时输出两个 `manual_required` 门禁：`release.provenance` 和 `release.alignment`。
- BLAST 状态纯函数/完成无命中测试：`2 passed`；持久化恢复和 API 用例已在最终 Python 3.12 定向回归中通过。
- 前端 `npm run build`：通过。
- `bash -n`、Python 编译检查：通过。

## 当前阻断项

- 本机 Python 3.9 无法导入项目 SQLAlchemy 模型中的 `datetime | None` 标注；项目测试应在 Python 3.12 后端环境执行。
- 项目默认 shell 仍指向 Python 3.9；本轮使用临时 Python 3.12 环境完成可运行的后端回归。
- Docker daemon 当前不可用，无法在本机启动 Python 3.12 测试容器。
- 工作树仍包含大量既有改动，尚未生成可部署的干净 release manifest；因此本轮不执行线上发布。
- 线上只读健康检查通过：`/api/health` 返回 `status=ok`、`tools_registered=60`；当前 `current` 仍指向 `20261016-wiki-probe-v1`，运行服务使用可变标签镜像且没有正式 `RELEASE-MANIFEST.json`，因此未重启生产容器。
- 已执行一次可清理的线上 7DVJ 浏览器上传验收：文件上传、PDB 预分析和策略确认均返回 200，测试会话与上传对象已删除；报告在 180 秒内未出现，任务持续为 `waiting`。线上日志显示 NCBI RID `D5PXTSTP014` 连续轮询未就绪，同时 ChromaDB 报告客户端/服务配置不兼容（`KeyError: '_type'`）。该结果确认当前线上旧 release 仍存在“外部 BLAST 长轮询拖慢完整报告”和文献检索不可用两个运行问题；本分支已加入 PDB 确定性报告快速路径和 BLAST waiting 证据门，但尚未发布。
- BLAST 持久化恢复和 API 用例已在最终 Python 3.12 定向回归中通过；临时测试密钥仅用于本地测试。
- 全仓 `git diff --check` 仍提示三个既有文档 EOF 空行；发布相关代码、测试、Compose 和报告的 scoped 检查通过。
- 默认 Python 3.9 仍会触发 SQLAlchemy `datetime | None` 兼容错误，后端回归需继续使用 Python 3.12 环境。
- 7DVJ 报告场景回归已在 Python 3.12 环境通过；线上复验仍需真实上传和完整服务依赖。
- 浏览器 smoke 需要临时本地测试权限；本轮已在该权限下完成并停止临时 Vite 服务。

## 发布前必须完成

1. 在项目 Python 3.12 环境执行完整后端定向测试和前端验收。
2. 使用不可变镜像 digest 生成并校验 `RELEASE-MANIFEST.json`。
3. 核对线上容器 Git revision、镜像 digest、模型配置和报告 schema 版本。
4. 用 7DVJ 重新执行一次上传结构深度分析，确认报告包含湿实验验证计划、配体接触和几何口袋章节，再进行小流量发布。
5. 生成 manifest 时必须使用 CLI 的 `--frontend-bundle frontend/dist`（默认值），并在发布前执行 `check_upgrade_readiness.py --require-ready`；当前缺少 manifest 时不会误报为可发布。
6. 发布操作员参考 [report-version-release-gate.md](../../docs/manuals/report-version-release-gate.md) 和 [version-management-audit-20261017.md](../version-management-audit-20261017.md) 完成正式 manifest、镜像 digest、回滚目标和 Python 3.12 回归。

## 线上回归补充（2026-10-17）

| 项目 | 结果 | 说明 |
|---|---|---|
| 线上健康接口 | 通过 | `status=ok`，`tools_registered=60` |
| 7DVJ 上传/PDB 预分析 | 通过 | `/api/files/upload`、`/api/pdb/analyze-by-name` 均 200 |
| 策略确认与后台任务提交 | 通过 | SSE/策略确认完成，BLAST task 进入 `waiting` |
| 完整报告 180 秒内返回 | 未通过 | 线上旧 release 等待 NCBI BLAST；会话和文件已清理 |
| Chroma 文献检索 | 降级 | 服务端返回集合配置缺少 `_type`，客户端 `chromadb==0.6.3` 无法解析 |

处理顺序：先发布本分支的确定性 PDB 报告路径，确保 BLAST `submitted/waiting` 不阻塞报告；再将 Chroma 客户端与服务端固定到同一兼容版本并重建或迁移集合，最后重复线上 7DVJ 全流程。

## 报告等待问题复验（2026-10-17）

- 已在 `_synthesize_sc()` 增加上传 PDB 且 BLAST 为 `submitted/waiting` 时的确定性结构报告快速路径；BLAST 任务回执保留在报告中，后续可通过报告修订补入完成的 NCBI 结果。
- 新增回归验证该路径会跳过 LLM 等待，并确保仍显示 BLAST 当前未完成的证据状态。
- Python 3.12 定向回归最终为 `302 passed`，包含报告生成、PDB 用户场景、BLAST 恢复、发布接口和发布 provenance 测试；临时 OIDC 测试密钥仅用于本地测试。
- 先前“两个 API 用例不能启动”的本机限制已在本次复验中排除；本轮选定的测试文件均通过。
- 发布相关代码、Compose、测试和报告的 scoped `git diff --check` 通过；全仓检查仍提示 2 个既有历史文档文件 EOF 空行。追加 Chroma 备份改动后 `check_upgrade_readiness.py --json` 当前为 `blocked`，工作树 dirty（461 个文件）、release manifest 缺失、环境和生产配置门禁未通过。生产仍未发布：干净 release worktree/manifest、镜像 digest 和 Chroma 数据卷恢复兼容性验证仍是上线门槛。

## BLAST 报告状态闭环（2026-10-17）

- 补齐后台任务 `waiting` 和工具 `failed/degraded` 到报告状态段的映射；等待与失败会明确说明“当前不能判定无命中”。
- 报告显示已完成 BLAST 的 `checked_at`、NCBI endpoint 和 RID；等待/提交状态展示任务 ID、队列和状态查询地址。
- 新增五条报告场景回归：`submitted`、`waiting`、`failed`、`completed_no_hit`、`completed_with_hits`。提交/等待/失败不能伪装成无命中，已完成命中显示 accession。
- 最终 Python 3.12 定向套件：`307 passed`；仅有 Python 3.13 将移除 `crypt` 的依赖弃用警告。

## Chroma 数据卷升级保护（2026-10-17）

- 新增 `scripts/backup_chroma_volume.sh`：要求源容器已停止且存在 `/chroma/chroma` 挂载，归档数据并验证 tar 可读；生成 SHA-256 和 JSON receipt，备份文件权限设为 `0600`、目录为 `0700`。
- `deploy-aliyun.sh app up` 在拉取镜像前暂停现有 Chroma、备份并重启原容器；备份失败时中止升级并尝试恢复原服务。没有现存容器时默认 fail-closed；确认空数据的初次安装可显式使用 `ALLOW_CHROMA_UNBACKED_INSTALL=1`。
- 新增脚本测试覆盖归档/checksum/receipt 和运行中容器拒绝；部署脚本静态测试覆盖备份先于镜像拉取。
- 归档校验不等同于目标版本兼容性证明。该段记录的是 2026-10-17 当时状态；后续维护窗口动作和最新恢复结论见下文。

## 发布计划执行复核（2026-10-19）

- 隔离 Python 3.12.13 环境已准备在 `/private/tmp`（未写入项目依赖文件）；报告/结构/BLAST/发布相关测试：`131 passed`，仅有 Python 3.13 `crypt` 弃用警告。
- 发布脚本和 Chroma 备份测试：`13 passed`。
- 前端 `npm run build`、`npm run lint`、基础 smoke 和 evidence-status smoke 均通过；临时 Vite 服务已停止。
- `run_release_acceptance.py --plan-only --json`：`0 failed`、`3 manual_required`、`1 skipped`；正式 manifest 缺失仍阻断真实发布验收。
- 线上只读核验：服务健康；`current` 仍为 `20261016-wiki-probe-v1`；Chroma 运行 `chromadb/chroma:latest`，未安装 `chromadb/chroma:0.6.3`。
- 线上 Chroma 的声明挂载 `/chroma/chroma` 为空，实际 SQLite 文件位于容器未挂载的 `/data/chroma.sqlite3`（约 188 KB）；现有备份脚本会拒绝该空挂载，当前数据没有可验证的归档保护。
- Chroma API v2 心跳和 collection 元数据接口可用，但当前 collection `protein_literature_specter2` 计数为 0，无法完成有意义的样本读取或目标版本兼容性证明。
- 因此当时没有生成 manifest 或部署；后续已完成一次受控 Chroma 停止/重启和实际 SQLite 备份，但目标镜像恢复仍失败，最新状态见“Chroma 维护窗口复核”。

## 候选材料（2026-10-19）

- 已生成候选范围清单：`output/report-analysis-upgrade-20261019/CANDIDATE-INVENTORY.md`。
- 已在 `/private/tmp` 生成报告/结构/发布相关 tracked patch 和 selected untracked archive；两者均未应用到源工作树，也未生成正式 release commit。
- 候选材料只能用于下一步人工复核；工作树仍 dirty，且正式 `RELEASE-MANIFEST.json`、生产环境文件和镜像 digest 尚未具备。

## Chroma 维护窗口复核（2026-10-19）

- 已在 ECS 上复制实际 `/data/chroma.sqlite3`，并在停止当前 Chroma 容器后重新复制一次，生成一致备份：`chroma-live-data-stopped-20261019T003540Z.sqlite3`，SHA-256 `5b1ad20275d1ddf0961e0ec35a8671014ec9e2b192efa7e4883a7108feebc630`。
- 备份 receipt 已写入线上 `/opt/protein-ai-platform/backups/chroma/`，记录源镜像、源路径、文件大小和恢复失败证据；原 Chroma 容器已启动并恢复 Docker health `healthy`。
- 已拉取目标镜像 `chromadb/chroma:0.6.3`，digest 为 `sha256:e0e78dc7609a599b63c99753442c7d01b1d3d369ce0e3bf3e0540536fec4fa7a`。
- 隔离恢复使用备份副本启动目标容器：heartbeat 通过；collection 读取失败，`/api/v2` 报 `KeyError('_type')`，`/api/v1` 报 `cannot unpack non-iterable coroutine object`。
- 空目标卷启动的 0.6.3 容器也出现同样的 collection API 异常，因此不能把“新建空卷”误判为兼容通过。
- 本次只停止并重启了原 Chroma 容器，未切换镜像、未修改 Compose、未重建其他服务；发布仍保持 blocked。

## Chroma 兼容性切换复核（2026-10-19，最新）

- 已在维护窗口内停止并保留旧容器 `docker-chromadb-legacy-20261019`，启动目标容器 `docker-chromadb-1`，镜像固定为 `chromadb/chroma:0.6.3`，镜像 digest 为 `sha256:e0e78dc7609a599b63c99753442c7d01b1d3d369ce0e3bf3e0540536fec4fa7a`。
- 目标容器挂载既有 `docker_chroma_data` 卷并通过 Docker health；容器内 heartbeat、collection 创建和文档 add/get 读写均通过。线上后端容器到 Chroma 的 heartbeat 和 collection listing 也通过，当前新库为空，仅有验证 collection `protein_literature_specter2`，count 为 0。
- 线上 `/api/health` 返回 `status=ok`、`tools_registered=60`；`/chat/agent` 返回 HTTP 200。其余应用容器保持 healthy，未重建 backend、worker、frontend 或 nginx。
- 已将当前线上 Compose 的 Chroma 镜像从可变 `chromadb/chroma:latest` 固定为 `chromadb/chroma:0.6.3`，Compose 解析结果与运行容器一致；旧容器保留为回滚证据，旧 SQLite 备份 `chroma-live-data-stopped-20261019T003540Z.sqlite3` 的 SHA-256 仍为 `5b1ad20275d1ddf0961e0ec35a8671014ec9e2b192efa7e4883a7108feebc630`。
- 旧 `/data/chroma.sqlite3` 在 0.6.3 中仍无法读取，`KeyError('_type')`。后续对备份做只读审计确认其 collection 有 0 条 embedding、0 条 embedding metadata 和 0 条全文索引内容，因此该备份没有历史文献 payload 需要迁移；当前服务已创建同名空 collection。
- 报告优化应用版本仍未发布。隔离候选已形成 clean 本地提交 `4321caac4e6efeacd8a0cae8bf7b5eec395d8ab9`（后续有版本记录文档提交），但正式 `RELEASE-MANIFEST.json`、生产配置检查、不可变应用镜像 digest 和完整线上 7DVJ 报告验收仍未通过。

### 生产配置门诊断（只读，2026-10-19）

- 在 ECS 当前 release 使用真实 `.env` 和 `.env.deploy-data` 执行 production config gate：11 项中仅 `PUBLIC_BASE_URL_HTTPS` 为 critical，其余密钥存在性、数据库、Redis、对象存储、LLM key、OIDC 和 Outline 检查均通过；输出没有包含密钥值。
- 仅作诊断地加 `--skip-domain-https` 后为 `ready`、0 critical、0 warning；这不是生产放行。部署记录确认主入口仍为 `http://120.27.108.138`，4243 仅为自签 TLS 技术验证端口，正式域名和可信证书尚未部署。
- 因此报告应用 release 的外部配置门需要正式 HTTPS 域名/证书；版本材料还需要 registry 可引用的五个 immutable application image digests 和可验证 rollback manifest。没有以临时占位值生成正式 manifest。

### LiteratureStore 实链路烟测

- 使用线上 backend 的真实 `LiteratureStore` 完成临时文献写入、统计、语义查询和删除：`before=0`、`indexed=1`、`after=1`、查询返回临时 PMID、删除成功、`final=0`。
- 该烟测证明当前 0.6.3 空库和 backend `chromadb==0.6.3` 客户端的实际读写链路可用；未留下测试文献数据。SPECTER2 模型在当前镜像缺少 `transformers` 时按既有代码降级到 hash embedding，属于已记录的运行时降级，不是 Chroma 兼容性错误。

### 旧备份数据量审计（只读）

- 使用 SQLite `mode=ro` 检查停止态备份，唯一 collection 为 `protein_literature_specter2`；`embeddings=0`、`embedding_metadata=0`、全文索引内容 `0`。
- 旧 schema 的确不能由 0.6.3 读取，但备份没有历史论文/向量正文，故无需为恢复历史文献执行 schema 迁移；当前服务已重建同名空 collection。该结论仅针对本次核对的备份 SHA-256 `5b1ad202...ebc630`。
