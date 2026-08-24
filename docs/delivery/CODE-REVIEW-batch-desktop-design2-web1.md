# Code review — Design 2.0 parity, batch 1 (operator webview)

**Surface:** `implementation/desktop/crates/selahcue-operator/dist/` (`index.html`, `app.css`, `app.js`)
**Gates:** `python3 scripts/operator_headless.py` — **707 checks, 0 FAIL**, `EXPECTED_MIN_CHECKS` raised **640 → 707**
**Author:** Farah (Frontend) · **Date:** 2026-08-23
**Sources:** `docs/design/DESIGN-2.0-PARITY-AUDIT-console.md` (CON-###), `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` (PME-###)

Files changed — nothing else in the tree was touched:

| File | + / − |
|---|---|
| `implementation/desktop/crates/selahcue-operator/dist/app.css` | 126 |
| `implementation/desktop/crates/selahcue-operator/dist/app.js` | 65 |
| `implementation/desktop/crates/selahcue-operator/dist/index.html` | 30 |
| `scripts/operator_headless.py` | 296 |
| `implementation/desktop/crates/selahcue-present/tests/test_tokens.rs` | 29 (see §6.1) |

`test_tokens.rs` is **shared with another live session** and already carried their uncommitted work
when I arrived. My hunk is additive at lines 945–978; theirs sit at 67–210. Nothing outside my own
assertion was reformatted, reordered or touched, and `git diff` shows no overlapping hunk — but
whoever commits this should stage the two hunks deliberately rather than the whole file.

`implementation/mobile/**`, `selahcue-engine/`, the rest of `selahcue-present/` and
`scripts/measure_nfr.sh` carry other sessions' uncommitted work and were **not** modified (verified
by mtime, not by intent).

---

## How the contrast numbers were produced

Every ratio below is measured **composited** and at **every stop of every gradient**, because
CON-046 is a worked example of what each of those omissions hides:

- The chip is `rgba(255,255,255,.18)` — a real layer between the ink and the fill. A token-on-token
  check reports "white on green" and never sees it.
- GO LIVE's fill is a two-stop gradient. A single-stop check passes on the bright end while the
  text is still failing on the dark end.

Two independent implementations agree on every number: a Python model used while choosing the
fixes, and a JS implementation inside `operator_headless.py` that reads the **real computed styles
of the real rendered page** (`getComputedStyle`, gradient stops parsed out of `background-image`,
`var()` resolved by the live CSS engine via a probe element). The gate's numbers are the ones
quoted here.

Each group also carries a **control that must measure as failing** — e.g. the original
white-on-`rgba(255,255,255,.18)` chip still reports 1.72 / 2.51:1 through the same helper. Without
it, a green result would be indistinguishable from a helper that returns a large number for
anything.

---

## 1. CON-046 — the keyboard-hint chips (blocker)

`app.css:3899-3906` declared one rule for three different fills:

```css
/* Key hints on token-filled buttons: white for AA on the fill. */
button.golive .key, #blackout.on .key, #clear-all.armed .key {
  color: #fff; background: rgba(255, 255, 255, 0.18);
}
```

The comment asserted the compliance the rule failed. Measuring each fill **separately** is what
made this tractable — the three answers are different, and one of them was already correct.

| Selector | Fill | Before | After | Bar |
|---|---|---|---|---|
| `button.golive .key` | `#3ed39a` (light stop) | **1.72:1** | **10.43:1** | 4.5 |
| `button.golive .key` | `#28a579` (dark stop) | **2.51:1** | **7.64:1** | 4.5 |
| `#blackout .key` **resting** | `#a3283a` (light stop) | **3.20:1** | **7.11:1** | 4.5 |
| `#blackout .key` **resting** | `#8f2030` (dark stop) | **3.75:1** | **8.35:1** | 4.5 |
| `#blackout .key` **engaged** | `#8f2030` | 5.80:1 (already passing) | **8.35:1** | 4.5 |
| `#clear-all.armed .key` | `#ff4d4d` | **2.74:1** | **7.26:1** | 4.5 |
| `#clear-all.armed` **label** | `#ff4d4d` | **3.27:1** | **5.31:1** | 4.5 |
| `#prev` / `#next` `.key` | `#1c1f28` | 6.24:1 | unchanged | 4.5 |
| `#clear-all` **resting** `.key` | `#2a1416` | 6.64:1 | unchanged | 4.5 |

