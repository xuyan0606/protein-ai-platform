# 统一外部门禁执行器设计

## 目标

将当前分散的外部验收脚本统一为一个安全、可审计、默认只读的 CLI。执行器负责发现输入、判定门禁是否 armed、调用现有验证脚本并生成脱敏证据；不重新实现科学计算，也不把计划、能力检查或 pending 状态升级为通过。

## 范围

第一版覆盖七条外部门禁：

1. 正式 HTTPS、DNS、TLS 与 OIDC/public URL 配置。
2. Foldseek live API 或真实 CLI/数据库。
3. GPU/GROMACS topology 与 MD black-box。
4. 配体 2D→3D→PDBQT→Vina→topology→MD 运行时。
5. OSS/MinIO 临时对象写入、读取和删除。
6. 管理员认证截图。
7. 维护窗口回滚、异地备份恢复和外部存储 shadow restore。

不在第一版范围：管理后台 UI、创建云资源、申请域名/证书、安装 GPU 驱动、绕过维护窗口、自动切换生产存储路径。

## 架构

### `scripts/external_gate_contract.py`

提供纯数据合同和状态判定，不执行命令。每个 gate 定义：

- `name`、`priority`、`lane`；
- 所需非敏感输入和敏感输入引用；
- 风险等级；
- 允许调用的既有脚本；
- passed 所需的终态证据；
- 禁止升级的状态和证据等级。

### `scripts/run_external_gate.py`

提供统一 CLI：

```bash
python3 scripts/run_external_gate.py --plan-only
python3 scripts/run_external_gate.py --gate oss_minio --execute
python3 scripts/run_external_gate.py --all --execute
```

行为：

- 默认等同 `--plan-only`；
- `--gate NAME` 选择单门，`--all` 选择全部；
- `--execute` 只执行 armed 门；
- 缺输入的门保持 blocked，且不启动子进程和网络请求；
- 子进程命令来自合同白名单，不接受任意 shell 字符串；
- 汇总执行结果并返回非零退出码，除非所有已选择门均 passed；
- blocked、failed 和 manual_required 均不能被统计为 passed。

### 现有脚本适配

执行器复用现有入口：

- `check_production_config.py`；
- `structure_smoke_readiness.py` / structure smoke；
- `smoke_md_topology.py`、`verify_md_blackbox.py`；
- `smoke_ligand_toolchain.py` / ligand runtime check；
- `smoke_oss_minio_contract.py`；
- 管理员 live smoke / screenshot runner；
- `run_release_acceptance.py`、备份和恢复验证脚本。

执行器仅做编排、输入门控、脱敏和证据归档。

## 输入合同

非敏感输入可来自 CLI 或环境变量。密码、token、access key 只允许：

- 进程环境变量；或
- `--credentials-from-stdin` 的一次性 JSON。

敏感值不得写入命令参数、JSON 报告、Markdown 报告或 progress 日志。报告只记录字段是否存在、secret reference 名称和脱敏指纹，不记录明文。

维护窗口门额外要求：

- `MAINTENANCE_WINDOW_ID`；
- `ALLOW_PRODUCTION_DRILL=true`；
- 独立恢复目标；
- 已通过的部署包和备份 checksum 证据。

MD 新提交额外要求 `ALLOW_MD_BLACKBOX_SUBMIT=true`。存在任务 ID 时优先 resume，不自动新建任务。

## 状态机

```text
planned → blocked | armed → running → passed | failed
```

- `planned`：仅生成计划，未调用外部系统。
- `blocked`：输入、权限、runtime 或人工批准不完整。
- `armed`：输入完整且安全门通过，可以执行。
- `running`：已启动白名单子进程。
- `passed`：子进程成功并满足该门的终态证据合同。
- `failed`：执行失败、证据不完整或清理失败。

`submitted`、`pending`、`capability_ready`、`demo-ready`、proxy 和 mock 永远不能映射为 passed。

## 门禁特殊规则

### OSS/MinIO

- 只使用随机运行 ID 下的临时对象前缀；
- 校验上传内容、下载哈希和删除结果；
- 清理失败时整个 gate 为 failed；
- 不允许操作用户提供的任意对象 key。

### MD/GPU/配体/Foldseek

- 必须验证真实二进制或 live API；
- 拒绝 `echo/true/false/printf` 等占位命令；
- topology 必须包含非空 `.itp/.top/.gro` 和合法 manifest；
- MD 必须达到终态并验证 artifact ownership/download；
- 当前 ARM64 capability 结果不能替代原生 linux/amd64 证据。

### HTTPS

- production strict 模式只接受正式 HTTPS URL；
- `--skip-domain-https` 仅可用于 plan/preparation，不可让 gate passed。

### 回滚与恢复

- 第一版执行器只允许验证、dry-run 和独立临时/shadow 目标；
- 生产 stop/restore/path switch 不由统一执行器自动执行；
- 即使输入完整，也将生产破坏性步骤输出为 manual_required operator action。

## 证据归档

每次运行创建：

```text
docs/manuals/external-gate-runs/<run-id>/
  summary.json
  summary.md
  gates/<gate-name>.json
  evidence-manifest.json
```

报告记录：时间、代码 revision、选择的 gate、输入完整性、白名单命令标识、退出码、状态、证据文件路径和 SHA-256。原始 stdout/stderr 在脱敏后才可归档；默认仅保存结构化摘要。

`evidence-manifest.json` 保存所有证据文件的大小和 SHA-256，用于 source-bound/current 校验。

## 错误处理

- 缺输入：blocked，不运行命令。
- 超时：终止子进程组，failed。
- 输出不是合法 JSON：failed，保存脱敏错误摘要。
- secret 检测命中：拒绝写报告并 failed。
- 部分 gate 失败：其他独立 armed gate 可以继续；汇总保持 failed/blocked。
- 清理失败：相关 gate failed，绝不标记 OSS 或临时资源验收通过。

## 测试策略

采用 TDD，先覆盖：

1. 默认 plan-only 不执行子进程。
2. 缺输入时 selected gate 为 blocked。
3. `--all --execute` 只执行 armed gate。
4. secret 不出现在 JSON/Markdown/命令字段。
5. pending/capability/demo/proxy 不升级为 passed。
6. HTTPS skip 不能通过正式 gate。
7. MD submit 必须显式授权，resume 必须显式密码。
8. OSS key 限定在随机临时前缀且 cleanup 必须成功。
9. 生产回滚仍为 manual_required，执行器不运行破坏性命令。
10. evidence manifest 的哈希、文件数和 source-bound 校验一致。

完成后运行定向测试、后端全量测试、前端 build/lint、release acceptance 与 `git diff --check`。

## 成功标准

- 七条 gate 使用一致的机器可读合同和状态；
- 缺任一关键输入时零外部调用；
- 报告和日志不包含秘密；
- `--all --execute` 不会绕过单门授权；
- 汇总明确区分代码可发布和生产可上线；
- 旧线上版本、现有部署、数据库和对象存储不被第一版执行器修改。
