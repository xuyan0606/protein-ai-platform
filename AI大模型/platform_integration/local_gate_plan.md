# KWB-EnzymeDesigner 本地接入 Gate 计划

## 目标

在修改主平台源码或同步服务器前，先完成本地 gate，降低接入风险。

## Gate 0：研发区边界

- 确认 `LOCAL_ONLY.md` 存在。
- 确认未执行服务器同步。
- 确认产物只在 `AI大模型/` 和本地进度文件中。

## Gate 1：合同校验

命令：

```bash
python3 -m json.tool AI大模型/contracts/kwb_enzyme_case.schema.json
python3 -m json.tool AI大模型/contracts/kwb_enzyme_designer.schema.json
python3 -m json.tool AI大模型/contracts/tool_event.schema.json
```

通过标准：

- JSON 均合法。
- 样例数据能抽取特征。

## Gate 2：规则 MVP

命令：

```bash
python3 AI大模型/prototype/kwb_enzyme_designer_rule.py AI大模型/datasets/sample_case.json --output AI大模型/reports/sample_case_result.json
```

通过标准：

- 输出模型名为 `KWB-EnzymeDesigner`。
- 至少有一个候选突变。
- 催化保护位点输出 `no_go`。
- 结果包含多头评分。

## Gate 3：Benchmark

命令：

```bash
python3 AI大模型/scripts/run_local_benchmark.py --output AI大模型/reports/local_benchmark_report.json
```

通过标准：

- 6 个案例全部通过。
- 没有 `needs_work`。

## Gate 4：本地 HTTP 服务

命令：

```bash
python3 AI大模型/scripts/smoke_local_service.py
```

通过标准：

- `GET /health` 返回 ok。
- `POST /v1/enzyme-design` 返回候选突变。

## Gate 4.5：结构工作流门控

命令：

```bash
python3 AI大模型/scripts/run_structure_workflow_gate.py
```

通过标准：

- 上传结构先完成结构解析和编号门控，不提交 ESMFold。
- 编号未确认时，结构依赖分析和 KWB 模型调用为 blocked。
- 仅序列时允许序列级分析，但结构依赖结论等待 ESMFold。
- 旧会话/旧轮次 task ref 被忽略，task_id 按 session/conversation/turn 隔离。

## Gate 5：训练数据准备

命令：

```bash
python3 AI大模型/scripts/check_safe_training_entrypoint.py
```

训练入口默认 fail-closed：只有 `training_pipeline_unlocked=true` 且 strict supervised rows 达到阈值后，才允许进入后续训练脚本；不得直接运行旧 `build_training_table.py` 或 baseline ranker 绕过安全入口。

通过标准：

- 生成 features JSONL/CSV。
- 生成 training table。
- 生成 baseline model。
- baseline 评估 accuracy >= 0.7。

## Gate 6：平台接入前审查

必须人工确认：

- 是否允许改 `backend/app/tools/`。
- 是否允许改 `ToolRegistry._TOOL_MODULES`。
- 是否允许改 `AgentOrchestrator` 规划逻辑。
- 是否允许改前端结果卡片。
- 是否允许本地 dev server 验证。
- 是否允许后续同步服务器。

未经用户明确确认，不进入 Gate 6 后的源码接入。
