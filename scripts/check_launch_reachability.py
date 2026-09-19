#!/usr/bin/env python3
"""Guards 86akcmzyq's follow-up acceptance criterion (see `.github/pull_request_template.md`'s
"Feature-flag reachability" section): a Cargo feature the product has decided must be reachable
from `make launch` / `make operator` under their DEFAULT (no override) invocation must actually
show up in those targets' resolved `--features` list, or this fails a build instead of relying
on the PR template's unchecked checkbox -- exactly the human step that let 86akby7d8 (sermon
notes, `openai-notes`) ship, merge, pass four-reviewer review, and stay invisible from the one
command a developer actually runs (86akcmzyq's own root cause).

THIS HAPPENED A SECOND TIME BEFORE THIS SCRIPT EVEN SHIPPED (86akby7th, `cloud-stt`, closed by
86akd10dq): PR #24 (this script) was authored before PR #22 (`cloud-stt`) merged, so the
then-hardcoded `REQUIRED_DEFAULT_FEATURES = {"dev-keys", "openai-notes"}` had no way to know
`cloud-stt` existed, let alone that it needed the same guarantee -- the check passed green while
Cloud transcription was exactly as unreachable as sermon notes had been. A hand-maintained set in
a script three directories away from the feature it describes is the same shape of hole as the PR
template's unchecked box: both rely on a human remembering a SEPARATE action in a SEPARATE place.
See DERIVATION below for how this version closes that.

DERIVATION (86akd10dq). The required set is no longer a literal set in this file. It is derived
by reading each registered crate's own `[features]` table (see MULTI-CRATE SCOPE) and requiring
every feature there (other than `default`) to carry TWO tags in its own comment block -- the same
comment block that already has to explain, in prose, why the feature defaults off:

  `LAUNCH_REACHABILITY: REQUIRED | AUTO | OPT-IN`
    * `REQUIRED` -- a product/owner decision (86akcmzrd is the precedent) that this feature must
      show up in `make launch`/`make operator`'s DEFAULT resolved `--features` list,
      unconditionally (modulo an explicit `AI=0`/`STT=0`/`RELEASE=1` override).
    * `AUTO` -- reachable only when a local probe succeeds (e.g. `stt`: cmake on PATH; `ndi`: the
      SDK is vendored), by design. Not required, because nobody has made the owner call that this
      must work with no toolchain/SDK present.
    * `OPT-IN` -- no dev launch target auto-enables this; reachable only via an explicit
      `OP_FEATURES=`/`cargo build --features` override. Typically because the thing it talks to
      (a live endpoint, say) does not exist yet, so there is nothing for a default `make launch`
      to usefully reach.

  `RELEASE: SAFE | UNSAFE` (86akd10dq remediation -- Sana S-1 / Cody Finding A / Quinn High)
    * `UNSAFE` -- must never reach a `RELEASE=1`/`--release` build of the crate that declares it.
      Cross-checked against the Makefile's own `RELEASE_UNSAFE_FEATURES` registry (see RELEASE
      CROSS-CHECK, and NEW-1 within it, below) so the two cannot drift apart silently the way the
      reachability set used to before this script existed at all.
    * `SAFE` -- no release-boundary concern (reads no developer-only credential, or ships in a
      real release artefact already, e.g. `stt` in the Windows installer).

A feature with NO tag on either axis, more than one tag on an axis, or an unrecognised tag value,
is a HARD FAILURE of this script -- not a silent "assume not required" / "assume safe". This is
the actual fix, not the relocation: today, a new off-by-default feature can land with no
reachability or release-boundary decision recorded anywhere and nothing objects. After this
change, it cannot -- the gate that already runs on every `make ci` and every CI push refuses to
pass until someone tags it on BOTH axes, which forces the decision to be made (and recorded, in
the one file a reviewer is already looking at for this exact feature) in the SAME PR that adds
the feature, rather than in a follow-up commit to an unrelated script or Makefile line that is
easy to forget entirely.

MULTI-CRATE SCOPE (86akd10dq remediation -- Cody Finding B / Quinn, independently found the same
gap). The first cut of this derivation only ever read `selahcue-operator/Cargo.toml`. But `make
launch` also builds `selahcue-desktop` (`build-output`'s `cargo build ... -p selahcue-desktop
$(DESKTOP_FEATURES)`), which has its own `[features]` table (`encryption`, `ndi`) feeding
`DESKTOP_FEATURES` in the same Makefile -- and nothing ever opened that file, so a future
off-by-default feature there got ZERO enforcement: not a failed check, not even a "missing tag"
error, because the crate was never in scope to begin with. `CRATE_MANIFESTS` below is now every
crate `make launch`/`make operator` build directly with their own `--features` flag, and every
one of them is fully in scope for both tag axes.

`CRATE_MANIFESTS` ITSELF IS NOT DERIVED, and that is an explicit, argued choice rather than an
oversight matching the earlier one: there is no independent, machine-readable source of "which
crate directories make launch/operator build directly" the way Cargo.toml is the source for a
crate's own feature names, or `cargo metadata` is for a workspace's package list -- reading it
back out of the Makefile's own `-p`/`--manifest-path` tokens would mean reading the very artefact
this script exists to check, exactly the circularity the original design rejected for feature
names. The difference that makes a hardcoded registry defensible here and not for feature names:
a new crate entering the dev-launch path is a rare, visible, architectural event (a new Cargo.toml
plus a new Makefile recipe line, both already under heavy review), unlike a new Cargo feature,
which is added routinely, inside one crate, as part of nearly every feature PR. Trusting a
hardcoded list unconditionally would still be the same mistake, though -- so
`unregistered_crate_mentions` parses every `-p <name>` / `crates/<name>/Cargo.toml` token that
actually appears in a REAL `make -n launch`/`make -n operator` dry run and hard-fails if any name
is not a key in `CRATE_MANIFESTS`, so a third crate joining the dev-launch path without a matching
registry entry is a loud failure, not a silent blind spot.

`TARGETS` (Quinn's consistency point, closed rather than argued down). The first cut of this
reasoning gave `TARGETS` a WEAKER treatment than `CRATE_MANIFESTS` for a reason that does not
survive scrutiny: "a new dev-launch target is rare and reviewed, so a human is already looking"
is exactly the reasoning this section just declined to accept for crate names, which got a real
drift check instead of trust. `TARGETS` stays hardcoded for a genuinely different reason -- there
is no independent source for "which Makefile targets are dev-launch entry points" the way Cargo.toml
is the source for feature names or `cargo metadata` is for crate names, so deriving the SET from
outside the Makefile is not possible the way it is for those two -- but it is NOT left untested:
`dev_launch_entry_point_targets` derives the set of targets that OUGHT to be in `TARGETS` from a
different, checkable property of the same file -- every target whose prerequisite list names both
`stt-preflight` and `release-ai-guard`, the two guards that gate a real build of the STT/AI
feature computation this script checks -- and `TARGETS` must equal that set exactly. Verified
(Quinn): `diff <(make -n run) <(make -n launch)` is byte-identical but for a cosmetic error-string
substitution (`run: launch` is a plain alias); `run-release`/`launch-release` reduce to a
recursive `$(MAKE) launch RELEASE=1` recipe command, not a static prerequisite, so dry-running
`launch` already exercises the identical computation; `build-operator` DOES carry both
prerequisites in its own right and is now a member of `TARGETS`, even though its dry run is
textually redundant with what `launch` already shows -- included rather than carved out as an
unexplained exception now that leaving it out is a hard failure instead of a silent gap.

COLLISION GUARD (Quinn's point on `missing_features()`). The dry-run comparison below unions
every `--features <list>` occurrence anywhere in a target's dry-run text into one flat set,
rather than tying a specific required feature to the exact command line that builds ITS crate.
Quinn is right that this could in principle let an unrelated crate's flag satisfy a requirement
by name coincidence -- and worse, `run`/`operator`'s recipe on Darwin shells out to
`scripts/run_operator_macapp.sh --features ...`, which carries no `-p`/`--manifest-path` token
of its own AT ALL in a `make -n` dry run (the manifest path lives inside that script, invisible
to a dry run that never executes it) -- so tying every required feature to an explicit per-line
crate attribution is not reliably possible on the exact platform (macOS) this check is wired into
CI for. Instead: the collision check inline in `collect_all_tags` (see its `owner` dict) makes it
a hard failure for two registered crates to declare the same feature name at all -- verified by
adding a real colliding `cloud-stt` feature name to `selahcue-desktop/Cargo.toml` (Quinn) and
confirming the check names both crates before doing anything else. With that invariant held, a feature
name found ANYWHERE in a target's resolved `--features` union is unambiguous evidence about the
one crate that could have produced it, regardless of whether that specific line's crate identity
was parseable -- a guarantee that does not depend on macOS's wrapper-script blind spot, and is
simpler than trying to attribute lines that a dry run cannot always identify.

RELEASE CROSS-CHECK (Sana S-1 / Cody Finding A / Quinn High, the Make-half of the `cloud-stt`
release-boundary remediation). Every feature tagged `RELEASE: UNSAFE` across every registered
crate must appear, as an exact token, in the Makefile's own `RELEASE_UNSAFE_FEATURES := ...`
line -- and every token in that line must correspond to a feature actually tagged `UNSAFE`
somewhere. This is the same shape of guarantee DERIVATION gives the reachability set, applied to
the release boundary: a Makefile edit that silently drops a token from `RELEASE_UNSAFE_FEATURES`,
or a Cargo.toml edit that tags a feature `UNSAFE` without updating the Makefile, fails this check
instead of drifting apart silently.

NEW-1 (Sana, verified live against the real repo, not just this claim). The first cut of this
cross-check read `RELEASE_UNSAFE_FEATURES` with `re.search`, which finds only the FIRST
occurrence of that assignment in the Makefile. GNU Make's `:=` is a plain reassignment, so a
SECOND, weaker `RELEASE_UNSAFE_FEATURES := ...` line inserted between the real registry and
`release-ai-guard`'s use of it silently becomes the value the guard actually sees -- Sana proved
this makes `release-ai-guard` accept `OP_FEATURES=stt,cloud-stt RELEASE=1` (exit 0, no refusal)
while this script, still trusting the first (stronger) occurrence, printed success. That is
exactly the drift this mechanism claims to make impossible, so "the two cannot drift apart
silently" was false as written before this fix. `find_release_unsafe_occurrences`/
`resolve_release_unsafe_line` now find EVERY occurrence and hard-fail on anything but exactly
one, closing this specific hole -- the same ambiguous-is-a-hard-failure treatment a duplicate
LAUNCH_REACHABILITY/RELEASE tag already gets. (A `RELEASE_UNSAFE_FEATURES` line appended AFTER
`release-ai-guard` is inert -- verified -- since nothing reads the variable again past that
point; this script does not attempt to reason about position, only about count, because
distinguishing "before" from "after" the guard would mean re-implementing Make's own parser.)

NEW-1b (Sana, verified live; Quinn independently reproduced the same gap against the real
guard). "Exactly one assignment" is only as strong as what counts as an assignment: the original
fix was anchored at `^` and matched only `:=`, so two spellings still weakened the guard while
this check stayed green -- a plain `=` recursive reassignment, and a space-indented `:=` (Make
strips leading whitespace before parsing a line; the regex did not). Both yield exit 0 on `make
release-ai-guard RELEASE=1 OP_FEATURES=stt,cloud-stt`. `RELEASE_UNSAFE_LINE` now matches any
assignment-shaped line -- `:=`, `+=`, `?=`, `!=`, or plain `=`, with an optional `override`
prefix and any leading indentation -- while still refusing anything but exactly one occurrence
of any of them (over-strictness is correct here: `?=` and `+=` are not actually dangerous the
way a second `:=`/`=`/`!=` is, but this script does not try to reason about which operators are
safe to duplicate). `$(eval ...)`-constructed or `include`-composed assignments remain beyond
what text analysis alone can see, and are not attempted.

NEW-2 (Quinn/the coordinator). Matching tokens between the tags and `RELEASE_UNSAFE_FEATURES`
proves the two REGISTRIES agree; it does not prove anything is actually enforced. Scoped to
`selahcue-operator` today because `release-ai-guard` (the only Make-level guard that exists) only
ever filters `OP_FEATURES_WORDS` -- it cannot see `DESKTOP_FEATURES` at all. Tagging a
`selahcue-desktop` feature `UNSAFE` and adding its token to `RELEASE_UNSAFE_FEATURES` would make
this cross-check agree and print "confirmed release-unsafe and matched against the Makefile" --
true about the registries, false about the build: `make -n launch RELEASE=1 NDI=1` would still
resolve `--features ndi --release` and `release-ai-guard` would still exit 0. A "confirmed"
message about something unenforced is worse than no message -- the same shape of bug as the
original one, one level up. `CRATES_WITH_RELEASE_GUARD` names which registered crates actually
have a Make-level guard behind their `UNSAFE` tags (`selahcue-operator` alone, today), and
`crates_with_unenforced_release_unsafe_features` refuses to reach the success message at all if
any other registered crate is ever tagged `UNSAFE` with nothing enforcing it.

NEW-2b (Sana, driving the exact probe the coordinator asked for -- the most consequential thing
this PR produced). NEW-2's registry is itself a CLAIM with no verification: Sana proved that
adding `"selahcue-desktop"` to `CRATES_WITH_RELEASE_GUARD` with NO guard built still made every
check above agree and print "confirmed release-unsafe" -- the finding had been relocated behind
a third unverified registry, not structurally closed. `CRATES_WITH_RELEASE_GUARD` is now
`dict[crate, Make target]`, and for every entry the real check actually runs
`make <target> RELEASE=1 OP_FEATURES=<a real, current UNSAFE token for that crate>` -- a real,
no-build, sub-second invocation -- via `probe_release_guard`, and `classify_probe` requires a
GENUINE refusal: GNU Make's own signature for "this target's recipe ran and one of its commands
exited non-zero" (a line containing `*** [<target>] Error <n>`), checked POSITIVELY rather than
by ruling out one specific bad shape, so a missing `make` binary, a renamed or deleted target, an
unrelated Makefile syntax error elsewhere in the file, or the wrong working directory are all
classified as `COULD_NOT_RUN` -- a problem with the PROBE -- rather than misreported as
`DID_NOT_REFUSE` -- a problem with the GUARD (the coordinator's caution, addressed generally
rather than for the one shape first demonstrated). A benign-input positive control (`OP_FEATURES=`
empty, same target, same `RELEASE=1`) then confirms the guard DISCRIMINATES rather than refusing
unconditionally, which the hostile probe alone cannot tell apart from a guard hardwired to reject
everything -- the same trap this repo's own testing conventions document
(`an_over_cap_frame_renders_correctly_and_bypasses_the_cache`), applied here. This is, as far as
this script or `make ci`/CI can tell, the FIRST automated exercise `release-ai-guard` has ever
had with a hostile input in its existence -- every prior confirmation of its behaviour was a
human running it by hand.

NEW-2's-final-round (Sana). One token was not enough. The probe above originally tried only the
alphabetically-first `UNSAFE` token for a crate; a PARTIAL weakening of the Makefile registry --
`cloud-stt` still present, `dev-keys`/`openai-notes` quietly dropped -- would still pass, because
the one token actually probed was still genuinely refused. `pick_probe_tokens` now returns EVERY
`UNSAFE` token for the crate, and each is probed independently, requiring every one to refuse
before the benign control even runs. Reproduced live: dropping `dev-keys`/`openai-notes` from
`RELEASE_UNSAFE_FEATURES` while keeping `cloud-stt` now fails with both tokens individually
reported as `DID_NOT_REFUSE`.

THE CONSUMING LOOP ITSELF (Quinn, the same night -- the round after the round above). Fixing
`pick_probe_tokens` to return every token was not the same as fixing anything that CONSUMES the
return value. The loop that iterated `pick_probe_tokens`' output used to live inline in `main()`,
untested as its own unit -- `pick_probe_tokens` and `classify_probe` each had mutation-verified
coverage individually, but the procedural glue combining them did not. Quinn truncated that loop
to `probe_tokens[:1]`: self-test stayed 31/31 green (nothing exercised the loop's own bound), the
real check against a healthy Makefile stayed green, and the real check against Sana's exact
`export RELEASE_UNSAFE_FEATURES := cloud-stt` partial weakening ALSO stayed green -- printing
"confirmed release-unsafe" while `dev-keys`/`openai-notes` were genuinely unenforced -- because
truncating the loop meant only `cloud-stt` (still genuinely refused) was ever probed. The
vulnerability the round above closed could be silently reopened by narrowing the code that
consumes two already-correct, already-tested functions -- indistinguishable, if left untested,
from every other instance of this bug class this whole script exists to eliminate.

Fixed by extracting the ENTIRE chain -- pick tokens, probe each, fold, benign control -- into
`verify_crate_release_guard`, with the probing mechanism itself swapped for a call-recording fake
in self-test (`prober`). `main()` is reduced to one call to this function per registered crate;
there is nothing left in `main()` to truncate. Critically, a pure fold over a caller-supplied
`list[ProbeOutcome]` (the first fix considered) would NOT have caught Quinn's mutation: a fold
over a list already truncated before the fold ever saw it is still a perfectly correct fold, so
the fix has to reach the CALLER of `pick_probe_tokens`, not just aggregate what it is handed.
Self-test's fake `prober` records every call made and asserts that list against
`pick_probe_tokens`' own output directly -- three cases: every token refused (asserting the full,
in-order call list, not just the verdict), a MIXED refused/not-refused pair (proving the loop
does not short-circuit on the first result, which an all-not-refused fixture could not prove),
and an explicit count/set cross-check against `pick_probe_tokens`. Verified against Quinn's exact
mutation, reproduced on this function rather than `main()`'s now-deleted loop: truncating
`verify_crate_release_guard`'s own `for probe_token in probe_tokens:` line to `probe_tokens[:1]`
turns all three new self-test cases red, then restored.

ONE LEVEL OUT, THE SAME NIGHT AGAIN (Quinn, verifying `verify_crate_release_guard` itself before
signing off). The inner loop above is genuinely closed -- Quinn reproduced the exact-mutation
claim independently. But the loop that CALLED `verify_crate_release_guard`, once per registered
crate, still lived inline in `main()`: `for crate_name, guard_target in
CRATES_WITH_RELEASE_GUARD.items(): problems.extend(verify_crate_release_guard(...))`. `main()`
is never exercised by `self_test()` at all, so nothing tested this outer loop's own bound. Quinn
truncated it to `list(CRATES_WITH_RELEASE_GUARD.items())[:0]` -- no crate probed, no guard
invoked, at all -- and got 31/31 self-test green plus a real check against the healthy repo
printing unqualified success with the guard never once invoked. Unlike NEW-2c, this was LIVE, not
latent: `CRATES_WITH_RELEASE_GUARD` has exactly one entry today, so "skip everything" and "skip
nothing" were, until this fix, indistinguishable outcomes -- two rounds of protection deleted by
narrowing one line, every gate staying green.

Closed with the identical discipline, one level out: `verify_all_release_guards` wraps the
`CRATES_WITH_RELEASE_GUARD.items()` loop, taking `verify_crate` as an injectable dependency the
same way `verify_crate_release_guard` takes `prober`. Self-test injects a call-recording fake
`verify_crate` and asserts the recorded `(crate_name, guard_target)` pairs against
`CRATES_WITH_RELEASE_GUARD`'s own keys, READ LIVE at assertion time -- not a hand-written
`{"selahcue-operator": ...}` literal, which would have passed just as well whether the registry
had one entry or none. Verified the way Quinn verifies "reads live, not a copy" (the same check
Quinn has now asked for three times on this PR, each time on a different join in this chain):
temporarily added a second, fake entry to `CRATES_WITH_RELEASE_GUARD` itself and confirmed the
self-test assertion tracked the change to two entries with no test-code edit, rather than staying
green against a value that no longer described the registry. Verified against Quinn's exact
mutation before reporting closed: truncating `verify_all_release_guards`'s own
`for crate_name, guard_target in CRATES_WITH_RELEASE_GUARD.items():` line to
`list(CRATES_WITH_RELEASE_GUARD.items())[:0]` turns the new self-test cases red, then restored.

WHY THIS TERMINATES THE REGRESS. `main()` is now a single, unconditional line --
`problems.extend(verify_all_release_guards(per_crate_tags))` -- with no loop of its own left to
truncate. The chain from "which crates are registered" (`CRATES_WITH_RELEASE_GUARD`, read live)
to "which tokens does each one need to refuse" (`pick_probe_tokens`, read live) to "did probing
actually happen" (the injected `prober`) is pinned at every join that exists, each verified by
mutating the REAL thing one level down and confirming the test tracks it rather than a
hand-copied stand-in going stale. There is no further "loop that calls this loop" left in
`main()` for a future review to find one level out again.

THE LAYERING ACTUALLY COMPOSING (Sana). Two further spellings genuinely weaken the guard while
evading NEW-1b's broadened regex entirely: `export RELEASE_UNSAFE_FEATURES := <weaker>` and a
`define ... endef` block are both assignment shapes outside `:=`/`+=`/`?=`/`!=`/`=` with only an
optional `override` prefix -- exactly the `$(eval ...)`/`include`-composition territory this
script's own docstring already renounces for text analysis. Text analysis cannot win that race.
But the real check still went RED on both, THROUGH NEW-2B, NOT THE REGEX: `make release-ai-guard
RELEASE=1 OP_FEATURES=cloud-stt` genuinely does not refuse once either spelling has taken effect,
so `classify_probe` reports `DID_NOT_REFUSE` and the check fails behaviourally. This is the
strongest argument for having built both layers rather than either alone: the regex catches the
spellings it knows by name, cheaply and specifically; the probe catches the ones nobody
enumerated, because it tests the EFFECT on the guard rather than the TEXT that produced it. Any
full weakening of the guard, however spelled -- including routes this script explicitly declines
to parse -- fails `make ci` behaviourally.

PROBE ATTRIBUTION, PINNED (Cody raised a Medium-High misattribution concern; Quinn reached the
opposite conclusion about the same mutation; the coordinator tested GNU Make's actual semantics
in a scratch Makefile rather than trust either verdict). The mutation: rename ONLY
`release-ai-guard:`'s own declaration line (e.g. to `release-ai-guard-RENAMED:`), leaving
`.PHONY` and every prerequisite reference (`launch: stt-preflight release-ai-guard`, ...)
untouched -- a plausible refactor accident, since prerequisite/`.PHONY` lists are edited far
less carefully than rule bodies. Probing the OLD name then yields `make: Nothing to be done for
`release-ai-guard'.`, exit 0 -- Make treats a still-`.PHONY` target with no rule body as a
satisfied no-op, not a missing target. Cody argued this should classify `COULD_NOT_RUN` (the
probe's own target reference is stale; the guard's logic, now homeless, is untouched). Verified
against GNU Make directly: after this exact mutation, `make launch RELEASE=1
OP_FEATURES=cloud-stt` actually BUILDS -- the guard does not stop it, because nothing on any real
build path invokes it under its new name any more. The dependent target runs regardless of
whether the detached rule's own logic is "correct". `DID_NOT_REFUSE` is therefore the accurate
classification, not `COULD_NOT_RUN`: this is a genuine, exploitable guard defeat -- the exact
failure this whole mechanism exists to catch -- not evidence the PROBE is stale. Routing it to
`COULD_NOT_RUN` would have reported a real release-boundary opening as "fix your registry",
which is worse than the misattribution it would have replaced. `classify_probe` is intentionally
unchanged from before this finding; only the `DID_NOT_REFUSE` message was extended to name the
detached-recipe possibility explicitly (alongside "the filter logic itself is wrong"), so a
developer checks both rather than only auditing the conditional. Pinned in self-test as
`DID_NOT_REFUSE` so this does not get relitigated a third time.

FEATURE-NAME AUTHORITY (Sana S-2). The line-based comment scanner above cannot see every legal
TOML spelling of a feature key -- an indented key, or a quoted key (`"cloud-stt" = [...]`), both
of which Cargo accepts and both of which would silently exit the tag-enforcement regime with no
diagnostic under a narrower regex. Rather than widen the regex to chase spellings by hand (the
exact hand-maintained-list shape this whole script exists to move away from), the real check
cross-references each crate's tagged feature names against `cargo metadata`'s own authoritative
feature list for that crate's manifest. Any name `cargo metadata` reports that the scanner did
not find a tag for -- regardless of why the scanner missed it -- is a hard failure naming the
feature, not a silent gap. (Not run in `--self-test`: it would require invoking `cargo` against
the real manifests, which the self-test's whole point is to avoid needing.)

KNOWN CONVENTIONS AND LIMITS (Cody's two residuals plus NEW-2c -- none live today, all worth
writing down rather than leaving as an implicit assumption the next change could quietly break).

  * NEW-2c (the coordinator, ticketed as 86akd3wd3, not fixed here). The probe proves "this
    registered target refuses this token when fed through `OP_FEATURES`" -- it does not, and
    structurally cannot as written, prove "this crate's own real feature-resolution path is
    guarded". Registering `CRATES_WITH_RELEASE_GUARD["selahcue-desktop"] = "release-ai-guard"`
    (an impostor entry -- that target is the operator's own guard) still passes today: it
    genuinely refuses a token fed through `OP_FEATURES`, and the probe has no way to know that
    `selahcue-desktop`'s real build line uses `DESKTOP_FEATURES` instead and is never touched by
    `release-ai-guard` at all. Latent -- no `selahcue-desktop` feature is tagged `UNSAFE` today,
    so the only real entry in the registry is `selahcue-operator`'s own, correctly-wired one --
    and narrower than the gap NEW-2b closed, since an impostor entry must now name a target that
    genuinely refuses via `OP_FEATURES`, and exactly one target in this Makefile qualifies. See
    86akd3wd3 for the two fix shapes considered (a per-crate probe variable, vs. a dry-run
    assertion that the crate's own release build line cannot carry the token) and why this is a
    design question deserving its own round rather than a same-night sixth one.

  * `crate_mentions` recognises exactly two shapes: a `-p <name>` token, or a
    `--manifest-path .../crates/<name>/Cargo.toml` path. A future Makefile recipe written some
    other way -- e.g. `cd crates/newthing && cargo build --features x` -- would name a crate this
    script cannot see at all, escaping the MULTI-CRATE SCOPE drift check entirely rather than
    failing loudly. Every recipe in this Makefile today uses one of the two recognised shapes;
    this is a convention this script depends on, not a guarantee it can verify by itself.
  * `FEATURES_FLAG` matches the literal substring `--features <list>` anywhere in a dry run's
    text, including inside an `@echo` status line -- it does not distinguish an actual build
    invocation from a line that merely mentions the words for a human to read. Nothing in the
    Makefile today echoes that exact substring outside `OPRUN`'s own real `--features` flag, but
    a future status message that happened to print it verbatim (rather than, say, `$(OP_FEATURES)`
    with different formatting) would be silently counted as evidence of a build that never
    happens.
  * `dev_launch_entry_point_targets` (Quinn) uses "carries both `stt-preflight` AND
    `release-ai-guard` as prerequisites" as a PROXY for "is a default dev-launch entry point that
    needs the reachability guarantee enforced" -- the two are not logically the same, and Quinn
    named two plausible future targets where they would part ways: a fast-iteration target that
    hardcodes `RELEASE=0` internally and drops `release-ai-guard` as pointless for it, while still
    consuming the default `OP_FEATURES` computation and still needing REQUIRED features
    reachable; or a target scoped to skip live transcription entirely that drops `stt-preflight`
    while keeping `release-ai-guard`, since `dev-keys`/`openai-notes` still apply to it. Neither
    exists today (Quinn checked every target referencing `$(OPRUN)`/`$(OP_FEATURES)`/`$(OP)` and
    found no live counterexample), so this is a residual assumption to know about, not a bug to
    fix -- the next person adding a dev-launch target that does not carry both prerequisites for
    a considered reason should update this heuristic (or add an explicit exemption) rather than
    discover the mismatch from a failing `TARGETS` cross-check with no context for why.

HOW THE CHECK WORKS. Runs `make -n <target>` (GNU Make's dry run: prints the resolved recipe
text without executing any of it) for both `launch` and `operator`, with AI/STT/RELEASE/
OP_FEATURES cleared from the environment first so the DEFAULT resolution is what gets checked,
not whatever override happened to be exported in the calling shell (Make's `?=` respects an
inherited environment variable exactly like a command-line override). Every `--features
<comma-list>` occurrence anywhere in that dry-run text is unioned into one set (see COLLISION
GUARD for why that is safe) and every REQUIRED feature must be an exact comma-split TOKEN in that
union, never a substring match: the Makefile's `stt-preflight`/`OP_FEATURES_WORDS` comments name
`cloud-stt` containing "stt" as a substring as exactly the trap a naive `in` check would fall
into.

CROSS-PLATFORM SCOPE. Wired into CI on Linux and macOS (see `.github/workflows/ci.yml`), Windows
excluded. Originally Linux-only, citing this pipeline's `nfr` job as precedent for "make is not
cross-OS-reliable" -- PR #24 remediation (86akcmzyq) tested that precedent and found it did not
hold: `nfr`'s macOS skip is about a one-time recorded timing baseline and its Windows skip is
about a POSIX shell script doing memory measurement, neither of which bears on Make itself being
unreliable cross-OS. The feature computation this script inspects has zero $(UNAME)-conditional
branching (verified by reading the Makefile) -- the only OS-conditional code there picks NDI
library paths and which shell wrapper launches the operator, not which Cargo features get
requested -- and every self-test mutation below also passes running this script on macOS.
Windows stays excluded because GNU Make dry-run parsing on that runner is unproven, unlike Linux
and macOS which both ship `make` by default. `make ci` runs this unconditionally, since that
always runs on whatever machine the developer is actually on.

Self-test: `check_launch_reachability.py --self-test` exercises the dry-run comparison, the
Cargo.toml tag parser (both axes), the cross-crate collision guard, the crate-registry drift
check, the TARGETS derivation, the Makefile RELEASE_UNSAFE_FEATURES cross-check (including the
NEW-1/NEW-1b assignment-shape cases), the NEW-2 unenforced-crate-tag check, and NEW-2b's pure
decision logic (`pick_probe_tokens`'s every-UNSAFE-token behaviour, `classify_probe`'s seven
outcome shapes including the PINNED detached-recipe case two reviewers disagreed about, and
`verify_crate_release_guard`'s consuming loop via an injected call-recording `prober` (an
all-refused case, a MIXED refused/not-refused case, and an explicit cross-check against
`pick_probe_tokens`' own token count/set, verified to turn red against Quinn's exact
`probe_tokens[:1]` mutation), and `verify_all_release_guards`'s OUTER consuming loop via an
injected call-recording `verify_crate` (asserted against `CRATES_WITH_RELEASE_GUARD`'s own keys
read live, verified to turn red against Quinn's exact `[:0]` truncation, and verified to track a
real second entry added to that registry rather than staying green against a stale copy) --
against fixed fixtures, including several built by deleting or corrupting a tag from a fixture
`[features]` block (the exact regressions this version closes) -- without touching the real
Makefile, the
real Cargo.toml files, or invoking `make`/`cargo` at all, so it runs anywhere. The real check
(`check_launch_reachability.py`, no flag) reads the real Cargo.toml files, the real Makefile,
and shells out to the actual `make -n launch` / `make -n operator` / `cargo metadata` /
`probe_release_guard`'s real `make <target> RELEASE=1 OP_FEATURES=...` invocations in this repo
checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = REPO_ROOT / "implementation" / "desktop"
MAKEFILE_PATH = REPO_ROOT / "Makefile"

# See MULTI-CRATE SCOPE in the module docstring for what this is, and why it is a hardcoded
# registry rather than something derived, with an automatic drift check against it regardless.
CRATE_MANIFESTS: dict[str, Path] = {
    "selahcue-operator": DESKTOP_ROOT / "crates" / "selahcue-operator" / "Cargo.toml",
    "selahcue-desktop": DESKTOP_ROOT / "crates" / "selahcue-desktop" / "Cargo.toml",
}

# NEW-2 (Quinn/the coordinator): which registered crates actually HAVE a Make-level mechanism
# enforcing their `RELEASE: UNSAFE` tags, and the Make TARGET that mechanism is. Today that is
# `release-ai-guard` alone, and it filters only `OP_FEATURES_WORDS` (selahcue-operator's resolved
# features) -- it does not, and cannot as written, see `DESKTOP_FEATURES` (selahcue-desktop's).
# Tagging a `selahcue-desktop` feature `UNSAFE` today would make the RELEASE CROSS-CHECK above
# pass (the tag and the RELEASE_UNSAFE_FEATURES token would agree) and print "confirmed
# release-unsafe and matched against the Makefile" -- true about the REGISTRY, false about
# anything actually being enforced. A claim of "confirmed" about something unenforced is worse
# than no claim at all: it is the shape of the original bug (a feature's real state disagreeing
# with what a green check reports) one level up.
#
# NEW-2b (Sana, driving the exact probe the coordinator asked for): Sana proved this registry
# ITSELF has no verification -- adding `"selahcue-desktop"` here with NO guard built still made
# the whole check pass, because nothing had ever confirmed that `CRATES_WITH_RELEASE_GUARD`'s
# claims describe a REAL, FIRING guard rather than a name in a set. `crates_with_unenforced_
# release_unsafe_features` below still refuses to print success for a registered crate with no
# entry here at all; membership in this dict is now ALSO required to correspond to a Make target
# that actually refuses a hostile build -- see `probe_release_guard` and its use in `main`, which
# runs `make <target> RELEASE=1 OP_FEATURES=<a real UNSAFE token>` for every entry here (a real,
# no-build, sub-second invocation) and hard-fails if it does not refuse. This is also, as far as
# this script or `make ci`/CI can tell, the FIRST automated exercise `release-ai-guard` has ever
# had with a hostile input -- every prior confirmation of its behaviour was a human running it by
# hand (Sana twice, Cody, Quinn, the coordinator).
CRATES_WITH_RELEASE_GUARD: dict[str, str] = {"selahcue-operator": "release-ai-guard"}

# See DERIVATION in the module docstring for what each tag on each axis means.
LAUNCH_TAGS = {"REQUIRED", "AUTO", "OPT-IN"}
RELEASE_TAGS = {"SAFE", "UNSAFE"}

# TARGETS (Quinn's consistency point). Every Makefile target whose prerequisite list names BOTH
# `stt-preflight` AND `release-ai-guard` -- the two guards that gate a real build carrying the
# STT/AI feature computation this script checks. Verified (Quinn): `diff <(make -n run) <(make -n
# launch)` is byte-identical but for a cosmetic error-string substitution (`run: launch` is a
# plain alias), and `run-release`/`launch-release` reduce to a recursive `$(MAKE) launch
# RELEASE=1` recipe command rather than a static prerequisite -- neither needs its own entry
# because dry-running `launch` already exercises the identical computation. `build-operator` DOES
# list both prerequisites in its own right (it is `launch`'s own build step, reused) and is
# textually redundant with what dry-running `launch` already shows -- included anyway rather than
# carved out as a silent exception, once `TARGETS_MATCHES_MAKEFILE` below makes leaving it out a
# hard failure instead of an unexplained omission.
TARGETS = ("launch", "operator", "build-operator")

FEATURES_FLAG = re.compile(r"--features\s+(\S+)")
FEATURE_DEF = re.compile(r"^([A-Za-z0-9_-]+)\s*=")
LAUNCH_TAG_RE = re.compile(r"^#\s*LAUNCH_REACHABILITY:\s*(\S+)")
RELEASE_TAG_RE = re.compile(r"^#\s*RELEASE:\s*(\S+)")
CRATE_NAME_IN_MANIFEST_PATH = re.compile(r"crates/([A-Za-z0-9_-]+)/Cargo\.toml")
CRATE_NAME_VIA_DASH_P = re.compile(r"(?:^|\s)-p\s+([A-Za-z0-9_-]+)")
# NEW-1b (Sana, verified live): anchored at `^` with no leading `\s*`, and matching only `:=`,
# the original regex missed two spellings that also weaken the guard while staying green: a
# plain `=` recursive reassignment, and a space-indented `:=` (Make strips leading whitespace
# before parsing a line; this regex did not). Broadened to any assignment-shaped line -- `:=`,
# `+=`, `?=`, `!=`, or plain `=`, with an optional `override` prefix -- while still refusing
# anything but exactly one such line (see `resolve_release_unsafe_line`): `?=` (only takes effect
# if unset, so a second one is inert) and `+=` (appends, so a second one only ever widens the set)
# are not actually dangerous the way a second `:=`/`=`/`!=` is, but this script still treats any
# count other than one as ambiguous rather than trying to reason about which operators are safe
# to duplicate -- over-strictness is the right default here, since no legitimate reason exists
# for a second assignment of any flavour. `$(eval ...)`-constructed or `include`-composed
# assignments are beyond what text analysis alone can see and are not attempted.
RELEASE_UNSAFE_LINE = re.compile(
    r"^\s*(?:override\s+)?RELEASE_UNSAFE_FEATURES\s*(?::=|\+=|\?=|!=|=)\s*(.*)$", re.MULTILINE
)
# A Makefile target-definition line: `name: prereq1 prereq2 ## help text`. The negative lookahead
# excludes `:=`/variable assignment lines (`OP_FEATURES_WORDS := ...`), which would otherwise
# match the same "identifier followed by colon" shape.
MAKEFILE_TARGET_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?!=)\s*(.*)$", re.MULTILINE)


class FeatureTags(NamedTuple):
    reachability: str
    release: str


def _validate_axis(
    feature: str, axis: str, found: list[str], valid: set[str], problems: list[str]
) -> str | None:
    """Shared validation for one tag axis on one feature: exactly one occurrence, and it must be
    a recognised value. Appends a human-readable diagnostic to `problems` and returns None for
    anything else -- missing, ambiguous (>1), or unrecognised."""
    if not found:
        problems.append(f"`{feature}` has no `{axis}:` tag in its comment block")
        return None
    if len(found) > 1:
        problems.append(
            f"`{feature}` has {len(found)} `{axis}:` tags in its comment block "
            f"(ambiguous): {found}"
        )
        return None
    if found[0] not in valid:
        problems.append(
            f"`{feature}`'s `{axis}:` tag {found[0]!r} is not one of {sorted(valid)}"
        )
        return None
    return found[0]


def parse_feature_tags(cargo_toml_text: str) -> tuple[dict[str, FeatureTags], list[str]]:
    """Every non-`default` feature declared in the `[features]` table of a Cargo.toml, mapped to
    its `(LAUNCH_REACHABILITY, RELEASE)` tags -- plus a list of human-readable problems for any
    feature missing a tag on either axis, carrying more than one, or carrying an unrecognised
    one. A Cargo.toml with NO `[features]` table at all is not a problem -- it simply has nothing
    to tag (needed now that `CRATE_MANIFESTS` covers more than one crate; a future registered
    crate with no optional features must not be flagged as broken for lacking a section it has
    no reason to have).

    Deliberately line-based rather than a TOML parser: a TOML parser would discard the very
    comments this function exists to read. The contract this depends on: each tag line sits
    somewhere in the CONTIGUOUS block of `#`-prefixed lines immediately above the feature's own
    `name = [...]` line, with nothing but comment lines between them. See FEATURE-NAME AUTHORITY
    in the module docstring for the spellings this cannot see, and how the real check catches
    them anyway via `cargo metadata`.
    """
    lines = cargo_toml_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "[features]")
    except StopIteration:
        return {}, []

    end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s != "[features]":
            end = i
            break

    tags: dict[str, FeatureTags] = {}
    problems: list[str] = []
    i = start + 1
    while i < end:
        m = FEATURE_DEF.match(lines[i])
        if m:
            name = m.group(1)
            if name != "default":
                block: list[str] = []
                j = i - 1
                while j > start and lines[j].strip().startswith("#"):
                    block.append(lines[j].strip())
                    j -= 1
                block.reverse()
                launch_found = [tm.group(1) for l in block if (tm := LAUNCH_TAG_RE.match(l))]
                release_found = [tm.group(1) for l in block if (tm := RELEASE_TAG_RE.match(l))]
                launch_tag = _validate_axis(
                    name, "LAUNCH_REACHABILITY", launch_found, LAUNCH_TAGS, problems
                )
                release_tag = _validate_axis(
                    name, "RELEASE", release_found, RELEASE_TAGS, problems
                )
                if launch_tag is not None and release_tag is not None:
                    tags[name] = FeatureTags(launch_tag, release_tag)
        i += 1
    return tags, problems


def collect_all_tags() -> tuple[dict[str, FeatureTags], dict[str, dict[str, FeatureTags]], list[str]]:
    """Parse every registered crate's Cargo.toml. Returns `(merged, per_crate, problems)`:
    `merged` is every feature name -> tags, valid only because of the collision check below (see
    COLLISION GUARD in the module docstring); `per_crate` keeps each crate's own tags separately,
    needed by the `cargo metadata` cross-check, which must compare like-for-like against one
    manifest at a time.
    """
    merged: dict[str, FeatureTags] = {}
    owner: dict[str, str] = {}
    per_crate: dict[str, dict[str, FeatureTags]] = {}
    problems: list[str] = []
    for crate_name, manifest_path in CRATE_MANIFESTS.items():
        crate_tags, crate_problems = parse_feature_tags(manifest_path.read_text())
        per_crate[crate_name] = crate_tags
        rel = manifest_path.relative_to(REPO_ROOT)
        problems.extend(f"{crate_name} ({rel}): {p}" for p in crate_problems)
        for feature_name, feature_tags in crate_tags.items():
            if feature_name in owner:
                problems.append(
                    f"feature name `{feature_name}` is declared by BOTH `{owner[feature_name]}` "
                    f"and `{crate_name}` -- this script unions every crate's --features tokens "
                    "from the dry run without attributing a line to a specific crate (see "
                    "COLLISION GUARD in the module docstring), so two crates sharing a feature "
                    "name would let one crate's flag silently satisfy the other's requirement. "
                    "Rename one of them."
                )
                continue
            merged[feature_name] = feature_tags
            owner[feature_name] = crate_name
    return merged, per_crate, problems


def required_from_tags(tags: dict[str, FeatureTags]) -> set[str]:
    """Features tagged `LAUNCH_REACHABILITY: REQUIRED` -- the set this script asserts is
    reachable from `make launch`/`make operator` by default."""
    return {name for name, t in tags.items() if t.reachability == "REQUIRED"}


def release_unsafe_from_tags(tags: dict[str, FeatureTags]) -> set[str]:
    """Features tagged `RELEASE: UNSAFE` -- the set that must never reach a RELEASE=1/--release
    build, cross-checked against the Makefile's own `RELEASE_UNSAFE_FEATURES` registry."""
    return {name for name, t in tags.items() if t.release == "UNSAFE"}


