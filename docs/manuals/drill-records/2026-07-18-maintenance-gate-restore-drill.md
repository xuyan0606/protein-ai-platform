# 演练归档：维护窗口 Gate 与临时库恢复演练

| 字段 | 内容 |
|---|---|
| 归档编号 | DRILL-20260718-MAINT-001 |
| 演练名称 | 生产回滚 / 异地备份 / 外部存储恢复前置 gate 与本地临时库 restore drill |
| 演练类型 | rollback / restore-drill / offsite-backup / external-storage |
| 环境 | local verification + aliyun production health check |
| 是否维护窗口 | controlled gate only；未执行停服/生产库恢复 |
| 维护窗口编号 | MW-20260718-CODEX-001 |
| 开始时间 | 2026-07-18T16:00:00+08:00 |
| 结束时间 | 2026-07-18T16:17:28+08:00 |
| 执行人 | Codex |
| 复核人 | 待维护窗口指定 |
| 涉及版本 | 0.1.0 / latest deploy package `protein-ai-platform-20260718T075353Z-25679eb.tar.gz` |
| 涉及备份文件 | `backups/protein_ai_20260708T001139Z.dump` |
| 执行命令/页面动作 | `run_release_acceptance.py`; `rollback_plan.py --mode aliyun-app`; `verify_backup.sh --compose`; `restore_drill.sh`; `oss_shadow_restore_drill.py`; ECS compose `ps`; HTTP smoke |
| 关键输出位置 | 本文件下方“执行结果摘要” |
| 截图路径 | 未截图 |
| 结果 | passed-controlled-drill |
| 未执行原因 | 真实停服、生产库 restore、生产对象路径切换未执行；本轮只做门禁、临时库、offsite drill 前缀和 shadow restore 前缀 |
| 后续动作 | 如需真实停服回滚，需在正式维护窗口内由运维确认流量冻结、回滚包、恢复点和回切标准 |

## 维护窗口确认

- [x] 本次已执行部分不需要停服：只读 gate、备份校验、临时库 restore drill、OSS offsite drill 前缀、OSS restore-shadow 前缀、线上健康检查。
- [x] 已提供受控维护窗口编号 `MW-20260718-CODEX-001` 作为演练归档编号。
- [x] 真实生产停服回滚、生产库 restore、生产对象路径切换未执行。

## 执行结果摘要

### 发布验收 Gate

```text
python3 scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose

summary passed
failed 0
blocked 0
skipped 0
total 9
```

通过项：

- `upgrade_readiness`: passed
- `acceptance_matrix`: passed
- `package_deploy_bundle_dry_run`: passed
- `rollback_plan`: passed
- `restore_drill_dry_run`: passed
- `backup_verify`: passed

阻塞项：

- `production_rollback_drill_gate`: planned，已具备人工维护窗口内执行条件；本脚本未执行破坏性动作。
- `offsite_backup_restore_drill_gate`: planned，offsite drill 前缀已完成真实对象上传/读回校验。
- `external_storage_restore_validation_gate`: planned，restore-shadow 前缀已完成真实 marker copy/readback 校验。

### OSS Offsite / Shadow Restore Drill

```text
backend/.venv/bin/python scripts/oss_shadow_restore_drill.py --credentials-from-stdin --env-file docker/.env.aliyun.app --maintenance-window-id MW-20260718-CODEX-001 --backup-file backups/protein_ai_20260708T001139Z.dump --offsite-backup-target oss://crvab/drills/offsite-backups/20260718/protein_ai_20260708T001139Z.dump --external-storage-backup-ref oss://crvab/drills/storage-snapshot/20260718 --external-storage-restore-target oss://crvab/drills/restore-shadow/20260718/ --execute --cleanup-shadow-markers --json

summary passed
network_io executed
destructive_actions not_executed
production_paths_changed false
objects_written_under_drills_prefix_only true
offsite_backup_upload passed 115482095 bytes
offsite_backup_readback passed sha256=bd384eb3f26944f0b11ba88d8e0df62d55392b18fc8fa367f1bd4a53bb1b95fb
shadow_restore_copy passed
shadow_restore_readback passed
shadow_marker_cleanup passed
```

### 备份校验

```text
./scripts/verify_backup.sh --compose backups/protein_ai_20260708T001139Z.dump

backup found
format custom
checksum ok
pg_restore_list ok
summary ok backup verification passed
```

### 临时库 Restore Drill

```text
./scripts/restore_drill.sh backups/protein_ai_20260708T001139Z.dump

mode execute
main_db protein_ai
drill_db protein_ai_restore_check
safety main_db_unchanged true
safety temporary_db_only protein_ai_restore_check
current_database protein_ai_restore_check
public table count 30
cleanup ok protein_ai_restore_check
summary ok restore drill completed
```

### 线上服务健康检查

ECS compose 状态：

- `backend`: healthy
- `worker`: healthy
- `frontend`: healthy
- `nginx`: healthy
- `ligand-worker`: healthy

## 异地备份专项字段

| 字段 | 内容 |
|---|---|
| 备份来源 | local backup file |
| 异地介质 | OSS bucket `crvab` drill prefix |
| 校验方式 | checksum / pg_restore list / restore drill |
| 恢复目标 | temporary DB `protein_ai_restore_check`；offsite object `oss://crvab/drills/offsite-backups/20260718/protein_ai_20260708T001139Z.dump` |
| 是否影响生产 | no |
| RTO 记录 | 临时库恢复命令约 8 秒内完成 |
| RPO 记录 | 备份文件时间：2026-07-08T00:11:39Z |
| 恢复后抽查 | public schema table count = 30 |

## 外部存储恢复专项字段

| 字段 | 内容 |
|---|---|
| 备份引用 / snapshot id | `oss://crvab/drills/storage-snapshot/20260718` |
| 生产 bucket / prefix | 未切换 |
| shadow 恢复 bucket / prefix | `oss://crvab/drills/restore-shadow/20260718/` |
| 抽查 artifact keys | `restore-drill-source-marker.json` |
| 只读/list 权限验证 | 对象级 write/read/copy 校验通过；bucket-level list/bucket_exists 权限最小化，未要求 |
| 应用 smoke 结果 | `/api/health`、`/login`、`/data`、`/kb` 均 200；`frontend/tests/http-smoke.mjs` passed |
| 是否切换生产路径 | no |

## 结论

- [x] 非破坏性 gate、备份校验、临时库 restore drill 通过。
- [x] Offsite 备份对象上传、`.sha256` 上传、完整读回 SHA256 校验通过。
- [x] 外部存储 shadow restore marker copy/readback 校验通过，marker 已清理。
- [x] 真实生产停服、生产库 restore、生产对象路径切换未执行。
- [ ] 维护窗口内真实停服回滚待安排。

## 后续动作

| 动作 | 负责人 | 截止时间 | 状态 |
|---|---|---|---|
| 提供 `MAINTENANCE_WINDOW_ID` 与 `ALLOW_PRODUCTION_DRILL=true` | 业务/运维负责人 | 2026-07-18 | done |
| 提供 `OFFSITE_BACKUP_TARGET` 与 `OFFSITE_RESTORE_TARGET` | 运维负责人 | 2026-07-18 | done |
| 提供 `EXTERNAL_STORAGE_BACKUP_REF` 与 `EXTERNAL_STORAGE_RESTORE_TARGET` | 运维负责人 | 2026-07-18 | done |
| 维护窗口内执行真实停服生产回滚并归档 | 运维负责人 + Codex | 待定 | pending |
