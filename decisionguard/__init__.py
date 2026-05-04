"""DecisionGuard Python SDK — runtime governance for AI agents."""

from .dg_client import (
    DecisionGuardClient,
    DGError,
    DGBlockedError,
    DGEscalatedError,
    enforce_verdict,
    enforce_review_verdict,
)
from .langchain_tools import DGGuardedTool, guard_tools
from .crewai_auditor import DecisionGuardCrewAuditor
from .autogen_auditor import DecisionGuardAuditor
from .openai_agents import DecisionGuardRail
from .workflow_wrapper import audit_step, audit_or_fail, guard_and_execute, aguard_and_execute

__all__ = [
    "DecisionGuardClient",
    "DGError",
    "DGBlockedError",
    "DGEscalatedError",
    "enforce_verdict",
    "enforce_review_verdict",
    "DGGuardedTool",
    "guard_tools",
    "DecisionGuardCrewAuditor",
    "DecisionGuardAuditor",
    "DecisionGuardRail",
    "audit_step",
    "audit_or_fail",
    "guard_and_execute",
    "aguard_and_execute",
]

__version__ = "0.4.1"
