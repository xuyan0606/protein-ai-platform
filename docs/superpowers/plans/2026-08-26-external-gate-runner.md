# 统一外部门禁执行器实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个默认只读、密钥不落盘、只执行 armed 门并生成可追溯证据的统一外部门禁 CLI。

**架构：** `external_gate_contract.py` 只定义门禁、输入和证据策略；`run_external_gate.py` 负责输入发现、白名单子进程执行、状态聚合和证据归档。现有 smoke/validator 脚本继续承担具体外部验证，统一执行器不重写科学工具。

**技术栈：** Python 3.9+ 标准库、pytest、现有 shell/Python smoke 脚本、JSON/Markdown、SHA-256。

---

## 文件结构

- 创建：`scripts/external_gate_contract.py` — 七条门禁的纯数据合同、输入完整性和证据升级规则。
- 创建：`scripts/run_external_gate.py` — CLI、白名单命令构造、执行、脱敏和证据归档。
- 创建：`backend/tests/test_external_gate_runner.py` — 合同、状态机、安全边界和 CLI 回归。
- 修改：`Makefile` — 增加 plan、单门执行和全部门禁入口。
- 创建：`docs/manuals/external-gate-runner.md` — 运维使用说明、输入变量和安全边界。
- 修改：`progress.md`、`findings.md` — 记录实现结果和真实阻塞，不记录秘密。

### 任务 1：定义七条门禁合同

**文件：**
- 创建：`scripts/external_gate_contract.py`
- 创建：`backend/tests/test_external_gate_runner.py`

- [ ] **步骤 1：编写失败的合同测试**

```python
from scripts.external_gate_contract import GateStatus, gate_contracts, evaluate_inputs


def test_contract_covers_seven_external_gates():
    contracts = gate_contracts()
    assert set(contracts) == {
        "production_https", "foldseek_live", "gpu_md", "ligand_runtime",
        "oss_minio", "admin_screenshot", "maintenance_restore",
    }


def test_missing_secret_keeps_oss_gate_blocked():
    result = evaluate_inputs("oss_minio", {"OSS_ENDPOINT": "oss.example", "OSS_BUCKET": "smoke"})
    assert result.status is GateStatus.BLOCKED
    assert "OSS_ACCESS_KEY" in result.missing
    assert "OSS_SECRET_KEY" in result.missing
```

- [ ] **步骤 2：运行测试确认红灯**

运行：

```bash
PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_external_gate_runner.py -q
```

预期：FAIL，`ModuleNotFoundError: scripts.external_gate_contract`。

- [ ] **步骤 3：实现最小合同**

```python
class GateStatus(str, Enum):
    PLANNED = "planned"
    BLOCKED = "blocked"
    ARMED = "armed"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True)
class GateContract:
    name: str
    priority: str
    lane: str
    required_inputs: tuple[str, ...]
    secret_inputs: tuple[str, ...]
    command_id: str
    destructive: bool = False
```

`gate_contracts()` 返回七条固定合同；`evaluate_inputs()` 只检查存在性，并且 maintenance gate 即使输入完整也返回 `MANUAL_REQUIRED`。

- [ ] **步骤 4：运行测试确认绿灯**

运行同上。预期：合同测试全部 PASS。

- [ ] **步骤 5：只提交任务 1 文件**

```bash
git add scripts/external_gate_contract.py backend/tests/test_external_gate_runner.py
git commit -m "feat: define external gate contracts"
```

### 任务 2：实现默认 plan-only 和 armed-only 执行

**文件：**
- 修改：`scripts/run_external_gate.py`
- 修改：`backend/tests/test_external_gate_runner.py`

- [ ] **步骤 1：编写失败的执行选择测试**

```python
def test_default_mode_never_runs_subprocess(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: calls.append(a))
    payload, exit_code = runner.run(selected=["oss_minio"], execute=False, values={}, output_root=tmp_path)
    assert calls == []
    assert payload["gates"][0]["status"] == "blocked"
    assert exit_code == 1


def test_execute_all_runs_only_armed_gates(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_execute_gate", lambda gate, values: calls.append(gate.name) or passed(gate.name))
    values = complete_https_inputs()
    payload, _ = runner.run(selected=list(gate_contracts()), execute=True, values=values, output_root=tmp_path)
    assert calls == ["production_https"]
```

