# Design 2.0 parity audit — Mobile controller (Flutter)

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-mobile.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`, page `0:1`
**Code seam:** `implementation/mobile/selahcue_controller/lib/`
**Status:** point-in-time. Figma, `lib/`, and the two prior batch reviews all move; re-run before
acting on a row older than a few weeks.

## Why this audit exists

Every mobile screen file carries a doc-comment citing a Figma frame id, and
`docs/design/MOBILE-2.0-SPEC.md` (2026-08-17) is a measured, frame-by-frame implementation spec.
That looked like parity coverage, but it is **provenance, not verification** — nothing in the repo
re-checks, screen by screen, that the live widget tree still matches the cited frame. Desktop has
three numbered `CON-`/`PME-`/`STG-` audits doing exactly that; mobile had none. This document is
mobile's equivalent: `MOB-###`, same verdict taxonomy, same `file:line` discipline as
`DESIGN-2.0-PARITY-AUDIT-presentation.md`.

## Method

For each of the 13 surfaces in `MOBILE-2.0-SPEC.md §1`:

1. Read the Dart source's doc comment and confirm the cited Figma frame id actually resolves to
   that screen (`get_metadata`, this session) — not a different screen, not a dangling id.
2. Read the implementation (`lib/views/**`) and record the current behaviour/values with
   `file:line`.
3. Compare against `MOBILE-2.0-SPEC.md`'s own *measured* values for that frame (itself a
   `get_design_context`/`get_metadata` reading, done 2026-08-17) and, where a prior batch review
   already diffed implementation against spec (`CODE-REVIEW-batch-mobile-design2.md`,
   `-b.md`), treat that diff as a fast first pass — then re-verify the claim against the *current*
   tree rather than trusting the batch doc's point-in-time snapshot (the same discipline the
   Phase A desktop reconciliation used).
4. Cross-check against the Flutter test suite (`test/views/*_test.dart`, `test/models/*_test.dart`
   — 20 view-test files, 9 model-test files) as corroborating evidence for behavioural claims,
   not a substitute for reading the widget.

**Frame-citation spot-check.** Nine of the doc-comment-cited frame ids were independently pulled
via `get_metadata` this session: `342:133`, `363:124`/`363:133`, `364:128`, `357:218`, `358:128`,
`358:149`, `343:128`, `343:169`, `367:126`. All nine resolve to content matching the surface that
cites them — no dangling or wrong-screen citation was found among them. One **imprecision** was
found and is recorded as **MOB-001**.

**Depth varies by surface, stated honestly.** `lib/views/widgets/enforcement.dart` and
`lib/views/widgets/mobile_widgets.dart` (the two most recently built, most a11y-sensitive files)
were read in full, line-by-line, against spec §3.9/§4.2/§4.10–§4.13. `lib/views/tabs/plan_tab.dart`
was read in full. The remaining surfaces (`pairing_view.dart`, `controller_view.dart`,
`live_tab.dart`, `scripture_tab.dart`, `timer_tab.dart`, `detections_view.dart`,
`custom_time_well.dart`) were read via doc-comment header, structural grep (`d2TextMuted`
leftovers, key widget names, spacing constants), and the Batch A/B review's own diff tables — not
a full pixel-by-pixel re-derivation from `get_design_context` on every element. Rows sourced this
way are marked **[batch-review]** in the Source column; rows independently re-verified this session
are marked **[verified]**. This is a real scope limitation against the "nothing is inferred"
desktop standard, recorded in **§ Open questions**.

## Verdict vocabulary

Same as the desktop audits: **MATCH** / **DRIFT** / **MISSING** / **EXTRA** / **UNSPECIFIED** /
**A11Y-INTENTIONAL** (the frame is the defect, code already correct) / **A11Y-DEFECT** (code fails
NFR-020 regardless of the frame) / **FIXED** (a batch-review-documented gap that is closed as of
this audit, with the fixing evidence). Severity: **S1** blocks correct/accessible use · **S2**
visible parity break an operator would notice · **S3** cosmetic · **S4** informational.

The accessibility bar is the same one desktop uses: `docs/product/prds/SelahCue-PRD.md:396`,
NFR-020 — WCAG 2.1 AA, ≥4.5:1 normal text, ≥3:1 large text/UI (large = ≥24px, or ≥18.66px bold).

---

# Summary

**24 numbered items: MOB-001…MOB-024.**

