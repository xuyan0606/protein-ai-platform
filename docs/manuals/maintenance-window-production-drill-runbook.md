# 维护窗口生产演练 Runbook

更新时间：2026-07-23

## 当前范围

- 本轮不做正式域名和 HTTPS 切换。
- 默认只执行只读检查、备份校验、临时库恢复、OSS `drills/` 前缀验证。
- 生产停服回滚、生产 RDS restore、对象存储生产路径切换必须在维护窗口内人工确认后执行。

## 维护窗口前置条件

| 项目 | 要求 | 当前默认动作 |
|---|---|---|
| 维护窗口编号 | 设置 `MAINTENANCE_WINDOW_ID` | 缺失时 gate 阻断 |
| 生产演练开关 | 设置 `ALLOW_PRODUCTION_DRILL=true` | 缺失时不执行破坏性动作 |
| 部署包 | 已存在并校验 checksum | `rollback_plan.py` 只读发现 |
| 数据库备份 | `.dump` 与 `.sha256` 均存在 | `verify_backup.sh` 校验 |
| 独立恢复目标 | 不能指向生产库 | `restore_drill.sh` 用临时库 |
| 对象存储恢复目标 | 必须是 shadow bucket/prefix | `oss_shadow_restore_drill.py` 强制 `drills/` |

## 非破坏性评测命令

```bash
python3 scripts/check_production_config.py --mode production --skip-domain-https
python3 scripts/run_release_acceptance.py --json --include-backup-verify --backup-verify-compose
python3 scripts/run_nightly_live_gates.py --json
python3 scripts/run_nightly_live_gates.py --plan-only --include-md-blackbox
python3 scripts/run_nightly_live_gates.py --fail-closed-external --json
python3 scripts/rollback_plan.py --mode aliyun-app --json
```

## 真实维护窗口执行顺序

1. 冻结发布基线：记录 git revision、部署包路径、数据库备份路径和 OSS snapshot 前缀。
2. 运行发布前 gate：`run_release_acceptance.py`、`run_nightly_live_gates.py`。
3. 进入维护窗口：确认 `MAINTENANCE_WINDOW_ID` 和 `ALLOW_PRODUCTION_DRILL=true`。
4. 执行回滚计划中的 stop / restore / restart 步骤，逐步确认服务状态。
5. 执行数据库和对象存储恢复后的 smoke：`/api/health`、登录、文件下载、chat/SSE、任务状态。
6. 归档记录到 `docs/manuals/drill-records/`。

## MD 黑盒 gate

- 默认只在 `--plan-only` 或显式 `--include-md-blackbox` 时出现在 nightly 计划里。
- `--fail-closed-external` 会把缺少输入的 MD 黑盒 gate 标为 `blocked`。
- 若要复用已有任务，提供 `MD_BLACKBOX_TASK_ID`、`MD_BLACKBOX_EMAIL`、`MD_BLACKBOX_PASSWORD`。
- 若要提交新任务，额外设置 `ALLOW_MD_BLACKBOX_SUBMIT=true`，并在维护窗口内执行。

## 当前已完成演练证据

| 演练 | 状态 | 证据 |
|---|---|---|
| 线上 DB 备份 | 已完成 | `/opt/protein-ai-platform/backups/protein_ai_20260722T234645Z.dump` |
| checksum / pg_restore list | 已通过 | `.sha256` OK，`pg_restore --list` entries=359 |
| OSS offsite shadow | 已通过 | `oss://crvab/drills/offsite-backups/protein_ai_20260722T234645Z.dump` |
| 异地下载恢复 | 已通过 | 临时 PostgreSQL 表 sanity：`public_table_count=40`，`users_row_count=79` |
| 生产停服回滚 | 未执行 | 等维护窗口 |
| 生产对象路径切换 | 未执行 | 等独立 shadow 目标和维护窗口 |
