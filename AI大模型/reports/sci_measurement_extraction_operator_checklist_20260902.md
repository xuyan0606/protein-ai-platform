# SCI 测量抽取审核清单

## 每条证据必须填写

- PMCID 与来源文件路径
- 表格定位 ID
- 构建体或突变体名称
- 测量类型（如 kcat、Km、Tm、半衰期）
- 数值与原文单位
- 完整实验条件（底物、温度、pH、缓冲液等）
- 原文引用或表格行定位
- 审核人、审核时间

## 提交规则

- 未确认的记录保持 `pending_human_extraction`。
- 不得填写推算值、四舍五入值或模型预测值。
- 完成记录必须使用 `status=reviewed`，并通过模板校验器。
- 通过抽取校验不等于训练授权；训练导入仍需独立决策和发布闸门。

## 校验命令

```bash
python3 scripts/validate_sci_measurement_extraction_templates.py
python3 scripts/validate_literature_measurement_review_healthcheck.py
```
