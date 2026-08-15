# Mobile — "Needs your approval" detections view · UX spec

- Date: 2026-08-15 · Role: `/ui-ux-designer` (Uma) → `/mobile-engineer` (Mika), `/qa-engineer` (Quinn)
- ClickUp: [86ak188mz](https://app.clickup.com/t/86ak188mz) (Bug, high) · epic [86ajp086b](https://app.clickup.com/t/86ajp086b) · regression of [86ajxx4uv](https://app.clickup.com/t/86ajxx4uv)
- Goal contract: [`docs/delivery/goals/GOAL-mobile-detections-view-ux.md`](../delivery/goals/GOAL-mobile-detections-view-ux.md)
- Surfaces: `implementation/mobile/selahcue_controller` (Flutter controller)
- Companions: [UX-CANONICAL.md](UX-CANONICAL.md) (authoritative on colour + emergency chrome) · [DESIGN-TOKENS.md](DESIGN-TOKENS.md) · [DESIGN-2.0-HANDOFF.md](DESIGN-2.0-HANDOFF.md) §5.5/§5.8/§6/§7 · [MOBILE-DESIGN-CLEANUP-handoff.md](MOBILE-DESIGN-CLEANUP-handoff.md) §1/§4/§5
- Requirements: FR-095 (mobile suggestion approval), FR-115 (operator-confirmation is the default mode; nothing auto-displays), FR-097 (a stale command is rejected, never queued), NFR-026 (mobile accessibility)

> **Reminder for readers new to the codebase.** A SelahCue *theme* is a slide-design template
> (typography / background / elements), **not** a light/dark colour mode. Nothing in this spec
> concerns themes. See [THEME-MODEL-spec.md](THEME-MODEL-spec.md).

---

## 1. Why this exists

The Scripture tab draws every pending auto-detected verse as a full approval card, stacked
directly into the tab's `Column` (`lib/views/tabs/scripture_tab.dart`, `_detectionSection` /
`_detectionRow`). The verse list is the only child allowed to flex, so once five or six
detections are waiting the cards consume the whole viewport, the list is handed a negative
height, and the tab breaks — translation picker, reference field and verse list all go with it.

A talkative preacher generates detections quickly. The operator loses scripture control at
precisely the moment they need it.

**The class of bug, not just the instance.** The defect is *a `Column` child whose height is a
function of unbounded host state*. Relocating the cards is necessary but not sufficient — the
replacement must be bounded in the detection count **and** must not clip when the operator has
large system text. Both properties are specified below and both are testable.

### 1.1 The approved interaction contract (authoritative, do not diverge)

1. The Scripture tab keeps only a **single-line banner of count-independent height**:
   `⚠ N verses need approval ›`, warn-toned. Tapping it pushes a full-screen route.
2. New full-screen route **`Needs your approval · N`** — a scrolling list of detection cards.
   Each card is reference + confidence badge (`97% MATCH`) + up-to-2-line ellipsised verse text
   + an Approve / Reject pair. Approve stages to Preview. Reject dismisses. **Nothing ever
   auto-displays** (FR-115, human-in-the-loop gate FR-095).
3. A **pending-count badge on the Scripture tab icon**, so detections are visible from Live,
   Plan and Timer. It **composes with** the existing muted view-only dot; it never replaces it.
4. **Drain:** if the host clears the last detection while the route is open, show an
   "All caught up" empty state. **No auto-pop.** The route **does** pop on device revoke or on
   loss of the `SearchScripture` capability.

### 1.2 Spec clarification the contract needs

"Fixed-height banner" means **fixed with respect to the detection count** — the property that
fixes the bug. It does **not** mean a literal `SizedBox(height: 44)`. A hard pixel height clips
the label the moment the operator raises their system font size, which converts an overflow bug
into a legibility bug on the same screen. The banner's height is therefore
`max(48dp, intrinsic content height at the current text scale)` and is **O(1) in N**. See §5.2.

---

## 2. Scope

### In scope

- The Scripture-tab approval banner (replaces `_detectionSection` / `_detectionRow`)
- The Scripture tab-icon pending-count badge in `ControllerView`
- The full-screen route `lib/views/detections_view.dart`
- All states, tokens, metrics, copy, accessibility and motion for the above

### Non-goals

- Backend, wire-protocol or RBAC change — `DetectionView`, `approve_detection` and
  `dismiss_detection` already exist and are unchanged
- The Design 2.0 mobile re-skin (see §4.1)
- Low-confidence "alternatives / Edit" treatment (DESIGN-2.0-HANDOFF §5.5 state 4) — see §16
- Detection history / audit tab (DESIGN-2.0-HANDOFF §5.5 state 8) — desktop-only for now
- Any auto-display or auto-approve behaviour. FR-115 forbids it on this surface.

---

## 3. Data the surface renders

From `lib/models/protocol.dart` — nothing else is available, so nothing else may be designed in.

| Field | Type | Notes for design |
|---|---|---|
| `DetectionView.id` | `int` | Command target. Never shown. |
| `DetectionView.reference` | `String` | May be empty on a malformed host reply — see S13. |
| `DetectionView.text` | `String` | Verse text. May be empty; the block is then omitted. |
| `DetectionView.confidence` | `int?` | Whole percent 0–100. **Nullable** — badge omitted when null. |
| `DetectionView.translation` | `String` | e.g. `KJV`. Empty when the host omits it. **Currently unused in the UI — this spec surfaces it.** |
| `DetectionView.sourceSegment` | `int?` | Transcript provenance. Not shown on mobile (see §16). |
| `OperatorStateView.detections` | `List<DetectionView>` | Host order is authoritative — do not re-sort. |

