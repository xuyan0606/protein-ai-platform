# 国际先进路线调研：KWB-EnzymeDesigner 对标

日期：2026-07-24

## 结论

国际先进蛋白/酶 AI 不是单一 GPT 式聊天模型，而是多模型系统：

- 蛋白语言模型负责序列表示、远缘同源和突变先验。
- 结构模型负责折叠、复合物、配体和位点几何。
- 结构条件生成模型负责提出可折叠突变组合。
- 实验反馈系统负责把真实 assay 结果反哺排序模型。
- 主控 LLM 负责工具编排、解释和报告，不直接替代专业模型。

这与科为博平台的最佳架构一致：GPT-5.6 继续做主控，`KWB-EnzymeDesigner` 做自有专业工具模型。

## 对标对象

### AlphaFold 3

定位：结构与相互作用预测。

要点：

- 覆盖蛋白、核酸、小分子、离子等复合物建模。
- 对酶平台的启发是：底物适配、口袋几何和蛋白-配体状态必须进入结构层，而不能只靠序列文本判断。

参考：

- Nature: https://www.nature.com/articles/s41586-024-07487-w
- Google DeepMind: https://blog.google/innovation-and-ai/products/google-deepmind-isomorphic-alphafold-3-ai-model/

### ESM3

定位：多模态蛋白语言模型，联合序列、结构、功能生成。

要点：

- 适合做序列/结构/功能联合表示和生成候选。
- 对科为博的启发是：自有模型应保留多头输出，不要只做一个综合分。

参考：

- Science DOI: https://doi.org/10.1126/science.ads0018

### ProteinMPNN / LigandMPNN

定位：给定结构或配体环境的序列设计。

要点：

- ProteinMPNN 适合结构约束下的序列改造。
- LigandMPNN 更贴近酶场景，因为它把小分子、金属、核酸等原子上下文纳入设计。
- 对科为博的启发是：底物 fit head 应从配体/口袋原子环境中抽特征，而不是只看底物名称。

参考：

- ProteinMPNN PubMed: https://pubmed.ncbi.nlm.nih.gov/36108050/
- LigandMPNN PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC11978504/

### ProGen / ProGen2 / 条件蛋白语言模型

定位：蛋白序列生成和条件生成。

要点：

- 适合做 enzyme family 和 function-conditioned generation。
- 对科为博的启发是：可以先做 adapter/LoRA/轻量头，不需要一开始训练超大基础模型。

参考：

- ProGen: https://arxiv.org/abs/2004.03497
- ProGen2: https://arxiv.org/abs/2206.13517
- ProCALM: https://arxiv.org/abs/2410.03634

## 科为博落地路线

### V1：自有数据 + 多头排序模型

目标：

- MutationRanker
- StabilityPredictor
- ActivityRiskModel
- SubstrateFitModel
- AssaySuccessPredictor

实现方式：

- 对外统一为 `KWB-EnzymeDesigner`。
- 内部保留五个 head。
- GPT-5.6 调用它，不与它冲突。

### V2：结构增强

需要补：

- 上传/预测结构解析。
- 位点到结构编号映射。
- 距催化残基距离。
- 距底物/配体/口袋距离。
- 位点 SASA/埋藏度。
- pLDDT/局部结构可信度。

### V3：保守性和家族增强

需要补：

- MSA 频率。
- 位点保守性。
- BLOSUM/替换矩阵特征。
- PFAM/domain 内相对位置。
- enzyme family embedding。

### V4：真实反馈闭环

需要补：

- 实验设计版本号。
- 样品表达/纯化/活性/稳定性结果。
- assay 条件标准化。
- 失败样本保留。
- 每轮模型推荐与实验结果对齐。

## 当前差距

本地 0.4.0 已完成监督训练流水线，但模型质量尚未成立：

- 500 条监督 mutation 标签可训练。
- 非泄漏 baseline validation/test accuracy = 0.317/0.239。
- 粗粒度结构代理特征没有改善表现。

这说明下一步应投入结构解析和保守性特征，而不是继续堆模型名字。
