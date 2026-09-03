# 产品化验收操作手册

适用版本：0.1.0

## 目标

这份手册用于正式部署、升级、验收、权限复核和告警联动前的统一检查。

默认原则：

- 先 dry-run，再真实执行。
- 先本地/预发验收，再生产变更。
- 回滚、恢复、异地备份演练必须有维护窗口。
- `/api/ops/summary` 只读，不发送外部通知。
- 外部告警必须由管理员显式 dispatch。

## 发布验收

默认安全验收：

```bash
make release-acceptance
```

等价脚本：

```bash
python3 scripts/run_release_acceptance.py
```

默认会执行：

- upgrade readiness
- acceptance matrix
- package deploy bundle dry-run
- rollback plan
- restore drill dry-run

默认不会执行：

- 真实 rollback
- 真实数据库 restore
- live gate
- 浏览器 smoke
- MD 黑盒长任务
- 备份 `pg_restore` 校验

本机 pytest runner、浏览器 smoke contract 和 MD blackbox plan/fail-closed 入口见 [本机测试 Runner 与黑盒 Gate](pytest-runner-and-blackbox-gates.md)。

默认会输出但不执行的维护窗口 gate。缺输入时状态为 `manual_required`，表示测试已完成但真实演练还需要人工提供维护窗口或恢复目标，不表示代码失败：

- `production_rollback_drill_gate`：缺维护窗口或授权时为 `manual_required`。
- `offsite_backup_restore_drill_gate`：缺异地备份目标或独立恢复目标时为 `manual_required`。
- `external_storage_restore_validation_gate`：缺外部存储备份引用或 shadow 恢复目标时为 `manual_required`。

详细执行边界见 [维护窗口演练 Runbook](maintenance-drill-runbook.md)。

PDB-only 酶改造报告的输入审计、工具边界、候选阻断和 HM.pdb 发布 gate 见 [PDB-only 酶改造分析 SOP](pdb-only-enzyme-analysis-sop.md)。

正式域名/HTTPS/OIDC、GPU/GROMACS、维护窗口、异地备份、外部存储恢复和数据更新制度见 [外部基础设施验收清单](external-infrastructure-acceptance-checklist.md)。

2026-08-17 本地自动门槛、增强备份校验和人工门状态见 [发布交接记录](release-handoff-2026-08-17.md)。面向操作员的一页式入口见 [发布操作员包](release-operator-packet-2026-08-17.md)。

最终人工门输入模板：

```bash
make release-manual-gate-template
```

填写 `docs/manuals/release-manual-gate-inputs.template.json` 后只读校验：

```bash
make release-manual-gate-validate
```

人工演练完成后，按 [发布人工门证据归档模板](release-manual-gate-evidence-template.md) 记录维护窗口、异地备份恢复和外部存储恢复证据。

先生成机器可读证据记录模板：

```bash
make release-manual-gate-evidence-template
```

填写 `docs/manuals/release-manual-gate-evidence-inputs.template.json` 后只读校验：

```bash
make release-manual-gate-evidence-validate
```

证据校验返回 `manual_required` 时，不得做 go 决策；它只说明证据仍不完整。

证据记录结构和 example-only 样例：

```text
docs/manuals/release-manual-gate-evidence.schema.json
docs/manuals/release-manual-gate-evidence.example.json
```

生成复核摘要和 dirty worktree 路径清单：

```bash
make release-go-no-go-summary
make release-worktree-manifest
```

交接前可生成操作员包机器清单：

```bash
make release-operator-packet-manifest
```

交接前检查机器清单是否仍匹配当前文件：

```bash
make release-operator-packet-manifest-check
```

## 发布验收 JSON

CI 或部署脚本读取：

```bash
make release-acceptance-json
```

只看计划，不执行命令：

```bash
make release-acceptance-plan
```

## 可选增强验收

前端生产构建：

```bash
python3 scripts/run_release_acceptance.py --include-frontend
```

真实浏览器 smoke：

```bash
python3 scripts/run_release_acceptance.py --include-browser-smoke
```

真实 live 数据 gate：

```bash
python3 scripts/run_release_acceptance.py --include-live
```

MD 黑盒长任务：

```bash
python3 scripts/run_release_acceptance.py --include-md-blackbox
```

未提供浏览器或 MD live 输入时，如需把缺口视为阻断而不是跳过：

```bash
make acceptance-matrix-fail-closed
make nightly-live-gates-fail-closed
```

备份校验：

```bash
python3 scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose
```

维护窗口 gate 预检查：

```bash
MAINTENANCE_WINDOW_ID=MW-YYYYMMDD-001 \
ALLOW_PRODUCTION_DRILL=true \
OFFSITE_BACKUP_TARGET=oss://bucket/path/protein_ai.dump \
OFFSITE_RESTORE_TARGET=staging-temp-db \
EXTERNAL_STORAGE_BACKUP_REF=oss-snapshot-YYYYMMDD \
EXTERNAL_STORAGE_RESTORE_TARGET=oss://bucket/restore-shadow/ \
python3 scripts/run_release_acceptance.py --json
```

