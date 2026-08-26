# GELU-only 预注册序列预训练实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 建立结果前预注册、冻结 source-group 分割、配对多 seed 训练和一次性 sealed-test 门，严格评估只增加 `GELU(Conv1d(hidden))` 的无标签 MLM 候选。

**架构：** 将模型配置解析收口到严格解析器，用独立协议模块产生确定性分割、mask banks 和 canonical hashes。训练、dev 评估、统计决策与 sealed-test 分成独立 CLI，以 validity gate 先行的状态机串联；实验 manifest 与当前 v6 baseline manifest 隔离。

**技术栈：** Python 3、PyTorch、`unittest`、JSON/JSONL、JSON Schema（项目内最小 validator）、SHA-256、Git isolated worktree。

---

## 文件结构

- 修改 `AI大模型/scripts/pretrain_sequence_mlm.py`：严格 checkpoint 配置解析，增加 `dilation/context_gelu` 和 GELU-only 路径。
- 修改 `AI大模型/scripts/continuous_pretrain_sequence_mlm.py`：显式参数、checkpoint 持久化与严格 CLI 解析。
- 修改 `AI大模型/scripts/evaluate_sequence_mlm_checkpoint.py`、`build_sequence_embedding_index.py`、`export_sequence_embeddings.py`：共用 resolved config。
- 创建 `AI大模型/scripts/preregistered_mlm_protocol.py`：canonical JSONL、分割、确定 mask、hash 和统计公共函数。
- 创建 `AI大模型/scripts/build_preregistered_mlm_inputs.py`：生成 split/mask/environment 冻结资产。
- 创建 `AI大模型/scripts/validate_preregistered_mlm_experiment.py`：校验 schema、hash、Git 提交关系和单变量 config diff。
- 创建 `AI大模型/scripts/run_preregistered_mlm_training.py`：单 arm/seed 正式训练与证据输出。
- 创建 `AI大模型/scripts/evaluate_preregistered_mlm_dev.py`：只评估 dev，输出逐 seed×bank 原始计数。
- 创建 `AI大模型/scripts/decide_preregistered_mlm.py`：两级 validity/efficacy 决策门。
- 创建 `AI大模型/scripts/run_preregistered_mlm_sealed_test.py`：原子消耗 sealed-test 唯一尝试。
- 创建 `AI大模型/scripts/build_preregistered_mlm_manifest.py`：验证外部 runtime 证据后物化实验资产并绑定 hash，但不修改当前 baseline manifest。
- 创建 `AI大模型/schemas/preregistered_mlm_*.schema.json`：预注册、run、decision、attempt 产物的严格 schema。
- 创建 `AI大模型/tests/test_preregistered_mlm_*.py`：覆盖协议、训练、决策和密封门。
- 修改 `AI大模型/model_cards/sequence-pretraining.status.md`、`progress.md`、`findings.md`：记录方法边界与最终决策。

### 任务 1：严格模型配置与 GELU-only 路径

**文件：**
- 修改：`AI大模型/scripts/pretrain_sequence_mlm.py`
- 修改：`AI大模型/scripts/continuous_pretrain_sequence_mlm.py`
- 修改：`AI大模型/scripts/evaluate_sequence_mlm_checkpoint.py`
- 修改：`AI大模型/scripts/build_sequence_embedding_index.py`
- 修改：`AI大模型/scripts/export_sequence_embeddings.py`
- 测试：`AI大模型/tests/test_pretrain_sequence_mlm.py`
- 测试：`AI大模型/tests/test_continuous_pretraining.py`
- 测试：`AI大模型/tests/test_sequence_checkpoint_config_consumers.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_checkpoint_config_defaults_each_missing_field_independently(self):
    self.assertEqual(
        MODULE.checkpoint_model_config({"config": {"residual": True}}),
        (32, 3, 1, True, False),
    )

def test_checkpoint_config_rejects_string_boolean(self):
    with self.assertRaises(ValueError):
        MODULE.checkpoint_model_config({"config": {"context_gelu": "false"}})

def test_gelu_only_path_is_exact(self):
    model = MODULE.build_encoder(22, context_gelu=True)
    legacy = MODULE.build_encoder(22)
    for encoder in (model, legacy):
        with torch.no_grad():
            encoder.embedding.weight.fill_(1.0)
            encoder.position.weight.zero_()
            encoder.context.weight.zero_()
            encoder.context.bias.fill_(2.0)
    ids = torch.tensor([0, 1])
    self.assertTrue(torch.allclose(legacy.contextualize(ids), torch.full((2, 32), 2.0)))
    self.assertTrue(torch.allclose(model.contextualize(ids), torch.nn.functional.gelu(torch.full((2, 32), 2.0))))
```

