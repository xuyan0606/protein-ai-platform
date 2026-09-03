# 2026-08-17 发布交接记录

适用版本：0.1.0

## 结论

- 本地代码、文档和自动发布门槛已收口。
- 默认 release acceptance 与增强备份校验均无 failed / blocked。
- 生产部署未执行，真实上线仍等待人工发布门和外部基础设施输入。

面向操作员的一页式执行入口见：

```text
docs/manuals/release-operator-packet-2026-08-17.md
```

## 已通过的自动门槛

```bash
./backend/.venv/bin/python scripts/run_acceptance_matrix.py --json
```

结果：

- status：`passed-with-skips`
- failed：0
- blocked：0
- skipped：7
- total：21

```bash
./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json
```

结果：

- status：`passed-with-manual-gates`
- failed：0
- blocked：0
- manual_required：3
- skipped：0
- total：9
- `backup_verify`：passed
- `backup_verify` 方式：compose postgres 内执行只读 `pg_restore --list`

## 备份校验说明

本机缺少本地 `pg_restore`，直接运行：

```bash
./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --json
```

会因本机 PostgreSQL client 缺失失败。已改用：

```bash
./backend/.venv/bin/python scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose --json
```

该路径只读取备份文件并校验：

- 备份文件存在；
- `.sha256` checksum 匹配；
- PostgreSQL custom dump 可被 `pg_restore --list` 解析。

不执行真实恢复，不写生产数据库。

## 仍需人工提供

生产上线前仍需补齐：

| Gate | 缺失输入 | 状态 |
|---|---|---|
| `production_rollback_drill_gate` | `MAINTENANCE_WINDOW_ID`, `ALLOW_PRODUCTION_DRILL=true` | `manual_required` |
| `offsite_backup_restore_drill_gate` | `OFFSITE_BACKUP_TARGET`, `OFFSITE_RESTORE_TARGET` | `manual_required` |
| `external_storage_restore_validation_gate` | `EXTERNAL_STORAGE_BACKUP_REF`, `EXTERNAL_STORAGE_RESTORE_TARGET` | `manual_required` |

人工门输入模板：

```bash
make release-manual-gate-template
```

填写后校验：

```bash
make release-manual-gate-validate
```

人工演练完成后的证据归档模板：

```text
docs/manuals/release-manual-gate-evidence-template.md
```

机器可读证据记录先生成并校验：

```bash
make release-manual-gate-evidence-template
make release-manual-gate-evidence-validate
```

只有证据校验不再返回 `manual_required`，且最终决策与证据一致时，才可进入 go/no-go/defer 复核；校验脚本不会执行外部恢复或生产切换。

复核前生成 go/no-go 汇总和 dirty worktree 路径清单：

```bash
make release-go-no-go-summary
make release-worktree-manifest
```

交接前检查操作员包机器清单是否仍匹配当前文件：

```bash
make release-operator-packet-manifest-check
```

## 上线前执行口径

人工门补齐后再跑：

```bash
./backend/.venv/bin/python scripts/run_release_acceptance.py \
  --include-backup-verify \
  --backup-verify-compose \
  --maintenance-window-id "$MAINTENANCE_WINDOW_ID" \
  --allow-production-drill \
  --offsite-backup-target "$OFFSITE_BACKUP_TARGET" \
  --offsite-restore-target "$OFFSITE_RESTORE_TARGET" \
  --external-storage-backup-ref "$EXTERNAL_STORAGE_BACKUP_REF" \
  --external-storage-restore-target "$EXTERNAL_STORAGE_RESTORE_TARGET" \
  --json
```

只有该命令仍保持 failed=0 / blocked=0，并且维护窗口、回滚、异地恢复、外部存储恢复证据已按 `release-manual-gate-evidence-template.md` 归档后，才能把状态从“可进入人工发布审批”改为“可执行生产上线”。