def crates_with_unenforced_release_unsafe_features(
    per_crate_tags: dict[str, dict[str, FeatureTags]]
) -> dict[str, set[str]]:
    """For every registered crate NOT in `CRATES_WITH_RELEASE_GUARD`, any feature(s) it tags
    `RELEASE: UNSAFE` anyway -- a tag with no Make-level mechanism behind it. See NEW-2 next to
    `CRATES_WITH_RELEASE_GUARD` for why this must be a hard failure rather than letting the
    RELEASE CROSS-CHECK's agreement (tag present, Makefile token present) print a false
    "confirmed release-unsafe" for a crate nothing actually blocks."""
    unenforced: dict[str, set[str]] = {}
    for crate_name, crate_tags in per_crate_tags.items():
        if crate_name in CRATES_WITH_RELEASE_GUARD:
            continue
        unsafe = {name for name, t in crate_tags.items() if t.release == "UNSAFE"}
        if unsafe:
            unenforced[crate_name] = unsafe
    return unenforced


def pick_probe_tokens(per_crate_tags: dict[str, dict[str, FeatureTags]], crate_name: str) -> list[str]:
    """EVERY token to pass, one probe each, as `OP_FEATURES=<token>` when probing `crate_name`'s
    registered release guard: every feature that crate itself tags `RELEASE: UNSAFE`, sorted for
    determinism (real and current -- picking a fixed name here instead would silently stop
    probing anything the day that specific feature is ever retagged or removed).

    NEW-2's-final-round (Sana): a single token is not enough. A PARTIAL weakening of the guard --
    one token still refused, one or more others quietly dropped from the effective registry --
    would pass a probe that only ever tries the alphabetically-first token, because that one
    token alone would still trigger a genuine refusal. Each of a crate's UNSAFE tokens carries
    its own independent claim ("this build must never carry ME"), so each gets its own
    independent probe; the cost is a few more sub-second, no-build `make` invocations, not a
    qualitatively different check. A crate with NO `UNSAFE` feature at all has nothing a
    hostile-input probe could meaningfully test, which is itself a NEW-2b-shaped problem worth
    surfacing rather than silently skipping -- see this function's use in `main`.
    """
    unsafe = sorted(name for name, t in per_crate_tags.get(crate_name, {}).items() if t.release == "UNSAFE")
    if not unsafe:
        raise ValueError(
            f"`{crate_name}` is in CRATES_WITH_RELEASE_GUARD but tags no feature `RELEASE: "
            "UNSAFE` -- there is nothing for a hostile-input probe to test. Either it should not "
            "be in that registry, or a feature is missing its UNSAFE tag."
        )
    return unsafe


