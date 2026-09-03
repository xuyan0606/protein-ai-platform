---
name: enzyme-property-workflow-router
description: This skill should be used when an AI enzyme engineering platform needs to predict, optimize, or redesign one or more enzyme properties such as stability, pH adaptation, activity, specificity, or expression. It deterministically routes the primary property to a matching workflow, separates mandatory and optional steps, binds the proposed strategy to the executed workflow, and requires structured execution and validation. Do not use a single generic workflow for all properties.
agent_created: true
---

# Enzyme Property Workflow Router

## Purpose

将酶工程任务从“统一分析流程”改为“按性质目标确定性路由”。先识别主目标和次目标，再选择唯一主流程；流程中的步骤必须标记为 `MUST`、`OPTIONAL` 或 `FORBIDDEN`，并在执行前后核对策略与实际步骤是否一致。

该 skill 适用于稳定性、pH/酸碱适应、活性、特异性、表达，以及这些目标的多目标组合。详细流程定义见 `references/workflow_catalog.md`；稳定性专用流程见 `references/stability_workflow.md`；pH 专用流程见 `references/ph_workflow.md`；活性目标专用流程见 `references/activity_workflow.md`；特异性专用流程见 `references/specificity_workflow.md`；表达专用流程见 `references/expression_workflow.md`；策略卡片与流程步骤绑定见 `references/strategy_bindings.md`；工具细分标签见 `references/fine_tool_taxonomy.md`；工具替补矩阵见 `references/tool_fallback_matrix.md`；58 工具同功能分组见 `references/tool_groups.md`；输入策略见 `references/input_policy.md`；会话意图识别见 `references/conversation_intent.md`；平台接入契约见 `references/platform_contract.md`。

## 核心规则

1. **先识别会话意图，再决定是否开新流程。** 每轮用户输入先判定是追问、补充输入、改目标、新任务还是非执行对话；追问和补充不得重开预设流程。详见 `references/conversation_intent.md`。
2. **先同步工具注册表，后路由。** 每次新任务开始先读取当前 `/api/tools`，以当前返回的精确工具名和参数 schema 为准；不得依赖旧清单或 UI 快捷入口。
3. **首轮先盘点并告知缺口，等待用户反馈。** 允许用户用口语、段落、附件、上下文直接发起任务；先由 LLM 抽取已知信息并输出缺口，不调用性质分析或候选设计工具。用户补充信息或明确“按现有信息继续”后，才进入 workflow。详见 `references/input_policy.md`。
4. **先确认，再路由和分析。** 未完成目标分类、输入盘点和用户确认，不得调用性质分析工具；输入门是内部会话阶段，不是 `bio_specialty_input_gate` 工具。
5. **主目标只能有一个。** 多目标任务必须指定 `primary_property`；未指定时要求补充，不能自行把所有目标并列处理。
6. **主流程唯一。** 根据路由表选择一个 `workflow_id`，不得让模型自由拼接一条新流程。
7. **共享步骤最小化。** 仅执行所有任务都需要的预检查；性质专属步骤必须由对应流程决定。
8. **可选步骤必须有条件。** 每个 `OPTIONAL` 步骤必须写明触发条件、输入、预期产物和跳过理由。禁止使用“视情况”“必要时”等无判定标准的表述。
9. **策略与执行绑定。** 策略中引用的每个动作必须映射到一个 `step_id`；执行记录中不得出现未在计划中的分析或设计动作。
10. **每个性质任务必须服从对应专用流程。** 主目标是某性质时，加载对应的 `references/*_workflow.md`，按其中的工具级步骤、必选/可选/禁用规则执行，不得退回通用描述。
11. **工具步骤必须使用工具组。** 流程文件要列出首选工具、直接替补、降级替补、切换条件和不可替补边界；内部 intake_review 等控制阶段不调用平台工具。58 工具同功能分组见 `references/tool_groups.md`。
12. **替补只能同组切换。** 首选工具失败时，先用同一工具组的 `DIRECT` 替补，再用 `DEGRADED` 替补；降级结果必须降低证据等级并记录原因。
13. **替补不改变任务含义。** 不能用结构预测替代稳定性数据，用对接替代动力学预测，用活性预测替代特异性比较。
14. **禁止跨性质偷换流程。** 例如：稳定性任务不得默认执行底物对接；表达任务不得默认执行催化残基重设计；特异性任务不得用普通稳定性筛选代替底物识别分析。
15. **数据不足时停在缺口报告。** 不得用猜测补齐关键输入，也不得输出看似完整但无法执行的设计方案。
16. **先生成计划，再执行。** 任何设计、打分或候选筛选动作都必须在 `execution_plan` 中声明后执行。
17. **完成后做一致性校验。** 对照 `workflow_id`、步骤状态、工具调用记录和最终结论，输出偏差报告。