Controller state consumed: `live.view`, `live.can(Capability.searchScripture)`, `live.revoked`,
`live.syncing`, `live.reconnecting`, `live.error`, `live.act(...)`.

---

## 4. Design-system basis

### 4.1 Token layer — use the canonical layer, not `d2*`

The mobile app renders entirely on the **canonical** `DesignTokens` members. The additive
Design 2.0 `d2*` members exist in `lib/models/design_tokens.dart` but **no mobile surface
consumes them**, and adopting them is a coordinated four-surface migration with a WCAG re-audit
(DESIGN-2.0-HANDOFF §3.2, open owner decision §9.1).

**This surface uses the canonical layer.** Building it on `d2*` would produce a single
violet-and-warm-ink screen inside a blue-and-cool-ink app, and would need re-doing at migration
time anyway. When the migration runs, this spec's §4.2 mapping column is the swap list.

### 4.2 Token provenance — every colour used here

All members exist today in `lib/models/design_tokens.dart`. **No colour outside this table may
appear in the implementation, and no raw hex may be written into a widget.**

| Purpose | Token | Hex | Design 2.0 successor (migration only) |
|---|---|---|---|
| Screen / tab background | `DesignTokens.bgBase` | `#0E1116` | `d2Base` |
| Card / app-bar / nav surface | `DesignTokens.bgPanel` | `#171B22` | `d2Surface` |
| Hairline borders | `DesignTokens.border` | `#2B323D` | `d2Border` |
| Primary text | `DesignTokens.textPrimary` | `#EEF1F6` | `d2Text` |
| Secondary / hint text | `DesignTokens.textMuted` | `#9AA4B2` | `d2TextSecondary` |
| Warn ink (banner text, icons, border) | `DesignTokens.warnInk` | `#F2B53C` | `d2Warn` |
| Warn fill (banner tint, count badge) | `DesignTokens.warnFill` | `#9A5B00` | `d2WarnSoft` |
| Approve button fill | `DesignTokens.previewFill` | `#0F7B6C` | `d2Preview` |
| "All caught up" tick | `DesignTokens.previewInk` | `#2BB673` | `d2Preview` |
| Error banner fill | `DesignTokens.liveFill` | `#A3283A` | `d2LiveSoft` |
| Brand accent (progress, focus) | `DesignTokens.accentBrand` | `#5B6BD6` | `d2Primary` |

> `DesignTokens.d2*` members are **out of bounds** for this work.

### 4.3 Contrast — measured, against the pinned audit

`selahcue-present/tests/test_tokens.rs` pins `AA_TEXT = 4.5` and asserts white-on-fill and
ink-on-background for every canonical token. The pairs this surface introduces, computed to
WCAG 2.1 relative luminance:

| Foreground | Background | Ratio | Bar | Verdict |
|---|---|---|---|---|
| `warnInk` `#F2B53C` | banner tint (`warnFill` @ 14 % over `bgBase` ≈ `#221B13`) | **9.28 : 1** | 4.5 | pass |
| `warnInk` | `bgBase` | **10.31 : 1** | 4.5 | pass |
| `warnInk` | `bgPanel` | **9.41 : 1** | 4.5 | pass |
| White | `warnFill` (count badge) | **5.42 : 1** | 4.5 | pass |
| White | `previewFill` (Approve) | **5.16 : 1** | 4.5 | pass |
| White | `liveFill` (error banner) | **7.19 : 1** | 4.5 | pass |
| `textPrimary` | `bgPanel` (card body) | **13.9 : 1** | 4.5 | pass |
| `textMuted` | `bgPanel` (verse text) | **6.84 : 1** | 4.5 | pass |
| `textMuted` | `bgBase` (footnote) | **7.50 : 1** | 4.5 | pass |
| `previewInk` | `bgBase` ("All caught up" tick) | **7.24 : 1** | 4.5 | pass |

Warn-on-dark is the tone the brief asked about specifically: at **9.28 : 1** the banner clears
AA-normal twice over. It is safe at 13sp and would still clear at 11sp.

> **The canonical `textMuted` `#9AA4B2` is fine for body text at 7.5 : 1.** Do not confuse it
> with the Design 2.0 `d2TextMuted` `#6B7383`, which is label-only (DESIGN-TOKENS a11y note).
> Another reason this surface stays on the canonical layer.

### 4.4 Scale

- **Spacing:** 4 / 8 / 10 / 12 / 14 / 16 / 20 / 24 (MOBILE-DESIGN-CLEANUP §4). Horizontal
  gutter inside the Scripture tab is **14**, to align with the existing search row.
- **Radius:** banner and inline chips **10**; cards **12**; buttons **8**; pills **4**
  (matches `StatusBadge`).
- **Borders:** 1 dp, always a token colour, never a shadow (the app is flat by design).
- **Type** (all existing mobile values — no new steps):

  | Role | Size / weight | Letter-spacing | Colour |
  |---|---|---|---|
  | Route title | 16 / w700 | 0 | `textPrimary` |
  | Card reference | 15 / w700 | 0 | `textPrimary` |
  | Empty-state heading | 17 / w700 | 0 | `textPrimary` |
  | Banner label | 13 / w700 | 0.2 | `warnInk` |
  | Body / verse text | 13 / w400, line-height 1.4 | 0 | `textMuted` |
  | Button label | 14 / w600 | 0 | white or `textPrimary` |
  | Badge / pill | 11 / w800 | 0.5 | white or `textMuted` |
  | Footnote / hint | 11 / w400 | 0 | `textMuted` |

- **Touch targets: ≥ 48 × 48 dp for every interactive element.** MOBILE-DESIGN-CLEANUP §1 sets
  48; DESIGN-2.0-HANDOFF §6 sets ≥ 44 pt. 48 dp satisfies both — use 48.