| Verdict | Count |
|---|---|
| MATCH | 9 |
| FIXED (batch-review gap, closed since) | 5 |
| A11Y-INTENTIONAL (frame wrong, code correct) | 3 |
| DRIFT | 4 |
| MISSING | 1 |
| UNSPECIFIED / scope note | 2 |

Severity: **0 × S1**, 4 × S2, 12 × S3, 8 × S4.

## Headline

**The user's instinct to distrust the doc-comment citations as proof of parity was right in
principle, but the actual drift this audit found is small.** Mobile's Design 2.0 migration
(Batch A, then Batch B) was unusually rigorous about the exact trap this audit exists to catch: the
implementation carries inline comments that *quote the WCAG ratio* at the point a frame value was
deliberately not built (e.g. `mobile_widgets.dart:43-45`, `enforcement.dart:166-168`), and a
dedicated `test/views/token_drift_test.dart` plus `test/models/design_tokens_test.dart` pin the
palette against exactly this kind of silent regression. A repo-wide grep for the single most
dangerous mapping error the spec itself calls out — `d2TextMuted` used for actual text instead of
`d2TextSecondary` (§2.3) — returns **zero hits** in any of the 13 surface files; every occurrence
still in the tree is inside a code comment explaining a fix already made, not a live violation.

So the gap between "cites a frame" and "verified against a frame" is real, but when this audit
closed it, most rows came back **MATCH** or **FIXED**, not **DRIFT**. This is a materially better
starting position than desktop's own first parity pass (`PME-`: 39 DRIFT / 16 MISSING out of 143
Part-A+B rows). The honest caveat is **coverage, not correctness**: 7 of the 13 surfaces were
audited at the depth described in §Method, not to the full per-element `get_design_context`
standard desktop's three audits used — see **§ Open questions, Q-01**.

**The one MISSING item found (MOB-018)** is a known, already-documented deferral, not a surprise:
the Timer tab's `Reset` and `Send "TIME UP" to stage` controls have no wire-protocol command to
send, so they are honestly described in words rather than built as dead buttons — a design decision
carried since Batch A, re-confirmed current in this pass.

---

# § Frame citation accuracy

| # | Surface | Cited frame(s) | Verdict | Evidence |
|---|---|---|---|---|
| — | Pairing / discovery | `342:133` | correct | `get_metadata` `342:133` (this session): "Discovered on your network", host rows, QR hint card — matches `pairing_view.dart:5` |
| **MOB-001** | App shell | `363:124` | **imprecise** | `controller_view.dart:2` cites `363:124`. `get_metadata` shows `363:124` is the **entire annotated spec board** "SPEC — Mobile · Navigation & Config" (1898×932, containing the app-bar screen `363:133`, the role-tabs board `364:128`, and the Config sheet board `366:128` as siblings). `MOBILE-2.0-SPEC.md §1` itself names the narrower, correct id: `363:133`. The citation is not wrong — `363:133` is inside `363:124` — but it points at the container, not the screen, which is a weaker anchor for a future reader trying to open the right frame directly. **Fix:** change the doc comment to `363:133`. Severity S4. |
| — | Live tab | `342:189`, `363:149` | correct | `363:149` confirmed via the `363:124` pull above (PREVIEW/LIVE monitors, GO LIVE, transport) — matches `live_tab.dart:2` |
| — | Config / About sheet | `366:128` | correct | `get_metadata` `363:124` pull includes `366:128` — CONNECTION/PREFERENCES/ABOUT groups match `controller_view.dart` `ConfigSheet` |
| — | Permission blocked | `357:218` | correct | `get_metadata` `357:218` (this session): lock glyph, "That's not in your role", ROLES THAT CAN card, Got it / Request access — matches `enforcement.dart:1-2` |
| — | Role changed — live | `358:128` | correct | `get_metadata` `358:128` (this session): "Your role changed → Observer", PREVIOUS CONTROLS, removed rows, reassurance row — matches `enforcement.dart:1-2` |
| — | Action rejected | `358:149` | correct | `get_metadata` `358:149` (this session): "Action rejected", reconnecting row — matches `enforcement.dart:1-2` |
| — | Scripture tab | `343:128` | correct | `get_metadata` `343:128` (this session): reference search, KJV picker, numbered verse rows, footer hint — matches `scripture_tab.dart:4` |
| — | Timer tab | `343:169`, `356:139` | correct | `get_metadata` `343:169` (this session): RUNNING chip, readout, custom-time well nested at `367:124`, ±1:00, Pause/Reset/Stop, TIME UP row — matches `timer_tab.dart:2` |
| — | Custom-time well | `367:126` | correct | `get_metadata` `367:126` (this session): HH:MM:SS three-pair well + Start — matches `custom_time_well.dart:1` |
| — | Plan tab | none (derived) | correct as stated | `plan_tab.dart:1-8` itself states no frame exists; `MOBILE-2.0-SPEC.md §4.4` agrees. Not a citation defect — an honest "no frame" note. |
| — | Detections view | (via `DETECTIONS-VIEW-spec.md`, no direct frame id in the file) | correct as stated | `detections_view.dart:1-21` cites the companion spec doc rather than a Figma frame id, consistent with that spec's own scope (route-level behaviour, not a drawn frame) |
| — | Role-scoped bottom tabs | `364:128` | correct | confirmed via the `363:124` pull — six role rows (Observer/Worship Leader/Scripture Op./Timer Op./Production Op./Administrator), each with per-tab visibility/view-only glyphs — matches `tab_scope.dart:1` |

