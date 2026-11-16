# WebKit browser process diagnostic

The real WebKit Responsive failures in PR419 and PR422 delivered a crash callback for the current page. The diagnostic records do not identify a process exit, allocator fault or OOM. Other runs on the same marketing source passed; runner image revisions differ. The root-cause preflight is `release-evidence/open-pr-review/webkit-crash-preflight-20261116.md` in the controller evidence directory. No dependency or CSS cause is established.

## Decision and scope

First add only the documented Playwright browser-process logging channel to the existing failing CI step. This changes one diagnostic variable and may expose a concrete process error without adding a new harness, wrapper or timing perturbation. Dedicated lifecycle timestamps and kernel/cgroup telemetry remain possible followups only if this bounded capture does not explain the failure. A successful capture is a non-reproduction, not proof of a fixed crash.

Implementation owns only `.github/workflows/ci.yml`: add `DEBUG: "pw:browser"` to the `env` mapping of `Responsive sweep (WebKit)`. Preserve `SELAHCUE_SWEEP_REQUIRE`, step condition, exact command, browser/version/runner selection, route order, assertions, existing timeouts and the original exit status. Do not change application CSS, responsive harness or test code, add retries, broaden to `pw:api`/`pw:protocol`, or dump process environment. One short explanatory comment is allowed.

The existing step runs only fixed synthetic loopback pages in hosted CI and has no provider secret requirement. The channel logs browser launch/process stderr rather than protocol/DOM traffic. Root retains official bounded job logs; no new public download artifact or environment dump is introduced. Existing job limits bound execution; logging is not an excuse to weaken pass criteria.

Root will trigger one normal hosted candidate run, inspect the captured process output and original result, and decide the next experiment from that evidence. Preserve historical failures and all unexecuted cells. This diagnostic is not a product fix and has no invented behavioral RED. Static actionlint plus current hosted gates verify the wiring; tests which assert a YAML string add no useful coverage.

Local runtime remains held for paging. Static source/configuration reads, actionlint and Git checks only. One source implementer; preserve other work and sibling plans. Root owns refs, CI, archive, reviews and any merge. No secrets/provider calls or subagents.
