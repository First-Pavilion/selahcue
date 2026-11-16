# 17tnw2bcakr — reconnect snapshot boundary

Base: `13bb3c255dd83ef9917a344964ce55725ec91db2`. Test-only correction; production, dependency manifests and lockfiles unchanged.

## Diagnosis and RED

PR356's Flutter job126354512243 reported 514 passing tests and one premature banner assertion failure. Successful authentication intentionally ends `reconnecting` before `Timer.run(refresh)` installs the replacement snapshot. `syncing` and the outage notice remain until that state arrives.

Holding the replacement session's snapshot with a Completer while retaining the old assertion reproduces the same failure deterministically:

```text
Expected: null
  Actual: 'Connection lost — reconnecting…'
...live_controller_reconnect_malformed_test.dart 143:3 _recoversAfter
00:02 +0 -1: Some tests failed.
```

The test now proves both FormatException and TypeError recovery phases: after reconnect, syncing is true, the outage notice remains, and a command fails without reaching the replacement session; after completing the snapshot, syncing ends, the notice clears and one command is applied. Teardown releases the gate on failed assertions after disposing the controller. Existing retry/revocation/disposal cases remain.

## Local verification

Configured installed SDK: Flutter3.47.4 stable (9584c6713b), Dart3.13.3. CI uses unpinned stable on Linux; actual hosted verification is still required. No device/build validation is applicable to this test-only patch.

- `flutter pub get --enforce-lockfile`: successful. Flutter rewrote its SDK lower bound in this isolated worktree's lockfile; that incidental rewrite was discarded before testing with `--no-pub`. Primary worktree lock untouched.
- Malformed-reply test file: 7/7 pass.
- Combined malformed, sync, retired-read, stalled-command, reconnect-policy and reconnect-backoff files: 31/31 pass.
- `flutter analyze --no-pub`: no issues.
- `flutter test --no-pub`: 515/515 pass.
- Both controlled malformed-reply scenarios repeated three times: 2/2 pass per run.
- Current `dart format --output=none --set-exit-if-changed` on changed test: 0 changes. Current formatter normalizes the file's preexisting layout.
- `git diff --check`: clean.

Raw local logs: `/private/tmp/17tnw2bcakr-{red,focused,regression,analyze,full,repeat-1,repeat-2,repeat-3}.log`.

## Handoff

GATE_REVIEW: root owns exact-head Cody, Shadow, Quinn and Vera reviews, actual hosted CI, merge to main and QA transition. None is claimed complete by these local checks.