class ProbeOutcome(NamedTuple):
    """Which of three things happened when a release guard was probed. `kind` is one of:
    `"REFUSED"` (a genuine refusal), `"DID_NOT_REFUSE"` (the guard ran and let the build
    through), or `"COULD_NOT_RUN"` (the PROBE itself is broken -- `make` missing, the target
    renamed, an unrelated Makefile error, wrong working directory -- which says nothing about
    whether the guard works). `detail` carries the raw output or exception text for a human to
    read. Kept as three states rather than a bool specifically so a broken probe is never
    reported as a broken guard -- see `classify_probe`."""

    kind: str
    detail: str


def classify_probe(returncode: int | None, output: str, guard_target: str) -> ProbeOutcome:
    """Classify one probe result. `returncode` is `None` when `make` itself could not even be
    invoked (see `probe_release_guard`).

    A GENUINE refusal is recognised POSITIVELY, not by ruling out one known-bad shape. GNU
    Make's own signature for "this target's recipe ran and one of its commands exited non-zero"
    is a line containing `*** [<guard_target>] Error <n>` -- the exact text `release-ai-guard`'s
    own `exit 1` produces. Checking for that positively (rather than the prior version's
    `"No rule to make target" not in output`, which named only ONE specific bad shape) means
    every OTHER way a probe can go wrong -- `make` missing entirely, the target renamed or
    deleted, an unrelated Makefile syntax error elsewhere in the file, a `cwd` mismatch --
    produces output that does not match this signature either, and is classified as
    `COULD_NOT_RUN` rather than `DID_NOT_REFUSE`. A failure OF the probe must never be reported
    as a failure IN the thing being probed.

    THE BRACKETED TARGET NAME CARRIES AN OPTIONAL `file:line:` PREFIX -- GNU Make >= 4.x
    (Ubuntu 24.04's default, confirmed live: 4.3) prints `*** [Makefile:462: release-ai-guard]
    Error 1`, while macOS's ancient bundled Make 3.81 prints the bare `*** [release-ai-guard]
    Error 1` with no prefix at all. A substring match on the bare form only recognises the
    macOS shape and misclassifies every genuine Linux refusal as `COULD_NOT_RUN` -- which is
    exactly how this script's own Linux CI job went red (86akhf8e6): `main`'s `rust
    (ubuntu-latest)` job failed this check on every real invocation, which (via the surrounding
    workflow's success()-gated steps) skipped installing `libdbus-1-dev` further down the same
    job, surfacing an hour later as an unrelated-looking `libdbus-sys` pkg-config failure. The
    self-test below only ever exercised the bare macOS shape (a hardcoded fixture, never a real
    `make` call), so it stayed green throughout. The regex below accepts either shape."""
    if returncode is None:
        return ProbeOutcome("COULD_NOT_RUN", output)
    if returncode == 0:
        return ProbeOutcome("DID_NOT_REFUSE", output)
    if re.search(rf"\*\*\* \[(?:[^\[\]\n]*:\s*)?{re.escape(guard_target)}\] Error", output):
        return ProbeOutcome("REFUSED", output)
    return ProbeOutcome("COULD_NOT_RUN", output)


