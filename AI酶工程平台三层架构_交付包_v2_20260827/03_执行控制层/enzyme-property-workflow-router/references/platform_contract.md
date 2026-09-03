# Platform Contract

## Expected inputs (not mandatory schema)
平台不要求用户按固定表单输入。优先接收自然语言、段落、附件和上下文。以下为建议字段，缺失时先抽取已有信息，只对阻断执行的关键缺口追问（详见 `references/input_policy.md`）：
- `optimization_targets`（用户要改变/变好的性质；可由目标描述推断，是路由唯一依据）
- `preservation_constraints`（用户要求保持不下降的性质，例如“别影响活性”）
- `primary_property`（来自 `optimization_targets`，必须唯一）
- `secondary_properties`（**只**来自用户明确声明的第二个优化目标，不得从约束派生）
- `sequence` or `reference_id`
- `assay_metric`
- `available_inputs`

## Router responsibilities
- Detect conversation intent before routing: `NEW_TASK`, `FOLLOW_UP`, `INPUT_UPDATE`, `TARGET_CHANGE`, `NON_EXECUTION` (see `references/conversation_intent.md`).
- For `NEW_TASK`, run internal `intake_review` first; do not call property-analysis tools in the first turn.
- Return an input inventory containing known inputs, gaps, gap levels, impact, and recommended next inputs.
- Wait for user feedback: accept added inputs, or accept an explicit `continue_with_current` instruction.
- For `FOLLOW_UP` and `INPUT_UPDATE`, continue the existing session context instead of restarting a workflow.
- Normalize property labels.
- Select exactly one `workflow_id` only after the user-confirmed intake stage.
- Reject ambiguous primary property selection.
- Attach a route reason, confidence, and intake status.

## Executor responsibilities
- Execute only declared `step_id` items.
- Record `tool_id`, inputs, and outputs for each step.
- Record `primary_tool`, `selected_tool`, `fallback_level`, `fallback_reason`, and `tool_group` whenever a substitute is used.
- Mark skipped optional steps with evidence.
- Block plan drift.

## Validator responsibilities
- Compare route, steps, tool trace, and final report.
- Fail when a forbidden step appears.
- Fail when strategy and execution diverge.
- **Fail when any optimization target in the final report is not present in the user-declared `optimization_targets`.** Constraints (e.g. "keep activity") must never appear as optimization candidates or improvement suggestions.
- Emit `NEEDS_REVIEW` instead of masking drift.

## Minimal data schema
```yaml
session_id: string
intent: NEW_TASK|FOLLOW_UP|INPUT_UPDATE|TARGET_CHANGE|NON_EXECUTION
job_id: string
optimization_targets: []        # only user-declared properties to improve
primary_property: string        # from optimization_targets, unique
secondary_properties: []        # only explicit second optimization target
preservation_constraints: []    # properties to keep, NOT optimization targets
workflow_id: string
route_reason: string
route_confidence: low|medium|high
intake_status: WAITING_FOR_USER_INPUT|USER_CONFIRMED|READY_FOR_ANALYSIS
known_inputs: []
input_gaps: []
recommended_next_inputs: []
user_action: provide_missing_inputs|continue_with_current|clarify_target
steps: []
trace: []
fallback_trace:
  - step_id: string
    tool_group: string
    primary_tool: string
    selected_tool: string
    fallback_level: DIRECT|DEGRADED
    fallback_reason: string
    evidence_change: string
final_status: READY|NEEDS_INPUT|NEEDS_REVIEW|UNSUPPORTED
```
