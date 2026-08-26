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
- 创建 `AI大模型/scripts/run_preregistered_mlm_matrix.py`：串行编排 10 个 runs，首次失败立即终止并固化 runtime identity。
- 创建 `AI大模型/scripts/evaluate_preregistered_mlm_dev.py`：只评估 dev，输出逐 seed×bank 原始计数。
- 创建 `AI大模型/scripts/decide_preregistered_mlm.py`：两级 validity/efficacy 决策门。
- 创建 `AI大模型/scripts/run_preregistered_mlm_sealed_test.py`：原子消耗 sealed-test 唯一尝试。
- 创建 `AI大模型/scripts/build_preregistered_mlm_manifest.py`：验证外部 runtime 证据后物化实验资产并绑定 hash，但不修改当前 baseline manifest。
- 创建 `AI大模型/scripts/promote_preregistered_mlm_baseline.py`：仅在最终通过时构建新 checkpoint/index/evaluation 资产，验证后以 selection/manifest 指针最后写入的方式切换 baseline。
- 创建 `AI大模型/schemas/preregistered_mlm_*.schema.json`：覆盖 source/sequence split、input validation、mask bank、environment lock、preregistration、runtime registry、run、raw evaluation row、exception ledger、decision、attempt、experiment manifest、baseline proposal/update 和晋级 baseline JSON 资产的严格 schema。
- 创建 `AI大模型/tests/test_preregistered_mlm_*.py`：覆盖协议、训练、决策和密封门。
- 修改 `AI大模型/model_cards/sequence-pretraining.status.md`、`progress.md`、`findings.md`：记录方法边界与最终决策。

### 任务 0：版本化隔离 worktree 所需的现有本地基线

**文件：**
- 纳入版本：`AI大模型/scripts/pretrain_sequence_mlm.py`
- 纳入版本：`AI大模型/scripts/continuous_pretrain_sequence_mlm.py`
- 纳入版本：`AI大模型/scripts/evaluate_sequence_mlm_checkpoint.py`
- 纳入版本：`AI大模型/scripts/build_sequence_embedding_index.py`
- 纳入版本：`AI大模型/scripts/export_sequence_embeddings.py`
- 纳入版本：`AI大模型/scripts/deduplicate_msa_sequences.py`
- 纳入版本：`AI大模型/tests/test_pretrain_sequence_mlm.py`
- 纳入版本：`AI大模型/tests/test_continuous_pretraining.py`
- 纳入版本：`AI大模型/tests/test_sequence_checkpoint_config_consumers.py`
- 纳入版本：`AI大模型/datasets/derived/msa_sequences_deduplicated.fasta`

- [ ] **步骤 1：在当前 feature 分支验证并只暂存明确依赖**

```bash
shasum -a 256 AI大模型/datasets/derived/msa_sequences_deduplicated.fasta AI大模型/scripts/deduplicate_msa_sequences.py
git add \
  AI大模型/scripts/pretrain_sequence_mlm.py \
  AI大模型/scripts/continuous_pretrain_sequence_mlm.py \
  AI大模型/scripts/evaluate_sequence_mlm_checkpoint.py \
  AI大模型/scripts/build_sequence_embedding_index.py \
  AI大模型/scripts/export_sequence_embeddings.py \
  AI大模型/scripts/deduplicate_msa_sequences.py \
  AI大模型/tests/test_pretrain_sequence_mlm.py \
  AI大模型/tests/test_continuous_pretraining.py \
  AI大模型/tests/test_sequence_checkpoint_config_consumers.py \
  AI大模型/datasets/derived/msa_sequences_deduplicated.fasta
git diff --cached --name-only
```

预期两个 SHA 分别为 `19fdb1bb614ec4a9ed2397a49f2eb4e2eee197b0c835dde5c6618eaa7efc516e` 和 `4762a85ef8eea7b54ccb7fa7b3eb7ab0f7f0f541ec61636cedddc58b3f2eb18c`；由于其余 8 项已被跟踪且当前无修改，暂存列表精确为新增的 FASTA 与去重脚本 2 项，不包含工作区其他改动。

