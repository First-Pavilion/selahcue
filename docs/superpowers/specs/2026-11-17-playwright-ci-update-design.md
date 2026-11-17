# Playwright 1.65.2 CI update design

Status: accepted engineering repair under the user's standing review, repair, re-review and merge authorization. The version choice is the controller's ruling, not a user-selected product change.

## Intent and evidence

Repeated original WebKit gates fail with page crashes on Python Playwright 1.61.0 / WebKit 2311. Main run 43979257903 failed Responsive and Home; PR424 run 43993404815 failed Secondary after Responsive/Home passed. PR233 run 43993505313 passed its browser gates. These results do not establish a shared native cause or an application defect.

Upstream [issue 42637](https://github.com/microsoft/playwright/issues/42637) reports a Linux WPE compositor crash affecting build2311 and points to [WebKit fix73621](https://github.com/WebKit/WebKit/pull/73621) and [Playwright roll42748](https://github.com/microsoft/playwright/pull/42748). Those sources justify evaluating a maintained browser; they do not match SelahCue's faults. [Python1.65.2](https://github.com/microsoft/playwright-python/releases/tag/v1.65.2) pins driver bbd948344ea9a60bf1e6f125c02ca99b2b51593b, whose [manifest](https://github.com/microsoft/playwright/blob/bbd948344ea9a60bf1e6f125c02ca99b2b51593b/packages/playwright-core/browsers.json) selects WebKit2388/27.2 and Chromium1255/159.0.8154.6 on Ubuntu26.04 x64. Python3.14 meets its Python>=3.10 requirement.

## Approaches and ruling

The controller selects a coherent update to current stable Python1.65.2. Keeping1.61.0 and collecting more data leaves the known old browser in use. Updating only to1.64 would include the cited fix but still needs the same original compatibility gates and retains an older supported browser. Updating the current stable pin is a reversible CI dependency change; its cost is possible browser-compatibility rework, including Chromium. It is not a declared crash fix and cannot waive any failing gate.

## Exact scope

Update all three literal workflow pins to `playwright==1.65.2`: two in `.github/workflows/ci.yml`, one in `.github/workflows/legal-drift.yml`. In `implementation/marketing/scripts/webkit_crash_journal.py`, set the exact WPE bundle root to `/home/runner/.cache/ms-playwright/webkit-2388/minibrowser-wpe` and the WebKit receipt producer/export validator to exact version1.65.2 and revision2388. Update independent active fixtures in `implementation/marketing/tests/test_webkit_crash_journal.py` together; explicitly reject previous revision2311 and previous receipt pair. Retain historical evidence and synthetic alias examples.

Official ZIP directory inspection of the Ubuntu26.04 archive confirms all four existing `bin/` executable names, canonical `lib/libWPEWebKit-2.0.so.1` symlink entry and versioned `.1.12.0` regular entry. The 4,086-byte directory has40 members; it is metadata evidence, not installed/launch proof. Independent builder check found no required code redesign. Evidence is retained in the release review workspace as `playwright-1.65.2-bundle-metadata.json`, `playwright-1.65.2-bundle-central-directory.bin` and `playwright-1.65.2-builder-check.md`.

Keep exact role/module allowlists, parser admission, output schema, finite bounds, rejection behavior, privacy controls and kernel-fault attribution unchanged except the deliberate exact bundle revision. The shared WPE allowlist consequently changes how hypothetical absolute WPE paths in GPU frames resolve; GPU-specific admission, identity, receipt schema and all bounds remain unchanged. Do not preserve stale2311 absolute paths by broadening the allowlist.

Keep every original application file and browser gate unchanged: Responsive41routes×5widths=205cells per engine and10s settle; Home one click,1200ms wait and95±2 assertion; Secondary original attempts/waits; Operator and legal checks; runner selections, job timeouts, commands, coverage and failure policy. Do not add a retry, platform override, capture, debugger, custom browser flag, core dump, or alternative CI run.

## Acceptance and limits

Use named real collector fixtures for RED before production edits, then GREEN and the full existing collector suite, legal workflow pin test and workflow/actionlint/minutes guards. No application imports, DB/services, native builds, browser install/launch or heavy local tests under the resource hold. Standalone fake fixtures only, one process group at a time with30s whole-command bound and explicit child cleanup. No silent timeout increase.

Require independent source/spec/quality review before one ordinary candidate push. The automatic normal and legal workflows must exercise their original complete gates. Verify actual install/launch evidence, source/merge tree, versions and collector configured/installed identity separately. A passing run proves those gates on that composition, not fault causation or zero recurrence. Keep previous failures and unexecuted checks as recorded. Review again on current target composition before authorized merge. Root owns CI, PR publication and merge; no deploy or installer claim.
