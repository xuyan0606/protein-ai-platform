# KWB-EnzymeDesigner v0.1.0-rule-mvp Model Card

## 类型

规则 + 数据驱动 MVP，不是已训练神经网络模型。

## 目标

在没有正式训练模型前，先验证统一输入输出、多头评分、催化保护、结构门控和 benchmark 流程。

## 当前能力

- 读取 `KWB-EnzymeCase`。
- 输出候选突变排序。
- 输出 5 个 head 分数：
  - mutation rank
  - stability
  - activity risk
  - substrate fit
  - assay success
- 对催化保护位点输出 `no_go`。
- 对证据不足场景输出 `watch` 或降低置信度。
- 输出证据引用和下一轮实验建议。

## 当前不能宣称

- 不能宣称已完成机器学习训练。
- 不能宣称预测值等价于实验结果。
- 不能宣称 docking/MD/结构结论在无工具结果时已经验证。
- 不能作为湿实验替代。

## 验证

- 本地样例推理：passed。
- 本地 6-case benchmark：passed。
- HTTP 本地 smoke：passed。

## 后续版本

`v0.2.0` 建议加入：

- 真实 KWB Lipase DB 特征抽取。
- 工具调用审计样本抽取。
- benchmark 更细评分。
- `mutation_rank_head` 训练数据准备。

