# 故障与回滚演练记录模板

适用版本：0.1.0

## 基本信息

| 字段 | 内容 |
|---|---|
| 演练日期 | YYYY-MM-DD |
| 演练环境 | local / staging / production |
| 负责人 |  |
| 参与人 |  |
| 维护窗口 |  |
| 版本 | 0.1.0 |
| Git revision |  |

## 演练类型

- [ ] 发布验收
- [ ] 数据库备份校验
- [ ] 临时库恢复演练
- [ ] 真实回滚演练
- [ ] 异地备份恢复演练
- [ ] 外部告警发送演练
- [ ] MD 长任务失败演练
- [ ] deploy_data live gate 演练
- [ ] lipase curation 发布演练
- [ ] lipase.db staged copy 替换演练

## 执行边界

可在本机或预发环境执行并归档：

- 发布验收 dry-run。
- 回滚计划生成。
- 数据库备份、checksum 和 `pg_restore --list` 校验。
- 临时库恢复演练。
- 维护窗口 gate plan-only 检查，见 [维护窗口演练 Runbook](maintenance-drill-runbook.md)。
- lipase curation batch dry-run、prepared batch 和 publish 记录归档。

必须在维护窗口执行：

- 生产数据库真实 restore。
- 生产服务真实 rollback。
- 生产 `deploy_data/` 替换。
- 生产 lipase.db staged copy 替换。
- 异地备份恢复后切换生产访问路径。
- 外部存储恢复验证会影响生产读写路径的操作。

## 前置条件

| 检查项 | 命令 | 结果 |
|---|---|---|
| 环境预检 | `make env-preflight` |  |
| 升级 readiness | `make upgrade-readiness` |  |
| 发布验收 | `make release-acceptance` |  |
| 回滚计划 | `make rollback-plan` |  |
| 数据 live gate | `make deploy-live-gate` |  |
| 备份校验 | `make verify-backup BACKUP_FILE=...` |  |
| 维护窗口 gate | `python3 scripts/run_release_acceptance.py --json` |  |

## 操作步骤

| 时间 | 操作 | 执行人 | 结果 | 备注 |
|---|---|---|---|---|
|  |  |  |  |  |

## 关键输出

粘贴关键命令输出，不要粘贴 token、password、secret。

```text

```

## 截图归档

截图必须来自真实浏览器或真实终端输出；不要生成伪截图。

| 截图编号 | 文件路径 | 对应步骤 | 是否已补齐 | 备注 |
|---|---|---|---|---|
| SHOT-AUTH-001 | `docs/manuals/screenshots/auth-login.png` | 登录页 | yes | 自动截图已归档 |
| SHOT-ADMIN-001 | `docs/manuals/screenshots/admin-users.png` | 管理员用户管理 | partial | 未登录自动截图会回到登录页；后台内容待 admin 登录后补齐 |
| SHOT-DATA-001 | `docs/manuals/screenshots/data-readiness.png` | 数据 readiness | yes | 自动截图已归档 |
| SHOT-DATA-004 | `docs/manuals/screenshots/data-experiment-feedback.png` | 实验反馈和组合检查 | yes | 自动截图已归档 |
| SHOT-LIPASE-001 | `docs/manuals/screenshots/lipase-evidence-browser.png` | Lipase 证据浏览 | yes | 自动截图已归档 |
| SHOT-LIPASE-002 | `docs/manuals/screenshots/lipase-curation-batch.png` | lipase batch manifest | no | 待真实浏览器补齐 |
| SHOT-OPS-001 | `docs/manuals/screenshots/ops-summary-alerts.png` | 运维 summary | yes | 自动截图已归档 |
| SHOT-DRILL-001 | `docs/manuals/screenshots/rollback-plan.png` | 回滚计划 | no | 待真实执行补齐 |
| SHOT-DRILL-002 | `docs/manuals/screenshots/backup-restore-drill.png` | 备份/恢复演练 | no | 待真实执行补齐 |

