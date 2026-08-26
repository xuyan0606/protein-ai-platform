# 连续预训练资产 Manifest 升级实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将当前资产包从独立 batch-0001 基准升级为连续覆盖 12,830 条序列的单一 checkpoint，并以哈希和 fail-closed 门禁保证交接安全。

**架构：** 连续训练报告和 checkpoint 作为唯一当前基准；连续 checkpoint 生成全量 embedding index。选择清单、发布隔离报告、模型卡和资产 manifest 通过路径与 SHA-256 绑定，旧批次资产只保留历史用途。

**技术栈：** Python 3、PyTorch、unittest、JSON/Markdown、SHA-256。

---

### 任务 1：为当前基准切换编写失败测试

**文件：**
- 修改：`AI大模型/tests/test_pretraining_asset_manifest.py`
- 测试：`AI大模型/tests/test_pretraining_asset_manifest.py`

- [ ] **步骤 1：编写失败测试**

加入断言：当前 manifest 的 assets 必须包含 `sequence_mlm_continuous_full.checkpoint.pt`，且不得包含 `sequence_mlm_batch_0001.checkpoint.pt`；旧 manifest 在该断言下必须失败。

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest AI大模型/tests/test_pretraining_asset_manifest.py -q`

预期：FAIL，原因是当前 manifest 仍绑定旧 batch-0001 选择清单和 checkpoint。

- [ ] **步骤 3：Commit**

```bash
git add AI大模型/tests/test_pretraining_asset_manifest.py
git commit -m "test: require continuous checkpoint in asset manifest"
```

### 任务 2：生成连续基准选择清单

**文件：**
- 创建：`AI大模型/reports/sequence_pretraining_continuous_selection.json`
- 修改：`AI大模型/scripts/build_pretraining_asset_manifest.py`

- [ ] **步骤 1：实现选择清单生成**

清单必须读取 `sequence_mlm_continuous_full.json`，记录 `sequence_count=12830`、`checkpoint_path`、checkpoint SHA-256、`selection_rule=continuous_full_dataset_coverage`、`supersedes=sequence_pretraining_checkpoint_selection.json`，并固定 `release_status=pretraining_only_not_for_production`。

- [ ] **步骤 2：运行生成并校验字段**

运行 Python 生成命令，断言 checkpoint 存在、序列数为 12,830、安全标记均为 false。

- [ ] **步骤 3：Commit**

```bash
git add AI大模型/scripts/build_pretraining_asset_manifest.py AI大模型/reports/sequence_pretraining_continuous_selection.json
git commit -m "feat: bind continuous pretraining checkpoint"
```

### 任务 3：切换资产 manifest 和发布门输入

**文件：**
- 修改：`AI大模型/reports/sequence_pretraining_asset_manifest.json`
- 修改：`AI大模型/reports/sequence_pretraining_release_gate.json`
- 修改：`AI大模型/model_cards/sequence-pretraining.status.md`

- [ ] **步骤 1：重建连续 checkpoint 的 embedding index**

使用 `build_sequence_embedding_index.py` 输出 `sequence_embedding_index_continuous_full.json`，并生成对应 validation/collision 报告。

- [ ] **步骤 2：重建 7 项资产 manifest**

资产集合改为连续选择清单、连续训练报告、连续 checkpoint、连续 index、连续 validation、连续 collision、模型卡和发布门报告；每项写入存在性、大小和 SHA-256。

- [ ] **步骤 3：重新运行发布隔离门**

要求输出 `decision=blocked_pretraining_only`、`release_ready=false`。

- [ ] **步骤 4：Commit**

```bash
git add AI大模型/reports AI大模型/model_cards/sequence-pretraining.status.md
git commit -m "feat: upgrade pretraining asset bundle to continuous run"
```

### 任务 4：完整验证与篡改回归

**文件：**
- 修改：`AI大模型/tests/test_pretraining_asset_manifest.py`

- [ ] **步骤 1：运行定向和全量测试**

运行：`python3 -m unittest discover -s AI大模型/tests -q`

预期：所有测试通过，包含 manifest 基准切换断言。

- [ ] **步骤 2：运行 manifest 独立验证**

运行资产 manifest 验证器，预期 `missing_count=0`、`hash_mismatch_count=0`、`boundary_ok=true`、`release_ready=false`。

- [ ] **步骤 3：执行独立内容审计**

读取最终 manifest，断言连续 checkpoint 路径存在，旧 `sequence_mlm_batch_*.checkpoint.pt` 不在当前资产列表中，且所有安全标记为 false。

- [ ] **步骤 4：Commit**

```bash
git add AI大模型/tests/test_pretraining_asset_manifest.py AI大模型/reports/sequence_pretraining_asset_manifest_validation.json
git commit -m "test: verify continuous asset manifest integrity"
```