### The audit's own suggested fix does not reach AA

The audit (`console.md:684`) proposes `color: #06231a` on `rgba(6,35,26,0.14)` — dark ink on a
**dark-tinted** chip. Measured at both stops that is **6.78:1 light / 4.31:1 dark**. It still
fails AA-normal where the button is darkest. A dark tint pulls the chip *toward* the ink, so the
direction cannot work here. Reported rather than papered over.

The chip is tinted **light** instead, which keeps the dark ink (matching `.gl-label`, so the
button has one ink, not two): `#06231a` on `rgba(255,255,255,.30)` = **10.43 / 7.64:1**.

### `#blackout.on .key` was already passing — and was left alone

Measured at **5.80:1**, because the review block resolves the engaged state to solid `#8f2030`.
Applying the GO LIVE fix here would have made it worse. This is why the three were measured
separately rather than assumed to share a treatment.

### A fourth instance: the RESTING `#blackout` chip

Found by the visual-parity harness from a real render, then reproduced independently here. The
resting button had **no** `.key` rule of its own, so it fell through to the generic
`button .key` (muted `#a7aebe` on `rgba(107,115,131,.16)`) onto the resting red gradient:
**3.20:1 / 3.75:1**. Both stops fail AA-normal, on a safety-critical control in the state an
operator looks at most.

This is the shape of the whole defect class: **the specific rule you are reading does not mention
the state at all**, so a rule-by-rule review cannot see it. The gate now enumerates *every*
`.key` chip on the page and measures each on its own button's fill, so a chip added later is
measured rather than missed.

The rule is now `#blackout .key` (all states) taking the button's own white ink and keeping the
generic chip: **7.11 / 8.35:1 resting, 8.35:1 engaged** (6.54 / 7.74 under the `:hover`
`brightness(1.06)` filter). That is better than the 5.80:1 the engaged-only rule bought, and it
removes the chip "jump" the two different backgrounds produced on engage.

### `#clear-all.armed`: the `#blackout` precedent was measured and **rejected**

The instruction was to apply the `#blackout` resolution (swap the fill to canonical `#a3283a`).
Measured, that trades one failure for another:

| Property | `--sc-live #ff4d4d` (kept) | `--live #a3283a` (rejected) | Bar |
|---|---|---|---|
| Label contrast | 5.31:1 with `--sc-live-soft` ink | 7.19:1 with white ink | 4.5 |
| **Armed fill vs RESTING fill `#2a1416`** | **5.31:1** | **2.41:1** | **3.0** |
| **Armed fill vs page `#14161d`** | **5.52:1** | **2.51:1** | **3.0** |

The armed state is a **one-second transient whose only signal is the colour flip**. WCAG 1.4.11
covers component *states*, so dropping it to 2.41:1 against the resting fill would be a net
accessibility loss. The fill is kept and the **ink darkens** instead — `--sc-live-soft` on
`--sc-live` = 5.31:1 — which is the resolution the mobile app already ships for armed-danger
controls (`MOBILE-2.0-SPEC.md:245`) and which the presentation audit recommends for this exact
pairing. Every axis passes.

The rejected option is pinned as a mutation (M4 below): setting the fill to `#a3283a` turns the
state-contrast checks red.

**The comment was fixed too.** Each of the three rules now carries its own measured ratios at both
stops and the reason for its treatment, so the next reader is not told the file is compliant where
it is not.

---

## 2. CON-142 — the `.seg` class collision (major)

`.seg` was declared **three** times at equal specificity, so the cascade resolved it per-property
by source order and every family got some of every other family's geometry. The audit describes
one direction; the collision is bidirectional, and there was a **fourth** effect it did not record:

- The Timer|Stage control (`app.css:2623`) rendered with the transcript's `gap: 8px` and
  `align-items: baseline`.
- Transcript lines (`app.css:2831`) inherited the control's `padding: 3px`, `1px` border,
  `9px` radius and `margin-bottom: 12px` — every line was silently boxed.
- **`.seg button` (0,0,1,1) from the Theme-Designer family outranked `.seg-btn` (0,0,1,0)**, so the
  sub-tab buttons rendered at `12px` / `6px 8px` instead of the `13px` / `6px 0` they were written
  for. Specificity, not source order — a different mechanism from the one the audit found.

Renamed into three families with no shared token:

