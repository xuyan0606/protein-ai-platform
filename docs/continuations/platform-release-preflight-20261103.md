# 2026-11-03 发布前远端核验

> 后续结果：20261103 已整合并发布真实模型与应用，详见[发布验收记录](platform-thermostability-deployment-20261103.md)。下文为当时的历史检查/交付状态，其中“未部署”“尚未执行”不代表当前状态。

结论：**no-go，现有候选不能直接覆盖生产**。本轮完成只读远端核验、三方源码差异盘点和候选源码包校验；没有推送、部署、数据库变更或修正服务器版本指针。完整标识、哈希和核验范围见 [机器可读记录](platform-release-preflight-20261103.json)。

## 版本记录与实际运行

| 入口 | 本次读取结果 |
| --- | --- |
| 本地生产记录 | `20261020T232642Z-0421817d-gpt-recovery` |
| 服务器 `production-version.json` | `20261022-quality-report-373e45d7` |
| `current` | `20261030T005847Z-theoretical-model-identity/protein-ai-platform` |
| `current/DEPLOYMENT-RECORD.json` | `20261030-theoretical-model-identity-710b4ff7` |
| 后端实际 Compose release | `20261030T034747Z-identity-evidence-tier/protein-ai-platform` |
| 该 release 记录 | `20261030-identity-evidence-tier-b728d4ca` |
| 后端 / worker / md-worker 实际 image ID | `sha256:540798f81804ecad942461e4fb60466eb126c78c376465c4f7088339a76a7721` |

八个实际运行服务均为 running / healthy、重启次数 0，镜像均与实际后端 release 的记录一致；健康接口返回 HTTP 200。首次按 Compose project 标签查询发现历史 created 容器，随后按八个运行服务名称独立核对，不能把历史容器当作服务故障。

从运行后端只读获取 `app` 与 `alembic`，234 个文件逐项 SHA-256 与实际后端 release 树一致。前端运行入口为 `assets/index-DkCwLw5i.js`，已记录静态资源哈希；未声称前端镜像 ID 足以证明全部运行资源与源码一致。

## 候选相对线上缺失的改动

以 `0421817d` 为共同基线，对实际后端容器与候选做逐文件三方比较：

- 20 个线上已修改文件在候选中仍等于旧基线，包括链选择与 BLAST 别名排除、结构问题/证据范围、身份证据分层、理论模型 B 因子语义、配体接触和残基映射等涉及的文件。直接覆盖会丢失这些线上修改。
- 3 个文件两边都已改变：`backend/app/core/agent_graph.py`、`backend/app/services/enzyme_workflow_runtime.py`、`backend/app/services/task_evidence.py`，需要逐段合并审查；哈希不同本身不代表自动合并冲突。
- 另有 7 个共有文件仅候选相对基线变化，以及候选新增的 18 个应用文件；这些能力也需要保留。
- 远端 release 前端源码与候选另有 7 个文件不同；该盘点尚不能替代前端运行产物与最终源码的绑定验收。

完整路径见 JSON 中 `source_review`；原始哈希清单和容器源码快照保存在本地被忽略目录 `output/release-preflight-20261103/`。本轮没有自动选择任意一方覆盖另一方。

## 发布包、正式清单和回滚资产

- 从已提交 `08f2f7206` 的 Git archive 生成独立源码包，应用代码仍对应已测 `1e5e8d304`。包内 706 个文件全部与提交内容逐项哈希一致，排除密钥配置、运行数据、依赖、模型权重与 `frontend/frontend`。包的路径和 SHA-256 见 JSON。
- 包内清单明确为 `audit_only_not_release_ready` / `deployment_allowed=false`。它没有正式 `RELEASE-MANIFEST.json`，默认 installer 会阻断。不能作为新整合版本的部署包。
- 实际运行的 backend/frontend/ligand-worker 镜像均存在，但无仓库 RepoDigest。正式清单仍需真实仓库摘要、运行配置指纹、前端构建及报告 schema 绑定；当前没有新增受信任 HTTPS 验收证据，不沿用历史临时发布例外。
- 老镜像归档 `candidates/0cc380a4-frontend-20261020/rollback/images.tar.gz` 存在，475837740 字节，SHA-256 与旧生产文档的 `626c96f1…a0802b` 一致。它是历史资产，不能代替当前运行镜像的完整外部归档。
- 实际运行增量 `increments/20261030-identity-evidence-tier-b728d4ca/rollback/` 的两份旧源码及哈希记录存在；旧后端镜像 `4944663d…` 也存在。实际 release 的镜像锁、代理锁和回滚脚本存在且已记录哈希，但未核验脚本目标适用于下一次发布，也未执行回滚。
- 发现的数据库备份为 `protein_ai_pre_20261019_7b0ed23b.dump`，SHA-256 与 sidecar 一致。该备份早于本次发布准备，仍需发布前新备份、可恢复性校验及当前运行镜像的独立回滚资产。

## 数据库只读检查

通过运行后端以只读事务查询：生产迁移版本为 `20260917_0004`，不在候选 Alembic 图中；公共 schema 有 51 个表、185 个索引。复用 `audit_production_migration_drift.py` 检查候选 15 个迁移的字面量 `create_table/create_index` 名称，15 个均存在、缺项 0。

上述检查只证明表名与索引名存在，未验证列类型、约束或迁移可重放性；不得由此直接执行 `alembic upgrade head` 或 `stamp`。候选相对旧基线未改模型和迁移目录，也不能据此省略新整合版本的数据库兼容性检查。

## 下一批执行边界

先以实际运行源码快照及对应本地测试恢复生产改动，在独立整合分支保留候选能力，审查上述 20 个遗漏文件、3 个双边修改文件及前端差异；随后重新执行整合版本的后端、前端和真实关键流程验收。再补正式清单、HTTPS、发布前备份、当前运行镜像归档与回滚目标核验，完成后才进入生产切换。

旧候选的后端 1211 项和前端通过结果仍为此前证据，本轮没有重复运行，不适用于尚未生成的整合源码。本地 `current-production.json` 保留原历史事实；本次观察单独记录，避免把不一致的服务器指针写成新的已验收生产基线。
