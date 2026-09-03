# 本机测试 Runner 与黑盒 Gate

更新时间：2026-08-19

## 边界

- 不在生产容器内跑 pytest。
- 不读取云账号、数据库、Redis、OSS 或 OIDC 明文凭据。
- 不联网安装依赖。
- 不自动提交 MD 长任务。
- `plan-only` 只输出命令、缺口和风险，不执行浏览器、HTTP 或 pytest。

## Pytest Runner

远端标准来源是 `.github/workflows/ci.yml` 的 `backend-test` job。本机镜像入口：

```bash
make pytest-runner-plan
make pytest-runner
make pytest-runner-json
```

`make pytest-runner` 使用 `backend/.venv/bin/python`，强制 `USE_SQLITE=true`，并生成临时 `TEST_DATABASE_URL`。执行前会审计 CI contract，缺少 `backend-test`、独立 SQLite 测试库、pytest 命令或 coverage artifact 时 fail-closed。

## 浏览器 Gate

只读合同检查：

```bash
make browser-smoke-plan
```

真实浏览器 smoke 必须显式打开：

```bash
python3 scripts/run_acceptance_matrix.py --include-browser-smoke --json
```

没有启动本地前后端或没有设置 `FRONTEND_BASE_URL` 时，不应把浏览器 gate 写成已通过。发布前需要严格模式时：

```bash
make acceptance-matrix-fail-closed
```

该模式会把未武装的浏览器 gate 标为 `blocked`。

## MD Blackbox Gate

只读计划：

```bash
make backend-md-blackbox-plan
```

复用已有任务优先：

```bash
make backend-md-blackbox MD_BLACKBOX_ARGS='--task-id <task-id> --email <email>'
```

提交新任务必须显式授权：

```bash
ALLOW_MD_BLACKBOX_SUBMIT=true make backend-md-blackbox
```

需要发布前严格阻断时：

```bash
python3 scripts/run_acceptance_matrix.py --fail-closed-external --json
python3 scripts/run_nightly_live_gates.py --fail-closed-external --json
```

缺少 task id、账号引用或提交授权时，MD blackbox 必须保持 `blocked` 或 plan-only，不得记为 live 已验证。
