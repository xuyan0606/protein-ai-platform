# 2026-08-17 发布操作员包

适用版本：0.1.0

## 当前状态

- 本地自动门槛：通过。
- 增强 release acceptance：已纳入 compose 备份校验，failed=0 / blocked=0 / skipped=0。
- 生产部署：未执行。
- 发布决策：等待人工门输入、真实外部演练和证据归档。

## 操作顺序

| 步骤 | 操作 | 产物 |
|---|---|---|
| 1 | 阅读发布交接记录 | `docs/manuals/release-handoff-2026-08-17.md` |
| 2 | 生成或打开人工门输入模板 | `docs/manuals/release-manual-gate-inputs.template.json` |
| 3 | 只读校验人工门输入 | `docs/manuals/release-manual-gate-input-validation-report.json` |
| 4 | 输入完整后运行增强 release acceptance | release acceptance JSON |
| 5 | 执行维护窗口/异地恢复/外部存储恢复演练 | 外部演练输出 |
| 6 | 填写并只读校验证据记录，再归档 | `docs/manuals/release-manual-gate-evidence-validation-report.json` |
| 7 | 做 go/no-go/defer 决策 | 已签署证据归档 |

## 命令

生成模板：

```bash
make release-manual-gate-template
```

校验输入：

```bash
make release-manual-gate-validate
```

生成证据记录模板：

```bash
make release-manual-gate-evidence-template
```

校验证据记录：

```bash
make release-manual-gate-evidence-validate
```

生成 go/no-go 汇总：

```bash
make release-go-no-go-summary
```

生成当前工作区变更清单：

```bash
make release-worktree-manifest
```

生成操作员包 manifest：

```bash
make release-operator-packet-manifest
```

检查已有 manifest 是否仍匹配当前操作员包文件：

```bash
make release-operator-packet-manifest-check
```

只看终验计划，不执行真实动作：

```bash
./backend/.venv/bin/python scripts/run_release_acceptance.py \
  --plan-only \
  --include-backup-verify \
  --backup-verify-compose \
  --json
```

人工门齐备后的最终自动终验：

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

## 必备文件

| 文件 | 用途 |
|---|---|
| `docs/manuals/release-handoff-2026-08-17.md` | 当前自动门槛与人工门状态 |
| `docs/manuals/release-manual-gate-inputs.template.json` | 人工门输入模板 |
| `scripts/validate_release_manual_gate_inputs.py` | 人工门只读校验 |
| `docs/manuals/release-manual-gate-evidence-template.md` | 人工演练证据归档模板 |
| `docs/manuals/release-manual-gate-evidence-inputs.template.json` | 机器可读证据记录模板 |
| `docs/manuals/release-manual-gate-evidence.schema.json` | 证据记录结构说明 |
| `docs/manuals/release-manual-gate-evidence.example.json` | example-only 证据记录样例 |
| `scripts/validate_release_manual_gate_evidence.py` | 证据记录只读校验 |
| `scripts/build_release_go_no_go_summary.py` | go/no-go 汇总生成 |
| `scripts/build_release_worktree_manifest.py` | dirty worktree 路径清单 |
| `docs/manuals/external-infrastructure-acceptance-checklist.md` | 外部基础设施验收清单 |
| `docs/manuals/productization-acceptance-manual.md` | 总体验收手册 |
| `docs/manuals/release-operator-packet-manifest-2026-08-17.json` | 操作员包机器清单 |

交接前必须运行 `make release-operator-packet-manifest-check`。如果返回 `stale-or-missing`，先重新运行 `make release-operator-packet-manifest`，再复查。

## 不能越过的边界

- 不得把 `manual_required` 写成已上线。
- 不得在没有维护窗口编号和授权时执行生产 rollback/restore。
- 不得把外部存储恢复直接指向生产 bucket/prefix；必须先恢复到 shadow bucket/prefix。
- 不得把本地 dry-run、plan-only 或 demo smoke 写成正式域名/GPU/GROMACS/外部恢复已上线。
- 不得在证据未归档、未复核、未签署前做 go 决策。
- 不得把 `release-manual-gate-evidence.example.json` 当作真实证据。

## go/no-go 最小条件

| 条件 | 要求 |
|---|---|
| 自动终验 | failed=0 / blocked=0 |
| 人工门 | manual_required=0，或所有 manual gate 已有签署证据 |
| 备份 | checksum 与 `pg_restore --list` 已归档 |
| 维护窗口 | 审批记录、rollback plan、restore drill 证据已归档 |
| 异地备份恢复 | 独立恢复目标验证已归档 |
| 外部存储恢复 | shadow restore 与应用只读 smoke 证据已归档 |
| 签署 | 发布负责人、复核人、业务确认人已签署 |

## 当前下一步

填写 `release-manual-gate-inputs.template.json`，运行 `make release-manual-gate-validate`；真实演练后填写 `release-manual-gate-evidence-inputs.template.json`，运行 `make release-manual-gate-evidence-validate`，再运行 `make release-go-no-go-summary` 和 `make release-worktree-manifest` 供复核。
