# Changelog

## 0.1.0 (2025-05-02)

Initial release.

### Added
- `DecisionGuardClient` — sync and async HTTP client (`audit`, `aaudit`, `auto_audit`, `aauto_audit`, `fact_check`, `afact_check`, `batch_audit`, `abatch_audit`, `list_reviews`, `alist_reviews`, `list_resources`, `alist_resources`, `get_identity`, `aget_identity`, `get_review`, `with_trace`)
- `DGBlockedError` / `DGEscalatedError` — typed exceptions for BLOCK and ESCALATE verdicts
- `enforce_verdict()` — raise typed exceptions for non-ALLOW verdicts
- `DGGuardedTool` + `guard_tools()` — LangChain `BaseTool` wrapper
- `DecisionGuardCrewAuditor` — CrewAI auditor with `audit_task()` and `guard_tool()` decorator
- `DecisionGuardAuditor` — Microsoft AutoGen auditor with `audit_function_call()` and `create_hook()`
- `DecisionGuardRail` — OpenAI Agents SDK guardrail with `before_tool_call()` and `wrap_tool()`
- `audit_step()` + `audit_or_fail()` — generic CI/workflow helpers
- `dg-audit` CLI entry point
- Zero hard dependencies — `httpx` and `requests` are optional extras