- [ ] **步骤 2：验证现有基线并提交 bootstrap**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest \
  AI大模型/tests/test_pretrain_sequence_mlm.py \
  AI大模型/tests/test_continuous_pretraining.py \
  AI大模型/tests/test_sequence_checkpoint_config_consumers.py -v
git diff --cached --check
git commit -m "chore: 纳入序列预训练基线输入"
```

预期测试全绿且 bootstrap 提交只含上述 2 个新增依赖；提交后用 `git ls-files --error-unmatch` 确认 10 项依赖全部可从 worktree 检出。完成后才按 `using-git-worktrees` 创建隔离 feature worktree，任务 1-9 全部在该 worktree 执行。

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
MASK_THRESHOLD = (15 * (1 << 256)) // 100

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
- 创建：`AI大模型/schemas/preregistered_mlm_source_split.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_sequence_split.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_input_validation.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_mask_bank.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_environment_lock.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_preregistration.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_runtime_registry.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_run.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_raw_evaluation.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_exception.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_decision.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_attempt.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_experiment_manifest.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_baseline_update.schema.json`
- 创建：`AI大模型/schemas/preregistered_mlm_baseline_asset.schema.json`
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

validator 必须支持本项目用到的 `type/required/properties/additionalProperties/enum/const/items/minItems/maxItems/uniqueItems/minimum/maximum/exclusiveMinimum/minLength/pattern/oneOf`，不接受未知字段。artifact-to-schema 映射必须穷举且无 fallback：source membership、sequence membership/split rows、input validation/overlap audit、mask bank manifest/rows、environment lock、preregistration、runtime registry、run config/report、raw evaluation rows、exception rows、decision receipts、attempt receipt/event rows、experiment manifest、baseline proposal/update，以及 actual embedding index、index validation、collision audit、independent evaluation、selection、release gate、asset manifest 七类晋级 JSON。最后七类使用 `preregistered_mlm_baseline_asset.schema.json` 按 `artifact_kind` 的 `oneOf` 分支严格校验。每种 JSON/JSONL 在正向、缺必填字段、未知字段、越界数字和重复数组项上都有测试；无法映射的 `.json`/`.jsonl` 直接失败。预注册验证还要重算输入、split、banks、environment 和 training-code commit 的 hash。

- [ ] **步骤 3：增加 Git 关系与 clean-tree 检查**

```python
def validate_git_phase(repo: Path, phase: str, training_commit: str, experiment_dir: Path) -> None:
    head = run_git(repo, "rev-parse", "HEAD")
    dirty = set(run_git(repo, "status", "--porcelain").splitlines())
    if phase == "precommit":
        require(head == training_commit and dirty_paths_only_under(dirty, experiment_dir))
    elif phase in {"preregistered", "launch", "final"}:
        require(run_git(repo, "rev-parse", "HEAD^") == training_commit and not dirty)
```

单测用临时 Git repo 逐一覆盖四个 phase：`precommit` 只允许 experiment 冻结资产未提交；`preregistered/launch/final` 都要求 clean tree 且 `HEAD^=training_code_commit`，其中 `final` 必须在物化 results 前执行。错误父提交、任意 dirty path 和提前 results 均必须失败；sealed attempt 固定在 registry 绑定的 repo 外 runtime，因此不构成 worktree dirty 例外。

- [ ] **步骤 4：运行绿灯并提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_validate_preregistered_mlm_experiment.py' -v
git add AI大模型/schemas AI大模型/scripts/validate_preregistered_mlm_experiment.py AI大模型/tests/test_validate_preregistered_mlm_experiment.py
git commit -m "feat: 增加预注册有效性门"
```

### 任务 4：配对单 arm/seed 训练 runner

**文件：**
- 创建：`AI大模型/scripts/run_preregistered_mlm_training.py`
- 创建：`AI大模型/scripts/run_preregistered_mlm_matrix.py`
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