- [ ] **步骤 2：确认新测试红灯**

运行：`PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_pretrain_sequence_mlm.py' -v`，再运行 `PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_sequence_checkpoint_config_consumers.py' -v`。

预期：FAIL，报告 `context_gelu`/`dilation` 参数或严格类型校验尚不存在。

- [ ] **步骤 3：实现最小严格配置与数学路径**

```python
def checkpoint_model_config(checkpoint):
    config = checkpoint.get("config", {})
    hidden_dim = strict_int(config, "hidden_dim", 32, minimum=1)
    kernel_size = strict_odd_int(config, "kernel_size", 3)
    dilation = strict_int(config, "dilation", 1, minimum=1)
    residual = strict_bool(config, "residual", False)
    context_gelu = strict_bool(config, "context_gelu", False)
    if residual and context_gelu:
        raise ValueError("residual and context_gelu cannot both be true")
    return hidden_dim, kernel_size, dilation, residual, context_gelu
```

`SequenceEncoder.contextualize()` 只允许三条路径：legacy `context`、candidate `GELU(context)`、legacy residual `GELU(hidden + context)`。Conv1d padding 固定为 `dilation * (kernel_size - 1) // 2`。

- [ ] **步骤 4：同步五个 consumer 并运行绿灯**

运行：`PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -q`

预期：全部 PASS；evaluate 的 trained/random 模型与 index/export 都收到相同五字段配置。

- [ ] **步骤 5：提交**

```bash
git add AI大模型/scripts/pretrain_sequence_mlm.py AI大模型/scripts/continuous_pretrain_sequence_mlm.py AI大模型/scripts/evaluate_sequence_mlm_checkpoint.py AI大模型/scripts/build_sequence_embedding_index.py AI大模型/scripts/export_sequence_embeddings.py AI大模型/tests/test_pretrain_sequence_mlm.py AI大模型/tests/test_continuous_pretraining.py AI大模型/tests/test_sequence_checkpoint_config_consumers.py
git commit -m "feat: 增加GELU单变量配置"
```

### 任务 2：确定性分割与 mask-bank 协议

**文件：**
- 创建：`AI大模型/scripts/preregistered_mlm_protocol.py`
- 创建：`AI大模型/scripts/build_preregistered_mlm_inputs.py`
- 测试：`AI大模型/tests/test_preregistered_mlm_protocol.py`

- [ ] **步骤 1：写分割与 mask 失败测试**

```python
def test_source_bucket_split_is_disjoint(self):
    split = MODULE.assign_source("source-a", seed=20260827)
    self.assertIn(split, {"train", "dev", "sealed-test"})

def test_missing_or_duplicate_source_is_rejected(self):
    for header in ("id", "id|source=", "id|source=a|source=b"):
        with self.subTest(header=header), self.assertRaises(ValueError):
            MODULE.parse_source(header)

def test_mask_indices_match_digest_threshold_and_fallback(self):
    self.assertEqual(MODULE.mask_indices("record", 4, 3030001, 0.15), [1])
```

- [ ] **步骤 2：运行并确认红灯**

运行：`PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_preregistered_mlm_protocol.py' -v`

预期：FAIL，模块尚不存在。

- [ ] **步骤 3：实现 canonical 协议函数**

```python
MASK_THRESHOLD = int(0.15 * (1 << 256))

def assign_source(source: str, seed: int = 20260827) -> str:
    bucket = int.from_bytes(hashlib.sha256(f"{seed}:{source}".encode()).digest(), "big") % 100
    return "train" if bucket < 80 else "dev" if bucket < 90 else "sealed-test"

def mask_indices(record_id: str, length: int, bank_seed: int, probability: float = 0.15) -> list[int]:
    selected = [i for i in range(length) if digest_int(f"{bank_seed}:{record_id}:{i}") < MASK_THRESHOLD]
    return selected or [digest_int(f"fallback:{bank_seed}:{record_id}") % length]
```