---

## 5. Surface A — the Scripture-tab banner

Replaces `_detectionSection` and `_detectionRow` entirely. Those two methods are deleted.

### 5.1 Anatomy

```
┌──────────────────────────────────────────────────────────┐   ← 1dp warnInk border, r10
│  ⚠   4 verses need approval                          ›   │   ← warnFill @14% over bgBase
└──────────────────────────────────────────────────────────┘   ← min 48dp tall, full width
   18dp   13/w700 warnInk, maxLines 1, ellipsis      20dp
```

### 5.2 Metrics

| Property | Value |
|---|---|
| Position | First child of the Scripture tab `Column`, above the translation + search row |
| Outer margin | `EdgeInsets.fromLTRB(14, 12, 14, 0)` — identical to the section it replaces, so nothing else on the tab moves |
| Inner padding | `EdgeInsets.symmetric(horizontal: 12, vertical: 10)` |
| Height | `ConstrainedBox(minHeight: 48)` around intrinsic content. **Never a fixed `SizedBox`.** ≈48 dp at scale 1.0, ≈58 dp at 2.0, ≈75 dp at 3.0 — and **constant in N at every scale** |
| Fill | `DesignTokens.warnFill.withValues(alpha: 0.14)` (the exact treatment already used by `_detectionSection`) |
| Border | 1 dp `DesignTokens.warnInk`, radius 10 |
| Leading icon | `Icons.warning_amber_rounded`, 18 dp, `warnInk` |
| Label | 13 / w700 / ls 0.2 / `warnInk`, `maxLines: 1`, `overflow: TextOverflow.ellipsis`, wrapped in `Expanded` |
| Trailing icon | `Icons.chevron_right`, 20 dp, `warnInk` |
| Ink | `Material` + `InkWell` with radius 10 so the ripple is clipped to the banner |

> **Use real `Icon`s, not the `⚠` and `›` glyphs.** `U+26A0` has an emoji presentation variant
> that renders as a full-colour glyph on iOS — it ignores `warnInk` and breaks the warn tone —
> and glyph metrics differ across Android OEM fonts, so a text-glyph banner will not have the
> same height on two devices. The label's *wording* stays exactly as the contract specifies.

### 5.3 Copy

| N | Label |
|---|---|
| 0 | banner is absent (not empty — absent) |
| 1 | `1 verse needs approval` |
| ≥ 2 | `N verses need approval` |

Singular/plural is a required behaviour, not a nicety: `1 verses need approval` in front of a
volunteer mid-service reads as a broken app.

### 5.4 Interaction

- Whole banner is one tap target, full content width, ≥ 48 dp tall.
- Tap → `SettingsScope.maybeOf(context)?.haptic()` then push the route (§7.2). The haptic call
  matches the precedent in `EmergencyStrip._guarded`.
- **The banner is never disabled**, including while `live.syncing`. Reading the queue is always
  safe; it is the Approve/Reject *actions* that are gated (§8.6). Blocking navigation during a
  reconnect would strand the operator with a count they cannot inspect.

---

## 6. Surface B — the Scripture tab-icon count badge

In `ControllerView._destinationFor`.

### 6.1 The composition rule

Today `_destinationFor` wraps the icon in a `Badge(backgroundColor: textMuted, smallSize: 7)`
when `spec.viewOnly`. The count badge must **compose** with that dot, never replace it.

| Both present? | Count badge | View-only dot |
|---|---|---|
| Count only | default top-end | — |
| View-only only | — | default top-end (**unchanged from today**) |
| Both | top-**end** | top-**start**, `offset: Offset(-2, -2)` |

Rationale for who moves: the count is actionable and time-critical, so it keeps the
conventional top-end position; the view-only dot is an ambient property of the tab and yields.

```dart
// shape only — the count badge is the OUTER wrapper
Badge(                                   // count
  backgroundColor: DesignTokens.warnFill,
  textColor: Colors.white,
  label: Text(n > 99 ? '99+' : '$n'),
  child: viewOnly
      ? Badge(                           // view-only dot, displaced to top-start
          backgroundColor: DesignTokens.textMuted,
          smallSize: 7,
          alignment: AlignmentDirectional.topStart,
          offset: const Offset(-2, -2),
          child: Icon(i),
        )
      : Icon(i),
)
```

### 6.2 The branch is currently unreachable — test it directly anyway

`lib/models/tab_scope.dart:46-47` hides the Scripture tab entirely from a role without
`Capability.searchScripture`, and always constructs it `viewOnly: false`. **On today's 4-role
backend the Scripture tab can never be view-only**, so the both-present branch cannot be reached
through any role.

It is still required, because the 7-role expansion (`86ajxufbg`) is the case the product owner
was protecting against. Because no role reaches it, it **must be covered by a widget test that
calls the destination builder with a synthetic `TabSpec(ControllerTab.scripture, viewOnly: true)`
plus a non-zero count** — a role-driven test will silently pass without exercising anything.

### 6.3 Metrics and behaviour

| Property | Value |
|---|---|
| Fill | `DesignTokens.warnFill` — ties the badge to the banner; white label is 5.42 : 1 |
| Label | 11 / w800, white, `99+` above 99 |
| Shown when | `n > 0` **and** the Scripture tab is present for the role (which already implies `searchScripture`) |
| Hidden when | `n == 0`. No zero badge, no placeholder. |
| Animation | **None.** See §12.4. |
| Value source | `live.view?.detections.length ?? 0`, recomputed on the existing 1 s poll rebuild — no new timer |

---

## 7. Surface C — the `Needs your approval` route

New file `lib/views/detections_view.dart`, per the ClickUp contract.

### 7.1 Layout

