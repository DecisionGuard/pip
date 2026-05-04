"""Generic audit-step and guard-and-execute functions for any workflow or agent.

Usage:
    from decisionguard import guard_and_execute, audit_step, audit_or_fail, DecisionGuardClient

    client = DecisionGuardClient.from_env()

    # ── Recommended: guard_and_execute ──────────────────────────────────────
    # DG evaluates FIRST. Tool only runs if approved.
    # Pattern: DG → tool  (not: tool → DG)

    def send_email(recipient, subject, body):
        ...

    result = guard_and_execute(
        client,
        tool_fn=send_email,
        tool_name="send_email",
        goal="Complete the user email workflow",
        proposed_action=f"Send email to {recipient}",
        tool_kwargs={"recipient": recipient, "subject": subject, "body": body},
        environment="production",
        actor_source="langchain",
    )

    # ── Lower-level: audit_step / audit_or_fail ─────────────────────────────
    ok, resp = audit_step(client, ...)
    result = audit_or_fail(client, ...)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, Optional, Tuple

from .dg_client import (
    DecisionGuardClient,
    DGBlockedError,
    DGEscalatedError,
    enforce_review_verdict,
    enforce_verdict,
)


def guard_and_execute(
    client: DecisionGuardClient,
    tool_fn: Callable[..., Any],
    tool_name: str,
    goal: str,
    proposed_action: str,
    tool_args: Optional[tuple] = None,
    tool_kwargs: Optional[Dict[str, Any]] = None,
    change_type: str = "agentic_action",
    environment: str = "production",
    resource_name: Optional[str] = None,
    actor_source: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Any:
    """DG evaluates first; tool only executes if approved.

    Pattern:  DG → tool   (not: tool → DG)

    Args:
        client:           DecisionGuardClient instance.
        tool_fn:          The callable to execute if DG approves.
        tool_name:        Name of the tool (shown in DG dashboard).
        goal:             High-level goal the agent is pursuing.
        proposed_action:  Specific action description sent to DG.
        tool_args:        Positional args forwarded to tool_fn.
        tool_kwargs:      Keyword args forwarded to tool_fn.
        change_type:      DG change category (default: 'agentic_action').
        environment:      'production', 'staging', or 'development'.
        resource_name:    The resource being acted upon.
        actor_source:     Source system label (e.g. 'langchain', 'crewai').
        idempotency_key:  Deduplicate repeated submissions.

    Returns:
        The return value of tool_fn if approved.

    Raises:
        DGBlockedError:    If DG returns BLOCK.
        DGEscalatedError:  If DG returns REQUIRE_APPROVAL.
    """
    response = client.review(
        change_type=change_type,
        change_payload={
            "tool_name": tool_name,
            "summary": proposed_action,
            "args": list(tool_args) if tool_args else [],
            "kwargs": tool_kwargs or {},
        },
        environment=environment,
        intent={"goal": goal, "proposed_action": proposed_action},
        resource_name=resource_name,
        actor_source=actor_source,
        idempotency_key=idempotency_key,
    )

    enforce_review_verdict(response)  # raises DGBlockedError or DGEscalatedError if not approved

    return tool_fn(*(tool_args or ()), **(tool_kwargs or {}))


async def aguard_and_execute(
    client: DecisionGuardClient,
    tool_fn: Callable[..., Any],
    tool_name: str,
    goal: str,
    proposed_action: str,
    tool_args: Optional[tuple] = None,
    tool_kwargs: Optional[Dict[str, Any]] = None,
    change_type: str = "agentic_action",
    environment: str = "production",
    resource_name: Optional[str] = None,
    actor_source: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Any:
    """Async version of guard_and_execute(). Requires httpx."""
    response = await client.areview(
        change_type=change_type,
        change_payload={
            "tool_name": tool_name,
            "summary": proposed_action,
            "args": list(tool_args) if tool_args else [],
            "kwargs": tool_kwargs or {},
        },
        environment=environment,
        intent={"goal": goal, "proposed_action": proposed_action},
        resource_name=resource_name,
        actor_source=actor_source,
        idempotency_key=idempotency_key,
    )

    enforce_review_verdict(response)

    result = tool_fn(*(tool_args or ()), **(tool_kwargs or {}))
    if hasattr(result, "__await__"):
        result = await result
    return result


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