builder 必须严格校验输入 SHA/12,830 条、header/source/词表/重复，输出 canonical source/sequence manifests、dev/test 各 5 个 bank 及 overlap report。

- [ ] **步骤 4：双次生成可复现性测试**

在两个 `TemporaryDirectory` 生成相同输入，断言除输出路径外所有 bytes/hash 相同，overlap=0，无效 source 时不写部分产物。

- [ ] **步骤 5：提交**

```bash
git add AI大模型/scripts/preregistered_mlm_protocol.py AI大模型/scripts/build_preregistered_mlm_inputs.py AI大模型/tests/test_preregistered_mlm_protocol.py
git commit -m "feat: 冻结预注册分割与遮盖库"
```

### 任务 3：预注册 schema 与 validity validator

**文件：**
- 创建：`AI大模型/schemas/preregistered_mlm_preregistration.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_run.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_decision.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_attempt.schema.json`
- 创建：`AI大模型/scripts/validate_preregistered_mlm_experiment.py`
- 测试：`AI大模型/tests/test_validate_preregistered_mlm_experiment.py`

- [ ] **步骤 1：先写 schema/hash/config-diff 失败测试**

```python
def test_only_context_gelu_may_differ(self):
    incumbent = {"model": {"hidden_dim": 32, "kernel_size": 3, "dilation": 1, "residual": False, "context_gelu": False}, "learning_rate": 0.0005}
    candidate = {"model": {**incumbent["model"], "context_gelu": True}, "learning_rate": 0.0005}
    self.assertEqual(MODULE.config_diff(incumbent, candidate), ["/model/context_gelu"])
    with self.assertRaises(ValueError):
        MODULE.validate_single_variable(incumbent, candidate | {"learning_rate": 0.001})

def test_unknown_field_and_hash_mismatch_fail_closed(self):
    schema = {"type": "object", "required": ["experiment_id"], "properties": {"experiment_id": {"type": "string"}}, "additionalProperties": False}
    with self.assertRaises(ValueError):
        MODULE.validate_schema({"experiment_id": "gelu-only-20260827", "unexpected": True}, schema)
```

- [ ] **步骤 2：确认红灯后实现最小 schema validator**

validator 必须支持本项目用到的 `type/required/properties/additionalProperties/enum/items/minItems/maxItems`，不接受未知字段。预注册验证还要重算输入、split、banks、environment 和 training-code commit 的 hash。

- [ ] **步骤 3：增加 Git 关系与 clean-tree 检查**

```python
def validate_git_binding(repo: Path, training_commit: str, prereg_commit: str) -> None:
    parent = run_git(repo, "rev-parse", f"{prereg_commit}^")
    if parent != training_commit or run_git(repo, "status", "--porcelain"):
        raise ValueError("preregistration git binding is not clean")
```

单测用临时 Git repo 构造正确父子提交、错误父提交和 dirty tree。

- [ ] **步骤 4：运行绿灯并提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_validate_preregistered_mlm_experiment.py' -v
git add AI大模型/schemas AI大模型/scripts/validate_preregistered_mlm_experiment.py AI大模型/tests/test_validate_preregistered_mlm_experiment.py
git commit -m "feat: 增加预注册有效性门"
```

### 任务 4：配对单 arm/seed 训练 runner

**文件：**
- 创建：`AI大模型/scripts/run_preregistered_mlm_training.py`
- 测试：`AI大模型/tests/test_run_preregistered_mlm_training.py`

- [ ] **步骤 1：写训练顺序、mask 配对与证据失败测试**

```python
def test_both_arms_use_identical_record_and_mask_plan(self):
    records = [{"record_id": "a", "sequence": "ACDE"}, {"record_id": "b", "sequence": "FGHI"}]
    incumbent = MODULE.build_update_plan(records, seed=20260827, epochs=3)
    candidate = MODULE.build_update_plan(records, seed=20260827, epochs=3)
    self.assertEqual(incumbent, candidate)

