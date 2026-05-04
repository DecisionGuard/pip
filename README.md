# DecisionGuard Python SDK

Runtime governance for AI agents. Intercept tool calls before execution and get an ALLOW / BLOCK / CONDITIONAL / ESCALATE verdict from DecisionGuard.

[![PyPI version](https://badge.fury.io/py/decisionguard.svg)](https://pypi.org/project/decisionguard/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Install

```bash
pip install decisionguard                 # core only (bring your own http client)
pip install "decisionguard[httpx]"        # recommended — sync + async
pip install "decisionguard[langchain]"    # LangChain + httpx
pip install "decisionguard[all]"          # everything
```

## Quick start

```python
from decisionguard import DecisionGuardClient, DGBlockedError

client = DecisionGuardClient.from_env()
# Reads DG_API_KEY from environment; DG_BASE_URL is optional (default: https://decision-guard.com)

response = client.audit({
    "actor": {"id": "my-agent", "type": "agent", "authority": "supervised"},
    "intent": {
        "requested_goal": "Deploy updated service to production",
        "proposed_action": "helm upgrade my-service --set image.tag=v2.1.0",
    },
    "environment": "production",
    "tool": {
        "name": "helm",
        "operation": "upgrade",
        "resource_name": "my-service",
        "change_type": "infrastructure",
    },
})

print(response["verdict"])   # ALLOW | BLOCK | CONDITIONAL | ESCALATE
print(response["summary"])
```

## Adding facts to an audit

The `facts` field signals what kind of data is in play so DecisionGuard can apply the right sensitivity rules:

```python
response = client.audit({
    "actor": {"id": "my-agent", "type": "agent", "authority": "supervised"},
    "intent": {
        "requested_goal": "Export user records to CSV",
        "proposed_action": "db.export(table='users')",
    },
    "environment": "production",
    "tool": {"name": "db", "operation": "export"},
    "facts": {
        "has_sensitive_data": True,
        "data_classifications": ["PII", "financial"],
        "risk_signals": ["bulk_export", "cross_border_transfer"],
    },
})
```

## LangChain

Wrap any `BaseTool` so DecisionGuard is consulted before every call:

```python
from langchain_community.tools import ShellTool
from decisionguard import DGGuardedTool, guard_tools, DecisionGuardClient

client = DecisionGuardClient.from_env()
shell = ShellTool()

# Wrap a single tool
guarded_shell = DGGuardedTool(
    inner_tool=shell,
    dg_client=client,
    actor_id="my-langchain-agent",
    environment="production",
    data_classifications=["infrastructure"],
    risk_signals=["shell_execution"],
)

# Or wrap a whole list at once
guarded_tools = guard_tools(
    [shell, tool2, tool3],
    dg_client=client,
    actor_id="my-langchain-agent",
    environment="production",
)

# Drop them into your agent exactly like the originals
agent = initialize_agent(tools=guarded_tools, ...)
```

Async (`_arun`) is also supported — requires `httpx`.

## CrewAI

```python
from decisionguard import DecisionGuardCrewAuditor, DecisionGuardClient

client = DecisionGuardClient.from_env()
auditor = DecisionGuardCrewAuditor(client, actor_id="crewai-deployer")

# Guard an individual task before crew execution
auditor.audit_task(
    task_description="Merge feature branch to main",
    agent_role="deployer",
    tool_name="git",
    tool_args={"command": "merge feature/new-model"},
    data_classifications=["source_code"],
    risk_signals=["branch_merge"],
)

# Or wrap a plain function
@auditor.guard_tool(tool_name="run_tests", agent_role="qa")
def run_tests(suite: str) -> str:
    ...
```

## AutoGen

```python
from decisionguard import DecisionGuardAuditor, DecisionGuardClient

client = DecisionGuardClient.from_env()
auditor = DecisionGuardAuditor(client, actor_id="autogen-executor")

# Use as a function-call hook inside an AssistantAgent
hook = auditor.create_hook(goal="Execute database maintenance")

# Returns True (allowed) or False (blocked/escalated)
allowed = hook("drop_table", {"table": "sessions"}, sender_name="assistant")

# Or call directly with facts
auditor.audit_function_call(
    function_name="send_report",
    arguments={"to": "finance@co.com"},
    goal="Email quarterly report",
    data_classifications=["financial", "PII"],
    risk_signals=["external_email"],
)
```

## OpenAI Agents SDK

```python
from decisionguard import DecisionGuardRail, DecisionGuardClient

client = DecisionGuardClient.from_env()
rail = DecisionGuardRail(
    client,
    actor_id="openai-agent",
    on_block=lambda r: print("Blocked:", r["summary"]),
)

# Call before every tool execution
rail.before_tool_call(
    tool_name="send_email",
    tool_args={"to": "team@company.com", "body": "Deploying now"},
    agent_goal="notify team of deployment",
)
```

## Fact-checking

Verify content for misinformation, logical errors, unsupported claims, and more:

```python
from decisionguard import DecisionGuardClient

client = DecisionGuardClient.from_env()

result = client.fact_check(
    content="The EU AI Act was signed into law in 2023 and applies to all AI systems globally.",
    context="Legal compliance review",
    checks=["misinformation", "errors", "unsupported_claims"],
)

print(result["verdict"])      # PASS | FAIL | WARN | INCOMPLETE
print(result["dg_verdict"])   # ALLOW | BLOCK | REQUIRE_APPROVAL
print(result["summary"])
print(result["review_id"])    # persisted audit trail

for issue in result["issues"]:
    print(f"[{issue['severity'].upper()}] {issue['description']}")
    if issue.get("suggestion"):
        print(f"  → {issue['suggestion']}")
```

Available check types: `misinformation`, `inconsistencies`, `errors`, `incompleteness`, `unsupported_claims`, `logical_errors`, `missing_citations`.

**Async:**
```python
result = await client.afact_check(
    content="...",
    checks=["misinformation", "errors"],
)
```

## Auto-audit (observe-only)

Record every action without blocking. Good for telemetry, shadow mode, and gradual rollouts:

```python
client.auto_audit(
    tool_name="vector_search",
    action_summary="Semantic search over customer embeddings",
    parameters={"query": "refund policy", "top_k": 5},
    environment="production",
    resource="customer-vectors",
)

# Async
await client.aauto_audit(
    tool_name="vector_search",
    action_summary="Semantic search over customer embeddings",
    environment="production",
)
```

## List reviews

Retrieve the audit trail for your tenant:

```python
reviews = client.list_reviews(
    limit=20,
    decision="BLOCK",
    environment="production",
    change_type="infrastructure",
)

for r in reviews:
    print(r["id"], r["verdict"], r["summary"])

# Async
reviews = await client.alist_reviews(decision="ESCALATE")
```

## Batch audit

Submit up to 50 audits in a single round-trip:

```python
result = client.batch_audit([
    {
        "actor": {"id": "agent-1", "type": "agent", "authority": "supervised"},
        "intent": {"requested_goal": "Read logs", "proposed_action": "tail /var/log/app.log"},
        "environment": "production",
        "tool": {"name": "bash", "operation": "read"},
    },
    {
        "actor": {"id": "agent-2", "type": "agent", "authority": "autonomous"},
        "intent": {"requested_goal": "Send alert", "proposed_action": "slack.post(...)"},
        "environment": "production",
        "tool": {"name": "slack", "operation": "post"},
    },
])

for item in result["results"]:
    print(item["index"], item["verdict"])

# Async
result = await client.abatch_audit(reviews)
```

## Resources

List active resources registered to the tenant:

```python
resources = client.list_resources(resource_type="database")
for r in resources["resources"]:
    print(r["name"], r["resource_type"])

# Async
resources = await client.alist_resources(tag="prod")
```

## Identity snapshot

Retrieve the identity context that was recorded at audit time:

```python
identity = client.get_identity(review_id)
print(identity["actor_id"], identity["authority"])

# Async
identity = await client.aget_identity(review_id)
```

## Direct review submission

Submit a change for governance review using the full reviews API contract:

```python
from decisionguard import DecisionGuardClient

client = DecisionGuardClient.from_env()

result = client.review(
    change_type="iac_terraform",
    environment="production",
    change_payload={
        "resources": [
            {"type": "aws_s3_bucket", "action": "create", "name": "audit-logs-prod"}
        ]
    },
    intent={"goal": "Create audit log bucket", "proposed_action": "terraform apply"},
    actor_source="ci-pipeline",
    resource_name="audit-logs-prod",
)

print(result["data"]["review_id"])
print(result["data"]["verdict"]["decision"])  # ALLOW | ALLOW_WITH_CONDITIONS | REQUIRE_APPROVAL | BLOCK

# Async variant
result = await client.areview(
    change_type="iac_terraform",
    environment="production",
    change_payload={...},
)
```

## Enforce a review verdict

Raise a typed exception if the verdict is not `ALLOW` or `ALLOW_WITH_CONDITIONS`:

```python
from decisionguard import DecisionGuardClient, enforce_review_verdict, DGBlockedError, DGEscalatedError

client = DecisionGuardClient.from_env()
result = client.review(change_type="code_application", environment="production", change_payload={...})

try:
    enforce_review_verdict(result)
    # Only reaches here on ALLOW or ALLOW_WITH_CONDITIONS
    run_deployment()
except DGBlockedError as e:
    print("Blocked:", e.response["data"]["verdict"]["decision"])
except DGEscalatedError as e:
    print("Requires approval:", e.response["data"]["verdict"]["decision"])
```

## guard_and_execute

Review a change and, if approved, immediately execute a callable. On `BLOCK` or `REQUIRE_APPROVAL` the callable is never invoked:

```python
from decisionguard import DecisionGuardClient, guard_and_execute

client = DecisionGuardClient.from_env()

def run_migration():
    return apply_database_migration()

result, tool_result = guard_and_execute(
    client=client,
    change_type="data_migration",
    environment="production",
    change_payload={"migration": "add_user_index", "table": "users"},
    intent={"goal": "Add index for performance", "proposed_action": "ALTER TABLE users ADD INDEX"},
    fn=run_migration,
)

print(result["data"]["verdict"]["decision"])  # ALLOW
print(tool_result)                            # return value of run_migration()

# Async variant
result, tool_result = await aguard_and_execute(
    client=client,
    change_type="data_migration",
    environment="production",
    change_payload={...},
    fn=async_run_migration,
)
```

## Fetch a stored review

Poll for an approval decision after `ESCALATE` or `REQUIRE_APPROVAL`:

```python
review = client.get_review(result["review_id"])
print(review["verdict"])
```

## Tracing multi-step workflows

Tie a chain of related audits together with a shared trace ID:

```python
traced = client.with_trace("trace-abc-123")

# All audits made with `traced` share the same trace_id
traced.audit({...})
traced.audit({...})
```

## CI / workflow pipelines

```bash
# One-liner for shell scripts, GitHub Actions, n8n, etc.
dg-audit "Deploy to production" "helm upgrade api" helm upgrade ci-pipeline
```

```python
from decisionguard import audit_or_fail, DecisionGuardClient

client = DecisionGuardClient.from_env()
audit_or_fail(
    client,
    actor_id="ci-pipeline",
    goal="Deploy to production",
    action="helm upgrade api --set image.tag=v3",
    tool_name="helm",
    operation="upgrade",
    environment="production",
)
# Raises RuntimeError on non-ALLOW verdict
```

## Error handling

```python
from decisionguard import DecisionGuardClient, DGBlockedError, DGEscalatedError

client = DecisionGuardClient.from_env()

try:
    client.audit(request)
except DGBlockedError as e:
    print("Blocked:", e.response["summary"])
except DGEscalatedError as e:
    print("Needs human approval:", e.response["summary"])
    # Pause and wait for review at e.response["links"]["review_url"]
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DG_API_KEY` | Yes | Your tenant API key |
| `DG_BASE_URL` | No | API base URL (default: `https://decision-guard.com`) |

## Links

- [DecisionGuard dashboard](https://decision-guard.com/app)
- [API documentation](https://decision-guard.com/docs)
- [GitHub repository](https://github.com/DecisionGuard/pip)