## Lipase Curation 发布归档

| 字段 | 内容 |
|---|---|
| batch id / batch key |  |
| record ids |  |
| record 来源 | literature / experiment / tool_feedback / manual_note |
| 发布人 |  |
| 复核人 |  |
| 发布时间 |  |
| 确认令牌 | `PUBLISH_LIPASE_CURATION_BATCH` |
| manifest 摘要 |  |
| export payload 保存位置 |  |
| staged SQLite 路径 |  |
| integrity_check 结果 |  |
| foreign_key_check 结果 |  |
| 是否替换生产 lipase.db | yes / no |
| 是否需要维护窗口 | yes / no |
| 维护窗口编号 |  |
| 回滚文件路径 |  |

结论：

- [ ] 仅完成 batch dry-run / manifest 预览。
- [ ] 已完成平台 publish 记录。
- [ ] 已在维护窗口完成 staged lipase.db 校验。
- [ ] 已在维护窗口完成生产 lipase.db 替换。
- [ ] 未执行生产替换，本记录仅为发布准备归档。

## 问题记录

| 问题 | 影响 | 根因 | 处理 | 是否复现 |
|---|---|---|---|---|
|  |  |  |  |  |

## 回滚判定

| 条件 | 是否触发 | 说明 |
|---|---|---|
| readiness manual_required |  |  |
| live gate failed |  |  |
| 数据恢复失败 |  |  |
| 关键接口 5xx |  |  |
| MD 任务大量失败 |  |  |
| 文件下载权限异常 |  |  |
| lipase staged DB 校验失败 |  |  |
| 异地备份恢复不可用 |  |  |

## 已执行演练归档

每次演练完成后复制本节追加一条记录。未在维护窗口执行的项目必须标注“未执行”，不能写成已完成。

| 字段 | 内容 |
|---|---|
| 归档编号 | DRILL-YYYYMMDD-001 |
| 演练名称 |  |
| 演练类型 | rollback / restore-drill / offsite-backup / lipase-curation / deploy-data |
| 环境 | local / staging / production |
| 是否维护窗口 | yes / no |
| 维护窗口编号 |  |
| 开始时间 |  |
| 结束时间 |  |
| 执行人 |  |
| 复核人 |  |
| 涉及版本 |  |
| 涉及备份文件 |  |
| 涉及 deploy_data 版本 |  |
| 涉及 lipase batch |  |
| 执行命令/页面动作 |  |
| 关键输出位置 |  |
| 截图路径 |  |
| 结果 | passed / passed-with-actions / failed / not-executed |
| 未执行原因 |  |
| 后续动作 |  |

维护窗口确认：

- [ ] 本演练不需要维护窗口。
- [ ] 本演练已在维护窗口执行。
- [ ] 本演练需要维护窗口，但本次未执行。

异地备份专项字段：

| 字段 | 内容 |
|---|---|
| 备份来源 | local / OSS / external disk / other |
| 异地介质 |  |
| 校验方式 | checksum / pg_restore list / restore drill / application smoke |
| 恢复目标 | temporary DB / staging / production |
| 是否影响生产 | yes / no |
| RTO 记录 |  |
| RPO 记录 |  |
| 恢复后抽查 |  |

外部存储恢复专项字段：

| 字段 | 内容 |
|---|---|
| 备份引用 / snapshot id |  |
| 生产 bucket / prefix |  |
| shadow 恢复 bucket / prefix |  |
| 抽查 artifact keys |  |
| 只读/list 权限验证 |  |
| 应用 smoke 结果 |  |
| 是否切换生产路径 | yes / no |

## 结论

- [ ] 演练通过
- [ ] 演练通过但有改进项
- [ ] 演练失败，需要重新安排

## 后续动作

| 动作 | 负责人 | 截止时间 | 状态 |
|---|---|---|---|
|  |  |  |  |