```
┌────────────────────────────────────────────┐
│ ‹  Needs your approval   [ 4 ]             │  AppBar, bgPanel, 56dp
├────────────────────────────────────────────┤
│ ⚠ Reconnecting to the host… (only if …)    │  connection banner — §7.3
├────────────────────────────────────────────┤
│  ╭──────────────────────────────────────╮  │
│  │ Romans 8:28 · KJV        94% MATCH   │  │  scrolling ListView
│  │ And we know that all things work…    │  │
│  │ ┌──────────┐  ┌──────────┐           │  │
│  │ │ Approve  │  │  Reject  │           │  │  each ≥48dp
│  │ └──────────┘  └──────────┘           │  │
│  ╰──────────────────────────────────────╯  │
│  ╭──────────────────────────────────────╮  │
│  │ …                                    │  │
│                                            │
│  Approving stages the verse in Preview.    │  footnote, last list child
│  It does not go on air.                    │
├────────────────────────────────────────────┤
│  ■ BLACKOUT          ✕ CLEAR ALL           │  EmergencyStrip — §7.6, REQUIRED
└────────────────────────────────────────────┘
```

The whole body (banner + list + strip) is wrapped in `ResponsiveBody` (560 dp cap, centred) per
MOBILE-DESIGN-CLEANUP §1 — this is a screen body, so the tablet rule applies to it too.

### 7.2 Route construction

| Property | Value |
|---|---|
| Route | **plain `MaterialPageRoute`** (see §12.1 — a hand-rolled `PageRouteBuilder` breaks reduced motion) |
| Settings | `RouteSettings(name: 'detections')` so tests and future analytics can identify it |
| Push from | The banner only. The route is not a tab and is not reachable any other way. |
| Full-screen | Yes — `fullscreenDialog: false`, so iOS keeps its edge-swipe-back gesture |
| Scaffold background | `DesignTokens.bgBase` |
| Rebuild source | `ListenableBuilder(listenable: live, …)` — the same controller the tabs use, no new state |

### 7.3 App bar and connection banner

- `AppBar`, `backgroundColor: DesignTokens.bgPanel`, `elevation: 0`, default back button
  (keeps the localized "Back" tooltip and the iOS swipe gesture).
- Title is a `Row`: `Flexible(Text('Needs your approval', maxLines: 1, overflow: ellipsis,
  style: 16/w700 textPrimary))` + `SizedBox(width: 8)` + the count pill.
- **Count pill:** reuse `StatusBadge(text: '$n', color: DesignTokens.warnFill)`. It sits outside
  the `Flexible`, so **the count can never be the thing that gets ellipsised** — at a large text
  scale the words truncate and the number survives. Hidden when `n == 0`.
- **Connection banner:** the route must render `live.syncing` and `live.error` itself, with the
  same copy and colours `ControllerView` uses. A pushed route covers `ControllerView.body`, so
  without this the operator taps Approve during a reconnect and nothing happens, with no
  explanation anywhere on screen. See §14.3.

### 7.4 The detection card

| Element | Spec |
|---|---|
| Container | `bgPanel` fill, 1 dp `border`, radius 12, padding 12, `margin: EdgeInsets.only(bottom: 10)` |
| Card body tap | **None.** The card is not interactive; only the two buttons act. An `InkWell` on the body would make "did I open it or approve it?" ambiguous on a slip-prone touch surface. |
| Reference | `'{reference} · {translation}'` when `translation` is non-empty, else `reference`. 15 / w700 / `textPrimary`, `maxLines: 2`, ellipsis, in an `Expanded`. Showing the translation matters because the verse text below is ellipsised — the operator is judging a match, and needs to know which text they are reading (DESIGN-2.0-HANDOFF §7). |
| Confidence badge | `'{confidence}% MATCH'`, 11 / w800 / ls 0.5, `textMuted` on a `bgBase` pill, 1 dp `border`, radius 4, padding `(8, 3)`. **Omitted entirely when `confidence == null`.** |
| Verse text | `maxLines: 2`, ellipsis, 13 / line-height 1.4 / `textMuted`, `padding: only(top: 6)`. Omitted when `text` is empty. |
| Action row | `SizedBox(height: 10)` above; Approve then Reject; see §7.5 |

> **The confidence badge must not be green.** The shipped card renders it in
> `DesignTokens.previewInk`. UX-CANONICAL §4 assigns green exactly one meaning —
> *preview / staged, not on air* — and a green `94% MATCH` on a card whose whole purpose is
> that the verse is **not** staged inverts that meaning. Confidence is a neutral quantity:
> render it muted-on-inset. This is a deliberate correction, not a regression; the existing
> test asserts the string `94% MATCH`, not its colour, so it stays green-free and green.

### 7.5 Approve / Reject

| Property | Approve | Reject |
|---|---|---|
| Widget | `FilledButton` | `OutlinedButton` |
| Fill / border | `backgroundColor: DesignTokens.previewFill`, white label | `side: BorderSide(color: DesignTokens.border)`, `foregroundColor: DesignTokens.textPrimary` |
| Min size | `Size(0, 48)` | `Size(0, 48)` |
| Label | `Approve` | `Reject` |
| Command | `live.act(cmdApproveDetection(d.id))` | `live.act(cmdDismissDetection(d.id))` |
| Haptic | `SettingsScope.maybeOf(context)?.haptic()` before the command | same |

- **Order is Approve-left, Reject-right**, matching reading order and the shipped card.
- **Neither action gets an arm-then-confirm step.** `EmergencyStrip` uses arm-then-confirm
  because Blackout and Clear change what the audience sees. Approve only stages to *Preview*,
  and Reject only drops a suggestion — **neither touches the audience output**, so a confirm
  step would cost a tap per detection during a service and buy no safety. Stated explicitly so
  it is not "hardened" in later by analogy.
