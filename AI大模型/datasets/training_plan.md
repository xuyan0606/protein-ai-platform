# 训练数据准备计划

## 目标

把 KWB 私有实验数据、平台工具结果、benchmark 案例和公开证据整理为可训练数据。

## 数据分层

### Tier A：核心训练样本

要求：

- 有明确序列或结构。
- 有明确突变。
- 有实验标签。
- 有 assay 条件。
- 有数据来源和人工审核。

用途：

- 训练 `mutation_rank_head`。
- 训练 `stability_head`。
- 训练 `activity_risk_head`。

### Tier B：弱监督样本

要求：

- 有文献或数据库证据。
- 标签可能不完整。
- 有人工或规则抽取的趋势判断。

用途：

- 预训练排序器。
- 辅助特征校准。
- 不能直接作为最终实验准确率评估。

### Tier C：证据展示样本

要求：

- 只有文献摘要、工具预测或数据库注释。
- 没有明确实验标签。

用途：

- RAG 和报告证据。
- 不进入监督训练标签。

## 数据切分

建议：

- train：70%
- validation：15%
- test：15%

切分原则：

- 同一项目、同一酶家族高度相似样本不要跨 train/test 泄漏。
- benchmark 案例不进入训练集。
- 最终测试集优先使用真实实验记录。

## 第一批数据源

- KWB Lipase Evidence DB。
- 平台实验反馈记录。
- 工具调用审计。
- Venus-15B 淀粉酶案例。
- 用户上传结构和分析结果。

## 下一步脚本

- `scripts/extract_features.py`
- `scripts/build_training_table.py`
- `scripts/train_baseline_ranker.py`
- `scripts/evaluate_baseline_ranker.py`

