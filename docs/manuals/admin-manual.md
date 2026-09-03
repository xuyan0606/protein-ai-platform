# 管理员手册

适用版本：0.1.0

## 管理入口

- Web 管理后台：`/admin`
- 需要用户角色为 `admin`
- 后端会强制校验管理员权限，前端入口隐藏不等于安全边界

## 用户与角色

当前支持两类角色：

- `admin`：可访问管理后台、跨用户任务审计、用户角色管理
- `researcher`：普通研发用户

管理员可在 `/admin` 中修改其他用户角色。系统禁止管理员把自己的账号降级，避免锁死后台。

## 任务审计

管理后台可查看跨用户工具任务审计，包括：

- task id
- 用户 id
- 工具名
- 状态
- 队列
- 进度
- 阶段
- 错误摘要

CSV 导出入口：`/api/tools/admin/tasks/audits/export`

导出内容是脱敏摘要，不包含原始 PDB 文本、序列、token、password、secret。

## 部署与升级

常用检查：

```bash
make env-preflight
make release-acceptance
make upgrade-readiness
make package-deploy-bundle-dry-run
make rollback-plan
```

本地升级预览：

```bash
make upgrade-dry-run
```

正式升级前必须先确认：

- 有最近一次数据库备份
- `make upgrade-readiness` 无 critical
- `make rollback-plan` 已确认可用备份、部署包和 destructive 步骤
- `deploy_data/` 中真实数据状态符合上线要求
- 当前变更已经纳入发布包或版本记录

发布验收、权限矩阵和告警 dispatch 见：

- [产品化验收操作手册](productization-acceptance-manual.md)
- [截图版操作手册（文字占位版）](screenshot-operation-placeholder-manual.md)
- [故障与回滚演练记录模板](drill-record-template.md)

## 备份恢复

备份预览：

```bash
make backup-dry-run
```

本地 Docker 备份：

```bash
make backup-local
```

恢复预览：

```bash
make restore-dry-run BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
```

恢复会删除并重建数据库。没有确认前不要执行真实恢复。

## 维护窗口边界

可在普通工作时间执行：

- `/admin` 用户与任务审计只读查看
- 审计 CSV 导出
- `make backup-dry-run`
- `make rollback-plan`
- 临时库恢复演练 dry-run

必须安排维护窗口执行：

- 生产数据库真实 restore
- 生产服务真实 rollback
- 生产 `deploy_data/` 或 lipase.db 替换
- 异地备份恢复后切换生产访问路径
- 可能触发外部值班流程的真实告警 dispatch
