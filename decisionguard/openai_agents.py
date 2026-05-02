"""OpenAI Agents SDK guardrail integration for DecisionGuard.

Usage:
    from decisionguard import DecisionGuardRail, DecisionGuardClient

    client = DecisionGuardClient.from_env()
    guard = DecisionGuardRail(client, actor_id="my-agent")

    # Use as a before-tool hook in OpenAI Agents SDK
    result = guard.before_tool_call(
        tool_name="sql_query",
        tool_args={"query": "DROP TABLE users"},
        agent_goal="clean up database",
    )
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .dg_client import DecisionGuardClient, DGBlockedError, DGEscalatedError, enforce_verdict


class DecisionGuardRail:
    def __init__(
        self,
        client: DecisionGuardClient,
        actor_id: str = "openai-agent",
        actor_type: str = "agent",
        authority: str = "supervised",
        environment: str = "production",
        on_block: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_escalate: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.client = client
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.authority = authority
        self.environment = environment
        self.on_block = on_block
        self.on_escalate = on_escalate

    def before_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        agent_goal: str = "",
        proposed_action: Optional[str] = None,
        agent_confidence: float = 0.5,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "actor": {
                "id": self.actor_id,
                "type": self.actor_type,
                "authority": self.authority,
            },
            "intent": {
                "requested_goal": agent_goal or f"Execute {tool_name}",
                "proposed_action": proposed_action or f"{tool_name}({', '.join(f'{k}={v!r}' for k, v in tool_args.items())})",
                "agent_confidence": agent_confidence,
            },
            "environment": self.environment,
            "tool": {
                "name": tool_name,
                "operation": tool_name,
                "params": tool_args,
            },
        }
        if idempotency_key:
            request["idempotency_key"] = idempotency_key

        response = self.client.audit(request)

        try:
            return enforce_verdict(response)
        except DGBlockedError:
            if self.on_block:
                self.on_block(response)
            raise
        except DGEscalatedError:
            if self.on_escalate:
                self.on_escalate(response)
            raise

    def wrap_tool(self, tool_fn: Callable, tool_name: str, agent_goal: str = "") -> Callable:
        rail = self

        def guarded(*args: Any, **kwargs: Any) -> Any:
            rail.before_tool_call(
                tool_name=tool_name,
                tool_args=kwargs,
                agent_goal=agent_goal,
            )
            return tool_fn(*args, **kwargs)

        guarded.__name__ = f"dg_guarded_{tool_name}"
        guarded.__doc__ = getattr(tool_fn, "__doc__", "")
        return guarded
