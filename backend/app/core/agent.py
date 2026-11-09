"""Agent orchestration — re-exports the multi-role Plan-Execute-Synthesize engine.

The actual implementation is in agent_graph.py (graph nodes and flow)
and agent_roles.py (role-specific system prompts).
"""

from app.core.agent_graph import AgentOrchestrator, ChatSnapshot, PlanStep

# Re-export the singleton
from app.core.agent_graph import orchestrator

__all__ = ["AgentOrchestrator", "ChatSnapshot", "PlanStep", "orchestrator"]
