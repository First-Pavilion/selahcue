#!/usr/bin/env python3
"""Committed BEHAVIOURAL test for the SelahCue operator webview (audit follow-up #9).

Injects a window.__TAURI__ stub + a driver into a copy of the real dist/index.html,
runs it under headless Chrome (real layout/CSS/canvas), and parses the driver's
PASS/FAIL results. This is the CI-gated behavioural counterpart to the static
content pins in `test_tokens.rs` / `test_keymap.rs`: it exercises the actual JS
(console render, plan-dedup, transcript cap, Theme-Designer wiring), so a
behavioural regression fails CI rather than only a dev-time check.

Runs on macOS (dev) and Linux CI. Chrome is resolved via CHROME_BIN, then PATH
(google-chrome/chromium), then the macOS app bundle. If Chrome is absent this
exits 0 with a LOUD SKIP notice so `make ci` on a Chrome-less box still passes —
UNLESS SELAHCUE_HEADLESS_REQUIRE=1 (set in CI), which turns a missing Chrome into a
hard failure so the gate can never silently no-op.

FIDELITY NOTE (known gap): this drives Blink (headless Chrome), NOT the engine Tauri
actually ships on — WebKitGTK (Linux), WKWebView (macOS), WebView2 (Windows). It is
therefore a gate for BROWSER-PORTABLE DOM/JS LOGIC (the behaviours asserted here:
render/dedup/cap/wiring), not for engine-specific CSS/canvas quirks. A WebKit/WKWebView-
driven smoke would be a stronger fidelity check; tracked as an audit follow-up. The real
Tauri webview stays owner-run / dev-time.
"""
import json
import shutil
import subprocess, tempfile, os, re, sys

# Repo-relative: this file lives in <repo>/scripts/, the webview in
# <repo>/implementation/desktop/crates/selahcue-operator/dist. SELAHCUE_OPERATOR_DIST
# overrides it (e.g. to point at a staged/built copy, or a mutated copy in a test).
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.environ.get("SELAHCUE_OPERATOR_DIST") or os.path.join(
    _REPO, "implementation", "desktop", "crates", "selahcue-operator", "dist"
)

# ---------------------------------------------------------------------------------------------
# D5 (ADR-0026 rev 4 — rev 2 / 86akcffvt, extended by 86akgqdxr then 86akgqdw0) — the
# "transcripts.js never writes scrollTop" invariant is STATIC and grep-checkable, not inferred
# from timing-dependent browser behaviour. Per the ADR: every previous round's control had to
# infer correctness from behaviour under conditions nobody could reliably reproduce, which is
# exactly how round 6 shipped a mutation-verified check that pinned a bug (the "TR wheel-race"
# block that round deletes, below) instead of catching one. A static rule over the committed TEXT
# cannot pass vacuously and cannot drift with a future edit.
#
# The rule: `dist/transcripts.js` may contain NO assignment to `<expr>.scrollTop` — read access
# (`x.scrollTop` with no `=`, or comparisons `===`/`!==`/`>=` etc.) is unrestricted — except sites
# in the THREE CLASSES the ADR names, each of which must carry a marker comment naming its OWN
# class. As of rev 4 the file holds two independent virtualizers plus one deliberate navigation
# write, so the classes are:
#
#   D5-exempt(init)       — a virtualizer's single initial-position reset, which runs before any
#                           scroll or animation can exist on that container. TWO sites: the
#                           transcript log's, in `openTranscript`'s `transcript_get` success
#                           handler, and the detections panel's, in `renderDetections` (86akgqdxr
#                           — `#tr-det-log` is a persistent node reused across transcripts, so
#                           without it a new transcript opens at the previous one's offset).
#   D5-exempt(test-hook)  — a write inside a `window.__tr*` hook whose only purpose is to SIMULATE
#                           user input for this driver, which cannot dispatch a trusted scrollbar
#                           drag or wheel tick. THREE sites: `__trScrollToFraction`,
#                           `__trScrollBy`, `__trDetScrollToFraction`.
#   D5-exempt(jump)       — (rev 4, 86akgqdw0/FR-124) a deliberate, click-triggered, one-shot
#                           navigation write: clicking a generated note item's linked timestamp
#                           jumps the transcript log to it. ONE site: `jumpToOffsetMs`. Never
#                           reachable from `scroll`/`wheel`/`keydown`/an animation frame — see
#                           ADR-0026's "Revision 4" section for the full argument, including the
#                           honest limits of this exemption (no fresh engine-level spike was run
#                           for this specific write, unlike revisions 2/3's mechanism changes).
#
# There is no fourth class: a write reachable from a `scroll`/`wheel`/`keydown`/animation-frame
# handler is in none of the three and is forbidden outright — it is exactly the write ADR-0026's
# C1 says cannot be made correct on WebKit.
#
# This check fails on (a) ANY scrollTop write whose line carries no `D5-exempt(<class>)` marker,
# or carries a class this file does not know, and (b) a PER-CLASS marked count that does not match
# the ADR's own numbers. (b) is what stops a future violation from being silenced by copy-pasting
# a marker onto a NEW write instead of deleting it, which a marker-presence-only check could not
# catch.
#
# Why per-class and not one total (86akgqdxr, extended by 86akgqdw0): a flat budget is FUNGIBLE.
# With one total, a later edit could delete an `init` reset and spend the freed slot on a reactive
# write marked `D5-exempt`, leaving the total unchanged and this check green — reintroducing the
# very hole the count exists to close. Bumping the total for each new class would therefore have
# WEAKENED the control while appearing to keep it. Counting each class separately restores it, and
# scales: a further virtualizer or write class raises the relevant count by however many sites it
# needs, each recorded in its own ADR revision. As before: a new exemption cannot be added by
# marking it — only a revision of the ADR can grow any of these numbers, `jump` included.
#
# NOTE (rev 3 migration): a BARE `D5-exempt` with no `(class)` no longer satisfies this check, by
# design — it reports as unmarked, so the marker migration cannot be left half-done silently.
#
# Runs before Chrome is even resolved (a pure source-text check, independent of a browser being
# available at all) so it still gates a Chrome-less dev box, and reads through `DIST` — the same
# SELAHCUE_OPERATOR_DIST override every other check in this file honours — so this file's own
# mutation-verification discipline (CLAUDE.md: "mutation-verify before claiming it") can point it
# at an isolated mutated copy without touching the tracked tree.
D5_EXPECTED_EXEMPT_COUNTS = {"init": 2, "test-hook": 3, "jump": 1}
D5_SCROLLTOP_WRITE_RE = re.compile(r"\.scrollTop\s*[+\-]?=[^=]")
D5_MARKER_RE = re.compile(r"D5-exempt\(([A-Za-z0-9_-]+)\)")


def check_d5_no_scrolltop_writes():
    path = os.path.join(DIST, "transcripts.js")
    lines = open(path, encoding="utf-8").read().splitlines()
    unmarked, by_class = [], {}
    for lineno, text in enumerate(lines, start=1):
        if not D5_SCROLLTOP_WRITE_RE.search(text):
            continue
        m = D5_MARKER_RE.search(text)
        if m is None or m.group(1) not in D5_EXPECTED_EXEMPT_COUNTS:
            unmarked.append(lineno)
        else:
            by_class.setdefault(m.group(1), []).append(lineno)
    ok_unmarked = len(unmarked) == 0
    print(
        "PASS: D5 (ADR-0026) — no unmarked `.scrollTop` write in transcripts.js"
        if ok_unmarked
        else "FAIL: D5 (ADR-0026) — unmarked or unknown-class `.scrollTop` write(s) at line(s) %s "
        "(every write must carry a marker comment naming its class — 'D5-exempt(init)', "
        "'D5-exempt(test-hook)' or 'D5-exempt(jump)', the only three the ADR permits — or be "
        "deleted; a bare 'D5-exempt' with no class does NOT count)" % unmarked
    )
    ok_counts = True
    for cls in sorted(D5_EXPECTED_EXEMPT_COUNTS):
        want = D5_EXPECTED_EXEMPT_COUNTS[cls]
        got = by_class.get(cls, [])
        if len(got) == want:
            print(
                "PASS: D5 (ADR-0026) — exactly %d marked `D5-exempt(%s)` write(s), matching the ADR"
                % (want, cls)
            )
        else:
            ok_counts = False
            print(
                "FAIL: D5 (ADR-0026) — expected exactly %d `D5-exempt(%s)` write(s), found %d at "
                "line(s) %s (a new exemption cannot be added by marking it, and the classes are "
                "counted separately so a deleted one cannot pay for a new one; only a revision of "
                "the ADR can grow either number)" % (want, cls, len(got), got)
            )
    return ok_unmarked and ok_counts


# S3 (Sana, PR #51 security review, on the `D5-exempt(jump)` class rev 4 adds): the check above
# counts WRITE sites but constrains nothing about who may CALL `jumpToOffsetMs`. Moving that one
# call into a `scroll`/`wheel`/`keydown`/animation-frame handler would reintroduce the exact
# C1 hazard D5 exists to forbid while the write-site count stayed green at `jump: 1` — the write
# itself would not move, only its trigger. This is the call-site counterpart: `jumpToOffsetMs`
# may be CALLED from exactly one site, and that site's own line must register for a `"click"`
# event and must not sit alongside `scroll`/`wheel`/`keydown`/`requestAnimationFrame`.
#
# Known, accepted limitations (Sana's re-review, PR #51 round 2) — this is a line-local textual
# check, not a data-flow analysis, so it is defeated by (a) a misleading `"click"` string placed
# in a comment beside a real reactive registration (verified live; the same accepted-limit class
# as the Makefile's `RELEASE_UNSAFE_FEATURES` regex — see ADR-0026 Revision 4's own text), and
# (b) ALIASING: `var __alias = jumpToOffsetMs; someOtherHandler(function(){ __alias(ms); });`
# passes this check GREEN, since `JUMP_CALL_RE` matches the literal substring `jumpToOffsetMs(`
# and a bare reference assignment is invisible to it. Neither evasion is reachable by an
# ordinary refactor (every benign reshape Sana tried still fails RED); both would need to be
# introduced deliberately, which is what code review is for.
JUMP_CALL_RE = re.compile(r"jumpToOffsetMs\(")
JUMP_DEF_RE = re.compile(r"function jumpToOffsetMs\(")
JUMP_FORBIDDEN_CONTEXT = ('"scroll"', "'scroll'", '"wheel"', "'wheel'", '"keydown"', "'keydown'", "requestAnimationFrame(")


def check_jump_call_site_is_click_only():
    path = os.path.join(DIST, "transcripts.js")
    lines = open(path, encoding="utf-8").read().splitlines()
    call_sites = [
        lineno
        for lineno, text in enumerate(lines, start=1)
        if JUMP_CALL_RE.search(text) and not JUMP_DEF_RE.search(text)
    ]
    if len(call_sites) != 1:
        print(
            "FAIL: D5-jump-caller (ADR-0026 rev 4) — expected exactly 1 call site for "
            "jumpToOffsetMs(), found %d at line(s) %s (a second call site needs its own review "
            "against the same 'never reachable from scroll/wheel/keydown/an animation frame' "
            "argument Revision 4 makes for the one write)" % (len(call_sites), call_sites)
        )
        return False
    lineno = call_sites[0]
    text = lines[lineno - 1]
    forbidden = [kw for kw in JUMP_FORBIDDEN_CONTEXT if kw in text]
    if forbidden:
        print(
            "FAIL: D5-jump-caller (ADR-0026 rev 4) — jumpToOffsetMs's one call site (line %d) "
            "sits alongside %s — exactly the reactive-handler class D5 forbids for a scrollTop "
            "write, even though the write itself is still marked D5-exempt(jump)" % (lineno, forbidden)
        )
        return False
    if '"click"' not in text and "'click'" not in text:
        print(
            "FAIL: D5-jump-caller (ADR-0026 rev 4) — jumpToOffsetMs's one call site (line %d) is "
            "not textually inside a \"click\" event registration — Revision 4's safety argument "
            "rests specifically on this being a click handler" % lineno
        )
        return False
    print(
        "PASS: D5-jump-caller (ADR-0026 rev 4) — jumpToOffsetMs has exactly 1 call site, and it "
        "registers for \"click\" only"
    )
    return True


if not check_d5_no_scrolltop_writes():
    print(
        "\n=== D5 static check FAILED — transcripts.js violates the ADR-0026 "
        "no-scrollTop-write invariant — see docs/architecture/adr/"
        "ADR-0026-operator-virtualized-list-scroll-model.md ==="
    )
    sys.exit(1)

if not check_jump_call_site_is_click_only():
    print(
        "\n=== D5-jump-caller static check FAILED — jumpToOffsetMs is reachable from somewhere "
        "other than a single click handler — see docs/architecture/adr/"
        "ADR-0026-operator-virtualized-list-scroll-model.md 'Revision 4' ==="
    )
    sys.exit(1)

# Floor on the number of checks the driver must run — so a driver regression that
# silently runs FEWER checks (and thus reports 0 FAIL) still fails. Set TIGHT to the
# real load-bearing count (no tautologies), so any single dropped check trips exit 4.
# Bump when adding checks; never lower it to mask a lost one.
# (Re-tightened with the window-semantics checks: the floor had drifted 19 below the real
# count, so up to 19 checks could have been dropped silently. Verified stable across runs.)
# (Raised with the Design 2.0 parity batch 1 block — CON-046 / CON-142 / PME-001 / PME-005 /
# PME-014 / PME-015 — which adds 67 checks: 640 -> 707. Set to the REAL observed count, not a
# round number, so that dropping even one of the new checks trips exit 4.)
# (Raised for the Service Plan parity batch — 86ak846ft: run-sheet owner/duration, the Plan Summary
# panel, the loading state, and the QA/security remediation. Set to the REAL observed count so
# dropping even one trips exit 4. Sana S4: this floor had been left at 829 while the driver ran
# more, which would have let every new check disappear without failing.)
# (Raised for the PLAN LIFECYCLE batch — 86ak8467m: the five lifecycle commands, the viewer /
# publish / plan_templates three-state readers, the empty state's four starts, the view-only
# frame and the change badge. 963 -> 1103, the REAL observed count. THIRTY-NINE of these controls
# are mutation-verified — break the guard each names in dist/app.js or app.css and the NAMED
# check goes RED. Four did not, at first, and every one of those failures is worth knowing:
#   - the change-badge control re-derived the predicate beside the code under test instead of
#     consuming it, so deleting the predicate left the whole suite green;
#   - the publish-state control dereferenced a node that the defect REMOVES, so it threw and
#     aborted the driver at check 728 rather than failing the check that names the rule;
#   - the Alt+arrow keyboard reorder gate and the dialog's Tab trap had NO check at all, and
#     both were live, correct behaviour that a reviewer had to mutate to discover (PL AC-35,
#     PL AC-36);
#   - and the plan surface's keyboard UNDO was not gated on the permission at all, which is the
#     same defect as the Alt+arrow path in a second place. PL AC-47 therefore asserts the CLASS —
#     no plan-editing command reaches the host from the keyboard under view-only — because
#     enumerating the paths by hand is what let the first one hide.
# A battery proves a check BITES; it cannot prove the check asserts the right thing. The one
# defect this batch found in its own code — publish_plan sharing a helper with the four commands
# that replace the plan — was invisible to it, because the test and the code agreed.)
# (Raised 1119 -> 1121 with the two round-2 premises: PL AC-40's stale-notice premise, without
# which the fresh-visit check could not tell 'planActivate cleared it' from 'it was already
# clear' (Cody L5), and PL AC-49's derived-range premise, without which a sweep over an
# empty list would report 'all clear' forever (Quinn Q-N1). The REAL observed count, so
# dropping either trips exit 4.)
# (Raised 1121 -> 1179 for 86akby7d8's two blocking fixes, both mutation-verified RED/GREEN:
# the "PP defect 1" checks drive window.scCompletedTranscript through the REAL app.js bridge
# (render() with view.transcript segments, not a direct global poke) and would trip if that
# wiring were ever silently removed again; the "PP F-5" / "PP PERF-3" checks assert Generate
# never reaches generate_sermon_notes without an explicit Confirm on the review step showing
# the exact text (plus the two focus-management a11y checks on that step), and that an
# empty/below-minimum transcript is refused before any network call — the properties
# Sana/Quinn/Vera made release-blocking. The REAL observed count.)
# (Raised 1179 -> 1184 for the PR #19 four-reviewer remediation batch (86akby7d8), all four
# mutation-verified RED/GREEN:
#   M-1 (Cody) — two new "PP F-5 M-1 (computed display)" checks assert getComputedStyle(...)
#   .display === "none" on #pp-gen-preview after Cancel AND after Confirm. The prior checks only
#   read the `hidden` DOM property, which is exactly the direction this webview's [hidden]-vs-
#   author-`display` trap bites; these read what is actually painted, backed by the
#   .pp-gen-preview[hidden]{display:none} companion rule added to dist/app.css.
#   L-1 (Sana, Quinn — independently) — "PP F-5 L-1" premise + negative check. The transcript is
#   now advanced through the REAL render() path (PP_TRANSCRIPT_SEGMENTS_ADVANCED) WHILE the
#   preview sits open, then the sent transcript is asserted to be the PREVIEWED fixture and NOT
#   the advanced one — so a confirmGenerate regressed to re-read window.scCompletedTranscript at
#   send time (instead of using the value it was handed) now has something to disagree with.
#   L-2 (Quinn, Cody, Vera — independently) — "PP F-5 L-2" pins the new
#   .pp-gen-preview-scope disclosure copy verbatim, so the preview says in words that it may be
#   drawn from a recent window rather than the whole service.
#   L-3 (Vera, note) — two "PP L-3" checks drive 125 segments (over MAX_TRANSCRIPT_ROWS=120)
#   through the real render() path and assert window.scCompletedTranscript matches the SAME
#   120-tail #transcript-log renders from, not the unsliced list — the bridge was changed from
#   `all.map(...)` to `segs.map(...)` in app.js's syncTranscript() to make that true.
# The REAL observed count (1179 + 5 + 2 = 1186).)
# (Raised for the Transcripts surface — 86akcffvt / FR-130 core slice: the new page's list,
# read-only detail viewer, empty/error states, and the bounded-window rendering control (the
# transcript-length virtualizer that keeps mounted DOM rows bounded regardless of segment count).
# 1196 -> 1233, the REAL observed count (baseline drifted 1186 -> 1196 between rounds; both
# numbers are floors, never exact, per this constant's own contract). The three bounded-DOM
# checks were mutation-verified BY HAND with the whole suite running (not `--exact`): the initial
# windowed render call was mutated to render every segment unconditionally, which flipped exactly
# those three checks RED (mounted-row-count bound, the last-segment-absent-on-open control, and
# the scroll-to-end exact-text check) while every other check in the 1233-check run stayed GREEN
# — restoring the guard returned the suite to 0 FAIL. See the "=== Transcripts" block below.
# 1233 -> 1243: performance review (Vera V-1/V-2) found the 500-segment fixture above uses
# UNIFORM 85-char lines at this harness's 800x600 default, which happens to sit just above the
# real/estimated row-height "break-even" ratio (~0.63) the virtualizer's fixed 88-chars/line
# height ESTIMATE needs to stay correct — so the fixture never exercised the regime where the
# bug actually bites. The 10 new "TR realistic" checks widen the detail view to ~1500px (the
# operator's own real 1520px default) with a REALISTIC mixed-length transcript, reproducing
# Vera's measured failure (blank scroll frames, an unreachable last segment) and its fix
# (measured-height calibration, diff-and-patch + hysteresis). See the "=== TR realistic-width
# regression control" block below; mutation-verified against the pre-fix transcripts.js.
# 1243 -> 1246: code review (Cody) and performance review (Vera V-7) independently found that
# NONE of the checks above actually verify DOM-node identity across a diff-and-patch render —
# they assert render count, visual coverage, or reachability, all of which stay green even if
# the clear+rebuild anti-pattern this PR fixed were silently reintroduced (Vera confirmed by
# mutation: disabling only the diff-and-patch branch survives both committed suites at 0 FAIL).
# The 3 new "TR identity" checks tag mounted rows with a test-owned marker, force a real
# hysteresis-crossing window move, and assert every row still in the overlap between the old and
# new window kept ITS OWN marker (same DOM node), not a fresh one a rebuild would create. See the
# "=== TR DOM-node identity" block below; mutation-verified against a forced clear+rebuild.
# 1246 -> 1250: performance re-review (Vera V-6, blocking) found the scroll-anchor compensation
# fix itself has NO regression test either: the "TR realistic" fixture interleaves segment
# lengths evenly, so it happens to stay near the calibration ratio everywhere and never triggers
# the fully-blank-frame regression a fresh scrollbar-drag/jump into a DIFFERENT length regime
# produces (confirmed by mutation: disabling the V-6 compensation entirely leaves every check
# above, including "TR realistic", at 0 FAIL). The 4 new "TR regime-change" checks add a PHASED
# fixture (short/long/medium thirds, not interleaved) and jump straight into it fresh before each
# check, mutation-verified against the same compensation-disabled mutant. See the "=== TR
# regime-change fresh-open jump control" block below.
# 1250 -> 1254: performance re-review (Vera V-13, test gap) found no control specifically proves
# the ANCHOR half of the V-6 fix (as opposed to the ratio-fallback half) is necessary: the
# ratio-only-fallback mutant (MV6a, round 2's "P1") passes every check above at 0 FAIL, because a
# ratio-only correction still avoids a fully blank frame — it just lands 300-1,257px off the row
# it should have kept anchored, which none of "at least one row visible" / "reachable" can see.
# The 4 new "TR V-13" checks track ONE real row across a hysteresis-crossing render on the PHASED
# fixture's long block and assert its on-screen position stays within 2px of the expected
# 60px-per-tick displacement — a bound only the anchor term (reading that row's own live position)
# can hit. See the "=== TR V-13" block below; mutation-verified against the anchor-forced-null
# mutant (the assertion goes red; the two setup preconditions above it stay green).
# (drifted 1254 -> 1290 across intervening rounds without this constant being kept in step — the
# floor's own contract says "never lower it to hide a lost one", not "never let it fall behind the
# real count either", but a floor that drifts this far behind stops doing useful work. Round 6
# re-tightens it to the REAL observed count at HEAD before this round's own additions, then adds
# this round's own: 1290 -> 1297, the 7 new "TR wheel-race" checks (QA finding — Quinn, High: a
# real wheel tick landing 0-4ms before a keyboard jump is not defended by `expectedScrollTop`
# echo-suppression alone on Chromium/Blink). See the "=== TR wheel/jump race guard" block below —
# mutation-verified against three independent mutants: removing the `armJumpGuard()` call in
# `jumpScrollTop` turns the "corrected back to Home's true target" assertion red (the corruption
# this round fixes reappears); separately removing just the `wheelEventSeq` genuine-new-wheel bail
# turns the negative-control assertion red (the guard starts fighting real scrolling instead of
# only stale residue); separately removing `openTranscript`'s own `jumpGuardGen++` (own hardening,
# this round — a guard must not outlive the transcript it was armed for) turns the reopen check
# red ONLY when the reopened transcript is comparably long to the one the guard was armed for —
# the first version of this control reopened a short fixture instead and passed even with that
# invalidation removed, because a short transcript's own small `scrollHeight` reclamps ANY stale
# target down near 0 by coincidence (the same reclamp this round added for the legitimate resize
# case), so the control was rewritten to reopen the SAME long fixture instead, which does not
# benefit from that coincidence. All three verified with the whole suite running, not `--exact`.
# This same round
# also fixes `PL AC-53`'s two-check flake (Quinn, bisected to `0876d6c`, confirmed live on this
# PR's own CI run): a fixed `await sleep(20)` after a synchronous state-changing call raced an
# unrelated timing-margin change from THIS round's own `TR V-13` block added earlier in the same
# script execution. Replaced with `waitFor` polling the actual DOM condition, and `rowNode`'s
# capture for the adjacent "rebuilds nothing" control now happens only once that condition has
# verifiably settled — closing what had looked like a second, independent failure but was a
# knock-on effect of the same race. No check COUNT change from that fix (same two assertions,
# reworded trigger).)
# 1297 -> 1301 (86akmdkdg): the TR measureObserver disconnect-on-resize-mid-scroll fix adds 4
# checks.
#
# 1301 -> 1355 (86akcffy0, rebased onto 86akmdkdg): "Generate Sermon Notes from a selected stored
# transcript" — the new "TR generate"/"TR F-5" block adds 30 checks (then 17 more in a
# remediation round, then 4 more in a reviewer re-check round — see the three-round history in
# this ticket's own commits) covering the from-history Generate flow's own review-and-confirm
# step (same F-5 shape as "PP F-5" above, which is UNCHANGED and still passes with its own
# original, still-accurate "recent window" copy): the review shows the transcript's exact
# COMPLETE stored text and states its size; its OWN honest `.pp-gen-preview-scope` copy (pinned,
# "TR F-5 L-2"); Cancel/Confirm and the a11y focus moves that go with them; the SAME shared
# consent gate blocks the network call exactly like the live-tail path (a live UI-driven
# regression test, not an assumption); Confirm sends the transcript's ID rather than a client
# string; a successful generate renders the draft READ-ONLY (no Edit — that stays the Settings
# panel's persisted-draft flow) and flips the notes badge immediately; opening a DIFFERENT
# transcript resets all Generate UI/state; a transcript past the 400,000-character clamp gets a
# VISIBLE, exact-count truncation notice rather than a silent cut ("TR generate oversize"); an
# in-progress transcript is refused Generate entirely (Sana F1 — the button is genuinely
# disabled, computed, the operator is told why, and `onGenerate` independently re-checks as
# defense in depth); an existing draft is not silently overwritten (Sana F2); a stale selection
# cannot supersede a later one (Sana F3, driven with a deliberately deferred stub response so the
# race is real); the new `.tr-gen[hidden]` CSS fix has a real computed-display regression test
# (Cody — every prior check on these elements asserted only `.hidden`, never
# `getComputedStyle(...).display`, so deleting the CSS rule would have passed everything); the
# preview is bounded to the clamp instead of rendering an unbounded DOM node (Vera PERF-1 —
# measured ~0.10ms/KB of unbounded forced layout before the fix); and a fast double-click before
# the async character-limit resolves renders the review step exactly once (Vera PERF-2, whose
# own regression test needed a rebuild after a first, DOM-node-count version proved vacuous
# under its own mutation check — `openGenPreview` clears its container on every call, so two
# back-to-back calls leave an IDENTICAL final DOM to one; fixed with a real invocation counter,
# `window.__trOpenGenPreviewCallCount`, neither call site can fake). Every one of these
# mutation-verified RED/GREEN across three rounds (initial implementation, four-reviewer
# remediation, reviewer re-check follow-ups — see the PR's own commit history for the blow-by-
# blow). Measured post-rebase (86akcffy0's branch rebased onto 86akmdkdg's merged 1301): 1355
# checks, 0 FAIL — exactly 1301 + 54, confirming no collision or overlap between the two
# tickets' checks. (86akcffy0's own comment here notes this is the REAL observed count, not
# 1301+55 by arithmetic — the floor has drifted quietly between rounds before, so it is
# re-measured at HEAD, never merely incremented. Same discipline applies below.)
#
# 86akc0tua (this branch) separately adds 14 checks on top of the ORIGINAL 1300 baseline
# (verified against a clean `origin/main` worktree at 269591e, run BEFORE this change: 1300,
# not the 1297 this constant last recorded — this file's own count had already drifted a
# little stale; a floor value is a lower bound, not an exact tracker, so that alone is not a
# defect): 10 explicit `ok()` calls + 1 implicit one from an extra `ppGenerateAndConfirm` call
# in the first remediation round (empty-but-requested sections filtered from persistence,
# 1300 + 10 + 1 = 1311, matching two consecutive standalone runs), plus 3 more explicit `ok()`
# calls with no further implicit ones in the second remediation round (Cody's second finding
# on PR #46, the edit-save route — this edits an ALREADY-generated draft via
# el("pp-gen-edit")/el("pp-gen-save") directly, no new Generate click: the save actually
# happened (setup), the caveated-empty section is never sent to update_sermon_note_draft, and
# a populated section is NOT dropped by the same filter (positive control): 1311 + 3 = 1314,
# matching the real observed count — both measured BEFORE 86akmdkdg or 86akcffy0 existed).
#
# Rebased onto 86akcffy0 (which is itself rebased onto 86akmdkdg): all three tickets' additions
# are non-overlapping (different fixtures, different DRIVER sections — confirmed by inspecting
# each diff's hunk locations before this rebase, not assumed). The naive sum was
# 1355 + 11 + 3 = 1369, and this is confirmed as the REAL observed count too — a standalone run
# of this file after the rebase reported "1369 checks, 0 FAIL" exactly, so unlike the first
# remediation round above (where an implicit `ok()` inside a helper call made naive arithmetic
# wrong by one), this rebase's three additions really are fully independent with no shared
# side effects between them.
#
# 86akby820 (this branch) separately adds 6 more on top of the ORIGINAL pre-86akcffy0 1311
# (verified before 86akmdkdg's, 86akcffy0's, and 86akc0tua's second round existed): 5 explicit
# `ok()` calls on the new "scripture_verification" fixture (a verified reference still renders
# + its positive control carrying no unverified mark, an unverified reference in the extracted
# list carrying a computed-visible mark, a fabricated reference found ONLY embedded in a
# section's body text still rendering with its own mark, and the verification-scope note
# rendering with the exact required wording) plus ONE implicit check from the extra
# `ppGenerateAndConfirm` call. 1311 + 5 + 1 = 1317, matching the real observed count at the
# time (before 86akmdkdg/86akcffy0/86akc0tua's second round existed).
#
# Security review remediation (Sana F1/F3 on PR #47) adds 2 more: the verified reference
# now carries its own explicit computed-visible mark (F3), and the list's unverified
# entry is deliberately an ABBREVIATED spelling ("3Jn 4:12") rather than canonical, with
# an assertion that it still renders in the list at all before checking its mark (F1).
# 1317 + 2 = 1319, matching the real observed count at the time.
#
# Security review remediation (Sana F4 on PR #47) adds 4 more, no implicit ones (this
# block edits an ALREADY-generated draft, no new Generate click): the edit-save actually
# saved (setup), the verified mark survives an unrelated edit-save, the unverified mark
# ALSO survives it (the actual harm this ticket exists to prevent — a reloaded/saved
# draft, not just the live response), and the verification-scope note is still present.

# 1319 + 4 = 1323, matching the real observed count at the time (before 86akmdkdg/86akcffy0/
# 86akc0tua's second round existed) — this ticket's total own contribution across all three
# commits is therefore 1323 - 1311 = 12 checks.
#
# Rebased onto the now-combined 86akmdkdg+86akcffy0+86akc0tua floor of 1369: this ticket's own
# 12 checks (across all three of its commits) are independent of all three (own fixture, own
# DRIVER section, inserted immediately after 86akc0tua's edit-save block rather than
# overlapping it). The naive sum was 1369 + 12 = 1381, and this is confirmed as the REAL
# observed count too — a standalone run of this file after the rebase (and after fixing the
# sections_to_persist compile break the combined DraftCaveat enum exposed — see that commit)
# reported "1381 checks, 0 FAIL" exactly.
#
# 86akgqdxr (this ticket) rebuilt onto the above 1381 floor (86akmdkdg+86akcffy0+86akc0tua+
# 86akby820, all four now on `origin/main`) by cherry-picking only its own 3 unique commits
# rather than replaying its old fast-forward-merge history (which carried pre-fix copies of
# 86akcffy0/86akc0tua/86akby820 that no longer match their now-merged, differently-shaped
# equivalents). Adds its own detections panel (AC1, bounded-rendering AC5, NFR-019/020), the
# saved-draft's real content and in-place edit (AC2, ported from settings.js's persisted-draft
# surface), the empty states (AC3), the read-only correction overlay, and one flipped
# pre-existing assertion (the from-history draft now correctly shows an Edit affordance —
# 86akcffy0's own "no edit surface" restriction was written expecting this exact successor
# ticket to lift it). Previously measured against the old, pre-rebuild 1323 floor as ~76 checks
# (1410 - 1323 by subtraction) — per this constant's own repeated discipline, that arithmetic is
# NOT trusted here either. The naive sum against the new 1381 floor would be 1381 + 36 = 1417 by
# subtraction from the old figures, and this IS confirmed as the real observed count too — a
# standalone run of this file against the rebuilt branch (cherry-picked onto current
# `origin/main`, all four dependencies included) reported "1417 checks, 0 FAIL" exactly.
# 1417 -> 1419: closed a real gap the rebuild surfaced, not a rebuild artefact. This ticket's own
# `readSectionsFromForm` in transcripts.js was ported from settings.js BEFORE bfedaf2 (86akc0tua's
# second remediation round) added a client-side filter there dropping a caveated-empty section
# from the edit-save payload — so this ticket's own Transcripts edit surface carried the exact
# same bug bfedaf2 fixed for Settings, just never caught because no dependency branch touches
# transcripts.js. Fixed by porting the identical filter (+ its `isStillEmpty` helper) into
# transcripts.js; 2 new checks added to the existing "TR notes" edit-save block (a caveated-empty
# section is never sent; a populated section is not dropped by the same filter — positive
# control). Mutation-verified: disabling the new filter (`.filter(function (s) { return true; })`)
# turned exactly the first new assertion red while the positive control and every sibling check
# stayed green; restored and re-confirmed green. 1417 + 2 = 1419, matching the real observed count.
# 1419 -> 1423: four-reviewer gate remediation on PR #50, both real findings, not rebuild noise.
#   Cody (High) — .tr-line-txt-raw measured 3.79:1/3.96:1, failing AA-normal (the same
#   --sc-text-muted trap this file's own app.css already fixed once for .scr-card-meta). Fixed by
#   stepping to --sc-text-secondary; adds 1 check (NFR-020 on the correction overlay's raw text),
#   mutation-verified (reverting the colour turns exactly this check red at 4.41:1).
#   Vera (V-3) — the three existing AC5 scroll-driven checks are ALL driven through
#   `__trDetScrollToFraction`, which calls `recomputeDetWindow()` directly — the same "control
#   reads a copy" trap `implementation/desktop/CLAUDE.md` documents. The committed mutant (2)
#   disabled BOTH call sites (`onDetScroll`'s and the test hook's) together, so it proved ONE of
#   the two matters, never that the REAL `scroll` -> `onDetScroll` -> rAF path does anything —
#   disabling only `onDetScroll`'s call passed unchanged (Vera measured this live). Fixed by
#   adding 3 checks using the same proven-safe idiom the "TR measureObserver disconnect" block
#   already established for this harness's `--virtual-time-budget` (a real dispatched `scroll`
#   event, with `requestAnimationFrame` intercepted to CAPTURE the scheduled callback rather than
#   race real frame timing, then invoked directly): 1 setup assertion (the real event reached
#   `onDetScroll` and scheduled a frame) + 2 exercising the captured callback (eviction/mount via
#   the REAL path). Mutation-verified against Vera's exact scenario: disabling only `onDetScroll`'s
#   `recomputeDetWindow()` call turns RED exactly the 2 new real-path assertions while the 3
#   pre-existing hook-driven assertions stay GREEN — proving they test different things, closing
#   the gap without touching the pre-existing hook's own contract.
#   1419 + 1 + 3 = 1423, matching the real observed count.
#
# 86akgqdwc (rebased onto this settled 1423) separately adds 6 more, all in the unrelated
# "INCLUDE IN NOTES"/scripture-verification blocks, none overlapping 86akgqdxr's detections-
# panel/edit-surface work (confirmed by inspecting hunk locations before merging, not
# assumed):
#   - 2 from the include-in-notes forEach loop driving the two new toggles
#     ("podcast_show_notes", "short_description") through set_include_flag, each its own
#     `ok()`. The column/row-count assertion in the same block changed its numbers (3/3 ->
#     4/4) but stayed ONE `ok()` call, so it contributes nothing to the delta.
#   - 4 from security review remediation (Sana F2 on PR #48): a NEW, isolated
#     "scripture_incomplete" DRIVER block proving `DraftCaveat::ScriptureVerificationIncomplete`
#     renders — 3 explicit `ok()` calls (the note renders computed-visible with role=note;
#     the section it would most affect still renders its own content alongside the note; a
#     NEGATIVE CONTROL on the preceding "scripture_verification" draft, which carries no such
#     caveat, confirms the two notes are gated on different caveat kinds) plus ONE implicit
#     check from the extra `ppGenerateAndConfirm` call.
# The naive sum is 1423 + 2 + 4 = 1429, and this was confirmed as the real observed count too
# (a standalone run at that point reported "1429 checks, 0 FAIL" exactly).
#
# 1429 -> 1431: Cody's delta re-check on this ticket's rebased head caught a real gap, not
# rebuild noise — `transcripts.js` (the Transcripts-tab draft viewer) never rendered the new
# `scripture_verification_incomplete` note, even though `settings.js` does and the backend
# computes the caveat for both surfaces (`generate_sermon_notes` AND `sermon_note_draft_json`,
# which feeds `transcript_get` as well as the Settings reload path). Cody reproduced it live:
# added the caveat to the "Fixture Sermon" fixture, added a throwaway assertion mirroring
# settings.js's own check, confirmed FAIL, reverted the probe cleanly. Fixed by porting the
# identical `anyScriptureVerificationIncomplete` helper + note block from settings.js into
# transcripts.js (the same pattern already used there for the other two caveat kinds), and by
# adding this caveat to the SAME "Fixture Sermon" fixture (id 7) Cody's own reproduction used
# — real regression coverage, not the throwaway probe — with 2 explicit `ok()` calls (the note
# renders computed-visible with role=note; the draft's own content, asserted just above, still
# renders alongside it — a positive control that this is an addition, not a replacement). No
# new fixture, no new generate/open call was needed since fixture 7 was already opened earlier
# in this same test flow, so there is no additional implicit check here.
#
# This constant is a SINGLE assignment on purpose (Cody's NIT on the same re-check): two live
# `EXPECTED_MIN_CHECKS = ...` lines previously existed in this file (1423, then 1429) — harmless
# today only because Python resolves module-level names last-write-wins, but the identical
# shape this repo's own CLAUDE.md warns about elsewhere (the Makefile's
# `RELEASE_UNSAFE_FEATURES` multi-assignment guard). Updated in place from here on, never
# appended.
#
# 1431 -> 1490: FR-129 (86akgqdx8) regenerate-with-retention. New PP REGEN-*/TR REGEN-* blocks
# cover: staging leaves the accepted draft retrievable/unchanged; the banner names the
# still-saved prior draft; Edit is hidden while pending; Discard restores the accepted draft
# unchanged; Confirm replaces it (single prior version); consent-off still gates a regenerate
# exactly like a first-time generate; a transport failure during regenerate never loses the
# prior draft; a degraded regenerate stages and shows its content but cannot be CONFIRMED over
# an already AI-generated draft ("once AI-generated, always AI-generated", extended from Save to
# Confirm) — and, discovered live while writing this block, that a refusal on Confirm/Discard
# must render INLINE on the still-open banner rather than wiping the whole result region, or the
# Transcripts workspace specifically would have no recovery path back to Discard at all
# (`transcript_get` never re-surfaces a pending regeneration, unlike settings.js's in-memory
# `currentDraft`). Also updated the PRE-EXISTING "TR generate (Sana F2)" check, whose premise
# (Confirm outright REPLACES an existing draft) stopped being true the moment this shipped — the
# notice now says the accurate, safer thing. Confirmed as the real observed count: a standalone
# run at this point reported "1490 checks, 0 FAIL" exactly.
#
# 1490 -> 1496: 86akgqdx8 four-reviewer gate (Quinn — Low). PP REGEN-4/PP REGEN-5 proved
# consent-off and transport-failure SPECIFICALLY against a transcript that already has a saved
# draft (the regenerate scenario); the pre-existing TR consent-off check ("(d)" above) only
# covers the FIRST-TIME-generate case on this surface, so the same proof was missing for TR's
# own regenerate path — exactly the "proven on one console, assumed on the other" shape this
# batch has hit as a real MAJOR bug before. Added TR REGEN-5/TR REGEN-6, mirroring PP REGEN-4/
# PP REGEN-5 through this surface's own `tr-` wiring. Confirmed as the real observed count: a
# standalone run at this point reported "1496 checks, 0 FAIL" exactly.
#
# 86akgqdw0 (FR-124), authored in parallel off the PRE-86akgqdx8 baseline (4b21c39, 1431
# checks): re-derived by actually running this file against that real baseline (1431, 0 FAIL)
# versus this ticket's own branch at that point (1449, 0 FAIL): a delta of 18, one more than
# this ticket's own 17 explicit new `ok()` calls (12 transcripts.js timestamp/jump + 5
# settings.js data-parity). The 18th is real, not a miscount: `ppGenerateAndConfirm`
# (settings.js's shared Generate-and-Confirm test helper) carries its OWN internal `ok()`
# ("clicking Generate alone never calls generate_sermon_notes") on every call, and this
# ticket's new "timestamps" mock variant calls that helper ONE more time than the baseline
# did — confirmed by diffing the two runs' check lists directly, not guessed.
#
# Sana's security review (PR #51, S2/S3, still against the pre-86akgqdx8 baseline): the
# original 1449 above never exercised a jump to a genuinely UNMOUNTED target row. Closed by
# extending the fixture with 300 filler segments and a real "Deep in the service" marker,
# adding exactly 6 new browser-side `ok()` calls (re-run and diffed directly, not counted by
# hand): 1449 + 6 = 1455, confirmed by running this file (1455, 0 FAIL).
#
# Rebased onto origin/main after 86akgqdx8 merged (main had independently reached 1496 via its
# own, unrelated regenerate-with-retention checks — see the history above this point). The two
# branches' additions are now BOTH present in the same file, so the correct total is neither
# 1496 nor 1455 nor their sum-minus-overlap by hand arithmetic — re-derived the only honest way,
# by actually running the merged file: 1520, exactly the naive 1496 + (1455 - 1431) prediction
# (the two branches' checks really are simply additive here; there was no hidden interaction).
#
# CORRECTION: this constant briefly read 1514 — a wrong number from a single run whose exact
# cause was never root-caused (recorded at the time as "this file's own count has drifted from
# hand arithmetic before... never a flaky count," which was itself wrong reasoning: no evidence
# was gathered for WHY that run undercounted by 6, and no evidence was gathered that it wasn't a
# one-off before writing a confident explanation for it). Caught only because two independent
# reviewers (Quinn, Sana), each in their OWN fresh worktree pinned to the same commit, both
# independently ran this file and both got 1520 — not 1514 — which is what prompted re-running
# it a further two times in THIS worktree (1520 both times, `git status` clean throughout, no
# `SELAHCUE_OPERATOR_DIST` override). Four independent runs across three separate worktrees
# agreed on 1520 as the count AT THAT COMMIT; zero runs since have reproduced 1514. The lesson —
# verify empirically after every change to this file, never hand-derive — still applies, and is
# exactly what the next two corrections below are each about.
#
# 1520 -> 1544: ClickUp 17tnw2axpt9 (PR #58) added 24 assertions (TD-012/PSC-005/DLM-001 gradient-
# hover contrast, mirroring the existing PME-005 block).
# 1544 -> 1548: PR #62, remediating that PR's own review findings, added 4 more (a `filter` guard
# on the TD-012/PSC-005 hover checks Sana found missing, plus a PSC-005 disabled-state guard Vera's
# finding required).
# 1548 -> 1593: unrelated ticket 17tnw2axptb (PR #61) added its own 45 Detected-Scriptures
# assertions (CON-111/116/121/129/130/134/136/137/138) on top, in parallel (1548 + 45 = 1593).
# Its branch had claimed a rebase onto main that had not actually happened, so its own copy of
# this constant read 1544 — 45 checks looser than the real merged total. Cody's review of PR #61
# caught the drift; re-derived the only honest way, by actually running the file against the real
# rebase, and confirmed by two independent runs matching Cody's own independent trial-merge count.
# The commit that landed this recorded the constant as **1589**, not 1593 — a merge-resolution
# artifact (see the 1589 -> 1596 entry below), not what the arithmetic above actually gives.
# 1589 -> 1596: same PR #62, round 2 (rebased onto the by-then-merged main above) — Cody and Vera
# independently flagged that the PSC-005 disabled-state guard only checked a `background` was
# DECLARED, not that its VALUE was right (a nonsense `background: red` would have passed). Added 3
# more checks comparing it against the rest-state rule's own value instead of just its presence,
# mutation-verified. Hand arithmetic said 1589 + 3 = 1592, but two independent runs against the
# real rebase both reported 1596. Isolated why rather than writing it off as drift: running
# origin/main's OWN committed copy of this file, unmodified, reports **1593** — the 1589 that
# commit itself recorded was already 4 short of what its own code actually produces, before this
# change added anything. 1593 + 3 (this change's own additions) = 1596, which is exactly what both
# runs showed — so the number below is fully accounted for, even though the PRE-EXISTING 1589 on
# main was not independently re-investigated here (out of scope for this ticket; the discrepancy is
# on main already, not introduced by this branch). Bump this again, with the same
# empirical-not-hand-derived discipline, the next time a check is added or removed.
#
# 1596 -> ?: PR #61 (17tnw2axptb) merged to main at ITS OWN pre-remediation 1589 commit — before
# Sana's and Quinn's reviews of that same PR forced a real remediation pass (three blocking
# security findings + a QA bug, 17tnw2axre8; see the CON-137 REDESIGN comment in app.js and the
# Sana/Quinn-tagged assertions throughout this file for what changed and why). That pass removed
# the automatic client-side duplicate-cooldown suite (CON-137's original ~9 assertions:
# .det-duplicate rendering, the cooldown countdown, "Show anyway") and added a larger set of new
# ones (Mute-on-every-card + its History record/Unmute reverse gear + the once-per-id repeat-
# dismiss guard, the Edit/re-stage "never stages" checks that actually wait past the 120ms
# debounce, the whole-chapter on-air narrowing fix, and the confidence-fails-open fix). PR #61
# was then merged to main at that PRE-remediation commit (1589) — before this Sana/Quinn pass was
# pushed, despite both reviews being explicitly BLOCK — so the remediation was cut fresh from
# main and rebased. That first rebase (onto 1589 + PR #58's own Sana/Vera remediation) measured
# 1602 by two independent runs, and this constant briefly read that. A further, separate PR #63
# round then landed on main (the 1596 entry immediately above) before this branch's *own* PR was
# opened, forcing a SECOND rebase with a real merge conflict in this exact comment block — two
# independently-evolving hand-tallies is exactly the shape this constant's history keeps
# demonstrating cannot be trusted in isolation. Re-derived the only honest way, per this
# comment's own repeated lesson, against the file as it stands after resolving that conflict:
# 1605, confirmed by two independent runs in this worktree (both 1605, 0 FAIL).
#
# 1605 -> 1610: Cody's review of PR #64 found the verse-RANGE half of the Edit/History staging
# fix (app.js's `isRange` branch) had zero regression coverage — every existing fixture used a
# single-verse reference, so `isRange` was always false by construction and mutating that
# branch's own `stage` guard produced 0 FAIL across the whole suite. Widened the get_chapter mock
# to return a genuine range response for a "N-M" reference and added 2 real assertions (Edit and
# History re-stage each with a range reference) plus their setup/premise checks. Mutation-verified
# (reverted the guard, confirmed exactly those 2 assertions RED, restored). Confirmed by two
# independent runs (both 1610, 0 FAIL).
#
# 1610 -> 1622: Vera's performance review of PR #64 (P2) found that a REFUSED dismiss_detection
# for a muted reference was marked "handled" (added to mutedDismissSent) BEFORE the invoke
# resolved, with the .catch() swallowing the failure — so a failed dismiss was never retried,
# permanently reproducing the exact visible inconsistency (empty panel, stale count pill) Sana's
# original PR #61 finding was about. Fixed at both call sites (the auto-dismiss loop in
# syncDetections, and the manual mute-button click in buildDetectionCard) by un-remembering the id
# on failure. The FIRST version of that fix was itself incomplete, caught by this file's own new
# test going RED on the first run after writing it (not just claimed clean): un-remembering the id
# is not sufficient, because syncDetections bails out at its own top (`if (key === detectionsKey)
# return;`) whenever the host's view is byte-identical across polls — exactly the "host hasn't
# caught up" case the retry exists for — so the retry was inert until detectionsKey is ALSO
# invalidated on failure. A second, subtler gap surfaced the same way when writing the mutation
# test for the manual-button call site: the button's OWN detectionsKey reset is provably dead
# code against every test that does not land an intervening poll between the click and its
# failure — removing that line produced 0 FAIL until a dedicated race test (a one-shot
# DEFER+reject hook, __dismissDetectionDeferRejectOnce, holds the promise open so a genuinely
# unrelated render() can land mid-flight) was added to actually exercise it; only then did
# reverting that line go RED. Sana's follow-up security review of the same PR then found two
# further real issues in the same area: (finding C) recordDetectionOutcome fired unconditionally
# BEFORE the invoke settled, writing a false MUTED History row for a mute the host never
# confirmed, and would have written a SECOND row once a retry later succeeded — moved the record
# into each call site's success branch so it fires at most once, only once actually confirmed.
# The first version of THIS test was also incomplete in the same way as the retry test above: a
# single always-succeeding retry cannot distinguish "recorded on dispatch" from "recorded on
# confirmed success" for the auto-dismiss loop's own call site, so that mutation passed clean
# until the test was strengthened to fail the loop's own retry once too (three attempts total:
# fail, fail, succeed) before it caught it; (finding D) the Unmute button reset detHistoryKey but
# not detectionsKey, so a still-queued detection for a just-unmuted reference recomputed to the
# same stored key and never reappeared — fixed by invalidating detectionsKey there too. 12 new
# assertions across 5 dedicated scenarios (auto-dismiss-loop retry, manual-button retry, the
# manual-button race, finding C's no-false-row / no-duplicate-row across three real attempts,
# finding D's post-unmute reappearance), each mutation-verified individually against the
# STRENGTHENED suite (reverting its own guard turns exactly that scenario's assertions RED,
# nothing else — re-checked after each test strengthening, not just once at the start). Confirmed
# by two independent runs (both 1622, 0 FAIL).
#
# 1622 -> 1625: same PR #64, Sana's finding B (non-blocking): the setCursor-only clearTimeout
# above narrows the stage-timer race but does not close it — get_chapter is an async host round
# trip, and a timer already pending when a read-only load STARTS can still fire mid-fetch on a
# slow (300ms+) trip, before setCursor(idx, false) ever runs to cancel it. loadChapter now also
# clears it before the fetch starts (app.js). Reproduced for real with a new one-shot DEFER hook
# on the get_chapter mock (__getChapterDeferOnce/__getChapterDeferredResolve) that holds the
# fetch open so a genuinely pre-armed timer (from a real verse click, not a hand-set variable)
# gets a real chance to fire during the wait — 3 new checks (1 setup + 2 real assertions),
# mutation-verified (reverting loadChapter's own clearTimeout turned exactly those 2 assertions
# RED, restored). Also addressed in this same pass, no new checks needed: finding A (the isRange
# branch's `stage` guard, app.js's loadChapter) was already covered by the existing range-Edit
# test above and re-confirmed by inspection; finding E (app.css's CON-134 comment block still
# named the pre-fix window.__openChapterForStage as Edit's call) was a stale-comment correction
# only. Confirmed by two independent runs (both 1625, 0 FAIL).
#
# 1625 -> 1630: ClickUp 17tnw2axptu (Pre-service Check parity closure). The audit
# (docs/design/DESIGN-2.0-PARITY-AUDIT-preservice.md) flagged `.ps-detail-warn`/`.ps-detail-block`
# as an UNMEASURED contrast pairing (PSC-009) rather than a scored defect. Independently computed
# both clear AA-NORMAL against --sc-surface at the row's real 12px/500 weight (8.85:1 / 5.52:1 —
# the second figure matches PME-004's independently-established figure for the same token pairing
# exactly), so there was no fix to make — 5 new assertions (2 premises, 2 real measurements, 1
# cleanup) added to lock the passing state in place on the LIVE DOM instead of leaving it
# unmeasured. Mutation-verified: temporarily recoloured both rules to --sc-surface (matching the
# background, forcing ~1.00:1) and confirmed EXACTLY those 2 measurement assertions went RED
# (1630 checks, 2 FAIL) with nothing else disturbed; restored and re-confirmed clean. The other 8
# non-PSC-005 findings needed no code change: PSC-001/002/003/008 remain genuinely blocked on the
# still-open `DECISION — New-surfaces` ClickUp task (17tnw2axpu4, zero comments); PSC-004/006/007
# were already MATCH/EXTRA/an accepted honesty trade-off per the audit's own verdicts, re-verified
# against the live Figma frame (344:124) rather than just the doc. Confirmed by two independent
# runs (both 1630, 0 FAIL).
#
# 1630 -> 1672: ClickUp 17tnw2axptg (Presentation web: safety & access essentials), authored in
# parallel on a separate branch against the pre-17tnw2axptu baseline (1625) and rebased onto main
# after that ticket landed — this entry's starting point is 1630, not the 1625 these checks were
# originally counted against. New checks added on that branch, pre-rebase, in three passes: 37
# across PME-055/053/059/006-011/027 (this ticket's own implementation); +3 (1 setup + 2 real
# assertions) for Cody's PR #69 finding that a duplicate source vanishing mid-dialog toasted a
# false-positive "Presentation duplicated" instead of surfacing the error banner; +2 for Sana +
# Vera's independently-corroborated PR #69 finding that pmLibDelete's own comment promised "fail
# OPEN on the warning" for a failed view() read, but the code left the warning list untouched on
# failure — reading exactly like a clean "not referenced" and defeating PME-059's purpose. All
# three behavioural fixes were mutation-verified pre-rebase (reverting each turned exactly its own
# assertion(s) RED, restored). 1630 + 37 + 3 + 2 = 1672, matching the post-rebase measured count
# exactly.
#
# 1672 -> 1674: same ticket, remediation round 4 — 2 new checks covering Sana's PR #69 review
# round-2 finding that pmLibDelete's plan-reference check conflated "the deck is linked" with
# "the plan has a reported name": `if (linked && v.plan_name) planRefName = ...` gave NO warning
# at all when a deck was genuinely linked but the plan reported no name (reachable via
# Backend::Remote loading a ServicePlan built through from_parts, which applies no non-empty-name
# bound) — the same silent-clean-dialog failure already fixed above, one field over. Mutation-
# verified (removing the new linked-but-unnamed warning branch turns both assertions RED,
# restored). Confirmed by two independent runs (both 1674, 0 FAIL).
#
# 1674 -> 1676: same ticket, remediation round 5 — 2 new checks covering Vera's PR #69 review
# round-2 finding that pmLibDelete's `await invoke("view")` had no timeout: on Backend::Remote,
# ControlClient::command (selahcue-lan/src/client.rs) has no per-request timeout on this path
# (unlike connect/pair, which do), so a stalled-but-connected host would hang the whole delete
# flow forever — no spinner, no error. Added PM_VIEW_TIMEOUT_MS (1500 ms) via a small
# pmWithTimeout() wrapper; expiry is treated as the same planRefUnknown state the earlier
# rejection fix already added. New test hook (window.__viewHangOnce, a promise that never
# settles) proves the timeout is what moves the UI on, not the mock resolving late. Mutation-
# verified (removing the pmWithTimeout wrapper turns both new assertions RED, restored).
# Confirmed by two independent runs (both 1676, 0 FAIL).
#
# 1625 -> ?: ClickUp 17tnw2axptw (Settings: About & Licensing + Appearance pages, SET-007/SET-004),
# authored in parallel on its own branch against the same 1625 baseline as the two entries above
# and merged into main separately — this branch's own history did not record a comment for its
# +31 checks (`list_translations` fixture + the new Settings pages' assertions) before merging;
# recorded retroactively here at merge time instead of left silent. Per this comment block's own
# repeatedly-stated discipline, the number below is the empirically re-run total after resolving
# this merge, not a hand sum of the two branches' deltas.
#
# 1625 -> ?: ClickUp 17tnw2axptw (Settings: General + Scripture & Translations pages, SET-001/
# SET-002), authored as PR #70, genuinely stacked on the About & Licensing + Appearance branch
# above (not independently branched from 1625) — its own pre-merge count of 1689 already included
# that branch's +31 (plus a remediation round for Cody's and Quinn's PR #70 review findings on top).
# A first resolution attempt hand-summed 1625 + main's 82 + this branch's naive (1689-1625=64) and
# got 1771 — wrong, by exactly 31, because that arithmetic double-counted the shared +31 both
# branches carry. This constant's own history has made the same category of mistake before for the
# same reason (see the 1596 and 1605 entries above); the fix is the same each time — empirically
# re-run, don't hand-derive. Confirmed by a clean run: 1740, 0 FAIL.
#
# 1625 -> ?: ClickUp 17tnw2axptw (Settings: Outputs & Displays + Security + Storage & Backups +
# SET-009, SET-003/SET-005/SET-006/SET-009), authored as PR #71, genuinely stacked on the General
# + Scripture & Translations branch above (which is itself stacked on About & Licensing +
# Appearance) — its own pre-merge count of 1717 already included both ancestor branches' checks.
# Not hand-summed at all this time, per the lesson recorded immediately above: empirically re-run
# after resolving instead. Confirmed by a clean run: 1768, 0 FAIL.
#
# 1768 -> 1788: this branch adds GO-LIVE-HOVER / TIMER-START-HOVER (.tb-golive/.timer-start kept
# `filter: brightness(1.06)` on :hover after their rest gradient was darkened — the exact
# regression Sana's PR #58 review flagged as "unmeasured" for these two buttons specifically,
# including her own filter-guard check pattern, carried over here). Rebased onto main post-1768
# with a real conflict in this exact block (the pattern this comment keeps warning about) — per
# its own repeated lesson, re-derived empirically after resolving rather than hand-summed. Three
# independent runs against the real post-rebase tree all reported 1788, 0 FAIL.
#
# 1768 -> ?: ClickUp SET-010 (sermon-prep Generate panel gradient-hover contrast), authored in
# parallel on its own branch against the pre-17tnw2axptw baseline (1544) and rebased onto main
# twice — first onto PR #58 (1520->1544, above), then onto this branch's own PR #68/#70/#71 stack
# (1544->1768, above) — this entry's starting point is 1768, not either of those. 18 new PP-GEN
# assertions (.pp-generate/.pp-optin-btn/.pp-gen-preview-confirm gradient-hover contrast,
# mirroring the existing PME-005/CON-046 pattern). Per this comment block's own repeatedly-stated
# discipline, not hand-summed — empirically re-run after resolving this rebase instead.
# Confirmed by a clean run: 1786, 0 FAIL.
#
# 1786 -> 1791: Sana's PR #60 review found the exact PSC-005 trap (above) reproduced on
# .pp-generate[disabled]: moving hover from filter:brightness() to a flat background broke the
# disabled rule's neutralisation (equal specificity, no background of its own), so a disabled or
# aria-busy Generate button visibly flipped to the active fill on hover. Fixed the same way as
# .ps-start:disabled — the disabled rule now re-declares the REST gradient explicitly — and added
# the same two-check PSC-005 pattern (disabled rule declares its own background; that background
# is exactly the REST fill). Mutation-verified (reverting the disabled rule's background turns
# exactly 1 assertion RED, 1790/1 FAIL; a second dependent assertion goes unreachable, matching
# PSC-005's own `if (wPsDisabledBg && wPsBaseBg)` shape). Confirmed by a clean run: 1791, 0 FAIL.
#
# 1791 -> 1796: Cody's PR #60 re-review found the same PSC-005 trap reproduced a third time on
# .pp-gen-preview-confirm: that class is shared by the transient Confirm button (never disabled)
# and the edit-draft Save button (settings.js/transcripts.js set disabled + aria-busy="true" while
# saving), and there was no .pp-gen-preview-confirm[disabled]/[aria-busy="true"] rule at all, so
# the :hover fill this same PR added had nothing to lose to on a disabled/saving Save. Fixed by
# re-declaring the REST-state flat background explicitly (flat --sc-primary, not a gradient, so
# the fix mirrors .ps-start:disabled's flat sibling rather than .pp-generate[disabled]'s two-stop
# case), with the same opacity/cursor as .pp-generate[disabled] for consistency within this block.
# Added the same two-check PSC-005 pattern (disabled rule declares its own background; that
# background is exactly the REST fill). Mutation-verified (reverting the disabled rule's
# background turns exactly 1 assertion RED, 1795/1 FAIL; the dependent equality assertion goes
# unreachable, same shape as the two priors above). Confirmed by a clean run: 1796, 0 FAIL.
#
# 1796 -> ?: rebased onto main's own GO-LIVE-HOVER/TIMER-START-HOVER fix (1768->1788 above,
# `.tb-golive`/`.timer-start` — the follow-up this branch's own comments repeatedly deferred to a
# separate ticket, landed by a peer session while this PR was in review). Real conflict in this
# exact block again — per this comment's own repeated lesson, re-derived empirically after
# resolving rather than hand-summed. Confirmed by a clean run: 1816, 0 FAIL.
#
# 1816 -> 1818: Sana's independent security review of PR #75 (comment on 17tnw2axweu) found that
# PR #75 fixed `_lastFilterDecl()` reading only the FIRST `filter:` declaration inside an
# already-found rule body, but every rule-lookup ABOVE it in this file — the ones that find the
# RULE BLOCK itself — had the identical bug one level up: a non-global `.exec()` only ever returns
# the FIRST matching rule block for a selector, while the CSS cascade applies whichever
# same-specificity block appears LAST. Not currently live (each guarded selector has exactly one
# real rule today), but the same latent gap as PR #75's, confirmed pre-existing and correctly
# scoped out of that PR since it spans a much broader set of call sites: .pm-btn-primary:hover,
# .td-save-cta:hover, .ps-start:hover/:disabled/(base), .dl-btn-primary:hover, .tb-golive:hover,
# .timer-start:hover, the PME-006-011 muted-text loop, and — rebased onto main's SET-010 PP-GEN
# block above, landed by a peer session while this branch was in review, real conflict in this
# exact block again — the SAME bug on the 7 PP-GEN sites that block just added
# (.pp-optin-btn:hover, .pp-generate:hover/[disabled]/(base), .pp-gen-preview-confirm:hover/
# [disabled]/(base)). Routed all sixteen sites through one `_lastRule()` helper (matches globally,
# keeps the last hit — same technique as `_lastFilterDecl()`), and added a RULE-REGEX-LASTMATCH
# mutation-proof check pair (+2) proving it: a duplicated-selector rule fed through the shared
# helper correctly resolves to the LAST (cascade-winning) block, while a plain non-global .exec()
# on the same text would have wrongly read the FIRST. Per this constant's own repeated lesson:
# re-derived empirically, not hand-summed. Three independent runs against the real post-rebase
# tree all reported 1818, 0 FAIL.
#
# 1818 -> 1822: ClickUp 17tnw2axptx (Download modal: close remaining DLM-### drift), rebased onto
# main's own GO-LIVE-HOVER/TIMER-START-HOVER/PP-GEN/RULE-REGEX-LASTMATCH block above (1768->1818,
# landed by a peer session while this branch was open) — real conflict in this exact block again.
# Added the DLM-007/DLM-008 block (4 assertions — card + button radius, premise + measurement
# each) that locks in the geometry fix (card 14->16px, button 8->10px). DLM-002/003/004/006
# stayed decision-blocked and got no new assertions; DLM-005 needed no code change. Per this
# comment's own repeated lesson: not hand-summed, re-derived empirically after resolving.
# Confirmed by a clean run: 1822, 0 FAIL.
#
# 1822 -> ?: ClickUp 17tnw2axptt (Service Plan: close PLN-004 — the staged run-sheet row's
# border was solid; the handoff is explicit that staged is green/dashed and only live is
# red/solid). Added exactly 3 checks (a non-vacuousness setup check, the dashed-border assertion,
# and a solid-border control on an unstaged row) right next to the existing C-001 run-sheet
# fixture. Rebased onto main's own GO-LIVE-HOVER/TIMER-START-HOVER + SET-010 PP-GEN +
# rule-lookup-lastmatch chain above (1768->1818) after this branch was authored against the
# earlier 1768 baseline — a real conflict in this exact block, the pattern this comment keeps
# warning about. Per this constant's own repeatedly-stated discipline, 1821 is read off an actual
# clean run after resolving, not hand-summed as 1818+3 (even though it happens to match here).
# Confirmed by two independent clean runs against the real post-rebase tree: 1821, 0 FAIL.
#
# 1821 -> 1824: Vera's PR #83 performance review found a real correctness bug the PLN-004 fix
# above made WORSE, not a performance regression: Command::GoLive (selahcue-app/src/
# controller.rs) sets live_idx = staged_idx but never clears staged_idx, so the row that just
# went live carries BOTH is_live and is_staged classes on every ordinary Go Live — not a
# contrived case. .is-live/.is-staged had equal CSS specificity and .is-staged was declared
# second, so it won the cascade: the item actually on air rendered with Preview's colour (a
# pre-existing bug) and, after this PR's own change, Preview's dashed shape too — worse, not
# better. Fixed by scoping the staged rule to `:not(.is-live)` so Live always wins an overlap
# (app.css). Added 3 new checks in an isolated fixture (not the shared C-001 one, to avoid
# disturbing its own item-count/index assertions): a non-vacuousness setup check proving a
# live+staged row genuinely carries both classes, the solid-border assertion, and a border-colour
# control against a live-only row. Mutation-verified by reverting the `:not(.is-live)` guard and
# re-running: exactly the 2 new assertion checks (border-style and border-colour) went RED, none
# of the other 1822 checks moved, then restored. Confirmed by two independent clean runs against
# the real post-fix tree: 1824, 0 FAIL against this branch's own baseline (1818, pre-Download-
# modal-merge). Re-derived below against the actual merged tree instead of trusting that number.
#
# 1828 -> 1843: ClickUp 17tnw2axpta (Console: blackout footer + STAGED-pill contrast, PR #66),
# authored back near the 1625 baseline (well before this file's history above existed in its
# current form) and now finally rebased in. Own contribution: CON-054 (a real STAGED pill,
# rewritten mid-review after Cody found the first version gated on `.verse.cursor` — which moves
# for every browse gesture including the deliberately read-only ones — to instead gate on the
# host's own `staged_scripture` readback via a new `syncStagedPill()`) and CON-098 (the emergency
# footer's background/border genuinely re-tint on a real blackout engage/restore round trip).
# Both mutation-verified at authoring time. Per this constant's own repeated lesson: re-derived
# empirically below, not hand-summed against this branch's own long-stale prior count (1640).
# Confirmed by a clean run: 1843, 0 FAIL. (This is the last entry the `main` side of this history
# had reached at the point PR #79 below was rebased onto it. PR #85's own console-recovery work
# below was authored, remediated, and once rebased against this same 1843-era lineage,
# independently of PR #79 — the two chains are separate history from the same commit until the
# merge entry below that reconciles them.)
#
# 1818 -> 1819 (PR #79, against ITS OWN pre-rebase branch, not yet combined with the 1843 chain
# above): a second, independent finding from the SAME PR #75 review (Sana) was that even a
# global, last-match regex is the wrong mechanism — it is blind to any spelling the browser
# normalises but the regex's literal string does not (a vendor-prefixed `-webkit-filter`, the
# native property name on the WebKit engines Tauri ships, or a CSS-escaped property name). Her
# recommendation: read the browser's own parsed CSSOM instead of the source text. This removes
# `_lastRule()`/`_lastFilterDecl()` and the RULE-REGEX-LASTMATCH check pair entirely — CSS_SRC now
# also injects app.css into an inline `<style id="__css_probe__">` (inline, so unlike the real
# `<link>`-loaded app.css it carries no file:// origin for Chrome to refuse `.cssRules` against)
# and exposes `__cssRule`/`__cssBg`/`__cssFilter` as globals that read that CSSOM directly,
# closing both the duplicate-rule gap (walking rules in source order and keeping the LAST selector
# match) and the vendor-prefix/escape gap (through `CSSStyleDeclaration`, which normalises both)
# with the same mechanism. Replaces RULE-REGEX-LASTMATCH with CSSOM-PARSE-01/02, which insert the
# same kind of adversarial CSS directly into the probe sheet. Confirmed by three independent clean
# runs against PR #79's own pre-rebase tree: 1819, 0 FAIL.
#
# 1819 -> 1822 (PR #79, still against its own pre-rebase branch, not yet combined with the 1843
# chain above): Sana's independent PR review of the CSSOM migration above found the new mechanism
# traded the two closed gaps for a THIRD one it introduced: Chrome drops a whole declaration
# outright when it cannot parse the value (an unsupported/malformed filter function, or a vendor
# prefix — `-webkit-backdrop-filter` among them — it does not alias), verified live
# (`rule.style.cssText` comes back empty), so `__cssFilter` reports NONE for it exactly as if it
# had never been written — and NONE is the PASSING state every "carries no filter" guard relies
# on. No CSSOM read can see a declaration the parser discarded; only the raw source text still has
# it. Added `__cssRawHasFilter()` (built on a new `__cssRawBlock()` primitive) as a
# belt-and-suspenders backstop scanning `window.__CSSTEXT` for the rule's own block, independent of
# whether the value parses, and wired it into all five filter guards (TD-012/PSC-005/GO-LIVE-HOVER/
# TIMER-START-HOVER/PP-GEN) alongside the CSSOM read — neither mechanism alone is sufficient, since
# the text scan is exactly what cannot see a CSS escape. Same review also found `__cssRule`'s
# last-match tie-break mirrors SOURCE ORDER only, not the cascade: a duplicate inside an
# `@media`/`@supports` block that does not currently match could silently outrank one that does
# (latent today — no guarded selector is duplicated inside a conditional group rule — but a
# plausible future mistake, since most of this file's own `@media` blocks are
# `prefers-reduced-motion: reduce`, which never matches in headless Chrome). `_cssFlatten()` now
# tracks whether every enclosing conditional group rule's condition currently holds and drops a
# rule under a false one from candidacy. Adds CSSOM-PARSE-03 (the filter backstop; proven
# mutation-proof by making `__cssRawHasFilter` a no-op and watching exactly that check go red) and
# CSSOM-PARSE-04 (the `@media` tie-break; proven the same way by removing the media-matching
# check). Confirmed by three independent clean runs against PR #79's own pre-rebase tree: 1822,
# 0 FAIL.
#
# Rebase-merge (this commit): PR #79's CSSOM migration (the two entries just above, computed
# against its own 1818 pre-rebase baseline) combined with everything the `main` side of this
# history had independently landed while PR #79 was in review (Download modal, Service Plan
# PLN-004 + Vera's live/staged border fix, and the Console blackout-footer/STAGED-pill batch —
# the 1818 -> 1843 chain above). Per this constant's own repeatedly-demonstrated lesson (the
# words "re-derived empirically, not hand-summed" appear on nearly every entry above for exactly
# this reason), this number was NOT assumed to be 1843 + (1822 - 1818) = 1847 just because that
# arithmetic is available — PR #79 also DELETES checks the `main` chain never saw removed (the 2
# RULE-REGEX-LASTMATCH checks PR #79's first commit above retires) as well as adding new ones
# (CSSOM-PARSE-01..04), so a naive sum across two independently-evolved branches is exactly the
# failure mode this comment block warns against even when — as it turns out here — it happens to
# land on the same number. Read off three independent clean runs of the actual fully-merged tree
# instead, all agreeing: 1847, 0 FAIL.
#
# Rebase #2 (this commit): PR #72 landed on `main` (as an exact-match gate: `if count !=
# EXPECTED_MIN_CHECKS`, replacing the old `<` floor a few lines below this constant) while this
# branch's first rebase-merge above was still open for review — three more commits ahead. Picked
# up cleanly: PR #72's own diff touches only the comparison operator and its surrounding comment,
# not this history block, so it auto-merged with no conflict here. Re-ran anyway per this
# constant's own standing rule (never assume a clean rebase means the count is still right): three
# more independent clean runs, all still 1847, 0 FAIL — the count itself did not move, only the
# gate got strictly less forgiving (this file's own review round on this rebase used exactly that
# stricter gate to catch that the branch was stale in the first place, three commits behind
# `main`, before this rebase).
#
# 1847 -> 1852: Sana's independent re-review of this rebased branch (round 2) found the CSSOM
# migration's own follow-up fix (the 1819 -> 1822 entry above) traded its two closed gaps for
# three smaller new ones. Two were addressed here (the third, NEW-2, is a pre-existing gap on
# `main` too — not a regression — and is tracked as a follow-up instead of blocking this branch):
# NEW-1 (Medium) — `__cssRawBlock()`/`__cssRawHasFilter()` scan raw CSS TEXT and have no notion
# that a comment isn't code, proven both directions on shapes this file's own comments already
# use (a trailing historical comment shaped like `<selector> { ... }` became the "last match" and
# masked a real, currently-unparseable `filter:` declaration in the rule above it; a comment
# merely documenting a removed filter, with no real rule at all, tripped a false FAIL). Fixed by
# stripping `/* ... */` comments before scanning — the same property every regex this file used
# before the CSSOM migration already had, restored here for the one part of the migration that is
# still a text scan. Adds CSSOM-PARSE-05 (+3: the premise, the false-green case, the false-red
# guard). NEW-3 (Low) — a check that only calls `__cssRawHasFilter` in isolation pins the
# PRIMITIVE, not the WIRING: Sana proved live that deleting the `&& !window.__cssRawHasFilter(...)`
# conjunct from all five real filter guards left every check (CSSOM-PARSE-03 included) green,
# since nothing then routed through the primitive at all. Fixed by moving the composed
# CSSOM-plus-raw-text predicate into two shared functions (`__cssFilterGuardOk` for
# TD-012/PSC-005/GO-LIVE-HOVER/TIMER-START-HOVER's "no filter, or exactly none" shape;
# `__cssNoBrightnessFilter` for PP-GEN's narrower "no re-lightening brightness()" shape, per
# Cody's PR #79 round-1 note that this site's intent was always narrower than its siblings') that
# all five real call sites now call instead of inlining their own copy of the expression — there
# is no longer a separate per-call-site conjunct to silently drop without visibly deleting the
# call to a shared function, and pinning that function directly is therefore a guarantee about
# what the real guards evaluate. Adds CSSOM-PARSE-06 (+2). Mutation-tested each fix independently:
# reverting only the comment-strip reproduced exactly the 2 CSSOM-PARSE-05 comment-shape checks
# FAIL (its premise check still passed) and nothing else; reverting only the shared-helper's
# backstop conjunct reproduced exactly 1 FAIL (CSSOM-PARSE-06's first assertion) and nothing else;
# restoring each returned to 0 FAIL. Per this constant's own repeated lesson: re-derived
# empirically, not hand-summed (1847 + 3 + 2 = 1852 checks out here, but that arithmetic was
# verified against three independent clean runs, not assumed from it). All three reported:
# 1852 checks, 0 FAIL.
#
# 1818 -> 1853: 17tnw2axptc (CON-156/157/158/161/162/163/172/173/176/177 — console recovery &
# reliability states, PR #85), authored on its own branch against the 1818 baseline, independently
# of and concurrently with the 17tnw2axpta CON-054/CON-098 work immediately above (PR #66) — the
# two branches did not know about each other. Added coverage for the NDI rejection/unavailable
# messages (CON-156/157/158, including a real set_ndi_output mock — previously a no-op stub, now
# genuinely mutates V.screens[].config so the client-side duplicate-name refusal can be tested
# against it), the blackout-state monitor-pill re-tint (CON-161, plus the CON-162 divergence
# control proving Preview's own surface is never painted black), and the console's scoped
# empty-plan state (CON-172/173). Re-derived empirically, not hand-summed, after two real
# debugging detours this constant's own history already warns about: (1) a memoization-key
# omission (view.ndi_available was not part of renderOutputs' rebuild key, so a host-reported
# change to it alone never re-rendered the inspector — CON-158 FAILed until fixed), and (2) the
# newly-real set_ndi_output mock leaving "main"/"stream" genuinely broadcasting after the NDI
# block, which leaked into Pre-service Check's own NDI readiness probe (preservice.js:96-106) and
# flipped its passed-count in an unrelated, later check — fixed by resetting both screens' NDI
# config at the end of the NDI block. Confirmed by two independent clean runs against this
# branch's own pre-rebase tree: 1853, 0 FAIL.
#
# 1853 -> 1858: PR #85 review remediation (Cody, Code Reviewer), authored on the same branch,
# still against its own 1818-baseline lineage, before this branch had ever been rebased onto the
# concurrent PR #66 work above. commitNdi mirrored 2 of the host's 3 refusal rules (empty name,
# duplicate name) but not ndi_name_valid's control-character/length check, so a pasted name with a
# stray control character still hit the exact silent-revert failure mode this PR exists to close —
# added the third check (+3: refused-client-side, message shown, toggle stays unchecked) and a
# role=status check on the signal line (+1, a second finding from the same review: the div's job
# changed from passive status to active validation feedback, so it needs an announced live region
# or a refusal is silent to screen readers). Separately, the CON-173 empty-state's "Import —
# coming soon" button was found to mislabel a shipped capability (the Service Plan surface's real
# "Import a run sheet…" importer) as unbuilt — the two existing assertions for it were REPLACED
# (not added to) with corrected ones once the copy/behaviour was fixed to route to the real
# importer, which is why the net change here is +5 rather than +7. Every new/changed assertion
# mutation-tested (broken, confirmed RED, restored) before this number was re-derived. Confirmed
# by two independent clean runs against this branch's own pre-rebase tree: 1858, 0 FAIL.
#
# 1843 / 1858 -> 1883: rebase of PR #85 (ending at 1858 on its own, pre-rebase lineage above) onto
# current origin/main (ending at 1843 via PR #66's CON-054/CON-098 work, itself since overtaken by
# further unrelated PRs merged to main — Settings/Network, Outputs, Storage and Security page
# coverage among them, none of which touched this exact conflict block and so merged cleanly)
# — 2026-09-23. The two known lineages' own totals do not simply add (both were counted from the
# same 1818 ancestor along divergent paths, and main picked up still more checks neither lineage
# ever saw), so per this constant's own repeatedly-stated discipline the merged count is read off
# an actual clean run against the real post-rebase tree, not hand-summed as 1843 + 40 or any other
# arithmetic shortcut. Confirmed by two independent clean runs against the real post-rebase tree:
# 1883, 0 FAIL.
#
# 1852 & 1883 -> 1892: merge of origin/main into PR #85 (17tnw2axptc) — 2026-09-24. Since this
# branch's own previous rebase (the entry immediately above, ending 1883), origin/main gained
# two further merges: PR #79's full CSSOM-migration chain (the chain above, ending 1852 — the
# same PR #79 this branch's own history already knew was "rebased onto" the shared 1843
# fork point, now shown here in full) and PR #86 (mobile: wire LiveController.busy into every
# act()-triggering control). Checked directly rather than assumed: `git log origin/main ^HEAD --
# scripts/operator_headless.py` before resolving this conflict showed exactly PR #79's 4 commits
# touching this file and nothing from PR #86 — PR #86 touches only
# implementation/mobile/selahcue_controller and contributes no change to this count. Resolved as
# a merge (not a further rebase) specifically to avoid re-resolving this same block three more
# times against inconsistent intermediate per-commit states, one for each of this branch's own
# 3 commits — a real failure mode hit and abandoned earlier in this exact merge attempt. Per
# this constant's own repeated lesson, the combined total was NOT assumed to be either chain's
# endpoint (1852 or 1883), their sum, or their difference: it was read off real runs of the
# actual fully-merged tree. Confirmed by two independent clean runs against the real post-merge
# tree, both agreeing: 1892 checks, 0 FAIL.
# 1892 -> 1897: ClickUp 17tnw2axptr (Theme Designer TD-### drift closure). Of the 11 open
# findings audited, only TD-010 (the Typography section's text-colour swatch showing a static
# "Text colour" label instead of the live value) was a genuine, non-blocked gap — TD-001/002
# (save-theme)/003-009/012 were confirmed already matching/intentional/already-fixed on the live
# tree, and TD-002 (templates)/TD-011 (region alignment) are blocked on the still-open decision
# ticket 17tnw2axpu4 (TD-OQ-3/TD-OQ-4) and were deliberately left untouched. The TD-010 fix (a
# live #td-color-hex readout, mirroring the already-shipped #td-bg-hex pattern) added 5
# assertions: a DOM premise, a model-commit premise, a live-on-input check, a region-switch
# re-sync check, and a control proving the readout isn't a frozen/stale label. Mutation-tested:
# reverting the three fix files (app.css/app.js/index.html, test script unchanged) reproduces a
# clean single FAIL on the premise check (1893 checks, 1 FAIL, no aborting exception — the
# premise-guarded block is skipped rather than dereferencing a null element); restoring reproduces
# 1897 checks, 0 FAIL. Measured directly off real runs, not hand-summed.
#
# 1897 -> 1901 (17tnw2axwve, rebased onto the 1897 baseline above): +9 new checks for the
# deck-scoped pmThumbCache / LIVE-ring fix (two decks sharing a local slide id, switched via both
# pmLibOpen and pmLibPresent). This branch's own checks were originally measured at 1901 against a
# pre-17tnw2axptr baseline (1892 + 9); after rebasing onto 17tnw2axptr's +5, the combined total is
# NOT assumed to be either chain's endpoint, their sum by arithmetic, or any other derivation — per
# this constant's own repeated lesson (see the merge-conflict resolution note above it).
#
# 1901 -> 1906 (17tnw2axwve, PR #92 review round 1, Vera): +5 new checks — a bounded-memory test
# for pmThumbCache was missing (root CLAUDE.md requires one for changed buffering code); Vera wrote
# it (window.__pmGridDebug inspection hook + a check driving 70 distinct (deck, slide) pairs
# against the PM_THUMB_MAX=60 cap), mutation-verified in her own isolated review worktree before
# this session applied it here.
#
# 1906 -> 1911 (17tnw2axwve, PR #92 review round 1, Sana + Cody + Vera + Quinn): +5 new checks for
# two further gaps all four reviewers independently found in round 1 and this session fixed for
# real (not deferred):
#   - The LIVE-ring gate was redesigned from dv.live (DeckWorkspace.live — deck-EDITING-session
#     scoped, reset by deck_workspace.rs::load_deck on every real deck switch, including switching
#     BACK to a still-genuinely-live deck; also never set at all by a plan-driven present) to
#     pmLiveAuthoredDeckId, tracking deck ownership purely from actions this client itself observed
#     succeed. +3 checks: the A→B→A same-session revisit (the routine case the old design broke),
#     the Service-Plan/Live-Console cross-surface present, and re-sequencing the existing
#     cross-deck-collision check so it still runs cleanly alongside the new ones.
#   - The "Done" (editor→grid) handler trusted a possibly-stale pmGridDeckId whenever the open deck
#     changed via a path that never calls pmRenderGrid ("+ New presentation", duplicate, or the
#     host auto-switching away from a just-deleted open deck) — silently resurrecting the exact
#     thumbnail collision this ticket exists to close. Fixed by asking deck_list for ground truth
#     (its `open` field is computed live from ws.open_deck().id() on every call) instead of
#     trusting the tracked value. +2 checks (a premise + the actual collision-freedom assertion).
# Every behavioural fix in this round is mutation-verified (revert the fix, confirm the RIGHT
# assertion(s) go RED with no collateral failures, restore).
#
# 1911 -> 1916: rebased onto 17tnw2axptr's 1897 baseline (see above), whose +5 and this branch's
# own +19 (9+5+5, see above) touch disjoint areas of this file — re-measured for real post-rebase
# by two independent clean runs, both agreeing: 1916 checks, 0 FAIL. Confirms, not assumes, that
# the sum was the right combined total.
EXPECTED_MIN_CHECKS = 1916


def find_chrome():
    """Locate a Chrome/Chromium binary across dev (macOS) and CI (Linux)."""
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ):
        found = shutil.which(name)
        if found:
            return found
    for path in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(path):
            return path
    return None


CHROME = find_chrome()
if CHROME is None:
    require = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"
    msg = "no Chrome/Chromium found (set CHROME_BIN or install google-chrome)"
    if require:
        print("FAIL: SELAHCUE_HEADLESS_REQUIRE=1 but " + msg)
        sys.exit(3)
    # LOUD skip so it is never misread as "the webview gate passed" (e.g. under `make ci`,
    # whose final ALL-GREEN banner covers only the gates that actually ran). CI sets
    # SELAHCUE_HEADLESS_REQUIRE=1, so this graceful path is dev-box-only.
    print("=" * 68)
    print("!! WEBVIEW BEHAVIOURAL GATE SKIPPED — " + msg)
    print("!! (install Chrome or set CHROME_BIN to run it; CI runs it with REQUIRE=1)")
    print("=" * 68)
    sys.exit(0)

html = open(os.path.join(DIST, "index.html")).read()

# Settings/General (17tnw2axwet, SET-001) marks "Live Console" as the selected "on launch, open
# to" startup option — an honest claim only because it's true: #surface-console really does carry
# `active` at rest in the shipped markup (never asserted against the live DOM inside the browser
# driver below, since by the time that block runs many earlier checks have already navigated
# elsewhere, so the live .active class would no longer reflect the boot-time default). Checked
# here, once, against the pristine source, before Chrome even starts — an INFRA-level precondition
# a real behavioural check depends on, not a behaviour of the running app itself.
if 'id="surface-console" class="surface-page active"' not in html:
    print(
        "FAIL: Settings/General's 'Live Console is the real startup default' claim no longer "
        "holds — #surface-console's active class moved (or its markup changed) without updating "
        "settings-general.js's STARTUP_OPTIONS"
    )
    sys.exit(2)

# The real app.css text, handed to the driver as a string AND (see CSS_SRC below) injected into
# an inline `<style id="__css_probe__">` so the driver can read it as parsed CSSOM. Sana
# (security review, PR #75 and its follow-up) found the regex approach this used to be limited
# to has two related gaps: a regex keyed on a selector's text only ever finds the FIRST matching
# rule block, so a selector declared twice would silently read whichever declaration comes
# first while the browser's cascade applies whichever comes LAST; and it is blind to any
# spelling the browser normalises but the regex's literal string does not — a vendor-prefixed
# `-webkit-filter` (the actual property name on the WebKit engines Tauri ships — WebKitGTK on
# Linux, WKWebView on macOS) or a CSS-escaped property name both parse to the exact same
# `filter` a plain spelling would. Her recommendation, verified live in Chrome: read the
# browser's own parsed CSSOM instead of the source text — `rule.style.filter` normalises every
# spelling, and enumerating rules in source order and keeping the LAST selector match mirrors
# the cascade's own tie-break. Chrome refuses `document.styleSheets[i].cssRules` for the real,
# `<link>`-loaded, file://-origin app.css (SecurityError — a rule that only exists in a
# pseudo-class state like `.pm-btn-primary:hover` is unreachable from the live DOM either way),
# but an INLINE `<style>` carries no such restriction (proven live: the same page, the same
# file:// origin, throws for the `<link>` sheet and not for an inline one). CSS_SRC therefore
# also creates `__css_probe__` from the identical CSS text and exposes `__cssRule(selector)`
# (the last-match-wins lookup), `__cssBg(rule)` and `__cssFilter(rule)` (the normalised
# `background`/`filter` off a matched rule) as globals. The VALUE a lookup returns is then run
# back through the live CSS engine (an inline `background-color: var(--token)` on a probe
# element, in `_resolve()` below), so `var()` is followed rather than string-matched and a
# token rename still cannot fake a pass.
# Cody L6 — the two JS constants in dist/app.js are hand-transcribed copies of host constants in
# selahcue-core. This repo already pins one cross-language copy (test_protocol.rs pins the Dart
# fixtures byte-for-byte against the Rust shapes) precisely because a copy drifts silently. The
# values are read out of plan.rs here and handed to the driver, so moving either constant without
# moving the client fails this gate.
#
# BOTH lookups are hard failures. The name bound was `MAX_PLAN_NAME_LEN` while PR #14 was in
# flight and is `MAX_PLAN_LABEL_LEN` now that it has landed (the host applies one rule to a plan
# name, an item title and an owner, so it stopped calling the bound a "name" one). An earlier
# version of this pin tolerated a missing constant by passing when the lookup returned None --
# which is exactly what the rename produced: a check that could no longer fail, guarding a
# constant nobody was checking. A pin with an escape hatch is not a pin.
_PLAN_RS = os.path.join(
    _REPO, "implementation", "desktop", "crates", "selahcue-core", "src", "plan.rs"
)


def _rust_const(name):
    """The integer value of `pub const <name>: <ty> = <n>;` in plan.rs, or None if absent."""
    try:
        src = open(_PLAN_RS).read()
    except OSError:
        return None
    m = re.search(r"pub const " + name + r"\s*:\s*\w+\s*=\s*(\d+)\s*;", src)
    return int(m.group(1)) if m else None


_MAX_PLAN_ITEMS = _rust_const("MAX_PLAN_ITEMS")
if _MAX_PLAN_ITEMS is None:
    print("FAIL: could not read MAX_PLAN_ITEMS out of selahcue-core/src/plan.rs — the "
          "cross-language pin cannot be vacuous, so this is a hard failure")
    sys.exit(3)
_MAX_PLAN_LABEL_LEN = _rust_const("MAX_PLAN_LABEL_LEN")
if _MAX_PLAN_LABEL_LEN is None:
    print("FAIL: could not read MAX_PLAN_LABEL_LEN out of selahcue-core/src/plan.rs — the "
          "constant the client's PLAN_NAME_MAX copies. If it was renamed again, follow it "
          "here; do not soften this to a null-tolerant check, which is how the previous "
          "rename went unnoticed")
    sys.exit(3)


# Quinn Q-N1 — the client's PLAN_DISPLAY_HOSTILE regex is a hand-transcribed mirror of the
# host's `is_display_hostile` + `is_line_separator`. It used to be checked against an ELEVEN
# code-point sample typed out beside it, and every one of those eleven was a range ENDPOINT,
# which is the same failure mode that let the original defect ship (a sample of five scripts,
# none of which needed a joiner). Narrowing `\u202A-\u202E` to `[\u202A\u202E]` drops U+202D LRO,
# a Trojan-Source primitive, and the sample could not see it: 1119 checks, 0 FAIL. So the ranges
# are read out of plan.rs HERE and every code point inside them is swept, exactly as the two
# integer constants above are read rather than retyped. A sample cannot see interior drift.
def _rust_char_ranges(fn_name):
    """Inclusive (lo, hi) code-point ranges matched by `fn <fn_name>(c: char) -> bool` in plan.rs.

    Reads the `matches!` arms literally: `'\\u{202A}'..='\\u{202E}'` is a range and a bare
    `'\\u{200B}'` is a one-code-point range. Returns None if the function cannot be found, which
    the caller treats as a hard failure — a mirror check that silently sweeps nothing is worse
    than no check, because it reports "all clear" forever.
    """
    try:
        src = open(_PLAN_RS).read()
    except OSError:
        return None
    m = re.search(r"fn " + fn_name + r"\(c: char\) -> bool \{(.*?)\n\}", src, re.S)
    if not m:
        return None
    # The arms carry `// LRE, RLE, PDF, LRO, RLO`-style comments naming the characters; a comment
    # must not be read as an arm.
    body = re.sub(r"//[^\n]*", "", m.group(1))
    pair = r"'\\u\{([0-9A-Fa-f]+)\}'\s*\.\.=\s*'\\u\{([0-9A-Fa-f]+)\}'"
    ranges = [(int(lo, 16), int(hi, 16)) for lo, hi in re.findall(pair, body)]
    # Whatever is left once the ranges are removed is a singleton arm.
    for cp in re.findall(r"'\\u\{([0-9A-Fa-f]+)\}'", re.sub(pair, "", body)):
        ranges.append((int(cp, 16), int(cp, 16)))
    return sorted(ranges)


_HOSTILE_RANGES = _rust_char_ranges("is_display_hostile")
_SEPARATOR_RANGES = _rust_char_ranges("is_line_separator")
if not _HOSTILE_RANGES or not _SEPARATOR_RANGES:
    print("FAIL: could not read is_display_hostile / is_line_separator out of "
          "selahcue-core/src/plan.rs — the client's PLAN_DISPLAY_HOSTILE mirrors both, and a "
          "sweep derived from an empty range list would pass forever. If either was renamed or "
          "restructured, follow it here; do not soften this to an empty-tolerant read")
    sys.exit(3)
_HOSTILE_CPS = sorted(
    {cp for lo, hi in _HOSTILE_RANGES + _SEPARATOR_RANGES for cp in range(lo, hi + 1)}
)
# Floor, not an equality: the risk this guards is the range parse SHRINKING (a plan.rs refactor
# the regexes above stop matching), which would make the sweep vacuous while it still says "0
# missed". A host that legitimately narrows its rule lowers this deliberately, in review — the
# same discipline as EXPECTED_MIN_CHECKS. Never lower it to make a red run green.
_MIN_HOSTILE_CPS = 27
if len(_HOSTILE_CPS) < _MIN_HOSTILE_CPS:
    print("FAIL: only %d hostile code points were derived from plan.rs; expected >= %d. Either "
          "the host narrowed its rule (lower this deliberately, and check the client followed) "
          "or the range parse above stopped matching and the sweep has gone vacuous"
          % (len(_HOSTILE_CPS), _MIN_HOSTILE_CPS))
    sys.exit(3)

RUST_CONSTS = (
    "<script>window.__RUST_MAX_PLAN_ITEMS = "
    + json.dumps(_MAX_PLAN_ITEMS)
    + "; window.__RUST_MAX_PLAN_LABEL_LEN = "
    + json.dumps(_MAX_PLAN_LABEL_LEN)
    + "; window.__RUST_HOSTILE_CPS = "
    + json.dumps(_HOSTILE_CPS)
    + ";</script>"
)

CSS_SRC = (
    "<script>window.__CSSTEXT = "
    + json.dumps(open(os.path.join(DIST, "app.css")).read())
    + ";</script>"
    + r"""
<script>
(function(){
  // __cssRule/__cssBg/__cssFilter: see the comment above this constant's Python definition for
  // why this exists and why an inline <style> is the fix. `probe` carries the exact same CSS
  // text as the real, <link>-loaded app.css, but being inline it has no file:// origin for
  // Chrome to refuse .cssRules against.
  var probe = document.createElement("style");
  probe.id = "__css_probe__";
  probe.textContent = window.__CSSTEXT;
  document.head.appendChild(probe);

  // Depth-first flatten so a rule nested inside @media/@supports is still found — .cssRules on
  // a CSSMediaRule/CSSSupportsRule holds its own children, not the plain CSSStyleRules the
  // caller wants to match selectorText against. A plain CSSStyleRule ALSO carries a (usually
  // empty) .cssRules of its own — every style rule supports CSS Nesting now, whether or not
  // app.css actually nests anything — so `r.cssRules` is truthy even for a normal rule and
  // cannot be used as an is-this-a-container test; push every rule with its own selectorText
  // AND separately recurse into cssRules whenever it is non-empty, so both a bare @media
  // wrapper and a rule that is itself nested end up correctly represented.
  //
  // Sana (security review, PR #79 follow-up, finding 2): source order alone is not the
  // cascade's tie-break when a duplicate sits inside a conditional group rule — a rule inside
  // an @media/@supports block that does NOT currently match must not be allowed to win over one
  // that does, even if it appears later in the file (most of app.css's own @media blocks are
  // prefers-reduced-motion:reduce, which never matches in headless Chrome — a plausible future
  // home for a hover override that would otherwise silently win this lookup while the browser
  // never actually applies it). `ok` tracks whether every enclosing conditional group rule
  // currently matches; a rule under a false one is walked (so nothing inside it is lost if the
  // caller ever wants it) but never pushed as a candidate.
  function _cssFlatten(rules, out, ok) {
    for (var i = 0; i < rules.length; i++) {
      var r = rules[i];
      var childOk = ok;
      if (r.media) { childOk = ok && window.matchMedia(r.media.mediaText).matches; }
      else if (r.conditionText && typeof CSS !== "undefined" && CSS.supports) {
        childOk = ok && CSS.supports(r.conditionText);
      }
      if (r.selectorText && childOk) { out.push(r); }
      if (r.cssRules && r.cssRules.length) { _cssFlatten(r.cssRules, out, childOk); }
    }
    return out;
  }
  function _cssNormSel(s) {
    return String(s).replace(/\s*,\s*/g, ", ").replace(/\s+/g, " ").trim();
  }
  // The LAST rule (source order, among those whose enclosing conditions currently match) whose
  // selector matches `sel` once whitespace is normalised — "last" because that is the cascade's
  // own tie-break for equal specificity, so a selector declared twice resolves to whichever
  // rule actually wins, not whichever a lookup finds first.
  //
  // Vera (performance review, PR #79): do NOT memoize this function's `_cssFlatten` call. She
  // measured it, built both an obvious cache (keyed on nothing, invalidated never) and a
  // length-keyed one, and both silently break mutation coverage: the naive cache breaks
  // CSSOM-PARSE-01/02(x2)/04 outright, and the length-keyed one still breaks CSSOM-PARSE-02's
  // CSS-escape case via ABA — `probeSheet.insertRule`/`deleteRule`/`insertRule` (exactly what
  // several checks below do) can restore the rule COUNT while the CONTENTS differ, so a
  // length-keyed cache reuses a stale flatten. The ~13ms this function costs per full suite run
  // is not worth silently disabling the checks that justify this file's entire CSSOM migration.
  window.__cssRule = function(sel) {
    var target = _cssNormSel(sel);
    var rules = _cssFlatten(probe.sheet.cssRules, [], true);
    var match = null;
    for (var i = 0; i < rules.length; i++) {
      if (rules[i].selectorText && _cssNormSel(rules[i].selectorText) === target) match = rules[i];
    }
    return match;
  };
  // The rule's declared background, shorthand first: CSSStyleDeclaration puts a var()-valued
  // `background` shorthand's own longhands (background-color/-image) into a "pending
  // substitution" state where they read back empty, so the shorthand is the only property
  // guaranteed to carry the authored `var(--token)` text these checks resolve afterwards.
  window.__cssBg = function(rule) {
    if (!rule) return null;
    return rule.style.getPropertyValue("background")
        || rule.style.getPropertyValue("background-color")
        || rule.style.getPropertyValue("background-image")
        || null;
  };
  // The rule's declared filter, through the accessor that normalises -webkit-filter (the native
  // property name on the WebKit engines Tauri ships — WebKitGTK, WKWebView) and any CSS-escaped
  // spelling to the same value a plain `filter:` declaration would report.
  window.__cssFilter = function(rule) {
    return rule ? (rule.style.getPropertyValue("filter") || null) : null;
  };
  // Sana (security review, PR #79 follow-up, finding 1): __cssFilter reads real CSSOM, but
  // Chrome drops a WHOLE declaration outright when it cannot parse the value (an unsupported or
  // malformed filter function, or a vendor prefix it does not alias — `-webkit-backdrop-filter`
  // among them) — verified live: `rule.style.cssText` comes back empty, so __cssFilter reports
  // null exactly as if the declaration had never been written, and null is the PASSING state
  // for a "carries no filter" guard. No CSSOM read can see a declaration the browser's own
  // parser discarded; only the raw source text still has it. This is the coarse, deliberately
  // dumb backstop for that: scan window.__CSSTEXT for the rule's own block — matched globally
  // and keeping the LAST occurrence, the same tie-break __cssRule uses — for the literal,
  // case-insensitive substring "filter", independent of whether the declared value parses at
  // all. It does not replace __cssRule/__cssBg/__cssFilter (those still close the duplicate-rule
  // and vendor-prefix/escape gaps this file was regexing before), it only re-covers the one
  // thing reading real CSSOM cannot: a declaration the parser threw away.
  // The last matching rule's raw declaration text for `sel` (source order, mirroring the same
  // tie-break __cssRule uses) straight out of window.__CSSTEXT, or null — independent of
  // whether the browser's parser accepts any of it. The shared primitive `__cssRawHasFilter`
  // below is built on.
  //
  // Sana (security review, PR #79 follow-up round 2, finding NEW-1): this is a raw TEXT scan, so
  // it has no idea a CSS comment isn't code. Proven both directions on the real file's own
  // pre-existing prose (app.css already documents old rules in comments that read exactly like
  // this, e.g. the TD-012/.tb-golive/.pm-btn-primary:hover history note): (a) a historical
  // comment mentioning a `<selector> { ... }` shape AFTER the real rule becomes the "last match"
  // and can mask a genuine, currently-unparseable `filter:` sitting in the real rule right above
  // it — the exact silent-pass this backstop exists to prevent, reopened by a comment; (b) a bare
  // comment mentioning a selector's filter with no `{`/`}` at all (like app.css's own prose) can
  // still be walked into if a later edit ever adds the brace shape, and even short of that, a
  // comment merely mentioning "filter:" near an unrelated selector risks a false FAIL. Strip CSS
  // comments before scanning — the one property that makes a dumb text scan safe against a
  // stylesheet's own prose, which was true of every regex this file used before the CSSOM
  // migration and must stay true of this deliberately-dumb backstop too.
  function _cssStripComments(text) {
    return String(text || "").replace(/\/\*[\s\S]*?\*\//g, "");
  }
  window.__cssRawBlock = function(sel) {
    var escaped = String(sel).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    var re = new RegExp(escaped + "\\s*\\{([^}]*)\\}", "gi");
    var m, lastBody = null;
    while ((m = re.exec(_cssStripComments(window.__CSSTEXT))) !== null) { lastBody = m[1]; }
    return lastBody;
  };
  window.__cssRawHasFilter = function(sel) {
    var body = window.__cssRawBlock(sel);
    return !!body && /filter\s*:/i.test(body);
  };
  // Sana (security review, PR #79 follow-up round 2, finding NEW-3): a check that only calls
  // __cssRawHasFilter directly pins the PRIMITIVE, not the WIRING — it stays green even if a
  // call site's `ok(...)` predicate is edited to drop its `&& !window.__cssRawHasFilter(...)`
  // conjunct, since nothing then routes through the primitive at all. Proven live: deleting that
  // conjunct from all five filter guards left every check (including CSSOM-PARSE-03) green.
  // Fix: the composed CSSOM+raw-text predicate lives in exactly ONE place (here), and all five
  // real guards below call it instead of inlining their own copy of the expression. There is no
  // longer a separate "call site conjunct" to silently drop without visibly deleting the call to
  // this function — and the mutation-proof check on this function directly is therefore a
  // guarantee about what the real guards evaluate, not a parallel copy of it.
  // TD-012/PSC-005/GO-LIVE-HOVER/TIMER-START-HOVER's shape: no filter at all, or exactly `none`.
  window.__cssFilterGuardOk = function(sel, rule) {
    var filterVal = __cssFilter(rule);
    return (!filterVal || /^\s*none\s*$/.test(filterVal)) && !window.__cssRawHasFilter(sel);
  };
  // PP-GEN's own narrower shape (Cody, PR #79 review round 1): only a re-lightening `brightness`
  // filter is disqualifying, not "any filter at all" — a faithful migration of this site's
  // pre-existing intent, not something this fix changes.
  window.__cssNoBrightnessFilter = function(sel, rule) {
    var filterVal = __cssFilter(rule);
    var rawBlock = window.__cssRawBlock(sel);
    return (!filterVal || !/brightness/.test(filterVal)) && !(rawBlock && /brightness/i.test(rawBlock));
  };
})();
</script>"""
)

STUB = r"""
<script>
  window.__calls = [];
  window.__ev = {};          // event name -> [handlers] (Tauri event stub)
  window.__startCtl = null;  // resolve/reject for a pending start_listening
  window.__renderAvailable = true; // flip to test the Remote/older-host text fallback
  // Remote Control device-management mock (86ajxer8n): mirrors the host session registry so the
  // surface's optimistic updates reconcile against consistent snapshots (roles are non-Operator —
  // the host caps remote devices at Producer).
  window.__remote = {
    devices: [
      { device_id: "dev-aa01", name: "Booth iPad", platform: "iPadOS", role: "producer", idle_secs: 3, pinned: false },
      { device_id: "dev-bb02", name: "Guest tablet", platform: "iPadOS", role: "viewer", idle_secs: 210, pinned: false },
    ],
    pending: [
      { device_id: "dev-cc03", name: "Anna's iPhone", platform: "iOS", fingerprint: "A1 B2 C3 D4", waiting_secs: 8 },
    ],
  };
  // A REAL OperatorView so the boot render path (act->render->syncChrome->renderConsole) runs
  // exactly as in the app — the prior null stub masked the #7 render never firing on launch.
  var V = { plan_name:"Svc", items:[{id:1,kind:"scripture",title:"Genesis 1:13",is_live:true,is_staged:true}],
    live_index:0, staged_index:0, blackout:false, live_authored_id:null, timer:null, staged_scripture:"Genesis 1:13",
    live_scripture:"Genesis 1:13", live_free_text:null,
    outputs:[{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080}],
    displays:[{key:"d1", name:"Main", width:1920, height:1080}], translations:["KJV"],
    theme:"classic", themes:["classic"], saved_themes:[], screen_themes:[],
    // Health seams. Real Tauri ALWAYS sends these three keys (OperatorView carries no
    // skip_serializing_if on them), so absent is `null` with the key present — never a
    // missing key. The nested counters DO skip at zero, which is why `output_health` here is
    // {held:false} with no holds/recoveries: that is the exact byte shape
    // test_health_view.rs:177 pins for a healthy controller.
    output_health:{held:false}, storage:null, session:null, ndi_available:null,
    screens:[
      {screen:"main", role:"main", enabled:true, deletable:false, theme:null},
      {screen:"stage", role:"stage", enabled:true, deletable:false, theme:null}
    ] };
  var T = {
    background:{r:8,g:10,b:20,a:255},
    title:{x_permille:60,y_permille:150,w_permille:880,h_permille:110,align_h:"center",align_v:"middle",size_permille:48,line_height_permille:1200,color:{r:242,g:181,b:60,a:255},fit:"shrink_to_fit",visible:true},
    body:{x_permille:60,y_permille:280,w_permille:880,h_permille:560,align_h:"center",align_v:"middle",size_permille:78,line_height_permille:1150,color:{r:255,g:255,b:255,a:255},fit:"shrink_to_fit",visible:true}
  };
  // A DeckView (Presentation & Media, node 329:124) — the separate operator-local shape the
  // deck_* commands return (NOT the OperatorView). The stubs below mutate it so the surface's
  // add/select/edit/undo/media behaviours are exercised end to end.
  var D = {
    name:"Sermon: Grace That Feeds", count:2,
    slides:[
      {id:1, n:1, lines:["Grace That Feeds"], kind:"text"},
      {id:2, n:2, lines:["Isaiah 61:5"], kind:"text"}
    ],
    selected:2, live:null,
    slide:{ id:2, elements:[{index:0,kind:"text",label:"Isaiah 61:5",x:80,y:240,w:700,h:90,z:0,visible:true,
        text:"Isaiah 61:5",size_permille:90,line_height_permille:1100,weight:400,align_h:"left",align_v:"top",
        color:{r:240,g:240,b:245,a:255},fit:"shrink_to_fit",opacity:255}],
      selected_element:null, notes:"read slowly", transition:"fade", auto_advance_secs:null, has_background:false },
    media:{ assets:[
        {id:1,name:"harvest.jpg",path:"demo://harvest field.jpg",kind:"image",size_label:"2.4 MB",width:1920,height:1080,duration_label:null,missing:false,unused:false,uses:2},
        {id:2,name:"sunrise.jpg",path:"demo://sunrise.jpg",kind:"image",size_label:"3.1 MB",missing:false,unused:true,uses:0},
        {id:3,name:"testimony.mp4",path:"demo://testimony.mp4",kind:"video",size_label:"48 MB",duration_label:"2:14",missing:false,unused:true,uses:0},
        {id:4,name:"baptism.jpg",path:"demo://baptism.jpg",kind:"image",size_label:"2 MB",missing:true,unused:false,uses:1},
        {id:5,name:"ambient pad.wav",path:"demo://ambient pad.wav",kind:"audio",duration_label:"3:20",missing:false,unused:true,uses:0}
      ], total_label:"1.2 GB", missing_count:1, unused_count:3 },
    can_undo:false, can_redo:false
  };
  var dClone = function(){ return JSON.parse(JSON.stringify(D)); };
  var dEdit = function(){ D.can_undo = true; D.can_redo = false; return dClone(); };
  // Providers & Privacy (Settings, node 338:124) — the operator-local ProvidersView the
  // providers_* commands return. Mirrors the REAL backend default in a stock build: on-device is the
  // private default, cloud is OFF, cloud_status is "not_configured", notes_available is false,
  // notes_provider is null and quota is null. The driver flips cloud_status / notes_provider / quota
  // to exercise each of the four honest states (86akby7d8).
  //
  // `notes_available` is DERIVED here, exactly as the backend derives it from notes_provider, so the
  // stub cannot drift into a combination the backend can never produce and let a broken renderer
  // pass against it.
  //
  // WARNING: this stub is a HAND-WRITTEN MIRROR of the Rust ProvidersView. It cannot catch a field
  // rename on the backend -- it would simply keep serving the old name and every assertion below
  // would keep passing against a shape production no longer produces. The guards against that are
  // the two Rust tests `the_frontend_contract_field_names_are_pinned` and
  // `the_notes_provider_object_keys_are_pinned` (selahcue-operator/src/main.rs). If either fails,
  // the corresponding names HERE and in dist/settings.js must be changed in the same MR.
  var P = {
    transcription_mode:"on_device",
    on_device:{ready:true, state:"ready", model:"Small", detail:"ggml-small.en.bin"},
    cloud_transcription_consent:false, cloud_notes_consent:false,
    offline_by_default:true, any_cloud_enabled:false,
    notes_template:"full_outline",
    notes_templates:[{value:"full_outline",label:"Full outline + scriptures"},{value:"summary",label:"Short summary"},{value:"bullets",label:"Bullet points"}],
    preferred_translation:"KJV",
    translations:[{code:"KJV",name:"King James Version"},{code:"WEB",name:"World English Bible"},{code:"ASV",name:"American Standard Version"}],
    include:{prayer_points:true, scripture_extraction:true, social_excerpts:false, chapter_markers:true, notable_quotations:true, short_summary:true, podcast_show_notes:false, short_description:false},
    cloud_status:"not_configured", notes_provider:null, notes_available:false,
    account_token_set:false, quota:null,
    // Cloud (Deepgram) transcription readiness (86akby7th) — mirrors notes_provider/notes_available
    // above, same reason: `transcription_available` is DERIVED from `transcription_provider` below,
    // never set independently, so the stub cannot drift into a combination the backend can never
    // produce. Guarded by the Rust tests `transcription_available_is_true_in_the_view_when_a_provider_is_named`
    // and `the_transcription_provider_object_keys_are_pinned` — if either fails, the names here and
    // in dist/settings.js must change in the same MR.
    transcription_provider:null, transcription_available:false
  };
  var ppView = function(){
    P.any_cloud_enabled = !!(P.cloud_transcription_consent || P.cloud_notes_consent);
    // The backend's invariant, mirrored: notes_available is true exactly when a provider is named.
    P.notes_available = !!P.notes_provider;
    // Same invariant, transcription side.
    P.transcription_available = !!P.transcription_provider;
    return JSON.parse(JSON.stringify(P));
  };
  window.__pp = P; // exposed so the driver can flip cloud_status / notes_provider / quota
  // Sermon-note draft persistence mock (86akgqdv0; FR-123 "editable" half). A single-slot store —
  // this harness only ever has one active transcript fixture, mirroring the backend's "one
  // editable draft per transcript" shape. `null` = nothing persisted yet (the real state before
  // any Generate has ever succeeded, or after `load_sermon_note_draft` finds nothing).
  var SN_TRANSCRIPT_ID = 42;
  // `pending` mirrors `sermon_note`'s additive `pending_*` columns (FR-129, 86akgqdx8) — `null`
  // = no regeneration staged. Deliberately a SEPARATE slot from `draft` (the accepted one),
  // never merged into it — the whole point of the real schema this mirrors.
  var SN = { draft: null, pending: null };
  window.__sn = SN; // exposed so the driver can inspect persisted state directly
  window.__TAURI__ = { core: { invoke: function(cmd, args){
    window.__calls.push({cmd:cmd, args:args});
    if (cmd === "builtin_themes") return Promise.resolve([{name:"Classic", theme:JSON.parse(JSON.stringify(T))}]);
    if (cmd === "system_fonts") return Promise.resolve(["Arial","Georgia","Helvetica Neue"]);
    // The real bundled set (selahcue_scripture::Translation::ALL, mirrored — see main.rs's
    // list_translations): five public-domain translations, none downloadable (all shipped in the
    // binary). Settings › About & Licensing (17tnw2axwer) reads this for real, so the fixture
    // must be a real shape, not the generic Promise.resolve(null) fallback every unstubbed
    // command gets (which would make that page's render path untestable here).
    // Translation::ALL is SIX entries (selahcue-scripture/src/lib.rs), not five — the fifth
    // bundled PD translation (DBY) plus Young's Literal Translation (YLT), which is public domain
    // but NOT bundled (loads from an on-disk cache at runtime, feature `download`) and so is the
    // one real `downloadable:true` entry this command ever returns today (Cody's review of PR #68
    // caught the fixture under-counting this at five).
    if (cmd === "list_translations") return Promise.resolve({translations:[
      {code:"KJV", name:"King James Version", downloadable:false, available:true},
      {code:"WEB", name:"World English Bible", downloadable:false, available:true},
      {code:"ASV", name:"American Standard Version", downloadable:false, available:true},
      {code:"WEBBE", name:"World English Bible, British Edition", downloadable:false, available:true},
      {code:"DBY", name:"Darby Translation", downloadable:false, available:true},
      {code:"YLT", name:"Young's Literal Translation", downloadable:true, available:false}
    ]});
    // Test hook (mirrors __deckListNullOnce/__pmRejectOnce): force ONE `view()` rejection, so a
    // failed local-state read (e.g. PME-059's plan-reference check in pmLibDelete) can be told
    // apart from a genuinely healthy read reporting "not referenced".
    if (cmd === "view") {
      if (window.__viewRejectOnce) { window.__viewRejectOnce = false; return Promise.reject(new Error("view failed")); }
      // A stalled-but-connected host on Backend::Remote (Vera, PR #69 review round 2): the
      // promise NEVER settles, so only pmLibDelete's own client-side timeout can move the UI on.
      if (window.__viewHangOnce) { window.__viewHangOnce = false; return new Promise(function(){}); }
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    // Service Plan builder (86ajxxuz9): plan mutations + content-link + scripture search.
    // Each returns a fresh OperatorView (byte-cloned) so the builder re-render never aliases V;
    // set_item_content is a PLAN edit (never a live-control command — the invariant check relies
    // on this staying out of the go_live/next/select/blackout/clear/start_timer set).
    if (cmd === "set_item_content") {
      // One-shot rejection hook: lets the driver exercise the "host rejected the link" path
      // (modal stays open + role=alert), mirroring a reference the host can't parse.
      if (window.__sicRejectOnce) { window.__sicRejectOnce = false; return Promise.reject("simulated host rejection"); }
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "add_item" || cmd === "move_item" || cmd === "rename_item" || cmd === "remove_item" || cmd === "plan_undo" || cmd === "plan_redo")
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    // Plan lifecycle (86ak8467m; host side 86ajy0hwg). The reply is whatever the driver has
    // parked in window.__planLifeReply (defaulting to V), with the request's own name and items
    // folded in — so a check can assert that the client RENDERS what the host returned rather
    // than what it optimistically assumed. __planRejectOnce drives the rejection path.
    if (cmd === "publish_plan" || cmd === "new_plan" || cmd === "template_plan" ||
        cmd === "duplicate_plan" || cmd === "import_plan") {
      if (window.__planRejectOnce) { window.__planRejectOnce = false; return Promise.reject(new Error("simulated host rejection")); }
      var pv = JSON.parse(JSON.stringify(window.__planLifeReply || V));
      if (args && typeof args.name === "string") pv.plan_name = args.name;
      if (cmd === "new_plan") { pv.items = []; delete pv.summary; }
      if (cmd === "import_plan" && args && Array.isArray(args.items)) {
        pv.items = args.items.map(function(it, i){
          return { id: 800 + i, kind: it.kind, title: it.title, is_live: false, is_staged: false };
        });
        delete pv.summary;
      }
      return Promise.resolve(pv);
    }
    // Blackout mirrors the host: it MUTATES the state and returns the new view. It used to fall
    // through to `Promise.resolve(null)`, so the engaged blackout state could never be exercised
    // end to end — the driver could only fake it by poking V directly.
    if (cmd === "blackout") { V.blackout = !!(args && args.on); return Promise.resolve(JSON.parse(JSON.stringify(V))); }
    if (cmd === "scripture_search")
      return Promise.resolve([{reference:"Romans 8:28", text:"And we know that all things work together for good"}]);
    if (cmd === "preview_theme") return Promise.resolve({rgba: btoa("\x00\x00\x00\xff"), w:1, h:1});
    // FR-138 / 86ak0qmzv: pick_image now returns a tagged outcome, not a bare path. Tests can
    // override the next outcome via window.__pickImageNextOutcome (e.g. a validation refusal)
    // before triggering a pick, then clear it back to the default.
    if (cmd === "pick_image")
      return Promise.resolve(window.__pickImageNextOutcome || {outcome: "picked", path: "/tmp/picked.png"});
    if (cmd === "remote_snapshot")
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    if (cmd === "remote_approve") {
      var RA = window.__remote, ri = RA.pending.findIndex(function(p){return p.device_id === args.deviceId;});
      if (ri >= 0) { var rp = RA.pending.splice(ri,1)[0];
        RA.devices.push({device_id:rp.device_id, name:rp.name, platform:rp.platform, role:(args.role==="operator"?"producer":args.role), idle_secs:0, pinned:false}); }
      return Promise.resolve({devices: RA.devices.slice(), pending: RA.pending.slice()});
    }
    if (cmd === "remote_deny") {
      window.__remote.pending = window.__remote.pending.filter(function(p){return p.device_id !== args.deviceId;});
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    }
    if (cmd === "remote_revoke") {
      window.__remote.devices = window.__remote.devices.filter(function(d){return d.device_id !== args.deviceId;});
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    }
    if (cmd === "remote_set_role") {
      if (args.role !== "operator") window.__remote.devices.forEach(function(d){ if (d.device_id === args.deviceId) d.role = args.role; });
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    }
    if (cmd === "remote_new_code")
      return Promise.resolve({code:"AB12CD34", fingerprint:"A1 B2 C3 D4", expires_in_secs:120});
    if (cmd === "host_connected") return Promise.resolve(!window.__psNoHost); // a real output window (unless the test says otherwise)
  // Tier 2 control-link state. Defaults to a healthy remote link; __link overrides it.
  // Returning `null` here would exercise the "older shell" path instead, which the driver
  // covers separately by deleting the override.
  if (cmd === "link_status") return Promise.resolve(window.__link || {state:"connected", epoch:1, attempts:0, last_error:null});
    if (cmd === "stt_ready") return Promise.resolve(window.__psStt || {ready:true, state:"ready", model:"Small", detail:"On-device model ready"});
    if (cmd === "audio_input") return Promise.resolve(window.__psAudio || {available:true, state:"ok", name:"Focusrite Scarlett 2i2", channels:2, detail:"Focusrite Scarlett 2i2 · 2 ch"});
    if (cmd === "disk_free")
      return Promise.resolve({available_bytes: (window.__psDiskLow ? 0.5 : 42) * 1073741824, total_bytes: 500 * 1073741824}); // 42 GB free (or <1 GB critical when flagged)
    if (cmd === "render_console") return Promise.resolve(
      window.__renderAvailable
        ? {available:true,
           preview:{w:2,h:1,rgba:btoa("\xff\x00\x00\xff\x00\xff\x00\xff")},
           live:{w:2,h:1,rgba:btoa("\x00\x00\xff\xff\xff\xff\x00\xff")}}
        : {available:false});
    if (cmd === "render_screen") {
      // A distinct 2x1 RGBA frame per audience screen (86ajq321k), so the previews differ.
      var px = { "main": "\xff\x00\x00\xff\x00\x00\x00\xff",
                 "lower-third": "\x00\xff\x00\xff\x00\x00\x00\xff",
                 "stream": "\x00\x00\xff\xff\x00\x00\x00\xff" };
      return Promise.resolve({available:true, frame:{w:2, h:1, rgba: btoa(px[args.screen] || "\x33\x33\x33\xff\x00\x00\x00\xff")}});
    }
    if (cmd === "set_screen_enabled") {
      // Simulate an RBAC-denied / older-host rejection to exercise the no-lie revert.
      if (window.__rejectSetEnabled) return Promise.reject("denied");
      V.screens.forEach(function(s){ if (s.screen === args.screen) s.enabled = args.enabled; });
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "add_screen") {
      // Mint the bare role name first, then role-2, role-3… — mirroring the host registry.
      var ids = V.screens.map(function(s){ return s.screen; });
      var id = args.role, n = 2;
      while (ids.indexOf(id) >= 0) { id = args.role + "-" + n; n++; }
      V.screens.push({screen: id, role: args.role, enabled:true, deletable:true, theme:null});
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "remove_screen") {
      V.screens = V.screens.filter(function(s){ return !(s.screen === args.screen && s.deletable); });
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    // CON-156/157/158: a real mutation (mirrors LiveController::set_ndi_output), not a bare
    // Promise.resolve(V) — so a test can drive a screen into an ENABLED, NAMED NDI state and
    // then assert the client-side duplicate-name refusal against it for real, the same way
    // set_screen_enabled/add_screen above do for their own fields.
    if (cmd === "set_ndi_output") {
      V.screens.forEach(function(s){
        if (s.screen === args.screen) {
          s.config = Object.assign({}, s.config, {ndi_enabled: args.enabled, ndi_name: args.name});
        }
      });
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "set_custom_theme") return Promise.resolve({});
    if (cmd === "save_theme") return Promise.resolve({saved_themes:[{name:args.name, theme_json:args.themeJson}]});
    if (cmd === "operator_state" || cmd === "state") return Promise.resolve({});
    // Listen control: start_listening stays PENDING until the test drives it, mirroring the
    // host worker that loads the model + opens the mic before signalling readiness.
    if (cmd === "start_listening") return new Promise(function(res, rej){ window.__startCtl = {resolve:res, reject:rej}; });
    if (cmd === "stop_listening") return Promise.resolve(null);
    // Cody's review of PR #64: the RANGE half of loadChapter's stage=false guard
    // (app.js's isRange branch) had zero coverage — every fixture in this file requested a
    // single-verse reference, so verse_end was always null and isRange was always false by
    // construction, regardless of what the real production comparison would do. A reference
    // containing "N-M" after the colon (e.g. "John 3:16-18") now gets a genuine range response,
    // so a test can actually exercise that branch instead of it being permanently dead code as
    // far as this suite can see.
    if (cmd === "get_chapter") {
      var _gcRef = (args && args.reference) ? String(args.reference) : "";
      var _gcRange = /:(\d+)-(\d+)/.exec(_gcRef);
      var _gcResp = _gcRange
        ? (function () {
            var _gcLo = +_gcRange[1], _gcHi = +_gcRange[2];
            return {
              reference: _gcRef.replace(/:.*$/, ""),
              translation: "KJV", translations: ["KJV"],
              verses: [[_gcLo, "verse " + _gcLo + " text"], [_gcHi, "verse " + _gcHi + " text"]],
              verse_start: _gcLo, verse_end: _gcHi, prev: true, next: true,
            };
          })()
        : {
            reference: _gcRef ? _gcRef.replace(/:.*$/, "") : "Isaiah 61",
            translation: "KJV", translations: ["KJV"],
            verses: [[1, "verse one text"], [5, "verse five text"]],
            verse_start: 5, verse_end: null, prev: true, next: true,
          };
      // One-shot DEFER hook (Sana's security review, PR #64, finding B): holds this fetch open
      // so the driver can prove a stale, already-armed stageTimer does NOT fire while a
      // read-only load is still in flight — the exact race a slow (300ms+) fetch reopens if the
      // pending timer is only cleared AFTER this resolves (inside setCursor) rather than before
      // the fetch even starts.
      if (window.__getChapterDeferOnce) {
        window.__getChapterDeferOnce = false;
        return new Promise(function (res) {
          window.__getChapterDeferredResolve = function () { res(_gcResp); };
        });
      }
      return Promise.resolve(_gcResp);
    }
    // approve_detection stages (dequeues + remembers which reference was staged, mirroring the
    // real host); go_live commits that remembered reference to live_scripture ONLY when actually
    // called — Stage alone must never move it (CON-136's on-air card depends on this distinction:
    // it only claims on-air once view.live_scripture genuinely matches the approved reference).
    // Quinn's QA review (PR #61, bug 17tnw2axre8): the real host's ApproveDetection handler
    // (controller.rs's stage_reference_for_detection) narrows a WHOLE-CHAPTER reference (no
    // verse) to its first verse before staging — "Isaiah 61" goes live as "Isaiah 61:1". This
    // mock reproduces exactly that so app.js's fix is exercised against the real transformation,
    // not a hand-picked string: a reference with no ":" names no verse (every reference string
    // used anywhere in this fixture set follows "Book Chapter:Verse" when a verse is present),
    // matching the real check closely enough for this purpose (`Reference`'s Display is
    // "Book Chapter" for a whole chapter, and `parse_one` needs no colon to resolve a verse-only
    // spoken form — but nothing in this fixture set exercises that, so this heuristic is exact
    // for every case actually driven through it).
    if (cmd === "approve_detection") {
      var _apDet = (V.detections || []).find(function (x) { return x.id === args.detectionId; });
      if (_apDet) {
        V.__lastApprovedRef = _apDet.reference.indexOf(":") < 0
          ? _apDet.reference + ":1"
          : _apDet.reference;
        V.detections = (V.detections || []).filter(function (x) { return x.id !== args.detectionId; });
      }
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "dismiss_detection") {
      // One-shot rejection hook (Vera's review, PR #64, P2): lets the driver prove a FAILED
      // dismiss (busy host, link blip) is retried on the next poll rather than permanently
      // "handled" — exercises both call sites (the auto-dismiss loop in syncDetections and the
      // manual mute-button click in buildDetectionCard).
      if (window.__dismissDetectionRejectOnce) { window.__dismissDetectionRejectOnce = false; return Promise.reject("simulated host rejection"); }
      // One-shot DEFER+reject hook: holds the promise open so the driver can land an intervening
      // poll (a render() call) WHILE this dismiss is still in flight, before finally rejecting
      // it — reproduces the race where syncDetections's own memoization re-stores detectionsKey
      // to match the still-queued view during that gap, which would otherwise make a plain
      // "un-remember the id" retry fix inert once the rejection actually lands.
      if (window.__dismissDetectionDeferRejectOnce) {
        window.__dismissDetectionDeferRejectOnce = false;
        return new Promise(function (_res, rej) {
          window.__dismissDetectionDeferredReject = function () { rej("simulated host rejection (deferred)"); };
        });
      }
      V.detections = (V.detections || []).filter(function (x) { return x.id !== args.detectionId; });
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "go_live") {
      if (V.__lastApprovedRef) V.live_scripture = V.__lastApprovedRef;
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "clear") {
      V.live_scripture = null;
      V.live_free_text = null;
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    // --- Live Console slide picker (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §6): the read-only
    // deck-slide bridge + within-item staging the Slides filmstrip drives. deckId 7 = a 3-slide
    // presentation; deckId 999 = a removed deck (available:false → the "presentation missing" state). ---
    if (cmd === "plan_deck_slides") {
      if (args.deckId === 999) return Promise.resolve({available:false});
      if (args.deckId === 8) { var big=[]; for (var i=0;i<80;i++) big.push({slide_id:200+i, label:"S"+(i+1), has_notes:false}); return Promise.resolve({available:true, slides:big}); } // large deck: bounded-memory test
      return Promise.resolve({available:true, slides:[
        {slide_id:101, label:"Grace That Feeds", has_notes:false},
        {slide_id:102, label:"Isaiah 61:5", has_notes:true},
        {slide_id:103, label:"Closing", has_notes:false}
      ]});
    }
    if (cmd === "render_plan_deck_slide")
      return Promise.resolve({available:true, frame:{w:2, h:1, rgba:btoa("\xff\x00\x00\xff\x00\xff\x00\xff")}});
    if (cmd === "select_slide") { // mirror the host: clamp to the item's slide_count + set the STAGED cursor (never Live)
      if (V.items[1]) {
        var _cnt = V.items[1].slide_count || 1;
        var _k = Math.max(0, Math.min(_cnt - 1, args.slideIndex));
        V.items[1].staged_slide_index = _k;
        if (V.live_index !== 1) V.items[1].slide_index = _k; // slide_index is LIVE-first when also live
      }
      V.staged_index = 1; V.staged_scripture = null;
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "present_plan_deck_slide") { // route the authored deck slide to Live (mirror present_authored_slide)
      V.live_authored_id = args.slideId; // the on-air authored slide id drives the filmstrip LIVE marker
      V.live_index = null;               // present_authored takes over the live surface (clears the plan live item)
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    // --- Presentation & Media (deck_* commands + render_deck_slide) ---
    // One-shot rejection hook: lets the driver exercise the error banner (role=alert) + Retry.
    if (window.__pmRejectOnce && cmd.indexOf("deck_") === 0) { window.__pmRejectOnce = false; return Promise.reject("simulated host rejection"); }
    // One-shot DEFER hook: hold the next deck command pending so the driver can observe the
    // in-flight aria-busy loading state, then resolve it. Mirrors a slow host round-trip.
    if (window.__pmDeferOnce && cmd.indexOf("deck_") === 0) {
      window.__pmDeferOnce = false;
      return new Promise(function(res){ window.__pmDeferred = function(){ res(dEdit()); }; });
    }
    if (cmd === "deck_view") return Promise.resolve(dClone());
    // --- Presentations Library (deck_list/new/open/rename/duplicate/delete) ---
    var LIB = window.__LIB || (window.__LIB = {
      decks: [
        {id:1, name:"Sunday Service — Aug 4", slides:24},
        {id:2, name:"Sermon: Grace That Feeds", slides:2},  // the open deck (matches D)
        {id:3, name:"Youth Night — Identity", slides:12}
      ],
      open: 2, persistent: true, nextId: 4,
      // Mirrors the host's bounded in-memory trash (8 entries). Without it the driver could never
      // reach the restorable/non-restorable branches at all — a fixture that never reaches the
      // condition the test names is the way these checks rot into decoration.
      trash: []
    });
    var libView = function(){ return { decks: LIB.decks.map(function(d){return {id:d.id,name:d.name,slides:d.slides};}), open: LIB.open, persistent: LIB.persistent,
      // What an undo could ACTUALLY put back (LibraryView.restorable). Bounded, so it shrinks.
      restorable: LIB.trash.map(function(t){ return t.id; }) }; };
    var libUnique = function(base){ var n=base, k=2; var names=LIB.decks.map(function(d){return d.name;}); while(names.indexOf(n)>=0){ n=base+" ("+k+")"; k++; } return n; };
    if (cmd === "deck_list") {
      // Test hook (mirrors __pmRejectOnce): force a MALFORMED null answer, so a host that does
      // not implement deck_list can be told apart from one reporting an empty library.
      if (window.__deckListNullOnce) { window.__deckListNullOnce = false; return Promise.resolve(null); }
      return Promise.resolve(libView());
    }
    if (cmd === "deck_search") {
      var gq = String((args && args.query) || "").trim().toLowerCase();
      if (!gq) return Promise.resolve({hits: []});
      var ghits = [];
      LIB.decks.forEach(function(d){
        if (d.name.toLowerCase().indexOf(gq) >= 0) ghits.push({deck_id: d.id, name: d.name, kind: "name"});
      });
      // Synthetic slide-content hit so the modal's content-row (slide # + snippet) is exercised.
      if (gq.indexOf("grace") >= 0 && LIB.decks.length) {
        var gd = LIB.decks[LIB.decks.length - 1];
        ghits.push({deck_id: gd.id, name: gd.name, kind: "content", slide_id: 7, slide_index: 3, snippet: "Amazing grace, how sweet the sound"});
      }
      return Promise.resolve({hits: ghits});
    }
    if (cmd === "deck_new") {
      var nid=LIB.nextId++; var nm=libUnique((args.name&&args.name.trim())||"Untitled presentation");
      LIB.decks.push({id:nid, name:nm, slides:1}); LIB.open=nid;
      D.name=nm; D.count=1; return Promise.resolve(dClone()); // DeckView (opens the editor)
    }
    if (cmd === "deck_open") {
      var od=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      if (od){
        // Real host semantics (deck_workspace.rs::load_deck): switching to a DIFFERENT deck resets
        // the editing session — fresh selection (first slide), Live cleared. Reopening the SAME
        // already-open deck is a no-op (deck_workspace.rs::deck_open's early return). Mirrored here
        // ONLY for a deck that carries its own `.content` array — opt-in, set by a fixture that
        // needs REAL per-deck slide data (17tnw2axwve's cross-deck collision check below) — so
        // every other deck_open call keeps the pre-existing (content-blind) behaviour and none of
        // this suite's other checks change.
        if (od.content && LIB.open !== od.id) {
          D.slides = JSON.parse(JSON.stringify(od.content));
          D.selected = D.slides.length ? D.slides[0].id : null;
          D.live = null;
        }
        LIB.open=od.id; D.name=od.name; D.count=od.slides;
      }
      return Promise.resolve(dClone());
    }
    if (cmd === "deck_rename") {
      var rd=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      if (rd){ rd.name=libUnique((args.name&&args.name.trim())||"Untitled presentation"); if(LIB.open===rd.id) D.name=rd.name; } return Promise.resolve(libView());
    }
    if (cmd === "deck_duplicate") {
      var sd=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      if (!sd) return Promise.resolve(libView());
      // Mirrors deck_duplicate's real response shape (main.rs): the copy's own new_id, the same
      // additive pattern deck_restore already uses for restored_name — PME-053's "Start from →
      // Duplicate…" flow in the New-presentation dialog needs it to rename + open the copy.
      var nid = LIB.nextId++;
      LIB.decks.push({id:nid, name:libUnique(sd.name+" copy"), slides:sd.slides});
      var v = libView(); v.new_id = nid; return Promise.resolve(v);
    }
    if (cmd === "deck_delete") {
      var wasOpen=(LIB.open===args.id);
      var doomed=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      // The host retains the deck in a bounded trash — EXCEPT when it is too large to keep, which
      // is why `restorable` exists rather than "the last delete is always undoable".
      // window.__deckNoRetain names an id the fixture wants to be unretainable.
      if (doomed && window.__deckNoRetain !== args.id) {
        LIB.trash.push({id:doomed.id, deck:{id:doomed.id, name:doomed.name, slides:doomed.slides}});
        while (LIB.trash.length > 8) LIB.trash.shift();
      }
      LIB.decks=LIB.decks.filter(function(x){return x.id!==args.id;});
      if (wasOpen){ if(LIB.decks.length){ LIB.open=LIB.decks[0].id; D.name=LIB.decks[0].name; D.count=LIB.decks[0].slides; } else { LIB.decks.push({id:LIB.nextId++, name:"Untitled presentation", slides:1}); LIB.open=LIB.decks[0].id; D.name="Untitled presentation"; D.count=1; } }
      return Promise.resolve(libView());
    }
    // --- Transcripts (86akcffvt / FR-130 core slice): transcript_list / transcript_get ---
    var TR = window.__TR || (window.__TR = {
      list: [
        {id:1, label:"Sunday Service — Aug 4", provider:"manual", started_at_ms: 1722760800000, ended_at_ms: 1722764460000, segment_count: 3},
        // Never ended (a crash mid-service / still recording, FR-075) — exercises the "In progress"
        // duration branch instead of a bogus negative/garbage one.
        {id:2, label:"Wednesday Bible Study", provider:"whisper", started_at_ms: 1722160800000, ended_at_ms: null, segment_count: 1},
      ],
      detail: {
        // 86akgqdxr: fixtures 1/2 now also carry the REAL wire shape `transcript_get` returns
        // for "nothing detected/generated yet" (`detections`/`corrections: []`, `draft` and its
        // siblings `null`) — explicit rather than left `undefined`, though `transcripts.js`'s own
        // `Array.isArray(t.detections) ? ... : []` / `if (t.draft)` guards degrade either way
        // identically, which is exactly why fixtures 3-6 below (the bounded-rendering/oversize
        // scenarios, unrelated to this ticket) are left UNCHANGED rather than touched everywhere.
        // Dedicated fixtures 7/8 below cover the NEW detections/saved-draft rendering paths.
        1: { id:1, label:"Sunday Service — Aug 4", provider:"manual", started_at_ms: 1722760800000, ended_at_ms: 1722764460000,
             notes_generated: false,
             detections: [], corrections: [], draft: null, scripture_verification_note: null,
             ai_generated: null, ai_label: null, disclosure: null, notes_provider: null,
             segments: [
               {id:101, start_ms:0, end_ms:4000, text:"Good morning, church."},
               {id:102, start_ms:4000, end_ms:9000, text:"Please turn with me to Romans chapter eight."},
               {id:103, start_ms:9000, end_ms:15000, text:"Verse twenty-eight: And we know that all things work together for good."},
             ] },
        2: { id:2, label:"Wednesday Bible Study", provider:"whisper", started_at_ms: 1722160800000, ended_at_ms: null,
             notes_generated: false,
             detections: [], corrections: [], draft: null, scripture_verification_note: null,
             ai_generated: null, ai_label: null, disclosure: null, notes_provider: null,
             segments: [ {id:201, start_ms:0, end_ms:5000, text:"Let's open in prayer."} ] },
      },
    });
    // A transcript with TWO detections (one traced to a known segment, one with no known source
    // — the documented 0 sentinel) and an already-SAVED draft — the AC1/AC2 rendering fixture
    // (86akgqdxr). Seeded only on request (window.__trSeedDetectionsFixture), same reasoning as
    // the other conditionally-seeded fixtures below: an unconditional 3rd list entry here would
    // break the "TR: transcript_list renders one card per transcript" check's exact `=== 3`
    // count, which runs BEFORE this block would otherwise be reached.
    if (window.__trSeedDetectionsFixture && !window.__trDetectionsFixtureSeeded) {
      window.__trDetectionsFixtureSeeded = true;
      TR.detail[7] = { id:7, label:"Detections + Notes Fixture", provider:"manual", started_at_ms: 1723000000000, ended_at_ms: 1723003600000,
        notes_generated: true,
        detections: [
          {id:901, reference:"Romans 8:28", source_segment:702, confidence:95},
          {id:902, reference:"John 3:16", source_segment:0, confidence:70},
        ],
        corrections: [ {segment_id:701, corrected_text:"Good morning, everyone.", corrected_at_ms:5000} ],
        draft: {
          title:"Fixture Sermon", summary:"A saved draft's real content, not just a badge.",
          sections:[
            {heading:"Main points", items:["Faith"], points:[], empty_requested:false},
            {heading:"Prayer points", items:[], points:[], empty_requested:true},
          ],
          // 86akgqdwc (Sana F2 on PR #48; gap on THIS surface caught by Cody's delta re-check):
          // this fixture is where transcripts.js's own rendering of the draft-wide
          // "scripture_verification_incomplete" caveat is proven — added here rather than a
          // new isolated fixture because this is the exact reproduction Cody's own re-check
          // used (adding it to "Fixture Sermon", not a fresh one).
          scriptures:["Romans 8:28"], caveats:[{kind:"scripture_verification_incomplete"}], scripture_verdicts:[{reference:"Romans 8:28", verified:true}],
        },
        scripture_verification_note:"Verified means the reference address exists in the bundled Bible text — it does not confirm that any words this draft attributes to it are accurate. Always check a quotation against the actual text before you use it.",
        ai_generated:true, ai_label:"AI-generated draft",
        disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
        notes_provider:"OpenAI",
        segments: [
          {id:701, start_ms:0, end_ms:4000, text:"Good morning, church."},
          {id:702, start_ms:4000, end_ms:9000, text:"Turn with me to Romans eight."},
        ] };
      TR.list.push({id:7, label:"Detections + Notes Fixture", provider:"manual", started_at_ms: 1723000000000, ended_at_ms: 1723003600000, segment_count:2});
    }
    // Timestamp-linked note items (86akgqdw0; FR-124) — a dedicated fixture, seeded on request
    // like the one above, kept SEPARATE from "Detections + Notes Fixture" (id 7) rather than
    // added to it: id 7 already has its own edit/save flow later in this script that mutates
    // its draft in place, and this ticket's checks need a stable, untouched draft to assert
    // against. Three chapter-marker items exercise the three cases this ticket's own
    // adversarial-fixture acceptance criterion names: a REAL match (a real, in-range offset a
    // real segment produced), an OUT-OF-RANGE-but-numeric offset (past every segment — the
    // console must clamp to the nearest known position, never crash or scroll nonsensically),
    // and a MALFORMED (non-numeric) offset (the console must render no badge at all for it,
    // never a broken one).
    if (window.__trSeedTimestampsFixture && !window.__trTimestampsFixtureSeeded) {
      window.__trTimestampsFixtureSeeded = true;
      // Sana's security review (PR #51, S2): the three-segment fixture below is too small to
      // exercise the ADR-0026 rev-4 `D5-exempt(jump)` write's ENTIRE reason to exist — "the
      // target row may not be mounted" — every one of its 3 rows is already mounted well
      // under WINDOW_ROWS(150), so the original jump checks below pass in the one
      // configuration where the jump is trivially exact. `tsFillerSegs` adds 300 filler
      // segments (comfortably past WINDOW_ROWS) so a FOURTH marker, "Deep in the service",
      // targets a segment that is genuinely NOT in the initially-mounted window — verified
      // below by asserting its row is absent BEFORE the click.
      var tsFillerSegs = [];
      for (var tsi = 0; tsi < 300; tsi++) {
        tsFillerSegs.push({id: 900000 + tsi, start_ms: 15000 + tsi * 4000, end_ms: 15000 + tsi * 4000 + 3500,
          text: "Filler segment " + tsi + " of a long service, well past the initial WINDOW_ROWS mount."});
      }
      var TS_DEEP_INDEX = 200; // filler index; absolute segment index 203 — far past WINDOW_ROWS(150)
      var TS_DEEP_ID = 900000 + TS_DEEP_INDEX;
      var TS_DEEP_OFFSET_MS = 15000 + TS_DEEP_INDEX * 4000;
      TR.detail[8] = { id:8, label:"Timestamps Fixture", provider:"manual", started_at_ms: 1724000000000, ended_at_ms: 1724001000000 + 300 * 4000,
        notes_generated: true,
        detections: [], corrections: [],
        draft: {
          title:"Timestamps Fixture", summary:null,
          sections:[
            {heading:"Chapter markers", items:["Opening prayer","Far future","Bogus type","Deep in the service"], points:[], empty_requested:false},
          ],
          scriptures:[], caveats:[], scripture_verdicts:[],
          timestamps:[
            {heading:"Chapter markers", text:"Opening prayer", offset_ms:4000},
            // Numeric but past every real segment (the last starts at 9000) — a real, if
            // stale, `u64` value could look like this after a corrupted store row; the
            // console's own bound is what must keep this from landing somewhere nonsensical.
            {heading:"Chapter markers", text:"Far future", offset_ms:99999999999},
            // Non-numeric — the shape a hand-corrupted or hostile draft could carry.
            {heading:"Chapter markers", text:"Bogus type", offset_ms:"not-a-number"},
            // S2: a REAL segment far outside the window mounted on open.
            {heading:"Chapter markers", text:"Deep in the service", offset_ms:TS_DEEP_OFFSET_MS},
          ],
        },
        scripture_verification_note:null,
        ai_generated:true, ai_label:"AI-generated draft",
        disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
        notes_provider:"OpenAI",
        segments: [
          {id:801, start_ms:0, end_ms:4000, text:"Good morning, church."},
          {id:802, start_ms:4000, end_ms:9000, text:"Let us open this morning in a word of prayer."},
          {id:803, start_ms:9000, end_ms:15000, text:"Turn with me to Romans chapter eight."},
        ].concat(tsFillerSegs) };
      window.__trTsDeepId = TS_DEEP_ID;
      TR.list.push({id:8, label:"Timestamps Fixture", provider:"manual", started_at_ms: 1724000000000, ended_at_ms: 1724001000000 + 300 * 4000, segment_count: 3 + 300});
    }
    // A synthetic three-hour-scale transcript — 500 segments, well past the live console's
    // 240-segment ring cap — for the bounded-DOM-rendering checks (86akcffvt AC3). Each segment's
    // text names its own index so a check can assert exactly which ones are/aren't mounted.
    if (!window.__trBigSeeded) {
      window.__trBigSeeded = true;
      var bigSegs = [];
      for (var bi = 0; bi < 500; bi++) {
        bigSegs.push({id: 1000 + bi, start_ms: bi * 4000, end_ms: bi * 4000 + 3500,
          text: "Segment " + bi + " — the quick brown fox jumps over the lazy dog near the riverbank at dawn."});
      }
      var bigStart = 1725600000000, bigEnd = bigStart + 500 * 4000;
      TR.detail[3] = {id:3, label:"Three-Hour Service — Sep 6", provider:"manual", started_at_ms:bigStart, ended_at_ms:bigEnd, notes_generated:false, segments:bigSegs};
      TR.list.push({id:3, label:"Three-Hour Service — Sep 6", provider:"manual", started_at_ms:bigStart, ended_at_ms:bigEnd, segment_count:500});
    }
    // A REALISTIC-width/content-size transcript (performance review, Vera V-1/V-2), seeded only
    // when a test explicitly asks for it (window.__trSeedRealistic) — NOT unconditionally like
    // the 500-segment fixture above, because this fixture-seeding code runs on every invoke() and
    // an unconditional 4th list entry would break the earlier "exactly 3 transcripts" checks that
    // run before this block is ever reached. The 500-segment fixture above uses UNIFORM 85-char
    // lines, which sits just on the safe side of the real/estimated height "break-even" ratio
    // (~0.63) the virtualizer's fixed-chars-per-line ESTIMATE needs to stay accurate — that
    // narrow safety margin is why the estimate-only virtualizer's bug shipped undetected. This
    // fixture instead uses a MIXED character-length distribution approximating real speech
    // (~10% short 8-30 char utterances, ~70% medium 40-140, ~15% long 140-260, ~5% very long
    // 260-420 "utterance-level final" segments) — deterministic (no Math.random()) so the test
    // reproduces identically every run.
    if (window.__trSeedRealistic && !window.__trRealisticSeeded) {
      window.__trRealisticSeeded = true;
      var TR_FILLER = "the quick brown fox jumps over the lazy dog near the riverbank at dawn while the choir softly hums an old familiar hymn before the sermon begins ";
      var trRealisticText = function (n, len) {
        var s = "Segment " + n + ": ";
        while (s.length < len) s += TR_FILLER;
        return s.slice(0, len);
      };
      var realSegs = [];
      var TR_REALISTIC_COUNT = 3000;
      for (var ri = 0; ri < TR_REALISTIC_COUNT; ri++) {
        var rm = ri % 20, rlen;
        if (rm < 2) rlen = 8 + (ri % 23);          // ~10%: 8-30 chars
        else if (rm < 16) rlen = 40 + (ri % 101);  // ~70%: 40-140 chars
        else if (rm < 19) rlen = 140 + (ri % 121); // ~15%: 140-260 chars
        else rlen = 260 + (ri % 161);              // ~5%: 260-420 chars
        realSegs.push({id: 10000 + ri, start_ms: ri * 3000, end_ms: ri * 3000 + 2500, text: trRealisticText(ri, rlen)});
      }
      var realStart = 1728700000000, realEnd = realStart + TR_REALISTIC_COUNT * 3000;
      TR.detail[4] = {id:4, label:"Realistic Long Service — Oct 12", provider:"manual", started_at_ms:realStart, ended_at_ms:realEnd, notes_generated:false, segments:realSegs};
      TR.list.push({id:4, label:"Realistic Long Service — Oct 12", provider:"manual", started_at_ms:realStart, ended_at_ms:realEnd, segment_count:TR_REALISTIC_COUNT});
    }
    // A PHASED (segment-length REGIME CHANGE) transcript — performance review, Vera V-6 — seeded
    // only on request (window.__trSeedPhased), same reasoning as __trSeedRealistic above. The
    // fixture above interleaves short/medium/long segments EVENLY throughout, which is why it
    // never caught V-6: a fresh jump anywhere in it lands in roughly the SAME average length
    // regime the calibration ratio already learned near the top, so the ratio-driven spacer math
    // stays close to right by chance. This fixture instead runs three back-to-back BLOCKS of one
    // length each (short, then long, then medium thirds) — Vera's own reproduction shape — so a
    // fresh jump into the long or medium block lands somewhere the ratio learned from the OTHER
    // block(s) systematically mis-estimates, which is exactly the regime V-6 needs a fresh-open
    // jump/drag INTO to ever show a blank frame.
    if (window.__trSeedPhased && !window.__trPhasedSeeded) {
      window.__trPhasedSeeded = true;
      var TR_PFILLER = "the quick brown fox jumps over the lazy dog near the riverbank at dawn while the choir softly hums an old familiar hymn before the sermon begins ";
      var trPhasedText = function (n, len) {
        var s = "Segment " + n + ": ";
        while (s.length < len) s += TR_PFILLER;
        return s.slice(0, len);
      };
      var phasedSegs = [];
      var TR_PHASED_COUNT = 3000;
      var pThird = Math.floor(TR_PHASED_COUNT / 3);
      for (var pi = 0; pi < TR_PHASED_COUNT; pi++) {
        var plen;
        if (pi < pThird) plen = 8 + (pi % 23);                 // first third: short 8-30 chars
        else if (pi < 2 * pThird) plen = 260 + (pi % 161);      // middle third: long 260-420 chars
        else plen = 40 + (pi % 101);                            // last third: medium 40-140 chars
        phasedSegs.push({id: 20000 + pi, start_ms: pi * 3000, end_ms: pi * 3000 + 2500, text: trPhasedText(pi, plen)});
      }
      var phasedStart = 1730000000000, phasedEnd = phasedStart + TR_PHASED_COUNT * 3000;
      TR.detail[5] = {id:5, label:"Regime Change Service — Nov 2", provider:"manual", started_at_ms:phasedStart, ended_at_ms:phasedEnd, notes_generated:false, segments:phasedSegs};
      TR.list.push({id:5, label:"Regime Change Service — Nov 2", provider:"manual", started_at_ms:phasedStart, ended_at_ms:phasedEnd, segment_count:TR_PHASED_COUNT});
    }
    // A transcript whose COMPLETE joined text is deliberately well past the 400,000-character
    // note-generation clamp (86akcffy0 AC2) — seeded only on request (window.__trSeedOversize),
    // same reasoning as the two fixtures above. 4,500 segments of a fixed 100-char body, joined
    // by "\n" (86akcffy0's `transcript_full_text`/app.js's `syncTranscript` convention): total
    // length is exactly deterministic (4500*100 + 4499 = 454,499 characters, ~54,499 over the
    // clamp) so a check can assert the EXACT drop count the preview must disclose, not just "some
    // truncation happened".
    if (window.__trSeedOversize && !window.__trOversizeSeeded) {
      window.__trOversizeSeeded = true;
      var oversizeBody = "the quick brown fox jumps over the lazy dog near the riverbank at dawn while the choir hums.";
      // Pad/trim to EXACTLY 100 chars so the total is exactly computable (see above).
      while (oversizeBody.length < 100) oversizeBody += ".";
      oversizeBody = oversizeBody.slice(0, 100);
      var oversizeSegs = [];
      var TR_OVERSIZE_COUNT = 4500;
      for (var oi = 0; oi < TR_OVERSIZE_COUNT; oi++) {
        oversizeSegs.push({id: 30000 + oi, start_ms: oi * 3000, end_ms: oi * 3000 + 2500, text: oversizeBody});
      }
      var oversizeStart = 1732000000000, oversizeEnd = oversizeStart + TR_OVERSIZE_COUNT * 3000;
      TR.detail[6] = {id:6, label:"Oversize Service — Dec 1", provider:"manual", started_at_ms:oversizeStart, ended_at_ms:oversizeEnd, notes_generated:false, segments:oversizeSegs};
      TR.list.push({id:6, label:"Oversize Service — Dec 1", provider:"manual", started_at_ms:oversizeStart, ended_at_ms:oversizeEnd, segment_count:TR_OVERSIZE_COUNT});
    }
    // A transcript with 120 detections — comfortably past the LIVE console's `MAX_DETECTIONS =
    // 32` queue cap — for the bounded-DOM-rendering check on the detections panel (86akgqdxr
    // AC5). Seeded only on request (window.__trSeedManyDetections), same reasoning as the
    // fixtures above: an unconditional 9th list entry would break earlier "exactly N
    // transcripts" checks that run before this block is ever reached. Each detection's
    // reference names its own index so a check can assert exactly which ones are/aren't mounted,
    // the same technique the 500-segment fixture above uses for the transcript log.
    if (window.__trSeedManyDetections && !window.__trManyDetectionsSeeded) {
      window.__trManyDetectionsSeeded = true;
      var manyDets = [];
      var TR_MANY_DET_COUNT = 120;
      for (var di = 0; di < TR_MANY_DET_COUNT; di++) {
        manyDets.push({id: 40000 + di, reference: "Detection " + di + " — Psalm " + (di + 1) + ":1", source_segment: 0, confidence: 80});
      }
      var manyDetStart = 1733000000000, manyDetEnd = manyDetStart + 3000;
      TR.detail[8] = {id:8, label:"Many Detections Service — Dec 15", provider:"manual", started_at_ms:manyDetStart, ended_at_ms:manyDetEnd,
        notes_generated:false, detections:manyDets, corrections:[], draft:null, scripture_verification_note:null,
        ai_generated:null, ai_label:null, disclosure:null, notes_provider:null,
        segments: [ {id:50000, start_ms:0, end_ms:2500, text:"A single short segment is enough for this fixture."} ] };
      TR.list.push({id:8, label:"Many Detections Service — Dec 15", provider:"manual", started_at_ms:manyDetStart, ended_at_ms:manyDetEnd, segment_count:1});
    }
    if (cmd === "transcript_list") {
      if (window.__trListFailOnce) { window.__trListFailOnce = false; return Promise.reject("simulated host rejection"); }
      return Promise.resolve(TR.list.map(function(t){ return {id:t.id, label:t.label, provider:t.provider, started_at_ms:t.started_at_ms, ended_at_ms:t.ended_at_ms, segment_count:t.segment_count}; }));
    }
    if (cmd === "transcript_get") {
      if (window.__trGetFailOnce) { window.__trGetFailOnce = false; return Promise.reject("simulated host rejection"); }
      var td = TR.detail[args.id];
      if (!td) return Promise.reject("row not found");
      return Promise.resolve(JSON.parse(JSON.stringify(td)));
    }
    // --- Generate Sermon Notes from a STORED transcript (86akcffy0; FR-122/130) ---------------
    // `note_generation_limits` mirrors `selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS`
    // — a real host always returns 400000 here; the driver never overrides it, so a check that
    // wants an "over the clamp" transcript builds one bigger than this exact number.
    if (cmd === "note_generation_limits") {
      // Vera performance review (PERF-2, re-check): lets a check hold EVERY concurrent call
      // PENDING (a queue, not a single slot — `loadNoteCharLimit` has no in-flight
      // de-duplication, so N rapid clicks genuinely issue N of these before the first resolves)
      // so a check can fire several rapid clicks, then resolve them ALL — in order — and assert
      // only ONE preview ever rendered. Same deferred-promise convention as
      // window.__trGenDeferred (Sana F3), extended to a queue for this multi-in-flight case.
      if (window.__trLimitsDeferred) {
        return new Promise(function (resolve) {
          window.__trLimitsPendingResolvers = window.__trLimitsPendingResolvers || [];
          window.__trLimitsPendingResolvers.push(function () { resolve({ max_transcript_chars: 400000 }); });
        });
      }
      return Promise.resolve({ max_transcript_chars: 400000 });
    }
    if (cmd === "transcript_generate_notes") {
      // Consent-gated exactly like `generate_sermon_notes` (same shared `P.cloud_notes_consent`
      // — the real backend reads ONE `ProvidersConfig` for both flows): no notes consent → the
      // SAME `consent_required` shape, zero draft ever produced.
      if (!P.cloud_notes_consent)
        return Promise.resolve({ok:false, error:"consent_required", message:"cloud notes consent is off"});
      var tg = window.__trGen || "not_configured";
      if (tg === "ok") {
        var trOkDraft = {title:"From-History Sermon", summary:"A summary drawn from the complete stored transcript.",
          sections:[
            {heading:"Main points", items:[], points:[
              {text:"The whole service is in view here, not a recent window", sub_points:["That is the point of this ticket"]}
            ]},
            {heading:"Prayer points", items:["Give thanks for the whole message being preserved"], points:[]}
          ],
          scriptures:["John 3:16"]};
        var td2 = TR.detail[args.id];
        // Mirror the real backend: a successful from-history generate persists directly against
        // the SELECTED id (never "the active transcript") — `notes_generated` becomes true for
        // exactly this row, same invariant `sermon_note_repo::find_by_transcript` gives the
        // real `transcript_get`. 86akgqdxr: the draft's REAL content is now also mirrored onto
        // the fixture, so closing and reopening this same transcript (a fresh `transcript_get`)
        // shows the content it actually just generated, not just the notes_generated flag.
        if (td2) {
          td2.notes_generated = true;
          td2.draft = trOkDraft;
          td2.ai_generated = true;
          td2.ai_label = "AI-generated draft";
          td2.disclosure = "AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.";
          td2.notes_provider = "OpenAI";
          td2.scripture_verification_note = null;
        }
        var trOkResponse = {
          ok:true, degraded:false, provider:"OpenAI",
          ai_generated:true, ai_label:"AI-generated draft",
          disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
          degraded_notice:null,
          draft: trOkDraft,
          transcript_id: args.id,
          quota:null,
          clamp: window.__trGenClamp || null,
        };
        // TR F3 (race guard) support: when armed, the call stays PENDING until the driver
        // explicitly resolves it via window.__trGenResolveDeferred() — lets a check insert a
        // transcript switch BETWEEN Confirm and the response landing, mirroring how
        // "start_listening" (window.__startCtl) is already deferred elsewhere in this harness.
        if (window.__trGenDeferred) {
          return new Promise(function (resolve) {
            window.__trGenResolveDeferred = function () { resolve(trOkResponse); };
          });
        }
        return Promise.resolve(trOkResponse);
      }
      if (tg === "transport") return Promise.reject("network down");
      if (tg === "regenerate_pending" || tg === "regenerate_pending_degraded") {
        // FR-129 (86akgqdx8): mirrors the PP `regenerate_pending`/`regenerate_pending_degraded`
        // branches above — a caller is expected to have already generated a real accepted draft
        // for `args.id` (e.g. via `window.__trGen = "ok"` first), the real backend's own precondition.
        var trRegenDegraded = (tg === "regenerate_pending_degraded");
        var td3 = TR.detail[args.id];
        var trRegenPreviousView = td3 && td3.draft ? Object.assign({}, td3.draft) : null;
        var trRegenDraft = trRegenDegraded
          ? {title:"Offline outline (regenerated)", summary:null,
             sections:[{heading:"Outline", items:["a placeholder point"], points:[]}], scriptures:[]}
          : {title:"From-History Sermon (regenerated)",
             summary:"A revised summary drawn from the complete stored transcript.",
             sections:[{heading:"Main points", items:["A different point this time"], points:[]}],
             scriptures:["John 3:16"]};
        if (td3) {
          td3.pending = { draft: trRegenDraft, ai_generated: !trRegenDegraded,
            disclosure: trRegenDegraded ? null : "disc",
            provider: trRegenDegraded ? "Local (offline)" : "OpenAI" };
        }
        return Promise.resolve({
          ok:true, degraded: trRegenDegraded, provider: trRegenDegraded ? "Local (offline)" : "OpenAI",
          ai_generated: !trRegenDegraded, ai_label:"AI-generated draft",
          disclosure: trRegenDegraded ? null : "disc",
          degraded_notice: trRegenDegraded
            ? "The AI provider could not be reached, so this is an offline outline built from your transcript — not AI-generated notes. The headings are placeholders for you to fill in. Try again when you are back online."
            : null,
          draft: trRegenDraft,
          transcript_id: args.id,
          quota:null,
          clamp: window.__trGenClamp || null,
          pending_confirmation: true,
          previous_draft: trRegenPreviousView,
        });
      }
      return Promise.resolve({ok:false, error:"not_configured", message:"the SelahCue cloud service is not configured"});
    }
    // Detector liveness (HOST-SIGNAL-WEBVIEW-CONTRACT Tier 1a). All four keys always present.
    // __detHealthFail simulates a host with no such command — the UNKNOWN case, which is the one
    // the old `else -> NO SIGNAL` shape got wrong.
    if (cmd === "detection_health") {
      if (window.__detHealthFail) return Promise.reject("no such command");
      return Promise.resolve(window.__detHealth || {state:"idle", provider:null, error:null, can_retry:false});
    }
    if (cmd === "retry_detection") {
      if (window.__detRetryRefuse) return Promise.reject(window.__detRetryRefuse);
      window.__detHealth = {state:"listening", provider:"whisper-small", error:null, can_retry:false};
      return Promise.resolve(window.__detHealth);
    }
    if (cmd === "deck_restore") {
      var ti=-1; for (var k=0;k<LIB.trash.length;k++) if (LIB.trash[k].id===args.id) ti=k;
      // Refusal is a REJECTED PROMISE with an operator-facing reason — never a silent no-op.
      if (ti<0) return Promise.reject("That presentation can no longer be restored.");
      var back=LIB.trash.splice(ti,1)[0].deck;
      // The name can differ: if it was taken while the deck sat in the trash it is uniquified.
      back.name=libUnique(back.name);
      LIB.decks.push(back);
      var rv=libView(); rv.restored_name=back.name;
      return Promise.resolve(rv);
    }
    if (cmd === "render_deck_slide") {
      // Vary the rendered pixel by (currently-open deck, requested slide id) so a stale-cache
      // collision across decks sharing a local slide id is actually detectable by CONTENT, not
      // just by an id match (17tnw2axwve). render_deck_slide is itself deck-BLIND on the real host
      // (no deck-id argument — it renders whichever deck is currently open), mirrored here via
      // LIB.open. Both "pixels" in the 2x1 frame are identical so a cache-hit redraw (which scales
      // the cached 2x1 image up into whatever size the tile's canvas currently is) reads back a
      // flat, unambiguous colour at any sample point — no interpolation edge case.
      var rdR = (37 + LIB.open * 41 + args.id * 7) % 256;
      var rdG = (91 + LIB.open * 23 + args.id * 13) % 256;
      var rdB = (17 + LIB.open * 11 + args.id * 53) % 256;
      var rdPx = String.fromCharCode(rdR, rdG, rdB, 255);
      return Promise.resolve({available:true, frame:{w:2, h:1, rgba: btoa(rdPx + rdPx)}});
    }
    if (cmd === "deck_add_slide") {
      var nid = D.slides.length + 1;
      D.slides.push({id:nid, n:nid, lines:["Empty slide"], kind:"text"});
      D.count = D.slides.length; D.selected = nid;
      D.slide = {id:nid, elements:[], selected_element:null, notes:"", transition:"cut", auto_advance_secs:null, has_background:false};
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_select_slide") {
      D.selected = args.id;
      D.slide = {id:args.id, elements:[], selected_element:null, notes:"", transition:"cut", auto_advance_secs:null, has_background:false};
      return Promise.resolve(dClone());
    }
    if (cmd === "deck_add_element") {
      var ne = {index:D.slide.elements.length, kind:args.kind, x:200,y:430,w:600,h:160,z:0,visible:true, opacity:255};
      if (args.kind === "text") { ne.label="Text"; ne.text="Text"; ne.size_permille=90; ne.line_height_permille=1100; ne.weight=400; ne.align_h="left"; ne.align_v="top"; ne.color={r:240,g:240,b:245,a:255}; ne.fit="shrink_to_fit"; }
      else { ne.label="Shape"; ne.fill={r:124,g:92,b:255,a:255}; ne.border={r:0,g:0,b:0,a:0}; ne.border_permille=0; ne.corner_permille=16; ne.variant="rect"; }
      D.slide.elements.push(ne);
      D.slide.selected_element = D.slide.elements.length - 1;
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_add_image_element") {
      D.slide.elements.push({index:D.slide.elements.length, kind:"image", label:"img", name:"harvest.jpg", source:"demo://harvest field.jpg", missing:false, x:200,y:250,w:600,h:460,z:0,visible:true, opacity:255, fit:"stretch"});
      D.slide.selected_element = D.slide.elements.length - 1;
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_update_element") {
      var eu = D.slide.elements[args.index]; if (eu) { for (var k in args.patch) eu[k] = args.patch[k]; } return Promise.resolve(dEdit());
    }
    if (cmd === "deck_replace_element_image") {
      var er = D.slide.elements[args.index], ar = D.media.assets.filter(function(a){return a.id===args.mediaId;})[0];
      if (er && ar) { er.source = ar.path; er.name = ar.name; er.missing = false; } return Promise.resolve(dEdit());
    }
    if (cmd === "deck_select_element") { D.slide.selected_element = args.index; return Promise.resolve(dClone()); }
    if (cmd === "deck_move_element") {
      var e = D.slide.elements[args.index]; if (e) { e.x=args.x; e.y=args.y; e.w=args.w; e.h=args.h; }
      D.slide.selected_element = args.index; return Promise.resolve(dEdit());
    }
    if (cmd === "deck_set_element_z") { var e2=D.slide.elements[args.index]; if(e2) e2.z=args.z; return Promise.resolve(dEdit()); }
    if (cmd === "deck_reorder_elements") { var n=D.slide.elements.length; args.order.forEach(function(i,k){ if(D.slide.elements[i]) D.slide.elements[i].z = n-1-k; }); return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_element_text") { var et=D.slide.elements[args.index]; if(et && et.kind==="text"){ et.text=args.text; et.label=(args.text||"").split("\\n")[0]; } return Promise.resolve(dEdit()); }
    if (cmd === "deck_toggle_element_visible") { var e3=D.slide.elements[args.index]; if(e3) e3.visible=!e3.visible; return Promise.resolve(dEdit()); }
    if (cmd === "deck_remove_element") { D.slide.elements.splice(args.index,1); D.slide.selected_element=null; return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_notes") { D.slide.notes = args.notes; return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_transition") { D.slide.transition = args.transition; return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_auto_advance") { D.slide.auto_advance_secs = args.secs; return Promise.resolve(dEdit()); }
    if (cmd === "deck_undo") { D.can_undo = false; D.can_redo = true; return Promise.resolve(dClone()); }
    if (cmd === "deck_redo") { D.can_redo = false; D.can_undo = true; return Promise.resolve(dClone()); }
    if (cmd === "deck_go_live") { D.live = D.selected; V.live_authored_id = D.selected; return Promise.resolve(dClone()); }
    if (cmd === "deck_go_live_delta") {
      var gids = D.slides.map(function(s){ return s.id; });
      var gcur = (V.live_authored_id != null) ? gids.indexOf(V.live_authored_id) : gids.indexOf(D.selected);
      if (gcur < 0) gcur = 0;
      var gnx = Math.max(0, Math.min(gids.length - 1, gcur + args.delta));
      D.selected = gids[gnx]; D.live = gids[gnx]; V.live_authored_id = gids[gnx];
      return Promise.resolve(dClone());
    }
    if (cmd === "output_connected") return Promise.resolve(window.__outputConnected !== false);
    if (cmd === "deck_remove_slide") {
      D.slides = D.slides.filter(function(s){ return s.id !== args.id; });
      D.count = D.slides.length;
      D.slides.forEach(function(s, i){ s.n = i + 1; });
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_duplicate_slide" || cmd === "deck_reorder_slide")
      return Promise.resolve(dEdit());
    if (cmd === "deck_import_image") {
      D.media.assets.push({id:99,name:"picked.png",kind:"image",size_label:"1.0 MB",missing:false,unused:true});
      D.media.unused_count += 1; return Promise.resolve(dClone());
    }
    if (cmd === "deck_remove_media") return Promise.resolve(dClone());
    // --- Providers & Privacy (Settings 338:124) ---
    if (cmd === "providers_view") return Promise.resolve(ppView()); // the resync read is NEVER rejected
    // One-shot rejection hook for the PP MUTATION commands only (not providers_view): lets the driver
    // exercise the "host rejected a setting" path — the optimistic control must revert to the
    // backend-confirmed value (mutate() resyncs), never showing a state the backend didn't confirm.
    var __ppSet = (cmd==="set_transcription_mode"||cmd==="set_cloud_consent"||cmd==="set_notes_template"||
                   cmd==="set_preferred_translation"||cmd==="set_include_flag"||
                   cmd==="set_account_token"||cmd==="clear_account_token");
    if (__ppSet && window.__ppRejectOnce) { window.__ppRejectOnce = false; return Promise.reject("simulated host rejection"); }
    if (cmd === "set_transcription_mode") { P.transcription_mode = args.mode; return Promise.resolve(ppView()); }
    if (cmd === "set_cloud_consent") {
      if (args.kind === "transcription") P.cloud_transcription_consent = !!args.enabled;
      else if (args.kind === "notes") P.cloud_notes_consent = !!args.enabled;
      return Promise.resolve(ppView());
    }
    if (cmd === "set_notes_template") { P.notes_template = args.template; return Promise.resolve(ppView()); }
    if (cmd === "set_preferred_translation") {
      // Mirror the backend: only an installed code is accepted (unknown → keep current).
      if (P.translations.some(function(t){ return t.code === args.code; })) P.preferred_translation = args.code;
      return Promise.resolve(ppView());
    }
    if (cmd === "set_include_flag") { if (args.name in P.include) P.include[args.name] = !!args.enabled; return Promise.resolve(ppView()); }
    if (cmd === "set_account_token") { P.account_token_set = !!(args.token && args.token.length); return Promise.resolve(ppView()); }
    if (cmd === "clear_account_token") { P.account_token_set = false; return Promise.resolve(ppView()); }
    if (cmd === "generate_sermon_notes") {
      // Consent-gated end to end (mirrors the backend): no notes consent → consent_required; else the
      // driver picks the outcome via window.__ppGen ("ok" | "not_configured" | "quota_exceeded").
      if (!P.cloud_notes_consent)
        return Promise.resolve({ok:false, error:"consent_required", message:"cloud notes consent is off"});
      var g = window.__ppGen || "not_configured";
      if (g === "ok") {
        var snOkDraft = {title:"Grace That Feeds", summary:"A sermon on provision and grace.",
          sections:[
            // FR-122: an outline section carries `points` with nested sub_points and NO items.
            {heading:"Main points", items:[], points:[
              {text:"The crowd came back for the wrong reason", sub_points:["They ate of the loaves","A full church is not a fed one"]},
              {text:"Jesus does not shame the hunger", sub_points:["He redirects it"]}
            ]},
            // A flat section carries `items` and NO points.
            {heading:"Prayer points", items:["Thank God for provision","Pray for the hungry"], points:[]}
          ],
          scriptures:["Isaiah 61:5","John 6:35"]};
        var snOkAiLabel = "AI-generated draft";
        var snOkDisclosure = "AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.";
        // 86akgqdv0: save-on-generate — the real backend persists best-effort against the source
        // transcript's row id; mirrored here so `load_sermon_note_draft`/`update_sermon_note_draft`
        // below have something real to read/edit, exactly like the real SQLite-backed store would.
        SN.draft = { transcript_id: SN_TRANSCRIPT_ID, draft: snOkDraft, ai_generated:true,
          ai_label: snOkAiLabel, disclosure: snOkDisclosure, provider:"OpenAI" };
        return Promise.resolve({
          ok:true, degraded:false, provider:"OpenAI",
          // FR-123/128: a model draft is labelled and carries the fabrication warning. `disclosure`
          // is non-null exactly when `ai_generated`, mirroring the backend.
          ai_generated:true, ai_label:snOkAiLabel, disclosure:snOkDisclosure,
          degraded_notice:null,
          draft: snOkDraft,
          transcript_id: SN_TRANSCRIPT_ID, // null in the real backend only when persistence failed
          quota:null   // no metering in Phase 1 — the backend returns null even on success
        });
      }
      if (g === "degraded") {
        var snDegDraft = {title:"Offline outline", summary:null,
          sections:[
            {heading:"Outline", items:["point one"], points:[]},
            // 86akc0tua: a (hypothetical — the real backend never sends this combination,
            // since `local.rs` never populates `caveats`) caveated empty section on a
            // DEGRADED draft. Proves the console suppresses the empty-requested line via
            // `currentDraft.degraded` itself, not merely that the real backend happens
            // never to combine the two — a mutation deleting that guard would still be
            // caught here even though it could never be caught by a realistic fixture.
            {heading:"Prayer points", items:[], points:[], empty_requested:true}
          ], scriptures:[], caveats:[{kind:"section_empty", heading:"Prayer points"}]};
        // A degraded (offline-fallback) draft is STILL persisted by the real backend — FR-123
        // "editable" applies to it too, it is just not labelled AI-generated (see below).
        SN.draft = { transcript_id: SN_TRANSCRIPT_ID, draft: snDegDraft, ai_generated:false,
          ai_label:"AI-generated draft", disclosure:null, provider:"Local (offline)" };
        return Promise.resolve({
          ok:true, degraded:true, provider:"Local (offline)",
          // The offline scaffold is NOT a model: no AI label, no fabrication warning — but it does
          // carry its own notice, because the operator asked for AI notes and did not get them.
          ai_generated:false, ai_label:"AI-generated draft", disclosure:null,
          degraded_notice:"The AI provider could not be reached, so this is an offline outline built from your transcript — not AI-generated notes. The headings are placeholders for you to fill in. Try again when you are back online.",
          draft: snDegDraft,
          transcript_id: SN_TRANSCRIPT_ID,
          quota:null
        });
      }
      if (g === "empty_sections") {
        // 86akc0tua: one draft carrying BOTH states at once (Uma's own instruction — assert
        // ON+empty and a populated positive control from the SAME render, not two fixtures).
        // "Notable quotations" is deliberately absent altogether, simulating a section the
        // operator left switched off: no heading, no message, nothing.
        var snEmptyDraft = {
          title:"A Quiet Sunday", summary:null,
          sections:[
            {heading:"Illustrations", items:["The mill closed after nineteen years."], points:[], empty_requested:false},
            {heading:"Chapter markers", items:[], points:[], empty_requested:true}
          ],
          scriptures:[],
          caveats:[
            {kind:"section_empty", heading:"Chapter markers"},
            {kind:"section_empty", heading:"Summary"},
            {kind:"section_empty", heading:"Scripture references"}
          ],
          scripture_verdicts:[]
        };
        SN.draft = { transcript_id: SN_TRANSCRIPT_ID, draft: snEmptyDraft, ai_generated:true,
          ai_label:"AI-generated draft", disclosure:"disc", provider:"OpenAI" };
        return Promise.resolve({
          ok:true, degraded:false, provider:"OpenAI",
          ai_generated:true, ai_label:"AI-generated draft",
          disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
          degraded_notice:null,
          draft: snEmptyDraft,
          transcript_id: SN_TRANSCRIPT_ID,
          quota:null
        });
      }
      if (g === "scripture_verification") {
        // 86akby820 (FR-125/FR-128): a real reference (positive control), a fabricated
        // reference IN the extracted list, and a fabricated reference found ONLY embedded
        // in a section's body text (Jude 2:1 — not in `scriptures` at all) — all in one
        // render, so ON/unverified/embedded-only/positive-control are proven together.
        var snScriptDraft = {
          title:"Grace in the Wilderness", summary:"A sermon on provision.",
          sections:[
            {heading:"Illustrations", items:["This truth is affirmed in Jude 2:1 as well."], points:[], empty_requested:false}
          ],
          // "3Jn 4:12" — an ABBREVIATED spelling, deliberately not the canonical "3 John
          // 4:12" — end-to-end-verifies the JS side's contract that a verdict is matched
          // to a scriptures-list entry by EXACT string, whatever spelling the model used
          // (security review, Sana F1 on PR #47; the Rust-level regression that the
          // BACKEND echoes back the caller's own spelling, not a re-canonicalised one,
          // lives in selahcue-core's own test suite, which a JS-level mock cannot reach).
          scriptures:["John 3:16","3Jn 4:12"],
          caveats:[
            {kind:"scripture_unverified", reference:"3Jn 4:12"},
            {kind:"scripture_unverified", reference:"Jude 2:1"}
          ],
          scripture_verdicts:[
            {reference:"John 3:16", verified:true},
            {reference:"3Jn 4:12", verified:false},
            {reference:"Jude 2:1", verified:false}
          ]
        };
        SN.draft = { transcript_id: SN_TRANSCRIPT_ID, draft: snScriptDraft, ai_generated:true,
          ai_label:"AI-generated draft", disclosure:"disc", provider:"OpenAI" };
        return Promise.resolve({
          ok:true, degraded:false, provider:"OpenAI",
          ai_generated:true, ai_label:"AI-generated draft",
          disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
          degraded_notice:null,
          scripture_verification_note:"Verified means the reference address exists in the bundled Bible text — it does not confirm that any words this draft attributes to it are accurate. Always check a quotation against the actual text before you use it.",
          draft: snScriptDraft,
          transcript_id: SN_TRANSCRIPT_ID,
          quota:null
        });
      }
      if (g === "scripture_incomplete") {
        // 86akgqdwc (Sana F2 on PR #48): the embedded-scripture scan hit its budget before
        // scanning every section — a SEPARATE, minimal fixture from "scripture_verification"
        // above (which already exercises verified/unverified/embedded-only marks) so this
        // one new caveat kind's rendering is proven in isolation, not entangled with those.
        var snIncompleteDraft = {
          title:"A Long Sermon", summary:"A sermon with many references.",
          sections:[
            {heading:"Podcast show notes", items:["Title: A Long Sermon", "Scripture referenced: Isaiah 55:1"], points:[], empty_requested:false}
          ],
          scriptures:["John 3:16"],
          caveats:[{kind:"scripture_verification_incomplete"}],
          scripture_verdicts:[{reference:"John 3:16", verified:true}]
        };
        SN.draft = { transcript_id: SN_TRANSCRIPT_ID, draft: snIncompleteDraft, ai_generated:true,
          ai_label:"AI-generated draft", disclosure:"disc", provider:"OpenAI" };
        return Promise.resolve({
          ok:true, degraded:false, provider:"OpenAI",
          ai_generated:true, ai_label:"AI-generated draft",
          disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
          degraded_notice:null,
          scripture_verification_note:"Verified means the reference address exists in the bundled Bible text — it does not confirm that any words this draft attributes to it are accurate. Always check a quotation against the actual text before you use it.",
          draft: snIncompleteDraft,
          transcript_id: SN_TRANSCRIPT_ID,
          quota:null
        });
      }
      // FR-129 (86akgqdx8): regenerate-with-retention. These two branches are DELIBERATELY ISOLATED
      // from every "g" branch above — none of them check `SN.draft` before overwriting it, which is
      // intentional (rewriting them to be "realistic" would ripple through every existing PP C-*/SN-*
      // assertion in this file that assumes generate == immediate replace, none of which is this
      // ticket's concern to touch). A caller of these two branches is expected to have ALREADY put a
      // real accepted draft into `SN.draft` (e.g. via `window.__ppGen = "ok"` first) — exactly mirroring
      // the real backend's own precondition ("regenerate requires something to regenerate from").
      if (g === "regenerate_pending" || g === "regenerate_pending_degraded") {
        var regenDegraded = (g === "regenerate_pending_degraded");
        var regenDraft = regenDegraded
          ? {title:"Offline outline (regenerated)", summary:null,
             sections:[{heading:"Outline", items:["a placeholder point"], points:[]}], scriptures:[]}
          : {title:"Grace That Feeds (regenerated)", summary:"A revised summary on provision and grace.",
             sections:[{heading:"Main points", items:["A different point this time"], points:[]}],
             scriptures:["Isaiah 61:5"]};
        // The PREVIOUS (accepted) draft, exactly as `SN.draft` already holds it — untouched by
        // staging, mirroring the real `sermon_note_repo::stage_regeneration`'s core guarantee.
        var regenPreviousView = SN.draft ? Object.assign({}, SN.draft.draft) : null;
        SN.pending = {
          transcript_id: SN_TRANSCRIPT_ID, draft: regenDraft,
          ai_generated: !regenDegraded, disclosure: regenDegraded ? null : "disc",
          provider: regenDegraded ? "Local (offline)" : "OpenAI",
        };
        return Promise.resolve({
          ok:true, degraded: regenDegraded, provider: SN.pending.provider,
          ai_generated: SN.pending.ai_generated, ai_label:"AI-generated draft",
          disclosure: SN.pending.disclosure,
          degraded_notice: regenDegraded
            ? "The AI provider could not be reached, so this is an offline outline built from your transcript — not AI-generated notes. The headings are placeholders for you to fill in. Try again when you are back online."
            : null,
          draft: regenDraft,
          transcript_id: SN_TRANSCRIPT_ID,
          quota:null,
          pending_confirmation: true,
          previous_draft: regenPreviousView,
        });
      }
      if (g === "timestamps") {
        // 86akgqdw0 (FR-124): the Settings surface has no transcript-log virtualizer to jump
        // within (see settings.js's own header comment on `timestampFor`), so this proves
        // ONLY the data-parity half — a plain, non-clickable label renders for a matching
        // item, and "Copy chapter markers" produces the right export text. "Bogus type"
        // carries a non-numeric offset (the malformed case) and must render NO label at all.
        var snTsDraft = {
          title:"Timestamps Fixture", summary:null,
          sections:[
            {heading:"Chapter markers", items:["Opening prayer","Bogus type"], points:[], empty_requested:false}
          ],
          scriptures:[], caveats:[], scripture_verdicts:[],
          timestamps:[
            {heading:"Chapter markers", text:"Opening prayer", offset_ms:4000},
            {heading:"Chapter markers", text:"Bogus type", offset_ms:"not-a-number"}
          ]
        };
        SN.draft = { transcript_id: SN_TRANSCRIPT_ID, draft: snTsDraft, ai_generated:true,
          ai_label:"AI-generated draft", disclosure:"disc", provider:"OpenAI" };
        return Promise.resolve({
          ok:true, degraded:false, provider:"OpenAI",
          ai_generated:true, ai_label:"AI-generated draft",
          disclosure:"AI-generated. It can invent quotations, misattribute scripture and state things the sermon did not say. Check every reference and quotation against the transcript before you publish or project it.",
          degraded_notice:null,
          draft: snTsDraft,
          transcript_id: SN_TRANSCRIPT_ID,
          quota:null
        });
      }
      if (g === "quota_exceeded") return Promise.resolve({ok:false, error:"quota_exceeded", message:"monthly limit reached"});
      if (g === "transport") return Promise.reject("network down"); // invoke rejects → onGenerate .catch → transport
      if (g === "malformed") return Promise.resolve({ok:false, error:"malformed", message:"bad response"});
      return Promise.resolve({ok:false, error:"not_configured", message:"the SelahCue cloud service is not configured"});
    }
    // --- 86akgqdv0: sermon-note draft persistence + editing (FR-123 "editable" half) ---------
    // 86akby820 (Sana F4 remediation): the REAL backend re-verifies fresh from the
    // persisted `scriptures`/`sections` on every load/edit-save, rather than trusting a
    // stale stored verdict — this small helper mirrors that against the same "known good"
    // reference the mock's own fixtures already use, so `load_sermon_note_draft` and
    // `update_sermon_note_draft` below simulate re-verification rather than merely
    // echoing back whatever verdicts happened to be attached at generate time.
    var MOCK_VERIFIED_REFS = ["John 3:16"];
    function mockReVerify(scriptures) {
      var verdicts = (scriptures || []).map(function (ref) {
        return { reference: ref, verified: MOCK_VERIFIED_REFS.indexOf(ref) !== -1 };
      });
      var caveats = verdicts.filter(function (v) { return !v.verified; }).map(function (v) {
        return { kind: "scripture_unverified", reference: v.reference };
      });
      var note = verdicts.length
        ? "Verified means the reference address exists in the bundled Bible text — it does not confirm that any words this draft attributes to it are accurate. Always check a quotation against the actual text before you use it."
        : null;
      return { verdicts: verdicts, caveats: caveats, note: note };
    }
    if (cmd === "load_sermon_note_draft") {
      if (!SN.draft) return Promise.resolve({ok:false}); // no persistence connection / nothing saved
      var loadReVerified = mockReVerify(SN.draft.draft.scriptures);
      var loadDraft = Object.assign({}, SN.draft.draft, {
        scripture_verdicts: loadReVerified.verdicts, caveats: loadReVerified.caveats,
      });
      return Promise.resolve({
        ok:true, transcript_id:SN.draft.transcript_id,
        ai_generated:SN.draft.ai_generated, ai_label:SN.draft.ai_label,
        disclosure:SN.draft.disclosure, provider:SN.draft.provider,
        scripture_verification_note: loadReVerified.note,
        draft: loadDraft
      });
    }
    if (cmd === "update_sermon_note_draft") {
      // One-shot rejection hooks: let the driver exercise the backend's own refusal paths — an
      // edit for a transcript with no saved draft, and an oversized field rejected by the bound
      // check — WITHOUT the mock silently accepting everything the way `Promise.resolve(null)`
      // would for an unhandled command.
      if (window.__snRejectNotFound) { window.__snRejectNotFound = false;
        return Promise.resolve({ok:false, error:"not_found", message:"No saved draft exists for this transcript."}); }
      if (window.__snRejectTooLarge) { window.__snRejectTooLarge = false;
        return Promise.resolve({ok:false, error:"too_large", message:"sermon_note.title exceeds 300 characters"}); }
      // 86akgqdxr: this command is ALREADY transcript-id-generic on the real backend (confirmed
      // by reading the full call chain — Backend::update_sermon_note_draft -> LAN
      // Command::UpdateSermonNoteDraft -> LiveController::apply, none of which special-case "the
      // active transcript"), so the Transcripts workspace calls it for a HISTORICAL transcript
      // via the exact same command settings.js's live-session panel already used. The mock
      // therefore needs a SECOND branch, keyed against `window.__TR.detail[id]` instead of the
      // single `SN.draft` — checked only when the id does not match `SN.draft`'s, so every
      // existing Settings-panel test (all of which use `SN`) is completely unaffected.
      var trDetailForEdit = window.__TR && window.__TR.detail && window.__TR.detail[args.transcriptId];
      if ((!SN.draft || SN.draft.transcript_id !== args.transcriptId) && trDetailForEdit && trDetailForEdit.draft) {
        var trUpdated = {
          title: args.title,
          summary: args.summary,
          sections: (args.sections || []).map(function(s){
            return { heading: s.heading, items: s.items || [], points: s.points || [] };
          }),
          scriptures: args.scriptures || []
        };
        var trReVerified = mockReVerify(trUpdated.scriptures);
        trUpdated.scripture_verdicts = trReVerified.verdicts;
        trUpdated.caveats = trReVerified.caveats;
        trDetailForEdit.draft = trUpdated;
        return Promise.resolve({
          ok:true, transcript_id: args.transcriptId,
          ai_generated: trDetailForEdit.ai_generated, ai_label: trDetailForEdit.ai_label,
          disclosure: trDetailForEdit.disclosure, provider: trDetailForEdit.notes_provider,
          scripture_verification_note: trReVerified.note,
          draft: trUpdated
        });
      }
      if (!SN.draft || SN.draft.transcript_id !== args.transcriptId)
        return Promise.resolve({ok:false, error:"not_found", message:"No saved draft exists for this transcript."});
      // `ai_generated`/`disclosure`/`provider` are NOT accepted as arguments at all (mirrors the
      // real `sermon_note_repo::update`, which cannot touch those columns) — only ever re-read
      // from what was already persisted, never from `args`.
      var snUpdated = {
        title: args.title,
        summary: args.summary,
        sections: (args.sections || []).map(function(s){
          return { heading: s.heading, items: s.items || [], points: s.points || [] };
        }),
        scriptures: args.scriptures || []
      };
      var updateReVerified = mockReVerify(snUpdated.scriptures);
      snUpdated.scripture_verdicts = updateReVerified.verdicts;
      snUpdated.caveats = updateReVerified.caveats;
      SN.draft.draft = snUpdated;
      return Promise.resolve({
        ok:true, transcript_id:SN.draft.transcript_id,
        ai_generated:SN.draft.ai_generated, ai_label:SN.draft.ai_label,
        disclosure:SN.draft.disclosure, provider:SN.draft.provider,
        scripture_verification_note: updateReVerified.note,
        draft:snUpdated
      });
    }
    // FR-129 (86akgqdx8): regenerate-with-retention confirm/discard. ONE shared handler for
    // both surfaces — same dual PP (`SN`) / TR (`window.__TR.detail`) branch shape as
    // `update_sermon_note_draft` just above, for the identical reason (this command is already
    // transcript-id-generic on the real backend).
    if (cmd === "confirm_sermon_note_regeneration" || cmd === "discard_sermon_note_regeneration") {
      var isRegenConfirm = (cmd === "confirm_sermon_note_regeneration");
      if (SN.draft && SN.draft.transcript_id === args.transcriptId) {
        if (!SN.pending)
          return Promise.resolve({ok:false, error:"refused", message:"Nothing is pending for this transcript."});
        // "Once AI-generated, always AI-generated" — mirrors the real
        // `sermon_note_repo::confirm_regeneration`'s guard exactly (the case a degraded
        // regenerate produces): refuse the CONFIRM, but leave the pending draft staged either
        // way (Discard is unaffected by this guard — it never touches accepted content).
        if (isRegenConfirm) {
          if (SN.draft.ai_generated && !SN.pending.ai_generated) {
            return Promise.resolve({ok:false, error:"refused",
              message:"Accepting this would remove the AI-generated label from an already AI-generated draft."});
          }
          SN.draft = SN.pending;
        }
        SN.pending = null;
        var regenReVerified = mockReVerify(SN.draft.draft.scriptures);
        var regenViewDraft = Object.assign({}, SN.draft.draft, {
          scripture_verdicts: regenReVerified.verdicts, caveats: regenReVerified.caveats,
        });
        return Promise.resolve({
          ok:true, transcript_id: SN.draft.transcript_id,
          ai_generated: SN.draft.ai_generated, ai_label:"AI-generated draft",
          disclosure: SN.draft.disclosure, provider: SN.draft.provider,
          scripture_verification_note: regenReVerified.note,
          draft: regenViewDraft,
        });
      }
      var trDetailForRegen = window.__TR && window.__TR.detail && window.__TR.detail[args.transcriptId];
      if (trDetailForRegen) {
        if (!trDetailForRegen.pending)
          return Promise.resolve({ok:false, error:"refused", message:"Nothing is pending for this transcript."});
        if (isRegenConfirm) {
          if (trDetailForRegen.ai_generated && !trDetailForRegen.pending.ai_generated) {
            return Promise.resolve({ok:false, error:"refused",
              message:"Accepting this would remove the AI-generated label from an already AI-generated draft."});
          }
          trDetailForRegen.draft = trDetailForRegen.pending.draft;
          trDetailForRegen.ai_generated = trDetailForRegen.pending.ai_generated;
          trDetailForRegen.disclosure = trDetailForRegen.pending.disclosure;
          trDetailForRegen.notes_provider = trDetailForRegen.pending.provider;
        }
        trDetailForRegen.pending = null;
        var trRegenReVerified = mockReVerify(trDetailForRegen.draft.scriptures);
        var trRegenViewDraft = Object.assign({}, trDetailForRegen.draft, {
          scripture_verdicts: trRegenReVerified.verdicts, caveats: trRegenReVerified.caveats,
        });
        return Promise.resolve({
          ok:true, transcript_id: args.transcriptId,
          ai_generated: trDetailForRegen.ai_generated, ai_label:"AI-generated draft",
          disclosure: trDetailForRegen.disclosure, provider: trDetailForRegen.notes_provider,
          scripture_verification_note: trRegenReVerified.note,
          draft: trRegenViewDraft,
        });
      }
      return Promise.resolve({ok:false, error:"refused", message:"No accepted draft exists for this transcript."});
    }
    return Promise.resolve(null);
  } },
  event: { listen: function(name, cb){ (window.__ev[name] = window.__ev[name] || []).push(cb); return Promise.resolve(function(){}); } },
  // Tauri's own app-info API (Settings › About & Licensing, 17tnw2axwer, reads app.getVersion()
  // directly — see settings-about.js's header comment for why: it's Tauri's built-in global, not
  // a command this ticket invented). window.__appVersionAvailable lets a check remove this to
  // exercise the honest "—" fallback when the global isn't exposed.
  app: { getVersion: function(){
    return window.__appVersionAvailable === false
      ? Promise.reject(new Error("app info unavailable"))
      : Promise.resolve("0.1.0");
  } } };
  window.__emit = function(name, payload){ (window.__ev[name] || []).forEach(function(cb){ cb({event:name, payload:payload}); }); };
</script>
"""

DRIVER = r"""
<pre id="__r" style="position:fixed;z-index:99999;background:#fff;color:#000"></pre>
<script>
  var R = [];
  function ok(c,m){ R.push((c?"PASS":"FAIL")+": "+m); }
  // The theme JSON captured by the LAST set_custom_theme (Apply) call.
  function applied(){
    document.getElementById("td-apply").click();
    var cs = window.__calls.filter(function(c){return c.cmd==="set_custom_theme";});
    return cs.length ? JSON.parse(cs[cs.length-1].args.themeJson) : null;
  }
  // Add Shape now opens a PICKER (86ajtwq24); choose a geometry (default Rectangle, which
  // keeps the pre-batch behaviour — a rect element with no `variant`).
  function addShape(kind){
    document.querySelector('.td-addbar button[data-add="shape"]').click();
    document.querySelector('#td-shape-row [data-shape="'+(kind||"rect")+'"]').click();
  }
  function el(id){ return document.getElementById(id); }
  var sleep=(ms)=>new Promise(function(r){setTimeout(r,ms);});
  // Poll a predicate up to `tries`×20ms of virtual time instead of a fixed sleep (audit #11):
  // the gate then waits exactly as long as the boot render needs and stays deterministic
  // (bounded) — a fixed sleep would spuriously RED the gate if app.js boot timing ever grew.
  var waitFor=async function(pred, tries){ tries=tries||150; for(var i=0;i<tries;i++){ if(pred()) return true; await sleep(20); } return pred(); };
  var hasRender=function(id){ var s=el(id) && el(id).querySelector(".surface"); return !!(s && s.classList.contains("has-render")); };
  async function run(){
    try {
      // === #7-FIX Preview/Live TRUE render (86ajtwq28) — must fire on BOOT (no nav-click) ===
      // Poll for the boot render to COMPLETE (panels reach has-render) rather than a fixed
      // sleep (audit #11); if it never fires, the poll times out and the checks below FAIL.
      await waitFor(function(){ return hasRender("preview-panel") && hasRender("live-panel"); });
      ok(window.__calls.some(function(c){return c.cmd==="render_console";}), "#7-fix render_console fires on BOOT (no nav-click crutch)");
      ok(el("preview-panel").querySelector(".surface").classList.contains("has-render"), "#7-fix Preview panel shows the true render on boot");
      ok(el("live-panel").querySelector(".surface").classList.contains("has-render"), "#7-fix Live panel shows the true render on boot");
      ok(el("preview-canvas").width===2 && el("preview-canvas").height===1, "#7 preview canvas drawn at the frame size");
      // M5: the tight-loop base64 decode (b64ToBytes) must be BYTE-EXACT — read the preview
      // canvas back and assert the two known stub pixels (red, then green).
      var pd = el("preview-canvas").getContext("2d").getImageData(0, 0, 2, 1).data;
      ok(pd[0]===255 && pd[1]===0 && pd[2]===0 && pd[3]===255 &&
         pd[4]===0 && pd[5]===255 && pd[6]===0 && pd[7]===255,
         "M5 tight base64 decode is byte-exact (preview pixels: " + Array.from(pd).join(",") + ")");
      // #1 the panels are 16:9-ish, NOT a collapsed strip (align-items:flex-start lets aspect-ratio apply).
      var pp = el("preview-panel");
      var ratio = pp.offsetWidth > 0 ? pp.offsetHeight / pp.offsetWidth : 0;
      ok(ratio > 0.35, "#1 preview panel is a 16:9-ish monitor, not a stretched strip (h/w=" + ratio.toFixed(2) + ")");
      // #2 the plan-item kind label truncates (nowrap) so it cannot overflow under the theme dropdown.
      var kindEl = document.querySelector(".item .kind");
      ok(kindEl && getComputedStyle(kindEl).whiteSpace === "nowrap", "#2 plan-item kind label truncates (nowrap), no overflow under the dropdown");
      // Read-only: rendering the console fired NO control command (never changes on air).
      var ctrl = window.__calls.filter(function(c){return ["next","go_live","clear","blackout","select","start_timer"].indexOf(c.cmd)>=0;}).length;
      ok(ctrl===0, "#7 rendering the preview fired no control command (read-only)");
      // available:false (a Remote host / older host) → text fallback, no canvas.
      window.__renderAvailable = false;
      document.querySelector('.nav-item[data-surface="console"]').click(); // re-schedule a render
      await waitFor(function(){ return !hasRender("preview-panel"); }); // poll for the fallback (audit #11)
      ok(!el("preview-panel").querySelector(".surface").classList.contains("has-render"), "#7 available:false → text fallback (no canvas)");
      window.__renderAvailable = true; // restore for the rest of the run

      // === Live Console slide picker (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §1/§2/§4) ===
      // Default (a scripture is staged): Slides tab disabled + its panel hidden (computed display —
      // a class rule must not defeat [hidden] in WKWebView).
      ok(el("ctab-slides").getAttribute("aria-disabled")==="true", "SP: Slides tab disabled when no presentation is staged");
      ok(getComputedStyle(el("cpanel-slides")).display === "none", "SP: Slides panel hidden by COMPUTED display by default (WKWebView-safe)");
      ok(el("ctab-scriptures").getAttribute("aria-selected")==="true", "SP: Scriptures is the default active content tab");

      // Stage a presentation (a slide_group item linked to deck 7) in the real view; the 1s poll and
      // a direct sync agree because V is mutated. The filmstrip auto-surfaces + lists the deck's slides.
      V.items = [V.items[0], {id:2, kind:"slide_group", title:"Sermon Slides", is_live:false, is_staged:true, slide_count:3, slide_index:0, staged_slide_index:0, link:{kind:"deck", id:7, slide_count:3}}];
      V.staged_index = 1; V.staged_scripture = null;
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      await waitFor(function(){ return el("slide-strip").querySelectorAll(".slide-card").length === 3; });
      ok(!el("ctab-slides").hasAttribute("aria-disabled"), "SP: Slides tab enabled when a presentation is staged");
      ok(el("ctab-slides").getAttribute("aria-selected")==="true", "SP: auto-switched to the Slides tab on staging a presentation");
      ok(getComputedStyle(el("cpanel-slides")).display !== "none", "SP: Slides panel visible by COMPUTED display when active");
      ok(getComputedStyle(el("scriptures")).display === "none", "SP: Scriptures panel hidden when Slides is active ([hidden] wins over its flex display)");
      ok(el("slide-strip").querySelectorAll('[role="option"]').length === 3, "SP: the filmstrip lists all 3 slides as role=option cards");
      ok(el("slides-count").textContent === "3" && !el("slides-count").hidden, "SP: the Slides tab count badge reflects slide_count");
      ok((el("slide-strip").querySelector(".slide-card").getAttribute("aria-label")||"").indexOf("Grace That Feeds")>=0, "SP: a slide's aria-label carries its label text");
      ok(el("slide-strip").querySelectorAll(".slide-card")[0].classList.contains("staged"), "SP: the staged slide (0) is ringed PREVIEW");
      var __t0 = el("slide-strip").querySelectorAll(".slide-card")[0].querySelector(".slide-card-tag");
      ok(__t0 && __t0.textContent === "PREVIEW", "SP: PREVIEW is a text tag (never colour-only)");
      await waitFor(function(){ return window.__calls.some(function(c){return c.cmd==="render_plan_deck_slide" && c.args.deckId===7;}); });
      ok(window.__calls.some(function(c){return c.cmd==="render_plan_deck_slide" && c.args.deckId===7;}), "SP: thumbnails render lazily via render_plan_deck_slide");

      // Clicking a slide stages it to Preview (select_slide) — NEVER Live (FR-012).
      var __cb = window.__calls.length;
      el("slide-strip").querySelectorAll(".slide-card")[2].click();
      await waitFor(function(){ return window.__calls.some(function(c){return c.cmd==="select_slide" && c.args.slideIndex===2;}); });
      ok(window.__calls.some(function(c){return c.cmd==="select_slide" && c.args.itemId===2 && c.args.slideIndex===2;}), "SP: clicking slide 3 invokes select_slide{itemId:2, slideIndex:2}");
      ok(!window.__calls.slice(__cb).some(function(c){return c.cmd==="go_live";}), "SP: a slide click stages Preview only — never go_live (FR-012)");
      // B1 fix: the PREVIEW ring actually MOVES to the picked slide (it was stuck on slide 1 while the
      // host clamped every deck stage to 0). Proven end-to-end via staged_slide_index.
      await waitFor(function(){ return el("slide-strip").querySelectorAll(".slide-card")[2].classList.contains("staged"); });
      ok(el("slide-strip").querySelectorAll(".slide-card")[2].classList.contains("staged"), "SP: staging slide 3 moves the PREVIEW ring to slide 3 (B1 fixed — no longer stuck on slide 1)");
      ok(!el("slide-strip").querySelectorAll(".slide-card")[0].classList.contains("staged"), "SP: slide 1 is no longer the staged slide");

      // Enter routes the ACTUAL deck slide to Live via the authored-slide present path (NOT the
      // plan-item go_live, which would show only the item title). The presented slide is then marked
      // LIVE by live_authored_id.
      var __lb = window.__calls.length;
      el("slide-strip").dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", bubbles:true}));
      await waitFor(function(){ return window.__calls.slice(__lb).some(function(c){return c.cmd==="present_plan_deck_slide";}); });
      ok(window.__calls.slice(__lb).some(function(c){return c.cmd==="present_plan_deck_slide" && c.args.deckId===7;}), "SP: Enter routes the REAL deck slide to Live (present_plan_deck_slide, not the plan title)");
      ok(!window.__calls.slice(__lb).some(function(c){return c.cmd==="go_live";}), "SP: go-live for a deck does NOT use the plan-item go_live (which shows the title)");
      await waitFor(function(){ return el("slide-strip").querySelector(".slide-card.live") != null; });
      ok(el("slide-strip").querySelector(".slide-card.live") != null, "SP: the presented slide is marked LIVE (via live_authored_id)");
      // The global GO LIVE button also routes the staged deck slide (not the plan title).
      var __gb = window.__calls.length;
      el("golive").click();
      await waitFor(function(){ return window.__calls.slice(__gb).some(function(c){return c.cmd==="present_plan_deck_slide";}); });
      ok(window.__calls.slice(__gb).some(function(c){return c.cmd==="present_plan_deck_slide";}), "SP: the GO LIVE button routes the staged deck slide (present_plan_deck_slide)");
      ok(window.__consoleDeckPreview && window.__consoleDeckPreview.deckId===7, "SP: the staged deck slide is published for GO LIVE + the Preview panel render");

      // Arrow keys move + stage the neighbouring slide (Preview only).
      var __ab = window.__calls.length;
      el("slide-strip").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowLeft", bubbles:true}));
      await waitFor(function(){ return window.__calls.slice(__ab).some(function(c){return c.cmd==="select_slide";}); });
      ok(window.__calls.slice(__ab).some(function(c){return c.cmd==="select_slide";}), "SP: ArrowLeft moves + stages the previous slide (Preview)");

      // A removed linked deck → the honest 'presentation missing' state (no crash, FR-007).
      V.items[1].link.id = 999;
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      await waitFor(function(){ return !el("slides-empty").hidden; });
      ok(!el("slides-empty").hidden && el("slides-empty-msg").textContent.toLowerCase().indexOf("missing")>=0, "SP: a removed linked deck shows the honest 'presentation missing' state");

      // Bounded memory (spec §2 / no-leak): a large deck must not retain O(N) thumbnails. Stage an
      // 80-slide presentation, walk every card, and assert the thumbnail LRU stays capped.
      V.items = [V.items[0], {id:3, kind:"slide_group", title:"Big Deck", is_live:false, is_staged:true, slide_count:80, slide_index:0, staged_slide_index:0, link:{kind:"deck", id:8, slide_count:80}}];
      V.staged_index = 1; V.staged_scripture = null;
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      await waitFor(function(){ return el("slide-strip").querySelectorAll(".slide-card").length === 80; });
      ok(el("slide-strip").querySelectorAll(".slide-card").length === 80, "SP: a large (80-slide) deck lists every card");
      await window.__slidesDebug.renderAll(); // simulate a full scroll-through: render each card once
      ok(window.__slidesDebug.thumbCacheSize() <= 60, "SP: the thumbnail cache stays bounded (LRU cap) after rendering 80 slides — no O(N) growth (spec §2, no-leak)");

      // De-stage the presentation (a scripture staged) → Slides disabled + back to Scriptures. Restore V.
      V.items = [{id:1, kind:"scripture", title:"Genesis 1:13", is_live:true, is_staged:true}];
      V.staged_index = 0; V.staged_scripture = "Genesis 1:13";
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      ok(el("ctab-slides").getAttribute("aria-disabled")==="true", "SP: Slides tab disabled again when a scripture is staged");
      ok(el("ctab-scriptures").getAttribute("aria-selected")==="true", "SP: returns to Scriptures when the presentation is de-staged");

      // === audit L3: the Theme Designer loads LAZILY on first activation, not at boot ===
      ok(!window.__calls.some(function(c){return c.cmd==="builtin_themes";}),
         "L3 designer NOT loaded at boot (no builtin_themes before it is opened)");
      document.querySelector('.nav-item[data-surface="theme-designer"]').click(); // triggers the lazy load
      await sleep(80); // let the async builtin_themes / system_fonts resolve + build the designer
      ok(window.__calls.some(function(c){return c.cmd==="builtin_themes";}),
         "L3 designer loads on FIRST activation (builtin_themes fired after opening it)");

      // 86ajq3225 / Design 2.0: the background editor — a SEGMENTED type control switches
      // solid / gradient / image (Figma 317:142).
      var bgSeg = function(v){ return el("td-bg-type").querySelector('[data-bg="'+v+'"]'); };
      ok(bgSeg("solid").classList.contains("on") && !el("td-bg-solid").hidden,
         "bg: defaults to Solid with the colour picker shown");
      bgSeg("gradient").click();
      ok(!el("td-bg-gradient").hidden && el("td-bg-solid").hidden, "bg: Gradient shows the gradient controls");
      ok(bgSeg("gradient").classList.contains("on"), "bg: the Gradient segment is marked active");
      var bgG = applied().background;
      ok(!!bgG.from && !!bgG.to && bgG.direction==="vertical", "bg: the background serialises as a gradient {from,to,direction}");
      el("td-bg-dir").value = "horizontal"; el("td-bg-dir").dispatchEvent(new Event("change"));
      el("td-bg-to").value = "#ff0000"; el("td-bg-to").dispatchEvent(new Event("input"));
      var bgG2 = applied().background;
      ok(bgG2.direction==="horizontal" && bgG2.to.r===255 && bgG2.to.g===0, "bg: direction + to-colour update the gradient");
      bgSeg("image").click();
      ok(!el("td-bg-image").hidden, "bg: Image shows the image control");
      el("td-bg-img-pick").click();
      await sleep(30);
      ok(applied().background.source==="/tmp/picked.png", "bg: the image picker sets the background source");
      bgSeg("solid").click();
      el("td-bg").value = "#0a141e"; el("td-bg").dispatchEvent(new Event("input"));
      var bgS = applied().background;
      ok(typeof bgS.r==="number" && typeof bgS.from==="undefined" && typeof bgS.source==="undefined",
         "bg: Solid is a bare {r,g,b,a} colour (byte-compatible)");
      // Review MEDIUM fix: switching to Image must NOT write a malformed {source:""} — the
      // stored background stays a VALID shape (the previous solid) until a real source commits.
      bgSeg("image").click();
      var bgNoSrc = applied().background;
      ok(typeof bgNoSrc.source==="undefined" && typeof bgNoSrc.r==="number",
         "bg: switching to Image with no source keeps the valid solid bg (no malformed {source:''})");
      // The manual path field commits an image source (the no-native-dialog fallback, LOW fix).
      el("td-bg-img-path").value = "/host/bg.png"; el("td-bg-img-path").dispatchEvent(new Event("change"));
      ok(applied().background.source==="/host/bg.png", "bg: the manual path field commits an image source");

      // Design 2.0 TYPOGRAPHY (Figma 317:142): SIZE is a % field, LINE a multiplier field
      // (number fields, not sliders), and the Fit control is present + wired.
      el("td-size").value = "8.5"; el("td-size").dispatchEvent(new Event("input"));
      ok(applied().body.size_permille === 85, "typography: SIZE % field → size_permille (8.5% → 85)");
      el("td-lh").value = "1.30"; el("td-lh").dispatchEvent(new Event("input"));
      ok(applied().body.line_height_permille === 1300, "typography: LINE × field → line_height_permille (1.30 → 1300)");
      document.querySelector('#td-fit button[data-f="clip"]').click();
      ok(applied().body.fit === "clip", "typography: the Fit control sets the region fit");
      ok(document.querySelector('#td-fit button[data-f="clip"]').getAttribute("aria-pressed")==="true",
         "typography: the active Fit segment is marked");
      // Review fix: a BLANK number field must NOT commit (Number("")===0 would snap to the min);
      // an out-of-range value clamps the MODEL and `change` repopulates the FIELD to the clamp.
      el("td-size").value = "9.0"; el("td-size").dispatchEvent(new Event("input"));
      var szBefore = applied().body.size_permille;
      el("td-size").value = ""; el("td-size").dispatchEvent(new Event("input"));
      ok(applied().body.size_permille === szBefore, "typography: clearing SIZE does not snap the model to the min");
      el("td-size").value = "50"; el("td-size").dispatchEvent(new Event("input"));
      ok(applied().body.size_permille === 140, "typography: out-of-range SIZE clamps the model (50% → 140)");
      el("td-size").dispatchEvent(new Event("change"));
      ok(el("td-size").value === "14.0", "typography: SIZE field repopulates to the clamped value on change");

      // TD-010 (Design 2.0 parity, 17tnw2axptr): the text-colour swatch only showed the FIELD
      // label ("Text colour") with no reflection of the CURRENT value — an operator had to open
      // the OS colour picker to find out what colour was already set. Fixed by reflecting the
      // live hex value in #td-color-hex, mirroring the #td-bg-hex pattern already shipped for
      // the BACKGROUND section (tdBgReflect).
      var tdColorHex = el("td-color-hex");
      var tdColorCell = el("td-color").closest(".td-colorcell");
      ok(!!tdColorHex && !!tdColorCell && tdColorCell.contains(tdColorHex),
         "TD-010 (premise): #td-color-hex exists inside the same .td-colorcell as the swatch");
      if (tdColorHex) {
        el("td-color").value = "#3355ff"; el("td-color").dispatchEvent(new Event("input"));
        ok(applied().body.color.r===0x33 && applied().body.color.g===0x55 && applied().body.color.b===0xff,
           "TD-010 (premise): the colour input actually committed to the model, so the readout below isn't decorative");
        ok(tdColorHex.textContent === "#3355FF",
           "TD-010: the hex readout updates LIVE on input, not just on the next full sync (" + tdColorHex.textContent + ")");
        // Selecting a DIFFERENT region must re-sync the readout to THAT region's own stored colour —
        // the gap a naive "set once on the input event" fix would leave (a stale label from whichever
        // region was last dragged, not the one now selected).
        el("td-layers").querySelector('.td-layer[data-region="title"]').click();
        var tdTitleHex = "#" + [applied().title.color.r, applied().title.color.g, applied().title.color.b]
          .map(function(v){ return v.toString(16).padStart(2, "0"); }).join("").toUpperCase();
        ok(tdColorHex.textContent === tdTitleHex,
           "TD-010: switching the selected region re-syncs the hex readout to THAT region's colour (" +
           tdColorHex.textContent + " vs expected " + tdTitleHex + ")");
        ok(tdColorHex.textContent !== "#3355FF",
           "TD-010 (control): the readout actually changed away from the previous region's value — proves this isn't a frozen/stale label");
        el("td-layers").querySelector('.td-layer[data-region="body"]').click(); // restore for tests below
      }

      // C-001: Add Shape → an element on tdTheme.elements, inspector shows, selection is element.
      addShape();
      ok(!el("td-el-inspector").hidden, "Add Shape shows the element inspector");
      ok(el("td-sel").classList.contains("is-element"), "selection box marks an element");
      var t1 = applied();
      ok(t1 && t1.elements && t1.elements.length===1 && t1.elements[0].kind==="shape", "shape element serialized (kind=shape)");
      ok(t1.elements[0].z===0 && t1.elements[0].opacity===255, "default z=0, opacity=255");
      ok(el("td-shape-row").hidden, "C-004 shape picker closes after choosing a kind");
      ok(t1.elements[0].variant===undefined, "C-004 a Rectangle pick omits `variant` (byte-identical JSON)");

      // C-003 arrange: add a 2nd shape (z=1), Send to back → z becomes min-1 = -1 (behind text).
      addShape();
      var t2 = applied();
      ok(t2.elements.length===2 && t2.elements[1].z===1, "second shape z=max+1=1");
      // The inspector "Arrange (z-order)" buttons were removed — z-order now lives on the LAYERS
      // panel (drag) + the Cmd/Ctrl+Shift+[ / ] chords. Cmd+Shift+[ = Send to back.
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"[",metaKey:true,shiftKey:true,bubbles:true}));
      var t3 = applied();
      ok(t3.elements[1].z===-1, "Send to back (Cmd+Shift+[) sets z=min-1=-1 (rewrites z, not the list)");
      ok(el("td-el-zchip").textContent.indexOf("Behind")>=0, "chip shows 'Behind text'");
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"]",metaKey:true,shiftKey:true,bubbles:true}));
      ok(applied().elements[1].z===1, "Bring to front (Cmd+Shift+]) sets z=max+1=1");

      // C-003 opacity: 50% → u8 128.
      el("td-el-op").value = 50; el("td-el-op").dispatchEvent(new Event("input"));
      ok(applied().elements[1].opacity===128, "opacity 50% maps to u8 128");

      // (The numeric X/Y/W/H fields were removed — position is edited on the canvas: keyboard.)
      // C-002 keyboard move: ArrowRight nudges +10‰.
      var before = applied().elements[1].x_permille;
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight",bubbles:true}));
      ok(applied().elements[1].x_permille===before+10, "ArrowRight nudges +10 permille");

      // C-002 delete: two-click confirm removes the element.
      el("td-el-del").click(); el("td-el-del").click();
      ok(applied().elements.length===1, "two-click delete removes the element");

      // #1 native picker: Add Image → pick_image (stubbed) → an image element, NO path row.
      document.querySelector('.td-addbar button[data-add="image"]').click();
      await sleep(30);
      var ti = applied();
      ok(el("td-img-row").hidden, "#1 Add Image uses the native picker (no manual path row)");
      ok(ti.elements.some(function(e){return e.kind==="image" && e.source==="/tmp/picked.png";}), "#1 native picker adds an image with the chosen path");

      // FR-138 / 86ak0qmzv: a host-side validation refusal is surfaced to the operator, not
      // silently swallowed as "picker unavailable" or silently treated as a cancel. Count
      // elements before/after so a false-accept (the rejected file added anyway) is caught too.
      var elsBeforeRejection = applied().elements.length;
      window.__pickImageNextOutcome = {outcome: "rejected", reason: "that file is too large to import"};
      document.querySelector('.td-addbar button[data-add="image"]').click();
      await sleep(30);
      ok(el("td-status").textContent === "that file is too large to import",
        "a pick_image refusal shows the host's own reason, verbatim, to the operator");
      ok(applied().elements.length === elsBeforeRejection,
        "a rejected pick adds NO element — the refusal must not be treated as a successful pick");
      delete window.__pickImageNextOutcome;

      // A cancelled dialog adds no element and must not be confused with the rejection path
      // above — must not regress into treating a cancel as a refusal (or vice versa) now that
      // the outcome is tagged instead of a bare nullable path.
      window.__pickImageNextOutcome = {outcome: "cancelled"};
      document.querySelector('.td-addbar button[data-add="image"]').click();
      await sleep(30);
      ok(applied().elements.length === elsBeforeRejection, "a cancelled pick adds no element");
      delete window.__pickImageNextOutcome;

      // 86ajq6j64: the TEXT add button is ENABLED and adds a text element; the inspector edits it.
      var textBtn = document.querySelector('.td-addbar button[data-add="text"]');
      ok(textBtn && !textBtn.disabled, "the Text add button is enabled (86ajq6j64)");
      textBtn.click();
      await sleep(30);
      var last = function(){ var e = applied().elements; return e[e.length-1]; };
      var txt = last();
      ok(txt && txt.kind==="text" && txt.text==="Text", "Add Text adds a text element with default content");
      ok(!el("td-el-text").hidden, "the text inspector shows for a text element");
      ok(el("td-el-shape").hidden && el("td-el-image").hidden, "shape/image inspectors hidden for a text element");
      ok(el("td-el-head").textContent.indexOf("Text")>=0, "the inspector head names it 'Text'");
      // Edit the content via the inspector.
      el("td-el-text-content").value = "Hello world";
      el("td-el-text-content").dispatchEvent(new Event("input"));
      ok(last().text==="Hello world", "the inspector edits the text content");
      // Size + alignment controls update the element.
      el("td-el-text-size").value = 12; el("td-el-text-size").dispatchEvent(new Event("input"));
      ok(last().size_permille===120, "size 12% → size_permille=120");
      el("td-el-text-align").value = "left"; el("td-el-text-align").dispatchEvent(new Event("change"));
      ok(last().align_h==="left", "the alignment select sets align_h");
      // Review fix: the content is CLIENT-bounded to the host cap (2000), so the UI can never
      // author a theme the host would reject (no false-success on Apply).
      el("td-el-text-content").value = "x".repeat(3000);
      el("td-el-text-content").dispatchEvent(new Event("input"));
      ok(last().text.length===2000, "an over-cap paste is truncated to 2000 chars on the client");
      // Clean up the text element so later element-count assertions are unaffected.
      el("td-el-del").click(); el("td-el-del").click();

      // The Delete KEY removes the selected element in ONE press (global capture handler), distinct
      // from the button's two-click arm. Add a throwaway shape and delete it with a single Delete.
      addShape();
      var nKbdDel = applied().elements.length;
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"Delete", bubbles:true}));
      ok(applied().elements.length===nKbdDel-1, "TD: a single Delete keypress removes the selected element");

      // FIX: click empty canvas deselects back to region editing.
      var bx = el("td-canvas-box").getBoundingClientRect();
      el("td-canvas-box").dispatchEvent(new PointerEvent("pointerdown",{clientX:bx.left+1,clientY:bx.top+1,bubbles:true}));
      ok(el("td-el-inspector").hidden, "click on empty canvas deselects back to regions");

      // FIX: Escape deselects (keyboard path).
      addShape();
      ok(!el("td-el-inspector").hidden, "element re-selected");
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}));
      ok(el("td-el-inspector").hidden, "Escape deselects the element");

      // FIX: delete-arm resets on selection change (no cross-element leak).
      addShape(); // A (selected)
      el("td-el-del").click(); // arm delete on A
      addShape(); // B auto-selected → tdSyncEl resets the arm + label
      ok(el("td-el-del").textContent==="Delete element", "delete arm/label reset on selection change");
      var nA = applied().elements.length;
      el("td-el-del").click(); // should ARM B (not delete), since the arm was reset
      ok(applied().elements.length===nA, "one click after a selection change does NOT delete (arm reset)");

      // Region regression: selecting a region (via the LAYERS row — the Region picker was
      // removed) hides the element inspector and shows the region-layout controls.
      el("td-layers").querySelector('.td-layer[data-region="title"]').click();
      ok(el("td-el-inspector").hidden, "selecting a region hides the element inspector");
      ok(el("td-region-align").style.display!=="none", "region layout controls visible in region mode");

      // Make the designer laid out so getComputedStyle reflects the real CSS (the menu's
      // hide contract is CSS: .td-ctx[hidden]{display:none} vs .td-ctx{display:flex}).
      var tdSurf2=el("surface-theme-designer"); tdSurf2.style.display="block"; tdSurf2.classList.add("active");
      var cdisp=(id)=>getComputedStyle(el(id)).display;

      // #4 context menu: right-click opens it; Copy→Paste clones; Cmd+C/V; Delete.
      addShape();
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      ok(!el("td-ctx").hidden, "#4 right-click opens the context menu");
      ok(cdisp("td-ctx")!=="none", "#4 open menu is actually VISIBLE (computed display, not just attr)");
      el("td-ctx").querySelector('[data-ctx="copy"]').click();
      ok(el("td-ctx").hidden && cdisp("td-ctx")==="none", "#4 menu truly HIDDEN after close (the [hidden] guard works)");
      var nb = applied().elements.length;
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      el("td-ctx").querySelector('[data-ctx="paste"]').click();
      ok(applied().elements.length===nb+1, "#4 Copy then Paste clones the element (+1)");
      var n2 = applied().elements.length;
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"c",metaKey:true,bubbles:true}));
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"v",metaKey:true,bubbles:true}));
      ok(applied().elements.length===n2+1, "#4 Cmd+C then Cmd+V pastes a clone");
      var n3 = applied().elements.length;
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      el("td-ctx").querySelector('[data-ctx="delete"]').click();
      ok(applied().elements.length===n3-1, "#4 context-menu Delete removes the element");

      // LOW: a left-click while the menu is open just dismisses it (no select/deselect side-effect).
      addShape();
      var nSel = applied().elements.length;
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      ok(cdisp("td-ctx")!=="none", "#4 menu open before dismiss");
      el("td-canvas-box").dispatchEvent(new PointerEvent("pointerdown",{clientX:40,clientY:40,button:0,bubbles:true}));
      ok(cdisp("td-ctx")==="none", "#4 left-click dismisses the menu");
      ok(applied().elements.length===nSel, "#4 the dismiss click did not add/remove an element");

      // #3 click-select an element BENEATH the region box (position:fixed → real viewport coords).
      var surf=el("surface-theme-designer"); surf.style.display="block"; surf.classList.add("active");
      var box=el("td-canvas-box"); box.style.cssText="position:fixed;left:0;top:0;width:400px;height:226px;z-index:9;display:block";
      addShape(); // default centre ≈ (500,500) permille
      el("td-layers").querySelector('.td-layer[data-region="body"]').click(); // select the large Body region (LAYERS row)
      ok(el("td-el-inspector").hidden, "#3 region selected — element inspector hidden");
      var br=box.getBoundingClientRect();
      // The forced position:fixed;width:400px MUST yield real viewport geometry (Chrome does
      // layout); assert it as a precondition so the hit-test below can never be silently
      // skipped by a vacuous fallback (adversarial review, audit #9).
      ok(br.width>10, "#3 canvas box has real layout geometry (width=" + Math.round(br.width) + ")");
      // The Body region box overlays the shape centre; a click there must re-hit-test to the shape.
      var cx=br.left+br.width*0.5, cy=br.top+br.height*0.5;
      el("td-sel").dispatchEvent(new PointerEvent("pointerdown",{clientX:cx,clientY:cy,button:0,bubbles:true,pointerId:1}));
      ok(!el("td-el-inspector").hidden, "#3 clicking an element UNDER the region box selects it");

      // User ask: clicking the Body or Reference/Title text ON THE CANVAS auto-selects that
      // region. Load a fresh built-in (T has no elements) so the click can't hit a leftover
      // element; the box keeps its real position:fixed geometry from #3.
      el("td-themes").querySelector('.td-theme-row:not(.td-theme-saved) .td-theme-name').click();
      await sleep(20);
      var toClient = function(xp, yp){ var b = box.getBoundingClientRect(); return { x: b.left + (xp/1000)*b.width, y: b.top + (yp/1000)*b.height }; };
      var pt = toClient(500, 200); // inside the title rect (y 150..260)
      box.dispatchEvent(new PointerEvent("pointerdown",{clientX:pt.x,clientY:pt.y,button:0,bubbles:true,pointerId:2}));
      ok(el("td-el-inspector").hidden, "canvas region-click stays in region mode (no element)");
      // The Region picker was removed — the active region is named in the inspector header.
      ok(el("td-insp-title").textContent.indexOf("Reference")>=0,
         "canvas: clicking the Reference/Title text selects that region (header names it)");
      var pb = toClient(500, 500); // inside the body rect (y 280..840)
      box.dispatchEvent(new PointerEvent("pointerdown",{clientX:pb.x,clientY:pb.y,button:0,bubbles:true,pointerId:3}));
      ok(el("td-insp-title").textContent==="Body",
         "canvas: clicking the Body text selects the Body region (header names it)");

      // === Undo/redo (⌘Z / ⌘⇧Z): the Theme Designer's client-side snapshot history (tdHistory).
      // The document is the serialisable tdTheme object; ⌘Z/⌘⇧Z walk a bounded snapshot stack.
      // Typography reverts are read from the td-size field (tdSync updates it SYNCHRONOUSLY on
      // undo, before the debounced canvas re-render); structural reverts are read from applied()
      // (the last preview_theme JSON) after letting the 120ms debounce publish.
      el("surface-theme-designer").classList.add("active"); // ⌘Z acts only while the designer is up
      var undoZ = function(shift){ document.dispatchEvent(new KeyboardEvent("keydown",{key:"z",metaKey:true,shiftKey:!!shift,bubbles:true})); };
      var loadFreshTheme = function(){ el("td-themes").querySelector('.td-theme-row:not(.td-theme-saved) .td-theme-name').click(); };
      // (1) A typography edit undoes and redoes.
      loadFreshTheme(); await sleep(20);
      var szBase = el("td-size").value;
      var szEdit = (szBase === "7.5") ? "8.5" : "7.5";
      el("td-size").value = szEdit; el("td-size").dispatchEvent(new Event("input"));
      ok(el("td-size").value === szEdit && szEdit !== szBase, "undo(1): SIZE edited away from the loaded baseline");
      undoZ(false);
      ok(el("td-size").value === szBase, "undo(1): ⌘Z reverts the SIZE edit to the loaded value");
      undoZ(true);
      ok(el("td-size").value === szEdit, "undo(1): ⌘⇧Z re-applies the reverted SIZE edit");
      // (2) A new edit after an undo clears the redo branch (⌘⇧Z then does nothing).
      undoZ(false);
      ok(el("td-size").value === szBase, "undo(2): ⌘Z back to baseline (a redo is now available)");
      var szNew = (szBase === "9.5") ? "5.5" : "9.5";
      el("td-size").value = szNew; el("td-size").dispatchEvent(new Event("input")); // a NEW edit
      undoZ(true); // the pending redo was invalidated by the new edit
      ok(el("td-size").value === szNew, "undo(2): a new edit clears the redo branch (⌘⇧Z is a no-op)");
      // (3) Adding an element is undoable via ⌘Z (element count, debounce-published).
      loadFreshTheme(); await sleep(160);
      var nStart = (applied().elements || []).length;
      addShape(); await sleep(160);
      ok((applied().elements || []).length === nStart + 1, "undo(3): a shape was added (+1 element)");
      undoZ(false); await sleep(160);
      ok((applied().elements || []).length === nStart, "undo(3): ⌘Z removes the added shape (count back to start)");
      undoZ(true); await sleep(160);
      ok((applied().elements || []).length === nStart + 1, "undo(3): ⌘⇧Z re-adds the shape (+1 again)");
      // (4) A pointer gesture spanning multiple inputs collapses to ONE undo step (coalescing).
      loadFreshTheme(); await sleep(20);
      var szPreVal = el("td-size").value;
      var surfTD = el("surface-theme-designer");
      surfTD.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true})); // open a coalescing gesture
      el("td-size").value = "6.0"; el("td-size").dispatchEvent(new Event("input"));
      el("td-size").value = "6.5"; el("td-size").dispatchEvent(new Event("input"));
      window.dispatchEvent(new PointerEvent("pointerup",{bubbles:true})); // seal → the whole drag is one step
      ok(el("td-size").value === "6.5", "undo(4): a two-input pointer gesture set SIZE to 6.5");
      undoZ(false);
      ok(el("td-size").value === szPreVal, "undo(4): ONE ⌘Z reverts the WHOLE gesture (coalesced, not just the last input)");
      // (5) Undoing past the start is a safe no-op — the editor stays usable afterward.
      undoZ(false); undoZ(false); undoZ(false); undoZ(false);
      el("td-size").value = "8.0"; el("td-size").dispatchEvent(new Event("input"));
      ok(el("td-size").value === "8.0", "undo(5): undoing past the start does not corrupt — editing still works");

      // Design 2.0: LAYERS drag-and-drop reorders z, and dragging an element past the text
      // REGION rows crosses the text boundary (front z>0 <-> behind z<0). Fresh Classic theme
      // (no elements) → add two front shapes → drag the top one below the region rows.
      el("td-themes").querySelector('.td-theme-row:not(.td-theme-saved) .td-theme-name').click();
      await sleep(20);
      addShape(); addShape();
      var dTop = applied().elements.length - 1; // the frontmost (highest z) shape
      ok(applied().elements[dTop].z >= 0, "D2 dnd: a freshly-added shape starts in front of the text (z>=0)");
      var lbox = el("td-layers");
      var dragRow2 = Array.prototype.filter.call(lbox.querySelectorAll(".td-layer"), function(r){ return r.dataset.idx===String(dTop); })[0];
      var regionRows2 = Array.prototype.filter.call(lbox.querySelectorAll(".td-layer"), function(r){ return r.dataset.region; });
      var lastRegion = regionRows2[regionRows2.length-1];
      var dr = dragRow2.getBoundingClientRect(), lr = lastRegion.getBoundingClientRect();
      // Precondition: the layers list has real vertical layout (rows at distinct Y) — else the
      // drag hit-test is meaningless and the assertion below could pass vacuously.
      ok(lr.top > dr.top + 4, "D2 dnd: the LAYERS list has real row geometry (regions below the shape)");
      var hdl = dragRow2.querySelector(".td-layer-handle");
      hdl.dispatchEvent(new PointerEvent("pointerdown",{clientX:dr.left+6,clientY:dr.top+6,button:0,bubbles:true,pointerId:9}));
      window.dispatchEvent(new PointerEvent("pointermove",{clientX:lr.left+6,clientY:lr.bottom+8,bubbles:true,pointerId:9}));
      window.dispatchEvent(new PointerEvent("pointerup",{clientX:lr.left+6,clientY:lr.bottom+8,bubbles:true,pointerId:9}));
      await sleep(10);
      ok(applied().elements[dTop].z < 0, "D2 dnd: dragging a layer below the region rows moves it BEHIND the text (z<0)");

      // C-004 shape PICKER: each geometry adds an element with the right variant + the
      // corner-radius control appears only for a rounded rectangle.
      document.querySelector('.td-addbar button[data-add="shape"]').click();
      ok(!el("td-shape-row").hidden, "C-004 Add Shape opens the shape picker");
      document.querySelector('#td-shape-row [data-shape="ellipse"]').click();
      ok(el("td-shape-row").hidden, "C-004 picker closes after choosing Ellipse");
      var te = applied(); var lastE = te.elements[te.elements.length-1];
      ok(lastE.kind==="shape" && lastE.variant==="ellipse", "C-004 Ellipse pick → variant=ellipse");
      ok(el("td-el-corner-row").hidden, "C-004 corner control hidden for a non-rounded shape");
      ok(el("td-el-head").textContent.indexOf("Ellipse")>=0, "C-004 inspector head names the geometry");
      // Rounded: variant + a default corner_permille + the corner control visible + editable.
      addShape("rounded_rect");
      var tr = applied(); var lastR = tr.elements[tr.elements.length-1];
      ok(lastR.variant==="rounded_rect" && lastR.corner_permille>0, "C-004 Rounded pick → variant + default corner_permille");
      ok(!el("td-el-corner-row").hidden, "C-004 corner-radius control shown for a rounded rect");
      el("td-el-corner").value = 20; el("td-el-corner").dispatchEvent(new Event("input"));
      var idxR = tr.elements.length-1;
      ok(applied().elements[idxR].corner_permille===200, "C-004 corner slider 20% → corner_permille=200");
      // Triangle pick.
      addShape("triangle");
      var tt = applied();
      ok(tt.elements[tt.elements.length-1].variant==="triangle", "C-004 Triangle pick → variant=triangle");
      // Picker Cancel adds nothing.
      var nBefore = applied().elements.length;
      document.querySelector('.td-addbar button[data-add="shape"]').click();
      el("td-shape-cancel").click();
      ok(el("td-shape-row").hidden && applied().elements.length===nBefore, "C-004 picker Cancel adds nothing");

      // #5 font weight + letter-spacing (86ajq3225): the enabled fields set the theme + persist.
      el("td-weight").value = "700"; el("td-weight").dispatchEvent(new Event("change"));
      el("td-letter").value = "0.1"; el("td-letter").dispatchEvent(new Event("change"));
      var tw = applied();
      ok(tw.weight === 700, "#5 weight select sets theme.weight=700");
      ok(tw.letter_spacing_permille === 100, "#5 letter-spacing 0.1em → permille=100");
      ok(!el("td-weight").disabled && !el("td-letter").disabled, "#5 weight + letter fields are ENABLED");
      // Regular + zero drop the fields (byte-stable default).
      el("td-weight").value = "400"; el("td-weight").dispatchEvent(new Event("change"));
      el("td-letter").value = "0"; el("td-letter").dispatchEvent(new Event("change"));
      var td = applied();
      ok(td.weight === undefined, "#5 Regular drops weight (byte-stable)");
      ok(td.letter_spacing_permille === undefined, "#5 zero letter-spacing dropped");

      // === Design 2.0: LAYERS panel + per-layer visibility + zoom + Duplicate ===
      var layersBox = el("td-layers");
      ok(!!layersBox, "D2 LAYERS panel present");
      var qLayers = function(){ return el("td-layers").querySelectorAll(".td-layer"); };
      var elRowFor = function(i){ return Array.prototype.filter.call(qLayers(), function(r){ return parseInt(r.dataset.idx,10)===i; })[0]; };
      var regionRowFor = function(k){ return Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.region===k; })[0]; };
      addShape(); // a fresh element to operate on
      var elCount = applied().elements.length;
      ok(qLayers().length === elCount + 2, "D2 LAYERS lists every element + the 2 regions (got " + qLayers().length + ")");
      var regionRows = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.region; });
      ok(regionRows.length === 2, "D2 LAYERS includes both region rows (Title + Body)");
      ok(regionRows[0].querySelector(".td-layer-handle").getAttribute("aria-disabled")==="true",
         "D2 a region row is not reorderable (handle aria-disabled)");
      // The eye HIDES an element layer → a REAL, byte-stable `visible:false` in the Apply payload.
      var firstEl = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.idx!==undefined; })[0];
      var idx = parseInt(firstEl.dataset.idx, 10);
      firstEl.querySelector(".td-layer-eye").click();
      ok(applied().elements[idx].visible === false, "D2 the eye HIDES a layer (visible:false in the Apply payload)");
      elRowFor(idx).querySelector(".td-layer-eye").click(); // show again
      ok(applied().elements[idx].visible === undefined, "D2 showing a layer OMITS `visible` (byte-stable JSON)");
      // Selecting a layer row selects that element; a region row selects the region.
      elRowFor(idx).click();
      ok(!el("td-el-inspector").hidden, "D2 clicking a layer row selects its element");
      regionRowFor("title").click();
      ok(el("td-el-inspector").hidden, "D2 clicking a region row selects the region");
      // The eye also hides a REGION (real region.visible flag).
      regionRowFor("title").querySelector(".td-layer-eye").click();
      ok(applied().title.visible === false, "D2 the eye hides a REGION (title.visible=false)");
      regionRowFor("title").querySelector(".td-layer-eye").click();
      ok(applied().title.visible === true, "D2 toggling a region eye shows it again");
      // Zoom: −/+ scale the preview box via a CSS var; the % readout tracks it (frontend-only).
      var z0 = parseFloat(el("td-canvas-box").style.getPropertyValue("--td-zoom") || "1");
      el("td-zoom-in").click();
      ok(parseFloat(el("td-canvas-box").style.getPropertyValue("--td-zoom")) > z0, "D2 zoom-in increases the preview scale");
      ok(el("td-zoom-v").textContent.indexOf("%")>=0, "D2 the zoom readout shows a percentage");
      el("td-zoom-out").click();
      // Duplicate: clones the current design into a new unsaved working theme (elements carry over).
      var beforeDup = applied().elements.length;
      el("td-duplicate").click();
      // Check the status SYNCHRONOUSLY (before any await): a pending Apply .then from the
      // applied() above would otherwise overwrite #td-status with "Applied…" during a sleep.
      ok(el("td-status").textContent.indexOf("Duplicated")>=0, "D2 Duplicate reports it into the status line");
      await sleep(20);
      ok(applied().elements.length === beforeDup, "D2 Duplicate clones the current design (same elements, new unsaved copy)");

      // D2 a11y (review fix): keyboard focus survives the LAYERS innerHTML rebuild.
      addShape();
      var aRow = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.idx!==undefined; })[0];
      var aidx = parseInt(aRow.dataset.idx, 10);
      var eyeA = aRow.querySelector(".td-layer-eye"); eyeA.focus(); eyeA.click(); // hide → rebuild
      ok(document.activeElement && document.activeElement.classList.contains("td-layer-eye") &&
         document.activeElement.closest(".td-layer").dataset.idx === String(aidx),
         "D2 a11y: an eye toggle keeps focus on the same layer's eye after the rebuild");
      document.activeElement.click(); // show again (clean state)
      var rowB = elRowFor(aidx); rowB.focus();
      rowB.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowUp",altKey:true,bubbles:true})); // reorder → rebuild
      ok(document.activeElement && document.activeElement.classList.contains("td-layer") &&
         document.activeElement.dataset.idx === String(aidx),
         "D2 a11y: Alt+Arrow reorder keeps focus on the moved layer's row");
      // Review fix: the selected layer row exposes aria-current (not colour-only) to AT.
      ok(el("td-layers").querySelector(".td-layer.sel") &&
         el("td-layers").querySelector(".td-layer.sel").getAttribute("aria-current")==="true",
         "D2 a11y: the selected layer row exposes aria-current to assistive tech");
      // Review fix: Enter on a layer's EYE must NOT steal row selection (keyboard/pointer parity)
      // — row.onkeydown bails for keydowns originating on the child eye button.
      var elRowsK = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.idx!==undefined; });
      if (elRowsK.length >= 2) {
        var aK = parseInt(elRowsK[0].dataset.idx,10), bK = parseInt(elRowsK[1].dataset.idx,10);
        elRowFor(aK).click(); // select layer A
        elRowFor(bK).querySelector(".td-layer-eye").dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",bubbles:true}));
        ok(el("td-layers").querySelector('.td-layer[data-idx="'+aK+'"]').classList.contains("sel"),
           "D2 a11y: Enter on a layer's eye does not steal selection from another row");
      }

      // D2 reliability (review fix): a cancelled layer-drag tears down (no stuck reorder).
      var dragRow = elRowFor(aidx);
      var zBefore = applied().elements[aidx].z;
      dragRow.querySelector(".td-layer-handle").dispatchEvent(new PointerEvent("pointerdown",{clientX:0,clientY:0,button:0,bubbles:true,pointerId:7}));
      window.dispatchEvent(new PointerEvent("pointercancel",{pointerId:7,bubbles:true}));
      window.dispatchEvent(new PointerEvent("pointermove",{clientX:0,clientY:400,bubbles:true,pointerId:7})); // big move AFTER cancel
      ok(applied().elements[aidx].z === zBefore, "D2 a cancelled layer-drag stops reordering (pointercancel teardown)");

      // === Design 2.0: Templates strip is selectable (bug repro: "can't select templates") ===
      // "New from current" clears the selection so the builtin row is NOT current — a
      // selection CHANGE is then observable on a single builtin row (no saved-theme needed).
      el("td-new-2").click();
      await sleep(20);
      var biRow = el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved)");
      ok(!!biRow, "D2 a builtin template row renders");
      ok(biRow.dataset.current === "false", "D2 precondition: the builtin is not current after New");
      // Clicking the THUMBNAIL (the dominant card target) must select the template.
      biRow.querySelector(".td-theme-thumb").click();
      await sleep(20);
      ok(el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved)").dataset.current === "true",
         "D2 clicking a template THUMBNAIL selects it");
      // Deselect again; the NAME text must also select.
      el("td-new-2").click(); await sleep(20);
      el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved) .td-theme-name").click();
      await sleep(20);
      ok(el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved)").dataset.current === "true",
         "D2 clicking a template NAME selects it");

      // === Design 2.0: the LAYERS panel IS the z-order (reorder changes element z + list order) ===
      addShape(); // a fresh, frontmost element (z = maxZ+1)
      addShape(); // another frontmost element on top
      var topIdx = applied().elements.length - 1; // the topmost element
      var zTop = applied().elements[topIdx].z;
      // The topmost element's LAYERS row is ABOVE (earlier in DOM) the one it stacks over.
      var order1 = Array.prototype.map.call(qLayers(), function(r){ return r.dataset.idx; }).filter(function(x){ return x!==undefined; });
      ok(order1.indexOf(String(topIdx)) < order1.indexOf(String(topIdx-1)),
         "D2 LAYERS lists a higher-z element ABOVE a lower-z one (list = z-order)");
      // Reorder the topmost DOWN via the panel (Alt+ArrowDown) → its z drops below its neighbour.
      elRowFor(topIdx).focus();
      elRowFor(topIdx).dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowDown",altKey:true,bubbles:true}));
      await sleep(10);
      ok(applied().elements[topIdx].z < zTop, "D2 a LAYERS reorder changes the element's z-order (backward lowers z)");
      var order2 = Array.prototype.map.call(qLayers(), function(r){ return r.dataset.idx; }).filter(function(x){ return x!==undefined; });
      ok(order2.indexOf(String(topIdx)) > order2.indexOf(String(topIdx-1)),
         "D2 the LAYERS list re-sorts to the new z-order after a reorder");

      // === Design 2.0: collapsible Templates row (gives the canvas more room) ===
      var tmpl = document.querySelector(".td-templates");
      var tgl = el("td-templates-toggle");
      ok(!!(tmpl && tgl), "D2 templates collapse toggle present");
      ok(!tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="true", "D2 templates start expanded");
      tgl.click();
      ok(tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="false", "D2 toggle collapses the templates row (#td-panel hidden via CSS)");
      tgl.click();
      ok(!tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="true", "D2 toggling again expands the templates row");
      // Review fix (HIGH): "Save theme" while Templates are collapsed must EXPAND the strip so
      // the save form (inside the collapsible #td-panel) is visible — not a silent no-op.
      tgl.click(); // collapse
      ok(tmpl.classList.contains("collapsed"), "D2 precondition: templates collapsed before Save");
      el("td-save").click(); // the topbar "Save theme" CTA
      ok(!tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="true", "D2 Save-theme expands the collapsed Templates strip (no silent no-op)");
      ok(!el("td-save-row").hidden, "D2 Save-theme reveals the save-name form");
      el("td-save-cancel").click();
      // The Region picker + numeric X/Y/W/H + Lock were removed from the inspector.
      ok(!el("td-region") && !el("td-x") && !el("td-lock"), "D2 inspector trimmed: Region picker + X/Y/W/H + Lock removed");

      // === audit M1: the plan dedup key EXCLUDES view.timer (no per-second rebuild) ===
      // render() is a global function; drive it directly with crafted view deltas.
      var baseView = JSON.parse(JSON.stringify(V));
      render(baseView);                       // plan reflects baseView; lastRendered = narrowed key
      var row0 = document.querySelector("#plan .item");
      ok(!!row0, "M1 plan has a row to track");
      // (a) a view differing ONLY in timer must NOT rebuild the plan (same node identity).
      var vTimer = JSON.parse(JSON.stringify(baseView));
      vTimer.timer = { remaining_secs: 42, elapsed_secs: 8, running: true };
      render(vTimer);
      ok(document.querySelector("#plan .item") === row0,
         "M1 timer-only view delta does NOT rebuild the plan (node identity stable)");
      // (b) a genuine plan change (an added item) MUST still rebuild.
      var vItems = JSON.parse(JSON.stringify(baseView));
      vItems.items = baseView.items.concat([{id:2,kind:"song",title:"Added",is_live:false,is_staged:false}]);
      render(vItems);
      var rows2 = document.querySelectorAll("#plan .item");
      ok(rows2.length === 2 && rows2[0] !== row0,
         "M1 an items delta DOES rebuild the plan (2 fresh rows)");
      render(baseView); // restore so the trailing 1s poll stays consistent

      // === audit M4: the transcript DOM is client-capped even if the host over-sends ===
      var many = [];
      for (var mi = 0; mi < 200; mi++) many.push({ id: mi, text: "line " + mi, start_ms: mi * 1000 });
      syncTranscript({ transcript: many });
      var logEl = el("transcript-log");
      ok(logEl.children.length === 120,
         "M4 transcript DOM capped at 120 rows even when the host sends 200 (got " + logEl.children.length + ")");
      var segIds = Array.from(logEl.children).map(function (r) { return r.dataset.segId; });
      ok(segIds.indexOf("199") >= 0 && segIds.indexOf("0") < 0,
         "M4 keeps the NEWEST 120 (id 199 present, id 0 pruned)");

      // === right-column tabs: Service Timer | Detected Scriptures (Figma 430:124) ===
      var rtabTimer = el("rtab-timer"), rtabDet = el("rtab-detections");
      var rpTimer = el("rpanel-timer"), rpDet = el("rpanel-detections");
      ok(rtabTimer && rtabDet && rpTimer && rpDet, "tabs: right-column tabs + panels exist");
      ok(rtabTimer.getAttribute("aria-selected") === "true" && rpDet.hidden && !rpTimer.hidden,
         "tabs: Service Timer active on boot; the Detected panel is hidden");
      rtabDet.click();
      ok(rtabDet.getAttribute("aria-selected") === "true" && !rpDet.hidden &&
         rpTimer.hidden && rtabTimer.getAttribute("aria-selected") === "false",
         "tabs: clicking Detected Scriptures shows its panel and hides the timer");
      rtabDet.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
      ok(rtabTimer.getAttribute("aria-selected") === "true" && !rpTimer.hidden,
         "tabs: ArrowLeft moves selection back to Service Timer (real tablist)");
      // A new detection auto-surfaces the Detected tab (no focus steal) while on the timer tab.
      render(Object.assign({}, baseView, { detections: [
        { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
      ] }));
      ok(rtabDet.getAttribute("aria-selected") === "true",
         "tabs: a new detection auto-surfaces the Detected Scriptures tab");
      var rcnt = el("detections-count");
      ok(rcnt && rcnt.hidden === false && rcnt.textContent.indexOf("1") >= 0,
         "tabs: the count badge on the tab shows the unactioned detection count");

      // === Timer | Stage sub-tab: stage theme picker + production-message composer (stage-only) ===
      rtabTimer.click(); // back to the Service Timer tab
      var segTimer = el("seg-timer"), segStage = el("seg-stage");
      var stabTimer = el("stab-timer"), stabStage = el("stab-stage");
      ok(segTimer && segStage && stabTimer && stabStage, "stage: the Timer|Stage sub-tabs + panels exist");
      ok(!stabTimer.hidden && stabStage.hidden, "stage: the Timer sub-panel shows first");
      segStage.click();
      ok(!stabStage.hidden && stabTimer.hidden && segStage.getAttribute("aria-selected") === "true",
         "stage: clicking Stage reveals the theme/message panel");
      // ←/→ switch the Timer|Stage sub-tabs via the keyboard (APG tablist parity with the other tabs).
      segStage.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowLeft", bubbles:true}));
      ok(!stabTimer.hidden && stabStage.hidden && segTimer.getAttribute("aria-selected") === "true",
         "stage: ← switches the Timer|Stage sub-tabs via the keyboard");
      segTimer.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true}));
      ok(!stabStage.hidden && segStage.getAttribute("aria-selected") === "true",
         "stage: → returns to the Stage sub-tab (keyboard tablist)");
      // Theme picker -> set_stage_template.
      var scriptureCard = document.querySelector('#stage-themes .stage-theme[data-template="scripture"]');
      scriptureCard.click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_template" && c.args.template === "scripture"; }),
         "stage: a theme card invokes set_stage_template(scripture)");
      // Preset chip -> set_stage_message with its text.
      var preset = document.querySelector('#stage-presets .stage-preset');
      preset.click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_message" && c.args.text === preset.dataset.msg; }),
         "stage: a preset chip invokes set_stage_message with its text");
      // Custom field + Send -> set_stage_message(custom).
      el("stage-msg-input").value = "HOLD FOR PRAYER";
      el("stage-msg-send").click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_message" && c.args.text === "HOLD FOR PRAYER"; }),
         "stage: the custom field + Send invokes set_stage_message(custom)");
      // Clear -> set_stage_message("").
      el("stage-msg-clear").click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_message" && c.args.text === ""; }),
         "stage: Clear invokes set_stage_message with an empty string");
      // syncStage reflects the host's authoritative template + live message.
      render(Object.assign({}, baseView, { stage_template: "timer-only", stage_message: "WRAP UP NOW" }));
      var toCard = document.querySelector('#stage-themes .stage-theme[data-template="timer-only"]');
      ok(toCard.classList.contains("active") && toCard.getAttribute("aria-checked") === "true",
         "stage: syncStage marks the host's active template (timer-only)");
      var msgActive = el("stage-msg-active");
      ok(msgActive && !msgActive.hidden && msgActive.textContent.indexOf("WRAP UP NOW") >= 0,
         "stage: syncStage shows the live production message");
      // Restore the detection the following flow test depends on (do NOT clear it), now with the
      // provenance fields — translation + the transcript segment it was heard in.
      render(Object.assign({}, baseView, {
        detections: [
          { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95,
            translation: "KJV", source_segment: 42 },
        ],
        transcript: [{ id: 42, text: "turn to John three sixteen", start_ms: 3000, end_ms: 5000 }],
      }));
      // A bare detection must NOT display anything: no Preview/Live change, no chapter opened.
      ok(!window.__calls.some(function(c){ return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16"; }),
         "flow: a detection does NOT open its chapter or touch Preview/Live (nothing until Stage/Approve)");
      // The card renders the translation label + the source-phrase / "spoken Ns ago" provenance line.
      var det0 = el("detections-list").querySelector(".detection");
      var tr0 = det0 && det0.querySelector(".det-translation");
      ok(tr0 && tr0.textContent === "KJV", "card: the detection shows its translation label (KJV)");
      var meta0 = det0 && det0.querySelector(".det-meta");
      ok(meta0 && /spoken .+ ago/.test(meta0.textContent) && meta0.textContent.indexOf("John three sixteen") >= 0,
         "card: the detection shows its source phrase + 'spoken Ns ago' provenance");
      // Stage = accept into PREVIEW ONLY (nothing auto-goes-live — FR-115) + open the chapter.
      var goLiveBeforeStage = window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length;
      det0.querySelector(".det-stage").click();
      await sleep(15);
      ok(window.__calls.some(function(c){ return c.cmd === "approve_detection" && c.args && c.args.detectionId === 991; }),
         "flow: Stage → approve_detection (stages the verse in Preview)");
      ok(window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length === goLiveBeforeStage,
         "flow: Stage does NOT go live on its own (nothing auto-goes-live — FR-115)");
      ok(window.__calls.some(function(c){ return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16"; }),
         "flow: Stage → the full chapter opens in the Scriptures browser");
      // Approve = accept AND push Live to the audience in one action (the fast path).
      render(Object.assign({}, baseView, { detections: [
        { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
      ] }));
      var goLiveBeforeApprove = window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length;
      el("detections-list").querySelector(".det-approve").click();
      await sleep(15);
      ok(window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length > goLiveBeforeApprove,
         "flow: Approve → go_live (operator confirmed → pushed Live to the audience)");
      rtabTimer.click(); render(baseView); // reset for the following checks

      // === display: recognised STT text reaches the operator through the FULL poll->render
      // path (not just a direct syncTranscript call). This is what the 1s poll does with the
      // host-authoritative view once the on-device STT source ingests segments. ===
      var sttView = Object.assign({}, baseView, { transcript: [
        { id: 9001, text: "For God so loved the world", start_ms: 5000 },
        { id: 9002, text: "that he gave his only Son", start_ms: 9000 },
      ] });
      render(sttView); // the SAME top-level render() the 1s poll invokes
      var sttLog = el("transcript-log");
      var sttEmpty = el("transcript-empty");
      ok(sttLog.children.length === 2 &&
         sttLog.textContent.indexOf("For God so loved the world") >= 0 &&
         sttLog.textContent.indexOf("that he gave his only Son") >= 0,
         "display: STT segments in view.transcript render as visible lines in #transcript-log");
      ok(sttEmpty.style.display === "none",
         "display: the empty-state overlay is hidden once transcript lines arrive");
      // #1 real-time streaming: the in-progress interim renders as a live partial line and
      // clears when the utterance finalises (no partial_transcript).
      render(Object.assign({}, baseView, { partial_transcript: "and it came to" }));
      var partialEl = el("transcript-partial");
      ok(partialEl && !partialEl.hidden && partialEl.textContent.indexOf("and it came to") >= 0,
         "stream: a streaming interim renders as the live partial line");
      render(baseView);
      ok(partialEl.hidden, "stream: the partial line clears when the interim finalises");
      render(baseView); // restore so the trailing 1s poll stays consistent

      // === R4 detection: a confidence-bearing detection renders the match-% pill, colour-
      // coded green (>=90, e.g. an explicitly-spoken reference) vs amber "fuzzy" (a paraphrase). ===
      var detView = Object.assign({}, baseView, { detections: [
        { id: 501, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
        { id: 502, reference: "Psalm 23:1", text: "The Lord is my shepherd", confidence: 72 },
      ] });
      // CON-136/137/138 introduce session-persistent state keyed by REFERENCE TEXT (the
      // duplicate-suppression cooldown, the on-air link). "John 3:16" was just Staged AND
      // Approved above (id 991, the flow test) — without a clean slate here, THIS section's own
      // "John 3:16" (id 501) would render as a CON-137 duplicate instead of a normal card. A
      // reset before every detections-panel section keeps this section (and the ones with their
      // own reset calls below) independent of test order and of the stock reference strings the
      // rest of this suite reuses freely.
      window.__detResetForTest();
      render(detView); // the SAME render() the 1s poll invokes
      var detList = el("detections-list");
      var pills = detList.querySelectorAll(".match-pill");
      ok(pills.length === 2 &&
         detList.textContent.indexOf("95% MATCH") >= 0 &&
         detList.textContent.indexOf("72% MATCH") >= 0,
         "R4: detections render a match-% pill from view.confidence (95% + 72%)");
      // #3 newest-first: the host queues oldest-first, so id 502 (last in the array) renders on top.
      var firstRef = detList.querySelector(".detection .ref");
      ok(firstRef && firstRef.textContent.indexOf("Psalm 23:1") >= 0,
         "#3 the newest detection renders at the top (host oldest-first list reversed for display)");
      ok(pills[0].className.indexOf("fuzzy") >= 0 && pills[1].className.indexOf("fuzzy") < 0,
         "R4: pill colour follows its card — newest 72% fuzzy (amber) on top, 95% solid (green) below");

      // === CON-111/116/129/130 — list gap, meta text size, card tint by confidence, the bar ===
      ok(getComputedStyle(detList).gap === "12px",
         "CON-111: the detections list uses a 12px card gap (was 4px — cards read as a solid block)");
      var cards1 = Array.prototype.slice.call(detList.querySelectorAll(".detection"));
      var confCard = cards1.filter(function (c) { return c.classList.contains("det-confident"); })[0];
      var fuzzyCard = cards1.filter(function (c) { return c.classList.contains("det-fuzzy"); })[0];
      ok(!!confCard && !!fuzzyCard,
         "CON-129: a >=90% detection card is tinted det-confident and a <90% one det-fuzzy");
      ok(getComputedStyle(confCard).backgroundColor !== getComputedStyle(fuzzyCard).backgroundColor,
         "CON-129: the confident and fuzzy cards paint DIFFERENT computed background colours (not just a class name)");
      var confBar = confCard.querySelector(".det-bar-fill"), fuzzyBar = fuzzyCard.querySelector(".det-bar-fill");
      ok(!!confBar && confBar.style.width === "95%",
         "CON-130: the confidence bar fill is sized to the match % (95%)");
      ok(!!fuzzyBar && fuzzyBar.style.width === "72%" && fuzzyBar.classList.contains("fuzzy"),
         "CON-130: a fuzzy detection's bar fill is amber-classed and sized to its own % (72%)");
      ok(getComputedStyle(confCard.querySelector(".det-meta")).fontSize === "12px",
         "CON-116: detection meta text is 12px (was 11px)");

      // === CON-134 — a fuzzy (<90%) card drops the Approve fast-path for Edit, and explains the
      // missing alternatives list honestly rather than drawing one this build has no data for ===
      ok(!fuzzyCard.querySelector(".det-approve") && !!fuzzyCard.querySelector(".det-edit"),
         "CON-134: a low-confidence card offers Edit, not the Approve fast-path to the audience");
      ok(!!confCard.querySelector(".det-approve") && !confCard.querySelector(".det-edit"),
         "CON-134: a confident card is unchanged — it still offers Approve, not Edit");
      ok(/no alternative matches/i.test(fuzzyCard.textContent),
         "CON-134: the low-confidence card honestly explains no alternatives list is available (none is fabricated)");
      // Sana's security review (PR #61, blocking finding 1): the ORIGINAL version of this test
      // asserted immediately after the click, before setCursor's 120ms stageTimer could fire —
      // so it could not see the exact bug it was meant to guard against. window.__openChapterFor-
      // Stage's non-range branch arms that timer -> stage_scripture; Edit must use the read-only
      // window.__openChapterToBrowse instead, which passes stage=false and never arms it. This
      // now waits PAST 120ms and inspects the FULL call list for both staging commands.
      var callsBeforeEdit = window.__calls.length;
      fuzzyCard.querySelector(".det-edit").click();
      await sleep(200); // > setCursor's 120ms stageTimer debounce
      ok(window.__calls.some(function (c) { return c.cmd === "get_chapter" && c.args && c.args.reference === "Psalm 23:1"; }),
         "CON-134: Edit opens the reference in the real, already-working Scriptures chapter browser");
      var callsAfterEdit = window.__calls.slice(callsBeforeEdit);
      ok(!callsAfterEdit.some(function (c) { return c.cmd === "stage_scripture" || c.cmd === "follow_scripture"; }),
         "CON-134 (Sana finding 1): Edit never stages — checked well past the 120ms debounce, over the FULL call list, not just approve/dismiss");
      ok(!callsAfterEdit.some(function (c) { return c.cmd === "dismiss_detection" || c.cmd === "approve_detection"; }),
         "CON-134: Edit is non-destructive — it does not dequeue or dismiss the detection either");
      // Cody's review of PR #64: the VERSE-RANGE half of this fix (loadChapter's `isRange`
      // branch, app.js ~line 3699) is correct by code trace but had ZERO coverage — every
      // fixture above requests a single-verse reference, so `isRange` was always false by
      // construction and that branch's own `if (stage)` guard was dead code as far as this
      // suite could tell (mutating it back to always-stage produced 0 FAIL across the whole
      // suite). selahcue-core::Reference's Display confirms a range like "John 3:16-18" is real
      // production input (spoken multi-verse citations), not a hypothetical. This exercises it
      // directly: the mock's get_chapter now returns a genuine range response for a "N-M"
      // reference (see its own comment), so isRange really is true here, not simulated.
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 598, reference: "John 3:16-18", text: "For God so loved the world", confidence: 62 },
      ] }));
      var rangeCard = el("detections-list").querySelector(".detection");
      var callsBeforeRangeEdit = window.__calls.length;
      rangeCard.querySelector(".det-edit").click();
      await sleep(200);
      ok(window.__calls.some(function (c) { return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16-18"; }),
         "CON-134 (Sana finding 1, range coverage): Edit opens a range reference in the chapter browser");
      var callsAfterRangeEdit = window.__calls.slice(callsBeforeRangeEdit);
      ok(!callsAfterRangeEdit.some(function (c) { return c.cmd === "stage_scripture" || c.cmd === "follow_scripture"; }),
         "CON-134 (Sana finding 1, range coverage): Edit never stages a RANGE reference either — the isRange branch's own stage=false guard, not just the single-verse one");
      // Sana's follow-up security review (PR #64, finding B): setCursor's own clearTimeout only
      // runs once setCursor itself is reached — but loadChapter's get_chapter fetch sits BEFORE
      // that call, so a timer already pending when a read-only load STARTS can still fire mid-
      // fetch on a slow (300ms+) round trip, before setCursor(idx, false) ever gets a chance to
      // cancel it. Reproduce for real: arm the timer via a live verse click (not a hand-set
      // variable), then click Edit on a genuinely different detection while forcing its
      // get_chapter fetch to hang well past 120ms.
      var stageableVerseRow = el("verse-list").querySelector(".verse");
      ok(!!stageableVerseRow, "setup: the Scriptures browser has a clickable verse row to arm the stage timer from");
      var callsBeforeArm = window.__calls.length;
      stageableVerseRow.click(); // setCursor(i, true, true) — arms the 120ms stageTimer
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 599, reference: "Zephaniah 1:14", text: "The great day of the LORD is near", confidence: 61 },
      ] }));
      window.__getChapterDeferOnce = true;
      el("detections-list").querySelector(".detection").querySelector(".det-edit").click();
      await waitFor(function () { return window.__calls.some(function (c) { return c.cmd === "get_chapter" && c.args && c.args.reference === "Zephaniah 1:14"; }); });
      // The fetch is now deliberately held open. Wait well past the 120ms debounce while it is
      // still pending — before finding B's fix, THIS is exactly where the stale, pre-armed timer
      // would fire and stage the PRIOR verse, a target neither Edit nor the operator asked for.
      await sleep(200);
      ok(!window.__calls.slice(callsBeforeArm).some(function (c) { return c.cmd === "stage_scripture" || c.cmd === "follow_scripture"; }),
         "CON-134 (Sana finding B): a timer armed BEFORE a read-only Edit load starts does not fire while that load's chapter fetch is still in flight, even past its own 120ms debounce");
      window.__getChapterDeferredResolve();
      await sleep(200); // setCursor(idx, false) now runs too — confirm it stays quiet as well
      ok(!window.__calls.slice(callsBeforeArm).some(function (c) { return c.cmd === "stage_scripture" || c.cmd === "follow_scripture"; }),
         "CON-134 (Sana finding B): once the deferred fetch resolves and Edit's own setCursor(idx, false) runs, still nothing stages — the window is closed, not just narrowed");

      // === CON-054 (blocker, WCAG 1.4.1) — the staged verse's non-colour signal, gated on the
      // HOST's own staged_scripture readback (Cody's review of PR #66, remediated): the browse
      // cursor (.verse.cursor) moves for every navigation gesture, INCLUDING the deliberately
      // read-only ones (Edit on a low-confidence detection, History's re-stage) that pass
      // stage=false specifically so nothing is staged. Cody reproduced live that gating the
      // literal "STAGED" text on .cursor alone made the pill lie for exactly those flows. This
      // reproduces his exact scenario directly — window.__openChapterToBrowse (stage=false, the
      // same entry point Edit/History use) must move the cursor WITHOUT painting the pill — then
      // proves the pill turns on only once a real host readback (driven through render(), not
      // poked at the class) confirms the SAME verse, and turns off again once the host says so.
      // The console surface itself was last switched away to theme-designer a few tests back, so
      // switch back first — otherwise the panel is hidden and getClientRects() would read empty
      // for reasons that have nothing to do with the pill.
      document.querySelector('.nav-item[data-surface="console"]').click();
      render(Object.assign({}, baseView, { staged_scripture: null, staged_index: null }));
      window.__openChapterToBrowse("Isaiah 61:5"); // stage=false — the real Edit/History entry point
      await waitFor(function () { return !!el("verse-list").querySelector(".verse.cursor"); });
      var vRows = el("verse-list").querySelectorAll(".verse");
      ok(vRows.length === 2, "CON-054 (setup): the fixture chapter renders both its verses");
      var vCursorRow = el("verse-list").querySelector(".verse.cursor");
      var vPill = vCursorRow.querySelector(".verse-staged-pill");
      ok(!vCursorRow.classList.contains("is-staged") &&
         (!vPill || getComputedStyle(vPill).display === "none" || vPill.getClientRects().length === 0),
         "CON-054 (Cody's finding, reproduced + fixed): browsing a verse via the READ-ONLY __openChapterToBrowse path moves the cursor but paints no STAGED pill — nothing was ever staged");
      // Now the host confirms — via a real render(), the same path syncChrome/setPanel already
      // trust for the Preview panel, never by poking the class directly.
      render(Object.assign({}, baseView, { staged_scripture: "Isaiah 61:5", staged_index: null }));
      ok(vCursorRow.classList.contains("is-staged"), "CON-054 (setup): the host's staged_scripture readback now matches this row");
      vPill = vCursorRow.querySelector(".verse-staged-pill");
      ok(!!vPill && getComputedStyle(vPill).display !== "none" && vPill.getClientRects().length > 0,
         "CON-054: once the HOST confirms, the staged verse row paints a STAGED pill (computed display, not just the class)");
      ok(vPill.textContent.trim() === "STAGED",
         "CON-054: the pill states the word STAGED — a non-colour signal alongside the row's green tint (WCAG 1.4.1)");
      var vOtherRow = Array.prototype.filter.call(vRows, function (r) { return r !== vCursorRow; })[0];
      ok(!!vOtherRow, "CON-054 (setup): a second, non-staged verse row exists to serve as a negative control");
      var vOtherPill = vOtherRow.querySelector(".verse-staged-pill");
      ok(!vOtherRow.classList.contains("is-staged") && !!vOtherPill && getComputedStyle(vOtherPill).display === "none",
         "CON-054 (negative control): a DIFFERENT verse that is not the host's staged_scripture paints no STAGED pill");
      var vPillCs = getComputedStyle(vPill);
      var vPillR = _cr(_rgba(vPillCs.color), _rgba(vPillCs.backgroundColor));
      ok(vPillR >= 4.5, "CON-054: the STAGED pill's label clears AA-normal on its own fill (" + _f(vPillR) + ":1)");
      // De-stage (e.g. Clear/blackout on the host) — the pill must be reactive, not sticky.
      render(Object.assign({}, baseView, { staged_scripture: null, staged_index: null }));
      ok(!vCursorRow.classList.contains("is-staged"),
         "CON-054: once the host reports nothing staged, the pill is removed again — it is not sticky once painted");

      // Sana's non-blocking finding: a MISSING confidence used to fail OPEN into the confident
      // branch (Approve fast-path) purely because `hasConfidence && …` short-circuits false on
      // no score at all — an unscored match is at least as uncertain as a known-low one.
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 599, reference: "Nahum 1:7", text: "The Lord is good", translation: "KJV" }, // no confidence field
      ] }));
      var noConfCard = el("detections-list").querySelector(".detection");
      ok(!noConfCard.querySelector(".det-approve") && !!noConfCard.querySelector(".det-edit"),
         "CON-134 (Sana non-blocking): a detection with NO reported confidence takes the cautious Edit branch, not Approve");
      ok(!noConfCard.querySelector(".match-pill") && !noConfCard.querySelector(".det-bar-track"),
         "CON-134 (Sana non-blocking, control): still honest-empty — no fabricated match-% pill or bar for a score that was never reported");

      // === CON-121 — the empty-state redesign ===
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [] }));
      var emptyIcon = el("detections-empty").querySelector(".fwd-icon");
      ok(emptyIcon.textContent === "✦", "CON-121: the empty state uses the panel's gold ✦ identity mark (was ✨)");
      ok(getComputedStyle(emptyIcon).color !== getComputedStyle(el("det-empty-sub")).color,
         "CON-121: the empty glyph is gold-tinted, a genuinely different computed colour from the muted body copy");
      ok(parseInt(getComputedStyle(el("det-empty-msg")).fontWeight, 10) >= 700,
         "CON-121: the empty-state heading is bold, distinguishing it from the body copy below it");

      // === CON-136 — the on-air link: only claims on-air once the host CONFIRMS
      // view.live_scripture matches, and self-clears the moment reality moves on ===
      window.__detResetForTest();
      render(detView);
      // Seed the MOCK's own V.detections (not just the rendered view) so approve_detection's
      // handler can resolve which reference id 501 is — the mock looks up the id in V.detections
      // (mirroring a real host), and render() alone never touches V. Same pattern other sections
      // of this suite already use directly (e.g. V.items = [...] for the Service Plan tests).
      V.detections = detView.detections;
      ok(el("det-onair").hidden, "CON-136: no on-air card before anything is approved");
      var onAirGoLiveBefore = window.__calls.filter(function (c) { return c.cmd === "go_live"; }).length;
      var onAirConfCard = Array.prototype.filter.call(el("detections-list").querySelectorAll(".detection"),
        function (c) { return c.classList.contains("det-confident"); })[0];
      onAirConfCard.querySelector(".det-approve").click();
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "go_live"; }).length > onAirGoLiveBefore,
         "CON-136 (premise): Approve still calls go_live — CON-120's existing semantics are unchanged");
      ok(!el("det-onair").hidden && getComputedStyle(el("det-onair")).display !== "none",
         "CON-136: the on-air card appears once the host confirms John 3:16 is actually live (computed, not just [hidden])");
      ok(el("det-onair-ref").textContent === "John 3:16" && /ON AIR/.test(el("det-onair").querySelector(".det-onair-pill").textContent),
         "CON-136: the on-air card names the reference and carries an ON AIR pill");
      ok(/Live on main output/.test(el("det-onair-meta").textContent),
         "CON-136: the on-air card states it is live on the main output");
      // Self-clearing: feed a render() where live_scripture no longer matches (the NEXT poll
      // after the operator navigated elsewhere) — the card must clear with no further click.
      render(Object.assign({}, baseView, { live_scripture: "Genesis 1:13" }));
      ok(el("det-onair").hidden,
         "CON-136: the card clears the instant view.live_scripture no longer matches — never a stale claim");
      // Re-arm, then verify auto-clear specifically on blackout (even if live_scripture still
      // matches). Reset first (harmless defensive hygiene, matching every other section).
      window.__detResetForTest();
      render(detView);
      V.detections = detView.detections; // re-seed — the previous approve_detection filtered it out
      Array.prototype.filter.call(el("detections-list").querySelectorAll(".detection"),
        function (c) { return c.classList.contains("det-confident"); })[0].querySelector(".det-approve").click();
      await sleep(15);
      ok(!el("det-onair").hidden, "CON-136 (setup): re-armed for the blackout check");
      render(Object.assign({}, baseView, { live_scripture: "John 3:16", blackout: true }));
      ok(el("det-onair").hidden, "CON-136: the card clears on blackout even though live_scripture still matches");
      // Re-arm, then "Next verse" — a LOCAL dismiss that must NOT touch output.
      window.__detResetForTest();
      render(detView);
      V.detections = detView.detections; // re-seed
      Array.prototype.filter.call(el("detections-list").querySelectorAll(".detection"),
        function (c) { return c.classList.contains("det-confident"); })[0].querySelector(".det-approve").click();
      await sleep(15);
      var clearCallsBeforeNext = window.__calls.filter(function (c) { return c.cmd === "clear"; }).length;
      el("det-onair-next").click();
      ok(el("det-onair").hidden, "CON-136: 'Next verse' dismisses the on-air card");
      ok(window.__calls.filter(function (c) { return c.cmd === "clear"; }).length === clearCallsBeforeNext,
         "CON-136: 'Next verse' never invokes clear — the output itself is untouched");
      // Re-arm, then "Clear output" — invokes the SAME command the emergency footer uses.
      window.__detResetForTest();
      render(detView);
      V.detections = detView.detections; // re-seed
      Array.prototype.filter.call(el("detections-list").querySelectorAll(".detection"),
        function (c) { return c.classList.contains("det-confident"); })[0].querySelector(".det-approve").click();
      await sleep(15);
      var clearCallsBefore = window.__calls.filter(function (c) { return c.cmd === "clear"; }).length;
      el("det-onair-clear").click();
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "clear"; }).length > clearCallsBefore,
         "CON-136: 'Clear output' invokes the real clear command (the same one the emergency footer uses)");
      ok(el("det-onair").hidden, "CON-136: the card clears once the host confirms output is actually cleared");

      // === CON-136 / Quinn's QA review (PR #61, bug 17tnw2axre8): a WHOLE-CHAPTER detection
      // (e.g. a spoken "Isaiah 61", no verse) never lit the on-air card. controller.rs's
      // stage_reference_for_detection (the ApproveDetection handler) narrows a bare "Book
      // Chapter" reference to its first verse before it goes live — d.reference stays
      // "Isaiah 61" but view.live_scripture reads "Isaiah 61:1" — so a bare === compare could
      // never match this real, common input shape. The mock's go_live already reproduces this
      // exact narrowing (see its own comment) so this test exercises the real transformation,
      // not a hand-picked string. ===
      window.__detResetForTest();
      var chapterView = Object.assign({}, baseView, { detections: [
        { id: 901, reference: "Isaiah 61", text: "The Spirit of the Lord God is upon me", confidence: 93 },
      ] });
      render(chapterView);
      V.detections = chapterView.detections;
      el("detections-list").querySelector(".det-approve").click();
      await sleep(15);
      ok(V.live_scripture === "Isaiah 61:1",
         "CON-136 (premise): the mock's go_live narrowed the whole-chapter reference to its first verse, exactly like the real host");
      ok(!el("det-onair").hidden && el("det-onair-ref").textContent === "Isaiah 61",
         "CON-136 (Quinn, 17tnw2axre8): the on-air card lights for a whole-chapter detection even though live_scripture is the host-narrowed 'Isaiah 61:1'");
      // It must also SURVIVE the next poll (this is what a bare !== would have broken: the
      // card lighting once, then immediately self-clearing because live_scripture never equals
      // the un-narrowed reference on any later render either).
      render(Object.assign({}, chapterView, { live_scripture: "Isaiah 61:1" }));
      ok(!el("det-onair").hidden,
         "CON-136 (Quinn, 17tnw2axre8): the on-air card SURVIVES a later poll — it does not immediately self-clear on the narrowed reference");
      // Control: a genuinely different live reference still clears it — the narrowing match is
      // exact (append ":1"), not a fuzzy "starts with" that would paper over a real mismatch.
      render(Object.assign({}, chapterView, { live_scripture: "Isaiah 62:1" }));
      ok(el("det-onair").hidden,
         "CON-136 (Quinn, control): a genuinely different live reference still clears the card — the narrowing match is exact, not fuzzy");
      window.__detResetForTest();
      render(baseView);

      // === CON-137, REDESIGNED (Sana's security review, PR #61) — the original build here was
      // an AUTOMATIC client-side duplicate-cooldown UI. Sana proved the host already dedupes at
      // the source (selahcue-core::TranscriptEngine's RECENT_DEDUP_WINDOW ring, detection.rs) —
      // a re-detection of a still-ringed reference is dropped BEFORE it ever reaches
      // view.detections, so the automatic client UI was near-unreachable in production. It is
      // removed (no .det-duplicate/.det-dup-* anywhere any more). What remains is genuinely
      // NOT redundant with the host: an OPERATOR-DIRECTED mute, on every normal card, that the
      // host's blind automatic ring has no equivalent for. Dedicated reference strings (not
      // reused elsewhere in this suite) so mutedRefs cannot leak into an unrelated fixture. ===
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 601, reference: "Habakkuk 3:19", text: "The Lord God is my strength", confidence: 91 },
      ] }));
      var hCard = el("detections-list").querySelector(".detection");
      var hMuteBtn = hCard.querySelector(".det-mute-btn");
      ok(!!hMuteBtn, "CON-137: every normal detection card carries a Mute control in its head row — not gated behind any special state");
      ok(hMuteBtn.getAttribute("aria-label").indexOf("for this service") >= 0 &&
         hMuteBtn.getAttribute("aria-label").indexOf("undo from History") >= 0,
         "CON-137: Mute's accessible name states an honest, reversible scope — not an unqualified permanent claim");
      var dismissCallsBefore601 = window.__calls.filter(function (c) { return c.cmd === "dismiss_detection"; }).length;
      hMuteBtn.click();
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 601; }).length === 1,
         "CON-137: Mute dismisses the current detection on the host");
      // Sana's blocking finding 2: this used to fire on EVERY render that reached a still-queued
      // muted id (no cap, no record) — visibly, the panel would read empty while the tab's count
      // pill still said "1 new". Re-render the SAME still-queued id several times (simulating
      // poll latency before the host's own view catches up) and prove it is dismissed ONCE.
      for (var muteRepeat = 0; muteRepeat < 4; muteRepeat++) {
        render(Object.assign({}, baseView, { detections: [
          { id: 601, reference: "Habakkuk 3:19", text: "The Lord God is my strength", confidence: 91 },
        ] }));
      }
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 601; }).length === 1,
         "CON-137 (Sana finding 2): re-rendering the SAME still-queued muted id 4 more times sends exactly ONE dismiss total, not one per render");
      ok(el("detections-list").children.length === 0 && getComputedStyle(el("detections-empty")).display !== "none",
         "CON-137: a muted reference never renders as a card — auto-dismissed before it paints");
      // A genuinely NEW detection id for the same muted reference is real work and must still be
      // dismissed (and recorded) — the once-per-id guard must not become a once-ever guard.
      render(Object.assign({}, baseView, { detections: [
        { id: 602, reference: "Habakkuk 3:19", text: "The Lord God is my strength", confidence: 91 },
      ] }));
      ok(window.__calls.some(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 602; }),
         "CON-137: a genuinely NEW id for the same muted reference is also dismissed (the guard is per-id, not a stuck latch)");
      render(baseView);
      // History now carries a real record of the mute — Sana's finding 2 also required this;
      // the original build had none at all for this path.
      var histBtnM = el("det-view-history"), liveBtnM = el("det-view-live");
      histBtnM.click();
      var muteHistRow = Array.prototype.filter.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Habakkuk 3:19/.test(r.textContent); })[0];
      ok(!!muteHistRow && /MUTED/.test(muteHistRow.textContent),
         "CON-137: the mute is recorded in History with a MUTED badge — no more silent, unrecorded auto-dismisses");
      var unmuteBtn = muteHistRow.querySelector(".det-history-unmute");
      ok(!!unmuteBtn, "CON-137: the History row for a muted reference offers Unmute — a real reverse gear, not just a corrected copy claim");
      unmuteBtn.click();
      // renderDetectionHistory rebuilds the list from scratch (list.innerHTML = ""), so
      // muteHistRow is now a DETACHED node — re-query the live DOM, not the stale reference.
      var muteHistRowAfter = Array.prototype.filter.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Habakkuk 3:19/.test(r.textContent); })[0];
      ok(!!muteHistRowAfter && !muteHistRowAfter.querySelector(".det-history-unmute"),
         "CON-137: clicking Unmute removes the control immediately (re-rendered from the SAME History record — the row itself still exists as a log entry)");
      // Unmuting must actually restore normal behaviour — a later re-detection is NOT suppressed.
      liveBtnM.click();
      render(Object.assign({}, baseView, { detections: [
        { id: 603, reference: "Habakkuk 3:19", text: "The Lord God is my strength", confidence: 91 },
      ] }));
      ok(!!el("detections-list").querySelector('[aria-label="Dismiss Habakkuk 3:19"]'),
         "CON-137: after Unmute, a later re-detection of the same reference renders normally again — not silently suppressed forever");
      window.__detResetForTest();
      render(baseView);

      // === Vera's performance review (PR #64, P2): a FAILED dismiss_detection must NOT
      // permanently mark the id "handled". mutedDismissSent is recorded BEFORE the invoke
      // resolves so the once-per-id guard can stop repeat-fire on the SUCCESS path — but a
      // rejected invoke (busy host, link blip, refusal) used to leave the id stuck in that set
      // forever, with no retry: the exact visible inconsistency Sana's original finding was
      // about (empty panel, stale count pill), now permanent instead of transient. Exercises
      // BOTH call sites. Dedicated references, unused elsewhere in this suite. ===
      window.__detResetForTest();
      render(baseView);

      // Auto-dismiss loop (syncDetections): mute "Obadiah 1:3" via a normal, successful click —
      // then present a genuinely NEW still-queued id for the same now-muted reference while the
      // host is forced to reject the dismiss once.
      render(Object.assign({}, baseView, { detections: [
        { id: 611, reference: "Obadiah 1:3", text: "As you have done, it shall be done to you", confidence: 91 },
      ] }));
      el("detections-list").querySelector(".detection").querySelector(".det-mute-btn").click();
      await sleep(15);
      window.__dismissDetectionRejectOnce = true;
      render(Object.assign({}, baseView, { detections: [
        { id: 612, reference: "Obadiah 1:3", text: "As you have done, it shall be done to you", confidence: 91 },
      ] }));
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 612; }).length === 1,
         "CON-137 (Vera P2, auto-dismiss loop): the first (rejected) dismiss attempt is sent");
      // Re-present the SAME still-queued id — the host has not caught up, exactly Sana's original
      // "host is slow" scenario. Before this fix the id was already (wrongly) marked handled and
      // this would send nothing, leaving the inconsistency permanent.
      render(Object.assign({}, baseView, { detections: [
        { id: 612, reference: "Obadiah 1:3", text: "As you have done, it shall be done to you", confidence: 91 },
      ] }));
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 612; }).length === 2,
         "CON-137 (Vera P2, auto-dismiss loop): a FAILED dismiss is retried on the next poll, not permanently swallowed");
      window.__detResetForTest();
      render(baseView);

      // Manual mute-button click (buildDetectionCard): the click's OWN dismiss round-trip fails.
      // The mute itself is client-side state the operator asked for and must stick regardless —
      // but the failed dismiss must be retried, and by the auto-dismiss loop on the next poll
      // (the card no longer renders once muted, so the button itself gets no second chance).
      render(Object.assign({}, baseView, { detections: [
        { id: 621, reference: "Haggai 1:5", text: "Consider your ways", confidence: 91 },
      ] }));
      window.__dismissDetectionRejectOnce = true;
      el("detections-list").querySelector(".detection").querySelector(".det-mute-btn").click();
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 621; }).length === 1,
         "CON-137 (Vera P2, manual mute button): the button's own dismiss attempt is sent even though it will be rejected");
      render(Object.assign({}, baseView, { detections: [
        { id: 621, reference: "Haggai 1:5", text: "Consider your ways", confidence: 91 },
      ] }));
      ok(el("detections-list").children.length === 0,
         "CON-137 (Vera P2, manual mute button): the reference stays muted client-side even though its own dismiss round-trip failed");
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 621; }).length === 2,
         "CON-137 (Vera P2, manual mute button): the auto-dismiss loop retries the id the button's own failed dismiss left un-cleared — the two call sites' cleanup composes correctly");
      window.__detResetForTest();
      render(baseView);

      // Manual mute-button click, THE RACE: an intervening poll (a genuinely unrelated render()
      // call — same still-queued view) lands WHILE the click's own dismiss is still in flight,
      // before it finally fails. That intervening render's own pass through syncDetections
      // re-stores detectionsKey to match this exact still-queued view (mutedDismissSent already
      // has the id, so it does not double-invoke — but the key gets re-stored as an unconditional
      // side effect of reaching the top of the function). Un-remembering the id alone would then
      // be inert: the NEXT identical render recomputes the SAME key the intervening poll just
      // re-stored and bails before ever reaching the retry logic. Only invalidating detectionsKey
      // in the catch itself — not relying on whatever the last render happened to leave behind —
      // survives this ordering.
      render(Object.assign({}, baseView, { detections: [
        { id: 661, reference: "Micah 6:8", text: "He hath shewed thee, O man, what is good", confidence: 91 },
      ] }));
      window.__dismissDetectionDeferRejectOnce = true;
      el("detections-list").querySelector(".detection").querySelector(".det-mute-btn").click();
      await sleep(15); // the click's dismiss is now pending, not yet resolved
      // The intervening poll: identical still-queued view, host hasn't caught up either.
      render(Object.assign({}, baseView, { detections: [
        { id: 661, reference: "Micah 6:8", text: "He hath shewed thee, O man, what is good", confidence: 91 },
      ] }));
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 661; }).length === 1,
         "CON-137 (Vera P2, manual mute button, race): the intervening poll does not double-fire while the button's own dismiss is still in flight");
      window.__dismissDetectionDeferredReject();
      await sleep(15); // now the click's original dismiss actually fails
      // Re-present the SAME still-queued detection once more — this is the exact render the old,
      // simpler fix could not recover from, because the intervening poll above had already
      // re-stored detectionsKey to match it.
      render(Object.assign({}, baseView, { detections: [
        { id: 661, reference: "Micah 6:8", text: "He hath shewed thee, O man, what is good", confidence: 91 },
      ] }));
      await sleep(15);
      ok(window.__calls.filter(function (c) { return c.cmd === "dismiss_detection" && c.args.detectionId === 661; }).length === 2,
         "CON-137 (Vera P2, manual mute button, race): the deferred failure is still retried even though an intervening poll had already re-stored detectionsKey to match the unchanged view");
      window.__detResetForTest();
      render(baseView);

      // === Sana's security review (PR #64, finding C): recordDetectionOutcome used to fire
      // unconditionally BEFORE the dismiss settled, so a REFUSED dismiss still wrote a MUTED row
      // to the audit trail — a false record, since nothing actually changed on the host — and,
      // combined with Vera's P2 retry fix, a later successful retry would write a SECOND row for
      // the very same id. Prove: (a) a rejected attempt writes no row at all, (b) exactly one row
      // exists once a (retried) attempt actually succeeds — never two. ===
      window.__detResetForTest();
      render(baseView);
      render(Object.assign({}, baseView, { detections: [
        { id: 641, reference: "Jonah 1:17", text: "The Lord had prepared a great fish", confidence: 91 },
      ] }));
      window.__dismissDetectionRejectOnce = true;
      el("detections-list").querySelector(".detection").querySelector(".det-mute-btn").click();
      await sleep(15);
      var histBtnC = el("det-view-history"), liveBtnC = el("det-view-live");
      histBtnC.click();
      ok(!Array.prototype.some.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Jonah 1:17/.test(r.textContent); }),
         "CON-137 (Sana finding C): a REFUSED dismiss writes NO History row — the audit trail must not claim a mute the host never confirmed");
      liveBtnC.click();
      // The auto-dismiss loop retries on the next still-queued render of the SAME id — reject
      // THIS attempt too, so a genuine second failure exercises the auto-dismiss LOOP's own
      // recordDetectionOutcome placement, not only the button's (a single always-succeeding
      // retry cannot tell "recorded on dispatch" apart from "recorded on confirmed success").
      window.__dismissDetectionRejectOnce = true;
      render(Object.assign({}, baseView, { detections: [
        { id: 641, reference: "Jonah 1:17", text: "The Lord had prepared a great fish", confidence: 91 },
      ] }));
      await sleep(15);
      histBtnC.click();
      ok(!Array.prototype.some.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Jonah 1:17/.test(r.textContent); }),
         "CON-137 (Sana finding C): a SECOND refused attempt, this time via the auto-dismiss loop's own retry, still writes no row — the loop's record must also wait for confirmation, not fire on dispatch");
      liveBtnC.click();
      // A THIRD attempt, finally not rejected, succeeds.
      render(Object.assign({}, baseView, { detections: [
        { id: 641, reference: "Jonah 1:17", text: "The Lord had prepared a great fish", confidence: 91 },
      ] }));
      await sleep(15);
      histBtnC.click();
      var jonahRowsC = Array.prototype.filter.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Jonah 1:17/.test(r.textContent); });
      ok(jonahRowsC.length === 1,
         "CON-137 (Sana finding C): once a retry actually succeeds, exactly ONE row is written for this id — not a duplicate from either earlier failed attempt");
      liveBtnC.click();
      window.__detResetForTest();
      render(baseView);

      // === Sana's security review (PR #64, finding D): Unmute reset detHistoryKey (so the
      // History panel's own Unmute button disappeared immediately) but never detectionsKey — so
      // an unchanged, still-queued detection for the just-unmuted reference recomputed to the
      // SAME memoization key syncDetections already had stored and was silently skipped forever,
      // never reappearing in the live panel short of some UNRELATED change perturbing the key. ===
      window.__detResetForTest();
      render(baseView);
      render(Object.assign({}, baseView, { detections: [
        { id: 651, reference: "Habakkuk 2:4", text: "The just shall live by his faith", confidence: 91 },
      ] }));
      el("detections-list").querySelector(".detection").querySelector(".det-mute-btn").click();
      await sleep(15); // the id-651 dismiss succeeds — mutedRefs now has "Habakkuk 2:4"
      // A NEW still-open id for the same now-muted reference: auto-dismissed and skipped, but
      // this is the render call that leaves detectionsKey set to THIS exact dets array's hash —
      // the precondition finding D's reproduction depends on.
      render(Object.assign({}, baseView, { detections: [
        { id: 652, reference: "Habakkuk 2:4", text: "The just shall live by his faith", confidence: 91 },
      ] }));
      await sleep(15); // let id 652's own retried dismiss settle before touching History
      var histBtnD = el("det-view-history"), liveBtnD = el("det-view-live");
      histBtnD.click();
      var habRow = Array.prototype.filter.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Habakkuk 2:4/.test(r.textContent); })[0];
      ok(!!habRow, "sanity: the confirmed mute is recorded in History before testing Unmute");
      habRow.querySelector(".det-history-unmute").click();
      liveBtnD.click();
      // Re-present the EXACT SAME still-queued detection (id 652, unchanged) — the host has not
      // caught up. Before finding D's fix this recomputes to the identical key syncDetections
      // already has stored and the card never reappears.
      render(Object.assign({}, baseView, { detections: [
        { id: 652, reference: "Habakkuk 2:4", text: "The just shall live by his faith", confidence: 91 },
      ] }));
      ok(!!el("detections-list").querySelector('[aria-label="Dismiss Habakkuk 2:4"]'),
         "CON-137 (Sana finding D): after Unmute, an unchanged still-queued detection reappears — detectionsKey is invalidated alongside detHistoryKey, not left stale");
      window.__detResetForTest();
      render(baseView);

      // === CON-138 — Live | History: a session-only audit trail, since the host does not
      // retain a resolved detection once it is dequeued ===
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 701, reference: "Micah 7:8", text: "When I fall, I shall arise", confidence: 91 },
      ] }));
      var histBtn = el("det-view-history"), liveBtn = el("det-view-live");
      ok(el("detections-history-view").hidden && !el("detections-live-view").hidden,
         "CON-138: the panel opens on Live, not History");
      histBtn.click();
      ok(!el("detections-history-view").hidden && el("detections-live-view").hidden &&
         histBtn.getAttribute("aria-selected") === "true" && liveBtn.getAttribute("aria-selected") === "false",
         "CON-138: clicking History shows the history view and updates aria-selected");
      ok(/No detection history yet/.test(el("detections-history-empty").textContent) &&
         getComputedStyle(el("detections-history-empty")).display !== "none",
         "CON-138: an empty session shows a clear empty state, not a blank panel");
      liveBtn.click();
      el("detections-list").querySelector('[aria-label="Dismiss Micah 7:8"]').click();
      await sleep(15);
      histBtn.click();
      var histRow = el("detections-history-list").querySelector(".det-history-row");
      ok(!!histRow && /Micah 7:8/.test(histRow.textContent) && /DISMISSED/.test(histRow.textContent),
         "CON-138: a Dismissed detection appears in History with a DISMISSED badge");
      ok(getComputedStyle(el("detections-history-empty")).display === "none",
         "CON-138: the history empty state hides once an entry exists");
      // Re-stage: jumps to the reference in the real Scriptures browser (never replays a
      // dequeued detection id the host would refuse) and switches back to Live. Sana's security
      // review (PR #61, finding 1) applies here too — this must wait PAST setCursor's 120ms
      // stageTimer and check the full call list, the same gap that let re-stage silently stage
      // through window.__openChapterForStage before it was switched to …ToBrowse.
      var callsBeforeRestage = window.__calls.length;
      histRow.querySelector(".det-history-restage").click();
      await sleep(200); // > setCursor's 120ms stageTimer debounce
      ok(window.__calls.some(function (c) { return c.cmd === "get_chapter" && c.args && c.args.reference === "Micah 7:8"; }),
         "CON-138: re-stage opens Micah 7:8 in the Scriptures browser");
      var callsAfterRestage = window.__calls.slice(callsBeforeRestage);
      ok(!callsAfterRestage.some(function (c) { return c.cmd === "stage_scripture" || c.cmd === "follow_scripture"; }),
         "CON-138 (Sana finding 1): re-stage never stages on its own — checked well past the 120ms debounce, over the full call list");
      ok(!el("detections-live-view").hidden, "CON-138: re-stage switches the panel back to Live");
      // Cody's review of PR #64: same range-coverage hole as CON-134's Edit test above, for
      // re-stage's own call site. Dismiss a RANGE-reference detection to seed a History row,
      // then re-stage it — the mock's get_chapter now returns a genuine range response for it.
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 597, reference: "Romans 8:28-30", text: "And we know", confidence: 91 },
      ] }));
      el("detections-list").querySelector('[aria-label="Dismiss Romans 8:28-30"]').click();
      await sleep(15);
      histBtn.click();
      var rangeHistRow = Array.prototype.filter.call(el("detections-history-list").querySelectorAll(".det-history-row"),
        function (r) { return /Romans 8:28-30/.test(r.textContent); })[0];
      ok(!!rangeHistRow, "CON-138 (range coverage, setup): the range-reference dismissal is recorded in History");
      var callsBeforeRangeRestage = window.__calls.length;
      rangeHistRow.querySelector(".det-history-restage").click();
      await sleep(200);
      ok(window.__calls.some(function (c) { return c.cmd === "get_chapter" && c.args && c.args.reference === "Romans 8:28-30"; }),
         "CON-138 (range coverage): re-stage opens the range reference in the chapter browser");
      var callsAfterRangeRestage = window.__calls.slice(callsBeforeRangeRestage);
      ok(!callsAfterRangeRestage.some(function (c) { return c.cmd === "stage_scripture" || c.cmd === "follow_scripture"; }),
         "CON-138 (Sana finding 1, range coverage): re-stage never stages a RANGE reference either — the isRange branch's own stage=false guard");
      liveBtn.click();
      // DET_HISTORY_MAX bounds the log so it cannot grow without limit across a long service
      // (bounded-memory). Dismiss 60 distinct detections, OLDEST (#0) first through NEWEST
      // (#59) last — recordDetectionOutcome runs synchronously inside each click handler
      // (before any await, verified above), so push order is exactly this click order
      // regardless of the mocked host's own async resolution timing; all 60 buttons already
      // exist from the single render() above, so no re-render is needed between clicks.
      window.__detResetForTest();
      var manyDets = [];
      for (var hi = 0; hi < 60; hi++) {
        manyDets.push({ id: 8000 + hi, reference: "Nahum 1:7 #" + hi, text: "The Lord is good", confidence: 91 });
      }
      render(Object.assign({}, baseView, { detections: manyDets }));
      ok(el("detections-list").querySelectorAll('[aria-label^="Dismiss "]').length === 60,
         "CON-138 (setup): all 60 detections rendered with a Dismiss control");
      for (var hj = 0; hj < 60; hj++) {
        el("detections-list").querySelector('[aria-label="Dismiss Nahum 1:7 #' + hj + '"]').click();
      }
      await sleep(15);
      histBtn.click();
      var histRows = el("detections-history-list").querySelectorAll(".det-history-row");
      ok(histRows.length === 50,
         "CON-138 (bounded-memory): 60 resolved detections cap the History log at DET_HISTORY_MAX=50, not 60 (" + histRows.length + " rendered)");
      var histListText = el("detections-history-list").textContent;
      ok(/Nahum 1:7 #59/.test(histRows[0].textContent) && histListText.indexOf("Nahum 1:7 #0") < 0,
         "CON-138 (bounded-memory): the OLDEST entries are the ones dropped, not the newest — the log stays useful under the cap");
      liveBtn.click();

      window.__detResetForTest();
      render(baseView); // restore so the trailing 1s poll stays consistent

      // === listen control: a real state machine — the button never sits silently disabled,
      // and "no transcript" is a diagnosable state, not a dead panel. ===
      var lBtn = el("transcript-listen");
      var lLabel = el("transcript-listen-label");
      var lStatus = el("transcript-status");
      ok(lLabel.textContent.indexOf("Start listening") >= 0 && !lBtn.disabled,
         "listen: idle shows 'Start listening', enabled");
      ok(getComputedStyle(el("transcript-meter")).display === "none",
         "listen: the mic-level meter is hidden when idle (computed display, not just [hidden])");
      lBtn.click(); // start_listening stays pending (model load) — must show progress, not freeze
      ok(lBtn.disabled && lLabel.textContent.indexOf("Preparing") >= 0,
         "listen: clicking Start immediately shows 'Preparing…' (never a silent dead button)");
      window.__emit("stt://progress", { done: 620000000, total: 1600000000, pct: 38 });
      ok(lStatus.textContent.indexOf("38%") >= 0,
         "listen: first-run model-download progress renders (Downloading model… 38%)");
      window.__startCtl.resolve(null); // worker loaded the model + opened the mic
      await sleep(10);
      ok(!lBtn.disabled && lLabel.textContent.indexOf("Stop listening") >= 0,
         "listen: once ready the control flips to 'Stop listening' (enabled)");
      ok(lStatus.textContent.toLowerCase().indexOf("waiting for speech") >= 0,
         "listen: listening but no lines yet -> 'waiting for speech…' (makes empty transcript diagnosable)");
      // A live mic level drives the VISUAL meter (shown only while listening) so a dead/denied
      // microphone (peak 0 while speaking) is visibly distinct from a working mic with recognition
      // pending. role=meter + a numeric % (not colour-only).
      var lMeter = el("transcript-meter");
      var lMeterFill = el("transcript-meter-fill");
      var lMeterVal = el("transcript-meter-val");
      ok(lMeter && getComputedStyle(lMeter).display !== "none" && lMeter.getAttribute("role") === "meter",
         "listen: the mic-level meter (role=meter) is shown while listening");
      window.__emit("stt://level", { pct: 0 });
      ok(lMeter.getAttribute("aria-valuenow") === "0" && lMeterVal.textContent === "0%" && lMeterFill.style.width === "0%",
         "listen: mic level 0 sets the meter to 0% (isolates a dead/denied microphone)");
      window.__emit("stt://level", { pct: 42 });
      ok(lMeter.getAttribute("aria-valuenow") === "42" && lMeterVal.textContent === "42%" && lMeterFill.style.width === "42%",
         "listen: a live mic level fills the meter to 42% (audio arriving; recognition downstream)");
      // Sustained 0% (denied mic) turns into an actionable permission hint, not an endless wait.
      var lSub = el("transcript-empty-sub");
      for (var z = 0; z < 14; z++) window.__emit("stt://level", { pct: 0 });
      ok(lSub.textContent.indexOf("Privacy & Security") >= 0 && lSub.textContent.indexOf("Microphone") >= 0,
         "listen: a run of 0% surfaces the 'grant mic access' hint (actionable, not a dead 0%)");
      render(Object.assign({}, baseView, { transcript: [{ id: 77, text: "and it came to pass", start_ms: 1000 }] }));
      ok(lStatus.textContent.toLowerCase().indexOf("transcribing") >= 0,
         "listen: once a line is recognised, status shows 'transcribing on-device'");
      lBtn.click(); await sleep(5); // Stop -> idle
      lBtn.click();                 // Start again -> preparing/pending
      window.__startCtl.reject({ message: "This build does not include on-device speech-to-text." });
      await sleep(10);
      ok(!lBtn.disabled && lStatus.textContent.indexOf("does not include on-device") >= 0,
         "listen: a start failure surfaces the reason and re-enables the button (no silent no-op)");
      render(baseView); // restore the view for the trailing poll

      // (The Theme-Designer's MAX_ELEMENTS=64 cap is enforced + tested host-side in Rust —
      // engine/present tests — so it is not re-asserted here as a tautology.)

      // === per-screen PREVIEW (86ajq321k): only Audience + Stage are built in now, so ADD the
      // two secondary Audience feeds on demand; then all three previews render + differ ===
      document.querySelector('.nav-item[data-surface="screens"]').click();
      var rowFor = function(id){ return document.querySelector('#screens-list .screen-row[data-screen="'+id+'"]'); };
      var addFeed = function(role){
        document.getElementById("screen-add-role").value = role;
        document.getElementById("screen-add-btn").click();
      };
      addFeed("lower-third");
      await waitFor(function(){ return !!rowFor("lower-third"); });
      addFeed("stream");
      await waitFor(function(){ return !!rowFor("stream"); });
      await waitFor(function(){
        var cs = document.querySelectorAll('#screens-list canvas.screen-preview');
        return cs.length >= 3 && Array.from(cs).every(function(c){ return c.classList.contains("has-render"); });
      });
      var previews = document.querySelectorAll('#screens-list canvas.screen-preview');
      ok(previews.length === 3, "per-screen: 3 preview canvases render (main + added lower-third/stream, got " + previews.length + ")");
      var byScreen = {};
      Array.from(previews).forEach(function(c){ byScreen[c.dataset.screen] = c; });
      ok(!!byScreen["main"] && !!byScreen["lower-third"] && !!byScreen["stream"],
         "per-screen: a preview canvas for each of main / lower-third / stream");
      var pixel = function(c){ return Array.from(c.getContext("2d").getImageData(0,0,1,1).data).join(","); };
      ok(pixel(byScreen["main"]) === "255,0,0,255", "per-screen: main preview shows its own themed frame (red)");
      ok(pixel(byScreen["main"]) !== pixel(byScreen["lower-third"]) &&
         pixel(byScreen["lower-third"]) !== pixel(byScreen["stream"]),
         "per-screen: the three screens render DIFFERENT designs at once");

      // === Screens page — dynamic registry: only Audience + Stage are built in; the added
      // feeds are deletable virtuals ===
      ok(!!rowFor("main") && !!rowFor("stage"),
         "registry: the two built-in outputs render (Audience main + Stage)");
      ok(!rowFor("main").querySelector('.screen-delete') && !rowFor("stage").querySelector('.screen-delete'),
         "registry: a built-in output has an enable toggle but NO delete control");
      ok(!!rowFor("lower-third").querySelector('.screen-delete') && !!rowFor("stream").querySelector('.screen-delete'),
         "registry: an ADDED virtual feed HAS a delete control (unlike a built-in)");
      ok(window.__calls.some(function(c){ return c.cmd === "add_screen" && c.args.role === "stream"; }),
         "registry: '+ Add virtual output' invoked add_screen with role=stream");

      // Disabling a screen invokes set_screen_enabled(false) and dims the row.
      var beforeToggle = window.__calls.length;
      rowFor("lower-third").querySelector('.screen-enable-toggle').click();
      await waitFor(function(){ var r = rowFor("lower-third"); return r && r.classList.contains("screen-disabled"); });
      var disableCall = window.__calls.slice(beforeToggle).filter(function(c){ return c.cmd === "set_screen_enabled"; })[0];
      ok(disableCall && disableCall.args.screen === "lower-third" && disableCall.args.enabled === false,
         "registry: toggling a screen invokes set_screen_enabled(enabled=false)");
      ok(rowFor("lower-third").classList.contains("screen-disabled"),
         "registry: a disabled screen row is dimmed");

      // A SECOND stream feed mints stream-2 (the bare `stream` id is taken); delete it.
      addFeed("stream");
      await waitFor(function(){ return !!rowFor("stream-2"); });
      ok(!!rowFor("stream-2") && !!rowFor("stream-2").querySelector('.screen-delete'),
         "registry: a second stream feed mints stream-2 with a delete control");
      rowFor("stream-2").querySelector('.screen-delete').click();
      await waitFor(function(){ return !rowFor("stream-2"); });
      ok(!rowFor("stream-2"), "registry: deleting a virtual screen removes its row");
      ok(window.__calls.some(function(c){ return c.cmd === "remove_screen" && c.args.screen === "stream-2"; }),
         "registry: remove_screen invoked for the virtual screen");

      // A REJECTED enable-toggle (RBAC-denied / older host) must revert to authoritative,
      // never leave the checkbox lying (review HIGH fix).
      window.__rejectSetEnabled = true;
      var streamCb = rowFor("stream").querySelector('.screen-enable-toggle');
      var wasChecked = streamCb.checked; // true (enabled)
      streamCb.click(); // attempt to disable — the stub rejects
      await new Promise(function(r){ setTimeout(r, 80); });
      var streamRow = rowFor("stream");
      ok(streamRow.querySelector('.screen-enable-toggle').checked === wasChecked &&
         !streamRow.classList.contains("screen-disabled"),
         "registry: a REJECTED enable-toggle reverts to authoritative (no permanent desync)");
      window.__rejectSetEnabled = false;

      // Keyboard focus survives the destructive rebuild (a11y fix): focus a toggle, activate
      // it, and focus is restored to the rebuilt equivalent control.
      var mainCb = rowFor("main").querySelector('.screen-enable-toggle');
      mainCb.focus();
      mainCb.click(); // disable main (succeeds) → full rebuild
      await waitFor(function(){ var r = rowFor("main"); return r && r.classList.contains("screen-disabled"); });
      var active = document.activeElement;
      ok(active && active.classList.contains("screen-enable-toggle") &&
         active.closest('.screen-row') && active.closest('.screen-row').dataset.screen === "main",
         "registry: keyboard focus is restored to the toggle after the rebuild (a11y)");

      // === WINDOW SEMANTICS: for the two BUILT-IN screens (main/stage) the `enabled` flag means
      // THE OS OUTPUT WINDOW EXISTS — toggling off destroys the window, toggling on re-creates
      // it, and the window's own close button performs the identical action. The page must
      // therefore read "closed", never "muted"/"live". A VIRTUAL feed (lower-third/stream) has
      // NO window: its flag still gates NDI only, so window language must never leak onto it. ===
      var pillOf = function(id){ var p = rowFor(id).querySelector(".scr-pill"); return p ? p.textContent : ""; };
      var metaOf = function(id){ var m = rowFor(id).querySelector(".scr-card-meta"); return m ? m.textContent : ""; };
      var ariaOf = function(id){ return rowFor(id).querySelector(".screen-enable-toggle").getAttribute("aria-label") || ""; };
      // `main` is disabled by the focus check above, so it is the closed built-in here.
      ok(/CLOSED/.test(pillOf("main")),
         "window: a disabled BUILT-IN screen reads CLOSED (pill=" + pillOf("main") + ")");
      ok(!/MUTED/.test(pillOf("main")) && !/LIVE/.test(pillOf("main")) && !/CONNECTED/.test(pillOf("main")),
         "window: a closed built-in never claims LIVE/CONNECTED/MUTED (pill=" + pillOf("main") + ")");
      ok(/No output window/.test(metaOf("main")),
         "window: a closed built-in's meta line reports NO output window (meta=" + metaOf("main") + ")");
      // KNOWN TRAP in this webview: a class `display` rule defeats the `hidden` attribute, so a
      // node can be in the DOM and still unpainted. Assert COMPUTED DISPLAY + a real box, not
      // mere presence — otherwise "the pill says CLOSED" could pass while nobody can see it.
      var closedPill = rowFor("main").querySelector(".scr-pill");
      ok(getComputedStyle(closedPill).display !== "none" && closedPill.getClientRects().length > 0,
         "window: the CLOSED pill is actually PAINTED (computed display=" + getComputedStyle(closedPill).display + ")");
      ok(/^Open the .+ output window$/.test(ariaOf("main")),
         "window: a closed built-in's switch announces it will OPEN the output window (aria=" + ariaOf("main") + ")");
      ok(/^Close the .+ output window$/.test(ariaOf("stage")),
         "window: an open built-in's switch announces it will CLOSE the output window (aria=" + ariaOf("stage") + ")");
      // The switch stays a real, labelled, keyboard-operable checkbox (accessible switch intact).
      var mainSwitch = rowFor("main").querySelector(".screen-enable-toggle");
      ok(mainSwitch.tagName === "INPUT" && mainSwitch.type === "checkbox" && !mainSwitch.disabled
         && mainSwitch.checked === false,
         "window: the enable control is still a labelled, operable checkbox reflecting the closed state");
      // DIMMING IS SCOPED TO THE PREVIEW THUMBNAIL. A closed card is the only route back to an
      // open output window, so its controls must stay fully legible; at the old whole-card
      // opacity 0.5 the meta line measured 1.80:1 and the CLOSED pill 2.78:1, both under AA.
      // Assert EFFECTIVE opacity — the product of every ancestor's own opacity up to the list.
      // Reading computed opacity on the control ALONE would be a tautology: the old rule put
      // 0.5 on the CARD, so a control's own computed value was "1" before and after the fix.
      var listEl = document.getElementById("screens-list");
      var effOpacity = function(node){
        var v = 1;
        for (var n = node; n && n !== listEl; n = n.parentElement) {
          var o = parseFloat(getComputedStyle(n).opacity);
          if (!isNaN(o)) v *= o;
        }
        return v;
      };
      var closedCard = rowFor("main");
      // NB: measure the VISIBLE switch (.scr-toggle wrapper + .scr-toggle-knob). The <input>
      // itself is deliberately opacity:0 — it is the invisible hit target, and the knob draws
      // the switch — so asserting on the input would always read 0 and mean nothing.
      var knobEff = effOpacity(closedCard.querySelector(".scr-toggle-knob"));
      var pillEff = effOpacity(closedCard.querySelector(".scr-pill"));
      var thumbEff = effOpacity(closedCard.querySelector(".scr-thumb"));
      ok(knobEff === 1 && effOpacity(closedCard.querySelector(".scr-card-enable")) === 1,
         "dimming: the enable switch on a CLOSED card renders at FULL opacity (eff=" + knobEff + ")");
      ok(pillEff === 1,
         "dimming: the CLOSED pill renders at FULL opacity (eff=" + pillEff + ")");
      ok(effOpacity(closedCard.querySelector(".scr-card-name")) === 1
         && effOpacity(closedCard.querySelector(".scr-card-meta")) === 1,
         "dimming: the card name and meta line on a CLOSED card render at FULL opacity");
      ok(thumbEff === 0.5,
         "dimming: the PREVIEW THUMBNAIL is the ONLY dimmed part of a closed card (eff=" + thumbEff + ")");
      // A VIRTUAL feed: NDI-gating wording only, no window language anywhere.
      ok(/MUTED/.test(pillOf("lower-third")) && !/CLOSED/.test(pillOf("lower-third")),
         "window: a disabled VIRTUAL feed stays MUTED — it has no window to close (pill=" + pillOf("lower-third") + ")");
      ok(/COMPOSED/.test(pillOf("stream")),
         "window: an enabled virtual feed still reads COMPOSED (pill=" + pillOf("stream") + ")");
      ok(!/window/i.test(ariaOf("lower-third")) && !/window/i.test(ariaOf("stream")),
         "window: a virtual feed's switch never mentions an output window (aria=" + ariaOf("lower-third") + ")");
      ok(!/window/i.test(metaOf("lower-third")),
         "window: a virtual feed's meta line never mentions an output window (meta=" + metaOf("lower-third") + ")");

      // === CLOSE-BUTTON PATH: closing the output window with its own OS close button changes
      // `enabled` on the HOST with no operator interaction in this webview. Mutate the host view
      // directly (NO click anywhere) and let the app's own 1 s poll deliver it. ===
      var stageCb = function(){ return rowFor("stage").querySelector(".screen-enable-toggle"); };
      ok(stageCb().checked === true, "close-button: the stage switch starts ON (window open)");
      var enabledCalls = function(){
        return window.__calls.filter(function(c){ return c.cmd === "set_screen_enabled"; }).length;
      };
      var callsBeforeClose = enabledCalls();
      V.screens.forEach(function(s){ if (s.screen === "stage") s.enabled = false; });
      await waitFor(function(){ return stageCb() && stageCb().checked === false; }, 120); // 2.4s > the 1s poll
      ok(stageCb().checked === false,
         "close-button: an externally-closed window flips the switch OFF with NO operator interaction");
      ok(/CLOSED/.test(pillOf("stage")),
         "close-button: the externally-closed screen's pill becomes CLOSED (pill=" + pillOf("stage") + ")");
      ok(enabledCalls() === callsBeforeClose,
         "close-button: the page REFLECTED the close without echoing a set_screen_enabled back at the host");

      // === DEFERRED REBUILD: a focused <select> defers the grid rebuild so an open picker is
      // never yanked away. That deferral must NOT also freeze the enable switch — a <select> can
      // hold focus indefinitely, and `enabled` now changes with no operator input. Driven on
      // `main` in the OPEN direction (it is still closed from the checks above), which also
      // keeps this block to ONE poll of virtual time.
      var mainCb = function(){ return rowFor("main").querySelector(".screen-enable-toggle"); };
      ok(mainCb().checked === false, "deferred: main starts CLOSED before the deferral test");
      var inspSel = document.getElementById("screens-inspector").querySelector("select");
      inspSel.focus();
      var selOptionCount = inspSel.options.length;
      ok(!!inspSel && document.activeElement === inspSel,
         "deferred: an inspector <select> holds focus (the grid rebuild is now deferred)");
      V.screens.forEach(function(s){ if (s.screen === "main") s.enabled = true; });
      await waitFor(function(){ return mainCb() && mainCb().checked === true; }, 120);
      ok(mainCb().checked === true,
         "deferred: an externally-reopened window STILL flips the switch ON while a <select> holds focus");
      ok(!/CLOSED/.test(pillOf("main")),
         "deferred: the status pill reconciles in place too (pill=" + pillOf("main") + ")");
      ok(!rowFor("main").classList.contains("screen-disabled"),
         "deferred: the reopened card is un-dimmed by the in-place reconcile");
      ok(!/No output window/.test(metaOf("main")),
         "deferred: the meta line reconciles in place too (meta=" + metaOf("main") + ")");
      ok(document.activeElement === inspSel && inspSel.isConnected && inspSel.options.length === selOptionCount,
         "deferred: the open <select> is NOT destroyed by the reconcile (still focused, options intact)");
      // The revert must read the RECONCILED authoritative value, not this card's stale
      // render-pass closure: the card was reconciled IN PLACE (never rebuilt) and its closure
      // still holds enabled=false, so a closure read would snap the switch back OFF and deny a
      // window that is open. Read `checked` back SYNCHRONOUSLY — the onchange revert runs during
      // the click, before any deferred rebuild.
      window.__rejectSetEnabled = true;
      mainCb().click(); // attempt to close the reopened window — the stub rejects it
      var revertedTo = mainCb().checked;
      ok(revertedTo === true,
         "deferred: a REJECTED toggle reverts to the RECONCILED value, not the stale closure (got " + revertedTo + ")");
      window.__rejectSetEnabled = false;
      // Release the picker: the deferral lasts exactly as long as the <select> holds focus, and
      // a programmatic .click() does NOT move focus — so without this blur every later
      // renderOutputs would keep deferring and no new card would ever appear.
      inspSel.blur();
      await waitFor(function(){ return document.querySelectorAll('#screens-list .screen-row').length === 4
                                    && document.activeElement !== inspSel; });
      ok(mainCb().checked === true && !rowFor("main").classList.contains("screen-disabled"),
         "deferred: the full rebuild resumes once the <select> releases focus");

      // === Output cap: '+ Add virtual output' disables at the 8-output maximum (MAX_SCREENS) ===
      var addBtnCap = document.getElementById("screen-add-btn");
      var addRoleCap = document.getElementById("screen-add-role");
      var rowCount = function(){ return document.querySelectorAll('#screens-list .screen-row').length; };
      // Fill to the cap with virtual stream feeds (the registry currently holds 4 outputs).
      var capGuard = 0;
      while (rowCount() < 8 && !addBtnCap.disabled && capGuard++ < 12) {
        addFeed("stream");
        await new Promise(function(r){ setTimeout(r, 40); });
      }
      ok(rowCount() === 8, "cap: the registry fills to the 8-output maximum (got " + rowCount() + ")");
      ok(addBtnCap.disabled && addRoleCap.disabled,
         "cap: '+ Add virtual output' + role picker are DISABLED at the 8-output maximum");
      ok(/aximum of 8/.test(addBtnCap.getAttribute("aria-label") || ""),
         "cap: the disabled add affordance announces the 8-output maximum (a11y)");
      // Deleting a virtual output drops below the cap and re-enables the affordance.
      var lastV = Array.from(document.querySelectorAll('#screens-list .screen-row'))
        .map(function(r){ return r.dataset.screen; })
        .filter(function(id){ return /^stream-/.test(id); }).pop();
      rowFor(lastV).querySelector('.screen-delete').click();
      await waitFor(function(){ return !addBtnCap.disabled; });
      ok(!addBtnCap.disabled && !addRoleCap.disabled,
         "cap: deleting an output re-enables '+ Add virtual output' below the cap");

      // === Design 2.0 INSPECTOR: the per-output config controls drive the new backend
      // commands (orientation / scaling / mirror / delay / frame-rate / safe-area / layers). ===
      var insp = document.getElementById("screens-inspector");
      ok(!!insp && /DISPLAY/.test(insp.textContent) && /APPEARANCE/.test(insp.textContent)
         && /VISIBLE LAYERS/.test(insp.textContent) && /TIMING/.test(insp.textContent)
         && /DEVICE/.test(insp.textContent),
         "inspector: the selected output shows DISPLAY / APPEARANCE / VISIBLE LAYERS / TIMING / DEVICE");
      // The connected pill reflects the assigned physical outputs (honest count).
      ok(/connected/.test((document.getElementById("screens-conn")||{}).textContent||""),
         "inspector: the topbar shows an honest '<n> connected' pill");
      var setSel = function(aria, val){
        var s = insp.querySelector('select[aria-label="'+aria+'"]');
        s.value = String(val); s.dispatchEvent(new Event("change"));
      };
      var togInsp = function(aria){ insp.querySelector('input[aria-label="'+aria+'"]').click(); };
      var lastCall = function(cmd){
        var m = window.__calls.filter(function(c){ return c.cmd === cmd; }); return m[m.length-1];
      };
      setSel("Target frame rate for main", 30);
      ok((lastCall("set_output_frame_rate")||{}).args && lastCall("set_output_frame_rate").args.fps === 30
         && lastCall("set_output_frame_rate").args.screen === "main",
         "inspector: Frame rate → set_output_frame_rate(fps=30)");
      setSel("Orientation for main", 1);
      ok((lastCall("set_output_orientation")||{}).args && lastCall("set_output_orientation").args.quarterTurns === 1,
         "inspector: Orientation → set_output_orientation(quarterTurns=1)");
      setSel("Scaling and fit for main", "fit");
      ok((lastCall("set_output_scale_fit")||{}).args && lastCall("set_output_scale_fit").args.fit === "fit",
         "inspector: Scaling/fit → set_output_scale_fit(fit=fit)");
      setSel("Output delay for main", 40);
      ok((lastCall("set_output_delay")||{}).args && lastCall("set_output_delay").args.ms === 40,
         "inspector: Output delay → set_output_delay(ms=40)");
      togInsp("Mirror main horizontally");
      ok((lastCall("set_output_mirror")||{}).args && lastCall("set_output_mirror").args.on === true,
         "inspector: Mirror → set_output_mirror(on=true)");
      togInsp("Show safe-area guides on the operator preview for main");
      ok((lastCall("set_output_safe_area")||{}).args && lastCall("set_output_safe_area").args.on === true,
         "inspector: Safe-area guides → set_output_safe_area(on=true)");
      togInsp("Lower third layer on main");
      ok((lastCall("set_screen_layer_visible")||{}).args
         && lastCall("set_screen_layer_visible").args.layer === "lower-third"
         && lastCall("set_screen_layer_visible").args.visible === false,
         "inspector: a VISIBLE LAYERS toggle → set_screen_layer_visible(layer, visible=false)");

      // === NDI OUTPUT: an audience feed can be set up as an NDI source (name + broadcast). ===
      var streamCard = rowFor("stream");
      Array.from(streamCard.querySelectorAll("button")).filter(function(b){ return b.textContent === "Configure"; })[0].click();
      await waitFor(function(){ return /NDI OUTPUT/.test(document.getElementById("screens-inspector").textContent); });
      var insp2 = document.getElementById("screens-inspector");
      ok(/NDI OUTPUT/.test(insp2.textContent), "inspector: an audience feed shows an NDI OUTPUT section");
      var ndiName = insp2.querySelector('input[aria-label="NDI source name for stream"]');
      ok(!!ndiName, "inspector: NDI section has a source-name input");
      // Cody's PR #85 review, finding 5 — the signal line now carries active validation
      // feedback (CON-156/157/158), not just a passive status, so it needs an announced live
      // region or a refusal is silent to screen-reader users.
      ok(insp2.querySelector(".scr-signal").getAttribute("role") === "status",
         "inspector: the NDI signal/status line is role=status, so a refusal is announced, not just shown");
      ndiName.value = "Test NDI"; ndiName.dispatchEvent(new Event("change"));
      insp2.querySelector('input[aria-label="Broadcast stream as an NDI source"]').click();
      ok(window.__calls.some(function(c){
           return c.cmd === "set_ndi_output" && c.args.screen === "stream"
             && c.args.name === "Test NDI" && c.args.enabled === true;
         }),
         "inspector: NDI name + broadcast toggle → set_ndi_output(screen=stream, name, enabled=true)");
      await waitFor(function(){ return /Broadcasting NDI · Test NDI/.test(insp2.textContent); });
      ok(/Broadcasting NDI · Test NDI/.test(insp2.textContent),
         "inspector: stream settles into the confirmed broadcasting state (the mock now really persists it, like set_screen_enabled does)");

      // === CON-156/157/158 (Frame F states 4/5/6, node 462:194) — NDI rejection/unavailable
      // messages. Previously a rejected enable reverted the toggle with NO explanation at all;
      // these assert the exact Figma-spec copy now renders, driven by the SAME rule the host
      // itself enforces (LiveController::set_ndi_output), not a guess at it. ===
      var mainCard = rowFor("main");
      Array.from(mainCard.querySelectorAll("button")).filter(function(b){ return b.textContent === "Configure"; })[0].click();
      await waitFor(function(){ return /NDI OUTPUT/.test(document.getElementById("screens-inspector").textContent); });
      var insp3 = document.getElementById("screens-inspector");
      var mainNdiName = insp3.querySelector('input[aria-label="NDI source name for main"]');
      var mainNdiToggle = insp3.querySelector('input[aria-label="Broadcast main as an NDI source"]');
      ok(!!mainNdiName && mainNdiName.value === "", "inspector: main's NDI source name starts empty");

      // CON-156 — enabling with an empty name is refused CLIENT-SIDE: no round trip at all
      // (the host would refuse it too, so nothing is lost by not asking), and the exact
      // Figma-spec message renders instead of a silent revert.
      var callsBeforeEmpty = window.__calls.length;
      mainNdiToggle.click();
      ok(window.__calls.length === callsBeforeEmpty,
         "CON-156: enabling NDI with an empty name fires NO set_ndi_output round trip (refused client-side)");
      ok(/Enter a source name before enabling NDI/.test(insp3.querySelector(".scr-signal").textContent),
         "CON-156: the exact Figma-spec rejection message renders — 'Enter a source name before enabling NDI'");
      ok(!mainNdiToggle.checked, "CON-156 (control): the toggle never shows checked for a refused enable");

      // Cody's PR #85 review, finding 1 — a non-empty but INVALID name (e.g. pasted with a
      // stray control character) must be refused client-side too, mirroring ndi_name_valid
      // exactly (LiveController, controller.rs) — not just the empty-name and duplicate-name
      // rules. maxLength=64 stops most of this at the keyboard, never a paste.
      mainNdiName.value = "BadName"; mainNdiName.dispatchEvent(new Event("change"));
      var callsBeforeInvalid = window.__calls.length;
      mainNdiToggle.click();
      ok(window.__calls.length === callsBeforeInvalid,
         "CON-156 (control-char): a name with a control character fires NO set_ndi_output round trip (refused client-side)");
      ok(insp3.querySelector(".scr-signal").textContent.indexOf("isn't valid") >= 0,
         "CON-156 (control-char): an invalid name shows an explanation instead of a silent revert");
      ok(!mainNdiToggle.checked, "CON-156 (control-char, control): the toggle never shows checked for a refused enable");

      // CON-157 — enabling with a name ANOTHER already-enabled screen is broadcasting is
      // refused CLIENT-SIDE too, naming the real conflict (stream is genuinely broadcasting
      // "Test NDI" from the check above — not a fabricated example).
      mainNdiName.value = "Test NDI"; mainNdiName.dispatchEvent(new Event("change"));
      var callsBeforeDup = window.__calls.length;
      mainNdiToggle.click();
      ok(window.__calls.length === callsBeforeDup,
         "CON-157: enabling with an already-claimed name fires NO set_ndi_output round trip (refused client-side)");
      ok(insp3.querySelector(".scr-signal").textContent.indexOf('"Test NDI" is already broadcasting on another output') >= 0,
         "CON-157: the exact Figma-spec rejection message renders, naming the real conflicting source");
      ok(mainNdiName.classList.contains("mismatch"),
         "CON-157: the source-name field gets the same warn/mismatch border .scr-select.mismatch already uses");

      // CON-157 (control) — the refusal is name-specific, not a blanket block: a genuinely
      // unique name commits normally.
      mainNdiName.value = "Main Feed"; mainNdiName.dispatchEvent(new Event("change"));
      mainNdiToggle.click();
      ok(window.__calls.some(function(c){
           return c.cmd === "set_ndi_output" && c.args.screen === "main"
             && c.args.name === "Main Feed" && c.args.enabled === true;
         }),
         "CON-157 (control): a genuinely unique name commits normally — the refusal targets the conflict, not NDI as a whole");
      ok(!mainNdiName.classList.contains("mismatch"),
         "CON-157 (control): the mismatch border clears once the name no longer conflicts");

      // CON-158 (blocker) — the connected host reports it cannot transmit NDI at all
      // (view.ndi_available === false, e.g. selahcue-desktop built without --features ndi).
      // The control must be disabled outright and say why, never silently offer a broken
      // toggle; the section's own copy stays fully legible (CON-160 precedent — dim/disable
      // the control, never the explanation).
      V.ndi_available = false;
      await waitFor(function(){ return /NDI runtime unavailable/.test(document.getElementById("screens-inspector").textContent); });
      var insp4 = document.getElementById("screens-inspector");
      ok(insp4.textContent.indexOf("NDI runtime unavailable — build with the ndi feature to broadcast") >= 0,
         "CON-158: the exact Figma-spec message renders when the host reports NDI unavailable");
      ok(insp4.querySelector('input[aria-label="Broadcast main as an NDI source"]').disabled,
         "CON-158: the broadcast toggle is disabled outright when this build cannot transmit NDI");
      ok(insp4.querySelector('input[aria-label="NDI source name for main"]').disabled,
         "CON-158: the source-name field is disabled too — nothing to type toward a control that cannot work");
      var ndiSectionTitle = Array.from(insp4.querySelectorAll(".scr-isection-title"))
        .filter(function(t){ return t.textContent === "NDI OUTPUT"; })[0];
      ok(!!ndiSectionTitle && getComputedStyle(ndiSectionTitle).opacity === "1",
         "CON-158 (CON-160 precedent): the section's own title stays at full legibility — only the CONTROLS are disabled, never the explanation");

      // CON-158 (control) — an ABSENT report (unknown: Local/demo, or an older host) must
      // never render as unavailable. Restores the fixture for every check after this one.
      V.ndi_available = null;
      await waitFor(function(){
        var i = document.getElementById("screens-inspector");
        return i && i.textContent.indexOf("NDI runtime unavailable") < 0;
      });
      var insp5 = document.getElementById("screens-inspector");
      ok(!insp5.querySelector('input[aria-label="Broadcast main as an NDI source"]').disabled,
         "CON-158 (control): ndi_available reverting to unknown (null) re-enables the control — absent must never render as unavailable");

      // Restore: the set_ndi_output mock above (CON-156/157/158) is a REAL mutation, unlike the
      // rest of this file's earlier no-op stub for it, so "stream" and "main" are genuinely left
      // broadcasting at this point. Reset both, so that state does not leak into a later fixture
      // that assumes no screen is on the air — in particular Pre-service Check's own NDI
      // readiness probe (preservice.js:96-106), which reads view.screens[].config for real and
      // would otherwise start reporting NDI "ok" instead of "off" purely as a side effect of an
      // earlier, unrelated check.
      V.screens.forEach(function(s){ if (s.config) { s.config.ndi_enabled = false; s.config.ndi_name = ""; } });

      // === Presentation & Media surface (Design 2.0, node 329:124) ===
      var pmNav = document.querySelector('.nav-item[data-surface="presentation"]');
      ok(!!pmNav && pmNav.getAttribute("aria-disabled") !== "true", "PM: the Presentation nav item is ACTIVATED (not a disabled 'later' affordance)");
      ok(pmNav && !pmNav.dataset.nodigit && pmNav.querySelector(".nav-key").textContent === "⌘2", "PM: the Presentation item carries ⌘2 (menu-order digit)");
      pmNav.click();
      ok(el("surface-presentation").classList.contains("active"), "PM: clicking the nav item activates #surface-presentation");
      // --- Track B: browse/present/edit flow (story 86ajxeq17) ---
      // Nav lands on the LIBRARY (not the editor); grid + editor are hidden.
      ok(!el("pm-library").hidden && getComputedStyle(el("pm-library")).display !== "none", "PM/B: presentation nav lands on the Library (visible)");
      ok(el("pm-grid").hidden, "PM/B: the slide grid is hidden until a presentation is opened");
      ok(getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display === "none", "PM/B: the editor body is hidden on the Library");
      // Deck-open FAILURE stays on the Library (never a blank grid).
      await waitFor(function(){ return el("pm-lib-grid").querySelector(".pm-lib-open"); });
      window.__pmRejectOnce = true;
      el("pm-lib-grid").querySelector(".pm-lib-open").click();
      await waitFor(function(){ return !el("pm-error").hidden; });
      ok(el("pm-grid").hidden && !el("pm-library").hidden, "PM/B3: a failed deck_open stays on the Library (no blank grid)");
      ok(!el("pm-error").hidden, "PM/B3: a failed deck_open surfaces an error");
      if (el("pm-error-dismiss")) el("pm-error-dismiss").click();
      // Open a presentation card → the slide GRID.
      el("pm-lib-grid").querySelector(".pm-lib-open").click();
      await waitFor(function(){ return !el("pm-grid").hidden && el("pm-grid-tiles").querySelectorAll(".pm-tile").length > 0; });
      ok(!el("pm-grid").hidden, "PM/B: opening a presentation shows the slide GRID");
      ok(el("pm-library").hidden, "PM/B: the Library is hidden in grid mode");
      var pmTiles = el("pm-grid-tiles").querySelectorAll(".pm-tile");
      ok(pmTiles.length === 2, "PM/B: the grid renders one tile per slide (" + pmTiles.length + ")");
      // The 'no slides yet' empty-state must be TRULY hidden when the deck HAS slides. The box
      // carries an author `display: grid`, which defeats the UA `[hidden]{display:none}` in
      // WKWebView unless a `.pm-grid-empty[hidden]{display:none}` guard wins — assert the
      // COMPUTED display, not just the attribute (a stale empty-state otherwise overlays a
      // populated deck; cf. the .td-ctx/.pm-transport guards).
      ok(el("pm-grid-empty").hidden && getComputedStyle(el("pm-grid-empty")).display === "none",
         "PM/B: the 'no slides yet' empty-state is truly hidden when the deck HAS slides (computed display, not just [hidden])");
      ok(getComputedStyle(el("pm-grid-tiles")).display !== "none",
         "PM/B: the slide-tiles grid is visible when the deck HAS slides");
      ok(window.__calls.some(function(c){ return c.cmd === "render_deck_slide"; }), "PM/B: grid thumbnails compose via render_deck_slide");
      // Single-click SELECTS (safe — no go-live).
      var glBeforeSel = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      pmTiles[0].dispatchEvent(new MouseEvent("click", {bubbles:true}));
      ok(pmTiles[0].classList.contains("sel"), "PM/B: single-click selects a slide (safe cursor ring)");
      ok(!pmTiles[0].classList.contains("live"), "PM/B: single-click does NOT go live");
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length === glBeforeSel, "PM/B: single-click fires no deck_go_live");
      // Double-click PRESENTS live → the red LIVE ring on that tile. (Slide 2 keeps the host
      // selection at 2 so the editor checks below still read 'Slide 2 / 2'.)
      pmTiles[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-grid-tiles").querySelector(".pm-tile.live"); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_go_live"; }), "PM/B: double-click presents the slide live (deck_go_live)");
      ok(el("pm-grid-tiles").querySelector(".pm-tile.live"), "PM/B: the live slide shows the red LIVE ring");
      // --- Slice 2: transport + arrows advance live (deck_go_live_delta) + host-truth ring ---
      await waitFor(function(){ return !el("pm-transport").hidden; });
      ok(!el("pm-transport").hidden, "PM/B2: the transport bar shows once a slide is live");
      ok(el("pm-next").getAttribute("aria-disabled") === "true", "PM/B2: Next is disabled at the last live slide");
      ok(el("pm-prev").getAttribute("aria-disabled") !== "true", "PM/B2: Previous is enabled when not at the first slide");
      // ◀ Previous advances live via deck_go_live_delta(-1) → host-truth ring moves to slide 1.
      el("pm-prev").click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_go_live_delta" && c.args.delta === -1; }); });
      ok(true, "PM/B2: Previous advances live via deck_go_live_delta(-1)");
      await waitFor(function(){ var t = el("pm-grid-tiles").querySelectorAll(".pm-tile")[0]; return t && t.classList.contains("live"); });
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].classList.contains("live"), "PM/B2: host-truth LIVE ring moved to slide 1 (view().live_authored_id)");
      ok(el("pm-next").getAttribute("aria-disabled") !== "true", "PM/B2: Next re-enables after leaving the last slide");
      // A keyboard arrow while LIVE advances live (deck_go_live_delta(+1)) → back to slide 2.
      var deltaBefore = window.__calls.filter(function(c){ return c.cmd === "deck_go_live_delta"; }).length;
      el("pm-grid-tiles").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true}));
      await waitFor(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live_delta"; }).length > deltaBefore; });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_go_live_delta" && c.args.delta === 1; }), "PM/B2: a keyboard arrow while live advances live (deck_go_live_delta(+1))");
      await waitFor(function(){ var t = el("pm-grid-tiles").querySelectorAll(".pm-tile")[1]; return t && t.classList.contains("live"); });
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B2: arrows advance the LIVE ring (now slide 2)");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].tabIndex === 0, "PM/B2: focus/cursor follows live (the live tile is the roving-focus target)");
      // --- Slice 3: §8 states (preview-only, blackout, go-live failure) ---
      // Preview-only honesty: no audience output → a "Preview only" badge, never a false LIVE.
      window.__outputConnected = false;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return !el("pm-grid-badge").hidden; });
      ok(!el("pm-grid-badge").hidden && el("pm-grid-badge").textContent.indexOf("Preview only") >= 0, "PM/B3: no audience output → 'Preview only' badge (honest, not a false LIVE)");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("preview") && !el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B3: preview-only shows a distinct PREVIEW ring, NOT a true red LIVE ring");
      ok(el("pm-tp-live").textContent.indexOf("PREVIEW") >= 0, "PM/B3: the transport reads PREVIEW (not LIVE) with no audience output");
      window.__outputConnected = true;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-grid-badge").hidden; });
      ok(el("pm-grid-badge").hidden, "PM/B3: the badge clears once the audience output is connected");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B3: reconnecting restores the true red LIVE ring");
      // Blackout is shown IN WORDS on the transport (never an ambiguous blank).
      V.blackout = true;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-tp-live").textContent.indexOf("BLACKED OUT") >= 0; });
      ok(el("pm-tp-live").textContent.indexOf("BLACKED OUT") >= 0, "PM/B3: blackout is shown in words on the transport");
      V.blackout = false;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-tp-live").textContent.indexOf("● LIVE") >= 0; });
      ok(el("pm-tp-live").textContent.indexOf("● LIVE") >= 0, "PM/B3: the transport returns to '● LIVE' when blackout clears");
      // Go-live FAILURE: a rejected present surfaces the error banner; the LIVE ring stays put.
      window.__pmRejectOnce = true;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return !el("pm-error").hidden; });
      ok(!el("pm-error").hidden, "PM/B3: a rejected present surfaces the error banner (role=alert)");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B3: the LIVE ring stays on the prior slide after a failed present (no false ring)");
      if (el("pm-error-dismiss")) el("pm-error-dismiss").click(); // restore for later checks
      // --- Slice 5: a11y (role=listbox, roving tabindex, aria-live, LIVE text label) ---
      ok(el("pm-grid-tiles").getAttribute("role") === "listbox", "PM/B5: the grid is a role=listbox");
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].dispatchEvent(new MouseEvent("click", {bubbles:true}));
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].tabIndex === 0 && el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].tabIndex === -1, "PM/B5: roving tabindex (selected tile 0, others -1)");
      ok(/live/i.test(el("pm-grid-live-region").textContent), "PM/B5: live changes are announced via aria-live");
      var liveLbl = el("pm-grid-tiles").querySelector(".pm-tile.live .pm-tile-live");
      ok(liveLbl && /LIVE/.test(liveLbl.textContent), "PM/B5: the LIVE state carries a text label (WCAG 1.4.1, not colour-only)");
      // Edit ▸ → the authoring editor (so the existing editor checks below run).
      el("pm-grid-edit").click();
      ok(getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display !== "none", "PM/B: Edit ▸ opens the editor");
      ok(el("pm-grid").hidden, "PM/B: the grid is hidden in editor mode");
      // The surface loads its DeckView + composites the slide canvas (native preview, has-render).
      await waitFor(function(){ return el("pm-canvas").classList.contains("has-render"); });
      ok(el("pm-canvas").classList.contains("has-render"), "PM: the slide canvas shows a native composited preview (render_deck_slide → blitFrame)");
      ok(window.__calls.some(function(c){ return c.cmd === "render_deck_slide"; }), "PM: render_deck_slide drives the preview (compositor stays native, not HTML)");
      ok(document.querySelectorAll("#pm-slide-list .pm-slide").length === 2, "PM: the SLIDES list renders one row per deck slide");
      ok(/Slide 2 \/ 2/.test(el("pm-slide-pos").textContent), "PM: the canvas shows 'Slide N / M · 1920×1080'");
      // Preview→Live isolation (FR-012): editing NEVER changes Live; only Present does.
      var liveBefore = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_element"; }); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_add_element" && c.args.kind === "text"; }), "PM: the Text tool adds a text element to the slide");
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length === liveBefore, "PM: editing the slide never goes Live (FR-012 — Live untouched by edits)");

      // === Inspector: selecting/adding an element AUTO-OPENS the right-panel Inspector (design 509:124) ===
      await waitFor(function(){ return !el("pm-inspector-body").hidden; });
      ok(!el("pm-inspector-body").hidden && el("pm-tab-inspector").getAttribute("aria-selected") === "true",
         "PM: adding/selecting an element AUTO-OPENS the Inspector tab");
      ok(!el("pm-inspector-body").contains(document.activeElement),
         "PM: the auto-open does NOT move focus into the Inspector (no focus-steal off the canvas, review #9)");
      ok(el("pm-tab-inspector").getAttribute("aria-disabled") !== "true", "PM: the Inspector tab is enabled when an element is selected");
      ok(/Text element/.test(el("pm-inspector-body").textContent), "PM: the Inspector binds to the selected element (Text element header)");
      // A Text inspector control drives deck_update_element.
      var sizeIn = Array.from(el("pm-inspector-body").querySelectorAll("input[type=number]"))[0];
      sizeIn.value = "120"; sizeIn.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.size_permille === 120; }), "PM: an Inspector control drives deck_update_element (size)");
      var colorIn = el("pm-inspector-body").querySelector("input[type=color]");
      colorIn.value = "#ff8800"; colorIn.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.color && c.args.patch.color.r === 255; }), "PM: the Colour control patches deck_update_element with an {r,g,b,a}");
      var alignBtn = Array.from(el("pm-inspector-body").querySelectorAll("button[aria-label^='Align ']"))[1];
      alignBtn.focus(); alignBtn.click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.align_h === "center"; }), "PM: an Align button patches align_h");
      await sleep(20);
      ok(document.activeElement && document.activeElement.dataset && document.activeElement.dataset.ik === "align-center",
         "PM: focus is RESTORED to the button after its edit re-renders the inspector (WCAG 2.4.3, review #2)");
      // PME-027: left/centre/right previously read "≡"/"≣"/"≡" — left and right shared the same
      // glyph, so an operator could not tell which was pressed without reading aria-pressed.
      var alignBtns = Array.from(el("pm-inspector-body").querySelectorAll("button[aria-label^='Align ']"));
      var alignGlyphs = alignBtns.map(function(b){ return b.textContent; });
      ok(alignBtns.length === 3 && new Set(alignGlyphs).size === 3,
         "PME-027: the three horizontal-align buttons (Left/Centre/Right) all show DISTINCT glyphs (\"" + alignGlyphs.join("\", \"") + "\")");
      // The Layers panel (replacing the old Arrange buttons) lists the slide's elements; Alt+↑ on a
      // layer row raises it in the z-order.
      var layerRow = el("pm-inspector-body").querySelector("#pm-layers .td-layer");
      layerRow.focus(); layerRow.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowUp", altKey:true, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_element_z"; }), "PM: a Layers-panel Alt+↑ raises the element (deck_set_element_z)");
      // Manual tab switch: Media ⟷ Inspector. Assert the COMPUTED display, not just the `.hidden`
      // property — a class `display:flex` can outrank the UA `[hidden]{display:none}` and leave BOTH
      // panels visible while `.hidden` still reads true (the contextual switch must actually hide one).
      var disp = function(id){ return getComputedStyle(el(id)).display; };
      el("pm-tab-media").click();
      ok(!el("pm-media-body").hidden && el("pm-inspector-body").hidden, "PM: the Media tab switches the right panel back to the library");
      ok(disp("pm-media-body") !== "none" && disp("pm-inspector-body") === "none", "PM: on Media, ONLY the media library is rendered (inspector display:none)");
      el("pm-tab-inspector").click();
      ok(!el("pm-inspector-body").hidden, "PM: the Inspector tab switches back to the inspector");
      ok(disp("pm-inspector-body") !== "none" && disp("pm-media-body") === "none", "PM: on Inspector, the media library is NOT rendered (media display:none)");
      // Image inspector + Replace flow.
      document.querySelector('#surface-presentation .pm-tool[data-add="image"]').click();
      await waitFor(function(){ return /Image element/.test(el("pm-inspector-body").textContent); });
      ok(/Image element/.test(el("pm-inspector-body").textContent), "PM: adding an image element opens the Image inspector (source + Replace)");
      var repBtn = Array.from(el("pm-inspector-body").querySelectorAll("button")).filter(function(b){ return /Replace|Relink/.test(b.textContent); })[0];
      repBtn.click();
      ok(!el("pm-replace-hint").hidden && !el("pm-media-body").hidden, "PM: Replace… arms the flow + switches to the media library with a hint");
      var imgCell = document.querySelector('#pm-media-grid .pm-asset:not(.missing) .pm-asset-thumb');
      imgCell.click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_replace_element_image" && c.args.mediaId === 1 && typeof c.args.index === "number"; }), "PM: picking a media image fires deck_replace_element_image({mediaId, index}) — camelCase→snake arg crossing");
      // Deselect → the panel returns to Media.
      await waitFor(function(){ return !el("pm-inspector-body").hidden; }); // replace re-opened the inspector
      document.querySelector('#surface-presentation .pm-mtab[data-filter="all"]').click(); // reset the media filter after the Replace flow
      // Add a slide.
      var slidesBefore = document.querySelectorAll("#pm-slide-list .pm-slide").length;
      el("pm-add-slide").click();
      await waitFor(function(){ return document.querySelectorAll("#pm-slide-list .pm-slide").length > slidesBefore; });
      ok(document.querySelectorAll("#pm-slide-list .pm-slide").length === slidesBefore + 1, "PM: '+ Add slide' adds a slide via deck_add_slide");
      // Deselect (a fresh slide with no selected element) returns the panel to Media (review #8).
      await waitFor(function(){ return !el("pm-media-body").hidden; });
      ok(!el("pm-media-body").hidden && el("pm-inspector-body").hidden, "PM: a slide with no selected element returns the right panel to Media (deselect)");
      // Select the first slide.
      document.querySelector('#pm-slide-list .pm-slide .pm-slide-card').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_select_slide"; }); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_select_slide"; }), "PM: clicking a slide row selects it (deck_select_slide)");
      // Per-slide props: transition + auto-advance + notes.
      el("pm-transition").value = "cut"; el("pm-transition").dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_transition" && c.args.transition === "cut"; }), "PM: the Transition control drives deck_set_transition");
      el("pm-autoadv").value = "8"; el("pm-autoadv").dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_auto_advance" && c.args.secs === 8; }), "PM: Auto-advance drives deck_set_auto_advance(secs)");
      el("pm-notes").value = "pause here"; el("pm-notes").dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_notes" && c.args.notes === "pause here"; }), "PM: the speaker-notes field drives deck_set_notes");
      // Media library: grid + missing/unused footer + filter.
      ok(document.querySelectorAll("#pm-media-grid .pm-asset").length >= 3, "PM: the media library renders image/video asset cells");
      ok(document.querySelector("#pm-media-grid .pm-asset.missing"), "PM: a missing asset shows the missing state");
      ok(document.querySelectorAll("#pm-media-audio .pm-audio-row").length === 1, "PM: audio assets render in the AUDIO list");
      ok(/1 missing/.test(el("pm-media-stats").textContent) && /3 unused/.test(el("pm-media-stats").textContent), "PM: the footer reports 'N missing · M unused' (from media_usage + missing detection)");
      ok(el("pm-media-stats").classList.contains("warn"), "PM: the missing count is styled as a warning");
      document.querySelector('#surface-presentation .pm-mtab[data-filter="image"]').click();
      ok(!Array.from(document.querySelectorAll("#pm-media-grid .pm-asset .pm-asset-meta")).some(function(m){ return /VIDEO/.test(m.textContent); }), "PM: the Images filter hides video assets");
      document.querySelector('#surface-presentation .pm-mtab[data-filter="all"]').click();
      // Undo/redo (buttons + the DeckView's can_undo/redo drive enablement; ≥20 steps supported host-side).
      ok(el("pm-undo") && !el("pm-undo").disabled, "PM: after edits, Undo is enabled (can_undo)");
      el("pm-undo").click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_undo"; }); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_undo"; }), "PM: Undo drives deck_undo");
      // Present is now GRID-owned (double-click / Enter / transport) — the editor's ▶ Present button
      // was relocated (story 86ajxeq17). Grid go-live is covered by the PM/B checks above.
      // Canvas keyboard: add an element (which selects it), then nudge / toggle / raise / remove it.
      document.querySelector('#surface-presentation .pm-tool[data-add="shape"]').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_element" && c.args.kind === "shape"; }); });
      await sleep(20);
      el("pm-canvas").focus();
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"Tab", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_select_element"; }), "PM: Tab on the canvas selects/cycles an element (keyboard selection, WCAG 2.1.1)");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_move_element"; }), "PM: an arrow key nudges the selected element (deck_move_element)");
      // Resize: the selection box has drag handles; Alt+arrows resize by keyboard; a handle drag
      // resizes by pointer. The stub shape is 600×160 ‰ — a grow must report a larger w/h.
      ok(document.querySelectorAll('#pm-sel .pm-h').length === 8, "PM: the selection box has 8 resize handles");
      ok(!!document.querySelector('#pm-sel .pm-h[data-h="se"]') && !!document.querySelector('#pm-sel .pm-h[data-h="w"]'), "PM: handles cover corners + edges (data-h)");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", altKey:true, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_move_element" && c.args.w > 600 && c.args.h === 160; }),
         "PM: Alt+arrow RESIZES the element (width grows, height + origin unchanged — not a move)");
      // Pointer resize: the canvas collapses to 0×0 in headless (no definite layout), so stub its
      // getBoundingClientRect to a known 320×180 box → the SE-handle drag maps to a deterministic
      // per-mille delta (grab 800,590 → move 920,710 ⇒ w 600→720, h 160→280). This exercises the
      // REAL resize path (pointToPermille + the pointermove resize math), not the layout.
      var seH = document.querySelector('#pm-sel .pm-h[data-h="se"]');
      var cnv = el("pm-canvas");
      var origGBCR = cnv.getBoundingClientRect.bind(cnv);
      cnv.getBoundingClientRect = function(){ return {left:0, top:0, width:320, height:180, right:320, bottom:180, x:0, y:0}; };
      var mvBefore = window.__calls.filter(function(c){ return c.cmd === "deck_move_element"; }).length;
      seH.dispatchEvent(new PointerEvent("pointerdown", {clientX: 256, clientY: 106, pointerId: 7, bubbles: true}));
      cnv.dispatchEvent(new PointerEvent("pointermove", {clientX: 294, clientY: 128, pointerId: 7, bubbles: true}));
      cnv.dispatchEvent(new PointerEvent("pointerup", {clientX: 294, clientY: 128, pointerId: 7, bubbles: true}));
      cnv.getBoundingClientRect = origGBCR;
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_move_element"; }).slice(mvBefore).some(function(c){ return c.args.w > 600 && c.args.h > 160; }),
         "PM: dragging the SE handle resizes the element (deck_move_element grows both w and h)");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"h", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_toggle_element_visible"; }), "PM: 'H' toggles the selected element's visibility");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"]", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_element_z"; }), "PM: ']' raises the selected element's z-order");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"Delete", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_remove_element"; }), "PM: Delete removes the selected element");

      // === Inline text editing (double-click) + Layers panel (replaces Arrange) ===
      // A fresh slide with a single text element → deterministic canvas hit-test + layer list.
      el("pm-add-slide").click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_slide"; }); });
      await sleep(20);
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return /Text element/.test(el("pm-inspector-body").textContent); });
      // -- Inline editor: double-click the (visible) text element on the canvas (stub the 0×0
      //    headless canvas rect so the hit-test maps to the element). --
      var cnv2 = el("pm-canvas");
      var origG2 = cnv2.getBoundingClientRect.bind(cnv2);
      cnv2.getBoundingClientRect = function(){ return {left:0, top:0, width:320, height:180, right:320, bottom:180, x:0, y:0}; };
      cnv2.dispatchEvent(new MouseEvent("dblclick", {clientX:160, clientY:92, bubbles:true}));
      ok(!!el("pm-text-edit") && el("pm-text-edit").tagName === "TEXTAREA", "PM: double-clicking a text element opens an inline textarea editor");
      el("pm-text-edit").value = "Edited on canvas";
      el("pm-text-edit").dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", metaKey:true, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_element_text" && c.args.text === "Edited on canvas"; }), "PM: Cmd+Enter commits the edit via deck_set_element_text");
      ok(!el("pm-text-edit"), "PM: committing closes the inline editor");
      await sleep(20);
      cnv2.dispatchEvent(new MouseEvent("dblclick", {clientX:160, clientY:92, bubbles:true}));
      var setN = window.__calls.filter(function(c){ return c.cmd === "deck_set_element_text"; }).length;
      el("pm-text-edit").value = "discarded";
      el("pm-text-edit").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      ok(!el("pm-text-edit") && window.__calls.filter(function(c){ return c.cmd === "deck_set_element_text"; }).length === setN, "PM: Escape cancels the inline edit (editor closes, no commit)");
      cnv2.getBoundingClientRect = origG2;
      await sleep(20);
      // -- Layers panel (mirrors the Theme Designer): lists elements, eye toggles, handle drag reorders. --
      ok(!!el("pm-inspector-body").querySelector("#pm-layers"), "PM: the inspector has a LAYERS panel (replacing Arrange)");
      ok(el("pm-inspector-body").querySelectorAll("#pm-layers .td-layer").length >= 1, "PM: the Layers panel lists the slide's elements front→back");
      var lEye = el("pm-inspector-body").querySelector("#pm-layers .td-layer .td-layer-eye");
      var visN = window.__calls.filter(function(c){ return c.cmd === "deck_toggle_element_visible"; }).length;
      lEye.click();
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_toggle_element_visible"; }).length === visN + 1, "PM: a Layers-row eye toggles element visibility");
      await sleep(20);
      var lh = el("pm-inspector-body").querySelector("#pm-layers .td-layer .td-layer-handle");
      lh.dispatchEvent(new PointerEvent("pointerdown", {clientX:5, clientY:5, button:0, pointerId:9, bubbles:true}));
      window.dispatchEvent(new PointerEvent("pointerup", {clientX:5, clientY:40, pointerId:9, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_reorder_elements" && Array.isArray(c.args.order); }), "PM: dragging a layer handle reorders via deck_reorder_elements(order)");
      // Command palette: Presentation actions are offered while the surface is active.
      window.__cmdPalette.open();
      await sleep(20);
      document.getElementById("cmd-input").value = "Add slide";
      document.getElementById("cmd-input").dispatchEvent(new Event("input"));
      ok(Array.from(document.querySelectorAll("#cmd-list li")).some(function(li){ return /Add slide/.test(li.textContent); }), "PM: the command palette offers 'Add slide' while Presentation is active");
      window.__cmdPalette.closeAll();

      // --- Command palette sections (Design 2.0): ACTIONS / NAVIGATE / SCRIPTURES, with the whole
      //     top-level app menu mirrored under NAVIGATE carrying its ⌘ badges. ---
      window.__cmdPalette.open();
      el("cmd-input").value = ""; el("cmd-input").dispatchEvent(new Event("input"));
      var pGroups = Array.from(document.querySelectorAll("#cmd-list .cmd-group")).map(function(g){ return g.textContent; });
      ok(pGroups.indexOf("ACTIONS") >= 0 && pGroups.indexOf("NAVIGATE") >= 0, "Palette: renders ACTIONS + NAVIGATE section headers");
      ok(document.querySelector("#cmd-list .cmd-item").textContent.indexOf("Go Live") >= 0, "Palette: Go Live is the first ACTIONS item");
      var pItems = Array.from(document.querySelectorAll("#cmd-list .cmd-item")).map(function(li){ return li.textContent; });
      ok(pItems.some(function(t){ return /Go to Presentation/.test(t) && /⌘2/.test(t); }), "Palette: NAVIGATE mirrors 'Go to Presentation' with its ⌘2 badge");
      ok(["Live Console","Presentation","Theme Designer","Screens & Outputs","Service Plan","Transcript & Notes","Settings"].every(function(n){ return pItems.some(function(t){ return t.indexOf("Go to "+n) >= 0; }); }), "Palette: NAVIGATE lists all seven top-level app menu items");
      el("cmd-input").value = "grace"; el("cmd-input").dispatchEvent(new Event("input"));
      ok(Array.from(document.querySelectorAll("#cmd-list .cmd-group")).some(function(g){ return g.textContent === "SCRIPTURES"; }) &&
         Array.from(document.querySelectorAll("#cmd-list .cmd-item")).some(function(li){ return /Search "grace" in Bible/.test(li.textContent); }),
         "Palette: a typed query adds a SCRIPTURES 'Search … in Bible' entry");
      window.__cmdPalette.closeAll();

      // --- Global presentation search (⌘/Ctrl+S) — a dedicated modal over `deck_search` that
      //     searches deck names + slide text and opens the chosen presentation in the editor. ---
      var gsLibSave = window.__LIB; // restore after so the later PM/Lib tests keep their fixture
      window.__LIB = { decks: [{id:71, name:"Grace Sunday", slides:5}, {id:72, name:"Hymns Vol. 2", slides:8}], open:71, persistent:true, nextId:90 };
      var gs = el("gsearch");
      var gsEv = new KeyboardEvent("keydown", {key:"s", metaKey:true, bubbles:true, cancelable:true});
      document.dispatchEvent(gsEv);
      ok(!gs.hidden, "gsearch: ⌘S opens the presentation-search modal");
      ok(gsEv.defaultPrevented, "gsearch: ⌘S prevents the browser save-page default");
      ok(gs.getAttribute("role")==="dialog" && gs.getAttribute("aria-modal")==="true", "gsearch: the modal is a real dialog (aria-modal)");
      var gi = el("gsearch-input");
      ok(document.activeElement === gi, "gsearch: focus lands in the search input on open");
      gi.value = "grace"; gi.dispatchEvent(new Event("input"));
      await sleep(180); // debounce (120ms) + the deck_search promise
      var gRows = document.querySelectorAll("#gsearch-list .gsearch-item");
      ok(gRows.length >= 2, "gsearch: typing a query renders result rows from deck_search");
      ok(Array.from(gRows).some(function(li){ return /Grace Sunday/.test(li.textContent); }), "gsearch: a NAME match renders");
      ok(Array.from(gRows).some(function(li){ var s=li.querySelector(".gsearch-sub"); return s && /slide 4/.test(s.textContent) && /amazing grace/i.test(s.textContent); }),
         "gsearch: a slide-CONTENT match shows the slide number + snippet");
      ok(el("gsearch-list").getAttribute("role") === "listbox" && !!document.querySelector("#gsearch-list .gsearch-item[role='option']"),
         "gsearch: results are a listbox of role=option rows (a11y)");
      // ↓ then Enter opens the selected presentation in the editor (deck_open + surface switch).
      var gOpenBefore = window.__calls.filter(function(c){ return c.cmd === "deck_open"; }).length;
      gi.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowDown", bubbles:true}));
      gi.dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", bubbles:true}));
      await sleep(15);
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_open"; }).length > gOpenBefore, "gsearch: Enter opens the selected presentation (deck_open)");
      ok(el("surface-presentation").classList.contains("active"), "gsearch: opening a result switches to the Presentation surface");
      ok(gs.hidden, "gsearch: selecting a result closes the modal");
      // ⌘S is suppressed while another modal (the palette) is open — one modal at a time.
      window.__cmdPalette.open();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"s", metaKey:true, bubbles:true, cancelable:true}));
      ok(gs.hidden, "gsearch: ⌘S does NOT open the search while the command palette is open");
      window.__cmdPalette.closeAll();
      // Esc closes the search modal.
      window.__gsearch.open();
      ok(!gs.hidden, "gsearch: opens again via the API");
      el("gsearch-input").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      ok(gs.hidden, "gsearch: Esc closes the modal");
      window.__LIB = gsLibSave; // restore the library fixture for the later PM/Lib tests

      // ⌘2 jumps to the Presentation surface from elsewhere (menu-order digit).
      document.querySelector('.nav-item[data-surface="console"]').click();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"2", metaKey:true, bubbles:true}));
      ok(el("surface-presentation").classList.contains("active"), "PM: ⌘2 jumps to the Presentation surface");
      // The Present-ed slide shows a non-colour-only LIVE badge + names 'live' in its aria-label (review #4).
      await waitFor(function(){ return !!document.querySelector("#pm-slide-list .pm-slide.live .pm-slide-live-badge"); });
      var liveCard = document.querySelector("#pm-slide-list .pm-slide.live .pm-slide-card");
      ok(!!document.querySelector("#pm-slide-list .pm-slide.live .pm-slide-live-badge"), "PM: the live slide shows a non-colour-only LIVE badge");
      ok(liveCard && /live/i.test(liveCard.getAttribute("aria-label") || ""), "PM: the live slide names 'live' in its aria-label (not colour-only)");
      // The active media filter reflects aria-pressed (a real toggle-button group, not a fake tablist).
      ok(document.querySelector('#surface-presentation .pm-mtab[aria-pressed="true"]'), "PM: the media filter marks the active button with aria-pressed");

      // === Remaining states: font picker · image Fit · destructive confirms · system states ===

      // --- C-006 Font-family picker (Text inspector, from system_fonts) ---
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return /Text element/.test(el("pm-inspector-body").textContent); });
      await waitFor(function(){ var s = el("pm-inspector-body").querySelector('select[data-ik="font"]'); return s && s.options.length >= 4; });
      var fontSel = el("pm-inspector-body").querySelector('select[data-ik="font"]');
      ok(!!fontSel, "PM: the Text inspector has a Font-family picker (C-006)");
      ok(Array.from(fontSel.options).some(function(o){ return o.value === ""; }) && Array.from(fontSel.options).some(function(o){ return o.value === "Georgia"; }),
         "PM: the Font picker is populated from system_fonts (System default + families)");
      fontSel.value = "Georgia"; fontSel.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.font === "Georgia"; }),
         "PM: choosing a font patches deck_update_element {font}");
      await sleep(20);
      fontSel = el("pm-inspector-body").querySelector('select[data-ik="font"]'); // re-query after the re-render
      fontSel.value = ""; fontSel.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.font === null; }),
         "PM: 'System default' clears the font to null (bundled default)");

      // --- C-008 Image Fit control (Stretch / Fit / Fill) ---
      document.querySelector('#surface-presentation .pm-tool[data-add="image"]').click();
      await waitFor(function(){ return /Image element/.test(el("pm-inspector-body").textContent); });
      var fitSel = el("pm-inspector-body").querySelector('select[data-ik="imgfit"]');
      ok(!!fitSel && fitSel.options.length === 3, "PM: the Image inspector Fit control offers Stretch/Fit/Fill (C-008, not a disabled placeholder)");
      ok(fitSel && !fitSel.disabled, "PM: the Fit control is live (wired to the render), not a later-seam stub");
      fitSel.value = "fit"; fitSel.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.fit === "fit"; }),
         "PM: the Fit control patches deck_update_element {fit} (letterbox)");

      // --- C-003 Delete-element Undo toast (role=status) ---
      await sleep(20);
      el("pm-inspector-body").querySelector('button[data-ik="del"]').click();
      await waitFor(function(){ return !el("pm-toast").hidden; });
      ok(!el("pm-toast").hidden && el("pm-toast").getAttribute("role") === "status", "PM: deleting an element shows a role=status toast (C-003)");
      ok(/deleted/i.test(el("pm-toast").textContent), "PM: the toast reads 'Element deleted'");
      var undoBtn = el("pm-toast").querySelector(".pm-toast-action");
      ok(!!undoBtn && /Undo/.test(undoBtn.textContent), "PM: the toast offers an Undo action");
      // Before/after delta (deck_undo was already fired earlier by the Undo button, so a bare
      // `.some()` would be tautological — assert the toast Undo STRICTLY increases the count).
      var undoN = window.__calls.filter(function(c){ return c.cmd === "deck_undo"; }).length;
      undoBtn.click();
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_undo"; }).length === undoN + 1, "PM: the toast Undo drives a fresh deck_undo (⌘Z-backed)");

      // --- C-001 Delete-slide confirm (role=alertdialog, Cancel-focused, Esc cancels) ---
      await waitFor(function(){ return document.querySelectorAll("#pm-slide-list .pm-slide").length >= 2; });
      var slideDel = document.querySelector("#pm-slide-list .pm-slide .pm-slide-del:not([disabled])");
      ok(!!slideDel, "PM: each slide has a delete affordance, enabled while >1 slide (C-001)");
      slideDel.click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      var dlg = document.querySelector('.pm-confirm[role="alertdialog"]');
      ok(!!dlg, "PM: delete-slide opens a role=alertdialog confirm");
      ok(dlg.getAttribute("aria-modal") === "true" && dlg.hasAttribute("aria-labelledby"), "PM: the confirm is aria-modal + labelled (C-009)");
      ok(document.activeElement && document.activeElement.textContent === "Cancel", "PM: the confirm focuses Cancel (safe default for a destructive action)");
      var rmSlideBefore = window.__calls.filter(function(c){ return c.cmd === "deck_remove_slide"; }).length;
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      ok(!document.querySelector('.pm-confirm[role="alertdialog"]'), "PM: Esc cancels the confirm (C-009 modal semantics)");
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_remove_slide"; }).length === rmSlideBefore, "PM: cancelling does not remove the slide");
      document.querySelector("#pm-slide-list .pm-slide .pm-slide-del:not([disabled])").click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      Array.from(document.querySelectorAll('.pm-confirm .pm-btn-danger')).filter(function(b){ return /Delete slide/.test(b.textContent); })[0].click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_remove_slide"; }), "PM: confirming delete-slide drives deck_remove_slide");

      // --- C-002 Remove-media confirm with the in-use warning ---
      el("pm-tab-media").click();
      await waitFor(function(){ return !el("pm-media-body").hidden; });
      var inUseCell = Array.from(document.querySelectorAll("#pm-media-grid .pm-asset")).filter(function(cell){
        var d = cell.querySelector(".pm-asset-del"); return d && /used on 2/i.test(d.getAttribute("aria-label") || ""); })[0];
      ok(!!inUseCell, "PM: an in-use asset cell has a remove affordance labelling its usage (C-002)");
      inUseCell.querySelector(".pm-asset-del").click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      ok(!!document.querySelector(".pm-confirm-warn") && /2 slide/i.test(document.querySelector(".pm-confirm-warn").textContent),
         "PM: removing an in-use asset warns 'Used on 2 slides'");
      document.querySelector('.pm-confirm .pm-btn-danger').click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_remove_media" && c.args.id === 1; }), "PM: confirming remove-media drives deck_remove_media(id)");

      // --- C-004 System states: loading (aria-busy) + error banner (role=alert) + Retry ---
      // The busy state must actually ENGAGE while a command is in flight, then clear — not merely
      // exist as an attribute. Defer the next deck command, assert aria-busy="true" + the .busy
      // shimmer during it, resolve, assert it clears to "false".
      await waitFor(function(){ return el("pm-canvas-box").getAttribute("aria-busy") === "false"; }); // let prior commands settle
      ok(el("pm-canvas-box").getAttribute("aria-busy") === "false", "PM: the canvas is not busy at rest");
      window.__pmDeferOnce = true;
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return el("pm-canvas-box").getAttribute("aria-busy") === "true"; });
      ok(el("pm-canvas-box").getAttribute("aria-busy") === "true" && el("pm-canvas-box").classList.contains("busy"),
         "PM: a command in flight sets aria-busy=true + the .busy shimmer (C-004 loading)");
      if (window.__pmDeferred) window.__pmDeferred();
      await waitFor(function(){ return el("pm-canvas-box").getAttribute("aria-busy") === "false"; });
      ok(el("pm-canvas-box").getAttribute("aria-busy") === "false" && !el("pm-canvas-box").classList.contains("busy"),
         "PM: the busy state clears when the command resolves");
      window.__pmRejectOnce = true;
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return !el("pm-error").hidden; });
      ok(!el("pm-error").hidden && el("pm-error").getAttribute("role") === "alert", "PM: a rejected deck command shows a role=alert error banner");
      ok(/couldn't/i.test(el("pm-error-msg").textContent), "PM: the banner explains what failed (not colour-only)");
      el("pm-error-retry").click(); // the one-shot reject flag is cleared → the retry succeeds
      await waitFor(function(){ return el("pm-error").hidden; });
      ok(el("pm-error").hidden, "PM: Retry re-runs the action and clears the banner on success");

      // ‹ Done returns from the editor to the slide grid (the Edit ▸ / ‹ Done round-trip, C-005).
      ok(!!el("pm-done"), "PM/B4: the editor has a '‹ Done' control");
      el("pm-done").click();
      await waitFor(function(){ return !el("pm-grid").hidden; });
      ok(!el("pm-grid").hidden && getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display === "none", "PM/B4: ‹ Done returns from the editor to the grid");

      // === Presentations Library (deck_list / new / open / rename / duplicate / delete) ===
      ok(!!el("pm-deckswitch"), "PM/Lib: the topbar has a deck-switcher breadcrumb");
      el("pm-deckswitch").click();
      await waitFor(function(){ return !el("pm-library").hidden; });
      ok(!el("pm-library").hidden, "PM/Lib: the deck-switcher opens the Presentations Library");
      ok(getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display === "none",
         "PM/Lib: the editor is hidden while the Library is open");
      await waitFor(function(){ return el("pm-lib-grid").querySelectorAll(".pm-lib-card").length >= 3; });
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 3, "PM/Lib: deck_list renders one card per presentation");
      ok(!!el("pm-lib-grid").querySelector(".pm-lib-new-tile"), "PM/Lib: a '＋ New presentation' tile leads the grid");
      ok(/3 presentations/.test(el("pm-lib-count").textContent), "PM/Lib: the count reflects the library");
      ok(!!el("pm-lib-grid").querySelector(".pm-lib-card.open .pm-lib-openflag"), "PM/Lib: the open deck's card carries a non-colour-only OPEN flag");
      // search filters the grid.
      el("pm-lib-q").value = "youth"; el("pm-lib-q").dispatchEvent(new Event("input"));
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 1, "PM/Lib: search filters the grid");
      // a query with no matches shows a 'no results' message (no cards, no New tile).
      el("pm-lib-q").value = "zzznotacard"; el("pm-lib-q").dispatchEvent(new Event("input"));
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 0 && /No presentations match/.test(el("pm-lib-grid").textContent), "PM/Lib: a no-match search shows a no-results message");
      el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input"));
      // ⋯ menu → Duplicate.
      el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots").click();
      await waitFor(function(){ return !!el("pm-lib-menu"); });
      ok(!!el("pm-lib-menu") && el("pm-lib-menu").getAttribute("role") === "menu", "PM/Lib: the ⋯ menu opens (role=menu, keyboard-navigable)");
      var dupN = window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).length;
      Array.from(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /Duplicate/.test(b.textContent); })[0].click();
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).length === dupN + 1, "PM/Lib: ⋯ Duplicate drives deck_duplicate");
      await waitFor(function(){ return el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 4; });
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 4, "PM/Lib: the duplicate appears in the library");
      // ⋯ Rename → name dialog → deck_rename.
      el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots").click();
      await waitFor(function(){ return !!el("pm-lib-menu"); });
      Array.from(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /Rename/.test(b.textContent); })[0].click();
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      ok(!!el("pm-prompt-input") && document.querySelector('.pm-confirm[role="dialog"]'), "PM/Lib: Rename opens a role=dialog name prompt");
      el("pm-prompt-input").value = "Renamed Deck";
      Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_rename" && c.args.name === "Renamed Deck"; }), "PM/Lib: the Rename dialog drives deck_rename(name)");
      // ⋯ Delete the OPEN deck → alertdialog confirm → deck_delete(that id) → editor switches.
      var delCard = el("pm-lib-grid").querySelector(".pm-lib-card.open") || el("pm-lib-grid").querySelector(".pm-lib-card");
      var wantDelId = Number(delCard.dataset.id);
      var nameBeforeDelete = el("pm-plan-name").textContent;
      delCard.querySelector(".pm-lib-dots").click();
      await waitFor(function(){ return !!el("pm-lib-menu"); });
      Array.from(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /Delete/.test(b.textContent); })[0].click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      ok(!!document.querySelector('.pm-confirm[role="alertdialog"]'), "PM/Lib: Delete opens a role=alertdialog confirm");
      document.querySelector(".pm-confirm .pm-btn-danger").click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_delete" && c.args.id === wantDelId; }), "PM/Lib: confirming delete drives deck_delete(that card's id)");
      await waitFor(function(){ return el("pm-plan-name").textContent !== nameBeforeDelete; });
      ok(el("pm-plan-name").textContent !== nameBeforeDelete, "PM/Lib: deleting the OPEN deck switches the editor to a surviving deck");
      // ＋ New Presentation → dialog → deck_new → opens the editor.
      el("pm-lib-new").click();
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      el("pm-prompt-input").value = "Fresh Deck";
      Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_new" && c.args.name === "Fresh Deck"; }), "PM/Lib: New Presentation drives deck_new(name)");
      await waitFor(function(){ return el("pm-library").hidden; });
      ok(el("pm-library").hidden && getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display !== "none", "PM/Lib: creating a deck returns to the editor");
      ok(/Fresh Deck/.test(el("pm-plan-name").textContent), "PM/Lib: the deck-switcher shows the new deck's name");
      // Open a deck from the Library → editor (the CARD'S id crosses + the editor opens on it).
      el("pm-deckswitch").click();
      await waitFor(function(){ return !el("pm-library").hidden; });
      var openCard = el("pm-lib-grid").querySelector(".pm-lib-card");
      var wantOpenId = Number(openCard.dataset.id);
      var wantOpenName = openCard.querySelector(".pm-lib-name").textContent;
      openCard.querySelector(".pm-lib-open").click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_open" && c.args.id === wantOpenId; }), "PM/Lib: clicking a card drives deck_open(that card's id)");
      await waitFor(function(){ return el("pm-library").hidden; });
      ok(el("pm-library").hidden, "PM/Lib: opening a deck returns to the editor");
      ok(el("pm-plan-name").textContent === wantOpenName, "PM/Lib: the editor opens on the chosen deck (name matches)");
      // Not-persistent banner.
      el("pm-deckswitch").click();
      await waitFor(function(){ return !el("pm-library").hidden; });
      window.__LIB.persistent = false;
      el("pm-lib-retry").click();
      await waitFor(function(){ return !el("pm-lib-nopersist").hidden; });
      ok(!el("pm-lib-nopersist").hidden, "PM/Lib: a non-persistent library shows the 'not saved' banner");
      window.__LIB.persistent = true; el("pm-lib-retry").click();
      // Error state: a rejected deck_list shows an error + Retry recovers.
      await waitFor(function(){ return el("pm-lib-nopersist").hidden; });
      window.__pmRejectOnce = true;
      el("pm-lib-retry").click();
      await waitFor(function(){ return !el("pm-lib-error").hidden; });
      ok(!el("pm-lib-error").hidden && el("pm-lib-error").getAttribute("role") === "alert", "PM/Lib: a failed deck_list shows a role=alert error state");
      el("pm-lib-retry").click();
      await waitFor(function(){ return el("pm-lib-error").hidden; });
      ok(el("pm-lib-error").hidden, "PM/Lib: Retry recovers the library");
      // Empty state: an empty library shows 'No presentations yet' with a CTA that opens New.
      window.__LIB.decks = []; window.__LIB.open = 0;
      el("pm-lib-retry").click();
      await waitFor(function(){ return !el("pm-lib-empty").hidden; });
      ok(!el("pm-lib-empty").hidden && el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 0, "PM/Lib: an empty library shows the 'No presentations yet' state");
      el("pm-lib-empty-new").click();
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      ok(!!el("pm-prompt-input"), "PM/Lib: the empty-state CTA opens the New dialog");
      el("pm-prompt-input").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      await waitFor(function(){ return !el("pm-prompt-input"); });
      // ⌘N opens the New presentation dialog (a shipped shortcut the ⋯ menu advertises).
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"n", metaKey:true, bubbles:true}));
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      ok(!!el("pm-prompt-input"), "PM/Lib: ⌘N opens the New presentation dialog");
      el("pm-prompt-input").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      await waitFor(function(){ return !el("pm-prompt-input"); });
      // (The '‹ Back to editor' affordance was removed — the Library is the landing; opening a card
      //  goes to the grid, story 86ajxeq17.)

      // The ⌘1–7 surface map follows menu order: ⌘2 → Presentation, ⌘3 → Theme Designer.
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"3", metaKey:true, bubbles:true}));
      ok(el("surface-theme-designer").classList.contains("active") && !el("surface-presentation").classList.contains("active"),
         "PM: ⌘3 routes to Theme Designer (menu-order ⌘1–7 map)");

      // === Transcripts (86akcffvt / FR-130 core slice) ===============================
      // Local contrast helpers (NOT the shared _cr/_rgba/_f — those are function declarations
      // later in this same `try` block, and Annex B block-function hoisting only makes the NAME
      // safe to reference early, not the value: the outer binding stays undefined until actual
      // execution reaches that later declaration. Self-contained copies avoid depending on
      // execution order at all.)
      function _trSl(v){ v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }
      function _trLum(c){ return 0.2126*_trSl(c[0])+0.7152*_trSl(c[1])+0.0722*_trSl(c[2]); }
      function _trCr(a,b){ var la=_trLum(a), lb=_trLum(b), hi=Math.max(la,lb), lo=Math.min(la,lb); return (hi+0.05)/(lo+0.05); }
      function _trRgba(s){ var m=String(s).match(/[-\d.]+/g)||["0","0","0"]; return [+m[0],+m[1],+m[2], m.length>3?+m[3]:1]; }
      function _trF(r){ return r.toFixed(2); }
      document.querySelector('.nav-item[data-surface="transcripts"]').click();
      ok(el("surface-transcripts").classList.contains("active") && getComputedStyle(el("surface-transcripts")).display !== "none",
         "TR: the nav item opens the Transcripts surface (computed display, WKWebView-safe)");
      await waitFor(function(){ return el("tr-list").querySelectorAll(".tr-card").length >= 3; });
      ok(el("tr-list").querySelectorAll(".tr-card").length === 3, "TR: transcript_list renders one card per transcript");
      ok(el("tr-empty").hidden && getComputedStyle(el("tr-empty")).display === "none", "TR: the empty state is hidden (computed display) while transcripts exist");
      ok(/Sunday Service — Aug 4/.test(el("tr-list").textContent), "TR: a card shows the transcript's label");
      var card1Meta = el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-meta').textContent;
      ok(/3 segments/.test(card1Meta), "TR: a card shows its segment count");
      ok(/\d{1,2}:\d{2}:\d{2}/.test(card1Meta), "TR: a card shows an h:mm:ss duration for a finished transcript (1h01m — over an hour)");
      var card2Meta = el('tr-list').querySelector('.tr-card[data-id="2"] .tr-card-meta').textContent;
      ok(/In progress/.test(card2Meta), "TR: a never-ended transcript (crash/still-recording) shows 'In progress', not a bogus negative duration");
      ok(el("tr-list").querySelector(".tr-card-open").tagName === "BUTTON", "TR: each row's open control is a real <button> (keyboard-activatable by default, NFR-019)");
      // Contrast (NFR-020): card meta text on its card background clears AA-NORMAL.
      var trMetaEl = el("tr-list").querySelector(".tr-card-meta");
      var trMetaC = _trCr(_trRgba(getComputedStyle(trMetaEl).color), _trRgba(getComputedStyle(el("tr-list").querySelector(".tr-card")).backgroundColor));
      ok(trMetaC >= 4.5, "TR: card meta text clears AA-NORMAL on its card ground (" + _trF(trMetaC) + ":1)");

      // ⌘8 (menu-order ⌘1–8, raised from ⌘1–7 by this ticket): away then back.
      document.querySelector('.nav-item[data-surface="console"]').click();
      ok(!el("surface-transcripts").classList.contains("active"), "TR (setup): navigated away from Transcripts");
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"8", metaKey:true, bubbles:true}));
      ok(el("surface-transcripts").classList.contains("active"), "TR: ⌘8 routes to Transcripts (menu-order ⌘1–8 map)");
      await waitFor(function(){ return el("tr-list").querySelectorAll(".tr-card").length >= 3; });

      // Selecting a transcript shows its FULL stored text (86akcffvt AC2) — every segment, not a
      // tail or a sample — plus the honest notes-generated status.
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      ok(window.__calls.some(function(c){ return c.cmd === "transcript_get" && c.args.id === 1; }), "TR: opening a card drives transcript_get(that card's id)");
      await waitFor(function(){ return !el("tr-detail-view").hidden && /Good morning/.test(el("tr-detail-log").textContent); });
      ok(!el("tr-detail-view").hidden && getComputedStyle(el("tr-detail-view")).display !== "none", "TR: selecting a card opens the detail view (computed display)");
      ok(el("tr-list-view").hidden, "TR: the list view is hidden while a transcript is open");
      ok(el("tr-detail-title").textContent === "Sunday Service — Aug 4", "TR: the detail header shows the transcript's label");
      ok(/3 segments/.test(el("tr-detail-meta").textContent), "TR: the detail header shows the segment count");
      var trLog = el("tr-detail-log").textContent;
      ok(/Good morning, church\./.test(trLog) && /Romans chapter eight/.test(trLog) && /all things work together for good/.test(trLog),
         "TR: ALL THREE stored segments render — the full text, not a tail or a sample");
      ok(el("tr-detail-notes").textContent === "Notes not yet generated", "TR: the notes-generated status is honestly reported (no notes table exists yet, 86akcffy0)");
      ok(el("tr-detail-log").getAttribute("role") === "log" && el("tr-detail-log").getAttribute("tabindex") === "0",
         "TR: the transcript text is a role=log, tabindex=0 region — natively keyboard-scrollable once focused (NFR-019)");
      ok(document.activeElement === el("tr-detail-log"), "TR: opening a transcript moves focus INTO the scrollable log (WCAG 2.4.3)");
      // Contrast (NFR-020): rendered line text on the log's background clears AA-NORMAL.
      var trLineEl = el("tr-detail-log").querySelector(".tr-line-txt");
      var trLineC = _trCr(_trRgba(getComputedStyle(trLineEl).color), _trRgba(getComputedStyle(el("tr-detail-log")).backgroundColor));
      ok(trLineC >= 4.5, "TR: transcript line text clears AA-NORMAL on the log's ground (" + _trF(trLineC) + ":1)");

      // Back returns to the list, focus lands on a stable element (WCAG 2.4.3) — the card that
      // opened this transcript is gone from view, so focus must not fall to <body>.
      el("tr-detail-back").click();
      ok(el("tr-list-view").hidden === false && el("tr-detail-view").hidden === true, "TR: ‹ Transcripts returns to the list");
      ok(document.activeElement === el("tr-list").querySelector(".tr-card-open"), "TR: Back restores focus to a real control, not <body>");

      // Detail error state: a rejected transcript_get shows a role=alert error + Retry recovers.
      window.__trGetFailOnce = true;
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-error").hidden; });
      ok(!el("tr-detail-error").hidden && el("tr-detail-error").getAttribute("role") === "alert" && getComputedStyle(el("tr-detail-error")).display !== "none",
         "TR: a failed transcript_get shows a role=alert error state (computed display)");
      el("tr-detail-retry").click();
      await waitFor(function(){ return el("tr-detail-error").hidden && /Good morning/.test(el("tr-detail-log").textContent); });
      ok(el("tr-detail-error").hidden, "TR: Retry recovers the transcript detail");
      el("tr-detail-back").click();

      // List error state: a rejected transcript_list shows a role=alert error + Retry recovers.
      window.__trListFailOnce = true;
      el("tr-retry").click();
      await waitFor(function(){ return !el("tr-error").hidden; });
      ok(!el("tr-error").hidden && el("tr-error").getAttribute("role") === "alert" && getComputedStyle(el("tr-error")).display !== "none",
         "TR: a failed transcript_list shows a role=alert error state (computed display)");
      el("tr-retry").click();
      await waitFor(function(){ return el("tr-error").hidden && el("tr-list").querySelectorAll(".tr-card").length >= 3; });
      ok(el("tr-error").hidden, "TR: Retry recovers the transcripts list");

      // Empty state: no transcripts yet is shown clearly rather than a blank page.
      var savedTrList = window.__TR.list;
      window.__TR.list = [];
      el("tr-retry").click();
      await waitFor(function(){ return !el("tr-empty").hidden; });
      ok(!el("tr-empty").hidden && getComputedStyle(el("tr-empty")).display !== "none" && el("tr-list").querySelectorAll(".tr-card").length === 0,
         "TR: an empty store shows the 'No transcripts yet' state (computed display), not a blank page");
      window.__TR.list = savedTrList;
      el("tr-retry").click();
      await waitFor(function(){ return el("tr-list").querySelectorAll(".tr-card").length >= 3; });

      // === TR bounded rendering (86akcffvt AC3): a transcript with FAR more segments than the
      // live console's 240-segment cap must render COMPLETELY (every segment reachable by
      // scrolling) WITHOUT unbounded DOM growth (the mounted row count stays bounded throughout,
      // never approaching the transcript's real length). This is the mutation-verified control:
      // break `WINDOW_ROWS`/the windowing in transcripts.js and this whole block goes RED. ===
      var TR_BOUND = 200; // comfortably above WINDOW_ROWS(150); far below the 500-segment fixture
      el('tr-list').querySelector('.tr-card[data-id="3"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-view").hidden && el("tr-detail-title").textContent === "Three-Hour Service — Sep 6"; });
      await waitFor(function(){ return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      ok(window.__trRenderedRowCount() <= TR_BOUND,
         "TR bounded: opening a 500-segment transcript mounts <= " + TR_BOUND + " real rows (got " + window.__trRenderedRowCount() + "), not one unbounded DOM blob");
      var firstRow = window.__trRowFor(1000);
      ok(!!firstRow && /Segment 0 —/.test(firstRow.textContent), "TR bounded: the FIRST segment is mounted and reads correctly on open");
      ok(!window.__trRowFor(1499), "TR bounded (control): the LAST segment is NOT mounted on open — proves this is a real window, not every row pre-rendered and merely capped visually");
      // Scroll to the very end: the LAST segment must become reachable (full text, not truncated),
      // and the row count must stay bounded (not grow to 500) — the two halves of AC3 together.
      window.__trScrollToFraction(1);
      await waitFor(function(){ return !!window.__trRowFor(1499); }, 200);
      var lastRow = window.__trRowFor(1499);
      ok(!!lastRow && /Segment 499 —/.test(lastRow.textContent), "TR bounded: scrolling to the end reaches the LAST segment with its exact stored text — the full transcript, not a tail");
      ok(window.__trRenderedRowCount() <= TR_BOUND,
         "TR bounded: after scrolling to the end the mounted row count is STILL <= " + TR_BOUND + " (got " + window.__trRenderedRowCount() + ") — bounded throughout use, not just on first paint");
      ok(!window.__trRowFor(1000), "TR bounded: the FIRST segment's row was evicted once scrolled away — rows are recycled, not endlessly appended (the real 'unbounded growth' failure mode)");
      // A middle position reaches a middle segment, with BOTH ends absent — rules out a mutation
      // that special-cases only the first/last window instead of a genuine sliding one.
      window.__trScrollToFraction(0.5);
      await waitFor(function(){ return !!window.__trRowFor(1250); }, 200);
      ok(!!window.__trRowFor(1250), "TR bounded: scrolling to the middle reaches a middle segment");
      ok(!window.__trRowFor(1000) && !window.__trRowFor(1499), "TR bounded: at the middle position, NEITHER the first nor the last segment is mounted — a genuine sliding window");
      ok(window.__trRenderedRowCount() <= TR_BOUND, "TR bounded: the middle position also stays <= " + TR_BOUND + " rows");
      el("tr-detail-back").click();

      // === TR realistic-width regression control (performance review, Vera V-1/V-2) ==========
      // The 500-segment fixture above uses UNIFORM 85-char lines at this harness's 800x600
      // default — a ratio that sits just above the real/estimated row-height "break-even" point
      // (~0.63) the virtualizer's fixed 88-chars/line ESTIMATE needs to stay accurate, which is
      // exactly why that fixture never caught the bug. This block widens #tr-detail-view to
      // ~1500px (the operator's own real 1520px default window, tauri.conf.json) with a
      // REALISTIC mixed-length 3000-segment transcript, reproducing the regime Vera measured
      // breaking the estimate-only mapping: most scroll frames under 50% covered, up to 131/240
      // fully BLANK with long utterances, and the last segment unreachable (0/8 attempts — the
      // window re-centred back up on the next scroll event). Mutation-verified: reverting
      // transcripts.js to its pre-fix estimate-only scrollTop mapping (no measured-height
      // calibration, no end-pin, clear+rebuild instead of diff-and-patch) turns this whole block
      // RED — see the ticket's evidence for the recorded run.
      window.__trSeedRealistic = true;
      el("tr-retry").click();
      await waitFor(function(){ return el("tr-list").querySelectorAll(".tr-card").length >= 4; });
      var trDetailViewEl = document.getElementById("tr-detail-view");
      var trSavedWidth = trDetailViewEl.style.width, trSavedMaxWidth = trDetailViewEl.style.maxWidth;
      trDetailViewEl.style.maxWidth = "none";
      trDetailViewEl.style.width = "1500px";
      el('tr-list').querySelector('.tr-card[data-id="4"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-view").hidden && el("tr-detail-title").textContent.indexOf("Realistic Long Service") === 0; });
      await waitFor(function(){ return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });

      // Calibration actually ran (ADR-0026 D1: exact per-row heights via a Fenwick tree,
      // replacing the deleted global `avgRatio` scalar this check used to read). The direct
      // successor assertion: a real number of rows were folded into the exact metric — proof the
      // measured-height writeback engaged, not just that the end state happens to look plausible.
      var trMeasured = window.__trMeasuredCount ? window.__trMeasuredCount() : 0;
      ok(trMeasured > 50,
         "TR realistic: a real number of rows were measured and folded into the exact height metric (got " + trMeasured + ")");

      // The last segment must be reachable AND actually VISIBLE (not merely mounted somewhere in
      // the window while sitting behind a mis-sized spacer) after a real scroll to the end.
      var trLastId = String(10000 + 2999);
      window.__trScrollToFraction(1);
      await waitFor(function(){ return !!window.__trRowFor(10000 + 2999); }, 200);
      ok(!!window.__trRowFor(10000 + 2999),
         "TR realistic: scrolling to the end mounts the LAST segment of a realistic-width, realistic-length transcript");
      var trVisAtEnd = window.__trVisibleSegIds ? window.__trVisibleSegIds() : [];
      ok(trVisAtEnd.indexOf(trLastId) !== -1,
         "TR realistic: the last segment is not just mounted but actually VISIBLE at scroll-to-end (Vera V-1: previously 0/8 attempts)");

      // No fully blank frames at several realistic scroll positions (Vera V-1: previously up to
      // 131/240 frames fully blank with long utterances at this width).
      [0.15, 0.35, 0.5, 0.65, 0.85].forEach(function (f) {
        window.__trScrollToFraction(f);
        var trVis = window.__trVisibleSegIds ? window.__trVisibleSegIds() : [];
        ok(trVis.length > 0, "TR realistic: scroll position " + f + " shows at least one real row in the viewport (not a blank frame)");
      });
      ok(window.__trRenderedRowCount() <= TR_BOUND,
         "TR realistic: mounted row count stays bounded (<= " + TR_BOUND + ") on a realistic 3000-segment transcript too");

      // Hysteresis (V-2): a gradual scroll of REAL small wheel-sized steps (60px each, matching
      // Vera's own measured wheel-step size) must re-render far fewer times than it steps —
      // previously nearly every wheel step re-rendered (measured: 175/240 wheel frames, 3-8ms
      // each). Starts from the middle of the transcript (not the very top) so there is a full
      // mounted window's worth of buffer on both sides to demonstrate the hysteresis margin
      // against, rather than immediately hitting the start-of-document edge.
      window.__trScrollToFraction(0.5);
      var trRenderCountBefore = window.__trRenderCount ? window.__trRenderCount() : 0;
      for (var trGi = 0; trGi < 40; trGi++) window.__trScrollBy(60);
      var trRenderCountAfter = window.__trRenderCount ? window.__trRenderCount() : 0;
      ok((trRenderCountAfter - trRenderCountBefore) < 20,
         "TR realistic: 40 real 60px wheel-sized steps trigger well under 40 re-renders (got " +
         (trRenderCountAfter - trRenderCountBefore) + ") — hysteresis is real, not decorative");

      // === TR DOM-node identity across a diff-and-patch render (code review Cody; independently
      // found by Vera as V-7): every check above asserts render COUNT, visual COVERAGE, or
      // reachability — none of that distinguishes a genuine diff-and-patch from a silent
      // clear+rebuild regression, because both can produce the same right-segments-visible end
      // state. Cody proved the gap with his own DOM-node-identity probe; Vera independently
      // confirmed it by mutation (disabling only the diff-and-patch branch survives both
      // committed suites at 0 FAIL). Tag every row currently mounted in the window with a marker
      // THIS TEST owns (transcripts.js never touches it), force a real window move with genuine
      // overlap between the old and new window, then assert every row still in that overlap kept
      // ITS OWN marker — i.e. is the same DOM node the previous render mounted, not a fresh one a
      // clear+rebuild would have created bearing no marker at all.
      window.__trScrollToFraction(0.5);
      var trIdBefore = window.__trWindowBounds();
      for (var trTagI = trIdBefore.start; trTagI < trIdBefore.end; trTagI++) {
        var trTagRow = window.__trRowFor(10000 + trTagI);
        if (trTagRow) trTagRow.setAttribute("data-tr-identity-probe", "1");
      }
      var trIdAfter = trIdBefore;
      for (var trStep = 0; trStep < 60 && trIdAfter.start === trIdBefore.start && trIdAfter.end === trIdBefore.end; trStep++) {
        window.__trScrollBy(60);
        trIdAfter = window.__trWindowBounds();
      }
      ok(trIdAfter.start !== trIdBefore.start || trIdAfter.end !== trIdBefore.end,
         "TR identity (setup): scrolling past the hysteresis margin actually moved the mounted window");
      var trOverlapStart = Math.max(trIdBefore.start, trIdAfter.start);
      var trOverlapEnd = Math.min(trIdBefore.end, trIdAfter.end);
      ok(trOverlapStart < trOverlapEnd,
         "TR identity (setup): the window move left a real overlap to check identity against (not a full jump)");
      var trOverlapCount = 0, trSameNodeCount = 0;
      for (var trOi = trOverlapStart; trOi < trOverlapEnd; trOi++) {
        var trORow = window.__trRowFor(10000 + trOi);
        trOverlapCount++;
        if (trORow && trORow.getAttribute("data-tr-identity-probe") === "1") trSameNodeCount++;
      }
      ok(trOverlapCount > 0 && trSameNodeCount === trOverlapCount,
         "TR identity: every row still in the overlap between the old and new window (" + trOverlapCount +
         ") is the SAME DOM node the previous render mounted, not a freshly created one (" +
         trSameNodeCount + "/" + trOverlapCount + " kept their marker) — proves renderWindow() diffs " +
         "in place and does not silently clear+rebuild");

      // === TR regime-change fresh-open jump control (performance review, Vera V-6) ==============
      // The fixture above interleaves short/medium/long segments EVENLY, so a fresh jump anywhere
      // in it lands in roughly the average regime the calibration ratio already learned near the
      // top — which is exactly why it never caught V-6 (confirmed by mutation: disabling the
      // scroll-anchor compensation entirely leaves every check above at 0 FAIL). The PHASED
      // fixture instead runs three back-to-back length regimes; jumping straight into the long or
      // medium block puts the spacer math against a ratio calibrated on a DIFFERENT regime, which
      // without compensation can put the mounted window somewhere that does not overlap the
      // viewport at all (a fully blank frame). Re-opens the transcript FRESH before EACH jump — a
      // real scrollbar drag starts from a cold window every time the user first grabs the thumb,
      // not from wherever a previous scroll left off.
      window.__trSeedPhased = true;
      el("tr-retry").click();
      await waitFor(function(){ return el("tr-list").querySelectorAll(".tr-card").length >= 5; });
      var trPhasedFractions = [0.4, 0.5, 0.6, 0.8];
      for (var trPfi = 0; trPfi < trPhasedFractions.length; trPfi++) {
        el('tr-list').querySelector('.tr-card[data-id="5"] .tr-card-open').click();
        await waitFor(function(){ return !el("tr-detail-view").hidden && el("tr-detail-title").textContent.indexOf("Regime Change Service") === 0; });
        await waitFor(function(){ return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
        window.__trScrollToFraction(trPhasedFractions[trPfi]);
        var trPhasedVis = window.__trVisibleSegIds ? window.__trVisibleSegIds() : [];
        ok(trPhasedVis.length > 0,
           "TR regime-change: a FRESH-OPEN jump straight to fraction " + trPhasedFractions[trPfi] +
           " (a length regime the calibration ratio has not seen yet) shows at least one real row — not a blank frame (Vera V-6)");
        el("tr-detail-back").click();
      }

      // === TR V-13 (performance review, Vera, test gap): no control specifically proves the
      // ANCHOR half of the V-6 fix (as opposed to the ratio-fallback half) is necessary. Every
      // check above — including "TR regime-change" just above — passes at 0 FAIL even with the
      // anchor forced null and only the ratio-only term applied (round 2's partial "P1" fix,
      // Vera's MV6a mutant): a ratio-only correction still avoids a fully BLANK frame, it just
      // lands 300-1,257px off the row it should have kept anchored on a fair fraction of frames,
      // which none of the "at least one row visible" / "reachable" style assertions can see.
      // This tracks ONE real row that survives a hysteresis-crossing render (the overlap of the
      // old/new window — the same computation "TR identity" above already uses) and asserts its
      // ON-SCREEN pixel position after N real 60px wheel-sized steps lands within 2px of "moved
      // up by exactly 60*N px" — a bound only the anchor term (which reads that row's OWN live
      // rendered position) can hit, since the ratio-only fallback has no way to know any ONE
      // row's individual real/estimate error and misses by far more than 2px whenever a real
      // row's height diverges from the running average ratio (the whole reason the PHASED
      // fixture's long block exists).
      el('tr-list').querySelector('.tr-card[data-id="5"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-view").hidden && el("tr-detail-title").textContent.indexOf("Regime Change Service") === 0; });
      await waitFor(function(){ return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      window.__trScrollToFraction(0.5); // deep in the long block, same as "TR regime-change" above
      var trV13Before = window.__trWindowBounds();
      var trV13TargetIdx = Math.min(trV13Before.start + 70, trV13Before.end - 1);
      var trV13TargetId = String(20000 + trV13TargetIdx);
      var trV13Row = window.__trRowFor(trV13TargetId);
      ok(!!trV13Row, "TR V-13 (setup): the tracked row is mounted before any wheel-sized steps");
      var trV13OldTop = trV13Row ? trV13Row.getBoundingClientRect().top : null;
      var trV13RenderBefore = window.__trRenderCount();
      var trV13Ticks = 0, trV13RenderAfter = trV13RenderBefore;
      while (trV13Ticks < 80 && trV13RenderAfter === trV13RenderBefore) {
        window.__trScrollBy(60);
        trV13Ticks++;
        trV13RenderAfter = window.__trRenderCount();
      }
      ok(trV13RenderAfter > trV13RenderBefore,
         "TR V-13 (setup): a real hysteresis-crossing render fired within the tick budget (" + trV13Ticks + " ticks)");
      var trV13After = window.__trWindowBounds();
      var trV13RowAfter = window.__trRowFor(trV13TargetId);
      var trV13Survived = !!trV13RowAfter && trV13RowAfter === trV13Row;
      ok(trV13Survived,
         "TR V-13 (setup): the tracked row SURVIVED the crossing render as the same DOM node (still in the overlap)");
      // Always runs (never skipped) so this file's own check COUNT cannot vary run to run: a
      // failed survival above still fails this assertion outright rather than silently omitting
      // it, instead of leaving the count dependent on a runtime condition.
      var trV13NewTop = trV13Survived ? trV13RowAfter.getBoundingClientRect().top : NaN;
      var trV13ExpectedDelta = 60 * trV13Ticks;
      var trV13Error = trV13Survived && trV13OldTop !== null
        ? Math.abs(trV13NewTop - trV13OldTop + trV13ExpectedDelta) : Infinity;
      ok(trV13Error <= 2,
         "TR V-13: the anchor keeps a real tracked row within 2px of its expected on-screen " +
         "position after " + trV13Ticks + " real 60px steps crossing a render (error " +
         trV13Error.toFixed(2) + "px) — the ratio-only fallback alone cannot hit this bound " +
         "(Vera measured 300-1,257px hops under that mutant)");

      // === TR keyboard-jump no longer intercepted (ADR-0026 rev 2, D2/D3 — replaces round 6's
      // "TR wheel/jump race guard" block with its INVERSE, per the ADR's own words: "a suite that
      // has to be inverted is evidence the model is wrong, not that a case was missed"). Round
      // 6's guard (`armJumpGuard`/`wheelEventSeq`/`jumpGuardGen`/`expectedScrollTop`) existed only
      // to defend an ABSOLUTE `scrollTop` promise a keyboard jump made against a foreign write
      // landing after it. Under D2 nothing in this file ever writes `scrollTop` reactively, so
      // there is no promise left to defend and no guard exists to fight anything — round 7 (the
      // guard fighting a genuine scrollbar drag, Cody/Quinn) and round 5 (a stale wheel commit
      // corrupting a jump's landing, Quinn) are both unreachable by construction now, not merely
      // defended against. This asserts that directly: simulate a "jump" (the same
      // `__trScrollToFraction` setup the old block used) landing away from 0, then apply EXACTLY
      // the old test's stale-commit DOM signature (a bare `scrollTop` write + a `scroll` event
      // with no accompanying new `wheel` event) and assert it now STICKS — the same settle window
      // (10 * 20ms) the old guard used to poll, so a reintroduced guard would still have every
      // chance to reveal itself here.
      el('tr-list').querySelector('.tr-card[data-id="5"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-view").hidden && window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      window.__trScrollToFraction(0.5); // start deep in the transcript, same as TR V-13 above
      var trKjBefore = el("tr-detail-log").scrollTop;
      ok(trKjBefore > 0, "TR keyboard-jump (setup): the jump landed away from 0");
      el("tr-detail-log").scrollTop = trKjBefore + 400;
      el("tr-detail-log").dispatchEvent(new Event("scroll"));
      for (var trKjSettle = 0; trKjSettle < 10; trKjSettle++) { await sleep(20); }
      ok(el("tr-detail-log").scrollTop === trKjBefore + 400,
         "TR keyboard-jump: a scrollTop write right after a jump STICKS — round 7's guard (which " +
         "used to revert exactly this DOM signature, mistaking it for a stale wheel commit) no " +
         "longer exists to fight it (got " + el("tr-detail-log").scrollTop + ", expected " +
         (trKjBefore + 400) + ")");

      // === TR anchoring-is-live (ADR-0026 D2, "3 new controls"): the compensation that used to
      // be `renderWindow`'s own `findTopVisibleSurvivor` + anchor-term script write is now the
      // BROWSER's job — native scroll anchoring, enabled on `.tr-log` (no longer disabled),
      // excluded on the two spacers instead (`.tr-log-spacer { overflow-anchor: none }`) so a
      // real `.tr-line` row is always the anchor candidate. This is the ADR's own spike
      // discriminator (Q7/Q8) run against the REAL component instead of a synthetic fixture: grow
      // the top spacer (content entirely above the viewport) by a fixed amount with NO
      // accompanying scrollTop write, and assert (a) the row the reader is looking at drifts
      // <= 2px on screen, and (b) scrollTop moved by ~the same amount the spacer grew — i.e. the
      // ENGINE did the compensation, not this file. Mutation: restoring `overflow-anchor: none`
      // on `.tr-log` (undoing D2) makes scrollTop NOT move and the reader's row jump by the full
      // growth instead — the exact pre-fix defect this ADR replaces.
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="4"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-view").hidden && window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      window.__trScrollToFraction(0.5);
      var trAnchVis = window.__trVisibleSegIds();
      ok(trAnchVis.length > 0, "TR anchoring-is-live (setup): at least one row visible before the mutation");
      var trAnchRow = window.__trRowFor(trAnchVis[0]);
      var trAnchBeforeTop = trAnchRow.getBoundingClientRect().top;
      var trAnchBeforeScroll = el("tr-detail-log").scrollTop;
      var trAnchSpacer = el("tr-log-top-spacer");
      var trAnchGrow = 200;
      var trAnchCurH = parseFloat(trAnchSpacer.style.height) || 0;
      trAnchSpacer.style.height = (trAnchCurH + trAnchGrow) + "px"; // a plain DOM mutation — NO scrollTop write
      void el("tr-detail-log").offsetHeight; // force layout so anchoring has run before reading below
      await sleep(50);
      var trAnchAfterTop = trAnchRow.getBoundingClientRect().top;
      var trAnchAfterScroll = el("tr-detail-log").scrollTop;
      trAnchSpacer.style.height = trAnchCurH + "px"; // restore — this block owns no lasting DOM change
      ok(Math.abs(trAnchAfterTop - trAnchBeforeTop) <= 2,
         "TR anchoring-is-live: growing the top spacer by " + trAnchGrow + "px drifts the reader's " +
         "own row by <= 2px on screen (got " + (trAnchAfterTop - trAnchBeforeTop).toFixed(2) +
         "px) — native scroll anchoring compensates it, not this file");
      ok(Math.abs((trAnchAfterScroll - trAnchBeforeScroll) - trAnchGrow) <= 2,
         "TR anchoring-is-live: scrollTop moved by ~" + trAnchGrow + "px on its OWN (delta " +
         (trAnchAfterScroll - trAnchBeforeScroll) + "), matching the spacer growth — proves the " +
         "ENGINE did this compensation, with no script scrollTop write anywhere in the path");

      // === TR I2 monotonicity (ADR-0026 D1, "3 new controls"): D1's whole justification is that
      // measuring row i moves the position of rows > i ONLY — rows <= i never move (I2). This
      // reads the D1 metric DIRECTLY (`__trOffsetAt`, the exact Fenwick-tree prefix sum), not a
      // rendered pixel position, so it tests the DATA STRUCTURE'S invariant rather than anything
      // conflated with rendering/anchoring. Snapshot the offsets of several EARLY rows, force a
      // real number of LATER rows (deep in the transcript) to be measured, then assert the early
      // rows' offsets are byte-identical to before. Mutation: reintroducing a global rescale
      // (the deleted `avgRatio` mechanism) moves every earlier row's offset too — this fails
      // immediately and by a large margin, not a rounding-sized drift.
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="5"] .tr-card-open').click();
      await waitFor(function(){ return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      window.__trScrollToFraction(0.3);
      var trI2Wb = window.__trWindowBounds();
      var trI2EarlyIdx = [0, 50, 150, Math.max(0, trI2Wb.start - 10)];
      var trI2Before = trI2EarlyIdx.map(function (i) { return window.__trOffsetAt(i); });
      window.__trScrollToFraction(0.8);
      for (var trI2T = 0; trI2T < 20; trI2T++) window.__trScrollBy(600);
      var trI2Measured = window.__trMeasuredCount();
      ok(trI2Measured > 100,
         "TR I2 (setup): a real number of rows were measured deep in the transcript (" + trI2Measured + ")");
      var trI2After = trI2EarlyIdx.map(function (i) { return window.__trOffsetAt(i); });
      var trI2AllSame = true, trI2Diffs = [];
      for (var trI2K = 0; trI2K < trI2EarlyIdx.length; trI2K++) {
        if (trI2Before[trI2K] !== trI2After[trI2K]) {
          trI2AllSame = false;
          trI2Diffs.push([trI2EarlyIdx[trI2K], trI2Before[trI2K], trI2After[trI2K]]);
        }
      }
      ok(trI2AllSame,
         "TR I2 monotonicity: the exact offsets of early rows " + JSON.stringify(trI2EarlyIdx) +
         " are UNCHANGED after measuring rows far below them (diffs: " + JSON.stringify(trI2Diffs) +
         ") — measuring row i never moves the position of rows <= i");
      el("tr-detail-back").click();

      // === TR measureObserver disconnect on resize-mid-scroll (86akmdkdg): `invalidateHeightsForWidth`
      // (the resize-triggered force-remount path, ADR-0026 D4) used to clear `rowsHost.innerHTML`
      // WITHOUT disconnecting `measureObserver` first, unlike the file's other two mount call sites
      // (`renderWindow`'s no-overlap branch, `openTranscript`). If a row is mid-async-measurement —
      // the deferred `ResizeObserver` path 86akmd00b introduced, only ever live while `inScrollFrame`
      // (i.e. reached through a real `scroll` event's own rAF callback, never through a test hook
      // that calls `renderWindow` directly) — when a resize fires, the observer is left holding a
      // reference to a now-detached node: a real leak (CLAUDE.md's bounded-memory discipline).
      //
      // NOTE on why this checks ORDER, not just the end state: `invalidateHeightsForWidth` ends by
      // calling `renderWindow(savedStart, savedEnd)` with `winStart`/`winEnd` already zeroed, which
      // makes THAT call's own no-overlap branch disconnect `measureObserver` a few lines later
      // regardless of this ticket's fix — so the count of live observer targets is back to 0 by the
      // time `invalidateHeightsForWidth` RETURNS either way, and a check that only reads the count
      // afterwards would pass even without the fix (exactly the "control asserting nothing" trap
      // this repo's bounded-memory discipline warns about). What actually differs is ORDER: does
      // `rowsHost.innerHTML` get cleared before or after `measureObserver` is disconnected? This is
      // captured by intercepting the `innerHTML` setter on `rowsHost` itself and reading
      // `__trMeasureObservedCount()` at the exact moment of the FIRST clear inside the call — before
      // the fix that count is whatever was pending; after the fix it is already 0.
      //
      // The pending state is reproduced by dispatching a genuine `scroll` event (so `onScroll`
      // schedules its usual rAF callback, and — critically — `rafPending` really is set, matching
      // production) but capturing that ONE callback via a temporary `requestAnimationFrame`
      // override instead of racing the browser's own frame scheduling to run right after it. This
      // file runs under Chrome's `--virtual-time-budget` (see the harness docstring above): real
      // rAF-ordering-across-frames assumptions are exactly the kind of "condition nobody can
      // reliably reproduce" ADR-0026 D3's own comment warns against, and an ordering surprise here
      // does not merely flake — it can throw partway through the driver and abort the ENTIRE run
      // with "NO RESULTS BLOCK" instead of one named FAIL (confirmed against this exact block: solid
      // standalone, but crashed the whole suite once under load — never again with the direct-call
      // approach below, which needs no frame scheduling at all). Invoking the captured callback
      // ourselves runs the SAME code (`inScrollFrame = true; recomputeWindow(); … inScrollFrame =
      // false;`) as a real frame would, deterministically, on our own schedule.
      el('tr-list').querySelector('.tr-card[data-id="5"] .tr-card-open').click();
      await waitFor(function(){ return !el("tr-detail-view").hidden && window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      window.__trScrollToFraction(0.5); // land mid-transcript (test-hook jump, no async path — count stays 0)
      var trMoLog = el("tr-detail-log");
      var trMoOrigRaf = window.requestAnimationFrame;
      var trMoCapturedCb = null;
      try {
        window.requestAnimationFrame = function (cb) { trMoCapturedCb = cb; return 1; };
        var trMoMax = Math.max(0, trMoLog.scrollHeight - trMoLog.clientHeight);
        trMoLog.scrollTop = trMoMax; // a REAL scroll all the way to the end — guaranteed to move the
                                      // mounted window regardless of this fixture's per-row height
        trMoLog.dispatchEvent(new Event("scroll")); // onScroll() runs synchronously here and calls
                                                      // the patched requestAnimationFrame above,
                                                      // which just records the callback (does not run it)
      } finally {
        window.requestAnimationFrame = trMoOrigRaf;
      }
      ok(typeof trMoCapturedCb === "function",
         "TR measureObserver disconnect (setup): the real scroll event scheduled onScroll's rAF " +
         "callback — captured directly rather than racing real frame timing");
      trMoCapturedCb(); // run it ourselves: inScrollFrame is true for exactly this call, during
                         // which startMeasuring defers the newly-scrolled-in rows onto measureObserver
      var trMoPending = window.__trMeasureObservedCount();
      ok(trMoPending > 0,
         "TR measureObserver disconnect (setup): a real scroll deferred at least one row onto " +
         "measureObserver (got " + trMoPending + ") — without a pending measurement the check " +
         "below would test nothing");

      var trMoRowsHost = el("tr-log-rows");
      var trMoAtFirstClear = null;
      var trMoOrigDesc = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
      Object.defineProperty(trMoRowsHost, "innerHTML", {
        configurable: true,
        get: function () { return trMoOrigDesc.get.call(this); },
        set: function (v) {
          if (trMoAtFirstClear === null) trMoAtFirstClear = window.__trMeasureObservedCount();
          return trMoOrigDesc.set.call(this, v);
        }
      });
      try {
        window.__trInvalidateHeightsForWidth(); // force-fires the resize path, mid the pending measurement above
      } finally {
        delete trMoRowsHost.innerHTML; // restore the prototype's own accessor unconditionally
      }
      ok(trMoAtFirstClear === 0,
         "TR measureObserver disconnect on resize: invalidateHeightsForWidth must disconnect " +
         "measureObserver BEFORE the FIRST time it clears rowsHost.innerHTML — measureObserver " +
         "still had " + trMoAtFirstClear + " live target(s) referencing now-detached nodes at that " +
         "exact moment (expected 0) — matching renderWindow's no-overlap branch and openTranscript");
      ok(window.__trMeasureObservedCount() === 0,
         "TR measureObserver disconnect on resize: no live observer targets remain once " +
         "invalidateHeightsForWidth has finished re-rendering (got " + window.__trMeasureObservedCount() + ")");
      el("tr-detail-back").click();

      trDetailViewEl.style.width = trSavedWidth;
      trDetailViewEl.style.maxWidth = trSavedMaxWidth;
      el("tr-detail-back").click();

      // === TR generate: Generate Sermon Notes from a STORED transcript (86akcffy0; FR-122/130,
      // AC1/AC2/AC3/AC4/AC5/AC6) =================================================================
      // Same F-5/PERF-3 shape as the Settings panel's live-tail Generate (86akby7d8, "PP F-5"
      // above) — the review-and-confirm step is real and calling transcript_generate_notes never
      // happens without an explicit Confirm, the SAME shared consent gate (one ProvidersConfig)
      // blocks the network call with consent off — but built from a STORED transcript's COMPLETE
      // text (never the live console's 60-segment tail) with its own honest
      // `.pp-gen-preview-scope` disclosure copy, and its own visible over-the-clamp notice.
      // Local helpers, not the later-declared `ppCall`/`ppLast` (those are `var`s assigned much
      // further down this same script — referencing them here would hit the exact Annex-B
      // hoisting trap the "_trSl" comment above already warns about: the NAME exists early, the
      // VALUE does not).
      var trCall = function (cmd) { return window.__calls.filter(function (c) { return c.cmd === cmd; }); };
      var trLast = function (cmd) { var a = trCall(cmd); return a.length ? a[a.length - 1] : null; };

      document.querySelector('.nav-item[data-surface="transcripts"]').click();
      await waitFor(function () { return el("tr-list").querySelectorAll(".tr-card").length >= 3; });
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      var trFullText1 = window.__TR.detail[1].segments.map(function (s) { return s.text; }).join("\n");

      // (a) Generate opens the review step instead of sending, and calling
      // transcript_generate_notes has still not happened.
      ok(!!el("tr-generate") && getComputedStyle(el("tr-generate")).display !== "none",
         "TR generate: the Generate Sermon Notes button is present on the transcript detail view");
      var trGenBefore = trCall("transcript_generate_notes").length;
      el("tr-generate").click();
      await sleep(40);
      var trPreview = el("tr-gen-preview");
      ok(!!trPreview && trPreview.hidden === false, "TR F-5: Generate opens the review step instead of sending");
      // hidden-attr-vs-css-display trap (this webview) — assert COMPUTED display, same discipline
      // as "PP F-5 (computed display)" above.
      ok(getComputedStyle(trPreview).display !== "none",
         "TR F-5 (computed display): the review step is actually visible on screen, not defeated by a CSS display rule");
      var trPreviewText = trPreview.querySelector(".pp-gen-preview-text");
      ok(!!trPreviewText && trPreviewText.textContent === trFullText1,
         "TR F-5 (AC1): the review step shows the transcript's EXACT complete stored text, byte for byte — not a 60-segment tail");
      ok(new RegExp(String(trFullText1.length) + " characters").test(trPreview.textContent),
         "TR F-5: the review step states how much text is about to be sent");
      ok(trCall("transcript_generate_notes").length === trGenBefore,
         "TR F-5: opening the review step alone still has not called transcript_generate_notes");
      ok(el("tr-generate").hidden === true, "TR F-5: the Generate button is hidden while its own review step is open (no double-fire path)");
      ok(document.activeElement === trPreview.querySelector(".pp-gen-preview-title"),
         "TR F-5 a11y: opening the review step moves focus into it");

      // (b) TR F-5 L-2 (AC3/AC4): the from-history disclosure is honest — it states the COMPLETE
      // stored transcript is being sent, in contrast to the live-tail flow's "recent window"
      // disclosure (which stays unchanged and still true for THAT flow — see "PP F-5 L-2" above,
      // pinned separately). Exact copy pinned so this cannot silently drift back toward the
      // misleading claim the ticket's own context calls out.
      var trPreviewScope = trPreview.querySelector(".pp-gen-preview-scope");
      ok(!!trPreviewScope && trPreviewScope.textContent ===
         "This is the complete transcript stored for this service — every recorded segment, not a recent window.",
         "TR F-5 L-2 (AC3): the from-history review step discloses the COMPLETE transcript is being sent (exact copy pinned)");
      ok(!trPreview.querySelector(".pp-gen-preview-clamp"),
         "TR F-5 L-2 (AC2 negative control): a transcript well under the 400,000-character clamp shows NO truncation notice");

      // (c) Cancel closes the review step without ever calling transcript_generate_notes, and
      // returns focus to Generate (same F-5 a11y property as the live-tail flow).
      el("tr-gen-preview-cancel").click();
      ok(trCall("transcript_generate_notes").length === trGenBefore, "TR F-5: Cancel never calls transcript_generate_notes");
      ok(el("tr-gen-preview").hidden === true, "TR F-5: Cancel closes the review step");
      ok(getComputedStyle(el("tr-gen-preview")).display === "none",
         "TR F-5 (computed display): Cancel actually removes the panel from layout, not just the [hidden] attribute");
      ok(el("tr-generate").hidden === false, "TR F-5: Cancel restores the Generate button");
      ok(document.activeElement === el("tr-generate"), "TR F-5 a11y: Cancel returns keyboard focus to Generate");

      // (d) AC5: consent off blocks the network call for THIS path exactly as it does for the
      // live-tail path — a regression test, not an assumption: both flows read the SAME shared
      // ProvidersConfig consent gate (state.providers in main.rs), proven here by driving the
      // ACTUAL from-history UI rather than asserting the shared Rust function in isolation.
      ok(!window.__pp.cloud_notes_consent, "TR generate consent (premise): consent defaults to OFF, untouched by this point in the script");
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      ok(trCall("transcript_generate_notes").length === trGenBefore + 1,
         "TR generate consent (setup): Confirm really did call transcript_generate_notes once");
      var trConsentResult = el("tr-gen-result");
      ok(!!trConsentResult && !trConsentResult.hidden && /Turn on cloud processing/.test(trConsentResult.textContent),
         "TR generate consent (AC5): consent-off refuses the from-history path exactly like the live-tail path — no draft is produced or shown");
      ok(!el("tr-detail-notes").classList.contains("tr-notes-on"),
         "TR generate consent: notes_generated is NOT flipped by a refused (consent_required) call");

      // (e) With consent on, Confirm sends the transcript's ID (not a client-supplied string —
      // the command re-reads the store itself, AC6's premise), the result renders WITH an Edit
      // affordance (86akgqdxr: this ticket is the named successor to 86akcffy0's own "editing
      // stays the Settings panel's persisted-draft flow" restriction — a from-history draft is
      // now editable in place, via the SAME transcript-id-generic `update_sermon_note_draft`
      // command), and the notes badge flips immediately.
      window.__pp.cloud_notes_consent = true;
      window.__trGen = "ok";
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      var trOkLast = trLast("transcript_generate_notes");
      ok(!!trOkLast && trOkLast.args.id === 1,
         "TR generate: Confirm sends the transcript's id, not its text — the command re-reads the store itself");
      var trOkResult = el("tr-gen-result");
      ok(!!trOkResult && /From-History Sermon/.test(trOkResult.textContent), "TR generate: a successful generation renders the returned draft");
      ok(!!trOkResult.querySelector(".pp-gen-edit-btn") && !!document.getElementById("tr-gen-edit"),
         "TR generate (86akgqdxr): the from-history draft now renders WITH an Edit affordance — the id is tr-gen-edit, never pp-gen-edit, since both panels' markup coexists in one document");
      ok(!document.getElementById("pp-gen-edit"),
         "TR generate: this Edit button is NOT settings.js's own #pp-gen-edit — no id collision between the two panels");
      ok(el("tr-detail-notes").classList.contains("tr-notes-on") && /Notes generated/.test(el("tr-detail-notes").textContent),
         "TR generate: a successful generate flips the notes badge immediately, without waiting for a reopen");

      // === FR-129 (86akgqdx8) on the Transcripts workspace: the SAME regenerate-with-retention
      // contract PP REGEN-* proves above, exercised through THIS surface's own wiring
      // (transcript_generate_notes / confirm+discard_sermon_note_regeneration, `tr-` prefixed
      // element ids, shared `.pp-gen-regen-*` CSS classes) — transcript 1 already has a saved
      // "From-History Sermon" draft from the block just above, consent is ON. Not re-proving
      // every nuance PP REGEN-* already covers end to end (consent-off, transport-failure) —
      // those are the SAME shared backend gate/pipeline (see (d) above, which already proves
      // THIS surface shares the consent gate); this proves TR's OWN banner/edit-gating/confirm/
      // discard wiring actually works, and that a degraded regenerate cannot downgrade an
      // already AI-generated draft here either. ================================================
      window.__trGen = "regenerate_pending";
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      var trRegenResult = el("tr-gen-result");
      ok(/From-History Sermon \(regenerated\)/.test(trRegenResult.textContent),
         "TR REGEN-1: the freshly regenerated draft's content is shown immediately");
      var trRegenBanner = trRegenResult.querySelector(".pp-gen-regen-banner");
      ok(!!trRegenBanner && getComputedStyle(trRegenBanner).display !== "none",
         "TR REGEN-1: a pending-confirmation banner is rendered (computed display)");
      ok(/From-History Sermon/.test(trRegenBanner.textContent) && !/\(regenerated\)/.test(trRegenBanner.textContent),
         "TR REGEN-1: the banner names the STILL-SAVED prior draft's own title");
      ok(!document.getElementById("tr-gen-edit"),
         "TR REGEN-1: Edit is hidden while a regeneration is pending, on this surface too");
      var trPriorStillSaved = window.__TR.detail[1].draft;
      ok(!!trPriorStillSaved && trPriorStillSaved.title === "From-History Sermon",
         "TR REGEN-1 (AC): the prior draft is retrievable and UNCHANGED on the host immediately " +
         "after a regenerate is requested, before the operator confirms replacement");

      // Discard leaves the saved draft exactly as it was.
      el("tr-gen-regen-discard").click();
      await sleep(60);
      var trAfterDiscard = el("tr-gen-result");
      ok(/From-History Sermon/.test(trAfterDiscard.textContent) && !/regenerated/.test(trAfterDiscard.textContent),
         "TR REGEN-2: after Discard, the view shows the ORIGINAL saved draft");
      ok(!trAfterDiscard.querySelector(".pp-gen-regen-banner"),
         "TR REGEN-2: the pending-confirmation banner is gone after Discard");
      ok(!!document.getElementById("tr-gen-edit"),
         "TR REGEN-2: Edit is offered again once nothing is pending");

      // Confirm REPLACES the saved draft — single prior version, so the replaced one is gone.
      window.__trGen = "regenerate_pending";
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      el("tr-gen-regen-confirm").click();
      await sleep(60);
      var trAfterConfirm = el("tr-gen-result");
      ok(/From-History Sermon \(regenerated\)/.test(trAfterConfirm.textContent),
         "TR REGEN-3: after Confirm, the view shows the NEW draft as the current one");
      ok(!trAfterConfirm.querySelector(".pp-gen-regen-banner"),
         "TR REGEN-3: the banner is gone once confirmed");
      ok(window.__TR.detail[1].draft.title === "From-History Sermon (regenerated)",
         "TR REGEN-3: the CONFIRMED content is what the host now actually persists for this transcript");

      // A degraded regenerate stages and shows its content, but cannot be CONFIRMED over an
      // already AI-generated draft — "once AI-generated, always AI-generated" holds on this
      // surface too, and the refused pending draft remains staged rather than vanishing.
      window.__trGen = "regenerate_pending_degraded";
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      var trRegenDegResult = el("tr-gen-result");
      ok(/Offline outline \(regenerated\)/.test(trRegenDegResult.textContent) &&
         !!trRegenDegResult.querySelector(".pp-gen-regen-banner") &&
         !trRegenDegResult.querySelector(".pp-gen-ai-label"),
         "TR REGEN-4: a degraded regenerate stages and shows its (unlabelled) content, exactly like the original flow's degraded handling");
      el("tr-gen-regen-confirm").click();
      await sleep(60);
      // The refusal renders INLINE on the still-visible banner — never a whole-region wipe.
      // This matters MORE here than on settings.js: reopening this transcript would LOSE the
      // pending state entirely (transcript_get never re-surfaces it), so there is no
      // "navigate away and back" recovery path if the banner itself were wiped.
      var trRegenDegAfterRefusal = el("tr-gen-result");
      ok(/Offline outline \(regenerated\)/.test(trRegenDegAfterRefusal.textContent),
         "TR REGEN-4: the pending draft's content is STILL shown after the refused confirm");
      var trRegenDegInlineError = trRegenDegAfterRefusal.querySelector(".pp-gen-regen-error");
      ok(!!trRegenDegInlineError && trRegenDegInlineError.getAttribute("role") === "alert" &&
         /AI-generated label/.test(trRegenDegInlineError.textContent),
         "TR REGEN-4: the refusal reason renders INLINE on the banner, not as a separate message that replaces the draft view");
      ok(!!document.getElementById("tr-gen-regen-discard") && !!document.getElementById("tr-gen-regen-confirm"),
         "TR REGEN-4: Confirm/Discard remain reachable after a refused confirm — no dead end");
      ok(window.__TR.detail[1].draft.title === "From-History Sermon (regenerated)",
         "TR REGEN-4: the accepted draft is untouched by the refused confirm attempt");
      ok(!!window.__TR.detail[1].pending,
         "TR REGEN-4: the refused pending draft remains staged on the host, not silently discarded");
      el("tr-gen-regen-discard").click();
      await sleep(60);
      ok(/From-History Sermon \(regenerated\)/.test(el("tr-gen-result").textContent),
         "TR REGEN-4: discarding the refused degraded regeneration cleanly restores the accepted draft");

      // TR REGEN-5/6 (Quinn, 86akgqdx8 four-reviewer gate — Low): PP REGEN-4/PP REGEN-5 prove
      // consent-off and transport-failure SPECIFICALLY against a transcript that ALREADY has a
      // saved draft (the regenerate scenario) — not just the first-time-generate case (d) above
      // already covers on this surface. Code inspection shows both consoles share the exact
      // same `persist_generated_draft`/`transcript_generate_notes` call sites, so this is not
      // expected to reveal a functional gap — but this batch has hit a real MAJOR bug before
      // from exactly this shape of "proven on one console, assumed on the other" gap, so it is
      // proven here explicitly rather than left as an inference from (d) + PP REGEN-4/5.
      window.__pp.cloud_notes_consent = false;
      window.__trGen = "regenerate_pending";
      var trRegenConsentGenCallsBefore = trCall("transcript_generate_notes").length;
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      var trRegenConsentOffResult = el("tr-gen-result");
      ok(trRegenConsentOffResult.getAttribute("role") === "alert" &&
         /Turn on cloud processing/.test(trRegenConsentOffResult.textContent),
         "TR REGEN-5: with consent OFF, regenerating a transcript that already has a saved " +
         "draft is STILL gated exactly like a first-time generate (consent_required)");
      ok(trCall("transcript_generate_notes").length === trRegenConsentGenCallsBefore + 1,
         "TR REGEN-5 (sanity): the call reached the backend and was gated there — the client " +
         "did not merely refuse locally");
      ok(!/regenerated/.test(trRegenConsentOffResult.textContent),
         "TR REGEN-5: no draft content of any kind leaked into view — nothing was generated");
      ok(window.__TR.detail[1].draft.title === "From-History Sermon (regenerated)" &&
         !window.__TR.detail[1].pending,
         "TR REGEN-5: the saved draft from REGEN-3 is completely unaffected by the refused " +
         "attempt, and no pending regeneration was created");
      window.__pp.cloud_notes_consent = true;

      window.__trGen = "transport";
      el("tr-generate").click();
      await sleep(40);
      el("tr-gen-preview-confirm").click();
      await sleep(60);
      var trRegenTransportResult = el("tr-gen-result");
      ok(trRegenTransportResult.getAttribute("role") === "alert",
         "TR REGEN-6: a transport failure during regenerate surfaces as an alert, same as a first-time generate");
      ok(window.__TR.detail[1].draft.title === "From-History Sermon (regenerated)" &&
         !window.__TR.detail[1].pending,
         "TR REGEN-6 (AC): a transport failure during regenerate never loses the prior " +
         "(pre-regenerate) draft, and stages nothing");

      window.__trGen = "ok"; // restore for any later reads

      // (f) Switching to a DIFFERENT transcript resets all Generate UI/state — no stale result
      // from transcript 1 leaks into transcript 2's freshly opened detail view. Transcript 2
      // ("Wednesday Bible Study") is the harness's own never-ended fixture (`ended_at_ms: null`)
      // — reused here rather than adding a new one, and it doubles as the in-progress case for
      // (f-2) below.
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="2"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      ok(el("tr-gen-result").textContent.indexOf("From-History Sermon") === -1,
         "TR generate: opening a DIFFERENT transcript clears any previous Generate result — transcript 1's draft text does not leak into transcript 2's view");
      ok(!el("tr-detail-notes").classList.contains("tr-notes-on"),
         "TR generate: transcript 2's own (untouched) notes_generated state shows, not transcript 1's");

      // (f-2) AC/Sana F1 (High): a transcript still being recorded is NOT eligible for
      // from-history Generate — transcript 2 has `ended_at_ms: null` in its own fixture. The
      // button must be genuinely disabled (computed, not just the attribute) and the operator
      // must be told why, immediately, without having to click anything first.
      ok(el("tr-generate").disabled === true,
         "TR generate (Sana F1): the Generate button is disabled for a transcript still being recorded");
      ok(el("tr-generate").hasAttribute("disabled"),
         "TR generate (Sana F1, computed): the disabled state is real (attribute present), not merely a class");
      var trInProgressResult = el("tr-gen-result");
      ok(!!trInProgressResult && !trInProgressResult.hidden && /still being recorded/.test(trInProgressResult.textContent),
         "TR generate (Sana F1): the operator is told WHY Generate is unavailable, before clicking anything");
      // A genuinely `disabled` button never fires its click listener at all in a real browser,
      // so clicking it here only proves the DOM's own disabled semantics — not that `onGenerate`
      // HAS its own guard (Sana security review, re-check: this exact gap in an earlier version
      // of this test). Prove the disabled attribute itself blocks the click first...
      var trInProgressCallsBefore = trCall("transcript_generate_notes").length;
      el("tr-generate").click();
      await sleep(30);
      ok(el("tr-gen-preview").hidden === true,
         "TR generate (Sana F1): clicking the disabled button never opens the review step");
      ok(trCall("transcript_generate_notes").length === trInProgressCallsBefore,
         "TR generate (Sana F1): clicking the disabled button never reaches the backend");
      // ...then prove `onGenerate`'s OWN `generateAllowed` check is what actually does the work,
      // by clearing the attribute (simulating a stale/replayed event bypassing it) and clicking
      // again — real defense in depth, not two assertions of the same DOM fact.
      el("tr-generate").disabled = false;
      el("tr-generate").click();
      await sleep(30);
      ok(el("tr-gen-preview").hidden === true && trCall("transcript_generate_notes").length === trInProgressCallsBefore,
         "TR generate (Sana F1, true defense in depth): with the disabled attribute forcibly cleared, onGenerate's OWN generateAllowed check still refuses — the backend refusal is not the only thing standing between a bypass and a call");
      el("tr-generate").disabled = true; // restore, so the next checks see the real state

      // Positive control: switching BACK to an ENDED transcript re-enables Generate — "disabled"
      // above is a real per-transcript check, not a mechanism that has gone permanently dead.
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      ok(el("tr-generate").disabled === false,
         "TR generate (Sana F1 positive control): an ENDED transcript re-enables Generate — the in-progress check is not stuck on");

      // (g) AC2: a transcript at/near the 400,000-character clamp gets a VISIBLE, documented
      // notice — never a silent cut. Seeds the dedicated oversize fixture (86akcffy0's own
      // fixture: 4,500 segments of a fixed 100-char body, exactly 454,499 characters joined —
      // deterministic so the exact drop count is asserted, not just "some truncation happened").
      window.__trSeedOversize = true;
      el("tr-detail-back").click();
      el("tr-retry").click(); // force loadList() to re-fetch — showList() alone does not
      await waitFor(function () { return el("tr-list").querySelectorAll('.tr-card[data-id="6"]').length === 1; });
      el('tr-list').querySelector('.tr-card[data-id="6"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      var trOversizeFull = window.__TR.detail[6].segments.map(function (s) { return s.text; }).join("\n");
      ok(trOversizeFull.length === 454499,
         "TR generate oversize (premise): the fixture's complete text is deterministically 454,499 characters, well past the 400,000 clamp");
      el("tr-generate").click();
      await sleep(40);
      var trOversizePreview = el("tr-gen-preview");
      ok(!!trOversizePreview && trOversizePreview.hidden === false, "TR generate oversize: the review step still opens for an over-the-clamp transcript");
      var trClampNotice = trOversizePreview.querySelector(".pp-gen-preview-clamp");
      ok(!!trClampNotice && getComputedStyle(trClampNotice).display !== "none",
         "TR generate oversize (AC2): a VISIBLE truncation notice is shown — not a silent cut");
      ok(/400,000-character limit/.test(trClampNotice.textContent) && /54,499 characters will be left out/.test(trClampNotice.textContent),
         "TR generate oversize (AC2): the notice states the real limit and the EXACT number of characters that will be left out");

      // (h) Vera performance review PERF-1: rendering the FULL, potentially multi-megabyte
      // transcript into one un-virtualised DOM text node forced real layout cost with no bound
      // (measured: ~0.10ms/KB, 320ms at 3MB) — and it contradicted this file's own bounded-
      // window promise. The rendered preview text must be bounded to `limit` characters, not the
      // fixture's full 454,499 — proving both the perf fix and that the preview shows EXACTLY
      // what will be sent (not a superset of it).
      var trOversizePreviewText = trOversizePreview.querySelector(".pp-gen-preview-text");
      ok(!!trOversizePreviewText && trOversizePreviewText.textContent.length === 400000,
         "TR generate oversize (Vera PERF-1): the rendered preview text is bounded to the 400,000-character limit, not the fixture's full 454,499");
      var trOversizeLeadDesc = trOversizePreview.querySelector(".pp-gen-preview-desc");
      ok(!!trOversizeLeadDesc && /The first 400,000/.test(trOversizeLeadDesc.textContent) && !/This exact text/.test(trOversizeLeadDesc.textContent),
         "TR generate oversize (Vera PERF-1): the lead sentence says the first 400,000 characters will be sent, not the false 'this exact text will be sent' claim for text that will actually be cut");
      el("tr-gen-preview-cancel").click();

      // (i) Cody code review (Medium): every new "TR generate"/"TR F-5" check above asserted
      // only the `.hidden` PROPERTY on `#tr-generate`/`#tr-gen-result`, never their COMPUTED
      // display — the exact hidden-attr-vs-CSS-display trap this webview has bitten before
      // (`.pp-gen-preview[hidden]`'s own fix, "M-1" elsewhere in this file), and deleting the new
      // `.tr-gen .pp-generate[hidden], .tr-gen .pp-gen-result[hidden] { display: none; }` rule in
      // app.css would not have turned any of them red. Return to transcript 1 (ended, no open
      // preview).
      //
      // 86akgqdxr changes what "before any generate" now means here: step (e) above already ran
      // a SUCCESSFUL generate against transcript 1, and the real backend (unlike the pre-86akgqdxr
      // mock) now PERSISTS that draft's real content — so reopening transcript 1 correctly shows
      // it painted immediately, without a fresh Generate click, exactly like a genuine restart
      // would (AC2). The pre-86akgqdxr version of this check asserted the OPPOSITE (result box
      // unpainted) because the mock never remembered a prior generate across a reopen; that
      // premise no longer holds, and asserting it would now be asserting a REGRESSION of AC2, not
      // a control on the M-1 CSS fix. The M-1 fix itself is still exercised two checks below (a
      // still-hidden `#tr-gen-preview` after Cancel closes the review step) and by the AC3 empty-
      // state checks in the "Detected scripture + saved sermon notes" section further down (a
      // transcript with NO draft still needs `#tr-gen-result` genuinely unpainted).
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      ok(getComputedStyle(el("tr-generate")).display !== "none",
         "TR generate (Cody, computed display): the Generate button is actually painted when not hidden");
      ok(getComputedStyle(el("tr-gen-result")).display !== "none" && /From-History Sermon/.test(el("tr-gen-result").textContent),
         "TR generate + 86akgqdxr (computed display): reopening a transcript with an earlier successful generate shows its PERSISTED draft painted immediately — this is AC2, not a regression of the M-1 fix (see the empty-state checks below for the still-unpainted case)");
      el("tr-generate").click();
      await sleep(30);
      ok(getComputedStyle(el("tr-generate")).display === "none",
         "TR generate (Cody, computed display): the Generate button is genuinely unpainted while its own review step is open");
      el("tr-gen-preview-cancel").click();

      // (j) Sana F2 (Medium), UPDATED for FR-129/86akgqdx8: `notes_generated` is real and
      // visible on this very screen — transcript 1 already has a persisted draft from the
      // earlier "(e)" check (the mock set `td2.notes_generated = true`). Before
      // regenerate-with-retention shipped, this notice warned Confirm would REPLACE the
      // existing draft outright. It no longer does that — Confirm now STAGES a new draft for
      // review instead — so the notice now says the true, safer thing: the operator will be
      // shown the new draft, and the saved one will not change unless they choose to use it.
      ok(el("tr-detail-notes").classList.contains("tr-notes-on"),
         "TR generate F2 (premise): transcript 1 already shows Notes generated from the earlier check");
      el("tr-generate").click();
      await sleep(30);
      var trOverwriteNotice = el("tr-gen-preview").querySelector(".pp-gen-preview-overwrite");
      ok(!!trOverwriteNotice && getComputedStyle(trOverwriteNotice).display !== "none" &&
         /will not change unless you choose to use it/.test(trOverwriteNotice.textContent),
         "TR generate (Sana F2 / FR-129): pressing Generate again on a transcript that already " +
         "has a draft tells the operator, before Confirm, that their saved notes will NOT change " +
         "unless they explicitly choose the new draft");
      ok(!/REPLACE/.test(trOverwriteNotice.textContent),
         "TR generate (FR-129 regression): the notice no longer claims an outright replace — that stopped being true when regenerate-with-retention shipped");
      el("tr-gen-preview-cancel").click();

      // (k) Sana F3 (Medium): a LATER selection must not let an EARLIER Confirm's result land
      // under it. Drive this with a deliberately deferred response (window.__trGenDeferred) so
      // the switch to transcript 2 happens WHILE transcript 1's call is still in flight, then
      // resolve it and confirm nothing from transcript 1 reached transcript 2's now-open view.
      window.__trGenDeferred = true;
      el("tr-generate").click();
      await sleep(30);
      el("tr-gen-preview-confirm").click();
      await sleep(30);
      ok(typeof window.__trGenResolveDeferred === "function",
         "TR generate F3 (setup): the call is genuinely pending, not already resolved");
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="2"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      ok(el("tr-generate").disabled === true,
         "TR generate F3 (setup): transcript 2 (still recording) is the one now open, its own disabled state showing");
      window.__trGenResolveDeferred();
      await sleep(40);
      ok(el("tr-gen-result").textContent.indexOf("From-History Sermon") === -1,
         "TR generate (Sana F3): transcript 1's stale, now-arrived result does not render under transcript 2's now-open view");
      ok(!el("tr-detail-notes").classList.contains("tr-notes-on"),
         "TR generate (Sana F3): transcript 2's own notes badge is not falsely flipped by transcript 1's stale completion");
      ok(el("tr-generate").disabled === true,
         "TR generate (Sana F3): transcript 1's stale completion does not re-enable transcript 2's (correctly disabled) Generate button");
      window.__trGenDeferred = false;

      // (l) Vera performance review PERF-2 (re-check): a fast double-click, both landing before
      // `note_generation_limits` resolves, must render the review step exactly ONCE, not twice
      // (a genuine risk: `onGenerate`'s own synchronous guards — `generating`, the preview's own
      // `hidden` state — do not change until the FIRST resolution actually opens the preview, so
      // nothing stops a second click from also calling `loadNoteCharLimit` before then). Resolve
      // BOTH pending calls (in order) rather than just one, so this proves the guard holds even
      // when every in-flight call eventually completes, not only the specific one a test happens
      // to resolve.
      el("tr-detail-back").click();
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      window.__resetNoteCharLimitForTest(); // force the UNCACHED path — every earlier check above already warmed it
      window.__trLimitsDeferred = true;
      window.__trLimitsPendingResolvers = [];
      var trOpenGenPreviewCountBefore = window.__trOpenGenPreviewCallCount;
      el("tr-generate").click();
      el("tr-generate").click();
      await sleep(20);
      ok(window.__trLimitsPendingResolvers.length === 2,
         "TR generate (Vera PERF-2, premise): two rapid clicks really did issue two concurrent note_generation_limits calls — onGenerate has no synchronous guard against this, which is exactly why the resolution-time check matters");
      window.__trLimitsPendingResolvers.forEach(function (resolve) { resolve(); });
      await sleep(30);
      ok(el("tr-gen-preview").hidden === false,
         "TR generate (Vera PERF-2): the preview opens once the deferred limits resolve");
      // NOT a DOM-node count: openGenPreview clears its container on every call, so two calls
      // back-to-back leave an IDENTICAL final DOM to one call — a node count would pass here
      // even with the guard deleted (confirmed: it did, on first attempt). The call counter is
      // the only signal that actually distinguishes "rendered once" from "rendered twice,
      // second call silently overwrote the first" — which is the real PERF-2 property (redundant
      // work), not a rendering-correctness one.
      ok(window.__trOpenGenPreviewCallCount === trOpenGenPreviewCountBefore + 1,
         "TR generate (Vera PERF-2): a fast double-click before the async limit resolves calls openGenPreview exactly ONCE, not twice, even though BOTH concurrent calls complete");
      window.__trLimitsDeferred = false;
      el("tr-gen-preview-cancel").click();

      // Restore shared consent state to its default (false): this section runs BEFORE the
      // dedicated "Settings → Providers & Privacy" section below, whose own checks assume the
      // untouched default consent-off state at the point they begin.
      window.__pp.cloud_notes_consent = false;
      el("tr-detail-back").click();

      // === Detected scripture + saved sermon notes (86akgqdxr; FR-130 remaining scope) ========
      // Opening transcript 7 (fixture: 2 detections + an already-saved draft) must show BOTH,
      // as real content — not the `notes_generated` status-only badge 86akcffvt shipped, and not
      // nothing at all for detections (86ajtxzrn's `detection` table was never surfaced before
      // this ticket). Seeded now (not from the top) for the same reason __trSeedRealistic/
      // __trSeedPhased/__trSeedOversize are seeded on request above, not unconditionally.
      window.__trSeedDetectionsFixture = true;
      el("tr-retry").click();
      await waitFor(function () { return el("tr-list").querySelectorAll(".tr-card").length >= 4; });
      el('tr-list').querySelector('.tr-card[data-id="7"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });

      // AC1: every detection persisted against the transcript renders — reference, confidence,
      // and an approximate position (resolved from the segment it was traced to, or "Position
      // unknown" for the documented 0/no-known-segment sentinel — never guessed at).
      ok(el("tr-detections-empty").hidden === true && getComputedStyle(el("tr-detections-empty")).display === "none",
         "TR detections (AC1): the empty state is hidden when detections exist (computed, not just the attribute)");
      ok(el("tr-det-log").hidden === false && getComputedStyle(el("tr-det-log")).display !== "none",
         "TR detections (AC1): the detections list is genuinely painted (computed) when detections exist");
      ok(window.__trDetRenderedRowCount() === 2, "TR detections (AC1): both persisted detections are mounted");
      var trDetRowsText = el("tr-det-rows").textContent;
      ok(/Romans 8:28/.test(trDetRowsText) && /95% match/.test(trDetRowsText),
         "TR detections (AC1): the known-segment detection shows its reference and confidence");
      ok(/John 3:16/.test(trDetRowsText) && /70% match/.test(trDetRowsText),
         "TR detections (AC1): the no-known-segment detection ALSO shows — it is not silently dropped");
      var trRow901 = window.__trDetRowFor(901), trRow902 = window.__trDetRowFor(902);
      ok(!!trRow901 && /00:04/.test(trRow901.textContent),
         "TR detections (AC1): a detection traced to a known segment shows that segment's timestamp as its approximate position (segment 702 starts at 4s)");
      ok(!!trRow902 && /Position unknown/.test(trRow902.textContent),
         "TR detections (AC1): a detection with the documented 0/no-known-segment sentinel says so honestly, rather than guessing a position");

      // AC2: the saved draft's ACTUAL content shows — not just a "Notes generated" badge — and
      // is editable from this same screen via the ALREADY-transcript-id-generic
      // `update_sermon_note_draft` command (86akgqdv0/86akby820's own vocabulary, reused
      // unchanged: caveats/scripture_verdicts/empty_requested).
      ok(el("tr-notes-empty").hidden === true, "TR notes (AC2): the empty state is hidden when a draft exists");
      var trNotesResult = el("tr-gen-result");
      ok(!trNotesResult.hidden && /Fixture Sermon/.test(trNotesResult.textContent) &&
         /A saved draft's real content, not just a badge\./.test(trNotesResult.textContent),
         "TR notes (AC2): the saved draft's real title and summary render, not only notes_generated");
      ok(/Faith/.test(trNotesResult.textContent), "TR notes (AC2): the draft's real section content renders");
      ok(/AI-generated draft/.test(trNotesResult.textContent) && /invent quotations/.test(trNotesResult.textContent),
         "TR notes (AC2/FR-128): the AI-generated label and fabrication disclosure travel with a RELOADED draft, not only a freshly generated one");
      ok(!!trNotesResult.querySelector(".pp-gen-scr-verified"),
         "TR notes (86akby820 vocabulary reused): a verified scripture reference carries its explicit checkmark, same as the live-session panel");
      // 86akgqdwc (Sana F2 on PR #48; gap caught by Cody's delta re-check on this ticket):
      // settings.js already rendered the draft-wide "scripture_verification_incomplete" note;
      // transcripts.js did not, despite its own header comment claiming the wire vocabulary is
      // reused unchanged. The fixture above now carries this caveat — real regression coverage,
      // not the throwaway probe Cody used to prove the gap.
      var trIncompleteNote = Array.prototype.filter.call(
        trNotesResult.querySelectorAll(".pp-gen-scripture-note"),
        function (p) { return /more scripture references than could be checked/.test(p.textContent); }
      )[0];
      ok(!!trIncompleteNote && getComputedStyle(trIncompleteNote).display !== "none" &&
         trIncompleteNote.getAttribute("role") === "note",
         "TR notes (86akgqdwc): the scripture-verification-incomplete note renders on the " +
         "Transcripts surface too, computed-visible, role=note — not just in Settings");
      // POSITIVE CONTROL: the draft's own content (asserted above — title, summary, section
      // text, the verified checkmark) still renders alongside the new note, so this is an
      // addition, not a replacement.
      ok(/Faith/.test(trNotesResult.textContent) && !!trNotesResult.querySelector(".pp-gen-scr-verified"),
         "TR notes (86akgqdwc, positive control): the draft's own content still renders " +
         "alongside the incomplete-verification note");
      var trEditBtn = document.getElementById("tr-gen-edit");
      ok(!!trEditBtn, "TR notes (editable workspace): Edit is reachable for a saved draft opened from the Transcripts list, not only the Settings panel");

      // Editing: same `update_sermon_note_draft` command, this transcript's id (7) — the edit
      // form and Save/Cancel wiring mirror settings.js's own (ported), with `tr-` prefixed ids so
      // neither panel's `document.getElementById` can resolve to the other's node.
      trEditBtn.click();
      ok(!!document.querySelector(".pp-gen-edit-form") && !document.getElementById("tr-gen-edit"),
         "TR notes: Edit swaps the view for the edit form (Edit itself is gone while editing)");
      var trTitleInput = document.getElementById("tr-edit-title");
      ok(!!trTitleInput && trTitleInput.value === "Fixture Sermon", "TR notes: the edit form is pre-filled with the real saved title");
      trTitleInput.value = "Edited Fixture Sermon";
      var trSaveCallsBefore = window.__calls.filter(function (c) { return c.cmd === "update_sermon_note_draft"; }).length;
      document.getElementById("tr-gen-save").click();
      await waitFor(function () { return window.__calls.filter(function (c) { return c.cmd === "update_sermon_note_draft"; }).length > trSaveCallsBefore; });
      await sleep(30);
      var trSaveCall = window.__calls.filter(function (c) { return c.cmd === "update_sermon_note_draft"; }).slice(-1)[0];
      ok(!!trSaveCall && trSaveCall.args.transcriptId === 7,
         "TR notes: Save calls update_sermon_note_draft with THIS transcript's id — the same command the Settings panel already uses, unchanged");
      ok(!document.querySelector(".pp-gen-edit-form") && /Edited Fixture Sermon/.test(el("tr-gen-result").textContent),
         "TR notes: a successful save re-renders the view with the edited title, form closed");
      ok(!!document.getElementById("tr-gen-edit"), "TR notes: Edit is reachable again after a save");
      ok(el("tr-detail-notes").classList.contains("tr-notes-on"),
         "TR notes: the notes badge still reads generated after an edit — editing a draft is not the same as un-generating it");

      // TR 86akc0tua parity (bfedaf2's fix, ported): this ticket's own edit surface reaches the
      // SAME update_sermon_note_draft call as settings.js's, via the SAME transcript-id-generic
      // command — so it needs the identical client-side caveated-empty-section filter settings.js
      // already carries. The just-completed save above did not touch "Prayer points" (empty,
      // empty_requested:true in the fixture): it must never have reached the payload, while the
      // populated "Main points" section (edited via the title-only change above, itself untouched)
      // still does (positive control) — proves the filter drops the RIGHT section, not every one.
      ok(!trSaveCall.args.sections.some(function (s) { return s.heading === "Prayer points"; }),
         "TR notes (86akc0tua parity, edit-save fix): a caveated-empty section the operator did " +
         "not fill in is NEVER sent to update_sermon_note_draft from the Transcripts workspace " +
         "either — the same bug bfedaf2 fixed for the Settings panel, ported to this ticket's own " +
         "edit surface");
      ok(trSaveCall.args.sections.some(function (s) { return s.heading === "Main points"; }),
         "TR notes (positive control): an ordinary populated section is NOT dropped by the same " +
         "filter — without this, the assertion above could pass on a mechanism that drops every " +
         "section");

      // Correction layer (86akgqdxr; "reachable from one screen", read-only in this ticket — see
      // the linked follow-up for actual editing): transcript 7's segment 701 carries an existing
      // correction. Both the raw and corrected text must render — a correction is an overlay,
      // never a silent rewrite of the immutable raw stream.
      var trCorrectedRow = window.__trRowFor(701);
      ok(!!trCorrectedRow && trCorrectedRow.classList.contains("tr-line-corrected"),
         "TR correction layer: a segment with an existing correction is marked as corrected");
      ok(!!trCorrectedRow && /Good morning, church\./.test(trCorrectedRow.textContent),
         "TR correction layer: the RAW segment text still renders — a correction never hides the original");
      ok(!!trCorrectedRow && /Good morning, everyone\./.test(trCorrectedRow.textContent),
         "TR correction layer: the corrected text also renders");
      var trUncorrectedRow = window.__trRowFor(702);
      ok(!!trUncorrectedRow && !trUncorrectedRow.classList.contains("tr-line-corrected"),
         "TR correction layer: a segment with NO correction renders exactly as before (no false positive)");
      // Cody, PR #50 (High): --sc-text-muted measured 3.79:1 on this ground, failing AA-normal —
      // the raw (struck-through) text is essential content, not decorative, since the whole point
      // of the overlay is that neither the raw nor the corrected text is hidden. No prior check
      // covered this element's contrast, unlike every other new text this ticket added.
      var trRawTxtC = _trCr(_trRgba(getComputedStyle(trCorrectedRow.querySelector(".tr-line-txt-raw")).color), _trRgba(getComputedStyle(el("tr-detail-log")).backgroundColor));
      ok(trRawTxtC >= 4.5, "TR correction layer (NFR-020): the raw (struck-through) text clears AA-NORMAL on the log's ground (" + _trF(trRawTxtC) + ":1)");

      // AC3: no detections / no draft shows a CLEAR empty state, not a blank area — reopening
      // transcript 2. NOT transcript 1: an earlier "TR generate" check (e) already ran a
      // successful generate against transcript 1, and 86akgqdxr means that draft now correctly
      // PERSISTS across a reopen (see that check's own updated comment) — so transcript 1 no
      // longer has "no draft" by this point in the continuous script. Transcript 2 is still
      // recording (`ended_at_ms: null`) for its entire life in this fixture, so Generate is
      // disabled for it throughout and nothing in this script can ever attach a draft to it —
      // it is genuinely draft-less and detection-less at every point, not just by coincidence
      // of test ordering.
      el('tr-list').querySelector('.tr-card[data-id="2"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });
      ok(el("tr-detections-empty").hidden === false && getComputedStyle(el("tr-detections-empty")).display !== "none" &&
         /No scripture references were detected/.test(el("tr-detections-empty").textContent),
         "TR detections (AC3): a clear, non-blank empty state when there are none (computed, not just the attribute)");
      ok(el("tr-det-log").hidden === true && getComputedStyle(el("tr-det-log")).display === "none",
         "TR detections (AC3): the (empty) list itself is genuinely unpainted, not just visually collapsed");
      ok(el("tr-notes-empty").hidden === false && getComputedStyle(el("tr-notes-empty")).display !== "none" &&
         /No sermon notes have been generated/.test(el("tr-notes-empty").textContent),
         "TR notes (AC3): a clear, non-blank empty state when no draft exists yet (computed, not just the attribute)");

      // NFR-019 (keyboard parity): the detections list is a native keyboard-scrollable region
      // once focused, same shape as the transcript log above.
      ok(el("tr-det-log").getAttribute("role") === "list" && el("tr-det-log").getAttribute("tabindex") === "0",
         "TR detections (NFR-019): the panel is a native keyboard-scrollable/focusable region");
      // Contrast (NFR-020): the detections panel's own text clears AA-NORMAL against its ground —
      // reopen transcript 7 (has real rows to measure against).
      el('tr-list').querySelector('.tr-card[data-id="7"] .tr-card-open').click();
      await waitFor(function () { return window.__trDetRenderedRowCount && window.__trDetRenderedRowCount() > 0; });
      var trDetRowEl = window.__trDetRowFor(901);
      var trDetRefC = _trCr(_trRgba(getComputedStyle(trDetRowEl.querySelector(".tr-det-ref")).color), _trRgba(getComputedStyle(el("tr-det-log")).backgroundColor));
      ok(trDetRefC >= 4.5, "TR detections (NFR-020): the reference text clears AA-NORMAL on the panel's ground (" + _trF(trDetRefC) + ":1)");
      var trDetConfC = _trCr(_trRgba(getComputedStyle(trDetRowEl.querySelector(".tr-det-conf")).color), _trRgba(getComputedStyle(el("tr-det-log")).backgroundColor));
      ok(trDetConfC >= 4.5, "TR detections (NFR-020): the confidence text clears AA-NORMAL on the panel's ground (" + _trF(trDetConfC) + ":1)");
      el('tr-list').querySelector('.tr-card[data-id="1"] .tr-card-open').click();
      await waitFor(function () { return el("tr-detections-empty").hidden === false; });
      var trEmptyC = _trCr(_trRgba(getComputedStyle(el("tr-detections-empty")).color), _trRgba(getComputedStyle(el("tr-detections-empty")).backgroundColor));
      ok(trEmptyC >= 4.5, "TR detections empty state (NFR-020): its text clears AA-NORMAL on its own background (" + _trF(trEmptyC) + ":1)");

      // AC5: a transcript with far more detections than the LIVE console's own MAX_DETECTIONS=32
      // queue cap renders COMPLETELY (every one reachable by scrolling) without unbounded DOM
      // growth — bounded, fixed-row-height sliding window (transcripts.js). Mutation-verified
      // against two isolated `SELAHCUE_OPERATOR_DIST` copies, whole suite running (never
      // `--exact`), both restored after:
      //   (1) `renderDetections` mutated to `renderDetWindow(0, dets.length)` (ignore
      //       DET_WINDOW_ROWS) — turns RED exactly the bound check and the initial-open positive
      //       control (120 mounted, last detection present on open); every sibling check,
      //       including the scroll-driven ones below, stays GREEN.
      //   (2) `recomputeDetWindow()` calls in `onDetScroll` and `__trDetScrollToFraction`
      //       commented out (scroll-driven recompute disabled) — turns RED exactly the three
      //       scroll-driven assertions below (end-scroll eviction/mount, middle-scroll neither
      //       end); the initial-open assertions above stay GREEN, confirming they exercise a
      //       DIFFERENT code path than these three.
      // 1410 checks total in both runs, only the named ones move — no vacuous over-broad mutant.
      //
      // Vera, PR #50 (V-3): the three scroll-driven checks above are ALL driven through
      // `__trDetScrollToFraction`, which calls `recomputeDetWindow()` DIRECTLY — the same "control
      // reads a copy" trap `implementation/desktop/CLAUDE.md` documents. Mutant (2) disabled BOTH
      // call sites (`onDetScroll`'s and the test hook's) together, so it proves ONE of the two
      // matters, not that the REAL `scroll` → `onDetScroll` → rAF path does anything — disabling
      // only `onDetScroll`'s call passes unchanged (Vera measured this live). The check below
      // bypasses the test hook entirely, using the SAME proven-safe idiom the "TR measureObserver
      // disconnect" block above already established for this exact class of problem: this harness
      // runs under Chrome's `--virtual-time-budget`, where racing REAL rAF timing is unreliable
      // and can crash the whole suite rather than just fail one check (documented above, hard-won).
      // A genuine `scroll` event runs `onDetScroll()` synchronously, which calls
      // `requestAnimationFrame(cb)` — intercepted here to CAPTURE `cb` instead of letting the
      // browser schedule it, then invoked directly on our own schedule. This exercises the real
      // listener wiring (proven by asserting the callback was actually captured) without racing
      // frame timing.
      window.__trSeedManyDetections = true;
      el("tr-retry").click();
      await waitFor(function () { return el("tr-list").querySelectorAll(".tr-card").length >= 5; });
      el('tr-list').querySelector('.tr-card[data-id="8"] .tr-card-open').click();
      await waitFor(function () { return window.__trDetRenderedRowCount && window.__trDetRenderedRowCount() > 0; });
      ok(window.__trDetRenderedRowCount() <= 40,
         "TR detections bounded (AC5): far fewer than 120 detections are ever mounted as real DOM nodes at once");
      ok(window.__trDetRowFor(40119) === null,
         "TR detections bounded (AC5, positive control): the LAST detection is NOT mounted on initial open — this is a real window, not all 120 rendered and hidden");
      var trDetLogEl = el("tr-det-log");
      var trDetOrigRaf = window.requestAnimationFrame;
      var trDetCapturedCb = null;
      try {
        window.requestAnimationFrame = function (cb) { trDetCapturedCb = cb; return 1; };
        var trDetMax = Math.max(0, trDetLogEl.scrollHeight - trDetLogEl.clientHeight);
        trDetLogEl.scrollTop = trDetMax; // a REAL scroll to the end, NOT the test hook
        trDetLogEl.dispatchEvent(new Event("scroll")); // onDetScroll() runs synchronously here
      } finally {
        window.requestAnimationFrame = trDetOrigRaf;
      }
      ok(typeof trDetCapturedCb === "function",
         "TR detections bounded (AC5, real scroll event, setup): the real scroll event reached " +
         "onDetScroll and scheduled its rAF-coalesced recompute — captured directly rather than " +
         "racing real frame timing under this harness's --virtual-time-budget");
      // Vera, PR #50 (V-6, LOW): guarded rather than called unconditionally — if the assertion
      // above ever goes red (nothing captured), calling a null callback threw and aborted the
      // whole driver mid-script (EXPECTED_MIN_CHECKS still caught the resulting shrink and failed
      // safe, but as "most of the suite vanished" rather than named reds — the exact noisy-failure
      // shape this block's own capture idiom exists to avoid in the first place).
      if (typeof trDetCapturedCb === "function") trDetCapturedCb(); // run the REAL captured callback —
                          // the same recomputeDetWindow() call onDetScroll's own rAF frame would
                          // make, on our own deterministic schedule
      ok(window.__trDetRowFor(40000) === null,
         "TR detections bounded (AC5, real scroll event): the real onDetScroll → rAF path evicts " +
         "the FIRST detection from the DOM — not just the test hook's direct call");
      ok(window.__trDetRowFor(40119) !== null,
         "TR detections bounded (AC5, real scroll event, positive control): the same real path " +
         "mounts the LAST detection — every detection stays reachable through genuine scrolling");
      window.__trDetScrollToFraction(1);
      await sleep(20);
      ok(window.__trDetRowFor(40000) === null,
         "TR detections bounded (AC5): scrolling to the end evicts the FIRST detection from the DOM");
      ok(window.__trDetRowFor(40119) !== null,
         "TR detections bounded (AC5, positive control): scrolling to the end mounts the LAST detection — every detection stays reachable by scrolling, none truncated to a sample");
      window.__trDetScrollToFraction(0.5);
      await sleep(20);
      ok(window.__trDetRowFor(40000) === null && window.__trDetRowFor(40119) === null,
         "TR detections bounded (AC5): scrolling to the middle mounts neither end — confirms a real sliding window, not two static halves");

      el("tr-detail-back").click();

      // === Timestamp-linked note items (86akgqdw0; FR-124; ADR-0026 rev 4) ====================
      // Clicking a chapter marker's timestamp jumps the transcript log to it. This is the ONE
      // place transcripts.js is allowed to write `scrollTop` outside `init`/`test-hook`
      // (`D5-exempt(jump)`) — a click handler, never `scroll`/`wheel`/`keydown`/an animation
      // frame, so it cannot race an in-flight native scroll animation the way ADR-0026's D5
      // exists to forbid. Three items exercise this ticket's own adversarial-fixture acceptance
      // criterion: a REAL match, an out-of-range-but-numeric offset (past every real segment),
      // and a malformed (non-numeric) offset.
      window.__trSeedTimestampsFixture = true;
      el("tr-retry").click();
      await waitFor(function () { return el("tr-list").querySelectorAll(".tr-card").length >= 5; });
      el('tr-list').querySelector('.tr-card[data-id="8"] .tr-card-open').click();
      await waitFor(function () { return window.__trRenderedRowCount && window.__trRenderedRowCount() > 0; });

      var tsResult = el("tr-gen-result");
      var tsBadges = tsResult.querySelectorAll(".tr-item-ts");
      ok(tsBadges.length === 3,
         "TR timestamps (adversarial fixture): exactly three of the four chapter markers carry a " +
         "badge — 'Opening prayer' (real match), 'Far future' (out-of-range but numeric) and " +
         "'Deep in the service' (a real, genuinely unmounted match); 'Bogus type' (non-numeric " +
         "offset) gets none at all, never a broken one");
      ok(tsResult.textContent.indexOf("Bogus type") !== -1,
         "TR timestamps (adversarial fixture): the malformed item's OWN text still renders — only " +
         "its timestamp badge is missing");
      // S2 (Sana, PR #51 security review): checked FIRST, before any other click in this block
      // moves the virtualizer's window — every jump exercised below this point in the ORIGINAL
      // fixture landed within a 3-segment log where every row was ALREADY mounted (well under
      // WINDOW_ROWS), the trivial case, not the one ADR-0026 rev 4's `D5-exempt(jump)` exists for
      // ("the target row may not be mounted"). `tsFillerSegs` (300 segments) makes the "Deep in
      // the service" marker's target genuinely unmounted on the pristine, just-opened window —
      // verified explicitly below, not assumed.
      ok(window.__trRowFor(window.__trTsDeepId) === null,
         "TR timestamps (S2 setup): the deep target segment is genuinely UNMOUNTED before the " +
         "jump — the actual case this ADR revision exists for, not a trivially-already-visible row");
      var tsDeepBtn = Array.prototype.filter.call(tsBadges, function (b) { return b.textContent === "13:35"; })[0];
      ok(!!tsDeepBtn, "TR timestamps (S2): the deep marker's badge renders with its real, far-future timestamp");
      tsDeepBtn.click();
      ok(window.__trJumpTargetSegId() === window.__trTsDeepId,
         "TR timestamps (S2): clicking a badge for an UNMOUNTED target still jumps to the segment it actually matched");
      var tsDeepRow = window.__trRowFor(window.__trTsDeepId);
      ok(!!tsDeepRow && tsDeepRow.classList.contains("tr-line-jump-target"),
         "TR timestamps (S2): the target row is now MOUNTED — the virtualizer's window re-rendered " +
         "around it, not merely scrolled toward a row that was never there — and highlighted");
      var tsDeepMaxScroll = Math.max(0, el("tr-detail-log").scrollHeight - el("tr-detail-log").clientHeight);
      ok(el("tr-detail-log").scrollTop >= 0 && el("tr-detail-log").scrollTop <= tsDeepMaxScroll,
         "TR timestamps (S2): the resulting scrollTop stays within the log's real scrollable range " +
         "even for a jump the virtualizer had to remount for");
      ok(el("tr-detail-log").scrollTop === window.__trOffsetAt(203),
         "TR timestamps (S2): scrollTop is set to exactly the newly-mounted window's own computed " +
         "offset for the target row (D1's metric) — segment index 203 (3 real + 200 filler), the " +
         "same value jumpToOffsetMs itself reads immediately after remounting");

      var tsOpenBtn = Array.prototype.filter.call(tsBadges, function (b) { return b.textContent === "00:04"; })[0];
      ok(!!tsOpenBtn, "TR timestamps: the real match shows its transcript timestamp (segment 802 starts at 4s)");
      // Verification expectation (this ticket's own): "asserted on computed style" — a real,
      // painted, genuinely clickable affordance, not merely a class name with no visual effect.
      ok(getComputedStyle(tsOpenBtn).cursor === "pointer",
         "TR timestamps: the badge is computed as genuinely clickable (cursor: pointer)");
      ok(tsOpenBtn.getAttribute("aria-label").indexOf("00:04") !== -1,
         "TR timestamps: the badge names the time it jumps to in its accessible label");

      // Click it: jumps to segment 802 (id 802, start_ms 4000) and highlights it. The S2 jump
      // above already moved the mounted window away from segment 802 (index 1) — this click's
      // own remount (`jumpToOffsetMs`'s own `renderWindow` call, exercised for real, not assumed)
      // is what brings it back, so the assertion below is on the EXACT scrollTop the jump
      // computed, not merely "it moved" and not resting on any assumption about what was already
      // mounted going in.
      tsOpenBtn.click();
      ok(window.__trJumpTargetSegId() === 802,
         "TR timestamps: clicking the real-match badge jumps to the segment it actually matched");
      var tsJumpRow = window.__trRowFor(802);
      ok(!!tsJumpRow && tsJumpRow.classList.contains("tr-line-jump-target"),
         "TR timestamps: the landed-on row carries the jump-target highlight class");
      ok(el("tr-detail-log").scrollTop === window.__trOffsetAt(1),
         "TR timestamps: the log's scrollTop is set to EXACTLY the target row's own computed " +
         "offset (D1's exact metric), not an approximation");
      // Computed-style proof the highlight is REAL paint, not a dead class name: a highlighted
      // row's background must differ from an un-highlighted sibling's.
      var tsNonJumpRow = window.__trRowFor(801);
      ok(getComputedStyle(tsJumpRow).backgroundColor !== getComputedStyle(tsNonJumpRow).backgroundColor,
         "TR timestamps: the jump-target row's computed background genuinely differs from a " +
         "non-target row's — the highlight class has real visual effect, not just a name");

      // Adversarial: an out-of-range-but-numeric offset (99999999999 — past every real segment,
      // INCLUDING the 300 filler ones added for S2 above) must clamp to the nearest real
      // position, never crash and never scroll to something nonsensical. The last of the 303
      // segments is the final filler row, id 900299 (900000 + tsi for tsi up to 299).
      // fmtTimestamp's own format includes an hour component (`h + ":" + mm + ":" + ss`) only
      // when h > 0 — true only of "Far future"'s raw, unclamped offset_ms (99999999999 ≈
      // 3170 years, badge text like "27777:46:40"); "Opening prayer" (00:04) and "Deep in the
      // service" (13:35) both stay under an hour, so this uniquely identifies it without
      // hardcoding the exact digits.
      var tsFarBtn = Array.prototype.filter.call(tsBadges, function (b) { return /^\d+:\d\d:\d\d$/.test(b.textContent); })[0];
      ok(!!tsFarBtn && tsFarBtn !== tsOpenBtn && tsFarBtn !== tsDeepBtn,
         "TR timestamps (setup): the 'Far future' badge (the only one with an hours component) " +
         "is a distinct element from the other two");
      tsFarBtn.click();
      ok(window.__trJumpTargetSegId() === 900299,
         "TR timestamps (adversarial fixture): an out-of-range offset clamps to the LAST real " +
         "segment — a bounded, sane landing, never an out-of-bounds index and never a crash");
      var tsMaxScroll = Math.max(0, el("tr-detail-log").scrollHeight - el("tr-detail-log").clientHeight);
      ok(el("tr-detail-log").scrollTop <= tsMaxScroll,
         "TR timestamps (adversarial fixture): the resulting scrollTop is within the log's real " +
         "scrollable range — never an absurd value the browser itself has to clamp silently");

      // Clicking a jump badge is the one write ADR-0026 rev 4 permits outside init/test-hook —
      // confirmed structurally (not just behaviourally) by the D5 static check elsewhere in
      // this file's own source-text checks, run independently of this browser session.

      el("tr-detail-back").click();

      // === Pre-service Check (moved into the Settings sidebar, Design 2.0) ===
      document.querySelector('.nav-item[data-surface="settings"]').click();
      document.querySelector('.set-nav[data-setpage="preservice"]').click();
      ok(el("surface-preservice").classList.contains("active"), "Pre-service: the Settings sidebar entry opens the surface");
      await waitFor(function(){ return document.querySelectorAll("#ps-sections .ps-row").length >= 10 && el("ps-passed").textContent !== "0"; });
      ok(document.querySelectorAll("#ps-sections .ps-row").length === 10,
         "Pre-service: all 10 checks render across the four sections");
      ok(document.querySelectorAll("#ps-sections .ps-section").length === 4,
         "Pre-service: four grouped sections (Displays / Media / Audio / Storage)");
      ok(el("ps-passed").textContent === "5" && el("ps-warnings").textContent === "1" && el("ps-blocking").textContent === "0",
         "Pre-service: readiness counts derive from live host data (5 passed · 1 warning · 0 blocking)");
      var psStt = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Transcription & AI/.test(r.textContent); });
      ok(psStt && psStt.querySelector(".ps-ico-ok") && /On-device STT ready/.test(psStt.textContent),
         "Pre-service: on-device STT ready reflects the real stt_ready probe");
      var psAudio = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Input device/.test(r.textContent); });
      ok(psAudio && psAudio.querySelector(".ps-ico-ok") && /Focusrite/.test(psAudio.textContent),
         "Pre-service: Input device reflects the real audio_input probe (device name)");
      // STT model missing → the check becomes an attention warning (not a fabricated pass).
      window.__psStt = {ready:false, state:"not_downloaded", model:"Small", detail:"On-device model not downloaded yet"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Transcription & AI/.test(x.textContent);}); return r && r.querySelector(".ps-ico-warn"); });
      ok(true, "Pre-service: stt_ready 'not downloaded' → attention warning (honest, not a pass)");
      window.__psStt = null;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-passed").textContent === "5"; });
      // No input device → the Input device check becomes an attention warning (not a fabricated pass).
      window.__psAudio = {available:false, state:"no_device", name:"", channels:null, detail:"No microphone / input device detected"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Input device/.test(x.textContent);}); return r && r.querySelector(".ps-ico-warn"); });
      ok(true, "Pre-service: audio_input 'no device' → attention warning (honest, not a pass)");
      // Default (no-STT) build → 'not_in_build' → honest PENDING, never a fabricated pass.
      window.__psAudio = {available:false, state:"not_in_build", name:"", channels:null, detail:"Audio input check is not enabled in this build"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Input device/.test(x.textContent);}); return r && r.querySelector(".ps-ico-pending"); });
      var psAudioNib = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Input device/.test(x.textContent);});
      ok(psAudioNib && psAudioNib.querySelector(".ps-ico-pending") && el("ps-passed").textContent === "4",
         "Pre-service: audio_input 'not_in_build' → honest pending, not counted as passed (default build)");
      window.__psAudio = null;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-passed").textContent === "5"; });
      ok(el("ps-verdict").textContent === "Safe to start" && el("ps-verdict-card").getAttribute("data-state") === "ok",
         "Pre-service: 0 blocking → Safe to start (green verdict)");
      ok(document.querySelectorAll("#ps-review .ps-review-card").length === 1,
         "Pre-service: the one warning surfaces as a Review-before-start card");
      var psMediaRow = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Slide media present/.test(r.textContent); });
      ok(psMediaRow && psMediaRow.querySelector(".ps-ico-warn") && psMediaRow.querySelector(".ps-row-action"),
         "Pre-service: missing-media check is a warning with a Locate fix action");
      ok(document.querySelectorAll("#ps-sections .ps-ico-pending").length >= 4,
         "Pre-service: subsystems the host doesn't expose yet show an honest 'not checked' state (never faked)");
      ok(!el("ps-start").disabled, "Pre-service: Start service enabled when nothing is blocking");
      // A BLOCKING check (disk critically low) flips the verdict to Not-safe and disables Start.
      window.__psDiskLow = true;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-blocking").textContent !== "0"; });
      ok(el("ps-blocking").textContent === "1" && el("ps-verdict").textContent === "Not safe to start"
         && el("ps-verdict-card").getAttribute("data-state") === "block" && el("ps-start").disabled,
         "Pre-service: a blocking check → Not safe to start, red verdict, Start disabled");
      ok(/Disk space/.test((document.querySelector("#ps-review .ps-review-block") || {}).textContent || ""),
         "Pre-service: the blocking check leads the Review-before-start list");
      window.__psDiskLow = false;
      // NO output window connected → never a green 'Safe to start'; Start is gated.
      window.__psNoHost = true;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-verdict").textContent === "No output window"; });
      ok(el("ps-start").disabled && el("ps-verdict-card").getAttribute("data-state") === "pending",
         "Pre-service: no output window → not ready, Start disabled (never a false 'Safe to start')");
      var psNet = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Local network & remotes/.test(r.textContent); });
      ok(psNet && psNet.querySelector(".ps-ico-pending"),
         "Pre-service: network reads 'not checked' with no host (no fabricated green)");
      window.__psNoHost = false;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-verdict").textContent === "Safe to start"; });
      el("ps-start").click();
      ok(el("surface-console").classList.contains("active"), "Pre-service: Start service goes to the Live Console");
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"K", metaKey:true, shiftKey:true, bubbles:true}));
      ok(el("surface-preservice").classList.contains("active"),
         "Pre-service: ⌘⇧K jumps to the surface (now reached from the Settings sidebar)");

      // === Remote Control (Figma 359:124) — now reached from Settings › Network & Mobile (it left the
      // top-nav, Figma 336:124), not a top-level nav item: pair/approve/role/revoke ===
      ok(!document.querySelector('.nav-item[data-surface="remote"]'),
         "Nav: Remote Control is no longer a top-level nav item (moved under Settings, Figma 336:124)");
      document.querySelector('.nav-item[data-surface="settings"]').click();
      setSettingsPage("network");
      ok(document.getElementById("set-page-network") && !document.getElementById("set-page-network").hidden,
         "Settings: the Network & Mobile page renders");
      document.getElementById("set-open-remote").click();
      ok(el("surface-remote").classList.contains("active"),
         "Settings › Network & Mobile → 'Manage devices' opens the Remote Control surface");
      var rcN0 = +el("rc-count-n").textContent;
      ok(document.querySelectorAll("#rc-rows .rc-row").length === rcN0 && rcN0 >= 1,
         "Remote: the paired-devices table renders and the count chip matches");
      var rcPend = document.querySelector("#rc-pending .rc-pending-card");
      ok(!!rcPend, "Remote: a pending pair request is shown with a role picker");
      rcPend.querySelector(".rc-approve").click();
      ok(document.querySelectorAll("#rc-pending .rc-pending-card").length === 0 &&
         +el("rc-count-n").textContent === rcN0 + 1,
         "Remote: Approve moves the request into paired devices (" + rcN0 + "→" + el("rc-count-n").textContent + ")");
      var rcRevs = document.querySelectorAll("#rc-rows .rc-revoke");
      var rcRb = rcRevs[rcRevs.length - 1];
      var rcRows0 = document.querySelectorAll("#rc-rows .rc-row").length;
      rcRb.click();
      ok(rcRb.classList.contains("armed"), "Remote: first Revoke click arms a two-step confirm (destructive)");
      rcRb.click();
      ok(document.querySelectorAll("#rc-rows .rc-row").length === rcRows0 - 1,
         "Remote: second Revoke click removes the device");
      document.querySelector('.nav-item[data-surface="console"]').click();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"R", metaKey:true, shiftKey:true, bubbles:true}));
      ok(el("surface-settings").classList.contains("active") && !document.getElementById("set-page-network").hidden,
         "Remote: ⌘⇧R now opens Settings › Network & Mobile (Remote left the top-nav; ⌘1–7 map intact)");

      // === Service Plan builder (86ajxxuz9, Figma 614:124) — the `plan` surface is a real
      // builder (palette · run sheet · inspector) with link status + link/unlink flows, and a
      // plan edit NEVER changes Live. The CI driver never navigated here before, so the builder
      // + link states had zero behavioural coverage; these checks close that gap. ==============
      var isLiveCtrl = function(c){ return ["go_live","next","select","blackout","clear","start_timer"].indexOf(c.cmd) >= 0; };
      var ctrlBefore = window.__calls.filter(isLiveCtrl).length;
      // #6/#7 fix: the console resolves deck-link chips at BOOT (planDecks loaded WITHOUT ever
      // visiting the plan surface). No plan nav has happened yet, so a non-null resolution here
      // proves the boot-time load; the boot fixture's deck id 2 is "Sermon: Grace That Feeds".
      ok(typeof planDeckName === "function" && planDeckName(2) === "Sermon: Grace That Feeds",
         "SP C-001: the console resolves deck-link names at boot (planDecks loaded before any plan visit)");
      // This block owns its deck fixture: an earlier library test empties __LIB.decks (the
      // 'No presentations yet' state), so restore a known list BEFORE planActivate loads it —
      // deck-link chips resolve names from deck_list, and the picker lists these decks.
      window.__LIB = window.__LIB || {};
      window.__LIB.decks = [{id:2, name:"Sermon: Grace That Feeds", slides:2}, {id:5, name:"Youth Night — Identity", slides:12}];
      window.__LIB.open = 2; window.__LIB.persistent = true; window.__LIB.nextId = 6;
      document.querySelector('.nav-item[data-surface="plan"]').click(); // showSurface("plan") → planActivate
      ok(el("surface-plan").classList.contains("active"), "SP: the plan nav opens the Service Plan builder surface");
      await sleep(60); // let planActivate resolve invoke("view") + invoke("deck_list") (deck names for chips)
      // C-002: the three builder regions replace the placeholder.
      var palette = el("plan-palette-btns");
      ok(palette && palette.querySelectorAll(".plan-palette-btn").length === 7,
         "SP C-002: the Add-item palette lists all 7 item kinds (got " + (palette ? palette.querySelectorAll(".plan-palette-btn").length : "none") + ")");
      ok(!!el("plan-b-list") && !!el("plan-b-insp"), "SP C-002: the run sheet + item inspector regions exist");
      // Palette wiring: clicking a kind sends add_item{kind,title}.
      palette.querySelector('.plan-palette-btn').click();
      await sleep(20);
      ok(window.__calls.some(function(c){return c.cmd==="add_item";}), "SP: a palette button sends add_item to the host");
      // ⌘Z / ⌘⇧Z on the plan surface drive the backend-authoritative run-sheet undo/redo.
      var __pu = window.__calls.length;
      document.dispatchEvent(new KeyboardEvent("keydown",{key:"z",metaKey:true,bubbles:true}));
      await sleep(10);
      ok(window.__calls.slice(__pu).some(function(c){return c.cmd==="plan_undo";}), "SP: ⌘Z on the plan surface invokes plan_undo (backend history)");
      document.dispatchEvent(new KeyboardEvent("keydown",{key:"z",metaKey:true,shiftKey:true,bubbles:true}));
      await sleep(10);
      ok(window.__calls.slice(__pu).some(function(c){return c.cmd==="plan_redo";}), "SP: ⌘⇧Z on the plan surface invokes plan_redo");

      // === Offline download modal (Figma 396-124): ONE dialog, 7 states, driven by stt://phase.
      var dlBack = el("dl-modal-back");
      ok(dlBack.hidden, "DL: the download modal is hidden until a phase arrives");
      // (1) Downloading — progress bar + 'X of Y' bytes + Hide/Cancel, no primary.
      window.__dlModal.onPhase({phase:"downloading", done:650000000, total:1600000000, pct:41});
      ok(!dlBack.hidden && getComputedStyle(dlBack).display!=="none", "DL(1): a downloading phase opens the modal (computed display, not just attr)");
      ok(el("dl-modal-progfill").getAttribute("aria-valuenow")==="41", "DL(1): the progressbar reflects the percent");
      ok(el("dl-modal-progbytes").textContent.indexOf("of")>=0 && el("dl-modal-progbytes").textContent.indexOf("GB")>=0, "DL(1): bytes render as 'X of Y GB'");
      ok(!el("dl-modal-hide").hidden && !el("dl-modal-secondary").hidden && el("dl-modal-primary").hidden, "DL(1): Downloading offers Hide + Cancel, no primary");
      // (2) Verifying — indeterminate bar, Cancel only, Esc-cancel still allowed but no Hide.
      window.__dlModal.onPhase({phase:"verifying"});
      ok(el("dl-modal-progwrap").classList.contains("is-indeterminate"), "DL(2): Verifying shows an indeterminate bar");
      ok(el("dl-modal-progfill").getAttribute("aria-valuenow")===null, "DL(2): the bar is indeterminate (no aria-valuenow)");
      ok(el("dl-modal-hide").hidden && !el("dl-modal-secondary").hidden, "DL(2): Verifying hides Hide, keeps Cancel");
      // (3) Ready — success (green) icon + Start listening primary.
      window.__dlModal.onPhase({phase:"ready"});
      ok(el("dl-modal-ico").classList.contains("is-ready"), "DL(3): Ready shows the success (green) icon");
      ok(!el("dl-modal-primary").hidden && el("dl-modal-primary").textContent.indexOf("Start")>=0, "DL(3): Ready offers the primary Start listening");
      ok(window.__dlModal.state()==="ready", "DL(3): the controller is in the ready state");
      // (4) Couldn't connect — warn, Retry + Cancel.
      window.__dlModal.onPhase({phase:"downloading", done:200000000, total:1600000000, pct:12});
      window.__dlModal.onPhase({phase:"failed", reason:"connect", message:"reset", resumable:false, bytes_kept:0});
      ok(el("dl-modal-ico").classList.contains("is-warn") && el("dl-modal-title").textContent.indexOf("interrupted")>=0, "DL(4): a connect failure shows 'Download interrupted' (warn)");
      ok(!el("dl-modal-primary").hidden && el("dl-modal-primary").textContent==="Retry", "DL(4): couldn't-connect offers Retry");
      // (5) Couldn't verify — integrity (red) icon, progress hidden, discarded.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:99});
      window.__dlModal.onPhase({phase:"failed", reason:"verify", message:"sha mismatch", resumable:false, bytes_kept:0});
      ok(el("dl-modal-ico").classList.contains("is-integrity"), "DL(5): a verify failure shows the integrity (red) icon");
      ok(el("dl-modal-title").textContent.indexOf("verified")>=0 && el("dl-modal-progwrap").hidden, "DL(5): couldn't-verify names the failure + hides the progress bar");
      // (6) Offline — Try again + Not now.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:3});
      window.__dlModal.onPhase({phase:"failed", reason:"offline", message:"dns", resumable:false, bytes_kept:0});
      ok(el("dl-modal-title").textContent.toLowerCase().indexOf("offline")>=0, "DL(6): an offline failure shows 'You're offline'");
      ok(el("dl-modal-primary").textContent==="Try again" && el("dl-modal-secondary").textContent==="Not now", "DL(6): offline offers Try again + Not now");
      // Cancel aborts the in-flight download (cancel_download) and closes.
      var __cd = window.__calls.length;
      el("dl-modal-secondary").click();
      ok(window.__calls.slice(__cd).some(function(c){return c.cmd==="cancel_download";}), "DL: Cancel/Not-now invokes cancel_download (abort)");
      ok(dlBack.hidden, "DL: Cancel closes the modal");
      // A 'cancelled' failure echo (from the abort) closes silently — never an error state.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:100, pct:1});
      window.__dlModal.onPhase({phase:"failed", reason:"other", message:"cancelled", resumable:false, bytes_kept:0});
      ok(dlBack.hidden, "DL: a 'cancelled' echo closes the modal silently (no error state)");
      // A lone `ready` with nothing active (warm cache hit) must NOT pop the modal.
      window.__dlModal.onPhase({phase:"ready"});
      ok(dlBack.hidden, "DL: a lone ready (warm cache hit) does not open the modal");
      // Hide backgrounds the download to a pill; progress keeps updating it; the pill re-opens it.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:20});
      el("dl-modal-hide").click();
      ok(dlBack.hidden && !el("dl-pill").hidden, "DL: Hide backgrounds the modal to a pill");
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:55});
      ok(el("dl-pill").textContent.indexOf("55")>=0, "DL: progress keeps updating the background pill");
      el("dl-pill").click();
      ok(!dlBack.hidden && el("dl-pill").hidden, "DL: clicking the pill re-opens the modal");
      window.__dlModal.close();
      ok(dlBack.hidden, "DL: closing tidies up for later checks");
      // State 7 — the SAME dialog reused for a Bible translation (bible://phase carries name + id).
      window.__dlModal.onBiblePhase({phase:"downloading", name:"Young's Literal Translation", id:"ylt", done:5000000, total:12000000, pct:42});
      ok(!dlBack.hidden && el("dl-modal-title").textContent.indexOf("Young")>=0, "DL(7): a bible://phase opens the SAME modal, titled with the translation");
      ok(el("dl-modal-sub").textContent.toLowerCase().indexOf("translation")>=0, "DL(7): the subtitle names it a Bible translation (assetKind reuse)");
      window.__dlModal.onBiblePhase({phase:"ready", name:"Young's Literal Translation", id:"ylt"});
      ok(el("dl-modal-title").textContent.indexOf("ready")>=0 && el("dl-modal-ico").classList.contains("is-ready"), "DL(7): a translation reaches Ready in the same dialog");
      window.__dlModal.close();
      ok(dlBack.hidden, "DL(7): the reused dialog closes cleanly");
      // PLN-004 (Vera, PR #83 review): Command::GoLive (controller.rs) sets live_idx = staged_idx
      // but never clears staged_idx, so the item that just went live carries BOTH is_live AND
      // is_staged on every ordinary Go Live — not a contrived edge case. Render a plan with such a
      // row in ISOLATION (its own fixture, not the shared C-001 one below, so this doesn't disturb
      // that fixture's own item count/index-based assertions) and prove Live wins the cascade.
      planRenderBuilder({ plan_name:"Overlap", items:[
        {id:901, kind:"song", title:"Just Went Live", is_live:true, is_staged:true},
        {id:902, kind:"song", title:"Was Never Staged", is_live:true, is_staged:false}
      ] });
      var liveAndStagedRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="901"]');
      ok(liveAndStagedRow.classList.contains("is-live") && liveAndStagedRow.classList.contains("is-staged"),
         "PLN-004 (setup): a just-went-live row genuinely carries BOTH classes — this is not vacuous");
      ok(getComputedStyle(liveAndStagedRow).borderTopStyle === "solid",
         "PLN-004: a row that is BOTH live and staged renders Live's SOLID border, not Preview's dashed one — got " +
         getComputedStyle(liveAndStagedRow).borderTopStyle);
      ok(getComputedStyle(liveAndStagedRow).borderTopColor === getComputedStyle(document.querySelector('#plan-b-list .plan-b-row[data-item-id="902"]')).borderTopColor,
         "PLN-004 (control): a live+staged row's border colour matches a live-only row's — Live wins the colour too, not just the shape");

      // C-001 / C-005 read side: render a crafted plan covering every link state (scripture-linked,
      // deck-linked, deck-MISSING, unlinked) and assert the run-sheet chips. planRenderBuilder is a
      // global (top-level fn), driven directly the same way the M1 checks drive render().
      var planView = { plan_name:"Sunday", items:[
        {id:11, kind:"scripture",   title:"Opening Word",  is_live:false, is_staged:true,  link:{kind:"scripture", reference:"John 3:16", translation:"KJV"}},
        {id:12, kind:"slide_group", title:"Sermon Deck",   is_live:false, is_staged:false, link:{kind:"deck", id:2}},   // resolves to a name
        {id:13, kind:"slide_group", title:"Old Deck",      is_live:false, is_staged:false, link:{kind:"deck", id:99}},  // id gone → missing
        {id:14, kind:"scripture",   title:"Closing Prayer",is_live:false, is_staged:false}                              // unlinked
      ] };
      planRenderBuilder(planView);
      var bRows = document.querySelectorAll("#plan-b-list .plan-b-row");
      ok(bRows.length === 4, "SP C-001: the run sheet renders a typed row per plan item (got " + bRows.length + ")");
      var sChip = document.querySelector("#plan-b-list .link-scripture");
      ok(sChip && /John 3:16/.test(sChip.textContent) && /KJV/.test(sChip.textContent),
         "SP C-001: a scripture-linked item shows its reference + translation chip");
      var dChips = document.querySelectorAll("#plan-b-list .link-deck");
      ok(Array.prototype.some.call(dChips, function(c){return /Grace That Feeds/.test(c.textContent);}),
         "SP C-001: a deck-linked item resolves the deck name from the lazily-loaded deck list");
      var mChip = document.querySelector("#plan-b-list .link-missing");
      ok(mChip && /missing/i.test(mChip.textContent), "SP C-001: a deck whose id is gone shows a ⚠ missing chip");
      // PLN-004 (DESIGN-2.0-PARITY-AUDIT-plan.md): the handoff is explicit — "Preview/staged =
      // green/dashed, Live/Program = red/solid" — and the staged row's border used to stay solid.
      // Item 11 above is staged-only (is_staged:true, is_live:false); item 12 is neither, so it is
      // the control proving the dashed rule is scoped to .is-staged, not a global border reset.
      var stagedBRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]');
      ok(stagedBRow.classList.contains("is-staged") && !stagedBRow.classList.contains("is-live"),
         "PLN-004 (setup): item 11 is staged-only, so the border-style assertion below is not vacuous");
      ok(getComputedStyle(stagedBRow).borderTopStyle === "dashed",
         "PLN-004: a staged run-sheet row's border is dashed, per the handoff — got " + getComputedStyle(stagedBRow).borderTopStyle);
      var plainBRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="12"]');
      ok(getComputedStyle(plainBRow).borderTopStyle === "solid",
         "PLN-004 (control): a row that is neither live nor staged keeps its ordinary solid border");
      // C-005 inspector: a linked scripture item → chip + Change…/Unlink/Remove.
      document.querySelectorAll("#plan-b-list .plan-b-row")[0].click();
      var insp = el("plan-b-insp");
      ok(insp.querySelector(".link-scripture") && /John 3:16/.test(insp.textContent),
         "SP C-005: selecting a linked item shows its link in the inspector");
      ok(Array.prototype.some.call(insp.querySelectorAll(".pm-btn-primary"), function(b){return /Change/.test(b.textContent);}),
         "SP C-005: a linked item's inspector offers Change…");
      ok(Array.prototype.some.call(insp.querySelectorAll("button"), function(b){return b.textContent==="Unlink";}),
         "SP C-005: a linked item's inspector offers Unlink");
      ok(!!insp.querySelector(".pm-btn-danger"), "SP C-005: the inspector offers Remove item");
      ok(/never changes Live/.test(insp.textContent), "SP C-006: the inspector states editing here never changes Live");
      // #4 selection is exposed to AT via role=option + aria-selected (not border-colour alone);
      // #3 keyboard focus survives the list-rebuild (lands on the selected row, not <body>);
      // #5 the reorder buttons carry an accessible name.
      var selRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]');
      ok(selRow && selRow.getAttribute("role") === "option" && selRow.getAttribute("aria-selected") === "true",
         "SP C-005 a11y: the selected run-sheet row is role=option aria-selected=true");
      ok(document.querySelector('#plan-b-list .plan-b-row[data-item-id="12"]').getAttribute("aria-selected") === "false",
         "SP C-005 a11y: an unselected row exposes aria-selected=false");
      ok(document.activeElement === selRow,
         "SP C-005 a11y: selecting a row keeps keyboard focus on it (survives the list rebuild)");
      var upBtn = document.querySelector('#plan-b-list .plan-b-up');
      ok(upBtn && /move/i.test(upBtn.getAttribute("aria-label") || ""),
         "SP C-007 a11y: the ↑/↓ reorder buttons have an accessible name");
      // C-005 unlinked state: distinct warning + a Link… affordance.
      document.querySelectorAll("#plan-b-list .plan-b-row")[3].click();
      var insp2 = el("plan-b-insp");
      ok(!!insp2.querySelector(".plan-insp-unlinked"), "SP C-005: an unlinked scripture item shows the 'no reference yet' warning");
      ok(/Link a scripture/.test(insp2.textContent), "SP C-005: an unlinked item offers Link a scripture…");
      // C-003 link-Scripture flow: the modal → set_item_content{kind:scripture,reference,translation}.
      var sicBefore = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      openLinkModal({id:14, kind:"scripture", title:"Closing Prayer"});
      var lm = document.querySelector(".pm-confirm.pm-link");
      ok(!!lm && lm.getAttribute("aria-modal")==="true", "SP C-007: the link modal is a labelled aria-modal dialog");
      // #2 the scripture modal opens with the reference input focused (not Cancel) — a keyboard
      // operator types the reference immediately.
      ok(document.activeElement === lm.querySelector('input[aria-label="Scripture reference"]'),
         "SP C-007 a11y: the scripture link modal opens with the reference input focused (not Cancel)");
      // #1 focus trap: Tab is contained within the dialog (the background console — which holds
      // live-control buttons — is NOT inert, so an escaping Tab could reach Go Live). A synthetic
      // Tab does NOT move focus natively, so asserting "focus stayed inside" would be tautological
      // (it passes even with the trap removed). Instead assert the trap ACTIVELY wraps focus from
      // the last control back to the first — that only happens if the Tab handler fired.
      var lmFoc = Array.prototype.filter.call(lm.querySelectorAll("button, input, select"), function(n){ return !n.disabled; });
      var lmFirst = lmFoc[0], lmLast = lmFoc[lmFoc.length - 1];
      lmLast.focus();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
      ok(document.activeElement === lmFirst && lmFirst !== lmLast && lm.contains(document.activeElement),
         "SP C-007 a11y: Tab from the last control WRAPS to the first (the trap actively contains focus, not a no-op)");
      var refIn = lm.querySelector('input[aria-label="Scripture reference"]');
      refIn.value = "Romans 8:28";
      Array.prototype.filter.call(lm.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(20);
      var sic = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sic.length > sicBefore && sic[sic.length-1].args.link && sic[sic.length-1].args.link.kind==="scripture" &&
         /Romans 8:28/.test(sic[sic.length-1].args.link.reference),
         "SP C-003: the link-Scripture flow sends set_item_content{link:{kind:scripture,reference}}");
      // === Frame 610:124 — scripture verse picker (chapter nav + verse list + verses/slide) =====
      openLinkModal({ id: 14, kind: "scripture", title: "Opening Word" });
      await sleep(20);
      var lmV = document.querySelector(".pm-confirm.pm-link");
      lmV.querySelector('input[aria-label="Scripture reference"]').value = "Isaiah 61:1";
      Array.prototype.filter.call(lmV.querySelectorAll("button"), function(b){return b.textContent==="Browse";})[0].click();
      await sleep(30); // get_chapter
      var vpick = lmV.querySelector(".pm-verse-picker");
      ok(vpick && !vpick.hidden, "SP2 C-003: Browse opens the verse picker (get_chapter)");
      ok(!!lmV.querySelector('.pm-verse-navbtn[aria-label="Next chapter"]') && !!lmV.querySelector('.pm-verse-navbtn[aria-label="Previous chapter"]'),
         "SP2 C-003: the picker has chapter next/prev nav");
      var vrows = lmV.querySelectorAll(".pm-verse");
      ok(vrows.length >= 1, "SP2 C-003: the verse list renders");
      ok(!!lmV.querySelector('.pm-verse-list[aria-multiselectable="true"]'),
         "SP2 C-006 a11y: the verse list is aria-multiselectable (a contiguous range is selectable)");
      vrows[0].click();
      ok(lmV.querySelector(".pm-verse.sel") && lmV.querySelector('.pm-verse[aria-selected="true"]'),
         "SP2 C-003: clicking a verse highlights the selected range (aria-selected)");
      ok(/Isaiah 61/.test(lmV.querySelector(".pm-verse-preview").textContent),
         "SP2 C-003: the gold reference preview reflects the selection");
      var vpsIn = lmV.querySelector('input[aria-label="Verses per slide"]');
      ok(!!vpsIn, "SP2 C-003: a verses-per-slide control is present");
      vpsIn.value = "2"; vpsIn.dispatchEvent(new Event("input", { bubbles: true }));
      var sicV = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      Array.prototype.filter.call(lmV.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(20);
      var sicV2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sicV2.length > sicV && sicV2[sicV2.length-1].args.link.kind === "scripture" && sicV2[sicV2.length-1].args.link.verses_per_slide === 2,
         "SP2 C-003: Link commits scripture with the selected reference + verses_per_slide");
      // SP2 fix: editing the reference AFTER browsing invalidates the stale chapter — the freshly
      // typed reference wins on Link (was silently committing the browsed one).
      openLinkModal({ id: 14, kind: "scripture", title: "Opening Word" });
      await sleep(20);
      var lmS = document.querySelector(".pm-confirm.pm-link");
      var sIn = lmS.querySelector('input[aria-label="Scripture reference"]');
      sIn.value = "Isaiah 61:1";
      Array.prototype.filter.call(lmS.querySelectorAll("button"), function(b){return b.textContent==="Browse";})[0].click();
      await sleep(30);
      ok(!lmS.querySelector(".pm-verse-picker").hidden, "SP2 C-003: precondition — a chapter is browsed");
      sIn.value = "John 3:16";
      sIn.dispatchEvent(new Event("input", { bubbles: true }));
      ok(lmS.querySelector(".pm-verse-picker").hidden,
         "SP2 C-003: editing the reference invalidates the browsed chapter (picker hides)");
      var sicS = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      Array.prototype.filter.call(lmS.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(20);
      var sicS2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sicS2.length > sicS && /John 3:16/.test(sicS2[sicS2.length-1].args.link.reference),
         "SP2 C-003: Link commits the freshly-typed reference, not the stale browsed one");
      // #8 host-rejection path: a rejected link keeps the modal OPEN and shows a role=alert error
      // (no silent close on a no-op). The one-shot __sicRejectOnce hook fails the next command.
      openLinkModal({id:14, kind:"scripture", title:"Closing Prayer"});
      var lmE = document.querySelector(".pm-confirm.pm-link");
      lmE.querySelector('input[aria-label="Scripture reference"]').value = "Nope 9:9";
      window.__sicRejectOnce = true;
      Array.prototype.filter.call(lmE.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(30);
      ok(document.querySelector(".pm-confirm.pm-link") === lmE,
         "SP C-006: a host-rejected link keeps the modal open (no optimistic close on a silent no-op)");
      var alertEl = lmE.querySelector(".pm-link-err");
      ok(alertEl && !alertEl.hidden && alertEl.getAttribute("role") === "alert",
         "SP C-007: a rejected link surfaces an inline role=alert error");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); // close before the next modal
      await sleep(10);
      // C-004 link-Presentation flow: SELECT-then-confirm (handoff §4.2). Clicking a deck selects it
      // (aria-selected + "✓ Selected", NO commit); the footer "Link to item" → set_item_content{deck}.
      openLinkModal({id:12, kind:"slide_group", title:"Sermon Deck"});
      await sleep(40); // planDeckBody awaits the deck list
      var lm2 = document.querySelector(".pm-confirm.pm-link");
      var deckHit = lm2.querySelector(".pm-link-hit");
      ok(!!deckHit, "SP C-004: the link-Presentation modal lists the available decks");
      // Frame 610:390 — grid picker: grid layout + slide-count pills + New card + Grid/List toggle.
      ok(!!lm2.querySelector(".pm-deck-grid") && !!lm2.querySelector(".pm-deck-card .pm-deck-pill"),
         "SP2 C-004: the picker is a grid with per-deck slide-count pills");
      ok(!!lm2.querySelector(".pm-deck-new"), "SP2 C-004: a New-presentation card is offered");
      ok(!lm2.querySelector(".pm-deck-grid .pm-deck-new"),
         "SP2 C-006 a11y: the New card is outside the deck role=listbox (options only)");
      var listSeg = Array.prototype.filter.call(lm2.querySelectorAll(".pm-deck-seg-btn"), function(b){return b.dataset.view==="list";})[0];
      ok(!!listSeg, "SP2 C-004: a Grid/List toggle is present");
      listSeg.click();
      ok(lm2.querySelector(".pm-deck-grid").classList.contains("as-list"),
         "SP2 C-004: switching to List re-lays the picker");
      var linkFoot = lm2.querySelector(".pm-link-foot .pm-btn-primary");
      ok(!!linkFoot && linkFoot.disabled, "SP C-004: 'Link to item' is disabled until a deck is selected");
      var sicBeforeDeck = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      deckHit.click(); // SELECT (must not commit)
      ok(window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length === sicBeforeDeck,
         "SP C-004: selecting a deck does NOT commit (no premature set_item_content)");
      ok(deckHit.getAttribute("aria-selected") === "true" && deckHit.querySelector(".pm-link-sel") &&
         !deckHit.querySelector(".pm-link-sel").hidden && !linkFoot.disabled,
         "SP C-004: a selected deck shows '✓ Selected' + enables 'Link to item'");
      linkFoot.click(); // CONFIRM
      await sleep(20);
      var sic2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      // The label conjunct is the WRITE half of B2. M4 covers only the read half (planDeckCard
      // rendering a label it was handed), so dropping `label` from this send site left the gate
      // green at 834 checks. Resolved by id rather than hardcoded, so it asserts "the selected
      // deck's own name" instead of a string that happens to match.
      var sicLink = sic2.length ? sic2[sic2.length-1].args.link : null;
      var sicDeck = ((window.__LIB && window.__LIB.decks) || []).filter(function(d){ return sicLink && d.id === sicLink.id; })[0];
      ok(sic2.length > sicBeforeDeck && sicLink && sicLink.kind==="deck" &&
         typeof sicLink.id === "number" &&
         !!sicDeck && sicLink.label === sicDeck.name,
         "SP C-004: 'Link to item' sends set_item_content{link:{kind:deck,id,label}} — the label is the SELECTED deck's own name, which is the only thing that can name it once the library row is gone (select-then-confirm)");
      // SP2 New-presentation card: creates a deck (deck_new) and links it immediately.
      openLinkModal({ id: 12, kind: "slide_group", title: "Sermon Deck" });
      await sleep(40);
      var lmN = document.querySelector(".pm-confirm.pm-link");
      var sicN = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      lmN.querySelector(".pm-deck-new").click();
      await sleep(50); // deck_new → planLoadDecks → commit
      var sicN2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      // The third and last deck-link send site. Resolved by id against the library the stub just
      // pushed the new deck into, so it asserts the CREATED deck's own name rather than a literal.
      var sicNLink = sicN2.length ? sicN2[sicN2.length-1].args.link : null;
      var sicNDeck = ((window.__LIB && window.__LIB.decks) || []).filter(function(d){ return sicNLink && d.id === sicNLink.id; })[0];
      ok(window.__calls.some(function(c){return c.cmd==="deck_new";}) && sicN2.length > sicN &&
         sicNLink && sicNLink.kind === "deck",
         "SP2 C-004: the New-presentation card creates + links a deck");
      ok(!!sicNLink && !!sicNDeck && sicNLink.label === sicNDeck.name,
         "SP2 C-004: the New-presentation card carries the created deck's OWN name as link.label (third of three send sites)");
      // SP2 fix: double-activating the New card creates exactly ONE deck (re-entrancy/disabled guard).
      openLinkModal({ id: 12, kind: "slide_group", title: "Sermon Deck" });
      await sleep(40);
      var lmNN = document.querySelector(".pm-confirm.pm-link");
      var dnBefore = window.__calls.filter(function(c){return c.cmd==="deck_new";}).length;
      var nc = lmNN.querySelector(".pm-deck-new");
      nc.click(); nc.click(); // double-activate
      await sleep(50);
      ok(window.__calls.filter(function(c){return c.cmd==="deck_new";}).length === dnBefore + 1,
         "SP2 C-004: the New card guards double-activation (exactly one deck_new)");
      // F12b Change… on an item whose linked deck was DELETED: preselect nothing so "Link to item"
      // stays disabled (no phantom-id re-commit), not enabled with nothing visibly selected.
      openLinkModal({ id: 20, kind: "slide_group", title: "Ghost Deck", link: { kind: "deck", id: 999999 } });
      await sleep(40);
      var lm3 = document.querySelector(".pm-confirm.pm-link");
      ok(!lm3.querySelector('.pm-link-hit[aria-selected="true"]'),
         "SP C-004: Change… on a deleted deck preselects nothing (no phantom selection)");
      ok(lm3.querySelector(".pm-link-foot .pm-btn-primary").disabled,
         "SP C-004: 'Link to item' stays disabled when the preselected deck is missing");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); // close before the next check
      await sleep(10);
      // F11 empty state: an empty plan renders the centered CTA (not a bare line); "Add first item"
      // focuses the palette; the inspector is cleared.
      planRenderBuilder({ plan_name: "Empty", items: [] });
      var emptyEl = document.querySelector("#plan-b-list .plan-empty");
      ok(!!emptyEl && !!document.getElementById("plan-empty-add"),
         "SP C-002: an empty plan renders the centered CTA with an 'Add first item' action");
      // Superseded by 86ak8467m: Template / Duplicate / Import are no longer a "coming soon" line
      // but four real controls, each either live or disabled with the reason it cannot work. What
      // survives from the original intent is asserted here and exercised in full in the PLAN
      // LIFECYCLE block below: the frame still offers all four starts, and none of them is a no-op.
      ok(!!document.getElementById("plan-empty-new") && !!document.getElementById("plan-empty-template") &&
         !!document.getElementById("plan-empty-duplicate") && !!document.getElementById("plan-empty-import"),
         "SP C-002: the empty state offers all four designed starts (Create · Template · Duplicate · Import)");
      ok(!/coming soon/i.test(emptyEl.textContent),
         "SP C-002: ...as controls, not as a 'coming soon' sentence");
      document.getElementById("plan-empty-add").click();
      ok(document.activeElement === document.querySelector("#plan-palette-btns .plan-palette-btn"),
         "SP C-002 a11y: 'Add first item' focuses the Add-item palette");
      ok(/Select an item/i.test(el("plan-b-insp").textContent), "SP C-002: an empty plan clears the item inspector");
      // F5: a FAILED deck-list load leaves deck chips GENERIC (planDecks stays null), never a false
      // "⚠ missing". Reuse the one-shot deck_ rejection hook, reload, and assert the chip is generic.
      window.__pmRejectOnce = true;
      await planLoadDecks();
      ok(!/missing/i.test(planLinkChip({ kind: "deck", id: 987654 }).textContent),
         "SP C-001: a failed deck-list load renders a generic chip, not a false '⚠ missing'");
      await planLoadDecks(); // restore the resolved deck list
      planRenderBuilder(planView); // restore a populated run sheet
      // === Frame 608:124 — presentation-linked inspector: deck card + Open in editor ============
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="12"]').click(); // the deck-linked item
      var dinsp = el("plan-b-insp");
      var deckCard = dinsp.querySelector(".plan-deck-card");
      ok(deckCard && /Grace That Feeds/.test(deckCard.textContent) && /slide/.test(deckCard.textContent),
         "SP2 C-005: a presentation-linked item shows a deck card (name + slide count)");
      // --- Frame 611:1035 — a MISSING deck is named, which is the whole point of link.label ---
      // The deck's library row is gone, so the id resolves to nothing; only the label captured
      // at link time can say WHICH presentation vanished. Without this the card degrades to
      // "presentation missing" and the design's "'X' was deleted from the library" is unbuildable.
      var goneNamed = planDeckCard({ kind: "deck", id: 987654, label: "Sunday Service \u2014 Aug 4" });
      ok(goneNamed.classList.contains("missing"),
         "SP2 C-005: an unresolvable deck id renders the missing card");
      ok(/Sunday Service \u2014 Aug 4/.test(goneNamed.textContent),
         "SP2 C-005: the missing card NAMES the deleted deck from link.label, not just 'presentation missing'");
      ok(/deleted from the library/i.test(goneNamed.textContent),
         "SP2 C-005: and it says what happened to it, so the operator knows to relink rather than retry");
      // CONTROL 1: without a label there is nothing to name, so it must fall back rather than
      // render an empty quotation — otherwise the check above would pass on any card at all.
      var goneAnon = planDeckCard({ kind: "deck", id: 987654 });
      ok(goneAnon.classList.contains("missing") && /presentation missing/i.test(goneAnon.textContent)
         && !/\u201c\u201d/.test(goneAnon.textContent),
         "SP2 C-005 (control): a missing deck with no captured label degrades to the generic message, never an empty quotation");
      // CONTROL 2: a PRESENT deck must not take the missing branch even when a stale label is
      // attached — the live library name wins, so a rename can never render as a deletion.
      var alive = planDeckCard({ kind: "deck", id: 2, label: "Some Old Name" });
      ok(!alive.classList.contains("missing") && !/Some Old Name/.test(alive.textContent),
         "SP2 C-005 (control): a resolvable deck ignores a stale label and shows the library name");
      var openEd = Array.prototype.filter.call(dinsp.querySelectorAll("button"), function(b){return b.textContent==="Open in editor";})[0];
      ok(!!openEd, "SP2 C-005: the deck inspector offers Open in editor");
      openEd.click();
      await sleep(30);
      ok(el("surface-presentation").classList.contains("active"),
         "SP2 C-005: Open in editor navigates to the Presentation surface with the deck");
      document.querySelector('.nav-item[data-surface="plan"]').click(); // back to the builder
      await sleep(40);
      planRenderBuilder(planView); // restore a populated run sheet after the plan-surface re-activation
      // === Frame 611:820 — run-sheet reorder (keyboard Alt+↑/↓ + pointer drag) ==================
      // C-001 keyboard: Alt+↓ on a row reorders it down via move_item{to:i+1}.
      var r0 = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]');
      r0.focus();
      var mvBefore = window.__calls.filter(function(c){return c.cmd==="move_item";}).length;
      r0.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", altKey: true, bubbles: true }));
      await sleep(20);
      var mv = window.__calls.filter(function(c){return c.cmd==="move_item";});
      ok(mv.length > mvBefore && mv[mv.length-1].args.itemId === 11 && mv[mv.length-1].args.to === 1,
         "SP2 C-001: Alt+↓ reorders the row via move_item{to:i+1}");
      planRenderBuilder(planView); // restore
      // C-006 a11y: the drag handle is aria-hidden (Alt+↑/↓ is the keyboard-accessible reorder path).
      var handle = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"] .plan-b-handle');
      ok(handle && handle.getAttribute("aria-hidden") === "true",
         "SP2 C-006: the drag handle is aria-hidden (Alt+↑/↓ is the accessible reorder path)");
      // C-002 pointer drag: pointerdown on the handle → move past threshold → drop line renders +
      // origin row lifts → pointerup reorders via move_item.
      var pr = document.querySelectorAll('#plan-b-list .plan-b-row');
      var startRect = pr[0].getBoundingClientRect(), thirdRect = pr[2].getBoundingClientRect();
      handle.dispatchEvent(new PointerEvent("pointerdown", { button: 0, clientY: startRect.top + 5, bubbles: true, pointerId: 9 }));
      window.dispatchEvent(new PointerEvent("pointermove", { clientY: thirdRect.top + thirdRect.height * 0.6, bubbles: true, pointerId: 9 }));
      ok(!!document.querySelector("#plan-b-list .plan-b-dropline"), "SP2 C-002: dragging shows the drop line");
      ok(document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]').classList.contains("dragging"),
         "SP2 C-002: the dragged origin row is marked (lifted)");
      var mvBefore2 = window.__calls.filter(function(c){return c.cmd==="move_item";}).length;
      window.dispatchEvent(new PointerEvent("pointerup", { clientY: thirdRect.top + thirdRect.height * 0.6, bubbles: true, pointerId: 9 }));
      await sleep(20);
      ok(window.__calls.filter(function(c){return c.cmd==="move_item";}).length > mvBefore2, "SP2 C-002: dropping reorders via move_item");
      ok(!document.querySelector("#plan-b-list .plan-b-dropline"), "SP2 C-002: the drop line is torn down after drop");
      // C-002 a cancelled drag never reorders + tears down.
      planRenderBuilder(planView);
      var pr2 = document.querySelectorAll('#plan-b-list .plan-b-row');
      var h2 = pr2[1].querySelector(".plan-b-handle");
      h2.dispatchEvent(new PointerEvent("pointerdown", { button: 0, clientY: pr2[1].getBoundingClientRect().top + 5, bubbles: true, pointerId: 10 }));
      window.dispatchEvent(new PointerEvent("pointermove", { clientY: pr2[3].getBoundingClientRect().top + 5, bubbles: true, pointerId: 10 }));
      var mvBefore3 = window.__calls.filter(function(c){return c.cmd==="move_item";}).length;
      window.dispatchEvent(new PointerEvent("pointercancel", { pointerId: 10, bubbles: true }));
      window.dispatchEvent(new PointerEvent("pointerup", { clientY: pr2[3].getBoundingClientRect().top + 5, bubbles: true, pointerId: 10 }));
      await sleep(10);
      ok(window.__calls.filter(function(c){return c.cmd==="move_item";}).length === mvBefore3, "SP2 C-002: a cancelled drag does not reorder");
      ok(!document.querySelector("#plan-b-list .plan-b-dropline"), "SP2 C-002: pointercancel tears down the drop line");
      // === 86ak846ft — run-sheet owner/duration + Plan Summary + loading ======================
      // A plan whose per-item owner + duration are known, so the RENDERED rows and the RENDERED
      // summary can be checked against each other rather than against a hand-copied constant.
      var sumView = { plan_name:"Sunday", items:[
        {id:21, kind:"song",         title:"Opening Song",    is_live:false, is_staged:false, owner:"Worship",      planned_secs:300},
        {id:22, kind:"announcement", title:"Welcome",         is_live:false, is_staged:false, owner:"Host",         planned_secs:120},
        {id:23, kind:"scripture",    title:"Romans 8:28-30",  is_live:false, is_staged:false, owner:"Scripture op", planned_secs:120,
         link:{kind:"scripture", reference:"Romans 8:28-30", translation:"WEB"}},
        {id:24, kind:"slide_group",  title:"Sermon",          is_live:false, is_staged:false, owner:"Pastor",       planned_secs:2100, link:{kind:"deck", id:2}},
        {id:25, kind:"media",        title:"Testimony Video", is_live:false, is_staged:false, owner:"Media",        planned_secs:192},
        {id:26, kind:"song",         title:"Closing Song",    is_live:false, is_staged:false,                       planned_secs:360}
      ] };
      planSelectedId = null; // nothing selected -> the right panel is the Plan Summary
      planRenderBuilder(sumView);
      // --- owner + planned duration on every row (handoff §3, FR-004) -------------------------
      var oRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]');
      ok(!!oRow.querySelector(".plan-b-owner") && /Worship/.test(oRow.querySelector(".plan-b-owner").textContent),
         "SP3 AC-1: a run-sheet row renders its owner");
      ok(!!oRow.querySelector(".plan-b-dur") && /5:00/.test(oRow.querySelector(".plan-b-dur").textContent),
         "SP3 AC-1: a run-sheet row renders its planned duration as m:ss");
      ok(/Owner:/.test(oRow.querySelector(".plan-b-owner").textContent),
         "SP3 AC-1 a11y: the owner carries a visually-hidden prefix, so a bare 'Worship' is not ambiguous to AT");
      // Positive control: the element is OMITTED when unassigned, never padded with a placeholder
      // dash that would read as data. Without this, "renders the owner" could pass on a stub.
      var noOwner = document.querySelector('#plan-b-list .plan-b-row[data-item-id="26"]');
      ok(!noOwner.querySelector(".plan-b-owner"), "SP3 AC-1 (control): an unassigned item renders NO owner element");
      ok(!!noOwner.querySelector(".plan-b-dur"), "SP3 AC-1 (control): that same row still renders its duration — the owner omission is per-field, not a dead branch");
      ok(oRow.querySelector(".plan-b-dur").getAttribute("aria-label") === "Planned 5 minutes",
         "SP3 AC-1 a11y (UI-A1 §211): the duration carries a SPOKEN label — a screen reader reading \"five colon zero zero\" is not useful");
      // --- AC-3: the summary must AGREE with the run sheet ------------------------------------
      // Design-QA §9 rejected these frames once for exactly this: "8 items · 1:12:00" displayed
      // over 6 rows summing 53:12. So compare the two RENDERED surfaces against each other. A
      // second, independent computation of the totals is precisely how they drift apart, and only
      // a cross-check between them catches it — asserting the summary against a literal would not.
      function sumRowValue(label) {
        var rows = document.querySelectorAll("#plan-b-insp .plan-sum-row");
        for (var i = 0; i < rows.length; i++) {
          if (rows[i].querySelector(".plan-sum-label").textContent === label)
            return rows[i].querySelector(".plan-sum-value").textContent.trim();
        }
        return null;
      }
      function clockToSecs(t) {
        // Tolerates surrounding text: the total renders "0:05:00 · partial", and a naive split
        // would make the last field NaN and silently zero the comparison.
        var m = String(t).match(/(\d+):(\d{2})(?::(\d{2}))?/);
        if (!m) return NaN;
        return m[3] !== undefined
          ? Number(m[1])*3600 + Number(m[2])*60 + Number(m[3])
          : Number(m[1])*60 + Number(m[2]);
      }
      var renderedRows = document.querySelectorAll("#plan-b-list .plan-b-row");
      function rowDurationSum() {
        var t = 0;
        Array.prototype.forEach.call(document.querySelectorAll("#plan-b-list .plan-b-dur"), function(d) {
          var txt = d.textContent.trim();
          if (txt === "\u2014") return; // an unset duration renders "—" and is excluded from the sum
          t += clockToSecs(txt);
        });
        return t;
      }
      var rowSum = rowDurationSum();
      ok(sumRowValue("Items") === String(renderedRows.length),
         "SP3 AC-3: Plan Summary 'Items' equals the rows the run sheet actually rendered (" + sumRowValue("Items") + " vs " + renderedRows.length + ")");
      ok(clockToSecs(sumRowValue("Total time")) === rowSum,
         "SP3 AC-3: Plan Summary total equals the sum of the durations shown on those rows (" + sumRowValue("Total time") + " vs " + rowSum + "s)");
      ok(sumRowValue("Total time") === "0:53:12",
         "SP3 AC-3: the total is formatted h:mm:ss, so a 53-minute plan cannot read as 53 minutes 12 seconds of m:ss");
      // Derived, not literal — same reasoning as the per-kind counts: a hardcoded "5 / 6" stops
      // describing the fixture the moment the fixture changes, and keeps passing anyway.
      var expAssigned = sumView.items.filter(function(i){ return !!i.owner; }).length;
      ok(sumRowValue("Assigned") === expAssigned + " / " + sumView.items.length,
         "SP3 AC-3: 'Assigned' counts the items that actually carry an owner (shown " + sumRowValue("Assigned") +
         ", fixture " + expAssigned + " / " + sumView.items.length + ")");
      // AC-3 states a SUMMATION invariant, so assert the sum — derived from the fixture, never
      // hardcoded. The literals this replaces held for ANY fixture, and because sumView contains
      // no timer and no section they never exercised the summation at all: the bug (two kinds
      // uncounted) and the check that should have caught it shared a blind spot. Deriving the
      // expectation also means an eighth ItemKind cannot slip past unnoticed.
      // No `section` entry: the panel has no Sections row, because every summary metric describes
      // the TRIGGERABLE run sheet and `items` excludes dividers (frame 608:875 — "6 items",
      // "Assigned 6 / 6", six rows over three dividers).
      var KIND_ROWS = { song:"Songs", scripture:"Scripture", slide_group:"Presentations", media:"Media",
                        announcement:"Announcements", timer:"Timers" };
      function assertKindCounts(view, label) {
        var expected = {}, unmapped = [];
        Object.keys(KIND_ROWS).forEach(function(k){ expected[k] = 0; });
        var triggerable = view.items.filter(function(it){ return it.kind !== "section"; });
        triggerable.forEach(function(it){
          if (KIND_ROWS[it.kind] === undefined) unmapped.push(it.kind);
          else expected[it.kind] += 1;
        });
        ok(unmapped.length === 0,
           "SP3 AC-3 (" + label + "): every item kind present has a summary row — an unrepresented kind is invisible in the counts (unmapped: " + (unmapped.join(",") || "none") + ")");
        var shownTotal = 0, wrong = [];
        Object.keys(KIND_ROWS).forEach(function(k){
          var shown = Number(sumRowValue(KIND_ROWS[k]));
          shownTotal += shown;
          if (shown !== expected[k]) wrong.push(KIND_ROWS[k] + " shows " + shown + ", fixture has " + expected[k]);
        });
        ok(wrong.length === 0,
           "SP3 AC-3 (" + label + "): each per-kind count matches the fixture (" + (wrong.join("; ") || "all match") + ")");
        ok(shownTotal === triggerable.length && String(shownTotal) === sumRowValue("Items"),
           "SP3 AC-3 (" + label + "): the per-kind counts SUM to Items, counting triggerable rows only (" + shownTotal +
           " vs Items=" + sumRowValue("Items") + ", fixture=" + triggerable.length + " of " + view.items.length + " rows)");
        ok(!sumRowValue("Sections"),
           "SP3 AC-3 (" + label + "): the panel has NO Sections row — one would make the per-kind rows stop summing to Items");
      }
      assertKindCounts(sumView, "sumView");
      // A fixture carrying ALL seven ItemKind variants, so the summation is exercised across every
      // row the panel draws rather than only the five the demo plan happens to contain.
      var allKindsView = { plan_name:"All", items:[
        {id:101, kind:"song",         title:"a", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:102, kind:"scripture",    title:"b", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:103, kind:"slide_group",  title:"c", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:104, kind:"media",        title:"d", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:105, kind:"announcement", title:"e", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:106, kind:"timer",        title:"f", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:107, kind:"section",      title:"g", is_live:false, is_staged:false, planned_secs:60, owner:"o"}
      ] };
      planSelectedId = null;
      planRenderBuilder(allKindsView);
      assertKindCounts(allKindsView, "all seven kinds");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- Q2: the run-sheet header carries the planned total (frame 608:925) ------------------
      // Section 9 records this total as the fix for the MAJOR these frames were rejected for, so a
      // header that omits it reintroduces the defect. It must agree with the rows AND the summary:
      // two headline numbers that can drift apart is precisely what was rejected.
      planSelectedId = null;
      planRenderBuilder(sumView);
      // Q12: assert the RENDERED STRING, not its parse. clockToSecs reads "53:12" and "0:53:12"
      // identically, so comparing parsed seconds let a regression from planFmtTotal to fmtClock
      // pass every assertion here while the header and the summary visibly disagreed.
      function fmtHMS(secs) {
        var h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), q = secs % 60;
        return h + ":" + String(m).padStart(2, "0") + ":" + String(q).padStart(2, "0");
      }
      ok(sumRowValue("Total time") === fmtHMS(rowDurationSum()),
         "SP3 AC-22 (Quinn Q2): the Plan Summary total is the h:mm:ss STRING for the rendered rows' durations (got \"" +
         sumRowValue("Total time") + "\", expected \"" + fmtHMS(rowDurationSum()) + "\")");
      ok(el("plan-b-total").textContent === "planned " + fmtHMS(rowDurationSum()),
         "SP3 AC-22 (Quinn Q2): the run-sheet header renders exactly \"planned \" + that same string (got \"" +
         el("plan-b-total").textContent + "\")");
      ok(el("plan-b-total").textContent === "planned " + sumRowValue("Total time"),
         "SP3 AC-22 (Quinn Q2): header and summary are the same STRING — m:ss vs h:mm:ss drift between them cannot hide behind a matching parse");
      // The header must count the SAME thing the panel does. It read "9 items" beside a summary
      // saying "Items 6" — two headline numbers describing one run sheet and disagreeing.
      var secView = { plan_name:"Sec", items:[
        {id:601, kind:"section",      title:"GATHERING", is_live:false, is_staged:false},
        {id:602, kind:"song",         title:"Open",  is_live:false, is_staged:false, owner:"W", planned_secs:300},
        {id:603, kind:"section",      title:"WORD",  is_live:false, is_staged:false},
        {id:604, kind:"announcement", title:"Notes", is_live:false, is_staged:false, owner:"H", planned_secs:120}
      ] };
      planSelectedId = null;
      planRenderBuilder(secView);
      ok(el("plan-b-count").textContent === "2 items" && sumRowValue("Items") === "2",
         "SP3 AC-26: the run-sheet header counts triggerable rows, agreeing with the panel (header=\"" +
         el("plan-b-count").textContent + "\" panel=\"" + sumRowValue("Items") + "\")");
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 4,
         "SP3 AC-26 (control): all four rows including the dividers really are rendered — the count excludes them, the run sheet does not hide them");
      ok(sumRowValue("Assigned") === "2 / 2",
         "SP3 AC-26: Assigned excludes dividers too — a divider is not a staffable item, so a fully-staffed sectioned plan reads 2 / 2 and never 2 / 4");
      ok(!document.querySelector('#plan-b-list .plan-b-row[data-item-id="601"] .plan-b-dur'),
         "SP3 AC-26: an inert divider carries no duration on its row — its duration is excluded from the total, so a figure there would not be in the header");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- AC-4: the empty plan's counters, verbatim -------------------------------------------
      // AC-4 had no test at all, which is how the missing header total hid: with no total in the
      // header, the string AC-4 quotes could not be produced on any input.
      planSelectedId = null;
      planRenderBuilder({ plan_name:"E", items: [] });
      ok(el("plan-b-count").textContent === "0 items · 0:00",
         "SP3 AC-23 (AC-4): an empty plan's header counters read exactly \"0 items · 0:00\" (got \"" + el("plan-b-count").textContent + "\")");
      ok(sumRowValue("Items") === "0" && clockToSecs(sumRowValue("Total time")) === 0 && sumRowValue("Assigned") === "0 / 0",
         "SP3 AC-23 (AC-4): and the summary is zeroed too — not the previous plan's figures left standing");
      ok(!document.querySelector("#plan-b-list .plan-b-row") && !!document.querySelector("#plan-b-list .plan-empty"),
         "SP3 AC-23 (control): the empty state really rendered — the zeros describe an empty run sheet, not a failed render");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- host summary + `partial` (PR #13 contract, consumed not computed) -------------------
      // These drive the RENDERER with a synthetic host summary, so the consumption path is proven
      // against the agreed shape before the wire carries it — and so the swap cannot land wrong.
      // A host summary is only trusted when it DESCRIBES the items being rendered, so each of these
      // pairs a summary with items it actually adds up over. (The first draft of this block used
      // arbitrary figures and the new validator rejected every one of them — which is the guard
      // working.)
      function withSummary(items, sum) {
        planSelectedId = null;
        planRenderBuilder({ plan_name:"HS", items: items, summary: sum });
        return sumRowValue("Total time");
      }
      function hostSum(extra) {
        var o = { planned_total_secs:0, items:0, songs:0, scripture:0, presentations:0, media:0,
                  announcements:0, timers:0, sections:0, assigned:0, missing:0, unknown:0 };
        Object.keys(extra).forEach(function(k){ o[k] = extra[k]; });
        return o;
      }
      var SONG = function(id, secs) {
        var it = { id:id, kind:"song", title:"s"+id, is_live:false, is_staged:false };
        if (secs !== null) it.planned_secs = secs;
        return it;
      };
      ok(withSummary([SONG(301, 750), SONG(302, null)],
                     hostSum({ planned_total_secs:750, items:2, songs:2, partial:true, planned_items:1 })) === "0:12:30 · partial",
         "SP3 AC-24: a partial total with something planned reads as a real but incomplete sum plus the marker (got \"" + sumRowValue("Total time") + "\")");
      ok(withSummary([SONG(303, null), SONG(304, null)],
                     hostSum({ planned_total_secs:0, items:2, songs:2, partial:true, planned_items:0 })) === "— · partial",
         "SP3 AC-24: with planned_items 0 the figure is meaningless and reads \"— · partial\" — zero is a legitimate duration meaning instant (spec §4.1), so a 0 total does NOT imply nothing is set");
      ok(withSummary([SONG(305, 750)], hostSum({ planned_total_secs:750, items:1, songs:1, partial:false, planned_items:1 })) === "0:12:30",
         "SP3 AC-24 (control): a complete total carries no marker — 'partial' is not stuck on");
      ok(!/partial/i.test(document.querySelector("#plan-b-insp .plan-sum-total .plan-sum-value").getAttribute("aria-label")),
         "SP3 AC-24 (control): and the spoken form does not say partial either when it is complete");
      withSummary([SONG(306, null)], hostSum({ planned_total_secs:0, items:1, songs:1, partial:true, planned_items:0 }));
      ok(/partial/i.test(document.querySelector("#plan-b-insp .plan-sum-total .plan-sum-value").getAttribute("aria-label")) &&
         !!document.querySelector("#plan-b-insp .plan-sum-total.is-partial"),
         "SP3 AC-24 a11y: 'partial' is spoken and marked, and the word is in the TEXT so it is not colour-only");
      // The "inert sections never set partial" rule (spec §4.2) is the HOST's to enforce, and this
      // client cannot diverge from it because it never computes the flag. A plan that is nothing
      // but dividers, reported partial:false, must render no marker — the client must not
      // second-guess it into one.
      ok(withSummary([{id:201, kind:"section", title:"Gathering", is_live:false, is_staged:false},
                      {id:202, kind:"section", title:"The Word",  is_live:false, is_staged:false}],
                     hostSum({ planned_total_secs:0, items:0, sections:2, partial:false, planned_items:0 })) === "0:00:00" &&
         !document.querySelector("#plan-b-insp .plan-sum-total.is-partial"),
         "SP3 AC-24: a plan of inert section dividers is NOT marked partial — a warning that is always on is one coordinators learn to ignore");
      // --- Q13: the pass-through crosses a trust boundary and must validate ---------------------
      // None of these needs an attacker: a host one release ahead or behind produces them. Each
      // must fall back to the local computation, which is derived from the rendered items.
      //
      // THE DISCRIMINATOR, and why every check below was worth nothing without it. Falling back and
      // trusting the host have to RENDER DIFFERENTLY, or the assertion cannot say which path ran.
      // So the items carry OWNERS — the local path renders "Assigned 2 / 2" — and each malformed
      // summary claims assigned:1, a value that is perfectly VALID (1 <= 2, so no sub-condition
      // rejects it) yet one the local computation cannot produce for these items. Before this the
      // fixtures had no owners and hostSum defaults assigned:0, so "Assigned 0 / 2" rendered
      // identically down BOTH paths and distinguished nothing. That is how QA could delete eleven
      // of the nineteen guard sub-conditions one at a time — total-eq among them — and watch all
      // 947 checks stay green while this panel rendered "Total time: 27:46:39" over rows summing
      // 0:10:00, which is the §9 MAJOR itself, live.
      var q13Items = [SONG(311, 300), SONG(312, 300)]; // local: total 600 -> "0:10:00", owners -> "2 / 2"
      q13Items[0].owner = "Worship";
      q13Items[1].owner = "Host";
      function malformed(sum, label) {
        planSelectedId = null;
        planRenderBuilder({ plan_name:"M", items:q13Items, summary:sum });
        ok(sumRowValue("Total time") === "0:10:00" && sumRowValue("Items") === "2" &&
           sumRowValue("Songs") === "2" && sumRowValue("Assigned") === "2 / 2",
           "SP3 AC-25 (Q13): " + label + " falls back to the local computation (got total \"" +
           sumRowValue("Total time") + "\", Items \"" + sumRowValue("Items") + "\", Songs \"" +
           sumRowValue("Songs") + "\", Assigned \"" + sumRowValue("Assigned") + "\")");
      }
      // ISOLATION IS THE POINT, not coverage. Each fixture marked PINS is well-formed in every
      // respect EXCEPT the one sub-condition it names, so deleting that sub-condition fails exactly
      // this case and no other. Undeliberate overlap is what let the first round of these survive.
      // Measured, by deleting each of the NINETEEN sub-conditions of planSummaryIsSound in turn and
      // running this file: THIRTEEN are pinned and fail exactly one check, the case naming them.
      // One more, the `for` loop applying count() to SUMMARY_COUNTS, fails FOUR — it is the
      // container for four pinned sub-conditions, so that is containment, not masking: each of the
      // four is still individually pinned by its own case.
      // The remaining FIVE cannot be isolated by any input, because each is subsumed — not merely
      // overlapped — by a later check, and no value exists that only they reject:
      //   typeof and isFinite, on the total AND inside count(), are subsumed by Number.isInteger,
      //     which is false for every non-number and for Infinity, -Infinity and NaN alike;
      //   the total's >= 0 is subsumed by total-eq, because the local total is a sum of
      //     planHasDuration-validated values and so can never be negative.
      // They are kept anyway: they make the guard say what it means at the point it means it, and
      // they are cheap. What is NOT kept is a comment claiming a pin no fixture can supply.
      malformed({}, "an empty summary object"); // LAYERED: the type check and all eleven counts
      // LAYERED, and the ONLY fixture that reaches the finiteness check at all. isFinite is
      // subsumed by Number.isInteger, which returns false for Infinity, -Infinity and NaN alike:
      // no value exists that isFinite rejects and Number.isInteger accepts, so this sub-condition
      // is defence in depth and cannot be pinned. Kept because it is the case that exercises it.
      malformed(hostSum({ planned_total_secs:Infinity, items:2, songs:2, assigned:1 }), "a non-finite total");
      // LAYERED (regression case). 1e308 is FINITE — it never reaches the check above; the
      // week-long bound is what rejects it, with total-eq behind that. Kept for the exact historical
      // render, which is the string PLAN_MAX_ITEM_SECS and PLAN_MAX_TOTAL_SECS both exist to stop.
      malformed(hostSum({ planned_total_secs:1e308, items:2, songs:2, assigned:1 }), "a total at 1e308 (rendered 2.77e+304:58:56)");
      // LAYERED. A negative total is caught by the >= 0 check first, but can never be pinned: the
      // local total is a sum of planHasDuration-validated values, each >= 0, so a negative host
      // total can never equal it and total-eq always rejects it too.
      malformed(hostSum({ planned_total_secs:-1200, items:2, songs:2, assigned:1 }), "a negative total (rendered -1:-20:00)");
      // LAYERED, and the only fixture that reaches count()'s typeof check. Subsumed for the same
      // reason as isFinite above: Number.isInteger("1") is false, so the integrality check rejects
      // a string too and typeof can never be the sole rejector.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:"1" }), "a count that is a string rather than a number");
      // PINS count()'s integrality. 1.5 is a number, finite, non-negative, under the cap and not
      // greater than items, so only Number.isInteger can reject it. Counts are usize on the wire.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1.5 }), "a fractional count (\"1.5 / 2\")");
      // PINS count()'s non-negativity. -1 is a finite integer under the cap, and -1 > items is
      // false, so the assigned-exceeds-items check cannot catch it — only v >= 0 can.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:-1 }), "a negative count (\"-1 / 2\")");
      // PINS PLAN_MAX_COUNT. `sections` is deliberately the field used: it is excluded from `items`
      // by the settled rule and from the per-kind sum, so no other check reads it and the count cap
      // is the only thing standing between this panel and a six-figure row count.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, sections:100001 }), "a count beyond PLAN_MAX_COUNT");
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, partial:"yes" }), "a non-boolean partial"); // PINS the partial type check
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, partial:true }), "partial:true with no planned_items to disambiguate it"); // PINS the pairing rule
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:9 }), "more assigned items than items"); // PINS assigned <= items
      // PINS the per-kind sum. songs:5 over items:2 is otherwise sound, so only kinds !== items
      // rejects it. This was songs:7 on every fixture in the block, which is why several of them
      // could not tell a fallback from a trusted host object: they all tripped this one check.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:5, assigned:1 }), "per-kind counts that do not add up to items");
      // PINS the subset rule. Backend's own incoherence, mirrored: a duration set ON a section
      // reached planned_items while the section was absent from items, so planned_items could
      // exceed items and this panel would have rendered "7 of 6". A subset cannot exceed its whole.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, partial:true, planned_items:9 }), "planned_items exceeding items (\"7 of 6\")");
      // PINS the planned_items type/range check — the ONLY guard on this field, because
      // planned_items is deliberately NOT in SUMMARY_COUNTS (it is optional, so the loop cannot
      // require it) and the subset rule above only compares it. Without this check a host sending
      // the STRING "0" renders "0:10:00 · partial" — a real total, meaning "some items are
      // planned" — where planned_items:0 must render "— · partial", meaning "nothing is planned
      // and this figure is meaningless". `nothingPlanned` tests `=== 0`, which a string fails, so
      // dropping this check INVERTS the two-field distinction planned_items exists to carry.
      // "0" and not -1 on purpose: a string is rejected by count()'s typeof AND its integrality,
      // so neutralising either one alone leaves this fixture still rejected. -1 is rejected only
      // by count()'s v >= 0, which couples this case to that mutation — measured, it made the
      // negative-count case and this one fail together and cost count.nonneg its isolation.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, partial:true, planned_items:"0" }),
                "a planned_items that is a string rather than a number (\"0:10:00 · partial\" for what is really \"— · partial\")");
      // PINS missing + unknown <= items. Both counts are individually legal (2 <= 2) and every
      // other field is sound, so only their SUM can reject this — individually-correct fields that
      // do not add up are exactly what design QA rejected these frames for the first time round.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, missing:2, unknown:2 }),
                "missing + unknown exceeding items");
      // PINS total-eq — THE guard against this ticket's signature defect, and the one QA found
      // deletable with the suite green: a header total that does not describe the rows beneath it.
      // 99999 is a number, finite, integral, non-negative and inside the week-long bound, and every
      // count here adds up, so total-eq is the only check that can reject it.
      malformed(hostSum({ planned_total_secs:99999, items:2, songs:2, assigned:1 }),
                "a total that does not describe the rows being rendered (the \u00a79 MAJOR)");
      // A fractional total: finite, non-negative, in-bounds, and EQUAL to the fixture's own sum, so
      // only the integrality check can reject it. planned_total_secs is u32 on the wire.
      var fracItems = [SONG(331, 300.25), SONG(332, 300.25)];
      fracItems[0].owner = "Worship"; fracItems[1].owner = "Host";
      planSelectedId = null;
      planRenderBuilder({ plan_name:"F", items:fracItems,
                          summary: hostSum({ planned_total_secs:600.5, items:2, songs:2, assigned:1 }) });
      ok(sumRowValue("Assigned") === "2 / 2",
         "SP3 AC-25 (Q13): a fractional total is rejected even though it is finite, in range and agrees with its rows — only the integrality check can catch this one (Assigned=" +
         sumRowValue("Assigned") + ")");
      // Isolates PLAN_MAX_TOTAL_SECS: eight items at the per-item cap sum to 691200s, so the total
      // AGREES with the rows and every other check passes — only the week-long bound rejects it.
      // A corrupt plan claiming eight days of runtime is the real shape of this.
      var hugeItems = [];
      for (var hz = 0; hz < 8; hz++) hugeItems.push(SONG(400 + hz, 86400));
      planSelectedId = null;
      planRenderBuilder({ plan_name:"HUGE", items:hugeItems,
                          summary: hostSum({ planned_total_secs:691200, items:8, songs:8, assigned:5 }) });
      ok(sumRowValue("Assigned") === "0 / 8",
         "SP3 AC-25 (Q13): a total beyond the week-long bound is rejected even though it agrees with the rows and every other field is sound — only the bound can catch this one (Assigned=" +
         sumRowValue("Assigned") + ")");
      // Control: a WELL-FORMED summary is still used. Without this the guard could pass by
      // rejecting everything, which would silently disable PR #13 the day it merges.
      planSelectedId = null;
      planRenderBuilder({ plan_name:"OK", items:q13Items,
                          summary: hostSum({ planned_total_secs:600, items:2, songs:2, assigned:0, partial:true, planned_items:2 }) });
      ok(sumRowValue("Total time") === "0:10:00 · partial",
         "SP3 AC-25 (control): a sound host summary IS used — the guard rejects malformed input, not every input");
      // ...and it is genuinely the HOST's object, not the local fallback coincidentally agreeing:
      // the local computation cannot produce a partial marker at all.
      ok(!!document.querySelector("#plan-b-insp .plan-sum-total.is-partial"),
         "SP3 AC-25 (control): and the marker proves the host object was used — the local fallback carries no partial flag");
      // The DISCRIMINATOR itself, proven live in the accepting direction. Every malformed case
      // above concludes "the local path ran" from Assigned reading "2 / 2"; that inference is only
      // worth something if a trusted host summary can make the same row read something else. These
      // are the same two owned items, and the host's assigned:0 comes through as "0 / 2".
      ok(sumRowValue("Assigned") === "0 / 2",
         "SP3 AC-25 (control): the host's own assigned count is what renders when the summary is trusted — the field the malformed cases read is genuinely host-sourced, not a constant (Assigned=" +
         sumRowValue("Assigned") + ")");
      // Sections-not-items is UNSETTLED (frame 608:875 counts 6 items over 3 dividers), so the
      // guard must accept both readings rather than hard-code a decision nobody has made.
      planSelectedId = null;
      planRenderBuilder({ plan_name:"SX", items:[SONG(321, 600), {id:322, kind:"section", title:"D", is_live:false, is_staged:false}],
                          summary: hostSum({ planned_total_secs:600, items:1, songs:1, sections:1 }) });
      ok(sumRowValue("Items") === "1",
         "SP3 AC-25: a host summary excluding inert sections from `items` is accepted — that is the settled rule, and the per-kind rows sum to it");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- missing-content count: three-state link status -------------------------------------
      // Local deck resolution stays authoritative (the host has no deck store and cannot resolve a
      // deck_id), and an "unknown" status must never be counted as either missing or resolved-by-
      // fiat. Deck 2 resolves locally; deck 99 does not.
      var missView = { plan_name:"S", items:[
        {id:31, kind:"slide_group", title:"Gone",       is_live:false, is_staged:false, link:{kind:"deck", id:99}},
        {id:32, kind:"slide_group", title:"Present",    is_live:false, is_staged:false, link:{kind:"deck", id:2}},
        {id:33, kind:"media",       title:"Host: gone", is_live:false, is_staged:false, link:{kind:"media", id:7, status:"missing"}},
        {id:34, kind:"media",       title:"Unknown",    is_live:false, is_staged:false, link:{kind:"media", id:8, status:"unknown"}}
      ] };
      planSelectedId = null;
      planRenderBuilder(missView);
      ok(sumRowValue("Missing content") === "⚠ 2",
         "SP3 AC-4: Missing content counts the locally-unresolvable deck AND the host-flagged media (got " + sumRowValue("Missing content") + ")");
      ok(document.querySelectorAll("#plan-b-insp .plan-sum-warn").length === 1,
         "SP3 AC-4: a non-zero missing count is marked, and the ⚠ is in the TEXT so it is not colour-only");
      // Control for the "unknown" branch specifically. Item 34 is a NON-deck link carrying
      // status:"unknown" — it reaches the `status === "unknown"` return, which a deck link never
      // does (decks short-circuit into local resolution first). "Could not check" must not be
      // counted as broken; if it were, the count above would read 3.
      ok(planLinkState(missView.items[3].link) === "unknown",
         "SP3 AC-4 (control): a non-deck link with status 'unknown' resolves to unknown, not missing and not resolved-by-fiat");
      // Control for the OTHER unknown branch: a deck_list that never loaded. planDecks === null
      // must read unknown, so one transient deck_list failure cannot flag every deck-linked item
      // in the plan as broken. This is the branch a loaded fixture otherwise never exercises.
      var decksSaved = planDecks;
      planDecks = null;
      planRenderBuilder(missView);
      ok(planLinkState(missView.items[0].link) === "unknown" && sumRowValue("Missing content") === "⚠ 1",
         "SP3 AC-4 (control): with the deck list unloaded, deck links read unknown — only the host-flagged media counts missing (got " + sumRowValue("Missing content") + ")");
      planDecks = decksSaved;
      planRenderBuilder(missView);
      ok(sumRowValue("Missing content") === "⚠ 2",
         "SP3 AC-4 (control): restoring the deck list restores the real count — the unknown path is a state, not a latch");
      // Regression, found by rendering the real dist in WebKit: a host that answers deck_list with
      // null must read as UNKNOWN, not as a loaded-and-empty library. `(r && r.decks) || []` made
      // a null response mean "the library is empty", so every deck-linked item was flagged
      // "⚠ presentation missing" and counted here — the false alarm the catch branch exists to
      // prevent, reached through the success path instead.
      window.__deckListNullOnce = true;
      await planLoadDecks();
      ok(planDecks === null, "SP3 AC-4 (regression): a null deck_list response reads UNKNOWN, not an empty library");
      planRenderBuilder(missView);
      ok(sumRowValue("Missing content") === "⚠ 1",
         "SP3 AC-4 (regression): with the deck library unreadable, deck links are NOT counted missing — only the host-flagged media is (got " + sumRowValue("Missing content") + ")");
      await planLoadDecks();
      ok(Array.isArray(planDecks) && planDecks.length > 0,
         "SP3 AC-4 (control): a well-formed deck_list still loads the library — the guard rejects malformed responses, not every response");
      planRenderBuilder(missView);
      planRenderBuilder(sumView);
      ok(sumRowValue("Missing content") === "0" && !document.querySelector("#plan-b-insp .plan-sum-warn"),
         "SP3 AC-4 (control): a plan with nothing missing reads 0 and is NOT marked — the marker is not stuck on");
      // --- the panel swaps with selection, and the heading says which panel this is ------------
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY", "SP3 AC-2: with nothing selected the right panel is headed PLAN SUMMARY");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(el("plan-insp-h").textContent === "ITEM" && !document.querySelector("#plan-b-insp .plan-sum-card"),
         "SP3 AC-2: selecting an item swaps the summary for the item inspector, and the heading follows");
      planSelectedId = null;
      planRenderBuilder(sumView);
      ok(!!document.querySelector("#plan-b-insp .plan-sum-card"), "SP3 AC-2: clearing the selection brings the summary back");
      // --- the two write actions are present, honest, and slotted for 86ak8467m ---------------
      ok(!!el("plan-sum-publish") && el("plan-sum-publish").disabled,
         "SP3 AC-5: 'Publish to team' is PRESENT and disabled — not hidden (an operator must be able to find it) and not wired to a no-op");
      ok(!!el("plan-sum-precheck") && el("plan-sum-precheck").disabled, "SP3 AC-5: 'Run pre-service check' is present and disabled");
      ok(el("plan-sum-publish").getAttribute("aria-describedby") === "plan-sum-later" && !!el("plan-sum-later"),
         "SP3 AC-5 a11y: the disabled actions point at a stated reason, so AT hears why they are unavailable");
      ok(!!el("plan-sum-live") && !el("plan-sum-live").disabled,
         "SP3 AC-5 (control): 'Open in Live' in the SAME panel is enabled — 'disabled' means not-yet-built, not a dead panel");
      // Open in Live is a pure surface switch: it must never send a live-control command.
      // Assert what is FORBIDDEN, not a raw call count: a 1 Hz `view` poll runs throughout the
      // gate, so counting every call makes this pass or fail on timing rather than on behaviour.
      var liveCallsBefore = window.__calls.length;
      el("plan-sum-live").click();
      await sleep(20);
      var during = window.__calls.slice(liveCallsBefore).map(function(c){ return c.cmd; });
      // Name what is FORBIDDEN rather than allowlisting reads: the console polls view /
      // detection_health / link_status continuously, so a new poll must not break this, while any
      // command that commits to Live or edits the plan must.
      var FORBIDDEN = ["go_live","deck_go_live","deck_go_live_delta","blackout","clear","next","previous",
                       "select","select_slide","stage_scripture","present_plan_deck_slide",
                       "add_item","move_item","remove_item","rename_item","set_item_content","plan_undo","plan_redo"];
      var offended = during.filter(function(c){ return FORBIDDEN.indexOf(c) >= 0; });
      ok(offended.length === 0,
         "SP3 AC-6 invariant: 'Open in Live' only switches surface — it commits nothing to Live and edits no plan item (saw: " + (offended.join(",") || "none") + ")");
      // --- unset durations: OMITTED, per 86ak846ft AC-1 ("without a gap or placeholder text") ---
      // UI-A1 FR-202 asks for a "—" placeholder instead. The two acceptance criteria genuinely
      // conflict and DECISION 86ak84cth owns it; this pins the CURRENT contract so a silent switch
      // to either behaviour fails here rather than surprising whichever spec wins.
      var partialView = { plan_name:"P", items:[
        {id:41, kind:"song",        title:"Has one",  is_live:false, is_staged:false, owner:"W", planned_secs:300},
        {id:42, kind:"song",        title:"Has none", is_live:false, is_staged:false, owner:"W"},
        {id:43, kind:"announcement",title:"Zero",     is_live:false, is_staged:false, owner:"H", planned_secs:0}
      ] };
      planSelectedId = null;
      planRenderBuilder(partialView);
      ok(!document.querySelector('#plan-b-list .plan-b-row[data-item-id="42"] .plan-b-dur'),
         "SP3 AC-8: an item with no planned duration renders NO duration element (86ak846ft AC-1; the UI-A1 em-dash is DECISION 86ak84cth)");
      // An explicit 0 is SET, not unset — guards the predicate against a truthiness bug.
      var zeroRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="43"] .plan-b-dur');
      ok(!!zeroRow && zeroRow.textContent.trim() === "0:00",
         "SP3 AC-8 (control): planned_secs 0 is a SET duration and renders 0:00 — the omission is 'absent', not 'falsy'");
      ok(clockToSecs(sumRowValue("Total time")) === rowDurationSum(),
         "SP3 AC-8: the total still equals the sum of the durations that ARE set");
      // KNOWN GAP pinned deliberately: the total excludes unplanned items with no marker. `partial`
      // must be computed in ONE place, the same place as the sum (PLAN-SECTIONS-DURATIONS §128),
      // and that place is the host's PlanSummaryView — which does not carry it yet (raised on PR
      // #13). Computing it here would make THIS surface look right while the mobile client and the
      // Live Console panel stayed wrong. This asserts the gap is not silently "fixed" locally.
      ok(!/partial/i.test(sumRowValue("Total time")),
         "SP3 AC-8 (pinned gap): the total carries no locally-computed 'partial' — that flag belongs on the wire beside the sum, not in this one client");
      // Hostile numerics must not corrupt the total (Sana S3): out of range is treated as UNSET.
      planRenderBuilder({ plan_name:"X", items:[
        {id:44, kind:"song", title:"Neg",  is_live:false, is_staged:false, planned_secs:-1200},
        {id:45, kind:"song", title:"Huge", is_live:false, is_staged:false, planned_secs:1e308},
        {id:46, kind:"song", title:"Real", is_live:false, is_staged:false, planned_secs:600}
      ] });
      ok(sumRowValue("Total time") === "0:10:00",
         "SP3 AC-8 (Sana S3): a negative or non-finite planned_secs is treated as UNSET, so it cannot render -1:-15:00 or Infinity:NaN:NaN (got " + sumRowValue("Total time") + ")");
      ok(document.querySelectorAll("#plan-b-list .plan-b-dur").length === 1,
         "SP3 AC-8 (Sana S3 control): only the one in-range duration renders — the guard rejects bad values, not every value");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- unknown is counted separately from missing, and never merged into it ----------------
      // The host structurally cannot resolve decks or media, so it returns "unknown" for both.
      // Collapsing that into "resolved" is the failure the three-state field exists to prevent.
      var unkView = { plan_name:"U", items:[
        {id:51, kind:"media",       title:"Unresolvable media", is_live:false, is_staged:false, link:{kind:"media", id:9, status:"unknown"}},
        {id:52, kind:"slide_group", title:"Gone deck",          is_live:false, is_staged:false, link:{kind:"deck", id:99}}
      ] };
      planRenderBuilder(unkView);
      ok(planSummaryOf(unkView).unknown === 1 && planSummaryOf(unkView).missing === 1,
         "SP3 AC-9: unknown and missing are counted SEPARATELY — 'the host could not check' is not 'it is fine'");
      ok(sumRowValue("Missing content") === "⚠ 1",
         "SP3 AC-9 (control): the unknown item is NOT folded into the missing count");
      // The summary object mirrors OperatorStateView.summary field-for-field, so adopting the
      // host's summary is a swap of planSummaryOf's body and nothing else.
      var shape = planSummaryOf(sumView);
      var WIRE = ["items","songs","scripture","presentations","media","announcements","timers","sections","assigned","missing","unknown","planned_total_secs"];
      var absent = WIRE.filter(function(k){ return !(k in shape); });
      ok(absent.length === 0,
         "SP3 AC-10: the local summary carries every OperatorStateView.summary field, so the backend swap is one function (missing: " + (absent.join(",") || "none") + ")");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- QA-review remediation (Quinn, PR #12): these guard fixes whose probes were transient ---
      showSurface("plan");
      await sleep(40);
      // P1: the per-kind rows must ALWAYS sum to Items, including kinds the demo frame has none of.
      var kindsView = { plan_name:"K", items:[
        {id:61, kind:"song",    title:"S", is_live:false, is_staged:false, planned_secs:60},
        {id:62, kind:"timer",   title:"T", is_live:false, is_staged:false, planned_secs:60},
        {id:63, kind:"section", title:"Sec", is_live:false, is_staged:false, planned_secs:60},
        {id:64, kind:"media",   title:"M", is_live:false, is_staged:false, planned_secs:60}
      ] };
      planSelectedId = null;
      planRenderBuilder(kindsView);
      var kindSum = ["Songs","Scripture","Presentations","Media","Announcements","Timers"]
        .reduce(function(a,k){ return a + Number(sumRowValue(k)); }, 0);
      ok(String(kindSum) === sumRowValue("Items"),
         "SP3 AC-11 (Quinn P1): the per-kind rows sum to Items for every kind, so a reader's arithmetic adds up (kinds=" + kindSum + " vs Items=" + sumRowValue("Items") + ")");
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 4,
         "SP3 AC-11 (control): the run sheet really did render all four kinds");
      // P5c: a long owner must not crush the title to nothing (WKWebView trap #1, owner side).
      var longView = { plan_name:"L", items:[{id:71, kind:"song", title:"A reasonably long item title here",
        is_live:false, is_staged:false, owner:"Wednesday Evening Worship Team Coordinator", planned_secs:300}] };
      planRenderBuilder(longView);
      var lRow = document.querySelector('#plan-b-list .plan-b-row');
      var lTitle = lRow.querySelector(".plan-b-title");
      // The bug was titleW=0 — total collapse. The floor on .plan-b-main stops that. In a SQUEEZED
      // column the title is still short, because the ↑↓ tools (66px) and the type badge (33px) are
      // fixed and the owner has already yielded to ~7px; that is geometry, not a starvation bug.
      // What must hold is that the title never disappears and the owner yields FIRST.
      ok(lTitle.getBoundingClientRect().width > 20,
         "SP3 AC-12 (Quinn P5c): a very long owner never crushes the title out of existence (titleW=" + Math.round(lTitle.getBoundingClientRect().width) + ")");
      ok(lRow.querySelector(".plan-b-owner").getBoundingClientRect().width < lTitle.getBoundingClientRect().width,
         "SP3 AC-12: under pressure the OWNER yields before the title — priority is title > duration > owner");
      ok(lRow.scrollWidth <= lRow.clientWidth + 2,
         "SP3 AC-12 (Quinn P5): a very long owner does not overflow its row (scrollW=" + lRow.scrollWidth + " clientW=" + lRow.clientWidth + ")");
      ok(lRow.querySelector(".plan-b-dur").getBoundingClientRect().width > 20,
         "SP3 AC-12 (control): the duration is never the thing that gets truncated — a clipped time is worse than a clipped name");
      // P9: a 65-minute row must not read "65:00".
      planRenderBuilder({ plan_name:"H", items:[{id:81, kind:"song", title:"Long", is_live:false, is_staged:false, planned_secs:3900}] });
      var hDur = document.querySelector("#plan-b-list .plan-b-dur").textContent.trim();
      ok(hDur === "1:05:00",
         "SP3 AC-13 (Quinn P9): a 65-minute row reads h:mm:ss like the total, not '65:00' (got " + hDur + ")");
      ok(document.querySelector("#plan-b-list .plan-b-dur").getAttribute("aria-label") === "Planned 1 hour 5 minutes",
         "SP3 AC-13: and its spoken form is unambiguous");
      // P8: the per-type accent bar (handoff §3), decorative — the badge carries the type as text.
      planSelectedId = null;
      planRenderBuilder(sumView);
      var acc = document.querySelector('#plan-b-list .plan-b-row[data-item-id="23"] .plan-b-accent');
      ok(!!acc && acc.classList.contains("kind-scripture"),
         "SP3 AC-14 (Quinn P8): run-sheet rows carry a per-type accent bar");
      ok(acc.getAttribute("aria-hidden") === "true",
         "SP3 AC-14 a11y: the accent bar is decorative — the type badge carries the same information as TEXT, so colour is never the only cue");
      ok(document.querySelectorAll("#plan-b-list .plan-b-accent").length === document.querySelectorAll("#plan-b-list .plan-b-row").length,
         "SP3 AC-14 (control): every row gets one, not just the typed ones");
      // P7: the landmark must follow the heading rather than claim "Item inspector" throughout.
      var aside = document.getElementById("plan-insp-panel");
      ok(aside.getAttribute("aria-labelledby") === "plan-insp-h" && !aside.getAttribute("aria-label"),
         "SP3 AC-15 (Quinn P7): the right panel is labelled BY its heading, so it never announces the wrong panel");
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY",
         "SP3 AC-15 (control): and that heading currently reads PLAN SUMMARY");
      // P6: swapping the panel must not strand focus on <body>.
      el("plan-sum-live").focus();
      ok(document.activeElement === el("plan-sum-live"), "SP3 AC-16 (setup): focus is inside the Plan Summary panel");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(document.activeElement !== document.body,
         "SP3 AC-16 (Quinn P6): swapping the summary for the inspector does not strand focus on <body> (activeElement=" + document.activeElement.tagName + ")");
      // Control: a swap with focus OUTSIDE the panel must NOT steal it — otherwise the fix would
      // yank focus away from the run sheet on every background re-render.
      planSelectedId = null;
      planRenderBuilder(sumView);
      var outside = document.querySelector('#plan-b-list .plan-b-row[data-item-id="22"]');
      outside.focus();
      planRenderBuilder(sumView);
      // Asserts what planKeepPanelFocus OWNS: it must not PULL focus into the panel when focus was
      // outside it. (Where focus lands after a run-sheet rebuild is separate, pre-existing
      // behaviour — planFocusAfterRender is deliberately null on a background re-render.)
      ok(!el("plan-b-insp").contains(document.activeElement),
         "SP3 AC-16 (control): a rebuild with focus OUTSIDE the panel does not steal focus into it (activeElement=" + document.activeElement.tagName + ")");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- Sana S1: local deck truth outranks a host-stamped status ---------------------------
      // The host has no deck store, so its verdict on a deck is never ground truth. A deck the
      // operator can SEE is not missing because the host said so.
      ok(planLinkState({kind:"deck", id:2, status:"missing"}) === "resolved",
         "SP3 AC-17 (Sana S1): a deck present in the local library resolves even when the host stamped status:missing");
      ok(planLinkState({kind:"deck", id:99, status:"missing"}) === "missing",
         "SP3 AC-17 (control): a deck absent locally is still missing — local truth decides BOTH ways, it does not merely ignore the host");
      var savedDecks = planDecks;
      planDecks = null;
      ok(planLinkState({kind:"deck", id:2, status:"missing"}) === "missing" && planLinkState({kind:"deck", id:2}) === "unknown",
         "SP3 AC-17: with no local library there is no ground truth, so the host's status is the fallback and silence reads unknown");
      planDecks = savedDecks;
      // --- Sana S2: one verdict per link, shared by the chip and the summary -------------------
      var s2View = { plan_name:"S2", items:[
        {id:91, kind:"media", title:"Host says gone", is_live:false, is_staged:false, link:{kind:"media", id:3, status:"missing"}},
        {id:92, kind:"media", title:"Fine",           is_live:false, is_staged:false, link:{kind:"media", id:4}}
      ] };
      planSelectedId = null;
      planRenderBuilder(s2View);
      // THE assertion behind planLinkState's stated purpose: what is DRAWN missing and what is
      // COUNTED missing must be the same set. Previously the chip ignored `status` while the
      // summary honoured it, so the panel read "⚠ 1" with no visibly-missing row.
      ok(document.querySelectorAll("#plan-b-list .link-missing").length === Number(String(sumRowValue("Missing content")).replace(/\D/g, "")),
         "SP3 AC-18 (Sana S2): the rows DRAWN missing equal the summary's missing count — one verdict, not two (drawn=" +
         document.querySelectorAll("#plan-b-list .link-missing").length + " counted=" + sumRowValue("Missing content") + ")");
      ok(/media missing/i.test(document.querySelector('#plan-b-list .plan-b-row[data-item-id="91"] .link-chip').textContent),
         "SP3 AC-18: a host-flagged missing medium is drawn missing, not as a healthy chip");
      ok(!document.querySelector('#plan-b-list .plan-b-row[data-item-id="92"] .link-chip').classList.contains("link-missing"),
         "SP3 AC-18 (control): a medium with no status is NOT drawn missing — the treatment is not stuck on");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- Cody BLOCKER 1: the way back to the Plan Summary must exist as a GESTURE -----------
      // AC-2 above proved nothing about reachability: it restores the summary by assigning
      // planSelectedId = null, which no operator can do. Selecting a row was a one-way door, and
      // it took Publish / Run pre-service check (the 86ak8467m seam) with it.
      planSelectedId = null;
      planRenderBuilder(sumView);
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(el("plan-insp-h").textContent === "ITEM", "SP3 AC-19 (setup): clicking a row opens the item inspector");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(40);
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY" && !!el("plan-sum-publish"),
         "SP3 AC-19 (Cody BLOCKER 1): Escape returns to the Plan Summary, so Publish is reachable again after a row has been selected");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(el("plan-insp-h").textContent === "ITEM", "SP3 AC-19 (setup): re-selected, for the pointer path");
      el("plan-b-list").click(); // the empty area below the rows — target is the list itself
      await sleep(40);
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY",
         "SP3 AC-19 (Cody BLOCKER 1): clicking the empty run-sheet area also deselects");
      // Control: Escape with nothing selected must not fire a pointless refetch.
      var cardBefore = document.querySelector("#plan-b-insp .plan-sum-card");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);
      ok(document.querySelector("#plan-b-insp .plan-sum-card") === cardBefore,
         "SP3 AC-19 (control): Escape with nothing selected does not rebuild the panel — it is a genuine no-op, not a rebuild on every keypress");
      // --- Cody HIGH 4: the summary must not report a plan that is loading or failed to open ---
      planSelectedId = null;
      planRenderBuilder(sumView);
      ok(!!document.querySelector("#plan-b-insp .plan-sum-card"), "SP3 AC-20 (setup): the summary is showing real figures");
      planRenderLoading();
      ok(!document.querySelector("#plan-b-insp .plan-sum-card") && !!document.querySelector("#plan-b-insp .plan-sum-blank"),
         "SP3 AC-20 (Cody HIGH 4): loading clears the summary — it must not report the previous plan's figures beside a skeleton run sheet");
      planRenderLoading();
      planRenderLoadFailed(new Error("x"));
      ok(!document.querySelector("#plan-b-insp .plan-sum-card") && /unavailable/i.test(el("plan-b-insp").textContent),
         "SP3 AC-20 (Cody HIGH 4): after a failed open the panel says figures are unavailable, not 'Items 6 · 0:53:12' next to 'Couldn't open the plan'");
      // --- focus retention, exercised properly --------------------------------------------------
      // AC-16 could not reach planKeepPanelFocus: clicking a row focuses the ROW, so focus was
      // never inside the panel at rebuild time. This drives the actual path — a background
      // re-render under a focused panel control.
      planSelectedId = null;
      planRenderBuilder(sumView);
      el("plan-sum-live").focus();
      planRenderBuilder(sumView);
      ok(el("plan-insp-panel").contains(document.activeElement),
         "SP3 AC-16b: a rebuild under a focused panel control keeps focus in the panel rather than dropping it to <body> (activeElement=" + document.activeElement.tagName + ")");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- the Plan Summary must stay REACHABLE as it grows (WKWebView trap #2 family) ---------
      // Adding the Timers/Sections rows pushed the panel's last element below the emergency
      // footer. That is fine only because #surface-plan scrolls; if a future row made the panel
      // taller than the scroll container allows, the bottom of the summary would be permanently
      // obscured. Note the weaker check this replaces: the grid's own scrollHeight === clientHeight
      // stayed equal the whole time the content was overflowing, so it proved nothing.
      planSelectedId = null;
      planRenderBuilder(sumView);
      var surf = el("surface-plan");
      var hint = document.querySelector("#plan-b-insp .plan-sum-hint");
      ok(!!hint, "SP3 AC-21 (setup): the summary's last element exists");
      // Self-referential to the SCROLL CONTAINER, not to the footer: the footer sits in different
      // places under the gate's layout than in the real window, so a footer-relative assertion
      // would measure the harness rather than the product.
      // FORCE the overflow. At the gate's viewport the panel happens to fit, so the assertion
      // would be trivially true and guard nothing (it survived an overflow-y:hidden mutation until
      // this was added). Squeezing the surface reproduces the real-window condition, where the
      // panel's last element sits below the fold.
      var savedH = surf.style.height;
      surf.style.height = "200px";
      ok(hint.getBoundingClientRect().bottom > Math.round(surf.getBoundingClientRect().top + surf.clientHeight),
         "SP3 AC-21 (premise): with the surface squeezed the summary really does overflow — otherwise the reachability check below proves nothing");
      // The container must be USER-scrollable, not merely script-scrollable: overflow-y:hidden
      // still honours a programmatic scrollTop, so scrolling in a test and finding the element
      // proves nothing about whether an operator could ever reach it.
      var ovf = getComputedStyle(surf).overflowY;
      ok(ovf === "auto" || ovf === "scroll",
         "SP3 AC-21: the plan surface is user-scrollable (overflow-y=" + ovf + "), so overflowing panel content is reachable by a person and not just by script");
      surf.scrollTop = surf.scrollHeight;
      var surfBottom = Math.round(surf.getBoundingClientRect().top + surf.clientHeight);
      ok(Math.round(hint.getBoundingClientRect().bottom) <= surfBottom + 1,
         "SP3 AC-21: the bottom of the Plan Summary can be scrolled into the surface's visible area — a taller panel must never become unreachable (hint=" +
         Math.round(hint.getBoundingClientRect().bottom) + " surfaceBottom=" + surfBottom + ")");
      surf.scrollTop = 0;
      surf.style.height = savedH;
      // --- loading (frame 611:350) ------------------------------------------------------------
      planRenderLoading();
      ok(document.querySelectorAll("#plan-b-list .plan-skel-row").length > 0, "SP3 AC-7: opening the plan paints skeleton rows");
      var lmsg = document.querySelector("#plan-b-list .plan-loading-msg");
      ok(!!lmsg && lmsg.getAttribute("role") === "status" && /scanning for missing content/i.test(lmsg.textContent),
         "SP3 AC-7 a11y: the wait is announced via role=status and names the missing-content scan, not just drawn");
      ok(document.querySelector("#plan-b-list .plan-skel-row").getAttribute("aria-hidden") === "true",
         "SP3 AC-7 a11y: the skeleton rows are aria-hidden — texture, not four empty rows announced to AT");
      ok(el("plan-b-count").textContent === "—",
         "SP3 AC-7: the count reads — while loading, rather than showing a stale count as if it were current");
      // Positive control: the skeleton is REPLACED by real content. Without this, "paints a
      // skeleton" would pass just as well on a loading state that never resolves.
      planSelectedId = null;
      planRenderBuilder(sumView);
      ok(!document.querySelector("#plan-b-list .plan-skel-row") && document.querySelectorAll("#plan-b-list .plan-b-row").length === 6,
         "SP3 AC-7 (control): the first real render clears the skeleton — the loading state is not stuck");
      ok(el("plan-b-count").textContent === "6 items", "SP3 AC-7 (control): and the real count replaces the — placeholder");
      // A failed open must not leave the skeleton up forever: an endless loading state is a lie
      // about work still being in flight.
      planRenderLoading();
      planRenderLoadFailed(new Error("boom"));
      var lfail = document.querySelector("#plan-b-list .plan-load-failed");
      ok(!!lfail && lfail.getAttribute("role") === "alert" && !document.querySelector("#plan-b-list .plan-skel-row"),
         "SP3 AC-7: a failed open replaces the skeleton with a role=alert message instead of spinning forever");
      ok(/Live output is unaffected/.test(lfail.textContent),
         "SP3 AC-7: the failure says the audience is unaffected (NFR-024) rather than implying live output is at risk");
      // Control: a LATE failure must not wipe a run sheet that already painted.
      planRenderBuilder(sumView);
      planRenderLoadFailed(new Error("late"));
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 6 && !document.querySelector("#plan-b-list .plan-load-failed"),
         "SP3 AC-7 (control): a late rejection does not clobber a run sheet that already rendered");
      showSurface("plan");
      await sleep(40);
      planRenderBuilder(planView); // restore before the nav check
      // #9/#10 "Open in Live ▶" is a real, NAV-ONLY control (it was a dead button) — it switches to
      // the Live Console and sends no live-control command.
      el("plan-open-live").click();
      ok(el("surface-console").classList.contains("active") && !el("surface-plan").classList.contains("active"),
         "SP C-006: 'Open in Live' navigates to the Live Console (nav-only, not a go-live)");
      // C-006 invariant: the whole builder session (incl. Open-in-Live) sent NOT ONE live-control command.
      ok(window.__calls.filter(isLiveCtrl).length === ctrlBefore,
         "SP C-006: no plan-builder interaction sent a live-control command (staging/linking never changes Live)");

      // ==================================================================================
      // PLAN LIFECYCLE (86ak8467m) — frames 608:875 (publish), 611:124 (empty state),
      // 612:342 (view only), 612:1020 (change badge), against the settled 86ajy0hwg wire
      // shape: five commands behind the EXISTING EditPlan permission, and three appended
      // view fields (viewer / publish / plan_templates), every one of them skip-if-none.
      //
      // The three semantics under test are the three that fabricate state when got wrong:
      // an ABSENT field is not a negative verdict; can_edit is the host's verdict and is
      // never re-derived from role; and `changed` means nothing without a baseline.
      // ==================================================================================
      showSurface("plan");
      await sleep(80); // let planActivate's two async renders land before we drive our own
      var PL_ITEMS = [
        { id: 301, kind: "song",      title: "Opening", is_live: false, is_staged: false },
        { id: 302, kind: "scripture", title: "Reading", is_live: false, is_staged: false }
      ];
      var lifeView = function (extra) {
        var v = { plan_name: "Sunday AM", items: JSON.parse(JSON.stringify(PL_ITEMS)) };
        for (var k in (extra || {})) v[k] = extra[k];
        return v;
      };
      var emptyLife = function (extra) { var v = lifeView(extra); v.items = []; return v; };
      var openPlan = function (view) { planSelectedId = null; planRenderBuilder(view); };
      var palette = function () { return document.querySelector("#surface-plan .plan-palette"); };
      var paletteShown = function () { return getComputedStyle(palette()).display !== "none"; };
      var plCalls = function (cmd) { return window.__calls.filter(function (c) { return c.cmd === cmd; }); };
      var dlgOk = function () { return document.querySelector(".pm-confirm .pm-confirm-actions .pm-btn-primary"); };
      // Null-safe on purpose. Dereferencing .plan-pub-line directly turned a real defect —
      // requiring `version`, which makes every skip-if-default draft read as unreported — into a
      // THROWN exception that aborted the driver at check 728 instead of failing the check that
      // names the rule. A control that dies rather than reporting tells you something is wrong
      // but not what.
      var pubLine = function () { var n = document.querySelector("#plan-b-insp .plan-pub-line"); return n ? n.textContent : ""; };
      // THE REAL WIRE SHAPES. PublishStateView is #[serde(default)] with skip-if-none /
      // skip-if-zero / skip-if-false, so the fixtures below carry exactly the keys the host
      // actually sends — a fixture that spelled out the defaults would test a shape that never
      // arrives, and would have hidden the bug where requiring `version` made every real draft
      // read as unreported.
      var PUB_DRAFT   = { revision: 0 };                                        // fresh draft: the WHOLE object
      var PUB_CLEAN   = { revision: 5, published_revision: 5, version: 4 };      // no `changed` key
      var PUB_CHANGED = { revision: 7, published_revision: 5, version: 4, changed: true };
      // Touched but NOT different: an edit that was undone. Revisions differ, content does not.
      var PUB_TOUCHED = { revision: 9, published_revision: 5, version: 4 };
      var PL_TEMPLATES = [
        { id: "sunday-morning", name: "Sunday Morning",    items: 5 },
        { id: "midweek",        name: "Midweek Gathering", items: 4 }
      ];

      // --- viewer: three states, and the absent one is NOT view-only --------------------------
      openPlan(lifeView());
      ok(!el("plan-viewonly"),
         "PL AC-1: an ABSENT viewer draws no 'View only' badge — a host declining to report a permission is not a host imposing one");
      ok(paletteShown(),
         "PL AC-1: ...and hides no editing control (the Add-item column is still displayed)");
      ok(!!document.querySelector('#plan-b-list .plan-b-row[data-item-id="301"] .plan-b-up'),
         "PL AC-1: ...and the run-sheet reorder controls are still on the rows");

      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false } }));
      ok(!!el("plan-viewonly") && /view only/i.test(el("plan-viewonly").textContent),
         "PL AC-2 (frame 612:342): can_edit:false draws the 'View only' badge as TEXT, never colour alone");
      // COMPUTED display, not the hidden attribute: in this webview a class-level display rule
      // silently defeats `hidden`, so the assertion has to ask the CSS engine.
      ok(getComputedStyle(palette()).display === "none",
         "PL AC-2: view-only hides the Add-item column — asserted as COMPUTED display, so a class rule cannot defeat it");
      ok(!document.querySelector("#plan-b-list .plan-b-up") && !document.querySelector("#plan-b-list .plan-b-down") &&
         !document.querySelector("#plan-b-list .plan-b-handle"),
         "PL AC-2 (UX-STATE-MATRIX:111): reorder controls are REMOVED, not greyed — so they leave the tab order too");
      // Hiding a GRID CHILD does not remove its track. With three fixed tracks and the first
      // child out of flow, every remaining child shifts one place left — the run sheet landed in
      // the 220px palette track and truncated every title, beside an empty third track. Found by
      // looking at a real WKWebView render; asserted here on the resolved track list so the
      // regression is caught by the fast gate.
      var voTracks = getComputedStyle(document.querySelector("#surface-plan .plan-builder-grid")).gridTemplateColumns.trim().split(/\s+/);
      ok(voTracks.length === 2,
         "PL AC-2 layout: with the ADD ITEM column hidden the grid drops its TRACK too — otherwise the run sheet inherits the 220px palette column and truncates every title (tracks: " + voTracks.join(" | ") + ")");
      var voSheet = document.querySelector("#surface-plan .plan-runsheet").getBoundingClientRect().width;
      ok(voSheet > 400,
         "PL AC-2 layout: ...so the run sheet still gets the wide column (" + Math.round(voSheet) + "px)");
      ok(!el("plan-sum-publish"),
         "PL AC-2: Publish is removed under view-only rather than shown disabled");

      // THE control that dies the moment anyone re-derives the verdict from the role name.
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: true }, publish: PUB_CLEAN }));
      ok(paletteShown() && !!document.querySelector("#plan-b-list .plan-b-up") && !!el("plan-sum-publish") && !el("plan-viewonly"),
         "PL AC-3: role='viewer' with can_edit:TRUE still edits — the host's verdict is consumed, never recomputed from the role (the rbac.dart drift this field exists to remove)");
      openPlan(lifeView({ viewer: { role: "operator", can_edit: false }, publish: PUB_CLEAN }));
      ok(!!el("plan-viewonly") && !el("plan-sum-publish") && !paletteShown(),
         "PL AC-3 (mirror): role='operator' with can_edit:FALSE is view-only — the verdict decides in BOTH directions, it does not merely ignore the role in one");
      openPlan(lifeView({ viewer: { role: "producer" } }));
      ok(!el("plan-viewonly") && paletteShown(),
         "PL AC-3: a viewer object carrying no can_edit boolean says nothing, so it reads UNREPORTED rather than restricted");
      // The Tauri path always carries the KEY, so `null` is the shape an unreported viewer
      // actually takes there. Reading it as view-only would take controls away from an operator
      // who has them — the mirror of the fabrication this field exists to prevent.
      openPlan(lifeView({ viewer: null, plan_templates: [] }));
      ok(!el("plan-viewonly") && paletteShown() && !!document.querySelector("#plan-b-list .plan-b-up"),
         "PL AC-3: an explicit viewer:null is UNREPORTED, not view-only — the key being present says nothing about the verdict");

      // --- publish: absent / draft / published / edited-since ---------------------------------
      openPlan(lifeView());
      ok(!document.querySelector("#plan-b-insp .plan-pub") && !el("plan-pub-changed"),
         "PL AC-4: an ABSENT publish field says nothing about publication — no version, no draft label, no badge");
      ok(!!el("plan-sum-publish") && el("plan-sum-publish").disabled &&
         el("plan-sum-publish").getAttribute("aria-describedby") === "plan-sum-later" && !!el("plan-sum-later"),
         "PL AC-4: ...and Publish is PRESENT, disabled, and points at a stated reason — never hidden, never a no-op");

      openPlan(lifeView({ publish: PUB_DRAFT }));
      ok(!el("plan-pub-changed") && /not published yet/i.test(pubLine()),
         "PL AC-5: with published_revision absent there is no baseline, so the panel reads draft and draws NO change badge");
      ok(!!document.querySelector("#plan-b-insp .plan-pub"),
         "PL AC-5: ...and a bare {revision:0} is still REPORTED, not mistaken for an absent field — the host omits every default-valued key, so requiring `version` here would silence the panel on every real draft");
      openPlan(lifeView({ publish: { revision: 3, version: 0, changed: true } }));
      // Mutation-verified: deleting `published &&` from planPublishState's `changed` turns this
      // RED. It did NOT, on the first attempt, because the renderer re-derived `!pub.published`
      // beside the predicate instead of consuming it — a control asserting a copy (CLAUDE.md's
      // 86ak643rc trap). The renderer now tests pub.changed first, so this check and the code
      // under test read the SAME expression.
      ok(!el("plan-pub-changed") && /not published yet/i.test(el("plan-pub-line").textContent),
         "PL AC-5 (hostile): a host claiming changed:true with nothing published still draws no badge and still reads draft — 'changed' has no meaning without a baseline to have changed from");

      openPlan(lifeView({ publish: PUB_CLEAN }));
      ok(!el("plan-pub-changed") && /version 4/i.test(pubLine()),
         "PL AC-6: a published, unedited plan reads its version with no change badge");
      openPlan(lifeView({ publish: PUB_CHANGED }));
      ok(!!el("plan-pub-changed") && /plan updated/i.test(el("plan-pub-changed").textContent),
         "PL AC-6 (frame 612:1020, positive control): edited-since-publish DOES draw the badge — AC-5 is a rule being applied, not a renderer that never fires");
      ok(el("plan-sum-publish").getAttribute("aria-describedby") === "plan-pub-line" &&
         /edited since version 4/i.test(pubLine()),
         "PL AC-6 a11y: the badge's meaning reaches AT through the Publish button's description — the change glyph is never the only carrier");
      // The badge must come from `changed` ALONE. `revision !== published_revision` is the
      // obvious implementation, it looks right in testing, and it is wrong: an edit that is then
      // undone moves the revision while restoring the content, so this state means "touched, not
      // different" and a badge here would offer the operator nothing to review.
      openPlan(lifeView({ publish: PUB_TOUCHED }));
      ok(!el("plan-pub-changed") && /version 4/i.test(pubLine()),
         "PL AC-6b: revision 9 against published_revision 5 with NO `changed` key draws no badge — the counters say the document was touched, `changed` says whether it differs, and only the second is worth interrupting an operator with");
      ok(planPublishState(lifeView({ publish: PUB_TOUCHED })).changed === false &&
         planPublishState(lifeView({ publish: PUB_TOUCHED })).revision !==
         planPublishState(lifeView({ publish: PUB_TOUCHED })).publishedRevision,
         "PL AC-6b (premise): the fixture really does have differing revisions — otherwise the check above passes for the wrong reason");
      // One fixture exercised ONE of this reader's four guards; the other three were asserted by
      // comment. Each shape below is refused by a different clause, so removing any one of them
      // turns this red rather than leaving three-quarters of the validator untested.
      var malformedPublish = [
        [{ revision: -1, published_revision: 2, version: 4, changed: true }, "a negative revision"],
        [{ revision: 1.5, published_revision: 1, version: 4 }, "a non-integer revision"],
        [{ revision: 5, published_revision: 5, version: "4" }, "a version that is not a number"],
        [{ revision: 5, published_revision: "5", version: 4 }, "a published_revision that is not a number"],
        [{ revision: 5, published_revision: 5, version: 4, changed: "yes" }, "a changed that is not a boolean"]
      ];
      var rendered = malformedPublish.filter(function (pair) {
        openPlan(lifeView({ publish: pair[0] }));
        return !!document.querySelector("#plan-b-insp .plan-pub");
      });
      ok(rendered.length === 0,
         "PL AC-7: every malformed publish shape reads UNREPORTED — a plausible-looking wrong revision printed on a run sheet is worse than none (rendered anyway: " +
         rendered.map(function (p) { return p[1]; }).join(", ") + ")");
      ok(malformedPublish.length >= 5,
         "PL AC-7 (premise): the sweep covers every clause of the reader, not one of them (" + malformedPublish.length + " shapes)");
      openPlan(lifeView({ publish: { revision: -1, version: 4, published_revision: 2, changed: true } }));
      ok(el("plan-sum-publish").disabled,
         "PL AC-7: ...and the lifecycle controls disable with it rather than staying live over a state nothing could read");

      // --- the name rule, mirrored from plan_label_valid ---------------------------------------
      ok(planNameProblem("Sunday 2nd Service") === null,
         "PL AC-8 (control): a normal name is accepted — the rule refuses bad input, it is not a wall");
      ok(planNameProblem("") !== null && planNameProblem("   ") !== null,
         "PL AC-8: empty and whitespace-only names are refused");
      var name120 = new Array(121).join("a");
      ok(planNameProblem(name120) === null && planNameProblem(name120 + "a") !== null,
         "PL AC-8: the bound is 120 characters — 120 passes and 121 does not");
      var astral = "";
      for (var ai = 0; ai < 120; ai++) astral += "\u{1F600}"; // 120 scalar values, 240 UTF-16 code units
      ok(planNameProblem(astral) === null,
         "PL AC-9: 120 astral-plane characters are accepted — the bound counts SCALAR VALUES like the host's chars(), not UTF-16 code units");
      ok(planNameProblem(astral + "\u{1F600}") !== null,
         "PL AC-9 (control): 121 of them are refused, so the bound is real and not simply missing");
      // Built from code points rather than typed literally, so this file stays free of control
      // characters. The set spans the whole Cc class: C0, DEL, and the C1 range the host's
      // char::is_control also refuses.
      var ctrlMissed = [0x00, 0x07, 0x09, 0x0a, 0x0d, 0x1b, 0x7f, 0x85, 0x9f].filter(function (cp) {
        return planNameProblem("Sunday" + String.fromCharCode(cp) + "Service") === null;
      });
      ok(ctrlMissed.length === 0,
         "PL AC-10: every control character in the CLASS is refused, not just NUL — the guard this repo already had to sweep across its class in ee3646f (missed " + ctrlMissed.length + ")");
      ok(planNameProblem("Sundays’ Café — 2nd") === null,
         "PL AC-10 (control): punctuation and accents are NOT control characters — the class test does not over-refuse ordinary names");

      // --- empty state (frame 611:124): four real starts, none of them a no-op ------------------
      openPlan(emptyLife({ publish: PUB_CLEAN, plan_templates: PL_TEMPLATES }));
      ok(!!el("plan-empty-new") && !el("plan-empty-new").disabled,
         "PL AC-11: with the lifecycle reported, 'Create a service' is live");
      var newBefore = plCalls("new_plan").length;
      el("plan-empty-new").click();
      await sleep(20);
      ok(!!el("pm-prompt-input"),
         "PL AC-11: it opens a name dialog rather than creating an unnamed plan");
      el("pm-prompt-input").value = "   ";
      dlgOk().click();
      await sleep(20);
      ok(plCalls("new_plan").length === newBefore && !!el("pm-prompt-input"),
         "PL AC-12: a whitespace-only name sends NOTHING and the dialog stays open with the typed value intact");
      ok(!!el("pm-prompt-error") && !el("pm-prompt-error").hidden && el("pm-prompt-error").getAttribute("role") === "alert",
         "PL AC-12 a11y: the refusal is announced (role=alert), not a silent red line an operator can only see");
      var errCr = _cr(_rgba(getComputedStyle(el("pm-prompt-error")).color),
                      _rgba(getComputedStyle(document.querySelector(".pm-confirm")).backgroundColor));
      ok(errCr >= 4.5,
         "PL AC-12 a11y: ...and it clears AA-NORMAL against the dialog (" + _f(errCr) + ":1) — the refusal is the one thing in this dialog the operator must be able to read");
      el("pm-prompt-input").value = "Sunday" + String.fromCharCode(9) + "Service";
      dlgOk().click();
      await sleep(20);
      ok(plCalls("new_plan").length === newBefore,
         "PL AC-12: a control character in the name sends nothing either");
      el("pm-prompt-input").value = "  Sunday 2nd Service  ";
      dlgOk().click();
      await sleep(40);
      var newCalls = plCalls("new_plan");
      ok(newCalls.length === newBefore + 1 && (newCalls.length ? newCalls[newCalls.length - 1].args || {} : {}).name === "Sunday 2nd Service",
         "PL AC-12 (positive control): a VALID name sends new_plan with the TRIMMED name — the guard refuses bad input, it is not a dead button");
      ok(!el("pm-prompt-input"), "PL AC-12: ...and the dialog closes once the host accepts");
      var okNote = document.querySelector("#plan-notice .plan-notice-status");
      ok(!!okNote && okNote.getAttribute("role") === "status",
         "PL AC-13: the outcome is reported in the PLAN surface's own live region (the presentation surface's toast is not visible from here)");

      // --- templates come from the host, never from a client-side list --------------------------
      openPlan(emptyLife({ publish: PUB_CLEAN, plan_templates: PL_TEMPLATES }));
      el("plan-empty-template").click();
      await sleep(20);
      var tplRows = document.querySelectorAll(".plan-tpl-row");
      ok(tplRows.length === 2 && /Sunday Morning/.test(tplRows[0].textContent) && /5 items/.test(tplRows[0].textContent),
         "PL AC-14: the picker lists the HOST's templates with the host's own item COUNT — the client carries no copy of the list to drift from");
      ok(!document.querySelector(".pm-confirm select"),
         "PL AC-14 (WKWebView): the picker uses radios, not a flex-parented select — that collapses to zero width off-Blink and this Blink gate could never see it");
      ok(el("pm-prompt-input").value === "Sunday Morning",
         "PL AC-15: the name defaults to the chosen template's name rather than an empty field");
      document.getElementById("plan-tpl-1").click();
      ok(el("pm-prompt-input").value === "Midweek Gathering",
         "PL AC-15: choosing another template follows its name...");
      el("pm-prompt-input").value = "My Own Name";
      el("pm-prompt-input").dispatchEvent(new Event("input", { bubbles: true }));
      document.getElementById("plan-tpl-0").click();
      ok(el("pm-prompt-input").value === "My Own Name",
         "PL AC-15: ...but never overwrites a name the operator has typed");
      el("pm-prompt-input").value = "Sunday 2nd Service";
      var tplBefore = plCalls("template_plan").length;
      dlgOk().click();
      await sleep(40);
      var tplCalls = plCalls("template_plan");
      // Null-safe: dereferencing `.args` on a send that never happened turns a real defect into a
      // THROWN exception that aborts the driver — 280 checks lost, and only the floor reporting
      // it. Fourth instance of that class in this batch, so it is worth naming: a control that
      // dies tells you something is wrong but never what.
      var tplLast = tplCalls.length ? tplCalls[tplCalls.length - 1].args || {} : {};
      ok(tplCalls.length === tplBefore + 1 &&
         tplLast.template === "sunday-morning" &&
         tplLast.name === "Sunday 2nd Service",
         "PL AC-14: it sends template_plan{template,name} carrying the id the HOST reported, so no id is invented here");

      openPlan(emptyLife({ publish: PUB_CLEAN }));
      ok(el("plan-empty-template").disabled &&
         el("plan-empty-template").getAttribute("aria-describedby") === "plan-empty-no-templates" &&
         !!el("plan-empty-no-templates"),
         "PL AC-16: a host offering no templates disables the action WITH the reason — never an empty picker");

      // --- the two affordances that are disabled BY DESIGN, not by dependency -------------------
      ok(el("plan-empty-duplicate").disabled && !!el("plan-empty-no-library") &&
         /saved-plan library/i.test(el("plan-empty-no-library").textContent),
         "PL AC-17: 'Duplicate previous' states its real reason — duplicate_plan copies the OPEN plan, and this build keeps exactly one, so there is no past service to choose from");
      ok(el("plan-empty-bundle").disabled && !!el("plan-empty-no-bundle") &&
         /media/i.test(el("plan-empty-no-bundle").textContent),
         "PL AC-17: FR-139's plan BUNDLE is a named, disabled affordance — the run-sheet import must not stand in for it and silently drop every operator's media");

      // --- import: a run-sheet item list, typed per line ----------------------------------------
      openPlan(emptyLife({ publish: PUB_CLEAN }));
      el("plan-empty-import").click();
      await sleep(20);
      ok(!!el("plan-import-text"), "PL AC-18: Import opens a run-sheet paste");
      el("pm-prompt-input").value = "Imported";
      el("plan-import-text").value = "Sermon";
      var impBefore = plCalls("import_plan").length;
      dlgOk().click();
      await sleep(20);
      ok(plCalls("import_plan").length === impBefore && /line 1/i.test(el("pm-prompt-error").textContent),
         "PL AC-18: a line that does not name its type is refused BY LINE NUMBER and nothing is sent — never imported as a guessed type that misbehaves on service day");
      el("plan-import-text").value = "Song: Opening\nScripture: Romans 8:28\n\nPresentation: Sermon Deck";
      dlgOk().click();
      await sleep(40);
      var impCalls = plCalls("import_plan");
      var impSent = impCalls.length ? impCalls[impCalls.length - 1].args || {} : { items: [] };
      ok(impCalls.length === impBefore + 1 && impSent.name === "Imported" && (impSent.items || []).length === 3,
         "PL AC-18 (positive control): a well-formed paste sends import_plan with one item per non-blank line");
      ok((impSent.items || []).length === 3 && impSent.items[0].kind === "song" && impSent.items[2].kind === "slide_group",
         "PL AC-18: the on-screen label 'Presentation' maps to the WIRE tag slide_group, and blank lines are spacing rather than empty items");
      ok((impSent.items || []).length === 3 && impSent.items.every(function (x) { return !("link" in x) && !("content" in x); }),
         "PL AC-18: import carries kind + title only — content links are set afterwards with SetItemContent, so none is invented on this path");
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 3,
         "PL AC-18: ...and the run sheet re-renders from the view the HOST returned, not from what the client assumed it sent");

      var badTitle = planParseRunSheet("Song: " + name120 + "a");
      ok(!badTitle.items.length && badTitle.problems.length === 1,
         "PL AC-19: an item TITLE is validated by the SAME rule as the plan name — one definition, not a looser copy written for this path");
      var many = [];
      for (var bi = 0; bi < 501; bi++) many.push("Song: Item " + bi);
      ok(planParseRunSheet(many.join("\n")).problems.some(function (m) { return /500/.test(m); }),
         "PL AC-19: a paste over MAX_PLAN_ITEMS is refused with the cap named");
      var atCap = planParseRunSheet(many.slice(0, 500).join("\n"));
      ok(atCap.items.length === 500 && !atCap.problems.length,
         "PL AC-19 (control): exactly 500 is accepted — the cap is the host's 500, not one either side of it");
      // Quinn (Low, MU-C) — the other end of the same cap. Deleting the empty-paste guard left
      // the suite completely green, and without it an empty paste sends import_plan{items:[]},
      // which replaces the operator's run sheet with nothing at all.
      openPlan(emptyLife({ publish: PUB_CLEAN }));
      el("plan-empty-import").click();
      await sleep(20);
      el("pm-prompt-input").value = "Imported";
      el("plan-import-text").value = "   \n\n  ";
      var emptyBefore = plCalls("import_plan").length;
      dlgOk().click();
      await sleep(20);
      ok(plCalls("import_plan").length === emptyBefore && !!el("plan-import-text"),
         "PL AC-19 (Quinn MU-C): a paste with no items sends NOTHING and keeps the dialog open — import REPLACES the run sheet, so an empty one would replace it with nothing");
      // Null-safe, for the reason the reviewers raised three times on this suite: without the
      // guard, removing the rule under test closes the dialog and this line THROWS, aborting the
      // driver instead of failing the check that names the rule.
      var emptyErr = document.getElementById("pm-prompt-error");
      ok(/at least one/i.test((emptyErr && emptyErr.textContent) || ""),
         "PL AC-19 (Quinn MU-C): ...and says why, rather than refusing in silence");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);

      // --- publish (FR-006) ---------------------------------------------------------------------
      openPlan(lifeView({ publish: PUB_CHANGED }));
      var pubBefore = plCalls("publish_plan").length;
      el("plan-sum-publish").click();
      await sleep(40);
      ok(plCalls("publish_plan").length === pubBefore + 1 && !plCalls("publish_plan")[pubBefore].args,
         "PL AC-20 (FR-006): Publish sends publish_plan and carries no arguments");
      var pubNote = document.querySelector("#plan-notice .plan-notice-status");
      ok(!!pubNote && !/\b(team|network|internet|upload|uploaded|sent to)\b/i.test(pubNote.textContent),
         "PL AC-20 (copy): the confirmation states the LOCAL builder-to-console hand-off and claims no network transfer — SERVICE-PLAN-2.0-HANDOFF.md:105 and FR-006 both describe publish as local, and the conflict with the button's shipped label is the owner's to settle, not this file's to assert");

      window.__planRejectOnce = true;
      openPlan(lifeView({ publish: PUB_CHANGED }));
      el("plan-sum-publish").click();
      await sleep(40);
      var failNote = document.querySelector("#plan-notice .plan-notice-alert");
      ok(!!failNote && failNote.getAttribute("role") === "alert" && /simulated host rejection/.test(failNote.textContent),
         "PL AC-21: a rejected command reports the HOST'S OWN message, so a name the host refused is fixable rather than an unexplained dead button");
      ok(!document.querySelector("#plan-notice .plan-notice-status"),
         "PL AC-21 (control): ...and no stale success message is left standing beside the failure");

      openPlan(lifeView({ publish: PUB_CHANGED }));
      var raceBefore = plCalls("publish_plan").length;
      var pubBtn = el("plan-sum-publish");
      pubBtn.click();
      pubBtn.click();
      await sleep(60);
      ok(plCalls("publish_plan").length === raceBefore + 1,
         "PL AC-22: double-activating Publish sends exactly one command — these five REPLACE the plan, and two in flight would leave the operator unable to tell which reply they are looking at");

      // --- duplicate_plan lives beside the OPEN plan (FR-005) -----------------------------------
      openPlan(lifeView({ publish: PUB_CLEAN }));
      ok(!!el("plan-sum-duplicate") && !el("plan-sum-duplicate").disabled,
         "PL AC-23 (FR-005): 'Duplicate this service' sits beside the open plan's summary, because duplicate_plan copies the plan that is OPEN — which is exactly why it is wrong for the empty state");
      el("plan-sum-duplicate").click();
      await sleep(20);
      ok(el("pm-prompt-input").value === "Sunday AM (copy)",
         "PL AC-23: it proposes a name derived from the open plan rather than an empty field");
      var dupBefore = plCalls("duplicate_plan").length;
      // Typing the CURRENT name back is refused here rather than sent: the host ACCEPTS it and
      // does nothing (an Ack, not an error), and this client cannot report that honestly —
      // "Service duplicated" would be false and silence would read as a broken button.
      el("pm-prompt-input").value = "Sunday AM";
      dlgOk().click();
      await sleep(20);
      ok(plCalls("duplicate_plan").length === dupBefore && /current name/i.test(el("pm-prompt-error").textContent),
         "PL AC-23b: duplicating under the plan's CURRENT name is refused with an explanation — the host would Ack and change nothing, which is a success message over a plan that did not move");
      el("pm-prompt-input").value = "Sunday AM (copy)";
      dlgOk().click();
      await sleep(40);
      var dupCalls = plCalls("duplicate_plan");
      ok(dupCalls.length === dupBefore + 1 && (dupCalls.length ? dupCalls[dupCalls.length - 1].args || {} : {}).name === "Sunday AM (copy)",
         "PL AC-23 (positive control): ...and a genuinely different name does send duplicate_plan{name}");

      // --- the read-only inspector (frame 612:342) ----------------------------------------------
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false } }));
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="301"]').click();
      ok(!el("plan-insp-title") && !!el("plan-insp-title-ro"),
         "PL AC-24: the view-only inspector shows the title as static text — a field that looks like a field and refuses typing is the same complaint in a different costume");
      ok(!document.querySelector("#plan-b-insp .pm-btn-danger"),
         "PL AC-24: ...and 'Remove item' is absent, not disabled");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="302"]').click();
      ok(!document.querySelector("#plan-b-insp .plan-insp-actions .pm-btn-primary"),
         "PL AC-25: view-only removes the Link/Change action from a scripture item's inspector");
      openPlan(lifeView());
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="301"]').click();
      ok(!!el("plan-insp-title") && !!document.querySelector("#plan-b-insp .pm-btn-danger"),
         "PL AC-24 (control): with nothing reported the inspector is fully editable — the read-only treatment is a state, not a latch that sticks on");

      // --- Open in Live stays navigation, but stops looking like a write ------------------------
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false } }));
      ok(/Follow in Live/.test(el("plan-open-live").textContent) && el("plan-open-live").className === "pm-btn-ghost",
         "PL AC-26 (design-QA section 9): under view-only the header action reads as the passive thing it is, rather than an enabled write-looking primary on a plan this operator cannot change");
      ok(!!el("plan-sum-live") && /Follow in Live/.test(el("plan-sum-live").textContent),
         "PL AC-26: the panel's twin follows the same rule");
      openPlan(lifeView());
      ok(/Open in Live/.test(el("plan-open-live").textContent) && el("plan-open-live").className === "pm-btn-primary",
         "PL AC-26 (control): with no restriction reported it is the primary 'Open in Live' again");
      var edTracks = getComputedStyle(document.querySelector("#surface-plan .plan-builder-grid")).gridTemplateColumns.trim().split(/\s+/);
      ok(edTracks.length === 3,
         "PL AC-26 (control): ...and the three-track layout comes back with the ADD ITEM column — the dropped track is a state, not a latch (tracks: " + edTracks.join(" | ") + ")");

      // --- an empty plan under view-only offers nothing to press --------------------------------
      openPlan(emptyLife({ viewer: { role: "viewer", can_edit: false }, publish: PUB_CLEAN, plan_templates: PL_TEMPLATES }));
      ok(!!el("plan-empty-viewonly") && !el("plan-empty-new") && !el("plan-empty-add") && !el("plan-empty-duplicate"),
         "PL AC-27: an empty plan under view-only offers no creation controls at all — a permission is not a 'coming soon', so it gets no disabled buttons to explain away");
      ok(/No service plan yet/i.test(document.querySelector("#plan-b-list .plan-empty-h").textContent) &&
         !/Add songs/i.test(el("plan-b-list").textContent),
         "PL AC-27: ...and the COPY follows the permission too — no \"Build your service plan · Add songs…\" instruction to someone whose role forbids all of it");

      // --- a host without the lifecycle gets honest controls, not failing ones -------------------
      openPlan(emptyLife({ plan_templates: PL_TEMPLATES }));
      ok(el("plan-empty-new").disabled && el("plan-empty-import").disabled && el("plan-empty-template").disabled &&
         el("plan-empty-new").getAttribute("aria-describedby") === "plan-empty-later" && !!el("plan-empty-later"),
         "PL AC-29: a host that does not report the lifecycle gets DISABLED actions pointing at the reason — never live-looking buttons that fail on click against an older or remote host");
      var quietFrom = window.__calls.length;
      el("plan-empty-new").click();
      el("plan-empty-import").click();
      el("plan-empty-template").click();
      await sleep(20);
      ok(window.__calls.slice(quietFrom).filter(function (c) {
           return ["new_plan", "import_plan", "template_plan"].indexOf(c.cmd) >= 0;
         }).length === 0,
         "PL AC-29 (control): pressing them sends nothing — genuinely disabled, not merely styled to look it");

      // --- the copy that says WHY a control is unavailable must be readable ---------------------
      // These lines are not decoration: they are the only thing that turns a dead-looking button
      // into an explained one, so they are essential copy at small size and belong on
      // --sc-text-secondary, not the AA-large-only --sc-text-muted. Measured through the live CSS
      // engine so a token rename cannot fake it.
      openPlan(emptyLife({ plan_templates: PL_TEMPLATES }));
      var reasonEl = el("plan-empty-later");
      var reasonBg = (function (n) {
        // Walk to the first ancestor that actually paints, so the ratio is against the ground the
        // text really sits on rather than a transparent parent.
        for (var e = n; e && e !== document.documentElement; e = e.parentElement) {
          var bg = getComputedStyle(e).backgroundColor;
          if (_rgba(bg)[3] > 0) return bg;
        }
        return getComputedStyle(document.body).backgroundColor;
      })(reasonEl);
      var reasonCr = _cr(_rgba(getComputedStyle(reasonEl).color), _rgba(reasonBg));
      ok(reasonCr >= 4.5,
         "PL AC-30: the stated reason under a disabled action clears AA-NORMAL (" + _f(reasonCr) + ":1) — a reason an operator cannot read leaves the control indistinguishable from a dead button");
      openPlan(emptyLife({ viewer: { role: "viewer", can_edit: false } }));
      var voEl = el("plan-empty-viewonly");
      var voCr = _cr(_rgba(getComputedStyle(voEl).color), _rgba(reasonBg));
      ok(voCr >= 4.5,
         "PL AC-30: so does the view-only explanation (" + _f(voCr) + ":1)");

      // --- which one of the five is not like the others? ----------------------------------------
      // FOUR of the five REPLACE the run sheet; publish_plan moves a marker and leaves the plan,
      // its item ids and the operator's selection intact. A shared helper that treats all five
      // alike is exactly where that difference hides — a twelve-mutation battery would pass,
      // because the test and the code would agree with each other.
      // Publish lives on the SUMMARY, so the selection is set without opening the item inspector
      // over it — then the command runs and the selection must survive it.
      openPlan(lifeView({ publish: PUB_CHANGED }));
      ok(!!el("plan-sum-publish"), "PL AC-31 (setup): the summary is showing, with Publish on it");
      planSelectedId = 302;
      el("plan-sum-publish").click();
      await sleep(40);
      ok(planSelectedId === 302,
         "PL AC-31: publish_plan does NOT clear the operator's selection — it moves a marker, it does not replace the plan, so throwing them back to the Plan Summary would be a reset they could not name");
      // ...and the control: a command that DOES replace the plan clears it.
      openPlan(lifeView({ publish: PUB_CLEAN }));
      planSelectedId = 302;
      el("plan-sum-duplicate").click();
      await sleep(20);
      el("pm-prompt-input").value = "A Different Name";
      dlgOk().click();
      await sleep(40);
      ok(planSelectedId === null,
         "PL AC-31 (control): duplicate_plan DOES clear it — the four that mint new item ids must not leave a stale one pointing at an item that no longer exists");

      // --- duplicating mid-service says what is on air ------------------------------------------
      var liveView = lifeView({ publish: PUB_CLEAN });
      liveView.items[0].is_live = true;
      openPlan(liveView);
      el("plan-sum-duplicate").click();
      await sleep(20);
      var warn = el("pm-prompt-warn");
      ok(!!warn && /is LIVE/.test(warn.textContent) && warn.textContent.indexOf(PL_ITEMS[0].title) >= 0,
         "PL AC-32: duplicating while an item is LIVE NAMES it — the copy replaces the run sheet being edited, and an operator mid-service deserves to be told which of those two things is true (got: " + (warn ? warn.textContent : "no warning") + ")");
      ok(/audience output is unaffected/i.test(warn.textContent),
         "PL AC-32: ...and states that the audience is unaffected, rather than leaving them to fear it");
      ok(document.querySelector(".pm-confirm").getAttribute("aria-describedby").indexOf("pm-prompt-warn") >= 0,
         "PL AC-32 a11y: the consequence is in the dialog's accessible description — a warning a screen reader never speaks did not happen (WCAG 4.1.2)");
      ok(!dlgOk().disabled,
         "PL AC-32: it STATES the consequence, it does not block — duplicating a running service is a legitimate thing to want");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);
      // A live slide whose plan item is already gone is the case a naive items[live_index] misses.
      var freeView = lifeView({ publish: PUB_CLEAN });
      freeView.live_free_text = "Removed but still on air";
      openPlan(freeView);
      el("plan-sum-duplicate").click();
      await sleep(20);
      ok(!!el("pm-prompt-warn") && /Removed but still on air/.test(el("pm-prompt-warn").textContent),
         "PL AC-32: a live FREE slide — one whose plan item was already removed — is named too, not missed by an items lookup");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);
      openPlan(lifeView({ publish: PUB_CLEAN }));
      el("plan-sum-duplicate").click();
      await sleep(20);
      ok(!el("pm-prompt-warn"),
         "PL AC-32 (control): with NOTHING on air there is no warning — the line is a state, not decoration on every duplicate");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);

      // --- the template list is BOUNDED before it is rendered -----------------------------------
      // The operator shell reads this from a host across the LAN link, and ControlClient sets no
      // max_message_size (client.rs:70) while the server caps its own inbound at 64 KiB
      // (server.rs:46) — so a reply may be far larger than any picker should render.
      var manyTpl = [];
      for (var ti = 0; ti < 25; ti++) manyTpl.push({ id: "t" + ti, name: "Template " + ti, items: 3 });
      ok(planTemplateList({ plan_templates: manyTpl }) === null,
         "PL AC-33: a template list past the picker's entity cap reads as NO list — bounded by entry COUNT, not by a byte proxy that still admits unboundedly many tiny rows");
      ok(planTemplateList({ plan_templates: manyTpl.slice(0, 24) }) !== null,
         "PL AC-33 (control): exactly at the cap it still loads — the bound refuses excess, it is not a dead mechanism");
      var longName = new Array(200).join("x");
      ok(planTemplateList({ plan_templates: [{ id: "t", name: longName, items: 3 }] }) === null,
         "PL AC-33: an over-long template NAME is refused — the string is rendered, so its length is bounded too");
      ok(planTemplateList({ plan_templates: [{ id: longName, name: "T", items: 3 }] }) === null,
         "PL AC-33: ...and so is an over-long id");
      openPlan(emptyLife({ publish: PUB_CLEAN, plan_templates: manyTpl }));
      ok(el("plan-empty-template").disabled && !document.querySelector(".plan-tpl-row"),
         "PL AC-33: ...and the picker renders no row for a list it refused, rather than building one DOM node per entry");
      ok(/no usable starter templates/i.test(el("plan-empty-no-templates").textContent),
         "PL AC-33: the stated reason is true for a REFUSED list as well as an empty one — 'this host offers none' would have been a claim about the host that this client cannot make");

      // --- a long session must not silently disable the whole panel -----------------------------
      var busy = planPublishState({ publish: { revision: 250000, published_revision: 240000, version: 900 } });
      ok(busy !== null && busy.version === 900,
         "PL AC-34: a revision past 100,000 is still REPORTED — these are ordinals rendered as labels, never summed, and refusing them would degrade the whole lifecycle panel to 'unreported' under a reason that was not true");


      // --- review round 1: the controls the reviewers proved nothing guarded --------------------
      // Each of these went GREEN under a mutation of the guard it now names. That is the whole
      // reason they exist: "right and unguarded" is the state this repo's CLAUDE.md warns about,
      // and three of the four below were live, correct behaviour that no check would have missed.

      // Cody M1 — the buttons being gone is not the same as the keyboard path being gated.
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false } }));
      var voRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="301"]');
      var mvBefore = plCalls("move_item").length;
      voRow.focus();
      voRow.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", altKey: true, bubbles: true }));
      await sleep(30);
      ok(plCalls("move_item").length === mvBefore,
         "PL AC-35 (Cody M1): under view-only Alt+ArrowDown sends no move_item — a restriction that only holds for the mouse is not a restriction, and PL AC-2 proving the buttons are gone says nothing about the key handler, which is attached regardless of permission");
      // The positive control matters more than usual here: without it this passes just as well if
      // the key handler stopped firing for a reason that has nothing to do with the permission.
      openPlan(lifeView());
      var edRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="301"]');
      var mvBefore2 = plCalls("move_item").length;
      edRow.focus();
      edRow.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", altKey: true, bubbles: true }));
      await sleep(30);
      ok(plCalls("move_item").length === mvBefore2 + 1,
         "PL AC-35 (control): the SAME gesture with no restriction reported DOES reorder — so the check above is measuring the permission, not a dead key handler");

      // Cody M2 — the Tab trap must walk the dialog's LIVE focusables. Under the old hard-coded
      // [input, cancel, ok] triple, indexOf returns -1 for the textarea and for every template
      // radio, so a keyboard user could never reach either and the import dialog was unusable
      // without a mouse.
      openPlan(emptyLife({ publish: PUB_CLEAN, plan_templates: PL_TEMPLATES }));
      el("plan-empty-import").click();
      await sleep(20);
      el("pm-prompt-input").focus();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true }));
      ok(document.activeElement === el("plan-import-text"),
         "PL AC-36 (Cody M2): the dialog's Tab trap reaches the run-sheet textarea — content opts.body adds must be reachable, or the import dialog cannot be operated without a mouse");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);
      el("plan-empty-template").click();
      await sleep(20);
      el("pm-prompt-input").focus();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true }));
      ok(document.activeElement === document.getElementById("plan-tpl-1"),
         "PL AC-36 (Cody M2): ...and the template radios, which the same old trap could never reach either");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);

      // Cody L3 — can_edit must be a real boolean. A serde host cannot send anything else, but
      // the entire reason this field exists is that the console talks to hosts it did not build,
      // and "false" is truthy.
      ok(planViewer({ viewer: { role: "operator", can_edit: "false" } }).canEdit === null,
         "PL AC-37 (Cody L3): a non-boolean can_edit reads as UNREPORTED — coercing it would make the string \"false\" mean editable and the number 0 mean view-only");
      openPlan(lifeView({ viewer: { role: "operator", can_edit: "false" } }));
      ok(!el("plan-viewonly") && paletteShown(),
         "PL AC-37: ...and the surface treats it as unreported rather than as either verdict");

      // Cody L2 — plan_templates crosses the same trust boundary as publish, which has PL AC-7
      // for exactly this. The asymmetry was the finding.
      ok(planTemplateList({ plan_templates: [{ id: "", name: "", items: -3 }] }) === null,
         "PL AC-38 (Cody L2): a malformed template entry is dropped — no picker row with a blank name and \"-3 items\"");
      ok(planTemplateList({ plan_templates: [{ id: "ok", name: "Fine", items: 3 }, { id: "", name: "", items: -3 }] }) !== null &&
         planTemplateList({ plan_templates: [{ id: "ok", name: "Fine", items: 3 }, { id: "", name: "", items: -3 }] }).length === 1,
         "PL AC-38 (control): a good entry beside a bad one still loads, and only the bad one is dropped — the filter refuses entries, it does not refuse lists");

      // Cody L4 — a control that looks live and silently does nothing is the exact thing this
      // panel's disabled-with-a-reason treatment exists to avoid, and in the in-flight window
      // five of them did it.
      openPlan(lifeView({ publish: PUB_CHANGED }));
      planNotice(""); // start from a clean slot so the message below cannot be a leftover
      planLifecycleBusy = true;
      el("plan-sum-publish").click();
      await sleep(20);
      ok(/still finishing/i.test(el("plan-notice").textContent),
         "PL AC-39 (Cody L4): a command dropped by the in-flight guard SAYS so — PL AC-22 pins that only one is sent, which is right; the silence was the defect");
      planLifecycleBusy = false;

      // Cody L5 — the outcome message must not outlive the run sheet it describes.
      openPlan(lifeView({ publish: PUB_CHANGED }));
      el("plan-sum-publish").click();
      await sleep(40);
      ok(!!document.querySelector("#plan-notice .plan-notice-status"),
         "PL AC-40 (setup): publishing leaves its confirmation in the live region");
      await planMutate(() => invoke("add_item", { kind: "song", title: "Later addition" }));
      await sleep(20);
      ok(el("plan-notice").textContent === "",
         "PL AC-40 (Cody L5): a later plan EDIT clears it — \"Plan published\" is true of the run sheet that was published, not of the one now on screen");
      // ...and the SAME control on the NAVIGATION path needs a premise of its own. The check
      // immediately above has just asserted the slot is EMPTY, so without putting an outcome back
      // on screen first, "a fresh visit does not inherit it" passes whether planActivate cleared
      // it or not — nothing in the sequence distinguishes "planActivate cleared it" from "it was
      // already clear". Deleting planNotice("") from planActivate left the whole gate green
      // (Cody L5, re-review at e71be48). The clearing IS load-bearing: #plan-notice is a static
      // element in index.html, not rebuilt by the render, so a stale outcome really does survive
      // a navigation without it.
      planNotice("status", "A stale outcome from the last visit");
      ok(/stale outcome/.test(el("plan-notice").textContent),
         "PL AC-40 (premise): an outcome really is on screen immediately before the navigation — without it the fresh-visit check below is vacuous and planActivate's clearing goes unexercised");
      planActivate();
      await sleep(80);
      ok(el("plan-notice").textContent === "",
         "PL AC-40 (Cody L5): ...and a fresh visit to the surface does not inherit the last visit's outcome");

      // Cody S2 — the value the client VALIDATED and the value it SENDS must be the same string,
      // or the validation is describing something other than what the host will see.
      var trimParsed = planParseRunSheet("Song:   Opening   ");
      ok(trimParsed.items.length === 1 && trimParsed.items[0].title === "Opening",
         "PL AC-41 (Cody S2): an imported title is SENT trimmed, not merely validated trimmed");

      // Cody S1 (the half that holds) — an explicit changed:null must not silence the panel,
      // because published_revision:null is deliberately tolerated four lines above it.
      var nullChanged = planPublishState({ publish: { revision: 7, published_revision: 5, version: 4, changed: null } });
      ok(nullChanged !== null && nullChanged.changed === false,
         "PL AC-42 (Cody S1): an explicit changed:null reads as false rather than silencing the whole publish state — the reader treats its two nulls the same way");

      // Vera F2 — the exact pre-check. A scalar value is at most two UTF-16 code units, so a
      // string past 2x the bound must exceed it; no string that would have been accepted can be
      // refused by the guard. Both halves are asserted, because a guard that over-refuses would
      // be a regression the fast path cannot show.
      var huge = new Array(300001).join("x"); // 300,000 code units on one line
      // HONEST SCOPE. This pins the REFUSAL, not the cheap path to it: with the code-unit
      // pre-check deleted the string is still refused, just after materialising a 300,000-element
      // array. The pre-check's value is a MEASUREMENT (Vera: 3,267ms main-thread block and ~270MB
      // transient heap on Blink for a 50MB single-line paste, 357ms on WebKit), and this harness
      // runs under --virtual-time-budget, which virtualises clocks and makes a timing assertion
      // here meaningless. So the guard below says what it can prove, and the comment says who
      // proved the rest — rather than a check whose name claims more than it measures.
      ok(planNameProblem(huge) !== null,
         "PL AC-43 (Vera F2): a very long single-line paste is refused — the code-unit pre-check that makes the refusal CHEAP is measured, not asserted here (see the comment)");
      ok(planNameProblem(astral) === null && planNameProblem(name120) === null,
         "PL AC-43 (control): the code-unit pre-check refuses nothing the scalar-value bound accepts — 120 astral characters are 240 code units and still pass");

      // Vera F1 — the parse cost is a function of the CAP, not of the clipboard.
      var overCap = [];
      for (var oc = 0; oc < 5000; oc++) overCap.push("Song: Item " + oc);
      var capped = planParseRunSheet(overCap.join("\n"));
      ok(capped.items.length <= PLAN_MAX_ITEMS + 1,
         "PL AC-44 (Vera F1): parsing stops at the cap rather than building the whole intermediate — the old error message's exact count was itself proof that it had not (got " + capped.items.length + ")");
      ok(capped.problems.length > 0 && /at most 500/.test(capped.problems[capped.problems.length - 1]),
         "PL AC-44: ...and the over-cap paste is still refused, with the cap named");
      var manyBad = [];
      for (var mb = 0; mb < 3000; mb++) manyBad.push("no type here " + mb);
      ok(planParseRunSheet(manyBad.join("\n")).problems.length <= 20,
         "PL AC-44: the problem list is bounded too — only the first is ever shown, so holding thousands of them is unbounded growth for no reader");

      // Cody L6 — these two constants are hand-transcribed copies of host constants. The repo
      // already pins a cross-language copy (test_protocol.rs pins the Dart fixtures byte-for-byte
      // against the Rust shapes) precisely so a copy cannot drift unnoticed. Pinned in Python,
      // beside the harness, because these are JS constants and no Rust test reads dist/.
      ok(window.__RUST_MAX_PLAN_ITEMS === PLAN_MAX_ITEMS,
         "PL AC-45 (Cody L6): PLAN_MAX_ITEMS still equals selahcue-core's MAX_PLAN_ITEMS — a client refusing at a different cap than the host tells the operator a rule that is not the system's (js=" +
         PLAN_MAX_ITEMS + " rust=" + window.__RUST_MAX_PLAN_ITEMS + ")");
      ok(window.__RUST_MAX_PLAN_LABEL_LEN === PLAN_NAME_MAX,
         "PL AC-45 (Cody L6): PLAN_NAME_MAX still equals selahcue-core's MAX_PLAN_LABEL_LEN — the constant was renamed out from under an earlier, null-tolerant version of this pin, so it is now a hard failure on both sides (js=" +
         PLAN_NAME_MAX + " rust=" + window.__RUST_MAX_PLAN_LABEL_LEN + ")");

      // Every new text site that carries meaning clears AA-NORMAL, measured through the live CSS
      // engine rather than by reading a token name. Swept in one loop so a new site added without
      // a check is a one-line addition here rather than a forgotten one.
      openPlan(lifeView({ publish: PUB_CHANGED }));
      var inkSites = [
        [".plan-pub-line", "the publication state line"],
        [".plan-pub-badge", "the change badge"],
        [".plan-sum-hintline", "the hint under an enabled Publish"],
        [".plan-sum-later", "the reason under a disabled action"]
      ];
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false }, publish: PUB_CHANGED }));
      inkSites.push([".plan-viewonly", "the View only badge"]);
      inkSites.push([".plan-viewonly-why", "the View only explanation"]);
      var inkFails = [];
      var groundOf = function (n) {
        for (var e = n; e && e !== document.documentElement; e = e.parentElement) {
          var bg = getComputedStyle(e).backgroundColor;
          if (_rgba(bg)[3] > 0) return bg;
        }
        return getComputedStyle(document.body).backgroundColor;
      };
      var measureInk = function () {
        inkSites.forEach(function (pair) {
          var n = document.querySelector(pair[0]);
          if (!n) return;
          var r = _cr(_rgba(getComputedStyle(n).color), _rgba(groundOf(n)));
          if (r < 4.5) inkFails.push(pair[1] + " " + _f(r) + ":1");
        });
      };
      measureInk();
      openPlan(lifeView({ publish: PUB_CHANGED }));
      measureInk();
      openPlan(emptyLife({}));
      inkSites.push([".plan-empty-note", "the view-only empty note"]);
      measureInk();
      openPlan(emptyLife({ viewer: { role: "viewer", can_edit: false } }));
      measureInk();
      ok(inkFails.length === 0,
         "PL AC-46: every new text site that carries meaning clears AA-NORMAL against its own ground (" +
         (inkFails.join("; ") || "all clear") + ")");
      ok(inkSites.length >= 7,
         "PL AC-46 (premise): the sweep actually covers the new sites — a loop over an empty list would report 'all clear' forever (" + inkSites.length + " sites)");


      // --- QA review round 1: the second keyboard path, the Cf mirror, and the badge's refresh --

      // Quinn Q1 — the Alt+arrow gate was the FIRST keyboard edit path missing its guard. This is
      // the second, in the same surface, found the same way. Enumerating the two by hand is what
      // let the first one hide, so this asserts the whole class: under view-only, NO plan-editing
      // command reaches the host from the keyboard.
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false } }));
      var PLAN_EDIT_CMDS = ["move_item", "rename_item", "remove_item", "add_item", "set_item_content", "plan_undo", "plan_redo"];
      var editsFrom = window.__calls.length;
      var voRow2 = document.querySelector('#plan-b-list .plan-b-row[data-item-id="301"]');
      voRow2.focus();
      voRow2.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", altKey: true, bubbles: true }));
      voRow2.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", altKey: true, bubbles: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, bubbles: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, shiftKey: true, bubbles: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "z", ctrlKey: true, bubbles: true }));
      await sleep(40);
      var leaked = window.__calls.slice(editsFrom).filter(function (c) { return PLAN_EDIT_CMDS.indexOf(c.cmd) >= 0; });
      ok(leaked.length === 0,
         "PL AC-47 (Quinn Q1): under view-only NO plan-editing command reaches the host from the KEYBOARD — undo/redo were live behind hidden buttons, which is the same defect as the Alt+arrow path in a second place (leaked: " +
         (leaked.map(function (c) { return c.cmd; }).join(",") || "none") + ")");
      // The positive control, again: without it this passes just as well if the key handlers
      // stopped firing for a reason that has nothing to do with the permission.
      openPlan(lifeView());
      var editsFrom2 = window.__calls.length;
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, bubbles: true }));
      await sleep(40);
      ok(window.__calls.slice(editsFrom2).some(function (c) { return c.cmd === "plan_undo"; }),
         "PL AC-47 (control): the SAME keystroke with no restriction reported DOES undo — the check above measures the permission, not a dead key handler");

      // Quinn — a refused plan edit used to reach console.error and nothing else, so a host that
      // rejected a rename or an undo looked exactly like a control that did nothing.
      openPlan(lifeView());
      planNotice("");
      window.__planRejectOnce = true;
      await planMutate(function () { return invoke("publish_plan"); }); // the one stub path that can reject
      await sleep(20);
      ok(!!document.querySelector("#plan-notice .plan-notice-alert"),
         "PL AC-48 (Quinn): a plan edit the host REFUSES says so — silence made a refusal indistinguishable from a dead control");

      // Quinn Q7 — the client must agree with the host's invisible-character rule, and this
      // check is written against the host's OWN test table (selahcue-core/tests/test_plan.rs,
      // plan_label_valid) rather than against a set retyped from memory.
      //
      // BOTH DIRECTIONS ARE TESTED, because both are real defects and only one of them looks
      // like one. Client LOOSER: a name this client accepts and the host refuses comes back as a
      // raw bad_request, and on import it loses the line number the per-line validator exists to
      // give. Client STRICTER: the operator is refused a name the system actually allows, with a
      // message they cannot act on — and since the admitted set is the orthographic joiners, the
      // names it locks out are Sinhala, Persian, Urdu, Devanagari and Malayalam ones, plus every
      // family emoji. That is the direction this suite previously got wrong: it asserted U+200D
      // was refused, which was true of the host at 7a6e404 and false of the host at 352886d, so
      // after the host narrowed its rule the check went on vouching for a client defect.
      //
      // Quinn Q-N1 — the refused set is swept in FULL, every code point of it, and the set is
      // DERIVED FROM THE HOST'S RANGES in plan.rs by the harness (window.__RUST_HOSTILE_CPS)
      // rather than typed out here. It used to be an eleven-code-point sample, and every one of
      // the eleven was a range ENDPOINT: narrowing this client's `\u202A-\u202E` to
      // `[\u202A\u202E]` drops U+202D LRO — a Trojan-Source primitive — and the sample went on
      // reporting 1119 checks, 0 FAIL. Sampling the endpoints of a range cannot see the range
      // being hollowed out, which is the same shape of gap (a sample standing in for a class)
      // that let the original defect ship.
      var hostileCps = window.__RUST_HOSTILE_CPS || [];
      ok(hostileCps.length >= 27,
         "PL AC-49 (premise): the harness really did read the host's ranges out of plan.rs — a sweep over an empty or truncated list reports 'all clear' forever and the whole mirror goes unexercised (" + hostileCps.length + " code points)");
      var hostileMissed = hostileCps.filter(function (cp) {
        return planNameProblem("Sunday" + String.fromCodePoint(cp) + "Service") === null;
      });
      ok(hostileMissed.length === 0,
         "PL AC-49 (Quinn Q7): every character the host's is_display_hostile / is_line_separator refuses is refused here too — missed " + hostileMissed.length + " of " + hostileCps.length +
         (hostileMissed.length ? ": " + hostileMissed.map(function (cp) { return "U+" + ("000" + cp.toString(16).toUpperCase()).slice(-4); }).join(" ") : ""));
      // The other direction. Each of these is asserted VALID by the host's own test file; a
      // client that refuses them stops entire writing systems being typed into a name field.
      var admitted = [
        ["\u0DC1\u0DCA\u200D\u0DBB\u0DD3", "Sinhala Sri — U+200D is not optional, the word cannot be written without it"],
        ["\u0646\u200C\u06C1", "Urdu ZWNJ"],
        ["\u0915\u094D\u200C\u0937", "Devanagari conjunct control"],
        ["Sunday \uD83D\uDC68\u200D\uD83D\uDC69\u200D\uD83D\uDC67", "a family emoji is a ZWJ sequence"],
        ["Sun\u200Eday", "LRM — a stateless implicit bidi mark, not an override"],
        ["Sun\u200Fday", "RLM"],
        ["Sun\u061Cday", "ALM"]
      ];
      var admittedRefused = admitted.filter(function (c) { return planNameProblem(c[0]) !== null; });
      ok(admittedRefused.length === 0,
         "PL AC-49 (Quinn Q7, the other direction): the orthographic joiners and stateless bidi marks the host ADMITS are accepted here — refusing them locks writing systems out of the name field (refused " +
         admittedRefused.length + ": " + admittedRefused.map(function (c) { return c[1]; }).join("; ") + ")");
      // ...but a name made only of them still renders as nothing, which is has_visible_content.
      ok(planNameProblem("\u200C\u200C") !== null && planNameProblem(" \u200C ") !== null,
         "PL AC-49: a name of nothing but joiners is still refused — admitted-as-spelling is not admitted-as-content, and the host's has_visible_content draws exactly that line");
      // U+FEFF is the one that proves the test runs on the ORIGINAL string: JS trim() strips it
      // and Rust's does not, so a leading BOM must be refused here or the client is looser than
      // the host on exactly the character the host added the rule for.
      ok(planNameProblem("﻿Sunday Service") !== null,
         "PL AC-49 (Quinn Q7): a LEADING U+FEFF is refused — JS trim() strips it and Rust's does not, so testing the trimmed string would have let it through");
      ok(planNameProblem("Sundays’ Café — 2nd") === null && planNameProblem(astral) === null,
         "PL AC-49 (control): ordinary punctuation, accents and emoji are untouched — the rule refuses invisible formatting, not everything unfamiliar");
      // And the import path inherits it, which is where losing the line number would hurt.
      var invisibleImport = planParseRunSheet("Song: Open‮ing");
      ok(!invisibleImport.items.length && /line 1/i.test(invisibleImport.problems[0] || ""),
         "PL AC-49 (Quinn Q7): an imported title carrying a bidi override is refused BY LINE NUMBER here, rather than as an opaque host bad_request for the whole paste");

      // Quinn Q5 — a run-sheet problem must not blame the Service name field.
      openPlan(emptyLife({ publish: PUB_CLEAN }));
      el("plan-empty-import").click();
      await sleep(20);
      el("pm-prompt-input").value = "A Perfectly Good Name";
      el("plan-import-text").value = "Sermon";
      dlgOk().click();
      await sleep(20);
      ok(el("plan-import-text").getAttribute("aria-invalid") === "true" &&
         !el("pm-prompt-input").getAttribute("aria-invalid"),
         "PL AC-50 (Quinn Q5): a RUN-SHEET problem marks the run sheet invalid, not the valid Service name beside it (WCAG 3.3.1)");
      ok(document.activeElement === el("plan-import-text"),
         "PL AC-50 (Quinn Q5): ...and focus lands on the control the operator has to fix, not on the one that was already correct (WCAG 3.3.2)");
      // ...and the mirror: a bad NAME still marks the name.
      el("plan-import-text").value = "Song: Opening";
      el("pm-prompt-input").value = "   ";
      dlgOk().click();
      await sleep(20);
      ok(el("pm-prompt-input").getAttribute("aria-invalid") === "true" &&
         !el("plan-import-text").getAttribute("aria-invalid"),
         "PL AC-50 (control): a bad NAME marks the name and clears the previous target — the routing decides both ways, it does not simply always blame the textarea");
      // A stray backdrop click must not throw away a long paste.
      var pasted = el("plan-import-text").value;
      document.querySelector(".pm-confirm-back").dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      await sleep(20);
      ok(!!el("plan-import-text") && el("plan-import-text").value === pasted,
         "PL AC-51 (Quinn): a backdrop click does NOT discard a dialog the operator has typed into — a pasted run sheet has no undo");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);
      // ...while a plain name prompt still closes on the backdrop, as it always did.
      openPlan(lifeView({ publish: PUB_CLEAN }));
      el("plan-sum-duplicate").click();
      await sleep(20);
      document.querySelector(".pm-confirm-back").dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      await sleep(20);
      ok(!el("pm-prompt-input"),
         "PL AC-51 (control): a plain name prompt still closes on a backdrop click — the guard protects typed CONTENT, it does not disable the gesture");

      // Quinn Q2 — the badge exists for the case where SOMEONE ELSE edits the plan. Without a
      // refresh it could only ever appear because this operator did something, which is the one
      // case it is not for.
      showSurface("plan");
      await sleep(80);
      var polledBase = JSON.parse(JSON.stringify(V));
      polledBase.publish = { revision: 5, published_revision: 5, version: 4 };
      planSelectedId = null;
      planRenderBuilder(polledBase);
      ok(!el("plan-pub-changed"), "PL AC-52 (setup): the plan is published and unedited, so there is no badge");
      var polledEdited = JSON.parse(JSON.stringify(polledBase));
      polledEdited.publish = { revision: 9, published_revision: 5, version: 4, changed: true };
      planSyncPublishFromPoll(polledEdited);
      ok(!!el("plan-pub-changed"),
         "PL AC-52 (Quinn Q2): a remote edit arriving on the POLL raises the badge — the builder renders only on this operator's own actions, so without this the badge could never show the state it exists for");
      // ...and it must not thrash: an identical poll re-render would eat in-flight clicks, which
      // is the reason render() keys its own plan rebuild on a change signature.
      var badgeNode = el("plan-pub-changed");
      planSyncPublishFromPoll(polledEdited);
      ok(el("plan-pub-changed") === badgeNode,
         "PL AC-52 (control): an unchanged poll re-renders NOTHING — a panel rebuilt every second would eat the clicks landing on it");
      // ...and it stays out of the way while the operator is somewhere else in the surface.
      planSelectedId = 301;
      planRenderBuilder(polledBase);
      var inspHeading = el("plan-insp-h").textContent;
      planSyncPublishFromPoll(polledEdited);
      ok(el("plan-insp-h").textContent === inspHeading,
         "PL AC-52 (control): with an item selected the poll leaves the ITEM inspector alone — the badge is not on screen there, and swapping the panel under the operator would be worse than a late badge");

      // Quinn — the same finding as the badge, applied to the OTHER field the poll ignored: a
      // role demotion arriving from the host left every edit control up until the operator did
      // something and had it refused.
      planSelectedId = null;
      var demoteBase = JSON.parse(JSON.stringify(V));
      demoteBase.viewer = { role: "producer", can_edit: true };
      planRenderBuilder(demoteBase);
      ok(!el("plan-viewonly") && !!document.querySelector("#plan-b-list .plan-b-up"),
         "PL AC-53 (setup): the operator may edit, so there is no View only badge and the row reorder controls are built");
      // QA regression (round 6 — Quinn, bisected to 0876d6c): this block's two state-CHANGE
      // assertions used a fixed `await sleep(20)` between triggering the rebuild and reading the
      // DOM, on the assumption that `planSyncViewerFromPoll` — a plain synchronous function — is
      // always fully applied well within that budget. Adding an unrelated, purely-synchronous
      // block of work earlier in this same script (the TR V-13 checks above — confirmed by Quinn
      // bisecting to `0876d6c` and reproducing on both her machine and this PR's own CI run) was
      // enough to push this fixed budget past its margin under `--virtual-time-budget`, failing
      // this check AND the "rebuilds nothing" control right after it (which captures `rowNode`
      // from whatever the DOM happened to be at that moment — a premature read here left it
      // capturing a stale/pre-rebuild node, so the control failed as a knock-on effect of the
      // same race, not a second independent bug). `waitFor` polls the actual condition instead of
      // gambling on a fixed duration, so this no longer races machine load or a neighbouring
      // check's timing footprint — and `rowNode` below is now captured only once that condition
      // has verifiably settled, closing the knock-on failure at its source.
      var demoted = JSON.parse(JSON.stringify(demoteBase));
      demoted.viewer = { role: "viewer", can_edit: false };
      planSyncViewerFromPoll(demoted);
      await waitFor(function(){
        return !!el("plan-viewonly") && !document.querySelector("#plan-b-list .plan-b-up");
      });
      ok(!!el("plan-viewonly") && !document.querySelector("#plan-b-list .plan-b-up"),
         "PL AC-53 (Quinn): a DEMOTION arriving on the poll takes the edit controls away — the chrome alone was not enough, because the per-row ↑/↓ controls are built by planRenderBuilder and a View only badge over live reorder buttons is worse than either state");
      // ...and it must not rebuild on every poll, for the same reason the publish one must not.
      var rowNode = document.querySelector("#plan-b-list .plan-b-row");
      planSyncViewerFromPoll(demoted);
      ok(document.querySelector("#plan-b-list .plan-b-row") === rowNode,
         "PL AC-53 (control): an unchanged poll rebuilds NOTHING — a surface rebuilt every second would eat the clicks landing on it");
      // ...and a PROMOTION travels the same path, so the mechanism is not one-directional.
      planSyncViewerFromPoll(demoteBase);
      await waitFor(function(){
        return !el("plan-viewonly") && !!document.querySelector("#plan-b-list .plan-b-up");
      });
      ok(!el("plan-viewonly") && !!document.querySelector("#plan-b-list .plan-b-up"),
         "PL AC-53 (control): a promotion arriving on the poll gives the controls BACK — the check above measures the verdict, not a one-way latch");

      // Quinn — a failed open must not leave the last plan's permission chrome painted over a
      // surface that has no plan.
      openPlan(lifeView({ viewer: { role: "viewer", can_edit: false } }));
      ok(!!el("plan-viewonly"), "PL AC-54 (setup): the surface is painted view-only, so there is stale chrome to leave behind");
      planRenderLoading();
      planRenderLoadFailed(new Error("boom"));
      await sleep(20);
      ok(!el("plan-viewonly"),
         "PL AC-54 (Quinn): a failed open clears the View only badge — the failure makes the viewer field UNKNOWN, and painting a restriction from an unknown is the fabrication this surface's three-state rule exists to stop");
      var failedPalette = document.querySelector("#surface-plan .plan-palette");
      ok(!failedPalette || getComputedStyle(failedPalette).display === "none",
         "PL AC-54 (Quinn): ...and the ADD ITEM column goes with it — there is no plan to add an item to, so leaving it up is a control that looks live and cannot work");
      ok(!!document.querySelector("#plan-b-list .plan-load-failed"),
         "PL AC-54 (control): the failure message is still the thing on screen — the chrome reset did not paint over the only explanation the operator gets");

      // --- the WIRING, not just the function ---------------------------------------------------
      // AC-52 and AC-53 call planSyncPublishFromPoll / planSyncViewerFromPoll DIRECTLY. That
      // proves each function does its job; it does not prove the 1 Hz poll ever calls it — and
      // the whole of Quinn's finding was that the poll did not. Deleting the call from the
      // interval left AC-53 completely green, which is the "control asserting a copy" trap in
      // CLAUDE.md: the check consumed the function instead of the wiring. These two drive the
      // REAL interval, by moving the stub view the poll fetches and waiting for a tick.
      showSurface("plan");
      await sleep(60);
      planSelectedId = null;
      V.viewer = { role: "producer", can_edit: true };
      V.publish = { revision: 5, published_revision: 5, version: 4 };
      planRenderBuilder(JSON.parse(JSON.stringify(V)));
      ok(!el("plan-viewonly"),
         "PL AC-55 (setup): the surface is painted from a view that permits editing, so a badge appearing later can only have come from the poll");
      V.viewer = { role: "viewer", can_edit: false };
      await sleep(1300);
      ok(!!el("plan-viewonly"),
         "PL AC-55 (Quinn): the 1 Hz poll actually CALLS the viewer sync — nothing above this line would notice if the call were deleted from the interval, which is exactly how the gap being fixed here got in");
      V.viewer = { role: "producer", can_edit: true };
      await sleep(1300);
      planSelectedId = null;
      planRenderBuilder(JSON.parse(JSON.stringify(V)));
      ok(!el("plan-pub-changed"),
         "PL AC-55 (setup): ...and the same for publish — painted unedited, so a badge can only arrive on the poll");
      V.publish = { revision: 9, published_revision: 5, version: 4, changed: true };
      await sleep(1300);
      ok(!!el("plan-pub-changed"),
         "PL AC-55 (Quinn Q2): the poll actually calls the publish sync too — AC-52 proves the function, this proves the wire");
      delete V.viewer;
      delete V.publish;
      await sleep(1300);

      planSelectedId = null;

      // --- the seam was used as a seam ----------------------------------------------------------
      openPlan(lifeView({ publish: PUB_CLEAN }));
      var sumLabels = Array.prototype.map.call(
        document.querySelectorAll("#plan-b-insp .plan-sum-card .plan-sum-label"),
        function (n) { return n.textContent; }
      ).join("|");
      ok(sumLabels === "Total time|Items|Songs|Scripture|Presentations|Media|Announcements|Timers|Missing content|Assigned",
         "PL AC-28: the Plan Summary CARD is untouched — 86ak8467m adds its actions at the declared planSummaryActions seam and does not rebuild 86ak846ft's panel (got " + sumLabels + ")");
      planSelectedId = null;
      planRenderBuilder(planView); // leave the surface on the driver's own fixture

      // === Settings → Providers & Privacy (Figma 338:124, backend 86ajy034h + 86akby7d8) — the panel
      // renders REAL providers_view() state and each control invokes the right command. HONESTY is
      // the whole point of this screen, and it now cuts BOTH ways: a stock build
      // (cloud_status="not_configured", notes_available=false, quota=null) must show "coming soon"
      // and a placeholder quota and NEVER a fabricated "12/40" — AND a build that can genuinely
      // generate notes must NOT be shown as unavailable. Under-reporting broke this contract as
      // badly as over-reporting: with GPT wired directly the old `cloud_connected` stayed false
      // while real drafts came back, so the panel denied a feature while printing its output.
      // All four cloud_status states are exercised below.
      // ==================================================================================
      var ppCall = function(cmd){ return window.__calls.filter(function(c){return c.cmd===cmd;}); };
      var ppLast = function(cmd){ var a=ppCall(cmd); return a.length?a[a.length-1]:null; };
      document.querySelector('.nav-item[data-surface="settings"]').click(); // showSurface → settingsActivate
      ok(el("surface-settings").classList.contains("active"), "PP: the Settings nav opens the Providers & Privacy surface");
      // hidden-attr-vs-css-display trap: assert the COMPUTED display, not just the .active class.
      ok(getComputedStyle(el("surface-settings")).display === "block",
         "PP C-008: the active Settings surface is computed display:block (not defeated by a display rule)");
      await sleep(60); // let settingsActivate resolve invoke("providers_view") + render
      ok(ppCall("providers_view").length > 0, "PP C-001: activation reads real state via providers_view()");
      ok(!/Application settings arrive later/.test(el("surface-settings").textContent),
         "PP C-001: the old stub copy is gone");

      // (1) Offline-by-default banner
      var ppBanner = document.querySelector("#surface-settings .pp-banner-ok");
      ok(!!ppBanner && /Offline by default/.test(ppBanner.textContent), "PP C-001: the Offline-by-default banner renders");
      ok(/never leave this device/.test(ppBanner.textContent), "PP C-001: the offline banner carries the honest 'never leave this device' copy");

      // (2) LIVE TRANSCRIPTION radio cards
      var odCard = el("pp-radio-ondevice"), clCard = el("pp-radio-cloud");
      ok(!!odCard && !!clCard, "PP C-002: both transcription radio cards render (On-device + Cloud)");
      ok(odCard.getAttribute("role")==="radio" && clCard.getAttribute("role")==="radio" &&
         document.querySelector('#pp-trans[role="radiogroup"]'),
         "PP C-002 a11y: the two cards form a radiogroup of role=radio");
      ok(odCard.getAttribute("aria-checked")==="true" && clCard.getAttribute("aria-checked")==="false",
         "PP C-002: On-device is the selected (private) default; Cloud is unselected");
      ok(/PRIVATE/.test(odCard.textContent) && !!odCard.querySelector(".pp-badge-private"),
         "PP C-002: the On-device card shows the PRIVATE badge");
      var odDetail = odCard.querySelector(".pp-radio-detail");
      ok(!!odDetail && /Small/.test(odDetail.textContent) && /works offline/.test(odDetail.textContent),
         "PP C-002: the On-device model line is driven from the backend on_device probe (model 'Small')");
      ok(/OPT-IN/.test(clCard.textContent) && !!clCard.querySelector(".pp-badge-optin"),
         "PP C-002: the Cloud card shows the OPT-IN badge");
      var clWarn = clCard.querySelector(".pp-warn");
      ok(!!clWarn && /Streams live microphone audio/.test(clWarn.textContent),
         "PP C-002: the Cloud card shows the amber live-audio warning");
      ok(/currently off/.test(clCard.textContent), "PP C-002: the Cloud footer honestly reads 'currently off' when consent is off");

      // Selecting Cloud is the opt-in gesture: grants transcription consent THEN switches mode.
      var scBefore = ppCall("set_cloud_consent").length, tmBefore = ppCall("set_transcription_mode").length;
      el("pp-radio-cloud").click();
      await sleep(70);
      var scT = ppCall("set_cloud_consent").filter(function(c){return c.args.kind==="transcription" && c.args.enabled===true;});
      ok(scT.length > 0, "PP C-002: selecting Cloud grants transcription consent (set_cloud_consent{transcription,true})");
      ok(ppLast("set_transcription_mode") && ppLast("set_transcription_mode").args.mode==="cloud",
         "PP C-002: selecting Cloud switches the mode (set_transcription_mode{cloud})");
      ok(el("pp-radio-cloud").getAttribute("aria-checked")==="true" && /currently on/.test(el("pp-radio-cloud").textContent),
         "PP C-002: after opt-in the Cloud card is selected and the footer reads 'currently on'");
      // Selecting On-device switches back AND revokes cloud-transcription consent (audio stays local).
      el("pp-radio-ondevice").click();
      await sleep(70);
      ok(ppLast("set_transcription_mode").args.mode==="on_device",
         "PP C-002: selecting On-device switches the mode back (set_transcription_mode{on_device})");
      ok(ppCall("set_cloud_consent").some(function(c){return c.args.kind==="transcription" && c.args.enabled===false;}),
         "PP C-002: selecting On-device revokes cloud-transcription consent (audio never leaves the device)");
      ok(el("pp-radio-ondevice").getAttribute("aria-checked")==="true", "PP C-002: On-device is selected again");

      // (2b) 86akby7th PR #22 review (Cody, Medium): the Cloud card's live-audio warning must
      // name the ACTUAL provider driven from transcription_provider/transcription_available —
      // not merely satisfy a prefix regex ("Streams live microphone audio") that would pass
      // whether the rendered name were "Deepgram", a generic string, or "undefined". Both
      // states are driven here the same way the notes-provider states are driven above (C-010).
      window.__pp.transcription_provider = null; // transcription_available derives to false
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);
      var clWarnUnready = el("pp-radio-cloud").querySelector(".pp-warn");
      ok(!!clWarnUnready && /a cloud speech service/.test(clWarnUnready.textContent),
         "PP C-002 (86akby7th): with transcription_available=false the warning falls back to the honest generic name, not a fabricated provider");
      ok(!/Deepgram/.test(clWarnUnready.textContent) && !/undefined/i.test(clWarnUnready.textContent),
         "PP C-002 (86akby7th): with no provider named, the warning must not say Deepgram or leak 'undefined'");
      ok(/not available right now on this machine/.test(el("pp-radio-cloud").textContent),
         "PP C-002 (86akby7th): with transcription_available=false the footer honestly says the feature is not ready on this machine");

      window.__pp.transcription_provider = {kind:"deepgram", name:"Deepgram", model:"nova-3", developer_key:true};
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);
      var clWarnReady = el("pp-radio-cloud").querySelector(".pp-warn");
      ok(!!clWarnReady && /Deepgram/.test(clWarnReady.textContent),
         "PP C-002 (86akby7th): with a real provider named, the warning says Deepgram specifically (FR-120/FR-132)");
      ok(!/not available right now on this machine/.test(el("pp-radio-cloud").textContent),
         "PP C-002 (86akby7th): with transcription_available=true the footer does not claim the feature is unavailable");
      window.__pp.transcription_provider = null; // restore the stock-build default for later checks

      // (3) AI sermon notes — honest status FIRST (no fabricated pills/quota with nothing configured).
      var aiStatus = document.querySelector(".pp-ai-status");
      ok(!!aiStatus && !/Cloud connected/.test(aiStatus.textContent) && !/Available/.test(aiStatus.textContent),
         "PP C-006: with notes_available=false the Available / Cloud-connected pills are NOT shown");
      ok(!!aiStatus.querySelector(".pp-pill-muted") && /Coming soon/.test(aiStatus.textContent),
         "PP C-006: an honest 'Coming soon' pill is shown instead");
      ok(!/12\s*\/\s*40/.test(el("surface-settings").textContent),
         "PP C-006: NO fabricated '12 / 40' quota anywhere on the panel");
      var ppQuota = document.querySelector(".pp-quota");
      ok(!!ppQuota && ppQuota.classList.contains("pp-quota-empty") && /Not available yet/.test(ppQuota.textContent),
         "PP C-006: the quota shows an honest placeholder (null quota → 'Not available yet'), not numbers");
      // 86akby7d8: with nothing configured the card must NOT claim a provider or an included plan.
      ok(!document.querySelector(".pp-badge-included") && !document.querySelector(".pp-badge-dev"),
         "PP C-010: with no provider configured, neither the INCLUDED nor the DEVELOPER KEY badge is shown");
      ok(!/no accounts, keys or billing to manage/i.test(el("surface-settings").textContent),
         "PP C-010: the 'no accounts, keys or billing to manage' claim is gone — it is false once a developer key generates the notes");

      // (3) selects — options + selected value from the backend; each change invokes its command.
      var tSel = el("pp-template");
      ok(!!tSel && tSel.tagName==="SELECT" && tSel.options.length===3 && tSel.value==="full_outline",
         "PP C-003: the notes-template select lists the backend options with the current value selected");
      ok(tSel.getBoundingClientRect().width > 40,
         "PP C-003: the template <select> does not collapse to a sliver (WKWebView flex-collapse trap)");
      tSel.value = "summary"; tSel.dispatchEvent(new Event("change"));
      await sleep(50);
      ok(ppLast("set_notes_template") && ppLast("set_notes_template").args.template==="summary",
         "PP C-003: changing the template invokes set_notes_template{template}");
      var xSel = el("pp-translation");
      ok(!!xSel && xSel.tagName==="SELECT" && xSel.value==="KJV" && xSel.classList.contains("pp-select-gold"),
         "PP C-003: the translation select shows the current (gold) value from the backend");
      xSel.value = "WEB"; xSel.dispatchEvent(new Event("change"));
      await sleep(50);
      ok(ppLast("set_preferred_translation") && ppLast("set_preferred_translation").args.code==="WEB",
         "PP C-003: changing the translation invokes set_preferred_translation{code}");

      // (3) INCLUDE IN NOTES — 8 switches in two columns; each invokes set_include_flag{name,enabled}.
      // 86akgqdwc added "Podcast show notes" (left) and "Short description" (right), one per
      // column, so the 3/3 split from the six pre-existing toggles becomes 4/4.
      var incCols = document.querySelectorAll("#surface-settings .pp-inc-col");
      ok(incCols.length===2 && incCols[0].querySelectorAll(".pp-inc-row").length===4 && incCols[1].querySelectorAll(".pp-inc-row").length===4,
         "PP C-004: the 8 include-in-notes toggles render in two columns of four");
      var soc = el("pp-inc-social_excerpts");
      ok(!!soc && soc.getAttribute("role")==="switch" && soc.checked===false,
         "PP C-004: 'Social excerpts' is a switch reflecting the backend (off)");
      soc.click(); // check it
      await sleep(50);
      var incSoc = ppLast("set_include_flag");
      ok(incSoc && incSoc.args.name==="social_excerpts" && incSoc.args.enabled===true,
         "PP C-004: toggling a switch invokes set_include_flag{name:social_excerpts,enabled:true}");
      el("pp-inc-prayer_points").click(); // was on → turn off
      await sleep(50);
      ok(ppLast("set_include_flag").args.name==="prayer_points" && ppLast("set_include_flag").args.enabled===false,
         "PP C-004: toggling another switch off invokes set_include_flag{name:prayer_points,enabled:false}");
      // Every one of the remaining flags fires with the correct snake_case name + toggled value
      // (a wrong name string would be a silent no-op the 2-flag check above would miss). Includes
      // the two 86akgqdwc toggles, both OFF in the backend fixture, so this also exercises the
      // off→on direction the two checks above didn't.
      ["scripture_extraction","chapter_markers","notable_quotations","short_summary","podcast_show_notes","short_description"].forEach(function(nm){
        var sw = el("pp-inc-"+nm), before = sw.checked;
        sw.click(); // checkbox change fires synchronously → the invoke is recorded immediately
        var last = ppLast("set_include_flag");
        ok(last && last.args.name===nm && last.args.enabled===(!before),
           "PP C-004: toggling '"+nm+"' invokes set_include_flag{name:"+nm+", enabled:"+(!before)+"}");
      });
      await sleep(40);
      // (M2 — no-lie on host rejection) a REJECTED mutation must revert the optimistic switch to the
      // backend-confirmed value (mutate() resyncs via providers_view), never leaving a lying toggle.
      var rjBackend = window.__pp.include.short_summary; // authoritative value the backend keeps
      ok(el("pp-inc-short_summary").checked === rjBackend, "PP C-004: (pre) the switch matches the backend value");
      window.__ppRejectOnce = true;
      el("pp-inc-short_summary").click(); // optimistic flip → host rejects → resync
      await sleep(90);
      ok(window.__pp.include.short_summary === rjBackend,
         "PP C-004: a rejected set_include_flag leaves the BACKEND value unchanged");
      ok(el("pp-inc-short_summary").checked === rjBackend,
         "PP C-004 (M2): after a host rejection the switch REVERTS to the backend value (no silent lie)");

      // (3) Generate — consent-gated end to end.
      ok(el("pp-consent-notes") && el("pp-consent-notes").getAttribute("role")==="switch" && el("pp-consent-notes").checked===false,
         "PP C-005: the cloud-notes consent switch reflects the backend (off) before opt-in");

      // 86akby7d8 defect 1: the panel has no transcript store of its own — it reads app.js's
      // bridge, window.scCompletedTranscript, set on every render() from the host-authoritative
      // view.transcript (syncTranscript() in app.js) — exactly the FULL poll->render path the R3
      // display checks above already exercise, not a shortcut. Before this fix nothing anywhere
      // assigned that global, so it stayed "" and every Generate click sent an empty transcript.
      // Drive it for real: render() with finalised segments, through the SAME render() the 1s
      // poll invokes, then assert the bridge actually did its job before trusting it below.
      var PP_TRANSCRIPT_SEGMENTS = [
        { id: 601, text: "Good morning, church.", start_ms: 0, end_ms: 2000 },
        { id: 602, text: "Turn with me to Isaiah sixty-one.", start_ms: 2000, end_ms: 5000 },
        { id: 603, text: "This morning we consider what it means to be fed by grace, not by our own striving.", start_ms: 5000, end_ms: 9000 },
      ];
      var PP_TRANSCRIPT_FIXTURE =
        "Good morning, church.\n" +
        "Turn with me to Isaiah sixty-one.\n" +
        "This morning we consider what it means to be fed by grace, not by our own striving.";
      render(Object.assign({}, baseView, { transcript: PP_TRANSCRIPT_SEGMENTS, partial_transcript: "and the crowd came back" }));
      ok(window.scCompletedTranscript === PP_TRANSCRIPT_FIXTURE,
         "PP defect 1: render() with finalised segments populates window.scCompletedTranscript via the real app.js bridge, joined in order");
      ok(window.scCompletedTranscript.indexOf("and the crowd came back") === -1,
         "PP defect 1: the in-progress partial line is NEVER part of the completed transcript the bridge exposes");
      render(Object.assign({}, baseView, { transcript: PP_TRANSCRIPT_SEGMENTS })); // clear the partial, keep the segments
      ok(window.scCompletedTranscript === PP_TRANSCRIPT_FIXTURE,
         "PP defect 1: the bridge is stable (same segments -> same completed transcript) once the partial clears");

      // L-3 (Vera, note — 86akby7d8 remediation): the bridge must map the SAME capped list the
      // DOM renders from (`segs`, MAX_TRANSCRIPT_ROWS=120), not the unsliced `all` — so if a host
      // ever returns more than the DOM's own defensive cap, "what Generate sends" and "what the
      // transcript log shows" never disagree about what "the transcript" is.
      var PP_OVERCAP_SEGMENTS = [];
      for (var ppOc = 0; ppOc < 125; ppOc++) {
        PP_OVERCAP_SEGMENTS.push({ id: 900 + ppOc, text: "seg" + ppOc, start_ms: ppOc * 100, end_ms: ppOc * 100 + 90 });
      }
      render(Object.assign({}, baseView, { transcript: PP_OVERCAP_SEGMENTS }));
      var ppOvercapExpected = PP_OVERCAP_SEGMENTS.slice(-120).map(function (s) { return s.text; }).join("\n");
      ok(window.scCompletedTranscript === ppOvercapExpected,
         "PP L-3: over the DOM's own 120-segment cap, the Generate bridge reflects the SAME tail #transcript-log renders, not the unsliced list");
      ok(window.scCompletedTranscript.indexOf("seg0") === -1,
         "PP L-3: ...specifically, the oldest over-cap segment is excluded — proving this is actually capped, not coincidentally equal");
      render(Object.assign({}, baseView, { transcript: PP_TRANSCRIPT_SEGMENTS })); // restore the fixture for the checks below

      // Persist into the mock's own view state too (not just this one-off render()): the REAL
      // app.js 1s poll keeps running underneath this whole block (exactly as it does in the real
      // app while the operator sits on Settings), and every reactivation below re-fetches
      // invoke("view") — either would otherwise re-render from V's default (no transcript) and
      // silently wipe window.scCompletedTranscript back to "" partway through this test.
      V.transcript = PP_TRANSCRIPT_SEGMENTS;

      // 86akby7d8 defect 2 / F-5 (Sana, escalated blocking by Quinn): Generate no longer sends on
      // click — it opens a review step showing the exact text and waits for an explicit Confirm.
      // This helper drives that two-step flow so the pre-existing outcome checks below don't have
      // to duplicate it, and it re-asserts the core guarantee (no send without Confirm) on every
      // single call site that exercises Generate — a regression back to send-on-click would fail
      // here, not just in the dedicated F-5 block further down.
      var ppGenerateAndConfirm = async function (waitAfterConfirm) {
        var before = ppCall("generate_sermon_notes").length;
        el("pp-generate").click();
        await sleep(30);
        ok(ppCall("generate_sermon_notes").length === before,
           "PP F-5: clicking Generate alone never calls generate_sermon_notes — the review step opens first");
        var confirmBtn = el("pp-gen-preview-confirm");
        if (confirmBtn) confirmBtn.click();
        await sleep(waitAfterConfirm || 70);
      };

      // Generate with consent OFF → the backend returns consent_required → prompt to opt in.
      window.__ppGen = "not_configured";
      await ppGenerateAndConfirm(70);
      var genRes = el("pp-gen-result");
      ok(!!genRes && !genRes.hidden && genRes.getAttribute("role")==="alert" && /Turn on cloud processing/.test(genRes.textContent),
         "PP C-005: Generate with consent off surfaces a consent_required prompt (role=alert)");
      ok(!!el("pp-optin-retry"), "PP C-005: the consent_required prompt offers a one-click 'Opt in & generate'");
      // PP-GEN: .pp-optin-btn:hover — same defect class as .pm-btn-primary:hover/CON-007/PME-005.
      // Checked HERE because #pp-optin-retry only exists transiently, during this consent_required
      // state — the click below (opting in) removes it again, so a later check point would miss it.
      (function() {
        var restBg = _rgba(getComputedStyle(el("pp-optin-retry")).backgroundColor);
        var hoverRule = __cssRule(".pp-optin-btn:hover");
        ok(!!hoverRule, "PP-GEN (premise): the .pp-optin-btn:hover rule is present in the shipped app.css");
        var hb = __cssBg(hoverRule);
        ok(!!hb, "PP-GEN (premise): the .pp-optin-btn:hover rule declares a background, so there is a value to measure");
        if (hb) {
          var hoverBg = _resolve(hb.trim());
          var hoverR = _cr([255,255,255,1], hoverBg);
          ok(hoverR >= 4.5, "PP-GEN: the HOVERED .pp-optin-btn keeps its white label at AA-NORMAL (" + _f(hoverR) + ":1)");
          ok(_lum(hoverBg) < _lum(restBg),
             "PP-GEN: .pp-optin-btn hover DARKENS the fill instead of lightening it, matching .pm-btn-primary:hover");
        }
        var oldHover = _resolve("var(--sc-primary-hover)");
        ok(_cr([255,255,255,1], oldHover) < 4.5,
           "PP-GEN (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], oldHover)) + ":1) — the TOKEN VALUE is untouched; only this rule stopped using it");
      })();
      // Opt in & generate → grants notes consent then retries (through the SAME review-and-confirm
      // gate — opting in mid-flow does not bypass it); the service is not configured → 'coming soon'.
      el("pp-optin-retry").click();
      await sleep(60);
      ok(ppCall("set_cloud_consent").some(function(c){return c.args.kind==="notes" && c.args.enabled===true;}),
         "PP C-005: 'Opt in & generate' grants cloud-notes consent (set_cloud_consent{notes,true})");
      var confirmAfterOptin = el("pp-gen-preview-confirm");
      if (confirmAfterOptin) confirmAfterOptin.click();
      await sleep(60);
      var genRes2 = el("pp-gen-result");
      ok(!!genRes2 && genRes2.getAttribute("role")==="status" && /isn.t available in this build/i.test(genRes2.textContent),
         "PP C-005: with consent on but nothing configured, Generate says so honestly (role=status, not an error)");
      // 86akby7d8: the SAME not_configured error code means two different things, and the panel
      // tells them apart from the status it already holds. "we haven't built it" and "you haven't
      // supplied a key" ask different things of the reader; collapsing them wastes their time.
      window.__pp.cloud_status = "key_missing";
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);
      await ppGenerateAndConfirm(70);
      var genKey = el("pp-gen-result");
      ok(!!genKey && /OPENAI_API_KEY/.test(genKey.textContent) && /\.env/.test(genKey.textContent),
         "PP C-010: under key_missing the SAME not_configured code renders the actionable missing-key message instead");
      ok(!/isn.t available in this build/i.test(genKey.textContent),
         "PP C-010: ...and NOT the generic 'not available in this build' copy — the two states stay distinguishable");
      window.__pp.cloud_status = "not_configured";
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);
      ok(el("pp-consent-notes").checked===true, "PP C-005: the consent switch now reflects the granted consent");
      // Now simulate a configured service returning a draft.
      window.__ppGen = "ok";
      await ppGenerateAndConfirm(80);
      var genOk = el("pp-gen-result");
      ok(!!genOk && genOk.classList.contains("pp-gen-ok") && /Grace That Feeds/.test(genOk.textContent),
         "PP C-005: a successful generation renders the returned draft (title + sections)");
      ok(genOk.querySelectorAll(".pp-gen-list li").length > 0 && /Isaiah 61:5/.test(genOk.textContent),
         "PP C-005: the draft renders section items + scriptures");

      // --- 86akby7d8: FR-123 label, FR-128 disclosure, FR-122 sub-points ------------------
      var aiLabel = genOk.querySelector(".pp-gen-ai-label");
      ok(!!aiLabel && getComputedStyle(aiLabel).display !== "none" && /AI-generated/i.test(aiLabel.textContent),
         "PP C-011 (FR-123): a model draft is VISIBLY labelled AI-generated (computed display, not just present)");
      var disc = genOk.querySelector(".pp-gen-disclosure");
      ok(!!disc && getComputedStyle(disc).display !== "none",
         "PP C-011 (FR-128): the fabrication-risk disclosure is rendered with the draft");
      ok(/invent/i.test(disc.textContent) && /Check every/i.test(disc.textContent),
         "PP C-011 (FR-128): the disclosure actually warns that the model can invent things and asks for review");
      // The retention/DPA language is Phase 2 (86akby942) and must NOT appear yet: naming a provider
      // is safe without the DPA work, describing its retention posture is not.
      ok(!/retention|retain|training data|processing agreement|DPA/i.test(disc.textContent),
         "PP C-011: the disclosure makes NO retention or data-processing claim (that is gated on the DPA ticket)");
      // FR-122: sub-points render nested INSIDE their parent point, not flattened into one list.
      var pt = genOk.querySelector(".pp-gen-point");
      ok(!!pt && /crowd came back/.test(pt.textContent),
         "PP C-012 (FR-122): outline points render");
      var sub = genOk.querySelector(".pp-gen-point > .pp-gen-sublist");
      ok(!!sub && sub.querySelectorAll("li").length === 2,
         "PP C-012 (FR-122): sub-points render as a NESTED list inside their parent point, not flattened");
      ok(genOk.querySelectorAll(".pp-gen-sublist > li")[0].textContent === "They ate of the loaves",
         "PP C-012 (FR-122): a sub-point is attached to the right parent point");
      // quota is null even on the SUCCESS path in this phase — no meter is conjured from a working
      // generation. This is the negative requirement a well-meaning implementation invents past.
      var qAfter = document.querySelector(".pp-quota");
      ok(qAfter.classList.contains("pp-quota-empty"),
         "PP C-006: a successful generation with no metering leaves the honest quota placeholder alone");

      // (C-005 — the terminal generate outcomes each surface honestly; consent is on from the opt-in above.)
      window.__ppGen = "quota_exceeded"; await ppGenerateAndConfirm(70);
      var gQ = el("pp-gen-result");
      ok(gQ.getAttribute("role")==="alert" && /Monthly limit reached/.test(gQ.textContent),
         "PP C-005: quota_exceeded surfaces 'Monthly limit reached' (role=alert)");
      window.__ppGen = "transport"; await ppGenerateAndConfirm(70);
      var gT = el("pp-gen-result");
      ok(gT.getAttribute("role")==="alert" && /Couldn’t generate notes/.test(gT.textContent),
         "PP C-005: a transport failure (rejected invoke) surfaces 'Couldn’t generate notes' (role=alert)");
      window.__ppGen = "malformed"; await ppGenerateAndConfirm(70);
      var gM = el("pp-gen-result");
      ok(gM.getAttribute("role")==="alert" && /Couldn’t generate notes/.test(gM.textContent),
         "PP C-005: a malformed response surfaces 'Couldn’t generate notes' (role=alert)");
      // A degraded (local fallback) success renders the draft with a 'Local draft' badge — and,
      // following the errors above, the result region is role=status, NOT a lingering alert (L1).
      window.__ppGen = "degraded"; await ppGenerateAndConfirm(80);
      var gD = el("pp-gen-result");
      ok(gD.classList.contains("pp-gen-ok") && /Local draft/.test(gD.textContent),
         "PP C-005: a degraded generation renders the draft with a 'Local draft' badge (FR-135)");
      // 86akby7d8: the offline scaffold is NOT a model, so it carries no AI label and no fabrication
      // warning — but it must NOT be shown in silence either, or a scaffold reads as though it were
      // the AI notes the operator asked for.
      ok(!gD.querySelector(".pp-gen-ai-label"),
         "PP C-011: a degraded offline draft is NOT labelled AI-generated (it invents nothing — the label would be a false claim)");
      ok(!gD.querySelector(".pp-gen-disclosure"),
         "PP C-011: a degraded offline draft carries no fabrication warning, which does not apply to it");
      var degNote = gD.querySelector(".pp-gen-degraded");
      ok(!!degNote && getComputedStyle(degNote).display !== "none" && /could not be reached/i.test(degNote.textContent),
         "PP C-011 (FR-135): a degraded draft says IN WORDS that the provider was unreachable and this is not the AI draft asked for");
      ok(/not AI-generated notes/i.test(degNote.textContent),
         "PP C-011 (FR-135): the degraded notice is explicit that these are not AI-generated notes");
      ok(gD.getAttribute("role")==="status",
         "PP C-005 (L1): a success after an error is announced as role=status, not a lingering alert");

      // --- 86akc0tua: a section the operator requested and got nothing back says so ------------
      // Degraded suppression FIRST, on the SAME "degraded" fixture already rendered above (gD) —
      // its mock now also carries a caveated, empty "Prayer points" section (see the fixture's own
      // comment for why: this is a mutation-catching check, not a realistic-payload one).
      ok(gD.querySelectorAll(".pp-gen-empty").length === 0,
         "PP 86akc0tua: a degraded draft renders ZERO empty-requested lines, even though its own " +
         "payload carries an empty, caveated section — the suppression is the CONSOLE's, not merely " +
         "an accident of what the real backend happens to send");
      ok(!gD.querySelector(".pp-gen-empty-explainer"),
         "PP 86akc0tua: a degraded draft never renders the once-per-draft explainer either");

      function ppSecHeading(root, text) {
        return Array.prototype.filter.call(root.querySelectorAll(".pp-gen-sec-h"), function (h) {
          return h.textContent === text;
        })[0];
      }
      var EMPTY_LINE = "Included in the request — nothing came back.";

      window.__ppGen = "empty_sections"; await ppGenerateAndConfirm(80);
      var gE = el("pp-gen-result");

      var chHeading = ppSecHeading(gE, "Chapter markers");
      ok(!!chHeading, "PP 86akc0tua: an empty-but-requested section's heading still renders, in its natural position");
      var chEmpty = chHeading && chHeading.nextElementSibling;
      ok(!!chEmpty && chEmpty.classList.contains("pp-gen-empty") &&
         getComputedStyle(chEmpty).display !== "none" && chEmpty.getClientRects().length > 0 &&
         chEmpty.textContent === EMPTY_LINE,
         "PP 86akc0tua: the empty-requested line replaces the (would-be-empty) list — computed-visible, exact copy");

      // POSITIVE CONTROL: a populated section in the SAME render still gets its list, not a
      // line — without this, the assertion above could pass on a mechanism that marks
      // EVERY section empty regardless of content.
      var illHeading = ppSecHeading(gE, "Illustrations");
      var illList = illHeading && illHeading.nextElementSibling;
      ok(!!illList && illList.tagName === "UL" && illList.classList.contains("pp-gen-list") &&
         illList.querySelectorAll("li").length === 1 && !illList.classList.contains("pp-gen-empty"),
         "PP 86akc0tua (positive control): a populated section renders its list, not an empty-line");

      // OFF: a section never in the response (the operator left it switched off) is absent
      // entirely — no heading, no message. Asserted on absence of the heading TEXT, not a class,
      // per the ticket's own verification bar.
      ok(!/Notable quotations/.test(gE.textContent),
         "PP 86akc0tua: a section the operator never enabled is absent entirely — no heading, no message");

      // `summary`/`scriptures` are not `NoteSection`s, so they get their own assertions —
      // same copy, same suppression rule, per Uma's "one string covers all four unmodified".
      var summaryHeading = ppSecHeading(gE, "Summary");
      ok(!!summaryHeading, "PP 86akc0tua: an empty-but-requested Summary is given a heading so the line has somewhere to attach");
      ok(!!summaryHeading && summaryHeading.nextElementSibling &&
         summaryHeading.nextElementSibling.classList.contains("pp-gen-empty") &&
         summaryHeading.nextElementSibling.textContent === EMPTY_LINE,
         "PP 86akc0tua: the empty Summary uses the exact same copy as a section");
      var scriptEmpty = gE.querySelector(".pp-gen-scriptures .pp-gen-empty");
      ok(!!scriptEmpty && scriptEmpty.textContent === EMPTY_LINE,
         "PP 86akc0tua: an empty-but-requested scripture list renders the same line inline after 'Scriptures:'");

      // Once per draft, after everything else, only because at least one caveat fired.
      var explainer = gE.querySelector(".pp-gen-empty-explainer");
      ok(!!explainer && getComputedStyle(explainer).display !== "none" && explainer.getAttribute("role") === "note" &&
         /doesn.t say why/i.test(explainer.textContent) && /Generating again/.test(explainer.textContent),
         "PP 86akc0tua: the once-per-draft explainer renders, role=note, exact wording, when at least one caveat fired");

      // Cody's second finding on PR #46 (the reload route was fixed by `sections_to_persist`
      // server-side; this is the OTHER reachable route — edit-save, which the backend has NO
      // caveat data to filter on at all, since `NoteSectionInput` carries no `empty_requested`).
      // Generate a caveated-empty section, edit something ELSE, Save — the caveated-empty
      // section must never reach `update_sermon_note_draft`'s payload, while an ordinary
      // populated section still does (positive control).
      el("pp-gen-edit").click();
      document.getElementById("pp-edit-title").value = "A Quiet Sunday (edited)";
      var emptySaveBefore = ppCall("update_sermon_note_draft").length;
      el("pp-gen-save").click();
      await sleep(60);
      ok(ppCall("update_sermon_note_draft").length === emptySaveBefore + 1,
         "PP 86akc0tua (edit-save fix, setup): Save actually called update_sermon_note_draft");
      var emptySaveArgs = ppLast("update_sermon_note_draft").args;
      ok(!emptySaveArgs.sections.some(function (s) { return s.heading === "Chapter markers"; }),
         "PP 86akc0tua (edit-save fix): a caveated-empty section the operator did not fill in " +
         "is NEVER sent to update_sermon_note_draft — saving ANY unrelated edit must not write " +
         "the confusing 'bare heading, no explanation' state to persisted storage");
      ok(emptySaveArgs.sections.some(function (s) { return s.heading === "Illustrations"; }),
         "PP 86akc0tua (positive control): an ordinary populated section is NOT dropped by the " +
         "same filter — without this, the assertion above could pass on a mechanism that drops " +
         "every section");

      // --- 86akby820: scripture verification (FR-125/FR-128) -----------------------------------
      // Runs AFTER the 86akc0tua edit-save block above rather than before it: that block keeps
      // operating on the still-active "empty_sections" draft from earlier in this section (no
      // re-generate call), while this block deliberately switches `window.__ppGen` and calls
      // `ppGenerateAndConfirm` again — doing that first would pull the rug out from under the
      // edit-save block's fixture. Two independent, non-conflicting insertions at the same
      // point in the file (confirmed by reading both diffs before merging, not assumed); this
      // ordering is the only one that keeps both correct.
      window.__ppGen = "scripture_verification"; await ppGenerateAndConfirm(80);
      var gS = el("pp-gen-result");
      var scLine = gS.querySelector(".pp-gen-scriptures");
      ok(!!scLine && /John 3:16/.test(scLine.textContent),
         "PP 86akby820: a verified reference still renders in the Scriptures line");
      var verifiedItem = Array.prototype.filter.call(scLine.querySelectorAll(".pp-gen-scr-item"), function (s) {
        return s.textContent === "John 3:16";
      })[0];
      var verifiedMark = verifiedItem && verifiedItem.nextElementSibling;
      // Security review finding (Sana F3): "verified" gets its OWN explicit mark — silence
      // is never the only signal, so a check that slips past a gap can't read as clean.
      ok(!!verifiedMark && verifiedMark.classList.contains("pp-gen-scr-verified") &&
         getComputedStyle(verifiedMark).display !== "none" && verifiedMark.getClientRects().length > 0,
         "PP 86akby820 (F3): a verified reference carries its OWN explicit computed-visible mark, " +
         "not just the absence of the unverified one");
      ok(!verifiedMark.classList.contains("pp-gen-scr-unverified"),
         "PP 86akby820 (positive control): a verified reference's mark is the VERIFIED class, " +
         "not the unverified one — without this, the assertion below could pass on a mechanism " +
         "that marks EVERY reference the same way");
      var unverifiedItem = Array.prototype.filter.call(scLine.querySelectorAll(".pp-gen-scr-item"), function (s) {
        return s.textContent === "3Jn 4:12";
      })[0];
      ok(!!unverifiedItem,
         "PP 86akby820 (F1): an ABBREVIATED reference ('3Jn 4:12', not the canonical '3 John " +
         "4:12') still renders in the list at all — proves the exact-match lookup keys on the " +
         "model's own spelling, not a re-canonicalised one");
      var unverifiedMark = unverifiedItem && unverifiedItem.nextElementSibling;
      ok(!!unverifiedMark && unverifiedMark.classList.contains("pp-gen-scr-unverified") &&
         getComputedStyle(unverifiedMark).display !== "none" && unverifiedMark.getClientRects().length > 0 &&
         /unverified/i.test(unverifiedMark.textContent),
         "PP 86akby820: an unverified (abbreviated-spelling) reference in the extracted list " +
         "carries a computed-visible mark — the exact bug class Sana's F1 finding named");
      // Embedded-only: a fabricated reference found ONLY inside a section's body text (not in
      // the extracted `scriptures` list at all) still gets an unmissable mark — the ticket's own
      // named more-dangerous case.
      var elsewhereBlock = Array.prototype.filter.call(gS.querySelectorAll(".pp-gen-scriptures"), function (p) {
        return /Also referenced in this draft/.test(p.textContent);
      })[0];
      ok(!!elsewhereBlock && /Jude 2:1/.test(elsewhereBlock.textContent) &&
         !!elsewhereBlock.querySelector(".pp-gen-scr-unverified"),
         "PP 86akby820: a fabricated reference embedded ONLY in a sermon point (not in the " +
         "extracted list) still renders, unmissably marked — the more dangerous case the ticket names");
      // The address-only scope of verification is stated in words, not implied.
      var scNote = gS.querySelector(".pp-gen-scripture-note");
      ok(!!scNote && getComputedStyle(scNote).display !== "none" && scNote.getAttribute("role") === "note" &&
         /exists in the bundled Bible text/.test(scNote.textContent) &&
         /does not confirm/.test(scNote.textContent),
         "PP 86akby820: the verification-scope note renders, role=note, and is explicit that " +
         "verification confirms the reference exists, not that quoted words are accurate");

      // Security review remediation (Sana F4 on PR #47): the check must survive an
      // edit-save, not just the live generation — edit something UNRELATED (the title)
      // and confirm the unverified mark, the verified mark, and the note are all STILL
      // there afterward, re-verified fresh rather than silently dropped.
      el("pp-gen-edit").click();
      document.getElementById("pp-edit-title").value = "Grace in the Wilderness (edited)";
      el("pp-gen-save").click();
      await sleep(60);
      var gSAfterSave = el("pp-gen-result");
      ok(/Grace in the Wilderness \(edited\)/.test(gSAfterSave.textContent),
         "PP 86akby820 (F4 setup): the edit actually saved — proves the check below is against " +
         "a real post-save render, not the pre-edit one");
      var scLineAfterSave = gSAfterSave.querySelector(".pp-gen-scriptures");
      var verifiedAfterSave = Array.prototype.filter.call(scLineAfterSave.querySelectorAll(".pp-gen-scr-item"), function (s) {
        return s.textContent === "John 3:16";
      })[0];
      ok(!!verifiedAfterSave && verifiedAfterSave.nextElementSibling &&
         verifiedAfterSave.nextElementSibling.classList.contains("pp-gen-scr-verified"),
         "PP 86akby820 (F4): the verified mark survives an UNRELATED edit-save, re-verified fresh");
      var unverifiedAfterSave = Array.prototype.filter.call(scLineAfterSave.querySelectorAll(".pp-gen-scr-item"), function (s) {
        return s.textContent === "3Jn 4:12";
      })[0];
      ok(!!unverifiedAfterSave && unverifiedAfterSave.nextElementSibling &&
         unverifiedAfterSave.nextElementSibling.classList.contains("pp-gen-scr-unverified"),
         "PP 86akby820 (F4): the unverified mark ALSO survives an edit-save — this is the exact " +
         "harm the ticket cites (a pastor reading from a saved/reloaded draft), not only the " +
         "live-generation response");
      ok(!!gSAfterSave.querySelector(".pp-gen-scripture-note"),
         "PP 86akby820 (F4): the verification-scope note is still present after an edit-save");

      // NEGATIVE CONTROL for the NEXT block: this "scripture_verification" draft carries no
      // `scripture_verification_incomplete` caveat, so its own scripture-note text must never
      // contain the "more than could be checked" wording — proves the two notes render from
      // DIFFERENT caveat kinds, not from the same generic "any scripture note" branch.
      ok(!/more scripture references than could be checked/.test(gSAfterSave.textContent),
         "PP 86akgqdwc (negative control): a draft with no scripture_verification_incomplete " +
         "caveat must not show its note");

      // --- 86akgqdwc (Sana F2 on PR #48): scripture verification budget exhaustion --------------
      window.__ppGen = "scripture_incomplete"; await ppGenerateAndConfirm(80);
      var gSIncomplete = el("pp-gen-result");
      var incompleteNote = Array.prototype.filter.call(
        gSIncomplete.querySelectorAll(".pp-gen-scripture-note"),
        function (p) { return /more scripture references than could be checked/.test(p.textContent); }
      )[0];
      ok(!!incompleteNote && getComputedStyle(incompleteNote).display !== "none" &&
         incompleteNote.getAttribute("role") === "note",
         "PP 86akgqdwc: the scripture-verification-incomplete note renders, computed-visible, role=note");
      // POSITIVE CONTROL: the section this budget exhaustion would most affect (last in scan
      // order in the real backend) still renders normally alongside the note — the note is an
      // ADDITION, not a replacement for the section's own content.
      ok(/Podcast show notes/.test(gSIncomplete.textContent) && /Isaiah 55:1/.test(gSIncomplete.textContent),
         "PP 86akgqdwc (positive control): the podcast section's own content still renders " +
         "alongside the incomplete-verification note");

      // --- 86akgqdw0 (FR-124): timestamp-linked note items — DATA PARITY on this surface -------
      // No transcript-log virtualizer exists on Settings to jump within (see settings.js's own
      // header comment), so this proves only the half that DOES apply here: the timestamp
      // renders as a plain, non-interactive label (never falsely clickable), "Copy chapter
      // markers" produces a correct export, and a malformed (non-numeric) offset renders NO
      // label at all rather than a broken one — this workstream's own "port a new field to BOTH
      // consoles" lesson (PR #48 Cody MAJOR), applied going forward rather than repeated.
      window.__ppGen = "timestamps"; await ppGenerateAndConfirm(80);
      var gTs = el("pp-gen-result");
      var tsLabels = gTs.querySelectorAll(".pp-item-ts");
      ok(tsLabels.length === 1 && tsLabels[0].textContent === "00:00:04",
         "PP 86akgqdw0: a chapter marker with a valid, real offset shows its HH:MM:SS label — " +
         "exactly one, not one per item, since the malformed one below must render none");
      ok(getComputedStyle(tsLabels[0]).cursor !== "pointer",
         "PP 86akgqdw0: the label is genuinely NON-interactive on this surface (computed style, " +
         "not just the absence of a click handler) — there is nowhere for it to jump to here");
      ok(gTs.textContent.indexOf("Bogus type") !== -1,
         "PP 86akgqdw0 (adversarial fixture): the item with a non-numeric offset still renders " +
         "its OWN text (never dropped) — only its timestamp label is missing, per the " +
         "`tsLabels.length === 1` check above (a label for it would have made that 2)");
      var copyBtn = el("pp-copy-chapters-btn") || gTs.querySelector(".pp-copy-chapters-btn");
      ok(!!copyBtn, "PP 86akgqdw0: the 'Copy chapter markers' action is offered whenever at " +
         "least one marker resolved a timestamp");
      ok(copyBtn.textContent === "Copy chapter markers",
         "PP 86akgqdw0: the copy button's default label, before any click");

      window.__ppGen = "ok"; // restore for any later reads

      // === 86akgqdv0: sermon-note draft persistence + editing (FR-123 "editable" half) ========
      // Verification expectation from the ticket: assert COMPUTED STYLE for the edit UI, never
      // just the `.hidden` attribute — this codebase's known WKWebView trap (a class `display`
      // rule can defeat `hidden`; the Blink engine driving this harness would not catch that on
      // its own, see CLAUDE.md / the operator-webview-wkwebview-layout-traps note).
      window.__ppGen = "ok"; await ppGenerateAndConfirm(80); // a known-fresh "ok" draft to start from
      var snView = el("pp-gen-result");

      // SN-1: a successful (persisted) generate offers an Edit affordance, visibly.
      var snEditBtn = el("pp-gen-edit");
      ok(!!snEditBtn && getComputedStyle(snEditBtn).display !== "none" && snEditBtn.textContent === "Edit",
         "PP SN-1: a persisted draft (transcript_id present) renders a visible Edit button (computed display)");
      ok(ppLast("generate_sermon_notes") && ppLast("generate_sermon_notes").args, // sanity: a call really happened
         "PP SN-1 (sanity): generate_sermon_notes was actually called for this fixture");

      // SN-2: the persisted-draft WIRE CONTRACT — what a fresh app process would fetch on restart
      // via load_sermon_note_draft — carries the label/disclosure/title untouched. This is called
      // directly (bypassing settings.js's own in-memory `currentDraft`, which this one continuous
      // page session never naturally clears) because it is the IPC boundary, not the client cache,
      // that "the draft is still there after a restart" actually rests on — the deeper SQLite
      // restart-survival property itself is proven in selahcue-data's own
      // `a_draft_survives_a_fresh_database_open_of_the_same_file` test.
      var snLoaded = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(!!snLoaded && snLoaded.ok === true && snLoaded.transcript_id === 42,
         "PP SN-2: load_sermon_note_draft returns the persisted draft, keyed to its transcript id");
      ok(snLoaded.draft && snLoaded.draft.title === "Grace That Feeds",
         "PP SN-2: the restored draft's title matches what was generated");
      ok(snLoaded.ai_generated === true && /invent/i.test(snLoaded.disclosure || ""),
         "PP SN-2 (FR-123/128): the label and disclosure travel with the draft through a restart, not just an edit");

      // SN-3: opening Edit shows the edit form (computed style) and HIDES the read-only view's own
      // Edit button, while the AI label + disclosure remain visibly rendered THROUGHOUT — editing
      // must never even transiently drop the FR-123/FR-128 warning.
      snEditBtn.click();
      var snForm = document.querySelector(".pp-gen-edit-form");
      ok(!!snForm && getComputedStyle(snForm).display !== "none",
         "PP SN-3: clicking Edit reveals the edit form (computed display, not just an absent .hidden attribute)");
      ok(!document.getElementById("pp-gen-edit"),
         "PP SN-3: the read-only Edit button is gone while editing (view and edit are not both on screen)");
      var snEditAiLabel = snView.querySelector(".pp-gen-ai-label");
      ok(!!snEditAiLabel && getComputedStyle(snEditAiLabel).display !== "none",
         "PP SN-3 (FR-123): the AI-generated label is STILL visibly rendered while the edit form is open");
      var snEditDisc = snView.querySelector(".pp-gen-disclosure");
      ok(!!snEditDisc && getComputedStyle(snEditDisc).display !== "none",
         "PP SN-3 (FR-128): the fabrication disclosure is STILL visibly rendered while the edit form is open");

      // SN-4: the form is pre-filled from the CURRENT draft — title, summary, a flat section's
      // item, an outline point's text, and its sub-point — proving both shapes (FR-122) round-trip
      // into editable fields, not just one of them.
      var snTitleInput = document.getElementById("pp-edit-title");
      var snSummaryInput = document.getElementById("pp-edit-summary");
      ok(!!snTitleInput && snTitleInput.value === "Grace That Feeds",
         "PP SN-4: the title field is pre-filled from the current draft");
      ok(!!snSummaryInput && snSummaryInput.value === "A sermon on provision and grace.",
         "PP SN-4: the summary field is pre-filled from the current draft");
      var snItemInput = snForm.querySelector('.pp-edit-item-text[data-si="1"][data-ii="0"]');
      ok(!!snItemInput && snItemInput.value === "Thank God for provision",
         "PP SN-4: a flat section's item is pre-filled in its own editable field");
      var snPointInput = snForm.querySelector('.pp-edit-point-text[data-si="0"][data-pi="0"]');
      ok(!!snPointInput && snPointInput.value === "The crowd came back for the wrong reason",
         "PP SN-4: an outline section's point text is pre-filled in its own editable field");
      var snSubInput = snForm.querySelector('.pp-edit-subpoint-text[data-si="0"][data-pi="0"][data-spi="0"]');
      ok(!!snSubInput && snSubInput.value === "They ate of the loaves",
         "PP SN-4: a sub-point is pre-filled in its own editable field, nested under its parent point");

      // SN-5: editing the title and a point's wording, then Save — persists via
      // update_sermon_note_draft with the edited values (and the UNCHANGED sub-point, proving a
      // partial edit does not clobber fields the operator did not touch), returns to view mode, and
      // the label/disclosure are STILL present afterward (re-read from the backend's own response,
      // never assumed).
      var snBeforeSave = ppCall("update_sermon_note_draft").length;
      snTitleInput.value = "Grace That Feeds (edited)";
      snPointInput.value = "The crowd came back hungry again";
      el("pp-gen-save").click();
      await sleep(60);
      ok(ppCall("update_sermon_note_draft").length === snBeforeSave + 1,
         "PP SN-5: Save calls update_sermon_note_draft exactly once");
      var snSaveArgs = ppLast("update_sermon_note_draft").args;
      ok(snSaveArgs.transcriptId === 42 && snSaveArgs.title === "Grace That Feeds (edited)",
         "PP SN-5: the edited title is sent, keyed to the SAME transcript id the draft was loaded against");
      ok(snSaveArgs.sections[0].points[0].text === "The crowd came back hungry again",
         "PP SN-5: the edited point's wording is sent");
      ok(snSaveArgs.sections[0].points[0].sub_points[0] === "They ate of the loaves" &&
         snSaveArgs.sections[0].points[0].sub_points[1] === "A full church is not a fed one",
         "PP SN-5: sub-points the operator did NOT touch are sent UNCHANGED, not dropped");
      ok(!("ai_generated" in snSaveArgs) && !("disclosure" in snSaveArgs) && !("provider" in snSaveArgs),
         "PP SN-5: the edit request itself carries no ai_generated/disclosure/provider field — the label cannot be touched from the client because there is nowhere on the wire to put a change to it");
      var snAfterSave = el("pp-gen-result");
      ok(!document.querySelector(".pp-gen-edit-form"),
         "PP SN-5: after Save the form is gone (back to view mode)");
      ok(/Grace That Feeds \(edited\)/.test(snAfterSave.textContent),
         "PP SN-5: the view now shows the SAVED title, not the pre-edit one");
      var snPostSaveLabel = snAfterSave.querySelector(".pp-gen-ai-label");
      var snPostSaveDisc = snAfterSave.querySelector(".pp-gen-disclosure");
      ok(!!snPostSaveLabel && getComputedStyle(snPostSaveLabel).display !== "none",
         "PP SN-5 (FR-123): the AI-generated label is still visibly rendered AFTER a save, re-read from the backend response");
      ok(!!snPostSaveDisc && getComputedStyle(snPostSaveDisc).display !== "none",
         "PP SN-5 (FR-128): the fabrication disclosure is still visibly rendered AFTER a save");

      // SN-6: Cancel discards in-progress edits and restores the view showing the PRIOR (saved)
      // content, never the abandoned draft edit.
      el("pp-gen-edit").click();
      document.getElementById("pp-edit-title").value = "An edit that will be abandoned";
      el("pp-gen-edit-cancel").click();
      ok(!document.querySelector(".pp-gen-edit-form"), "PP SN-6: Cancel closes the edit form");
      ok(/Grace That Feeds \(edited\)/.test(el("pp-gen-result").textContent) &&
         !/abandoned/.test(el("pp-gen-result").textContent),
         "PP SN-6: Cancel discards the in-progress edit — the view still shows the last SAVED title, not the abandoned one");

      // SN-9 (86akgqdv0, Quinn's QA review of PR #33): the CLIENT-SIDE restart-render path —
      // loadPersistedDraft() actually making a restored draft REAPPEAR ON SCREEN after a real
      // app restart, with no click required — was previously provable only by (a) a DB-level
      // test, (b) a wire-contract test (SN-2 above), and (c) a manual code trace, since this
      // harness is one continuous page session that never naturally clears settings.js's own
      // in-memory `currentDraft`. `window.__resetSermonNoteDraftForTest()` (the test-only hook
      // settings.js exposes for exactly this) simulates that clean-slate restart; clearing the
      // DOM by hand first proves what follows is really painted BY the restore, not leftover
      // markup from the fixture above. Deliberately placed HERE, right after SN-6 and before
      // SN-7/SN-8 — SN-7's rejected save and SN-8's own generate calls each persist a DIFFERENT
      // draft to the mock's single-slot store, so "the last SAVED title" this check names is
      // only still `Grace That Feeds (edited)` (SN-5's save) at THIS point in the sequence; run
      // any later, it asserts a title that generation has since overwritten, not a restart bug.
      el("pp-gen-result").textContent = "";
      el("pp-gen-result").removeAttribute("role");
      window.__resetSermonNoteDraftForTest();
      ok(el("pp-gen-result").textContent === "" && !el("pp-gen-edit"),
         "PP SN-9 (setup): the page genuinely shows nothing before the simulated restart");
      window.settingsActivate();
      await sleep(60);
      var snRestored = el("pp-gen-result");
      ok(/Grace That Feeds \(edited\)/.test(snRestored.textContent),
         "PP SN-9: after a simulated restart, settingsActivate() alone (no click) restores the \
last SAVED draft's title, via the real loadPersistedDraft() render path");
      var snRestoredEditBtn = el("pp-gen-edit");
      ok(!!snRestoredEditBtn && getComputedStyle(snRestoredEditBtn).display !== "none",
         "PP SN-9: the restored draft offers Edit again (computed display), same as the first \
persisted view in SN-1");
      var snRestoredLabel = snRestored.querySelector(".pp-gen-ai-label");
      var snRestoredDisc = snRestored.querySelector(".pp-gen-disclosure");
      ok(!!snRestoredLabel && getComputedStyle(snRestoredLabel).display !== "none",
         "PP SN-9 (FR-123): the AI-generated label renders on the restored draft too, not just \
right after a generate/save");
      ok(!!snRestoredDisc && getComputedStyle(snRestoredDisc).display !== "none",
         "PP SN-9 (FR-128): the fabrication disclosure renders on the restored draft too");

      // SN-7: a backend refusal (oversized field) on Save surfaces an error (role=alert), not a
      // silent no-op — the operator must be told the edit did not take.
      el("pp-gen-edit").click();
      window.__snRejectTooLarge = true;
      el("pp-gen-save").click();
      await sleep(60);
      var snTooLarge = el("pp-gen-result");
      ok(snTooLarge.getAttribute("role") === "alert" && /exceeds 300 characters/.test(snTooLarge.textContent),
         "PP SN-7: an oversized-field refusal from the backend surfaces as an alert naming the reason, not a silent failure");

      // SN-8: a degraded (offline-fallback) draft is STILL persisted and editable — FR-123
      // "editable" is not conditional on ai_generated — but its Edit view carries no AI label or
      // disclosure to preserve, since it never had one (86akgqdv0 does not invent a false claim on
      // the one draft type that is honestly not AI-generated).
      window.__ppGen = "degraded"; await ppGenerateAndConfirm(80);
      var snDegView = el("pp-gen-result");
      var snDegEditBtn = el("pp-gen-edit");
      ok(!!snDegEditBtn && getComputedStyle(snDegEditBtn).display !== "none",
         "PP SN-8: a degraded (offline-fallback) draft is ALSO persisted and offers Edit — FR-123 editability is not gated on ai_generated");
      snDegEditBtn.click();
      ok(!!document.querySelector(".pp-gen-edit-form") && !el("pp-gen-result").querySelector(".pp-gen-ai-label"),
         "PP SN-8: a degraded draft's edit view carries no AI-generated label to preserve — it never had one");
      el("pp-gen-edit-cancel").click();
      window.__ppGen = "ok"; await ppGenerateAndConfirm(80); // restore a clean "ok" fixture for later reads

      // === FR-129 (86akgqdx8): regenerate produces a new draft while RETAINING the prior
      // version until the operator explicitly confirms/discards it (single prior version,
      // explicit-confirm-before-replace — see the Goal Contract for the full decision). The
      // mock's `regenerate_pending`/`regenerate_pending_degraded` `window.__ppGen` values are
      // DELIBERATELY ISOLATED from every other "g" branch (see that branch's own comment) —
      // this block always sets up its OWN known-fresh "ok" fixture first, never relying on
      // whatever a prior block left in `SN.draft`. ==========================================
      window.__ppGen = "ok"; await ppGenerateAndConfirm(80); // known-fresh accepted draft
      ok(/Grace That Feeds/.test(el("pp-gen-result").textContent) && !/regenerated/.test(el("pp-gen-result").textContent),
         "PP REGEN-0 (setup): a known accepted draft exists before any regenerate attempt");

      // REGEN-1: pressing Generate again on a transcript that already has a saved draft does
      // NOT replace it — it STAGES the new draft instead, and the console shows both the new
      // content and an explicit accept/discard choice.
      window.__ppGen = "regenerate_pending"; await ppGenerateAndConfirm(80);
      var regenResult = el("pp-gen-result");
      ok(/Grace That Feeds \(regenerated\)/.test(regenResult.textContent),
         "PP REGEN-1: the freshly regenerated draft's content is shown immediately");
      var regenBanner = regenResult.querySelector(".pp-gen-regen-banner");
      ok(!!regenBanner && getComputedStyle(regenBanner).display !== "none",
         "PP REGEN-1: a pending-confirmation banner is rendered (computed display), not just present in markup");
      ok(regenBanner.getAttribute("role") === "status",
         "PP REGEN-1: the banner is a polite status, not an alert — nothing has gone wrong");
      ok(/Grace That Feeds/.test(regenBanner.textContent) && !/\(regenerated\)/.test(regenBanner.textContent),
         "PP REGEN-1: the banner names the STILL-SAVED prior draft's own title (the one about to " +
         "possibly be replaced), not the new one — proving the operator can see it was not silently destroyed");
      ok(!el("pp-gen-edit"),
         "PP REGEN-1: Edit is hidden while a regeneration is pending — the content on screen is " +
         "unconfirmed, and Edit would otherwise write to the accepted row while showing different text");
      var regenConfirmBtn = el("pp-gen-regen-confirm");
      var regenDiscardBtn = el("pp-gen-regen-discard");
      ok(!!regenConfirmBtn && getComputedStyle(regenConfirmBtn).display !== "none" &&
         !!regenDiscardBtn && getComputedStyle(regenDiscardBtn).display !== "none",
         "PP REGEN-1: both Confirm ('Use this draft') and Discard ('Keep my current notes') are visibly offered");

      // Direct proof the prior draft is RETRIEVABLE, unmodified, right now — not merely that
      // the banner names it. `load_sermon_note_draft` is the same wire contract SN-2 above
      // already uses for "what would a restart see right now".
      var regenPriorStillSaved = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(!!regenPriorStillSaved && regenPriorStillSaved.ok === true &&
         regenPriorStillSaved.draft.title === "Grace That Feeds",
         "PP REGEN-1 (AC): the prior draft is retrievable and UNCHANGED immediately after a " +
         "regenerate is requested, before the operator confirms replacement");

      // REGEN-2: Discard leaves the saved draft exactly as it was — no change at all.
      var regenDiscardCallsBefore = ppCall("discard_sermon_note_regeneration").length;
      regenDiscardBtn.click();
      await sleep(60);
      ok(ppCall("discard_sermon_note_regeneration").length === regenDiscardCallsBefore + 1,
         "PP REGEN-2: Discard calls discard_sermon_note_regeneration");
      var afterDiscard = el("pp-gen-result");
      ok(/Grace That Feeds/.test(afterDiscard.textContent) && !/regenerated/.test(afterDiscard.textContent),
         "PP REGEN-2: after Discard, the view shows the ORIGINAL saved draft, not the discarded one");
      ok(!afterDiscard.querySelector(".pp-gen-regen-banner"),
         "PP REGEN-2: the pending-confirmation banner is gone after Discard");
      ok(!!el("pp-gen-edit") && getComputedStyle(el("pp-gen-edit")).display !== "none",
         "PP REGEN-2: Edit is offered again once nothing is pending");
      var regenAfterDiscardLoaded = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(regenAfterDiscardLoaded.draft.title === "Grace That Feeds",
         "PP REGEN-2: the persisted draft on the host is STILL the original — Discard changed nothing there");

      // REGEN-3: Confirm REPLACES the saved draft with the new one — single prior version, so
      // the version it replaces is now gone (not kept as further history).
      window.__ppGen = "regenerate_pending"; await ppGenerateAndConfirm(80);
      var regenConfirmCallsBefore = ppCall("confirm_sermon_note_regeneration").length;
      el("pp-gen-regen-confirm").click();
      await sleep(60);
      ok(ppCall("confirm_sermon_note_regeneration").length === regenConfirmCallsBefore + 1,
         "PP REGEN-3: 'Use this draft' calls confirm_sermon_note_regeneration");
      var afterConfirm = el("pp-gen-result");
      ok(/Grace That Feeds \(regenerated\)/.test(afterConfirm.textContent),
         "PP REGEN-3: after Confirm, the view shows the NEW draft as the current one");
      ok(!afterConfirm.querySelector(".pp-gen-regen-banner"),
         "PP REGEN-3: the banner is gone once the regeneration is confirmed — nothing left pending");
      ok(!!el("pp-gen-edit"),
         "PP REGEN-3: Edit is offered again on the newly confirmed draft");
      var regenAfterConfirmLoaded = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(regenAfterConfirmLoaded.draft.title === "Grace That Feeds (regenerated)",
         "PP REGEN-3: the CONFIRMED content is what the host now actually persists, re-read fresh " +
         "over the same wire contract a restart would use — not merely a client-side swap");

      // REGEN-4: consent-off still blocks Regenerate's network call EXACTLY like the original
      // Generate flow (regression test, not an assumption) — regenerate reuses the exact same
      // consent-gated generate_sermon_notes command, so this is the same code path SN-*/C-005
      // already prove for a first-time generate, re-asserted here against a transcript that
      // ALREADY has a saved draft.
      window.__pp.cloud_notes_consent = false;
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);
      var regenGenCallsBefore = ppCall("generate_sermon_notes").length;
      window.__ppGen = "regenerate_pending";
      await ppGenerateAndConfirm(70);
      var regenConsentOffResult = el("pp-gen-result");
      ok(regenConsentOffResult.getAttribute("role") === "alert" &&
         /Turn on cloud processing/.test(regenConsentOffResult.textContent),
         "PP REGEN-4: with consent OFF, pressing Generate again on a transcript that already " +
         "has a saved draft is STILL gated exactly like a first-time Generate (consent_required)");
      ok(ppCall("generate_sermon_notes").length === regenGenCallsBefore + 1,
         "PP REGEN-4 (sanity): the call reached the backend and was gated there — the client did " +
         "not merely refuse locally");
      ok(!/regenerated/.test(regenConsentOffResult.textContent),
         "PP REGEN-4: no draft content of any kind leaked into view — nothing was generated");
      var regenAfterConsentOffLoaded = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(regenAfterConsentOffLoaded.draft.title === "Grace That Feeds (regenerated)",
         "PP REGEN-4: the saved draft from REGEN-3 is completely unaffected by the refused attempt");
      window.__pp.cloud_notes_consent = true;
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);

      // REGEN-5: a transport failure during regenerate must not lose the prior draft — same
      // fallback ladder as a first-time Generate (PP C-005's own "transport" case), re-asserted
      // here against a transcript that already has a saved draft. `window.__ppGen = "transport"`
      // makes the mocked invoke() REJECT — the exact same simulated failure PP C-005 uses — so
      // `generate_sermon_notes` never even returns a value to stage from, and the accepted
      // draft cannot have been touched by construction (the real backend's own guarantee: see
      // `an_unstaged_draft_has_no_pending_regeneration_and_is_unaffected_by_a_failed_generation_attempt`
      // in selahcue-data's own test suite for the persistence-layer half of this same proof).
      window.__ppGen = "transport"; await ppGenerateAndConfirm(70);
      var regenTransportResult = el("pp-gen-result");
      ok(regenTransportResult.getAttribute("role") === "alert",
         "PP REGEN-5: a transport failure during regenerate surfaces as an alert, same as a first-time Generate");
      var regenAfterTransportLoaded = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(regenAfterTransportLoaded.draft.title === "Grace That Feeds (regenerated)",
         "PP REGEN-5 (AC): a transport failure during regenerate never loses the prior (pre-regenerate) draft");

      // REGEN-6: a DEGRADED (local-fallback) regenerate still stages (never silently refused
      // outright) and still carries ai_generated:false + a degraded notice, matching the
      // original flow's degraded handling — but "once AI-generated, always AI-generated" means
      // it can be VIEWED and DISCARDED, never CONFIRMED over an already AI-generated draft.
      window.__ppGen = "regenerate_pending_degraded"; await ppGenerateAndConfirm(80);
      var regenDegResult = el("pp-gen-result");
      ok(/Offline outline \(regenerated\)/.test(regenDegResult.textContent),
         "PP REGEN-6: a degraded regenerate still stages and shows its content, exactly like the original flow's degraded handling");
      ok(!regenDegResult.querySelector(".pp-gen-ai-label"),
         "PP REGEN-6: the degraded pending draft carries no AI-generated label, same as a first-time degraded draft");
      var regenDegNotice = regenDegResult.querySelector(".pp-gen-degraded");
      ok(!!regenDegNotice && /could not be reached/i.test(regenDegNotice.textContent),
         "PP REGEN-6: the degraded fallback notice renders on a pending regeneration too");
      var regenDegConfirmCallsBefore = ppCall("confirm_sermon_note_regeneration").length;
      el("pp-gen-regen-confirm").click();
      await sleep(60);
      ok(ppCall("confirm_sermon_note_regeneration").length === regenDegConfirmCallsBefore + 1,
         "PP REGEN-6 (sanity): the confirm attempt actually reached the backend");
      // The refusal is kept INLINE on the still-visible banner — never a whole-region wipe,
      // which would strand the operator with no reachable Discard button on this transcript
      // (settings.js can recover via settingsActivate()'s currentDraft re-render, but the
      // Transcripts workspace genuinely cannot — transcript_get never re-surfaces a pending
      // regeneration; this inline behaviour is shared code, so proving it here proves it there).
      var regenDegResultAfterRefusal = el("pp-gen-result");
      ok(/Offline outline \(regenerated\)/.test(regenDegResultAfterRefusal.textContent),
         "PP REGEN-6: the pending draft's content is STILL shown after the refused confirm — nothing was wiped");
      var regenDegInlineError = regenDegResultAfterRefusal.querySelector(".pp-gen-regen-error");
      ok(!!regenDegInlineError && getComputedStyle(regenDegInlineError).display !== "none" &&
         regenDegInlineError.getAttribute("role") === "alert" &&
         /AI-generated label/.test(regenDegInlineError.textContent),
         "PP REGEN-6: the refusal reason renders INLINE on the banner (role=alert), not as a " +
         "separate message that replaces the draft view");
      ok(!!el("pp-gen-regen-discard") && !!el("pp-gen-regen-confirm"),
         "PP REGEN-6: Confirm/Discard remain reachable after a refused confirm — no dead end");
      var regenDegAfterRefusedLoaded = await window.__TAURI__.core.invoke("load_sermon_note_draft");
      ok(regenDegAfterRefusedLoaded.draft.title === "Grace That Feeds (regenerated)",
         "PP REGEN-6: the accepted draft is untouched by the refused confirm attempt");
      el("pp-gen-regen-discard").click();
      await sleep(60);
      ok(/Grace That Feeds \(regenerated\)/.test(el("pp-gen-result").textContent),
         "PP REGEN-6: discarding the refused degraded regeneration cleanly restores the accepted draft");
      ok(!el("pp-gen-result").querySelector(".pp-gen-regen-error"),
         "PP REGEN-6: the inline refusal message is gone once the regeneration is resolved");

      // === (F-5 / PERF-3) The review-and-confirm step is real, and an empty/below-minimum
      // transcript is refused before any network call — 86akby7d8 ============================
      // The footnote under Generate promises "You'll see exactly what's sent and confirm before
      // anything is generated." Before this fix nothing enforced that: onGenerate sent on the
      // same click (Sana F-5, escalated to release-blocking by Quinn — both read the shipped
      // onGenerate themselves rather than take the gap on description). These checks fail if
      // that regresses in EITHER direction: Generate reaching the network without an explicit
      // Confirm, or Confirm sending something other than what the review step displayed.

      // (a) PERF-3 (Vera): an empty transcript is refused before any network call, not sent —
      // the guard that stops a mis-wire (defect 1) silently billing for a fabricated draft again.
      // Driven through the REAL bridge (V.transcript + render()), not a direct global override —
      // an empty FINALISED-segment list is what the host actually reports before any speech.
      V.transcript = [];
      render(Object.assign({}, baseView, { transcript: [] }));
      ok(window.scCompletedTranscript === "", "PP defect 1: an empty transcript array bridges to \"\", not undefined or a stale value");
      var genBeforeEmpty = ppCall("generate_sermon_notes").length;
      el("pp-generate").click();
      await sleep(40);
      ok(ppCall("generate_sermon_notes").length === genBeforeEmpty,
         "PP PERF-3: an empty transcript never reaches generate_sermon_notes — refused before the network call");
      ok(el("pp-gen-preview").hidden === true,
         "PP PERF-3: an empty transcript does not open the review step either — there is nothing to review");
      var genEmptyRes = el("pp-gen-result");
      ok(!!genEmptyRes && !genEmptyRes.hidden && /No transcript yet/.test(genEmptyRes.textContent),
         "PP PERF-3: an empty transcript surfaces its own honest 'No transcript yet' state");

      // (b) PERF-3: a below-floor, non-empty transcript (noise, not silence) is refused the same
      // way, and distinguishably — the empty and near-empty cases say different true things.
      V.transcript = [{ id: 701, text: "uh", start_ms: 0, end_ms: 300 }];
      render(Object.assign({}, baseView, { transcript: V.transcript }));
      ok(window.scCompletedTranscript === "uh", "PP defect 1: a single short segment bridges byte for byte");
      el("pp-generate").click();
      await sleep(40);
      ok(ppCall("generate_sermon_notes").length === genBeforeEmpty,
         "PP PERF-3: a below-minimum transcript never reaches generate_sermon_notes either");
      var genShortRes = el("pp-gen-result");
      ok(!!genShortRes && /too short/i.test(genShortRes.textContent) && !/No transcript yet/.test(genShortRes.textContent),
         "PP PERF-3: a below-minimum (but non-empty) transcript surfaces 'too short', distinct from the empty case");

      // (c) F-5: a real transcript opens a review step showing the EXACT string about to be sent,
      // and calling generate_sermon_notes has still not happened.
      V.transcript = PP_TRANSCRIPT_SEGMENTS;
      render(Object.assign({}, baseView, { transcript: PP_TRANSCRIPT_SEGMENTS }));
      ok(window.scCompletedTranscript === PP_TRANSCRIPT_FIXTURE, "PP defect 1: the fixture transcript is back via the real bridge before the review-step checks");
      var genBeforeReview = ppCall("generate_sermon_notes").length;
      el("pp-generate").click();
      await sleep(40);
      var previewBox = el("pp-gen-preview");
      ok(!!previewBox && previewBox.hidden === false, "PP F-5: Generate opens the review step instead of sending");
      // hidden-attr-vs-css-display trap (this webview): assert COMPUTED display, not just the
      // cleared [hidden] attribute — a class display rule has defeated `hidden` here before.
      ok(getComputedStyle(previewBox).display !== "none",
         "PP F-5 (computed display): the review step is actually visible on screen, not defeated by a CSS display rule");
      var previewText = previewBox.querySelector(".pp-gen-preview-text");
      ok(!!previewText && previewText.textContent === PP_TRANSCRIPT_FIXTURE,
         "PP F-5: the review step shows the EXACT text that will be sent, byte for byte");
      ok(new RegExp(String(PP_TRANSCRIPT_FIXTURE.length) + " characters").test(previewBox.textContent),
         "PP F-5: the review step states how much text is about to be sent");
      // L-2 (Quinn, Cody, Vera — independently): the preview is honest about the byte count but
      // said nothing about SCOPE — window.scCompletedTranscript is the operator's bounded recent
      // tail (app.js's syncTranscript), not a full-service store (that's FR-130, not built), so a
      // 45-minute sermon previews as a confident, complete-looking draft built from its last few
      // minutes. Pin the disclosure copy exactly — unpinned copy is how F-5's promise rotted once.
      var previewScope = previewBox.querySelector(".pp-gen-preview-scope");
      ok(!!previewScope && previewScope.textContent ===
         "This is drawn from the most recently transcribed speech, not the whole service — for a " +
         "long sermon, that may be just the last few minutes.",
         "PP F-5 L-2: the review step discloses that this may be a recent window, not the whole service (exact copy pinned)");
      ok(document.activeElement && document.activeElement.id === "pp-gen-preview-title",
         "PP F-5 a11y: opening the review step moves focus into it (a screen reader hears 'Review before sending', not silence)");
      ok(ppCall("generate_sermon_notes").length === genBeforeReview,
         "PP F-5: opening the review step alone still has not called generate_sermon_notes");
      ok(el("pp-generate").hidden === true,
         "PP F-5: the Generate button is hidden while its own review step is open (no double-fire path)");

      // (d) F-5: Cancel sends nothing and returns the panel to idle.
      el("pp-gen-preview-cancel").click();
      await sleep(30);
      ok(ppCall("generate_sermon_notes").length === genBeforeReview,
         "PP F-5: Cancel never calls generate_sermon_notes");
      ok(el("pp-gen-preview").hidden === true, "PP F-5: Cancel closes the review step");
      // M-1 (Cody): the DOM `hidden` property alone is not proof the panel left the layout — this
      // webview's known trap is an author `display` rule outranking the UA `[hidden]{display:none}`
      // rule, which is exactly the direction the check above cannot see. Assert COMPUTED display,
      // the same discipline the OPEN-direction check a few lines up already applies.
      ok(getComputedStyle(el("pp-gen-preview")).display === "none",
         "PP F-5 M-1 (computed display): Cancel actually removes the panel from layout, not just the [hidden] attribute");
      ok(el("pp-generate").hidden === false, "PP F-5: Cancel restores the Generate button");
      ok(document.activeElement === el("pp-generate"),
         "PP F-5 a11y: Cancel returns keyboard focus to Generate, not to whatever the browser defaults to");

      // (e) F-5: Confirm sends the SAME string the review step displayed, and only once pressed.
      el("pp-generate").click();
      await sleep(40);
      // L-1 (Sana and Quinn, independently): the check below used to compare the sent transcript
      // to PP_TRANSCRIPT_FIXTURE without ever moving the transcript between preview-open and
      // Confirm — so a captured value and a fresh re-read of window.scCompletedTranscript were
      // trivially identical and the check could not fail under the mutation it claims to guard
      // against (confirmGenerate re-reading the global instead of using the value it was handed).
      // Advance the transcript through the REAL render() path while the preview sits open — exactly
      // what the live 1s poll would do during a real review — so the two are actually different.
      var PP_TRANSCRIPT_SEGMENTS_ADVANCED = PP_TRANSCRIPT_SEGMENTS.concat([
        { id: 604, text: "And now the congregation begins to respond.", start_ms: 9000, end_ms: 12000 },
      ]);
      var PP_TRANSCRIPT_FIXTURE_ADVANCED =
        PP_TRANSCRIPT_FIXTURE + "\nAnd now the congregation begins to respond.";
      V.transcript = PP_TRANSCRIPT_SEGMENTS_ADVANCED;
      render(Object.assign({}, baseView, { transcript: PP_TRANSCRIPT_SEGMENTS_ADVANCED }));
      // Positive control: prove the transcript genuinely advanced underneath the open preview
      // before trusting the control below to have caught anything.
      ok(window.scCompletedTranscript === PP_TRANSCRIPT_FIXTURE_ADVANCED,
         "PP F-5 L-1 (premise): the bridge really did advance past what the open preview is showing, while the preview stayed open");
      // PP-GEN: .pp-gen-preview-confirm:hover — same defect class as .pm-btn-primary:hover/CON-007.
      // Checked HERE, right before Confirm is clicked, while the review step is genuinely open —
      // the button is rebuilt fresh on each Generate cycle, so a later check point cannot rely on
      // finding it still in the DOM.
      (function() {
        var confirmEl = el("pp-gen-preview-confirm");
        var restBg = _rgba(getComputedStyle(confirmEl).backgroundColor);
        var restR = _cr([255,255,255,1], restBg);
        ok(restR >= 4.5,
           "PP-GEN (premise): .pp-gen-preview-confirm REST already clears AA-NORMAL (flat --sc-primary, " + _f(restR) + ":1) — only :hover regresses");
        var hoverRule = __cssRule(".pp-gen-preview-confirm:hover");
        ok(!!hoverRule, "PP-GEN (premise): the .pp-gen-preview-confirm:hover rule is present in the shipped app.css");
        var hb = __cssBg(hoverRule);
        ok(!!hb, "PP-GEN (premise): the .pp-gen-preview-confirm:hover rule declares a background, so there is a value to measure");
        if (hb) {
          var hoverBg = _resolve(hb.trim());
          var hoverR = _cr([255,255,255,1], hoverBg);
          ok(hoverR >= 4.5, "PP-GEN: the HOVERED .pp-gen-preview-confirm keeps its white label at AA-NORMAL (" + _f(hoverR) + ":1)");
          ok(_lum(hoverBg) < _lum(restBg),
             "PP-GEN: .pp-gen-preview-confirm hover DARKENS the fill instead of lightening it, matching .pm-btn-primary:hover");
        }
      })();
      // PSC-005: .pp-gen-preview-confirm[disabled] / [aria-busy="true"] — Cody's PR #60 re-review
      // found the exact same trap reproduced here: this class is shared by the transient Confirm
      // button above (never disabled) and the edit-draft Save button (id pp-gen-save/tr-gen-save
      // in settings.js/transcripts.js, which sets disabled + aria-busy="true" while saving), and
      // :hover/[disabled] are equal specificity with nothing declared here to make the disabled
      // rule win. Same two-check technique as .pp-generate[disabled] and .ps-start:disabled above:
      // the disabled rule must declare its own background, AND that background must be the exact
      // REST fill — not just any declared value (Cody/Vera's PR #62 finding on PSC-005 itself).
      var wPpGenConfirmDisabledRule = __cssRule('.pp-gen-preview-confirm[disabled], .pp-gen-preview-confirm[aria-busy="true"]');
      ok(!!wPpGenConfirmDisabledRule, "PP-GEN (premise): the .pp-gen-preview-confirm[disabled] rule is present in the shipped app.css");
      var wPpGenConfirmDisabledBg = __cssBg(wPpGenConfirmDisabledRule);
      ok(!!wPpGenConfirmDisabledBg,
         "PP-GEN: the .pp-gen-preview-confirm disabled rule declares its OWN background — without one, `:hover` (equal specificity) wins the fill and a disabled/saving button visibly flips to the active colour on hover");
      var wPpGenConfirmBaseRule = __cssRule(".pp-gen-preview-confirm");
      ok(!!wPpGenConfirmBaseRule, "PP-GEN (premise): the rest-state .pp-gen-preview-confirm rule is present in the shipped app.css");
      var wPpGenConfirmBaseBg = __cssBg(wPpGenConfirmBaseRule);
      ok(!!wPpGenConfirmBaseBg, "PP-GEN (premise): the rest-state rule declares a background, so there is a value to compare the disabled rule against");
      if (wPpGenConfirmDisabledBg && wPpGenConfirmBaseBg) {
        ok(wPpGenConfirmDisabledBg.trim() === wPpGenConfirmBaseBg.trim(),
           "PP-GEN: the .pp-gen-preview-confirm disabled rule's background is EXACTLY the rest-state fill (found \"" + wPpGenConfirmDisabledBg.trim() +
           "\" vs rest \"" + wPpGenConfirmBaseBg.trim() + "\") — not just any declared value, the one that keeps a disabled/saving button visually inert");
      }
      el("pp-gen-preview-confirm").click();
      await sleep(70);
      var sentCall = ppLast("generate_sermon_notes");
      ok(!!sentCall && sentCall.args.transcript === PP_TRANSCRIPT_FIXTURE,
         "PP F-5: Confirm sends the exact transcript the review step displayed — not a re-read that could have drifted");
      ok(!!sentCall && sentCall.args.transcript !== PP_TRANSCRIPT_FIXTURE_ADVANCED,
         "PP F-5 L-1: ...and specifically NOT the transcript that advanced underneath the open preview (a re-read-at-send regression sends this)");
      ok(el("pp-gen-preview").hidden === true, "PP F-5: the review step closes once Confirm is pressed");
      ok(getComputedStyle(el("pp-gen-preview")).display === "none",
         "PP F-5 M-1 (computed display): Confirm actually removes the panel from layout, not just the [hidden] attribute");
      window.__ppGen = "ok"; // restore for any later reads
      V.transcript = undefined; V.partial_transcript = undefined; // undo the persistent override above
      render(baseView); // clears view.transcript back to the default so the trailing 1s poll stays consistent

      // === (C-010) THE FOUR PROVIDER STATES — 86akby7d8 ==================================
      // The panel's rendered state must match the backend's reported state in every one of them.
      // Asserted on COMPUTED display and rendered text, never on class names alone.
      var ppReactivate = async function () {
        document.querySelector('.nav-item[data-surface="settings"]').click();
        await sleep(60);
        return document.querySelector(".pp-ai-status");
      };

      // (a) "key_missing" — the direct path is COMPILED IN but no developer key is present. This is
      // the state a fresh checkout is in. It must be distinguishable from "not_configured": the
      // feature exists and the reader can do something about it.
      window.__pp.cloud_status = "key_missing"; window.__pp.notes_provider = null;
      var sKey = await ppReactivate();
      ok(!/Coming soon/.test(sKey.textContent),
         "PP C-010: key_missing is NOT reported as 'Coming soon' — the feature is built, the key is not");
      ok(/No key configured/i.test(sKey.textContent),
         "PP C-010: key_missing names the actual problem (a missing key)");
      ok(/OPENAI_API_KEY/.test(el("surface-settings").textContent) || /developer API key/i.test(el("surface-settings").textContent),
         "PP C-010: key_missing tells the reader what to supply");
      ok(!/Available/.test(sKey.textContent),
         "PP C-010: key_missing must NOT claim the feature is available — the fix must not invert into over-reporting");

      // (b) "direct_provider" — a developer key IS configured. Notes really are generated, so the
      // panel must NOT show 'coming soon', must name the provider (FR-132), and must say the key is
      // a developer key rather than implying a shipped, supported configuration.
      window.__pp.cloud_status = "direct_provider";
      window.__pp.notes_provider = {kind:"openai", name:"OpenAI", model:"gpt-5.6-terra", developer_key:true};
      var sDirect = await ppReactivate();
      ok(!/Coming soon/.test(sDirect.textContent),
         "PP C-010: with a provider configured the panel does NOT say 'coming soon' — this is THE trust bug this ticket fixes");
      ok(/Available/.test(sDirect.textContent),
         "PP C-010: direct_provider reports the feature as available");
      ok(/OpenAI/.test(document.querySelector(".pp-ai-head").textContent),
         "PP C-010: the panel NAMES OpenAI as the provider generating the notes (FR-132)");
      ok(!/SelahCue AI/.test(document.querySelector(".pp-ai-head").textContent),
         "PP C-010: the card no longer claims 'SelahCue AI' when OpenAI generates the notes");
      ok(!!document.querySelector(".pp-badge-dev") && /DEVELOPER KEY/.test(document.querySelector(".pp-ai-head").textContent),
         "PP C-010: the throwaway developer-key posture is stated on the card, not implied");
      ok(/gpt-5\.6-terra/.test(document.querySelector(".pp-ai-status").textContent),
         "PP C-010: the model actually in use is disclosed");
      // quota STAYS null in this phase — a working provider must not conjure a meter.
      var qDirect = document.querySelector(".pp-quota");
      ok(qDirect.classList.contains("pp-quota-empty") && !/\d+\s*\/\s*\d+/.test(qDirect.textContent),
         "PP C-010: with generation WORKING and no metering, quota is still the honest placeholder — no fabricated meter");

      // (c) "hosted" — Phase 2. The hosted service is reachable; the pills say so, and the developer
      // -key language is absent because it does not apply.
      window.__pp.cloud_status = "hosted";
      window.__pp.notes_provider = {kind:"selahcue_hosted", name:"SelahCue AI", model:"", developer_key:false};
      var sHosted = await ppReactivate();
      ok(/Available/.test(sHosted.textContent) && /Cloud connected/.test(sHosted.textContent) && !/Coming soon/.test(sHosted.textContent),
         "PP C-010: hosted renders the Available + Cloud-connected pills");
      ok(!document.querySelector(".pp-badge-dev"),
         "PP C-010: hosted does NOT show the developer-key badge");

      // (d) a real quota, when a hosted server ever reports one, still drives the meter.
      window.__pp.quota = {used:13, limit:40, remaining:27, resets_label:"Sep 1"};
      await ppReactivate();
      var q2 = document.querySelector(".pp-quota");
      ok(!q2.classList.contains("pp-quota-empty") && /13/.test(q2.textContent) && /\/\s*40/.test(q2.textContent),
         "PP C-006: a real server-reported quota renders the used/limit meter");

      // restore the honest stock-build default for everything after this block
      window.__pp.cloud_status = "not_configured"; window.__pp.notes_provider = null; window.__pp.quota = null;
      await ppReactivate();
      ok(/Coming soon/.test(document.querySelector(".pp-ai-status").textContent),
         "PP C-010: back at not_configured the honest 'coming soon' returns (the four states are reversible, not sticky)");

      // (C-007) excluded sections are absent.
      ok(!/Bring your own key/i.test(el("surface-settings").textContent) && !/Text-to-Speech/i.test(el("surface-settings").textContent) && !/BYOK/i.test(el("surface-settings").textContent),
         "PP C-007: the excluded BYOK/Advanced row and Text-to-Speech section are NOT built");

      // (C-008) layout robustness: the panel does not overflow horizontally past its surface.
      var ss = el("surface-settings");
      ok(ss.scrollWidth <= ss.clientWidth + 2, "PP C-008: the Settings body does not overflow horizontally (no sideways scroll)");

      // ==================================================================================
      // W — Design 2.0 parity, batch 1. CON-046 / CON-142 / PME-001 / PME-005 / PME-014-015.
      //
      // Every contrast number below is measured COMPOSITED from the REAL computed styles and
      // at EVERY stop of every gradient. Both properties matter and both were real defects:
      // CON-046's chip is `rgba(255,255,255,.18)` sitting invisibly between the ink and the
      // fill, so a token-on-token check reports "white on green" and misses it entirely; and
      // GO LIVE's fill is a two-stop gradient, so a single-stop check passes on the bright end
      // while the text is still failing on the dark end. Each group carries a control that must
      // measure as FAILING, so a green result proves the measurement works.
      // ==================================================================================
      function _sl(v){ v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }
      function _lum(c){ return 0.2126*_sl(c[0])+0.7152*_sl(c[1])+0.0722*_sl(c[2]); }
      function _cr(a,b){ var la=_lum(a), lb=_lum(b), hi=Math.max(la,lb), lo=Math.min(la,lb); return (hi+0.05)/(lo+0.05); }
      function _rgba(s){ var m=String(s).match(/[-\d.]+/g)||["0","0","0"]; return [+m[0],+m[1],+m[2], m.length>3?+m[3]:1]; }
      function _over(f,b){ var a=(f[3]==null?1:f[3]); return [a*f[0]+(1-a)*b[0], a*f[1]+(1-a)*b[1], a*f[2]+(1-a)*b[2]]; }
      // ink over chip over backdrop — the layer order the browser actually paints.
      function _stack(ink, chip, bg){ var base=_over(chip,bg); return _cr(_over(ink,base), base); }
      function _f(r){ return r.toFixed(2); }
      // Resolve ANY colour declaration (hex, rgb(), or var(--token)) through the live CSS engine.
      function _resolve(decl){
        var pr=document.createElement("span");
        pr.style.cssText="position:absolute;left:-9999px;top:-9999px;background-color:"+decl;
        document.body.appendChild(pr);
        var c=getComputedStyle(pr).backgroundColor; pr.remove(); return _rgba(c);
      }
      // Every colour stop of an element's gradient, or its flat fill when it has no gradient.
      function _stops(node){
        var cs=getComputedStyle(node), m=(cs.backgroundImage||"none").match(/rgba?\([^)]*\)/g);
        return (m && m.length) ? m.map(_rgba) : [_rgba(cs.backgroundColor)];
      }
      function _same(a,b){ return a[0]===b[0] && a[1]===b[1] && a[2]===b[2]; }

      // --- CSSOM-PARSE-01 / CSSOM-PARSE-02: prove __cssRule/__cssBg/__cssFilter (defined on
      // window by CSS_SRC — see operator_headless.py's comment above that constant) actually
      // close the two gaps Sana's security review found in the regex approach they replaced
      // (PR #75 and its follow-up): a duplicated selector, and a `filter` spelling other than
      // the plain one. Every check below (PME-005 onward) reads through these three helpers, so
      // if either regressed back to text-matching every one of those checks would still pass
      // against today's app.css — it has neither a duplicated selector nor a non-plain filter
      // spelling. These checks are mutation-proof for exactly that reason: they insert the
      // adversarial CSS directly into the SAME probe sheet every other check reads, so a
      // regression fails HERE even though production app.css stays clean.
      (function(){
        var probeSheet = document.getElementById("__css_probe__").sheet;

        // Gap 1 (duplicate-rule blindness): a regex keyed on a selector's text only ever finds
        // the FIRST matching rule block. The cascade applies the LAST one (equal specificity,
        // later wins) — prove __cssRule agrees with the cascade, not with "whichever a scan
        // meets first".
        var dupI1 = probeSheet.insertRule(".__cssom_dup_probe__{background:#111111;}", probeSheet.cssRules.length);
        var dupI2 = probeSheet.insertRule(".__cssom_dup_probe__{background:#333333;}", probeSheet.cssRules.length);
        var dupRule = __cssRule(".__cssom_dup_probe__");
        var dupBg = __cssBg(dupRule);
        ok(!!dupRule && !!dupBg && _same(_resolve(dupBg), [51,51,51,1]),
           "CSSOM-PARSE-01: a selector declared TWICE (`.__cssom_dup_probe__`, #111111 then #333333) resolves to the LAST rule — " +
           "the one the cascade actually applies (got \"" + (dupBg || "none") + "\") — not the first; a lookup keyed on selector text alone could only ever find the first");
        probeSheet.deleteRule(dupI2); probeSheet.deleteRule(dupI1);

        // Gap 2 (vendor-prefix / escape blindness): `-webkit-filter` is the native property name
        // on the WebKit engines Tauri ships (WebKitGTK, WKWebView), and a CSS-escaped property
        // name is just another spelling of the same property — both normalise to `filter` through
        // the browser's own parser, which a regex keyed on the literal string `filter:` cannot see.
        var wpI = probeSheet.insertRule(".__cssom_webkit_probe__{-webkit-filter:brightness(1.5);}", probeSheet.cssRules.length);
        var wpFilter = __cssFilter(__cssRule(".__cssom_webkit_probe__"));
        ok(!!wpFilter && /brightness\(\s*1\.5\s*\)/.test(wpFilter),
           "CSSOM-PARSE-02: a `-webkit-filter: brightness(1.5)` declaration reads back as `filter` (got \"" + (wpFilter || "none") + "\")");
        probeSheet.deleteRule(wpI);

        var escI = probeSheet.insertRule(".__cssom_escape_probe__{f\\69lter:brightness(2);}", probeSheet.cssRules.length);
        var escFilter = __cssFilter(__cssRule(".__cssom_escape_probe__"));
        ok(!!escFilter && /brightness\(\s*2\s*\)/.test(escFilter),
           "CSSOM-PARSE-02 (CSS escape): a CSS-escaped `f\\69lter:` declaration reads back as `filter` too (got \"" + (escFilter || "none") + "\") — same normalisation, a different spelling");
        probeSheet.deleteRule(escI);

        // Gap 3 (Sana, PR #79 follow-up, finding 1): Chrome drops a WHOLE declaration outright
        // when it cannot parse the value — an unsupported/malformed filter function, verified
        // live — so __cssFilter reports NONE for it exactly as if it had never been written, and
        // NONE is the PASSING state every "carries no filter" guard relies on. First prove Chrome
        // really does drop it (or this would not be exercising the gap it claims to), then prove
        // the raw-text backstop (__cssRawHasFilter, defined in CSS_SRC) still sees it.
        var wRejectSel = ".__cssom_reject_probe__:hover";
        var wRejectCss = wRejectSel + "{filter:brightness(1.06) not-a-real-css-function();}";
        var rejectProbe = document.createElement("style");
        rejectProbe.textContent = wRejectCss;
        document.head.appendChild(rejectProbe);
        var wRejectRule = null, wRejectRules = rejectProbe.sheet.cssRules;
        for (var wRi = 0; wRi < wRejectRules.length; wRi++) {
          if (wRejectRules[wRi].selectorText === wRejectSel) wRejectRule = wRejectRules[wRi];
        }
        var wRejectFilter = __cssFilter(wRejectRule);
        ok(!!wRejectRule && !wRejectFilter,
           "CSSOM-PARSE-03 (premise): Chrome's own parser drops a filter: declaration whose value it does not recognise, so __cssFilter alone reports it as carrying NO filter (\"" +
           (wRejectFilter || "none") + "\") — the exact blind spot the raw-text backstop below exists for");
        document.head.removeChild(rejectProbe);
        var wSavedCssText = window.__CSSTEXT;
        window.__CSSTEXT = wRejectCss;
        ok(window.__cssRawHasFilter(wRejectSel),
           "CSSOM-PARSE-03: the raw-text backstop (__cssRawHasFilter) still sees the filter: declaration CSSOM silently dropped — closing the gap a CSSOM-only read leaves open, independent of whether the value parses");
        window.__CSSTEXT = wSavedCssText;

        // Gap 4 (Sana, PR #79 follow-up, finding 2): source order alone is not the cascade's
        // tie-break — a duplicate sitting inside an @media block that does NOT currently match
        // must not win over one that does, even though it appears later in the file. Most of
        // app.css's own @media blocks are prefers-reduced-motion:reduce, which never matches in
        // headless Chrome — a plausible future home for exactly this mistake.
        var mqSel = ".__cssom_mq_probe__";
        var mqI1 = probeSheet.insertRule(mqSel + "{background:#0000ff;}", probeSheet.cssRules.length);
        var mqI2 = probeSheet.insertRule("@media (max-width:1px){" + mqSel + "{background:#ff0000;}}", probeSheet.cssRules.length);
        var mqRule = __cssRule(mqSel);
        var mqBg = __cssBg(mqRule);
        ok(!!mqRule && !!mqBg && _same(_resolve(mqBg), [0,0,255,1]),
           "CSSOM-PARSE-04: a duplicate declared inside an @media block that does NOT match the current environment (max-width:1px) is skipped — __cssRule resolves to the rule the browser actually applies (got \"" +
           (mqBg || "none") + "\"), not whichever came last in SOURCE ORDER alone");
        probeSheet.deleteRule(mqI2); probeSheet.deleteRule(mqI1);

        // Gap 5 (Sana, PR #79 follow-up round 2, finding NEW-1): __cssRawBlock/__cssRawHasFilter
        // are a raw TEXT scan and have no idea a CSS comment is not code — proven both directions
        // on shapes this file's own comments already carry (e.g. app.css documents old rules in
        // prose that reads exactly like a selector block).
        ok(!!wRejectRule && !wRejectFilter, "CSSOM-PARSE-05 (premise, reuses Gap 3's fixture): the adversarial rule above still carries an unparseable filter: that CSSOM alone cannot see");
        window.__CSSTEXT = wRejectCss + "\n/* Historical note, kept for context: " + wRejectSel +
          " { background: var(--sc-primary-hover); } before the AA fix. */";
        ok(window.__cssRawHasFilter(wRejectSel),
           "CSSOM-PARSE-05: a trailing CSS comment that itself contains a `<selector> { ... }` shape does not mask the REAL rule's unparseable filter: declaration above it — without stripping comments first, the comment's own fake block (no `filter` inside it) would become the \"last match\" and silently hide the real one");
        var wCmtOnlySel = ".__cssom_cmtonly_probe__:hover";
        window.__CSSTEXT = "/* Historical note: " + wCmtOnlySel + " { filter: brightness(1.06); } was the old rule, removed for AA. */";
        ok(!window.__cssRawHasFilter(wCmtOnlySel),
           "CSSOM-PARSE-05 (false-red guard): a CSS comment that only DOCUMENTS a removed filter, with no real rule for the selector at all, does not itself trip the raw-text backstop");
        window.__CSSTEXT = wSavedCssText;

        // Gap 6 (Sana, PR #79 follow-up round 2, finding NEW-3): CSSOM-PARSE-03 above pins the
        // __cssRawHasFilter PRIMITIVE, not the WIRING — proven live that deleting the
        // `&& !window.__cssRawHasFilter(...)` conjunct from all five real filter guards left every
        // check (CSSOM-PARSE-03 included) green, since nothing then called the primitive at all.
        // The five real guards below now call __cssFilterGuardOk/__cssNoBrightnessFilter instead of
        // inlining their own copy of the composed expression, so there is exactly one place left
        // that could silently drop the backstop — pin THAT function directly, reusing the same
        // CSSOM-drops-it fixture as Gap 3/5, so a regression here is a regression in exactly what
        // every real call site evaluates, not a parallel copy of it.
        window.__CSSTEXT = wRejectCss;
        ok(!__cssFilterGuardOk(wRejectSel, wRejectRule),
           "CSSOM-PARSE-06: __cssFilterGuardOk (what TD-012/PSC-005/GO-LIVE-HOVER/TIMER-START-HOVER actually call) correctly reports the guard as FAILING for a filter: declaration CSSOM alone cannot see — proving the raw-text backstop is wired into the shared function every real call site uses, not just callable in isolation");
        ok(!__cssNoBrightnessFilter(wRejectSel, wRejectRule),
           "CSSOM-PARSE-06 (PP-GEN shape): __cssNoBrightnessFilter (what the PP-GEN guard actually calls) correctly reports FAILING for the same fixture — a brightness() filter stacked with a value Chrome's parser rejects outright");
        window.__CSSTEXT = wSavedCssText;
      })();

      // Shorter wait budget than the default 150×20ms. This block sits at the very END of the
      // driver, so every FAILING predicate here spends virtual time that the RESULTS write still
      // needs: at the default budget a handful of real regressions could push the run past
      // --virtual-time-budget and the gate would report "NO RESULTS BLOCK" (an infra error) instead
      // of the named FAIL that tells you what broke. 60×20ms is ample for these local predicates.
      var wWait = function(pred){ return waitFor(pred, 60); };

      // --- CON-046: the keyboard-hint chips on the three token-filled buttons ---------------
      var wGl = el("golive"), wGlKey = wGl.querySelector(".key"), wGlLbl = wGl.querySelector(".gl-label");
      var wGlStops = _stops(wGl);
      ok(wGlStops.length === 2 && !_same(wGlStops[0], wGlStops[1]),
         "CON-046 (premise): GO LIVE really is a TWO-stop gradient (" + wGlStops.length + " stops, distinct), so 'measured at both stops' is not vacuous");
      // Control: the pairing that actually shipped must still measure as FAILING through this
      // exact helper. Without it, a green result below could just mean the helper returns 21.
      var wOld = wGlStops.map(function(s){ return _stack([255,255,255,1],[255,255,255,0.18],s); });
      ok(Math.max.apply(null, wOld) < 3.0,
         "CON-046 (control): the ORIGINAL white-on-rgba(255,255,255,.18) chip still measures below AA-LARGE through this helper (" + wOld.map(_f).join(" / ") + ":1) — the measurement is not rubber-stamping");
      var wGlChip = _rgba(getComputedStyle(wGlKey).backgroundColor), wGlInk = _rgba(getComputedStyle(wGlKey).color);
      wGlStops.forEach(function(s, i){
        var r = _stack(wGlInk, wGlChip, s);
        ok(r >= 4.5, "CON-046: the GO LIVE '⏎ Enter' chip clears AA-NORMAL on gradient stop " + (i+1) + " (" + _f(r) + ":1)");
      });
      ok(getComputedStyle(wGlKey).color === getComputedStyle(wGlLbl).color,
         "CON-046: the key hint carries the SAME dark ink as the GO LIVE label — one ink on one fill, not two answers to the same question");
      ok(parseFloat(getComputedStyle(wGlKey).fontSize) < 18.66,
         "CON-046 (premise): the chip is SMALL text (" + getComputedStyle(wGlKey).fontSize + "), so 4.5:1 is the right bar — a font-size bump must not silently relax this");

      // Every OTHER key chip on the page, measured on its own button's real fill. The generic
      // `button .key` fallthrough is where this defect class hides: the specific rule you are
      // reading does not mention the state at all, so a rule-by-rule review never sees it.
      // #blackout RESTING was exactly that — muted ink on the resting red gradient, 3.20 / 3.75:1.
      var wEveryKey = Array.prototype.slice.call(document.querySelectorAll("button .key"));
      ok(wEveryKey.length >= 5,
         "CON-046 (premise): every `.key` chip on the page is enumerated (" + wEveryKey.length + " found) — a chip added later is measured, not missed");
      wEveryKey.forEach(function(k){
        var host = k.closest("button"), kc = getComputedStyle(k);
        var worst = Math.min.apply(null, _stops(host).map(function(st){
          return _stack(_rgba(kc.color), _rgba(kc.backgroundColor), st);
        }));
        ok(worst >= 4.5, "CON-046: key chip '" + k.textContent.trim().slice(0,6) + "' on #" + (host.id||host.className) +
           " (RESTING) clears AA-NORMAL on every stop of its own fill (" + _f(worst) + ":1)");
      });
      // The resting BLACKOUT specifically, including its :hover brightness(1.06) — the state the
      // operator looks at most on a safety-critical control.
      var wBoRest = el("blackout"), wBoRestKey = wBoRest.querySelector(".key");
      var wBoRestCs = getComputedStyle(wBoRestKey);
      var wBoRestStops = _stops(wBoRest);
      ok(wBoRestStops.length === 2 && !_same(wBoRestStops[0], wBoRestStops[1]),
         "CON-046 (premise): resting BLACKOUT is a TWO-stop gradient, so both stops must be measured");
      var wBoRestWorst = Math.min.apply(null, wBoRestStops.map(function(st){
        return _stack(_rgba(wBoRestCs.color), _rgba(wBoRestCs.backgroundColor), st); }));
      ok(wBoRestWorst >= 4.5,
         "CON-046: the RESTING BLACKOUT key hint clears AA-NORMAL on both stops of the resting red gradient (" + _f(wBoRestWorst) + ":1)");
      // Control: the muted ink it used to fall through to must still measure as FAILING here.
      var wBoRestOld = Math.max.apply(null, wBoRestStops.map(function(st){
        return _stack(_resolve("var(--sc-text-secondary)"), [107,115,131,0.16], st); }));
      ok(wBoRestOld < 4.5,
         "CON-046 (control): the generic `button .key` muted ink still measures BELOW AA-normal on this fill (" + _f(wBoRestOld) + ":1) — the fix is the ink override, not a measurement artefact");
      ok(getComputedStyle(wBoRestKey).color === getComputedStyle(wBoRest).color,
         "CON-046: the resting BLACKOUT chip takes the button's OWN ink, so resting and engaged read the same (no chip jump on engage)");

      // BLACKOUT engaged: `.on` and [aria-pressed=true] are set together by the render loop, and
      // the review block resolves that state to the darkened canonical red. Measured rather than
      // assumed; a shared fix would have been wrong here.
      var wBo = el("blackout"), wBoKey = wBo.querySelector(".key");
      var wBoWasOn = wBo.classList.contains("on"), wBoPressed = wBo.getAttribute("aria-pressed");
      wBo.classList.add("on"); wBo.setAttribute("aria-pressed", "true");
      var wBoStops = _stops(wBo);
      var wBoChip = _rgba(getComputedStyle(wBoKey).backgroundColor), wBoInk = _rgba(getComputedStyle(wBoKey).color);
      var wBoWorst = Math.min.apply(null, wBoStops.map(function(s){ return _stack(wBoInk, wBoChip, s); }));
      ok(wBoWorst >= 4.5, "CON-046: the BLACKOUT-engaged key hint clears AA-NORMAL on its real engaged fill (" + _f(wBoWorst) + ":1)");
      var wBoLabel = Math.min.apply(null, wBoStops.map(function(s){ return _cr(_rgba(getComputedStyle(wBo).color), s); }));
      ok(wBoLabel >= 4.5,
         "CON-046 (premise): BLACKOUT engaged still uses the darkened canonical red (label " + _f(wBoLabel) + ":1) — that is WHY its white chip passes where GO LIVE's did not");
      if (!wBoWasOn) wBo.classList.remove("on");
      if (wBoPressed == null) wBo.removeAttribute("aria-pressed"); else wBo.setAttribute("aria-pressed", wBoPressed);

      // Clear Output armed sits on --sc-live, an INK used as a fill — the light chip measured 2.74:1.
      var wCa = el("clear-all"), wCaKey = wCa.querySelector(".key"), wCaWasArmed = wCa.classList.contains("armed");
      wCa.classList.add("armed");
      var wCaStops = _stops(wCa);
      var wCaChip = _rgba(getComputedStyle(wCaKey).backgroundColor), wCaInk = _rgba(getComputedStyle(wCaKey).color);
      var wCaWorst = Math.min.apply(null, wCaStops.map(function(s){ return _stack(wCaInk, wCaChip, s); }));
      ok(wCaWorst >= 4.5, "CON-046: the ARMED Clear-Output key hint clears AA-NORMAL on its fill (" + _f(wCaWorst) + ":1)");
      ok(getComputedStyle(wGlKey).backgroundColor !== getComputedStyle(wBoKey).backgroundColor,
         "CON-046: the chips are treated PER FILL, not re-merged into one shared declaration (the merge is what hid this defect)");
      // The armed LABEL, and the non-text contrast of the armed STATE itself. Fixing the label by
      // swapping the FILL would have cost the state its visibility — WCAG 1.4.11 covers states, and
      // the armed hint is a one-second transient whose only signal is that colour flip.
      var wCaArmedFill = _rgba(getComputedStyle(wCa).backgroundColor);
      var wCaLabel = _cr(_rgba(getComputedStyle(wCa).color), wCaArmedFill);
      ok(wCaLabel >= 4.5, "CON-046: the ARMED Clear-Output LABEL clears AA-NORMAL on its fill (" + _f(wCaLabel) + ":1, was white-on---sc-live at 3.27:1)");
      wCa.classList.remove("armed");
      var wCaRestFill = _rgba(getComputedStyle(wCa).backgroundColor);
      if (wCaWasArmed) wCa.classList.add("armed");
      var wCaState = _cr(wCaArmedFill, wCaRestFill);
      ok(wCaState >= 3.0,
         "CON-046: ARMED still stands out from RESTING at the 3:1 non-text bar (" + _f(wCaState) + ":1) — the label fix did not cost the state its visibility");
      ok(_cr(wCaArmedFill, _resolve("var(--panel)")) >= 3.0,
         "CON-046: the ARMED fill still clears 3:1 against the page behind it (" + _f(_cr(wCaArmedFill, _resolve("var(--panel)"))) + ":1)");

      // --- CON-142: three unrelated `.seg` declarations, equal specificity, last-wins ---------
      ok(document.querySelectorAll(".seg").length === 0,
         "CON-142: no element carries the bare `seg` class any more — the three families cannot collide again through markup");
      var wSub = document.querySelector(".subtab-seg"), wSubCs = getComputedStyle(wSub);
      ok(wSubCs.columnGap === "3px",
         "CON-142: the Timer|Stage control keeps its OWN 3px gap (the transcript rule was leaking 8px into it) — got " + wSubCs.columnGap);
      ok(wSubCs.alignItems !== "baseline",
         "CON-142: the Timer|Stage control no longer inherits the transcript line's align-items:baseline — got " + wSubCs.alignItems);
      ok(wSubCs.paddingTop === "3px" && wSubCs.borderTopLeftRadius === "9px",
         "CON-142: the Timer|Stage control keeps its own inset chrome (padding " + wSubCs.paddingTop + ", radius " + wSubCs.borderTopLeftRadius + ")");
      var wSubBtn = wSub.querySelector(".subtab-seg-btn"), wSubBtnCs = getComputedStyle(wSubBtn);
      ok(wSubBtnCs.fontSize === "13px",
         "CON-142: a sub-tab button keeps its own 13px label — `.seg button` (0,0,1,1) used to OUTRANK `.seg-btn` (0,0,1,0) and force 12px; got " + wSubBtnCs.fontSize);
      ok(wSubBtnCs.paddingLeft === "0px",
         "CON-142: a sub-tab button keeps its own `padding: 6px 0` — the same specificity bug forced 6px 8px; got " + wSubBtnCs.paddingLeft);
      var wTp = el("transcript-partial"), wTpWasHidden = wTp.hidden; wTp.hidden = false;
      var wTpCs = getComputedStyle(wTp);
      ok(wTpCs.paddingTop === "0px" && wTpCs.borderTopWidth === "0px" && wTpCs.marginBottom === "0px" && wTpCs.borderTopLeftRadius === "0px",
         "CON-142: a transcript line no longer inherits the segmented control's inset chrome (padding " + wTpCs.paddingTop + ", border " + wTpCs.borderTopWidth + ", margin-bottom " + wTpCs.marginBottom + ", radius " + wTpCs.borderTopLeftRadius + ")");
      ok(wTpCs.columnGap === "8px" && wTpCs.alignItems === "baseline",
         "CON-142: the transcript line keeps its own 8px baseline-aligned geometry (gap " + wTpCs.columnGap + ", align " + wTpCs.alignItems + ")");
      wTp.hidden = wTpWasHidden;
      // Positive control: the rename must have MOVED the Theme-Designer rules, not deleted them.
      // Without this, "the collision is gone" is indistinguishable from "the CSS is gone".
      var wTd = el("td-bg-type"), wTdCs = getComputedStyle(wTd), wTdBtn = wTd.querySelector("button");
      ok(wTdCs.display === "flex",
         "CON-142 (positive control): the Theme-Designer option group still gets its .td-seg layout — got display " + wTdCs.display);
      ok(!!wTdBtn && getComputedStyle(wTdBtn).flexGrow === "1",
         "CON-142 (positive control): `.td-seg button` still styles the designer's segment buttons (the rename moved the rules, it did not drop them)");

      // --- PME-005: .pm-btn-primary:hover ---------------------------------------------------
      var wHoverRule = __cssRule(".pm-btn-primary:hover");
      ok(!!wHoverRule, "PME-005 (premise): the .pm-btn-primary:hover rule is present in the shipped app.css");
      var wHb = __cssBg(wHoverRule);
      ok(!!wHb, "PME-005 (premise): the hover rule declares a background, so there is a value to measure");
      if (wHb) {
        var wHoverBg = _resolve(wHb.trim());
        var wRestBg = _rgba(getComputedStyle(document.querySelector(".pm-btn-primary")).backgroundColor);
        var wHoverR = _cr([255,255,255,1], wHoverBg), wRestR = _cr([255,255,255,1], wRestBg);
        ok(wHoverR >= 4.5, "PME-005: the HOVERED primary keeps its white label at AA-NORMAL (" + _f(wHoverR) + ":1) — hover is a real UI state and WCAG applies to it");
        ok(_lum(wHoverBg) < _lum(wRestBg),
           "PME-005: hover DARKENS the fill instead of lightening it (rest " + _f(wRestR) + ":1 → hover " + _f(wHoverR) + ":1), matching the fix already shipped for .tb-golive");
        var wOldHover = _resolve("var(--sc-primary-hover)");
        ok(_cr([255,255,255,1], wOldHover) < 4.5,
           "PME-005 (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], wOldHover)) + ":1) — the TOKEN VALUE is untouched; only this rule stopped using it");
      }

      // --- TD-012 / PSC-005 / DLM-001: the shared gradient-hover contrast defect, fixed at three
      // more surfaces with the same darken-not-lighten pattern as .tb-golive and .pm-btn-primary:hover
      // above. Each button's own hover RULE TEXT is measured (not a simulated :hover pseudo-class,
      // which this headless page cannot trigger) — same technique as PME-005.
      // --- TD-012: .td-save-cta (Theme Designer "Save theme") --------------------------------
      var wTdSave = document.querySelector(".td-save-cta");
      ok(!!wTdSave, "TD-012 (premise): the Theme Designer Save-theme button exists in the DOM");
      if (wTdSave) {
        var wTdStops = _stops(wTdSave);
        ok(wTdStops.length === 2 && !_same(wTdStops[0], wTdStops[1]),
           "TD-012 (premise): .td-save-cta really is a TWO-stop gradient, so 'measured at both stops' is not vacuous");
        wTdStops.forEach(function(s, i){
          var r = _cr([255,255,255,1], s);
          ok(r >= 4.5, "TD-012: the Save-theme label clears AA-NORMAL on gradient stop " + (i+1) + " (" + _f(r) + ":1)");
        });
        var wTdHoverRule = __cssRule(".td-save-cta:hover");
        ok(!!wTdHoverRule, "TD-012 (premise): the .td-save-cta:hover rule is present in the shipped app.css");
        var wTdHb = __cssBg(wTdHoverRule);
        ok(!!wTdHb, "TD-012 (premise): the hover rule declares a background, so there is a value to measure");
        if (wTdHb) {
          var wTdHoverBg = _resolve(wTdHb.trim());
          var wTdHoverR = _cr([255,255,255,1], wTdHoverBg);
          ok(wTdHoverR >= 4.5, "TD-012: the HOVERED Save-theme button keeps its white label at AA-NORMAL (" + _f(wTdHoverR) + ":1)");
          ok(_lum(wTdHoverBg) <= Math.max.apply(null, wTdStops.map(_lum)),
             "TD-012: hover does not LIGHTEN past the gradient's brightest rest stop — no `filter: brightness()` re-lightening the darkened fill");
        }
        // Sana (security review, PR #58): the two checks above only ever read `background`, so a
        // `filter: brightness()` added BACK onto this same hover rule — the exact re-lightening bug
        // this finding exists to prevent, and exactly what .tb-golive/.timer-start still carry
        // unmeasured — passed this whole suite silently (proven live: adding it back kept all 1544
        // checks green). Assert the rule declares no re-lightening filter at all — read through
        // __cssFilter (CSSOM-PARSE-02 above), which also catches a re-lightening `-webkit-filter`
        // or CSS-escaped spelling, not just the plain one.
        var wTdHoverFilter = __cssFilter(wTdHoverRule);
        ok(__cssFilterGuardOk(".td-save-cta:hover", wTdHoverRule),
           "TD-012: the hover rule carries no `filter` (found " + (wTdHoverFilter ? wTdHoverFilter.trim() : "none") +
           ") — a brightness() filter stacked on an already-darkened fill would re-lighten it past AA, and the background-only checks above cannot see that");
        ok(_cr([255,255,255,1], _resolve("var(--sc-primary-hover)")) < 4.5,
           "TD-012 (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], _resolve("var(--sc-primary-hover)"))) + ":1) — the TOKEN VALUE is untouched; only this rule stopped using it");
      }

      // --- PSC-005: .ps-start (Pre-service "▶ Start service") --------------------------------
      var wPsStart = el("ps-start");
      ok(!!wPsStart, "PSC-005 (premise): the Pre-service Start-service button exists in the DOM");
      if (wPsStart) {
        var wPsStops = _stops(wPsStart);
        ok(wPsStops.length === 2 && !_same(wPsStops[0], wPsStops[1]),
           "PSC-005 (premise): .ps-start really is a TWO-stop gradient, so 'measured at both stops' is not vacuous");
        wPsStops.forEach(function(s, i){
          var r = _cr([255,255,255,1], s);
          ok(r >= 4.5, "PSC-005: the Start-service label clears AA-NORMAL on gradient stop " + (i+1) + " (" + _f(r) + ":1)");
        });
        var wPsHoverRule = __cssRule(".ps-start:hover");
        ok(!!wPsHoverRule, "PSC-005 (premise): the .ps-start:hover rule is present in the shipped app.css");
        var wPsHb = __cssBg(wPsHoverRule);
        ok(!!wPsHb, "PSC-005 (premise): the hover rule declares a background, so there is a value to measure");
        if (wPsHb) {
          var wPsHoverBg = _resolve(wPsHb.trim());
          var wPsHoverR = _cr([255,255,255,1], wPsHoverBg);
          ok(wPsHoverR >= 4.5, "PSC-005: the HOVERED Start-service button keeps its white label at AA-NORMAL (" + _f(wPsHoverR) + ":1)");
          ok(_lum(wPsHoverBg) <= Math.max.apply(null, wPsStops.map(_lum)),
             "PSC-005: hover does not LIGHTEN past the gradient's brightest rest stop — no `filter: brightness()` re-lightening the darkened fill");
        }
        // Same gap Sana found on TD-012 above (PR #58 review): background-only checks miss a
        // `filter: brightness()` stacked back onto this hover rule. Assert none is declared —
        // through __cssFilter, so a re-lightening `-webkit-filter` or escaped spelling counts too.
        var wPsHoverFilter = __cssFilter(wPsHoverRule);
        ok(__cssFilterGuardOk(".ps-start:hover", wPsHoverRule),
           "PSC-005: the hover rule carries no `filter` (found " + (wPsHoverFilter ? wPsHoverFilter.trim() : "none") +
           ") — a brightness() filter stacked on an already-darkened fill would re-lighten it past AA, and the background-only checks above cannot see that");
        ok(_cr([255,255,255,1], _resolve("var(--sc-primary-hover)")) < 4.5,
           "PSC-005 (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], _resolve("var(--sc-primary-hover)"))) + ":1) — the TOKEN VALUE is untouched; only this rule stopped using it");
      }
      // Vera (performance review, PR #58): moving the hover effect from `filter: brightness()` to
      // `background: #5a48d0` broke `.ps-start:disabled`'s neutralisation — `filter: none` only ever
      // cancelled a filter-based hover, and `:disabled`/`:hover` are equal specificity, so without its
      // OWN `background` a disabled+hovered button visibly flips to the active fill (verified live in
      // Chromium: old code stayed inert, this branch did not, before the fix below). This headless
      // page cannot simulate a real `:hover`, so — same technique as the rest of this block — the
      // disabled rule's own declared background is checked to win the cascade.
      var wPsDisabledRule = __cssRule('.ps-start:disabled, .ps-start[aria-disabled="true"]');
      ok(!!wPsDisabledRule, "PSC-005 (premise): the .ps-start:disabled rule is present in the shipped app.css");
      var wPsDisabledBg = __cssBg(wPsDisabledRule);
      ok(!!wPsDisabledBg,
         "PSC-005: the disabled rule declares its OWN background — without one, `:hover` (equal specificity, later in a real disabled+hover) wins the fill and a disabled button visibly flips to the active colour on hover");
      // Cody + Vera (PR #62 review): presence alone doesn't prove the VALUE is right — a
      // nonsense `background: red` would have passed the check above just as well. Compare
      // against the REST-state rule's own declared background: the disabled state should read
      // as the same fill (just dimmed by `opacity: .45`), not a different one. `__cssRule` matches
      // the bare `.ps-start` selector EXACTLY, so it cannot accidentally pick up `:hover`,
      // `:focus-visible` or the `:disabled, .ps-start[...]` rule above.
      var wPsBaseRule = __cssRule(".ps-start");
      ok(!!wPsBaseRule, "PSC-005 (premise): the rest-state .ps-start rule is present in the shipped app.css");
      var wPsBaseBg = __cssBg(wPsBaseRule);
      ok(!!wPsBaseBg, "PSC-005 (premise): the rest-state rule declares a background, so there is a value to compare the disabled rule against");
      if (wPsDisabledBg && wPsBaseBg) {
        ok(wPsDisabledBg.trim() === wPsBaseBg.trim(),
           "PSC-005: the disabled rule's background is EXACTLY the rest-state fill (found \"" + wPsDisabledBg.trim() +
           "\" vs rest \"" + wPsBaseBg.trim() + "\") — not just any declared value, the one that keeps a disabled button visually inert");
      }

      // --- PSC-009: .ps-detail-warn / .ps-detail-block (Pre-service check-row detail text) -----
      // The audit (docs/design/DESIGN-2.0-PARITY-AUDIT-preservice.md) flagged this pairing as
      // UNMEASURED — "worth a direct follow-up measurement" — not as a scored defect. Farah
      // independently computed it for ClickUp 17tnw2axptu: --sc-warn/--sc-live on --sc-surface
      // clear AA-NORMAL even at the row's own 12px/500 weight (8.85:1 / 5.52:1), so there is no
      // fix to make here — this block locks the passing state in place instead of leaving it
      // unmeasured, same discipline as every other contrast finding in this file. Both classes
      // recolour `.ps-row-detail` (app.css:6701-6703); the real painted background behind them is
      // `.ps-card`'s --sc-surface (`.ps-row` itself declares none). Measured on the LIVE DOM, in
      // real application states (not the raw CSS variables), matching this file's own established
      // technique for the rest of the PSC-005/TD-012/DLM-001 group above.
      var wPsCardBg = _rgba(getComputedStyle(document.querySelector(".ps-card")).backgroundColor);
      // The default warning (missing slide media) is still live from the earlier functional
      // Pre-service Check block — nothing between there and here mutates pre-service state.
      var wPsWarnRow = document.querySelector(".ps-detail-warn");
      ok(!!wPsWarnRow, "PSC-009 (premise): a .ps-detail-warn row is live in the DOM (the default missing-media warning)");
      if (wPsWarnRow) {
        var wPsWarnR = _cr(_rgba(getComputedStyle(wPsWarnRow).color), wPsCardBg);
        ok(wPsWarnR >= 4.5,
           "PSC-009: .ps-detail-warn (--sc-warn on --sc-surface) clears AA-NORMAL at its real 12px/500 weight (" + _f(wPsWarnR) + ":1) — the audit flagged this pairing as unmeasured, not failing");
      }
      // .ps-detail-block only exists once a check is actually BLOCKING — trigger the same disk-low
      // fixture the functional Pre-service Check block above uses, so the measurement is a real
      // painted row, not an assertion about the CSS variable's raw value in isolation.
      window.__psDiskLow = true;
      el("ps-rerun").click();
      ok(await wWait(function(){ return !!document.querySelector(".ps-detail-block"); }),
         "PSC-009 (premise): a .ps-detail-block row appears once a check goes BLOCKING (disk space)");
      var wPsBlockRow = document.querySelector(".ps-detail-block");
      if (wPsBlockRow) {
        var wPsBlockR = _cr(_rgba(getComputedStyle(wPsBlockRow).color), wPsCardBg);
        ok(wPsBlockR >= 4.5,
           "PSC-009: .ps-detail-block (--sc-live on --sc-surface) clears AA-NORMAL at its real 12px/500 weight (" + _f(wPsBlockR) + ":1) — matches PME-004's independently-established 5.52:1 figure for the same token pairing (DESIGN-2.0-PARITY-AUDIT-presentation.md)");
      }
      window.__psDiskLow = false;
      el("ps-rerun").click();
      ok(await wWait(function(){ return el("ps-blocking").textContent === "0"; }),
         "PSC-009 (cleanup): the blocking fixture is cleared, so pre-service state is not left dirty for anything that runs after this block");

      // --- DLM-001: .dl-btn-primary:hover (Download modal primary button) --------------------
      var wDlHoverRule = __cssRule(".dl-btn-primary:hover");
      ok(!!wDlHoverRule, "DLM-001 (premise): the .dl-btn-primary:hover rule is present in the shipped app.css");
      var wDlHb = __cssBg(wDlHoverRule);
      ok(!!wDlHb, "DLM-001 (premise): the hover rule declares a background, so there is a value to measure");
      if (wDlHb) {
        var wDlRestEl = document.querySelector(".dl-btn-primary");
        ok(!!wDlRestEl, "DLM-001 (premise): the download modal's primary button exists in the DOM");
        var wDlHoverBg = _resolve(wDlHb.trim());
        var wDlRestBg = wDlRestEl ? _rgba(getComputedStyle(wDlRestEl).backgroundColor) : [0,0,0,1];
        var wDlHoverR = _cr([255,255,255,1], wDlHoverBg), wDlRestR = _cr([255,255,255,1], wDlRestBg);
        ok(wDlHoverR >= 4.5, "DLM-001: the HOVERED primary keeps its white label at AA-NORMAL (" + _f(wDlHoverR) + ":1) — hover is a real UI state and WCAG applies to it");
        ok(_lum(wDlHoverBg) < _lum(wDlRestBg),
           "DLM-001: hover DARKENS the fill instead of lightening it (rest " + _f(wDlRestR) + ":1 → hover " + _f(wDlHoverR) + ":1), matching the fix already shipped for .pm-btn-primary:hover");
        var wDlOldHover = _resolve("var(--sc-primary-hover)");
        ok(_cr([255,255,255,1], wDlOldHover) < 4.5,
           "DLM-001 (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], wDlOldHover)) + ":1) — the TOKEN VALUE is untouched; only this rule stopped using it");
      }

      // --- DLM-007 / DLM-008: Download modal geometry drift (17tnw2axptx) --------------------
      // Cosmetic card/button radius drift vs Figma 396:124 — card 14→16, button 8→10. `#dl-modal`
      // and its buttons are always present in the DOM (only the `.dl-modal-back` wrapper toggles
      // `hidden`), so computed border-radius is measurable regardless of visibility.
      var wDlCard = el("dl-modal");
      ok(!!wDlCard, "DLM-007 (premise): the download modal card exists in the DOM");
      if (wDlCard) {
        ok(getComputedStyle(wDlCard).borderRadius === "16px",
           "DLM-007: .dl-modal card radius matches the Figma spec (16px), found " + getComputedStyle(wDlCard).borderRadius);
      }
      var wDlBtn = el("dl-modal-secondary");
      ok(!!wDlBtn, "DLM-008 (premise): a .dl-btn (Cancel) exists in the DOM to measure");
      if (wDlBtn) {
        ok(getComputedStyle(wDlBtn).borderRadius === "10px",
           "DLM-008: .dl-btn radius matches the Figma spec (10px), found " + getComputedStyle(wDlBtn).borderRadius);
      }

      // --- GO-LIVE-HOVER / TIMER-START-HOVER: .tb-golive/.timer-start kept `filter:
      // brightness(1.06)` on :hover when their REST gradient was darkened (#10 above,
      // app.css:5002-5007) to fix white-on-the-light-stop failing AA. Brightening the ALREADY
      // darkened near stop by 6% pulls it back under AA-normal (4.27:1) — a regression no
      // existing check measured: CON-046 above measures the '⏎ Enter' key-hint CHIP on this
      // same button, not the button's own label, and PME-005 measures a different button,
      // .pm-btn-primary:hover. Same technique as TD-012/PSC-005/DLM-001: measure the parsed
      // :hover rule text, not a simulated :hover pseudo-class, which this headless page cannot
      // trigger. Also carries TD-012's own filter-guard check (Sana, PR #58 review) — this is
      // literally the surface her comment names as still carrying the gap unmeasured.
      // --- GO-LIVE-HOVER: .tb-golive (topbar "● GO LIVE") ------------------------------------
      var wTbGl = el("top-golive");
      ok(!!wTbGl, "GO-LIVE-HOVER (premise): the topbar GO LIVE button exists in the DOM");
      if (wTbGl) {
        var wTbGlStops = _stops(wTbGl);
        ok(wTbGlStops.length === 2 && !_same(wTbGlStops[0], wTbGlStops[1]),
           "GO-LIVE-HOVER (premise): .tb-golive really is a TWO-stop gradient, so 'measured at both stops' is not vacuous");
        wTbGlStops.forEach(function(s, i){
          var r = _cr([255,255,255,1], s);
          ok(r >= 4.5, "GO-LIVE-HOVER: the topbar GO LIVE label clears AA-NORMAL on gradient stop " + (i+1) + " (" + _f(r) + ":1)");
        });
        var wTbGlHoverRule = __cssRule(".tb-golive:hover");
        ok(!!wTbGlHoverRule, "GO-LIVE-HOVER (premise): the .tb-golive:hover rule is present in the shipped app.css");
        var wTbGlHb = __cssBg(wTbGlHoverRule);
        ok(!!wTbGlHb, "GO-LIVE-HOVER (premise): the hover rule declares a background, so there is a value to measure — a bare `filter: brightness()` would leave nothing here");
        if (wTbGlHb) {
          var wTbGlHoverBg = _resolve(wTbGlHb.trim());
          var wTbGlHoverR = _cr([255,255,255,1], wTbGlHoverBg);
          ok(wTbGlHoverR >= 4.5, "GO-LIVE-HOVER: the HOVERED topbar GO LIVE button keeps its white label at AA-NORMAL (" + _f(wTbGlHoverR) + ":1)");
          ok(_lum(wTbGlHoverBg) <= Math.max.apply(null, wTbGlStops.map(_lum)),
             "GO-LIVE-HOVER: hover does not LIGHTEN past the gradient's brightest rest stop — no `filter: brightness()` re-lightening the darkened fill");
        }
        // Sana's TD-012 finding (PR #58 review) applies identically here: the background-only
        // checks above cannot see a `filter: brightness()` stacked back onto this hover rule.
        var wTbGlHoverFilter = __cssFilter(wTbGlHoverRule);
        ok(__cssFilterGuardOk(".tb-golive:hover", wTbGlHoverRule),
           "GO-LIVE-HOVER: the hover rule carries no `filter` (found " + (wTbGlHoverFilter ? wTbGlHoverFilter.trim() : "none") +
           ") — a brightness() filter stacked on an already-darkened fill would re-lighten it past AA, and the background-only checks above cannot see that");
        // Control: recomputing the ORIGINAL `filter: brightness(1.06)` against the darkened
        // rest gradient's own stops must still measure as FAILING through this exact helper —
        // proves the assertions above are not rubber-stamping a value that was already fine.
        var wTbGlBrightened = wTbGlStops.map(function(s){ return [Math.min(255,s[0]*1.06), Math.min(255,s[1]*1.06), Math.min(255,s[2]*1.06), s[3]]; });
        ok(Math.min.apply(null, wTbGlBrightened.map(function(s){ return _cr([255,255,255,1], s); })) < 4.5,
           "GO-LIVE-HOVER (control): `filter: brightness(1.06)` on the darkened rest gradient still measures BELOW AA-normal through this helper — the fix is a real background change, not a measurement artefact");
      }

      // --- TIMER-START-HOVER: .timer-start (Service Timer "Start") --------------------------
      var wTimerStart = el("timer-start-custom");
      ok(!!wTimerStart, "TIMER-START-HOVER (premise): the Service Timer custom-time Start button exists in the DOM");
      if (wTimerStart) {
        var wTsStops = _stops(wTimerStart);
        ok(wTsStops.length === 2 && !_same(wTsStops[0], wTsStops[1]),
           "TIMER-START-HOVER (premise): .timer-start really is a TWO-stop gradient, so 'measured at both stops' is not vacuous");
        wTsStops.forEach(function(s, i){
          var r = _cr([255,255,255,1], s);
          ok(r >= 4.5, "TIMER-START-HOVER: the Timer Start label clears AA-NORMAL on gradient stop " + (i+1) + " (" + _f(r) + ":1)");
        });
        var wTsHoverRule = __cssRule(".timer-start:hover");
        ok(!!wTsHoverRule, "TIMER-START-HOVER (premise): the .timer-start:hover rule is present in the shipped app.css");
        var wTsHb = __cssBg(wTsHoverRule);
        ok(!!wTsHb, "TIMER-START-HOVER (premise): the hover rule declares a background, so there is a value to measure — a bare `filter: brightness()` would leave nothing here");
        if (wTsHb) {
          var wTsHoverBg = _resolve(wTsHb.trim());
          var wTsHoverR = _cr([255,255,255,1], wTsHoverBg);
          ok(wTsHoverR >= 4.5, "TIMER-START-HOVER: the HOVERED Timer Start button keeps its white label at AA-NORMAL (" + _f(wTsHoverR) + ":1)");
          ok(_lum(wTsHoverBg) <= Math.max.apply(null, wTsStops.map(_lum)),
             "TIMER-START-HOVER: hover does not LIGHTEN past the gradient's brightest rest stop — no `filter: brightness()` re-lightening the darkened fill");
        }
        var wTsHoverFilter = __cssFilter(wTsHoverRule);
        ok(__cssFilterGuardOk(".timer-start:hover", wTsHoverRule),
           "TIMER-START-HOVER: the hover rule carries no `filter` (found " + (wTsHoverFilter ? wTsHoverFilter.trim() : "none") +
           ") — a brightness() filter stacked on an already-darkened fill would re-lighten it past AA, and the background-only checks above cannot see that");
        var wTsBrightened = wTsStops.map(function(s){ return [Math.min(255,s[0]*1.06), Math.min(255,s[1]*1.06), Math.min(255,s[2]*1.06), s[3]]; });
        ok(Math.min.apply(null, wTsBrightened.map(function(s){ return _cr([255,255,255,1], s); })) < 4.5,
           "TIMER-START-HOVER (control): `filter: brightness(1.06)` on the darkened rest gradient still measures BELOW AA-normal through this helper — the fix is a real background change, not a measurement artefact");
      }

      // --- PP-GEN: sermon-prep Generate panel (.pp-generate / .pp-optin-btn /
      // .pp-gen-preview-confirm) — Providers & Privacy `348:124`; `#tr-generate` in the
      // Transcripts workspace reuses the same `.pp-generate` class (TRANSCRIPTS-2.0-HANDOFF.md
      // §"Component primitives"). Same defect class as CON-007/CON-067/PME-005: white text on
      // --sc-primary-hover (3.78:1) fails AA-normal. Previously unaudited on this surface —
      // DESIGN-2.0-PARITY-AUDIT-settings.md's A11Y-1 said no gradient defect was found here,
      // which was wrong; corrected alongside this fix.
      // .pp-generate REST: a two-stop gradient, like GO LIVE — both stops must be measured.
      var wPpGen = el("pp-generate");
      var wPpGenStops = _stops(wPpGen);
      ok(wPpGenStops.length === 2 && !_same(wPpGenStops[0], wPpGenStops[1]),
         "PP-GEN (premise): .pp-generate REST really is a two-stop gradient (" + wPpGenStops.length + " stops, distinct), so 'measured at both stops' is not vacuous");
      var wPpGenWorst = Math.min.apply(null, wPpGenStops.map(function(s){ return _cr([255,255,255,1], s); }));
      ok(wPpGenWorst >= 4.5,
         "PP-GEN: .pp-generate REST clears AA-NORMAL on every gradient stop for its 16px bold white label (" + _f(wPpGenWorst) + ":1)");
      var wPpGenOldStop = _resolve("var(--sc-primary-hover)");
      ok(_cr([255,255,255,1], wPpGenOldStop) < 4.5,
         "PP-GEN (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], wPpGenOldStop)) + ":1) — the token is untouched, only the gradient stopped using it as a stop");
      // .pp-generate:hover must not reintroduce filter:brightness() — brightening the now-darker
      // gradient back up is the exact unfixed gap flagged on .tb-golive/.timer-start.
      var wPpGenHoverRule = __cssRule(".pp-generate:hover");
      ok(!!wPpGenHoverRule, "PP-GEN (premise): the .pp-generate:hover rule is present in the shipped app.css");
      if (wPpGenHoverRule) {
        // Read through __cssFilter (not a raw-text scan for "filter:") so a re-lightening
        // -webkit-filter or CSS-escaped spelling counts as brightness() too, not just the plain
        // one — AND through the raw block text (Sana, PR #79 follow-up, finding 1), since Chrome
        // drops a filter: declaration outright when it cannot parse the value, which would make
        // __cssFilter report null (the passing state) for a brightness() call stacked with an
        // unparseable one.
        ok(__cssNoBrightnessFilter(".pp-generate:hover", wPpGenHoverRule),
           "PP-GEN: .pp-generate:hover does NOT use filter:brightness() — that would re-lighten the darkened gradient stop, the exact gap still open on .tb-golive/.timer-start");
        var wPpGenHb = __cssBg(wPpGenHoverRule);
        ok(!!wPpGenHb, "PP-GEN (premise): the hover rule declares a background, so there is a value to measure");
        if (wPpGenHb) {
          var wPpGenHoverBg = _resolve(wPpGenHb.trim());
          var wPpGenHoverR = _cr([255,255,255,1], wPpGenHoverBg);
          ok(wPpGenHoverR >= 4.5, "PP-GEN: the HOVERED .pp-generate keeps its white label at AA-NORMAL (" + _f(wPpGenHoverR) + ":1)");
          ok(_lum(wPpGenHoverBg) <= Math.max.apply(null, wPpGenStops.map(_lum)),
             "PP-GEN: .pp-generate hover does not lighten past the REST gradient's brightest stop");
        }
      }
      // Sana (PR #60 review): the exact PSC-005 trap (.ps-start:disabled, above) reproduced here —
      // moving hover from `filter: brightness()` to `background: #5a48d0` broke the disabled rule's
      // neutralisation, since `:hover`/`[disabled]` are equal specificity and `filter: none` alone
      // only ever cancelled a filter-based hover. Without its OWN background, a disabled+hovered
      // button visibly flips to the active fill. Same two-check technique as PSC-005: the disabled
      // rule must declare its own background, AND that background must be the exact REST fill (not
      // just any declared value — Cody/Vera's PR #62 finding on PSC-005 itself).
      var wPpGenDisabledRule = __cssRule('.pp-generate[disabled], .pp-generate[aria-busy="true"]');
      ok(!!wPpGenDisabledRule, "PP-GEN (premise): the .pp-generate[disabled] rule is present in the shipped app.css");
      var wPpGenDisabledBg = __cssBg(wPpGenDisabledRule);
      ok(!!wPpGenDisabledBg,
         "PP-GEN: the disabled rule declares its OWN background — without one, `:hover` (equal specificity) wins the fill and a disabled button visibly flips to the active colour on hover");
      var wPpGenBaseRule = __cssRule(".pp-generate");
      ok(!!wPpGenBaseRule, "PP-GEN (premise): the rest-state .pp-generate rule is present in the shipped app.css");
      var wPpGenBaseBg = __cssBg(wPpGenBaseRule);
      ok(!!wPpGenBaseBg, "PP-GEN (premise): the rest-state rule declares a background, so there is a value to compare the disabled rule against");
      if (wPpGenDisabledBg && wPpGenBaseBg) {
        ok(wPpGenDisabledBg.trim() === wPpGenBaseBg.trim(),
           "PP-GEN: the disabled rule's background is EXACTLY the rest-state fill (found \"" + wPpGenDisabledBg.trim() +
           "\" vs rest \"" + wPpGenBaseBg.trim() + "\") — not just any declared value, the one that keeps a disabled button visually inert");
      }

      // .pp-optin-btn:hover is checked earlier, at "PP C-005" (`#pp-optin-retry` only exists
      // transiently during the consent_required state and is gone again by this point in the run).
      // .pp-gen-preview-confirm:hover is checked earlier too, at "PP F-5" (the button is rebuilt
      // fresh on each Generate cycle and is not reliably present here).

      // RULE-REGEX-LASTMATCH (the `_lastRule()`-based duplicate-selector check that used to live
      // here) is superseded by CSSOM-PARSE-01 above (right after the `_same` helper): reading the
      // browser's own parsed CSSOM makes a global-match regex helper unnecessary, and CSSOM-PARSE-01
      // proves the same last-match-wins property against the mechanism this file actually uses now.

      // --- PME-014 / PME-015: the two missing topbar primary actions ------------------------
      document.querySelector('.nav-item[data-surface="presentation"]').click();
      ok(await wWait(function(){ return el("surface-presentation").classList.contains("active") && !el("pm-library").hidden; }),
         "PME-014/015 (setup): the Presentation surface opens on the Library");
      var wPres = el("pm-present"), wAtp = el("pm-addtoplan");
      ok(!!wPres && wPres.tagName === "BUTTON", "PME-014: a real '▶ Present' control exists in the Presentation topbar (it was reachable ONLY from the ⌘K palette)");
      ok(!!wAtp && wAtp.tagName === "BUTTON", "PME-015: an 'Add to plan' control exists in the Presentation topbar");
      ok(getComputedStyle(wPres).display === "none" && getComputedStyle(wAtp).display === "none",
         "PME-014/015: both topbar actions are hidden by COMPUTED display while browsing the Library (not merely the [hidden] attribute, which a class `display` rule would defeat)");
      ok(wPres.getClientRects().length === 0 && wAtp.getClientRects().length === 0,
         "PME-014/015: the hidden actions are genuinely unpainted, so they leave the tab order too (WCAG 2.4.3)");
      ok(await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-open"); }), "PME-014 (setup): the library lists at least one presentation to open");
      el("pm-lib-grid").querySelector(".pm-lib-open").click();
      ok(await wWait(function(){ return !el("pm-grid").hidden; }), "PME-014 (setup): opening a presentation shows the slide grid");
      ok(getComputedStyle(wPres).display !== "none" && wPres.getClientRects().length > 0,
         "PME-014: '▶ Present' is really PAINTED once a presentation is open (computed display " + getComputedStyle(wPres).display + ")");
      ok(getComputedStyle(wAtp).display !== "none" && wAtp.getClientRects().length > 0,
         "PME-015: 'Add to plan' is really painted once a presentation is open");
      // B2 WRITE half, second send site. The driver asserted this button was painted but never
      // CLICKED it, so dropping `label` from pmAddToPlan() left the gate green at 834 even after
      // the link-modal site was pinned. The add_item/set_item_content stubs return an unmutated
      // copy of V, so clicking here cannot disturb any other check.
      var wAtpN = window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).length;
      wAtp.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).length > wAtpN; }),
         "PME-015: 'Add to plan' links the open presentation to the plan item it just created (set_item_content)");
      var atpCalls = window.__calls.filter(function(c){ return c.cmd === "set_item_content"; });
      var atpLink = atpCalls.length ? atpCalls[atpCalls.length-1].args.link : null;
      var atpDeck = ((window.__LIB && window.__LIB.decks) || []).filter(function(d){ return atpLink && d.id === atpLink.id; })[0];
      ok(!!atpLink && atpLink.kind === "deck" && !!atpDeck && atpLink.label === atpDeck.name,
         "PME-015: 'Add to plan' carries the open deck's OWN name as link.label, so a later deletion can still name it");
      ok(getComputedStyle(wPres).backgroundImage === "none",
         "PME-003: '▶ Present' uses the FLAT primary fill, never the frame's gradient (white on the frame's light stop is 3.78:1)");
      var wGlN = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      wPres.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length > wGlN; }),
         "PME-014: '▶ Present' presents from GRID mode (deck_go_live) — the same split the ⌘K palette already made");
      el("pm-grid-edit").click();
      ok(await wWait(function(){ return getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display !== "none"; }),
         "PME-014 (setup): Edit ▸ opens the authoring editor");
      ok(getComputedStyle(wPres).display !== "none", "PME-014: '▶ Present' stays available in the EDITOR, not just the grid");
      var wGlN2 = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      wPres.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length > wGlN2; }),
         "PME-014: '▶ Present' presents the selected slide from EDITOR mode (deck_go_live)");

      // --- PME-001: the LIVE badge on the presented slide's rail card ------------------------
      // Measured on the REAL badge the editor just rendered, not on a synthetic probe.
      ok(await wWait(function(){ return !!document.querySelector(".pm-slide-live-badge"); }),
         "PME-001 (positive control): a presented slide really renders the non-colour LIVE badge — the ratio below is measured on a live element");
      var wBadge = document.querySelector(".pm-slide-live-badge");
      if (wBadge) {
        var wBc = getComputedStyle(wBadge), wBFill = _rgba(wBc.backgroundColor), wBInk = _rgba(wBc.color);
        var wBR = _cr(wBInk, wBFill);
        ok(wBR >= 4.5, "PME-001: the LIVE badge clears AA-NORMAL at " + wBc.fontSize + "/" + wBc.fontWeight + " (" + _f(wBR) + ":1) — an accessibility affordance that was itself failing accessibility");
        ok(parseFloat(wBc.fontSize) < 18.66,
           "PME-001 (premise): the badge really is SMALL text (" + wBc.fontSize + "), so AA-normal applies — a size change must not silently relax this check");
        ok(!_same(wBFill, _resolve("var(--sc-live)")),
           "PME-001: the badge no longer uses --sc-live (an INK) as a fill; it uses the canonical white-text red fill, the same resolution #blackout already took");
        ok(_cr([255,255,255,1], _resolve("var(--sc-live)")) < 4.5,
           "PME-001 (control): white on --sc-live still measures BELOW AA-normal (" + _f(_cr([255,255,255,1], _resolve("var(--sc-live)"))) + ":1) — the token value is untouched; the badge stopped using it as a fill");
      }

      // --- PME-015 behaviour: a REAL plan item with a REAL deck link -------------------------
      var wOpenId = window.__LIB.open;
      var wOpenDeck = window.__LIB.decks.filter(function(d){ return d.id === wOpenId; })[0];
      var wAiN = window.__calls.filter(function(c){ return c.cmd === "add_item"; }).length;
      var wSicN = window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).length;
      wAtp.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).length > wSicN; }),
         "PME-015: 'Add to plan' commits through the host (set_item_content), not a local stub");
      var wAdd = window.__calls.filter(function(c){ return c.cmd === "add_item"; }).pop();
      ok(window.__calls.filter(function(c){ return c.cmd === "add_item"; }).length === wAiN + 1 && wAdd.args.kind === "slide_group",
         "PME-015: it appends exactly ONE Presentation item to the plan (add_item{kind:slide_group})");
      ok(wAdd.args.title === wOpenDeck.name,
         "PME-015: the new plan item is titled with the OPEN deck's name (\"" + wAdd.args.title + "\")");
      var wLink = window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).pop();
      ok(wLink.args.link && wLink.args.link.kind === "deck" && wLink.args.link.id === wOpenId,
         "PME-015: the item carries a REAL deck reference (link{kind:deck,id:" + (wLink.args.link && wLink.args.link.id) + "}), not an unlinked title");
      ok(wLink.args.link.slide_count === wOpenDeck.slides,
         "PME-015: the link carries the deck's slide count (" + wLink.args.link.slide_count + ") to the host, which owns no deck store — so the plan row reports a real count");
      ok(!el("pm-toast").hidden && /plan/i.test(el("pm-toast").textContent),
         "PME-015: a role=status toast confirms the plan edit");
      var wUndo = el("pm-toast").querySelector(".pm-toast-action");
      ok(!!wUndo && /Undo/i.test(wUndo.textContent), "PME-015: the toast offers Undo — the plan edit is reversible");
      var wRiN = window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length;
      wUndo.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length > wRiN; }),
         "PME-015: Undo really removes the item it just added (remove_item)");
      // Rollback: a rejected LINK must not leave behind a plan row that claims a deck it has not got.
      if (!el("pm-error").hidden && el("pm-error-dismiss")) el("pm-error-dismiss").click();
      window.__sicRejectOnce = true;
      var wRiN2 = window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length;
      wAtp.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length > wRiN2; }),
         "PME-015: a REJECTED deck link rolls the plan item back (no orphan row promising a deck it does not hold)");
      ok(await wWait(function(){ return !el("pm-error").hidden; }) && el("pm-error").getAttribute("role") === "alert",
         "PME-015: a rejected deck link surfaces the role=alert error banner — the failure is reported, not swallowed");
      if (el("pm-error-dismiss")) el("pm-error-dismiss").click();

      // --- CON-128 / CON-139: detector liveness -------------------------------------------
      // THE ACCEPTANCE BAR, as a test: a dead detector and a silent room must not render
      // identically. Every fixture below asserts it actually REACHED the state it names before
      // asserting what that state renders — silence looks the same from outside, so a fixture
      // that never arrives would let all of this pass while proving nothing.
      document.querySelector('.nav-item[data-surface="console"]').click();
      ok(await wWait(function(){ return el("surface-console").classList.contains("active"); }),
         "CON-128/139 (setup): the console surface is active");
      el("rtab-detections").click();
      ok(await wWait(function(){ return !el("rpanel-detections").hidden; }),
         "CON-128/139 (setup): the Detected Scriptures panel is open");
      var wHealth = function(h){ window.__detHealth = h; window.__detHealthFail = false; return window.__detHealthRefresh(); };
      var wHBox = el("det-health"), wHTitle = el("det-health-title"), wHBody = el("det-health-body"),
          wHRetry = el("det-health-retry"), wEmptyMsg = el("det-empty-msg"), wEmptySub = el("det-empty-sub");
      ok(!!wHBox && !!wEmptyMsg, "CON-128/139: the detector-health element and a state-driven empty state exist");

      // (1) LISTENING, nothing heard yet — a silent room.
      await wHealth({state:"listening", provider:"whisper-small", error:null, can_retry:false});
      ok(wHBox.hidden, "CON-128 (premise): a healthy listening detector shows NO fault card — the fixture reached 'listening'");
      var wSilent = (wEmptyMsg.textContent + " " + wEmptySub.textContent).replace(/\s+/g, " ").trim();
      ok(/listening/i.test(wSilent), "CON-128: a silent room says it is LISTENING (\"" + wSilent.slice(0, 58) + "\")");
      ok(/whisper-small/.test(wSilent), "CON-128: it names the engine producing the transcript (FR-120 honest disclosure), rather than an unattributed claim");

      // (2) IDLE — not listening at all. Must NOT read like (1).
      await wHealth({state:"idle", provider:null, error:null, can_retry:false});
      var wIdle = (wEmptyMsg.textContent + " " + wEmptySub.textContent).replace(/\s+/g, " ").trim();
      ok(wHBox.hidden, "CON-128 (premise): idle is not a fault either — the fixture reached 'idle'");
      ok(/not running/i.test(wIdle) && wIdle !== wSilent,
         "CON-128: 'not listening' and 'listening, nothing yet' render DIFFERENTLY — they used to be the same sentence");

      // (3) UNAVAILABLE — a dead detector. THE other half of the bar.
      await wHealth({state:"unavailable", provider:null, error:"The speech model failed to load.", can_retry:true});
      ok(!wHBox.hidden && getComputedStyle(wHBox).display !== "none" && wHBox.getClientRects().length > 0,
         "CON-139 (premise): a dead detector renders a PAINTED fault card — the fixture reached 'unavailable'");
      ok(/Detection unavailable/i.test(wHTitle.textContent), "CON-139: it says the detection is unavailable, in words");
      ok(/speech model failed to load/i.test(wHBody.textContent),
         "CON-139: it shows the HOST'S retained reason, not a generic apology (\"" + wHBody.textContent.slice(0, 50) + "\")");
      var wDead = (wHTitle.textContent + " " + wHBody.textContent + " " + wEmptyMsg.textContent).replace(/\s+/g, " ").trim();
      ok(wDead !== wSilent,
         "ACCEPTANCE BAR: a DEAD detector and a SILENT room do not render identically — this is the property the whole batch is measured against");
      var wCardBg = _rgba(getComputedStyle(wHBox).backgroundColor);
      ok(_cr(_rgba(getComputedStyle(wHTitle).color), wCardBg) >= 4.5,
         "CON-139: the fault heading clears AA-NORMAL on the card (" + _f(_cr(_rgba(getComputedStyle(wHTitle).color), wCardBg)) + ":1)");
      ok(_cr(_rgba(getComputedStyle(wHBody).color), wCardBg) >= 4.5,
         "CON-139: the fault body clears AA-NORMAL on the card (" + _f(_cr(_rgba(getComputedStyle(wHBody).color), wCardBg)) + ":1)");
      ok(!wHRetry.hidden, "CON-139: retry is offered when the host says can_retry");
      var wRetryEdge = Math.max(_cr(_rgba(getComputedStyle(wHRetry).backgroundColor), wCardBg),
                                _cr(_rgba(getComputedStyle(wHRetry).borderTopColor), wCardBg));
      ok(wRetryEdge >= 3.0,
         "CON-139: the retry control is distinguishable from the card it sits on (" + _f(wRetryEdge) + ":1, 3:1 non-text bar) — the frame's own treatment measures 1.07:1");

      // (4) can_retry FALSE — the affordance must not exist.
      await wHealth({state:"unavailable", provider:null, error:"Microphone is in use by another application.", can_retry:false});
      ok(!wHBox.hidden && wHRetry.hidden,
         "CON-139: when the host says can_retry is FALSE the retry control is not rendered at all");

      // (5) UNSUPPORTED — a build fact, not a scare.
      await wHealth({state:"unsupported", provider:null, error:null, can_retry:false});
      ok(!wHBox.hidden && wHBox.classList.contains("det-health-quiet"),
         "CON-139 (premise): 'unsupported' renders in the QUIET treatment, not the amber fault card — the fixture reached 'unsupported'");
      ok(wHRetry.hidden, "CON-139: no retry is offered in 'unsupported' — the host cannot even construct the permission to honour it");

      // (6) UNKNOWN — the case the NO SIGNAL fallthrough gets wrong.
      window.__detHealthFail = true;
      await window.__detHealthRefresh();
      ok(!wHBox.hidden && wHBox.classList.contains("det-health-quiet"),
         "CON-139 (premise): an unreported detector renders quietly — the fixture reached UNKNOWN");
      ok(/unknown/i.test(wHTitle.textContent) && !/unavailable/i.test(wHTitle.textContent),
         "TRI-STATE: absent telemetry renders as UNKNOWN, never as a fault (\"" + wHTitle.textContent + "\")");
      ok(wHTitle.textContent !== "" && !wHBox.classList.contains("det-health-fault"),
         "TRI-STATE: ...and it is not silently treated as healthy either — both wrong readings collapse three states into two");
      window.__detHealthFail = false;

      // (7) retry calls the host, and a refusal survives the 1 Hz re-render.
      await wHealth({state:"unavailable", provider:null, error:"Audio device disappeared.", can_retry:true});
      window.__detRetryRefuse = "Retry does not apply while detection is 'idle'.";
      var wRtN = window.__calls.filter(function(c){ return c.cmd === "retry_detection"; }).length;
      wHRetry.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "retry_detection"; }).length > wRtN; }),
         "CON-139: the retry control calls retry_detection on the host");
      ok(await wWait(function(){ return /does not apply/i.test(wHBody.textContent); }),
         "CON-139: a refused retry shows the HOST'S reason");
      await window.__detHealthRefresh();
      ok(/does not apply/i.test(wHBody.textContent),
         "CON-139: the refusal SURVIVES the next poll's re-render — written straight to the DOM it would vanish within a second of appearing");
      window.__detRetryRefuse = null;
      wHRetry.click();
      ok(await wWait(function(){ return wHBox.hidden; }),
         "CON-139: a successful retry recovers, and the stale refusal is not left showing beside the recovered state");
      window.__detHealth = null;

      // (8) 86akby7th PR #22 review (Vera, Medium): an engine-change / audio-dropped NOTE must
      // be visible even while detection rows exist. Previously it only rendered into
      // #det-empty-sub, which JS sets display:none the instant #detections-list is non-empty —
      // so a mid-sermon disclosure (the exact case that matters) was literally unreachable on
      // screen. Reproduced here with a REAL detection row present, not the empty state.
      // Defensive reset (CON-136/137/138 introduced session-persistent, reference-keyed state
      // earlier in this suite) — this section must render Psalm 23:1 as a normal detection row
      // regardless of what any earlier section did with the same stock reference string.
      window.__detResetForTest();
      render(Object.assign({}, baseView, { detections: [
        { id: 7001, reference: "Psalm 23:1", text: "The Lord is my shepherd", confidence: 90 },
      ] }));
      ok(getComputedStyle(el("detections-empty")).display === "none",
         "CON-128/139 (premise): with a detection row present, the empty state IS hidden — the exact condition that swallowed the note before this fix");
      var wNoteEl = el("det-engine-note");
      ok(!!wNoteEl, "CON-128/139: a dedicated, always-checked element carries the engine note");
      await wHealth({state:"listening", provider:"deepgram-nova-3", error:null, can_retry:false,
                     note:"Cloud transcription could not be reached. The transcript below is coming from the on-device engine instead."});
      ok(!wNoteEl.hidden && getComputedStyle(wNoteEl).display !== "none",
         "CON-128/139: the note is VISIBLE even though the empty state (where it used to render) is hidden by the detection row above");
      ok(/on-device engine instead/.test(wNoteEl.textContent),
         "CON-128/139: the note text matches the host's disclosure verbatim");
      // Clearing the note hides the element again — never a stale disclosure with nothing to say.
      await wHealth({state:"listening", provider:"deepgram-nova-3", error:null, can_retry:false, note:null});
      ok(wNoteEl.hidden, "CON-128/139: a null note hides the element rather than leaving stale text behind");
      window.__detHealth = null;
      render(baseView); // restore — clears the fixture detection row for what follows

      // --- PME-058 / Q-08: the delete confirm must state the SLIDE COUNT, and must not promise
      // reversibility the host cannot deliver. The interesting case is NOT the one where the count
      // is known — it is the ABSENT one. A naive "it says 2 slides" check passes happily while an
      // unknown count renders as a confidently wrong "its 0 slides".
      var wOpenDel = async function(){
        el("pm-deckswitch").click();
        if (!(await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots"); }))) return null;
        el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots").click();
        if (!(await wWait(function(){ return !!el("pm-lib-menu"); }))) return null;
        var items = Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button"));
        var del = items.filter(function(b){ return /^Delete/.test(b.textContent); })[0];
        if (!del) return null;
        del.click();
        if (!(await wWait(function(){ return !!document.querySelector(".pm-confirm-body"); }))) return null;
        return document.querySelector(".pm-confirm-body").textContent.replace(/\s+/g, " ").trim();
      };
      var wCloseDel = function(){
        var back = document.querySelector(".pm-confirm-back");
        if (!back) return;
        var cancel = Array.prototype.slice.call(back.querySelectorAll("button")).filter(function(b){ return /Cancel/i.test(b.textContent); })[0];
        if (cancel) cancel.click(); else back.remove();
      };
      // The deck the driver will ACTUALLY act on: the first RENDERED card, read by its data-id.
      // Deriving it from LIB order instead was a real fixture bug — the grid sorts by NAME, so the
      // fixture named one deck while the UI deleted another, and a check about "the deck that was
      // not retained" was quietly reporting on a different deck. A fixture that does not reach the
      // condition its check names is worth less than no check.
      var wFirstDeck = function(){
        var card = el("pm-lib-grid") && el("pm-lib-grid").querySelector(".pm-lib-card");
        if (!card) return null;
        var id = Number(card.dataset.id);
        return window.__LIB.decks.filter(function(d){ return d.id === id; })[0] || null;
      };
      el("pm-deckswitch").click();
      await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
      if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      var wD = wFirstDeck();
      if (wD) {
        wD.slides = 7;
        var wBody7 = await wOpenDel();
        ok(!!wBody7 && /its 7 slides/.test(wBody7),
           "PME-058: the delete confirm names the SLIDE COUNT (\"" + String(wBody7).slice(0, 70) + "\")");
        wCloseDel();
        wD.slides = 1;
        var wBody1 = await wOpenDel();
        ok(!!wBody1 && /its 1 slide\b/.test(wBody1) && !/1 slides/.test(wBody1),
           "PME-058: a one-slide presentation reads \"its 1 slide\", not \"1 slides\"");
        wCloseDel();
        // THE CASE THAT MATTERS: the host did not report a count.
        delete wD.slides;
        var wBodyU = await wOpenDel();
        ok(!!wBodyU && /its slides/.test(wBodyU),
           "PME-058: an UNKNOWN slide count falls back to \"its slides\" (\"" + String(wBodyU).slice(0, 70) + "\")");
        ok(!!wBodyU && !/\b0 slides?\b/.test(wBodyU) && !/undefined/.test(wBodyU) && !/NaN/.test(wBodyU),
           "PME-058: an unknown count is never rendered as a confident \"0 slides\"/undefined/NaN — vague beats fabricated");
        // Q-08 honesty invariant: the PROMISE and the BEHAVIOUR must agree. The host has no restore
        // path today (no deck_export/deck_import/deck_restore; DeckLibrary::delete is a hard drop),
        // so the copy must say so. When the seam lands and an Undo appears, this check goes RED and
        // forces the sentence to be corrected with it — in either direction the product cannot lie.
        // Q-08, flipped. deck_restore + a bounded trash shipped, so "can't be undone" is now FALSE.
        ok(!/can.t be undone/i.test(wBodyU || ""),
           "Q-08: the confirm no longer claims the delete is irreversible — deck_restore exists");
        ok(!/you can undo/i.test(wBodyU || ""),
           "Q-08: ...and it does not promise undo either: whether THIS deck is retained depends on its size against the trash budget, which is not knowable at confirm time. The promise is made where it can be verified");
        wCloseDel();
        wD.slides = 3;
        var wDoDelete = async function(){
          el("pm-deckswitch").click();
          if (!(await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots"); }))) return false;
          if (!(await wOpenDel())) return false;
          var back = document.querySelector(".pm-confirm-back");
          var go = back ? Array.prototype.slice.call(back.querySelectorAll("button")).filter(function(b){ return /^Delete$/.test(b.textContent.trim()); })[0] : null;
          if (!go) return false;
          go.click();
          return await wWait(function(){ return !el("pm-toast").hidden; });
        };
        // THE PROPERTY, capability-aware: Undo is offered IF AND ONLY IF the host reports this deck
        // as restorable. The previous version compared the copy against the webview's OWN behaviour,
        // which stayed self-consistent — and therefore GREEN — when the host gained a capability the
        // UI was not using. This version fails in that case.
        var wTarget = wFirstDeck(), wTargetId = wTarget && wTarget.id, wTargetName = wTarget && wTarget.name;
        window.__deckNoRetain = null;
        ok(await wDoDelete(), "Q-08 (setup): a restorable delete completes");
        var wRestorableNow = (window.__LIB.trash || []).some(function(t){ return t.id === wTargetId; });
        var wUndoShown = !!el("pm-toast").querySelector(".pm-toast-action");
        ok(wRestorableNow && wUndoShown,
           "Q-08: a RESTORABLE delete offers Undo (host restorable=" + wRestorableNow + ", Undo offered=" + wUndoShown + ")");
        // The restored name must be the host's, not the remembered one. Make the old name be taken
        // first, so restore genuinely uniquifies — a fixture that never reaches the rename would
        // let a "shows the right name" check pass while showing the wrong one.
        await invoke("deck_new", { name: wTargetName });
        var wRestN = window.__calls.filter(function(c){ return c.cmd === "deck_restore"; }).length;
        el("pm-toast").querySelector(".pm-toast-action").click();
        ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_restore"; }).length > wRestN; }),
           "Q-08: Undo calls deck_restore on the host — the client cannot rebuild the slides itself");
        await wWait(function(){ return /Restored/.test(el("pm-toast").textContent); });
        var wToastTxt = el("pm-toast").textContent;
        var wBackName = (window.__LIB.decks.filter(function(d){ return d.id === wTargetId; })[0] || {}).name;
        ok(/\(2\)/.test(wBackName || ""),
           "Q-08 (premise): the fixture really reached the RENAME path — the deck came back as \"" + wBackName + "\", not its original name");
        ok(wToastTxt.indexOf(wBackName) >= 0,
           "Q-08: the confirmation quotes the name the deck came back UNDER (\"" + wBackName + "\"), not the one that was deleted");
        // THE CASE THAT MATTERS: a delete the host did NOT retain must offer no Undo at all.
        var wBig = wFirstDeck();
        if (wBig) {
          window.__deckNoRetain = wBig.id;
          ok(await wDoDelete(), "Q-08 (setup): a non-retained delete completes");
          var wRetained = (window.__LIB.trash || []).some(function(t){ return t.id === wBig.id; });
          var wUndoShown2 = !!el("pm-toast").querySelector(".pm-toast-action");
          ok(!wRetained && !wUndoShown2,
             "Q-08: a delete the host could NOT retain offers no Undo (restorable=" + wRetained + ", Undo offered=" + wUndoShown2 + ") — an affordance that would fail is a new fabrication, not a courtesy");
          window.__deckNoRetain = null;
        }
        // A refusal is a rejected promise with the host's OWN reason: the affordance was valid when
        // shown, but the trash aged out before the operator reached for it.
        var wT2 = wFirstDeck();
        if (wT2) {
          ok(await wDoDelete(), "Q-08 (setup): a third delete completes so Undo is on screen");
          var wAct = el("pm-toast").querySelector(".pm-toast-action");
          if (wAct) {
            window.__LIB.trash.length = 0; // it ages out between offer and click
            if (el("pm-error-dismiss") && !el("pm-error").hidden) el("pm-error-dismiss").click();
            wAct.click();
            ok(await wWait(function(){ return !el("pm-error").hidden; }),
               "Q-08: a refused restore surfaces an error rather than failing silently");
            ok(/no longer be restored/i.test(el("pm-error-msg").textContent),
               "Q-08: it shows the HOST'S own reason (\"" + el("pm-error-msg").textContent.slice(0, 60) + "\"), not a generic \"couldn't do that, retry\" for something retrying cannot fix");
            if (el("pm-error-dismiss")) el("pm-error-dismiss").click();
          }
        }
      }

      // --- PME-055: "Present" in the library card \u22ef menu ----------------------------------
      // PME-014's topbar \u25b6 Present only ever acts on the OPEN deck; this is the OTHER half of
      // the finding \u2014 presenting a deck straight off its card, without first making it the open
      // deck in the editor. Deliberately picks a card that is NOT already open, so a pass here
      // cannot be explained by the button silently riding the topbar's open-deck-only Present.
      el("pm-deckswitch").click();
      await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
      if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      var wPresCards = Array.prototype.slice.call(el("pm-lib-grid").querySelectorAll(".pm-lib-card"));
      var wPresCard = wPresCards.filter(function(c){ return !c.classList.contains("open"); })[0] || wPresCards[0];
      ok(!!wPresCard, "PME-055 (premise): a presentation card exists to test Present on");
      if (wPresCard) {
        var wPresDeckId = Number(wPresCard.dataset.id);
        wPresCard.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        var wPresMenuItems = Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button"));
        var wPresItem = wPresMenuItems.filter(function(b){ return /^Present$/.test(b.textContent.trim()); })[0];
        ok(!!wPresItem, "PME-055: the card \u22ef menu carries a 'Present' item (Open \u00b7 Rename\u2026 \u00b7 Duplicate \u00b7 Present \u00b7 \u2014 \u00b7 Delete)");
        if (wPresItem) {
          var wDoN = window.__calls.filter(function(c){ return c.cmd === "deck_open" && c.args.id === wPresDeckId; }).length;
          var wGlN3 = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
          wPresItem.click();
          ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_open" && c.args.id === wPresDeckId; }).length > wDoN; }),
             "PME-055: 'Present' opens the CARD'S OWN deck (deck_open), not the deck already open in the editor");
          ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length > wGlN3; }),
             "PME-055: 'Present' actually goes live (deck_go_live) \u2014 not just a navigation to the grid");
          ok(await wWait(function(){ return !el("pm-grid").hidden; }),
             "PME-055: 'Present' lands the operator on the slide grid, where the presented slide is visible");
        }
      }

      // --- 17tnw2axwve: deck-scoped pmThumbCache / LIVE ring — cross-deck local-slide-id
      // collision --------------------------------------------------------------------------------
      // Slide ids are DECK-LOCAL (each deck numbers its own slides from scratch —
      // selahcue-present::deck.rs) — two decks routinely share a local id (both fixture decks
      // below use "1"). Before the fix, pmThumbCache keyed purely by the bare slide id and
      // pmGridSyncLive matched the LIVE ring purely against view().live_authored_id (also a bare
      // id), so switching decks could paint the WRONG deck's cached thumbnail or ring the WRONG
      // deck's tile as live. Snapshots and fully restores D / window.__LIB / V.live_authored_id
      // around itself so nothing leaks into the PME-053 block (which reads
      // window.__LIB.decks.length directly) or anything that runs after it.
      var wCollSnapD = JSON.parse(JSON.stringify(D));
      var wCollSnapLib = JSON.parse(JSON.stringify(window.__LIB));
      var wCollSnapLive = V.live_authored_id;
      var wCollSnapLiveIndex = V.live_index;
      var wCollSnapConsoleDeckPreview = window.__consoleDeckPreview || null;
      var wCollDeckX = 70001, wCollDeckY = 70002;
      window.__LIB.decks.push({id: wCollDeckX, name: "Collision Deck X", slides: 1,
        content: [{id: 1, n: 1, lines: ["Deck X — Slide One"], kind: "text"}]});
      window.__LIB.decks.push({id: wCollDeckY, name: "Collision Deck Y", slides: 1,
        content: [{id: 1, n: 1, lines: ["Deck Y — Slide One"], kind: "text"}]});
      var wCollGoToLibrary = async function(){
        el("pm-deckswitch").click();
        await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
        if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      };
      var wCollOpenById = function(deckId){
        var card = el("pm-lib-grid").querySelector('.pm-lib-card[data-id="' + deckId + '"]');
        if (card) card.querySelector(".pm-lib-open").click();
        return !!card;
      };
      var wCollPresentById = async function(deckId){
        var card = el("pm-lib-grid").querySelector('.pm-lib-card[data-id="' + deckId + '"]');
        if (!card) return false;
        card.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        var items = Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button"));
        var presentItem = items.filter(function(b){ return /^Present$/.test(b.textContent.trim()); })[0];
        if (!presentItem) return false;
        presentItem.click();
        return true;
      };
      var wCollTilePixel = function(slideId){
        var tile = el("pm-grid-tiles") && el("pm-grid-tiles").querySelector('.pm-tile[data-id="' + slideId + '"]');
        var cv = tile && tile.querySelector("canvas");
        return cv ? Array.prototype.join.call(cv.getContext("2d").getImageData(0, 0, 1, 1).data, ",") : null;
      };
      // Counts only GRID per-tile thumbnail fetches (a real numeric slide id), never the EDITOR's
      // own single-slide canvas preview (pmRenderCanvas calls render_deck_slide with id:null on
      // EVERY successful deck action via pAct/renderPresentation, entirely unrelated to
      // pmThumbCache) — conflating the two would make a genuine grid cache-hit look like a miss
      // whenever a go-live (pmGridGoLive, which pmLibPresent triggers) fires in the same step.
      var wCollRenderCalls = function(){ return window.__calls.filter(function(c){ return c.cmd === "render_deck_slide" && c.args && c.args.id != null; }).length; };

      // Open Deck X fresh: its slide-1 thumbnail must render via a genuine render_deck_slide call.
      await wCollGoToLibrary();
      var wCollN0 = wCollRenderCalls();
      ok(wCollOpenById(wCollDeckX), "17tnw2axwve (premise): Deck X's library card is reachable");
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await wWait(function(){ return wCollRenderCalls() > wCollN0; });
      await sleep(30);
      var wCollPixelX = wCollTilePixel(1);
      ok(wCollPixelX != null, "17tnw2axwve (premise): Deck X's tile 1 renders a thumbnail");

      // Switch to Deck Y via the plain "Open" affordance (pmLibOpen) — a fresh deck, so slide 1
      // must render via ITS OWN render_deck_slide call and show ITS OWN colour, not Deck X's.
      await wCollGoToLibrary();
      var wCollN1 = wCollRenderCalls();
      wCollOpenById(wCollDeckY);
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await wWait(function(){ return wCollRenderCalls() > wCollN1; });
      await sleep(30);
      var wCollPixelY = wCollTilePixel(1);
      ok(wCollPixelY != null && wCollPixelY !== wCollPixelX,
         "17tnw2axwve: switching to Deck Y (pmLibOpen) shows Deck Y's OWN slide-1 thumbnail, not Deck X's stale cached one (X=" + wCollPixelX + ", Y=" + wCollPixelY + ")");

      // Switch BACK to Deck X via the card menu's "Present" action (pmLibPresent — the OTHER
      // deck-switch path) — must be a genuine cache HIT (no new render_deck_slide call) showing
      // Deck X's own correct colour again, proving option (b)'s benefit as well as correctness.
      await wCollGoToLibrary();
      var wCollN2 = wCollRenderCalls();
      var wCollPresentOk = await wCollPresentById(wCollDeckX);
      ok(wCollPresentOk, "17tnw2axwve (premise): Deck X's card carries a working 'Present' menu item");
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await sleep(60);
      var wCollN3 = wCollRenderCalls();
      var wCollPixelXAgain = wCollTilePixel(1);
      ok(wCollN3 === wCollN2,
         "17tnw2axwve: switching back to Deck X (pmLibPresent) hits the thumbnail cache — no new render_deck_slide call (option (b): a deck-scoped key, not clear-on-switch, preserves already-fetched thumbnails)");
      ok(wCollPixelXAgain === wCollPixelX,
         "17tnw2axwve: the cache-hit thumbnail for Deck X's slide 1 is still Deck X's own colour, not Deck Y's (got " + wCollPixelXAgain + ")");

      // LIVE-ring collision: pmLibPresent above already presented Deck X's slide 1 live; confirm its
      // own tile shows the ring, then switch (plain Open — no present) to Deck Y and confirm Deck
      // Y's OWN slide-1 tile does NOT inherit a false LIVE ring for Deck X's actually-live slide,
      // despite the colliding local id.
      ok(!!el("pm-grid-tiles").querySelector(".pm-tile.live"), "17tnw2axwve (premise): Deck X's slide 1 is presented live (its own tile rings) after Present");
      await wCollGoToLibrary();
      wCollOpenById(wCollDeckY);
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await sleep(80); // let pmGridSyncLive's async view() round-trip resolve
      ok(!el("pm-grid-tiles").querySelector(".pm-tile.live"),
         "17tnw2axwve: Deck Y's tile 1 does NOT show a false LIVE ring for Deck X's actually-live slide 1, despite the colliding local id");

      // A→B→A regression (Sana + Quinn, PR #92 review round 1): switching BACK to Deck X (plain
      // Open, no re-present) must still show its LIVE ring — X never stopped being the actually-
      // live deck, only the grid's VIEW moved away and back. The FIRST attempt at this fix gated
      // the ring on dv.live (DeckWorkspace.live), which deck_workspace.rs::load_deck resets on
      // EVERY real deck switch — including switching back — so it broke the single most routine
      // operator action (glance at another deck, come back), not just a rare cold-boot edge case
      // as first assumed. This is the check that would have caught that.
      await wCollGoToLibrary();
      wCollOpenById(wCollDeckX);
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await sleep(80); // let pmGridSyncLive's async view() round-trip resolve
      ok(!!el("pm-grid-tiles").querySelector(".pm-tile.live"),
         "17tnw2axwve: switching BACK to Deck X (plain Open, no re-present) still shows its LIVE ring — X never stopped being live, only the view moved away and back (A→B→A)");

      // Positive control: the gate suppresses a false CROSS-deck match, not the ring mechanism
      // itself — presenting Deck Y's OWN slide 1 must still correctly ring it.
      await wCollGoToLibrary();
      wCollOpenById(wCollDeckY);
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      var wCollTileY1 = el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]');
      wCollTileY1.dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await wWait(function(){ return el("pm-grid-tiles").querySelector(".pm-tile.live"); });
      ok(!!el("pm-grid-tiles").querySelector(".pm-tile.live"),
         "17tnw2axwve (control): presenting Deck Y's OWN slide 1 afterward still correctly rings it — the ring gate suppresses a false cross-deck match, not the ring mechanism itself");

      // Cross-surface (Sana, PR #92 review round 1): a deck slide presented from the Service Plan /
      // Live Console surface (present_plan_deck_slide, main.rs — a SECOND, entirely separate path
      // to live_authored_id that never touches DeckWorkspace.live at all) must be recognised by the
      // Presentation grid's LIVE ring too. window.__consoleDeckPreview is the real app.js-owned
      // state the console's goLive() reads (set for real by its own staging render path elsewhere
      // in this suite, e.g. the "SP:" block above) — set directly here to drive goLive() itself
      // (the actual code this ticket's round-1 fix touched) via a real click, without re-deriving
      // the full Service Plan staging UI flow.
      window.__consoleDeckPreview = { deckId: wCollDeckX, slideId: 1 };
      var wCollCpN0 = window.__calls.filter(function(c){ return c.cmd === "present_plan_deck_slide"; }).length;
      el("golive").click();
      await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "present_plan_deck_slide"; }).length > wCollCpN0; });
      await sleep(60);
      await wCollGoToLibrary();
      wCollOpenById(wCollDeckX);
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await sleep(80);
      ok(!!el("pm-grid-tiles").querySelector(".pm-tile.live"),
         "17tnw2axwve: a deck slide presented from the Service Plan / Live Console (present_plan_deck_slide) is recognised by the Presentation grid's LIVE ring too — not just grid-driven presents");

      // pmGridDeckId staleness at the deck-CREATE path (Sana + Cody + Vera, PR #92 review round 1,
      // independently found and reproduced live by all three): "+ New presentation" → Blank deck
      // (app.js pmNewDeck) lands STRAIGHT IN THE EDITOR, bypassing pmRenderGrid entirely — the only
      // place pmGridDeckId was previously written. The "Done" handler then rendered the BRAND-NEW
      // deck's grid keyed under whatever deck the grid last showed. Cody proved this is not
      // hypothetical: reproduced live with zero new render_deck_slide fetches and the new deck's
      // tile byte-identical to a different deck's cached tile. DeckView carries no id field
      // (deck_workspace.rs), so this can't be fixed by threading an id through pmNewDeck's own two
      // branches alone (confirmed: the mock's deck_new response, like the real one, has no id) — the
      // fix instead makes "Done" ask deck_list for ground truth (its `open` field is computed live
      // from ws.open_deck().id() on every call).
      await wCollGoToLibrary();
      wCollOpenById(wCollDeckY); // leaves pmGridDeckId = wCollDeckY, a KNOWN, different deck
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await sleep(30);
      var wCollPixelYForNewCheck = wCollTilePixel(1);
      ok(wCollPixelYForNewCheck != null, "17tnw2axwve (premise): Deck Y's tile 1 has a cached thumbnail going into the deck-create staleness check");
      await wCollGoToLibrary();
      el("pm-lib-new").click();
      await wWait(function(){ return !!el("pm-prompt-input"); });
      el("pm-prompt-input").value = "Blank Deck For Staleness Check";
      Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
      await wWait(function(){ return el("pm-library").hidden; }); // lands in the EDITOR, not the grid
      var wCollNewDeckId = window.__LIB.open;
      ok(wCollNewDeckId != null && wCollNewDeckId !== wCollDeckY && wCollNewDeckId !== wCollDeckX,
         "17tnw2axwve (premise): '+ New presentation' opened a genuinely NEW deck (id " + wCollNewDeckId + "), distinct from Deck Y");
      var wCollN4 = wCollRenderCalls();
      if (el("pm-done")) el("pm-done").click(); // editor → grid
      await wWait(function(){ return !el("pm-grid").hidden && !!el("pm-grid-tiles").querySelector('.pm-tile[data-id="1"]'); });
      await wWait(function(){ return wCollRenderCalls() > wCollN4; }); // a genuinely new deck must MISS the cache
      await sleep(30);
      var wCollNewDeckPixel = wCollTilePixel(1);
      ok(wCollNewDeckPixel != null && wCollNewDeckPixel !== wCollPixelYForNewCheck,
         "17tnw2axwve: after '+ New presentation' (Blank deck, lands straight in the editor) and Done, the new deck's tile 1 shows ITS OWN thumbnail, not Deck Y's stale cached one (new=" + wCollNewDeckPixel + ", Y=" + wCollPixelYForNewCheck + ")");

      // --- 17tnw2axwve (bounded memory): the deck-scoped key widened pmThumbCache's KEY SPACE from
      // "every slide id" to "every (deck, slide) pair ever visited this session". The cap must
      // still be GLOBAL — PM_THUMB_MAX total entries across all decks — never per-deck, and never
      // decks x PM_THUMB_MAX. Drive strictly MORE distinct (deck, slide) pairs than the cap through
      // the real UI and assert the entity (entry count) plus a NAMED key evicted / a NAMED key
      // retained. Per-key accessor (window.__pmGridDebug.cached), never a global counter.
      var wBmDecks = [], wBmPerDeck = 10, wBmBase = 71000;
      var wBmCap = window.__pmGridDebug.max();
      var wBmNeeded = Math.ceil((wBmCap + 1) / wBmPerDeck);   // enough decks to strictly EXCEED the cap
      for (var wBmI = 0; wBmI < wBmNeeded; wBmI++) {
        var wBmId = wBmBase + wBmI, wBmContent = [];
        // All wBmPerDeck slides sit inside pmRenderGrid's eager first fold (i < 12), so every one
        // is really fetched and really cached — no IntersectionObserver dependence.
        for (var wBmS = 1; wBmS <= wBmPerDeck; wBmS++) wBmContent.push({id: wBmS, n: wBmS, lines: ["D" + wBmId + " S" + wBmS], kind: "text"});
        wBmDecks.push(wBmId);
        window.__LIB.decks.push({id: wBmId, name: "Bounded Deck " + wBmI, slides: wBmPerDeck, content: wBmContent});
      }
      var wBmPairs = wBmNeeded * wBmPerDeck;
      // Pin the premise: if PM_THUMB_MAX ever grows past what this block drives, the bound
      // assertion below would pass vacuously (nothing would ever be evicted). Fail loudly instead.
      ok(wBmPairs > wBmCap,
         "17tnw2axwve (bounded memory, premise): this check drives " + wBmPairs + " distinct (deck, slide) pairs, strictly MORE than the PM_THUMB_MAX cap of " + wBmCap + " — so the cap is genuinely exercised and the bound assertion is not vacuous");
      for (var wBmJ = 0; wBmJ < wBmDecks.length; wBmJ++) {
        await wCollGoToLibrary();
        wCollOpenById(wBmDecks[wBmJ]);
        await wWait(function(){ return !el("pm-grid").hidden && el("pm-grid-tiles").querySelectorAll(".pm-tile").length === wBmPerDeck; });
        await sleep(40);
      }
      var wBmFirstDeck = wBmDecks[0], wBmLastDeck = wBmDecks[wBmDecks.length - 1];
      // Non-vacuity: the cache really was populated by this walk — assert a NAMED recent key is
      // present BEFORE asserting the bound, so "size <= cap" cannot pass because nothing got in.
      ok(window.__pmGridDebug.cached(wBmLastDeck, wBmPerDeck) !== null,
         "17tnw2axwve (bounded memory, premise): the most recently visited deck's last slide IS cached after the walk — the cache was actually populated, so the bound below is not passing on an empty map");
      ok(window.__pmGridDebug.size() <= wBmCap,
         "17tnw2axwve (bounded memory): after visiting " + wBmDecks.length + " DISTINCT decks (" + wBmPairs + " distinct (deck, slide) pairs), pmThumbCache holds " + window.__pmGridDebug.size() + " entries — bounded GLOBALLY at PM_THUMB_MAX=" + wBmCap + ", not per-deck and not decks x cap");
      ok(window.__pmGridDebug.cached(wBmFirstDeck, 1) === null,
         "17tnw2axwve (bounded memory): the FIRST-visited deck's slide 1 was evicted — the oldest entries are the ones dropped, i.e. eviction really happened rather than the walk merely fitting under the cap");
      // Positive control: the cap evicts, it does not disable the cache. A deck visited most
      // recently must still be a genuine HIT (no fresh render_deck_slide) when reopened.
      await wCollGoToLibrary();
      var wBmN0 = wCollRenderCalls();
      wCollOpenById(wBmLastDeck);
      await wWait(function(){ return !el("pm-grid").hidden && el("pm-grid-tiles").querySelectorAll(".pm-tile").length === wBmPerDeck; });
      await sleep(60);
      ok(wCollRenderCalls() === wBmN0,
         "17tnw2axwve (bounded memory, control): reopening the most recently visited deck still HITS the cache with no new render_deck_slide call — the cap evicts old entries, it does not render the cache dead");

      // Restore D / window.__LIB / V.live_authored_id / V.live_index / window.__consoleDeckPreview
      // so nothing leaks into PME-053 or any later check.
      Object.assign(D, JSON.parse(JSON.stringify(wCollSnapD)));
      window.__LIB.decks = wCollSnapLib.decks;
      window.__LIB.open = wCollSnapLib.open;
      window.__LIB.nextId = wCollSnapLib.nextId;
      window.__LIB.persistent = wCollSnapLib.persistent;
      window.__LIB.trash = wCollSnapLib.trash;
      V.live_authored_id = wCollSnapLive;
      V.live_index = wCollSnapLiveIndex;
      window.__consoleDeckPreview = wCollSnapConsoleDeckPreview;

      // --- PME-053: "Start from" in the New-presentation dialog -------------------------------
      // Blank deck / Duplicate an existing presentation / From a template (later, honestly
      // disabled \u2014 no template model exists yet, PME-052/OUT-009).
      el("pm-deckswitch").click();
      await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
      if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      el("pm-lib-new").click();
      await wWait(function(){ return !!el("pm-prompt-input"); });
      var wSfGroup = document.querySelector(".pm-startfrom");
      ok(!!wSfGroup && wSfGroup.getAttribute("role") === "radiogroup", "PME-053: the New-presentation dialog carries a 'Start from' radiogroup");
      var wSfBlank = document.getElementById("pm-startfrom-blank"), wSfDup = document.getElementById("pm-startfrom-dup"), wSfTpl = document.getElementById("pm-startfrom-tpl");
      ok(!!wSfBlank && wSfBlank.checked, "PME-053: 'Blank deck' is the default selection");
      ok(!!wSfDup && !wSfDup.disabled, "PME-053: 'Duplicate an existing presentation' is available (the library is non-empty)");
      ok(!!wSfTpl && wSfTpl.disabled, "PME-053: 'From a template' is an honest disabled 'later' affordance, not a broken live control");
      var wSfPicker = document.querySelector(".pm-startfrom-picker");
      // Check COMPUTED display, not just the DOM `hidden` property: an author `display` rule
      // (here .pm-startfrom-picker's own `display: flex`) can defeat the [hidden] attribute in
      // WKWebView/Chrome without an explicit `[hidden] { display: none }` override — the exact
      // trap .td-bgpanel[hidden] etc. already guard against elsewhere in app.css. Checking only
      // `.hidden` (the DOM property) passes even when the element is still visually painted, which
      // is precisely how this shipped broken once already (Quinn, PR #69 review — 17tnw2axwg9).
      ok(!!wSfPicker && wSfPicker.hidden && getComputedStyle(wSfPicker).display === "none",
         "PME-053 (premise): the duplicate-source picker starts hidden under the default 'Blank deck' choice (hidden=" + (wSfPicker && wSfPicker.hidden) + ", computed display=" + (wSfPicker && getComputedStyle(wSfPicker).display) + ")");
      if (wSfDup) {
        wSfDup.click();
        ok(!wSfPicker.hidden && getComputedStyle(wSfPicker).display !== "none" && wSfPicker.getClientRects().length > 0,
           "PME-053: choosing 'Duplicate an existing presentation' reveals the deck picker (computed display=" + getComputedStyle(wSfPicker).display + ", painted rects=" + wSfPicker.getClientRects().length + ")");
        var wSfRows = wSfPicker.querySelectorAll(".pm-startfrom-picker-row");
        ok(wSfRows.length === window.__LIB.decks.length, "PME-053: the picker lists one row per existing presentation (" + wSfRows.length + " of " + window.__LIB.decks.length + ")");
        // Pick a row OTHER than the pre-selected first one, so a pass proves selecting a row
        // actually changes which deck gets duplicated \u2014 not that the default happened to work.
        var wSfRow = Array.prototype.slice.call(wSfRows).filter(function(r){ return !r.querySelector("input").checked; })[0] || wSfRows[0];
        var wSfSrcId = Number(wSfRow.querySelector("input").value);
        var wSfSrcDeck = window.__LIB.decks.filter(function(d){ return d.id === wSfSrcId; })[0];
        wSfRow.querySelector("input").click();
        ok(el("pm-prompt-input").value === (wSfSrcDeck.name + " copy"),
           "PME-053: the Name field follows the chosen source (\"" + el("pm-prompt-input").value + "\") until the operator types their own");
        el("pm-prompt-input").value = "My Copied Deck";
        el("pm-prompt-input").dispatchEvent(new Event("input", {bubbles:true}));
        var wSfDupN = window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).length;
        Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
        ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).length > wSfDupN; }),
           "PME-053: confirming 'Duplicate' drives deck_duplicate(the CHOSEN source's id)");
        var wSfDupCall = window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).slice(-1)[0];
        ok(!!wSfDupCall && wSfDupCall.args.id === wSfSrcId, "PME-053: deck_duplicate is called with the SELECTED row's id (" + wSfSrcId + "), not the first/default one");
        // Each step of onConfirm's deck_duplicate -> deck_rename -> deck_open chain is a
        // separately-awaited invoke; polling (wWait) rather than checking window.__calls
        // synchronously avoids racing a still-pending later step in the chain.
        ok(await wWait(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_rename" && c.args.name === "My Copied Deck"; }); }),
           "PME-053: the typed name renames the COPY (deck_rename), never the original");
        var wSfRenameCall = window.__calls.filter(function(c){ return c.cmd === "deck_rename" && c.args.name === "My Copied Deck"; }).slice(-1)[0];
        ok(!!wSfRenameCall && wSfRenameCall.args.id !== wSfSrcId,
           "PME-053: the rename targets the NEW deck's id, not the source deck's id");
        // The onConfirm chain is deck_duplicate -> deck_rename -> deck_open, three sequential
        // awaited invokes; wWait above only proves deck_duplicate fired. Poll for deck_open too
        // rather than checking window.__calls synchronously, which would race the still-pending
        // rename/open awaits and fail even when the implementation is correct.
        ok(await wWait(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_open" && c.args.id === wSfRenameCall.args.id; }); }),
           "PME-053: 'Create presentation' opens the newly-created copy in the editor");
        ok(await wWait(function(){ return el("pm-library").hidden; }), "PME-053: the dialog and Library close, landing the operator in the editor on the new deck");
      }

      // --- Cody (PR #69 review): a duplicate source that vanishes mid-dialog must not toast a
      // false "Presentation duplicated" success. deck_duplicate is a no-op when its source id no
      // longer resolves (another action deleted it between the picker rendering and Create being
      // pressed) — no new_id comes back, so nothing was actually created, and the flow must route
      // through the same failure path every other create failure in this dialog already uses.
      el("pm-deckswitch").click();
      await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
      if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      el("pm-lib-new").click();
      await wWait(function(){ return !!el("pm-prompt-input"); });
      var wVanDup = document.getElementById("pm-startfrom-dup");
      ok(!!wVanDup && !wVanDup.disabled, "Cody (PR #69) (premise): a duplicate source is selectable to test the vanished-mid-dialog case");
      if (wVanDup && !wVanDup.disabled) {
        wVanDup.click();
        var wVanRow = document.querySelector(".pm-startfrom-picker .pm-startfrom-picker-row input");
        var wVanSrcId = Number(wVanRow.value);
        wVanRow.click();
        // The race itself: another action removes the chosen source from the library between
        // selecting it here and pressing Create.
        window.__LIB.decks = window.__LIB.decks.filter(function(d){ return d.id !== wVanSrcId; });
        Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
        ok(await wWait(function(){ return !el("pm-error").hidden; }),
           "Cody (PR #69): a duplicate source that vanished mid-dialog surfaces the error banner, not a false-positive success toast");
        // Checked by TEXT, not by the toast's `hidden` state, so this cannot pass merely because
        // an unrelated earlier toast in this long-running script happens to still be showing.
        ok(!/duplicated/i.test(el("pm-toast").textContent || ""),
           "Cody (PR #69): ...and never claims \"Presentation duplicated\" over a request that created nothing (\"" + (el("pm-toast").textContent || "").slice(0, 40) + "\")");
        if (el("pm-error-dismiss") && !el("pm-error").hidden) el("pm-error-dismiss").click();
      }

      // --- PME-059: warn when the deck being deleted is referenced by a service-plan item -----
      el("pm-deckswitch").click();
      await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
      if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      var wPlanCards = Array.prototype.slice.call(el("pm-lib-grid").querySelectorAll(".pm-lib-card"));
      ok(wPlanCards.length >= 2, "PME-059 (premise): at least two presentations exist \u2014 one to link from the plan, one as a clean negative control");
      if (wPlanCards.length >= 2) {
        var wLinkedCard = wPlanCards[0], wCleanCard = wPlanCards[1];
        var wLinkedId = Number(wLinkedCard.dataset.id);
        var wSavedItems = V.items, wSavedPlanName = V.plan_name;
        V.items = wSavedItems.concat([{id:9001, kind:"slide_group", title:"Sermon slides", is_live:false, is_staged:false, link:{kind:"deck", id: wLinkedId}}]);
        V.plan_name = "Sunday Service \u2014 Aug 4";
        wLinkedCard.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /^Delete/.test(b.textContent); })[0].click();
        ok(await wWait(function(){ return !!document.querySelector(".pm-confirm-warn"); }),
           "PME-059: deleting a deck the service plan links shows a warning before the operator can confirm");
        var wWarnLinked = document.querySelector(".pm-confirm-warn");
        ok(!!wWarnLinked && /Sunday Service \u2014 Aug 4/.test(wWarnLinked.textContent) && /show missing/.test(wWarnLinked.textContent),
           "PME-059: the warning names the PLAN (\"" + (wWarnLinked ? wWarnLinked.textContent : "") + "\") and states the consequence \u2014 the linked plan item will show missing");
        var wWarnDlg = document.querySelector('.pm-confirm[role="alertdialog"]');
        ok(!!wWarnDlg && /pm-confirm-warn/.test(wWarnDlg.getAttribute("aria-describedby") || ""),
           "PME-059: the warning is wired into the dialog's accessible description, so a screen reader speaks it (WCAG 4.1.2)");
        wCloseDel();
        // Negative control: a deck NOT referenced by the plan gets no plan-reference warning \u2014
        // proves the check above is reading the actual link, not always drawing a warning.
        wCleanCard.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /^Delete/.test(b.textContent); })[0].click();
        await wWait(function(){ return !!document.querySelector(".pm-confirm-body"); });
        var wWarnClean = document.querySelector(".pm-confirm-warn");
        ok(!wWarnClean || !/show missing/.test(wWarnClean.textContent),
           "PME-059 (control): a deck NOT referenced by the plan shows no plan-reference warning");
        wCloseDel();
        // Sana + Vera (PR #69 review): a FAILED view() read must not collapse into the same
        // "no warning" shape as a genuinely clean read — that would let a delete through
        // silently on exactly the failure this check exists to survive. window.__viewRejectOnce
        // is consumed by pmLibDelete's own first `await invoke("view")`, triggered by the Delete
        // click below. There IS an `await wWait(...)` between setting the flag and that click
        // (Sana, PR #69 review round 2 — an earlier version of this comment wrongly claimed none)
        // — but the menu it waits for is built synchronously by the ⋯ click just before it, so
        // `wWait`'s very first check (before any real sleep) already sees it and resolves on that
        // same microtask turn: effectively 0 ms of wall-clock time, nowhere near the app's 1 Hz
        // view() poll's 1000 ms interval, so the poll has no practical chance to consume the flag
        // first.
        window.__viewRejectOnce = true;
        wLinkedCard.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /^Delete/.test(b.textContent); })[0].click();
        ok(await wWait(function(){ return !!document.querySelector(".pm-confirm-warn"); }),
           "Sana + Vera (PR #69): a FAILED plan-reference check still shows a warning — fails OPEN, never silently reading as \"not referenced\"");
        var wWarnFailed = document.querySelector(".pm-confirm-warn");
        ok(!!wWarnFailed && /couldn.t check/i.test(wWarnFailed.textContent),
           "Sana + Vera (PR #69): ...and the warning honestly says the check couldn't be completed, not a fabricated \"not referenced\" or a fabricated \"referenced\" (\"" + (wWarnFailed ? wWarnFailed.textContent : "") + "\")");
        wCloseDel();
        // Vera (PR #69 review, round 2): a REJECTED view() (above) is one failure mode; a
        // STALLED-BUT-CONNECTED host on Backend::Remote is another, and ControlClient::command
        // (selahcue-lan/src/client.rs) has no per-request timeout on this path — unlike
        // connect/pair, which do. Without a client-side bound, this would hang the whole delete
        // flow forever: no spinner, no error, nothing. window.__viewHangOnce makes the mock's
        // view() promise never settle at all; the only way this test can pass is if
        // pmLibDelete's own PM_VIEW_TIMEOUT_MS actually fires and moves the UI on.
        window.__viewHangOnce = true;
        wLinkedCard.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /^Delete/.test(b.textContent); })[0].click();
        ok(await waitFor(function(){ return !!document.querySelector(".pm-confirm-warn"); }, 100),
           "Vera (PR #69, round 2): a STALLED (never-resolving) plan-reference check does not hang forever — the client-side timeout fires and the dialog still shows a warning");
        var wWarnHung = document.querySelector(".pm-confirm-warn");
        ok(!!wWarnHung && /couldn.t check/i.test(wWarnHung.textContent),
           "Vera (PR #69, round 2): ...with the same honest \"couldn't check\" copy as a rejected read, not a fabricated verdict");
        wCloseDel();
        // Sana (PR #69 review, round 2): "linked" and "the plan has a reported name" are TWO
        // separate facts that the original fix conflated into one `if` — a genuinely linked deck
        // whose plan reports no name (reachable via Backend::Remote loading a ServicePlan built
        // through from_parts, which applies no non-empty-name bound) got NO warning at all, the
        // same silent-clean-dialog failure one field over from the bug already fixed above.
        V.items = wSavedItems.concat([{id:9002, kind:"slide_group", title:"Sermon slides", is_live:false, is_staged:false, link:{kind:"deck", id: wLinkedId}}]);
        V.plan_name = "";
        wLinkedCard.querySelector(".pm-lib-dots").click();
        await wWait(function(){ return !!el("pm-lib-menu"); });
        Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /^Delete/.test(b.textContent); })[0].click();
        ok(await wWait(function(){ return !!document.querySelector(".pm-confirm-warn"); }),
           "Sana (PR #69, round 2): a deck genuinely linked from a plan that reports NO name still shows a warning — \"linked\" and \"named\" are checked separately");
        var wWarnUnnamed = document.querySelector(".pm-confirm-warn");
        ok(!!wWarnUnnamed && /show missing/.test(wWarnUnnamed.textContent) && !/“”/.test(wWarnUnnamed.textContent),
           "Sana (PR #69, round 2): ...and it degrades to the generic \"Used in your service plan\" wording rather than printing an empty-quoted plan name (\"" + (wWarnUnnamed ? wWarnUnnamed.textContent : "") + "\")");
        wCloseDel();
        V.items = wSavedItems; V.plan_name = wSavedPlanName;
      }

      // --- PME-006\u2013011: promote AA-large-only muted text to --sc-text-secondary ------------
      // Each is essential text under the project's own written policy (app.css review-fixes
      // block: headings/labels/instructions/empty-states/error text must clear AA-normal;
      // --sc-text-muted, at 3.79:1 on --sc-surface, is AA-large only). Checked against the
      // shipped rule's own parsed declaration block (the same __cssRule pattern PSC-005/DLM-001
      // use above), because several of these selectors only render in states this pass does not
      // drive the UI into.
      var wMutedFixes = [
        ["PME-006", ".pm-insp-note"],
        ["PME-007", ".pm-media-empty"],
        ["PME-008", ".pm-lib-empty-sub"],
        ["PME-009", ".pm-grid-hint"],
        ["PME-010", ".pm-tile-failmsg"],
        ["PME-011", ".pm-deck-seg-btn"],
      ];
      wMutedFixes.forEach(function(pair){
        var wId = pair[0], wSel = pair[1];
        var wRule = __cssRule(wSel);
        ok(!!wRule, wId + " (premise): the " + wSel + " rule is present in the shipped app.css");
        if (wRule) {
          var wDecl = wRule.style.cssText;
          ok(/--sc-text-secondary/.test(wDecl) && !/--sc-text-muted/.test(wDecl),
             wId + ": " + wSel + " uses --sc-text-secondary (AA-normal, 7.40\u20138.74:1 on surface), not the AA-large-only --sc-text-muted (\"" + wDecl.trim().slice(0, 80) + "\")");
        }
      });

      // --- \u00a710 case 6 / CON-099, CON-101, CON-102: the engaged BLACKOUT state ------------
      // The bug is that the most destructive state in the product explains nothing: the operator
      // sees "BLACKOUT ON" and no statement of what the audience sees or how to get back. So the
      // checks that matter are the ones about the ABSENT case (nothing shown when not blacked out)
      // and about the explanation being genuinely PAINTED, not merely un-hidden — a class display
      // rule defeats [hidden] in this webview, which is how an "it appears" check goes vacuous.
      var wBoBtn = el("blackout"), wExp = el("blackout-explain"), wRes = el("restore-output");
      ok(!!wExp && !!wRes, "CON-101/102: the blackout explanation and a Restore control exist at all");
      // (a) NOT blacked out — both must be genuinely gone, and the label must not claim the state.
      ok(getComputedStyle(wExp).display === "none" && wExp.getClientRects().length === 0,
         "CON-101 (control): with output live the explanation is NOT painted — otherwise 'it appears on blackout' proves nothing");
      ok(getComputedStyle(wRes).display === "none" && wRes.getClientRects().length === 0,
         "CON-102 (control): with output live the Restore control is unpainted and out of the tab order");
      ok(el("blackout-label").textContent.trim() === "BLACKOUT",
         "CON-099: with output live the button reads BLACKOUT (the action), not the state");
      // CON-161 controls: neither monitor pill carries the blackout re-tint before one is engaged.
      var wPrevPill = el("preview-pill"), wLivePill = el("live-pill");
      ok(!!wPrevPill && !!wLivePill, "CON-161: both monitor pills exist");
      ok(!wPrevPill.classList.contains("blackout") && !wLivePill.classList.contains("blackout"),
         "CON-161 (control): with output live neither pill carries the blackout re-tint");
      ok(el("preview-pill-status").textContent.trim() === "STAGED" && el("live-pill-status").textContent.trim() === "ON AIR",
         "CON-161 (control): pill status text reads normally before a blackout");
      // (b) engage it through the REAL command path, not by poking the view.
      wBoBtn.click();
      ok(await wWait(function(){ return !wExp.hidden; }), "CON-101 (setup): engaging blackout via the real command renders the engaged state");
      ok(getComputedStyle(wExp).display !== "none" && wExp.getClientRects().length > 0,
         "CON-101: the explanation is actually PAINTED during a blackout (computed display " + getComputedStyle(wExp).display + ")");
      // Normalise whitespace first: the sentence wraps in the markup, so textContent carries a
      // newline + indent and a literal-phrase regex silently misses. Assert the words, not the layout.
      var wExpTxt = wExp.textContent.replace(/\s+/g, " ").trim();
      ok(/audience sees nothing/i.test(wExpTxt) && /restore/i.test(wExpTxt),
         "CON-101: it says what the AUDIENCE sees and how to get back — the two things the state never stated (\"" + wExpTxt.slice(0, 72) + "\")");
      ok(wExp.getAttribute("role") === "status",
         "CON-101: the explanation is announced to assistive tech (role=status), not a silent visual-only cue");
      ok(el("blackout-label").textContent.trim() === "BLACKED OUT",
         "CON-099: engaged, the button states the STATE in words (non-colour, WCAG 1.4.1)");
      // CON-161 — both monitor pills flag the blackout, not just the Live panel's own marker.
      ok(wPrevPill.classList.contains("blackout"),
         "CON-161: the PREVIEW pill re-tints during a blackout too, not just Live's own marker");
      ok(wLivePill.classList.contains("blackout"), "CON-161: the LIVE pill also carries the blackout re-tint");
      ok(el("preview-pill-status").textContent.trim() === "AUDIENCE DARK",
         "CON-161: the Preview pill's STATUS TEXT changes too, not colour alone (WCAG 1.4.1)");
      ok(el("live-pill-status").textContent.trim() === "BLACK",
         "CON-161: the Live pill reads 'LIVE · BLACK' per the Figma spec (346:144)");
      var wPrevPillCs = getComputedStyle(wPrevPill);
      var wPrevPillR = _cr(_rgba(wPrevPillCs.color), _rgba(wPrevPillCs.backgroundColor));
      ok(wPrevPillR >= 4.5, "CON-161: the re-tinted Preview pill text clears AA-normal (" + _f(wPrevPillR) + ":1) — the same --sc-live-soft/--sc-live pairing the Live pill already ships at rest, no new pairing introduced");
      // CON-162 documented divergence (FRAME-G-RECOVERY-STATES-divergences.md #7): Preview's own
      // SURFACE (the real staged content) is left untouched — blackout only blanks the
      // audience/Live output (present.rs's own blackout() doc comment), so painting Preview's
      // monitor black would misstate what the operator is actually looking at. Only the pill
      // (a status echo, never a content claim) reflects it.
      ok(!document.getElementById("preview-panel").classList.contains("blackout"),
         "CON-162 (documented divergence): Preview's own surface is never painted black — only its pill echoes the blackout state");
      ok(document.querySelector("#emergency .note").hidden,
         "CON-101: the general footer note yields its slot, so the bar carries one sentence not two");
      // Contrast of the explanation, measured composited against the footer's REAL ground.
      var wFoot = _rgba(getComputedStyle(el("emergency")).backgroundColor);
      var wExpR = _stack(_rgba(getComputedStyle(wExp).color), _rgba(getComputedStyle(wExp).backgroundColor), wFoot);
      ok(wExpR >= 4.5, "CON-101: the explanation clears AA-NORMAL on the real footer ground (" + _f(wExpR) + ":1)");
      var wResCs = getComputedStyle(wRes);
      var wResR = _cr(_rgba(wResCs.color), _rgba(wResCs.backgroundColor));
      ok(wResR >= 4.5, "CON-102: the Restore label clears AA-NORMAL on its fill (" + _f(wResR) + ":1)");
      ok(_cr(_rgba(wResCs.backgroundColor), wFoot) >= 3.0,
         "CON-102: the Restore control is distinguishable from the footer behind it (" + _f(_cr(_rgba(wResCs.backgroundColor), wFoot)) + ":1, 3:1 non-text bar)");
      ok(_cr(_rgba(wResCs.backgroundColor), _rgba(getComputedStyle(wBoBtn).backgroundColor)) >= 3.0,
         "CON-102: Restore is distinguishable from the BLACKOUT button beside it — the way back must not read as another way in");
      // (c) Restore is ONE-WAY. A toggle here would re-black the output on a double-press, so
      // assert the ARGUMENT, twice — a single click passing proves nothing about a toggle.
      var wBn = window.__calls.filter(function(c){ return c.cmd === "blackout"; }).length;
      wRes.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "blackout"; }).length > wBn; }),
         "CON-102 (setup): Restore issues the blackout command");
      var wLast = window.__calls.filter(function(c){ return c.cmd === "blackout"; }).pop();
      ok(wLast.args && wLast.args.on === false, "CON-102: Restore sends blackout{on:false} — it restores, never toggles");
      ok(await wWait(function(){ return wExp.hidden; }), "CON-102: restoring clears the engaged state");
      ok(await wWait(function(){ return !wPrevPill.classList.contains("blackout") && !wLivePill.classList.contains("blackout"); }),
         "CON-161: both pills revert once blackout clears");
      ok(el("live-pill-status").textContent.trim() === "ON AIR" && el("preview-pill-status").textContent.trim() === "STAGED",
         "CON-161: both pills' status text reverts to normal ('ON AIR' / 'STAGED')");
      ok(document.activeElement === wBoBtn,
         "CON-102: focus lands on the BLACKOUT button after Restore disappears, not on <body> (WCAG 2.4.3)");
      // Press it again while output is already live: it must STILL mean restore, never re-black.
      wRes.hidden = false; // reachable only in the engaged state, but prove the handler is one-way
      wRes.click();
      ok(await wWait(function(){ var l = window.__calls.filter(function(c){ return c.cmd === "blackout"; }).pop(); return l && l.args.on === false; }),
         "CON-102: a second activation still sends on:false — the control is not a disguised toggle");
      ok(!el("blackout-explain") || el("blackout-explain").hidden,
         "CON-102: the audience is NOT re-blacked by pressing Restore twice");

      // --- CON-098 (blocker): the emergency-footer CONTAINER itself re-tints on blackout,
      // not just the button label/explanation. A prior pass judged the Figma re-tint
      // invisible using the WCAG relative-luminance ratio between the two grounds (1.03:1) —
      // that ratio is a text-legibility metric and compresses toward 1:1 for any two very-dark
      // colours regardless of hue, so it does not actually answer "is this visible". Re-checked
      // in CIELAB (ticket 17tnw2axpta): deltaE76 ~3.5 for the background and ~13.4 for the
      // border shift — past the ~2.3 JND, so the re-tint is real. State is restored by the
      // block above, so this starts from the resting ground, engages via the real command
      // path (never by poking the view), and restores again so later checks in this suite see
      // the resting footer, not an engaged one. ---
      var wEmFoot = el("emergency");
      ok(!wEmFoot.classList.contains("blackout"),
         "CON-098 (control): with output live the footer carries no re-tint class");
      var wRestBg = getComputedStyle(wEmFoot).backgroundColor;
      var wRestBorder = getComputedStyle(wEmFoot).borderTopColor;
      wBoBtn.click(); // engage via the real command path
      ok(await wWait(function(){ return wEmFoot.classList.contains("blackout"); }),
         "CON-098 (setup): engaging blackout adds the re-tint class to the real #emergency element");
      var wEngBg = getComputedStyle(wEmFoot).backgroundColor;
      var wEngBorder = getComputedStyle(wEmFoot).borderTopColor;
      ok(wEngBg !== wRestBg,
         "CON-098: the footer's computed background genuinely changes on blackout (" + wRestBg + " -> " + wEngBg + ")");
      ok(wEngBorder !== wRestBorder,
         "CON-098: the footer's computed border colour changes too, not just the background (" + wRestBorder + " -> " + wEngBorder + ")");
      ok(wEngBg === "rgb(26, 12, 12)",
         "CON-098: the engaged ground is exactly the canonical frame's #1a0c0c (337:203), not an approximation");
      var wRes2 = el("restore-output");
      wRes2.click();
      ok(await wWait(function(){ return !wEmFoot.classList.contains("blackout"); }),
         "CON-098: restoring output un-tints the footer again (cleanup — later checks expect the resting footer)");

      // --- §10 case 5: the emergency-ready chip is the canonical frame's PILL --------------
      // Asserting the declared radius alone would pass on an element nobody paints, and "999px"
      // is a string, not a shape. Measure it against the element's REAL rendered height instead:
      // a pill is radius >= half the height, whatever the number says.
      var wRdy = document.querySelector(".emergency-ready");
      ok(!!wRdy && wRdy.getClientRects().length > 0,
         "\u00a710 case 5 (positive control): the Offline-ready chip is actually painted, so its shape can be measured");
      if (wRdy) {
        var wRdyH = wRdy.getBoundingClientRect().height;
        var wRdyR = parseFloat(getComputedStyle(wRdy).borderTopLeftRadius);
        ok(wRdyH > 0 && wRdyR >= wRdyH / 2,
           "\u00a710 case 5: the Offline-ready chip is a PILL — radius " + wRdyR.toFixed(1) + "px >= half its " + wRdyH.toFixed(1) + "px height (canonical frame 312:151; was 10px)");
      }

      // ===================================================================================
      // SYSTEM & RECOVERY STATES (Design 2.0 Frame G, node 346:124) + the honest pill.
      //
      // What these checks defend, in one line: ABSENT TELEMETRY IS UNKNOWN, NEVER A FAULT AND
      // NEVER HEALTHY. Every state below therefore ships with a negative control, because
      // "the banner appeared" proves nothing unless "it stays away when it should" also holds.
      //
      // The edge checks are the load-bearing ones. The console polls at 1 Hz with NO health
      // event channel, so a hold that begins AND ends between two polls reads `held:false` in
      // both samples. Reading the counters as LEVELS would miss it entirely; only a delta
      // against the previous poll sees it. Those checks drive two real polls to prove it.
      // ===================================================================================
      var gPoll = function(pred){ return waitFor(pred, 120); };   // past the 1s poll, virtual
      // Count completed view polls. `gPoll(function(){ return true; })` does NOT wait — waitFor
      // returns immediately on an already-true predicate — so anything that must observe a real
      // poll (every edge check does, by definition) waits on THIS instead.
      var gViews = function(){
        var n = 0;
        for (var i = 0; i < window.__calls.length; i++) if (window.__calls[i].cmd === "view") n++;
        return n;
      };
      var gTicks = function(n){ var t = gViews(); return waitFor(function(){ return gViews() >= t + n; }, 200); };
      var gTx = function(id){ var e = el(id); return e ? e.textContent.replace(/\s+/g," ").trim() : ""; };
      // Painted = COMPUTED display + a real client rect. Never `.hidden` and never DOM
      // presence: a class `display` rule defeats the [hidden] attribute in this webview.
      var gOn = function(id){
        var e = el(id);
        return !!e && getComputedStyle(e).display !== "none" && e.getClientRects().length > 0;
      };

      document.querySelector('.nav-item[data-surface="console"]').click();
      await gPoll(function(){ return el("surface-console").classList.contains("active"); });

      // ---- resting state -------------------------------------------------------------
      ok(!!el("recovery"), "Frame G: the recovery region exists in the console");
      ok(!gOn("recovery"),
         "Frame G (control): with a healthy host NOTHING is painted — the region stays out of the way, so every 'it appeared' below means something");

      // ---- G.5 session recovery ------------------------------------------------------
      V.session = {restored:true};
      await gPoll(function(){ return gOn("rcv-session"); });
      ok(gOn("rcv-session"), "G.5: session.restored paints the recovery notice (computed display)");
      var gS = gTx("rcv-session-title") + " " + gTx("rcv-session-text");
      ok(/restored/i.test(gS), "G.5: it says the session was restored (\"" + gS.slice(0,60) + "\")");
      ok(!/unexpectedly|crashed/i.test(gS),
         "G.5: it does NOT claim a crash — `restored` means crash OR restart, and a clean exit also saves a session, so 'closed unexpectedly' would be false after an ordinary relaunch");
      ok(!/Start fresh|Restore session/i.test(gTx("rcv-session")),
         "G.5: no Restore/Start-fresh buttons — the host already restored before this rendered and NO command exists to undo it, so the frame's choice dialog would be two buttons that cannot act");

      // The crash-loop case is the one where "started clean" would read as data loss.
      V.session = {crash_loop:true, rapid_launches:4};
      await gPoll(function(){ return /clean/i.test(gTx("rcv-session-title")); });
      var gL = gTx("rcv-session-title") + " " + gTx("rcv-session-text");
      ok(/clean/i.test(gL) && /4/.test(gL), "G.5: the crash-loop breaker is reported with its real launch count (\"" + gL.slice(0,64) + "\")");
      ok(/preserved/i.test(gL),
         "G.5: it says the previous session is PRESERVED — the breaker skips it, never deletes it, and omitting that reads as data loss");

      // Storage: checkpoints paused is about SAVING, and must not imply the audience is affected.
      V.session = {restored:true}; V.storage = {status:"critical", checkpoints_paused:true};
      await gPoll(function(){ return gOn("rcv-session-chip"); });
      ok(gOn("rcv-session-chip") && /checkpoint/i.test(gTx("rcv-session-chip")),
         "G.5: checkpoints_paused surfaces as a chip (\"" + gTx("rcv-session-chip").slice(0,52) + "\")");
      // The host's OWN reason, not a generic failure.
      V.session = {restored:true, autosave_error:"disk quota exceeded"};
      await gPoll(function(){ return /quota/i.test(gTx("rcv-session-chip")); });
      ok(/disk quota exceeded/.test(gTx("rcv-session-chip")),
         "G.5: an autosave failure shows the HOST'S reason, not a generic 'something went wrong'");

      el("rcv-session-x").click();
      ok(!gOn("rcv-session"), "G.5: the notice is dismissible — an informational banner must not hold console space for a whole service");
      ok(!gOn("recovery"), "G.5: dismissing the only live state hides the whole region too");

      V.session = null; V.storage = null;
      await gPoll(function(){ return !gOn("rcv-session"); });
      ok(!gOn("rcv-session"),
         "G.5 (control): session:null paints NOTHING — a host that does not report session health is UNKNOWN, not a host with a healthy session and not one with a fault");

      // ---- G.2 control-link loss + the pill ------------------------------------------
      ok(!gOn("rcv-link"), "G.2 (control): a healthy link paints no banner");
      ok(gTx("conn-label") === "Connected", "pill (control): a real connected link reads Connected");

      window.__link = {state:"disconnected", epoch:1, attempts:0, last_error:"connection closed"};
      await gPoll(function(){ return gOn("rcv-link"); });
      ok(gOn("rcv-link"), "G.2: a dropped link paints the banner");
      var gK = gTx("rcv-link");
      ok(!/reconnecting/i.test(gK),
         "G.2: it does NOT say 'Reconnecting' — build_backend() runs once and nothing re-dials, so claiming a retry is the exact fabrication this seam removes");
      ok(/host keeps presenting|unaffected/i.test(gK),
         "G.2: it states the thing the operator needs under pressure — the host keeps presenting (\"" + gK.slice(0,64) + "\")");
      ok(!/mobile remote/i.test(gK),
         "G.2: it does NOT claim 'Mobile remotes are paused' — no seam reports LAN controller peers, so the frame's line would be a fabrication through a truthful-looking surface");
      ok(gTx("conn-label") === "Host unreachable",
         "pill: a dropped link reads 'Host unreachable', not 'Connected' and not 'Reconnecting…' (\"" + gTx("conn-label") + "\")");
      ok(el("conn-pill").classList.contains("down") && !el("conn-pill").classList.contains("reconnecting"),
         "pill: the dropped state is red, and is NOT the amber reconnecting state");

      // `local` is the fabrication that mattered most: green for the ABSENCE of a failure path.
      window.__link = {state:"local", epoch:0, attempts:0, last_error:null};
      await gPoll(function(){ return gTx("conn-label") === "Local"; });
      ok(gTx("conn-label") === "Local",
         "pill: the stand-alone backend says 'Local' — it has no host and wants none");
      ok(!el("conn-pill").classList.contains("down"),
         "pill: 'local' is NEUTRAL, not an error — no link is wanted, so it is not a failure");
      var gPc = getComputedStyle(el("conn-pill")).color;
      var gGreen = getComputedStyle(document.documentElement).getPropertyValue("--sc-preview").trim();
      ok(_cr(_rgba(gPc), _rgba(getComputedStyle(el("conn-pill")).backgroundColor)) >= 4.5,
         "pill: the Local label clears AA-NORMAL on its own ground (" + _f(_cr(_rgba(gPc), _rgba(getComputedStyle(el("conn-pill")).backgroundColor))) + ":1)");
      ok(!gOn("rcv-link"),
         "G.2 (control): 'local' paints NO banner — a console with no host link is healthy, not disconnected");

      window.__link = {state:"connected", epoch:1, attempts:0, last_error:null};
      await gPoll(function(){ return gTx("conn-label") === "Connected"; });
      ok(gTx("conn-label") === "Connected" && !gOn("rcv-link"),
         "pill (positive control): the pill and banner both recover when the link does — so 'it went red' above was the state changing, not a dead mechanism");

      // ---- G.3 output signal lost + the never-blank hold ------------------------------
      ok(!gOn("rcv-output"),
         "G.3 (control): an assigned output with NO `signal` reported paints nothing — absent telemetry is UNKNOWN, which is exactly the `else -> NO SIGNAL` bug this replaces");

      V.outputs = [{role:"stage", assigned:true, assigned_key:"d2", display:"Stage Display", width:1920, height:1080, signal:"no_signal"},
                   {role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];
      await gPoll(function(){ return gOn("rcv-output"); });
      ok(gOn("rcv-output"), "G.3: a reported no_signal on an ASSIGNED output paints the card");
      ok(gTx("rcv-output-pill-label") === "SIGNAL LOST", "G.3: the pill reads SIGNAL LOST");
      var gO = gTx("rcv-output-text");
      ok(/Stage Display/.test(gO),
         "G.3: it names the output the HOST reported, not the frame's invented 'HDMI-2' (\"" + gO.slice(0,56) + "\")");
      ok(!/HDMI/i.test(gO), "G.3: no invented connector name — no seam carries a display identity for a lost output");
      ok(/Other outputs are unaffected/i.test(gO),
         "G.3: isolation is asserted FROM DATA — the sibling output really does report healthy");
      ok(!/attempt|∞/i.test(gTx("rcv-output")),
         "G.3: no 'attempt 2 of ∞' — retries are bounded by contract and unbounded counters contradict it");
      ok(gOn("rcv-output-reattach") && /automatically/i.test(gTx("rcv-output-reattach")),
         "G.3: it states FR-041's real guarantee — content reattaches automatically on reconnect");
      ok(!gOn("rcv-output-held"),
         "G.3 (control): with held:false the held-frame line is NOT painted, so its appearance below means the host really reported a hold");

      // The isolation claim must disappear when it stops being true.
      V.outputs = [{role:"stage", assigned:true, assigned_key:"d2", display:"Stage Display", width:1920, height:1080, signal:"no_signal"}];
      await gPoll(function(){ return !/Other outputs/i.test(gTx("rcv-output-text")); });
      ok(!/Other outputs are unaffected/i.test(gTx("rcv-output-text")),
         "G.3: with no healthy sibling the isolation sentence is DROPPED — it is asserted from data, never printed as boilerplate");

      V.output_health = {held:true, fault:"gpu_device_lost", holds:1};
      await gPoll(function(){ return gOn("rcv-output-held"); });
      var gH = gTx("rcv-output-held");
      ok(gOn("rcv-output-held"), "G.3: held:true paints the never-blank explanation");
      ok(/still sees content|holding its last good frame/i.test(gH),
         "G.3: it is worded as the GUARANTEE WORKING — 'output held (audience unaffected)' is accurate, 'output failed' is not (\"" + gH.slice(0,56) + "\")");
      ok(!/failed|failure/i.test(gH), "G.3: it never calls the never-blank guarantee a failure");

      // Everything healthy again -> the region must retract on its own. Placed HERE, before any
      // recovery is announced, so it does not have to wait out the confirmation's 8s window.
      V.output_health = {held:false}; V.session = null; V.storage = null;
      V.outputs = [{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];
      await gPoll(function(){ return !gOn("recovery"); });
      ok(!gOn("recovery"),
         "Frame G: with every seam healthy again the whole region retracts (positive control for the region itself — it is not simply stuck open)");

      // ---- G.3 recovery: EDGES ACROSS POLLS, NOT LEVELS ------------------------------
      // These assert the EDGE (an announcement fired), not the card's visibility. The
      // confirmation is a transient whose 8s window deliberately outlives the moment it
      // fired, so "is it on screen?" cannot tell a NEW edge from the previous one still
      // showing — and a test that cannot tell those apart would pass on a broken edge.
      var gAnn = function(){ return window.__rcvAnnounced(); };

      V.outputs = [{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];
      // Go UNKNOWN first so the next sample is genuinely a FIRST observation. (Without this the
      // baseline from the checks above is still live, and 1 -> 3 is a real delta of 3.)
      V.output_health = null;
      await gTicks(2);
      var gA0 = gAnn();
      V.output_health = {held:false, holds:3, recoveries:3};
      await gTicks(2);
      ok(gAnn() === gA0,
         "G.3 EDGE (control): a FIRST observation carrying recoveries:3 announces NOTHING — a non-zero counter is a level, not an event; baselining it is the whole point (announcements " + gA0 + " -> " + gAnn() + ")");

      var gA1 = gAnn();
      V.output_health = {held:false, holds:4, recoveries:4};
      await gPoll(function(){ return gAnn() > gA1; });
      ok(gAnn() === gA1 + 1,
         "G.3 EDGE: recoveries incrementing between two polls announces EXACTLY ONE recovery — THE case `held` cannot see, because a hold that begins and ends between polls reads false in both samples");
      ok(gOn("rcv-recovered") && /recovered/i.test(gTx("rcv-recovered-text")),
         "G.3 EDGE: the confirmation is actually painted (\"" + gTx("rcv-recovered-text").slice(0,52) + "\")");

      // Re-polling the SAME counters is not a new event.
      var gA2 = gAnn();
      await gTicks(2);
      ok(gAnn() === gA2,
         "G.3 EDGE (control): polling again with UNCHANGED counters announces nothing — otherwise every poll would re-announce the same recovery forever");

      // A counter going DOWN is a new host/session, not a recovery.
      var gA3 = gAnn();
      V.output_health = {held:false, holds:1, recoveries:1};
      await gTicks(2);
      ok(gAnn() === gA3,
         "G.3 EDGE: counters DECREASING announces nothing — both are monotonic and saturating, so a decrease means a new host/session, never a recovery (announcements " + gA3 + " -> " + gAnn() + ")");

      // ...and the re-baseline must be the NEW low value, not the old high one: climbing back
      // to 2 is one recovery, not a replay of the gap.
      var gA4 = gAnn();
      V.output_health = {held:false, holds:2, recoveries:2};
      await gPoll(function(){ return gAnn() > gA4; });
      ok(gAnn() === gA4 + 1 && /recovered — /i.test(gTx("rcv-recovered-text")),
         "G.3 EDGE: after a decrease the baseline is the NEW value — climbing 1 -> 2 announces ONE recovery, not a replay (\"" + gTx("rcv-recovered-text").slice(0,44) + "\")");

      // Unknown health must drop the baseline, or the next known sample fakes a huge delta.
      var gA5 = gAnn();
      V.output_health = null;
      await gTicks(2);
      V.output_health = {held:false, holds:9, recoveries:9};
      await gTicks(2);
      ok(gAnn() === gA5,
         "G.3 EDGE: after output_health goes UNKNOWN the baseline is DROPPED, so the next known sample re-baselines instead of reading as a 7-recovery delta (announcements " + gA5 + " -> " + gAnn() + ")");

      V.output_health = {held:false}; V.session = null; V.storage = null;
      V.outputs = [{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];

      // ---- G.6 missing-media fallback (347:165) --------------------------------------
      // The inspector already NAMED a missing file. What it never said is the only thing that
      // matters mid-service: what the AUDIENCE is seeing. FR-070 guarantees a safe placeholder
      // and never a black screen, and the rasterizer already honours it — so the console does
      // not synthesize a fallback, it explains the one that exists.
      //
      // Driven entirely through the app's OWN commands (add image -> go missing -> refresh) so
      // the fixture and the editor can never disagree about which deck is open. The negative
      // control is therefore the SAME element before it goes missing, which is stronger than a
      // different element that happens to be fine.
      document.querySelector('.nav-item[data-surface="presentation"]').click();
      await waitFor(function(){ return el("surface-presentation").classList.contains("active"); }, 200);
      // Navigating to the surface lands on the LIBRARY, not the editor, and the grid renders
      // asynchronously — so a one-shot "is the grid hidden?" test can run before it exists and
      // silently skip the Edit click, leaving every later check measuring a display:none subtree.
      var gBody = function(){ return getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display; };
      await waitFor(function(){ return gBody() !== "none" || (el("pm-grid-edit") && !el("pm-grid").hidden); }, 200);
      if (gBody() === "none" && el("pm-grid-edit")) el("pm-grid-edit").click();
      await waitFor(function(){ return gBody() !== "none"; }, 200);
      ok(gBody() !== "none", "G.6 (setup): the deck editor is open, so the inspector checks measure a painted subtree");
      if (el("pm-tab-inspector")) el("pm-tab-inspector").click();
      document.querySelector('#surface-presentation .pm-tool[data-add="image"]').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_image_element"; }); }, 200);
      await waitFor(function(){ return /image/i.test(el("pm-inspector-body").textContent); }, 200);
      ok(/image/i.test(el("pm-inspector-body").textContent),
         "G.6 (setup): an image element is selected in the inspector, so the missing state has something real to attach to");
      ok(!document.querySelector(".pm-insp-miss"),
         "G.6 (control): a PRESENT asset paints no missing-media explanation — the same element, before it goes missing");

      // Take it missing at the host, exactly as a deleted file would, then let the app refresh
      // through its own round-trip (the eye toggle returns a fresh DeckView; toggled twice so
      // visibility ends where it started and only `missing` differs).
      var gIx = D.slide.elements.length - 1;
      D.slide.elements[gIx].missing = true;
      D.slide.elements[gIx].name = "Harvest field.jpg";
      var gEye = document.querySelector("#pm-layers .td-layer.sel .td-layer-eye") || document.querySelector("#pm-layers .td-layer-eye");
      ok(!!gEye, "G.6 (setup): the layer row exposes a visibility control to drive a real host refresh");
      if (gEye) {
        gEye.click();
        await waitFor(function(){ return !!document.querySelector(".pm-insp-miss"); }, 200);
        var gEye2 = document.querySelector("#pm-layers .td-layer.sel .td-layer-eye") || document.querySelector("#pm-layers .td-layer-eye");
        if (gEye2) gEye2.click();
        await waitFor(function(){ return !!document.querySelector(".pm-insp-miss"); }, 200);
        // Re-assert the Inspector tab: the rect check below is meaningless if an ANCESTOR is
        // display:none, and an element's own computed display stays "block" in that case — so
        // without this the check could pass on an invisible panel or fail on a correct one.
        if (el("pm-tab-inspector")) el("pm-tab-inspector").click();
        await waitFor(function(){
          var m = document.querySelector(".pm-insp-miss");
          return !!m && m.getClientRects().length > 0;
        }, 200);
        var gMiss = document.querySelector(".pm-insp-miss");
        var gDbg = "surface=" + el("surface-presentation").classList.contains("active")
          + " pmBody=" + getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display
          + " inspHidden=" + (el("pm-inspector-body") ? el("pm-inspector-body").hidden : "n/a")
          + " inspDisp=" + (el("pm-inspector-body") ? getComputedStyle(el("pm-inspector-body")).display : "n/a")
          + " missDisp=" + (gMiss ? getComputedStyle(gMiss).display : "n/a")
          + " rects=" + (gMiss ? gMiss.getClientRects().length : "n/a");
        ok(!!gMiss && getComputedStyle(gMiss).display !== "none" && gMiss.getClientRects().length > 0,
           "G.6: a missing image paints the fallback explanation (computed display + a real rect) [" + gDbg + "]");
        var gMt = gMiss ? gMiss.textContent.replace(/\s+/g, " ").trim() : "";
        ok(/audience/i.test(gMt) && /background/i.test(gMt),
           "G.6: it says what the AUDIENCE sees — the slide composes without the asset (\"" + gMt.slice(0, 58) + "\")");
        ok(/never an error/i.test(gMt),
           "G.6: it states FR-070's guarantee explicitly rather than leaving the operator to fear a black screen");
        ok(/re-push/i.test(gMt) && /on air/i.test(gMt),
           "G.6: it warns that repairing the DECK does not repair what is already ON AIR — deck repairs route through with_deck and never present (FR-012)");
        ok(gMiss && gMiss.getAttribute("role") === "status",
           "G.6: the explanation is announced to assistive tech, not a silent visual-only cue");
        var gMc = _cr(_rgba(getComputedStyle(gMiss).color), _rgba(getComputedStyle(gMiss).backgroundColor));
        ok(gMc >= 4.5,
           "G.6: the explanation clears AA-NORMAL on its own warn ground (" + _f(gMc) + ":1) — essential copy, so --sc-text-secondary not the AA-large-only --sc-text-muted");
        ok(/Relink/i.test(el("pm-inspector-body").textContent),
           "G.6: the repair affordance is offered and reads 'Relink…' for a missing asset, not the generic 'Replace…'");
      }

      // === Settings › About & Licensing (Figma 584:124 — story 17tnw2axwer, closes SET-007) ===
      {
        function _luma(rgb){ var s=[rgb[0],rgb[1],rgb[2]].map(function(c){c/=255; return c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4);}); return 0.2126*s[0]+0.7152*s[1]+0.0722*s[2]; }
        function _parseRgb(s){ var m=String(s).match(/[-\d.]+/g)||["0","0","0"]; return [+m[0],+m[1],+m[2]]; }
        function _contrast(fg,bg){ var lf=_luma(_parseRgb(fg)), lb=_luma(_parseRgb(bg)), hi=Math.max(lf,lb), lo=Math.min(lf,lb); return (hi+0.05)/(lo+0.05); }

        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("about");
        ok(el("set-page-about") && !el("set-page-about").hidden && el("set-placeholder").hidden,
           "Settings/About: the real page renders (SET-007 page-level MISSING closed, not the shared placeholder)");

        // Version: real Tauri app.getVersion(), never a fabricated "1.0.0" string.
        await sleep(40);
        ok(el("ab-version").textContent === "0.1.0",
           "Settings/About: Version reads the real app.getVersion() value (\"" + el("ab-version").textContent + "\")");
        window.__appVersionAvailable = false; // simulate an older/narrower Tauri global
        window.__resetSettingsAboutForTest();
        setSettingsPage("about");
        await sleep(40);
        ok(el("ab-version").textContent === "—",
           "Settings/About (control): with no app.getVersion() available it shows the honest \"—\", never a guessed number");
        window.__appVersionAvailable = true;
        window.__resetSettingsAboutForTest();
        setSettingsPage("about");
        await sleep(40);

        // Platform: derived from navigator, never the Figma mock's static "macOS 15.3 · Apple Silicon".
        ok(el("ab-platform").textContent.length > 0 && el("ab-platform").textContent !== "—",
           "Settings/About: Platform is read from the real navigator, not left as the honest-empty default (\"" + el("ab-platform").textContent + "\")");

        // Scripture attributions: real list_translations() data, never the mock's hardcoded
        // "World English Bible, ASV, KJV, WEBBE, Darby" line.
        ok(window.__calls.some(function(c){ return c.cmd === "list_translations"; }),
           "Settings/About: scripture attributions are loaded via the real list_translations() command");
        var abRows = document.querySelectorAll("#ab-scripture-list .pp-inc-row");
        ok(abRows.length === 6, "Settings/About: all 6 real translations render as their own row, bundled AND downloadable (" + abRows.length + ")");
        ok(/King James Version/.test(abRows[0].textContent) && /Public Domain/.test(abRows[0].textContent),
           "Settings/About: a bundled row names the real translation and its real public-domain licence, not fabricated text");
        ok(/Young's Literal Translation/.test(abRows[5].textContent) && !/Public Domain/.test(abRows[5].textContent),
           "Settings/About: the one downloadable (not-yet-installed) translation does NOT get the Public Domain badge its bundled siblings get — the code reads downloadable, not a hardcoded assumption every entry is bundled");

        // Update status: honestly inert — a real, disabled, labelled control, never a fake "UP TO DATE".
        ok(el("ab-check-update").disabled && el("ab-check-update").getAttribute("aria-disabled") === "true",
           "Settings/About: 'Check for updates' is a real disabled control (no update mechanism exists yet) — not a live-looking button that would silently no-op");
        ok(!/UP TO DATE/.test(el("set-page-about").textContent),
           "Settings/About: no fabricated 'UP TO DATE' status — this build has no update-check mechanism to report one from");

        // DPA row: driven by the REAL providers_view().any_cloud_enabled — flips with real state,
        // never a static "SHOWN WITH CLOUD" pill regardless of whether cloud is actually on. This
        // block runs after the earlier Providers & Privacy checks, which toggle these SAME shared
        // fixture flags — force both to a known false state first rather than assuming whatever
        // they were left at.
        window.__pp.cloud_notes_consent = false;
        window.__pp.cloud_transcription_consent = false;
        window.__resetSettingsAboutForTest();
        setSettingsPage("about");
        await sleep(40);
        ok(el("ab-dpa-badge").textContent === "NOT SHOWN",
           "Settings/About (control): DPA row reads NOT SHOWN while no cloud provider is enabled");
        window.__pp.cloud_notes_consent = true;
        window.__resetSettingsAboutForTest();
        setSettingsPage("about");
        await sleep(40);
        ok(el("ab-dpa-badge").textContent === "CLOUD ENABLED" && /cloud provider is enabled/.test(el("ab-dpa-note").textContent),
           "Settings/About: enabling a real cloud provider flips the DPA row to CLOUD ENABLED — driven by data, not a fixed Figma badge");
        window.__pp.cloud_notes_consent = false; // restore for later PP checks in this same run

        // Contrast (NFR-020): essential row copy uses --sc-text-secondary (AA-normal), never the
        // AA-large-only --sc-text-muted reserved for genuinely tertiary notes. Contrast against the
        // row's OWN real computed background (already in rgb()/rgba() form _contrast expects),
        // never a hand-typed hex guess that could silently drift from the actual token.
        var abRowD = document.querySelector("#set-page-about .set-row-d");
        var abRowBg = getComputedStyle(abRowD.closest(".set-row")).backgroundColor;
        var abRowDc = _contrast(getComputedStyle(abRowD).color, abRowBg);
        ok(abRowDc >= 4.5, "Settings/About: .set-row-d body copy clears AA-normal on its own row background (" + abRowDc.toFixed(2) + ":1)");
      }

      // === Settings › Appearance (Figma 581:124 — story 17tnw2axwer, closes SET-004) ===
      {
        V.stage_template = "scripture"; // exercise the non-default card being pre-selected
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("appearance");
        await sleep(40);
        ok(el("set-page-appearance") && !el("set-page-appearance").hidden && el("set-placeholder").hidden,
           "Settings/Appearance: the real page renders (SET-004 page-level MISSING closed, not the shared placeholder)");

        // Layout regression guard (Vera's performance review of PR #68): a stray "*/" inside a
        // CSS comment above .set-stack's definition once silently truncated the comment early,
        // turning the rest of the prose into an invalid selector and dropping the WHOLE .set-stack
        // rule — the wiring/contrast checks below all kept passing because none of them reads
        // layout. This asserts the actual computed style the class exists to produce (a flex
        // column with a real gap), so a repeat of that exact bug class fails HERE, not silently.
        var apStageThemesCs = getComputedStyle(el("ap-stage-themes"));
        ok(apStageThemesCs.display === "flex" && apStageThemesCs.flexDirection === "column" && parseFloat(apStageThemesCs.gap) > 0,
           "Settings/Appearance: #ap-stage-themes (.set-stack) actually computes as a flex column with a real gap — proves the CSS rule is live, not silently dropped");

        // Default stage theme: REAL — reflects view.stage_template, the exact field/command the
        // Presentation surface's own stage-theme picker already uses (app.js #stage-themes).
        var apScr = el("ap-stage-theme-scripture"), apWor = el("ap-stage-theme-worship");
        ok(apScr && apScr.classList.contains("sel") && apScr.getAttribute("aria-checked") === "true",
           "Settings/Appearance: the card matching the REAL view.stage_template (scripture) renders selected");
        ok(apWor && !apWor.classList.contains("sel") && apWor.getAttribute("aria-checked") === "false",
           "Settings/Appearance (control): the non-active template card is not marked selected");
        var apCallsBefore = window.__calls.length;
        apWor.click();
        await sleep(20);
        ok(window.__calls.slice(apCallsBefore).some(function(c){ return c.cmd === "set_stage_template" && c.args.template === "worship"; }),
           "Settings/Appearance: selecting a stage-theme card invokes the REAL set_stage_template(worship) — same command the Presentation surface's picker uses");

        // Keyboard reachability (QA finding on PR #68, ClickUp 17tnw2axwfm): the roving tabIndex
        // this radiogroup sets up is USELESS without an arrow-key handler moving focus between
        // the tabIndex=-1 siblings — a keyboard-only operator could reach the selected card and
        // nothing else. ArrowRight from the now-selected "worship" card must move focus AND
        // selection to "scripture" (wrapping), exactly like the Providers & Privacy radiogroup's
        // own onRadioKeydown already does.
        // Re-query: the click above triggered a full renderStageThemes() rebuild of the host, so
        // the ORIGINAL apWor node is now detached — focusing it would silently no-op.
        var apWorNow = el("ap-stage-theme-worship");
        apWorNow.focus();
        var apCallsBeforeKey = window.__calls.length;
        apWorNow.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true, cancelable:true}));
        await sleep(20);
        ok(document.activeElement === el("ap-stage-theme-scripture"),
           "Settings/Appearance: ArrowRight on the stage-theme radiogroup moves FOCUS to the next card");
        ok(window.__calls.slice(apCallsBeforeKey).some(function(c){ return c.cmd === "set_stage_template" && c.args.template === "scripture"; }),
           "Settings/Appearance: ArrowRight also SELECTS the newly-focused card (matches native radiogroup behaviour)");
        V.stage_template = "worship"; // restore the fixture default for anything after this block

        // Default slide theme: real builtin_themes() names populate the select; left disabled
        // because there is no distinct "default new-deck theme" field to write to (see
        // settings-appearance.js's header comment) — never a fabricated "SelahCue Classic" option.
        ok(window.__calls.some(function(c){ return c.cmd === "builtin_themes"; }),
           "Settings/Appearance: the slide-theme select is populated from the real builtin_themes() command");
        var apSlideOpts = Array.prototype.map.call(document.querySelectorAll("#ap-slide-theme option"), function(o){ return o.textContent; });
        ok(apSlideOpts.indexOf("Classic") !== -1, "Settings/Appearance: the real built-in theme name renders in the select (" + apSlideOpts.join(",") + ")");
        ok(el("ap-slide-theme").disabled, "Settings/Appearance: the slide-theme select is disabled (informational only — no writable 'default' field exists)");

        // Every control with NO backend command anywhere in this app is a REAL, disabled control —
        // never one that looks live and silently forgets the choice on the next reload.
        ["ap-textsize","ap-high-contrast","ap-stage-textsize","ap-reduced-motion"].forEach(function(id){
          ok(el(id).disabled, "Settings/Appearance: #" + id + " is honestly disabled — no persistence exists for it yet");
        });
        var apDensityBtns = document.querySelectorAll("#ap-density .pp-segmented-btn");
        var apClockBtns = document.querySelectorAll("#ap-clockfmt .pp-segmented-btn");
        ok(apDensityBtns.length === 2 && Array.prototype.every.call(apDensityBtns, function(b){ return b.disabled; }),
           "Settings/Appearance: the density segmented control's two options are both honestly disabled");
        ok(apClockBtns.length === 2 && Array.prototype.every.call(apClockBtns, function(b){ return b.disabled; }),
           "Settings/Appearance: the stage-clock-format segmented control's two options are both honestly disabled");

        // Theme Designer link-out: a REAL navigation, not a dead row styled like a link.
        el("ap-open-theme-designer").click();
        ok(el("surface-theme-designer").classList.contains("active"),
           "Settings/Appearance: 'Open Theme Designer' really navigates to the Theme Designer surface");
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("appearance");
        await sleep(20);

        // Contrast (NFR-020): same bar as About above, applied to Appearance's own body copy and
        // its honest "not saved yet" notes (tertiary — text-muted is the CORRECT token there).
        // Against the row's own real computed background, same reasoning as the About check.
        var apRowD = document.querySelector("#set-page-appearance .set-row-d");
        var apRowBg = getComputedStyle(apRowD.closest(".set-row")).backgroundColor;
        var apRowDc = _contrast(getComputedStyle(apRowD).color, apRowBg);
        ok(apRowDc >= 4.5, "Settings/Appearance: .set-row-d body copy clears AA-normal on its own row background (" + apRowDc.toFixed(2) + ":1)");
      }

      // === Settings › General (Figma 577:126 — story 17tnw2axwet, closes SET-001) ===
      {
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("general");
        ok(el("set-page-general") && !el("set-page-general").hidden && el("set-placeholder").hidden,
           "Settings/General: the real page renders (SET-001 page-level MISSING closed, not the shared placeholder)");

        // Startup: "Live Console" is marked selected because that is the REAL shipped default
        // (index.html's #surface-console carries `active` at rest). The claim itself is checked
        // at the PYTHON level below (SURFACE_CONSOLE_ACTIVE_AT_BOOT, against the pristine source —
        // by THIS point in the suite many earlier checks have navigated away, so the live DOM's
        // current .active class no longer reflects the app's boot-time default).
        var gnStartupCards = document.querySelectorAll("#gn-startup-list .pp-radio-card");
        ok(gnStartupCards.length === 3 && gnStartupCards[0].classList.contains("sel") &&
           !gnStartupCards[1].classList.contains("sel") && !gnStartupCards[2].classList.contains("sel"),
           "Settings/General: exactly the Live Console startup option renders selected");
        // Quinn's QA review of PR #70: these cards have no click handler at all (no backend to
        // persist the choice) but the shared .pp-radio-card base class always applies
        // cursor:pointer + a hover highlight, so they LOOKED clickable while doing nothing — a
        // "looks interactive, silently does nothing" defect, unlike every other inert control in
        // this batch, which uses native `disabled`. A plain <div> radio card has no such
        // attribute to lean on, so this is a computed-style check instead.
        ok(getComputedStyle(gnStartupCards[1]).cursor === "default",
           "Settings/General: an inert (non-selected) startup card computes cursor:default, not the base class's cursor:pointer — it no longer looks clickable");

        // Keyboard shortcuts: read LIVE from the app's own #shortcuts overlay, never a hand-typed
        // second copy that could drift from the real bindings.
        var realShortcutRows = document.querySelectorAll("#shortcuts .sc-row").length;
        var gnShortcutRows = document.querySelectorAll("#gn-shortcuts-list .set-row").length;
        ok(realShortcutRows > 0 && gnShortcutRows === realShortcutRows,
           "Settings/General: the shortcuts table renders exactly the real #shortcuts overlay's row count (" + gnShortcutRows + " of " + realShortcutRows + ")");
        ok(/Blackout the output/.test(document.getElementById("gn-shortcuts-list").textContent) &&
           /Command palette/.test(document.getElementById("gn-shortcuts-list").textContent),
           "Settings/General: real shortcut descriptions render verbatim (not the Figma mock's different row set — no 'Stage message'/'Undo' rows this build doesn't bind)");
        ok(!/Stage message|Undo\b/.test(document.getElementById("gn-shortcuts-list").textContent),
           "Settings/General (control): the Figma mock's un-bound shortcuts (Stage message ⌘M, Undo ⌘Z) do NOT appear — this page never renders a keybinding the app doesn't really have");
        ok(el("shortcuts").hidden !== false, "Settings/General (control): the real shortcuts overlay starts hidden");
        el("gn-open-shortcuts").click();
        ok(el("shortcuts").hidden === false,
           "Settings/General: 'Open the full shortcuts overlay' really opens the app's own shortcuts dialog");
        // Goes through the REAL openShortcuts() (app.js's generic data-open="shortcuts" wiring),
        // not a bespoke `overlay.hidden = false` — proven by checking the SAME side effect
        // openShortcuts() itself produces: focus moves to #sc-close, the dialog's Tab-trap anchor
        // (Cody's review of PR #70: a prior version opened the dialog visually but left focus
        // behind it, outside the aria-modal region).
        ok(document.activeElement === el("sc-close"),
           "Settings/General: opening the shortcuts overlay moves focus into it (via the real openShortcuts(), not a bespoke hidden-flip) — the Tab-trap is live");
        el("sc-close").click();

        // Real cross-page navigation.
        el("gn-manage-updates").click();
        ok(el("set-page-about") && !el("set-page-about").hidden,
           "Settings/General: 'Manage updates' really navigates to About & Licensing");
        setSettingsPage("general");
        el("gn-open-preservice").click();
        ok(el("surface-preservice").classList.contains("active"),
           "Settings/General: 'Open Pre-service Check' really navigates to the Pre-service Check surface");
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("general");

        // Every control with no backend command is honestly disabled.
        ["gn-org-name","gn-lang","gn-region","gn-reduced-motion"].forEach(function(id){
          ok(el(id).disabled, "Settings/General: #" + id + " is honestly disabled — no persistence exists for it yet");
        });
      }

      // === Settings › Scripture & Translations (Figma 578:124 — story 17tnw2axwet, closes SET-002) ===
      {
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("scripture");
        await sleep(40);
        ok(el("set-page-scripture") && !el("set-page-scripture").hidden && el("set-placeholder").hidden,
           "Settings/Scripture: the real page renders (SET-002 page-level MISSING closed, not the shared placeholder)");

        // Installed translations: real list_translations() data.
        ok(window.__calls.some(function(c){ return c.cmd === "list_translations"; }),
           "Settings/Scripture: the installed-translations list is loaded via the real list_translations() command");
        var scRows = document.querySelectorAll("#sc-translations-list .pp-radio-card");
        ok(scRows.length === 6, "Settings/Scripture: all 6 real translations render as their own card, bundled AND downloadable (" + scRows.length + ")");
        ok(/King James Version/.test(scRows[0].textContent) && /PUBLIC DOMAIN/.test(scRows[0].textContent),
           "Settings/Scripture: each card names the real translation and its real public-domain badge");
        ok(/Young's Literal Translation/.test(scRows[5].textContent) && !/PUBLIC DOMAIN/.test(scRows[5].textContent),
           "Settings/Scripture: the one downloadable (not-yet-installed) translation does NOT get the Public Domain badge its bundled siblings get — parity with the equivalent About page check (Cody's review of PR #70 noted this page lacked its own copy)");

        // Default translation: real, TWO-WAY-SYNCED with the summary select (handoff §9) — driving
        // either one must move the other, both via the SAME set_preferred_translation the
        // Providers & Privacy panel already uses. This block runs after the earlier Providers &
        // Privacy checks, which already changed this SAME shared fixture's preferred_translation
        // (PP C-003 sets it to WEB) — force it back to the fixture's original KJV first rather
        // than assuming whatever the suite left it at.
        window.__pp.preferred_translation = "KJV";
        setSettingsPage("scripture");
        await sleep(40);
        ok(document.getElementById("sc-translation-KJV").classList.contains("sel"),
           "Settings/Scripture (control): KJV (the fixture's real preferred_translation) renders selected before any interaction");
        ok(document.getElementById("sc-default-select").value === "KJV",
           "Settings/Scripture (control): the summary select starts in sync with the radio's real default");
        var scCallsBefore = window.__calls.length;
        document.getElementById("sc-translation-ASV").click();
        await sleep(30);
        ok(window.__calls.slice(scCallsBefore).some(function(c){ return c.cmd === "set_preferred_translation" && c.args.code === "ASV"; }),
           "Settings/Scripture: clicking a translation card invokes the REAL set_preferred_translation(ASV)");
        ok(document.getElementById("sc-translation-ASV").classList.contains("sel") &&
           !document.getElementById("sc-translation-KJV").classList.contains("sel"),
           "Settings/Scripture: the radio list re-renders from the backend-confirmed default, not an optimistic guess");
        ok(document.getElementById("sc-default-select").value === "ASV",
           "Settings/Scripture: the summary select followed the radio's change — one shared value, not two");
        // Drive it the OTHER direction: changing the select must move the radio too.
        var scSel = document.getElementById("sc-default-select");
        scSel.value = "WEB";
        scSel.dispatchEvent(new Event("change"));
        await sleep(30);
        ok(document.getElementById("sc-translation-WEB").classList.contains("sel"),
           "Settings/Scripture: changing the summary select moves the radio's selection too — confirmed two-way sync");

        // Keyboard reachability on this SECOND new radiogroup in this batch (proactively covered
        // this time rather than caught by review, per the standing requirement from ClickUp
        // 17tnw2axwfm).
        document.getElementById("sc-translation-WEB").focus();
        var scCallsBeforeKey = window.__calls.length;
        document.getElementById("sc-translation-WEB").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true, cancelable:true}));
        await sleep(30);
        ok(window.__calls.slice(scCallsBeforeKey).some(function(c){ return c.cmd === "set_preferred_translation"; }),
           "Settings/Scripture: ArrowRight on the translations radiogroup selects the next card — keyboard-reachable, not just clickable");

        // The per-row "show in picker" toggle is real but genuinely inert (no backend field) —
        // clicking it must NOT accidentally trigger the card's own onSelect (set_preferred_translation).
        var scShowToggle = document.querySelector("#sc-translations-list .pp-toggle.set-inert input");
        ok(scShowToggle && scShowToggle.disabled,
           "Settings/Scripture: the per-row 'show in picker' toggle is honestly disabled — not configurable yet");

        // Every other control with no backend command is honestly disabled — never a fake Rebuild/
        // Clear-history button that would look actionable and do nothing.
        ["sc-verses-per-slide","sc-history-len"].forEach(function(id){
          ok(el(id).disabled, "Settings/Scripture: #" + id + " is honestly disabled — no persistence exists for it yet");
        });
        var scSegBtns = document.querySelectorAll("#sc-versenum .pp-segmented-btn");
        ok(scSegBtns.length === 3 && Array.prototype.every.call(scSegBtns, function(b){ return b.disabled; }),
           "Settings/Scripture: the verse-numbers segmented control's three options are all honestly disabled");

        // Theme Designer link-out: a REAL navigation.
        document.getElementById("sc-open-theme-designer").click();
        ok(el("surface-theme-designer").classList.contains("active"),
           "Settings/Scripture: 'Open Theme Designer' really navigates to the Theme Designer surface");
        document.querySelector('.nav-item[data-surface="settings"]').click();

        // Contrast (NFR-020).
        // Scoped to a .set-row-d that is actually INSIDE a .set-row — the page's first .set-row-d
        // by document order is the Installed Translations section's lead paragraph, which sits
        // directly in the section (no enclosing .set-row), so an unscoped query would hand
        // .closest(".set-row") a null and throw before this check ever ran.
        var scRowD = document.querySelector("#set-page-scripture .set-row .set-row-d");
        var scRowBg = getComputedStyle(scRowD.closest(".set-row")).backgroundColor;
        var scRowDc = _contrast(getComputedStyle(scRowD).color, scRowBg);
        ok(scRowDc >= 4.5, "Settings/Scripture: .set-row-d body copy clears AA-normal on its own row background (" + scRowDc.toFixed(2) + ":1)");
      }

      // === Settings › Network & Mobile — SET-009 addendum (story 17tnw2axweu) ===
      {
        // Reset the shared __remote fixture to a known state — the earlier Remote Control block
        // (Frame G aside) already approved/revoked devices against this SAME global, so this
        // point in the suite cannot assume the pristine two-devices-one-pending fixture.
        window.__remote.devices = [
          { device_id: "dev-aa01", name: "Booth iPad", platform: "iPadOS", role: "producer", idle_secs: 3, pinned: false },
          { device_id: "dev-bb02", name: "Guest tablet", platform: "iPadOS", role: "viewer", idle_secs: 210, pinned: false },
        ];
        window.__remote.pending = [
          { device_id: "dev-cc03", name: "Anna's iPhone", platform: "iOS", fingerprint: "A1 B2 C3 D4", waiting_secs: 8 },
        ];
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("network");
        await sleep(40);
        ok(window.__calls.some(function(c){ return c.cmd === "remote_snapshot"; }),
           "Settings/Network SET-009: the paired-devices summary is loaded via the real remote_snapshot() command");
        ok(/2 paired total/.test(el("net-paired-summary").textContent) && /1 online/.test(el("net-paired-summary").textContent) && /1 idle\/offline/.test(el("net-paired-summary").textContent) && /1 pending request/.test(el("net-paired-summary").textContent),
           "Settings/Network SET-009: the summary reflects REAL device counts, never the Figma mock's fabricated '3 paired total · 2 connected · 1 offline' (\"" + el("net-paired-summary").textContent + "\")");
        el("net-open-roles").click();
        ok(el("surface-remote").classList.contains("active"),
           "Settings/Network SET-009: 'Manage roles & grants' really navigates to the Remote Control surface");
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("network");
        ["net-advertised-name"].forEach(function(id){
          ok(el(id).disabled, "Settings/Network SET-009: #" + id + " is honestly disabled — no LAN-defaults backend exists yet");
        });
      }

      // === Settings › Outputs & Displays (Figma 579:124 — story 17tnw2axweu, closes SET-003) ===
      {
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("outputs");
        await sleep(40);
        ok(el("set-page-outputs") && !el("set-page-outputs").hidden && el("set-placeholder").hidden,
           "Settings/Outputs: the real page renders (SET-003 page-level MISSING closed, not the shared placeholder)");

        // Displays: REAL view().displays, never the Figma mock's fabricated "Display 1 — 1920×1080
        // · 60Hz · Built-in" text.
        var outRows = document.querySelectorAll("#out-displays-list .set-row");
        ok(outRows.length === V.displays.length && outRows.length > 0,
           "Settings/Outputs: every real display renders as its own row (" + outRows.length + " of " + V.displays.length + ")");
        ok(new RegExp(V.displays[0].name).test(outRows[0].textContent) && outRows[0].textContent.indexOf(String(V.displays[0].width)) !== -1,
           "Settings/Outputs: a display row names the REAL display and its real resolution, not fabricated numbers");

        // Identify displays: REAL command.
        var outCallsBefore = window.__calls.length;
        el("out-identify").click();
        await sleep(30);
        ok(window.__calls.slice(outCallsBefore).some(function(c){ return c.cmd === "identify_outputs"; }),
           "Settings/Outputs: 'Identify' invokes the REAL identify_outputs() command");

        // Manage screens: real navigation.
        el("out-open-screens").click();
        ok(el("surface-screens").classList.contains("active"),
           "Settings/Outputs: 'Manage screens' really navigates to the Screens & Outputs surface");
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("outputs");

        // Whole sections the FIGMA ITSELF marks SOON render that way — not fabricated content.
        ok(/COMING SOON/.test(el("out-peroutput-h").textContent) && /COMING SOON/.test(el("out-netoutputs-h").textContent),
           "Settings/Outputs: PER-OUTPUT CONFIG and NETWORK OUTPUTS render as the Figma frame's own SOON sections");

        // Every control with no backend command is honestly disabled.
        ["out-venue-select","out-audio-device"].forEach(function(id){
          ok(el(id).disabled, "Settings/Outputs: #" + id + " is honestly disabled — no persistence exists for it yet");
        });
      }

      // === Settings › Security (Figma 582:124 — story 17tnw2axweu, closes SET-005) ===
      {
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("security");
        await sleep(20);
        ok(el("set-page-security") && !el("set-page-security").hidden && el("set-placeholder").hidden,
           "Settings/Security: the real page renders (SET-005 page-level MISSING closed, not the shared placeholder)");

        // CORRECTION vs. the Figma mock: at-rest encryption must NOT read as ON — verified against
        // the real Cargo.toml/main.rs, not the design mock, which draws it enabled.
        ok(/NOT YET ON/.test(el("set-page-security").textContent),
           "Settings/Security: at-rest encryption honestly reads NOT YET ON — the Figma mock's 'ON' badge does not match this build (Cargo.toml has no `encryption` feature; main.rs calls Database::open, not open_encrypted)");
        ok(!/VERIFIED · ANTI-ROLLBACK ON/.test(el("set-page-security").textContent),
           "Settings/Security (control): no fabricated 'VERIFIED · ANTI-ROLLBACK ON' update-signature badge — no update mechanism exists in this build to verify anything");
        ok(!/Sarah.s iPad|FOH Mac/.test(el("set-page-security").textContent),
           "Settings/Security (control): no fabricated audit-log rows (the Figma mock's 'Sarah's iPad' / 'FOH Mac' entries) — this build has no audit data source");

        // Real link-outs.
        el("sec-open-providers").click();
        ok(el("set-page-providers") && !el("set-page-providers").hidden,
           "Settings/Security: 'Cloud providers & consent' really navigates to Providers & Privacy");
        setSettingsPage("security");
        el("sec-open-about").click();
        ok(el("set-page-about") && !el("set-page-about").hidden,
           "Settings/Security: 'Manage & install updates' really navigates to About & Licensing");
        setSettingsPage("security");
        el("sec-open-network-revoke").click();
        ok(el("set-page-network") && !el("set-page-network").hidden,
           "Settings/Security: 'Revoke all paired devices' really navigates to Network & Mobile");
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("security");

        // Danger Zone / destructive-control regression guard (Sana's security review of PR #71:
        // these had zero test coverage at all — mutation-proved by removing `disabled` from the
        // purge button and observing the WHOLE suite still passed). Matches the same pattern
        // Storage's equivalent controls already use (asserted across 6 buttons).
        var secDangerButtons = Array.prototype.filter.call(
          document.querySelectorAll("#set-page-security .pp-optin-btn"),
          function(b){ return /Purge & rotate…/.test(b.textContent); }
        );
        ok(secDangerButtons.length === 1 && secDangerButtons[0].disabled,
           "Settings/Security: 'Purge secrets & rotate database key' is honestly disabled — no purge/rotate command exists in this build");
        var secAppLockToggle = document.querySelector("#set-page-security .pp-toggle.set-inert input");
        ok(secAppLockToggle && secAppLockToggle.disabled,
           "Settings/Security: 'Require passphrase on launch' is honestly disabled — not available in this build yet");
        // The copy contradiction Sana's review caught: the purge row must not claim to
        // "re-encrypt" a database this build never encrypted in the first place.
        ok(!/re-encrypts the database/.test(document.getElementById("set-page-security").textContent),
           "Settings/Security (control): the purge/rotate row does not claim to 're-encrypt' a database — this build has no at-rest encryption to re-encrypt (contradiction Sana's review found, fixed)");
      }

      // === Settings › Network & Mobile — destructive-control regression guard (SET-009) ===
      // Same gap class Sana's review found on Security, checked here too rather than only where
      // it was reported: Regenerate certificate and Revoke all devices had no disabled-state test
      // coverage either.
      {
        setSettingsPage("network");
        var netDangerButtons = Array.prototype.filter.call(
          document.querySelectorAll("#set-page-network .pp-optin-btn"),
          function(b){ return /Regenerate…|Revoke all…/.test(b.textContent); }
        );
        ok(netDangerButtons.length === 2 && netDangerButtons.every(function(b){ return b.disabled; }),
           "Settings/Network SET-009: 'Regenerate certificate' and 'Revoke all devices' are both honestly disabled (" + netDangerButtons.length + " checked) — no cert-regenerate or revoke-all command exists in this build");
      }

      // === Settings › Storage & Backups (Figma 583:124 — story 17tnw2axweu, closes SET-006) ===
      {
        setSettingsPage("storage");
        await sleep(40);
        ok(el("set-page-storage") && !el("set-page-storage").hidden && el("set-placeholder").hidden,
           "Settings/Storage: the real page renders (SET-006 page-level MISSING closed, not the shared placeholder)");

        // Disk usage: REAL disk_free() — never the Figma mock's fabricated "38.2 GB free of 256 GB".
        ok(window.__calls.some(function(c){ return c.cmd === "disk_free"; }),
           "Settings/Storage: disk usage is loaded via the real disk_free() command");
        ok(/42\.0 GB free of 500\.0 GB/.test(el("st-disk-usage").textContent),
           "Settings/Storage: the real fixture's disk_free() numbers render verbatim (\"" + el("st-disk-usage").textContent + "\")");

        // Import/export: real link-out to the Service Plan surface (never a duplicated file-picker).
        el("st-open-plan").click();
        ok(el("surface-plan").classList.contains("active"),
           "Settings/Storage: 'Import or export a service plan' really navigates to the Service Plan surface");
        document.querySelector('.nav-item[data-surface="settings"]').click();
        setSettingsPage("storage");

        // Destructive actions with no backend command are honestly disabled, never a live-looking
        // button with nothing behind it.
        var stDangerButtons = Array.prototype.filter.call(
          document.querySelectorAll("#set-page-storage .pp-optin-btn"),
          function(b){ return /Back up now|Run check|Restore…|Change location…|Clear cache|Export diagnostics…/.test(b.textContent); }
        );
        ok(stDangerButtons.length >= 5 && stDangerButtons.every(function(b){ return b.disabled; }),
           "Settings/Storage: every backup/restore/location/cache/diagnostics action is honestly disabled (" + stDangerButtons.length + " checked) — this build has no backend command behind any of them");
      }

      // === CON-172/173 (Frame G.4, node 347:128) — the console's own scoped empty-plan state.
      // Runs LAST: it is destructive to V.items, and this file has no dedicated sync helper for
      // the plan list (unlike __syncSlides), so it rides the real 1 Hz poll like every other
      // direct-V-mutation check in this file — restored immediately after so nothing downstream
      // depends on plan contents.
      document.querySelector('.nav-item[data-surface="console"]').click();
      var planItemsBackup = V.items.slice();
      V.items = [];
      await wWait(function(){ return !!document.querySelector("#plan .plan-console-empty"); });
      var planEmpty = document.querySelector("#plan .plan-console-empty");
      ok(!!planEmpty, "CON-172: the console's #plan column renders a SCOPED empty state when the plan has no items (previously blank)");
      ok(planEmpty.textContent.indexOf("Your plan is empty") >= 0,
         "CON-172: the empty-state heading matches the Figma spec verbatim — 'Your plan is empty'");
      ok(planEmpty.textContent.indexOf("Add a song, scripture, or slide to build your order of service.") >= 0,
         "CON-172: the empty-state body copy matches the Figma spec verbatim");
      ok(!!planEmpty.querySelector(".plan-console-empty-icon"), "CON-172: the icon tile renders");
      var planAddBtn = document.querySelector(".plan-console-empty-add");
      ok(!!planAddBtn && planAddBtn.textContent.trim() === "+ Add first item",
         "CON-173: the '+ Add first item' action renders with the Figma spec's exact label");
      ok(!planAddBtn.disabled, "CON-173: '+ Add first item' is a REAL, enabled action — not a disabled placeholder");
      var planImportBtn = document.querySelector(".plan-console-empty-import");
      // Cody's PR #85 review: the Service Plan surface's primary Import ("Import a run
      // sheet…" -> planImportPlan) is a REAL, working importer, not unbuilt — only the
      // separate "Import a plan bundle…" control is. This button must not claim otherwise.
      ok(!!planImportBtn && !planImportBtn.disabled && planImportBtn.textContent.trim() === "Import a run sheet…",
         "CON-173: 'Import' names and links to the REAL Service Plan importer — never claims a shipped capability is 'coming soon'");
      planImportBtn.click();
      ok(document.getElementById("surface-plan").classList.contains("active"),
         "CON-173: 'Import a run sheet…' really navigates to the Service Plan surface, where the real importer lives — not a dead click");
      document.querySelector('.nav-item[data-surface="console"]').click();
      planAddBtn.click();
      ok(document.getElementById("surface-plan").classList.contains("active"),
         "CON-173: '+ Add first item' really navigates to the Service Plan surface, where the real add-item palette lives — not a dead click");
      // restore
      document.querySelector('.nav-item[data-surface="console"]').click();
      V.items = planItemsBackup;
      await wWait(function(){ return !document.querySelector("#plan .plan-console-empty"); });
      ok(!document.querySelector("#plan .plan-console-empty") && document.querySelectorAll("#plan .item").length === planItemsBackup.length,
         "CON-172 (control): restoring items clears the empty state and the normal plan list renders again");

    } catch(e){ R.push("FAIL: exception "+e.message+" @ "+(e.stack||"").split("\n")[1]); }
    el("__r").textContent = "RESULTS\n"+R.join("\n")+"\nDONE("+R.length+")";
  }
  // Wait until app.js has BOOTED (a host call fired + the designer DOM exists), then run.
  // The designer built-ins now load lazily on first activation (audit L3), so the driver
  // opens the designer itself — we no longer gate readiness on `builtin_themes`.
  var tries=0;
  var iv=setInterval(function(){
    tries++;
    var booted = window.__calls.length > 0 && document.getElementById("td-bg");
    if (booted){ clearInterval(iv); setTimeout(run, 50); }
    else if (tries>300){ clearInterval(iv); el("__r").textContent="RESULTS\nFAIL: app never booted\nDONE(1)"; }
  }, 30);
</script>
"""

# Inject the stub into <head> (before app.js runs) and the driver before </body>.
# The <base> MUST precede the <link rel=stylesheet href="app.css"> (line ~7) — a <base>
# only affects relative URLs that come AFTER it, so injecting it at </head> left app.css
# resolving against the /tmp temp file (never loading). Inject it right after <head> so the
# real app.css (and app.js) load and CSS-dependent checks are meaningful.
html = html.replace("<head>", '<head><base href="file://' + DIST + '/">', 1)
html = html.replace("</head>", STUB + CSS_SRC + RUST_CONSTS + "</head>", 1)
html = html.replace("</body>", DRIVER + "</body>", 1)

with tempfile.NamedTemporaryFile(
    "w", suffix=".html", delete=False, dir=tempfile.gettempdir()
) as f:
    f.write(html)
    path = f.name

try:
    try:
        out = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             # Budget is VIRTUAL time, fast-forwarded — it costs little wall clock, but every
             # driver step that waits on the app's own 1 s view poll spends a full second of it.
             # Raised from 9000 with the window-semantics checks, which wait on two real polls, and
             # again to 20000 with the Design 2.0 parity block: that block navigates surfaces and
             # waits on host round-trips at the very end of the run, so a run in which several of
             # its checks legitimately FAIL (each spending its wait budget) must still have time
             # left to WRITE the results. Without the headroom a real regression surfaces as
             # "NO RESULTS BLOCK" (exit 2, infra) instead of a named FAIL.
             # Raised again to 60000 for the Frame G recovery block, which is wait-heavy by
             # nature: every edge check must observe TWO successive 1 Hz polls (that is the
             # whole point of holds/recoveries being counters), so it spends ~1s of virtual
             # time per assertion pair and cannot be made cheaper without testing something
             # weaker than the real poll path.
             # Raised again to 75000 for CON-156/157/158/161/172/173 (17tnw2axptc): the NDI
             # runtime-unavailable/restore-to-unknown pair and the console empty-plan
             # add/restore pair are each two more real 1 Hz-poll round trips, all landing
             # BEFORE the already wait-heavy Frame G recovery block above — without the extra
             # headroom the run reached check ~1725 (mid-G.3) and then genuinely ran out of
             # virtual time, which surfaced as "NO RESULTS BLOCK" (an infra failure) rather
             # than any named FAIL, exactly the failure mode this comment block already warns
             # about. Confirmed empirically: a debug build that writes PROGRESS every 25
             # checks showed the run stalled inside the pre-existing G.3 edges-across-polls
             # section, not inside anything new.
             "--virtual-time-budget=75000", "--dump-dom", "file://" + path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90).stdout
    except subprocess.TimeoutExpired:
        # A hung Chrome is an INFRA failure (exit 2), distinct from a check FAIL (exit 1).
        print("FAIL: headless Chrome timed out (infra) — no RESULTS produced")
        sys.exit(2)
    m = re.search(r"RESULTS\n(.*?)\nDONE\((\d+)\)", out, re.S)
    if not m:
        print("NO RESULTS BLOCK — dom head:\n", out[:1500]); sys.exit(2)
    body = m.group(1)
    count = int(m.group(2))
    print(body)
    fails = [line for line in body.splitlines() if line.startswith("FAIL")]
    print("\n=== %d checks, %d FAIL ===" % (count, len(fails)))
    # Guard against the suite count DRIFTING in either direction: a `<` floor only ever
    # catches SHRINKING (a driver regression / early return running fewer checks). It never
    # catches GROWING past the recorded value, which lets EXPECTED_MIN_CHECKS drift stale-low
    # with no red build to catch it — this has happened three times (1514/1520, 1544/1589,
    # 1589/1593), each caught only by a human/reviewer noticing an oddity, never by this gate.
    # The third time (17tnw2axpt9, PR #63) root-caused to a merge commit (00f9a50) keeping one
    # parallel branch's own recorded EXPECTED_MIN_CHECKS instead of re-deriving it after both
    # branches' new checks were combined. An exact match forces every branch that adds/removes
    # a check to conflict on this constant during rebase and re-derive it explicitly — that
    # friction is the point; it's what was skipped at the merge that caused drift #3.
    # Bump EXPECTED_MIN_CHECKS to the new count when you add or remove a check — always by
    # actually running the suite, never by hand arithmetic (see the log above this constant).
    if count != EXPECTED_MIN_CHECKS:
        print(
            "FAIL: %d checks ran; expected exactly %d (bump me to %d if this is a real "
            "add/remove — never hand-derive; re-run and use the measured count)"
            % (count, EXPECTED_MIN_CHECKS, count)
        )
        sys.exit(4)
    sys.exit(1 if fails else 0)
finally:
    os.unlink(path)