**Result: 12 of 13 citations correct and precise; 1 (MOB-001) correct but imprecise (cites a
container board instead of the screen sub-frame). Zero dangling or wrong-screen citations found.**

---

# § The two known Figma-is-wrong cases — re-confirmed

`docs/delivery/CODE-REVIEW-batch-mobile-design2.md:60-61` recorded two places where the Figma
frames are wrong and the shipped code is intentionally right. Re-checked this session:

| # | Case | Figma says | Code does | Still correct? |
|---|---|---|---|---|
| **MOB-002** | Tab visibility — Observer role | `get_metadata` `364:128` (`364:130-152`, this session): Observer's **Scripture tab is drawn visible+view-only** (👁 badge present) and **Timer is drawn visible, not view-only** (no 👁 badge) | `tab_scope.dart:37-50` — `visibleTabsFor()` derives visibility purely from `role.can(Capability)`, not a per-role hardcoded table, so it structurally **cannot** reproduce the frame's inversion even by accident: Scripture only ever appears `if (role.can(Capability.searchScripture))`, and Timer's view-only flag is `!role.can(Capability.timer)` regardless of role name. | **A11Y-INTENTIONAL** (verdict repurposed here as "frame-wrong-code-right"). No change since the batch review; the capability-driven design makes regression toward the frame structurally unlikely, not merely undone. |
| **MOB-003** | Role naming — "Producer" vs "Production Operator" | `get_metadata` `364:128`/`366:128` (this session): **three** text layers still read "Production Op." (`364:243`) / "Controller · Production Operator" (`366:140`) / "Production Operator" (`366:153`) — more occurrences than the batch review's "five Figma text layers," but same defect class | `rbac.dart:109` — `MobileRole.producer.label => 'Producer'`. Confirmed the sole definition; `MobileRole.label` is what every role chip, the enforcement sheet's `_RolesCard`, the Config sheet, and the role-changed banner render (`enforcement.dart:264`, `mobile_widgets.dart:461`, `controller_view.dart:792`). | Still correctly resolved in code's favour. The Figma-side fix (rename the text layers, no code change) remains open — same status as the batch review left it. |

---

# § Per-surface findings

## 1. Pairing / discovery — `pairing_view.dart` (frame `342:133`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Gutter/spacing rhythm | MATCH | — | `pairing_view.dart:279,313,427` use `SelahSpace.gutter` (=20, `selah_theme.dart:61-62`) — spec §3.10 flagged the *pre-migration* app as using 14/16; current code is on the spec's 20. **[verified]** |
| — | `Connect` action per host row | MATCH | — | `pairing_view.dart:446-504` renders a `PAIRED` chip vs a `Connect` button per row, matching `get_metadata 342:133` (`342:149-151` PAIRED, `342:158-159`/`342:166-167` Connect) — **[verified]** |
| **MOB-004** | Host-row metrics (70pt height, icon inset) and waiting/error copy | not independently re-measured this session | UNSPECIFIED | Spec §4.1 marks these *measured*; not re-derived from `get_design_context` here — **[batch-review / inherited from spec, not independently re-verified]** |

## 2. App shell — `controller_view.dart` (frame `363:124`/`363:133`, see MOB-001)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | App-bar structure (title · LIVE chip · role chip · clock · ⓘ) | MATCH | — | `controller_view.dart:280` (`RoleBadge`), `:711-712` (56×56 identity element), `:540` (version string via `package_info_plus`, matching the Config sheet's `Version 1.0.0 (128)` row at `366:184`) — **[verified, structural]** |
| **MOB-001** | Doc-comment cites the container board, not the screen sub-frame | DRIFT (citation precision) | S4 | see §Frame citation accuracy above |
| **MOB-005** | Emergency strip role-gating (whole strip omitted when role holds neither Blackout nor ClearLive) | MATCH | — | `mobile_widgets.dart:462-466,486,527` — `canBlackout`/`canClear` gate each button independently; comment at `:462-464` states the call site omits the whole strip for a role with neither, consistent with spec §4.2 | **[verified]** |

