# API uv migration verification — 17tnw2az0kw

Baseline: main `c0325d52e809847fac141a605b74a7e6d7de7021`. Agent branch `codex/17tnw2az0kw-api-uv`.
Local date2026-11-04; Python3.14.5, system helper/test harness also executed with Python3.9.
No API business/schema code, package direct pins or minimum Python requirement changed.

## Reproducibility and tool provenance

- uv0.13.4 released2026-10-20, outside14-day ordinary-release cooldown. Official macOS arm64 release archive
  SHA256 `e0b1d4743ce64c55d9f0f4a444afa6b81125680070ee04e853fcd0f6c1ebf8f1` verified before use.
- Official setup-uv v7 commit `94527f2e458b27549849d47d273a16bec83a01e9`, exact version input0.13.4.
- Official uv multi-platform container index digest `sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b`,
  metadata revision `7456b60bc6bc348e13e06e3691bf08e78d3aef54`.
- Universal lock38 entries: editable root plus37 concrete registry versions (including platform-conditional colorama).
- Actual macOS and Linux-arm64 Docker distributions: **37 each, exact name/version maps identical**;
  includes root and locked setuptools; platform-inapplicable colorama omitted on both. Base-image pip seed excluded from
  Docker comparison (local venv deliberately created without pip).
- Baseline project's runtime pins, dev pins, build-system pins and `requires-python >=3.12` compared structurally: identical.
- First install uses `uv sync --locked --extra dev --group build --no-install-project --no-build`.
  Final root builds offline/non-isolated/no-cache, using the installed hash-locked backend without isolated build fetches.
  Unsupported platforms lacking a wheel fail; no source-build exception introduced.

## Completed local verification (all processes exited)

| Verifier | Result / exit |
| --- | --- |
| RED lock-only freshness regression against original pip helper | expected failure exit1: checks accepted changed lock |
| Final locked deliberate local install, then install-free verify | exit0; interpreter3.14.5, current content stamp |
| `uv lock --check --offline` | exit0;38 packages, no lock write |
| Guard mutation proof | exit0; baseline51/51 cases green;57/57 mutations caught |
| Actual remote-artifact integrity negative | exit0; local HTTP index supplies pre-recorded SHA256; valid wheel payload changed after lock, empty cache: hash mismatch rejected, no stamp |
| `make api-check` | exit0; Django check/migration check pass;2330 passed,53 explicit service skips,57 subtests;409.31s |
| Snapshot correctness/ambiguity/missing-edge tests | exit0;4 tests |
| `actionlint .github/workflows/ci.yml` | exit0 |
| `git diff --check` | exit0 |
| Final Docker build | exit0; wheel-only dependency layer and no-cache offline final project install |
| Docker outside-cwd imports with `--network none --workdir /tmp` | exit0; API resolves `/usr/src/app/selahcue_api/__init__.py`; Celery find_app returns selahcue_api |
| Compose-equivalent curl health command with `--network none` | exit0; HTTP404 from root after6s confirms live WSGI response |
| Isolated targeted update | exit0; `uv lock --upgrade-package redis==6.3.0` changed ONLYredis6.4→6.3; restored original lock byte-identically; no package update committed |

Local suite skips are intentional: live Postgres/Redis concurrency/cache controls are exercised by the hosted API job
(Postgres16/Redis7). A three-second health probe initially raced Django startup; bounded polling observed readiness at6s.
A retained failed-rebuild test caught uv reuse of cached editable metadata; final offline build disables that cache.
A snapshot test caught missing selected-extra edges; exporter now includes celery/kombu redis and psycopg binary edges.

## Fresh legacy pip comparison: intentionally recorded drift

A separate fresh Python3.14 pip editable/dev install preserves the same direct pins but resolves newer transitives
than the enforced14-day uv policy. This is **not full pip/uv transitive-version parity**; no previous transitive lock existed.
The lock deliberately avoids those brand-new releases rather than folding unrelated upgrades into this migration.
All application imports/checks/full local regression tests run against the locked profile; Linux image matches that profile exactly.

| Package | fresh unlocked pip | committed uv policy |
| --- | --- | --- |
| amqp |5.4.2|5.4.1|
| asgiref |3.13.0|3.12.1|
| billiard |4.3.2|4.3.1|
| kombu |5.7.0|5.6.2|
| pycparser |3.12|3.11|
| python-dateutil |4.0.0|2.9.0.post0|
| redis |8.1.0|6.4.0|
| sqlparse |0.6.1|0.6.0|
| tzdata |2026.6|2026.5|
| tzlocal |5.4.5|5.4.4|
| wcwidth |0.9.4|0.9.3|
| six |absent|1.17.0 (dateutil2.9 transitive)|

## Remaining integration gates

Parent owns independent Cody/Shadow/Quinn/Vera review, remediation, current PR CI, fresh main integration/merge and QA status.
No deployment or packaging dispatch performed. No existing user environment/secret or primary checkout file changed.
GitHub static graph support does not currently list uv.lock; supported native Dependabot uv update support is separate.
A dedicated main-push/API-changes-only job (contents:write only there) submits the complete exact-version snapshot using built-in
GITHUB_TOKEN and retains its payload. Actual main indexing has not been claimed: follow README postmerge instructions, compare all
locked API PyPI name/version entries including platform conditionals, and record actual submission/run/merged-SHA plus SBOM readback
before QA. PR checks do not submit graph payloads and retain read-only permissions.

## Primary references

- https://github.com/astral-sh/uv/releases/tag/0.13.4
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.astral.sh/uv/guides/integration/docker/
- https://docs.astral.sh/uv/guides/integration/dependency-bots/#dependabot
- https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems
- https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/use-dependency-submission-api
