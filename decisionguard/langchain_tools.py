"""LangChain BaseTool wrapper for DecisionGuard.

Usage:
    from decisionguard import DGGuardedTool, guard_tools, DecisionGuardClient

    client = DecisionGuardClient.from_env()
    guarded = DGGuardedTool(inner_tool=my_tool, dg_client=client, actor_id="my-agent")
    result = guarded.run("some input")
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from .dg_client import DecisionGuardClient, enforce_verdict

try:
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel
except ImportError:
    from abc import ABC

    class BaseTool(ABC):  # type: ignore[no-redef]
        name: str = ""
        description: str = ""

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError

    class BaseModel:  # type: ignore[no-redef]
        pass


class DGGuardedTool(BaseTool):
    name: str = "dg_guarded_tool"
    description: str = "A tool guarded by DecisionGuard security audit"

    inner_tool: Any = None
    dg_client: Any = None
    actor_id: str = "langchain-agent"
    actor_type: str = "agent"
    authority: str = "supervised"
    environment: str = "production"
    data_classifications: Optional[list] = None
    risk_signals: Optional[list] = None

    def __init__(
        self,
        inner_tool: Any,
        dg_client: DecisionGuardClient,
        actor_id: str = "langchain-agent",
        actor_type: str = "agent",
        authority: str = "supervised",
        environment: str = "production",
        data_classifications: Optional[list] = None,
        risk_signals: Optional[list] = None,
        **kwargs: Any,
    ):
        tool_name = getattr(inner_tool, "name", "unknown_tool")
        tool_desc = getattr(inner_tool, "description", "")
        super().__init__(
            name=f"dg_guarded_{tool_name}",
            description=f"[DecisionGuard protected] {tool_desc}",
            inner_tool=inner_tool,
            dg_client=dg_client,
            actor_id=actor_id,
            actor_type=actor_type,
            authority=authority,
            environment=environment,
            data_classifications=data_classifications,
            risk_signals=risk_signals,
            **kwargs,
        )

    def _build_request(self, inner_name: str, tool_input: Any) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "actor": {
                "id": self.actor_id,
                "type": self.actor_type,
                "authority": self.authority,
            },
            "intent": {
                "requested_goal": f"Execute {inner_name}",
                "proposed_action": f"{inner_name}({tool_input})",
            },
            "environment": self.environment,
            "tool": {
                "name": inner_name,
                "operation": inner_name,
                "payload_summary": str(tool_input)[:500],
            },
        }
        if self.data_classifications or self.risk_signals:
            request["facts"] = {
                "has_sensitive_data": bool(self.data_classifications),
                "data_classifications": self.data_classifications or [],
                "risk_signals": self.risk_signals or [],
            }
        return request

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        tool_input = args[0] if args else str(kwargs)
        inner_name = getattr(self.inner_tool, "name", "unknown_tool")
        request = self._build_request(inner_name, tool_input)
        response = self.dg_client.audit(request)
        enforce_verdict(response)
        return self.inner_tool._run(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        tool_input = args[0] if args else str(kwargs)
        inner_name = getattr(self.inner_tool, "name", "unknown_tool")
        request = self._build_request(inner_name, tool_input)
        response = await self.dg_client.aaudit(request)
        enforce_verdict(response)

        if hasattr(self.inner_tool, "_arun"):
            return await self.inner_tool._arun(*args, **kwargs)
        return self.inner_tool._run(*args, **kwargs)


def guard_tools(
    tools: list,
    dg_client: DecisionGuardClient,
    actor_id: str = "langchain-agent",
    actor_type: str = "agent",
    authority: str = "supervised",
    environment: str = "production",
    data_classifications: Optional[list] = None,
    risk_signals: Optional[list] = None,
) -> list:
    """Wrap an entire list of LangChain tools with DecisionGuard in one call."""
    return [
        DGGuardedTool(
            inner_tool=t,
            dg_client=dg_client,
            actor_id=actor_id,
            actor_type=actor_type,
            authority=authority,
            environment=environment,
            data_classifications=data_classifications,
            risk_signals=risk_signals,
        )
        for t in tools
    ]