def test_run_report_binds_final_checkpoint_and_frozen_config(self):
    preregistration = {"training": {"epochs": 1, "seeds": [20260827]}, "model": {"hidden_dim": 4, "kernel_size": 3, "dilation": 1, "residual": False, "context_gelu": False}}
    records = [{"record_id": "a", "sequence": "ACDE"}]
    report = MODULE.train_arm(preregistration, "incumbent", 20260827, records)
    self.assertEqual(report["checkpoint_step"], report["expected_steps"])
    self.assertFalse(report["release_ready"])
```

- [ ] **步骤 2：确认红灯，再实现单运行 runner**

runner 在加载训练数据前先验证 preregistration/Git/environment。它只接受预注册的 arm 和 seed，设置 CPU/float32/deterministic/thread=1，使用固定 update plan，完成后将 checkpoint SHA、config SHA、step 数、loss ledger 和 fail-closed flags 写入 repo 外的显式 `--runtime-dir`。正式运行期间不在 clean preregistration worktree 内写生成物。

- [ ] **步骤 3：测试异常原子性**

在 optimizer step 中注入异常，断言生成 `invalid_experiment` run ledger，不写 completed checkpoint，不允许同一 experiment/arm/seed 第二次成功覆盖。

- [ ] **步骤 4：绿灯与提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_run_preregistered_mlm_training.py' -v
git add AI大模型/scripts/run_preregistered_mlm_training.py AI大模型/tests/test_run_preregistered_mlm_training.py
git commit -m "feat: 增加配对预训练runner"
```

### 任务 5：dev 原始评估与两级决策门

**文件：**
- 创建：`AI大模型/scripts/evaluate_preregistered_mlm_dev.py`
- 创建：`AI大模型/scripts/decide_preregistered_mlm.py`
- 测试：`AI大模型/tests/test_preregistered_mlm_decision.py`

- [ ] **步骤 1：写 token-pooled 评估与 CI 失败测试**

```python
def test_seed_metrics_pool_raw_counts_before_delta(self):
    result = MODULE.aggregate_seed([{"loss_sum": 3.0, "correct": 1, "count": 2}, {"loss_sum": 1.0, "correct": 1, "count": 1}])
    self.assertEqual(result, {"nll": 4.0 / 3.0, "accuracy": 2.0 / 3.0})

def test_paired_ci_uses_ddof_one_and_t_2776(self):
    self.assertEqual(MODULE.paired_ci([0.0] * 5), {"mean": 0.0, "lower": 0.0, "upper": 0.0})
```

- [ ] **步骤 2：写 validity 优先级和边界值失败测试**

```python
def decision_fixture(delta_nll, delta_accuracy=0.0, seed_count=5):
    return {
        "validity_failures": [],
        "paired_seed_metrics": [
            {"seed": 20260827 + index, "delta_nll": delta_nll, "delta_accuracy": delta_accuracy}
            for index in range(seed_count)
        ],
    }

def test_missing_seed_is_invalid_not_retain(self):
    self.assertEqual(MODULE.decide(decision_fixture(-0.006, seed_count=4))["decision"], "invalid_experiment")

def test_valid_but_small_effect_retains_incumbent(self):
    self.assertEqual(MODULE.decide(decision_fixture(-0.0049))["decision"], "retain_incumbent")

def test_all_preregistered_thresholds_promote_to_sealed_test(self):
    self.assertEqual(MODULE.decide(decision_fixture(-0.006))["decision"], "promote_to_sealed_test")
```

- [ ] **步骤 3：实现 dev-only 评估与决策**

dev evaluator 必须显式拒绝 `partition != "dev"`，对 2 arms×5 seeds×5 banks 输出 loss sum/correct/count/checkpoint SHA/bank SHA。decision 先运行 validity gate，然后用 float64 和 `2.776*s/sqrt(5)` 运行效果门，阈值前不舍入。