| Was | Now | Consumers updated |
|---|---|---|
| `.seg`, `.seg button`, `.seg button.on`, `.td-align-grid .seg`, `.seg.td-icons button`, `.td-inspector .seg{, button, button.on, .td-icons button}` | `.td-seg` … | `index.html:628, 633, 647, 725` |
| `.seg`, `.seg-btn{, .active, :focus-visible}` | `.subtab-seg`, `.subtab-seg-btn` | `index.html:258, 259, 261` |
| `.seg`, `.seg-time`, `.seg-text`, `.seg-partial{, [hidden], @media}` | `.tr-seg`, `.tr-seg-time`, `.tr-seg-text`, `.tr-seg-partial` | `index.html:123`; `app.js:4054, 4057, 4060` |

Every consumer was enumerated before renaming. **Six descendant-qualified rules
(`.td-inspector .seg …`, `.td-align-grid .seg`) did not appear in the first grep** and would have
been left dead by a rename of the base rule alone — the gate now carries a positive control that
the Theme-Designer segments are still styled, so "the collision is gone" cannot be confused with
"the CSS is gone". `tdSeg()` addresses its groups by `#id`, so the JS needed no change. Nothing
outside `dist/` referenced these classes (`scripts/operator_headless.py` uses the `seg-timer` /
`seg-stage` **ids**; no Rust test names them).

Verified after the rename: **no element carries the bare `seg` class**, so the families cannot
collide again through markup.

---

## 3. PME-001 — the LIVE badge (S1)

`.pm-slide-live-badge` was `#fff` on `--sc-live #ff4d4d` at 9px/700 = **3.27:1**. 9px bold is not
large text, so an accessibility affordance (`WCAG 1.4.1`, a non-colour LIVE indicator) was itself
failing accessibility.

`--sc-live` is an **ink** — `app.css:3` says so: *"Fills carry white text; inks are text/glyphs on
the dark surfaces."* Using it as a fill is the category error. The badge now uses the canonical
white-text red fill `--live`, the resolution `#blackout` already took: **7.19:1**. No token value
changed; `var(--live)` introduces no new hex.

**One trade-off to record.** The badge's own fill against the card (`--sc-elevated #1c1f28`) is
**2.29:1**, under the 3:1 non-text bar. I judge that acceptable: the word "LIVE" carries the
meaning at 7.19:1, and the card carries a redundant 3px `--sc-live` left rule at 5.03:1. If you
would rather the badge stay in the same red family as that rule, the audit's own recommendation —
`--sc-live-soft #2a1416` ink on the `--sc-live` fill — measures **5.31:1 text and 5.03:1 fill**,
i.e. it clears both bars with a lower text ratio. Both are defensible; say which you want and it is
a one-line change.

---

## 4. PME-005 — `.pm-btn-primary:hover` (S2)

Hover **lightened** to `--sc-primary-hover #7e6eff`, putting the white 14px/600 label at
**3.78:1** — below AA-normal, while the rest state (`--sc-primary #6e5cf0`) is 4.72:1. Hover was
the only failing state. Darkened to `#5a48d0` = **6.42:1**, the identical fix already shipped for
`.tb-golive` / `.timer-start` at `app.css:4505-4507`.

The token is untouched: the gate asserts `--sc-primary-hover` **still measures 3.78:1** — only this
rule stopped using it.

`file://` blocks `document.styleSheets[i].cssRules` (SecurityError), so a `:hover`-only value is
unreachable from the DOM. The harness now hands the driver the real `app.css` text; the rule is
regexed out of it and its **value resolved through the live CSS engine**, so `var()` is followed
rather than string-matched and a token rename cannot fake a pass.

---

## 5. PME-014 / PME-015 — the two missing primary actions (S1 / S4)

`pm-top-actions` held only `＋ New`. `pmPresent()` existed but was reachable **only** from the ⌘K
palette, so an operator who does not know the palette could not present a deck at all.

**`▶ Present`** (`#pm-present`, `.pm-btn-primary`) dispatches on the surface mode, reusing the split
the palette already made: grid → `pmGridGoLive(pmGridCursor)`, editor → `pmPresent()`. Flat
`--sc-primary`, never the frame's gradient (PME-003: white on `#7e6eff` is 3.78:1).

