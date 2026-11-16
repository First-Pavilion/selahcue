# Plan catalogue data — verification and recovery (17tnw2az0gd)

Approved Aria contract1400430000278606; baseline main `b3ae75f824fe8e43b18836d3d661dc996dce98bc`.
Owned branch `codex/17tnw2az0gd-plan-catalogue`; Goal maximum4. No prices, currency or commercial interval
are seeded. Final Core/Pro device/output decisions and actual prices remain launch configuration, not build blockers.

## Migration and recovery contract

1. Stop catalogue/licence writes and take a complete pre-migration database backup. This is a pre-launch reseed;
   old paid-plan names do not establish commercial equivalence with new tiers.
2.0006 adds nullable rank and append-only effective price schema.0007 performs the reference/data changes atomically;
  0008 enforces non-null positive unique ranks. Data and constraint DDL are separate migrations to avoid PostgreSQL
   pending-trigger-event failures. The original0002 seed is unchanged.
3. Known oldLEGACY/PRO/PLATINUM scope aliases and explicit assignments are repointed to Free, in bounded500-row batches.
   Existing Free references stay where they are. Each changed reference has a migration-owned audit; assignment actor,
   reason and old request metadata are retained in the private audit before-values. Assignment accountability is updated
   to the migration identity. No AppLicenseKey field, including device_limit, is rewritten.
4. Unexpected custom plan shapes, preexisting weekly keys, incompatible required dimensions, unpublished/inactive output
   dimensions or existing price history fail clearly before reseeding. The transaction rolls back all reference changes.
   Unhandled protected references prevent obsolete plan deletion rather than being silently removed.
5. Recovery is **restore the complete pre-migration backup with matching previous code**, not reverse constants.
   A constant reverse cannot recover custom aliases/assignments or grants.0007 deliberately refuses reverse migration;
  0006 also refuses to drop price history if any version exists. Do not delete history or migration records to force a downgrade.
   Reverting only fallback code against the new Free fallback would reintroduce the wrong refusal.

Actual isolated SQLite probes verified successful forward/revision bump, preserved key-field dictionaries, exactly six
reference audits for the obsolete reference fixtures, unpriced three-plan output, unsafe custom/price/dimension atomic
refusal, refusal of destructive reverse, preservation of a price version and actual restoration of the original backup
with original references. These probes use separate temporary databases, never pytest's shared database or a deployment.
Fresh PostgreSQL16 migration/schema installation also passed through the full price test setup.

## Price data and boundaries

`PlanPrice` stores plan, ISO currency, interval, nullable bounded whole minor-unit amount, aware effective timestamp,
actor and reason. No row and a nullable version both mean unpriced; zero is priced zero. The internal audited service
accepts only explicit non-backdated timestamps and dedicated MANAGE_PLAN_PRICING capability. No role/default grant,
staff/public endpoint, billing or usage enforcement is added.

Rows append; ordinary save/update/delete/bulk history mutation paths are refused. Plans with price history are protected
from deletion. The latest effective timestamp not after the query time wins. A prior version's end is its successor's start,
never an update to the old row. History reads have a bounded100 default/1000 maximum and compute ends in one window query;
the query-count test observes one query, including reading each returned effective end.

The service locks the plan, creates a version and success audit in one transaction; identical timestamp collisions
return CONFLICT. Actual PostgreSQL16 two-writer test observed exactly one version, one success audit and one conflict.
Permission/actor/reason/amount/currency/interval/time failures create no price or success audit; simulated audit failure
rolls the version back. Direct database checks also reject invalid amount/interval/currency/accountability writes.

SIX official current ISO4217 list (published2026-09-17) and historical list (2026-01-01) are pinned in
`currency_reference.py` with source URLs and SHA256 digests. Current numeric exponents include JPY0/USD2/KWD3;
non-numeric exponents and inactive-only codes cannot configure new prices. Historical codes/raw stored amounts remain
readable. The historic source does not supply exponents, so unknown is represented explicitly, never guessed as cents.
Future reference maintenance must retain previously pinned exponents when a currency is withdrawn. No runtime fetch occurs.

## Grants and signed payload

Exactly Free/Core/Pro ranks1/2/3 (display ordering separate), Free lowest sole fallback. All have explicit private
1-device grants,2 screens and0 NDI; Core/Pro affected rows carry accountable `PENDING D7(a)` reasons.
Active weekly transcript minutes20/50/80 and weekly notes1/5/10 use new keys with restrictive0 defaults;
the old monthly key is inactive and never reinterpreted. Watermark is on/off/off. The private device dimension is active
but unpublished; existing keys' own device_limit remains the sole signed/enforced instances_limit.

Both obsolete fallback refusals were removed with the migration; explicit-plan, unknown-plan and finite-seat gates remain.
Tests issue/assign all three plans, deny absent/0/unlimited/overflow seats without partial keys/audit success, and verify
an actual freshly signed Core manifest changes notes5→6 after set_plan_grant without restart. A configured test price
never enters the payload; neither private device grant nor price/actor/reason is added to signed grants.

The tier-name sweep exempts only explicit old/new seed files and retains positive controls for both. A source clone
with a real `plan.code == "CORE"` runtime branch is rejected by the actual sweep; the unmutated clone passes first.
Old fixtures now name current plans and amounts, while precedence tests assert plan identity/distinct weekly values so
equal temporary output caps cannot make them vacuous. Bounded and stale-cache controls remain intact.

## Completed checks / pending integration

- First seed RED: legacy four-plan table differs from approved three; subsequent seed GREEN.
- Focused catalogue regression169 passed; price/migration/mutation slice37 passed with one explicit PostgreSQL-only skip.
- Actual task-owned PostgreSQL16 final run:36 price/constraint/history/concurrency tests passed, no skips; isolated container removed.
  Additional real RED caught two NUL currency/interval lookups raising PostgreSQL DataError before scalar validation.
  The service now reuses model scalar validation before any lookup; all36 cases pass with the fix.
- Expanded real migration/recovery probes:4 passed, including unexpected output activation and schema-history rollback guard.
- Initial full API gate:2365 passed/54 explicit service skips/57 subtests, one stalePlatinum fixture failure; corrected that
  positive and NUL-prefixed fixture to currentCore and reran the full gate.
- Final complete install-free gate: Django check/migration consistency exit0;2369 passed,54 explicit live-service skips,
 57 subtests passed in226.84s, exit0. Final focused price/migration/source-mutation run40 passed/one explicit PG skip;
 seed/manifest/cache fixture run126 passed; control-character suite36 passed.
- Source diff check and Goal structural validator exit0.0002, pyproject and uv.lock unchanged. All local subprocesses exited;
  no task-owned test container remains. Actual hosted service-backed CI and independent review are pending, not called passing.
- Parent owns four independent reviews, actual hosted Postgres16/Redis7 CI, fresh main integration/merge and QA transition.
  No deployment/provider admission, billing, collection, installer action or credential search was performed.
