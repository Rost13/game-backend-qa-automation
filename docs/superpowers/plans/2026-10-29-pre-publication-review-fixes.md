# Pre-publication Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every confirmed pre-publication safety, correctness, diagnostic, CI, and metadata issue while preserving live coverage and keeping mutations disabled by default.

**Architecture:** Extend the existing environment-backed settings and fixtures with one explicit destructive-RBAC gate and disposable target. Add a small pure oracle module so live workflow assertions have independently testable expectations, and reuse the existing HTTP diagnostic sanitizer for server-controlled error text. Keep the public workflow offline and pin its OS/Python runtime.

**Tech Stack:** Python 3.12, pytest, Pydantic Settings, httpx, Ruff, MyPy, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-29-pre-publication-review-fixes-design.md`

## Global Constraints

- Do not run live or mutating tests without separate user authorization.
- Do not change backend behavior or documented API contracts.
- Do not add retries, dependencies, or hidden cleanup.
- Keep credentials and environment-specific values externalized.
- Do not create a Git commit because this public snapshot has no baseline commit and the user has not requested one.

## Review Focus

- A user JWT carrying an administrative role must stop destructive RBAC probes before any request.
- A disposable target matching either configured JWT subject must be rejected before any request.
- A purchase that reports a price different from the catalog must fail even when the balance matches the reported price.
- A Lottery replay that creates any unexpected opening ID must fail.
- An expired entitlement must extend from claim time while an active entitlement extends from its existing expiration.

---

### Task 1: Destructive RBAC safety gate

**Files:**
- Modify: `src/qa_automation/auth.py`
- Modify: `src/qa_automation/config.py`
- Modify: `fixtures/environment.py`
- Modify: `tests/unit/test_auth.py`
- Modify: `tests/unit/test_config.py`
- Modify: `tests/api/profile/test_profile_api.py`
- Modify: `tests/api/balance/test_balance_api.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Produces: `jwt_account_role(token: str) -> str` and `validate_disposable_account_target(target: UUID, user_token: str, admin_token: str | None) -> UUID`.
- Produces: settings `destructive_rbac_tests_enabled: bool` and `rbac_disposable_account_uuid: UUID | None`.
- Produces: fixture `destructive_rbac_target_uuid` that skips when disabled and fails with `TEST_DATA_DEFECT` for missing/unsafe configuration.

- [ ] **Step 1: Write failing auth and configuration tests**

Add tests proving role extraction accepts the existing `account_role` claim, rejects missing/unknown roles, rejects a disposable UUID equal to either token subject, and keeps both new settings disabled/unset by default.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/unit/test_auth.py tests/unit/test_config.py -q`

Expected: FAIL because the role/target helpers and settings do not exist.

- [ ] **Step 3: Implement the minimal helpers, settings, fixture, and test wiring**

Split Profile read-only admin probes from destructive probes. Make Profile destructive probes plus Balance replenish/backfill authorization probes depend on `destructive_rbac_target_uuid`; never use the ordinary JWT subject as their mutation target.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/unit/test_auth.py tests/unit/test_config.py -q`

Expected: PASS.

### Task 2: Independent business oracles

**Files:**
- Create: `src/qa_automation/oracles.py`
- Create: `tests/unit/test_oracles.py`
- Modify: `tests/integration/market_proxy/test_market_purchase_flow.py`
- Modify: `tests/integration/lottery/test_lottery_workflows.py`
- Modify: `tests/integration/daily_quests/test_daily_quest_rewards.py`

**Interfaces:**
- Produces: `market_purchase_debit_minor_units(catalog_price: Decimal, reported_price: Decimal, minor_units_per_unit: int) -> int`.
- Produces: `assert_only_expected_ids_added(before: set[UUID], after: set[UUID], expected: set[UUID]) -> None`.
- Produces: `reward_expiration_window(previous: datetime | None, observed_at: datetime, duration: timedelta, tolerance: timedelta) -> tuple[datetime, datetime]`.

- [ ] **Step 1: Write failing oracle tests**

Cover catalog/report mismatch, invalid currency precision, unexpected Lottery IDs, an expired entitlement, an active entitlement, and the boundary where expiration occurs during the request tolerance.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/unit/test_oracles.py -q`

Expected: FAIL because `qa_automation.oracles` does not exist.

- [ ] **Step 3: Implement minimal pure oracles and consume them from live tests**

Market final balance must derive from catalog price. Lottery must compare full history-ID deltas after the initial request, replay, and conflict. Daily reward polling must accept only values inside the computed expiration window.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/unit/test_oracles.py -q`

Expected: PASS.

### Task 3: Sanitized server-controlled failure text

**Files:**
- Modify: `src/qa_automation/clients/base.py`
- Modify: `tests/unit/test_http_diagnostics.py`
- Modify: `tests/integration/market_proxy/test_market_purchase_flow.py`

**Interfaces:**
- Produces: public `sanitize_diagnostic_text(value: str) -> str`, using the existing diagnostic replacement rules.

- [ ] **Step 1: Write a failing sanitizer regression test**

Test that a server error containing a URL, UUID, JWT, hostname, and secret-bearing term is redacted by the public helper.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/unit/test_http_diagnostics.py -q`

Expected: FAIL because the public helper does not exist.

- [ ] **Step 3: Expose the existing sanitizer and use it in Market failure messages**

Do not change attachment behavior. Ensure no raw `error_description`, `failure_reason`, or `last_error` is interpolated into assertion output.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python -m pytest tests/unit/test_http_diagnostics.py -q`

Expected: PASS.

### Task 4: Public metadata and deterministic CI runtime

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/quality.yml`

**Interfaces:**
- Public metadata describes API and integration automation.
- CI uses `ubuntu-24.04` and invokes `python3.12` explicitly.

- [ ] **Step 1: Update metadata and workflow with the smallest configuration-only change**

Replace remaining legacy API-layer wording and pin the runner/Python commands without adding third-party Actions.

- [ ] **Step 2: Verify configuration through static and publication checks**

Run: `python -m ruff check .`, `python -m mypy .`, and `python scripts/audit_publication.py`.

Expected: all commands exit 0.

### Task 5: Full offline verification

**Files:**
- Verify all modified files from Tasks 1-4.

**Interfaces:**
- No new interfaces.

- [ ] **Step 1: Run the complete offline suite**

Run: `python -m pytest -m "not live" --basetemp=.pytest_cache/pre-publication-fixes`

Expected: all selected tests pass and all live tests are deselected.

- [ ] **Step 2: Run all quality checks**

Run: `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy .`, and `python scripts/audit_publication.py`.

Expected: all commands exit 0 with no findings.

- [ ] **Step 3: Inspect the final diff and confirm scope**

Confirm no credentials, fixed environment addresses, generated reports, caches, or unrelated refactors were added. Do not run live tests.
