# Changelog

## 0.3.0 (2025-05-02)

### Added
- `review()` / `areview()` — direct reviews API client using the canonical contract (`change_type`, `change_payload`, `intent`, `actor_source`, `resource_name`); returns raw `result.data` envelope
- `enforce_review_verdict()` — raise `DGBlockedError` or `DGEscalatedError` from a `review()` response based on `result.data.verdict.decision`
- `guard_and_execute()` / `aguard_and_execute()` — submit a review and, on `ALLOW` / `ALLOW_WITH_CONDITIONS`, automatically invoke a callable; returns `(review_result, fn_result)` tuple
- `DecisionGuardClient.from_env()` — `DG_BASE_URL` is now **optional** (defaults to `https://decision-guard.com`)
- All new symbols exported from the top-level `decisionguard` package

### Fixed
- Default base URL corrected to `https://decision-guard.com` (no `/api` suffix)

---

## 0.2.0 (2025-05-02)

### Added
- `fact_check()` / `afact_check()` — content fact-checking with per-issue severity, descriptions, and suggestions
- `auto_audit()` / `aauto_audit()` — observe-only audit recording (no blocking)
- `batch_audit()` / `abatch_audit()` — submit up to 50 audits in a single round-trip
- `list_resources()` / `alist_resources()` — list resources registered to the tenant
- `get_identity()` / `aget_identity()` — retrieve actor identity snapshot for a review
- `get_review()` / `with_trace()` — poll reviews and scope a traced client
- `audit_step()` + `audit_or_fail()` — generic CI/workflow helpers
- `dg-audit` CLI entry point
- Subpath extras: `decisionguard[langchain]`, `decisionguard[all]`

---

## 0.1.0 (2025-05-02)

Initial release.

### Added
- `DecisionGuardClient` — sync and async HTTP client (`audit`, `aaudit`, `list_reviews`, `alist_reviews`)
- `DGBlockedError` / `DGEscalatedError` — typed exceptions for BLOCK and ESCALATE verdicts
- `enforce_verdict()` — raise typed exceptions for non-ALLOW verdicts
- `DGGuardedTool` + `guard_tools()` — LangChain `BaseTool` wrapper
- `DecisionGuardCrewAuditor` — CrewAI auditor with `audit_task()` and `guard_tool()` decorator
- `DecisionGuardAuditor` — Microsoft AutoGen auditor with `audit_function_call()` and `create_hook()`
- `DecisionGuardRail` — OpenAI Agents SDK guardrail with `before_tool_call()` and `wrap_tool()`
- Zero hard dependencies — `httpx` and `requests` are optional extras
