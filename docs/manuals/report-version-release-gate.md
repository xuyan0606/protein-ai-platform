# 报告版本与发布一致性门

## 目的

每次生产发布必须绑定同一套源码、报告协议、湿实验计划协议、前端构建产物、模型配置、镜像 digest 和回滚目标。缺少其中任一项时，发布保持人工门禁状态。

## 发布 manifest

使用发布 CLI 生成 manifest：

```bash
python3 scripts/release_provenance.py create \
  --release-id <release-id> \
  --output RELEASE-MANIFEST.json \
  --frontend-bundle frontend/dist \
  --compose-file docker/docker-compose.aliyun-app.yml \
  --env-file docker/.env.aliyun.app \
  --image backend=<registry>/<backend>@sha256:<digest> \
  --image frontend=<registry>/<frontend>@sha256:<digest> \
  --image worker=<registry>/<worker>@sha256:<digest> \
  --image md-worker=<registry>/<md-worker>@sha256:<digest> \
  --image ligand-worker=<registry>/<ligand-worker>@sha256:<digest> \
  --rollback-manifest <previous-manifest.json> \
  --rollback-release-id <previous-release-id>
```

`--frontend-bundle` 会记录以下对齐信息：

- 报告 schema `1.1`
- 湿实验计划 schema `wet_lab_plan_v1`
- 前端构建目录的稳定 SHA-256

manifest 不保存环境变量密钥值，只保存非敏感环境摘要。

## 检查顺序

```bash
python3 scripts/check_report_version_alignment.py \
  --manifest RELEASE-MANIFEST.json --json
python3 scripts/check_upgrade_readiness.py --json
python3 scripts/build_release_worktree_manifest.py --json
```

三项检查分别确认报告与前端对齐、整体升级门状态、工作树和 release 对齐摘要。`verified` 才能进入发布步骤；`blocked` 或 `manual_required` 需要补证据。

安装脚本和 `deploy-aliyun.sh` 会在切换 `current` 或启动 Compose 前，以 `--offline` 模式重复执行对齐检查。该模式适用于不携带 `.git` 的提取发布包，仍会校验报告 schema、湿实验 schema、前端 bundle、模型配置和回滚目标。

## Chroma 数据卷保护

阿里云 app 执行 `deploy-aliyun.sh app up` 时，会在拉取或启动新镜像前暂停现有 `chromadb` 容器，并归档其 `/chroma/chroma` 挂载目录。归档包括 tar 完整性检查、SHA-256 文件和记录旧容器镜像/volume identity 的 JSON manifest，备份目录默认为 `backups/chroma/`，可用 `CHROMA_BACKUP_DIR` 指定。备份失败会中止更新，并尝试恢复原 Chroma 容器。

首次安装且确认没有 Chroma 数据时，可显式设 `ALLOW_CHROMA_UNBACKED_INSTALL=1` 跳过现存容器备份门。该开关只用于确认空数据的初装；不要用于已有数据卷升级。

归档校验只证明备份文件完整可读，不证明 0.6.3 能兼容旧版 Chroma 数据格式。生产切换仍须在隔离环境恢复归档、用目标镜像读取 collection，并记录 collection 数量/名称和抽样查询；未完成恢复演练前，发布应保持人工门禁。

## 失败处理

- schema 漂移：重新构建报告服务和 manifest，不能只替换前端文件。
- bundle hash 漂移：重新生成前端构建并更新 manifest。
- 模型漂移：恢复生产配置到 `gpt-6-sol`，重新执行检查。
- rollback 缺失：补齐上一版 manifest 和 release ID。
- Git 或 Compose 漂移：从干净 release 工作树重新打包。

发布脚本在切换 `current` 前执行 manifest 校验。校验失败时保留当前线上版本，生成差异列表供操作员处理。