## 路由流程

### 0. 识别会话意图

每轮用户输入先判定意图（详见 `references/conversation_intent.md`）：

- `FOLLOW_UP`：对上一轮结果的追问、解释、修改要求。继续当前任务上下文，不重开流程。
- `INPUT_UPDATE`：补充之前任务缺失的信息。更新当前任务输入，再决定是否继续。
- `TARGET_CHANGE`：改变主目标或优先级。先重路由，再执行。
- `NEW_TASK`：明确提出新任务。新建任务上下文。
- `NON_EXECUTION`：只问概念、规则或解释，不进入平台任务。

只有在 `NEW_TASK` 或 `TARGET_CHANGE` 时才执行下面的目标解析与路由；`FOLLOW_UP` 与 `INPUT_UPDATE` 优先沿用当前会话上下文，不要把用户的追问当成新任务重跑整套流程。

### 1. 解析目标

**第一步：区分“要优化的目标”和“要保持的约束”。** 这是目标拆解准确的核心。用户的一句话里可能同时出现多个性质词，但只有“明确要求变好”的才是目标，其余一律是约束或仅监控项。提取三类：

- `optimization_targets`：用户明确要求**改变/变好**的性质（提升、降低、拓宽、收窄）。这是路由的唯一依据，缺它无法路由。
- `preservation_constraints`：用户要求**不下降、不受影响、保持原状**的性质（如“别影响活性”“活性不要掉”）。这只是约束，**禁止**进入任何优化流程，也禁止变成目标。
- `monitor_only`：用户仅提及但不要求改变的性质，只需在结果中报告是否受影响，不主动优化也不设硬约束。

提取字段：

- `primary_property`：主优化目标，来自 `optimization_targets`，必须唯一。
- `secondary_properties`：**只来自用户明确声明的第二个优化目标**（如“同时提升 X”“还要优化 Y”“第二目标是 Z”）。不得从约束、推荐或平台默认指标派生。
- `optimization_direction`：提升、降低、保持或拓宽/收窄（对应 `optimization_targets`）。
- `constraints`：来自 `preservation_constraints`（要保持的性质、固定残基、宿主、底物、实验条件等）。
- `available_inputs`：序列、结构、复合物、测定数据、突变数据、表达宿主等。

将同义词归一化：

| 归一化性质 | 常见表述（作为目标） |
|---|---|
| `stability` | 热稳定性、半衰期、溶剂耐受、蛋白酶耐受、耐受性 |
| `activity` | 活性、催化效率、kcat、Km、比活力、转化率、反应速率 |
| `specificity` | 特异性、选择性、底物谱、底物偏好、区域/立体选择性 |
| `expression` | 表达量、可溶性、折叠、分泌、聚集、宿主适配 |
| `pH` | 最适 pH、目标 pH 活性、pH 稳态拓宽、酸/碱耐受 |

**目标拆解反模式（禁止）：**

1. 用户说“提高热稳定性”，`primary_property=stability`，**不得**把活性/比活力当作优化目标或 `secondary_properties`。活性保持只是 `preservation_constraints` 里的“活性不下降”。
2. 用户用“不要影响/别掉/保持/不影响”描述某性质时，该性质是约束，不是目标。
3. 不得以“优化稳定性通常也要顺带优化活性”“该酶一般关注比活力”等经验为由，自行追加优化目标。
4. 不得将平台默认展示的推荐指标或历史常用指标，当成用户本次的目标。
5. 一个性质词出现 ≠ 一个目标。只有当用户显式表达“还要优化/第二目标/同时提升”时才产生 `secondary_property`。
6. 单目标需求（只提一个性质要变好）时，`secondary_properties` 必须为空，不得联想补充。