runner 在加载训练数据前先验证 preregistration/Git/environment。它只接受预注册的 arm 和 seed，设置 CPU/float32/deterministic/thread=1，使用固定 update plan，完成后将 checkpoint SHA、config SHA、step 数、loss ledger 和 fail-closed flags 写入 repo 外 runtime。matrix orchestrator 通过固定 `--runtime-registry /private/tmp/gelu-only-20260827.runtime.json` exclusive-create registry，内部创建唯一 runtime 根并绑定 experiment/preregistration；所有后续 CLI 只从 registry 解析 runtime，不接受任意 `--runtime-dir`。正式运行期间不在 clean preregistration worktree 内写生成物。

- [ ] **步骤 3：测试异常原子性**

在 optimizer step 中注入异常，断言生成 `invalid_experiment` run ledger，不写 completed checkpoint，不允许同一 experiment/arm/seed 第二次成功覆盖。

再为 matrix orchestrator 注入“第 3 个 run 返回非零”，断言只调用 3 次、未启动后续 7 个 runs，runtime state 写入 `invalid_experiment`。另测试 registry 已存在时拒绝创建新 runtime；evaluator/decision/sealed runner 只能从固定 registry 解析原 runtime，CLI 传入未知的 `--runtime-dir` 必须由严格参数解析直接拒绝。

- [ ] **步骤 4：绿灯与提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_run_preregistered_mlm_training.py' -v
git add AI大模型/scripts/run_preregistered_mlm_training.py AI大模型/scripts/run_preregistered_mlm_matrix.py AI大模型/tests/test_run_preregistered_mlm_training.py
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

同一测试文件还必须参数化覆盖并逐项断言：50 个 arm×seed×bank cells 少任意一个、NaN/Inf、checkpoint/bank/preregistration SHA 错配、两 arm steps/device/dtype 不对称、dev 决策前出现 sealed raw row，均为 `invalid_experiment`；accuracy CI lower 恰好等于 `-0.001` 为 `retain_incumbent`；只有 3/5 seeds 的 `delta_nll<0` 为 `retain_incumbent`；恰好 4/5 且其他三门满足时为 `promote_to_sealed_test`。validity failure 不得落入效果门，效果边界失败不得误报实验无效。

- [ ] **步骤 3：实现 dev-only 评估与决策**

dev evaluator 必须显式拒绝 `partition != "dev"`，对 2 arms×5 seeds×5 banks 输出 loss sum/correct/count/checkpoint SHA/bank SHA。decision 先运行 validity gate，然后用 float64 和 `2.776*s/sqrt(5)` 运行效果门，阈值前不舍入。

matrix 或 dev decision 若得到 `invalid_experiment`/`retain_incumbent`，只停止后续训练或 sealed 读取，不停止取证：必须继续执行任务 9 步骤 4 的 `final` validator（对当前 terminal state）、`build_preregistered_mlm_manifest.py --materialize-results` 和结果提交；manifest 必须包含 exception ledger、已有 raw rows、decision receipt 及 `release_ready=false`。只有 `promote_to_sealed_test` 才允许进入 sealed runner。

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
    with patch.object(MODULE, "consume_attempt", side_effect=lambda *a: events.append("attempt")):
        with patch.object(MODULE, "load_partition", side_effect=lambda *a: events.append("read")):
            MODULE.run_sealed_test({"decision": "promote_to_sealed_test", "success": True})
    self.assertEqual(events[:2], ["attempt", "read"])

def test_second_attempt_is_rejected_even_after_first_failure(self):
    with tempfile.TemporaryDirectory() as runtime:
        attempt = Path(runtime) / "sealed_test_attempt.json"
        MODULE.consume_attempt(attempt, b"{}\n")
        with self.assertRaises(FileExistsError):
            MODULE.consume_attempt(attempt, b"{}\n")

