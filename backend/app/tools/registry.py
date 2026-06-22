"""Tool Registry with typed error contracts and lazy loading.

Inspired by:
- protein-mcp-server: typed error contracts with reason/code/when/recovery
- OpenBioMed: LazyDictForTool pattern with __missing__ for lazy init
- deepagents: middleware-compatible tool schema
"""

from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum


class ErrorReason(str, Enum):
    """Standardized error reasons for tool failure recovery."""
    INVALID_INPUT = "invalid_input"
    FILE_NOT_FOUND = "file_not_found"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    VALIDATION_FAILED = "validation_failed"
    RATE_LIMITED = "rate_limited"
    COMPUTE_ERROR = "compute_error"
    UNKNOWN = "unknown"


@dataclass
class ToolError:
    """Typed error contract — LLM can use this for recovery decisions."""
    reason: str
    code: str
    when: str
    recovery: str


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable
    is_async: bool = False
    category: str = "general"
    errors: list[ToolError] = field(default_factory=list)
    timeout_seconds: int = 300
    annotations: dict = field(default_factory=dict)
    _lazy: bool = False  # True if handler needs lazy init

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_mcp_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters,
            "annotations": self.annotations,
        }


class LazyToolRegistry(dict):
    """Dict subclass that lazily initializes tools on first access.

    Pattern from OpenBioMed: __missing__ is called when a key isn't found,
    triggering lazy initialization of expensive resources (GPU models, clients).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._factories: dict[str, Callable] = {}

    def register_lazy(self, name: str, factory: Callable):
        """Register a lazy tool — factory called on first access."""
        self._factories[name] = factory

    def __missing__(self, key: str):
        if key in self._factories:
            tool = self._factories[key]()
            self[key] = tool
            return tool
        raise KeyError(key)

    def available_tools(self) -> list[str]:
        return list(self.keys()) + list(self._factories.keys())


class ToolRegistry:
    """Central tool registry with typed error contracts and aliases."""

    import concurrent.futures

    _tools: dict[str, Tool] = {}
    _aliases: dict[str, str] = {}
    _executor: concurrent.futures.ThreadPoolExecutor | None = None
    _lazy: LazyToolRegistry = LazyToolRegistry()

    # ---- Registration ----

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
        is_async: bool = False,
        category: str = "general",
        errors: list[dict] | None = None,
        timeout_seconds: int = 300,
        annotations: dict | None = None,
    ):
        """Register a tool with full metadata and error contracts."""
        tool_errors = []
        if errors:
            for e in errors:
                tool_errors.append(ToolError(
                    reason=e.get("reason", "unknown"),
                    code=e.get("code", "UNKNOWN"),
                    when=e.get("when", "during tool execution"),
                    recovery=e.get("recovery", "Check input parameters and retry."),
                ))

        cls._tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            is_async=is_async,
            category=category,
            errors=tool_errors,
            timeout_seconds=timeout_seconds,
            annotations=annotations or {},
        )

    @classmethod
    def register_alias(cls, alias: str, canonical: str):
        """Register an alias that redirects to a canonical tool name."""
        cls._aliases[alias] = canonical

    # ---- Discovery ----

    @classmethod
    def discover(cls):
        """Import all tool modules to trigger @register_tool decorators."""
        import concurrent.futures

        import app.tools.predict_properties  # noqa
        import app.tools.sequence_search  # noqa
        import app.tools.esmfold_folding  # noqa
        import app.tools.mutation_scan  # noqa
        import app.tools.blast_search  # noqa
        import app.tools.alphafold_folding  # noqa
        import app.tools.alphafold2_folding  # noqa
        import app.tools.diffdock_docking  # noqa
        import app.tools.proteinmpnn_design  # noqa
        import app.tools.rfdiffusion_design  # noqa
        import app.tools.esm2_predict  # noqa
        import app.tools.esm3_generate  # noqa
        import app.tools.ligandmpnn_design  # noqa
        import app.tools.esm1v_predict  # noqa
        import app.tools.rosettafold_folding  # noqa
        import app.tools.rosettafold_allatom  # noqa
        import app.tools.boltz1_predict  # noqa
        import app.tools.esm_if1_design  # noqa
        import app.tools.progen2_generate  # noqa
        import app.tools.evodiff_generate  # noqa
        import app.tools.chroma_design  # noqa
        import app.tools.soluble_mpnn_design  # noqa
        import app.tools.gromacs_md  # noqa
        import app.tools.mutation_priority_score  # noqa
        import app.tools.protein_benchmark  # noqa

        if cls._executor is None:
            cls._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    @classmethod
    def shutdown(cls):
        """Shutdown the thread pool executor."""
        if cls._executor is not None:
            cls._executor.shutdown(wait=True)
            cls._executor = None

    # ---- Access ----

    @classmethod
    def get_tool(cls, name: str) -> Tool | None:
        # Check aliases first
        canonical = cls._aliases.get(name, name)
        return cls._tools.get(canonical)

    @classmethod
    def get_tools_schema(cls) -> list[dict]:
        """Return all tools in OpenAI function-calling format with error hints."""
        return [
            t.to_openai_schema()
            for t in cls._tools.values()
        ]

    @classmethod
    def get_mcp_schema(cls) -> list[dict]:
        """Return all tools in MCP-compatible format."""
        return [
            t.to_mcp_schema()
            for t in cls._tools.values()
        ]

    @classmethod
    def list_error_contracts(cls) -> dict[str, list[dict]]:
        """Return all error contracts for LLM recovery guidance."""
        return {
            name: [
                {"reason": e.reason, "code": e.code, "when": e.when, "recovery": e.recovery}
                for e in tool.errors
            ]
            for name, tool in cls._tools.items()
        }

    # ---- Execution ----

    @classmethod
    async def execute(cls, name: str, params: dict) -> Any:
        """Execute a tool with error handling and timeout."""
        # Resolve alias
        canonical = cls._aliases.get(name, name)
        tool = cls._tools.get(canonical)

        if not tool:
            raise ValueError(f"Unknown tool: {name}. Available: {list(cls._tools.keys())}")

        import asyncio
        import functools

        try:
            if tool.is_async:
                result = await asyncio.wait_for(
                    tool.handler(**params),
                    timeout=tool.timeout_seconds,
                )
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        cls._executor,
                        functools.partial(tool.handler, **params),
                    ),
                    timeout=tool.timeout_seconds,
                )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Tool '{name}' timed out after {tool.timeout_seconds}s. "
                "Consider reducing input size or splitting the task."
            )
        except Exception as e:
            # Augment with error contract info if available
            error_hint = ""
            for err in tool.errors:
                if err.reason in str(e).lower():
                    error_hint = f"Recovery suggestion: {err.recovery}"
                    break
            if error_hint:
                raise type(e)(f"{e}\n{error_hint}") from e
            raise

    # ---- Categories ----

    @classmethod
    def list_by_category(cls) -> dict[str, list[str]]:
        """Group tools by category for organized display."""
        categories: dict[str, list[str]] = {}
        for name, tool in cls._tools.items():
            cat = tool.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(name)
        return categories

    @classmethod
    def categories(cls) -> list[str]:
        return list(set(t.category for t in cls._tools.values()))
