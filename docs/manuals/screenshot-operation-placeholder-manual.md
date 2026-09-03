# 截图版操作手册

适用版本：0.1.0

## 当前状态

本文用于固化操作路径、截图清单、自动截图归档和演练边界。

当前已生成一批真实浏览器自动截图，归档位置：

```text
docs/manuals/screenshots/
docs/manuals/screenshots/manifest.json
```

本机 Codex 不使用 `view_image` 查看截图内容；截图状态以 Playwright 生成结果、文件元数据和 manifest 为准。需要管理员登录后的后台页面截图时，应提供临时测试账号环境变量或由人工在真实浏览器补齐。

自动截图命令：

```bash
FRONTEND_BASE_URL=http://127.0.0.1:4203 node scripts/capture_manual_screenshots.mjs
make manual-screenshots FRONTEND_BASE_URL=http://127.0.0.1:4203
```

真实截图统一放入：

```text
docs/manuals/screenshots/
```

截图文件只保存界面证据，不得包含 token、password、secret、完整数据库连接串、内部 webhook 地址或未脱敏个人敏感信息。

## 截图补齐规则

| 截图编号 | 建议文件名 | 页面/动作 | 当前状态 | 补齐要求 |
|---|---|---|---|---|
| SHOT-AUTH-001 | `auth-login.png` | `/login` 登录页 | 已自动截图 | 用于证明未登录入口和登录页可达 |
| SHOT-ADMIN-001 | `admin-users.png` | `/admin` 管理员用户列表、角色和账号状态 | 已自动截图但未登录，最终 URL 为登录页 | 使用 admin 账号登录真实浏览器后重新截取后台内容 |
| SHOT-ADMIN-002 | `admin-role-update.png` | 管理员修改其他用户角色或状态后的结果 | 截图待补 | 确认不能把自己降级的保护逻辑可见或有操作记录 |
| SHOT-ADMIN-003 | `admin-task-audits.png` | 管理员任务审计筛选、失败分类、慢任务标记 | 截图待补 | 至少包含筛选条件和审计列表 |
| SHOT-ADMIN-004 | `admin-task-audit-export.png` | 审计 CSV 导出动作或导出结果提示 | 截图待补 | 确认导出内容已脱敏，不展示原始 PDB/SDF 或密钥 |
| SHOT-DATA-001 | `data-readiness.png` | `/data` 数据资产 readiness 总览 | 已自动截图 | 覆盖 PDB、AlphaFold、SIFTS、Foldseek、annotations、smoke 状态 |
| SHOT-DATA-002 | `data-update-history.png` | 数据更新记录和失败原因筛选 | 截图待补 | 展示最近一次更新记录、状态和时间 |
| SHOT-DATA-003 | `data-import-dry-run.png` | 真实数据导入 dry-run/确认前预览 | 截图待补 | 必须停在 dry-run 或确认前，不在截图补齐时执行破坏性动作 |
| SHOT-DATA-004 | `data-experiment-feedback.png` | `/data` 实验反馈录入和组合检查 | 已自动截图 | 覆盖 wet-lab feedback、Go/Watch/No-Go、epistasis 输入区 |
| SHOT-LIPASE-001 | `lipase-evidence-browser.png` | Lipase 证据浏览 | 已自动截图 | 覆盖 paper/variant/gap/evidence 浏览入口 |
| SHOT-LIPASE-QUEUE-001 | `lipase-curation-queue.png` | Lipase curation queue 审核列表 | 截图待补 | 覆盖 submitted/triaged/accepted/rejected 等状态 |
| SHOT-LIPASE-002 | `lipase-curation-batch.png` | accepted records 创建发布批次 | 截图待补 | 覆盖 batch manifest 或 export payload 摘要 |
| SHOT-LIPASE-003 | `lipase-curation-publish.png` | curation batch 发布确认 | 截图待补 | 必须显示确认令牌流程，不能误导为自动写原始 lipase.db |
| SHOT-OPS-001 | `ops-summary-alerts.png` | 运维 summary、队列、worker、告警状态 | 已自动截图 | 外部告警保持 dry-run，真实发送需管理员显式确认 |
| SHOT-DRILL-001 | `rollback-plan.png` | 回滚计划 dry-run 输出或只读计划页 | 截图待补 | 截图不能替代真实维护窗口演练 |
| SHOT-DRILL-002 | `backup-restore-drill.png` | 备份校验/临时库恢复演练记录 | 截图待补 | 可用临时库演练截图；生产恢复必须维护窗口 |

## 管理员操作

### 用户与角色管理

1. 访问 `http://localhost:4200/admin` 或生产域名的 `/admin`。
2. 使用 `admin` 角色账号登录。
3. 查看用户列表，确认目标用户的角色、禁用/锁定状态和最近活动信息。
4. 修改其他用户角色或状态。
5. 保存后刷新页面，确认结果仍存在。

截图待补：

- `SHOT-ADMIN-001`：用户列表。
- `SHOT-ADMIN-002`：角色或状态更新结果。

验收要点：

- 普通 `researcher` 不能访问 `/admin` 管理能力。
- 管理员不能把自己的账号降级导致后台锁死。
- 前端隐藏入口不是安全边界，后端必须继续强制校验 admin 权限。

### 任务审计与导出

1. 在 `/admin` 打开任务审计区域。
2. 按工具名、状态、队列、失败分类、慢任务标记或时间范围筛选。
3. 打开最近失败任务，复核错误摘要、阶段、耗时和运行环境字段。
4. 执行 CSV 导出。
5. 抽查 CSV：不得包含原始 PDB 文本、SDF 原文、token、password、secret。

截图待补：

