# Agent 工作流接入设计

## 目标

让 GPT-5.6 继续作为主控模型，同时把 KWB-EnzymeDesigner 作为专业工具模型接入，解决工具调用顺序、证据分层和突变推荐一致性问题。

## 标准流程

```text
用户输入
  -> 输入解析
  -> 文件/序列/结构门控
  -> 工具计划
  -> KWB-EnzymeDesigner
  -> 报告合成
  -> 实验反馈入口
```

## 流程门控

### G1：输入完整性

阻断条件：

- 没有序列。
- 没有结构。
- 没有明确蛋白/酶名称或 ID。

允许基础问答，但不进入结构依赖工具链。

### G2：结构门控

上传 PDB 优先级最高：

```text
uploaded PDB > PDB ID > AlphaFold > ESMFold
```

上传 PDB 可用时不应先跑 ESMFold。

### G3：编号门控

任何位点级结论前必须明确：

- 链 ID。
- 序列编号或结构编号。
- SIFTS/比对映射状态。

### G4：证据门控

报告必须分层：

- KWB 私有实验证据。
- 公开数据库/文献证据。
- 工具预测证据。
- 模型推断。
- 需要实验验证。

### G5：会话和任务隔离

每一轮结构预测、结构解析和 KWB 模型调用必须绑定当前：

- `session_id`
- `conversation_id`
- `request_turn_id`
- `task_id`

禁止行为：

- 新一轮回答引用旧轮次 `esmfold_folding` task_id。
- 上传 PDB 已可用时仍优先提交 ESMFold。
- 编号未确认时输出口袋距离、暴露度、催化网络等结构依赖结论。

降级行为：

- 找不到当前轮结构结果时，只允许输出序列级结论。
- 结构预测未完成时，结构级结论状态必须为 `blocked` 或 `pending_structure`。

## KWB-EnzymeDesigner 调用条件

建议调用：

- 用户要求突变推荐。
- 用户要求稳定性、活性、底物适配、多目标优化。
- 已有实验反馈需要下一轮设计。
- 已有结构和底物，需要口袋相关候选。

不建议调用：

- 普通平台介绍。
- 缺少具体酶目标。
- 纯文献问答，未要求设计。

## 输出合成规则

GPT-5.6 应只解释 KWB 模型结果，不覆盖或捏造分数。

必须保留：

- mutation
- overall_score
- five head scores
- confidence
- decision
- risk_flags
- evidence_refs
- next_experiment
