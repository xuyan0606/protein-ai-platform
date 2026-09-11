# 通用酶蛋白文献数据导入实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 建立从 Google 文献发现到可审计实验记录的研究数据导入链，为 Km、kcat、kcat/Km、Tm、pH、稳定性和突变效应排序提供冻结数据集。

**架构：** Google Search/Scholar 只产生来源发现清单；权威论文正文、补充表或作者数据文件作为原始证据进入 source drop。规范化器输出统一 JSONL，审计器检查序列、突变、单位、条件、来源哈希、许可证和分组泄漏；只有满足研究准入的记录才能生成冻结 manifest，生产注册始终保持关闭。

**技术栈：** Python 3.11、标准库 `argparse/json/csv/hashlib`、JSONL、现有 `AI大模型/scripts` 审计工具、`pytest`、JSON Schema。

---

## 文件清单

**创建：**

- `AI大模型/contracts/literature_source_manifest.schema.json`：Google 发现来源和原始文件快照合同。
- `AI大模型/contracts/enzyme_experimental_record.schema.json`：统一实验记录合同。
- `AI大模型/scripts/register_literature_sources.py`：验证来源清单、复制/哈希原始证据并生成 receipt。
- `AI大模型/scripts/normalize_literature_measurements.py`：将人工抽取表规范化为实验记录 JSONL。
- `AI大模型/scripts/audit_general_enzyme_dataset.py`：执行字段、序列、单位、去重、许可证和分组泄漏审计。
- `AI大模型/scripts/build_general_enzyme_dataset_manifest.py`：仅在审计通过时生成 research manifest，失败则 fail-closed。
- `AI大模型/datasets/curation/google_literature_source_manifest.jsonl`：Google 检索发现结果和人工确认的权威来源 URL。
- `AI大模型/datasets/curation/literature_measurements_extracted.jsonl`：人工抽取的原始实验行，默认不具备训练资格。
- `AI大模型/tests/test_literature_source_registration.py`：来源合同和哈希验证测试。
- `AI大模型/tests/test_normalize_literature_measurements.py`：单位、字段和突变规范化测试。
- `AI大模型/tests/test_audit_general_enzyme_dataset.py`：许可证、序列、泄漏和准入测试。

**修改：**

- `AI大模型/datasets/curation/sci_open_measurement_extraction_templates_20260902.jsonl`：扩展模板字段，使其覆盖统一记录合同中的来源定位、单位和条件字段。
- `AI大模型/scripts/build_literature_measurement_approved_preview.py`：透传来源文件哈希、许可证和训练准入原因，但继续保持只读 preview。
- `AI大模型/scripts/build_cleanroom_kinetics_training_candidate.py`：把通用 manifest 作为输入候选之一，并明确不会写训练行。

**不修改：** 模型 runner、生产 `/api/training` 接口、生产 model registry；阶段 A 不启动训练。

### 任务 1：建立来源发现与原始证据注册合同

**文件：**
- 创建：`AI大模型/contracts/literature_source_manifest.schema.json`
- 创建：`AI大模型/scripts/register_literature_sources.py`
- 创建：`AI大模型/datasets/curation/google_literature_source_manifest.jsonl`
- 测试：`AI大模型/tests/test_literature_source_registration.py`

- [x] **步骤 1：先写失败测试，锁定 Google 发现结果不能直接成为训练数据。**

```python
def test_search_result_is_not_training_source(tmp_path):
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text(json.dumps({
        "source_id": "google-001",
        "discovery_engine": "google_search",
        "query": "enzyme Km pH temperature dataset",
        "result_url": "https://example.test/paper",
        "evidence_type": "search_result",
        "training_import_status": "training_candidate",
    }) + "\n", encoding="utf-8")
    result = validate_source_manifest(manifest)
    assert result["training_import_allowed"] is False
    assert "search_result_not_primary_evidence" in result["errors"]
```

- [x] **步骤 2：运行测试确认失败。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_literature_source_registration.py`

预期：FAIL，`validate_source_manifest` 尚不存在。

- [x] **步骤 3：实现最小来源验证器。**

实现 `validate_source_manifest(path)`，逐行验证：`source_id`、`discovery_engine`、`query`、`result_url`、`primary_evidence_url`、`source_file`、`source_file_sha256`、`license`、`training_import_status`。当 `evidence_type` 为 `search_result`、缺少原始文件或哈希不匹配时，强制 `training_import_allowed=false`。`register_literature_sources.py` 只允许复制已存在的本地原始文件，不自动伪造下载结果。

- [x] **步骤 4：运行测试确认通过，并增加哈希 mismatch 负例。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_literature_source_registration.py`

预期：PASS，至少 3 个测试覆盖搜索结果阻断、文件哈希通过、哈希不匹配阻断。

- [x] **步骤 5：提交。**

