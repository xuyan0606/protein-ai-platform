# 外部基础设施验收清单

适用范围：正式域名/HTTPS/OIDC、GPU/GROMACS 节点、维护窗口演练、异地备份恢复、外部对象存储恢复和真实数据更新制度。

默认状态：未提供真实外部输入时均为 `pending` 或 `manual_required`。不得把本地 dry-run、demo smoke 或 plan-only 输出写成已上线。

## 统一证据格式

每个外部依赖验收记录必须包含：

| 字段 | 要求 |
|---|---|
| 负责人 | 真实执行人或审批人 |
| 输入 | 域名、证书、账号、节点、备份引用、恢复目标或数据源 |
| 命令/操作 | 实际执行命令、控制台操作或变更单编号 |
| 通过标准 | 可复验的 HTTP 状态、证书信息、任务结果、checksum 或 smoke 结果 |
| 失败回滚 | 回滚 DNS、证书、服务、数据库或对象存储路径的动作 |
| 证据归档位置 | drill record、日志、截图、JSON 输出、备份 sidecar 或工单链接 |

## 正式域名 + HTTPS + OIDC Callback

| 项 | 要求 |
|---|---|
| 负责人 | 运维负责人 + 平台负责人 |
| 输入 | 正式域名、DNS 解析、证书文件/证书服务、OIDC callback URL |
| 命令/操作 | 更新反向代理、`PUBLIC_BASE_URL`、`FRONTEND_URL`、OIDC redirect/callback 配置 |
| 通过标准 | HTTP 80 跳转或按策略关闭；HTTPS 443 返回 200；证书 CN/SAN 匹配正式域名；登录、Wiki OIDC、文件下载 smoke 通过 |
| 失败回滚 | 恢复上一版 nginx/compose/env；DNS 回滚到旧入口或临时入口 |
| 证据归档位置 | `docs/manuals/drill-records/<date>-domain-https-oidc.md` |

最小复验命令：

```bash
curl -I https://<domain>/api/health
curl -I https://<domain>/
python3 scripts/smoke_admin_oidc_tools_live.py --base-url https://<domain> --json
```

## GPU/GROMACS 节点

| 项 | 要求 |
|---|---|
| 负责人 | 计算节点负责人 |
| 输入 | GPU/ECS 实例、NVIDIA driver、CUDA、GROMACS、`GROMACS_BIN`、worker 队列配置 |
| 命令/操作 | 启动 GPU/MD worker，执行 topology live gate、mutant prepare、replicate submit、batch summary |
| 通过标准 | `gmx`/`gmx_mpi` 可执行；topology live gate 通过；WT/mutant replicate 任务有 TPR/XTC/EDR/XVG/log artifact；batch summary ranking gate 输出 |
| 失败回滚 | 停止 GPU worker；任务标记 blocked/failed；不把未完成 MD 写入报告结论 |
| 证据归档位置 | `docs/manuals/drill-records/<date>-gpu-gromacs-live.md` |

最小复验命令：

```bash
make backend-md-topology-live-gate
python3 scripts/run_acceptance_matrix.py --include-md-blackbox -- --timeout 900 --poll-interval 10
```

## 维护窗口真实回滚演练

| 项 | 要求 |
|---|---|
| 负责人 | 发布负责人 + 数据库负责人 |
| 输入 | `MAINTENANCE_WINDOW_ID`、`ALLOW_PRODUCTION_DRILL=true`、部署包、数据库备份 |
| 命令/操作 | 维护窗口内执行 rollback plan、backup verify、restore drill 或真实回滚演练 |
| 通过标准 | 备份 checksum 和 `pg_restore` 校验通过；临时库恢复 sanity check 通过；真实回滚演练有回滚前后 health/smoke 记录 |
| 失败回滚 | 恢复当前 release；撤销数据库恢复动作；解除维护模式前必须复验 health |
| 证据归档位置 | `docs/manuals/drill-records/<date>-maintenance-rollback.md` |

默认验收只会返回 `manual_required`，不会执行破坏性动作。

## 异地备份恢复演练

| 项 | 要求 |
|---|---|
| 负责人 | 备份负责人 |
| 输入 | `OFFSITE_BACKUP_TARGET`、`OFFSITE_RESTORE_TARGET`、备份文件和 checksum sidecar |
| 命令/操作 | 上传备份到异地目标；从异地副本下载；恢复到独立临时/预发数据库 |
| 通过标准 | 下载 checksum 与 sidecar 一致；恢复目标独立于生产；表数量、用户记录、关键业务表 sanity check 通过 |
| 失败回滚 | 删除失败恢复目标；保留原始备份；重新生成 sidecar |
| 证据归档位置 | `docs/manuals/drill-records/<date>-offsite-restore.md` |

## 外部对象存储恢复验证

| 项 | 要求 |
|---|---|
| 负责人 | 存储负责人 |
| 输入 | `EXTERNAL_STORAGE_BACKUP_REF`、`EXTERNAL_STORAGE_RESTORE_TARGET`、样本 artifact key 清单 |
| 命令/操作 | 将备份对象恢复到 shadow bucket/prefix；应用以只读方式读取样本 artifact |
| 通过标准 | shadow 路径与生产路径分离；样本文件 HEAD/GET/Range 正常；应用 smoke 能读取恢复样本 |
| 失败回滚 | 删除 shadow 恢复路径；不切换生产 bucket/prefix |
| 证据归档位置 | `docs/manuals/drill-records/<date>-external-storage-restore.md` |

## 数据更新制度

| 数据源 | 频率 | 通过标准 | 证据归档位置 |
|---|---|---|---|
| PDB | 每周 | manifest 更新，新增/变更数量可解释，`make check-deploy-data` 不退化 |
| AlphaFold | 每月 | 目标 accession 结构和 PAE 文件完整 |
| SIFTS | 每月 | mapping 文件版本更新，demo-only 状态不得冒充 live |
| annotations | 每月 | UniProt/InterPro/SignalP/M-CSA 来源和版本可追溯 |
| Foldseek DB | 每月或季度 | DB index 完整，无非便携 symlink，live smoke 通过 |

最小复验命令：

```bash
make deploy-data-update-plan
make check-deploy-data
make deploy-live-gate
```

## 发布前判定

| 状态 | 含义 |
|---|---|
| `passed` | 真实外部输入已提供，命令执行通过，证据已归档 |
| `manual_required` | 自动门禁通过，但仍缺维护窗口、恢复目标或人工审批 |
| `pending` | 依赖尚未准备，不能写成已上线 |
| `blocked` | 输入或环境不满足，通过前不得发布对应能力 |

生产发布说明只能写“自动代码门禁通过”或“等待人工发布门”，不能把 `manual_required` / `pending` 写成已完成上线。