- The existing vertical padding of 10 produced ≈40 dp buttons — below both the 48 dp bar
  (MOBILE-DESIGN-CLEANUP §1) and the 44 pt bar (DESIGN-2.0-HANDOFF §6). `minimumSize` fixes it.

### 7.6 Emergency strip — required, not optional

**The route must render `EmergencyStrip(live: live)` pinned above its bottom edge, under the
same role gate `ControllerView` applies** (`live.can(Capability.blackout) || live.can(Capability.clearLive)`).

UX-CANONICAL §3 makes this a testable UI invariant, not a preference:

> "the **emergency controls remain visible and operable at all times** ("always-on chrome" — an
> on-screen Blackout and Clear affordance is never occluded)… This 'always-on emergency chrome'
> is a testable UI invariant (present + operable in every live state)."

A pushed full-screen route occludes `ControllerView`'s strip. Without its own copy, this feature
creates the first screen in the app where an operator cannot black out the audience — and it is
a screen they may sit on for a whole sermon. **This is the highest-severity item in the spec.**

### 7.7 Footnote

Last child of the scroll list, `padding: fromLTRB(4, 8, 4, 4)`, 11 / `textMuted`:

> `Approving stages the verse in Preview. It does not go on air.`

FR-115 is a promise to the *operator* as much as to the audience. An operator who reads
"Approve" as "display" will approve and then wait for something that never happens. It is a
list child rather than a persistent footer so it costs no vertical space when scrolled past.

---

## 8. State matrix

Every state, its trigger, what renders, and how it ends.

| # | State | Trigger | Banner | Badge | Route | Exit |
|---|---|---|---|---|---|---|
| **S1** | **Zero detections** | `detections.isEmpty` | **Absent** (not empty — removed from the tree, so it reserves no space) | Absent | Not reachable | A detection arrives → S2 |
| **S2** | **One detection** | `length == 1` | `⚠ 1 verse needs approval ›` | `1` | 1 card | Approve / Reject → S1; another arrives → S3 |
| **S3** | **Many (2–99)** | `2 ≤ length ≤ 99` | `⚠ N verses need approval ›`, **same height as S2** | `N` | N cards, scrolls | — |
| **S4** | **Very many (> 99)** | `length > 99` | `⚠ 137 verses need approval ›` (banner is full-width; no cap needed) | `99+` | 137 cards, scrolls | — |
| **S5** | **Long reference** | e.g. `1 Thessalonians 5:16-18 · NASB95` | n/a | n/a | Reference wraps to 2 lines then ellipsises; the confidence badge keeps its intrinsic width and is never squeezed out | — |
| **S6** | **Long verse text** | any verse > 2 lines | n/a | n/a | Ellipsised at exactly 2 lines. **The card never grows to fit the verse** — that is the original bug in miniature | — |
| **S7** | **Narrow phone** | 320 dp logical width | Label ellipsises, count and both icons remain | Unchanged | Cards fill width; buttons may stack (§10.2) | — |
| **S8** | **Drained while open** | Host clears the last detection while the route is on top | Disappears from the tab underneath | Disappears | **"All caught up" empty state. The route does NOT pop.** Title loses its count pill | Operator taps back or `Back to Scripture`; or a new detection arrives → S9 |
| **S9** | **Refilled while open** | A detection arrives while S8 is showing | Reappears | Reappears | Empty state is replaced by the list. No animation, no scroll jump — the list starts at offset 0 | — |
| **S10** | **Revoked while open** | `live.revoked` becomes true | n/a | n/a | **Route pops immediately**, revealing `AccessRemovedScreen` | Terminal — user re-pairs |
| **S11** | **Capability lost while open** | `!live.can(Capability.searchScripture)` after a role change on reconnect | Gone with the tab | Gone with the tab | **Route pops immediately** | Returns to whichever tab is now selected |
| **S12** | **View-only / no-scripture role** | `Viewer`, `unknown` | Never rendered — `tab_scope` hides the whole Scripture tab | Never rendered | Unreachable. Belt-and-braces: if entered, render the tab's existing muted notice and pop on the next frame | — |
| **S13** | **Malformed detection** | `reference.isEmpty` | Counted normally | Counted normally | Reference renders as `Unknown reference` in `textMuted` italic; Approve/Reject still enabled — the **host** is authoritative about what `id` means | — |
| **S14** | **Reconnecting / syncing** | `live.syncing` | Rendered and **tappable** | Rendered (stale count) | Warn banner at top; **Approve/Reject disabled** at 0.4 opacity; list keeps showing the last snapshot | `syncing` clears → controls re-enable |
| **S15** | **Denied / host error** | `live.error != null` | Unchanged | Unchanged | Red dismissible banner, identical copy and behaviour to `ControllerView`'s | Tap to dismiss |
| **S16** | **Blackout active** | `live.blackout` | Unchanged | Unchanged | Unchanged; the route's `EmergencyStrip` shows `■ UN-BLACKOUT` and un-blackout stays **one tap** | — |

### 8.1 Why S8 does not pop — and S10/S11 do

S8 is the host finishing work the operator had queued. Popping there yanks navigation out from
under a thumb that is already descending on the next Approve; the tap lands on whatever the
Scripture tab has at those coordinates — plausibly a verse row, whose **double-tap sends a verse
live**. Staying put costs one deliberate back tap and removes that entire failure mode.

S10 and S11 are different in kind: the operator no longer has the right to be there. And there
is a concrete mechanism, not just a principle — `ControllerView` swaps its own body for
`AccessRemovedScreen` when `live.revoked`, but a **pushed route sits above `ControllerView` in
the navigator stack**, so that screen renders *underneath* and the operator is left staring at a
dead detections list. The pop is what makes the revoke visible.

