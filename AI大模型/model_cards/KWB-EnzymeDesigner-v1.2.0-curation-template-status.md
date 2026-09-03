# KWB-EnzymeDesigner v1.2.0 Curation Template Status

状态：本地回源模板和批次状态跟踪完成。

## 目标

让 P0 回源工作可以按批次执行，并明确区分：

- template：工作草稿，不进入 apply。
- decisions：真实审核决策，进入 validate/apply。

## 产物

- `scripts/build_curation_decision_templates.py`
- `scripts/build_curation_batch_status.py`
- `datasets/curation/decision_templates/p0_batch_001.decisions.template.jsonl`
- `reports/curation_decision_template_report.json`
- `reports/curation_batch_status_report.json`

## 当前结果

- templates：5 files
- template rows：125
- batch rows：125
- decided rows：0
- coverage：0.0
- safe pipeline steps：18
- failed steps：0

## 安全规则

`apply_numbering_curation.py` 只读取：

```text
datasets/curation/numbering_curation_decisions.jsonl
```

不会读取 `decision_templates/` 下的模板文件。
