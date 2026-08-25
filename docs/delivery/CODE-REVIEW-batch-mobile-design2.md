# Code Review — Mobile "Design 2.0" re-skin, Batch A

- **Scope:** the Flutter controller (`implementation/mobile/selahcue_controller`) had never adopted Design 2.0 — the `d2*` token layer existed in `design_tokens.dart` but **zero views used it**; all 179 colour references still pointed at the Design 1.0 navy/blue palette. Batch A migrates the whole app onto `d2*`, introduces the shared component system, and locks the result against regression. Frames: `342:124` (base surfaces), `355:124` (role homes), `357:124` (enforcement states), `363:124` (navigation & config).
- **Design source:** `docs/design/MOBILE-2.0-SPEC.md` — written for this batch from the four frames, measured by pixel-sampling rather than eyeballed, with every value marked *measured* or *default*.
- **Deliberately out of scope (Batch B):** timer HH:MM:SS entry · Reset · "Send TIME UP to stage" · the three enforcement states · any role expansion.

## What shipped

Two new files carry the system: **`lib/models/selah_theme.dart`** (the `ThemeData` builder plus the `SelahSpace` / `SelahRadius` / `SelahType` scales) and **`lib/views/widgets/primitives.dart`** (`SelahTone` + `SelahToneStyle`, `StatusBadge`, `KindBadge`, `SectionLabel`, `SelahCard`, `SelahListRow`, `SelahButton`, `SelahInput`, `SelahToggle`, `SelahSegmentedControl`). Every view — pairing, Live, Plan, Scripture, Timer, Detections, the app shell, the ⓘ Config sheet, Access-removed — moved onto them. Scripture references and verse numbers now take the gold treatment, which they never had.

## The fill→ink inversion

Design 2.0 replaces white-on-saturated-fill status chips with **bright ink on a same-hue soft tint plus a border**. `StatusBadge({text, color})` could not express a triple, so it became `StatusBadge({text, tone, semanticLabel})` over a 7-value `SelahTone` table. This is the batch's one breaking API change; all call sites and the widget tests that asserted the old colours moved with it.

## Where the implementation deliberately diverges from the frames

The spec pass measured four pairings the frames draw that **fail WCAG AA**. Each is built as the accessible fix, not as drawn:

| Element | As drawn | Shipped |
|---|---|---|
| White on the violet gradient's light stop | 3.78:1 | flat `d2Primary`, **4.72:1** |
| White on the GO LIVE green gradient | 1.93:1 | `d2PreviewSoft` ink, **8.50:1** |
| White on solid `d2Live` (armed alarm) | 3.27:1 | `d2LiveSoft` ink, **5.31:1** |
| White on `d2Preview` (Approve) | 3.15:1 | `success` variant with dark ink |

`d2TextMuted` was the subtler trap: it reads as the natural heir to the old `textMuted`, but measures **3.45–4.08:1** and fails AA-normal on every Design 2.0 surface. The correct mapping is `d2TextSecondary`; `d2TextMuted` survives in exactly one place, as a non-text decorative dot.

Two colours the frames use are **not in the palette** (`d2InfoBorder`, and the `#231B48` on-air wash). They are derived in `selah_theme.dart` rather than added to `design_tokens.dart`, because that file's `d2<Camel> = Color(0xFF<HEX>)` declarations are **grepped textually from Rust** by `selahcue-present/tests/test_tokens.rs::design2_palette_is_pinned_across_surfaces` — adding or reformatting members there breaks a Rust test with no visible connection to the edited file.

## Regression guards added

- `test/models/design_tokens_test.dart` — pins all 25 `d2*` values against the cross-surface manifest, asserts one-meaning-per-colour-family, and re-runs the AA audit for the inverted ink-on-tint pairings (the old audit only covered white-on-fill). It also asserts `d2TextMuted` **fails** AA, so a future palette change that lifts it above the line fails loudly instead of silently legitimising misuse.
- `test/views/token_drift_test.dart` — scans `lib/views/**` and fails on any reference to the 12 legacy palette members, with a budget of 1 for the sanctioned decorative `d2TextMuted`. A colour regression is invisible in a diff and invisible in a passing widget test; it is only visible on a phone. Hence a source-level assertion.

## Test changes — intent preserved, not re-baselined

Eight widget tests failed against the new system. None were relaxed:

| Test | Cause | Change |
|---|---|---|
| `live_tab_test` ×2 | monitor chips are now `PREVIEW` / `LIVE` | finder text updated; the layout assertions (same-row vs stacked) untouched |
| `transport_gate_test` ×2 | `OutlinedButton` → `SelahButton`; preset labels lost their `⏱` | widget type + labels updated |
| `detections_overflow_test` ×4 | `warnFill`→`d2Warn`, `previewInk`→`d2Preview`, `textMuted`→`d2TextSecondary`; `FilledButton`/`OutlinedButton`→`SelahButton` | tokens and widget types updated |

One test change is a genuine improvement rather than a port. `timer controls are visibly disabled while syncing` matched the bare text `5:00`, which after the label change was ambiguous — the running-timer fixture renders `5:00` in both the 68px readout and the preset button. Scoping the finder to `find.widgetWithText(SelahButton, ...)` matches the assertion's stated intent ("`$label` stays on screen") and is immune to the readout coinciding with a preset.

## Verification

```
make mobile-test  →  flutter analyze: No issues found
                     flutter test:    All tests passed  (140 → 143 with the new guards)
cargo test -p selahcue-present --test test_tokens  →  18 passed; 0 failed
```

The Rust run matters here specifically: it proves the cross-surface pinning survived a batch that touched the mobile mirror's every consumer.

## Open, carried to Batch B

1. **The frames still draw the four failing pairings.** Code diverges from Figma until someone pushes the fixes back — otherwise the next person to implement from the frames reintroduces them.
2. **Two Figma tab rows are wrong and the code is right** — Observer's Scripture/Timer are inverted versus `visibleTabsFor()`. `tab_scope.dart` needs no change.
3. **Role naming** — the app says "Producer", the RBAC matrix says "Production Operator". Recommendation is to canonicalise on "Producer": docs and five Figma text layers change, no code.
4. **Batch B has a Rust dependency** — `Reset` and "Send TIME UP to stage" have no wire commands, and `timeUp` is host-computed state rather than something a phone can push (`selahcue-lan/src/protocol.rs`). Those two controls need new protocol variants plus the cross-language fixture update before the timer can ship complete.
5. **Three of the six designed role homes are not buildable** on the 4-role backend, blocked by missing wire commands rather than permissions alone (`86ajxuf81` / `86ajxufbg`).
