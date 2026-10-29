# Pre-publication Review Fixes Design

## Intent

Remove the confirmed correctness, safety, diagnostic, and publication-readiness issues without weakening the existing live coverage or changing backend behavior.

## Goals

- Keep negative authorization coverage while preventing accidental mutations of the shared test account.
- Make Market Proxy and Lottery assertions independent enough to detect the reported business defects.
- Handle expired Premium and Booster timestamps without false product-defect classifications.
- Route server-controlled diagnostic text through the existing sanitization rules.
- Make public CI explicitly require Python 3.12 and align package metadata with the README.
- Add offline regression tests for every new pure helper or safety rule.

## Non-goals

- Do not provision users through undocumented production APIs.
- Do not run live or mutating tests as part of this change.
- Do not change API contracts, backend behavior, retry policy, or database/Kubernetes permissions.
- Do not add dependencies or broadly refactor service clients.

## Selected approach

Use targeted changes within the current architecture. Dangerous ordinary-user RBAC probes require an explicit opt-in setting and a separately configured disposable account UUID; they never target the JWT subject by default. JWT claims are decoded only for configuration preflight and are not treated as signature validation.

Extract small pure assertion/expectation helpers where offline tests can prove the Market price oracle, Lottery history delta, expiration baseline, and diagnostic redaction. Existing live tests consume those helpers without duplicating transport or service logic.

The CI workflow continues avoiding live credentials. It checks that the runner is Python 3.12+ before creating the environment. Project descriptions and marker text use consistent API/integration terminology.

## Alternatives considered

- Full disposable-user provisioning was rejected because no stable account-provisioning contract is available.
- Removing dangerous RBAC probes was rejected because it would reduce authorization coverage.

## Safety and expected behavior

- Dangerous RBAC tests skip unless both the explicit gate and disposable target are configured.
- A configured disposable target equal to the ordinary or admin JWT subject fails as `TEST_DATA_DEFECT` before any request.
- Market purchases must report and debit the price advertised by the selected catalog product.
- Lottery replays and conflicts may add no opening IDs beyond the original request's IDs.
- Expiration rewards extend from the later of the previous expiration and the observed claim time, with a bounded tolerance for request processing.
- Failure output contains sanitized service text only.

## Verification

- Focused offline regression tests are run red, then green.
- `ruff check .`, `ruff format --check .`, `mypy .`, `pytest -m "not live"`, and the publication audit must pass.
- Live tests remain unexecuted until separately authorized.