def probe_release_guard(guard_target: str, op_features: str) -> tuple[int | None, str]:
    """Actually invoke `make <guard_target> RELEASE=1 OP_FEATURES=<op_features>` -- a real,
    no-build, sub-second `make` call (the guard's own recipe is nothing but a shell conditional
    that either echoes an error and exits, or has nothing to do at all) -- and return its exit
    code and combined output for `classify_probe` to interpret. `returncode` is `None` if `make`
    could not be invoked AT ALL (not on PATH, no permission, etc.) rather than merely exiting
    non-zero -- a distinct failure mode `classify_probe` also treats as `COULD_NOT_RUN`. See
    NEW-2b: this is, as far as this script or `make ci`/CI can tell, the first automated exercise
    any registered release guard has ever had with a hostile input."""
    try:
        result = subprocess.run(
            ["make", guard_target, "RELEASE=1", f"OP_FEATURES={op_features}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return None, f"could not invoke `make` at all: {exc}"
    return result.returncode, result.stdout + result.stderr


def verify_crate_release_guard(
    crate_name: str,
    guard_target: str,
    per_crate_tags: dict[str, dict[str, FeatureTags]],
    prober: Callable[[str, str], tuple[int | None, str]] = probe_release_guard,
) -> list[str]:
    """The complete NEW-2b verification for ONE registered crate: pick every `RELEASE: UNSAFE`
    token for `crate_name` (`pick_probe_tokens`), probe `guard_target` with EACH ONE
    independently, and run the benign-input positive control -- returning a list of
    human-readable problems (empty means this crate's guard is proven).

    THE FINAL FINDING THIS FUNCTION EXISTS TO CLOSE (Quinn). `pick_probe_tokens` and
    `classify_probe` were each tested individually and each caught their own mutation. The
    PROCEDURAL LOOP that consumed them -- "for every token pick_probe_tokens returned, probe it,
    and require every single one to refuse" -- used to live inline in `main()`, untested as its
    own unit. Quinn truncated that loop to `probe_tokens[:1]`: `pick_probe_tokens` still
    correctly computed all three tokens, `classify_probe` still correctly classified whatever it
    was given, self-test stayed 31/31, and the real check against Sana's exact
    `export RELEASE_UNSAFE_FEATURES := cloud-stt` partial weakening stayed GREEN -- because only
    `cloud-stt` (still genuinely refused) was ever probed; `dev-keys`/`openai-notes` (silently
    unenforced by that mutation) never were. The vulnerability this whole round exists to close
    could be silently reopened by narrowing the code that CONSUMES two already-correct,
    already-tested functions.

    WHY THIS IS ONE FUNCTION WITH AN INJECTABLE PROBER, NOT TWO. A pure fold over a
    caller-supplied `list[ProbeOutcome]` (Quinn's first suggestion) proves the FOLD inspects
    every element it is given -- it cannot prove the CALLER handed it every element
    `pick_probe_tokens` actually returned; a fold over a list already truncated before the fold
    ever saw it is still a perfectly correct fold. Putting the whole chain -- pick tokens, probe
    each, fold -- inside one function, with the probing mechanism itself swapped out in
    self-test (`prober`), is what makes "was every token from `pick_probe_tokens` actually
    probed" a directly, mechanically testable question: a self-test with a call-recording fake
    `prober` asserts not just the VERDICT but the exact set of `(guard_target, op_features)`
    calls made, so truncating this function's own internal loop -- Quinn's exact mutation,
    reproduced by truncating the loop HERE instead of in `main()` -- is caught by a shorter call
    list, not just a possibly-still-correct verdict. `main()` itself is left with nothing to
    truncate: it is a single call to this function per registered crate.
    """
    try:
        probe_tokens = pick_probe_tokens(per_crate_tags, crate_name)
    except ValueError as exc:
        return [str(exc)]

    problems: list[str] = []
    for probe_token in probe_tokens:
        hostile_code, hostile_output = prober(guard_target, probe_token)
        hostile = classify_probe(hostile_code, hostile_output, guard_target)
        if hostile.kind == "COULD_NOT_RUN":
            problems.append(
                f"{crate_name}: the probe for `{guard_target}` (token `{probe_token}`) "
                "could not run -- this is a problem with the PROBE, not evidence the guard "
                "is broken (`make` missing, the target renamed, an unrelated Makefile "
                f"error, or a wrong working directory would all land here). `make "
                f"{guard_target} RELEASE=1 OP_FEATURES={probe_token}` exited {hostile_code} "
                f"without that target's own `*** [{guard_target}] Error` signature. Output: "
                f"{hostile.detail!r}"
            )
        elif hostile.kind == "DID_NOT_REFUSE":
            problems.append(
                f"{crate_name}: `make {guard_target} RELEASE=1 OP_FEATURES={probe_token}` "
                f"did NOT refuse (exit {hostile_code}) -- CRATES_WITH_RELEASE_GUARD claims "
                f"this target enforces {crate_name}'s release boundary, but a real "
                "invocation with a real UNSAFE token proceeded anyway. This can mean the "
                "guard's own filter logic is wrong, or that its recipe has been detached "
                "from the name every build path actually references -- e.g. the rule body "
                "renamed while `.PHONY`/a prerequisite list still names the old target, "
                "which GNU Make then treats as a satisfied no-op (exit 0) rather than a "
                "missing target, so every real build path bypasses it silently. Check both "
                "before assuming the conditional logic itself is at fault. Fix the guard, "
                "or remove this entry (which then makes every UNSAFE feature here fail the "
                "check above instead)."
            )
        # hostile.kind == "REFUSED" for this token -- keep checking the rest, unconditionally;
        # no early return/break, so truncation is the ONLY way to skip a token, and truncation
        # is exactly what the self-test's call-recording prober catches.

    if problems:
        return problems

    # Positive control, once per crate, ONLY after EVERY hostile token refused: the SAME target,
    # same RELEASE=1, with nothing to refuse, must NOT also refuse -- otherwise "refuses" above
    # could just mean "always fails", indistinguishable from a genuinely discriminating guard by
    # the hostile probe alone.
    benign_code, benign_output = prober(guard_target, "")
    benign = classify_probe(benign_code, benign_output, guard_target)
    if benign.kind == "COULD_NOT_RUN":
        problems.append(
            f"{crate_name}: the benign-input control probe for `{guard_target}` could not "
            f"run (exit {benign_code}) -- a problem with the PROBE, not the guard. Output: "
            f"{benign.detail!r}"
        )
    elif benign.kind == "REFUSED":
        problems.append(
            f"{crate_name}: `make {guard_target} RELEASE=1 OP_FEATURES=` (nothing unsafe "
            f"requested) ALSO refused -- {guard_target} appears to refuse unconditionally "
            "rather than discriminating on the actual feature set, which the hostile-input "
            "probe alone cannot tell apart from a working guard."
        )
    # benign.kind == "DID_NOT_REFUSE" is the expected, passing case.
    return problems


def verify_all_release_guards(
    per_crate_tags: dict[str, dict[str, FeatureTags]],
    verify_crate: Callable[[str, str, dict[str, dict[str, FeatureTags]]], list[str]] = verify_crate_release_guard,
) -> list[str]:
    """Every registered crate's release guard, verified: iterates `CRATES_WITH_RELEASE_GUARD`
    (read LIVE -- this function's own module-level global, not a value copied in at import time
    or a parameter a caller could hand it a stale snapshot of) and calls `verify_crate` once per
    entry.

    THE FINDING THIS FUNCTION EXISTS TO CLOSE (Quinn, one level out from the previous round's
    fix). `verify_crate_release_guard`'s OWN inner loop is now pinned -- truncating it is caught.
    But the loop that called IT, `for crate_name, guard_target in
    CRATES_WITH_RELEASE_GUARD.items(): problems.extend(verify_crate_release_guard(...))`, lived
    inline in `main()`, exercised by nothing: `self_test()` never calls `main()` at all. Quinn
    truncated that outer loop to `list(CRATES_WITH_RELEASE_GUARD.items())[:0]` -- no crate probed,
    no guard invoked, at all -- and got 31/31 self-test green plus a real check against the
    healthy repo printing unqualified success. This is LIVE, not latent, unlike NEW-2c:
    `CRATES_WITH_RELEASE_GUARD` has exactly one entry today, so "skip everything" and "skip
    nothing" were, until this function existed, indistinguishable outcomes -- the entire
    protection built over two rounds could be deleted by narrowing one line, with every gate
    staying green.

    THE SAME FIX, ONE LEVEL OUT, WITH THE SAME DISCIPLINE. `verify_crate_release_guard` closed
    the inner truncation by taking its probing mechanism (`prober`) as an injectable dependency
    rather than calling `probe_release_guard` directly, so self-test can record every call made
    and check that list against `pick_probe_tokens`' own live output. This function does the
    identical thing one level out: `verify_crate` is injectable, self-test injects a
    call-recording fake, and the assertion is against `CRATES_WITH_RELEASE_GUARD`'s own keys,
    read directly at assertion time -- not a hand-written `{"selahcue-operator"}` literal, which
    would keep passing even if the registry changed underneath it and would not have caught this
    exact mutation any more than the inner fixture's first draft would have. Verified the same
    way Quinn verifies "reads live, not a copy": mutate `CRATES_WITH_RELEASE_GUARD` itself (add a
    second entry) and confirm the self-test assertion tracks the change rather than going stale.

    WHY THIS TERMINATES THE REGRESS. `main()` is reduced to a single, unconditional call --
    `problems.extend(verify_all_release_guards(per_crate_tags))` -- with no loop of its own left
    to truncate. There is no further "loop that calls this loop" for a future review to find one
    level out again: the chain from "which crates are registered" (`CRATES_WITH_RELEASE_GUARD`,
    read live) to "which tokens does each one need to refuse" (`pick_probe_tokens`, read live) to
    "did probing actually happen" (the injected `prober`) is now pinned at every join, each
    verified by mutating the REAL thing one level down and confirming the test tracks it rather
    than a hand-copied stand-in.
    """
    problems: list[str] = []
    for crate_name, guard_target in CRATES_WITH_RELEASE_GUARD.items():
        problems.extend(verify_crate(crate_name, guard_target, per_crate_tags))
    return problems


def resolved_features(dry_run_text: str) -> set[str]:
    """Every feature token named in any `--features <list>` occurrence in `dry_run_text`. See
    COLLISION GUARD in the module docstring for why a flat union (rather than per-line crate
    attribution) is a safe comparison, given the cross-crate collision check this script also
    runs."""
    features: set[str] = set()
    for match in FEATURES_FLAG.finditer(dry_run_text):
        features.update(match.group(1).split(","))
    return features


def missing_features(dry_run_text: str, required: set[str]) -> set[str]:
    """The `required` features that do NOT appear as a token anywhere in `dry_run_text`."""
    return required - resolved_features(dry_run_text)


def crate_mentions(dry_run_text: str) -> set[str]:
    """Every crate name a dry run's text names explicitly, via either `-p <name>` or a
    `--manifest-path .../crates/<name>/Cargo.toml`. Used to catch a crate joining the dev-launch
    path without a matching `CRATE_MANIFESTS` entry -- see MULTI-CRATE SCOPE."""
    return set(CRATE_NAME_IN_MANIFEST_PATH.findall(dry_run_text)) | set(
        CRATE_NAME_VIA_DASH_P.findall(dry_run_text)
    )


def unregistered_crate_mentions(dry_run_texts: list[str]) -> set[str]:
    """Crate names mentioned across every given dry run that are NOT a key in `CRATE_MANIFESTS`."""
    mentioned: set[str] = set()
    for text in dry_run_texts:
        mentioned |= crate_mentions(text)
    return mentioned - set(CRATE_MANIFESTS)


def dev_launch_entry_point_targets(makefile_text: str) -> set[str]:
    """Every Makefile target whose prerequisite list names BOTH `stt-preflight` AND
    `release-ai-guard` -- see TARGETS above for why this pair, and why the result must equal
    `TARGETS` exactly rather than being trusted unchecked."""
    targets: set[str] = set()
    for name, rest in MAKEFILE_TARGET_LINE.findall(makefile_text):
        prereqs = set(rest.split("##", 1)[0].split())
        if {"stt-preflight", "release-ai-guard"} <= prereqs:
            targets.add(name)
    return targets


def find_release_unsafe_occurrences(makefile_text: str) -> list[set[str]]:
    """Every `RELEASE_UNSAFE_FEATURES := ...` assignment in the Makefile text, in file order,
    each as its own token set.

    NEW-1 (Sana, verified against the real repo). GNU Make's `:=` is a plain reassignment: at any
    USE site -- `release-ai-guard`'s `ifneq ($(filter $(RELEASE_UNSAFE_FEATURES),...))` -- the
    value is whichever assignment appears LAST before that use site in the file, not necessarily
    the first (or only) one. The original version of this function used `re.search`, which finds
    only the FIRST occurrence. Sana proved this concretely: inserting a second, weaker
    `RELEASE_UNSAFE_FEATURES := ...` line BETWEEN the real registry and `release-ai-guard` makes
    the guard silently accept `OP_FEATURES=stt,cloud-stt RELEASE=1` (exit 0, no refusal) while
    this script, still reading only the first (stronger) occurrence, reported everything green --
    exactly the silent drift the mechanism claims to make impossible. (A line appended AFTER
    `release-ai-guard` is inert -- verified -- because nothing reads the variable again past that
    point, but this script cannot see "before" vs "after" the guard without re-implementing
    Make's own parser, so position is not attempted as a distinguishing signal.)

    The fix: return every occurrence, and let the caller refuse anything other than exactly one --
    the same treatment a duplicate LAUNCH_REACHABILITY/RELEASE tag on one feature already gets
    (ambiguous is a hard failure, not "take the first"), applied to the Makefile side too.
    """
    return [set(m.split()) for m in RELEASE_UNSAFE_LINE.findall(makefile_text)]


def resolve_release_unsafe_line(makefile_text: str) -> tuple[set[str] | None, str | None]:
    """The single, unambiguous token set of the Makefile's `RELEASE_UNSAFE_FEATURES := ...` line,
    as `(tokens, None)` -- or `(None, <problem>)` if there is zero or more than one such
    assignment anywhere in the file. See `find_release_unsafe_occurrences` for why more than one
    is refused outright rather than resolved by position or by "first wins"."""
    occurrences = find_release_unsafe_occurrences(makefile_text)
    if not occurrences:
        return None, "no `RELEASE_UNSAFE_FEATURES := ...` line found at all"
    if len(occurrences) > 1:
        shown = [sorted(o) for o in occurrences]
        return None, (
            f"{len(occurrences)} separate `RELEASE_UNSAFE_FEATURES := ...` assignments found "
            f"({shown}) -- GNU Make's `:=` means whichever one sits last before "
            "`release-ai-guard`'s use of it silently wins, which this script cannot determine "
            "from text alone (see NEW-1 in `find_release_unsafe_occurrences`'s docstring). Keep "
            "exactly one assignment."
        )
    return occurrences[0], None


def run_make_dry(target: str) -> str:
    """`make -n <target>` output, with AI/STT/RELEASE/OP_FEATURES cleared so the DEFAULT
    resolution is what gets checked rather than an override left exported in the calling shell."""
    env = dict(os.environ)
    for var in ("AI", "STT", "RELEASE", "OP_FEATURES"):
        env.pop(var, None)
    result = subprocess.run(
        ["make", "-n", target],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"`make -n {target}` itself failed (exit {result.returncode}):", file=sys.stderr)
        print(result.stderr or result.stdout, file=sys.stderr)
        raise SystemExit(1)
    return result.stdout


def metadata_feature_names(manifest_path: Path) -> set[str]:
    """The authoritative feature-name set `cargo metadata` reports for the package at
    `manifest_path`, excluding `default`. See FEATURE-NAME AUTHORITY in the module docstring."""
    result = subprocess.run(
        [
            "cargo",
            "metadata",
            "--no-deps",
            "--format-version",
            "1",
            "--manifest-path",
            str(manifest_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"`cargo metadata` for {manifest_path} failed (exit {result.returncode}):",
            file=sys.stderr,
        )
        print(result.stderr or result.stdout, file=sys.stderr)
        raise SystemExit(1)
    data = json.loads(result.stdout)
    target = manifest_path.resolve()
    for pkg in data.get("packages", []):
        if Path(pkg["manifest_path"]).resolve() == target:
            return set(pkg.get("features", {}).keys()) - {"default"}
    raise SystemExit(f"cargo metadata reported no package for manifest {manifest_path}")


# --- fixtures for --self-test, modelled on real `make -n launch`/`make -n operator` output ----
# Deliberately NOT the real feature lists/Makefile content, so the self-test proves the MECHANISM
# works and keeps working as the real product decisions (and the real feature lists) change.

SELF_TEST_REQUIRED = {"dev-keys", "openai-notes"}

FIXTURE_LAUNCH_OK = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt,dev-keys,openai-notes \n"
    'echo ">> AI-assisted sermon notes: on"\n'
)
FIXTURE_OPERATOR_OK = (
    'echo ">> AI-assisted sermon notes: on"\n'
    "sh scripts/run_operator_macapp.sh --features stt,dev-keys,openai-notes\n"
)
FIXTURE_LAUNCH_REGRESSED = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt \n"
)
FIXTURE_NO_FEATURES_AT_ALL = "cargo build --manifest-path .../Cargo.toml \n"
FIXTURE_SUBSTRING_TRAP = "cargo build --manifest-path .../Cargo.toml --features cloud-stt,ndi \n"
# A dry run naming both registered crates by their real identifying tokens -- the shape
# `unregistered_crate_mentions` must accept without complaint.
FIXTURE_BOTH_CRATES_REGISTERED = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt,dev-keys,openai-notes,cloud-stt \n"
    "cargo build --manifest-path implementation/desktop/Cargo.toml -p selahcue-desktop "
    "--features ndi \n"
)
# A THIRD crate (`selahcue-widget`, invented) appearing in a dry run with no matching
# CRATE_MANIFESTS entry -- the exact shape of a fourth instance of the reachability-gap class,
# reproduced structurally without needing a real fourth crate to exist.
FIXTURE_UNREGISTERED_CRATE = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-widget/Cargo.toml "
    "--features some-new-feature \n"
)