### 8.2 Pop implementation rules

- Fire from the `ListenableBuilder`'s listener path, guarded by `mounted` and a one-shot
  `_popped` bool, so a stream of notifications cannot pop twice.
- Guard on `ModalRoute.of(context)?.isCurrent == true`. If something else is above (a dialog,
  the license page), do not pop blind — set the flag and pop when the route becomes current
  again. Popping the wrong route is worse than popping late.
- Never pop on `syncing` or `reconnecting`. A dropped link is temporary; disable, don't navigate.

---

## 9. Responsive behaviour

| Class | Width | Behaviour |
|---|---|---|
| compact | < 600 dp | Full-bleed within the 14 dp gutter |
| medium | 600–839 dp | `ResponsiveBody` caps content at 560 dp and centres it; gutters are `bgBase` |
| expanded | ≥ 840 dp | as medium |

- The `EmergencyStrip` on the route is wrapped in `ResponsiveBody` too, exactly as
  `ControllerView` does — otherwise Blackout/Clear become giant on a tablet.
- Landscape: same rules. The route's list already scrolls, so a short viewport is safe.
- The AppBar spans full width; only the body is constrained. Matches the existing app.

---

## 10. Text scaling — a first-class requirement

The bug being fixed is an unbounded-height child. Large system text is the same failure with a
different multiplier, and the two compose. Both are specified as hard bars.

### 10.1 The bar

**No layout overflow, no clipped glyph and no unreachable control at `textScaler` 3.0 on a
320 × 568 logical viewport** — the narrowest realistic phone at iOS AX5. Verify at **1.0, 1.3,
2.0 and 3.0**.

### 10.2 The rules that get us there

1. **Nothing in this feature may be an unbounded, non-flexing child of a `Column`.** The route's
   body is a `ListView`; the banner is bounded by content; the empty state is inside a
   `SingleChildScrollView`. This is the invariant, stated once, that closes the class of bug.
2. **Banner:** `ConstrainedBox(minHeight: 48)` + single-line ellipsised label. It grows with the
   scale and never clips; it stays constant in N. The count is leading, so it is the last thing
   the ellipsis would ever eat.
3. **Action row stacking:** when `MediaQuery.textScalerOf(context).scale(1) >= 1.3`, stack
   Approve above Reject, each full-width and ≥ 48 dp, with a 10 dp gap. Below 1.3 keep them
   side by side. A hard threshold rather than a `LayoutBuilder` guess so QA can test an exact
   boundary: **1.29 → side by side, 1.30 → stacked.**
4. **Route title:** the count pill lives outside the `Flexible`, so the number is never the text
   that truncates (§7.3).
5. **Do not clamp the text scale anywhere in this feature.** Capping `textScaler` to "fix"
   layout defeats the OS accessibility setting the operator deliberately turned on.
6. **Empty state** is inside a `SingleChildScrollView` so its icon + two lines + button still
   reach at 3.0 on a short landscape viewport.

---

## 11. Accessibility (NFR-026)

### 11.1 Semantic labels

| Element | Semantics |
|---|---|
| Banner | `Semantics(button: true, label: '4 verses need approval', hint: 'Opens the approval list', excludeSemantics: true)`. `excludeSemantics` keeps the decorative icons out of the announcement — the precedent is `_NavBtn` and `_EmgButton` in the shipped app. Singular form at N = 1. |
| Approve | `Semantics(button: true, label: 'Approve Romans 8:28')` — **include the reference**. A screen-reader user moving down a list of identical "Approve" buttons has no way to tell which verse they are on. |
| Reject | `Semantics(button: true, label: 'Reject Romans 8:28')` |
| Approve/Reject while `syncing` | `enabled: false`, label `'Approve Romans 8:28, unavailable while reconnecting'` — verbatim the pattern `_EmgButton` already uses |
| Confidence badge | `Semantics(label: '94 percent match')`. `'94% MATCH'` is read as "ninety-four percent match" by TalkBack but the all-caps `MATCH` is spelled out letter-by-letter by some VoiceOver voices. |
| Card container | `Semantics(container: true)` so each detection is one swipe stop, not five |
| Empty state | Heading is a focusable `Semantics(header: true)` and **receives focus when the list drains** — otherwise a screen-reader user hears nothing at all when the queue empties |
| Route | `Semantics(namesRoute: true)` on the title so the screen is announced on push |

### 11.2 The badge announcement

`NavigationDestination` has no separate badge-semantics slot: assistive tech reads the
destination `label`, and surfaces `tooltip` as the accessibility hint on Android and as the
hint on iOS. So:

- Keep `label: 'Scripture'` — short, so the bar does not wrap at large scale.
- Put the count in the `tooltip`, which is where it will actually be announced:

  | Role state | Tooltip |
  |---|---|
  | no detections | `Scripture` |
  | N pending | `Scripture — 4 need approval` |
  | view-only, no detections | `Scripture — view only` (unchanged from today) |
  | view-only + N pending | `Scripture — view only — 4 need approval` |

- **Platform variance here is real and cannot be proven by a widget test.** A widget test asserts
  the tooltip string; a **manual VoiceOver and TalkBack pass is a required verifier** (§15) and
  its result goes in the ticket. Do not mark this criterion done on the widget test alone.

### 11.3 Contrast

Every pair is measured in §4.3; the tightest is white-on-`previewFill` at **5.16 : 1** against a
4.5 bar. Warn-on-dark — the specific question the brief raised — is **9.28 : 1**.

### 11.4 Touch targets

≥ 48 × 48 dp for the banner, Approve, Reject, the back button, and `Back to Scripture`. The tab
badge is decorative and not itself a target; its parent destination is already 48 dp+.

