# KWB-EnzymeDesigner 路线图

## 阶段 1：模型合同和样本标准

- 定义统一输入输出 schema。
- 定义工具调用事件 schema。
- 明确序列、结构、底物、实验条件、突变、证据来源字段。
- 建立最小 benchmark：低 pH 淀粉酶、脂肪酶、热稳定性、底物适配、上传结构编号映射。

## 阶段 2：规则 + 数据驱动 MVP

- 复用现有 `mutation_priority_score`、`annotation_bundle`、`residue_numbering_gate`、`structure_search_foldseek`。
- 从 KWB Lipase DB 和实验反馈中提取证据。
- 输出统一候选突变表和多头评分。
- GPT-5.6 继续负责主控和报告。

## 阶段 3：KWB 小模型

- 训练 `mutation_rank_head`。
- 训练 `stability_head`。
- 训练 `activity_risk_head`。
- 训练 `substrate_fit_head`。
- 训练 `assay_success_head`。

## 阶段 4：平台接入

- 后端新增 `kwb_enzyme_designer` 工具。
- 前端新增模型运行时间线和多头评分面板。
- 工具调用结果进入任务审计和训练样本库。
- 报告输出区分实验结构、预测结构、序列级结论、私有数据证据、模型推断。

## 阶段 5：实验反馈闭环

- 支持实验轮次管理。
- 支持 plate/library 设计。
- 每轮实验结果回填模型样本库。
- 每个模型版本绑定数据版本、评测结果和发布记录。