def dry_run_cases() -> list[tuple[str, str, set[str]]]:
    return [
        ("launch OK fixture reports nothing missing", FIXTURE_LAUNCH_OK, set()),
        ("operator OK fixture reports nothing missing", FIXTURE_OPERATOR_OK, set()),
        (
            "AI_FEATURES-dropped fixture reports BOTH features missing",
            FIXTURE_LAUNCH_REGRESSED,
            set(SELF_TEST_REQUIRED),
        ),
        (
            "a dry run with no --features flag at all reports both missing, not vacuously OK",
            FIXTURE_NO_FEATURES_AT_ALL,
            set(SELF_TEST_REQUIRED),
        ),
        (
            "a substring-only feature list (cloud-stt) does not falsely satisfy "
            "dev-keys/openai-notes",
            FIXTURE_SUBSTRING_TRAP,
            set(SELF_TEST_REQUIRED),
        ),
    ]


def crate_registry_cases() -> list[tuple[str, list[str], set[str]]]:
    return [
        (
            "both registered crates' identifying tokens are accepted with no unregistered names",
            [FIXTURE_BOTH_CRATES_REGISTERED],
            set(),
        ),
        (
            "a crate with no CRATE_MANIFESTS entry is reported, not silently ignored",
            [FIXTURE_UNREGISTERED_CRATE],
            {"selahcue-widget"},
        ),
    ]