**`Add to plan`** (`#pm-addtoplan`, `.pm-btn-ghost`) is **not** a stub. A backing capability already
exists and is reused rather than invented: `add_item{kind:"slide_group", title}` then
`set_item_content{itemId, link:{kind:"deck", id, slide_count}}` — the same pair the plan builder's
own deck-link dialog commits with (`app.js:6251` and `app.js:5733`). `deck_list` is re-read on click
because it, not any cached value, is the authority on which deck is open.

Behaviour built to the repo's existing standards, all gate-verified:

- Re-entrancy guard, so a double-click cannot create two plan items.
- **Rollback**: if the host rejects the link, the item just added is removed again. A plan row that
  claims a deck it has not got is worse than no row on a Sunday morning.
- `role=status` toast with a working **Undo** (`remove_item`), matching the element-delete toast.
- Failures surface on the existing `role=alert` banner; nothing is swallowed.
- Both actions are **hidden** (not disabled) while browsing the Library — they act on the open deck,
  and hidden leaves the tab order too (WCAG 2.4.3). Asserted by **computed display**, not the
  `hidden` attribute, because a class `display` rule defeats the attribute in this webview.
- The two wirings are `if (pmEl(...))`-guarded: this init block wires the whole surface, and an
  unguarded lookup on an element someone later removes would throw and silently take out every
  wiring below it. (Found by mutation M9, which originally cascaded into six unrelated failures.)

### `Add to plan` — Q-14 answered: the control **stays**

Raised before merge because the evidence then pointed the other way:

1. `docs/design/PRESENTATIONS-LIBRARY-spec.md` §2 — the deck-switcher breadcrumb *"replaces the
   disabled 'Add to plan' stub"*.
2. Audit **PME-015** — verdict `MISSING (documented intent)`, severity **S4**, not S1.
3. Audit **Q-14**, an open question for you, whose own proposed answer is *"Permanently dropped;
   correct both frames and the spec diagram."*
4. `implementation/desktop/crates/selahcue-present/tests/test_tokens.rs:945-949` — a committed
   **regression guard**: `assert!(!html.contains("id=\"pm-addplan\""), "the disabled 'Add to plan'
   stub was replaced by the deck-switcher")`.

**Resolved.** The owner has answered Q-14: the control stays. The original drop no longer holds
because the `PlanItem → deck` reference the spec was waiting on has since landed, and
`PRESENTATIONS-LIBRARY-spec.md` now carries **§2.1 "Add to plan — reinstated"** recording the
decision and the shipped behaviour (including rollback-on-failure). §2's old sentence is rescoped to
*navigation*.

The stale Rust guard has been widened rather than left to rot — see §6.1.

---

## 6. Gate changes

`EXPECTED_MIN_CHECKS`: **640 → 707** (67 new checks). Set to the real observed count, not a round
number, so dropping even one trips exit 4. No existing assertion was weakened or removed; the count
is stable across repeated runs.

Two harness changes were needed and both make the gate stricter:

- The real `app.css` text is injected for the driver (see PME-005), since `file://` blocks
  `cssRules`.
- `--virtual-time-budget` **12000 → 20000**. My block navigates surfaces and waits on host
  round-trips at the very end of the run, and its waits are now explicitly bounded to 60×20ms.
  Without both changes a run in which several of the new checks legitimately FAIL ran out of virtual
  time before writing its results, and the gate reported **`NO RESULTS BLOCK` (exit 2, infra)
  instead of the named FAIL**. Found by mutation M10, which was silently green until this was fixed
  — i.e. a real regression would have been misreported as flaky infrastructure.

### 6.1 The `Add to plan` guard, widened (`test_tokens.rs`)

The old guard knew only about the banned stub:

```rust
assert!(!html.contains("id=\"pm-addplan\""),
        "the disabled 'Add to plan' stub was replaced by the deck-switcher");
```

A banned dead stub (`pm-addplan`) and a required live control (`pm-addtoplan`) are **one character
apart**, and only the first was guarded — so deleting the feature tomorrow would leave this test
green. It could not tell "correctly reinstated" from "deleted again".

It now asserts both halves, with a message saying what each protects:

1. the dead placeholder `id="pm-addplan"` stays absent;
2. the live control stays **present, wired and functional** — `id="pm-addtoplan"`,
   `function pmAddToPlan`, the `onclick` assignment that makes the button reach it, the
   `slide_group` item it appends, the `slide_count: deck.slides` deck link it carries, and the
   `remove_item` call behind rollback-on-failure and Undo.

