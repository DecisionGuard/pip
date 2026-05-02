"""Microsoft AutoGen auditor agent for DecisionGuard.

Usage:
    from decisionguard import DecisionGuardAuditor, DecisionGuardClient

    client = DecisionGuardClient.from_env()
    auditor = DecisionGuardAuditor(client, actor_id="autogen-agent")

    # Use as a hook before executing function calls
    verdict = auditor.audit_function_call(
        function_name="execute_sql",
        arguments={"query": "SELECT * FROM users"},
        sender_name="assistant",
        goal="retrieve user data",
    )
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .dg_client import DecisionGuardClient, DGBlockedError, DGEscalatedError, enforce_verdict


class DecisionGuardAuditor:
    def __init__(
        self,
        client: DecisionGuardClient,
        actor_id: str = "autogen-agent",
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

    def audit_function_call(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        sender_name: str = "assistant",
        goal: str = "",
        idempotency_key: Optional[str] = None,
        data_classifications: Optional[List[str]] = None,
        risk_signals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "actor": {
                "id": self.actor_id,
                "type": self.actor_type,
                "source": sender_name,
                "authority": self.authority,
            },
            "intent": {
                "requested_goal": goal or f"Execute {function_name}",
                "proposed_action": f"{function_name}({arguments})",
            },
            "environment": self.environment,
            "tool": {
                "name": function_name,
                "operation": function_name,
                "params": arguments,
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
        self.audit_log.append({"function": function_name, "response": response})
        return enforce_verdict(response)

    def create_hook(self, goal: str = "") -> Callable:
        auditor = self

        def hook(
            function_name: str,
            arguments: Dict[str, Any],
            sender_name: str = "assistant",
        ) -> bool:
            try:
                auditor.audit_function_call(
                    function_name=function_name,
                    arguments=arguments,
                    sender_name=sender_name,
                    goal=goal,
                )
                return True
            except (DGBlockedError, DGEscalatedError):
                return False

        return hook

    def get_audit_summary(self) -> Dict[str, Any]:
        total = len(self.audit_log)
        verdicts: Dict[str, int] = {}
        for entry in self.audit_log:
            v = entry["response"].get("verdict", "UNKNOWN")
            verdicts[v] = verdicts.get(v, 0) + 1
        return {"total_audits": total, "verdicts": verdicts}