def test_second_worktree_resolves_the_same_registry_bound_attempt(self):
    with tempfile.TemporaryDirectory() as runtime, tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        registry = {"experiment_id": "gelu-only-20260827", "preregistration_sha256": "a" * 64, "runtime_root": runtime}
        first_attempt = MODULE.resolve_attempt_path(registry, Path(first), "gelu-only-20260827", "a" * 64)
        second_attempt = MODULE.resolve_attempt_path(registry, Path(second), "gelu-only-20260827", "a" * 64)
        self.assertEqual(first_attempt, second_attempt)
        MODULE.consume_attempt(first_attempt, b"{}\n")
        with self.assertRaises(FileExistsError):
            MODULE.consume_attempt(second_attempt, b"{}\n")
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

receipt 的唯一位置固定为 `/private/tmp/gelu-only-20260827.runtime.json` 所绑定的唯一 `runtime_root/sealed_test_attempt.json`；registry 本身 exclusive-create，并绑定 experiment ID 与 preregistration SHA，所有 worktree 都解析到同一 receipt，CLI 不接受替换 registry identity 或 runtime root。attempt 事件按序追加到同一 runtime 的 `sealed_test_attempt_events.jsonl`，每行使用 attempt schema，必须恰好以 `consumed` 开始、以 `completed` 或 `failed` 终止，并由 final decision 绑定整文件 SHA。runner 在读取 sealed-test membership 前校验 dev receipt/hash 并消耗 attempt；随后对 2 arms×5 seeds×5 sealed banks 输出与 dev 同 schema 的原始计数，调用同一 `decide(..., phase="sealed-test")` 四条效果门。测试必须覆盖跨 worktree 第二次运行被拒绝、事件终态/顺序、通过输出 `promote_pretraining_baseline`、效果不达标输出 `retain_incumbent`、缺 cell/hash 错配输出 `invalid_experiment`。后续任何异常都为 `invalid_experiment`，不释放 attempt。该机制不声称抵抗拥有文件系统写权限者删除 registry/runtime 的恶意篡改；缺失或 hash 漂移一律 `invalid_experiment`。

- [ ] **步骤 3：绿灯与提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -p 'test_preregistered_mlm_sealed_test.py' -v
git add AI大模型/scripts/run_preregistered_mlm_sealed_test.py AI大模型/tests/test_preregistered_mlm_sealed_test.py
git commit -m "feat: 封闭预训练密封测试门"
```

### 任务 7：实验 manifest 与发布隔离回归

**文件：**
- 创建：`AI大模型/scripts/build_preregistered_mlm_manifest.py`
- 创建：`AI大模型/scripts/promote_preregistered_mlm_baseline.py`
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

def test_injected_promotion_failure_restores_all_incumbent_bytes(self):
    incumbent = {
        "reports/sequence_pretraining_continuous_selection.json": b"old-selection\n",
        "reports/sequence_mlm_continuous_full_v6.json": b"old-report\n",
        "reports/sequence_mlm_continuous_full_v6.checkpoint.pt": b"old-checkpoint",
        "reports/sequence_embedding_index_continuous_v6_validation.json": b"old-index\n",
        "reports/sequence_embedding_continuous_v6_collision_report.json": b"old-collision\n",
        "reports/sequence_mlm_continuous_full_v6_evaluation.json": b"old-evaluation\n",
        "model_cards/sequence-pretraining.status.md": b"old-card\n",
        "reports/sequence_pretraining_release_gate.json": b"old-gate\n",
        "reports/sequence_pretraining_asset_manifest.json": b"old-manifest\n",
    }
    candidate = {
        "reports/sequence_mlm_continuous_full_gelu_v1.json": b"new-report\n",
        "reports/sequence_mlm_continuous_full_gelu_v1.checkpoint.pt": b"new-checkpoint",
        "reports/sequence_embedding_index_continuous_full_gelu_v1.json": b"new-index-data\n",
        "reports/sequence_embedding_index_continuous_full_gelu_v1_validation.json": b"new-index\n",
        "reports/sequence_embedding_continuous_full_gelu_v1_collision_report.json": b"new-collision\n",
        "reports/sequence_mlm_continuous_full_gelu_v1_evaluation.json": b"new-evaluation\n",
        "model_cards/sequence-pretraining.status.md": b"new-card\n",
        "reports/sequence_pretraining_release_gate.json": b"new-gate\n",
        "reports/sequence_pretraining_continuous_selection.json": b"new-selection\n",
        "reports/sequence_pretraining_asset_manifest.json": b"new-manifest\n",
    }
    for fail_after_write in range(1, 11):
        with self.subTest(fail_after_write=fail_after_write), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, payload in incumbent.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            with patch.object(MODULE, "validate_staged_assets", return_value=None):
                with self.assertRaises(RuntimeError):
                    MODULE.promote_verified_bundle(
                        repo_root=root,
                        staged_assets=candidate,
                        final_decision={"decision": "promote_pretraining_baseline", "success": True},
                        fail_after_write=fail_after_write,
                    )
            after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual(after, before)
```

