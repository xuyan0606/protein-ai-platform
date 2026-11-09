"""MCP (Model Context Protocol) Server with typed error contracts.

Inspired by protein-mcp-server:
- Each tool declares typed errors with reason/code/when/recovery
- LLM can traverse the error tree for autonomous recovery
- Response budget management for large outputs
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json
import uuid
from datetime import datetime, timezone


class ToolStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPUTING = "computing"  # Async job still in progress


@dataclass
class ToolError:
    """Typed error for LLM-guided recovery."""
    reason: str
    code: str
    when: str
    recovery: str


@dataclass
class MCPTool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Any  # async callable
    is_async: bool = False
    timeout_seconds: int = 300
    errors: list[ToolError] = field(default_factory=list)
    annotations: dict = field(default_factory=dict)
    response_budget_bytes: int = 128 * 1024  # 128KB default


@dataclass
class ToolCall:
    id: str
    tool_name: str
    params: dict
    status: ToolStatus = ToolStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: str = ""
    duration_ms: int = 0
    retry_count: int = 0


class MCPServer:
    """MCP-compatible tool server with error contracts and budget management."""

    def __init__(self):
        self._tools: dict[str, MCPTool] = {}
        self._calls: dict[str, ToolCall] = {}
        self._max_calls: int = 1000

    def register(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> MCPTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """Return tools in MCP-compatible format with error contracts."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.parameters,
                "annotations": t.annotations,
                "errors": [
                    {"reason": e.reason, "code": e.code, "when": e.when, "recovery": e.recovery}
                    for e in t.errors
                ],
            }
            for t in self._tools.values()
        ]

    async def call_tool(self, name: str, params: dict) -> ToolCall:
        """Execute a tool call with lifecycle tracking and error enrichment."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(
                f"Unknown tool: {name}. Available: {list(self._tools.keys())}"
            )

        call = ToolCall(
            id=str(uuid.uuid4()),
            tool_name=name,
            params=params,
            status=ToolStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # Evict oldest calls if over max
        if len(self._calls) >= self._max_calls:
            oldest = min(
                self._calls.keys(),
                key=lambda k: self._calls[k].started_at,
            )
            del self._calls[oldest]

        self._calls[call.id] = call

        try:
            if tool.is_async:
                call.result = await tool.handler(**params)
            else:
                call.result = tool.handler(**params)
            call.status = ToolStatus.COMPLETED

            # Check response budget
            result_str = json.dumps(call.result, default=str)
            if len(result_str) > tool.response_budget_bytes:
                call.result = {
                    "summary": f"Result too large ({len(result_str)} bytes). "
                    f"Budget: {tool.response_budget_bytes} bytes.",
                    "preview": result_str[:1000],
                    "suggestion": "Re-request with more specific parameters or pagination.",
                }

        except Exception as e:
            call.status = ToolStatus.FAILED
            call.error = str(e)

            # Enrich with error contract recovery hint
            for err in tool.errors:
                if err.reason in str(e).lower() or err.code.lower() in str(e).lower():
                    call.error = f"{e}\n[Recovery: {err.recovery}]"
                    break

        return call

    def get_call(self, call_id: str) -> ToolCall | None:
        return self._calls.get(call_id)

    def cancel_call(self, call_id: str) -> bool:
        call = self._calls.get(call_id)
        if call and call.status in (ToolStatus.RUNNING, ToolStatus.COMPUTING):
            call.status = ToolStatus.CANCELLED
            call.error = "Cancelled by user"
            return True
        return False

    def list_calls(self, status: ToolStatus | None = None) -> list[ToolCall]:
        calls = list(self._calls.values())
        if status:
            calls = [c for c in calls if c.status == status]
        return sorted(calls, key=lambda c: c.started_at, reverse=True)[:50]


mcp_server = MCPServer()