- [ ] **步骤 4：绿灯与提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_preregistered_mlm_decision.py' -v
git add AI大模型/scripts/evaluate_preregistered_mlm_dev.py AI大模型/scripts/decide_preregistered_mlm.py AI大模型/tests/test_preregistered_mlm_decision.py
git commit -m "feat: 增加预注册MLM决策门"
```

### 任务 6：一次性 sealed-test runner

**文件：**
- 创建：`AI大模型/scripts/run_preregistered_mlm_sealed_test.py`
- 测试：`AI大模型/tests/test_preregistered_mlm_sealed_test.py`

- [ ] **步骤 1：写读数据前消耗 receipt 的失败测试**

```python
def test_attempt_is_created_before_test_data_is_read(self):
    events = []
    with patch.object(MODULE, "create_attempt", side_effect=lambda *a: events.append("attempt")):
        with patch.object(MODULE, "load_partition", side_effect=lambda *a: events.append("read")):
            MODULE.run_sealed_test({"decision": "promote_to_sealed_test", "success": True})
    self.assertEqual(events[:2], ["attempt", "read"])

def test_second_attempt_is_rejected_even_after_first_failure(self):
    with tempfile.TemporaryDirectory() as directory:
        attempt = Path(directory) / "sealed-test-attempt.json"
        MODULE.consume_attempt(attempt, b"{}\n")
        with self.assertRaises(FileExistsError):
            MODULE.consume_attempt(attempt, b"{}\n")
