# Iteration3 — native uv Dependabot compatibility correction

Same ClickUp17tnw2az0kw; fresh managed branch `codex/17tnw2az0kw-uv-bot-compat` from merged PR351
main `b3ae75f824fe8e43b18836d3d661dc996dce98bc`. Root returned the ticket to In Progress and read back its
start/evidence comment before code changes. Original Goal maximum4 retained; iterations1–2 are not reset.

## Actual failure and least-scope correction

Actual native updater run41759977866 failed for setuptools/strawberry-graphql-django with
`tool_version_not_supported`, detected project requirement `==0.13.4`, running/supported tool0.13.5.
Its exact updater image source commit `2499eccfd55a9f76db236e919b6e7e7b6c5c3d22`:

- `uv/Dockerfile` copies the official uv0.13.5 binary.
- `uv/lib/dependabot/uv/file_updater/lock_file_updater.rb` uses the preinstalled tool after configuring Python;
  it does not download our `.uv-version`. It runs `uv lock --upgrade-package TARGET`.
- `lock_file_error_handler.rb` maps uv's own required-version mismatch into `ToolVersionNotSupported`;
  its own spec covers that mapping. This is actual native tool behavior, not an inferred config parser limitation.

The project's required-version is now `>=0.13.4,<0.14`. Deliberate bootstrap stays exactly0.13.4 in
`.uv-version`, unchanged helper enforcement, CI input and unchanged Docker image digest. No package/direct pin,
lock bytes, runtime profile, hash/build/stamp/ownership gate or Python contract changed.

Official uv0.13.4 versioning policy says patch releases are nonbreaking, breaking changes bump minor, and lock
schema changes only in minor releases. This bounded compatibility contract allows the bot's managed patch
without requiring it to install a repository-chosen tool or allowing0.14. It is distinct from an installation pin.
The existing14-day ordinary dependency cooldown is unchanged in project and Dependabot config.

## Actual verification

- Official0.13.5 macOS arm64 archive digest verified:
  `743f85035a1996ecb350659e01cd9faea9709829be09b1b4b03c73eaf3c9cd73`.
- RED: actual0.13.5 `uv lock --check --offline` on the original exact requirement exits2 with the same version mismatch.
- GREEN: actual0.13.4 and0.13.5 both `lock --check --offline` exit0 on the changed compatibility requirement;
  committed `uv.lock` remains byte-identical SHA256 `839c550f9ffa41fbd2b373161a82ad862ab11ef71444c60405dd70a27dfe0dad`.
- Actual0.13.4 fresh deliberate `make api-install` exits0; selected dev/build dependencies and source install unchanged.
- Real local-install wrongpatch regression refuses a0.13.5-reporting uv before creating an environment; its mutation
  removes the exact local version check and must fail. Compatible project tooling does not broaden bootstrap acceptance.
- PEP440 compatibility boundaries accept0.13.4/0.13.5/0.13.99 and reject0.13.3/0.12.99/0.14/1.0;
  the same test checks the exact bootstrap consumers and14-day cutoff.
- Isolated native-command exercises with actual0.13.5: setuptools84.1→84.2.1 and
  strawberry-graphql-django0.92→0.93 each resolve successfully and change exactly one package version.
  Those scratch updates are not committed. The full `[project]`, build-system and build group declarations remain identical to main.
- Actual cooldown negative: isolated ordinary dependency probe `uv==0.13.5` is refused exit1;
  uv reports its2026-10-22 upload was filtered by the2026-10-21 cutoff. Thus accepting the bot's managed0.13.5 tool
  does not waive the application's14-day package policy.
- API system and migration checks exit0; five graph/build/compatibility tests exit0; final full baseline52/52 cases
  and58/58 mutations pass (exit0); actionlint/diff check/Goal structural validator exit0. System launcher3.9 used
  for retained guard proof. Full application behavior is unchanged; hosted service-backed regression remains required.
- All verifier processes completed before review handoff; no pending background local verification.

## Postmerge evidence and separate security follow-up

Root recorded PR351 all-four-review passes and actual hosted2382 passed/1 intentional skip/57 subtests;
cache miss then saved. Native GraphUpdate41759977317 indexed all37 locked versions before the custom snapshot job.
The initial published support matrix omission did not justify an absolute unsupported claim; README/exporter docs correct it.
The custom job remains an additional explicit ingestion/provenance path, with unchanged main-only least privilege.

Dependabot alert14 (`uv.lock`) duplicates existing alert12 (`pyproject.toml`) for the same pinned runtime
`graphql-core==3.3.0` and **GHSA-mpqx-q82w-9x46**, HIGH: memory-leak denial of service in aborted validations.
Affected>=3.3.0a3,<3.3.1; first fixed3.3.1. The pin predates uv and is unchanged. This migration exposed another
manifest record for the existing vulnerability; it did not newly upgrade to the affected version. This is not a dismissal of the risk.
Existing PR277 source `c530619e71d4e25d9ffe829c2772c74b50263f71` predates uv and changes only the old pip manifest;
root owns deduplication/targeted follow-up with correct lock regeneration. No security package upgrade is bundled here.

Actual successful postmerge native Dependabot readback on the follow-up is still mandatory; local command simulation
is not that receipt. Root alone coordinates four current-head reviews, CI, merge and actual updater/graph readback before QA.
No deployment, provider write, credential discovery or connector call performed.

## Primary provenance

- https://github.com/dependabot/dependabot-core/tree/2499eccfd55a9f76db236e919b6e7e7b6c5c3d22/uv
- https://github.com/astral-sh/uv/blob/0.13.4/docs/reference/policies/versioning.md
- https://github.com/astral-sh/uv/releases/tag/0.13.5
- https://github.com/First-Pavilion/selahcue/actions/runs/41759977866
- https://github.com/First-Pavilion/selahcue/security/dependabot/14
- https://github.com/First-Pavilion/selahcue/security/dependabot/12
