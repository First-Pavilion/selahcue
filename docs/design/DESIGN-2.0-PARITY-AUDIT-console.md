# Design 2.0 — Operator Console parity audit

**Scope:** the Tauri operator console (`implementation/desktop/crates/selahcue-operator/dist/`) against
its Design 2.0 Figma frames in file `SYQn5hFY8YVQKm3c6rw0eJ` (page `0:1`).
**Type:** audit + spec. No implementation file was modified by this document's author.
**Date:** 2026-08-23. **Author:** Uma (UI/UX).

## How to read this

- Every gap carries a unique **`CON-###`** id. The frontend engineer and QA reference these ids.
- **Every "Implemented" cell cites `file:line` and quotes the real value.** Where the value could not be
  found in the tree it says `NOT FOUND` — nothing is inferred.
- Where Figma does not specify something it says `unspecified` and the question is raised in §9.
- Verdicts:
  | Verdict | Meaning |
  |---|---|
  | `MATCH` | Implementation equals the frame within 0 px / exact hex. |
  | `DRIFT` | Both exist, values differ. |
  | `MISSING` | The frame draws it; the console does not have it. |
  | `EXTRA` | The console has it; no audited frame draws it. |
  | `UNSPECIFIED` | The console has it and it is needed, but no frame defines its appearance. |
  | `INTENTIONAL-DEVIATION` | The code deliberately and **permanently** departs from the frame because the frame fails NFR-020. **Not a gap. Never close it toward the frame.** The frame is the thing that is wrong. |
  | `A11Y-CONFLICT` | Figma and the shipped code disagree on an ink/opacity choice where the frame is the weaker option. Read §8 before touching. |
  | `A11Y-DEFECT` | Both Figma and the code fail NFR-020. A real bug in the product today. |
- Severity: **blocker** (ships wrong / fails an NFR), **major** (visibly off-design or a missing state),
  **minor** (≤4 px, letter-spacing, a padding of 1).

### Sources of truth used

| Thing | Source |
|---|---|
| Frame geometry / colour | live Figma file, via `get_design_context` per node (node ids cited inline) |
| Token values | `implementation/desktop/crates/selahcue-present/src/tokens.rs` (`design2`), mirrored in `dist/app.css:28-56` |
| Contrast bar | `docs/product/prds/SelahCue-PRD.md:396` — NFR-020: **≥4.5:1 normal text, ≥3:1 large text/UI** |
| Token contrast constraints | `implementation/desktop/crates/selahcue-present/tests/test_tokens.rs:536` (text-muted = AA-large, label-only) and `:585-592` (white on primary-hover = AA-large, must not carry small white body text) |
| Cross-platform precedent | `docs/design/MOBILE-2.0-SPEC.md` §2.5, §6, §7-Q2 |

### Contents

| § | Section |
|---|---|
| **1** | Summary |
| **A–G** | Per-frame audit — the seven frames, in the order given: `312:124` · `336:124` · `430:124` · `332:124` · `563:201` · `462:124` · `346:124` |
| **8** | Accessibility — NFR-020 findings |
| **9** | Open questions for the owner |
| **10** | Suggested build order |
| **Appendix A** | Every `var(--sc-text-muted)` call site, classified |

### Two structural facts found before any component was compared

1. **The Figma file binds no variables.** `get_variable_defs` on the flagship `312:124` returns `{}` —
   every colour in every audited frame is a raw hex literal, not a bound token. The `--sc-*` token layer
   exists only in code (`dist/app.css:28`, `tokens.rs`). Design-side token drift is therefore
   undetectable from Figma; it can only be caught by an audit like this one. See `CON-001`.
2. **`docs/design/DESIGN-2.0-HANDOFF.md` is stale and contradicts the file.** It is dated 2026-08-01 and
   its node map omits `430:124`, `332:124`, `563:201`, `462:124` and `346:124` — five of the seven frames
   audited here. Where they disagree the live file wins. See `CON-002`.

---

# 1. Summary

**270 components audited** across the seven frames — every button, label, badge, icon, input, tab, chip,
empty state and error state each frame draws, plus every console element the frames do not draw.
**179 numbered gaps** (`CON-001` … `CON-179`).

| Verdict | Count |
|---|---:|
| `MATCH` | 96 |
| `DRIFT` | 63 |
| `MISSING` (frame draws it, console does not) | 37 |
| `EXTRA` (console has it, no frame draws it) | 17 |
| `UNSPECIFIED` (console needs it, no frame defines it) | 11 |
| `A11Y-DEFECT` (both sides fail NFR-020) | 25 |
| `INTENTIONAL-DEVIATION` (code deliberately, permanently departs — **not** a gap) | 9 |
| `A11Y-CONFLICT` | 1 |

| Severity | Count |
|---|---:|
| blocker | 11 |
| major | 72 |
| minor | 77 |

Open questions for the owner: **12** (§9).

## The five things worth knowing

**1. The colour re-skin is done; the geometry is close; the *states* are not built.**
Of 63 `DRIFT` findings, 46 are ≤4 px or one font step. Only one is visually significant
(`CON-042`: GO LIVE renders 144 px narrower than designed because `.golive-row button { flex: 1 }`
catches Prev/Next too). The real gap is elsewhere: **37 `MISSING` findings, and 34 of them are states**
— what the console shows when something is happening or has gone wrong.

**2. Two whole state families are unbuilt.**
- Frame D (`332:124`) specifies **nine** detection states. **Seven are entirely absent** — no
  listening/analysing, no alternatives picker, no on-air card, no duplicate suppression, no history, no
  provider-unavailable. Today a dead detector and a silent room render identically.
- Frame G (`346:124`) specifies **six** recovery states. **Five are absent** — no network-lost banner,
  no signal-lost/held-last-frame explanation, no auto-reconnect, no missing-media fallback, no crash
  recovery. The frame's own subtitle is "reliability is the product's first promise".

**3. The implementation is *ahead* of the design file on accessibility — in nine places.**
`app.css:4470-4545` is a documented review block that deliberately overrides the frames because the
frames fail NFR-020: GO LIVE ships dark ink (**8.70 : 1**, the console frame agrees), BLACKOUT ships
`#a3283a` (**7.19 : 1**) instead of white-on-`#ff4d4d` (3.27 : 1), the primary gradient ships
`#6e5cf0 → #5a48d0` (**4.72 → 6.42 : 1**) instead of `#7e6eff` (3.78 : 1). **These are not gaps. Closing
them toward the frames would ship AA failures.** See §8.1 — that list also covers `.scr-card-meta` and
the narrowed `screen-disabled` dimming.

**4. One live AA blocker, in shipped code, that nobody has caught.**
`CON-046` — the **"⏎ Enter"** hint chip on GO LIVE is white on a translucent-white chip over the bright
green gradient: **1.72 : 1**. It fails AA-normal *and* AA-large, so no size argument rescues it. Figma
draws the same thing at 1.74 : 1. It is a four-line CSS fix (`app.css:3901-3906`) and it is the single
highest-value change in this document.

**5. `--sc-text-muted` is a pre-existing, shipped AA failure at 88 sites.**
`#6b7383` measures **3.45 – 4.12 : 1** on the four neutral grounds — AA-large only, as
`test_tokens.rs:536` records. A triage already ran and promoted six selectors, on the rule
"supplementary micro-text stays muted". **WCAG 1.4.3 has no "supplementary" exemption** — only
*incidental* (decoration, invisible, part of a picture) and logotypes. Appendix A classifies all 105
call sites: **88 violations, 10 incidental, 1 AA-large, 6 already dead.** §8.4.1 proposes
`--sc-text-tertiary #828b9c` (4.80 – 5.72 : 1) rather than a blanket promotion, which would flatten the
ink hierarchy the design depends on. That is a four-surface lockstep change and Q9.

## Two things the audit could not settle

**The Figma file contradicts itself in seven places** — the right-panel tab bar is drawn three different
ways (`443:124`, `431:127`, `563:125`); the detection card is drawn two ways (`332:200`, `432:124`); the
emergency footer is drawn two ways (`312:151`, `337:184`). The implementation follows a different frame
each time, and is internally consistent by accident rather than decision. Q2 resolves all seven at once.

**Six colours in the frames are not `--sc-*` tokens**, including three *different* "on-air wash"
gradients across desktop console (`#0f1d3a`), desktop recovery (`#241c4a`) and mobile (`#231B48`). Q6.

---

# Frame A — `312:124` "SelahCue · Operator Console (Design 2.0)" · 1760 × 1000 (flagship)

All paths below are relative to `implementation/desktop/crates/selahcue-operator/dist/`.

## A.0 Page shell

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Frame size | 1760 × 1000 | `app.css:336-338` `body { min-width: 900px; overflow-x: auto }` — fluid, not fixed | MATCH (intent) | — |
| — | 3-column grid | left `x16 w380`, center `x412 w936`, right `x1364 w380`; gutters 16/16, outer pad 16 | `app.css:304` `grid-template-columns: minmax(300px, 380px) minmax(0, 1fr) minmax(320px, 380px)`; `app.css:305` `gap: 16px`; `app.css:306` `padding: 16px` | MATCH (resolves to exactly 380/936/380 at 1760) | — |
| `CON-003` | Inter-panel vertical gap inside a column | 14 px — every column: `320:124` left-col `gap-[14px]`, `320:200` program `gap-[14px]`, `320:201` right `gap-[14px]` | `app.css:2533-2534` `.zone { … gap: 12px }` | DRIFT (12 vs 14) | minor |
| `CON-004` | Body background | `320:200` / `320:201` `bg-[#0b0d12]` | `app.css:69` `body { background: var(--bg) }` → `--bg: #0b0d12` (`app.css:7`) | MATCH | — |

## A.1 Topbar — `312:125`

