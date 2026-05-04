"""DecisionGuard HTTP client for Python.

Usage:
    from decisionguard import DecisionGuardClient

    client = DecisionGuardClient.from_env()
    response = client.audit({
        "actor": {"id": "agent-1", "type": "agent"},
        "intent": {"requested_goal": "deploy", "proposed_action": "helm upgrade"},
        "environment": "production",
        "tool": {"name": "kubectl", "operation": "apply"},
    })
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import httpx

    _USE_HTTPX = True
except ImportError:
    _USE_HTTPX = False

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]


class DGError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class DGBlockedError(Exception):
    def __init__(self, response: Dict[str, Any]):
        super().__init__(f"DecisionGuard blocked action: {response.get('summary', '')}")
        self.response = response


class DGEscalatedError(Exception):
    def __init__(self, response: Dict[str, Any]):
        super().__init__(f"DecisionGuard escalated action: {response.get('summary', '')}")
        self.response = response


@dataclass
class DecisionGuardClient:
    api_key: str
    base_url: str
    timeout: float = 30.0
    trace_id: Optional[str] = None
    parent_decision_id: Optional[str] = None

    @classmethod
    def from_env(cls, **overrides: Any) -> "DecisionGuardClient":
        api_key = overrides.pop("api_key", None) or os.environ.get("DG_API_KEY")
        base_url = (
            overrides.pop("base_url", None)
            or os.environ.get("DG_BASE_URL")
            or "https://decision-guard.com"
        )
        if not api_key:
            raise ValueError("DG_API_KEY is required")
        return cls(api_key=api_key, base_url=base_url.rstrip("/"), **overrides)

    def audit(self, request: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(request)
        if self.trace_id or self.parent_decision_id:
            trace = body.get("trace") or {}
            trace.setdefault("trace_id", self.trace_id)
            trace.setdefault("parent_decision_id", self.parent_decision_id)
            body["trace"] = trace

        url = f"{self.base_url}/api/v1/skills/security-audit"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(url, json=body, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    def review(
        self,
        change_type: str,
        change_payload: Dict[str, Any],
        environment: str = "production",
        intent: Optional[Dict[str, Any]] = None,
        resource_name: Optional[str] = None,
        actor_source: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a governance review via POST /api/v1/reviews.

        Args:
            change_type: Category of the action (e.g. 'agentic_action', 'deployment').
            change_payload: Dict describing the change (tool_name, summary, params, etc.).
            environment: 'production', 'staging', 'development'.
            intent: Optional dict with 'goal' and 'proposed_action' keys.
            resource_name: The resource being acted on (e.g. 'prod-db', 'k8s-cluster').
            actor_source: Source system (e.g. 'flowise', 'langchain', 'crewai').
            idempotency_key: Deduplicate repeated submissions.

        Returns:
            Full response dict. Use enforce_review_verdict() to raise on BLOCK/REQUIRE_APPROVAL.
        """
        body: Dict[str, Any] = {
            "change_type": change_type,
            "change_payload": change_payload,
            "environment": environment,
        }
        if intent:
            body["intent"] = intent
        if resource_name:
            body["resource_name"] = resource_name
        if actor_source:
            body["actor_source"] = actor_source
        if idempotency_key:
            body["idempotency_key"] = idempotency_key

        url = f"{self.base_url}/api/v1/reviews"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(url, json=body, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    async def areview(
        self,
        change_type: str,
        change_payload: Dict[str, Any],
        environment: str = "production",
        intent: Optional[Dict[str, Any]] = None,
        resource_name: Optional[str] = None,
        actor_source: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async version of review(). Requires httpx."""
        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use areview(): pip install httpx")

        body: Dict[str, Any] = {
            "change_type": change_type,
            "change_payload": change_payload,
            "environment": environment,
        }
        if intent:
            body["intent"] = intent
        if resource_name:
            body["resource_name"] = resource_name
        if actor_source:
            body["actor_source"] = actor_source
        if idempotency_key:
            body["idempotency_key"] = idempotency_key

        url = f"{self.base_url}/api/v1/reviews"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(url, json=body, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    def fact_check(
        self,
        content: str,
        context: Optional[str] = None,
        checks: Optional[list] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit content for fact-checking. Returns verdict, claims, issues, and a review_id."""
        body: Dict[str, Any] = {"content": content}
        if context:
            body["context"] = context
        if checks:
            body["checks"] = checks
        if timezone:
            body["timezone"] = timezone

        url = f"{self.base_url}/api/v1/fact-check"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(url, json=body, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard fact-check returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard fact-check returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    async def afact_check(
        self,
        content: str,
        context: Optional[str] = None,
        checks: Optional[list] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async version of fact_check(). Requires httpx."""
        body: Dict[str, Any] = {"content": content}
        if context:
            body["context"] = context
        if checks:
            body["checks"] = checks
        if timezone:
            body["timezone"] = timezone

        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use afact_check(): pip install httpx")

        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(
                f"{self.base_url}/api/v1/fact-check",
                json=body,
                headers={"Content-Type": "application/json", "x-api-key": self.api_key},
            )
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard fact-check returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    def auto_audit(
        self,
        tool_name: str,
        action_summary: str,
        parameters: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        parent_decision_id: Optional[str] = None,
        environment: str = "development",
        resource: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lightweight observe-only audit. Does not block; always records. Good for telemetry."""
        body: Dict[str, Any] = {
            "tool_name": tool_name,
            "action_summary": action_summary,
            "environment": environment,
        }
        if parameters:
            body["parameters"] = parameters
        if trace_id:
            body["trace_id"] = trace_id
        if parent_decision_id:
            body["parent_decision_id"] = parent_decision_id
        if resource:
            body["resource"] = resource

        url = f"{self.base_url}/api/v1/auto-audit"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(url, json=body, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    def list_reviews(
        self,
        limit: int = 50,
        actor_type: Optional[str] = None,
        actor_authority: Optional[str] = None,
        decision: Optional[str] = None,
        risk: Optional[str] = None,
        environment: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> list:
        """List reviews for the tenant. Requires reviews:list scope."""
        params: Dict[str, Any] = {"limit": limit}
        if actor_type:
            params["actor_type"] = actor_type
        if actor_authority:
            params["actor_authority"] = actor_authority
        if decision:
            params["decision"] = decision
        if risk:
            params["risk"] = risk
        if environment:
            params["environment"] = environment
        if change_type:
            params["change_type"] = change_type

        url = f"{self.base_url}/api/v1/reviews"
        headers = {"x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.get(url, params=params, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.get(url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    def batch_audit(self, reviews: list) -> Dict[str, Any]:
        """Submit up to 50 reviews in a single request. Returns per-item results."""
        if len(reviews) > 50:
            raise ValueError(f"Batch size {len(reviews)} exceeds maximum of 50")

        url = f"{self.base_url}/api/v1/reviews/batch"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(url, json={"reviews": reviews}, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.post(url, json={"reviews": reviews}, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    def list_resources(
        self,
        tag: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List active resources registered to the tenant."""
        params: Dict[str, Any] = {}
        if tag:
            params["tag"] = tag
        if resource_type:
            params["resource_type"] = resource_type

        url = f"{self.base_url}/api/v1/resources"
        headers = {"x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.get(url, params=params, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.get(url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    def get_identity(self, review_id: str) -> Dict[str, Any]:
        """Return the identity snapshot for a review. Requires reviews:read scope."""
        url = f"{self.base_url}/api/v1/reviews/{review_id}/identity"
        headers = {"x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.get(url, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    def get_review(self, review_id: str) -> Dict[str, Any]:
        """Fetch a past review by ID. Useful for polling approval status after ESCALATE."""
        url = f"{self.base_url}/api/v1/reviews/{review_id}"
        headers = {"x-api-key": self.api_key}

        if _USE_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.get(url, headers=headers)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        if _requests is not None:
            resp = _requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code >= 400:
                raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
            return resp.json()

        raise RuntimeError("Install httpx or requests to use DecisionGuardClient")

    async def aaudit(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of audit(). Requires httpx."""
        body = dict(request)
        if self.trace_id or self.parent_decision_id:
            trace = body.get("trace") or {}
            trace.setdefault("trace_id", self.trace_id)
            trace.setdefault("parent_decision_id", self.parent_decision_id)
            body["trace"] = trace

        url = f"{self.base_url}/api/v1/skills/security-audit"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use aaudit(): pip install httpx")

        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(url, json=body, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    async def aauto_audit(
        self,
        tool_name: str,
        action_summary: str,
        parameters: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        parent_decision_id: Optional[str] = None,
        environment: str = "development",
        resource: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async version of auto_audit(). Requires httpx."""
        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use aauto_audit(): pip install httpx")
        body: Dict[str, Any] = {
            "tool_name": tool_name,
            "action_summary": action_summary,
            "environment": environment,
        }
        if parameters:
            body["parameters"] = parameters
        if trace_id:
            body["trace_id"] = trace_id
        if parent_decision_id:
            body["parent_decision_id"] = parent_decision_id
        if resource:
            body["resource"] = resource

        url = f"{self.base_url}/api/v1/auto-audit"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(url, json=body, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    async def alist_reviews(
        self,
        limit: int = 50,
        actor_type: Optional[str] = None,
        actor_authority: Optional[str] = None,
        decision: Optional[str] = None,
        risk: Optional[str] = None,
        environment: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> list:
        """Async version of list_reviews(). Requires httpx."""
        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use alist_reviews(): pip install httpx")
        params: Dict[str, Any] = {"limit": limit}
        if actor_type:
            params["actor_type"] = actor_type
        if actor_authority:
            params["actor_authority"] = actor_authority
        if decision:
            params["decision"] = decision
        if risk:
            params["risk"] = risk
        if environment:
            params["environment"] = environment
        if change_type:
            params["change_type"] = change_type

        url = f"{self.base_url}/api/v1/reviews"
        headers = {"x-api-key": self.api_key}
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    async def abatch_audit(self, reviews: list) -> Dict[str, Any]:
        """Async version of batch_audit(). Requires httpx."""
        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use abatch_audit(): pip install httpx")
        if len(reviews) > 50:
            raise ValueError(f"Batch size {len(reviews)} exceeds maximum of 50")

        url = f"{self.base_url}/api/v1/reviews/batch"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(url, json={"reviews": reviews}, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    async def alist_resources(
        self,
        tag: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async version of list_resources(). Requires httpx."""
        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use alist_resources(): pip install httpx")
        params: Dict[str, Any] = {}
        if tag:
            params["tag"] = tag
        if resource_type:
            params["resource_type"] = resource_type

        url = f"{self.base_url}/api/v1/resources"
        headers = {"x-api-key": self.api_key}
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    async def aget_identity(self, review_id: str) -> Dict[str, Any]:
        """Async version of get_identity(). Requires httpx."""
        if not _USE_HTTPX:
            raise RuntimeError("Install httpx to use aget_identity(): pip install httpx")
        url = f"{self.base_url}/api/v1/reviews/{review_id}/identity"
        headers = {"x-api-key": self.api_key}
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.get(url, headers=headers)
        if resp.status_code >= 400:
            raise DGError(f"DecisionGuard returned {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    def with_trace(self, trace_id: str, parent_decision_id: Optional[str] = None) -> "DecisionGuardClient":
        return DecisionGuardClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
        )


def enforce_verdict(response: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce verdict from the security-audit skill endpoint.

    Verdict values: ALLOW, CONDITIONAL, ESCALATE, BLOCK
    """
    verdict = response.get("verdict", "BLOCK")
    if verdict == "ALLOW":
        return response
    if verdict == "CONDITIONAL":
        return response
    if verdict == "ESCALATE":
        raise DGEscalatedError(response)
    raise DGBlockedError(response)


def enforce_review_verdict(response: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce verdict from the POST /api/v1/reviews endpoint.

    Decision values: ALLOW, ALLOW_WITH_CONDITIONS, REQUIRE_APPROVAL, BLOCK
    Raises DGBlockedError on BLOCK, DGEscalatedError on REQUIRE_APPROVAL.
    Returns the full response on ALLOW or ALLOW_WITH_CONDITIONS.
    """
    data = response.get("data", response)
    verdict_obj = data.get("verdict", {})
    decision = verdict_obj.get("decision", "BLOCK") if isinstance(verdict_obj, dict) else str(verdict_obj)
    if decision == "ALLOW":
        return response
    if decision == "ALLOW_WITH_CONDITIONS":
        return response
    if decision == "REQUIRE_APPROVAL":
        raise DGEscalatedError({
            "decision": decision,
            "review_id": data.get("review_id"),
            "summary": verdict_obj.get("summary", "") if isinstance(verdict_obj, dict) else "",
        })
    raise DGBlockedError({
        "decision": decision,
        "review_id": data.get("review_id"),
        "summary": verdict_obj.get("summary", "") if isinstance(verdict_obj, dict) else "",
    })