```bash
git add AI大模型/contracts/literature_source_manifest.schema.json AI大模型/scripts/register_literature_sources.py AI大模型/datasets/curation/google_literature_source_manifest.jsonl AI大模型/tests/test_literature_source_registration.py
git commit -m "feat: add auditable literature source registration"
```

### 任务 2：接入 Google 文献发现清单和原始文件快照

**文件：**
- 修改：`AI大模型/datasets/curation/google_literature_source_manifest.jsonl`
- 创建：`AI大模型/datasets/source_drops/google_literature_20260911/README.md`
- 创建：`AI大模型/reports/google_literature_source_receipt_20260911.json`
- 测试：复用 `AI大模型/tests/test_literature_source_registration.py`

- [x] **步骤 1：建立查询集，不把搜索摘要当数据。**

记录以下查询及日期：`enzyme Km pH temperature assay dataset`、`enzyme kcat Km supplementary table sequence`、`protein thermostability Tm sequence dataset license`、`experimental protein mutation effect DMS enzyme`、`enzyme optimum pH activity mutant supplementary data`。每条结果填入 `discovery_engine=google_search`、`query`、`result_url`、`title`，仅当打开论文/仓库并取得原始文件后补齐 `primary_evidence_url` 和 `source_file_sha256`。

- [x] **步骤 2：为每个权威来源保存原始文件和许可证据。**

把论文 XML/PDF、补充 CSV/Excel、作者仓库导出文件放入 `AI大模型/datasets/source_drops/google_literature_20260911/`，旁边保存许可证文本或来源页面快照；禁止把 Google HTML 搜索页放入原始测量文件。

- [x] **步骤 3：运行注册器生成 receipt。**

运行：`python3 AI大模型/scripts/register_literature_sources.py --manifest AI大模型/datasets/curation/google_literature_source_manifest.jsonl --source-root AI大模型/datasets/source_drops/google_literature_20260911 --receipt AI大模型/reports/google_literature_source_receipt_20260911.json`

预期：缺少原始文件的发现项保留为 `needs_review`，有文件且哈希、许可证和主证据齐全的来源才标记 `research_candidate`；不允许出现未经证据升级的 `training_import_allowed=true`。

- [x] **步骤 4：提交来源审计产物。**

```bash
git add AI大模型/datasets/curation/google_literature_source_manifest.jsonl AI大模型/datasets/source_drops/google_literature_20260911/README.md AI大模型/reports/google_literature_source_receipt_20260911.json
git commit -m "data: record google literature source receipts"
```

### 任务 3：规范化实验测量与突变记录

**文件：**
- 修改：`AI大模型/datasets/curation/sci_open_measurement_extraction_templates_20260902.jsonl`
- 创建：`AI大模型/contracts/enzyme_experimental_record.schema.json`
- 创建：`AI大模型/scripts/normalize_literature_measurements.py`
- 创建：`AI大模型/datasets/curation/literature_measurements_extracted.jsonl`
- 测试：`AI大模型/tests/test_normalize_literature_measurements.py`

- [x] **步骤 1：先写规范化失败测试。**

```python
def test_normalize_preserves_original_unit_and_converts_km(tmp_path):
    row = {"source_id": "src-1", "protein_sequence": "MKT", "metric": "Km", "value": 2.5, "unit": "mM", "pH": 6.5, "temperature": 37, "source_row_or_table": "Table 2 row 4"}
    normalized = normalize_row(row)
    assert normalized["original_value"] == 2.5
    assert normalized["original_unit"] == "mM"
    assert normalized["value_si"] == 0.0025
    assert normalized["training_import_status"] == "needs_review"
```

- [x] **步骤 2：运行测试确认失败。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_normalize_literature_measurements.py`

预期：FAIL，`normalize_row` 尚不存在。

- [x] **步骤 3：实现规范化器和 JSON Schema。**

实现 `normalize_row(row)`：标准化蛋白序列大小写、计算 `sequence_hash`、解析 `mutation` 为 WT/position/mutant、保留 `original_value/original_unit`、仅对白名单单位执行显式转换；缺序列、缺来源定位、缺单位、缺实验条件或许可证时设置 `training_import_status=needs_review`，不删除记录。对同一来源、序列、突变、指标和条件生成 deterministic `record_id`。

- [x] **步骤 4：运行单元测试和 schema 校验。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_normalize_literature_measurements.py`

预期：PASS，覆盖 Km、Tm、突变效应、缺单位、非法序列和非法突变位置。

- [x] **步骤 5：提交。**

```bash
git add AI大模型/contracts/enzyme_experimental_record.schema.json AI大模型/scripts/normalize_literature_measurements.py AI大模型/datasets/curation/sci_open_measurement_extraction_templates_20260902.jsonl AI大模型/tests/test_normalize_literature_measurements.py
git commit -m "feat: normalize enzyme literature measurements"
```

### 任务 4：执行质量、许可证和分组泄漏审计

