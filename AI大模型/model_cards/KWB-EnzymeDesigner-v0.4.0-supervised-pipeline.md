# KWB-EnzymeDesigner v0.4.0 Supervised Pipeline

状态：本地研发完成，未达到生产模型声明门槛。

## 目标

验证科为博自有酶蛋白模型可以从本地 enzyme DB 标签进入监督训练流水线：

- 标签抽取
- 训练表构建
- protein-group 切分
- baseline 训练
- 评估和 readiness gating

## 数据

- 来源：`datasets/features/enzyme_mutation_labels.jsonl`
- 监督训练表：`datasets/curated/enzyme_mutation_training_table.jsonl`
- 行数：500
- UniProt group：145
- 标签分布：go 161、watch 181、no_go 158

## 防泄漏规则

当前标签由 dTm/ddG 派生，因此：

- `label_stability_delta_tm_c` 不作为输入特征。
- `label_ddg` 不作为输入特征。
- 两者只保留为标签元数据和审计字段。

## 切分

- train：373 行
- validation：60 行
- test：67 行
- group leakage：0

## 评估

- 监督 baseline：dependency-free centroid classifier + majority-class fallback
- 选中策略：`majority_class`
- centroid validation accuracy：0.250
- majority validation accuracy：0.317
- selected validation accuracy：0.317
- selected test accuracy：0.239

## 结论

监督训练流水线已经成立，但当前基础突变特征不足以支撑可用预测。下一阶段应加入：

- 结构位点和口袋距离特征。
- 活性中心保护和编号门控特征。
- MSA/保守性特征。
- 酶家族 embedding。
- KWB 真实湿实验反馈。
