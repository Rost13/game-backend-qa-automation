# Test Coverage

The suite is risk-based. Each domain uses typed clients and response models,
explicit authentication checks, boundary validation, and opt-in mutations.

| Domain | Default coverage | Optional integration or mutation |
| --- | --- | --- |
| Promocodes | Authentication, validation, contracts | Lifecycle, balance reward, database persistence |
| Balance | Read models, authorization, validation | Replenishment, destructive RBAC probes, and database persistence |
| Market Proxy | Catalog, lookup, validation | Purchase and idempotency |
| Social | Lists, recommendations, authorization | Presence and peer relationship lifecycle |
| Daily Quests | Configuration, status, claim eligibility | Reward delivery across dependent services |
| Battle Pass | Season, progress, rewards, authorization | XP grant and idempotency |
| Boosters | Active state, role boundaries | Goods delivery and expiry extension |
| Inventory | Lists, filters, pagination, authorization | Goods delivery and quantity change |
| Premium | Catalog and profile invariants | Subscription delivery and expiry change |
| Profile | Profile, referrals, settings, localization | Reversible locale update and destructive RBAC probes |
| Lottery | Season, chests, history, admin validation | Opening, keys, and draft configuration lifecycle |
| Ads | Availability, limits, callbacks, admin validation | Placement, configuration, and reward idempotency |
| Stat API | Counters, history, leaderboards, validation | Event ingestion and read-only persistence |

## Test layers

- `tests/unit`: offline infrastructure and model behavior.
- `tests/api`: deployed HTTP contracts and business behavior.
- `tests/integration`: cross-service and persistence checks.
- `fixtures`: configuration gates and controlled test data provisioning.

Live mutation tests use unique identifiers and are marked `serial` when they
share a dedicated account. Tests do not depend on execution order. Irreversible
flows remain disabled unless an operator explicitly enables the corresponding
environment variable. Destructive RBAC probes additionally require
`DESTRUCTIVE_RBAC_TESTS_ENABLED=true` and a separately configured
`RBAC_DISPOSABLE_ACCOUNT_UUID` that differs from both JWT subjects.

Database assertions complement API assertions only where persistence adds
meaningful confidence. Queries are parameterized and sessions are read-only
unless a test-owned setup operation is explicitly required.
