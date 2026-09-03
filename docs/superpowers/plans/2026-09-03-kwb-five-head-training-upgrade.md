# KWB-EnzymeDesigner 五头训练升级实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在不伪造监督标签、不绕过生产门禁的前提下，统一模型状态事实源，补齐可执行的五头掩码多任务训练内核，并完成当前真实数据允许的研究态验证。

**架构：** 保留现有生产级合取门禁；新增唯一模型状态快照，将规则 MVP、无标签预训练、研究训练和生产模型分层。五头训练使用共享编码器与独立 head，允许样本只携带部分 head 标签，但每个 head 独立满足样本、重复和 group 阈值后才可进入训练；当前 6 行 activity-risk 单测数据只能用于 fail-closed/smoke，不能产出模型质量声明。

**技术栈：** Python 3.13、PyTorch、JSON/JSONL、pytest、现有 KWB 数据/治理报告。

**工作区约束：** 工作区已有大量用户和其他 agent 改动，只修改本计划列出的文件；不提交、不部署、不写生产数据。

---

## 文件结构

- 创建：`AI大模型/scripts/build_model_status_snapshot.py` — 聚合训练、特征、工具和生产门禁，输出唯一状态事实源。
- 创建：`AI大模型/tests/test_model_status_snapshot.py` — 验证状态分层、来源优先级和冲突显式化。
- 创建：`AI大模型/scripts/train_research_multitask.py` — 共享编码器、五个独立 head、缺失标签 mask 和研究态门禁。
- 创建：`AI大模型/tests/test_research_multitask_training.py` — 覆盖空标签、单头不足、五头合格、group 泄漏、近标签特征排除和产物边界。
- 修改：`AI大模型/scripts/train_production_multitask.py` — 仅在生产 gate 与真实训练入口同时满足时调用内核，否则继续 fail-closed。
- 修改：`AI大模型/scripts/test_train_production_multitask.py` — 验证 gate、输入和生产产物约束。
- 修改：`AI大模型/milestones.md` — 将 M5 从“真实小模型完成”澄清为“规则/fixture baseline 完成”。
- 生成：`AI大模型/reports/model_status.json` — 当前唯一状态快照。
- 生成：`AI大模型/reports/research_multitask_training_run.json` — 当前研究态训练/阻断回执。
- 更新：`task_plan.md`、`findings.md`、`progress.md` — 持久化计划、事实和验证结果。

## 任务 1：建立唯一模型状态事实源

- [x] **步骤 1：编写失败测试**

在 `AI大模型/tests/test_model_status_snapshot.py` 覆盖：

```python
def test_snapshot_separates_rule_pretraining_research_and_production(tmp_path):
    snapshot = build_snapshot(tmp_path)
    assert snapshot["stages"]["rule_mvp"]["status"] == "baseline_only"
    assert snapshot["stages"]["pretraining"]["safe_for_model_claim"] is False
    assert snapshot["stages"]["production"]["ready"] is False


def test_snapshot_uses_current_structure_graph_count_and_reports_source_conflict(tmp_path):
    snapshot = build_snapshot(tmp_path)
    assert snapshot["features"]["structure_graph"]["ready_rows"] == 34
    assert snapshot["consistency"]["conflicts"]


def test_snapshot_reports_thermompnn_dimensions_separately(tmp_path):
    tool = build_snapshot(tmp_path)["tools"]["thermompnn"]
    assert set(tool) >= {"installed", "runtime_ready", "dependency_complete", "claim_eligible"}
```

- [x] **步骤 2：运行测试，确认因模块不存在而失败**

运行：

```bash
cd AI大模型
python3 -m pytest -q tests/test_model_status_snapshot.py
```

预期：FAIL，`ModuleNotFoundError: build_model_status_snapshot`。

- [x] **步骤 3：实现最小状态聚合器**

读取以下权威来源并保留 SHA-256：