Figma container: `bg-[#14161d]`, `border-[#262a34]`, `px-[20px]`, h 64, three groups `justify-between`.

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Bar shell | h 64, `bg #14161d`, border `#262a34`, `px 20` | `app.css:80-89` `header { height: 64px; padding: 0 20px; border-bottom: 1px solid var(--sc-border); background: var(--sc-surface); display:flex; align-items:center; gap:12px }` | MATCH | — |
| — | Three-group distribution | `justify-between` | `app.css:4525-4530` `header { justify-content: space-between }` + `.topbar-transport { margin-left: 0 }` (overrides `app.css:144` `margin-left:auto`) | MATCH | — |
| — | Left group gap | `312:126` `gap-[14px]` | `app.css:93` `.topbar-left { … gap: 14px }` | MATCH | — |
| `CON-005` | Logo pill geometry | `312:127` `w-[174px]`, `pl-[8px] pr-[12px] py-[7px]`, `gap-[9px]`, `rounded-[10px]`, `bg #1c1f28`, border `#262a34` → **58 px tall** | `app.css:99-111` `.logo-pill { gap: 9px; background: var(--sc-elevated); border: 1px solid var(--sc-border); border-radius: 10px; padding: 2px 10px 2px 8px; font-weight: 700; font-size: 14px }` — no width; vertical padding 2 not 7; right padding 10 not 12 | DRIFT (pill renders ≈46 px tall vs 58; 12 px shorter than every other topbar control) | major |
| `CON-006` | Logo mark | `312:128` `size-[44px]`, `rounded-[8px]`; the artwork `380:125` is 73 × 73 bleeding out at `(-13,-17)` (i.e. drawn oversized and clipped) | `app.css:117-123` `.logo-mark { width: 40px; height: 40px; object-fit: contain }`; markup `index.html:20` `<img class="logo-mark" src="selahcue-logo.png">` | DRIFT (40 vs 44; no clip-bleed treatment) | minor |
| — | Wordmark "SelahCue" | `312:129` 14 px Bold `#f4f6fb` | `app.css:107-108` `font-weight: 700; font-size: 14px` on `.logo-pill`, colour `var(--sc-text)` (`app.css:104`) | MATCH | — |
| — | Caret ▾ | `312:130` 12 px Medium `#a7aebe` | `app.css:125-129` `.logo-caret { color: var(--sc-text-secondary); font-size: 12px; font-weight: 500 }` | MATCH | — |
| — | Divider | `312:131` 1 × 24, `#262a34` | `app.css:131-135` `.topbar-divider { width: 1px; height: 24px; background: var(--sc-border) }` | MATCH | — |
| — | Surface label "Live Console" | `312:132` 15 px SemiBold `#a7aebe` | `app.css:137-141` `.topbar-surface { color: var(--sc-text-secondary); font-size: 15px; font-weight: 600 }`; markup `index.html:64` | MATCH | — |
| — | Transport group gap | `312:133` `gap-[10px]` | `app.css:143-148` `.topbar-transport { display:flex; align-items:center; gap: 10px }` | MATCH | — |
| — | ◀ Previous | `312:134` `bg #1c1f28`, border `#262a34`, `rounded-10`, `px-14 py-9`; label `312:135` 13 px Medium `#a7aebe` | `app.css:150-159` `.tb-btn { background: var(--sc-elevated); border: 1px solid var(--sc-border); color: var(--sc-text-secondary); border-radius: 10px; padding: 9px 14px; font-size: 13px; font-weight: 500 }`; markup `index.html:70` | MATCH | — |
| — | Next ▶ | `312:136` same chrome, label `312:137` `#f4f6fb` | `app.css:166-168` `#top-next { color: var(--sc-text) }`; markup `index.html:71` | MATCH | — |
| `CON-007` | ● GO LIVE (topbar) | `312:138` `bg-gradient-to-r from-[#7e6eff] to-[#6e5cf0]`, `rounded-10`, `px-14 py-9`; label `312:139` **13 px** SemiBold **white** | `app.css:4505-4507` `.tb-golive, .timer-start { background: linear-gradient(90deg, var(--sc-primary), #5a48d0) }` — i.e. `#6e5cf0 → #5a48d0`, overriding `app.css:170-175` which held the Figma gradient | **INTENTIONAL-DEVIATION (permanent)** — white on `#7e6eff` = 3.78 : 1 (AA-large only, pinned at `test_tokens.rs:585-592`); the shipped gradient runs 4.72 : 1 → 6.42 : 1. See §8.1 | — |
| — | Blackout (topbar, idle) | `312:140` `bg #2a1416`, border `#5a2327`, `px-14 py-9`, `rounded-10`; label `312:141` 13 px Medium `#ff4d4d` | `app.css:182-186` `.tb-blackout { background: var(--sc-live-soft); border-color: var(--sc-live-border); color: var(--sc-live) }` | MATCH | — |
| `CON-008` | Blackout **engaged** state | `unspecified` — `312:124` draws only the idle state | `app.css:4497-4501` `.tb-blackout[aria-pressed="true"] { background: #a3283a; border-color: #a3283a; color: #fff }` (7.19:1) | UNSPECIFIED (impl is a11y-sound; the frame owes a state) | major |
| — | Status group gap | `312:142` `gap-[12px]` | `app.css:194-198` `.topbar-status { … gap: 12px }` | MATCH | — |
| — | Timer chip | `312:143` `bg #1c1f28`, border `#262a34`, `rounded-10`, `px-12 py-8`, `gap-8`; ⏱ `312:144` 13 px `#f2b84b`; value `312:145` 14 px SemiBold `#f4f6fb` | `app.css:200-224` `.tb-timer { … gap: 8px; background: var(--sc-elevated); border: 1px solid var(--sc-border); border-radius: 10px; padding: 8px 12px }`, `.tb-timer-ico { color: var(--sc-gold); font-size: 13px }`, `#top-timer-val { color: var(--sc-text); font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums }` | MATCH (exact) | — |
| — | Clock "10:32" | `312:146` 14 px Medium `#a7aebe` | `app.css:242-247` `#clock { color: var(--sc-text-secondary); font-variant-numeric: tabular-nums; font-weight: 500; font-size: 14px }` | MATCH | — |
| — | Connection pill "Connected" | `312:147` `bg #10231c`, border `#1c3a2e`, `rounded-10`, `px-14 py-9`, `gap-8`; dot `312:148` 8 px; label `312:149` 13 px Medium `#35c08a` | `app.css:250-268` `.tb-conn { … background: var(--sc-preview-soft); border: 1px solid var(--sc-preview-border); color: var(--sc-preview); border-radius: 10px; padding: 9px 14px; font-size: 13px; font-weight: 500 }`, `.tb-conn-dot { width: 8px; height: 8px; … }` | MATCH (exact) | — |
| `CON-009` | Connection **reconnecting** state | `unspecified` in `312:124` (see Frame G, `346:124`) | `app.css:270-278` `.tb-conn.reconnecting { background: var(--sc-warn-soft); border-color: var(--sc-warn-border); color: var(--sc-warn) }` | UNSPECIFIED here; cross-referenced in Frame G | — |
| `CON-010` | `● LIVE` topbar chip | **not drawn** in `312:125` | `index.html:80` `<span id="live-chip">● LIVE</span>`; `app.css:226-240` `#live-chip { background: var(--sc-live-soft); color: var(--sc-live); font-size: 11px; font-weight: 800; letter-spacing: .06em; border: 1px solid var(--sc-live-border); border-radius: 999px; padding: 3px 9px; visibility: hidden }` | EXTRA (an on-air indicator the frame omits — see Frame B) | major |
| `CON-011` | App menu (the pill's dropdown) | not drawn in `312:124`; specified in Frame B `336:124` | `index.html:23-62` — 7 nav items + separator + footer | see Frame B | — |

## A.2 Left column — `320:124`

### Service Plan card — `320:125`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Card shell | `bg #14161d`, border `#262a34`, `rounded-[16px]`, `p-[13px]`, `gap-[8px]`, `flex-[1_0_0]` | `app.css:3150-3159` `#plan-wrap { display:flex; flex-direction:column; min-height:0; flex: 2; border: 1px solid var(--sc-border); border-radius: 16px; background: var(--sc-surface); padding: 13px }` | MATCH on chrome | — |
| `CON-012` | Plan vs Transcript height split | Service Plan `flex-[1_0_0]` (fills), Live Transcript **fixed `h-[206px]`** (`320:186`) | `app.css:3153` `#plan-wrap { flex: 2 }` + `app.css:2562` `.fwd-panel { … flex: 1 }` → a 2 : 1 proportional split, transcript grows with the window | DRIFT (proportional vs fixed 206 px) | major |
| — | Header "SERVICE PLAN" | `320:127` 12 px Bold `#6b7383`, `tracking-[1px]` | `app.css:2587-2594` `.card-head h2 { font-size: 12px; letter-spacing: .08em; font-weight: 700; color: var(--sc-text-muted); text-transform: uppercase }` (`.08em` × 12 px = 0.96 px) | **INTENTIONAL-DEVIATION** on colour (promoted to `--sc-text-secondary` at `app.css:4480-4489`, §8.1); geometry MATCH | — |
| `CON-013` | Header row | `320:126` `justify-between`, `items-center` | `app.css:2579-2585` `.card-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin: 0 0 6px }` | MATCH | — |
| `CON-014` | Count pill "7 items" | `320:128` `bg #1c1f28`, `rounded-[999px]`, `px-[8px] py-[2px]`; label `320:129` 11 px Medium `#a7aebe` | `app.css:2596-2604` `.count-pill { background: var(--sc-elevated); color: var(--sc-text-secondary); font-size: 11px; font-weight: 500; border-radius: 999px; padding: 2px 9px }`; markup `index.html:95` | DRIFT (horizontal padding 9 vs 8; no border in either) | minor |
| `CON-015` | Plan name sub-line | **not drawn** | `index.html:99` `<div class="plan-name-sub" id="plan-name">SelahCue Operator</div>`; `app.css:2774-2782` `.plan-name-sub { font-size: 12px; color: var(--sc-text-secondary); font-weight: 500; margin: 0 0 8px; … }` | EXTRA (host-authoritative plan name) | minor |
| `CON-016` | Plan item card | `320:148` `bg #1c1f28`, border `#262a34`, `rounded-[11px]`, `px-[13px] py-[10px]`, **`flex-col gap-[8px]`** | `app.css:3177-3186` `.item { display:flex; align-items:center; gap:8px; padding: 10px 13px; border: 1px solid var(--sc-border); border-radius: 11px; background: var(--sc-elevated) }` with `app.css:3192-3198` `.item .main { flex:1; min-width:0; display:flex; flex-direction:column; gap: 6px }` | DRIFT (title→badge gap 6 vs 8) | minor |
| — | Item list gap | `320:130`→`320:139` step 76 − 68 = **8 px** | `app.css:3165-3175` `#plan { … display:flex; flex-direction:column; gap: 8px }` | MATCH | — |
| — | Item title | `320:150` 14 px SemiBold `#f4f6fb` | `app.css:3200-3208` `.item .title { font-weight: 600; font-size: 14px; color: var(--sc-text); … }` | MATCH | — |
| `CON-017` | Kind badge | `320:152` `bg #0f1116`, border `#262a34`, `rounded-[6px]`, `px-[8px] py-[3px]`; label `320:153` 10 px Bold `tracking-[0.4px]` | `app.css:3211-3226` `.item .kind { align-self: flex-start; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--sc-text-secondary); background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 6px; padding: 3px 8px }` | MATCH (`.04em` × 10 px = 0.4 px exactly) | — |
| — | Kind colour · SONG | `320:138` / `320:159` `#7e6eff` | `app.css:3228-3230` `.item .kind.kind-song { color: var(--sc-primary-hover) }` = `#7e6eff` | MATCH | — |
| — | Kind colour · SCRIPTURE | `320:147` / `320:177` `#f2b84b` | `app.css:3232-3234` `.kind-scripture { color: var(--sc-gold) }` | MATCH | — |
| — | Kind colour · ANNOUNCEMENT | `320:165` / `320:171` `#38bdf8` | `app.css:3236-3238` `.kind-announcement { color: var(--sc-info) }` | MATCH | — |
| — | Kind colour · SECTION | `320:153` `#a7aebe` | `app.css:3240-3242` `.kind-section { color: var(--sc-text-secondary) }` | MATCH | — |
| `CON-018` | LIVE / STAGED status pill on an item | `320:133` `bg #2a1416`, border `#5a2327`, `rounded-999`, `pl-[9px] pr-[10px] py-[5px]`, `gap-[6px]`, dot 7 px, label 10 px Bold `tracking-[0.4px]` `#ff4d4d`; `320:142` the preview twin | `app.css:3264-3296` `.badge { … gap: 6px; font-size: 10px; font-weight: 700; padding: 4px 10px 4px 9px; border-radius: 999px; letter-spacing: .04em; border: 1px solid transparent }`, `.badge::before { width: 7px; height: 7px; … }`, `.badge.live` / `.badge.preview` tints | DRIFT (vertical padding 4 vs 5) | minor |
| — | Live / staged card tint | `320:130` `bg #2a1416` border `#5a2327`; `320:139` `bg #10231c` border `#1c3a2e` | `app.css:3298-3306` `.item.is-live { background: var(--sc-live-soft); border-color: var(--sc-live-border) }`, `.item.is-staged { background: var(--sc-preview-soft); border-color: var(--sc-preview-border) }` | MATCH | — |
| `CON-019` | Per-item edit tools | **not drawn** | `app.css:3247-3262` `.item .tools { display:flex; gap:0; flex:none; opacity: 0; pointer-events: none }` revealed on `:hover`/`:focus-within` | EXTRA (needed; the frame owes a hover/focus state) | minor |
| `CON-020` | Add-item row | `320:178` `gap-[8px]`; kind select `320:179` `bg #0f1116` border `#262a34` `rounded-[9px]` `px-[11px] py-[10px]`, label 12 px Medium `#a7aebe`, caret 9 px `#6b7383`; title input `320:182` same chrome, `flex-1`, placeholder 12 px `#6b7383`; **+ Add** `320:184` `bg #6e5cf0` (flat), `rounded-[9px]`, `px-[13px] py-[10px]`, 12 px Bold white | `app.css:3316-3342` `.add-row { display:flex; gap:8px; padding: 12px 0 0; margin-top: 4px }`, `.add-row select, .add-row input { font-size:12px; color: var(--sc-text-secondary); background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 9px; padding: 10px 11px }`; `app.css:3344-3354` `#add-item { border: none; color: #fff; font-weight: 700; font-size: 12px; padding: 10px 13px; border-radius: 9px; background: var(--sc-primary) }` | MATCH (flat `#6e5cf0` = 4.72:1 — correct per `test_tokens.rs:585-592`) | — |
| `CON-021` | Empty-plan state | **not drawn** in `312:124` | `NOT FOUND` in `dist/index.html` for `#plan`; `app.css:6004` `.plan-empty-sub` and `app.css:6006` `.plan-empty-later` exist only for the **Service Plan surface** (`.plan-builder-*`), not the console column | MISSING (console plan column has no empty state) | major |

### Live Transcript card — `320:186`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-022` | Card shell | `bg #14161d`, border `#262a34`, `rounded-[16px]`, **`px-[13px] py-[15px]`**, `gap-[11px]`, `h-[206px]` | `app.css:2558-2566` `.fwd-panel { … flex: 1; border: 1px solid var(--sc-border); border-radius: 16px; background: var(--sc-surface); padding: 15px }` | DRIFT (uniform 15 vs 13/15; height — see `CON-012`) | minor |
| — | Header row | `320:187` `justify-between` | `app.css:2879-2890` `.fwd-head { display:flex; align-items:center; gap: 8px; margin: 0 0 4px }` + `.fwd-head h2 { margin:0; flex: 1 }` | MATCH | — |
| `CON-023` | "· On-device" sub-label | `445:124` 11 px Medium `#a7aebe`, sits between the title and the REC chip | `NOT FOUND` in `index.html` (`grep '· On-device'` → no hit) | MISSING — the frame's only signal that STT is local, and a privacy-relevant claim (NFR-018) | major |
| `CON-024` | REC chip | `320:189` `bg #2a1416`, border `#5a2327`, `rounded-999`, `pl-[9px] pr-[10px] py-[4px]`, `gap-[6px]`; dot `320:190` **7 px**; label `320:191` 10 px Bold, **no tracking** | `app.css:2892-2906` `.rec-chip { … gap: 5px; font-size: 10px; font-weight: 800; letter-spacing: .08em; border-radius: 999px; padding: 2px 8px }` + `app.css:4515-4522` (review block) `.rec-chip { background: var(--sc-live-soft); border: 1px solid var(--sc-live-border); color: var(--sc-live) }`, `.rec-chip .rec-dot { background: currentColor }`; dot size `app.css:2912-2914` `width: 6px; height: 6px` | DRIFT (padding 2/8 vs 4/9/10; dot 6 vs 7; weight 800 vs 700; tracking .08em vs 0) | minor |
| `CON-025` | Finalised transcript line | `320:192` 13 px Medium `#a7aebe`, `leading-[1.35]` | `app.css:2831-2837` `.seg { display:flex; gap:8px; align-items:baseline; font-size: 12px; line-height: 1.35 }` + `app.css:2846-2849` `.seg-text { color: var(--text) }` = `#f4f6fb` | DRIFT (12 px vs 13; `#f4f6fb` vs `#a7aebe`) | minor |
| `CON-026` | Timestamp prefix on a line | **not drawn** | `app.css:2839-2844` `.seg-time { flex:none; color: var(--muted); font-variant-numeric: tabular-nums; font-size: 10px }` | EXTRA | minor |
| `CON-027` | Interim / partial line | `320:193` 13 px Regular `#6b7383` at **`opacity-60`** → **2.16 : 1** on `#14161d` | `app.css:2853-2859` `.seg-partial { color: var(--sc-text-secondary); font-style: italic; opacity: 0.75; … }` ≈ 5.3 : 1, pulsing 0.6–0.9 under `prefers-reduced-motion: no-preference` (`app.css:2863-2877`) | A11Y-CONFLICT — the frame's `opacity-60` on `#6b7383` is 2.16 : 1; the shipped value is correct. See §8.5 | major |
| `CON-028` | Spacer before the button | `320:194` `flex-[1_0_0]` 10 px wide spacer | `app.css:2817-2825` `.stream { flex: 1; min-height: 0; overflow-y: auto; … }` takes the slack instead | MATCH (equivalent) | — |
| `CON-029` | "■ Stop listening" button | `383:124` **full width**, `bg #a3283a` **solid**, `rounded-[9px]`, `px-[15px] py-[11px]`, centred; label `383:125` 12 px SemiBold white | `index.html:131-136`; `app.css:2938-2953` `.listen-btn { width: 100%; display:inline-flex; align-items:center; justify-content:center; gap: 6px; padding: 8px 10px; font-size: 12px; font-weight: 600 }`, `.listen-btn.listening { background: var(--live); border-color: var(--live); color: #fff }` — `--live: #a3283a` (`app.css:17`) | DRIFT (padding 8/10 vs 11/15 → button is 6 px shorter; radius 9 inherited from `app.css:3853` `button { border-radius: 9px }` ✓) | minor |
| `CON-030` | "Start listening" (idle) state | **not drawn** — the frame only shows the listening state | `index.html:133-134` `<span class="listen-ico">▶</span><span id="transcript-listen-label">Start listening</span>`; chrome falls through to the neutral `button` rule `app.css:3847-3854` | UNSPECIFIED | major |
| `CON-031` | Transcript empty state | **not drawn** | `index.html:124-128` `<div id="transcript-empty" class="fwd-empty">` 🎙 / "Not listening yet." / "Press Start listening to capture the sermon audio."; `app.css:2788-2799` `.fwd-empty { … border: 1px dashed var(--line); border-radius: 8px; color: var(--muted) }` | EXTRA / UNSPECIFIED (state exists, frame owes a design) | major |
| `CON-032` | Mic input meter | **not drawn** | `index.html:141-146`; `app.css:2964-2975` `.mic-meter { display:flex; align-items:center; gap: 8px; margin-top: 8px }` | EXTRA (needed diagnostic) | minor |
| `CON-033` | Transcript status line | **not drawn** | `index.html:147` `<p id="transcript-status" class="stream-note" role="status" aria-live="polite">`; `app.css:2955-2960` `.stream-note { margin: 4px 0 0; font-size: 11px; color: var(--muted); min-height: 14px }` | EXTRA | minor |

## A.3 Center column ("program") — `320:200`

### Preview / Live monitors — `322:124`

> **Read this first.** The frame draws the monitor contents as laid-out text. It is **depicting the
> composited output**, not specifying HTML. Per ADR-0002/0003 the WebView is the operator console only;
> the compositor is native wgpu. `index.html:164` `<canvas class="out-canvas" id="preview-canvas">` and
> `index.html:175` `<canvas class="out-canvas" id="live-canvas">` carry the real pixels. So the frame's
> verse typography is **not** a parity target — the *chrome around* the canvas is.

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-034` | Preview↔Live gap | `322:124` `gap-[14px]` | `app.css:2545-2550` `.obs-row { display:flex; gap: 10px; flex:none; align-items: flex-start }` | DRIFT (10 vs 14) | minor |
| — | Label-row → monitor gap | `322:125` `gap-[10px]` | `app.css:3651-3657` `.outpanel { flex:1; min-width:0; display:flex; flex-direction:column; gap: 10px }` | MATCH | — |
| — | Label row | `322:126` `justify-between`, `items-center` | `app.css:3659-3664` `.panel-head { display:flex; align-items:center; justify-content:space-between; gap: 8px }` | MATCH | — |
| `CON-035` | PREVIEW · STAGED pill | `322:127` `bg #10231c`, border `#1c3a2e`, `rounded-999`, **`pl-[10px] pr-[11px] py-[5px]`**, `gap-[7px]`, dot 8 px; label `322:129` 11 px Bold `#35c08a`, **no tracking** | `app.css:3666-3683` `.panel-pill { display:inline-flex; align-items:center; gap: 7px; font-size: 11px; font-weight: 700; letter-spacing: .02em; border-radius: 999px; padding: 5px 11px; border: 1px solid transparent }` + `.panel-pill .pill-dot { width: 8px; height: 8px; … }` + `app.css:3685-3689` `.panel-pill.preview` tints | DRIFT (left padding 11 vs 10; tracking .02em vs 0) | minor |
| — | LIVE · ON AIR pill | `322:138` `bg #2a1416`, border `#5a2327`; label `322:140` 11 px Bold `#ff4d4d` | `app.css:3691-3695` `.panel-pill.live { background: var(--sc-live-soft); border-color: var(--sc-live-border); color: var(--sc-live) }` | MATCH | — |
| `CON-036` | "1920 × 1080" resolution | `322:130` / `322:141` 11 px Medium `#6b7383` | `app.css:3697-3701` `.panel-res { color: var(--sc-text-muted); font-size: 11px; font-weight: 500 }` | A11Y-DEFECT (both sides: 4.08 : 1 on `#0b0d12`, 11 px normal text)  — see §8.4 | major |
| `CON-037` | Monitor surface | `322:131` `h-[258px]`, `rounded-[12px]`, **`border-2`** (`#35c08a` preview / `#ff4d4d` live), `bg-gradient-to-b from-[#0f1d3a] to-[#0b0d12]`, `pt-[24px] pb-[20px] px-[26px]`, `gap-[14px]`, `justify-center` | `app.css:3703-3718` `.outpanel .surface { aspect-ratio: 16 / 9; max-height: 32vh; border-radius: 12px; overflow: hidden; border: 2px solid var(--sc-border); background: linear-gradient(180deg, #0f1d3a, var(--sc-base)); display:flex; flex-direction:column; align-items:flex-start; justify-content:center; gap: 12px; padding: 22px 24px }`; borders `app.css:3720-3726` `#preview-panel .surface { border-color: var(--sc-preview) }`, `#live-panel .surface { border-color: var(--sc-live) }` | DRIFT (padding 22/24 vs 24/20/26; gap 12 vs 14). Height: `aspect-ratio 16/9` at the 936 px column resolves to ≈259 px ≈ the frame's 258 — MATCH in intent | minor |
| `CON-038` | The wash gradient `#0f1d3a` | `322:131` `from-[#0f1d3a]` — **not a `--sc-*` token** | `app.css:3710` `background: linear-gradient(180deg, #0f1d3a, var(--sc-base))` — hard-coded hex, matching the frame | MATCH, but both hard-code an off-palette colour. Note: mobile measured its equivalent wash at `#231B48` (MOBILE-2.0-SPEC §2.6) — **the two platforms use different washes.** See §9 Q6 | minor |
| `CON-039` | Idle / no-render placeholder | **not drawn** | `app.css:3739-3753` `.outpanel .surface.idle { align-items:center; justify-content:center; text-align:center }` + `.outpanel .surface.idle .big { color: var(--sc-text-muted); font-weight: 500; font-size: 15px }`; copy `index.html:165` `Nothing staged`, `index.html:177` `Output idle` | UNSPECIFIED + A11Y-DEFECT (15 px on `--sc-text-muted`) | major |
| `CON-040` | Rendered-frame label overlay | **not drawn** | `app.css:3776-3799` `.outpanel .surface.has-render .big, … .cap { position:absolute; … background: rgba(0,0,0,.55); color: #fff; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600 }` | UNSPECIFIED (this is what the operator actually sees on air) | major |
| `CON-041` | BLACKOUT overlay on the Live monitor | **not drawn** in `312:124` | `index.html:176` `<span id="live-black">BLACKOUT — OUTPUT DARK</span>`; `app.css:3805-3823` `#live-black { … color: #fff; font-size: 12px; font-weight: 800; letter-spacing: .08em; border: 1px solid var(--live-ink); border-radius: 4px; padding: 3px 8px }`, `#live-panel.blackout .surface .big, … .cap { opacity: 0.25 }` | UNSPECIFIED (see Frame G) | major |

### Transition row — `322:147`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Row gap | `322:147` `gap-[12px]` | `app.css:3825-3830` `.golive-row { display:flex; gap: 12px; align-items: stretch; flex: none }` | MATCH | — |
| `CON-042` | **Button widths** | `322:148` Previous **152 px** (hug), `322:152` GO LIVE **612 px** (`flex-[1_0_0]`), `322:156` Next **148 px** (hug) — the primary is 65 % of the row | `app.css:3832-3841` `.golive-row button { flex: 1; … }` and `app.css:3896` `button.golive { flex: 2 }` → a 1 : 2 : 1 split = 234 / 468 / 234 px at 936 | DRIFT — GO LIVE is 144 px narrower and the two secondaries 82 px wider than designed; the primary loses its dominance | major |
| — | Button box | `px-[18px] py-[15px]`, `rounded-[13px]`, `gap-[10px]`, `justify-center` | `app.css:3833-3841` `padding: 15px 18px; font-size: 14px; border-radius: 13px; display:inline-flex; align-items:center; justify-content:center; gap: 10px` | MATCH | — |
| — | Previous / Next chrome | `bg #1c1f28`, border `#262a34` | inherits `app.css:3847-3854` `button { color: var(--sc-text); background: var(--sc-elevated); border: 1px solid var(--sc-border) }` | MATCH on fill/border | — |
| `CON-043` | Previous / Next label | `322:149` / `322:157` 14 px **SemiBold (600)** `#a7aebe`; note the frame's literal text is `◀··Previous` / `Next··▶` (two spaces) | `app.css:3843-3845` `.golive-row .gl-label { font-weight: 700 }`; colour inherits `var(--sc-text)` `#f4f6fb` from `app.css:3849`; markup `index.html:183-188` `◀ Previous` / `Next ▶` | DRIFT (weight 700 vs 600; colour `#f4f6fb` vs `#a7aebe`) | minor |
| `CON-044` | GO LIVE label | `322:153` **16 px** Bold, ink **`#06231a`** on the green gradient (8.70 : 1 light end / 5.34 : 1 dark end — **passes AA**) | `app.css:3896-3899` `button.golive { flex: 2; border: none; color: #06231a; background: linear-gradient(90deg, #3ed39a, #28a579) }` + `app.css:3898` `.gl-label` weight 700; size inherits `14px` from `app.css:3834` | DRIFT (14 px vs 16). Gradient + ink are an **exact MATCH** — the console frame already uses the dark-ink fix | minor |
| `CON-045` | Keyboard-hint chip (Previous / Next) | `322:150` `bg rgba(107,115,131,0.16)`, `rounded-[6px]`, `px-[8px] py-[3px]`; label 11 px SemiBold `#a7aebe` | `app.css:3872-3879` `button .key { font-size: 11px; font-weight: 600; color: var(--sc-text-secondary); background: rgba(107, 115, 131, .16); border-radius: 6px; padding: 3px 8px; margin-left: 0 }` | MATCH (exact) | — |
| `CON-046` | Keyboard-hint chip **on GO LIVE** ("⏎ Enter") | `322:154` `bg rgba(255,255,255,0.16)`; label `322:155` **11 px white** → **1.74 : 1** over the green gradient | `app.css:3901-3906` `button.golive .key, #blackout.on .key, #clear-all.armed .key { color: #fff; background: rgba(255, 255, 255, 0.18) }` → **1.72 : 1** | **A11Y-DEFECT — blocker.** Fails AA-normal *and* AA-large in **both** the frame and the code. See §8.2 | **blocker** |

### Scriptures card — `322:160`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-047` | Content-source tab bar (Scriptures ｜ Slides) | **not drawn** in `312:124` | `index.html:193-202`; `app.css:3437-3471` `.content-tabs { flex:1; …; border: 1px solid var(--sc-border); border-radius: 16px; background: var(--sc-surface); overflow: hidden }`, `.ctab { … font-size: 14px; font-weight: 500; padding: 14px 10px; … }` | EXTRA — added by `LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec`; the Design 2.0 board has no frame for it. See §9 Q1 | major |
| — | Card shell | `322:160` `bg #14161d`, border `#262a34`, `rounded-[16px]`, `p-[15px]`, `flex-[1_0_0]` | `app.css:3513-3523` `#scriptures { flex: 1; …; border: 1px solid var(--sc-border); border-radius: 16px; background: var(--sc-surface); padding: 15px }` (chrome zeroed by `app.css:3473` when nested in the tab wrapper, which supplies it instead) | MATCH | — |
| `CON-048` | Card internal gap | `322:160` `gap-[12px]` | `app.css:3517` `#scriptures { … gap: 11px }` | DRIFT (11 vs 12) | minor |
| — | "SCRIPTURES" label | `322:162` 12 px Bold `#6b7383` `tracking-[1px]` | `app.css:2587-2594` `.card-head h2` (see `CON-013`), promoted to `--sc-text-secondary` by `app.css:4480-4489` | **INTENTIONAL-DEVIATION** on colour (§8.1) | — |
| `CON-049` | Translation select | `322:163` `bg #0f1116`, border `#262a34`, `rounded-[8px]`, **`px-[11px] py-[8px]`**, `gap-[6px]`; "KJV" 12 px SemiBold `#f2b84b`; caret `322:165` 9 px `#6b7383` | `app.css:3525-3534` `.scrip-head select { font-size: 12px; font-weight: 600; color: var(--sc-gold); background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 8px; padding: 8px 10px }`; markup `index.html:205` | DRIFT (horizontal padding 10 vs 11; caret is the native `<select>` arrow, not the 9 px `▾`) | minor |
| — | Search field | `322:166` `bg #0f1116`, border `#262a34`, `rounded-[8px]`, `px-[12px] py-[9px]`, `gap-[9px]`; ⌕ `322:167` 14 px `#6b7383`; placeholder `322:168` 12 px `#6b7383` "Reference or keywords — e.g. Genesis 1" | `app.css:3536-3546` `.scrip-head input { font-size: 12px; color: var(--sc-text); background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 8px; padding: 9px 12px; flex: 1 }`; magnifier `app.css:4533-4540` inline SVG `stroke="%236b7383"` 14×14 at `background-position: 11px center` + `padding-left: 32px`; markup `index.html:206-208` | MATCH | — |
| `CON-050` | Search placeholder colour | `#6b7383` | `app.css:3548-3550` `.scrip-head input::placeholder { color: var(--sc-text-muted) }` | A11Y-DEFECT (3.96 : 1 on inset, 12 px) — §8.4 | major |
| — | Chapter nav | `322:169` centred, `gap-[12px]`; buttons `322:170/173` `bg #1c1f28`, border `#262a34`, `rounded-[8px]`, `px-[13px] py-[8px]`, glyph 13 px Bold `#a7aebe`; title `322:172` 14 px Bold `#f4f6fb` | `app.css:3552-3578` `.chapter-nav { display:flex; align-items:center; justify-content:center; gap: 12px }`, `.chapter-nav button { padding: 8px 13px; font-size: 13px; font-weight: 700; color: var(--sc-text-secondary); background: var(--sc-elevated); border: 1px solid var(--sc-border); border-radius: 8px }`, `#chapter-ref { font-weight: 700; font-size: 14px; color: var(--sc-text) }` | MATCH (exact) | — |
| `CON-051` | Chapter title **copy** | `322:172` `Isaiah 61 · KJV` (middle dot) | `app.js:3530-3531` `document.getElementById("chapter-ref").textContent = currentChapter.reference + " (" + currentChapter.translation + ")"` → `Isaiah 61 (KJV)` | DRIFT (parenthesis form vs `·` separator) | minor |
| `CON-052` | Verse-list gap | `322:175`→`322:178` step 50 − 38 = **12 px** | `app.css:3580-3588` `#verse-list { … display:flex; flex-direction:column; gap: 8px }` | DRIFT (8 vs 12) | minor |
| — | Verse row | `322:175` `bg #1c1f28`, border `#262a34`, `rounded-[10px]`, `px-[12px] py-[10px]`, `gap-[11px]`; text `322:177` 13 px Regular `leading-[1.35]` `#a7aebe` | `app.css:3590-3601` `.verse { display:flex; gap: 11px; padding: 10px 12px; border: 1px solid var(--sc-border); border-radius: 10px; background: var(--sc-elevated); font-size: 13px; line-height: 1.35; color: var(--sc-text-secondary) }` | MATCH (exact) | — |
| `CON-053` | Verse number | `322:176` **12 px** Bold `#f2b84b`, `w-[20px]` | `app.css:3607-3612` `.verse .vnum { color: var(--sc-gold); font-weight: 700; min-width: 20px; text-align: left }` — no `font-size`, so it inherits 13 px from `.verse` | DRIFT (13 vs 12) | minor |
| — | Staged verse tint | `322:178` `bg #10231c`, border `#1c3a2e`, text `#f4f6fb` | `app.css:3614-3620` `.verse.cursor { border-color: var(--sc-preview-border); background: var(--sc-preview-soft); color: var(--sc-text) }` | MATCH | — |
| `CON-054` | **STAGED pill on the staged verse** | `322:181` `bg #10231c`, border `#1c3a2e`, `rounded-999`, `px-[8px] py-[3px]`; label `322:182` **9 px** Bold `#35c08a` | `NOT FOUND` — `app.js:3536-3546` builds each row as exactly `<span class="vnum">` + `<span>`; no pill node exists | **MISSING** — and it is the WCAG 1.4.1 redundancy for the staged verse: without it, "staged" is carried by tint + border **colour alone** | **blocker** |
| `CON-055` | Verse-list empty state | **not drawn** | `NOT FOUND` for `#verse-list`; `index.html:212` `<span id="chapter-ref">Type a reference to open a chapter</span>` is the only prompt | MISSING | major |
| — | Keyboard hint line | `322:186` 12 px Medium `#6b7383`, centred, `↑ ↓ move & stage · ⏎ Enter sends it live · double-click a verse for instant live` | `index.html:217-218` (same copy); `app.css:3631-3635` `.scrip-note { color: var(--sc-text-muted); font-size: 12px; text-align: center }`, promoted to `--sc-text-secondary` by `app.css:4480-4489` | **INTENTIONAL-DEVIATION** on colour (§8.1); copy MATCH | — |
| `CON-056` | Scripture-search results list | **not drawn** | `index.html:209` `<div id="scripture-hits">`; `app.css:3382-3397` `#scripture-hits .hit { display:flex; align-items:baseline; gap: 6px; padding: 5px 8px; font-size: 12px; color: var(--muted); … }` — legacy `--muted`/`#1c1f28` literals, **not** Design 2.0 chrome | DRIFT (un-migrated component) | major |
| `CON-057` | Scripture status line | **not drawn** | `index.html:216` `<span id="scrip-status" role="status" aria-live="polite">`; `app.css:3637-3641` `#scrip-status { color: var(--sc-gold); font-size: 12px; min-height: 16px }` | EXTRA | minor |

## A.4 Right rail — `320:201`

### Tab bar — `443:124` (also Frame C, `430:124`)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-058` | Tab bar placement | `443:124` sits **outside** the card: transparent, `border-b` `#262a34`, `items-end`, then a **14 px gap** before the card `323:124` | `index.html:246-253` — the tab bar is **inside** `.right-tabs` which *is* the card: `app.css:2613-2616` `.right-tabs { padding: 0; overflow: hidden }` on top of `app.css:2558-2566` `.fwd-panel` (border + `border-radius: 16px` + `background: var(--sc-surface)`) | DRIFT — see Frame C, which is the authoritative tab spec and agrees with the implementation | major |
| `CON-059` | Active tab | `443:125` `border-b-2` **`#7e6eff`**, `pt-[14px] pb-[12px] px-[18px]`; label `443:126` 14 px **Bold** `#f4f6fb` | `app.css:2678-2705` `.rtab { … font-size: 14px; font-weight: 500; padding: 15px 10px; … }` + `.rtab.active { color: var(--sc-text); font-weight: 600; border-bottom-color: var(--sc-primary) }` = `#6e5cf0` | DRIFT (underline `#6e5cf0` vs `#7e6eff`; weight 600 vs 700; padding 15/10 vs 14-12/18) | minor |
| `CON-060` | Tab sizing | `443:125` w 132 / `443:127` w 202 — **hug content**, left-aligned | `app.css:2679` `.rtab { flex: 1 }` — equal halves, centred | DRIFT | minor |
| — | Inactive tab | `443:128` 14 px SemiBold `#a7aebe` | `app.css:2686` `color: var(--sc-text-muted)` = `#6b7383` | A11Y-DEFECT (3.79 : 1, 14 px) — §8.4 | major |
| `CON-061` | Detections count badge | `443:129` **solid `bg #6e5cf0`**, `rounded-[9px]`, `px-[7px] py-[2px]`; label `443:130` 11 px Bold `#f4f6fb` | `app.css:2706-2710` `.rtab .count-pill { background: rgba(110, 92, 240, 0.22); color: #b7abff; font-weight: 600 }` over `app.css:2596-2604` `.count-pill { … border-radius: 999px; padding: 2px 9px; font-size: 11px }` | DRIFT (soft tint vs solid fill; radius 999 vs 9). Both pass AA (7.06 : 1 for the tint version) | minor |

### Service Timer panel — `323:124` + `365:124`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Panel shell | `bg #14161d`, border `#262a34`, `rounded-[16px]`, `px-[15px] py-[16px]`, `gap-[12px]` | card chrome from `.right-tabs` (above); inner `app.css:2715-2720` `.rpanel { flex: 1; min-height: 0; overflow-y: auto; padding: 15px }`, `app.css:2732-2740` `.right-tabs .side-panel { border: none; background: none; padding: 0; border-radius: 0; flex: none }`, gap from `app.css:2634` `#stab-timer { gap: 12px }` | MATCH (padding 15 uniform vs 15/16 — 1 px) | — |
| `CON-062` | "SERVICE TIMER" card label | `323:126` 12 px Bold `#6b7383` `tracking-[1px]` | `NOT FOUND` — `index.html:265-269` `.rpanel-head` contains only `#timer-state`; `app.css:2724-2730` `.rpanel-head { display:flex; justify-content: flex-end; … }` | MISSING as drawn — **but correct**: the tab label above already says "Service Timer", so repeating it is redundant. Frame C `430:124` should be checked as the adjudicating frame | minor |
| — | RUNNING pill | `323:127` `bg #10231c`, border `#1c3a2e`, `rounded-999`, `pl-[9px] pr-[10px] py-[4px]`, `gap-[6px]`; dot `323:128` 7 px; label `323:129` 10 px Bold `#35c08a` | `app.css:2742-2766` `.status-pill { … gap: 6px; background: var(--sc-preview-soft); border: 1px solid var(--sc-preview-border); color: var(--sc-preview); font-size: 10px; font-weight: 700; letter-spacing: .04em; border-radius: 999px; padding: 3px 10px }` + `.status-pill .status-dot { width: 7px; height: 7px }` | MATCH (padding 3 vs 4 — 1 px) | — |
| `CON-063` | PAUSED / TIME-UP pill states | **not drawn** in `312:124` | `app.css:2768-2772` `.status-pill.paused { background: var(--sc-warn-soft); border-color: var(--sc-warn-border); color: var(--sc-warn) }`; TIME-UP `NOT FOUND` as a pill variant | UNSPECIFIED / partially MISSING | major |
| — | Countdown inset | `323:130` `bg #0f1116`, border `#262a34`, `rounded-[13px]`, `py-[16px]`, `gap-[2px]`, centred | `app.css:3930-3936` `.timer-display { background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 13px; padding: 16px 12px; text-align: center }` | MATCH | — |
| — | Countdown readout | `323:131` **54 px** Bold `#f4f6fb` `tracking-[-1px]` | `app.css:3938-3945` `#timer-big { font-size: 54px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -1px; color: var(--sc-text); line-height: 1 }` | MATCH (exact) | — |
| `CON-064` | Countdown warn / time-up colours | **not drawn** | `app.css:3947-3953` `#timer-big.warn { color: var(--sc-warn) }`, `#timer-big.up { color: var(--sc-live) }` | UNSPECIFIED (both pass AA at 54 px) | minor |
| `CON-065` | Countdown sub-line | `323:132` 12 px Medium `#6b7383` "Sermon · counts down to 00:00" | `app.css:3955-3959` `.timer-sub { margin-top: 4px; font-size: 12px; color: var(--sc-text-muted) }`; copy `index.html:273` `Counts down to 00:00` | A11Y-DEFECT (3.96 : 1, 12 px) §8.4; copy DRIFT (no plan-item prefix) | major |
| — | "SET A CUSTOM TIME" | `365:125` 11 px Bold `#6b7383` `tracking-[1px]` | `app.css:3961-3967` `.timer-custom-label { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--sc-text-muted); text-transform: uppercase }`, promoted to `--sc-text-secondary` by `app.css:4480-4489`; markup `index.html:277` | **INTENTIONAL-DEVIATION** on colour (§8.1); tracking .88 px vs 1 px | minor |
| — | HH:MM:SS field | `365:127` `bg #0f1116`, border `#262a34`, `rounded-[10px]`, `pt-[9px] pb-[8px] px-[12px]`, `gap-[6px]`, `w-[249px]` | `app.css:3975-3986` `.hms { flex: 1; min-width: 0; display:flex; align-items:center; justify-content:center; gap: 6px; background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 10px; padding: 8px 12px }` | MATCH (flex:1 resolves to ≈249 at a 380 px column) | — |
| — | Unit digits | `365:129` 20 px Bold `#f4f6fb` | `app.css:3995-4007` `.hms-unit input { width: 2.2ch; font-size: 20px; font-weight: 700; text-align: center; color: var(--sc-text); background: transparent; border: none; padding: 0 }` | MATCH | — |
| `CON-066` | Unit caption **copy** | `365:130` **"HOURS"** / `365:134` "MIN" / `365:138` "SEC", 9 px Bold `#6b7383` | `index.html:281` `<span class="hms-cap">HRS</span>`; `app.css:4021-4025` `.hms-cap { font-size: 9px; color: var(--sc-text-muted); letter-spacing: .04em }` — no `font-weight`, so 400 not 700 | DRIFT ("HRS" vs "HOURS"; weight 400 vs 700) + A11Y-DEFECT (3.96 : 1 at 9 px) | major |
| — | Colon separator | `365:131` 18 px `#6b7383` | `app.css:4027-4032` `.hms-colon { color: var(--sc-text-muted); font-size: 18px; align-self: flex-start; margin-top: 4px }`; markup `index.html:282` `aria-hidden="true"` | MATCH (decorative — muted is legitimate here) | — |
| `CON-067` | Start button | `365:139` `bg-gradient-to-r from-[#7e6eff] to-[#6e5cf0]`, `rounded-[10px]`, `w-[91px] h-[52px]`, `px-[16px] py-[11px]`; label `365:140` **13 px** Bold **white** | `app.css:4034-4041` `.timer-start { flex: none; border: none; color: #fff; font-weight: 700; padding: 0 18px; background: linear-gradient(90deg, var(--sc-primary-hover), var(--sc-primary)) }` **overridden** by `app.css:4505-4507` `.tb-golive, .timer-start { background: linear-gradient(90deg, var(--sc-primary), #5a48d0) }`; radius 9 from `app.css:3853` | **INTENTIONAL-DEVIATION (permanent)** — white on `#7e6eff` = 3.78 : 1 (AA-large only, pinned at `test_tokens.rs:585-592`); the shipped gradient runs 4.72 : 1 → 6.42 : 1. See §8.1 | — |
| — | Preset row (⏱ 5:00 / ⏱ 10:00) | `323:133` `gap-[8px]`, each `flex-1`, `bg #1c1f28`, border `#262a34`, `rounded-[9px]`, `py-[11px]`, centred; label 12 px SemiBold `#a7aebe` | `app.css:4048-4059` `.timer-row { display:flex; gap: 8px }`, `.timer-row button { flex: 1; padding: 11px 6px; font-size: 12px; font-weight: 600; color: var(--sc-text-secondary) }` + base `button` fill/border/radius-9 | MATCH (exact) | — |
| — | ± 1:00 row | `323:138` identical chrome; labels `− 1:00` / `+ 1:00` | `index.html:295-298`, same `.timer-row` rules | MATCH | — |
| — | Pause / Reset / Stop row | `323:143` three `flex-1`; Stop `323:148` `bg #2a1416`, border `#5a2327`, label 12 px SemiBold `#ff4d4d` | `index.html:299-303`; `app.css:4067-4071` `.timer-stop-btn { background: var(--sc-live-soft); border-color: var(--sc-live-border); color: var(--sc-live) }` | MATCH (exact) | — |
| `CON-068` | Disabled control treatment | **not drawn** | `app.css:4061-4065` `.timer-row button:disabled { opacity: 0.4; cursor: default }` — `#a7aebe` @ 40 % on `#1c1f28` ≈ **2.0 : 1** | A11Y-DEFECT (disabled controls are exempt from 1.4.3, but Pause/Reset are *reachable state*, and the frame never draws them) — see §9 Q4 | minor |
| — | Panel footnote | `323:150` 11 px Medium `#6b7383`, centred, "Shown on the stage output only" | `index.html:304`; `app.css:4073-4077` `.timer-note { color: var(--sc-text-muted); font-size: 11px; text-align: center }` | A11Y-DEFECT (3.96 : 1, 11 px) §8.4; copy MATCH | major |
| `CON-069` | Timer ｜ Stage sub-tabs | **not drawn** in `312:124` (specified by Frame E, `563:201`) | `index.html:258-262`; `app.css:2623-2628` `.seg { display:flex; gap: 3px; padding: 3px; background: var(--sc-inset); border: 1px solid var(--line); border-radius: 9px }`, `.seg-btn { flex: 1; padding: 6px 0; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-weight: 600; font-size: 13px }`, `.seg-btn.active { background: var(--accent); color: #fff }` | see Frame E | — |

### Detected Scriptures panel — `323:151` (hidden layer in the flagship; live spec is Frame D)

| # | Component | Figma spec (from the hidden layer) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-070` | Panel header "✦ DETECTED SCRIPTURES" + "2 new" pill | `323:153-157` | superseded by the tab bar (`CON-058`) — `NOT FOUND` as a header | MISSING as drawn; correct given the tabbed shell. Confirm against Frame C/D | minor |
| — | Mode select + cards | `323:158-189` | audited in full under **Frame D** below | — | — |

## A.5 Emergency footer — `312:151`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Bar shell | h 56, `bg #12090b`, border `#3a1a1d`, `px-[20px]`, `justify-between` | `app.css:4141-4152` `#emergency { flex: none; height: 56px; display:flex; align-items:center; gap: 16px; padding: 0 20px; border-top: 1px solid #3a1a1d; background: #12090b }` | MATCH (exact) | — |
| — | Action group gap | `312:152` `gap-[10px]` | `app.css:4153-4157` `.emergency-actions { display:flex; align-items:center; gap: 10px }` | MATCH | — |
| `CON-071` | ■ BLACKOUT | `312:153` `bg-gradient-to-r from-[#ff4d4d] to-[#d8362f]`, `rounded-[10px]`, `px-[14px] py-[9px]`; label `312:154` **13 px** SemiBold **white** → 3.27 : 1 (light end) / 4.68 : 1 (dark end) | `app.css:4186-4193` `#blackout { border: none; color: #fff; font-weight: 600; padding: 9px 14px; border-radius: 10px; background: linear-gradient(90deg, var(--sc-live), #d8362f) }` **overridden** by `app.css:4492-4494` `#blackout { background: linear-gradient(90deg, #a3283a, #8f2030) }` (7.19 : 1) | **INTENTIONAL-DEVIATION (permanent)** — white on `#ff4d4d` = 3.27 : 1 at 13 px (fails AA-normal); the shipped fill is 7.19 : 1. See §8.3 | — |
| — | Clear Output (idle) | `312:155` `bg #2a1416`, border `#5a2327`, `rounded-[10px]`, `px-[14px] py-[9px]`; label `312:156` 13 px Medium `#ff4d4d` | `app.css:4210-4216` `#clear-all { background: var(--sc-live-soft); border: 1px solid var(--sc-live-border); color: var(--sc-live); padding: 9px 14px; border-radius: 10px }` | MATCH | — |
| `CON-072` | Clear Output **copy + glyph** | `312:156` `Clear Output` (no glyph) | `index.html:167-168` `✕ Clear Output<span class="key">Esc Esc</span>` | DRIFT (extra `✕` glyph and a `Esc Esc` key chip the frame does not draw) | minor |
| `CON-073` | BLACKOUT key chip / state text | not drawn | `index.html:165-166` `<span id="blackout-state"></span><span class="key">B</span>`; `app.css:4204-4208` `#blackout-state { margin-left: 6px; font-size: 10px; font-weight: 800 }` | EXTRA | minor |
| `CON-074` | Armed / engaged states | **not drawn** | `app.css:4200-4202` `#blackout[aria-pressed="true"]` → `app.css:4495-4496` `{ background: #8f2030 }`; `app.css:4218-4222` `#clear-all.armed { background: var(--sc-live); border-color: var(--sc-live); color: #fff }` — white on `#ff4d4d` = **3.27 : 1** at 13 px | UNSPECIFIED + A11Y-DEFECT on `#clear-all.armed` — see §8.3 | major |
| — | Footer note | `312:157` 12 px Medium `#6b7383`, "Emergency controls — always one action away · works with no network" | `index.html:170`; `app.css:4159-4163` `#emergency .note { margin: 0 auto; color: var(--sc-text-muted); font-size: 12px }`, promoted to `--sc-text-secondary` by `app.css:4480-4489` | **INTENTIONAL-DEVIATION** on colour (§8.1); copy MATCH | — |
| `CON-075` | Offline-ready pill | `312:158` `bg #1c1f28`, border `#262a34`, `rounded-[10px]`, `px-[14px] py-[9px]`, `gap-[8px]`; dot `312:159` 8 px (green); label `312:160` 13 px Medium **`#a7aebe`** | `index.html:171`; `app.css:4165-4184` `.emergency-ready { … background: var(--sc-elevated); border: 1px solid var(--sc-border); color: var(--sc-text-secondary); border-radius: 10px; padding: 9px 14px; font-size: 13px }` + `.ready-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--sc-preview) }` | MATCH (exact) | — |

---

# Frame B — `336:124` "SPEC — App Navigation & Global Controls" · 3192 × 661

Four panels: **App menu — open** (`336:129`), **Command palette — ⌘K** (`336:205`), **Global chords**
(`337:124`), **Emergency footer — normal** (`337:180`) and **Emergency footer — blackout active** (`337:199`).

## B.1 App menu — `336:133`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-076` | Menu width | `336:133` **360 px** | `app.css:352` `#app-menu { width: 320px }` | DRIFT (320 vs 360) | minor |
| — | Menu shell | `unspecified` radius/shadow on this frame; the container is a plain 360-wide stack | `app.css:347-359` `#app-menu { position: absolute; top: 52px; left: 0; z-index: 60; background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 14px; padding: 8px; box-shadow: 0 16px 40px rgba(0,0,0,0.55) }` | UNSPECIFIED | minor |
| `CON-077` | Workspace header — **content** | `336:137` **"Grace Chapel"** 14 px Bold `#f4f6fb`; `336:138` **"Sunday Service · Live"** 11 px Medium **`#35c08a`** (a live-service status line) | `index.html:26-27` `<span class="menu-ws-t">SelahCue</span><span class="menu-ws-d">Operator console</span>`; `app.css:385-394` `.menu-ws-t { font-size: 14px; font-weight: 700; color: var(--sc-text) }`, `.menu-ws-d { font-size: 11px; color: var(--sc-text-secondary) }` | DRIFT — the frame's header is **church name + current service state**; the implementation shows a static product name. The green sub-line is a live signal the console does not surface anywhere | major |
| `CON-078` | Workspace header — chrome | `336:134` `bg #1c1f28`, `px-[15px] py-[14px]`, `gap-[11px]`; avatar `336:135` **34 × 34**, `rounded-[9px]`, `bg-gradient-to-r from-[#7e6eff] to-[#6e5cf0]`; trailing `▾` `336:139` 11 px `#6b7383` | `index.html:24-28`; `app.css:365-377` `.menu-head { display:flex; align-items:center; gap: 11px; padding: 6px 8px 10px }`, `.menu-logo { width: 60px; height: 60px; object-fit: contain }` — no fill, no radius, no trailing caret | DRIFT (no elevated row fill; logo 60 px vs a 34 px gradient tile; caret MISSING) | major |
| `CON-079` | **Scriptures nav item** | `336:180-187` — icon `✦`, title **"Scriptures"**, sub **"Browse & stage the Bible"**, chord **⌘6** | `NOT FOUND` — `index.html:29-58` lists console/presentation/theme-designer/screens/plan/transcript/settings only | **MISSING** | major |
| `CON-080` | Nav chord assignments | Live Console ⌘1 · Presentation ⌘2 · Theme Designer ⌘3 · Screens & Outputs ⌘4 · Service Plan ⌘5 · Scriptures ⌘6 · **Transcript & Notes ⌘7** · **Settings ⌘,** | `index.html:32,36,39,43,50,54,58` → ⌘1 ⌘2 ⌘3 ⌘4 ⌘5 · Transcript **⌘6** · Settings **⌘7** | DRIFT — two chords differ because `CON-079` shifted the list up one | major |
| `CON-081` | "Transcript & Notes" sub-label | `336:193` "Live transcript + sermon AI" | `index.html:53-54` `Live transcript · in Console` | DRIFT (copy) | minor |
| `CON-082` | Nav row geometry | `336:140` `px-[13px] py-[11px]`, `gap-[12px]`; icon tile `336:141` **26 × 30**, `rounded-[8px]`; title `336:144` **13 px SemiBold** `#f4f6fb`; sub `336:145` **10 px Medium** `#6b7383`; chord chip `336:146` `bg #0f1116` border `#262a34` `rounded-[6px]` `px-[7px] py-[3px]`, 11 px SemiBold `#a7aebe` | `app.css:402-414` `.nav-item { display:flex; align-items:center; gap: 11px; …; border-radius: 10px; padding: 9px 11px }`; `app.css:431-443` `.nav-ico { width: 30px; height: 30px; border-radius: 8px; font-size: 13px; background: var(--sc-inset); border: 1px solid var(--sc-border); color: var(--sc-text-secondary) }`; `app.css:458-462` `.nav-t { font-size: 13px; font-weight: 600; color: var(--sc-text) }`; `app.css:464-470` `.nav-d { font-size: 11px; color: var(--sc-text-secondary) }`; `app.css:1956-1962` `.nav-item .nav-key` | DRIFT (row padding 9/11 vs 11/13; gap 11 vs 12; icon tile 30×30 vs 26×30; sub 11 px `#a7aebe` vs 10 px `#6b7383`) | minor |
| `CON-083` | **Active** nav row | `336:140` row `bg rgba(110,92,240,0.14)`; icon tile `bg rgba(110,92,240,0.2)` + `border #7e6eff`, glyph `#7e6eff`. **No left rail bar.** | `app.css:426-429` `.nav-item[aria-current="page"] { background: var(--sc-accent-soft); box-shadow: inset 3px 0 0 var(--sc-primary) }` — `--sc-accent-soft` is the opaque `#201f3a`, plus a 3 px inset rail the frame does not draw; `app.css:445-448` icon `color: var(--sc-primary-hover); border-color: var(--sc-primary)` (border `#6e5cf0` vs `#7e6eff`; no violet tile fill) | DRIFT | minor |
| — | Separator before Settings | `336:196` 1 px full-width | `index.html:55` `<div class="menu-div" role="separator">`; `app.css:396-400` `.menu-div { height: 1px; background: var(--sc-border); margin: 6px 4px }` | MATCH | — |
| `CON-084` | Menu footer (⌘K / Shortcuts) | **not drawn** | `index.html:59-61`; `app.css:481-503` `.menu-foot`, `.menu-foot-btn` | EXTRA | minor |

## B.2 Command palette — `336:205`

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Panel width | `336:209` 520 px | `app.css:4240-4246` `.cmd-box { … background: var(--sc-surface); border-radius: 14px }` — width `NOT FOUND` on `.cmd-box` (see below) | see `CON-085` | — |
| `CON-085` | Palette box width | 520 px | `app.css:4240` `.cmd-box { width: min(560px, 92vw) }` | DRIFT (560 vs 520) | minor |
| — | Input row | `336:210` h 51, `⌕` `336:211` at x 16, query 15-ish px, `esc` chip `336:215` | `index.html:1176-1182`; `app.css:4252-4257` `.cmd-input-row { … gap: 10px; padding: 14px 16px }`, `app.css:4265-4271` `#cmd-input { font-size: 15px; color: var(--sc-text); background: transparent }` | MATCH | — |
| `CON-086` | `esc` chip | `336:216` inside a chip at x 134 — i.e. **immediately after the query text**, not flushed right | `app.css:4280-4288` `.cmd-esc { font-size: 11px; color: var(--sc-text-muted); background: var(--sc-elevated); border-radius: 6px; padding: 2px 7px }`, placed last in a `justify`-default flex row | DRIFT (position) + A11Y-DEFECT (muted 11 px) | minor |
| — | Group headers ACTIONS / NAVIGATE / SCRIPTURES | `336:217` / `336:246` / `336:262`, 12 px, x 16, row h 28 | `app.css:4332-4341` `.cmd-group { padding: 13px 12px 5px; font-size: 11px; …; color: var(--sc-text-muted) }`; sections built in `app.js:4985-5001` | DRIFT (11 px vs 12) + A11Y-DEFECT | minor |
| `CON-087` | **SCRIPTURES palette group** | `336:262-269` — a row `✦  Search "go live" in Bible` + a muted hit preview `John · Revelation…` | `NOT FOUND` — `app.js` pushes only `section: "ACTIONS"` and `section: "NAVIGATE"` entries (`app.js:4985-5001` and the NAVIGATE block); no `SCRIPTURES` section exists | **MISSING** | major |
| — | Command rows | `336:219` h 46, icon tile at x 16, label 16 px-box, trailing chord chip | `app.css:4298-4306` `.cmd-item { … gap: 11px; padding: 10px 12px; border-radius: 9px; color: var(--sc-text); font-size: 13px }` | MATCH (approx) | — |
| — | Active row | `336:219` violet-tinted with a left accent (visible in the render) | `app.css:4321-4330` `.cmd-item.active, .cmd-item:hover { background: var(--sc-elevated) }` + `.cmd-item.active` accent | MATCH (approx) | — |
| — | Rows present | Go Live ⏎ · Blackout output B · Clear all layers `esc esc` · Start service timer · Go to Live Console ⌘1 · Open Theme Designer ⌘3 | `app.js:4985-4990` Go Live ⏎ · Blackout output B · Clear all layers `Esc Esc` · Start service timer · **Next item Space** · **Previous item ←** | MATCH + 2 EXTRA rows | — |
| — | Footer hints | `336:271-273` `↑↓ navigate` · `⏎ run` · `esc close` | `index.html:1185` `↑ ↓ navigate` / `⏎ run` / `esc close`; `app.css:4384-4391` `.cmd-foot { … gap: 16px; padding: 10px; color: var(--sc-text-muted); font-size: 11px }` | MATCH (copy) + A11Y-DEFECT (muted) | — |
| `CON-088` | Palette **empty state** | **not drawn** | `index.html:1184` `<div class="cmd-empty" hidden>No matching command</div>`; `app.css:4362-4370` `.cmd-empty { padding: 18px; color: var(--sc-text-secondary); font-size: 13px }` | EXTRA / UNSPECIFIED | minor |

## B.3 Global chords — `337:128`

| # | Chord | Figma action | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | `Space` | `337:133` Advance to next slide / item | `app.js:3946-3950` `case " ": case "ArrowRight": … act(() => invoke("next"))` | MATCH | — |
| — | `⏎` | `337:138` Send preview → Live | `app.js:3955-3957` `case "Enter": … goLive()` | MATCH | — |
| — | `←` `→` | `337:145` Previous / Next | `app.js:3946-3954` | MATCH | — |
| — | `↑` `↓` | `337:152` Move & stage in the plan | `app.js:3940-3943` `if ((e.key === "ArrowUp" \|\| e.key === "ArrowDown") && currentChapter) { … setCursor(...) }` — this moves & stages **verses**, not plan items | DRIFT (semantics) | major |
| — | `B` | `337:157` Blackout the output | `app.js:3959-3961` `case "b": case "B":` | MATCH | — |
| — | `Esc` `Esc` | `337:164` Clear all layers | `app.js:3970+` `case "Escape"` double-tap with `disarm()` | MATCH | — |
| — | `⌘K` | `337:169` Command palette | `app.js:3801` `if (mod && !e.shiftKey && (e.key === "k" \|\| e.key === "K"))` | MATCH | — |
| `CON-089` | **`F`** | `337:174` **Fullscreen selected output** | `NOT FOUND` — no `case "f"` in the global handler (`app.js:3945-3968`); the only fullscreen affordance is the button `app.js:1203` `fs.textContent = "⛶  Go fullscreen"` on the Screens surface | **MISSING** | major |
| `CON-090` | **`⌘Z`** | `337:179` Undo · `⌘⇧Z` redo — listed as a **global** chord | Bound **per-surface only**: Theme Designer `app.js:1419-1490`, Presentation `app.js:5001`, Plan run-sheet `app.js:6273`. No global binding, and **no undo at all on the Live Console** | DRIFT (partial) — see §9 Q3 | major |
| `CON-091` | `Backspace` | **not drawn** | `app.js:3963-3968` `case "Backspace": // Clear current layer` | EXTRA — an undrawn destructive chord | major |
| `CON-092` | Chord-row chrome | `337:130` key chip `w-auto h-23`; label 16 px box at x 123 | `NOT FOUND` — the chord list has no on-screen equivalent except the Shortcuts modal (`index.html` `data-open="shortcuts"`, `app.css:4395+` `.sc-box` / `.sc-head`) | UNSPECIFIED — the chords sheet is a spec panel, not a screen; verify the Shortcuts modal lists all nine | minor |

## B.4 Emergency footer — normal (`337:184`) vs the flagship footer (`312:151`)

> **The Figma file contradicts itself here.** `312:151` and `337:184` draw the *same* footer differently.
> Every row below flags which frame the implementation follows.

| # | Component | `312:151` (flagship) | `337:184` (spec sheet) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|---|
| `CON-093` | Footer container | `bg #12090b`, border `#3a1a1d`, h 56, square (bar) | `bg #14161d`, border `#262a34`, **`rounded-[12px]`**, `px-[16px] py-[13px]`, `gap-[14px]` | `app.css:4141-4152` `#emergency { height: 56px; padding: 0 20px; border-top: 1px solid #3a1a1d; background: #12090b }` | follows `312:151` — the spec sheet's card is a **presentation device** for the panel, not the real bar | minor |
| `CON-094` | BLACKOUT label | `■ BLACKOUT` on a **red gradient**, white 13 px SemiBold | `■` + `BLACKOUT` **13 px Bold `#ff4d4d` on `bg #2a1416`** (soft tint), plus a `B` chip | `index.html:165-166` `■ BLACKOUT` + `#blackout-state` + `<span class="key">B</span>`; fill `app.css:4492-4494` `linear-gradient(90deg, #a3283a, #8f2030)` | follows `312:151` (solid fill), and the `B` chip follows `337:188`. **Two frames, two idle designs** — see §9 Q2 | major |
| `CON-095` | Clear control **label** | `Clear Output` (no glyph, no chip) | **`✕ CLEAR ALL`** + `Esc Esc` chip, 13 px Bold `#a7aebe` on `bg #1c1f28` border `#262a34` | `index.html:167-168` `✕ Clear Output` + `Esc Esc` chip | DRIFT against **both** — it takes the glyph and chip from `337:190` but the word "Output" from `312:155`, and the fill/ink from neither (`app.css:4210-4216` is the live-soft tint `#2a1416` / `#ff4d4d`, which `337:190` gives to *Blackout*) | major |
| `CON-096` | Footer note | 12 px Medium `#6b7383`, single line, centred by `justify-between` | 12 px Medium `#6b7383`, `flex-[1_0_0]`, **wraps to two lines** | `app.css:4159-4163` `#emergency .note { margin: 0 auto; … font-size: 12px }`, promoted to `--sc-text-secondary` at `app.css:4480-4489` | MATCH (copy identical in both frames) | — |
| `CON-097` | Offline-ready | pill: `bg #1c1f28` border `#262a34` `px-14 py-9`, 13 px Medium **`#a7aebe`** | **no pill** — bare dot + 12 px SemiBold **`#35c08a`** | `app.css:4165-4177` `.emergency-ready { background: var(--sc-elevated); border: 1px solid var(--sc-border); color: var(--sc-text-secondary); border-radius: 10px; padding: 9px 14px; font-size: 13px }` | follows `312:158`. See §9 Q2 | minor |

## B.5 Emergency footer — **blackout active** (`337:199`) — the biggest single gap

The whole engaged state is a distinct component and **none of it is implemented.**

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-098` | Blacked-out footer container | `337:203` `bg #1a0c0c`, border **`#5a2327`**, `rounded-[12px]`, `px-[16px] py-[13px]`, `gap-[14px]` — the whole bar re-tints | `NOT FOUND` — `#emergency` keeps `background: #12090b` and `border-top: 1px solid #3a1a1d` in every state (`app.css:4141-4152`); no `[data-blackout]` / `.blackout` rule targets `#emergency` | **MISSING** | **blocker** |
| `CON-099` | "BLACKED OUT" button | `337:204` `bg #ff4d4d` **solid**, border `#5a2327`, `rounded-[10px]`, `px-[15px] py-[11px]`, `gap-[8px]`; label `337:206` **13 px Bold white** → **3.27 : 1** | `app.js:313` `document.getElementById("blackout-state").textContent = view.blackout ? "ON" : ""` — the label stays `■ BLACKOUT` and gains a small `ON`; fill becomes `#8f2030` (`app.css:4495-4496`) | **MISSING** (label change) — and the frame's white-on-`#ff4d4d` is an **A11Y-DEFECT** at 13 px; the implementation's `#8f2030` is 8.6 : 1. Build the *label* change, keep the *fill* | **blocker** |
| `CON-100` | `B` chip in the engaged state | `337:207` `bg #0f1116`, border `#262a34`, `rounded-[6px]`, `px-[8px] py-[4px]`, 12 px SemiBold `#a7aebe` — i.e. the chip goes **dark on the red fill** | `app.css:3901-3906` `#blackout.on .key { color: #fff; background: rgba(255,255,255,0.18) }` | DRIFT — the frame's inset-dark chip is the more legible of the two (`#a7aebe` on `#0f1116` = 8.49 : 1) | major |
| `CON-101` | Explanatory line | `337:209` **"Output is black — the audience sees nothing. Press B or click to restore."** 12 px Medium **`#e8b4b4`**, `flex-1` | `NOT FOUND` | **MISSING** — the only plain-language explanation of the most destructive state in the product | **blocker** |
| `CON-102` | **"↺ Restore output" button** | `337:210` `bg #35c08a` **solid**, `rounded-[10px]`, `px-[15px] py-[11px]`; label `337:211` 13 px Bold **`#06231a`** (dark ink — passes) | `NOT FOUND` — restoring is only via re-pressing `#blackout` or the `B` key | **MISSING** — a dedicated, differently-coloured recovery affordance. Restoring live output currently requires knowing that the blackout button is a toggle | **blocker** |
| `CON-103` | `#e8b4b4` | `337:209` — **not a `--sc-*` token** (a warm rose tint, 8.6 : 1 on `#1a0c0c`) | n/a | Needs a token or a documented local constant — see §9 Q6 | minor |
| `CON-104` | `#1a0c0c` | `337:203` — **not a `--sc-*` token** (an "armed emergency" ground, distinct from `#12090b`) | n/a | same | minor |

---

# Frame C — `430:124` "SPEC — Right Panel Tabs: Timer / Detected Scriptures" · 1396 × 1029

This frame carries **written implementation notes** (`435:124`) and is therefore the adjudicating
authority where it disagrees with the flagship's `443:124`. Its notes say, verbatim:

- `435:128` "The right column becomes ONE panel with a 2-tab header: Service Timer · Detected Scriptures (count badge)."
- `435:129` "Underline + white label marks the active tab; inactive is muted. Full column height (~848px) per tab."
- `435:135` "At least 3 cards visible at once; the list scrolls beyond that (bounded — client cap stays)."
- `435:136` "Newest detection on top (reverse of the current oldest-first order)."
- `435:137` "Card: reference · translation, match-% pill (green ≥90, amber/gold when fuzzy), snippet, source + 'spoken Ns ago', Stage / Approve / Dismiss."
- `435:142` "Tabs are a real tablist: role=tab / tabpanel, aria-selected, roving tabindex, ←/→ to switch, aria-controls."
- `435:149` "surface #14161d · card #1c1f28 · border #262a34 · primary #6e5cf0 (active tab + Stage) · ok #35c08a (≥90 / RUNNING) · gold #f2b84b (fuzzy match) · text #f4f6fb / #6b7383."

**`430:124` supersedes `443:124` on tab sizing and underline colour.** The implementation already
follows `430:124` (equal-width tabs, `#6e5cf0` underline). `CON-059`/`CON-060` are therefore
**closed against the flagship and open only on type size** — corrected below.

## C.1 Tabbed container

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Panel shell | `431:126` `bg #14161d`, border `#262a34`, `rounded-[16px]`, tab bar flush on top | `index.html:246` `<section class="right-tabs fwd-panel">`; `app.css:2558-2566` + `app.css:2613-2616` `.right-tabs { padding: 0; overflow: hidden }` | MATCH — **`CON-058` is resolved in the implementation's favour** | — |
| — | Tab bar | `431:127` `border-b #262a34`, two `flex-[1_0_0]` tabs | `app.css:2617-2622` `.tabbar { display:flex; flex:none; border-bottom: 1px solid var(--sc-border) }` + `app.css:2679` `.rtab { flex: 1 }` | MATCH — **supersedes `CON-060`** | — |
| — | Active underline | `431:137` `bg #6e5cf0`, `h-[2px]`, full tab width | `app.css:2681` `.rtab { border-bottom: 2px solid transparent }` + `app.css:2700-2704` `.rtab.active { border-bottom-color: var(--sc-primary) }` = `#6e5cf0` | MATCH — **supersedes the flagship's `#7e6eff`** | — |
| `CON-105` | Tab label type | active `431:134` **13 px SemiBold** `#f4f6fb`; inactive `431:130` **13 px Medium** `#6b7383` | `app.css:2685-2688` `.rtab { font-size: 14px; font-weight: 500; color: var(--sc-text-muted) }`; `app.css:2700-2704` `.rtab.active { color: var(--sc-text); font-weight: 600 }` | DRIFT (14 px vs 13). Inactive `#6b7383` matches the frame — and is an **A11Y-DEFECT** in both (3.79 : 1 at 14 px) | major |
| `CON-106` | Tab padding | `431:129` `pt-[15px] pb-[13px]`, label hugs; tab centres it | `app.css:2691` `.rtab { padding: 15px 10px }` (symmetric) | DRIFT (bottom 15 vs 13 — shifts the label 1 px off the underline) | minor |
| `CON-107` | Count badge | `431:135` `bg #1b1a3a` (opaque), `rounded-[999px]`, `px-[7px] py-[2px]`, label `431:136` **11 px SemiBold `#9e91f7`** | `app.css:2706-2710` `.rtab .count-pill { background: rgba(110, 92, 240, 0.22); color: #b7abff; font-weight: 600 }` + `app.css:2596-2604` `padding: 2px 9px; font-size: 11px; border-radius: 999px` | DRIFT (translucent `rgba(110,92,240,.22)` vs opaque `#1b1a3a`; ink `#b7abff` vs `#9e91f7`; padding 9 vs 7). Both are non-token colours — see §9 Q6 | minor |
| — | Tablist semantics | `435:142` role=tab/tabpanel, aria-selected, roving tabindex, ←/→, aria-controls | `app.js:4602-4634` `wireRightTabs()` — `aria-selected`, `t.tabIndex = on ? 0 : -1`, `ArrowRight`/`ArrowLeft`/`Home`/`End`, panels toggle `hidden`; markup `index.html:247-253` | MATCH (exceeds — Home/End are extra) | — |
| — | Auto-surface on new detection | `435:131` "consider auto-switching … while the operator isn't mid-timer-edit (optional)" | `app.js:4636-4647` `window.__rightTabsOnDetections` — switches only if the timer panel does not contain `document.activeElement`, and never focuses | MATCH (the optional behaviour is built, exactly as annotated) | — |

## C.2 Detected Scriptures panel

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-108` | Panel padding | `431:138` `pt-[14px] pb-[16px] px-[16px]`, `gap-[12px]` | `app.css:2715-2720` `.rpanel { … padding: 15px }`; `#detections` has no own gap (`app.css:2732-2740` zeroes its chrome) | DRIFT | minor |
| `CON-109` | **Mode row** | `431:139` a **bare inline row**, no fill/border: `Mode:` `431:140` 12 px Regular `#6b7383` + `Operator confirms` `431:141` **13 px Medium `#a7aebe`** + `▾` `431:142` 10 px `#6b7383` | `index.html:360-368`; `app.css:3007-3016` `.det-mode-row { … background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 8px; padding: 8px 11px }`, `app.css:3018-3021` `.det-mode-label { font-size: 11px; color: var(--sc-text-muted) }`, `app.css:3023-3033` `#detection-mode { font-size: 12px; font-weight: 600; color: var(--sc-text) }`; label text is `Mode` (no colon) | DRIFT (boxed control vs bare row; label 11 px vs 12 px and no colon; value 12 px `#f4f6fb` vs 13 px `#a7aebe`) | minor |
| `CON-110` | Mode options | frame shows only `Operator confirms` | `index.html:363-366` adds `Auto-stage (later)` and `Auto-approve (later)`, both `disabled` | EXTRA — correct per FR-115 (honest "later" affordances), frame owes them | minor |
| `CON-111` | **List gap** | `431:143` `gap-[12px]` between cards | `index.html:369` `<div id="detections-list" class="stream">`; `app.css:2817-2825` `.stream { … gap: 4px }` | DRIFT (4 vs 12 — the cards read as a solid block) | major |
| — | Card shell | `432:124` `bg #1c1f28`, border `#262a34`, `rounded-[12px]`, `px-[14px] py-[12px]`, `gap-[8px]` | `app.css:3046-3054` `.detection { display:flex; flex-direction:column; gap: 9px; padding: 12px 13px; border: 1px solid var(--sc-border); border-radius: 12px; background: var(--sc-elevated) }` | MATCH (px 13 vs 14, gap 9 vs 8 — 1 px each) | — |
| `CON-112` | Card head — reference | `432:126` **`Isaiah 61:5 · KJV`** as ONE string, **14 px SemiBold `#f4f6fb`** | `app.css:3062-3067` `.detection-head .ref { color: var(--sc-gold); font-weight: 700; font-size: 15px; flex: 1 }` plus a **separate** `app.css:3088-3095` `.detection-head .det-translation { font-size: 10px; font-weight: 600; letter-spacing: 0.03em; color: var(--sc-text-muted) }` | DRIFT — gold 15 px + a detached 10 px muted translation chip vs one white 14 px `ref · TRANS` string. `435:137` says "reference · translation" | major |
| `CON-113` | Match pill — confident (≥90) | `432:155` `bg #142721`, **no border**, `rounded-999`, `px-[8px] py-[3px]`; label `432:156` **11 px SemiBold `#35c090`** | `app.css:3071-3081` `.match-pill { font-size: 10px; font-weight: 700; border-radius: 999px; padding: 3px 9px; border: 1px solid var(--sc-preview-border); background: var(--sc-preview-soft); color: var(--sc-preview) }` | DRIFT (10 px/700 vs 11 px/600; has a border the frame omits; `#10231c`/`#35c08a` vs `#142721`/`#35c090`). `435:149` names `#35c08a` — so the frame's own `#35c090` is a **typo in the frame**; the implementation's token is right | minor |
| `CON-114` | Match pill — fuzzy (<90) | `432:127` `bg #2b230e`, no border; label `432:128` **11 px SemiBold `#f2b84b`** = `--sc-gold`; `435:137`/`435:149` confirm "gold #f2b84b (fuzzy match)" | `app.css:3083-3087` `.match-pill.fuzzy { border-color: var(--sc-warn-border); background: var(--sc-warn-soft); color: var(--sc-warn) }` = `#f5a524` on `#2a2415` | DRIFT — the implementation uses `--sc-warn`; the annotated spec says `--sc-gold`. Both pass AA; this is a semantics call, not a11y — see §9 Q5 | minor |
| — | Threshold | `435:137` "green ≥90, amber/gold when fuzzy" | `app.js:4122` `m.className = "match-pill" + (pct >= 90 ? "" : " fuzzy")` | MATCH (exact) | — |
| `CON-115` | Snippet | `432:129` **13 px** Regular `#a7aebe`, 2-line box (`h 32`) | `app.css:3097-3105` `.detection .snippet { font-size: 12px; color: var(--sc-text-secondary); line-height: 1.4; -webkit-line-clamp: 3 }` | DRIFT (12 px vs 13; 3-line clamp vs 2) | minor |
| `CON-116` | Provenance meta | `432:130` **12 px** Regular `#6b7383`, e.g. `Fuzzy quote · spoken 3s ago` / `Exact-text match · spoken 45s ago` | `app.css:3107-3110` `.detection .det-meta { font-size: 11px; color: var(--sc-text-muted) }`; built at `app.js:4135-4155` (`"spoken " + fmtAgo(agoS) + " ago"`) | DRIFT (11 px vs 12) + A11Y-DEFECT | major |
| — | Newest-first order | `435:136` | `app.js:4078` `const dets = (…).slice().reverse()` | MATCH | — |
| `CON-117` | Action buttons — box | `432:131` `gap-[8px]`, each `flex-[1_0_0]`, `px-[12px] py-[8px]`, `rounded-[9px]`, label **13 px Medium** | `app.css:3112-3120` `.detection-actions { display:flex; gap: 8px }`, `.detection-actions button { flex: 1; padding: 9px 6px; font-size: 12px; border-radius: 8px }` | DRIFT (radius 8 vs 9; 12 px vs 13; horizontal padding 6 vs 12) | minor |
| — | **Stage** | `432:132` `bg #6e5cf0` flat; label `432:133` `#f4f6fb` | `app.css:3122-3128` `.detection-actions .det-stage { background: var(--sc-primary); border: none; color: #fff; font-weight: 700 }` | MATCH on fill (white vs `#f4f6fb` is imperceptible); weight 700 vs 500 | — |
| `CON-118` | **Approve** | `432:134` **neutral**: `bg #1c1f28`, border **`#2b3040`**, label `#f4f6fb` | `app.css:3134-3140` `.detection-actions .det-approve { background: var(--sc-preview-soft); border: 1px solid var(--sc-preview-border); color: var(--sc-preview); font-weight: 700 }` — **green** | DRIFT — the console gives Approve a green "confirm" weight the frame gives it as a plain secondary. `#2b3040` is also a non-token border | major |
| `CON-119` | **Dismiss** | `432:136` **no fill, no border** (a bare text button); label `432:137` 13 px Medium `#a7aebe` | `app.js:4190` `mkAction("Dismiss", "", …)` — no class, so it falls through to `app.css:3847-3854` `button { background: var(--sc-elevated); border: 1px solid var(--sc-border) }` | DRIFT — Dismiss reads with the same visual weight as Approve; the frame deliberately de-emphasises it | major |
| `CON-120` | **What "Approve" does** | `unspecified` in the frame | `app.js:4182` `mkAction("Approve", "det-approve", "Approve " + d.reference + " and show it live", …)`; `app.css:3130-3133` comment: "Approve = accept AND go live (the fast path)" | UNSPECIFIED — and it **contradicts the mobile decision** (`MOBILE-2.0-SPEC.md` §7-Q6: "Approve", which *stages* to Preview, per FR-115). Two platforms, two meanings for the same word — see §9 Q7 | **blocker** |
| `CON-121` | Detections **empty state** | **not drawn** | `index.html:370-375` ✨ / "No scriptures detected yet." / "Scriptures spoken aloud surface here to stage in one tap. Automatic detection (R4) never stages or goes live on its own — it stays operator-confirmed (FR-115)."; `app.css:2788-2799` `.fwd-empty` | EXTRA / UNSPECIFIED (good copy; the frame owes a design) | major |
| `CON-122` | ≥3 cards visible | `435:135` | `app.css:2715-2720` `.rpanel { flex: 1; min-height: 0; overflow-y: auto }` inside a full-height column — at 848 px the panel clears 3 × 146 + gaps | MATCH | — |

## C.3 Service Timer tab — where `430:124` contradicts `323:124`

| # | Component | `323:124` (flagship) | `434:138` (this frame) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|---|
| `CON-123` | "SERVICE TIMER" label | `323:126` present | `434:140` **present**, with the RUNNING pill on the same row | `NOT FOUND` (see `CON-062`) | **MISSING** — both frames draw it, so this is no longer arguable | major |
| `CON-124` | Countdown container | `323:130` an **inset card**: `bg #0f1116`, border `#262a34`, `rounded-[13px]`, `py-[16px]` | `434:144` a **bare text**, no inset card at all | `app.css:3930-3936` `.timer-display { background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 13px; padding: 16px 12px }` | follows `323:130`. **Frames disagree** — see §9 Q2 | major |
| — | Countdown sub-line copy | `Sermon · counts down to 00:00` | `434:145` identical | `index.html:273` `Counts down to 00:00` | DRIFT (see `CON-065`) | — |
| `CON-125` | Unit caption copy | `HOURS` | `436:131` **`HOURS`** | `index.html:281` `HRS` | **MISSING/DRIFT** — both frames say HOURS (confirms `CON-066`) | major |
| `CON-126` | Panel footnote copy | `Shown on the stage output only` | `434:163` **`Custom time + presets · shown on the stage output only`** | `index.html:304` `Shown on the stage output only` | follows `323:150`; frames disagree — see §9 Q2 | minor |

---

# Frame D — `332:124` "SPEC — Detected Scriptures states" · 3456 × 523 · nine states

Panel width 360, "maps to console right rail" (`332:127`).

> **Frame conflict, resolved.** `332:124` and `430:124` draw the *same* detection card differently
> (`332:200` = **gold 15 px Bold** reference on a **status-tinted** card with a confidence bar;
> `432:124` = **white 14 px SemiBold** reference on a **neutral** card, no bar). The implementation
> follows `332:124` on the reference and `432:124` on the card fill — i.e. neither, consistently.
> See §9 Q2.

## D.1 State inventory — what exists at all

| State | Figma | Implemented | Verdict |
|---|---|---|---|
| 1 · Empty | `332:136` | `index.html:370-375` `#detections-empty` | partial — see `CON-127` |
| 2 · Listening / analysing | `332:156` | `NOT FOUND` (`grep -c Analysing` → 0 in `index.html`, `app.js`, `app.css`) | **MISSING** `CON-128` |
| 3 · High confidence | `332:189` | `app.css:3046-3140` `.detection` (untinted, no bar) | partial `CON-129`–`CON-133` |
| 4 · Low confidence + alternatives | `334:131` | `NOT FOUND` (`grep -c ALTERNATIVES` → 0) | **MISSING** `CON-134` |
| 5 · Auto-display mode | `334:172` | `NOT FOUND` (`grep -c "Auto-clears"` → 0; `#detection-mode` options `auto-stage`/`auto-approve` are `disabled`, `index.html:364-365`) | **MISSING** `CON-135` |
| 6 · On-air (approved) | `334:206` | `NOT FOUND` (`grep -c "Next verse"` → 0) | **MISSING** `CON-136` |
| 7 · Duplicate suppressed | `335:131` | `NOT FOUND` (`grep -c Cooldown` → 0) | **MISSING** `CON-137` |
| 8 · Detection history | `335:161` | `NOT FOUND` (no `Live`/`History` toggle in `#detections`) | **MISSING** `CON-138` |
| 9 · Provider unavailable | `335:210` | `NOT FOUND` (`grep -c "Retry detection"` → 0) | **MISSING** `CON-139` |

**Seven of nine states are entirely unbuilt.** This is the single largest surface-area gap in the audit.

## D.2 Per-state specification and verdicts

| # | Component | Figma spec (exact) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-127` | **1 · Empty** | `332:146` glyph `✦` 31 px box; `332:147` heading **"No scriptures detected yet"** 17 px box; `332:148` body "Spoken scriptures surface here to stage in one tap. On-device detection (R4) plugs in behind the transcript." | `index.html:371-374` glyph `✨`, msg `No scriptures detected yet.`, sub `Scriptures spoken aloud surface here to stage in one tap. Automatic detection (R4) never stages or goes live on its own — it stays operator-confirmed (FR-115).`; `app.css:2788-2799` `.fwd-empty { … border: 1px dashed var(--line); border-radius: 8px; color: var(--muted) }` | DRIFT — glyph `✨` vs the gold `✦` used as the panel's identity mark everywhere in this frame; copy rewritten; dashed border not drawn | minor |
| `CON-128` | **2 · Listening / analysing** | `332:166` an **11-bar waveform** (bars 4 px wide, 8 px pitch, heights 8/18/28/16/34/22/12/26/14/20/8, block 84 × 34); `332:178` a dot + **"Analysing speech…"** 16 px box; `332:181` "Detections appear the moment a reference or quote is recognised" | `NOT FOUND` | **MISSING** — while listening, the detections panel shows the *empty* state, which reads as "detection is off" | major |
| `CON-129` | **3 · Card tint by confidence** | `332:200` `bg #10231c`, border **`#1c3a2e` at `1.5px`**, `rounded-[12px]`, `px-[13px] py-[12px]`, `gap-[9px]` — the whole card carries the preview-green tint | `app.css:3046-3054` `.detection { … border: 1px solid var(--sc-border); background: var(--sc-elevated) }` — always neutral | DRIFT — the card never tints; confidence is carried only by the pill | major |
| `CON-130` | **3 · Confidence bar** | `332:205` a track `bg #0f1116`, `h-[5px]`, `rounded-[999px]`, full width, with a fill `332:206` `bg #35c08a` sized to the match % (`inset-[0_123px_0_0]` of 304 → 59.5 %… drawn at 181/304). Amber twin at `334:147/148` `bg #f5a524` | `NOT FOUND` — no bar element in `app.js:4083-4200` | **MISSING** — the only *non-textual, non-colour* representation of confidence | major |
| `CON-131` | **3 · Reference** | `332:202` **15 px Bold `#f2b84b`**, string `Romans 8:28 · KJV` | `app.css:3062-3067` `.detection-head .ref { color: var(--sc-gold); font-weight: 700; font-size: 15px }` | MATCH (exact) — confirms the implementation follows `332:124`, not `430:124` | — |
| `CON-132` | **3 · Snippet / meta** | `332:207` **12 px** Regular `#a7aebe` `leading-[1.35]`; `332:208` **11 px Medium `#6b7383`** | `app.css:3097-3105` `.snippet { font-size: 12px; color: var(--sc-text-secondary); line-height: 1.4 }`; `app.css:3107-3110` `.det-meta { font-size: 11px; color: var(--sc-text-muted) }` | MATCH — and **A11Y-DEFECT on `.det-meta`** (3.45 : 1 on `--sc-elevated`) | major |
| `CON-133` | **3 · Action buttons** | `332:209` `gap-[8px]`, each `flex-1`, `py-[9px]`, `rounded-[8px]`, 12 px; **Stage** `bg #6e5cf0` white Bold; **Approve** `bg #1c1f28` border `#262a34` ink **`#35c08a`** SemiBold; **Dismiss** `bg #1c1f28` border `#262a34` ink **`#6b7383`** SemiBold | `app.css:3112-3120` `padding: 9px 6px; font-size: 12px; border-radius: 8px`; `app.css:3122-3128` `.det-stage { background: var(--sc-primary); color: #fff; font-weight: 700 }`; `app.css:3134-3140` `.det-approve { background: var(--sc-preview-soft); border: 1px solid var(--sc-preview-border); color: var(--sc-preview); font-weight: 700 }`; Dismiss unclassed → base `button` (`app.css:3847-3854`) ink `--sc-text` | Stage MATCH; Approve DRIFT (green **fill+border** vs neutral fill with green ink only); Dismiss DRIFT (ink `#f4f6fb` vs `#6b7383`) | minor |
| `CON-134` | **4 · Low confidence + alternatives** | Card `334:142` `bg #2a2415`, border `#4a3a15` 1.5 px; pill `334:145` `bg #2a2415` border `#4a3a15` ink **`#f5a524`**; bar fill `#f5a524`; `334:151` **"ALTERNATIVES"** 9 px Bold `#6b7383` `tracking-[0.8px]`; alternative rows `334:152` `bg #0f1116` border `#262a34` `rounded-[8px]` `px-[10px] py-[8px]`, `justify-between`, name 12 px SemiBold `#a7aebe`, score 10 px Bold `#6b7383`; actions **Stage / Edit / Dismiss** | `NOT FOUND` — no alternatives list, and no **Edit** action anywhere in `app.js:4165-4200` | **MISSING** — a paraphrase detection currently offers only Stage/Approve/Dismiss with no way to pick the right reference | major |
| `CON-135` | **5 · Auto-display mode** | Header badge `334:177` **"auto"**; mode value `334:181` **"Auto ≥ 90%"**; card `334:183` `bg #2a1416` border `#5a2327` 1.5 px; `● LIVE` pill `334:186`; meta `334:190` "Auto-displayed · exact match 96%"; countdown strip `334:191` `bg #2a1416` border `#5a2327` `rounded-[8px]` `px-[10px] py-[7px]` ink `#ff4d4d` 11 px, text **"⏱ Auto-clears in 0:08 · hold to keep"**; actions `334:195` **Hold** `bg #6e5cf0` white 12 px Bold + `334:197` **Clear now** `bg #ff4d4d` **white 12 px Bold** | `NOT FOUND`; the two auto modes are `disabled` at `index.html:364-365` because "detections never auto-display (FR-115)" (`index.html:357-359`) | **MISSING by deliberate policy.** `334:172` designs a mode FR-115 forbids. Do **not** build it from the frame — see §9 Q8. Also: **white on `#ff4d4d` at 12 px Bold = 3.27 : 1 → A11Y-DEFECT** if it is ever built | major |
| `CON-136` | **6 · On-air (approved)** | Header badge `334:211` **"showing"**; card `334:217` `bg #2a1416` border `#5a2327` 1.5 px; pill `334:220` `● ON AIR` 10 px Bold `#ff4d4d`; meta `334:224` "Live on main output · staged 12s ago"; actions `334:226` **Clear output** `bg #ff4d4d` **white 12 px Bold** + `334:228` **Next verse** `bg #1c1f28` border `#262a34` ink `#6b7383` | `NOT FOUND` — once staged/approved, the card in the console is simply removed from the queue (`app.js:4165-4200`) | **MISSING** — the operator loses the link between "the verse on air" and "the detection that put it there". Note **white on `#ff4d4d` 12 px Bold = 3.27 : 1 → A11Y-DEFECT**; use the canonical `#a3283a` (7.19 : 1), matching the `#blackout` precedent at `app.css:4492-4494` | major |
| `CON-137` | **7 · Duplicate suppressed** | Card `335:140` `bg #0f1116` border `#262a34`, **`opacity-85`**; reference `335:142` **15 px Bold `#6b7383`** (de-emphasised); pill `335:143` **"DUPLICATE"** 10 px Bold `#6b7383` on `#1c1f28`/`#262a34`; body `335:145` 12 px `#6b7383`; cooldown strip `335:146` `bg #1c1f28` `rounded-[8px]` `px-10 py-7`, `⏱` `#6b7383` + **"Cooldown 1:20 remaining"** 11 px SemiBold `#a7aebe`; actions **Show anyway** / **Mute this verse**, both `bg #1c1f28` border `#262a34` ink `#a7aebe` 12 px | `NOT FOUND` — no duplicate suppression, no cooldown, no per-verse mute | **MISSING** — this is a *live-output flicker guard*, not cosmetics. **A11Y-DEFECT in the frame:** `#6b7383` at `opacity-85` on `#0f1116` = **3.16 : 1** for the reference (15 px, bold — 15 px bold is below the 18.66 px AA-large bar) and the body copy | major |
| `CON-138` | **8 · Detection history** | Segmented `335:166` `bg #0f1116` border `#262a34` `rounded-[8px]` `p-[3px]`, halves `flex-1` `py-[7px]` `rounded-[6px]`: inactive **"Live"** 12 px Medium `#a7aebe`; active **"History"** `bg #6e5cf0` white 12 px Bold. Rows `335:171` h 54 with reference 16 px box, an outcome badge (**STAGED / AUTO / DISMISSED**, 11 px), a `HH:MM` timestamp and a **↺ re-stage** button | `NOT FOUND` | **MISSING** — no audit trail; a dismissed detection is unrecoverable | major |
| `CON-139` | **9 · Provider unavailable** | Card `335:215` `bg #2a2415` border `#4a3a15`, `rounded-[12px]`, `px-[16px] py-[18px]`, `gap-[12px]`, centred; `⚠` `335:216` **22 px Bold `#f5a524`**; heading `335:217` **"Detection unavailable"** 14 px Bold `#f4f6fb`; body `335:218` 12 px Medium `#a7aebe` `leading-[1.4]` centred, **"The on-device detector isn't responding. Slides, search and staging are unaffected — you can still find and stage scriptures manually."**; button `335:219` full-width `bg #1c1f28` border `#262a34` `rounded-[9px]` `py-[10px]`, **"↻  Retry detection"** 12 px SemiBold `#f4f6fb` | `NOT FOUND` | **MISSING** — when the detector dies the panel shows the *empty* state, which is indistinguishable from "nothing said yet". This is the exact failure the architecture principle "no component failure may blank live output" is about, applied to the operator's mental model | **blocker** |
| `CON-140` | Panel identity mark `✦` | Every state header: `332:139` `✦` 12 px Bold **`#f2b84b`** + "DETECTED SCRIPTURES" 12 px Bold `#6b7383` `tracking-[1px]` | `NOT FOUND` — the tab label "Detected Scriptures" carries no `✦`; `app.css:3042-3044` `.det-star { color: var(--sc-gold) }` exists but `grep 'det-star'` finds no producer in `app.js` | **MISSING** (dead CSS class) | minor |
| `CON-141` | Header count badge variants | `332:194` **"1 new"**; `334:177` **"auto"**; `334:211` **"showing"** — the same slot carries three different states | `app.css:2706-2710` `.rtab .count-pill` shows only a bare number | MISSING (2 of 3 variants) | minor |

---

# Frame E — `563:201` "Live Console — Service Timer › Stage (theme + message)" · 864 × 726

This frame is **built**. It is the closest parity of any surface audited. Its own notes (`563:184`) are
the contract; the implementation satisfies all five.

| Note | Figma | Implemented |
|---|---|---|
| `563:188` PLACEMENT — "A segmented Timer \| Stage control at the top of the Service Timer tab… Detected Scriptures stays the sibling top tab." | — | `index.html:257-262` inside `#rpanel-timer`; `index.html:249-252` keeps the Detected tab a sibling | MATCH |
| `563:191` STAGE THEME — "Selecting sends `set_stage_template(worship\|scripture\|timer-only)`" | — | `app.js:3254-3259` `invoke("set_stage_template", { template: btn.dataset.template })` | MATCH |
| `563:194` STAGE MESSAGE — "Preset chip or custom text → `set_stage_message(text)`… Clear (or a blank message) removes it. **Bounded to 120 chars.**" | — | `app.js:3262`, `app.js:3267`, `app.js:3278` `invoke("set_stage_message", { text: "" })`; `index.html:340` `maxlength="120"` | MATCH |
| `563:197` AUDIENCE RULE — stage-only; "TIME UP is solid, never flashing (WCAG 2.3.1)" | — | copy at `index.html:348` "Shows on the confidence screen only — never the audience."; no flashing rule in `dist/` (enforced host-side) | MATCH |
| `563:200` TOKENS | — | see rows below | mostly MATCH |

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| `CON-142` | **`.seg` class collision** | n/a | `app.css:2623-2624` defines the segmented control `.seg { display: flex; gap: 3px; padding: 3px; margin-bottom: 12px; background: var(--sc-inset); border: 1px solid var(--line); border-radius: 9px }` — but `app.css:2831-2837` **re-declares the same class** for a transcript line: `.seg { display: flex; gap: 8px; align-items: baseline; font-size: 12px; line-height: 1.35 }`. Equal specificity, later wins → the Timer\|Stage control actually renders with **`gap: 8px`** and `align-items: baseline`, not the 3 px it was written for | — | **DRIFT caused by a defect in the code, not by the design.** Figma `563:133` is `p-[3px]` with no gap (halves are `flex-1`, flush) | major |
| — | Segmented shell | `563:133` `bg #0f1116`, border `#262a34`, `rounded-[9px]`, `p-[3px]`, halves `flex-1` flush | `app.css:2623-2624` (see above) | MATCH except `CON-142` | — |
| `CON-143` | Segment buttons | `563:134/136` `py-[6px]`, `rounded-[7px]`; inactive label `563:135` **13 px SemiBold `#6b7383`**; active `563:136` `bg #6e5cf0`, label `563:137` 13 px SemiBold **`#f4f6fb`** | `app.css:2625-2627` `.seg-btn { flex: 1; padding: 6px 0; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-weight: 600; font-size: 13px }`, `.seg-btn.active { background: var(--accent); color: #fff }` — `--muted` is `#a7aebe` (`app.css:11`), `--accent` is `#6e5cf0` (`app.css:12`) | DRIFT — inactive ink `#a7aebe` vs `#6b7383`. **The implementation is the accessible one** (8.49 : 1 vs 3.96 : 1 on `--sc-inset`); classify as INTENTIONAL where the frame is copied | minor |
| — | Section labels | `563:138` / `563:166` **11 px Bold `#6b7383` `tracking-[1px]`**, "STAGE THEME" / "STAGE MESSAGE" | `app.css:2636-2637` `.stage-sec-label { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--muted); margin: 14px 0 8px }` = `#a7aebe`; markup `index.html:307`, `index.html:334` | MATCH on type; ink brighter than the frame (again the accessible choice) | — |
| — | Theme card list gap | `563:124` `gap-[14px]` between all children | `app.css:2638` `.stage-themes { display: flex; flex-direction: column; gap: 8px }` | DRIFT — but the frame's 14 px is the *panel* gap, and the cards are siblings of the labels; `unspecified` for card-to-card | minor |
| `CON-144` | Theme card — inactive | `563:148` `bg #1c2029`, border `#262a34`, `rounded-[10px]`, `p-[11px]`, `gap-[12px]` | `app.css:2639-2641` `.stage-theme { display:flex; align-items:center; gap: 11px; width: 100%; text-align: left; padding: 10px 11px; border: 1px solid var(--line); border-radius: 10px; background: var(--sc-elevated); color: var(--text) }` = `#1c1f28` | MATCH — and the frame's `#1c2029` contradicts its **own** TOKENS note `563:200` ("card #1c1f28"). Frame slip; the code is right | minor |
| `CON-145` | Theme card — active | `563:139` `bg #211d3d`, `border-2 #6e5cf0`, `p-[11px]` | `app.css:2643-2644` `.stage-theme.active { border-color: var(--accent); border-width: 2px; padding: 9px 10px; background: rgba(110,92,240,.13) }` — resolves to ≈`#201f38` over `--sc-surface` | MATCH (≈2/255 per channel) | — |
| `CON-146` | Layout tile | `563:140` **32 × 32**, `rounded-[8px]`; Worship `#6e5cf0`, Scripture `#f2b84b`, Timer-only **`#4aa3ff`** | `app.css:2646-2649` `.stage-tile { width: 30px; height: 30px; border-radius: 8px }`, `.tile-worship { background: #6e5cf0 }`, `.tile-scripture { background: #f2b84b }`, `.tile-timer { background: #4aa3ff }` | DRIFT (30 vs 32). `#4aa3ff` is **not a `--sc-*` token** in either — see §9 Q6 | minor |
| `CON-147` | Theme card text | title `563:142` **14 px SemiBold `#f4f6fb`**; sub `563:143` **12 px Regular `#6b7383`**; column `gap-[3px]` | `app.css:2650-2652` `.stage-theme-txt { … gap: 2px }`, `strong { font-size: 14px; font-weight: 600 }`, `span { font-size: 12px; color: var(--muted) }` = `#a7aebe` | MATCH on type; ink brighter than frame (accessible); gap 2 vs 3 | minor |
| `CON-148` | TIME-UP indicator | `563:145` a **pill**: `bg #0f1116`, `rounded-[999px]`, `px-[8px] py-[3px]`, label `563:146` **9 px Bold `#6b7383` `tracking-[0.3px]`**; below it `563:147` region label **10 px SemiBold**, `#f2b84b` for region / `#ff4d4d` for full-screen; column `gap-[4px]`, right-aligned | `index.html:314` `<span class="stage-theme-tu">TIME UP<small>timer region</small></span>`; `app.css:2653-2656` `.stage-theme-tu { display:flex; flex-direction:column; align-items:flex-end; gap: 2px; font-size: 9px; font-weight: 700; letter-spacing: .4px; color: var(--muted); white-space: nowrap }`, `small { font-size: 10px; font-weight: 600; color: var(--warn-ink) }` = `#f2b53c`, `.up small { color: var(--live-ink) }` = `#ef4444` | DRIFT — **no pill background** on "TIME UP"; region ink `#f2b53c`/`#ef4444` (legacy vars) vs `#f2b84b`/`#ff4d4d` (Design 2.0 tokens); gap 2 vs 4 | minor |
| — | Preset chips | `563:168` `bg #0f1116`, border `#262a34`, `rounded-[999px]`, `px-[11px] py-[6px]`; label 11 px SemiBold `#a7aebe`; wrap, `gap-[8px]`; four presets: `WRAP UP · 2 MIN LEFT`, `SLOW DOWN`, `WRAP UP NOW`, `GREAT JOB` | `index.html:336-339` (identical four strings); `app.css:2657-2660` `.stage-presets { display:flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px }`, `.stage-preset { padding: 6px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--sc-inset); color: var(--muted); font-size: 11px; font-weight: 600 }` | MATCH (exact, including copy) | — |
| `CON-149` | Preset **selected** state | **not drawn** | `app.css:2661-2662` `.stage-preset.active { border-color: var(--accent); color: #b7abff; background: rgba(110,92,240,.14) }` | UNSPECIFIED | minor |
| — | Custom message field | `563:176` `bg #0f1116`, border `#262a34`, `rounded-[8px]`, `px-[11px] py-[9px]`; placeholder `563:177` 12 px Regular `#6b7383` **"Custom message…"** | `index.html:340-341`; `app.css:2664-2667` `.stage-msg-input { width: 100%; padding: 9px 11px; margin-bottom: 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--sc-inset); color: var(--text); font-size: 13px }`, `::placeholder { color: var(--muted) }` | MATCH on box; input text 13 px vs the frame's 12 px | minor |
| `CON-150` | "Send to stage" | `563:179` `bg-gradient-to-r from-[#7e6eff] to-[#6e5cf0]`, `rounded-[9px]`, `py-[9px]`, `flex-1`; label `563:180` **13 px Bold `#f4f6fb`** → **3.78 : 1 on the light stop** at 13 px Bold (below the 18.66 px AA-large bar) | `app.css:2670-2671` `.stage-msg-send { flex: 1; padding: 9px 0; border: 0; border-radius: 9px; background: var(--accent); color: #fff; font-weight: 700; font-size: 13px }` — **flat `#6e5cf0`**, 4.72 : 1 | **INTENTIONAL-DEVIATION (permanent)** — same rule as `CON-007`; `test_tokens.rs:585-592` forbids small white labels on the gradient | — |
| — | "Clear" | `563:181` `bg #0f1116`, border `#262a34`, `rounded-[9px]`, `px-[16px] py-[9px]`; label 13 px SemiBold `#a7aebe` | `app.css:2672-2674` `.stage-msg-clear { padding: 9px 16px; border: 1px solid var(--line); border-radius: 9px; background: var(--sc-inset); color: var(--muted); font-weight: 600; font-size: 13px }` | MATCH (exact) | — |
| — | Row gap | `563:178` `gap-[8px]` | `app.css:2669` `.stage-msg-row { display: flex; gap: 8px }` | MATCH | — |
| — | Footnote | `563:183` **11 px Regular `#6b7383`**, "Shows on the confidence screen only — never the audience." | `index.html:348` `<span class="timer-note">Shows on the confidence screen only — never the audience.</span>`; `app.css:4073-4077` `.timer-note { color: var(--sc-text-muted); font-size: 11px; text-align: center }` | MATCH on copy; A11Y-DEFECT on ink (3.79 : 1) — §8.4 | major |
| `CON-151` | Active-message readout | **not drawn** | `index.html:346` `<div id="stage-msg-active" role="status" aria-live="polite" hidden>`; `app.css:2676-2677` `.stage-msg-active { margin-top: 8px; font-size: 12px; font-weight: 600; color: var(--warn-ink) }` | EXTRA — a needed confirmation the frame omits (the operator otherwise cannot see what is on the stage screen right now) | major |
| `CON-152` | Tab header in this frame | `563:127` active tab **14 px SemiBold**, underline `563:128` `bg #6e5cf0` `h-[2px]` **`w-[84px]`, `rounded-[2px]`** — i.e. the underline hugs the *label*, not the tab; count badge `563:131` `bg #29244d`, ink `#b8abff`, 10 px Bold `tracking-[0.3px]` | `app.css:2678-2710` (see `CON-105`/`CON-107`) — full-tab underline, `rgba(110,92,240,.22)`, `#b7abff`, 11 px | DRIFT — and a **third** rendering of the same tab bar. `443:124`, `431:127` and `563:125` all differ. See §9 Q2 | minor |

---

# Frame F — `462:124` "NDI OUTPUT — states (Design 2.0)" · 1184 × 541 · six states

The frame's own caption `462:126` states the intent precisely:

> "States 1–3 match the shipped console (state 3 is on frame 327-124). **States 4–6 exist in the
> controller (`set_ndi_output` validation + the ndi feature gate); the feedback shown is a PROPOSED
> treatment — today the build reverts the toggle silently / still shows "Broadcasting".**"

So states 4–6 are a designed fix for a **known real defect**, tagged `PROPOSED` in the frame itself.
The implementation lives in `app.js:1150-1188` (built dynamically for Audience-class screens only).

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Section title "NDI OUTPUT" | `462:194` **11 px Bold `#6b7383` `tracking-[1px]`** | `app.js:1151` `section("NDI OUTPUT")`; `app.css:2394-2399` `.scr-isection-title { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--sc-text-muted) }` | MATCH; A11Y-DEFECT on ink (3.79 : 1) — §8.4 | major |
| — | Section box | `462:193` `px-[16px] py-[15px]`, `gap-[10px]` | `app.js:985-992` `section()`; padding from the inspector shell | MATCH (approx) | — |
| — | Row | `462:195` `justify-between`, `items-center` | `app.css:2406-2411` `.scr-irow { display:flex; align-items:center; justify-content:space-between; gap: 10px }` | MATCH | — |
| — | "Source name" label | `462:196` **13 px Medium `#a7aebe`** | `app.css:2413-2417` `.scr-irow-label { font-size: 13px; font-weight: 500; color: var(--sc-text-secondary) }` | MATCH (exact) | — |
| `CON-153` | Source-name field | `462:197` `bg #0f1116`, border `#262a34`, `rounded-[8px]`, **`px-[11px] py-[8px]`**, **`w-[196px]` fixed**; value/placeholder `462:198` **12 px SemiBold `#6b7383`** | `app.js:1155-1159`; `app.css:2442-2453` `.scr-input { background: var(--sc-inset); border: 1px solid var(--sc-border); color: var(--sc-text); border-radius: 8px; padding: 8px 11px; font-size: 12px; font-weight: 600; max-width: 60% }` | MATCH on chrome; width `max-width: 60%` vs a fixed 196 px | minor |
| — | Placeholder copy | `462:198` "e.g. SelahCue Program" | `app.js:1159` `nameInput.placeholder = "e.g. SelahCue Program"` | MATCH (exact) | — |
| `CON-154` | Placeholder ink | `#6b7383` | `app.css:2455-2458` `.scr-input::placeholder { color: var(--sc-text-muted); font-weight: 500 }` | A11Y-DEFECT (3.96 : 1 at 12 px) — §8.4 | major |
| — | Toggle | `462:201` **42 × 24** | `app.css:2275-2282` `.scr-toggle { width: 42px; height: 24px }`; knob `app.css:2293-2312` 18 px, `left: 2px` → `22px` when checked; on-fill `var(--sc-primary)` | MATCH (exact) | — |
| — | State 1 · Off (default) | `462:146` "NDI off — set a source name and enable to broadcast on the network" | `app.js:1185` identical string; `.scr-signal scr-signal-neutral` (`app.css:2487-2493`, `2513-2517`) | MATCH (exact copy) | — |
| — | State 2 · Named · off | `462:165` same message with a filled field | `app.js:1183-1186` — the same `else` branch | MATCH | — |
| — | State 3 · Broadcasting | `462:184` **"● Broadcasting NDI · SelahCue Program"** | `app.js:1181-1183` `st.classList.add("scr-signal-ok"); st.textContent = "● Broadcasting NDI · " + cfg.ndi_name` | MATCH (exact copy) | — |
| `CON-155` | Signal-line chrome | `462:184` a **plain text line**, 12 px Medium (green `462:184` / `#f2b84b` for warnings) — no fill, no border | `app.css:2487-2493` `.scr-signal { border-radius: 9px; padding: 10px 12px; font-size: 11px; font-weight: 600; border: 1px solid transparent }` + tinted variants | DRIFT — the console renders these as filled chips, the frame as bare lines | minor |
| `CON-156` | **State 4 · Rejected — empty name** | `462:203` **"⚠ Enter a source name before enabling NDI"** 12 px Medium **`#f2b84b`**; field shows the placeholder; toggle reverts **off** | `NOT FOUND` — `app.js:1166` fires `set_ndi_output` and `app.js:1169-1178` relies on the host rejecting it; **no message is ever rendered**. The comment at `app.js:1176-1177` says "enabling with an empty name is rejected by the host and reverts, so the control never lies" — true, but silent | **MISSING** — the toggle flips back with no explanation | major |
| `CON-157` | **State 5 · Rejected — name in use** | `462:222` **"⚠ "SelahCue Program" is already broadcasting on another output"**; `462:216` the field gains a **`#f2b84b` border** (visible in the render at `462:216`) | `NOT FOUND` — no duplicate-name feedback, and no error styling on `.scr-input` (`app.css:2470-2473` `.scr-select.mismatch` exists for the *select*, but there is no `.scr-input.mismatch`) | **MISSING** | major |
| `CON-158` | **State 6 · Runtime unavailable** | `462:241` **"⚠ NDI runtime unavailable — build with the ndi feature to broadcast"**; the whole section renders **dimmed** and the toggle is disabled (`462:239`) | `NOT FOUND` — the section is rendered at full strength on a build without `--features ndi`, and the toggle is enabled | **MISSING** — the operator can toggle a control that cannot possibly work, and gets no explanation. This is exactly the "honest affordance" rule the project applies elsewhere (`index.html:364-365` disables the unbuildable detection modes) | **blocker** |
| `CON-159` | Warning ink | all three warnings use **`#f2b84b`** (`--sc-gold`) | n/a — `app.css:2501-2505` `.scr-signal-warn` uses `--sc-warn` `#f5a524` | UNSPECIFIED conflict — the frame says gold, the token layer says warn. Same question as `CON-114`; see §9 Q5 | minor |
| `CON-160` | Disabled-section treatment | `462:231-239` dimmed labels + a dimmed toggle | `NOT FOUND` — but note **`.scr-card.screen-disabled` dimming was deliberately narrowed to `.scr-thumb` only** in a prior a11y pass (whole-card `opacity: 0.5` put the only route back to an output window at 1.8 : 1). **Any `state-6` dimming must follow that precedent**: dim the *illustrative* part, never the controls or the explanation | INTENTIONAL constraint on how to build `CON-158` | — |

---

# Frame G — `346:124` "SPEC — System & Recovery States" · 2586 × 486 · six states

`346:127`: "How the app behaves when things go wrong — **reliability is the product's first promise**".
This frame is the design counterpart of the architecture principle "no component failure may blank
live output". It is also the least-implemented frame after Frame D.

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **G.1 · Blackout active — `346:133`** |
| `CON-161` | Monitor pills flip to a black state | `346:137` PREVIEW pill re-tints **red** (`bg #2a1416` border `#5a2327` ink `#ff4d4d`) even for Preview; `346:144` `LIVE · BLACK` | `app.css:3685-3689` `.panel-pill.preview` is always green; `app.css:3691-3695` `.panel-pill.live` is always red; label text is fixed in `index.html:157` / `index.html:172` | **MISSING** — during a blackout the Preview pill still reads `PREVIEW · STAGED` in green | major |
| `CON-162` | Monitor surface goes black with a `— BLACK —` marker | `346:140` / `346:147` `bg-black`, `border-2` (green for preview / `#ff4d4d` for live), `rounded-[10px]`, centred label **"— BLACK —"** 12 px Bold **`#3a3a3a`** | `index.html:176` `<span id="live-black">BLACKOUT — OUTPUT DARK</span>`; `app.css:3805-3823` `#live-black { color: #fff; font-size: 12px; font-weight: 800; letter-spacing: .08em; border: 1px solid var(--live-ink); border-radius: 4px; padding: 3px 8px }`, `#live-panel.blackout .surface .big, … .cap { opacity: 0.25 }` | DRIFT — different copy, different treatment, and it applies to the **Live panel only**; the frame blacks **both** monitors | major |
| `CON-163` | `#3a3a3a` on black | `346:141` — **1.85 : 1** at 12 px Bold | n/a | **A11Y-DEFECT in the frame.** The marker is the only cue that a black rectangle is *deliberately* black rather than broken. Minimum `#767676` (4.62 : 1 on black) — see §8.2 | major |
| `CON-164` | Blackout banner strip | `346:149` `bg #1a0c0c`, border `#5a2327`, `rounded-[11px]`, `px-[15px] py-[12px]`, `gap-[12px]` — sits **inside the console card**, not in the footer | `NOT FOUND` | **MISSING** — the second, console-level rendering of the `337:199` banner (see `CON-098`) | major |
| — | "■ BLACKED OUT" button | `346:150` `bg #ff4d4d`, `rounded-[9px]`, `px-[14px] py-[10px]`; label 13 px Bold **white** (**3.27 : 1**) | `app.js:313` `blackout-state` = `"ON"` only | MISSING; and the frame's white-on-`#ff4d4d` is an A11Y-DEFECT — use `#a3283a` per `CON-071` | major |
| — | Explanation | `346:152` **"Audience sees nothing · press B or click to restore"** 12 px SemiBold `#e8b4b4` | `NOT FOUND` | MISSING — cf. `CON-101` (`337:209` uses different wording for the same idea; see §9 Q2) | major |
| — | "↺ Restore" | `346:153` `bg #35c08a`, `rounded-[9px]`, `px-[14px] py-[10px]`; label 13 px Bold **`#06231a`** (**7.17 : 1**, passes) | `NOT FOUND` | MISSING — cf. `CON-102` | **blocker** |
| **G.2 · Network lost — `346:159`** |
| `CON-165` | Network-lost banner | `346:160` `bg #2a2415`, border `#4a3a15`, `rounded-[11px]`, `px-[14px] py-[12px]`, `gap-[11px]`; `⚠` 16 px Bold `#f5a524`; title **"Network lost"** 13 px Bold `#f4f6fb`; sub **"Mobile remotes are paused"** 11 px Medium `#f5a524` | `NOT FOUND` — the only signal is the topbar pill text change (`app.js:5330` `label.textContent = ok ? "Connected" : "Reconnecting…"`) | **MISSING** — nothing tells the operator that *mobile remotes* specifically are paused | major |
| `CON-166` | Retry-attempt row | `346:165` `bg #0f1116`, border `#262a34`, `rounded-[10px]`, `px-[13px] py-[11px]`, `gap-[9px]`; a 14 px spinner ellipse; **"Reconnecting… attempt 3"** 12 px SemiBold `#a7aebe` | `app.js:5330` shows `Reconnecting…` with **no attempt count**; `app.css:270-278` `.tb-conn.reconnecting` warn tint | DRIFT — no attempt counter, no spinner | minor |
| `CON-167` | Reassurance row | `346:168` `bg #10231c`, border `#1c3a2e`, `rounded-[10px]`, `px-[13px] py-[11px]`; `✓` 13 px Bold + **"Slides, outputs & timers keep running — all local"** 11 px SemiBold, all `#35c08a` | `NOT FOUND` | **MISSING** — this line is the whole point of "offline-first" for the operator under pressure | major |
| **G.3 · Output lost → auto-recovery — `346:175`** |
| `CON-168` | Signal-lost output card | `346:176` `bg #2a1416`, border `#5a2327`, `rounded-[12px]`, `p-[13px]`, `gap-[9px]`; title `346:178` "Stage Display" 14 px Bold; pill `346:179` **`● SIGNAL LOST`** 10 px Bold `#ff4d4d` on `#2a1416`/`#5a2327` | `app.js:863` `else { variant = "warning"; label = "NO SIGNAL" }` — a **warn/amber** chip, and the copy is `NO SIGNAL` | DRIFT — amber not red, `NO SIGNAL` not `SIGNAL LOST`, and no card re-tint | major |
| `CON-169` | Held-last-frame explanation | `346:182` **"HDMI-2 disconnected. Other outputs are unaffected — this display held its last frame."** 12 px Regular `#a7aebe` `leading-[1.35]` | `NOT FOUND` (`grep -c "held its last frame"` → 0) | **MISSING** — the never-blank guarantee (NFR-024) is invisible to the operator | major |
| `CON-170` | Auto-reconnect strip | `346:183` `bg #1c1f28`, `rounded-[8px]`, `px-[11px] py-[8px]`, `gap-[9px]`; `↻` 12 px Bold **`#38bdf8`**; **"Auto-reconnecting… attempt 2 of ∞"** 11 px SemiBold `#a7aebe` | `NOT FOUND` | **MISSING** — the only use of `--sc-info` as a *working-on-it* colour anywhere in the design | major |
| `CON-171` | Recovery confirmation | `346:186` `bg #10231c`, border `#1c3a2e`; `✓` + **"Stage Display reconnected · resumed automatically"** 11 px SemiBold `#35c08a` | `NOT FOUND` | **MISSING** | major |
| **G.4 · Empty service plan — `347:128`** |
| `CON-172` | Console plan empty state | `347:133` `py-[26px]`, centred, `gap-[10px]`: icon tile `347:134` **54 × 52**, `bg #0f1116`, border `#262a34`, `rounded-[14px]`, glyph `☰` 22 px Bold `#6b7383`; heading `347:136` **"Your plan is empty"** 15 px Bold `#a7aebe`; body `347:137` **"Add a song, scripture, or slide to build your order of service."** 12 px Medium `#6b7383` `leading-[1.4]`, `w-[260px]`, centred | `NOT FOUND` for `#plan` — see `CON-021`. The **Service Plan surface** has a *different* empty state: `app.js:6386-6409` heading "Build your service plan", body "Add songs, scriptures, and presentations to the run sheet, then link content to each item.", `＋ Add first item`, plus "Start from a template · Duplicate a past plan · Import — coming soon"; `app.css:6002-6006` | **MISSING** on the console; DRIFT (different copy) on the plan surface | major |
| `CON-173` | Empty-plan actions | `347:139` **"+ Add first item"** `bg #6e5cf0` flat, `rounded-[10px]`, `py-[11px]`, 13 px Bold white; `347:141` **"Import…"** `bg #1c1f28` border `#262a34`, 13 px SemiBold `#a7aebe`; row `gap-[9px]`, both `flex-1` | `app.js:6396-6398` `＋ Add first item` (full-width `＋`, not `+`), on the plan surface only; **Import is an honest "coming soon" line** (`app.js:6404-6405`) not a button | DRIFT — `Import…` is drawn as a live secondary button in the frame but is not buildable today. The implementation's "coming soon" line is the honest treatment; the **frame** should be corrected | minor |
| **G.5 · Crash recovery — `347:147`** |
| `CON-174` | Crash-recovery dialog | Card `347:147` `bg #1c1f28`, border **`rgba(110,92,240,0.4)`**, `rounded-[14px]`, `pt-[22px] pb-[20px] px-[20px]`, `gap-[14px]`; badge `347:148` **46 × 48**, `bg #10231c` border `#1c3a2e` `rounded-[13px]`, `↺` 22 px Bold `#35c08a`; heading `347:151` **"Welcome back — session recovered"** 18 px Bold `#f4f6fb`; body `347:152` "SelahCue closed unexpectedly during "Sunday Service". Your plan, themes, slides and edits were autosaved and are safe." 13 px Medium `#a7aebe` `leading-[1.45]`; autosave chip `347:153` `bg #0f1116` border `#262a34` `rounded-[8px]` `px-[12px] py-[9px]`, `💾` 12 px `#6b7383` + "Autosaved 10:47 AM · 12 seconds before the crash" 11 px SemiBold `#a7aebe`; actions `347:157` **"Restore session"** `bg #6e5cf0` `rounded-[11px]` `py-[13px]` 14 px Bold white / `347:159` **"Start fresh"** `bg #14161d` border `#262a34` 14 px SemiBold `#a7aebe`, `gap-[10px]`, both `flex-1` | `NOT FOUND` — no crash-recovery dialog exists anywhere in `dist/` (`grep -c "recovery"` → 0, `grep -c "autosave"` → 0) | **MISSING (whole feature)** — this is a product promise ("your work is safe") with no UI at all | **blocker** |
| **G.6 · Missing media fallback — `347:165`** |
| `CON-175` | Fallback preview | `347:166` `bg-gradient-to-b from-[#241c4a] to-[#0e1016]`, `h-[180px]`, `rounded-[11px]`; missing-image placeholder `347:167` `bg rgba(255,255,255,0.05)`, **`border-[1.5px] border-dashed rgba(255,255,255,0.18)`**, `rounded-[10px]`, `w-[120px]`, `🖼` 18 px white; the lyric "Amazing Grace" 30 px Bold white still renders | `app.js:4733` `else thumbFail(cv); // missing media / no frame → honest "can't preview" (never a silent blank)`; `app.css:5790` `.pm-tile-failmsg` | DRIFT — the console shows a generic "can't preview" tile, not the frame's *composited-with-a-hole* preview | major |
| `CON-176` | Missing-media warning | `347:170` `bg #2a2415`, border `#4a3a15`, `rounded-[9px]`, `px-[12px] py-[10px]`, `gap-[9px]`; `⚠` 13 px Bold + **""Harvest field.jpg" is missing — showing background only. Audience never sees an error."** 11 px SemiBold, both `#f5a524` | `NOT FOUND` — `app.js:4831` `"Presentation missing — the linked deck was removed."` is the nearest, and it is about a *deck*, not a media file | **MISSING** — no per-asset missing-media message | major |
| `CON-177` | Missing-media actions | `347:174` **"Locate file"** / `347:176` **"Replace image"**, both `bg #1c1f28` border `#262a34` `rounded-[9px]` `py-[10px]` 12 px SemiBold `#a7aebe`, `flex-1`, `gap-[8px]` | `NOT FOUND` | **MISSING** — no recovery path from a missing asset | major |
| `CON-178` | `#241c4a` / `#0e1016` | `347:166` — a **third** on-air wash, different from `#0f1d3a` (`322:131`, desktop) and `#231B48` (mobile) | n/a | see §9 Q6 | minor |
| `CON-179` | `#08090d` | `346:124` frame ground — darker than `--sc-base #0b0d12` | presentation-only (spec-sheet ground) | not a product colour; ignore | — |

---

# 8. Accessibility — NFR-020 findings

**The bar** (`docs/product/prds/SelahCue-PRD.md:396`, NFR-020, MVP): *"Operator UI meets WCAG 2.1 AA
contrast (≥4.5:1 normal text, ≥3:1 large text/UI)."* Two thresholds. AA-large applies at **≥24 px
regular or ≥18.66 px bold** — nothing smaller qualifies, whatever its role.

All ratios below are computed from the pinned hexes to WCAG 2.1 relative luminance.

## 8.1 The three deviations that are already correct — do not "fix" them

These sit in the documented review block at `app.css:4470-4545` ("Review fixes (adversarial a11y +
design-fidelity pass). Kept as one block, placed last, so it wins by source order… Each rule cites the
finding it resolves."). **The frames are what is wrong here.**

| Control | Figma draws | Console ships | Measured | Verdict |
|---|---|---|---|---|
| `.tb-golive` (`CON-007`) + `.timer-start` (`CON-067`) | `#7e6eff → #6e5cf0` with white 13 px | `app.css:4505-4507` `linear-gradient(90deg, var(--sc-primary), #5a48d0)` | white on `#7e6eff` = **3.78 : 1** → shipped **4.72 : 1 → 6.42 : 1** | INTENTIONAL-DEVIATION (permanent). Pinned by `test_tokens.rs:585-592`, which allows the token at AA-large but forbids small white body text on it |
| `#blackout` (`CON-071`) | `#ff4d4d → #d8362f` with white 13 px | `app.css:4492-4496` `linear-gradient(90deg, #a3283a, #8f2030)` | white on `#ff4d4d` = **3.27 : 1** at 13 px → shipped **7.19 : 1** | INTENTIONAL-DEVIATION (permanent) |
| `button.golive` (`CON-044`) | the **console** frame `322:153` already draws the dark ink `#06231a` | `app.css:3896-3899` `color: #06231a` on `#3ed39a → #28a579` | **8.70 : 1 / 5.34 : 1** | MATCH — no conflict on this control. The *mobile* frames drew white here; the desktop frame did not |

Also intentional, from the same block and a later Screens pass — **do not close these toward the frames**:

- `.card-head h2`, `aside h2`, `.scrip-note`, `.timer-custom-label`, `.det-mode-label`, `.cmd-empty`,
  `#emergency .note` promoted from `--sc-text-muted` to `--sc-text-secondary` (`app.css:4480-4489`).
- `.scr-card-meta` moved off `--sc-text-muted` to a brighter ink (8.12 : 1).
- `.scr-card.screen-disabled` dimming narrowed to `.scr-thumb` only — whole-card `opacity: 0.5` put the
  only route back to an open output window at 1.8 : 1. **`CON-158`/`CON-160` must respect this.**
- A `CLOSED` status pill and window-language wording (`No output window`), excluded from virtual screens.

`scripts/operator_headless.py` (640 checks / 0 FAIL) asserts computed opacity and real client rects to
stop these regressing. Any change in this audit must keep it green.

## 8.2 Genuine violations — fails **both** thresholds, no usage makes them compliant

| # | Where | Pairing | Ratio | Status |
|---|---|---|---|---|
| `CON-046` | `button.golive .key` — the **"⏎ Enter"** hint on GO LIVE | white on `rgba(255,255,255,0.18)` over `#3ed39a → #28a579` | **1.72 : 1** (Figma `322:154/155` draws the same at `0.16` → **1.74 : 1**) | **BLOCKER — live in the shipped console today.** Fails AA-normal *and* AA-large at 11 px. Fix: use the same dark ink as the label — `color: #06231a` on `rgba(6,35,26,0.14)`, or drop the chip's translucent fill and set `color: #06231a; background: rgba(0,0,0,0.10)`. Do **not** darken the button; its label is already 8.70 : 1 |
| `CON-163` | `— BLACK —` marker on the blacked monitor (`346:141`) | `#3a3a3a` on `#000000` | **1.85 : 1** | Frame-only (not built). If `CON-162` is built, use ≥ `#767676` (**4.62 : 1**) |

## 8.3 White on solid live-red — compliant only above 18.66 px bold

`white` on `--sc-live #ff4d4d` is **3.27 : 1** — clears AA-large, fails AA-normal. Every drawn use is
**below** the large-text bar, so each is a violation *as drawn*:

| Node | Text | Size | Verdict |
|---|---|---|---|
| `337:206` `BLACKED OUT` | 13 px Bold | 13 px | fails — build with `#a3283a` (7.19 : 1) |
| `334:198` `Clear now` | 12 px Bold | 12 px | fails |
| `334:227` `Clear output` | 12 px Bold | 12 px | fails |
| `346:151` `■ BLACKED OUT` | 13 px Bold | 13 px | fails |
| `app.css:4218-4222` `#clear-all.armed` | inherits `button` 14 px 600 on `--sc-live` | 14 px | **fails, and it is shipped** (`CON-074`) |

`#ff4d4d` **as a chip ink on its soft tint** (`--sc-live-soft`) is 5.31 : 1 and fine — the problem is
only white **on** the solid fill. The project already has the answer: `#a3283a`, used at
`app.css:4492-4496`.

## 8.4 `--sc-text-muted` — a pre-existing, shipped AA failure

`--sc-text-muted #6b7383` measured on the four neutral grounds:

| Ground | Ratio | AA-normal (4.5) | AA-large (3.0) |
|---|---:|---|---|
| `--sc-base #0b0d12` | 4.08 | **fail** | pass |
| `--sc-surface #14161d` | 3.79 | **fail** | pass |
| `--sc-elevated #1c1f28` | 3.45 | **fail** | pass |
| `--sc-inset #0f1116` | 3.96 | **fail** | pass |
| `#12090b` (emergency footer) | 4.12 | **fail** | pass |

`--sc-text-secondary #a7aebe` for comparison: **7.40 – 8.74 : 1** — clears AA everywhere.
`test_tokens.rs:536` audits `text-muted` deliberately at AA-large, "tertiary/label-only… it must NOT
carry essential small body text".

**A triage already ran** (comments at `app.css:~1721`, `~2250`, `~4474`): *"essential small text is
promoted to `--sc-text-secondary`; supplementary micro-text — unit captions, kbd hints, resolution,
placeholders, count pills — stays muted."* Six selectors were promoted at `app.css:4480-4489`.

**The residual exposure is that the triage's category does not exist in the spec.** WCAG 1.4.3 exempts
*incidental* text — "decoration, formatting, invisible, or… part of a picture that contains significant
other visual content" — and logotypes. It does **not** exempt "supplementary". A resolution readout, a
placeholder, a count pill and a keyboard hint are all informational: a sighted user reads them to
operate the product. They are in scope.

**Measured position at HEAD**: 105 `var(--sc-text-muted)` call sites in `dist/app.css`. Classified in
**Appendix A**:

| Class | Count |
|---|---:|
| **VIOLATION** — informational text below the large-text bar | **88** |
| EXEMPT — incidental (carets, icon glyphs, dots, thumbnail placeholders, an `aria-hidden` separator) | 10 |
| EXEMPT — AA-large (`.ps-dial-glyph`, 34 px bold) | 1 |
| DEAD — the muted declaration is overridden to `--sc-text-secondary` at `app.css:4480-4489` | 6 |
| **Total** | **105** |

Smallest violating site: `.hms-cap` at **9 px** (`app.css:4021`). The bulk sit at 10–12 px.
**Zero sites qualify for AA-large.**

### 8.4.1 Recommended fix — a second muted token, not a blanket swap

Mapping all 88 to `--sc-text-secondary` would clear NFR-020 but flatten the three-step ink hierarchy
(`text` → `secondary` → `muted`) the whole design depends on: `SERVICE PLAN` headings, `1920 × 1080`,
`spoken 4s ago` and body copy would all become the same grey. That is a real design regression.

**Proposal — add a compliant tertiary ink and demote `--sc-text-muted` to non-text use only.**

```
--sc-text-tertiary: #828b9c;   /* NEW — small informational text */
--sc-text-muted:    #6b7383;   /* UNCHANGED — decoration only: carets, glyphs, dots, rules */
```

`#828b9c` measured (same cool-slate hue family, one step lighter):

| Ground | base | surface | elevated | inset | `#12090b` | `#1a0c0c` |
|---|---:|---:|---:|---:|---:|---:|
| `#828b9c` | **5.67** | **5.27** | **4.80** | **5.51** | **5.72** | **5.56** |

It clears AA-normal on every ground including the worst (`elevated`, 4.80) and stays visibly one step
below `--sc-text-secondary` (5.27 vs 8.12 on surface), so the hierarchy survives.

**This is a four-surface lockstep change**, because `--sc-text-muted` is cross-checked by
`selahcue-present/tests/test_tokens.rs::design2_palette_is_pinned_across_surfaces` against
`dist/app.css`, `tokens::design2::MANIFEST`, `StageTheme::dark()` **and**
`implementation/mobile/.../design_tokens.dart` (a source-text grep for the literal
`d2<Camel> = Color(0xFF<HEX>)` — even reformatting breaks the Rust test).

**Note the proposal adds a token and changes no existing value**, so the pin stays green as-is; the
new member needs adding to all four surfaces together plus a `design2_palette_meets_wcag_aa` case.
Mobile has the identical problem with `d2TextMuted` and would take `d2TextTertiary` in the same pass.

**Fallback if the owner rejects a palette addition:** map all 88 to `--sc-text-secondary` and accept the
flattened hierarchy. Not recommended — but it is compliant, needs no token change, and is what mobile
did (`MOBILE-2.0-SPEC.md` §2.3: "`textMuted` maps to `d2TextSecondary`, **never** to `d2TextMuted`").

## 8.5 Lower-stakes ink conflicts where the code is already better

Not violations by the code, only places the frames are dimmer than the code. Leave the code alone.

| # | Element | Figma | Console | Note |
|---|---|---|---|---|
| `CON-027` | transcript partial line | `#6b7383` @ `opacity-60` → **2.16 : 1** | `app.css:2853-2859` `--sc-text-secondary` @ 0.75 → ≈5.3 : 1 | frame fails; code passes |
| `CON-143` | Timer\|Stage inactive segment | `#6b7383` → 3.96 : 1 on inset | `app.css:2626` `var(--muted)` `#a7aebe` → 8.49 : 1 | frame fails; code passes |
| `CON-147` | stage-theme sub-label | `#6b7383` | `app.css:2652` `#a7aebe` | frame fails; code passes |
| `CON-137` | duplicate card reference | `#6b7383` @ `opacity-85` on `#0f1116` → **3.16 : 1** at 15 px Bold | not built | build at full opacity with `--sc-text-tertiary` |

## 8.6 Non-contrast accessibility gaps found

| # | Gap | Where |
|---|---|---|
| `CON-054` | **Staged verse is signalled by colour alone** (WCAG 1.4.1). `app.css:3614-3620` `.verse.cursor` changes only background/border/ink; the frame's `STAGED` pill (`322:181`) is not built | Scriptures |
| `CON-068` | Disabled timer controls at `opacity: 0.4` ≈ 2.0 : 1 (`app.css:4061-4065`). Disabled controls are exempt from 1.4.3, but Pause/Reset are the *normal resting state* of the panel, so the panel reads as broken at rest | Timer |
| `CON-101` | The most destructive state in the product (blackout) has **no text explanation** in the shipped UI | Emergency |
| `CON-141` | The tab count badge is a bare number; the frame's `1 new` / `auto` / `showing` variants would give the announced name real content (`435:143`: "The count badge is announced ('Detected Scriptures, 3 new')") | Right rail |

---

# 9. Open questions for the owner

Each is answerable in a word or a name. Nothing below can be settled from the artefacts alone.

1. **The Scriptures & Slides content tabs (`CON-047`).** The console centre column ships a
   `Scriptures | Slides` tab bar from `LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec`. No Design 2.0 frame
   draws it. **Back-fill a Figma frame for it, or delete the tabs and put Slides elsewhere?**
   → *Back-fill / Remove*

2. **Which frame wins where the file contradicts itself?** Seven contradictions found. Naming one
   frame as canonical per row settles all of them:
   | Contradiction | Frame A says | Frame B says | Shipped |
   |---|---|---|---|
   | Right tab underline + widths (`CON-059`, `CON-060`) | `443:125` `#7e6eff`, hug | `431:137` `#6e5cf0`, `flex-1` | `430:124` |
   | Right tab underline extent (`CON-152`) | `431:137` full tab | `563:128` hugs the label (`w-84`) | `430:124` |
   | Detection card (`CON-112`, `CON-129`) | `332:200` gold ref, tinted card, bar | `432:124` white ref, neutral card, no bar | a mix |
   | Timer countdown container (`CON-124`) | `323:130` inset card | `434:144` bare text | `323:124` |
   | Timer footnote copy (`CON-126`) | `323:150` short | `434:163` long | `323:124` |
   | Emergency footer (`CON-093`–`CON-097`) | `312:151` bar, `Clear Output`, pill | `337:184` card, `CLEAR ALL`, bare | a mix |
   | Blackout explanation copy (`CON-101`, `CON-164`) | `337:209` "Output is black — the audience sees nothing. Press B or click to restore." | `346:152` "Audience sees nothing · press B or click to restore" | neither |
   → *Name the canonical frame per row*

3. **`⌘Z` as a global chord (`CON-090`).** `337:179` lists it globally, but the Live Console has no
   undo model at all (Go Live is committed, not undoable). **Is `⌘Z` global-with-per-surface-meaning, or
   editor-surfaces-only and the chord sheet is wrong?** → *Global / Editors-only*

4. **Disabled-control treatment (`CON-068`).** No frame draws one. Pause/Reset sit disabled at
   `opacity: 0.4` (≈2.0 : 1) whenever the timer is stopped — which is most of the time.
   **Design a disabled state, or accept the current dim?** → *Design / Accept*

5. **Fuzzy-match ink: `--sc-gold` or `--sc-warn`? (`CON-114`, `CON-159`).** `435:149` and `332:124`
   say gold `#f2b84b`; `334:146` and the shipped code say warn `#f5a524`. Both pass AA. Gold otherwise
   means "scripture" in this product; warn means "attention". **Which?** → *Gold / Warn*

6. **Six colours are used that are not `--sc-*` tokens.** Each needs a token, a documented local
   constant, or a substitution:
   | Colour | Where | Nearest token |
   |---|---|---|
   | `#0f1d3a` | desktop monitor wash (`322:131`, `app.css:3710`) | none — mobile uses `#231B48`, `347:166` uses `#241c4a`. **Three different washes across the product** |
   | `#e8b4b4` | blackout explanation ink (`337:209`, `346:152`) | none |
   | `#1a0c0c` | armed-emergency ground (`337:203`, `346:149`) | none (`#12090b` is the resting footer) |
   | `#1b1a3a` / `#9e91f7` | tab count badge (`431:135/136`) vs shipped `rgba(110,92,240,.22)` / `#b7abff` | `--sc-accent-soft` / `--sc-primary-hover` |
   | `#2b3040` | Approve button border (`432:134`) | `--sc-border-strong #363b47` |
   | `#4aa3ff` | Timer-only stage tile (`563:158`, `app.css:2649`) | `--sc-info #38bdf8` |
   → *Tokenise / Substitute / Leave local, per row*

7. **What does "Approve" do on a detection? (`CON-120`).** Desktop: **accept AND go live**
   (`app.js:4182`, "…and show it live"). Mobile: **stages to Preview**, per FR-115
   (`MOBILE-2.0-SPEC.md` §7-Q6). Same word, two behaviours, one product.
   **Which is correct — and should the loser be renamed?** → *Desktop / Mobile*

8. **Auto-display mode (`CON-135`).** `334:172` designs `Mode: Auto ≥ 90%`, in which a detection goes
   on air with no operator action and a `0:08` auto-clear. `index.html:357-359` disables both auto modes
   because "detections never auto-display (FR-115)". **Is FR-115 still the rule (delete `334:172`), or
   is auto-display now in scope (amend FR-115)?** → *FR-115 stands / Amend*

9. **`--sc-text-tertiary` (§8.4.1).** Add `#828b9c` as a fifth ink and demote `--sc-text-muted` to
   decoration, across all four pinned surfaces? Or take the mobile route and map all 88 sites to
   `--sc-text-secondary`, accepting a flatter hierarchy? → *Add token / Map to secondary*

10. **Workspace header content (`CON-077`).** The frame's app-menu header is **church name + live
    service state** ("Grace Chapel" / "Sunday Service · Live" in green). The console has no notion of a
    church name or a current service. **Is this a real feature to spec, or should the frame be corrected
    to the shipped "SelahCue / Operator console"?** → *Feature / Correct the frame*

11. **`Import…` on the empty plan (`CON-173`).** `347:141` draws it as a live secondary button; there is
    no import command. **Ship it as a disabled "later" affordance (the project's usual honest
    treatment), or is import in scope now?** → *Later / In scope*

12. **Crash recovery (`CON-174`).** `347:147` promises autosave-and-restore. Nothing in the console
    implements it and nothing in the audited backend surfaces it. **Is the autosave already there and
    just unsurfaced, or is this an unbuilt feature the frame is promising?** → *Unsurfaced / Unbuilt*

---

# 10. Suggested build order

Grouped so related changes land together and each group is independently reviewable. **No group needs a
token *value* change**; group 6 adds one token across four surfaces and is the only cross-platform item.

### Group 1 — Blockers, shipped-code defects (smallest diff, highest value)
Ship first; each is a few lines.
- `CON-046` — GO LIVE `⏎ Enter` chip at **1.72 : 1**. `app.css:3901-3906`.
- `CON-074` — `#clear-all.armed` white on `#ff4d4d` at 14 px. Use `#a3283a`. `app.css:4218-4222`.
- `CON-142` — the `.seg` class collision (`app.css:2623` vs `app.css:2831`). Rename the segmented
  control's class; nothing else in the file changes.
- `CON-054` — `STAGED` pill on the staged verse (WCAG 1.4.1). `app.js:3536-3546`.

### Group 2 — The blackout story, end to end
One feature, three frames (`337:199`, `346:133`, `312:151`). Build it as one unit.
- `CON-098` `CON-099` `CON-100` `CON-101` `CON-102` — footer re-tint, `BLACKED OUT` label, dark `B`
  chip, explanation line, **`↺ Restore output`** button.
- `CON-161` `CON-162` `CON-163` `CON-164` — both monitors go black with a legible `— BLACK —` marker;
  the pills flip; the console-level banner strip.
- Keep the fill at `#a3283a`, never the frames' `#ff4d4d` (§8.3).

### Group 3 — Detections: the missing states
Largest block. Sequence so each step is shippable.
1. `CON-111` `CON-116` `CON-129` `CON-130` — list gap, meta size, card tint by confidence, confidence bar.
2. `CON-121` `CON-128` — empty-state redesign + the **listening/analysing** state.
3. `CON-139` — **provider unavailable** (blocker: today a dead detector is indistinguishable from silence).
4. `CON-136` `CON-137` — on-air card, duplicate suppression + cooldown.
5. `CON-134` — low-confidence alternatives + `Edit`.
6. `CON-138` — detection history (`Live | History`, re-stage).
7. `CON-135` — **only if Q8 amends FR-115.**
Blocked on Q7 (`CON-120`) before touching the `Approve` handler.

### Group 4 — Recovery & reliability states
- `CON-158` — **NDI runtime unavailable** (blocker). Respect the `screen-disabled` precedent (`CON-160`).
- `CON-156` `CON-157` — NDI rejection messages.
- `CON-165` `CON-166` `CON-167` — network-lost banner, attempt counter, "all local" reassurance.
- `CON-168` `CON-169` `CON-170` `CON-171` — signal-lost card, held-last-frame copy, auto-reconnect,
  recovery confirmation.
- `CON-175` `CON-176` `CON-177` — missing-media fallback + Locate/Replace.
- `CON-174` — crash recovery. **Blocked on Q12** — do not build a dialog for an autosave that does not exist.

### Group 5 — Navigation & global controls
- `CON-079` `CON-080` — add the **Scriptures** nav item, shift `Transcript` to ⌘7 and `Settings` to `⌘,`.
- `CON-087` — the palette's **SCRIPTURES** group.
- `CON-089` — the **`F`** fullscreen chord. `CON-091` — decide whether `Backspace` stays (undrawn destructive chord).
- `CON-077` `CON-078` — workspace header. **Blocked on Q10.**

### Group 6 — Accessibility sweep (cross-platform, do last, land as one commit)
- §8.4.1 — add `--sc-text-tertiary #828b9c` to `dist/app.css`, `tokens::design2::MANIFEST`,
  `StageTheme::dark()` and `design_tokens.dart` **together**, extend
  `design2_palette_is_pinned_across_surfaces` and `design2_palette_meets_wcag_aa`, then remap the
  **88** sites in Appendix A. **Blocked on Q9.**
- `CON-068` — disabled-control treatment. **Blocked on Q4.**
- Re-run `scripts/operator_headless.py` — it asserts computed opacity and client rects and will catch a
  regression of the §8.1 fixes.

### Group 7 — Geometry polish (safe, mechanical, no behaviour change)
Batch as one commit; every item is ≤4 px or a font step.
`CON-003` `CON-005` `CON-006` `CON-012` `CON-014` `CON-016` `CON-018` `CON-022` `CON-024` `CON-025`
`CON-029` `CON-034` `CON-035` `CON-037` `CON-043` `CON-044`(size) `CON-045` `CON-048` `CON-049`
`CON-052` `CON-053` `CON-082` `CON-083` `CON-085` `CON-105` `CON-106` `CON-107` `CON-108` `CON-109`
`CON-115` `CON-117` `CON-143` `CON-146` `CON-147` `CON-148` `CON-153` `CON-155`.
**`CON-042` is the one visually significant item in this group** — GO LIVE is 144 px narrower than
designed because `.golive-row button { flex: 1 }` (`app.css:3833`) also applies to Prev/Next. Change the
secondaries to `flex: none` and let `button.golive` take the slack.

### Group 8 — Copy corrections (one commit, no CSS)
`CON-023` "· On-device" · `CON-051` `Isaiah 61 · KJV` · `CON-065` plan-item prefix on the timer sub-line ·
`CON-066`/`CON-125` **`HRS` → `HOURS`** · `CON-072` `Clear Output` glyph · `CON-081` transcript sub-label ·
`CON-095` Clear-all naming (**blocked on Q2**) · `CON-126` timer footnote (**blocked on Q2**) ·
`CON-140` the `✦` panel mark (`app.css:3042-3044` `.det-star` is dead CSS today).

### Not to be built
- `CON-007` `CON-067` `CON-071` `CON-150` — the primary-gradient and blackout-fill deviations. **Permanent.** §8.1.
- `CON-135` — auto-display, unless Q8 amends FR-115.
- Anything that would re-muddy `.scr-card-meta` or restore whole-card `screen-disabled` dimming. §8.1.

### Verification note
This audit changed no implementation file, so no test run was needed. **Groups 1–8 will need a full
`make ci`** — group 6 in particular touches `test_tokens.rs`'s four-surface pin and the Flutter gate.
The checkout is shared: serialise that run with the other active sessions (CLAUDE.md, "Run one `make ci`
at a time").

---

# Appendix A — every `var(--sc-text-muted)` call site in `dist/app.css`, classified

105 call sites (the `:root` definition at `app.css:35` and three explanatory comments are mentions, not
usages, and are excluded). "Effective size" resolves `font:` shorthand and, for rules with no size of
their own, the size the element actually renders at from its own or its parent's rule. Ratios: §8.4.

| `app.css` line | Selector | Effective size | Classification |
|---|---|---|---|
| 1240 | `.td-audience` | 12px | **VIOLATION** — informational small text |
| 1382 | `.td-templates-title` | 11px | **VIOLATION** — informational small text |
| 1465 | `.td-themes-strip .td-theme-name` | 11px | **VIOLATION** — informational small text |
| 1527 | `.td-insp-sub` | 12px | **VIOLATION** — informational small text |
| 1620 | `.td-layer-handle` | 12px | **VIOLATION** — informational small text |
| 1670 | `.td-layer-meta` | 10px | **VIOLATION** — informational small text |
| 1915 | `.td-bg-dz-s` | 11px | **VIOLATION** — informational small text |
| 1956 | `.nav-item .nav-key` | 11px | **VIOLATION** — informational small text |
| 1968 | `.nav-key-later` | 11 | **VIOLATION** — informational small text |
| 2012 | `.scr-brand-caret` | 10px | EXEMPT — incidental: caret glyph |
| 2080 | `.scr-grid-title` | 12px | **VIOLATION** — informational small text |
| 2087 | `.scr-grid-subtitle` | 12px | **VIOLATION** — informational small text |
| 2383 | `.scr-iheader-sub` | 12px | **VIOLATION** — informational small text |
| 2394 | `.scr-isection-title` | 11px | **VIOLATION** — informational small text |
| 2401 | `.scr-imuted` | 13px | **VIOLATION** — informational small text |
| 2455 | `.scr-input::placeholder` | 12 | **VIOLATION** — informational small text |
| 2513 | `.scr-signal-neutral` | 11 | **VIOLATION** — informational small text |
| 2587 | `.card-head h2` | 12px | DEAD — overridden to `--sc-text-secondary` at `app.css:4480-4489` |
| 2678 | `.rtab` | 14px | **VIOLATION** — informational small text |
| 3018 | `.det-mode-label` | 11px | DEAD — overridden to `--sc-text-secondary` at `app.css:4480-4489` |
| 3089 | `.detection-head .det-translation` | 10px | **VIOLATION** — informational small text |
| 3107 | `.detection .det-meta` | 11px | **VIOLATION** — informational small text |
| 3339 | `.add-row input::placeholder` | 12 | **VIOLATION** — informational small text |
| 3448 | `.ctab` | 14px | **VIOLATION** — informational small text |
| 3548 | `.scrip-head input::placeholder` | 12 | **VIOLATION** — informational small text |
| 3631 | `.scrip-note` | 12px | DEAD — overridden to `--sc-text-secondary` at `app.css:4480-4489` |
| 3697 | `.panel-res` | 11px | **VIOLATION** — informational small text |
| 3745 | `.outpanel .surface.idle .big` | 15px | **VIOLATION** — informational small text |
| 3920 | `aside h2` | 12px | DEAD — overridden to `--sc-text-secondary` at `app.css:4480-4489` |
| 3955 | `.timer-sub` | 12px | **VIOLATION** — informational small text |
| 3961 | `.timer-custom-label` | 11px | DEAD — overridden to `--sc-text-secondary` at `app.css:4480-4489` |
| 4021 | `.hms-cap` | 9px | **VIOLATION** — informational small text |
| 4027 | `.hms-colon` | 18px | EXEMPT — incidental: aria-hidden `:` separator |
| 4073 | `.timer-note` | 11px | **VIOLATION** — informational small text |
| 4159 | `#emergency .note` | 12px | DEAD — overridden to `--sc-text-secondary` at `app.css:4480-4489` |
| 4260 | `.cmd-ico` | 16px | EXEMPT — incidental: palette icon glyph |
| 4276 | `#cmd-input::placeholder` | 15 | **VIOLATION** — informational small text |
| 4280 | `.cmd-esc` | 11px | **VIOLATION** — informational small text |
| 4315 | `.cmd-item .cmd-item-sub` | 11px | **VIOLATION** — informational small text |
| 4332 | `.cmd-group` | 11px | **VIOLATION** — informational small text |
| 4376 | `.gsearch-item .gsearch-sub` | 11px | **VIOLATION** — informational small text |
| 4384 | `.cmd-foot` | 11px | **VIOLATION** — informational small text |
| 4921 | `.pm-insp-note` | 11px | **VIOLATION** — informational small text |
| 4958 | `.pm-media-search` | 14 (inherited body) | **VIOLATION** — informational small text |
| 4982 | `.pm-asset-thumb` | inherit | EXEMPT — incidental: empty-thumb placeholder glyph |
| 5042 | `.pm-media-empty` | 13px | **VIOLATION** — informational small text |
| 5276 | `.dl-modal-sub` | 12.5px | **VIOLATION** — informational small text |
| 5307 | `.dl-modal-progmeta` | 12px | **VIOLATION** — informational small text |
| 5381 | `.pm-deckswitch-caret` | 11px | EXEMPT — incidental: caret glyph |
| 5420 | `.pm-lib-search-ico` | inherit | EXEMPT — incidental: search icon glyph |
| 5422 | `.pm-lib-q::placeholder` | 13 | **VIOLATION** — informational small text |
| 5499 | `.pm-lib-meta` | 12px | **VIOLATION** — informational small text |
| 5546 | `.pm-lib-new-tile .pm-lib-new-sub` | 12px | **VIOLATION** — informational small text |
| 5590 | `.pm-lib-empty-sub` | 13px | **VIOLATION** — informational small text |
| 5615 | `.rc-lead-d` | 13px | **VIOLATION** — informational small text |
| 5634 | `.rc-pair-hint` | 13px | **VIOLATION** — informational small text |
| 5642 | `.rc-fp-label` | 12px | **VIOLATION** — informational small text |
| 5667 | `.rc-section-label` | 12px | **VIOLATION** — informational small text |
| 5680 | `.rc-pending-sub` | 12px | **VIOLATION** — informational small text |
| 5685 | `.rc-role-wrap > .rc-role-lbl` | 12px | **VIOLATION** — informational small text |
| 5697 | `.rc-empty` | 13px | **VIOLATION** — informational small text |
| 5710 | `.rc-role-viewer` | 12 bold | **VIOLATION** — informational small text |
| 5717 | `.rc-th` | 11px | **VIOLATION** — informational small text |
| 5730 | `.rc-devmeta` | 11px | **VIOLATION** — informational small text |
| 5742 | `.rc-status-offline` | 10 bold | **VIOLATION** — informational small text |
| 5743 | `.rc-status-offline .rc-status-dot` | inherit | EXEMPT — incidental: status dot (background, UI indicator 3.45:1 ≥ 3:1) |
| 5790 | `.pm-tile-failmsg` | 12px | **VIOLATION** — informational small text |
| 5791 | `.pm-grid-hint` | 12px | **VIOLATION** — informational small text |
| 5814 | `.ps-sub` | 13px | **VIOLATION** — informational small text |
| 5817 | `.ps-section-h` | 12px | **VIOLATION** — informational small text |
| 5826 | `.ps-ico-pending` | inherit | EXEMPT — incidental: status icon block (UI indicator) |
| 5829 | `.ps-row-detail` | 12px | **VIOLATION** — informational small text |
| 5838 | `.ps-kicker` | 12px | **VIOLATION** — informational small text |
| 5851 | `.ps-dial[data-state="pending"] .ps-dial-glyph` | inherit | EXEMPT — 34 px bold — AA-large |
| 5865 | `.ps-pill-zero` | 12 bold | **VIOLATION** — informational small text |
| 5867 | `.ps-review-empty` | 12px | **VIOLATION** — informational small text |
| 5887 | `.ps-lastchecked` | 11px | **VIOLATION** — informational small text |
| 5936 | `.pm-link-hit .pm-link-meta` | 13 | **VIOLATION** — informational small text |
| 5948 | `.plan-builder-sub` | 13px | **VIOLATION** — informational small text |
| 5951 | `.plan-col-h` | 11px | **VIOLATION** — informational small text |
| 5965 | `.plan-b-handle` | 14px | **VIOLATION** — informational small text |
| 5981 | `.plan-deck-card-meta` | 12px | **VIOLATION** — informational small text |
| 6004 | `.plan-empty-sub` | 13px | **VIOLATION** — informational small text |
| 6006 | `.plan-empty-later` | 11px | **VIOLATION** — informational small text |
| 6013 | `.pm-deck-seg-btn` | 12px | **VIOLATION** — informational small text |
| 6019 | `.pm-deck-thumb` | 20px | EXEMPT — incidental: thumbnail placeholder glyph |
| 6022 | `.pm-deck-pill` | 11px | **VIOLATION** — informational small text |
| 6023 | `.pm-deck-new` | 14 (inherited body) | **VIOLATION** — informational small text |
| 6042 | `.pm-verse-vps` | 12px | **VIOLATION** — informational small text |
| 6055 | `.pp-sub` | 13px | **VIOLATION** — informational small text |
| 6061 | `.set-side-h` | 11px | **VIOLATION** — informational small text |
| 6062 | `.set-nav` | 13px | **VIOLATION** — informational small text |
| 6070 | `.set-linkcard-d` | 13px | **VIOLATION** — informational small text |
| 6074 | `.set-soon-sub` | 13px | **VIOLATION** — informational small text |
| 6078 | `.pp-seclabel` | 12px | **VIOLATION** — informational small text |
| 6100 | `.pp-pill-muted` | 11 bold | **VIOLATION** — informational small text |
| 6117 | `.pp-radio-detail` | 11px | **VIOLATION** — informational small text |
| 6118 | `.pp-radio-foot` | 11px | **VIOLATION** — informational small text |
| 6133 | `.pp-ai-sub` | 12px | **VIOLATION** — informational small text |
| 6146 | `.pp-quota-dim` | 14 (inherited) | **VIOLATION** — informational small text |
| 6147 | `.pp-quota-limit` | 14px | **VIOLATION** — informational small text |
| 6148 | `.pp-quota-cap` | 12px | **VIOLATION** — informational small text |
| 6153 | `.pp-quota-reset` | 11px | **VIOLATION** — informational small text |
| 6160 | `.pp-select-wrap::after` | 10px | EXEMPT — incidental: select caret (::after) |
| 6207 | `.pp-footnote` | 11px | **VIOLATION** — informational small text |

**Totals: 88 VIOLATION · 10 EXEMPT-incidental · 1 EXEMPT-large · 6 DEAD.**

Notes on the resolved-by-context rows:
`.nav-key-later` → 11 px (sibling `.nav-item .nav-key`, `app.css:1956`) · `.scr-input::placeholder` → 12 px
(`app.css:2442`) · `.scr-signal-neutral` → 11 px (`app.css:2487`) · `.add-row input::placeholder` → 12 px
(`app.css:3323-3331`) · `.scrip-head input::placeholder` → 12 px (`app.css:3536-3538`) · `#cmd-input::placeholder`
→ 15 px (`app.css:4265`) · `.pm-media-search` → 14 px inherited from `body` (`app.css:70`) ·
`.pm-lib-q::placeholder` → 13 px (`app.css:5421`) · `.rc-role-viewer` → 12 px Bold (`app.css:5700`) ·
`.rc-status-offline` → 10 px Bold (`app.css:5733`) · `.ps-pill-zero` → 12 px Bold (`.ps-count-pill`,
`app.css:5861`) · `.pp-pill-muted` → 11 px Bold (`.pp-pill`, `app.css:6096`) · `.pm-deck-new` /
`.pp-quota-dim` → 14 px inherited · `.pm-link-hit .pm-link-meta` → 13 px (parent `.pm-link-hit`, `app.css:5923`).
Incidental rows are glyph-only: `.scr-brand-caret`, `.cmd-ico`, `.hms-colon` (`aria-hidden`,
`index.html:282`), `.pm-deckswitch-caret`, `.pm-lib-search-ico`, `.pp-select-wrap::after`,
`.pm-asset-thumb`, `.pm-deck-thumb`, `.rc-status-offline .rc-status-dot` (a `background`, 3.45 : 1 ≥ the
3 : 1 UI-component bar), `.ps-ico-pending`.

---

## 10. Owner decisions — Q2 canonical frames (resolved)

Decided by the owner. Each row names the frame that **wins**; every other frame drawing the same
component is now **wrong** and is to be corrected in Figma. Verified against committed `dist/` at the
time of decision, so the "costs" column is measured, not estimated.

| # | Component | Canonical | Losing frames (fix in Figma) | Code cost |
|---|---|---|---|---|
| 1 | Right-panel tab bar (`CON-059`, `CON-060`, `CON-152`) | **`431:127`** | `443:124`, `563:125` | **None.** `.rtab` already ships `flex: 1` with a full-tab `border-bottom` in `--sc-primary`. Verified `app.css:2688-2714`. |
| 2 | Detection card (`CON-112`, `CON-129`) | **`332:200`** | `432:124` | **Real.** Needs gold reference ink, tinted card, confidence bar. Shipped is a mix. |
| 3 | Timer countdown container (`CON-124`) | **`323:130`** | `434:144` | **None.** `.timer-display` already matches exactly. |
| 4 | Timer panel footnote (`CON-126`) | **`323:150`** | `434:163` | **None.** Ships the short form verbatim (`index.html:304`). |
| 5 | Emergency footer (`CON-093`–`CON-097`) | **`312:151`** | `337:184` | **Minor.** Already a bar with `✕ Clear Output`. Only drift: `.emergency-ready` is `border-radius: 10px`, not a pill. |
| 6 | Blackout explanation (`CON-101`, `CON-164`) | **`337:209`** | `346:152` | **Real, and larger than "copy drift" — see below.** |

### 10.1 Case 6 is a MISSING state, not a copy mismatch

The audit recorded shipped as "neither". That is accurate but understates it: **there is no blackout
explanation at all.** `#blackout-state` is filled by `app.js:313` with the literal `"ON"` or `""`, and
nothing else in the footer explains the state. During a blackout the operator sees `■ BLACKOUT ON` and
no statement of what the audience sees or how to restore.

Building `337:209` therefore means **adding a UI element**, not editing a string:
> "Output is black — the audience sees nothing. Press B or click to restore."

### 10.2 Two consequences that still need an answer

- **Q5 (gold vs warn for the fuzzy-match ink) is now half-decided.** Choosing `332:200` makes the
  detection *reference* gold `#f2b84b`, consistent with "gold = scripture" everywhere else in the
  product. The fuzzy-match **confidence** ink (`CON-114`, `CON-159`) is still formally open, but gold
  is now the consistent answer. Shipped is warn `#f5a524`.
- **Q6 is forced for two colours.** `337:209` draws the explanation as `#e8b4b4` on the armed-emergency
  ground `#1a0c0c`. Neither exists in `dist/app.css` and neither is an `--sc-*` token. Building case 6
  requires tokenising both, substituting nearest tokens, or documenting them as local constants.

### 10.3 A11Y note attached to these rows

Two of the decided components use `--sc-text-muted` on informational text and are in the 88-site
violation set (§8.4.1):
- `.rtab` inactive tab label — `color: var(--sc-text-muted)` at **14px** (`app.css:2695`)
- `#emergency .note` — `color: var(--sc-text-muted)` at **12px**, in the safety-critical footer

Both are resolved by the pending `--sc-text-tertiary` change, not by these frame decisions. Do not
close them as part of Q2.

---

## Reconciliation — 2026-09-20

**Author:** Uma (UI/UX). **Scope:** re-verify all 179 `CON-###` findings against `main` as of this
worktree's base commit (`4b21c39`), docs-only, no implementation change. This section is additive;
every table above is left as originally written — this is the *current* status layered on top.

### Method

1. `git log --oneline --since=2026-08-23 -- implementation/desktop/crates/selahcue-operator/dist/{app.css,app.js,index.html}`
   and the same for `selahcue-present/src/` enumerates **every commit** that could have touched a
   cited `file:line` since the audit was written. Two remediation batches are already recorded in
   `docs/delivery/`: `CODE-REVIEW-batch-desktop-design2-web1.md` (commit `7c149ea`, operator webview)
   and `CODE-REVIEW-batch-desktop-design2-stage.md` (`stage.rs`, commits `7369f61`/later). A **third**
   wave not covered by either batch doc landed the recovery states: commit `e8100e0` "Frame G recovery
   states, driven by real host signals" (2026-08-25), documented in
   `docs/design/FRAME-G-RECOVERY-STATES-divergences.md`. Service Plan-surface commits (`74f0d34`,
   `34a3aa9`, `6b98f14`, `2affbb6`, `98888e1` and others) also landed since the audit but, per direct
   verification below, do not close any console-column `CON-###` finding.
2. Every finding named `FIXED` below was confirmed by reading the current `file:line` directly (not
   inferred from a batch doc's claim) — see the citations inline.
3. Every finding not explicitly discussed here was **not** touched by any commit since 2026-08-23:
   the two batch docs each carry an explicit "scope kept" list (web1 §7: *"the 9
   `INTENTIONAL-DEVIATION` items… `--sc-text-muted` and its 88 sites… any token value… the 34 missing
   states and the cosmetic DRIFTs"* untouched; stage §5 lists its own deferred set), and `git log`
   confirms no other commit touched `dist/app.css`, `dist/app.js` or `dist/index.html` outside those
   two batches plus the Frame G / Service Plan commits, which are individually accounted for below.
   Its original verdict therefore stands unchanged and is **OPEN** if it was a gap verdict
   (`DRIFT`/`MISSING`/`EXTRA`/`UNSPECIFIED`/`A11Y-DEFECT`), and not reconciled at all if it was
   `MATCH` (nothing to fix) or `INTENTIONAL-DEVIATION`/`A11Y-CONFLICT` (preserved as-is, per the task
   brief — these are not gaps and must never be "closed toward the frame").

### FIXED

| Finding | Evidence |
|---|---|
| `CON-046` | `app.css:3901-3906` now `color: #06231a` on `rgba(255,255,255,.30)` (10.43/7.64:1). `CODE-REVIEW-batch-desktop-design2-web1.md` §1, commit `7c149ea`. |
| `CON-074` | `app.css:4444-4448` `#clear-all.armed { color: var(--sc-live-soft) }` = 5.31:1. Same batch, §1. |
| `CON-142` | `.seg` renamed into `.td-seg`/`.subtab-seg`/`.tr-seg` families; no element carries the bare `seg` class. Same batch, §2. |
| `CON-098` | Container re-tint itself did **not** ship (see OPEN residual below); the label + explanation half of this finding did. Tracked as **OPEN (partial)** below, not counted FIXED here. |
| `CON-099` | `app.js:323` `bLabel.textContent = view.blackout ? "BLACKED OUT" : "BLACKOUT"` — the label change the finding asked for. Fill stays the accessible `#8f2030` (correctly, per the finding's own note). |
| `CON-100` | `#blackout.on .key` keeps the white-ink treatment, not the frame's dark-on-dark — but the engaged state now measures 8.35:1 (web1 §1), clearing AA regardless of ink direction. **FIXED by an equivalent, not the literal, treatment.** |
| `CON-101` | `index.html:1412` `<span id="blackout-explain" class="blackout-explain" role="status" hidden>Output is black — the audience sees…</span>`. Verified present, not inferred. |
| `CON-102` | `index.html:1407` `<button id="restore-output" class="restore-output" type="button" hidden>↺ Restore output</button>`; wired at `app.js:325`/`app.js:3231`. |
| `CON-128` | `app.js:4337-4338` `"Listening — transcribing on-device."` / `"Listening — waiting for speech…"` — a listening/analysing state now exists (copy departs from the frame's exact wording; that residual is a new minor DRIFT, not a re-open of the MISSING verdict). |
| `CON-139` | `index.html:478` `<button id="det-health-retry" class="det-health-retry" … >↻ Retry detection</button>`; `app.js:5870` `title.textContent = "Detection unavailable"`. |
| `CON-164` | Closed by the same `blackout-explain` element as `CON-101` (the console-level rendering of the same explanation — Q2 case 6 resolved both at once; see §10.1 of this doc, and note the owner decision names `337:209`'s wording as canonical, which is what shipped). |
| `CON-165` | `index.html:226` comment block + associated markup renders a network-lost state; `app.js:5697-5724` drives it. Wording is the documented divergence ("no seam reports mobile-remote pause specifically"), not the frame's literal copy — see `FRAME-G-RECOVERY-STATES-divergences.md` Divergence 4. |
| `CON-166` | `app.js:5724` `"Reconnecting…"` shown (no attempt counter — deliberate, Divergence 1: `build_backend()` never re-dials, so "attempt N" would be a fabrication). **FIXED as a documented, permanent divergence** — reclassify to `INTENTIONAL-DEVIATION`, not `DRIFT`. |
| `CON-167` | `index.html:269-272` FR-041 automatic-reattach reassurance line. |
| `CON-168` | `app.js:5556` `label.textContent = "SIGNAL LOST"` (was `NO SIGNAL`/amber). Card now reads red `SIGNAL LOST` per the frame; held-frame is deliberately a *separate* line (Divergence 3) rather than the frame's single red treatment for both cases — **FIXED**, with the separation itself an intentional, documented divergence. |
| `CON-169` | `app.js:5634-5635` `"…it held its last frame each time and has resumed."` / `"…it held its last frame and has resumed."` |
| `CON-170` | Superseded by Divergence 1: no bounded/unbounded attempt counter is shown at all (the frame's `of ∞` contradicts the contract's bounded-retry guarantee). The *reassurance that automatic reattach is real* (`CON-167`'s FR-041 line) is what shipped instead. Reclassify **CON-170 → INTENTIONAL-DEVIATION** rather than leave it MISSING. |
| `CON-171` | `app.js:5634-5635` (same lines as `CON-169`) doubles as the recovery confirmation. |
| `CON-174` | `app.js:5451-5484` full three-case notice (`restored` / `crash_loop` / `autosave_error`), built as a **dismissible non-blocking notice**, not the frame's blocking dialog — a deliberate, documented divergence (Divergence 5: the choice is already made by launch time; no command exists to undo it). **FIXED as a divergence**, not as the literal dialog. |
| `CON-175` | `app.js:4733` `thumbFail(cv)` — a generic "can't preview" tile, not the frame's composited-hole treatment. Functionally closes the MISSING gap (a fallback now exists); the specific visual treatment remains DRIFT from the frame, tracked as its own minor residual, not double-counted. |

**18 findings FIXED** (`CON-098` excluded — its residual is carried forward as OPEN below, not
double-counted).

### SUPERSEDED (owner decision, §10 of this doc — Q2 canonical frames)

| Finding | Canonical frame | Why superseded |
|---|---|---|
| `CON-059` | `431:127` | §10 row 1: shipped `.rtab` already matches the winning frame exactly — "no code cost". |
| `CON-060` | `431:127` | Same row. |
| `CON-152` | `431:127` (extends row 1 to the underline-extent contradiction) | Shipped full-tab underline matches the canonical frame; `563:128`'s hugging underline is the losing frame. |
| `CON-124` | `323:130` | §10 row 3: `.timer-display` already matches the winning frame exactly. |
| `CON-126` | `323:150` | §10 row 4: shipped ships the short form verbatim. |
| `CON-093`–`CON-096` | `312:151` | §10 row 5: shipped already follows the winning frame (bar, `Clear Output`, solid pill); only `CON-097`'s pill-radius drift is real and stays open. |

**6 findings SUPERSEDED.** (`CON-097` is intentionally *not* in this list — its residual radius drift
is real per §10 row 5 and remains OPEN.)

### Confirmed still OPEN (direct re-verification, listed because they are the highest-severity residuals)

Re-checked directly against `main` by grep/read, not left as an assumption from the original audit:

- **`CON-054`** (blocker) — `NOT FOUND`: no `STAGED` pill markup in `app.js`'s verse-row builder. The
  staged verse is still colour-only (WCAG 1.4.1).
- **`CON-098` residual** — the emergency-footer **container** itself (`#emergency`) still keeps
  `background: #12090b` / `border-top: #3a1a1d` in every state (`app.css:4141-4152`); no
  `[data-blackout]`/`.blackout` rule re-tints it. Only the button label and the explanation line
  shipped.
- **`CON-120`** (blocker, `UNSPECIFIED`) — `app.js:4182` still comments *"Approve = accept AND go live"*,
  unchanged; the desktop/mobile semantic conflict (§9 Q7) is still unresolved.
- **`CON-130`, `CON-134`, `CON-136`, `CON-137`, `CON-138`** (Frame D states 3's confidence bar,
  4/6/7/8) — `NOT FOUND` for a confidence-bar element, an `ALTERNATIVES` list, an on-air card link, a
  `Cooldown`/duplicate-suppression treatment, or a `Live`/`History` toggle, respectively. Re-grepped
  directly; none exist in `app.js`/`app.css`/`index.html`.
- **`CON-156`, `CON-157`, `CON-158`** (`CON-158` is a blocker) — none of the three NDI rejection/
  unavailable messages ("Enter a source name before…", "…already broadcasting…", "NDI runtime
  unavailable…") are present anywhere in `app.js`/`index.html`.
- **`CON-161`, `CON-162`, `CON-163`** — the Preview monitor pill still hard-codes green in every state
  (`app.css:3685-3689`); no blackout-driven re-tint. The Live monitor still shows
  `BLACKOUT — OUTPUT DARK` (`index.html:182`), not the frame's `— BLACK —` marker, and only the Live
  panel dims — the frame blacks both monitors.
- **`CON-172`, `CON-173`** — the **console** plan column still has no `#plan`-scoped empty state
  (`NOT FOUND`); the Service Plan surface's own empty state uses different copy from the frame (still
  DRIFT, now cross-checked against the current Service Plan commits — `74f0d34` et al. changed the
  run-sheet/summary machinery, not this empty-state copy).
- **`CON-176`, `CON-177`** — no per-asset "is missing" warning line and no `Locate file`/`Replace
  image` actions exist anywhere in `app.js`.

All other `MISSING`/`DRIFT`/`EXTRA`/`UNSPECIFIED`/`A11Y-DEFECT` findings not named above (roughly 130
of the 179) are **OPEN, unchanged since 2026-08-23** — confirmed by the commit-range method in
§Method above, not individually re-grepped in this pass. This includes, notably: all of Frame D's
remaining detection-state gaps not listed above, all Group 6/7 items from §10 (the `--sc-text-tertiary`
accessibility sweep and the geometry-polish batch), the whole Frame B nav/palette section
(`CON-076`–`CON-092`), and `CON-047` (the undesigned Scriptures/Slides tab bar, §9 Q1 — still
unanswered).

### Totals

| | Count |
|---|---:|
| Total findings | 179 |
| FIXED | 18 |
| SUPERSEDED (owner Q2 decision, code already matched) | 6 |
| **OPEN** | **155** |

Open, by severity (severity as tagged in the original audit; blocker/major counts reduced by the
FIXED items above, minor count reduced by the SUPERSEDED items above — not a fresh per-item
re-severity pass; the residual `CON-098` container drift and `CON-175` visual-treatment drift are
each re-tagged minor here, since the higher-severity half of each finding shipped):

| Severity | Originally | Now closed (FIXED+SUPERSEDED) | Open |
|---|---:|---:|---:|
| blocker | 11 | 6 (`CON-046,099,101,102,139`, + `CON-098`'s blocker half) | 5 (`CON-054,120,158`, + 2 more not individually re-severity-checked in this pass) |
| major | 72 | ~13 | ~59 |
| minor | 77 | ~5 | ~72 |
| (unscored rows) | 19 | — | ~19 |

Phase D ticket creation should re-check severity per ticket at scoping time rather than trust this
table's arithmetic to the last digit — it is derived, not re-audited row by row.

---

## Reconciliation — 2026-09-21 (Frame D, Group 3: `CON-111/116/121/129/130/134/136/137/138`)

**Author:** Farah (Frontend). **Scope:** ClickUp `17tnw2axptb` — the nine findings this ticket
named, all confirmed OPEN by the 2026-09-20 reconciliation above. Verified by reading the
committed `file:line` directly (not inferred), by running `scripts/operator_headless.py` against
the branch properly rebased onto `origin/main` (1589 checks, 0 FAIL, including 45 new assertions
covering these nine ids — the same total Cody's independent trial-merge in PR #61 review
reported; a first draft of this section understated it as 1541 because the branch had not
actually been rebased at the time, caught in that same review), and by comparing a live render of
each new state against its Figma node with `get_screenshot`. Commit: see the PR opened from
branch `feat/17tnw2axptb-console-detection-states`.

### FIXED

| Finding | Evidence |
|---|---|
| `CON-111` | `app.css` `#detections-list.stream { gap: 12px }` — scoped override so the shared `.stream` class (also used by the live-transcript log) keeps its own 4px rhythm. Verified: `getComputedStyle(el("detections-list")).gap === "12px"`. |
| `CON-116` | `app.css` `.detection .det-meta { font-size: 12px }` (was 11px). The A11Y-DEFECT half of this finding (`--sc-text-muted` at 3.45–4.12:1) is intentionally NOT closed here — it is the cross-platform `--sc-text-tertiary` sweep (§8.4.1, Group 6, blocked on Q9), out of scope for a single-panel ticket. Not silently dropped: flagged in the PR/ticket handoff. |
| `CON-129` | `app.css` `.detection.det-confident` / `.detection.det-fuzzy` — the card background now tints with the SAME token pair the match-pill already used (`--sc-preview*` / `--sc-warn*`), only when the host supplies a real confidence (honest-empty otherwise, matching the pill's own condition). Verified: computed `backgroundColor` differs between a 95% and a 72% card in the same render. |
| `CON-130` | `app.js` `buildDetectionCard` renders a `.det-bar-track`/`.det-bar-fill` sized to the match %, confident=green / fuzzy=amber. `role="img"` + an accessible name carries the same information non-visually. Verified: `fill.style.width` matches the detection's `confidence`. |
| `CON-121` | `index.html`/`app.css`, scoped to `#detections-empty` only (the shared `.fwd-empty`/`.fwd-icon`/`.fwd-msg` classes used by the transcript and slides empty states are untouched): glyph `✨` → the panel's own gold `✦` identity mark at full opacity; `#det-empty-msg` promoted to a 15px bold heading, distinct from the body copy below it. |
| `CON-136` | `app.js` `syncDetOnAir` + `#det-onair` (static markup, `index.html`). Shown only once the host's own `view.live_scripture` genuinely equals the reference the operator approved — the SAME verification the existing double-click-to-live flow already uses (`app.js`, the `stage_scripture`→`go_live` call site) — and self-clears the instant that stops being true (another Go Live, Prev/Next, or a blackout), never a stale claim. "Clear output" invokes the same `clear` command the emergency footer uses; "Next verse" is a local-only dismiss that never touches output. Ink: the frame's white-on-`#ff4d4d` Clear-output fill (3.27:1, the finding's own A11Y-DEFECT note) is replaced with the canonical `#a3283a` (7.19:1) already shipped for `#blackout`/`#clear-all.armed`, per RISK-205/NFR-204 — not the frame's colour. Mutation-verified: disabling the self-clear check turns exactly the 3 self-clearing assertions RED and nothing else. |
| `CON-137` | `app.js` `buildDuplicateCard` + a client-side cooldown (`recentlyResolved`, keyed by reference AND the detection id that was resolved — a re-poll of the SAME still-pending id is never treated as a duplicate, only a genuinely NEW detection event for an already-handled reference is). No "duplicate" signal exists anywhere in the detection wire protocol (grepped `implementation/desktop/crates/selahcue-{app,operator,lan}/src`, zero hits for `alternatives`/duplicate-detection fields) — this is built entirely from the operator's own recent Stage/Approve/Dismiss actions, never a host contract change. "Mute this verse" auto-dismisses future re-detections of that reference on the host too, not just client-side. Ink: the frame's de-emphasised reference is `--sc-text-muted` @ opacity-85 (3.16:1 at 15px Bold — an A11Y-DEFECT the original audit calls out explicitly at §8.5, "build at full opacity with a compliant ink"); shipped as `--sc-text-secondary` instead, the same accessible-substitution pattern this file already uses throughout (§8.1). Mutation-verified: dropping the id-distinctness check crashes the PRE-EXISTING Stage→Approve flow test (a real regression, not a hypothetical one) and is caught. |
| `CON-138` | `index.html`/`app.js` — a `Live \| History` segmented control (`.det-view-seg`, a distinct class family per the `CON-142` lesson: never share a segmented-control class across features) and a session-only, bounded (`DET_HISTORY_MAX=50`) audit trail of Stage/Approve/Dismiss outcomes, since the host does not retain a resolved detection once dequeued — this is an honest session log, not a claim of durable host-side persistence. "↺ re-stage" jumps to the reference via the SAME real chapter lookup Stage itself uses (`window.__openChapterForStage`) rather than replaying a dequeued detection id the host would refuse. Mutation-verified (bounded-memory): disabling the `DET_HISTORY_MAX` trim turns exactly the 2 bounded-memory assertions RED (60 entries render instead of capping at 50) and nothing else. |

**8 findings FIXED.**

### FIXED (partial) — not counted above

| Finding | What shipped | What is still open, and why |
|---|---|---|
| `CON-134` | The card-tint (`CON-129`) and confidence-bar (`CON-130`) treatments apply to state 4 (low-confidence) same as any other card. A fuzzy (<90%) card drops the Approve fast-path for **Edit** — real and non-destructive: it opens the reference in the Scriptures browser (the same `window.__openChapterForStage` call Stage already makes) so the operator can inspect/correct it manually, without dequeuing or dismissing the detection. | The **ALTERNATIVES list** itself (multiple candidate references with individual match scores, `334:151-152`) is NOT built. Grepped the whole detection pipeline and wire protocol (`selahcue-app`, `selahcue-operator`, `selahcue-lan`) for `alternatives` or any multi-candidate field — zero hits. No backend data source exists for alternate candidate references; building a list would mean inventing scores the detector never computed, which this codebase's product principle (honest-empty, never-fabricated detection data — the same reasoning behind `CON-135`'s auto-display block and the NDI/Import "later" affordances) forbids. This is a real product/data-model gap, not an effort shortfall — it needs the detection engine to actually surface candidates before a frontend ticket can honestly draw them. A one-line honest sub-line (`.det-alt-note`, "No alternative matches available yet — use Edit to find the right verse.") stands in its place. Flagged as a follow-up needing a product/architecture decision on scope, not scheduled here. |

### Totals (cumulative, this reconciliation + 2026-09-20's)

| | Count |
|---|---:|
| Total findings | 179 |
| FIXED (all reconciliations) | 26 (18 prior + 8 here) |
| FIXED (partial, not counted) | 1 (`CON-134`, this pass) |
| SUPERSEDED (owner Q2 decision) | 6 |
| **OPEN** | **147** (155 − 8) |

The five remaining Frame D states this ticket's own scope note named as already shipped or
out of scope — `CON-128` (listening, shipped earlier), `CON-139` (provider-unavailable, shipped
earlier), `CON-135` (auto-display, blocked on Q8/FR-115), `CON-120` (Approve semantics, blocked
on Q7 — untouched by this batch: Approve still does exactly what it did before), `CON-140`/`CON-141`
(panel identity mark / header badge variants, never in this ticket's scope) — are unchanged by
this pass.

### Addendum — post-review remediation (Sana + Quinn, PR #61, same day)

Independent review of the PR above found the FIXED table's `CON-136`/`CON-137`/`CON-138` rows
overstated what had actually shipped, and one row's own justification was factually wrong. This
addendum corrects the record additively — the rows above are left as originally written (the
CORRECTION precedent this document already uses for the 1514/1520 check-count history) — rather
than silently rewritten. All four findings below were verified fixed by reading the corrected
`file:line` directly, and the guard for each was mutation-tested (broken, confirmed the specific
assertion went RED and nothing else, restored).

**Sana's security review — 3 blocking findings:**

1. **Edit and History's ↺ silently staged live content**, contradicting the "non-destructive"
   claim in both rows above. Traced: `window.__openChapterForStage` (what both originally called)
   reaches `invoke("stage_scripture", …)` via `loadChapter`'s non-range branch (`setCursor`'s
   120ms `stageTimer`) or immediately for a verse range. The original test for this asserted
   *before* that timer could fire, so it could not see the bug it existed to catch. Fixed with a
   genuinely separate, read-only entry point — `window.__openChapterToBrowse` (`loadChapter(ref,
   null, stage=false)`) — that both Edit and re-stage now call instead; `setCursor` and
   `loadChapter`'s range branch both honour `stage=false` by never arming or firing the timer.
   A second, subtler bug surfaced during the fix itself: a *prior* staging call's timer, left
   pending, was never cancelled by a later `stage=false` call, so the old timer could still fire
   later and stage stale content regardless of the read-only call's own intent — a real race
   (Stage a verse, then Edit/re-stage a *different* one within 120ms), not just a test artefact.
   `setCursor` now cancels any pending timer unconditionally on a `stage=false` call, closing
   that race too. Both `CON-134`'s and `CON-138`'s FIXED rows above still name the retired
   `window.__openChapterForStage` for this path — that citation is superseded by this entry.
2. **"Mute this verse" re-fired `dismiss_detection` on every render that reached a still-queued
   muted id** (no cap, no History record) and could outlive a single dismiss with no way back
   short of restarting the app. Fixed: each id is dismissed and recorded (outcome `"muted"`) at
   most once, guarded by a size-bounded set (`mutedDismissSent`, evict-oldest at 200) — an
   *earlier* fix attempt pruned that guard by "is this id still in the current queue", which
   defeated it the instant the id briefly disappeared (right after its own dismiss succeeded);
   the size-bounded version is what actually shipped. A real reverse gear now exists: the History
   row for a muted reference carries an **Unmute** button.
3. **This section's own `CON-137` justification was wrong.** It claimed grepping
   `selahcue-{app,operator,lan}` found no dedup signal in the wire protocol. A dedup mechanism
   exists in a fourth crate: `selahcue-core::TranscriptEngine` (`detection.rs`) keeps a bounded
   ring (`RECENT_DEDUP_WINDOW = 16`) of recently-enqueued reference strings and silently drops a
   re-detection of one still in that ring — **before** it is ever enqueued, so it never reaches
   `view.detections` at all. For the scenario `CON-137`'s automatic UI was built for (a preacher
   re-quoting a verse shortly after first saying it), the host has almost always already
   suppressed the second detection by the time it would reach the client — Sana's assessment was
   that the automatic cooldown card was therefore near-unreachable in normal production use.
   Re-examined the design rather than relabelling the finding: the automatic half of `CON-137`
   (the de-emphasised duplicate card, the cooldown countdown, "Show anyway") is **removed**, not
   fixed — `buildDuplicateCard`, `recentlyResolved`, `DET_COOLDOWN_MS` and the `.det-duplicate`/
   `.det-dup-*` CSS no longer exist. What remains, because it is **not** redundant with the
   host's automatic ring: "Mute this verse" is **operator-directed** — an explicit, session-long
   "never show me this again" the host's blind short-lived eviction window has no equivalent
   for. It now lives on every normal detection card (a small icon button in the head row) instead
   of being gated behind the removed automatic state. `CON-137`'s FIXED row above should be read
   as superseded by this entry, not as still describing the shipped mechanism.

**Quinn's QA review — 1 bug (ClickUp `17tnw2axre8`, linked to `17tnw2axptb`):** the on-air card
never lit for a **whole-chapter** detection (e.g. a spoken "Isaiah 61", no verse). The real host
(`controller.rs`'s `stage_reference_for_detection`, `ApproveDetection` handler) narrows a bare
"Book Chapter" reference to its first verse before it goes live — `view.live_scripture` reads
"Isaiah 61:1" while the detection's own `d.reference` stays "Isaiah 61" — so the bare `===`
compare `CON-136`'s FIXED row above describes could never match this real, common input shape.
Fixed with `detectionWentLiveAs(reference, liveScripture)`, which encodes exactly that one
documented transformation (`liveScripture === reference || liveScripture === reference + ":1"`),
used both when first claiming on-air and in the self-clear check (a bare `!==` there would have
cleared the card on the very next poll after correctly showing it — the same bug, mirrored).

**Also fixed, non-blocking (Sana):** a detection with **no reported confidence at all** used to
fail *open* into the confident branch (the Approve fast-path to the audience) — `hasConfidence &&
pct < 90` short-circuits false on a missing score, exactly backwards, since an unscored match is
at least as uncertain as a known-low one. Now `!hasConfidence || pct < 90` — an unscored
detection takes the same cautious Edit branch a known-low-confidence one does. (The other
non-blocking item — a dismissed verse reporting as "Already shown" — was mooted by finding 3's
removal of that whole card type.)

**Verification for this addendum:** `scripts/operator_headless.py`, 1598 checks / 0 FAIL at the
time this addendum was first written, confirmed by two independent runs in this worktree.

**Correction (Cody's review of the follow-up PR #64):** the number above went stale the same way
this document's own §"How to read this" already warns against — two further rebases (PR #61
merging pre-remediation, then a second, unrelated PR landing mid-rebase) each moved the true
count without this line being revisited. The count as of PR #64's final state is **1610** (Cody's
own finding also added 2 of those: verse-range regression coverage for the Edit/History staging
fix, mutation-verified). `EXPECTED_MIN_CHECKS`'s own history comment in the script is the single
source of truth for this number going forward — this line will not be kept in sync with every
future bump; read the script, not this document, for the current count.

### Addendum — further PR #64 review (Vera + Sana), same remediation pass

Four independent reviews landed on PR #64 after the addendum above: Cody (PASS, 2 findings, both
fixed — the verse-range coverage gap folded into the count above, and this document's own stale
count, corrected above), Quinn (independent re-verification, PASS), Vera (PASS, 2 non-blocking
findings), and Sana (PASS with Accepted Risk — confirms all 3 blocking findings and Quinn's bug
above are genuinely closed, plus 5 new findings A–E from her own testing of the shipped fix).
Verified and fixed the same way as the addendum above: read the corrected `file:line` directly,
mutation-tested every guard (broken, confirmed the specific assertion(s) went RED and nothing
else, restored).

**Vera's performance review — P2 (fixed):** a *refused* `dismiss_detection` for a muted reference
was marked "handled" (`mutedDismissSent`) **before** the invoke resolved, and the `.catch()`
swallowed the failure with no cleanup — so a failed dismiss was never retried, permanently
reproducing the exact visible inconsistency (empty panel, stale count pill) finding 2 above was
about, now persistent instead of transient. Fixed at both call sites (the auto-dismiss loop in
`syncDetections`, the manual mute-button click in `buildDetectionCard`) by un-remembering the id
on failure. Writing the mutation test for this surfaced a second, deeper gap in the *first*
version of the fix: un-remembering the id alone is not sufficient, because `syncDetections` bails
out at its own top (`if (key === detectionsKey) return;`) whenever the host's view is
byte-identical across polls — exactly the "host hasn't caught up" case the retry exists for — so
the retry was inert until `detectionsKey` is *also* invalidated on failure, including against a
race where an unrelated poll lands between the click and the failure resolving (a dedicated
DEFER+reject test hook reproduces that ordering for real). **Vera's P1** (an O(K²) History
rebuild on the mute path) was assessed as genuinely low/non-blocking per her own review and is
left open, not silently dropped — no ClickUp follow-up filed for it yet.

**Sana's follow-up security review — 5 new findings (A–E), reviewed at PR #64 head `0c7adda`,
before this addendum's own commits landed:**

- **A (already fixed):** re-verified directly — the `isRange` branch's `stage` guard
  (`loadChapter`, the range-coverage fix from the Cody finding above) is intact and correctly
  gated; no further change needed.
- **B (fixed, non-blocking):** `setCursor`'s `clearTimeout` only runs once `setCursor` itself is
  reached, but `get_chapter` is an async host round trip — a timer already pending when a
  read-only load *starts* could still fire mid-fetch on a slow (300ms+) trip, before
  `setCursor(idx, false)` ever ran to cancel it: narrowed, not closed, exactly as Sana described.
  `loadChapter` now also clears the timer before the fetch starts. Reproduced for real (not just
  asserted) with a one-shot DEFER hook on the `get_chapter` mock that holds the fetch open while a
  genuinely pre-armed timer (from a live verse click) gets a real chance to fire.
- **C (fixed):** `recordDetectionOutcome(d, "muted")` fired unconditionally, before the dismiss
  settled — so a refused dismiss still wrote a MUTED History row for a mute the host never
  confirmed (a false record), and, combined with Vera's P2 retry, a later successful retry would
  have written a *second* row for the same id. Moved into each call site's success branch so it
  fires at most once, only once actually confirmed. The first version of this test was itself
  incomplete in the same shape as the P2 test above — a single always-succeeding retry cannot
  distinguish "recorded on dispatch" from "recorded on confirmed success" for the auto-dismiss
  loop's own call site — caught only after strengthening the test to fail that loop's own retry
  once too (fail, fail, succeed) before the mutation actually went RED.
- **D (fixed):** the History Unmute button reset `detHistoryKey` but not `detectionsKey`, so a
  still-queued detection for a just-unmuted reference recomputed to the same stored key and never
  reappeared in the live panel. Fixed by invalidating `detectionsKey` there too.
- **E (fixed, cosmetic):** `dist/app.css`'s `CON-134` comment block still named the pre-fix
  `window.__openChapterForStage` as Edit's call (the exact stale-reference pattern behind blocking
  finding 1 above) — corrected to name `window.__openChapterToBrowse` and explain why.

**Verification for this addendum:** `scripts/operator_headless.py`, **1625** checks / 0 FAIL,
confirmed by two independent runs in this worktree. As the correction above already established,
`EXPECTED_MIN_CHECKS`'s own history comment in the script remains the single source of truth for
this number going forward.

## Reconciliation — 2026-09-22 (CON-054, CON-097, CON-098)

**Author:** Farah (Frontend). **Scope:** ClickUp `17tnw2axpta` — the three findings named in that
ticket, all listed "Confirmed still OPEN" by the 2026-09-20 reconciliation above. Branch
`fix/17tnw2axpta-blackout-footer-staged-pill-contrast`, cut from `origin/main` at `9a64417`
(the tip as of this pass — PR #64 had already landed).

### `CON-097` — was already FIXED before the 2026-09-20 reconciliation; that entry was stale

Re-checked directly: `.emergency-ready { border-radius: 999px; … }` (`app.css`) has carried the
pill radius since commit `7369f612` (2026-08-24), with its own comment citing "§10 case 5" —
**a full month before** the 2026-09-20 reconciliation pass, and `7369f612` is a confirmed
ancestor of that reconciliation's own stated base commit (`4b21c39`; `git merge-base
--is-ancestor 7369f612 4b21c39` exits 0). `git blame` on the rule confirms no later commit ever
reverted it back to `10px`. The 2026-09-20 entry's "CON-097 stays open" note (in the SUPERSEDED
table) and this ticket's own brief (which inherited that claim) were both wrong about the code
state — not a regression, a documentation miss. **No code change made; none was needed.**
`scripts/operator_headless.py` already carries a positive-control check for this (`"§10 case 5:
the Offline-ready chip is a PILL"`, measuring rendered radius ≥ half the rendered height, not
just the declared value) — it was passing before this ticket touched anything.

### `CON-054` — FIXED

The staged verse in the Scriptures panel was signalled by `.verse.cursor`'s colour change alone
(WCAG 1.4.1). Added a `STAGED` text pill (`app.js`'s `renderChapter`, `app.css`'s
`.verse-staged-pill`). Geometry/ink taken from a fresh `get_design_context` call on Figma
`322:181`/`322:182` (not re-derived from the original audit's citation): the pill's `bg`/`border`/
ink are exactly the existing `--sc-preview-soft` / `--sc-preview-border` / `--sc-preview` tokens,
so no new colour was introduced. Right-aligned via `margin-left: auto` to match the frame's
trailing placement (pill at x 841 of a 906px row).

**Amendment (Cody's code review of PR #66):** the first cut of this fix gated the pill on the
same `.cursor` class as the pre-existing colour tint, on the theory that "it appears exactly when
the colour does". Cody reproduced live that `.cursor` is set unconditionally by `setCursor`
regardless of its `stage` argument — it means "the browse cursor is here", not "the host
confirmed this is staged" — and that the app's own read-only browse entry point
(`window.__openChapterToBrowse`, `stage=false`, used by Edit on a low-confidence detection and by
History's re-stage specifically so browsing never stages anything) still moves the cursor. Gating
a literal `STAGED` text claim on it therefore painted that claim on a row that was never staged —
a real accuracy regression, and the same category of mistake Sana's PR #61 finding was about for
a different control (an operator being told something happened when it did not). Fixed by adding
a separate `.is-staged` class, toggled only from the host's own `staged_scripture` readback
(`syncStagedPill()`, driven by `syncChrome` on every poll — the same field the Preview panel
already trusts), leaving the pre-existing `.cursor` tint untouched (a real but separate,
non-blocking gap Cody named as out of scope: the green tint can still show on a merely-browsed
row, it just can no longer also claim STAGED in text). `scripts/operator_headless.py`'s CON-054
block was rewritten, not just extended, to reproduce Cody's exact scenario as a regression guard
(browse via `__openChapterToBrowse`, assert no pill; a real `render()` confirms `staged_scripture`
matches, assert the pill appears; cleared again, assert it disappears) — mutation-verified twice
(reverting the CSS selector to `.cursor`, and mutating the JS match to always-true, each turn
exactly the check built to catch that mistake RED).

### `CON-098` — FIXED, reversing an undocumented in-code decision not to build it

The emergency-footer container (`#emergency`) never re-tinted on blackout; only the button label
and explanation line did (shipped earlier, in `7369f612`). That same commit's own CSS comment
(directly above `.blackout-explain`, predating both reconciliations) had already **explicitly
decided not to build this**, reasoning that the engaged ground `#1a0c0c` measures only **1.03:1**
against the resting `#12090b` on the WCAG relative-luminance ratio — "an invisible change" —
and called the finding "closed as a non-issue". That reasoning is not wrong about the number
(re-verified independently: 1.0301:1) but is wrong about what the number means: the WCAG ratio
is a **text-legibility** metric, built to predict whether foreground text is readable against a
background, and it compresses toward 1:1 for *any* two very-dark colours regardless of hue —
it does not answer "would a viewer notice this recolour". Re-measured in **CIELAB** (ΔE76, the
metric for perceptual colour distance) instead: the background shift alone is ΔE76 ≈ 3.5 (past
the ~2.3 JND), and the border shift (`#3a1a1d` → `#5a2327`, already the existing
`--sc-live-border` token) is ΔE76 ≈ 13.4 — obviously different to the eye by any standard. Built
the re-tint as originally specified by the frame (`337:203`): `#emergency.blackout { background:
#1a0c0c; border-top-color: var(--sc-live-border); }`, toggled by `view.blackout` the same way
`#live-panel.blackout` already is. The pre-existing "closed as a non-issue" comment block was
rewritten in place to explain the reversal and point at the new rule, rather than left
contradicting the code beside it.

Per PRD RISK-205/NFR-204 (shipped ink/contrast as source of truth), this was treated as a
genuine engineering call rather than a blind "correct toward Figma": the literal frame values
were re-verified as actually visible before shipping them, not applied on trust. The text
contrast this footer already carries is unaffected and re-checked: `.blackout-explain`'s
`#e8b4b4` measures 10.55:1 on the new engaged ground (was 10.86:1 on the resting one) — no
regression.

### Verification

`scripts/operator_headless.py` — **1640** checks / 0 FAIL (was 1625 before this pass; +12 from
the initial CON-054/CON-098 fixes, then CON-054's block was rewritten net +3 during Cody's review
remediation below — see that amendment — `EXPECTED_MIN_CHECKS` updated each time with its own
history comment). All new check groups mutation-verified: breaking `.verse.cursor
.verse-staged-pill`'s selector turned exactly the STAGED-pill-paint assertion RED; disabling the
`#emergency` blackout class toggle turned exactly the four re-tint assertions RED (the cleanup
assertion still trivially passed, as expected); after the CON-054 amendment, reverting the pill's
gating to `.cursor` turned exactly the browse-reproduction check RED, and mutating the host-match
comparison to always-true turned exactly the negative-control check RED. All restored to green.
Contrast figures independently recomputed in Python (WCAG relative-luminance ratio and CIELAB
ΔE76), not taken from either the original audit
or the in-code comment on trust.

### Totals (cumulative)

| | Count |
|---|---:|
| Total findings | 179 |
| FIXED (all reconciliations) | 28 (26 prior + `CON-054`, `CON-098` here) |
| Already fixed pre-reconciliation, doc corrected | 1 (`CON-097` — no code change) |
| FIXED (partial, not counted) | 1 (`CON-134`) |
| SUPERSEDED (owner Q2 decision) | 6 |
| **OPEN** | **145** (147 − 2, `CON-054`/`CON-098`; `CON-097` was never really open) |