### 11.5 Focus and reading order

Banner → translation picker → search field → verse list (tab). On the route: back button →
card 1 reference → card 1 confidence → card 1 verse → Approve → Reject → card 2 … → footnote →
Blackout → Clear All. Emergency controls last in reading order but always present, matching
`ControllerView`.

### 11.6 Never colour alone (WCAG 1.4.1)

The banner carries the word "approval" and a warning icon, not just amber. The count badge
carries a number, not just a dot. The empty state carries "All caught up", not just a green
tick. Consistent with how LIVE and PREVIEW are handled everywhere else in the app.

---

## 12. Motion and haptics

### 12.1 The banner → route transition

**Use a plain `MaterialPageRoute` and nothing else.**

`lib/main.dart:53-71` already installs a `pageTransitionsTheme` that swaps in a
zero-duration builder whenever `MediaQuery.disableAnimations || settings.reduceMotion`. A
`MaterialPageRoute` inherits that automatically, so the platform transition and the
reduced-motion behaviour both come for free:

- Android: the platform's shared-axis page transition, ~300 ms
- iOS: slide-from-right with the edge-swipe-back gesture, ~350 ms
- Reduced motion (OS setting **or** the in-app Config toggle): instant, no transition

**A hand-rolled `PageRouteBuilder` with a custom `transitionsBuilder` bypasses
`pageTransitionsTheme` entirely and would silently break reduced motion** — an accessibility
regression with no visible symptom for anyone who does not use the setting. Do not write one.
Do not lengthen the duration "so the transition reads better": this is a control surface used
under time pressure.

### 12.2 Banner appearance

- **No expand/fade-in animation** on the 0 → 1 transition. The banner is the first child of the
  tab column, so it displaces everything below it by ≈48 dp. An animated expand spreads that
  displacement across 200 ms and *doubles* the window in which a tap target is moving under a
  descending thumb. An instant insert makes the shift atomic between frames.
- The improvement over today is structural and worth stating: **the old card shifted the layout
  on every single detection arrival, because its height grew with N. The new banner shifts the
  layout only once, on the 0 → 1 transition — 5 → 6 detections moves nothing.** See §14.2.

### 12.3 Route dismissal

Default pop. On the programmatic pop of S10/S11 the transition still runs, so the operator sees
`AccessRemovedScreen` slide in rather than teleport — which reads as a system event, not a crash.

### 12.4 The count badge does not animate

No scale-in, no pulse, no bounce. A badge pulsing in an operator's peripheral vision for the
length of a sermon is a distraction, it would need its own reduced-motion branch, and it
communicates nothing the number does not.

### 12.5 Haptics

`SettingsScope.maybeOf(context)?.haptic()` on the banner tap, on Approve and on Reject. The
`maybeOf` form (not `of`) matters — widget tests pump these views without a `SettingsScope`
ancestor, and `of` would throw. This is the pattern `EmergencyStrip` already uses.

---

## 13. Copy

| Surface | String |
|---|---|
| Banner, N = 1 | `1 verse needs approval` |
| Banner, N ≥ 2 | `N verses need approval` |
| Route title | `Needs your approval` + count pill |
| Approve | `Approve` |
| Reject | `Reject` |
| Confidence | `94% MATCH` |
| Reference fallback | `Unknown reference` |
| Footnote | `Approving stages the verse in Preview. It does not go on air.` |
| Empty heading | `All caught up` |
| Empty body | `No verses are waiting for approval.` |
| Empty action | `Back to Scripture` |
| Reconnecting | `Reconnecting to the host… your taps won't be sent` *(verbatim from `ControllerView`)* |
| Syncing | `Syncing live state…` *(verbatim)* |

Voice check against DESIGN-2.0-HANDOFF §7: reassurance under failure, consequences named, no
softening. "It does not go on air" states the consequence plainly rather than implying it.

---

## 14. Live-service speed and safety callouts

Ordered by severity. Each is a thing that could make an operator slower or less safe mid-service.

### 14.1 The route hides the always-on emergency chrome — **blocking**

A pushed full-screen route occludes `ControllerView`'s `EmergencyStrip`. UX-CANONICAL §3 makes
"present and operable in every live state" a testable invariant. An operator sitting on the
approval queue during a sermon would have no Blackout and no Clear.
**Mitigation (required, §7.6): the route renders its own `EmergencyStrip` under the same role
gate.** Ship-blocking if absent.

### 14.2 Approval now costs a navigation — **accepted, mitigated**

Before: one tap to approve, inline. After: banner → route → Approve → back. For the common
single-detection case this is a net slowdown of two taps.

Accepted because the alternative is a tab that breaks outright. Mitigations:
- The banner is a full-width, low-precision target — no aiming required.
- After the last card is cleared the route lands on "All caught up" with a prominent
  `Back to Scripture` button, so the exit is one large tap rather than a small back chevron.
- **Do not "optimise" this by rendering the card inline when N == 1.** That re-introduces a
  Column child whose height depends on host state — the exact bug — and it splits the mental
  model so the operator cannot predict where approval lives. Written down here so it is not
  proposed later as an obvious win.

Offsetting gain: **the layout now shifts once (0 → 1), not on every arrival.** With the old card
the search field and verse list moved every time a detection landed; a mis-tap on a moving verse
row stages the wrong verse, and a double-tap across a shift is genuinely dangerous. That whole
category is now confined to a single 0 → 1 transition.

### 14.3 The route also hides the connection banner — **blocking**

`live.syncing` and `live.error` are rendered by `ControllerView.body`, which the route covers.
`live.act()` returns `failed` while `_reconnecting` **without surfacing anything**, so an
operator on the route during a blip would tap Approve, see nothing happen, and tap again.
**Mitigation (required, §7.3 + S14): the route renders the same banners and disables
Approve/Reject while `syncing`, with the reason in the semantic label.** Silent failure is worse
than a greyed button.