判定主目标顺序（仅在确实出现多个 `optimization_targets` 时）：

1. 用户明确指定的主目标；
2. 交付指标中带有“首要/主要/优先”的目标；
3. 与当前失败表型最直接对应的目标；
4. 仍无法判定时，停止并要求用户指定，不得默认使用统一流程。

### 2. 选择唯一工作流

| 主目标 | `workflow_id` | 必须加载 |
|---|---|---|
| 稳定性 | `WF-STABILITY` | 稳定性流程 |
| pH/酸碱适应 | `WF-PH` | pH 专用流程 |
| 活性 | `WF-ACTIVITY` | 活性流程 |
| 特异性 | `WF-SPECIFICITY` | 特异性流程 |
| 表达 | `WF-EXPRESSION` | 表达流程 |
| 不在支持范围 | `WF-UNSUPPORTED` | 缺口报告流程 |

### 2.1 策略卡片绑定

完成 `workflow_id` 选择后，必须从 `references/strategy_bindings.md` 检索与 `property`、`objective_scope`、`host_context` 和输入证据匹配的策略卡片。绑定结果必须写入执行计划：

```yaml
selected_strategy_cards:
  - strategy_id: PH-NEAR-01
    workflow_id: WF-PH
    step_ids: [P-03, P-04, P-05, P-06, P-07, P-10, P-11, P-12]
    required_inputs: [target_pH, pH_curve, catalytic_residues]
    forbidden_when: [surface_pI_only, catalytic_geometry_unconfirmed]
```

规则：

1. `strategy_id` 必须能映射到唯一 `workflow_id`。
2. 每个启用策略必须列出至少一个 `step_id`。
3. `required_inputs` 不满足时，该策略标记为 `blocked`，不得静默换成其他性质策略。
4. `forbidden_when` 命中时，禁止进入候选设计步骤。
5. `validation_metrics` 必须写入最终验收项。

**两类附加项必须区分，禁止混淆：**

- **约束（`preservation_constraints`）**：在每个专用流程里作为“不得破坏”的验收线存在，例如稳定性主目标下，活性/表达只需保持不显著下降；用户没要求优化它们，就绝不能进入候选优化的步骤。
- **次目标优化（`secondary_properties`）**：仅当用户明确声明第二个要变好的性质时才存在，作为受控附加模块，且只有在其输入足够、主流程完成后才能触发。

典型正确拆解示例：

| 用户原话 | `primary_property` | `secondary_properties` | `preservation_constraints` |
|---|---|---|---|
| 提高某某酶的热稳定性 | `stability` | `[]` | 活性不下降、表达不下降 |
| 提高热稳定性，同时把比活力也提上去 | `stability` | `[activity]` | 表达不下降 |
| 提升催化效率，但别影响热稳定性 | `activity` | `[]` | 稳定性不下降 |
| 同时提高活性和特异性 | `activity`（或用户指定） | `[specificity]` | 表达不下降 |

`secondary_properties` 为空时，报告里**不得出现**任何其他性质的“优化候选”或“提升建议”，只能出现“保持不变的验收结论”。

### 3. 生成执行计划

执行计划必须使用以下结构，不得只输出散文式方案：

```yaml
workflow_id: WF-STABILITY
optimization_targets: [stability]
primary_property: stability
selected_strategy_cards: []
secondary_properties: []            # 仅当用户明确第二个优化目标时非空
preservation_constraints: [activity_not_drop, expression_not_drop]
route_confidence: high
input_gaps: []
steps:
  - step_id: ST-01
    status: MUST
    action: 建立参考序列和结构输入
    trigger: always
    tools: [platform_tool_name]
    expected_output: reference_record
  - step_id: ST-02
    status: OPTIONAL
    action: 运行结构稳定性评估
    trigger: "存在可信结构或可获得结构模型"
    tools: [platform_tool_name]
    expected_output: stability_features
    skip_reason: null
forbidden_steps: []
validation:
  - 检查所有 MUST 步骤已执行
  - 检查策略动作均映射到 step_id
  - 检查未执行 FORBIDDEN 步骤
```

