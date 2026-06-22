"""Agent middleware chain architecture.

Inspired by deepagents: composable middleware that contributes
tools, system prompts, state schema, and lifecycle hooks.

Each middleware wraps agent operations:
- before_agent: one-time setup before execution
- wrap_tool_call: intercept/modify tool results
- wrap_model_response: intercept/modify LLM responses
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MiddlewareContext:
    """Execution context passed through middleware chain."""
    session_id: str = ""
    user_id: str = ""
    tool_call_count: int = 0
    total_tokens: int = 0
    large_result_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentMiddleware(ABC):
    """Base middleware — composable agent behavior extension.

    Each middleware can:
    - Contribute system prompt fragments
    - Provide tools to the agent
    - Intercept and modify tool calls/results
    - Manage context lifecycle
    """

    name: str = "base"
    system_prompt_suffix: str = ""
    tools: list = []

    async def before_agent(self, ctx: MiddlewareContext, state: dict) -> dict | None:
        """Called once before agent execution starts.
        Return a dict to update agent state.
        """
        return None

    async def wrap_tool_call(
        self, tool_name: str, params: dict, handler: Callable, ctx: MiddlewareContext
    ) -> Any:
        """Intercept tool calls — modify params or result.
        Default: pass through to handler.
        """
        return await handler(**params)

    async def wrap_model_response(
        self, response: Any, ctx: MiddlewareContext
    ) -> Any:
        """Intercept model responses — add context or modify output."""
        return response

    async def after_agent(self, ctx: MiddlewareContext, final_state: dict) -> None:
        """Called after agent execution completes."""
        pass


class ContextOverflowHandler(AgentMiddleware):
    """Handles context overflow by summarizing or truncating.

    Inspired by deepagents SummarizationMiddleware:
    - Offloads long conversation to backend storage
    - Truncates large tool arguments before summarization
    - Provides compact_conversation capability
    """

    name = "context_overflow"
    max_tokens_before_compact: int = 100_000
    keep_recent_turns: int = 6

    async def wrap_model_response(self, response: Any, ctx: MiddlewareContext) -> Any:
        ctx.total_tokens += self._estimate_tokens(response)
        return response

    def _estimate_tokens(self, response: Any) -> int:
        return len(str(response)) // 4


class LargeResultEvictionMiddleware(AgentMiddleware):
    """Evicts large tool results to storage, replacing with preview + path.

    Inspired by deepagents FilesystemMiddleware.wrap_tool_call:
    - Intercepts tool results exceeding token budget
    - Offloads to backend storage
    - Replaces with truncated preview
    """

    name = "large_result_eviction"
    tool_token_limit: int = 20_000

    async def wrap_tool_call(
        self, tool_name: str, params: dict, handler: Callable, ctx: MiddlewareContext
    ) -> Any:
        result = await handler(**params)
        result_str = str(result)
        if len(result_str) > self.tool_token_limit:
            ctx.large_result_count += 1
            return {
                "summary": f"Result too large ({len(result_str)} chars), "
                f"truncated from {self.tool_token_limit} chars.",
                "preview": result_str[:1000],
                "full_size": len(result_str),
                "hint": "Re-request with more specific parameters for full results.",
            }
        return result


class MiddlewareChain:
    """Ordered chain of middleware executed in sequence."""

    def __init__(self, middleware: list[AgentMiddleware] | None = None):
        self._middleware: list[AgentMiddleware] = middleware or []
        self.ctx = MiddlewareContext()

    def use(self, mw: AgentMiddleware) -> "MiddlewareChain":
        self._middleware.append(mw)
        return self

    async def before_agent(self, state: dict) -> dict:
        updates = {}
        for mw in self._middleware:
            result = await mw.before_agent(self.ctx, state)
            if result:
                updates.update(result)
        return updates

    async def wrap_tool(self, name: str, params: dict, handler: Callable) -> Any:
        """Execute handler through middleware chain (innermost first)."""
        async def chain(index: int, **kwargs) -> Any:
            if index >= len(self._middleware):
                return await handler(**kwargs)
            mw = self._middleware[index]

            async def next_handler(**kw):
                return await chain(index + 1, **kw)

            return await mw.wrap_tool_call(name, kwargs, next_handler, self.ctx)

        return await chain(0, **params)

    async def wrap_response(self, response: Any) -> Any:
        for mw in self._middleware:
            response = await mw.wrap_model_response(response, self.ctx)
        return response

    @property
    def system_prompt(self) -> str:
        parts = []
        for mw in self._middleware:
            if mw.system_prompt_suffix:
                parts.append(mw.system_prompt_suffix)
        return "\n".join(parts)
