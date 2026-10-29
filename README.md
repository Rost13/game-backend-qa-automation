# Game Backend QA Automation

Python API and integration tests for deployed game backend services. The suite
combines API contract validation, cross-service workflow checks, read-only
database assertions, and Kubernetes-assisted diagnostics.

HTTP transport, service clients, response models, fixtures, test data, and
environment configuration are kept separate so the same suite can run locally,
in Docker, or in CI.

The repository contains no working credentials or fixed environment addresses.
Operators provide their own test environment through local variables or GitHub
Actions secrets and variables.

## Requirements

- Python 3.12+
- access to a non-production test environment
- dedicated ordinary and administrative test accounts where required
- optional read-only database and least-privilege Kubernetes access

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --requirement requirements.lock
Copy-Item .env.example .env
```

Fill `.env` with values for your environment. The file is ignored by Git.
Never put real values in `.env.example`.

Common settings:

```text
API_TESTS_ENABLED
API_BEARER_TOKEN
API_ADMIN_BEARER_TOKEN
DESTRUCTIVE_RBAC_TESTS_ENABLED
RBAC_DISPOSABLE_ACCOUNT_UUID
<SERVICE>_BASE_URL
<SERVICE>_API_PATH
```

Mutation, database, and Kubernetes features are disabled by default and have
independent opt-in variables. Use dedicated disposable users for state-changing
tests. Destructive authorization probes additionally require
`DESTRUCTIVE_RBAC_TESTS_ENABLED=true` and a separate
`RBAC_DISPOSABLE_ACCOUNT_UUID`; the configured ordinary and admin JWT subjects
are rejected as targets. See [test coverage](docs/test-coverage.md) for the
service matrix.

## Run

Offline unit tests:

```powershell
.\.venv\Scripts\python -m pytest -m "not live"
```

One API service:

```powershell
.\.venv\Scripts\python -m pytest tests/api/<service> --alluredir=allure-results
```

One integration area:

```powershell
.\.venv\Scripts\python -m pytest tests/integration/<service> --alluredir=allure-results
```

Live tests skip or fail with an explicit configuration classification when
required values are absent. Successful mutations remain opt-in because some
deployed APIs do not provide safe cleanup operations.

## Database and Kubernetes checks

Direct persistence assertions are optional. Supply database host, port, name,
schema, user, password, and TLS mode through environment variables. Tests set
read-only session controls where the database supports them.

For cluster-internal databases, configure the corresponding `*_KUBE_*`
variables. Resource names, namespaces, contexts, and container names are never
hardcoded. Use a dedicated least-privilege service account in CI and keep
personal kubeconfigs outside the repository.

Kubernetes diagnostics are read-only. Tests may inspect workload state, events,
rollouts, and scoped logs after preserving the original failure evidence; they
must not restart, patch, scale, delete, or exec into resources automatically.

## Quality and publication checks

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m mypy .
.\.venv\Scripts\python -m pytest -m "not live"
.\.venv\Scripts\python scripts\audit_publication.py
```

The publication audit scans files eligible for Git for known credential formats,
private keys, credentialed URLs, kubeconfig credentials, and private network
addresses. Absolute HTTP origins are rejected unless they are explicit local or
example placeholders. Findings report only a rule, file, and line; matched
values are never printed.

## Docker

```powershell
docker build --tag game-backend-qa-automation .
docker run --rm --env-file .env game-backend-qa-automation
```

Secrets are injected at runtime and are not copied into the image.

## CI and live schedules

The public workflow runs only the publication audit, static checks, and offline
tests. It does not receive environment credentials, call deployed services, or
upload live reports.

Run scheduled live suites from a private execution repository or private CI
project that checks out this public source revision. Keep credentials in that
private project's secret store. Hosts, identifier-like URL path segments,
credential-bearing query parameters, sensitive JSON fields, and non-JSON bodies
are still omitted or redacted from local Allure diagnostics.

## Security

Do not report credential exposure through a public issue. Follow
[SECURITY.md](SECURITY.md) and rotate any credential that may have been exposed,
even if it was later removed from Git.