### 14.4 The route can mask a role downgrade or revoke — **blocking**

Mechanism in §8.1. Without the pop rule, an operator whose device was revoked mid-service keeps
tapping a dead list while `AccessRemovedScreen` renders invisibly beneath. **Mitigation
(required, §8.2).**

### 14.5 Approve is not "go live" — **copy risk**

FR-115 means Approve stages to Preview only. An operator who reads it as "display" will approve
and wait. **Mitigation: the §7.7 footnote.** Never label the button "Display", "Show" or "Send".

### 14.6 The badge is a stale number for up to one second — **accepted**

The count comes from the 1 s poll, so it can lag reality by a poll interval, and Approve on the
route can briefly race a host-side clear. Accepted: the host is authoritative, an
already-cleared `detection_id` is refused server-side and surfaces through the existing denial
banner, and adding an optimistic local removal would let the client disagree with the host —
the thing the whole architecture is built to avoid. **Do not add optimistic removal.**

### 14.7 The banner competes with the search field for the operator's eye — **watch**

The Scripture tab's primary job during a service is manual lookup. The banner sits above the
search field in warn amber, which is the loudest thing on the tab. That is correct while
detections are pending and invisible when they are not, so the cost is bounded — but if
operators report the amber pulling focus during manual lookup, the fix is to move the banner
below the search row, not to soften the tone. Flagged for post-release observation, not a
pre-release change.

---

## 15. Verification checklist

Maps 1:1 onto the ClickUp acceptance criteria plus the design-specific bars.

**Widget tests** (`test/views/`):

1. 20 detections, 320 × 568 surface → Scripture tab renders, **zero overflow**, the reference
   field is present and tappable *(AC 1)*
2. Banner text is `1 verse needs approval` at N = 1 and `4 verses need approval` at N = 4
3. Banner height is **identical** at N = 1 and N = 20 — the count-independence invariant
4. Tapping the banner pushes route `'detections'` and all N references are listed *(AC 2)*
5. Approve sends `approve_detection` with the right `detection_id`; Reject sends
   `dismiss_detection` *(AC 3)* — port the assertions from the existing
   `test/views/scripture_approval_test.dart`, which will otherwise fail once the inline card is
   deleted
6. Scripture destination shows the count badge at N > 0 and no badge at N = 0 *(AC 4)*
7. **Destination builder called directly with `viewOnly: true` + N > 0 → both markers present**
   (§6.2 — unreachable through any role)
8. Draining to zero while the route is open → "All caught up", route still on the stack *(AC 5)*
9. `live.revoked` → route pops *(AC 6)*
10. `searchScripture` lost → route pops *(AC 6)*
11. `live.syncing` → Approve/Reject disabled and the reconnect banner is rendered on the route
12. Route renders an `EmergencyStrip` for a role holding `blackout` or `clearLive` (§7.6)
13. `textScaler` 1.29 → buttons side by side; 1.30 → stacked (§10.2)
14. `textScaler` 3.0 on 320 × 568 with 20 detections → no overflow on tab **or** route (§10.1)
15. `confidence == null` → no badge; `reference == ''` → `Unknown reference`
16. 800 dp-wide surface → route body is capped at 560 dp and centred (§9)

**Manual, logged in the ticket:**

17. VoiceOver (iOS) and TalkBack (Android): the badge count is announced when focusing the
    Scripture tab; Approve/Reject announce their verse reference; the empty state is announced
    when the queue drains (§11.2 — a widget test cannot prove this)
18. Reduced motion on (OS setting and the in-app Config toggle) → the push is instant
19. Real-device sanity at the largest OS font size

**Gate:** `make mobile-test` (flutter analyze + test) green *(AC 7)*.

---

## 16. Deferred, with reasons

Honest "later", never omitted or faked:

| Item | Why deferred | Where it goes |
|---|---|---|
| Low-confidence amber treatment + alternative matches + Edit (DESIGN-2.0-HANDOFF §5.5 state 4) | The wire carries a single `confidence` int and no alternatives list; a threshold would be invented on the client | Needs a host-side threshold + alternatives in `DetectionView`; new ticket under `86ajp086b` |
| Detection history / re-stage (§5.5 state 8) | No history in `OperatorStateView`; desktop-only today | Follow-up |
| Transcript provenance (`sourceSegment` → "heard in: …") | Would help the operator judge a match, but the segment text is not joined to the detection on the wire | Follow-up |
| Bulk "Reject all" | Tempting for a runaway queue, but it is one tap from discarding a verse the preacher is about to read. Needs product input on undo | `/product-manager` |
| Design 2.0 re-skin of this surface | Coordinated four-surface token migration + WCAG re-audit; §4.1 | DESIGN-2.0-HANDOFF §9.1, owner decision |

---

## 17. Open questions

1. **Queue cap.** Nothing bounds `detections` on the client. The host presumably caps it, but
   this repository's bounded-memory rule (CLAUDE.md) says new buffering code gets a
   bounded-memory test. If the host can stream unboundedly, the badge and the list want a
   documented ceiling. Owner: `/backend-engineer` on the desktop detection pipeline.
2. **Ordering.** This spec renders host order. Newest-first would put the verse the preacher
   just spoke at the top, which is what the operator wants under time pressure — but only the
   host knows the true order. Owner: `/product-manager`.
3. **Should the banner also appear on the Live tab?** The badge makes detections *visible* from
   Live, but acting on them still costs a tab switch plus a banner tap. Out of scope here;
   worth a product decision if operators ask. Owner: `/product-manager`.
