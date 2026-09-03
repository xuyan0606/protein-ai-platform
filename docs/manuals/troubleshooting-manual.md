# 故障处理手册

适用版本：0.1.0

## 基础检查

```bash
make env-preflight
make upgrade-readiness
make deploy-preflight
cd docker && docker compose --env-file .env ps
```

## 页面无法访问

检查端口：

- Codex 项目固定使用 `4200-4299`
- 默认入口：`http://localhost:4200`

检查容器：

```bash
cd docker
docker compose --env-file .env ps
docker compose --env-file .env logs backend --tail=100
docker compose --env-file .env logs frontend --tail=100
```

## Wiki state-mismatch

处理顺序：

1. 关闭旧 Wiki 标签页。
2. 重新从平台 `/wiki` 或 `/kb` 进入。
3. 确认 `/auth/oidc` 会跳到 `/wiki/auth/oidc`。
4. 如果仍失败，查看 backend 日志中的 OIDC state。

## 文件下载 403

常见原因：

- artifact 没有绑定当前任务所有者
- 当前用户不是任务提交者
- 任务未完成
- object_name 不在允许下载范围

处理：

```bash
cd backend
.venv/bin/pytest tests/test_tools_api.py -q
```

管理员可在 `/admin` 查看任务审计。

## MD Validation 失败

检查：

- PDB 是否有效
- GROMACS 是否安装
- worker 是否运行
- 任务是否进入 `md_cpu` 队列
- artifact 是否成功写入对象存储

相关命令：

```bash
make backend-md-blackbox
cd docker && docker compose --env-file .env logs md-worker --tail=200
```

## 真实数据未 ready

检查：

```bash
make check-deploy-data
make backend-readiness
make deploy-live-gate
```

如果只看到 `demo-ready`，说明真实数据还不完整。

## 升级失败

升级前必须做：

```bash
make upgrade-readiness
make backup-local
make verify-backup BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
make restore-drill-dry-run BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
make upgrade-dry-run
```

如果升级后服务异常：

1. 查看 backend/frontend/worker 日志。
2. 确认 Alembic 是否成功到 head。
3. 确认 `.env` 和 `.env.deploy-data` 是否同时传入 compose。
4. 必要时用最近 `.dump` 备份恢复数据库。

恢复前先 dry-run：

```bash
make restore-dry-run BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
```

如果只是验证备份能否恢复，优先使用临时库演练，不要直接恢复主库：

```bash
make restore-drill BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
```

`restore-drill` 默认恢复到 `protein_ai_restore_check`，验证后会删除临时库。