Half (2) is the point: **a present-but-dead button is precisely the stub half (1) bans**, so the
guard now bans it by shape rather than by id.

Mutation-verified in **both** directions, whole file with siblings running, never `--exact`:

| Mutation | Result |
|---|---|
| **A1** live control deleted from `index.html` | RED — *"index.html missing `id="pm-addtoplan"` — the reinstated 'Add to plan' control (Q-14, PRESENTATIONS-LIBRARY-spec.md §2.1) must stay present, not merely un-stubbed"* |
| **A2** control present but its `onclick` removed (a dead button) | RED — *"app.js missing `pmEl(\"pm-addtoplan\").onclick = pmAddToPlan` — 'Add to plan' must stay WIRED and functional …"* |
| **B** a disabled `pm-addplan` stub reintroduced | RED — *"the disabled 'Add to plan' STUB must stay gone — it was a dead placeholder …"* |

A2 is the case the old guard was blind to. Because the Rust helper hardcodes `dist/` (no env
override, unlike the Python gate), the real files were mutated and restored; restoration was
verified **byte-identical by sha256**.

`cargo test -p selahcue-present --test test_tokens` → **19 passed, 0 failed**. That file is green,
including the other session's new `the_high_contrast_stage_theme_beats_the_dark_one_on_every_ink`;
their reported redness is in a different test file and was not investigated. The edit is surgical —
`git diff` shows their hunks at lines 67–210 and mine at 945–978, with no overlap and nothing
outside my assertion reformatted or reordered.

### Mutation verification

Every fix was reverted in a copy of `dist/` (via `SELAHCUE_OPERATOR_DIST`) and the gate re-run, to
confirm the check that names it actually goes red. **10 of 10 bite:**

| # | Mutation | Result |
|---|---|---|
| M1 | GO LIVE chip reverted to white-on-white | RED — "clears AA-NORMAL on gradient stop 1 (**1.72:1**)", stop 2 (**2.51:1**) |
| M2 | `#blackout .key` ink removed | RED — "RESTING BLACKOUT … (**3.20:1**)", engaged (**3.75:1**) |
| M3 | armed label ink reverted to `#fff` | RED — "ARMED Clear-Output LABEL … (**3.27:1**)" |
| M4 | armed fill → the **rejected** `#a3283a` | RED — "ARMED still stands out from RESTING … (**2.41:1**)" |
| M5 | `.subtab-seg` renamed back to `.seg` | RED — "keeps its OWN 3px gap — got normal" |
| M6 | `.tr-seg` renamed back to `.seg` | RED — "keeps its own 8px baseline-aligned geometry" |
| M7 | badge fill reverted to `--sc-live` | RED — "LIVE badge clears AA-NORMAL … (**3.27:1**)" |
| M8 | hover reverted to `--sc-primary-hover` | RED — "HOVERED primary … (**3.78:1**)" |
| M9 | `#pm-present` deleted | RED — "a real '▶ Present' control exists …" |
| M10 | the deck link dropped | RED — "commits through the host (set_item_content), not a local stub" |

The rejected `#clear-all.armed` option and the pre-fix ratio of every fix are therefore both pinned:
the gate fails if someone re-introduces either.

---

## 7. Scope kept

Not touched, deliberately: the 9 `INTENTIONAL-DEVIATION` items (`app.css:4470-4545`);
`--sc-text-muted` and its 88 sites (blocked on the `--sc-text-tertiary` owner decision); **any token
value** (`test_tokens.rs::design2_palette_is_pinned_across_surfaces` cross-checks `dist/app.css`,
the Rust manifest, `StageTheme::dark()` and a source-text grep of the mobile `design_tokens.dart` —
every fix here uses existing tokens or literals already present); the 34 missing states and the
cosmetic DRIFTs.

## 8. Findings raised, not fixed

| Finding | Evidence | Why not here |
|---|---|---|
| `test_tokens.rs:264` pins `"#clear-all.armed .key"` under the comment *"Key hints stay AA on token-filled buttons"* — the claim was false when written (1.72 / 2.74:1) | `selahcue-present/tests/test_tokens.rs:262-264` | Still open. `selahcue-present/` belongs to another session this pass and that line sits inside a different test from the one I was cleared to edit. The selector is preserved verbatim so the pin still passes; the **comment** should be corrected to say the ratios are now enforced behaviourally by `operator_headless.py`. Small, and worth doing while the file is open |
| PME-055 — no `Present` item in the library card `⋯` menu | `app.js:6766-6775` | The audit pairs it with PME-014; scope was the topbar only. Presenting is now reachable without ⌘K, so the S1 is closed, but the menu item is still missing |
| PME-001 badge fill vs card = 2.29:1 (non-text bar) | measured above | Needs your call between the two resolutions in §3 |


