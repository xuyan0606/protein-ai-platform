# 维护窗口演练 Runbook

适用版本：0.1.0

## 目标

把回滚演练、异地备份演练、外部存储恢复验证拆成三个层级：

- 本机/预发可做：只读计划、备份校验、临时库恢复演练。
- plan-only 可做：生成缺口清单、确认命令、记录维护窗口前置条件。
- 维护窗口可执行：生产回滚、生产数据库 restore、生产对象存储路径切换。

## 默认安全检查

```bash
python3 scripts/run_release_acceptance.py
python3 scripts/run_release_acceptance.py --json
```

默认不会执行生产回滚、生产 restore、对象存储写入或路径切换。输出中以下 gate 如为 `manual_required`，表示还缺维护窗口、授权或恢复目标，不代表脚本失败：

- `production_rollback_drill_gate`
- `offsite_backup_restore_drill_gate`
- `external_storage_restore_validation_gate`

## 当前本机能做

```bash
python3 scripts/rollback_plan.py
./scripts/verify_backup.sh --plan-only backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
./scripts/restore_drill.sh --plan-only backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
./scripts/restore_drill.sh --dry-run backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
```

如果已有真实备份，并且 Docker compose PostgreSQL 可用，可以执行临时库恢复演练：

```bash
make verify-backup BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
make restore-drill BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
```

`restore-drill` 只恢复到临时库，默认库名为 `protein_ai_restore_check`，不会触碰主库。

## 生产回滚演练

生产回滚演练必须同时具备：

- `MAINTENANCE_WINDOW_ID`
- `ALLOW_PRODUCTION_DRILL=true`
- 已校验的部署包
- 已校验的数据库备份
- 维护窗口负责人和复核人

只生成可执行计划：

```bash
MAINTENANCE_WINDOW_ID=MW-YYYYMMDD-001 \
ALLOW_PRODUCTION_DRILL=true \
python3 scripts/rollback_plan.py --mode aliyun-app --json
```

真正停服务、restore 主库、切换版本包只能在维护窗口内人工执行。执行后必须归档到 `docs/manuals/drill-record-template.md`。

## 异地备份恢复演练

异地备份恢复演练必须同时具备：

- 本地备份文件和 `.sha256`
- `OFFSITE_BACKUP_TARGET`：异地介质或对象存储位置
- `OFFSITE_RESTORE_TARGET`：独立恢复目标，不能是生产主库
- RTO/RPO 记录口径

plan-only 检查示例：

```bash
OFFSITE_BACKUP_TARGET=oss://bucket/path/protein_ai.dump \
OFFSITE_RESTORE_TARGET=staging-temp-db \
python3 scripts/run_release_acceptance.py --json
```

执行标准：

- 从异地介质取回备份。
- 校验 checksum。
- 在独立临时库或预发库 restore。
- 跑应用 smoke，记录表数量、关键接口和恢复耗时。

## 外部存储恢复验证

外部存储恢复验证必须同时具备：

- `EXTERNAL_STORAGE_BACKUP_REF`：OSS/MinIO 备份、快照或复制任务编号。
- `EXTERNAL_STORAGE_RESTORE_TARGET`：独立 bucket/prefix，不能覆盖生产路径。
- 需要抽查的对象前缀和样本 artifact key。
- 只读/list 权限先通过，再考虑写入恢复目标。

plan-only 检查示例：

```bash
EXTERNAL_STORAGE_BACKUP_REF=oss-snapshot-YYYYMMDD \
EXTERNAL_STORAGE_RESTORE_TARGET=oss://bucket/restore-shadow/ \
python3 scripts/run_release_acceptance.py --json
```

执行标准：

- 恢复到 shadow bucket/prefix。
- 抽查上传文件、MD artifact、报告下载对象。
- 使用应用 smoke 读取 shadow 目标。
- 只有在维护窗口内，且业务确认后，才允许切换生产访问路径。

## 归档要求

每次演练结束后补齐：

- 演练记录编号。
- 维护窗口编号。
- 执行命令和关键输出。
- 备份文件、checksum、对象存储备份引用。
- RTO/RPO。
- 截图路径。
- 结论和后续动作。

模板：`docs/manuals/drill-record-template.md`
