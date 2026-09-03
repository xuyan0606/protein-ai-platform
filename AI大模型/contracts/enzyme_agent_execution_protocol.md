# KWB Enzyme Agent Execution Protocol

Version: 2026-07-31

This protocol adapts Biomni's plan-execute-observe-reflect pattern into a KWB fail-closed enzyme engineering workflow.

## Protocol

1. Plan
   - State the user request, intended capability, and required evidence.
   - Select candidate actions from `datasets/governance/enzyme_action_space_registry.jsonl`.

2. Retrieve
   - Build a resource retrieval plan from action and tool contracts.
   - Classify resources into:
     - `recommended_read_only`
     - `executable_after_user_confirmation`
     - `blocked_requires_human_decision`
     - `forbidden_for_current_request`

3. Propose
   - Show planned tool calls before execution.
   - Include input artifacts, output artifacts, risk level, human gate, runtime/license status, and expected validator.

4. Execute
   - Only execute `allowed_execution_mode=local_script` contracts.
   - Never execute `manual_only` contracts without explicit user authorization.
   - Never execute external downloads, external MCP tools, formal decision writes, training imports, ordering, customer delivery, or release actions in this protocol.

5. Observe
   - Every execution must produce a report, receipt, or validator output.
   - Failed steps must be recorded with root cause and next action.

6. Reflect
   - Interpret only observed artifacts.
   - Do not claim progress from plans, drafts, or unavailable reports.

7. Conclude
   - Final output must include artifact references, blocked gates, manual review requirements, and forbidden claims.

## Hard Rules

- No formal human decision file may be written by the agent.
- No training rows may be written by the agent.
- No model-quality, customer, ordering, IP/FTO, biosecurity, external-tool-production, or release claim may be enabled.
- Review drafts and backlog rows remain draft-only.
- If a tool contract and a user request conflict, the contract wins unless the user explicitly authorizes a specific manual action.

## Next Artifacts

- `schemas/enzyme_resource_retrieval_plan.schema.json`
- `schemas/enzyme_agent_state_checkpoint.schema.json`
- `reports/enzyme_resource_retrieval_plan_report.json`
- `datasets/governance/enzyme_agent_state_checkpoints.jsonl`