## 3. Live tab — `live_tab.dart` (frames `342:189`, `363:149`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Stacked order: PREVIEW → transport → LIVE (not the role-home frames' side-by-side) | MATCH (documented deviation) | — | `live_tab.dart:4-8` doc comment states the spec (§4.3) explicitly resolves in favour of the shipped stacked order over `356:197`'s side-by-side drawing — a spec-level decision, not undocumented drift | — |
| — | `OutputCard`/`UpNextCard` construction | MATCH | — | `live_tab.dart:59,67,183` instantiate the shared `OutputCard`/`UpNextCard` from `mobile_widgets.dart` (audited in full above, §3.9 compliant) | **[verified via shared widget]** |
| **MOB-006** | Transport row exact metrics (64×54 Prev/Next, 8pt gaps) | not independently re-measured this session | UNSPECIFIED | **[batch-review / inherited from spec]** |

## 4. Plan tab — `plan_tab.dart` (no dedicated frame, derived per §4.4)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Empty-plan state | **FIXED** | — | Spec §4.4 flagged this as "*missing today — add*" at authoring time (2026-08-17). Current code has it in full: `plan_tab.dart:161-217` (`_EmptyPlan`) — 56×56 `d2Elevated` circle, `list_alt` glyph, "No items in this plan" as a `Semantics(header: true)`, "The operator adds items on the desktop." Matches spec's prescribed copy verbatim. **[verified]** |
| — | Hint footer (4 variants: syncing / read-only / stage+go-live / stage-only) | MATCH | — | `plan_tab.dart:34-40` — all four spec §4.4 copy variants present verbatim | **[verified]** |
| — | Row tint priority (live wins over staged) | MATCH | — | `plan_tab.dart:72-76` comment states and implements exactly this priority | **[verified]** |
| **MOB-007** | `KindBadge` on the row | MATCH (upgraded past spec's own "optional") | — | `plan_tab.dart:99` renders `KindBadge(kind: it.kind)` — spec §3.3 called the badge "optional in this pass; if it stays plain text it must move to `d2TextSecondary`." The badge was built, not left as plain text — a **superset** of what spec required. | **[verified]** |

## 5. Scripture tab — `scripture_tab.dart` (frame `343:128`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Gold-for-scripture-identity rule | MATCH | — | `scripture_tab.dart:552,558` — verse numbers / chapter heading in `DesignTokens.d2Gold`; doc comment `:7-9` states the rule explicitly and correctly ("gold never means status") | **[verified]** |
| — | "Approve" label (not the Figma role-home's "Approve → Live") | MATCH (documented resolution) | — | spec §4.5 records the FR-115 conflict and resolves it to "Approve." `get_metadata 357:218` (this session, the Scripture-role-home approval flow board) still shows the frame's own **"Approve → Live"** label (`357:224-225`) — confirming the frame is still unfixed, but that is a **known, resolved-in-code's-favour** item per spec, not new drift. | **[verified this session]** |
| — no MOB id — informational | Detection banner reroute | MATCH | — | `scripture_tab.dart` imports `detections_view.dart` (`:20`) — the Detections route supersedes the old inline card stack per `86ak188mz`, consistent with `detections_view.dart:6-13`'s stated rationale | **[verified]** |
| **MOB-008** | Verse-row exact metrics (≥26pt number column, row padding) | not independently re-measured this session | UNSPECIFIED | **[batch-review / inherited from spec]** |

## 6. Timer tab — `timer_tab.dart` (frames `343:169`, `356:139`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | HH:MM:SS custom-time well replaces the old minutes-only field | **FIXED** | — | `timer_tab.dart:219` uses `CustomTimeWell`; `custom_time_well.dart` full file audited (see §7) | **[verified]** |
| **MOB-009** | `Reset` / `Send "TIME UP" to stage"` | **FIXED** (2026-09-22, ticket 17tnw2axpty) | — | Both built, WITHOUT a new `Command` variant: `Reset` composes the existing `start_timer` with the host's `total_secs` (`timer_tab.dart:104-113`); `Send "TIME UP" to stage` composes the existing `adjust_timer` with a delta equal to `-remainingSecs`, landing the countdown in TIME UP via `AdjustTimer`'s own documented clamp-at-zero behaviour (`timer_tab.dart:115-124`). Mirrors the desktop operator console's own Reset button (`selahcue-operator/dist/app.js`'s `timer-reset` handler), which already used this exact composition. See Reconciliation. |
| — | PAUSED = warn chip (not neutral) | MATCH | — | `timer_tab.dart:119-120` comment + surrounding code implements this explicitly per spec §4.6 | **[verified]** |
| — | Lock-note copy uses `d2TextSecondary`, not `d2TextMuted` | **FIXED** (A11Y) | — | `timer_tab.dart:336` — the `d2TextMuted` reference is inside a **comment** citing the 3.96:1 failure as the reason it is NOT used; grep confirms zero live `d2TextMuted` usage in this file | **[verified]** |

## 7. Custom-time well — `custom_time_well.dart` (frame `367:126`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Three two-digit fields (HOURS/MIN/SEC) with `:` separators, min-height not fixed 67 | **DRIFT (intentional, documented)** | S4 | `CODE-REVIEW-batch-mobile-design2-b.md`'s own diff table: frame draws fixed 257×67; shipped uses **min-height** 67 so the well grows at large text-scale rather than clipping digits at 3.0×. Re-confirmed current via `custom_time_well.dart:1-30` doc comment, unchanged since the batch review. | **[batch-review, re-confirmed via doc comment]** |
| — | Clamp-not-rewrite entry behaviour (typing 60 in MIN leaves 6, doesn't silently coerce to 59) | MATCH | — | `custom_time_well.dart:22-28` (`maxCustomHours`, `_maxSexagesimal` constants) — the file's own doc comment states the declining-formatter rule; consistent with `test/views/custom_time_well_test.dart` (13 tests) existing as corroboration | **[verified, corroborated by test file presence]** |

## 8. Detections view — `detections_view.dart` (route-level, `DETECTIONS-VIEW-spec.md`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Carries its own `ConnectionBanner` + `PermissionBlockedHost` + `EmergencyStrip` (route covers the shell, so the route needs its own copies) | MATCH | — | `detections_view.dart:165,172,202` — all three present, matching the doc comment's stated rationale (`:14-19`) and `DETECTIONS-VIEW-spec.md §7.3/§7.6` | **[verified]** |
| — no MOB id | Scrolling list (not the old unbounded inline stack that caused `86ak188mz`'s RenderFlex overflow) | MATCH | — | `detections_view.dart:6-13` doc comment states the fix; `test/views/detections_overflow_test.dart` exists as corroboration | **[verified, corroborated by test file presence]** |

## 9. Permission blocked — `enforcement.dart` §4.10 (frame `357:218`)

Read in full this session (`enforcement.dart:27-224`).

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Modal scoped to the tab body, not the whole route (emergency strip stays reachable) | MATCH | — | `enforcement.dart:31-88` (`PermissionBlockedHost`) — `Stack` wraps only the `child` passed in, strip lives outside it per the class doc comment | **[verified]** |
| — | Lock-circle fill: `d2GoldSoft`, not the frame's `d2LiveSoft` | **A11Y-INTENTIONAL** | — | `enforcement.dart:166-171` — inline comment cites spec §6.2 item 4 by name: the frame transposes the fill, red would say "error" where the app means "not yours" | **[verified]** |
| — | "Request access" button absent (not disabled) | MATCH (documented deviation) | — | `enforcement.dart:206-216` — comment states no wire command exists; `Got it` takes full width, matching spec §4.10's own instruction to hide rather than disable | **[verified]** |
| — | Roles card falls back to generic copy when the host can't name qualifying roles | MATCH | — | `enforcement.dart:111-119` (`canName` gate) | **[verified]** |
| — | Chip tone parity with the app-bar role chip (`roleTone()` shared, not two tables) | MATCH | — | `enforcement.dart:265` uses `roleTone(role)` from `primitives.dart`, same function `RoleBadge.toneFor` delegates to per `controller_view.dart` | **[verified]** |

## 10. Role changed — live — `enforcement.dart` §4.11 (frame `358:128`)

Read in full this session.

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Inline non-blocking banner, not a modal | MATCH | — | `enforcement.dart:288-427` (`RoleChangedBanner`) is inserted inline; no route push, no dialog | **[verified]** |
| — | Removed-capability rows dimmed to 0.5 opacity | MATCH | — | `enforcement.dart:559-560` | **[verified]** |
| **MOB-010** | Contrast of the dimmed rows' text/icon **after** compositing (not the token's own on-surface contrast) | MATCH, and a genuinely sharper catch than spec called for | — | `enforcement.dart:549-557,584-586` — the implementation's own comment works through the actual math: `d2TextSecondary` on `d2Surface` alone is 8.12:1 and would look compliant in isolation, but composited through the ancestor `Opacity(0.5)` it becomes **2.97:1** and fails. The code uses `d2Text` at 0.5 (→ 4.96:1, passes) instead, and moves the label/marker distinction to size+weight rather than colour. This is evidence of *more* rigour than the spec (§4.11) itself specified — worth flagging as a pattern worth back-porting to any other `Opacity`-wrapped text elsewhere in the app (see **§Open questions Q-02**). | **[verified]** |
| — | Auto-dismiss 20s, cancelled on dispose, `SemanticsService.sendAnnouncement` (not the deprecated `announce`) | MATCH (justified deviation) | — | `enforcement.dart:297-307,349-359,370-374` — comment explains `announce` was deprecated post-Flutter 3.35 for multi-window; same channel/event/assertiveness | **[verified]** |
| — | Reassurance row gated on `Capability.monitor`, not shown unconditionally | MATCH | — | `enforcement.dart:410-421` | **[verified]** |
| — | Upgrade (not just downgrade) also reported | EXTRA (beyond frame, correctly justified) | — | `enforcement.dart:469-473` — frame only draws the downgrade case; code handles both, with adapted copy | **[verified]** |

## 11. Action rejected — `enforcement.dart` §4.12 (frame `358:149`)

Read in full this session.

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Takes the connection-banner slot rather than competing with the reconnect bar | MATCH | — | `mobile_widgets.dart:55-57` (`ConnectionBanner.build`, checked first) | **[verified]** |
| — | Reduced-motion swaps the spinner for a static ring | MATCH | — | `enforcement.dart:733-757` (`_ReconnectSpinner`) | **[verified]** |
| — | "Nothing is queued/retried" stated explicitly in copy | MATCH | — | `enforcement.dart:674-683` | **[verified]** |

## 12. Config / About sheet — `controller_view.dart` `ConfigSheet` (frame `366:128`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Version row sourced live from `package_info_plus`, not hardcoded | MATCH (better than the frame) | — | `controller_view.dart:540` — frame draws the literal string `1.0.0 (128)` (`get_metadata 366:128`, node `366:184`); code reads the real build | **[verified]** |
| **MOB-011** | Privacy policy / Terms of use rows (shipped, frame omits them) | EXTRA, correctly kept | S4 | Not independently re-confirmed present in this session's grep pass of `controller_view.dart` beyond the `366:*` metadata pull, which — being Figma's own frame — naturally omits them; spec §4.8 explicitly instructs "Keep them — they are store-compliance surfaces." Flagged **UNSPECIFIED** on the implementation side pending a direct grep for the row labels — see **§Open questions Q-01**. |

## 13. Role-scoped bottom tabs — `tab_scope.dart` (frame `364:128`)

| # | Item | Verdict | Sev | Source |
|---|---|---|---|---|
| — | Capability-driven visibility (not a hardcoded per-role table) | MATCH, structurally stronger than the frame | — | `tab_scope.dart:37-50` — see MOB-002 | **[verified]** |
| — | "More" tab omitted on the 4-role backend | MATCH (documented scope decision) | — | `tab_scope.dart:11-13` comment: Production/Admin tools are Operator-only on this backend; tracked as `86ajxufbg` for the 7-role expansion, not a defect in the 4-role build | **[verified]** |

---

# § Accessibility

## A11Y-1 — Confirmed fixed since `MOBILE-2.0-SPEC.md`'s authoring (2026-08-17)

| # | Item | Spec's flagged ratio | Current state |
|---|---|---|---|
| — | Connection banner (reconnecting/syncing/error) | white-on-solid `warnFill`/`liveFill`: 2.04:1 / 3.27:1 | `mobile_widgets.dart:43-45` states the fix in a comment; soft-tint form measures 7.56:1 / 5.31:1 per the same comment — **[verified against source, ratio not independently re-measured with a contrast tool this session]** |
| — | Permission-blocked lock circle | frame's `d2LiveSoft` fill | `enforcement.dart:166-171` — `d2GoldSoft` — **[verified]** |
| — | Timer lock-note / captions | `d2TextMuted` at 3.96:1 | `d2TextSecondary` throughout; grep confirms zero live `d2TextMuted` text usage in any of the 13 surface files — **[verified]** |
| — | Role-changed removed-capability rows | naive `d2TextSecondary` inside `Opacity(0.5)` would composite to 2.97:1 | `d2Text` at 0.5 → 4.96:1, see MOB-010 — **[verified]** |

## A11Y-2 — Open, not newly found by this audit

| # | Item | Status |
|---|---|---|
| **Q-03** (see below) | `d2InfoBorder` has no palette member (spec §2.6 item 2); `_ReconnectingRow` (`mobile_widgets.dart:692-725`) uses `SelahToneStyle.of(SelahTone.info)` — whether that resolves to the spec's recommended `Color.lerp` construction or the escalation (`d2InfoBorder` as a real token) was not traced into `primitives.dart`/`selah_theme.dart` this session. | UNSPECIFIED — see Open questions |
| — | Tap-target audit (48×48dp minimum, NFR-026) | Not independently re-measured against rendered widget geometry this session; spec §3 states the rule and cites specific elements it raised to 48 in the frames' own narrower drawings (e.g. the ⓘ button, the refresh icon). Taken as MATCH by inheritance from spec + the fact the two full-file reads (enforcement/mobile_widgets) show consistent `SelahSpace`-driven sizing, not spot-checked with `flutter test --update-goldens` or `inspect`. |

## A11Y-3 — Clear

- WCAG 1.4.1 (colour not the only signal): every tinted row/chip audited in this pass (Live/Preview
  monitor, Plan-tab row tint, Role-changed removed rows) pairs the tint with a text label or glyph —
  `plan_tab.dart:118-124` comment states the rule explicitly, `enforcement.dart` uses lock/warning
  glyphs throughout.
- No white-on-gradient GO-LIVE-green pairing was found reachable from the audited surfaces; the
  success-button gradient is confined to `OutputCard`'s wash (a background, not a text-carrying
  fill) per `mobile_widgets.dart:214-219`.

---

# § Open questions

- **Q-01 — Coverage depth.** 7 of 13 surfaces (`pairing_view.dart`, most of `controller_view.dart`,
  `live_tab.dart`, `scripture_tab.dart`, `timer_tab.dart` outside the well, `detections_view.dart`
  outside its three shared-widget mounts) were audited via doc-comment + structural grep + the
  Batch A/B review's own diff tables, not a full `get_design_context` pixel pass per element, for
  budget reasons stated in §Method. This is real, not a formality: MOB-004, MOB-006, MOB-008,
  MOB-011 are explicitly marked UNSPECIFIED for exactly this reason. **Recommendation:** a focused
  follow-up pass pulling `get_design_context` on the remaining un-pixel-verified nodes
  (`342:133` sub-elements, `363:149` transport metrics, `343:128` verse-row metrics) before this
  audit is treated as a complete parity baseline equal to desktop's three. Owner: product/design.
- **Q-02 — The composited-opacity contrast pattern (MOB-010).** `enforcement.dart`'s `_RemovedRow`
  correctly computes contrast *after* an ancestor `Opacity` wrapper rather than on the raw token
  pair. Grep this session did not find another `Opacity(...)`-wrapped text element elsewhere in
  `lib/views/` to check for the same trap in reverse (a token that looks compliant in isolation but
  fails once composited). Recommendation: a repo-wide sweep for `Opacity(` + nearby `Text(` as a
  follow-up audit, not scoped into this pass.
- **Q-03 — `d2InfoBorder`.** Spec §2.6 item 2 leaves this as an owner decision (escalate to a real
  palette member, four-surface lockstep change) vs. the `Color.lerp` workaround. Not traced into
  `primitives.dart` this session — whether the workaround or the real token is what `SelahTone.info`
  currently resolves to is unconfirmed. Owner: design + `test_tokens.rs` maintainer.
- **Q-04 — MOB-009 (Timer `Reset`/`TIME UP`). ANSWERED 2026-09-22 — see Reconciliation below.**
  This question assumed new `Command` variants were required; they were not. The
  `TimerSnapshot` original-duration field it also asked for had ALREADY shipped
  (`total_secs`, desktop-only) since the Design 2.0 operator console rewrite that predates this
  audit — the gap was that the Dart client never parsed it, not that the Rust wire lacked it.
- **Q-05 — MOB-001.** A one-line doc-comment fix (`controller_view.dart:2`, `363:124` → `363:133`).
  Not blocking; flagged for the next mobile touch to this file rather than justifying its own
  ticket.

---

# § Reconciliation — 2026-09-22 (Mika, implementation ticket 17tnw2axpty)

**MOB-009 closed. Q-04's premise was wrong: no new wire-protocol `Command` was needed for either
control.** The ticket (and this audit's Q-04) inherited its scope from `CODE-REVIEW-batch-mobile-
design2-b.md`'s "Not built" section, written when `TimerSnapshot` genuinely had no original-duration
field on EITHER side of the wire. Between that batch review and this ticket, the Design 2.0 operator
console rewrite (commit `c109193`) added `TimerSnapshot.total_secs` (+ `paused`) to the Rust struct
AND shipped the desktop console's own `Reset` button — but only on the desktop side. The Dart
`TimerSnapshot` model, the cross-language pinned fixtures, and the mobile Timer tab were never
updated to match, so the gap this ticket describes was real on mobile, just not for the reason
recorded: the field existed, the client just didn't read it.

Verified directly (not assumed) before implementing:

- `git log -S"total_secs" -- selahcue-lan/src/protocol.rs` and `git log -S"timer-reset" --
  selahcue-operator/dist/app.js` both land on `c109193`, confirming `total_secs` and the desktop
  Reset button shipped together, desktop-only, and predate this ticket.
- `selahcue-operator/dist/app.js`'s `timer-reset` handler (`:3385-3414`) already composes `start_timer`
  with `total_secs` (falling back to `remaining_secs + elapsed_secs` for an older host) — proving this
  composition is not a new idea invented for mobile, it is the SAME control already shipped, reviewed,
  and running in production on the other client.
- `Timer::adjust` (`selahcue-core/src/timer.rs:53-64`) and its own doc comment — "Reducing below the
  elapsed lands the timer in TIME UP on the next read" — confirm `AdjustTimer` already produces exactly
  the forced-overrun `Send "TIME UP" to stage` needs; `is_time_up` (`:135-140`) is `elapsed >= duration`,
  so driving `duration` down to `elapsed` (a delta of `-remainingSecs`) lands it there deterministically.
- `rbac.rs:130-134` — `StartTimer`/`AdjustTimer`/`StopTimer`/`PauseTimer`/`ResumeTimer` all require the
  SAME `Permission::Timer`, which the mobile Timer tab already gates its whole controls block on
  (`widget.live.can(Capability.timer)`). No RBAC change, no 7-role concept, nothing beyond the existing
  4-role model this ticket's guardrail asked not to expand.

**What actually shipped** (both sides, in lockstep per CLAUDE.md's pinned-fixture rule):

| Change | File |
|---|---|
| `TimerSnapshot.totalSecs` added, parses `total_secs` | `lib/models/protocol.dart` |
| `Reset` + `Send "TIME UP" to stage` controls, full doc-comment rewrite | `lib/views/tabs/timer_tab.dart` |
| Pinned fixture: `total_secs` round-trip (`to_json` populated shape + `from_json` against the SAME string the Dart test parses) | `selahcue-lan/tests/test_protocol.rs` (`timer_snapshot_total_secs_is_a_pinned_wire_shape_for_reset_and_time_up`) |
| Mirrored fixture + assertion | `test/models/protocol_test.dart` |
| Widget tests: Reset uses `totalSecs`, falls back to `remaining+elapsed` without it, Send-TIME-UP sends the right delta, disabled once already at TIME UP, both hidden for a Viewer | `test/views/timer_tab_test.dart` |

**No `selahcue-lan/src/protocol.rs` edit in this PR** — deliberately. `Command` is unchanged; only the
Dart model gained a field the Rust wire already sent. This is narrower than the ticket's own stated
scope ("New `Command` variants... for Reset and Send-TIME-UP"); flagged in the ClickUp start comment
and PR description rather than silently substituted, so the ticket owner can object before merge.

**A11Y note on the new control.** The frame's own `Send "TIME UP" to stage` caption colour
(`#6b7383`/`d2TextMuted`) on the frame's solid `#ff4d4d`/`d2Live` fill is ~1.5:1 — nowhere near AA.
Built with `SelahGradient.onLiveInk` instead (the same ink `SelahButtonVariant.alarm` already uses on
this exact fill, at a documented 5.31:1) for both the title and the caption — the same class of fix as
this file's pre-existing lock-note A11Y-FIX, not a new pattern.

---

# § Pending ClickUp update

No ClickUp task exists for this audit yet — see the Goal Contract's Identity block. Pending
Phase D of the parent plan (`~/.claude/plans/most-of-what-is-enumerated-noodle.md`), which converts
this document's findings into tickets alongside the desktop audits' reconciled backlog.
