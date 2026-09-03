# 发布人工门证据归档模板

适用版本：0.1.0

用途：在维护窗口、异地备份恢复、外部存储恢复验证真实完成后，统一记录证据。此文件是模板；未填写并归档前，不得把生产状态写成“已上线”。

先生成机器可读证据记录模板并校验：

```bash
make release-manual-gate-evidence-template
make release-manual-gate-evidence-validate
```

证据记录结构说明和 example-only 样例：

```text
docs/manuals/release-manual-gate-evidence.schema.json
docs/manuals/release-manual-gate-evidence.example.json
```

## 基本信息

| 字段 | 记录 |
|---|---|
| 发布日期 | `<YYYY-MM-DD>` |
| 发布负责人 | `<name / team>` |
| 复核人 | `<name / team>` |
| 维护窗口编号 | `<MAINTENANCE_WINDOW_ID>` |
| 发布包 | `<dist/packages/...tar.gz>` |
| 发布包 checksum | `<sha256 evidence path>` |
| 数据库备份 | `<backups/protein_ai_...dump>` |
| 数据库备份 checksum | `<sha256 evidence path>` |
| 证据归档目录 | `<docs/manuals/drill-records/YYYY-MM-DD-.../>` |

## 终验命令

填写人工门输入后运行：

```bash
make release-manual-gate-validate
```

确认 `ready_to_run_final_acceptance=true` 后运行：

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

| 检查项 | 结果 |
|---|---|
| release acceptance status | `<passed / failed / blocked / passed-with-manual-gates>` |
| failed | `<number>` |
| blocked | `<number>` |
| manual_required | `<number>` |
| skipped | `<number>` |
| JSON 输出归档 | `<path>` |

## 维护窗口与回滚演练

| 字段 | 记录 |
|---|---|
| `MAINTENANCE_WINDOW_ID` | `<fill>` |
| `ALLOW_PRODUCTION_DRILL` 授权人 | `<fill>` |
| 维护窗口开始/结束 | `<timestamp range>` |
| rollback plan 输出 | `<path>` |
| restore drill dry-run 输出 | `<path>` |
| backup verify 输出 | `<path>` |
| 是否执行真实 rollback | `<no / yes with reason>` |
| 失败回滚动作 | `<none / command and result>` |
| 结论 | `<passed / failed / blocked>` |

最低证据：

- release acceptance JSON；
- rollback plan JSON；
- backup checksum 校验输出；
- `pg_restore --list` 校验输出；
- 维护窗口审批记录。

## 异地备份恢复演练

| 字段 | 记录 |
|---|---|
| `OFFSITE_BACKUP_TARGET` | `<redacted target / object ref>` |
| `OFFSITE_RESTORE_TARGET` | `<independent restore target>` |
| 上传/复制证据 | `<path>` |
| checksum 复验 | `<path>` |
| 独立恢复目标连接证据 | `<path>` |
| 恢复验证命令 | `<command or runbook ref>` |
| 恢复验证输出 | `<path>` |
| RTO/RPO 记录 | `<value / evidence path>` |
| 结论 | `<passed / failed / blocked>` |

最低证据：

- 异地对象或快照引用；
- checksum 复验记录；
- 独立恢复目标验证记录；
- 应用只读 smoke 或数据可读性验证记录。

## 外部存储恢复验证

| 字段 | 记录 |
|---|---|
| `EXTERNAL_STORAGE_BACKUP_REF` | `<snapshot / backup ref>` |
| `EXTERNAL_STORAGE_RESTORE_TARGET` | `<shadow bucket / prefix>` |
| 恢复对象范围 | `<prefix list>` |
| 样本 artifact keys | `<path>` |
| 只读/list 权限验证 | `<path>` |
| shadow 恢复输出 | `<path>` |
| 应用读取 smoke 输出 | `<path>` |
| 是否切换生产路径 | `no` |
| 结论 | `<passed / failed / blocked>` |

最低证据：

- shadow bucket/prefix 证明；
- 样本对象读取证明；
- 应用 smoke 读取证明；
- 未切换生产路径的确认。

## 发布决策

| 条件 | 状态 |
|---|---|
| 自动门槛 failed=0 | `<yes/no>` |
| 自动门槛 blocked=0 | `<yes/no>` |
| 维护窗口证据完整 | `<yes/no>` |
| 异地备份恢复证据完整 | `<yes/no>` |
| 外部存储恢复证据完整 | `<yes/no>` |
| 回滚路径可执行 | `<yes/no>` |
| 审批人确认 | `<yes/no>` |

最终决策：

- `<go / no-go / defer>`

签署：

- 发布负责人：`<name / timestamp>`
- 复核人：`<name / timestamp>`
- 业务确认人：`<name / timestamp>`