# --- fixtures for the Cargo.toml tag parser -----------------------------------------------

FIXTURE_TOML_OK = """\
[features]
default = []
# On-device speech-to-text. AUTO-enabled when cmake is present.
#
# LAUNCH_REACHABILITY: AUTO — auto-enabled when cmake is on PATH.
# RELEASE: SAFE — no developer credential involved.
stt = ["dep:selahcue-stt"]
# Developer AI provider keys.
#
# LAUNCH_REACHABILITY: REQUIRED — 86akcmzrd.
# RELEASE: UNSAFE — must never reach a release build.
dev-keys = []
# Live cloud endpoint that does not exist yet.
#
# LAUNCH_REACHABILITY: OPT-IN — no endpoint to reach yet.
# RELEASE: SAFE — no developer credential involved.
cloud-live = ["dep:whatever"]

[dependencies]
tauri = "2"
"""

# The 86akby7th regression, reproduced structurally: a feature lands in [features] with a full
# prose comment but NO tags at all -- exactly what `cloud-stt` looked like before 86akd10dq.
FIXTURE_TOML_MISSING_TAGS = """\
[features]
default = []
# Cloud (Deepgram) live transcription. Off by default. No tags below -- forgot them.
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

FIXTURE_TOML_BAD_TAG = """\
[features]
default = []
# Typo'd tag value.
#
# LAUNCH_REACHABILITY: REQUIRED-ISH
# RELEASE: SAFE
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

FIXTURE_TOML_DUPLICATE_TAG = """\
[features]
default = []
# Two LAUNCH_REACHABILITY tags in one block -- ambiguous, must fail rather than silently pick one.
#
# LAUNCH_REACHABILITY: REQUIRED
# LAUNCH_REACHABILITY: OPT-IN
# RELEASE: SAFE
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

# A Cargo.toml with no [features] table at all -- a legitimate shape for a future registered
# crate with no optional features, and must NOT be reported as a problem.
FIXTURE_TOML_NO_FEATURES_TABLE = """\
[package]
name = "some-crate"

[dependencies]
serde = "1"
"""


def tag_parser_cases() -> list[tuple[str, str, dict[str, FeatureTags], list[str]]]:
    return [
        (
            "a fully-tagged [features] block derives the right tags with no problems",
            FIXTURE_TOML_OK,
            {
                "stt": FeatureTags("AUTO", "SAFE"),
                "dev-keys": FeatureTags("REQUIRED", "UNSAFE"),
                "cloud-live": FeatureTags("OPT-IN", "SAFE"),
            },
            [],
        ),
        (
            "a feature with NO tags at all is reported as a problem on both axes",
            FIXTURE_TOML_MISSING_TAGS,
            {},
            [
                "`cloud-stt` has no `LAUNCH_REACHABILITY:` tag in its comment block",
                "`cloud-stt` has no `RELEASE:` tag in its comment block",
            ],
        ),
        (
            "an unrecognised LAUNCH_REACHABILITY tag value is reported as a problem",
            FIXTURE_TOML_BAD_TAG,
            {},
            [
                "`cloud-stt`'s `LAUNCH_REACHABILITY:` tag 'REQUIRED-ISH' is not one of "
                "['AUTO', 'OPT-IN', 'REQUIRED']"
            ],
        ),
        (
            "two LAUNCH_REACHABILITY tags in one comment block is ambiguous and reported",
            FIXTURE_TOML_DUPLICATE_TAG,
            {},
            [
                "`cloud-stt` has 2 `LAUNCH_REACHABILITY:` tags in its comment block "
                "(ambiguous): ['REQUIRED', 'OPT-IN']"
            ],
        ),
        (
            "a Cargo.toml with no [features] table at all is not a problem",
            FIXTURE_TOML_NO_FEATURES_TABLE,
            {},
            [],
        ),
    ]


# --- fixtures for the cross-crate collision guard -------------------------------------------

FIXTURE_TOML_COLLIDING_A = """\
[features]
default = []
# Crate A's own take on a feature literally named `shared-name`.
#
# LAUNCH_REACHABILITY: REQUIRED — crate A's reason.
# RELEASE: SAFE
shared-name = []
"""

FIXTURE_TOML_COLLIDING_B = """\
[features]
default = []
# Crate B independently picked the SAME feature name -- a collision this script must refuse to
# resolve silently (see COLLISION GUARD).
#
# LAUNCH_REACHABILITY: OPT-IN — crate B's reason.
# RELEASE: SAFE
shared-name = []
"""


# --- fixtures for the RELEASE_UNSAFE_FEATURES Makefile cross-check ---------------------------

FIXTURE_MAKEFILE_OK = (
    "RELEASE ?= 0\n"
    "RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt\n"
    "STT ?= auto\n"
)
FIXTURE_MAKEFILE_NO_LINE = "RELEASE ?= 0\nSTT ?= auto\n"

# Fixture Makefile-shaped text for `dev_launch_entry_point_targets`, modelled on the real
# Makefile's shape: a variable assignment (must NOT be mistaken for a target), a target with no
# prerequisites, one with only ONE of the two guards, and two with BOTH.
FIXTURE_MAKEFILE_TARGETS = """\
OP_FEATURES_WORDS := $(subst $(COMMA),$(SPACE),$(OP_FEATURES))
stt-preflight: ## (internal) verify the toolchain
release-ai-guard: ## (internal) refuse a bad release
launch: stt-preflight release-ai-guard build-output build-operator ## Launch EVERYTHING
operator: stt-preflight release-ai-guard ## Run only the operator shell
output-ndi: ndi-preflight ## Force NDI (only one guard-shaped prerequisite, not both)
help: ## Show this help
"""
# NEW-1 (Sana): the exact shape of the drift the original re.search-based parser missed -- a
# second, weaker RELEASE_UNSAFE_FEATURES assignment landing between the real registry and
# release-ai-guard's use of it. Must be refused outright (ambiguous), not resolved by "first
# occurrence wins".
FIXTURE_MAKEFILE_DOUBLE_ASSIGNMENT = (
    "RELEASE ?= 0\n"
    "RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt\n"
    "STT ?= auto\n"
    "RELEASE_UNSAFE_FEATURES := dev-keys openai-notes\n"
    "release-ai-guard:\n"
)
# NEW-1b (Sana): the two spellings that weakened the guard while the ORIGINAL regex (anchored at
# `^`, `:=` only) stayed green -- a plain `=` recursive reassignment, and a space-indented `:=`.
# Both must now be detected as a second occurrence (hence ambiguous/refused), not missed.
FIXTURE_MAKEFILE_PLAIN_EQUALS_WEAKENING = (
    "RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt\n"
    "RELEASE_UNSAFE_FEATURES = dev-keys openai-notes\n"
    "release-ai-guard:\n"
)
FIXTURE_MAKEFILE_INDENTED_WEAKENING = (
    "RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt\n"
    "  RELEASE_UNSAFE_FEATURES := dev-keys openai-notes\n"
    "release-ai-guard:\n"
)


def _fake_prober(refuses: set[str]) -> tuple[Callable[[str, str], tuple[int, str]], list[tuple[str, str]]]:
    """A test double for `verify_crate_release_guard`'s `prober` parameter. Returns `(prober,
    calls)`: `prober` behaves like a real `probe_release_guard` would for a guard that refuses
    exactly the tokens in `refuses` (and never refuses the empty-string benign probe); `calls`
    records every `(guard_target, op_features)` pair the function under test actually invoked it
    with, IN ORDER -- this is what lets a self-test assert not just the final verdict but that
    EVERY token was actually probed, closing the gap a verdict-only assertion would leave (see
    `verify_crate_release_guard`'s own docstring, and Quinn's `probe_tokens[:1]` finding)."""
    calls: list[tuple[str, str]] = []

    def prober(guard_target: str, op_features: str) -> tuple[int, str]:
        calls.append((guard_target, op_features))
        if op_features and op_features in refuses:
            return 1, f"make: *** [{guard_target}] Error 1"
        return 0, f"make: Nothing to be done for `{guard_target}'."

    return prober, calls


def _fake_crate_verifier() -> tuple[
    Callable[[str, str, dict[str, dict[str, FeatureTags]]], list[str]], list[tuple[str, str]]
]:
    """A test double for `verify_all_release_guards`'s `verify_crate` parameter. Returns
    `(verify_crate, calls)`: `verify_crate` always reports success (no problems); `calls` records
    every `(crate_name, guard_target)` pair the function under test actually invoked it with, IN
    ORDER. Always-success isolates "did the outer loop iterate every registered crate" from
    whether any individual crate's own guard actually works -- `verify_crate_release_guard`'s own
    self-test already covers that half."""
    calls: list[tuple[str, str]] = []

    def verify_crate(crate_name: str, guard_target: str, per_crate_tags: dict) -> list[str]:
        calls.append((crate_name, guard_target))
        return []

    return verify_crate, calls