- [ ] **步骤 2：实现独立 experiment manifest**

experiment manifest 绑定预注册、split/banks、run/evaluation/decision/attempt 资产和 SHA。只有 final decision=`promote_pretraining_baseline` 时才允许生成 baseline-update proposal；proposal 仍强制三个 false。

promotion CLI 只接受已验证的 `promote_pretraining_baseline` final decision。它先在 repo 外 staging 目录构建并验证候选训练报告/checkpoint、12,830 条 embedding index 及其 validation、collision audit、independent evaluation、model card、release gate、selection 和 asset manifest。晋级 bundle 的 9 个 canonical 资产精确是：

1. `reports/sequence_pretraining_continuous_selection.json`
2. `reports/sequence_mlm_continuous_full_gelu_v1.json`
3. `reports/sequence_mlm_continuous_full_gelu_v1.checkpoint.pt`
4. `reports/sequence_embedding_index_continuous_full_gelu_v1.json`
5. `reports/sequence_embedding_index_continuous_full_gelu_v1_validation.json`
6. `reports/sequence_embedding_continuous_full_gelu_v1_collision_report.json`
7. `reports/sequence_mlm_continuous_full_gelu_v1_evaluation.json`
8. `model_cards/sequence-pretraining.status.md`
9. `reports/sequence_pretraining_release_gate.json`

晋级 checkpoint 来源在预注册中固定为 candidate arm 的 seed `20260827` 第 3 epoch 最后一次 optimizer update；该 seed 是 canonical export seed，不按 dev NLL、sealed NLL、accuracy 或任何事后指标择优，也不允许从其他 seed cherry-pick。actual index 只由该固定 checkpoint、全量 12,830 条冻结序列、固定 export 配置生成；若该 checkpoint 缺失或 provenance/hash 不匹配，promotion 必须 `invalid_experiment`，不得重训或补跑。

`sequence_pretraining_asset_manifest.json` 是指向上述 9 项的提交指针，不计入 asset_count。promotion 先记录每个目标的旧 bytes 或“不存在”标记；外部 staging 验证通过后，将每项 bytes 写入其最终目标旁的唯一临时文件并 `fsync`，再以同文件系统 `os.replace` 逐项落位，不能假设 `/private/tmp` 与 repo 位于同一文件系统。selection 倒数第二写入，asset manifest 最后写入。任意写入/验证异常都恢复被覆盖文件、删除本次新建文件和临时文件。单测对 10 个写入位置逐一注入失败，断言 v6 selection/manifest 及整个受管文件集合逐字节不变且无 GELU 残留；成功路径断言 actual index 的 `record_count=12830`、9 项 hash、`release_ready=false`、`safe_for_supervised_training=false`、`safe_for_model_claim=false`。