平台接入时，将 `platform_tool_name` 替换为真实工具标识。不要凭空创建不存在的工具名。

### 4. 执行与记录

每执行一步，记录：

- `step_id`
- 实际调用的 `tool_id`
- 输入摘要和输入版本
- 输出摘要和输出版本
- 状态：`completed`、`skipped`、`blocked` 或 `failed`
- 若为 `OPTIONAL` 且跳过，填写满足/不满足触发条件的证据
- 若发生计划外动作，立即标记 `unplanned_action`，停止后续设计步骤并重新审查计划

### 5. 结束校验

最终输出前执行四项校验：

1. **路由校验**：最终报告中的主目标、`workflow_id` 和流程目录一致。
2. **步骤校验**：所有 `MUST` 步骤已完成；`OPTIONAL` 步骤有条件证据；`FORBIDDEN` 步骤未执行。
3. **策略校验**：每个候选设计的依据都能追溯到已执行步骤和实际输出。
4. **结果校验**：区分预测、设计建议、实验验证结果；没有实验数据时不得写成“已验证”。

任一校验失败时，输出 `status: NEEDS_REVIEW`，列出偏差，不得输出 `status: READY`。

## 标准输出

最终结果至少包含：

```yaml
status: READY | NEEDS_INPUT | NEEDS_REVIEW | UNSUPPORTED
route:
  optimization_targets: [...]
  primary_property: ...
  secondary_properties: []          # 不得包含约束；为空时报告禁止出现其他性质优化候选
  preservation_constraints: [...]
  workflow_id: ...
  reason: ...
execution_summary:
  completed_steps: []
  skipped_optional_steps: []
  blocked_steps: []
  unplanned_actions: []
  strategy:
  selected_strategy_cards: []
  objective: ...
  constraints: []
  candidates: []
traceability:
  - candidate_id: ...
    supporting_step_ids: []
    evidence: ...
validation:
  route_consistent: true
  must_steps_complete: true
  forbidden_steps_clean: true
  strategy_execution_consistent: true
  no_undeclared_optimization_target: true   # 报告中出现的优化目标必须全部来自用户声明
  caveats: []
next_actions: []
```

## 失败处理

- 主目标不清：返回 `NEEDS_INPUT`，只询问目标优先级和评价指标。
- 关键输入缺失：返回 `NEEDS_INPUT`，列出缺失输入及其影响。
- 性质不支持：返回 `UNSUPPORTED`，说明当前 skill 支持范围，不得套用其他流程。
- 工具不可用：将对应步骤标记为 `blocked`，不得用未声明的替代流程静默替换。
- 计划与执行不一致：返回 `NEEDS_REVIEW`，停止生成最终候选或将候选标记为草案。

## 平台实现边界

该 skill 能约束模型的路由和输出格式，但不能单独保证平台的强制执行。平台侧至少应实现：

- 用结构化路由器根据 `primary_property` 选择 `workflow_id`；
- 用执行器只允许调用当前流程声明的工具和步骤；
- 保存每次执行的 `step_id` 与 `tool_id`；
- 在最终输出前运行一致性校验；
- 将流程定义和工具清单版本化。

如果平台只能把 `SKILL.md` 作为普通提示词注入，而没有执行器和校验器，稳定性会改善，但不能视为确定性保证。

## 参考资料

- `references/workflow_catalog.md`：五类性质的总流程目录，含独立 `WF-PH`。
- `references/fine_tool_taxonomy.md`：按实际功能重新整理的细分标签体系。
- `references/ph_workflow.md`：pH/酸碱适应目标的工具级流程、必选/可选/禁用工具和触发条件。
- `references/activity_workflow.md`：活性目标的工具级流程、必选/可选/禁用工具和触发条件。
- `references/platform_tool_catalog.md`：平台工具名称、功能、输入输出和能力边界原始目录。
- `references/platform_contract.md`：平台路由器、执行器和校验器的最小接口契约。