注意：不要把 `release-acceptance` 和全量 pytest 并行跑。两者可能竞争同一测试环境，导致 transient error。CI 如需并行拆分后端 pytest job，必须为每个 job 设置独立 `TEST_DATABASE_URL` 和隔离存储目录。

## 外部生信运行时

Rosetta、Foldseek、GROMACS 属于部署节点运行时，不随默认应用代码自动安装。

上线前按目标能力配置：

| 能力 | 变量 | 验收口径 |
|---|---|---|
| Rosetta ΔΔG | `ROSETTA_CARTESIAN_DDG` 或 `ROSETTA_DDG_BINARY` | 已配置并可执行时返回真实 Rosetta ΔΔG；负值更稳定，正值更不稳定；缺失时返回 blocked，不伪造结果 |
| Foldseek 结构检索 | `FOLDSEEK_API_URL` 或 `FOLDSEEK_BINARY` + `FOLDSEEK_DATABASE_*` | live gate 可连通 API 或本地 DB 时通过；否则只允许 demo/summary 降级 |
| GROMACS MD | `GROMACS_BIN` | 安装真实 `gmx`/`gmx_mpi` 后再跑 topology/live MD gate；缺失时返回 `GROMACS_NOT_INSTALLED` |

Rosetta ΔΔG 默认判读区间：

| ΔΔG | 判读 |
|---:|---|
| `<= -2.0` | 强稳定候选 |
| `-2.0 ~ -1.0` | 稳定候选 |
| `-1.0 ~ 1.0` | 中性或不确定，需人工核实 |
| `1.0 ~ 2.0` | 不稳定风险 |
| `> 2.0` | 强不稳定风险 |

## 权限矩阵

项目级角色：

| Action | owner | editor | viewer |
|---|---:|---:|---:|
| project.read | yes | yes | yes |
| project.update | yes | yes | no |
| project.delete | yes | no | no |
| project.members.read | yes | yes | yes |
| project.members.manage | yes | no | no |
| project.sequence.create | yes | yes | no |
| project.sequence.delete | yes | yes | no |
| project.batch.read | yes | yes | yes |
| project.batch.run | yes | yes | no |
| project.wiki.publish | yes | yes | no |
| project.file.read | yes | yes | yes |
| project.file.write | yes | yes | no |
| project.chat.bind | yes | yes | no |

后端返回字段：

- `access_role`
- `permissions`

前端应优先使用 `permissions` 控制按钮，而不是只根据 `access_role` 推断。

## 告警 dispatch

只读监控：

```bash
GET /api/ops/summary
```

管理员 dry-run：

```bash
POST /api/ops/alerts/dispatch
```

真实发送：

```bash
POST /api/ops/alerts/dispatch?dry_run=false
```

必须先配置：

```env
OPS_ALERT_WEBHOOK_ENABLED=true
OPS_ALERT_WEBHOOK_URL=https://example.com/webhook
OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS=3
OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS=2
OPS_ALERT_SILENCE_SECONDS=900
OPS_ALERT_ESCALATE_AFTER_COUNT=3
```

默认不发送外部通知，避免刷新页面或健康检查误触发企业微信、钉钉、邮件网关。

## 真实数据样例

当前 `deploy_data/` 已包含可作为样例的数据形态：

```text
deploy_data/pdb/1QHP.cif
deploy_data/pdb/1QHO.cif
deploy_data/alphafold/AF-P19531-F1-model_v6.cif
deploy_data/alphafold/AF-P19531-F1-predicted_aligned_error_v6.json
deploy_data/sifts/1qhp.json
deploy_data/annotations/base.json
deploy_data/annotations/interpro.json
deploy_data/smoke/query.pdb
```

真实上线前必须确认：

```bash
make check-deploy-data
make deploy-live-gate
make backend-smoke-live
```

如果只是 demo-ready，不等于真实数据可上线。

## 截图清单

截图建议保存到：

```text
docs/manuals/screenshots/
```

建议截图：

- `admin-users.png`：管理员用户状态与角色管理
- `admin-data-readiness.png`：数据资产 readiness
- `admin-task-audits.png`：任务审计与筛选
- `data-ops-summary.png`：运维摘要与告警
- `pdb-md-report.png`：PDB/MD 报告与下载
- `projects-permissions.png`：项目权限与 viewer 只读边界

当前环境不生成截图文件，避免伪造界面证据。

截图版文字占位手册见：

- [截图版操作手册（文字占位版）](screenshot-operation-placeholder-manual.md)

仍待真实浏览器补齐：

- 管理员用户/角色/状态管理。
- 管理员任务审计筛选和 CSV 导出。
- 数据 readiness、更新历史和导入 dry-run。
- Lipase curation queue、batch manifest 和 publish 确认。
- 运维 summary、告警 dry-run 和回滚计划。

这些截图必须来自真实浏览器；当前文档不包含截图文件。

## 上线前检查单

- `make release-acceptance` 通过。
- `make upgrade-readiness` 无 critical。
- `make deploy-live-gate` 通过，且不是 demo-only。
- 最近一次备份存在并可校验。
- `make rollback-plan` 输出可人工复核。
- 管理员账号未被禁用或锁定。
- 外部告警先 dry-run，再真实发送。
- 生产恢复或回滚必须有维护窗口。