```text
reports/multitask_training_readiness_report.json
reports/five_head_training_execution_contract_report.json
reports/advanced_model_feature_contract_validation_report.json
reports/sequence_pretraining_continuous_selection.json
reports/ddg_backend_readiness_report.json
reports/production_model_gate_20260829.json
```

输出必须包含 `stages`、`heads`、`features`、`tools`、`consistency`、`next_actions`，且不得将 feature row 计入 label row。

- [x] **步骤 4：运行测试并生成当前快照**

运行：

```bash
cd AI大模型
python3 -m pytest -q tests/test_model_status_snapshot.py
python3 scripts/build_model_status_snapshot.py
```

预期：测试通过；`reports/model_status.json` 明确 `production.ready=false`、`ready_head_count=0`。

## 任务 2：补齐研究态五头掩码训练内核

- [x] **步骤 1：编写失败测试**

`AI大模型/tests/test_research_multitask_training.py` 必须覆盖：

```python
def test_empty_labels_block_training():
    assert run_training([])["status"] == "blocked_no_trainable_heads"


def test_partial_labels_train_only_eligible_heads():
    result = run_training(activity_rows, mode="smoke")
    assert result["trained_heads"] == ["activity_risk"]
    assert result["safe_for_model_claim"] is False


def test_default_mode_rejects_below_threshold_head():
    result = run_training(activity_rows)
    assert result["status"] == "blocked_head_thresholds_not_met"


def test_group_split_has_no_overlap():
    result = run_training(five_head_fixture, mode="research")
    assert result["split"]["group_overlap_count"] == 0
```

- [x] **步骤 2：运行测试并确认正确失败**

运行：

```bash
cd AI大模型
python3 -m pytest -q tests/test_research_multitask_training.py
```

预期：FAIL，训练模块尚不存在。

- [x] **步骤 3：实现共享编码器与独立 heads**

最小模型：

```python
class KWBMultiTaskModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, head_dims: dict[str, int]):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.heads = nn.ModuleDict({
            name: nn.Linear(hidden_dim, output_dim)
            for name, output_dim in head_dims.items()
        })
```

训练 loss 只计算样本已提供的标签；split 必须按 `project_id/enzyme_id/uniprot_id` 分组，禁止行级随机泄漏。`smoke` 模式只证明代码路径可运行，产物固定标记：

```json
{
  "artifact_kind": "research_multitask_smoke_only",
  "safe_for_model_claim": false,
  "release_ready": false
}
```

- [x] **步骤 4：运行研究训练测试**

运行：

```bash
cd AI大模型
python3 -m pytest -q tests/test_research_multitask_training.py
```

预期：全部通过。

## 任务 3：保持生产训练严格 fail-closed

- [x] **步骤 1：扩展生产入口失败测试**

增加：

```python
def test_training_blocks_when_training_dataset_is_missing(tmp_path):
    result = run_training(tmp_path)
    assert result["training_executed"] is False
    assert "dataset" in result["status"]


def test_training_receipt_never_promotes_research_smoke(tmp_path):
    result = run_training(tmp_path)
    assert result["safe_for_model_claim"] is False
    assert result["release_ready"] is False
```

- [x] **步骤 2：运行测试确认失败**

运行：

```bash
cd AI大模型/scripts
python3 -m pytest -q test_train_production_multitask.py
```

- [x] **步骤 3：将生产入口接到真实内核但保留合取门禁**

只有同时满足以下条件才允许训练：

```text
production_model_gate.production_ready == true
five_head_training_execution_contract.training_execution_allowed == true
五头训练 JSONL 存在且 SHA-256 可核
五个 head 均达到 sample/replicate/group 阈值
```

当前仓库必须返回阻断回执，不执行生产训练。

- [x] **步骤 4：运行生产入口测试**

运行：

```bash
cd AI大模型/scripts
python3 -m pytest -q test_train_production_multitask.py
```

预期：全部通过。

## 任务 4：执行当前允许的训练阶段