---

## Appendix — real `operator_headless.py` output (the 67 new checks)

```
$ python3 scripts/operator_headless.py
... (640 pre-existing checks elided — all PASS, none modified) ...
PASS: CON-046 (premise): GO LIVE really is a TWO-stop gradient (2 stops, distinct), so 'measured at both stops' is not vacuous
PASS: CON-046 (control): the ORIGINAL white-on-rgba(255,255,255,.18) chip still measures below AA-LARGE through this helper (1.72 / 2.51:1) — the measurement is not rubber-stamping
PASS: CON-046: the GO LIVE '⏎ Enter' chip clears AA-NORMAL on gradient stop 1 (10.43:1)
PASS: CON-046: the GO LIVE '⏎ Enter' chip clears AA-NORMAL on gradient stop 2 (7.64:1)
PASS: CON-046: the key hint carries the SAME dark ink as the GO LIVE label — one ink on one fill, not two answers to the same question
PASS: CON-046 (premise): the chip is SMALL text (11px), so 4.5:1 is the right bar — a font-size bump must not silently relax this
PASS: CON-046 (premise): every `.key` chip on the page is enumerated (5 found) — a chip added later is measured, not missed
PASS: CON-046: key chip '←' on #prev (RESTING) clears AA-NORMAL on every stop of its own fill (6.24:1)
PASS: CON-046: key chip '⏎
    ' on #golive (RESTING) clears AA-NORMAL on every stop of its own fill (7.64:1)
PASS: CON-046: key chip 'Space' on #next (RESTING) clears AA-NORMAL on every stop of its own fill (6.24:1)
PASS: CON-046: key chip 'B' on #blackout (RESTING) clears AA-NORMAL on every stop of its own fill (7.11:1)
PASS: CON-046: key chip 'Esc
  ' on #clear-all (RESTING) clears AA-NORMAL on every stop of its own fill (6.64:1)
PASS: CON-046 (premise): resting BLACKOUT is a TWO-stop gradient, so both stops must be measured
PASS: CON-046: the RESTING BLACKOUT key hint clears AA-NORMAL on both stops of the resting red gradient (7.11:1)
PASS: CON-046 (control): the generic `button .key` muted ink still measures BELOW AA-normal on this fill (3.75:1) — the fix is the ink override, not a measurement artefact
PASS: CON-046: the resting BLACKOUT chip takes the button's OWN ink, so resting and engaged read the same (no chip jump on engage)
PASS: CON-046: the BLACKOUT-engaged key hint clears AA-NORMAL on its real engaged fill (8.35:1)
PASS: CON-046 (premise): BLACKOUT engaged still uses the darkened canonical red (label 8.69:1) — that is WHY its white chip passes where GO LIVE's did not
PASS: CON-046: the ARMED Clear-Output key hint clears AA-NORMAL on its fill (7.26:1)
PASS: CON-046: the chips are treated PER FILL, not re-merged into one shared declaration (the merge is what hid this defect)
PASS: CON-046: the ARMED Clear-Output LABEL clears AA-NORMAL on its fill (5.31:1, was white-on---sc-live at 3.27:1)
PASS: CON-046: ARMED still stands out from RESTING at the 3:1 non-text bar (5.31:1) — the label fix did not cost the state its visibility
PASS: CON-046: the ARMED fill still clears 3:1 against the page behind it (5.52:1)
PASS: CON-142: no element carries the bare `seg` class any more — the three families cannot collide again through markup
PASS: CON-142: the Timer|Stage control keeps its OWN 3px gap (the transcript rule was leaking 8px into it) — got 3px
PASS: CON-142: the Timer|Stage control no longer inherits the transcript line's align-items:baseline — got normal
PASS: CON-142: the Timer|Stage control keeps its own inset chrome (padding 3px, radius 9px)
PASS: CON-142: a sub-tab button keeps its own 13px label — `.seg button` (0,0,1,1) used to OUTRANK `.seg-btn` (0,0,1,0) and force 12px; got 13px
PASS: CON-142: a sub-tab button keeps its own `padding: 6px 0` — the same specificity bug forced 6px 8px; got 0px
PASS: CON-142: a transcript line no longer inherits the segmented control's inset chrome (padding 0px, border 0px, margin-bottom 0px, radius 0px)
PASS: CON-142: the transcript line keeps its own 8px baseline-aligned geometry (gap 8px, align baseline)
PASS: CON-142 (positive control): the Theme-Designer option group still gets its .td-seg layout — got display flex
PASS: CON-142 (positive control): `.td-seg button` still styles the designer's segment buttons (the rename moved the rules, it did not drop them)
PASS: PME-005 (premise): the .pm-btn-primary:hover rule is present in the shipped app.css
PASS: PME-005 (premise): the hover rule declares a background, so there is a value to measure
PASS: PME-005: the HOVERED primary keeps its white label at AA-NORMAL (6.42:1) — hover is a real UI state and WCAG applies to it
PASS: PME-005: hover DARKENS the fill instead of lightening it (rest 4.72:1 → hover 6.42:1), matching the fix already shipped for .tb-golive
PASS: PME-005 (control): --sc-primary-hover itself still measures BELOW AA-normal for white (3.78:1) — the TOKEN VALUE is untouched; only this rule stopped using it
PASS: PME-014/015 (setup): the Presentation surface opens on the Library
PASS: PME-014: a real '▶ Present' control exists in the Presentation topbar (it was reachable ONLY from the ⌘K palette)
PASS: PME-015: an 'Add to plan' control exists in the Presentation topbar
PASS: PME-014/015: both topbar actions are hidden by COMPUTED display while browsing the Library (not merely the [hidden] attribute, which a class `display` rule would defeat)
PASS: PME-014/015: the hidden actions are genuinely unpainted, so they leave the tab order too (WCAG 2.4.3)
PASS: PME-014 (setup): the library lists at least one presentation to open
PASS: PME-014 (setup): opening a presentation shows the slide grid
PASS: PME-014: '▶ Present' is really PAINTED once a presentation is open (computed display block)
PASS: PME-015: 'Add to plan' is really painted once a presentation is open
PASS: PME-003: '▶ Present' uses the FLAT primary fill, never the frame's gradient (white on the frame's light stop is 3.78:1)
PASS: PME-014: '▶ Present' presents from GRID mode (deck_go_live) — the same split the ⌘K palette already made
PASS: PME-014 (setup): Edit ▸ opens the authoring editor
PASS: PME-014: '▶ Present' stays available in the EDITOR, not just the grid
PASS: PME-014: '▶ Present' presents the selected slide from EDITOR mode (deck_go_live)
PASS: PME-001 (positive control): a presented slide really renders the non-colour LIVE badge — the ratio below is measured on a live element
PASS: PME-001: the LIVE badge clears AA-NORMAL at 9px/700 (7.19:1) — an accessibility affordance that was itself failing accessibility
PASS: PME-001 (premise): the badge really is SMALL text (9px), so AA-normal applies — a size change must not silently relax this check
PASS: PME-001: the badge no longer uses --sc-live (an INK) as a fill; it uses the canonical white-text red fill, the same resolution #blackout already took
PASS: PME-001 (control): white on --sc-live still measures BELOW AA-normal (3.27:1) — the token value is untouched; the badge stopped using it as a fill
PASS: PME-015: 'Add to plan' commits through the host (set_item_content), not a local stub
PASS: PME-015: it appends exactly ONE Presentation item to the plan (add_item{kind:slide_group})
PASS: PME-015: the new plan item is titled with the OPEN deck's name ("Sermon: Grace That Feeds")
PASS: PME-015: the item carries a REAL deck reference (link{kind:deck,id:2}), not an unlinked title
PASS: PME-015: the link carries the deck's slide count (2) to the host, which owns no deck store — so the plan row reports a real count
PASS: PME-015: a role=status toast confirms the plan edit
PASS: PME-015: the toast offers Undo — the plan edit is reversible
PASS: PME-015: Undo really removes the item it just added (remove_item)
PASS: PME-015: a REJECTED deck link rolls the plan item back (no orphan row promising a deck it does not hold)
PASS: PME-015: a rejected deck link surfaces the role=alert error banner — the failure is reported, not swallowed

=== 707 checks, 0 FAIL ===
```

Exit code **0**. Full run: 707 PASS, 0 FAIL, floor 707.