- [ ] **步骤 3：运行全量实现验证**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -q
python3 -m py_compile AI大模型/scripts/*.py
git diff --check
```

预期：全部退出码 0，不存在正式训练、dev 或 sealed-test 指标产物。

- [ ] **步骤 4：规格和代码两阶段审查后提交 `training_code_commit`**

```bash
git add AI大模型/scripts/build_preregistered_mlm_manifest.py AI大模型/scripts/promote_preregistered_mlm_baseline.py AI大模型/tests/test_preregistered_mlm_manifest.py AI大模型/model_cards/sequence-pretraining.status.md progress.md findings.md
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
experiment_created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 AI大模型/scripts/build_preregistered_mlm_inputs.py \
  --input AI大模型/datasets/derived/msa_sequences_deduplicated.fasta \
  --deduplication-script AI大模型/scripts/deduplicate_msa_sequences.py \
  --expected-deduplication-script-sha256 4762a85ef8eea7b54ccb7fa7b3eb7ab0f7f0f541ec61636cedddc58b3f2eb18c \
  --experiment-id gelu-only-20260827 \
  --created-at "$experiment_created_at" \
  --training-code-commit "$(git rev-parse HEAD)" \
  --output-dir AI大模型/experiments/gelu-only-20260827
```

预期：12,830 records，source errors=0，三区 source/sequence overlap=0；固定 hash 算法的序列数为 train/dev/sealed-test=`10699/1047/1084`，source 数为 `130/14/14`；产物中没有训练/dev/test 指标。

- [ ] **步骤 2：复现性与 schema 验证**

从首次产物读取同一个 `created_at` 和 `training_code_commit`，用相同参数到 repo 外临时目录重生成一次，逐文件比较 canonical bytes/SHA；创建时间不在第二次调用中重算。然后运行：

```bash
experiment_created_at="$(python3 -c 'import json; print(json.load(open("AI大模型/experiments/gelu-only-20260827/preregistration.json"))["created_at"])')"
training_code_commit="$(python3 -c 'import json; print(json.load(open("AI大模型/experiments/gelu-only-20260827/preregistration.json"))["training_code_commit"])')"
repro_dir="$(mktemp -d /private/tmp/gelu-only-20260827-repro.XXXXXX)"
python3 AI大模型/scripts/build_preregistered_mlm_inputs.py \
  --input AI大模型/datasets/derived/msa_sequences_deduplicated.fasta \
  --deduplication-script AI大模型/scripts/deduplicate_msa_sequences.py \
  --expected-deduplication-script-sha256 4762a85ef8eea7b54ccb7fa7b3eb7ab0f7f0f541ec61636cedddc58b3f2eb18c \
  --experiment-id gelu-only-20260827 \
  --created-at "$experiment_created_at" \
  --training-code-commit "$training_code_commit" \
  --output-dir "$repro_dir"
diff -ru AI大模型/experiments/gelu-only-20260827 "$repro_dir"
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --phase precommit
```

预期：`diff` 无输出且退出码 0；validator 为 `success=true`、`decision=valid_preregistration`、`metric_artifact_count=0`。

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
- runtime registry：固定 `/private/tmp/gelu-only-20260827.runtime.json`，exclusive-create 后不可替换
- runtime 生成：registry 绑定的唯一 repo 外目录下 `runs/*`
- runtime 生成：同一 repo 外目录下 `dev_evaluation.jsonl`
- runtime 生成：同一 repo 外目录下 `dev_decision.json`
- runtime 条件生成：同一 repo 外目录下 `sealed_test/*`
- 验证后物化：`AI大模型/experiments/gelu-only-20260827/results/*`
- 生成：`AI大模型/experiments/gelu-only-20260827/experiment_manifest.json`

- [ ] **步骤 1：在 clean `preregistration_commit` 上串行运行 10 个配对 runs**

```bash
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py --experiment-dir AI大模型/experiments/gelu-only-20260827 --phase launch
python3 AI大模型/scripts/run_preregistered_mlm_matrix.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json
```

matrix 按预注册顺序串行调用 10 个 runs；任一 run 非零立即停止，原子记录 `invalid_experiment`，不启动后续 run、不重试。registry 已存在即拒绝另建 runtime。

- [ ] **步骤 2：只评估 dev 并执行决策门**

```bash
python3 AI大模型/scripts/evaluate_preregistered_mlm_dev.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json
python3 AI大模型/scripts/decide_preregistered_mlm.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json \
  --phase dev
```

预期只能为 `invalid_experiment`、`retain_incumbent` 或 `promote_to_sealed_test`。前两者立即终止，不读取 sealed-test。

- [ ] **步骤 3：仅在 dev 通过时消耗 sealed-test 一次尝试**

```bash
python3 AI大模型/scripts/run_preregistered_mlm_sealed_test.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json
```

如 dev 未通过，此命令不运行；按步骤 4 完成 finalization 和证据提交。如运行，registry 绑定的唯一 `runtime_root/sealed_test_attempt.json` 必须在读取 sealed-test membership 前 exclusive-create，且任何失败都不允许从同一或另一 worktree 第二次尝试。sealed runner 必须生成 50 个 raw cells 并调用与 dev 相同的 validity/efficacy gate，最终状态只能是 `promote_pretraining_baseline`、`retain_incumbent` 或 `invalid_experiment`。

- [ ] **步骤 4：先通过 final 门，再物化实验 manifest**

```bash
python3 AI大模型/scripts/validate_preregistered_mlm_experiment.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json \
  --phase final
python3 AI大模型/scripts/build_preregistered_mlm_manifest.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json \
  --materialize-results
```

`final` validator 必须在任何 `results/*` 物化前运行；attempt receipt 位于 repo 外，此时 worktree 必须完全 clean。`retain_incumbent`/`invalid_experiment` 时，当前 `continuous_full_v6` 的 selection/index/manifest 字节级不改变；若 matrix 在第 N 个 run 失败，finalization 仍物化截至该失败点的 exception ledger 和 terminal decision，不伪造缺失 runs，不执行 sealed 或 promotion。

- [ ] **步骤 5：仅在 sealed-test 决定晋级时执行 baseline promotion**

仅当物化后的 final decision 精确为 `promote_pretraining_baseline` 时运行：

```bash
python3 AI大模型/scripts/promote_preregistered_mlm_baseline.py \
  --experiment-dir AI大模型/experiments/gelu-only-20260827 \
  --runtime-registry /private/tmp/gelu-only-20260827.runtime.json \
  --baseline-id continuous_full_gelu_v1
```

CLI 先在 repo 外 staging 构建全量 12,830 条 embedding index、index validation、collision audit 和独立评估，逐项验证后才切换 9 项 baseline 资产与最后的 asset manifest。final decision 为另外两种状态、证据 hash 不一致或任一安全 flag 非 false 时必须拒绝写 baseline。

- [ ] **步骤 6：完整验证、独立审查和结果提交**

```bash
PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -q
python3 -m py_compile AI大模型/scripts/*.py
git diff --check
```

提交前核对所有 SHA、raw counts、CI、decision、manifest 与三个 fail-closed flags；先暂存实验相关文件：

```bash
git add AI大模型/experiments/gelu-only-20260827 AI大模型/model_cards/sequence-pretraining.status.md progress.md findings.md
if [ "$final_decision" = "promote_pretraining_baseline" ]; then
git add \
  AI大模型/reports/sequence_pretraining_continuous_selection.json \
  AI大模型/reports/sequence_mlm_continuous_full_gelu_v1.json \
  AI大模型/reports/sequence_mlm_continuous_full_gelu_v1.checkpoint.pt \
  AI大模型/reports/sequence_embedding_index_continuous_full_gelu_v1.json \
  AI大模型/reports/sequence_embedding_index_continuous_full_gelu_v1_validation.json \
  AI大模型/reports/sequence_embedding_continuous_full_gelu_v1_collision_report.json \
  AI大模型/reports/sequence_mlm_continuous_full_gelu_v1_evaluation.json \
  AI大模型/reports/sequence_pretraining_release_gate.json \
  AI大模型/reports/sequence_pretraining_asset_manifest.json
fi
git commit -m "eval: 决策GELU预训练候选"
```

若未发生 promotion，条件分支不执行；该结果提交仍必须包含 exception ledger、decision receipt 和 experiment manifest。提交后再次运行 `validate_preregistered_mlm_experiment.py --phase final` 与 `git status --short`，前者成功且后者不得存在未提交 baseline 资产。
