# 本机演练归档：截图与 Ligand Gate

| 字段 | 内容 |
|---|---|
| 归档编号 | DRILL-20260710-LOCAL-001 |
| 演练日期 | 2026-07-10 |
| 演练名称 | 本机截图归档与 ligand runtime gate 验证 |
| 演练类型 | screenshot / ligand-gate / compose-config |
| 环境 | local |
| 是否维护窗口 | no |
| 维护窗口编号 | 不适用 |
| 版本 | 0.1.0 |
| 执行人 | Codex |
| 复核人 | 待人工复核截图内容 |

## 执行边界

本记录只覆盖本机非生产演练：

- 生成真实浏览器截图文件和 manifest。
- 执行 ligand toolchain smoke。
- 执行 ligand worker compose config 校验。
- 执行前端生产构建和后端配置测试。

未执行：

- 生产回滚。
- 生产数据库恢复。
- 异地备份恢复。
- 真实 Vina docking。
- 真实 ligand topology。
- 真实 GROMACS 复合物 MD。

## 执行命令与结果

| 命令 | 结果 |
|---|---|
| `FRONTEND_BASE_URL=http://127.0.0.1:4203 node scripts/capture_manual_screenshots.mjs` | `manual_screenshots status=ok count=6` |
| `python3 -m json.tool docs/manuals/screenshots/manifest.json` | JSON 解析通过 |
| `file docs/manuals/screenshots/*.png` | 6 张 PNG，均为 `1440 x 1100` |
| `make backend-ligand-toolchain-smoke` | `blocked_toolchain_missing`，确认 SDF 为 2D，缺少真实工具链 |
| `make docker-config-ligand-worker` | 通过，无明文 env 输出 |
| `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` | `84 passed` |
| `cd frontend && npm run build` | 通过，无 3Dmol `eval` 或 chunk size 构建警告 |

## 截图归档

| 截图编号 | 文件路径 | 状态 | 备注 |
|---|---|---|---|
| SHOT-AUTH-001 | `docs/manuals/screenshots/auth-login.png` | captured | 登录页 |
| SHOT-DATA-001 | `docs/manuals/screenshots/data-readiness.png` | captured | 数据 readiness |
| SHOT-DATA-004 | `docs/manuals/screenshots/data-experiment-feedback.png` | captured | 实验反馈与组合检查 |
| SHOT-LIPASE-001 | `docs/manuals/screenshots/lipase-evidence-browser.png` | captured | Lipase 证据浏览 |
| SHOT-OPS-001 | `docs/manuals/screenshots/ops-summary-alerts.png` | captured | 运维 summary |
| SHOT-ADMIN-001 | `docs/manuals/screenshots/admin-users.png` | partial | 未提供 admin 登录凭据，最终 URL 为登录页 |

Manifest：

```text
docs/manuals/screenshots/manifest.json
```

## Ligand Gate 结论

本机当前 ligand pipeline 状态为 `blocked_toolchain_missing`：

```text
missing=conformer_generation,pdbqt_preparation,vina_docking,ligand_topology,gromacs_md
```

该状态说明：

- 2D SDF 输入已可解析。
- 本机未安装完整 OpenBabel/RDKit、Vina、ACPYPE/Antechamber 和 GROMACS runtime。
- 平台没有伪造 3D、PDBQT、docking、topology 或 MD 结果。
- `docker-config-ligand-worker` 已通过，后续可在具备网络/镜像源的节点执行 `docker-build-ligand-worker`。

## 后续动作

| 动作 | 负责人 | 状态 |
|---|---|---|
| 使用 admin 测试账号重新生成后台截图 | 待定 | pending |
| 在具备工具链的容器/服务器执行 `ligand-runtime-check --require-live` | 待定 | pending |
| 安装或提供 OpenBabel/RDKit/Vina/ACPYPE/AmberTools/GROMACS runtime | 待定 | pending |
| 执行真实 PDBQT、Vina docking、ligand topology 阶段 | 待定 | pending |

## 结论

- [x] 本机截图自动归档通过。
- [x] 本机 ligand smoke 安全阻断符合预期。
- [x] ligand worker compose config 通过。
- [ ] 未完成真实 ligand runtime live gate。
- [ ] 未执行生产维护窗口演练。
