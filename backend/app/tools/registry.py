"""Tool Registry with typed error contracts and lazy loading.

Inspired by:
- protein-mcp-server: typed error contracts with reason/code/when/recovery
- OpenBioMed: LazyDictForTool pattern with __missing__ for lazy init
- deepagents: middleware-compatible tool schema
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum
import inspect


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
        effective_is_async = is_async or inspect.iscoroutinefunction(handler)
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
            is_async=effective_is_async,
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

    # All tool modules to load.  Each entry is (module_path, label).
    # Label is optional — defaults to module name.
    _TOOL_MODULES: list[str] = [
        "app.tools.predict_properties",
        "app.tools.sequence_search",
        "app.tools.esmfold_folding",
        "app.tools.mutation_scan",
        "app.tools.blast_search",
        "app.tools.alphafold_folding",
        "app.tools.alphafold2_folding",
        "app.tools.diffdock_docking",
        "app.tools.proteinmpnn_design",
        "app.tools.rfdiffusion_design",
        "app.tools.esm2_predict",
        "app.tools.esm3_generate",
        "app.tools.ligandmpnn_design",
        "app.tools.esm1v_predict",
        "app.tools.rosettafold_folding",
        "app.tools.rosettafold_allatom",
        "app.tools.rosetta_ddg",
        "app.tools.boltz1_predict",
        "app.tools.ligand_preprocess",
        "app.tools.esm_if1_design",
        "app.tools.progen2_generate",
        "app.tools.evodiff_generate",
        "app.tools.chroma_design",
        "app.tools.soluble_mpnn_design",
        "app.tools.gromacs_md",
        "app.tools.enzyme_identity_profile",
        "app.tools.mutation_priority_score",
        "app.tools.kwb_enzyme_designer",
        "app.tools.protein_benchmark",
        "app.tools.protssn_score",
        "app.tools.enzyme_function",
        "app.tools.kcat_predict",
        "app.tools.data_lookup",
        "app.tools.wt_baseline_registry",
        "app.tools.annotation_bundle",
        "app.tools.interpro_annotation",
        "app.tools.interpro_live_lookup",
        "app.tools.interproscan_sequence_submit",
        "app.tools.literature_live_search",
        "app.tools.external_connectivity_check",
        "app.tools.catalytic_site_lookup",
        "app.tools.signal_peptide_predict",
        "app.tools.residue_mapping_sifts",
        "app.tools.structure_search_foldseek",
        "app.tools.site_structure_function_features",
        "app.tools.ligand_contact_analysis",
        "app.tools.structure_pocket_interface_analysis",
        "app.tools.disulfide_saltbridge_scan",
        "app.tools.pocket_residue_lookup",
        "app.tools.mutation_epistasis_check",
        "app.tools.feedback_iteration_planner",
        "app.tools.residue_numbering_gate",
        "app.tools.scientific_claim_gate",
        "app.tools.enzyme_objective_module_plan",
        "app.tools.tool_capability_audit",
        "app.tools.bio_specialty_input_gate",
        "app.tools.external_research_evidence",
    ]

    @classmethod
    def discover(cls):
        """Import all tool modules with per-module error handling.

        Each import is wrapped in try/except so one broken module (missing
        dependency, network timeout at module level, etc.) never blocks the
        rest.  Failed tools are clearly logged and simply skipped.
        """
        import importlib
        import logging
        import time

        _log = logging.getLogger(__name__)

        ok = 0
        failed = 0

        for mod in cls._TOOL_MODULES:
            name = mod.rsplit(".", 1)[-1]
            start = time.monotonic()
            try:
                importlib.import_module(mod)
                elapsed = time.monotonic() - start
                _log.debug("Tool '%s' loaded (%.1fs)", name, elapsed)
                ok += 1
            except ImportError as e:
                elapsed = time.monotonic() - start
                _log.warning("Tool '%s' skipped — ImportError (%.1fs): %s", name, elapsed, e)
                failed += 1
            except Exception as e:
                elapsed = time.monotonic() - start
                _log.warning("Tool '%s' skipped — %s (%.1fs): %s", name, type(e).__name__, elapsed, e)
                failed += 1

        _log.info("Tools: %d loaded, %d skipped", ok, failed)

        if cls._executor is None:
            import concurrent.futures
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
    async def execute(cls, name: str, params: dict, *, internal_params: dict[str, Any] | None = None) -> Any:
        """Execute a tool with error handling and timeout."""
        # Resolve alias
        canonical = cls._aliases.get(name, name)
        tool = cls._tools.get(canonical)

        if not tool:
            raise ValueError(f"Unknown tool: {name}. Available: {list(cls._tools.keys())}")

        import asyncio
        import functools

        try:
            # Validate required parameters before execution
            required = tool.parameters.get("required", []) if isinstance(tool.parameters, dict) else []
            missing = [r for r in required if r not in params or params[r] is None]
            if missing:
                raise ValueError(
                    f"Tool '{name}' missing required parameters: {missing}. "
                    f"Provided: {list(params.keys())}"
                )

            # Filter out undeclared params — LLM-generated plans may include extras
            declared = set(tool.parameters.get("properties", {}).keys()) if isinstance(tool.parameters, dict) else set()
            if declared:
                filtered = {k: v for k, v in params.items() if k in declared}
                # Always include required params even if somehow missing from properties
                for r in required:
                    if r not in filtered:
                        filtered[r] = params[r]
            else:
                filtered = params

            if internal_params:
                signature = inspect.signature(tool.handler)
                for key, value in internal_params.items():
                    if key in signature.parameters:
                        filtered[key] = value

            if tool.is_async:
                result = await asyncio.wait_for(
                    tool.handler(**filtered),
                    timeout=tool.timeout_seconds,
                )
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        cls._executor,
                        functools.partial(tool.handler, **filtered),
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
