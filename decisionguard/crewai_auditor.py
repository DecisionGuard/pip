"""CrewAI auditor role for DecisionGuard.

Usage:
    from decisionguard import DecisionGuardCrewAuditor, DecisionGuardClient

    client = DecisionGuardClient.from_env()
    auditor = DecisionGuardCrewAuditor(client, actor_id="crewai-agent")

    # Audit a planned action before crew execution
    result = auditor.audit_task(
        task_description="Deploy updated model to production",
        agent_role="deployer",
        tool_name="kubectl",
        tool_args={"command": "apply -f deployment.yaml"},
    )
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .dg_client import DecisionGuardClient, DGBlockedError, DGEscalatedError, enforce_verdict


class DecisionGuardCrewAuditor:
    def __init__(
        self,
        client: DecisionGuardClient,
        actor_id: str = "crewai-agent",
        actor_type: str = "agent",
        authority: str = "supervised",
        environment: str = "production",
    ):
        self.client = client
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.authority = authority
        self.environment = environment
        self.audit_log: List[Dict[str, Any]] = []

    def audit_task(
        self,
        task_description: str,
        agent_role: str = "crew_member",
        tool_name: str = "crew_task",
        tool_args: Optional[Dict[str, Any]] = None,
        agent_confidence: float = 0.5,
        idempotency_key: Optional[str] = None,
        data_classifications: Optional[List[str]] = None,
        risk_signals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "actor": {
                "id": self.actor_id,
                "type": self.actor_type,
                "source": agent_role,
                "authority": self.authority,
            },
            "intent": {
                "requested_goal": task_description,
                "proposed_action": f"{tool_name}({tool_args or {}})",
                "agent_confidence": agent_confidence,
            },
            "environment": self.environment,
            "tool": {
                "name": tool_name,
                "operation": tool_name,
                "params": tool_args or {},
            },
        }
        if idempotency_key:
            request["idempotency_key"] = idempotency_key
        if data_classifications or risk_signals:
            request["facts"] = {
                "has_sensitive_data": bool(data_classifications),
                "data_classifications": data_classifications or [],
                "risk_signals": risk_signals or [],
            }

        response = self.client.audit(request)
        self.audit_log.append({
            "task": task_description,
            "role": agent_role,
            "response": response,
        })
        return enforce_verdict(response)

    def guard_tool(self, tool_fn: Callable, tool_name: str, agent_role: str = "crew_member") -> Callable:
        auditor = self

        def guarded(*args: Any, **kwargs: Any) -> Any:
            auditor.audit_task(
                task_description=f"Execute {tool_name}",
                agent_role=agent_role,
                tool_name=tool_name,
                tool_args=kwargs,
            )
            return tool_fn(*args, **kwargs)

        guarded.__name__ = f"dg_guarded_{tool_name}"
        guarded.__doc__ = getattr(tool_fn, "__doc__", "")
        return guarded

    def get_audit_summary(self) -> Dict[str, Any]:
        total = len(self.audit_log)
        verdicts: Dict[str, int] = {}
        for entry in self.audit_log:
            v = entry["response"].get("verdict", "UNKNOWN")
            verdicts[v] = verdicts.get(v, 0) + 1
        return {"total_audits": total, "verdicts": verdicts}
