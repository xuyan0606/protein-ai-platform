# Family-level Split 计划

## 为什么需要 family-level split

酶蛋白数据高度同源。如果同一个家族或高度相似序列同时出现在训练集和测试集，模型评估会虚高。

普通随机切分可能导致：

- 同源 lipase 同时进入 train/test。
- 同一项目不同轮次进入 train/test。
- 同一文献不同突变进入 train/test。

这样得到的准确率不能代表真实泛化能力。

## 推荐切分层级

优先级从高到低：

1. `project_id`
2. `enzyme.family`
3. `enzyme.uniprot_id`
4. `sequence_md5`
5. `paper_key`

## 第一版策略

```text
group_key = project_id || enzyme_family || uniprot_id || sequence_md5 || paper_key || case_id
```

按 `group_key` 切分：

- train: 70%
- validation: 15%
- test: 15%

## Benchmark 规则

benchmark 案例永远不进入训练集。

## 报告要求

每次训练报告必须包含：

- train/validation/test 样本数。
- family 分布。
- project 分布。
- mutation label 分布。
- 是否存在 group leakage。

## 下一步脚本

- `scripts/make_family_split.py`
- `reports/family_split_report.json`

