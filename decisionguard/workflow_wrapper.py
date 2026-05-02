"""Generic audit-step function for n8n, CI, and workflow integrations.

Usage:
    from decisionguard import audit_step, audit_or_fail, DecisionGuardClient

    client = DecisionGuardClient.from_env()

    # Returns the response dict (raises on BLOCK/ESCALATE)
    result = audit_or_fail(
        client,
        actor_id="ci-pipeline",
        goal="deploy to production",
        action="helm upgrade myapp",
        tool_name="helm",
        operation="upgrade",
        environment="production",
    )

    # Or use audit_step which returns (success: bool, response: dict)
    ok, resp = audit_step(client, ...)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional, Tuple

from .dg_client import DecisionGuardClient, DGBlockedError, DGEscalatedError, enforce_verdict


def audit_step(
    client: DecisionGuardClient,
    actor_id: str,
    goal: str,
    action: str,
    tool_name: str,
    operation: str,
    environment: str = "production",
    actor_type: str = "service",
    authority: str = "supervised",
    params: Optional[Dict[str, Any]] = None,
    resource_name: Optional[str] = None,
    change_type: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    trace_id: Optional[str] = None,
    parent_decision_id: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    request: Dict[str, Any] = {
        "actor": {
            "id": actor_id,
            "type": actor_type,
            "authority": authority,
        },
        "intent": {
            "requested_goal": goal,
            "proposed_action": action,
        },
        "environment": environment,
        "tool": {
            "name": tool_name,
            "operation": operation,
        },
    }
    if params:
        request["tool"]["params"] = params
    if resource_name:
        request["tool"]["resource_name"] = resource_name
    if change_type:
        request["tool"]["change_type"] = change_type
    if idempotency_key:
        request["idempotency_key"] = idempotency_key
    if trace_id or parent_decision_id:
        request["trace"] = {}
        if trace_id:
            request["trace"]["trace_id"] = trace_id
        if parent_decision_id:
            request["trace"]["parent_decision_id"] = parent_decision_id

    response = client.audit(request)

    try:
        enforce_verdict(response)
        return True, response
    except (DGBlockedError, DGEscalatedError):
        return False, response


def audit_or_fail(
    client: DecisionGuardClient,
    actor_id: str,
    goal: str,
    action: str,
    tool_name: str,
    operation: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    ok, response = audit_step(
        client,
        actor_id=actor_id,
        goal=goal,
        action=action,
        tool_name=tool_name,
        operation=operation,
        **kwargs,
    )
    if not ok:
        raise RuntimeError(
            f"DecisionGuard denied action: verdict={response.get('verdict')}, "
            f"summary={response.get('summary')}"
        )
    return response


def cli_audit() -> None:
    if len(sys.argv) < 4:
        print("Usage: python -m decisionguard.workflow_wrapper <goal> <action> <tool_name>", file=sys.stderr)
        sys.exit(2)

    client = DecisionGuardClient.from_env()
    goal, action, tool_name = sys.argv[1], sys.argv[2], sys.argv[3]
    operation = sys.argv[4] if len(sys.argv) > 4 else tool_name
    actor_id = sys.argv[5] if len(sys.argv) > 5 else "cli-workflow"

    ok, response = audit_step(
        client,
        actor_id=actor_id,
        goal=goal,
        action=action,
        tool_name=tool_name,
        operation=operation,
    )

    print(json.dumps(response, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    cli_audit()