def self_test() -> int:
    failures = []

    for name, fixture, expected_missing in dry_run_cases():
        actual = missing_features(fixture, SELF_TEST_REQUIRED)
        if actual != expected_missing:
            failures.append(
                f"{name}: expected missing={sorted(expected_missing)}, got={sorted(actual)}"
            )

    for name, texts, expected_unregistered in crate_registry_cases():
        actual = unregistered_crate_mentions(texts)
        if actual != expected_unregistered:
            failures.append(
                f"{name}: expected unregistered={sorted(expected_unregistered)}, "
                f"got={sorted(actual)}"
            )

    for name, fixture, expected_tags, expected_problems in tag_parser_cases():
        tags, problems = parse_feature_tags(fixture)
        if tags != expected_tags or problems != expected_problems:
            failures.append(
                f"{name}: expected tags={expected_tags} problems={expected_problems}, "
                f"got tags={tags} problems={problems}"
            )

    # The collision guard, exercised via two crates' worth of tags merged the same way
    # collect_all_tags() does, without needing real files on disk.
    tags_a, problems_a = parse_feature_tags(FIXTURE_TOML_COLLIDING_A)
    tags_b, problems_b = parse_feature_tags(FIXTURE_TOML_COLLIDING_B)
    if problems_a or problems_b:
        failures.append(
            f"collision fixtures should each parse cleanly on their own: {problems_a + problems_b}"
        )
    merged: dict[str, FeatureTags] = {}
    owner: dict[str, str] = {}
    collision_problems: list[str] = []
    for crate_name, crate_tags in (("crate-a", tags_a), ("crate-b", tags_b)):
        for feature_name in crate_tags:
            if feature_name in owner:
                collision_problems.append(feature_name)
                continue
            merged[feature_name] = crate_tags[feature_name]
            owner[feature_name] = crate_name
    if collision_problems != ["shared-name"]:
        failures.append(
            "collision guard: two crates declaring the same feature name was not caught "
            f"(got {collision_problems})"
        )

    # The RELEASE_UNSAFE_FEATURES Makefile cross-check, against fixture Makefile text.
    tokens, problem = resolve_release_unsafe_line(FIXTURE_MAKEFILE_OK)
    if tokens != {"dev-keys", "openai-notes", "cloud-stt"} or problem is not None:
        failures.append(
            f"RELEASE_UNSAFE_FEATURES parse: expected the three tokens with no problem, "
            f"got tokens={tokens} problem={problem}"
        )
    tokens, problem = resolve_release_unsafe_line(FIXTURE_MAKEFILE_NO_LINE)
    if tokens is not None or problem is None:
        failures.append(
            "RELEASE_UNSAFE_FEATURES parse: a Makefile with no such line must report "
            f"(None, <problem>), got ({tokens}, {problem})"
        )
    # NEW-1 mutation control: two assignments (the exact shape Sana found live) must be refused,
    # not resolved by picking the first one -- that silent "first wins" behaviour is the bug.
    tokens, problem = resolve_release_unsafe_line(FIXTURE_MAKEFILE_DOUBLE_ASSIGNMENT)
    if tokens is not None or problem is None:
        failures.append(
            "RELEASE_UNSAFE_FEATURES parse: two assignments must be refused as ambiguous, not "
            f"resolved to the first one found, got ({tokens}, {problem})"
        )
    # NEW-1b: the two spellings the original `^RELEASE_UNSAFE_FEATURES\s*:=` regex missed --
    # a plain `=` reassignment, and a space-indented `:=` -- must now be counted as a second
    # occurrence each, making both fixtures ambiguous/refused rather than silently green.
    for name, fixture in (
        ("plain `=` weakening", FIXTURE_MAKEFILE_PLAIN_EQUALS_WEAKENING),
        ("indented `:=` weakening", FIXTURE_MAKEFILE_INDENTED_WEAKENING),
    ):
        tokens, problem = resolve_release_unsafe_line(fixture)
        if tokens is not None or problem is None:
            failures.append(
                f"RELEASE_UNSAFE_FEATURES parse: {name} must be detected as a second occurrence "
                f"and refused, got ({tokens}, {problem})"
            )

    # TARGETS derivation, against fixture Makefile text: a var assignment isn't mistaken for a
    # target, a target with only one guard-shaped prerequisite doesn't qualify, and both
    # dual-guarded targets are found.
    derived = dev_launch_entry_point_targets(FIXTURE_MAKEFILE_TARGETS)
    if derived != {"launch", "operator"}:
        failures.append(
            f"dev_launch_entry_point_targets: expected {{'launch', 'operator'}}, got {derived}"
        )

    # NEW-2: an UNSAFE tag on a crate with no Make-level guard is a hard failure, not a silent
    # "confirmed" success. Positive control included -- selahcue-operator's own UNSAFE feature
    # must NOT be flagged, or this check would be indistinguishable from "always fail".
    unenforced = crates_with_unenforced_release_unsafe_features(
        {
            "selahcue-operator": {"dev-keys": FeatureTags("REQUIRED", "UNSAFE")},
            "selahcue-desktop": {"ndi": FeatureTags("AUTO", "UNSAFE")},
        }
    )
    if unenforced != {"selahcue-desktop": {"ndi"}}:
        failures.append(
            "NEW-2: expected only the unguarded crate's UNSAFE feature reported, got "
            f"{unenforced}"
        )

    # NEW-2b: the pure decision logic behind the executable probe, tested without invoking a
    # real `make` -- `pick_probe_tokens` (EVERY current UNSAFE feature, not just one -- a crate
    # with none raises rather than silently skipping) and `classify_probe` (a genuine refusal vs.
    # a benign success vs. every shape of "the probe itself could not run").
    try:
        pick_probe_tokens({"selahcue-operator": {"dev-keys": FeatureTags("REQUIRED", "UNSAFE")}}, "selahcue-operator")
    except ValueError:
        failures.append("pick_probe_tokens: raised for a crate that DOES tag an UNSAFE feature")
    if pick_probe_tokens(
        {"selahcue-operator": {"cloud-stt": FeatureTags("REQUIRED", "UNSAFE"), "dev-keys": FeatureTags("REQUIRED", "UNSAFE")}},
        "selahcue-operator",
    ) != ["cloud-stt", "dev-keys"]:
        failures.append(
            "pick_probe_tokens: expected EVERY UNSAFE feature (sorted), not just the "
            "alphabetically-first one -- a partial weakening that only spared one token would "
            "otherwise pass"
        )
    try:
        pick_probe_tokens({"selahcue-desktop": {"ndi": FeatureTags("AUTO", "SAFE")}}, "selahcue-desktop")
        failures.append("pick_probe_tokens: must raise for a crate with no UNSAFE feature at all")
    except ValueError:
        pass

    # classify_probe: a genuine refusal is recognised POSITIVELY (the target's own bracketed
    # `*** [<target>] Error` line), not by ruling out one specific bad shape -- so every one of
    # these must land in the state named, including two shapes ("missing separator" and a
    # differently-named target's own Error line) the coordinator asked to confirm are covered
    # generally rather than as one hardcoded exception.
    real_refusal = classify_probe(
        1, "ERROR: refusing to build...\nmake: *** [release-ai-guard] Error 1", "release-ai-guard"
    )
    if real_refusal.kind != "REFUSED":
        failures.append(f"classify_probe: a genuine `*** [target] Error` line must be REFUSED, got {real_refusal.kind}")
    # 86akhf8e6: GNU Make >= 4.x (Ubuntu 24.04's default -- confirmed live: 4.3) prefixes the
    # bracketed target with `file:line:`; macOS's bundled Make 3.81 does not. A fixture using
    # only the bare macOS shape stayed green while every real Linux invocation misclassified as
    # COULD_NOT_RUN -- this is the shape that actually broke `main`'s `rust (ubuntu-latest)` job.
    real_refusal_linux_make = classify_probe(
        1, "ERROR: refusing to build...\nmake: *** [Makefile:462: release-ai-guard] Error 1", "release-ai-guard"
    )
    if real_refusal_linux_make.kind != "REFUSED":
        failures.append(
            "classify_probe: a genuine refusal with GNU Make's `file:line:`-prefixed target "
            f"(the real shape on Linux) must be REFUSED, got {real_refusal_linux_make.kind}"
        )
    benign = classify_probe(0, "make: Nothing to be done for `release-ai-guard'.", "release-ai-guard")
    if benign.kind != "DID_NOT_REFUSE":
        failures.append(f"classify_probe: exit 0 must be DID_NOT_REFUSE, got {benign.kind}")
    missing_target = classify_probe(
        2, "make: *** No rule to make target `release-ai-guard-typo'.  Stop.", "release-ai-guard-typo"
    )
    if missing_target.kind != "COULD_NOT_RUN":
        failures.append(f"classify_probe: a missing target must be COULD_NOT_RUN, got {missing_target.kind}")
    syntax_error = classify_probe(2, "Makefile:5: *** missing separator.  Stop.", "release-ai-guard")
    if syntax_error.kind != "COULD_NOT_RUN":
        failures.append(
            "classify_probe: an UNRELATED Makefile syntax error must be COULD_NOT_RUN, not "
            f"mistaken for a refusal or misreported as the guard being broken, got {syntax_error.kind}"
        )
    someone_elses_error = classify_probe(
        1, "make: *** [a-different-target] Error 1", "release-ai-guard"
    )
    if someone_elses_error.kind != "COULD_NOT_RUN":
        failures.append(
            "classify_probe: a DIFFERENT target's own Error line must not be read as THIS "
            f"target refusing, got {someone_elses_error.kind}"
        )
    make_missing = classify_probe(None, "could not invoke `make` at all: [Errno 2] No such file or directory: 'make'", "release-ai-guard")
    if make_missing.kind != "COULD_NOT_RUN":
        failures.append(f"classify_probe: `make` itself missing must be COULD_NOT_RUN, got {make_missing.kind}")
    # PINNED (the coordinator, after Cody and Quinn independently reached opposite conclusions
    # and the coordinator verified GNU Make's actual behaviour in a scratch Makefile rather than
    # trust either): a "detached recipe" -- the rule body renamed while `.PHONY`/a prerequisite
    # list still names the OLD target -- makes Make treat the old name as a satisfied no-op,
    # `Nothing to be done for <target>`, exit 0. Verified live: with this shape, every real
    # dependent target (`launch`, `operator`, ...) still runs to completion; the guard does not
    # stop them. So exit 0 here is NOT a stale probe -- it is a GENUINE, exploitable guard
    # defeat, and DID_NOT_REFUSE is the correct classification, not COULD_NOT_RUN. Pinned so the
    # next person does not relitigate it.
    detached_recipe = classify_probe(0, "make: Nothing to be done for `release-ai-guard'.", "release-ai-guard")
    if detached_recipe.kind != "DID_NOT_REFUSE":
        failures.append(
            "classify_probe: a detached recipe (renamed rule body, stale .PHONY/prerequisite "
            "reference) is a GENUINE guard defeat -- every real build path bypasses it -- and "
            f"must classify DID_NOT_REFUSE, not COULD_NOT_RUN; got {detached_recipe.kind}"
        )

    # verify_crate_release_guard: the PROCEDURAL LOOP that consumes pick_probe_tokens' output,
    # tested with an injected prober so this runs with no real `make` call at all. Three cases,
    # matching what the coordinator asked for specifically:
    #   1. every token refused + benign correctly does not -> no problems, and EVERY token
    #      (matched against pick_probe_tokens' own output) was actually probed, in order,
    #      plus the benign probe.
    #   2. a MIXED refused/not-refused list -> must report a problem AND must have probed BOTH
    #      tokens (not short-circuited on the first, and not skipped the second) -- an
    #      all-not-refused list would pass a fold that fails unconditionally, so this is the
    #      case that actually proves the loop inspects every element.
    #   3. Quinn's exact regression, reproduced structurally: a prober that WOULD refuse every
    #      token if asked, cross-checked against pick_probe_tokens' own count and token set --
    #      this is the assertion a pure fold over a pre-built outcome list cannot make, because
    #      it has no way to know what pick_probe_tokens would have returned; tying the injected
    #      prober's call list back to pick_probe_tokens' own output is what closes that gap.
    three_unsafe = {
        "selahcue-operator": {
            "cloud-stt": FeatureTags("REQUIRED", "UNSAFE"),
            "dev-keys": FeatureTags("REQUIRED", "UNSAFE"),
            "openai-notes": FeatureTags("REQUIRED", "UNSAFE"),
        }
    }
    expected_tokens = pick_probe_tokens(three_unsafe, "selahcue-operator")

    prober, calls = _fake_prober(refuses=set(expected_tokens))
    result = verify_crate_release_guard("selahcue-operator", "release-ai-guard", three_unsafe, prober=prober)
    if result != []:
        failures.append(f"verify_crate_release_guard: all-refused + benign-clean case should report no problems, got {result}")
    expected_calls = [("release-ai-guard", t) for t in expected_tokens] + [("release-ai-guard", "")]
    if calls != expected_calls:
        failures.append(
            "verify_crate_release_guard: expected every token from pick_probe_tokens to be "
            f"probed in order, then the benign probe; expected calls={expected_calls}, got {calls}"
        )

    two_unsafe = {
        "selahcue-operator": {
            "cloud-stt": FeatureTags("REQUIRED", "UNSAFE"),
            "dev-keys": FeatureTags("REQUIRED", "UNSAFE"),
        }
    }
    prober, calls = _fake_prober(refuses={"cloud-stt"})  # dev-keys deliberately NOT refused
    result = verify_crate_release_guard("selahcue-operator", "release-ai-guard", two_unsafe, prober=prober)
    if not result:
        failures.append("verify_crate_release_guard: a MIXED refused/not-refused list must report a problem, got none")
    if calls != [("release-ai-guard", "cloud-stt"), ("release-ai-guard", "dev-keys")]:
        failures.append(
            "verify_crate_release_guard: the mixed case must probe BOTH tokens (not "
            f"short-circuit on the first refusal), got {calls}"
        )

    # Quinn's exact regression, reproduced structurally against THIS function rather than
    # main()'s now-deleted inline loop: a prober that refuses every token it is ever asked
    # about, cross-checked against pick_probe_tokens' own count. If this function's internal
    # loop were ever truncated to probe_tokens[:1] the way Quinn's mutation did in main(), the
    # hostile call count below would drop to 1 while expected_tokens stays 3 -- see the mutation
    # verification in the PR/commit history for this exact edit applied and confirmed red.
    prober, calls = _fake_prober(refuses=set(expected_tokens))
    verify_crate_release_guard("selahcue-operator", "release-ai-guard", three_unsafe, prober=prober)
    hostile_calls = [c for c in calls if c[1] != ""]
    if len(hostile_calls) != len(expected_tokens):
        failures.append(
            f"verify_crate_release_guard: probed {len(hostile_calls)} token(s) but "
            f"pick_probe_tokens returned {len(expected_tokens)} -- this is exactly Quinn's "
            "probe_tokens[:1] truncation, reproduced structurally"
        )
    if {t for _, t in hostile_calls} != set(expected_tokens):
        failures.append(
            f"verify_crate_release_guard: probed token set {sorted(t for _, t in hostile_calls)} "
            f"does not match pick_probe_tokens' output {expected_tokens}"
        )

    # verify_all_release_guards: the OUTER loop, one level out from the case just above -- Quinn
    # found this untested after the inner loop was pinned, and truncated it to
    # list(CRATES_WITH_RELEASE_GUARD.items())[:0] (no crate probed at all). The assertion below
    # reads CRATES_WITH_RELEASE_GUARD LIVE, not a hand-written copy -- verified the same way
    # Quinn verifies "reads live": see the real mutation of CRATES_WITH_RELEASE_GUARD itself,
    # applied and confirmed tracked, in this change's own verification record.
    fake_verify_crate, crate_calls = _fake_crate_verifier()
    all_guards_result = verify_all_release_guards({}, verify_crate=fake_verify_crate)
    if all_guards_result != []:
        failures.append(
            f"verify_all_release_guards: an always-success fake verify_crate must yield no "
            f"problems, got {all_guards_result}"
        )
    if set(crate_calls) != set(CRATES_WITH_RELEASE_GUARD.items()):
        failures.append(
            "verify_all_release_guards: expected to iterate every CRATES_WITH_RELEASE_GUARD "
            f"entry, read live ({dict(CRATES_WITH_RELEASE_GUARD)}), got calls={crate_calls}"
        )
    if len(crate_calls) != len(CRATES_WITH_RELEASE_GUARD):
        failures.append(
            f"verify_all_release_guards: iterated {len(crate_calls)} crate(s) but "
            f"CRATES_WITH_RELEASE_GUARD has {len(CRATES_WITH_RELEASE_GUARD)} -- this is exactly "
            "Quinn's [:0] truncation, reproduced structurally"
        )

    # Mutation control, in the repo's own idiom: take a known-GOOD fixture, delete ONE feature's
    # tags (the exact shape of the 86akby7th regression), and confirm the parser flips from zero
    # problems to reporting exactly that feature on both axes -- proving the enforcement actually
    # bites rather than only running on fixtures built to already contain a missing tag.
    mutated = FIXTURE_TOML_OK.replace(
        "#\n# LAUNCH_REACHABILITY: REQUIRED — 86akcmzrd.\n"
        "# RELEASE: UNSAFE — must never reach a release build.\n"
        "dev-keys = []",
        "dev-keys = []",
    )
    if mutated == FIXTURE_TOML_OK:
        failures.append("mutation control: the string replace did not match FIXTURE_TOML_OK")
    else:
        tags, problems = parse_feature_tags(mutated)
        if "dev-keys" in tags or not any("dev-keys" in p for p in problems):
            failures.append(
                "mutation control: deleting dev-keys' tags did not surface as a problem "
                f"(tags={tags}, problems={problems})"
            )

    total = (
        len(dry_run_cases())
        + len(crate_registry_cases())
        + len(tag_parser_cases())
        + 1  # collision guard
        + 1  # TARGETS derivation
        + 3  # RELEASE_UNSAFE_FEATURES parse (present, absent, double-assignment)
        + 2  # NEW-1b: plain `=` and indented `:=` weakenings
        + 1  # NEW-2: unenforced-crate UNSAFE tag
        + 3  # NEW-2b: pick_probe_tokens (has-one, returns-every-token-sorted, raises-on-none)
        + 8  # NEW-2b: classify_probe (refused, refused w/ GNU Make's file:line-prefixed target
        #     (86akhf8e6), benign, missing target, syntax error, wrong-target error, make
        #     missing, detached-recipe PINNED)
        + 4  # verify_crate_release_guard: all-refused+calls, mixed (non-trivial), truncation-count, truncation-tokenset
        + 3  # verify_all_release_guards: no-problems, iterates-live-registry, truncation-count
        + 1  # mutation control
    )
    if failures:
        print("check_launch_reachability self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"check_launch_reachability self-test: {total} cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    merged_tags, per_crate_tags, problems = collect_all_tags()

    # FEATURE-NAME AUTHORITY (Sana S-2): cross-check the comment scanner's findings for each
    # crate against cargo metadata's own authoritative feature list for that crate.
    for crate_name, manifest_path in CRATE_MANIFESTS.items():
        authoritative = metadata_feature_names(manifest_path)
        scanned = set(per_crate_tags[crate_name])
        unscanned = authoritative - scanned
        for feature_name in sorted(unscanned):
            problems.append(
                f"{crate_name}: cargo metadata reports feature `{feature_name}` that the "
                "comment-tag scanner did not find a tag for -- possibly an unusual TOML "
                "spelling (an indented key, or a quoted key) the line-based scanner cannot see. "
                "Add a `LAUNCH_REACHABILITY:`/`RELEASE:` tag directly above it, using the plain "
                "`name = [...]` spelling if possible."
            )
        stale = scanned - authoritative
        for feature_name in sorted(stale):
            problems.append(
                f"{crate_name}: a `LAUNCH_REACHABILITY:`/`RELEASE:` tag was found for "
                f"`{feature_name}`, but cargo metadata does not know this feature -- it may have "
                "been removed, renamed, or the comment scanner mis-parsed something as a feature "
                "definition."
            )

    # NEW-2 (Quinn/the coordinator): a RELEASE: UNSAFE tag on a crate with no Make-level guard
    # enforcing it is worse than no tag -- refuse before ever reaching a success message that
    # would call it "confirmed".
    for crate_name, unsafe in crates_with_unenforced_release_unsafe_features(per_crate_tags).items():
        problems.append(
            f"{crate_name}: feature(s) {sorted(unsafe)} tagged `RELEASE: UNSAFE`, but no "
            f"Make-level guard enforces the release boundary for `{crate_name}` today -- only "
            "`release-ai-guard` exists, and it filters only selahcue-operator's "
            "OP_FEATURES_WORDS. Either build a Make-level guard for this crate (e.g. extend "
            "release-ai-guard to also filter DESKTOP_FEATURES, or add an analogous guard) and "
            "add the crate to CRATES_WITH_RELEASE_GUARD, or retag the feature SAFE if it "
            "genuinely has no release-boundary concern."
        )

    # NEW-2b (Sana's probe, the coordinator's ask): membership in CRATES_WITH_RELEASE_GUARD is a
    # CLAIM that a real Make target refuses a hostile build for that crate. Prove it by actually
    # invoking it, for every registered crate -- not just checking that the registry's tokens
    # agree with each other, which Sana showed can all agree while nothing is enforced at all.
    # Every outcome is reported as what it actually is: COULD_NOT_RUN (a problem with the PROBE)
    # is never phrased as "the guard is broken" -- see classify_probe's docstring for why that
    # distinction is load-bearing, not cosmetic.
    # verify_all_release_guards owns the WHOLE chain, including which crates are registered --
    # see its own docstring for why this reduces `main()` to a single unconditional call with no
    # loop of its own left to truncate.
    problems.extend(verify_all_release_guards(per_crate_tags))

    if problems:
        print(
            "check_launch_reachability: feature(s) with no valid reachability/release decision "
            "recorded:",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "  Add a `# LAUNCH_REACHABILITY: REQUIRED|AUTO|OPT-IN` AND a `# RELEASE: SAFE|UNSAFE` "
            "line to the feature's own comment block (see this script's DERIVATION docstring "
            "section for what each means) before merging -- an off-by-default feature cannot "
            "land without recording both decisions.",
            file=sys.stderr,
        )
        return 1

    required = required_from_tags(merged_tags)
    release_unsafe = release_unsafe_from_tags(merged_tags)

    dry_run_texts: dict[str, str] = {target: run_make_dry(target) for target in TARGETS}

    unregistered = unregistered_crate_mentions(list(dry_run_texts.values()))
    if unregistered:
        print(
            "check_launch_reachability: `make -n launch`/`make -n operator` reference crate(s) "
            f"not in CRATE_MANIFESTS: {sorted(unregistered)}",
            file=sys.stderr,
        )
        print(
            "  A crate joined the dev-launch path with no matching entry in this script's "
            "CRATE_MANIFESTS registry -- its [features] table (if any) gets zero enforcement. "
            "Add it. See MULTI-CRATE SCOPE in this script's docstring.",
            file=sys.stderr,
        )
        return 1

    derived_targets = dev_launch_entry_point_targets(MAKEFILE_PATH.read_text())
    if derived_targets != set(TARGETS):
        only_in_makefile = derived_targets - set(TARGETS)
        only_in_targets = set(TARGETS) - derived_targets
        print(
            "check_launch_reachability: TARGETS and the Makefile's own "
            "stt-preflight+release-ai-guard prerequisites have drifted apart:",
            file=sys.stderr,
        )
        if only_in_makefile:
            print(
                f"  Target(s) with both guard prerequisites but missing from TARGETS: "
                f"{sorted(only_in_makefile)}",
                file=sys.stderr,
            )
        if only_in_targets:
            print(
                f"  In TARGETS but no longer carrying both guard prerequisites: "
                f"{sorted(only_in_targets)}",
                file=sys.stderr,
            )
        print(
            "  Update TARGETS to match -- see the TARGETS comment for why this is checked "
            "rather than trusted.",
            file=sys.stderr,
        )
        return 1

    makefile_release_unsafe, release_line_problem = resolve_release_unsafe_line(
        MAKEFILE_PATH.read_text()
    )
    if release_line_problem is not None:
        print(
            f"check_launch_reachability: {release_line_problem}",
            file=sys.stderr,
        )
        print(
            f"  In {MAKEFILE_PATH.relative_to(REPO_ROOT)} -- the RELEASE cross-check has nothing "
            "reliable to compare against. See NEW-1 in `find_release_unsafe_occurrences`'s "
            "docstring for why more than one assignment is refused outright.",
            file=sys.stderr,
        )
        return 1
    if makefile_release_unsafe != release_unsafe:
        only_in_makefile = makefile_release_unsafe - release_unsafe
        only_in_tags = release_unsafe - makefile_release_unsafe
        print(
            "check_launch_reachability: the Makefile's RELEASE_UNSAFE_FEATURES and the "
            "Cargo.toml `RELEASE: UNSAFE` tags have drifted apart:",
            file=sys.stderr,
        )
        if only_in_makefile:
            print(
                f"  In the Makefile but not tagged UNSAFE anywhere: {sorted(only_in_makefile)}",
                file=sys.stderr,
            )
        if only_in_tags:
            print(
                f"  Tagged UNSAFE but missing from the Makefile: {sorted(only_in_tags)}",
                file=sys.stderr,
            )
        print(
            "  See RELEASE CROSS-CHECK in this script's docstring -- update whichever side is "
            "stale and say why in the commit.",
            file=sys.stderr,
        )
        return 1

    failed = False
    for target, dry_run_text in dry_run_texts.items():
        missing = missing_features(dry_run_text, required)
        if missing:
            failed = True
            print(
                f"`make {target}` (default invocation) does not reach: "
                f"{', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            print(
                "  These Cargo features are tagged `LAUNCH_REACHABILITY: REQUIRED`, meaning "
                "they must be reachable from `make launch`/`make operator` by default. If "
                "downgrading one to AUTO/OPT-IN was intentional, change its tag and say why in "
                "the commit; if not, this is the exact regression 86akcmzyq/86akd10dq fixed.",
                file=sys.stderr,
            )
    if failed:
        return 1
    print(
        "check_launch_reachability: "
        f"{sorted(required)} reachable from `make launch`/`make operator` by default; "
        f"{sorted(release_unsafe)} confirmed release-unsafe and matched against the Makefile"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
