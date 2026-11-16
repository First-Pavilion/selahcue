# Installer publisher source evidence

Task 4 starts at `b19b565f57617e43cd10a23bcbd20d69c05eefa4`. Its source head is the commit that introduces this file with `feat: connect installer publisher to release manifest`. The publisher source inventory digest at that checkpoint is `fed26a1e52451596a29c0b1dd22627b7edcaaaf45daf366ba526fb6f8d5ff02b`. The [accepted design](../../superpowers/plans/2026-11-15-installer-publication-design.md), [implementation plan](../../superpowers/plans/2026-11-15-installer-publication-plan.md), [evidence linkage](../../superpowers/plans/2026-11-15-installer-publication-evidence-linkage.md) and [upload deadline](../../superpowers/plans/2026-11-15-installer-publication-upload-deadline.md) describe the contract.

| Local source check | Result |
| --- | --- |
| `python3 -m unittest discover -s scripts -p 'test_installer_publication_cli.py' -v` before implementation | 9 expected failures for absent CLI, emitter and routing. Existing thin-Mac refusal passed. |
| `node --test implementation/marketing/tests/installerPublicationManifest.test.ts` before implementation | 7 expected failures for the absent validator. Direct parser assertions used the landed implementation. |
| `python3 scripts/publish_installers.py --self-test` | 52 passed with TCP loopback available for synthetic verifier fixtures. The default local sandbox denied the loopback bind. |
| `node --test implementation/marketing/tests/installerPublicationManifest.test.ts implementation/marketing/tests/publicDownloads.test.ts` | 63 passed, including the real website parser and the validator subprocess. |
| `npm --prefix implementation/marketing run type-check` and `npm --prefix implementation/marketing run lint` | Both passed using existing lockfile-identical dependencies copied locally. |
| Strict `tsc --noEmit` for the validator and integration test | Passed. |
| `node --test --test-concurrency=2 'tests/*.test.ts'` from the marketing package | All 1,336 tests passed using the normal marketing test glob. |
| `actionlint -color .github/workflows/ci.yml` | Passed. |
| `python3 .github/scripts/check_workflows.py --self-test` and `python3 .github/scripts/check_workflows.py` | Both passed. The ordinary check covered 7 workflows and 21 jobs. |
| `python3 .github/scripts/check_ci_minutes.py --self-test` and `python3 .github/scripts/check_ci_minutes.py` | Both passed. The ordinary check covered 7 workflows. |

Local versions were CPython 3.14.5, Node 22.23.4, npm 10.9.9, actionlint 1.7.12, and PyYAML 6.0.3. The self-test uses temporary Git source and evidence fixtures, a fake AWS executable and local fake/loopback verification transports. The emitter validates temporary candidate bytes using the website parser. The production manifest digest remained `00db423643ac10683b028d5b04a907f47ad57e950f27170daebdadc2a9233b7e`.

The manifest controls reject stale plan, verifier source and prepare receipt digests, reused uploader observations, missing or partial receipts, changed snapshots, invalid parser input, thin Mac evidence and differing existing output. Separate TypeScript controls reject a wrong host, duplicate target, inconsistent shared macOS metadata, unknown fields, duplicate JSON keys, malformed UTF-8 and oversized input. An identical existing candidate preserves its original file.

## Marketing CI routing

`test_publisher_only_paths_select_existing_marketing_checks` checks each route and the existing `changes.outputs.marketing` to `needs.changes.outputs.marketing` connection. It removes each new route in memory and checks that the corresponding source test fails. `test_marketing_runs_offline_publisher_after_runtime_setup` verifies the repository-root working directory, exact command and placement after Node/Python setup and `npm ci`. Removing the step or adding a skip or step environment fails the control.

| Representative publisher-only path | Marketing selection | Existing job's offline command |
| --- | --- | --- |
| `scripts/installer_publication/manifest.py` | `scripts/installer_publication/**` | `python3 scripts/publish_installers.py --self-test` |
| `scripts/publish_installers.py` | `scripts/publish_installers.py` | Same |
| `scripts/_installer_publication_fixtures.py` | `scripts/_installer_publication_fixtures.py` | Same |
| `scripts/test_installer_publication_cli.py` | `scripts/test_installer_publication_*.py` | Same |

The existing `make marketing-check` runs `npm test`, whose `tests/*.test.ts` glob picks up `installerPublicationManifest.test.ts`. These checks are local source evidence. Retain the hosted marketing self-test log and workflow-lint result from the actual source revision when the delivery workflow runs.

## Manual release handoff

1. Retain the exact final Windows x64, universal macOS and Ubuntu 24.04 x64 artifacts with accepted CI or reproducible local build provenance, final-package inspections, and native/provider acceptance. Run `prepare` with the reviewed release input and clean source checkout.
2. Run the authorized conditional `upload` for the private release directory, then invoke `verify-public` from a separate credential-free process against the exact public plan. Retain the independent invocation context and full-byte verification receipt alongside the upload receipt.
3. Use `emit-manifest` to produce a separate candidate. Review those bytes and the website update with the website owner, then retain the website commit and manifest digest for the owner's manual Coolify deployment.
4. After deployment, collect live browser and manifest evidence. Check the four links and both macOS target destinations, the same-origin manifest bytes and caching, and complete anonymous installer bytes and headers. Complete final native acceptance using the publicly downloaded packages.

Real acceptance, conditional upload, independent public verification, website review, deployment and final browser/native evidence remain pending at this source checkpoint.