- [ ] **步骤 2：运行红灯**

预期：FAIL，runner 模块或 `run()` 不存在。

- [ ] **步骤 3：实现 CLI 和执行器最小闭环**

CLI 参数：

```python
parser.add_argument("--plan-only", action="store_true")
parser.add_argument("--execute", action="store_true")
parser.add_argument("--gate", action="append", choices=sorted(gate_contracts()))
parser.add_argument("--all", action="store_true")
parser.add_argument("--json", action="store_true")
parser.add_argument("--output-root", default="docs/manuals/external-gate-runs")
```

`--execute` 未出现时永不调用子进程；`--all --execute` 遍历所有门，但只把 `ARMED` 交给 `_execute_gate()`。

- [ ] **步骤 4：运行绿灯并验证 CLI**

```bash
PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_external_gate_runner.py -q
python3 scripts/run_external_gate.py --plan-only --json
```

预期：测试 PASS；CLI 返回 blocked 计划且 `network_io=not_executed`。

- [ ] **步骤 5：Commit**

```bash
git add scripts/run_external_gate.py backend/tests/test_external_gate_runner.py
git commit -m "feat: add fail-closed external gate runner"
```

### 任务 3：接入白名单命令与证据升级规则

**文件：**
- 修改：`scripts/external_gate_contract.py`
- 修改：`scripts/run_external_gate.py`
- 修改：`backend/tests/test_external_gate_runner.py`

- [ ] **步骤 1：编写失败的白名单和证据测试**

```python
@pytest.mark.parametrize("status", ["submitted", "pending", "capability_ready", "demo-ready", "proxy"])
def test_nonterminal_evidence_never_passes(status):
    assert runner.classify_result("foldseek_live", 0, {"status": status}) is GateStatus.FAILED


def test_command_is_argv_not_shell_string():
    command = runner.build_command("production_https", complete_https_inputs())
    assert isinstance(command, list)
    assert command[:2] == [sys.executable, "scripts/check_production_config.py"]
    assert all(";" not in part for part in command)
```

- [ ] **步骤 2：运行红灯**

预期：FAIL，`classify_result` / `build_command` 不存在。

- [ ] **步骤 3：实现七条白名单适配器**

命令 ID 映射到固定 argv：

- HTTPS → strict `check_production_config.py`；
- Foldseek → `structure_smoke_readiness.py --require-live`；
- GPU/MD → topology live gate或 MD resume；
- ligand → runtime readiness `--require-ligand-ready`；
- OSS → `smoke_oss_minio_contract.py --require-live`；
- admin screenshot →现有 screenshot/live smoke；
- maintenance →仅 release acceptance plan/manual evidence validator，不执行 destructive command。

解析器要求 exit code 0 且终态字段满足各 gate 合同。未知输出、非 JSON 或非终态全部 failed。

- [ ] **步骤 4：运行绿灯**

预期：白名单和证据分类测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add scripts/external_gate_contract.py scripts/run_external_gate.py backend/tests/test_external_gate_runner.py
git commit -m "feat: enforce external gate evidence contracts"
```

### 任务 4：密钥保护和 evidence manifest

**文件：**
- 修改：`scripts/run_external_gate.py`
- 修改：`backend/tests/test_external_gate_runner.py`

- [ ] **步骤 1：编写失败的脱敏与哈希测试**

```python
def test_reports_never_contain_secret_values(tmp_path):
    secret = "super-secret-storage-value"
    payload, _ = runner.run(
        selected=["oss_minio"], execute=False,
        values=complete_oss_inputs(secret=secret), output_root=tmp_path,
    )
    rendered = json.dumps(payload)
    assert secret not in rendered
    assert payload["gates"][0]["secret_inputs_present"] == ["OSS_ACCESS_KEY", "OSS_SECRET_KEY"]


def test_evidence_manifest_matches_written_files(tmp_path):
    run_dir = runner.write_evidence(sample_payload(), tmp_path)
    manifest = json.loads((run_dir / "evidence-manifest.json").read_text())
    for row in manifest["files"]:
        path = run_dir / row["path"]
        assert row["size"] == path.stat().st_size
        assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