- `SHOT-ADMIN-003`：任务审计筛选。
- `SHOT-ADMIN-004`：CSV 导出入口或导出结果。

### 运维摘要与告警

1. 打开运维 summary 页面或调用只读接口 `GET /api/ops/summary`。
2. 复核 Redis、队列 backlog、Celery worker、慢请求、5xx 趋势和任务失败趋势。
3. 外部告警先执行 dry-run。
4. 只有管理员明确确认后，才允许真实 dispatch。

截图待补：

- `SHOT-OPS-001`：运维 summary 和告警状态。

维护窗口边界：

- 只读 summary 和 dry-run 不需要维护窗口。
- 真实告警 dispatch 需要管理员确认；如会触发外部值班流程，应在预先通知的时间窗口执行。

## 数据导入操作

### 标准数据目录

真实数据统一进入项目根目录的 `deploy_data/`：

```text
deploy_data/
  annotations/
  sifts/
  foldseek/
  pdb/
  alphafold/
  smoke/
    query.pdb
```

### 导入前 dry-run

1. 准备真实 PDB、AlphaFold、SIFTS、Foldseek DB、annotations 和 smoke PDB。
2. 先执行导入计划或 dry-run，不写入生产数据。
3. 复核计划中的源路径、目标路径、数量、版本、更新时间和缺失项。
4. dry-run 通过后，再安排真实导入或更新。

可用命令入口：

```bash
make deploy-data-update-plan
python3 scripts/run_deploy_data_update.py --plan-only --json
```

真实执行入口：

```bash
make deploy-data-update
make check-deploy-data
make deploy-live-gate
```

截图待补：

- `SHOT-DATA-001`：数据 readiness 总览。
- `SHOT-DATA-002`：更新历史。
- `SHOT-DATA-003`：导入 dry-run/确认前预览。

维护窗口边界：

- `plan-only`、readiness 查看、失败原因筛选可以在普通工作时间执行。
- 真实替换 `deploy_data/`、重建 Foldseek DB、切换生产 `.env.deploy-data` 或触发 live gate 前后的服务重启，应安排维护窗口。
- `demo-ready` 只能证明 demo 数据可跑，不等于真实数据上线可用。

## Lipase Curation 发布

### 当前能力边界

Lipase 接入层已完成：

- 只读接入 `/Users/xuyan/lipase-db/lipase.db`。
- `/data` 可查看 lipase 文献、变体、gap 和证据搜索。
- PDB 页面可在用户确认编号体系后展示 lipase evidence overlay。
- 平台主库已有 curation queue。
- accepted curation records 可进入受控 batch。
- batch publish 需要确认令牌 `PUBLISH_LIPASE_CURATION_BATCH`。

重要边界：

- 原始 `lipase.db` 仍是只读 curated evidence source。
- 平台 publish 记录的是人工审核发布流程，不直接改写原始 SQLite。
- 真正替换 staged lipase.db、同步生产文件或切换服务配置，必须在维护窗口执行。

### 审核与发布流程

1. 普通用户提交 `literature`、`experiment`、`tool_feedback` 或 `manual_note` curation record。
2. 管理员在 curation queue 中复核来源、证据、关联 paper、mutation、position、linked task 和备注。
3. 管理员将记录推进为 `accepted` 或 `rejected`；证据不足时标为 `needs_more_evidence`。
4. 管理员基于 accepted records 创建 curation batch。
5. 先查看 batch manifest/export payload，确认人工导入步骤完整。
6. 提供确认令牌 `PUBLISH_LIPASE_CURATION_BATCH` 后发布 batch。
7. 归档发布记录、人工复核人、发布时间、record ids 和后续 staged DB 校验结果。

截图待补：

- `SHOT-LIPASE-001`：curation queue 审核列表。
- `SHOT-LIPASE-002`：curation batch manifest/export payload。
- `SHOT-LIPASE-003`：发布确认和发布后状态。

维护窗口边界：

- 提交、审核、batch dry-run、batch manifest 预览不需要维护窗口。
- 将 export payload 应用到 staged SQLite、执行 integrity/foreign key check、替换生产 lipase.db、重启服务或切换挂载，必须在维护窗口执行。

### 发布记录归档字段

每次 curation 发布至少归档：

| 字段 | 内容 |
|---|---|
| batch id / batch key |  |
| record ids |  |
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
| 维护窗口编号 |  |
| 回滚文件路径 |  |

## 回滚与异地备份演练

### 可本机完成的演练

以下演练可在本机或预发环境完成，不代表生产维护窗口已执行：

```bash
make rollback-plan
make backup-dry-run
make backup-local
make verify-backup BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
make restore-drill-dry-run BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
make restore-drill BACKUP_FILE=backups/protein_ai_YYYYMMDDTHHMMSSZ.dump
```

截图待补：

- `SHOT-DRILL-001`：回滚计划。
- `SHOT-DRILL-002`：备份校验或临时库恢复演练。

### 必须维护窗口执行的演练

以下事项不得在普通工作时段临时执行：

- 生产数据库真实 restore。
- 生产服务版本真实 rollback。
- 生产 `deploy_data/` 替换或 Foldseek DB 切换。
- 生产 lipase.db staged copy 替换。
- 异地备份介质恢复到独立环境后的服务切换验证。
- 外部存储 OSS/MinIO 恢复验证会影响生产访问路径的操作。

每次演练完成后，将记录填写到 [故障与回滚演练记录模板](drill-record-template.md) 的“已执行演练归档”部分。

## 未完成项

- 真实浏览器截图尚未补齐。
- 真实维护窗口回滚演练尚未执行。
- 真实异地备份恢复演练尚未执行。
- 生产 lipase.db staged copy 替换演练尚未执行。
- 外部存储恢复验证尚未执行。