```

- [ ] **步骤 2：实现 exclusive-create 与 append-only ledger**

```python
def consume_attempt(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
```

runner 在读取 sealed-test membership 前校验 dev receipt/hash 并消耗 attempt；后续任何异常都将 final decision 设为 `invalid_experiment`，不释放 attempt。

- [ ] **步骤 3：绿灯与提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_preregistered_mlm_sealed_test.py' -v
git add AI大模型/scripts/run_preregistered_mlm_sealed_test.py AI大模型/tests/test_preregistered_mlm_sealed_test.py
git commit -m "feat: 封闭预训练密封测试门"
```

### 任务 7：实验 manifest 与发布隔离回归

**文件：**
- 创建：`AI大模型/scripts/build_preregistered_mlm_manifest.py`
- 测试：`AI大模型/tests/test_preregistered_mlm_manifest.py`
- 修改：`AI大模型/model_cards/sequence-pretraining.status.md`
- 修改：`progress.md`
- 修改：`findings.md`

- [ ] **步骤 1：写 manifest 与 release 隔离失败测试**

```python
def test_experiment_manifest_is_always_pretraining_only(self):
    manifest = MODULE.build_manifest([{"path": "preregistration.json", "sha256": "a" * 64, "size": 1}])
    self.assertFalse(manifest["release_ready"])
    self.assertFalse(manifest["safe_for_supervised_training"])
    self.assertFalse(manifest["safe_for_model_claim"])

def test_retain_decision_cannot_replace_v6_selection(self):
    with self.assertRaises(ValueError):
        MODULE.build_baseline_update({"decision": "retain_incumbent", "release_ready": False})
```

- [ ] **步骤 2：实现独立 experiment manifest**

experiment manifest 绑定预注册、split/banks、run/evaluation/decision/attempt 资产和 SHA。只有 final decision=`promote_pretraining_baseline` 时才允许生成 baseline-update proposal；proposal 仍强制三个 false。

- [ ] **步骤 3：运行全量实现验证**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -q
python3 -m py_compile AI大模型/scripts/*.py
git diff --check
```

预期：全部退出码 0，不存在正式训练、dev 或 sealed-test 指标产物。

- [ ] **步骤 4：规格和代码两阶段审查后提交 `training_code_commit`**

```bash
git add AI大模型/scripts/build_preregistered_mlm_manifest.py AI大模型/tests/test_preregistered_mlm_manifest.py AI大模型/model_cards/sequence-pretraining.status.md progress.md findings.md
git commit -m "feat: 完成GELU预训练实验基础设施"
```

### 任务 8：生成冻结资产并提交 preregistration

**文件：**
- 生成：`AI大模型/experiments/gelu-only-20260827/splits/*.jsonl`
- 生成：`AI大模型/experiments/gelu-only-20260827/mask_banks/*.jsonl`
- 生成：`AI大模型/experiments/gelu-only-20260827/environment_lock.json`
- 生成：`AI大模型/experiments/gelu-only-20260827/preregistration.json`
- 生成：`AI大模型/experiments/gelu-only-20260827/input_validation.json`

- [ ] **步骤 1：在隔离 worktree 的 clean `training_code_commit` 上生成资产**

```bash
python3 AI大模型/scripts/build_preregistered_mlm_inputs.py \
  --input AI大模型/datasets/derived/msa_sequences_deduplicated.fasta \
  --experiment-id gelu-only-20260827 \
  --training-code-commit "$(git rev-parse HEAD)" \
  --output-dir AI大模型/experiments/gelu-only-20260827
```

预期：12,830 records，source errors=0，三区 source/sequence overlap=0；固定 hash 算法的序列数为 train/dev/sealed-test=`10699/1047/1084`，source 数为 `130/14/14`；产物中没有训练/dev/test 指标。

- [ ] **步骤 2：复现性与 schema 验证**

在临时目录重生成一次，逐文件比较 canonical bytes/SHA，然后运行：

```bash
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --phase precommit
```

预期：`success=true`、`decision=valid_preregistration`、`metric_artifact_count=0`。

- [ ] **步骤 3：仅提交冻结资产**

```bash
git add AI大模型/experiments/gelu-only-20260827
git commit -m "experiment: 预注册GELU单变量实验"
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --phase preregistered
```

确认 `git diff HEAD^ --name-only` 只包含该 experiment 目录，该提交的父提交等于 preregistration 中的 `training_code_commit`，且提交后 validator 为 `success=true`。

### 任务 9：正式配对训练、dev 决策与条件密封评估

**文件：**
- runtime 生成：由 `mktemp -d /private/tmp/gelu-only-20260827.XXXXXX` 创建的 repo 外目录下 `runs/*`
- runtime 生成：同一 repo 外目录下 `dev_evaluation.jsonl`
- runtime 生成：同一 repo 外目录下 `dev_decision.json`
- runtime 条件生成：同一 repo 外目录下 `sealed_test/*`
- 验证后物化：`AI大模型/experiments/gelu-only-20260827/results/*`
- 生成：`AI大模型/experiments/gelu-only-20260827/experiment_manifest.json`

- [ ] **步骤 1：在 clean `preregistration_commit` 上串行运行 10 个配对 runs**

```bash
experiment_runtime_dir="$(mktemp -d /private/tmp/gelu-only-20260827.XXXXXX)"
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --phase launch
for seed in 20260827 20260828 20260829 20260830 20260831; do
  python3 AI大模型/scripts/run_preregistered_mlm_training.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir" --arm incumbent --seed "$seed"
  python3 AI大模型/scripts/run_preregistered_mlm_training.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir" --arm candidate --seed "$seed"
done
```

任一命令失败立即终止，记录 `invalid_experiment`，不重试。

- [ ] **步骤 2：只评估 dev 并执行决策门**

```bash
python3 AI大模型/scripts/evaluate_preregistered_mlm_dev.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir"
python3 AI大模型/scripts/decide_preregistered_mlm.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir" --phase dev
```

预期只能为 `invalid_experiment`、`retain_incumbent` 或 `promote_to_sealed_test`。前两者立即终止，不读取 sealed-test。

- [ ] **步骤 3：仅在 dev 通过时消耗 sealed-test 一次尝试**

```bash
python3 AI大模型/scripts/run_preregistered_mlm_sealed_test.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir"
```

如 dev 未通过，此命令不运行。如运行，attempt receipt 必须在读数据前存在，且任何失败都不允许第二次尝试。

- [ ] **步骤 4：构建实验 manifest 并根据最终决策处理 baseline**

```bash
python3 AI大模型/scripts/build_preregistered_mlm_manifest.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir" --materialize-results
```

- `retain_incumbent`/`invalid_experiment`：当前 `continuous_full_v6` 的 selection/index/manifest 字节级不改变。
- `promote_pretraining_baseline`：先为新 baseline 构建全量 12,830 条 embedding index、collision audit 和独立评估，全部验证通过后才原子切换 8 项 baseline manifest。

- [ ] **步骤 5：完整验证、独立审查和结果提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -q
python3 -m py_compile AI大模型/scripts/*.py
git diff --check
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --runtime-dir "$experiment_runtime_dir" --phase final
```

提交前核对所有 SHA、raw counts、CI、decision、manifest 与三个 fail-closed flags，只暂存实验相关文件：

```bash
git add AI大模型/experiments/gelu-only-20260827 AI大模型/model_cards/sequence-pretraining.status.md progress.md findings.md
git commit -m "eval: 决策GELU预训练候选"
```