```

- [ ] **步骤 2：运行红灯**

预期：FAIL，报告含敏感值或 manifest 不存在。

- [ ] **步骤 3：实现脱敏与归档**

只保存：字段存在性、secret 名称、命令 ID、状态、退出码、证据路径。stdout/stderr 经过敏感值替换后才可写入；发现无法脱敏的疑似 secret 时拒绝归档并标记 failed。

- [ ] **步骤 4：运行绿灯**

预期：secret 测试和 manifest 测试 PASS。

- [ ] **步骤 5：Commit**

```bash
git add scripts/run_external_gate.py backend/tests/test_external_gate_runner.py
git commit -m "feat: archive redacted external gate evidence"
```

### 任务 5：运维入口和文档

**文件：**
- 修改：`Makefile`
- 创建：`docs/manuals/external-gate-runner.md`
- 修改：`backend/tests/test_external_gate_runner.py`

- [ ] **步骤 1：编写失败的入口合同测试**

```python
def test_makefile_exposes_external_gate_commands():
    content = (PROJECT_ROOT / "Makefile").read_text()
    assert "external-gates-plan:" in content
    assert "external-gate:" in content
    assert "external-gates-execute:" in content
```

- [ ] **步骤 2：运行红灯**

预期：FAIL，Makefile targets 不存在。

- [ ] **步骤 3：增加 Makefile 和手册**

```make
external-gates-plan:
	$(PYTHON) scripts/run_external_gate.py --plan-only --all

external-gate:
	$(PYTHON) scripts/run_external_gate.py --execute --gate $(GATE)

external-gates-execute:
	$(PYTHON) scripts/run_external_gate.py --execute --all
```

手册逐门列出非敏感参数、secret 环境变量、执行命令、证据输出和禁止行为。

- [ ] **步骤 4：运行绿灯和手册检查**

```bash
PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_external_gate_runner.py -q
make external-gates-plan
```

预期：测试 PASS；plan 输出 7 gates，零外部调用。

- [ ] **步骤 5：Commit**

```bash
git add Makefile docs/manuals/external-gate-runner.md backend/tests/test_external_gate_runner.py
git commit -m "docs: add external gate operator workflow"
```

### 任务 6：全量验证和治理材料同步

**文件：**
- 修改：`progress.md`
- 修改：`findings.md`
- 重新生成：`docs/manuals/remaining-backlog-*.json`
- 重新生成：`docs/manuals/remaining-backlog-*.md`

- [ ] **步骤 1：运行定向测试**

```bash
PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_external_gate_runner.py backend/tests/test_config_validation.py -q
```

预期：全部 PASS。

- [ ] **步骤 2：运行后端全量回归**

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

预期：0 failed。

- [ ] **步骤 3：运行前端和静态检查**

```bash
cd frontend && npm run build && npm run lint
python3 -m py_compile scripts/external_gate_contract.py scripts/run_external_gate.py
git diff --check
```

预期：全部退出码 0。

- [ ] **步骤 4：运行只读 release acceptance**

```bash
python3 scripts/run_release_acceptance.py --json --include-frontend --include-backup-verify --backup-verify-compose
```

预期：0 failed；HTTPS、维护窗口和外部目标仍保持 manual gates。

- [ ] **步骤 5：重建并校验治理材料**

```bash
python3 scripts/build_remaining_backlog_operator_packet_manifest.py
python3 scripts/build_remaining_backlog_go_no_go_summary.py
python3 scripts/validate_remaining_backlog_execution_tickets.py
```

预期：manifest missing=0；tickets failure_count=0；缺外部输入的 gate 不得 armed。

- [ ] **步骤 6：记录结果并提交明确文件**

```bash
git add progress.md findings.md scripts/external_gate_contract.py scripts/run_external_gate.py \
  backend/tests/test_external_gate_runner.py Makefile docs/manuals/external-gate-runner.md
git commit -m "feat: unify external release gates"
```

提交前使用 `git diff --cached --name-only` 确认不包含用户既有变更。