- [x] **步骤 1：确认连续无标签预训练资产完整**

运行：

```bash
cd AI大模型
python3 scripts/validate_pretraining_release_gate.py
```

预期：资产完整但 `decision=blocked_pretraining_only`，不能升级为监督模型。

- [x] **步骤 2：执行五头研究态 smoke**

运行：

```bash
cd AI大模型
python3 scripts/train_research_multitask.py \
  --mode smoke \
  --activity-risk datasets/training/activity_risk_training_import_labels.jsonl \
  --output reports/research_multitask_training_run.json
```

预期：只训练 `activity_risk` 代码路径；6 行、2 个突变、0 显式重复；`safe_for_model_claim=false`。

- [x] **步骤 3：执行正式研究/生产入口**

运行：

```bash
cd AI大模型
python3 scripts/train_research_multitask.py \
  --mode research \
  --output reports/research_multitask_training_blocked.json
python3 scripts/train_production_multitask.py
```

预期：两者因五头阈值和生产 gate 阻断。阻断是正确结果，不得改成成功。

## 任务 5：修正文档与完成验证

- [x] **步骤 1：修正 M5 口径**

将 `AI大模型/milestones.md` 的 M5 标题和状态改为规则/fixture baseline 完成，真实监督小模型未完成；保留历史 `accuracy=0.833` 但明确不能用于生产模型声明。

- [x] **步骤 2：运行定向测试**

```bash
cd AI大模型
python3 -m pytest -q \
  tests/test_model_status_snapshot.py \
  tests/test_research_multitask_training.py \
  scripts/test_train_production_multitask.py
```

- [x] **步骤 3：运行现有训练与预训练回归**

```bash
cd AI大模型
PYTHONPATH=scripts python3 -m pytest -q \
  tests/test_continuous_pretraining.py \
  tests/test_pretraining_asset_manifest.py \
  tests/test_pretraining_release_gate.py \
  tests/test_pretraining_quality_report.py
```

- [x] **步骤 4：检查改动和声明边界**

```bash
git diff --check
git diff -- AI大模型/scripts AI大模型/tests AI大模型/milestones.md \
  AI大模型/reports/model_status.json \
  AI大模型/reports/research_multitask_training_run.json
```

验收要求：

- 生产训练未被错误执行。
- 无 feature/proxy/文献候选被转成监督标签。
- smoke 产物不能被生产工具读取。
- 模型状态只有一个当前事实源，并明确来源冲突。
- 所有新测试先红后绿。
- 研究训练 numeric features 不得包含标签或近标签字段（含 `activity_relative_to_wt`）；显式 `features` 字典同样过滤；回执/checkpoint 记录 exclusion contract。

## 任务 6：research multitask 近标签泄漏修复（2026-09-03）

- [x] **步骤 1：失败测试** — `tests/test_research_multitask_training.py` 证明标签/近标签字段不进入 feature vector，且回执/checkpoint 记录 schema。
- [x] **步骤 2：红灯确认** — 缺失 `LABEL_OR_NEAR_LABEL_FEATURE_FIELDS` / `feature_schema` 时 2 failed。
- [x] **步骤 3：修复** — `train_research_multitask.py` 采用 exclusion contract + 默认非标签 schema；过滤 `features` 字典。
- [x] **步骤 4：回归** — research + pretraining + production 定向测试 `31 passed`；重新生成 smoke/blocked/model_status；`safe_for_model_claim=false`。

## 外部阻断

- 真实五头训练仍需：每个 head 至少 100 个严格样本、至少 3 个显式重复、至少 10 个独立 group。
- 当前 6 行 activity-risk 标签来自 2 个突变，0 个显式重复，只能做代码 smoke。
- 编号修复、parent/construct FASTA、完整 assay 条件与湿实验训练授权需要人工/外部输入，不能由代码生成。
- GPU、Boltz-2、LigandMPNN、真实长 MD 不在本轮本机训练范围。
