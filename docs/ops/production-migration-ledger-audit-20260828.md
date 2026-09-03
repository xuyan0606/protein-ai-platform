# 线上数据库迁移账本核对（2026-08-28）

## 结论

- 线上 `alembic_version` 当前为 `9c8d7e6f5a41`。
- 本地迁移链当前唯一 head 为 `1a2b3c4d5e6f`。
- 生产库已具备 `9c8d7e6f5a41` 之后的历史迁移对象，说明账本落后于实际结构。
- 14 个本地 revision 中，13 个的表、索引及已抽查的列/外键/唯一约束均已存在。
- 仅 `1a2b3c4d5e6f` 缺少 `workflow_shadow_audits` 及 6 个索引。

## 线上只读证据

| 项目 | 结果 |
| --- | --- |
| Alembic version | `9c8d7e6f5a41` |
| 业务表数量 | 45 |
| 索引数量 | 159 |
| `enzyme_metadata_curation_*` | 已存在，唯一约束/索引存在 |
| `tool_task_audits` | 已存在 |
| `strategy_checkpoints` / `wet_lab_calibration_runs` | 已存在 |
| `analysis_evidence_snapshots` | 已存在 |
| `project_members`、组织权限表 | 已存在 |
| Wiki/会话项目列 | 已存在 |
| `workflow_shadow_audits` | 不存在 |

## 迁移漂移判定

历史迁移对象已在数据库中，但没有同步写入 Alembic 账本。直接执行 `alembic upgrade head` 会从 `9c8d7e6f5a41` 重放历史迁移，并已实际复现 `DuplicateTableError`（`enzyme_metadata_curation_records`）。

## 推荐的最小变更（尚未执行）

1. 在批准的维护窗口内先完成生产数据库备份和校验。
2. 由数据库负责人复核 13 个历史 revision 的对象映射报告。
3. 将账本受控对齐到 `a7c4e2f9b601`（仅修复迁移元数据，不重建表）。
4. 单独执行 `1a2b3c4d5e6f`，创建 `workflow_shadow_audits` 和 6 个索引。
5. 查询新表结构并运行影子审计 API/聊天 SSE 验收。

## 安全状态

- 本次核对全部为只读操作。
- 未执行 `stamp`、未删除或修改业务表、未重启线上服务。
- 旧 release 保持运行并可回滚。

机器可读明细见 `docs/ops/production-schema-drift-report-20260828.json`。