**文件：**
- 创建：`AI大模型/scripts/audit_general_enzyme_dataset.py`
- 创建：`AI大模型/reports/general_enzyme_dataset_audit_20260911.json`
- 测试：`AI大模型/tests/test_audit_general_enzyme_dataset.py`
- 修改：`AI大模型/scripts/build_literature_measurement_approved_preview.py`

- [x] **步骤 1：先写失败测试，锁定同 WT 不跨 split。**

```python
def test_same_sequence_mutants_are_grouped_together():
    rows = [
        {"record_id": "a", "sequence_hash": "wt1", "metric": "Tm", "split": "train", "license_status": "approved"},
        {"record_id": "b", "sequence_hash": "wt1", "metric": "mutation_effect", "split": "test", "license_status": "approved"},
    ]
    audit = audit_rows(rows)
    assert audit["training_import_allowed"] is False
    assert "sequence_group_cross_split" in audit["errors"]
```

- [x] **步骤 2：运行测试确认失败。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_audit_general_enzyme_dataset.py`

预期：FAIL，`audit_rows` 尚不存在。

- [x] **步骤 3：实现 fail-closed 审计。**

审计检查序列字符、突变一致性、数值范围、单位白名单、来源哈希、许可证状态、重复键、同 `sequence_hash`/同论文跨 split、同一派生标签作为独立证据等。输出每个任务的样本数、蛋白组数、显式 replicate 数、可训练数和阻断原因；任何错误都将总状态设为 `blocked_quality_check`。

- [x] **步骤 4：接入现有文献 preview 并运行回归。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_audit_general_enzyme_dataset.py AI大模型/tests/test_import_public_experimental_research_labels.py`

预期：PASS；preview 仍输出 `training_import_allowed=false`，只新增来源哈希和许可证审计字段。

- [x] **步骤 5：提交。**

```bash
git add AI大模型/scripts/audit_general_enzyme_dataset.py AI大模型/reports/general_enzyme_dataset_audit_20260911.json AI大模型/scripts/build_literature_measurement_approved_preview.py AI大模型/tests/test_audit_general_enzyme_dataset.py
git commit -m "feat: audit general enzyme dataset quality and leakage"
```

### 任务 5：生成冻结研究 manifest，不启动训练

**文件：**
- 创建：`AI大模型/scripts/build_general_enzyme_dataset_manifest.py`
- 创建：`AI大模型/reports/general_enzyme_training_manifest_20260911.json`
- 创建：`AI大模型/tests/test_general_enzyme_dataset_manifest.py`

- [x] **步骤 1：先写失败测试，锁定审计失败不能生成可训练 manifest。**

```python
def test_manifest_stays_blocked_when_audit_has_errors(tmp_path):
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"status": "blocked_quality_check", "training_import_allowed": False}), encoding="utf-8")
    result = build_manifest(audit)
    assert result["status"] == "blocked"
    assert result["training_import_allowed"] is False
```

- [x] **步骤 2：运行测试确认失败。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_general_enzyme_dataset_manifest.py`

预期：FAIL，`build_manifest` 尚不存在。

- [x] **步骤 3：实现 manifest 生成器。**

只读取审计报告、来源 receipt 和规范化 JSONL，记录文件 SHA-256、行数、任务覆盖、许可证分层、group split、审计报告路径和 `execution_scope=research_only`。审计非 `passed` 时输出 `status=blocked`、`training_import_allowed=false`；此脚本不得导入 torch、启动训练或写入模型 checkpoint。

- [x] **步骤 4：运行全阶段验证。**

运行：`PYTHONPATH=AI大模型/scripts python3 -m pytest -q AI大模型/tests/test_literature_source_registration.py AI大模型/tests/test_normalize_literature_measurements.py AI大模型/tests/test_audit_general_enzyme_dataset.py AI大模型/tests/test_general_enzyme_dataset_manifest.py`

预期：全部 PASS；manifest 明确显示研究范围和阻断项。

- [x] **步骤 5：提交阶段 A。**

```bash
git add AI大模型/scripts/build_general_enzyme_dataset_manifest.py AI大模型/reports/general_enzyme_training_manifest_20260911.json AI大模型/tests/test_general_enzyme_dataset_manifest.py
git commit -m "feat: freeze research-only enzyme dataset manifest"
```

## 交付验收

- [x] `git diff --check` 通过。
- [x] 四组新增测试全部通过。
- [x] 所有来源有查询日期、权威 URL、文件哈希和许可证状态；缺失项明确为 `needs_review` 或 `blocked_license`。
- [x] 统一记录保留原始单位和原始值，任何转换均可复算。
- [x] 同一 WT 序列、同一论文和派生标签没有跨 split 泄漏。
- [x] 最终 manifest 为 `research_only`；本阶段没有训练进程、模型 checkpoint 或生产注册变更。
