# Visual-parity harness

**What it is:** a measuring instrument that turns "pixel-perfect against Figma" from an assertion
into a number and a picture. It captures each surface, pairs it with the committed Figma frame,
scores the difference, draws the diff, and separates *defects* from *deliberate divergences*.

**What it is not:** a pass/fail gate on similarity. Nothing is converged yet, and a similarity gate
today could only be satisfied by lowering it.

```bash
python3 scripts/visual_parity.py                # capture everything, both web engines, compare
python3 scripts/visual_parity.py --engine webkit # closest-to-shipped web engine only
python3 scripts/visual_parity.py --only console  # one surface
python3 scripts/vp_selftest.py                  # prove the harness itself still bites
open .visual-parity/run-*/report.html

python3 scripts/visual_parity.py --suite marketing   # the marketing site + account screens (section 11)
```

---

## 1. The parts

| File | Role |
|---|---|
| `scripts/vp_core.py` | shared core: the two bounded stores, local SSIM, diff rendering, WCAG contrast |
| `scripts/vp_reference.py` | ingest/verify the committed Figma reference PNGs |
| `scripts/vp_capture_web.py` | screenshot the real operator `dist/` under **Blink** and **WebKit** |
| `scripts/vp_capture_native.py` | run the Rust renderer for the stage + audience output |
| `scripts/vp_compare.py` | pair, score, diff, run the deviation gate + contrast survey, write the report |
| `scripts/vp_selftest.py` | the harness's own gate — 112 controls (45 operator, 67 marketing), each demonstrated in both directions |
| `scripts/visual_parity.py` | orchestrator |
| `implementation/desktop/crates/selahcue-present/tests/visual_parity_render.rs` | the native renderer (also a real `cargo test` gate) |
| `docs/design/visual-parity/surfaces.json` | the capture catalogue — what, at what size, against which node |
| `docs/design/visual-parity/deviations.json` | the allowed-deviation list |
| `docs/design/visual-parity/reference/` | 13 committed Figma frame PNGs + `manifest.json` (2.1 MB) |
| `.visual-parity/` | run artefacts (gitignored, bounded to 5 runs) |

Nothing here is wired into `make ci` yet. See §9.

---

## 2. What it proves

### Similarity, per surface pair
Local (blockwise) SSIM over 8×8 blocks, per colour channel, reduced by the channel **minimum** —
plus mean per-pixel delta and the fraction of pixels differing by more than 12/255. Every pair also
gets a diff PNG: the capture desaturated, differences in red, low-SSIM blocks tinted blue so a
*displacement* shows even where the per-pixel delta is small.

**Why not `selahcue_engine::analysis::ssim`.** That function (`analysis.rs:151`) is a **global**
SSIM — one window over the whole image. It is the right oracle for its job (CPU-vs-GPU parity,
where the scene is identical and only rounding differs) and the wrong one here: global
mean/variance/covariance barely move when an element is displaced 30 px, which is exactly the
defect this harness exists to find. Measured on a synthetic frame:

| difference | this harness (local) | note |
|---|---|---|
| identical | 1.0000 | |
| 4 px shift | 0.7993 | |
| 12 px shift | 0.4749 | a global SSIM barely registers this |
| channel swap (chroma only) | 0.7457 | caught by the per-channel minimum |
| entirely different | 0.2454 | |

Same Wang et al. formula and the same C1/C2 constants as the crate's version, evaluated per block
rather than once globally.

### Accessibility, per declared region
A contrast survey that picks the threshold from the **rendered** text size, per PRD NFR-020
(`docs/product/prds/SelahCue-PRD.md:396`): 4.5:1 for normal text, 3:1 for large text **and**
non-text UI, where large = ≥24 px, or ≥18.66 px at weight ≥700. The useful output is not "this
pairing is under 4.5:1" — several Design 2.0 pairings legitimately sit between 3 and 4.5 behind
large type — but **"this pairing carries text too small for the ratio it has"**.

Contrast is computed **composited**. Three composition traps defeat any check that compares a
foreground token against a background token — which is the shape of most automated colour audits —
and all three are shipped in this codebase:

1. **A translucent fill over non-flat ground.** `button.golive .key` is `rgba(255,255,255,.18)`
   sitting on the GO LIVE gradient. White on the *composite* is **1.72:1**. Comparing `#fff` to the
   green endpoint gives ~1.91; comparing it to the chip colour gives 1.0. Neither is what a human
   sees. So a translucent layer is blended over everything still behind it rather than having its
   endpoints checked.
2. **A gradient needs every stop.** White on `#3ed39a` is 1.91:1 while white on `#28a579` is
   3.11:1 — the same button. The backdrop candidate set is carried forward as a *list*, so a
   translucent layer above a gradient produces one composite per stop.
3. **Opacity composes down the ancestor chain.** A `0.5` on a card leaves
   `getComputedStyle(control).opacity` reading `"1"` while a human sees 1.86:1. The harness walks
   the chain and multiplies; `scripts/operator_headless.py:1466` proves the same point
   behaviourally and is where this approach comes from.

`vp_selftest.py` pins three independently-measured shipped cases as fixtures the checker must
reproduce — **1.72:1** (`button.golive .key`), **3.27:1** judged at the 4.5 threshold
(`.pm-slide-live-badge`, white on `--sc-live` at 9px/700 — 9px is not large text), and **3.78:1**
(`.pm-btn-primary:hover`). A checker that cannot reproduce those is not ready, whatever it reports
elsewhere.

The same numbers are also measured **independently from the captured pixels** (see §5) and reported
alongside as corroboration. Measuring from pixels handles all three traps by construction; the
computed-style path is kept because it is deterministic, names which threshold it applied, and is
what goes red when the CSS changes.

### A wrong answer produced by a real check is worse than no check
`app.css:3899` reads *"Key hints on token-filled buttons: white for AA on the fill."* Someone ran a
check, got a passing number for `#fff` against the green, never saw the 18%-white chip in between,
and wrote the conclusion down. The comment now vouches for a 1.72:1 pairing. The harness is built
so it cannot produce that comment: every reported ratio names the composited ink, the composited
backdrop, the number of backdrop candidates evaluated, and the threshold applied.

Constants are held to the crate's: `vp_selftest.py` pins white-on-`--sc-primary` = 4.72,
white-on-`--sc-primary-hover` = 3.78, muted-on-surface = 3.79, secondary-on-surface = 8.12 — the
values `selahcue-present/tests/test_tokens.rs` asserts. Two contrast implementations that disagree
by a shade are a bug generator.

### That the capture actually happened
Asserted **before** any similarity number:

* a missing image, or a uniform (blank) frame where content was expected, is a **failure**, not a
  score — `vp_compare.py` says so in words ("the similarity number below would describe nothing
  that was rendered");
* a catalogued surface that never appeared in the run is a failure naming the surface — this fired
  for real when the native crate briefly failed to compile mid-run and the report would otherwise
  have said "0 failures" over the surfaces that survived;
* on the native side, `every_native_capture_renders_at_figma_size_with_the_expected_ink` asserts
  size and ink coverage on every ordinary `cargo test -p selahcue-present`, with the deliberate
  blackout frame as the positive control for the ink detector.

---

## 3. What it does **not** prove

Read this before quoting a number.

| Surface | Engine that produced the image | What that image is NOT evidence about |
|---|---|---|
| operator console + all web surfaces | **Blink** (headless Chrome 151.0.7922.173) | anything WKWebView-specific. Recorded defects in this codebase — a class `display` rule defeating the `hidden` attribute, flex `<select>` collapse, grid implicit-auto-row overflow past the footer — reproduce **only** in WebKit/WKWebView |
| operator console + all web surfaces | **WebKit** (Playwright WebKit 26.4) | WKWebView *inside a Tauri window*. Same engine family (WebCore/JavaScriptCore), different embedder, no Tauri IPC, possibly a different WebKit build than the OS one |
| stage / confidence, audience output | `selahcue-engine` CPU rasterizer | the wgpu-composited output window as it appears on a real display (the two are held to SSIM ≥ 0.99 by `selahcue-gpu/tests/test_parity.rs`, which is a bound, not identity), and nothing about window chrome, display scaling or colour management |

Further limits:

* **The host is stubbed.** Every web capture boots against the `window.__TAURI__` stub extracted
  from `operator_headless.py`. Fixture data, not a real service plan, real detections, real media
  or real installed fonts.
* **Not every Figma node is a screen.** `332:124` (3456×523), `336:124` (3192×661), `346:124`
  (2586×486), `349:124`, `351:124` and the palette board `310:124` are multi-state **spec boards**.
  A whole-frame diff against them is meaningless, so the harness marks them `board` and never
  scores them. Today none is captured at all — the states they specify are §8 work.
* **No interaction states.** Hover, focus rings, pressed, drag, transitions, modals, toasts, the ⌘K
  palette over a surface: not captured.
* **The pixel-sampled contrast is approximate for small antialiased text.** It is corroboration;
  the composited DOM value is what the deviation gate uses. Where the two disagree by more than
  50% the report says so rather than silently picking one.
* **Content differences inflate the score.** The native fixtures were aligned to the Figma frames'
  own copy for exactly this reason; the web captures still show stub content.
* **Nothing about mobile.** `implementation/mobile/` is untouched.

### Live findings from the first real run

Both are **defects, not deviations** — they are deliberately *not* on the allowed-deviation list, so
a full run currently exits 1. That is the harness working.

| region | measured (composited, from a real capture) | rendered | verdict |
|---|---|---|---|
| `#golive .key` ("⏎ Enter") | **1.72:1** — white on `rgba(255,255,255,.18)` over `#3ed39a` = `rgb(97,219,172)` | 11px / 600 | fails AA-normal **and** AA-large; no text-size argument rescues it |
| `#blackout .key` ("B") | **3.20:1** — `rgb(167,174,190)` on `rgba(107,115,131,.16)` over `#a3283a` = `rgb(154,52,70)` | 11px / 600 | fails AA-normal **and** AA-large |

The second one appears to be **new**: same class of bug, different rule (the generic `button .key`
at `app.css:3872` rather than the `button.golive .key` override at `:3899`). Both should be fixed
in `dist/app.css`, not exempted.

---

## 4. The allowed-deviation list

`docs/design/visual-parity/deviations.json`. Several Design 2.0 pairings **fail WCAG AA as drawn**,
so a naive "drive the diff to zero" harness would actively push us to ship accessibility failures.
Regions on this list are reported `INTENTIONAL`; regions not on it still have to converge.

**Every entry is a gate, not a comment.** Each carries a `requires` bound and a `measured` value,
and `vp_compare.py` re-measures from that run's capture. An entry whose region no longer meets its
bound goes **RED**. An entry that cannot fail would authorise the drift it exists to prevent: the
next reviewer reads "intentional" and moves on.

Each entry records:

* `requires.min`/`equals` **and** `requires.threshold` — an entry that does not name *which* WCAG
  threshold applies (`AA-normal` 4.5 vs `AA-large` 3.0) cannot be checked correctly;
* `figma` — what the source draws and what it measures, i.e. the known-bad value;
* `category` — `source-defect` (the Figma frame is wrong) vs `semantic-divergence` (our behaviour
  differs, so our visual must too);
* `permanence` + `retire_when` — without this someone will reasonably try to clear the whole list
  after a Figma correction, including the entries that must survive it.

### Current entries

| id | region | bound | measured | Figma draws | category |
|---|---|---|---|---|---|
| `golive-primary-ink` | `#golive` | ≥4.5 (AA-normal) | **5.34:1** | white on the green gradient (**1.91:1** light stop) | source-defect, permanent |
| `blackout-red-fill` | `#blackout` | ≥4.5 (AA-normal) | **7.19:1** | white on `--sc-live #ff4d4d` (**3.27:1**) | source-defect, permanent |
| `primary-gradient-darkened` | `.tb-golive`, `.timer-start` | ≥4.5 (AA-normal) | **4.72:1** | white on `--sc-primary-hover #7e6eff` (**3.78:1**) | source-defect, permanent |
| `closed-card-meta-ink` | `.scr-card-meta` | ≥4.5 (AA-normal) | **8.12:1** | `--sc-text-muted` (**3.79:1** on surface) | semantic-divergence, permanent |
| `closed-card-dimming-scoped-to-thumbnail` | meta, name, pill | effective opacity = 1.0 | **1.0000** | whole-card dim (**1.86:1** composited) | semantic-divergence, permanent |
| `closed-card-thumbnail-is-dimmed` | `.scr-thumb` | effective opacity = 0.5 | **0.5000** | — (positive control) | semantic-divergence, permanent |
| `closed-built-in-reads-CLOSED` | `.scr-pill` | text matches `CLOSED`, not `MUTED` | **`● CLOSED`** | `MUTED` | semantic-divergence, permanent |

The last two are worth naming: `closed-card-thumbnail-is-dimmed` is the **positive control** for
the entry above it. Without it, "the controls are not dimmed" would also pass if the dimming
mechanism were deleted entirely — a dead mechanism and a correctly-scoped one would be
indistinguishable.

### Proving an entry can fail

Copy `dist/` to a scratch directory, revert the region to the Figma value, point the harness at the
copy with `SELAHCUE_OPERATOR_DIST`, and confirm the entry goes RED. **Never mutate the real
`dist/`** — the checkout is shared.

```bash
cp -R implementation/desktop/crates/selahcue-operator/dist /tmp/mutdist
# ...edit /tmp/mutdist/app.css: button.golive { color: #ffffff }  (the Figma value)
SELAHCUE_OPERATOR_DIST=/tmp/mutdist python3 scripts/vp_capture_web.py --out /tmp/mutrun/web \
    --engine blink --only console
python3 scripts/vp_compare.py --run /tmp/mutrun --allow-missing
```

All seven entries were verified this way. Results (each RED entry reproduces the known-bad value
exactly, while its siblings stay `INTENTIONAL` — the failure is targeted, not a blanket red):

| mutation | result |
|---|---|
| `button.golive` ink → `#ffffff` | `FAIL golive-primary-ink … composited **1.91:1** vs required 4.50:1` |
| `#blackout` fill → `var(--sc-live)` | `FAIL blackout-red-fill … composited **3.27:1** vs required 4.50:1` |
| `.tb-golive`/`.timer-start` gradient top → `--sc-primary-hover` | `FAIL primary-gradient-darkened … composited **3.78:1**` (both regions) |
| `.scr-card-meta` ink → `--sc-text-muted` | `FAIL closed-card-meta-ink … composited **3.79:1** vs required 4.50:1` |
| dimming re-broadened to `.scr-card` | `FAIL … effective opacity **0.5000**, required 1.0000` on all three controls, and the meta contrast collapses to **2.97:1** |
| both of the above together (the full Figma treatment) | `FAIL … composited **1.86:1** … at opacity 0.500` — the historically recorded defect value |
| pill label `CLOSED` → `MUTED` | `FAIL closed-built-in-reads-CLOSED … rendered text '● MUTED'` |

`vp_selftest.py` also carries these as in-harness controls, so the gate's ability to fail is
re-proved on every self-test run without touching any file.

---

## 5. How a number is produced

**Local SSIM.** Pillow only — there is no numpy on this box. Per channel: convert to `"F"`, square
and cross-multiply with `ImageMath.unsafe_eval`, take per-block means with a C-path
`Image.resize(..., Image.BOX)`, combine, reduce the three channels with `min`. ~0.03 s for
1760×1000. No Python per-pixel loop anywhere.

**Composited contrast (the gate).** From the DOM record the capture driver emits alongside every
screenshot: the element's colour, font size/weight, and the full ancestor chain with each
ancestor's own `opacity`, `background-color` and `background-image`. Backdrops resolve to the
nearest painted layer — **every stop** if it is a gradient — composited down onto whatever is
behind it. Deterministic, and it goes red when the CSS changes.

**Pixel-sampled contrast (corroboration).** Straight from the screenshot crop, immune by
construction to every compositing assumption above. Colours are grouped into 5-bit-per-channel
buckets first — this step is load-bearing: in a 300 px-wide gradient every individual RGB value
occupies one thin column and holds well under 1% of the crop, so a population filter over *exact*
colours discards the entire background and leaves only the text, reporting ~19:1 for a button that
measures 7.19:1. Each surviving bucket keeps its most populous exact colour, so precision is not
lost. It returns `None` — not a number — when no ink population is large enough to measure
honestly; a refusal is the right answer for a 10 px label whose glyph core never covers half a
percent of its box.

Agreement on solid fills is exact (`topbar-golive` and `timer-start` both read 4.72:1 by either
method; `blackout-button` 7.19 vs 7.24). On small antialiased text the pixel method is pulled
toward the antialiasing halo and reads low. That is why it corroborates rather than gates.

---

## 6. Bounds

Two stores, two different correct behaviours:

* **Reference store** (`docs/design/visual-parity/reference/`, committed): capped at
  `MAX_REFERENCE_ENTRIES = 32` **and** `MAX_REFERENCE_BYTES = 24 MB`. A byte budget alone admits
  unboundedly many tiny entries; an entry count alone admits one enormous one. An ingest that would
  breach either cap **raises `StoreFull`** — it never evicts, because every entry is a checked-in
  artefact somebody chose to keep. Currently 13 entries / 2.1 MB. `verify` also fails on checksum
  drift, a dimension that no longer matches the catalogue, an orphan PNG, or a catalogued reference
  that was never ingested.
* **Run store** (`.visual-parity/`, gitignored): `prune_runs` keeps the newest
  `MAX_RUNS_KEPT = 5` run directories and deletes the rest. Each run writes ~30 images; without
  eviction the artefact root grows linearly and forever. The five kept runs are shared by BOTH suites: the operator
  suite writes ~31 MB at 5 runs, and one marketing run is 18.5 MB on Blink and 39.7 MB with `--engine both`, so the
  ceiling is about 200 MB (5 x 39.7 MB), not 35 MB (§11).
* **Per-run file cap** (`MAX_FILES_PER_RUN = 200`): a *second, independent* bound, because run
  eviction caps how many runs survive, not how large one run may get — a per-state loop writing N
  images per surface would grow a single run without limit and never trip the run-count cap.
  `vp_compare.py` fails the run if it is exceeded, and `vp_selftest.py` asserts that vp_compare
  actually reads it, because a declared-but-unchecked bound is decoration.
* **Native captures** overwrite a fixed set of filenames.
  `native_captures_are_idempotent_and_bounded` runs the writer twice and asserts the file count is
  unchanged — which is what bites if someone makes the filenames run-unique and turns the output
  directory into an unbounded image dump. `CAPTURES.len() <= MAX_NATIVE_CAPTURES` is pinned with
  `const _: () = assert!(…)`, plus a second pin that the cap keeps headroom, so the bound cannot
  quietly become "however many captures we happen to have".

Each of these is mutation-verified in `vp_selftest.py`, in both directions — the cap refuses the
overflowing entry **and** still accepts a replacement at the cap; the prune evicts the oldest
**and** a second prune under the cap deletes nothing.

---

## 7. Environment (verified 2026-08-23, this box)

| thing | status |
|---|---|
| headless Chrome | **available** — `Google Chrome 151.0.7922.173` at the macOS app bundle path |
| Playwright WebKit | **available** — `Playwright WebKit 26.4`, launches and screenshots |
| Playwright Chromium / Firefox | **not installed** (revision mismatch); irrelevant, the Chrome CLI covers Blink |
| numpy | **not installed** on any interpreter here — the harness is Pillow-only by necessity |
| Pillow | 11.3.0 |
| GPU parity path | not exercised — `selahcue-gpu` needs a GPU and is out of scope here |

**Chrome viewport trap, defused.** `chrome --headless=new --window-size=W,H --screenshot` writes a
`W×H` PNG but lays the page out at `innerHeight = H − 87` (macOS window chrome) while the driver
runs, then re-renders at `H` for the capture. Region rects measured by the driver would be offset
from the pixels they claim to describe — a silently wrong contrast sample. The Blink path probes
that delta once, runs the **measurement** pass at `H + delta` (asserting `innerHeight == H`), and
the **screenshot** pass at `H`. The WebKit path sets an exact viewport and has no such gap.

### Can `operator_webkit_smoke.py` be extended to capture WKWebView screenshots?

**Partly — and the harness already does the achievable part.** Playwright WebKit is installed and
working here, and `page.screenshot()` on it produces exact-viewport images of the real `dist/`
(`vp_capture_web.py --engine webkit`). That is a genuine upgrade on Blink: same engine family as
the shipped WKWebView, so an engine-specific CSS/JS break has a real chance of showing.

What it still is **not** is WKWebView inside a Tauri window. Blocking that:

* Playwright drives its own WebKit build, not the OS `WKWebView` framework — version skew is
  possible and unmeasured;
* no Tauri IPC, no Tauri window chrome, no `wry` webview configuration;
* the three recorded WKWebView defects were found in the *real app*, and only a real-app screenshot
  can confirm they are gone.

A genuinely WKWebView-backed automated capture would need a small macOS host that loads `dist/` in
a real `WKWebView` and calls `takeSnapshot(with:)` — not built here, and it would still lack Tauri.
Until then the shot list below is how that gap is covered.

---

## 8. Shot list for manual capture

What automation here cannot reach. Every shot: **the real running app** (`make launch`), operator
window sized to **1760×1000** unless stated (Screens & Outputs at **1760×1154** to match its
frame), a real service plan loaded, PNG, no window shadow if avoidable.

Reason codes: **W** = only a real WKWebView-in-Tauri can show it · **D** = needs real host data the
stub cannot fake · **N** = native output window on a real display · **I** = interaction/motion state.

| # | Screen | State to have on screen | Size | Why automation can't |
|---|---|---|---|---|
| 1 | Operator Console (`312:124`) | idle, plan loaded, nothing live | 1760×1000 | W, D |
| 2 | Operator Console | an item **live** + a different item **staged**, real preview/live thumbnails | 1760×1000 | W, D |
| 3 | Operator Console | **BLACKOUT engaged** (footer + topbar mirror both in engaged state) | 1760×1000 | W |
| 4 | Operator Console | Service Timer **running**, and a second shot at **TIME UP** | 1760×1000 | W, D |
| 5 | Operator Console | Detected Scriptures rail with **real detections** (≥3 cards, mixed confidence) | 1760×1000 | W, D |
| 6 | Operator Console | Live Transcript actively **listening** with real transcript text | 1760×1000 | W, D |
| 7 | Service Plan | a **long** plan (≥20 items) scrolled mid-list, one item being dragged | 1760×1000 | W, D, I |
| 8 | Screens & Outputs (`327:124`) | ≥2 physical displays connected, one screen **CLOSED**, one virtual feed **MUTED** | 1760×**1154** | W, D |
| 9 | Screens & Outputs | the `<select>` output-assignment dropdown **open** | 1760×1154 | W, I — flex `<select>` collapse is a known WKWebView-only defect |
| 10 | Presentation & Media (`329:124`) | a real deck open, canvas editing an element, real media thumbnails in the library | 1760×1000 | W, D |
| 11 | Presentation & Media | media library with a **missing** asset and a video asset | 1760×1000 | W, D |
| 12 | Theme Designer (`317:124`) | a theme mid-edit with the **native preview** populated, system font picker open | 1760×1000 | W, D, I |
| 13 | Settings (`338:124`) | Providers & Privacy, **cloud connected**, a real quota meter | 1760×1000 | W, D |
| 14 | Settings | scrolled to the **bottom** of the longest section | 1760×1000 | W — grid implicit-auto-row overflow past the footer is WKWebView-only |
| 15 | Pre-service Check (`344:124`) | a real run with a **mix** of pass / warn / fail rows | 1760×1000 | W, D |
| 16 | Remote Control · Devices (`359:124`) | pairing **QR visible**, ≥1 paired device, ≥1 pending request | 1760×1000 | W, D |
| 17 | App shell (`336:124`) | ⌘K command palette **open** over the console | 1760×1000 | W, I |
| 18 | Any surface | a **focus ring** on a control (Tab to it) and a **hover** state on a primary button | 1760×1000 | W, I |
| 19 | Audience output window | a scripture slide **live**, fullscreen on the real display | display native | N |
| 20 | Audience output window | **blackout** engaged | display native | N |
| 21 | Stage / confidence window | each of Worship / Scripture / Timer-only, **running**, on a real display | display native | N |
| 22 | Stage / confidence window | Worship at **TIME UP**, and Timer-only at **TIME UP** (full screen) | display native | N |
| 23 | Stage / confidence window | a **stage message** banner over dimmed content | display native | N |
| 24 | Output windows | the **display-identify** overlay showing on two displays at once | display native | N |

Shots 1–18 are the ones the automated web captures approximate; the value of the manual versions is
that they are WKWebView-in-Tauri with real data. Shots 19–24 have no automated counterpart at all
beyond the CPU-raster PNGs — those show the *composition*, not the window on a display.

Drop them in a directory and they can be ingested as additional references or compared ad hoc:

```bash
python3 scripts/vp_reference.py ingest --slug console-real --node 312:124 --file ~/shots/01.png \
    --note "manual WKWebView capture, real plan data"
```

---

## 9. CI

Deliberately **not** wired into `make ci` yet:

* the web capture needs Chrome (already a `make ci` dependency, loudly skipped without it) *and*
  Playwright WebKit (not a CI dependency today);
* a full run is ~30 Chrome/WebKit launches, ~90 s;
* similarity is not gated, so the only CI-worthy signal is the deviation gate and the contrast
  survey.

Two things are already CI-safe and cheap, and are the sensible first step:

```bash
cargo test -p selahcue-present --test visual_parity_render   # native captures render + are non-blank
python3 scripts/vp_selftest.py                               # 112 harness controls, no browser needed
```

`scripts/operator_headless.py` is untouched and still reports **640 checks, 0 FAIL**;
`EXPECTED_MIN_CHECKS` was not lowered. `vp_capture_web.py` *reuses* that file's `__TAURI__` stub by
extracting the literal at run time rather than copying it, so the behavioural gate and the
screenshotter cannot drift into stubbing different applications.

---

## 10. Baseline (run 2026-08-23, both engines)

Similarity today — reported, not gated. Higher is closer; 1.0 is identical.

| surface | Blink | WebKit | CPU raster |
|---|---|---|---|
| console `312:124` | 0.5536 | 0.5562 | — |
| settings `338:124` | 0.5703 | 0.5700 | — |
| theme-designer `317:124` | 0.6012 | 0.6087 | — |
| screens `327:124` | 0.6266 | 0.6303 | — |
| presentation `329:124` | 0.6676 | 0.6688 | — |
| preservice `344:124` | 0.6913 | 0.6921 | — |
| remote `359:124` | 0.7095 | 0.7063 | — |
| stage-worship-timeup `373:159` | — | — | 0.6650 |
| stage-scripture-running `374:128` | — | — | 0.6935 |
| stage-worship-running `373:133` | — | — | 0.7115 |
| stage-message `375:128` | — | — | 0.7269 |
| stage-timer-only-running `374:151` | — | — | 0.8467 |
| stage-timer-only-timeup `374:166` | — | — | 0.8967 |

Blink and WebKit agree to within ~0.008 on every surface, which is itself a finding: **at this
distance from the design, the engine difference is noise.** Engine-specific defects will only become
visible in these numbers once a surface is close to converged — which is another reason the manual
WKWebView shots matter now rather than later.

Captured but deliberately not scored: `console-blackout`, `screens-closed`, `plan`,
`audience-scripture-live`, `audience-blackout` — no 1:1 Figma frame depicts them.

---

## 11. The `marketing` suite — the website and account screens (ClickUp 17tnw2b2c75)

The harness was written for the desktop operator. The marketing site (16 pages) and the auth/account/device
states (19 frames) are a **second suite of the same instrument**: same comparator, same bounded stores, same
deviation gate. Each suite names its own catalogue, deviation list, reference store and caps
(`vp_core.get_suite`), so growing one cannot push the other over its bound.

```bash
(cd implementation/marketing && npm ci && npm run build)    # the capture serves dist/ and refuses a stale one
python3 scripts/visual_parity.py --suite marketing           # capture 35 surfaces (Chromium) + compare; ~2 min
python3 scripts/visual_parity.py --suite marketing --engine both --only home pricing
python3 scripts/vp_style_diff.py --slug signin --dom .visual-parity/run-<stamp>/marketing/signin.blink.dom.json --limit 0
python3 scripts/vp_slice.py --slug home --run .visual-parity/run-<stamp> --y 900 --h 900 --out /tmp/home-900.png
python3 scripts/vp_reference.py --suite marketing verify     # 35 references + 35 style dumps, caps, checksums
python3 scripts/check_fidelity_audit.py                      # the audit data is complete and consistent
```

### The parts that are new

| File | Role |
|---|---|
| `scripts/vp_capture_marketing.py` | serves `dist/` with SPA fallback, drives Playwright at 1440 wide, scripts the account API (`page.route`), writes a full-page PNG and a bounded DOM/computed-style dump per surface |
| `scripts/vp_style_diff.py` | compares **values**: Figma's text/box styles against the DOM dump (size, weight, line height, colour, alignment, position, radius, fill, border, copy only on one side) |
| `scripts/figma_extract_style.js` | the **read-only** `use_figma` snippet that produces the Figma side of that comparison |
| `scripts/vp_slice.py` | Figma and build side by side for one slice of a long page, for a human to read |
| `scripts/check_fidelity_audit.py` | structural checker, summariser and report writer for the audit data; self-tested (34 controls) |
| `scripts/build_fidelity_artifact.py` | builds the stand-alone side-by-side page (Figma beside the build, every finding) from the audit data and a run |
| `docs/design/visual-parity/marketing/surfaces.json` | the 35 frames: node id, route, scripted state, status (`captured` / `unbuilt` / `not-rendered`) |
| `docs/design/visual-parity/marketing/reference/` | 35 committed Figma PNGs at native size + `manifest.json` (node ids, sizes, SHA-256) |
| `docs/design/visual-parity/marketing/figma-style/` | 35 committed style dumps, one per frame, registered in the same manifest |
| `docs/design/visual-parity/marketing/findings/*.json` | the audit's findings, one file per area; `tickets.json` maps each area to its fix ticket |
| `docs/design/visual-parity/marketing/deviations.json` | the marketing allowed-deviation gate (metrics below) |

### What is different from the operator suite, and why

* **Pages are long and their height legitimately differs from the frame's** (the build carries the real legal
  drafts where Figma drew a placeholder). Stretching one image to the other would turn a content difference into a
  phantom layout difference everywhere, so the pair is compared **top-aligned over the shared height** and the
  height delta is reported as its own number (`vp_compare.align_top_crop`; self-tested against a stretch).
* **Inter must have loaded.** Figma is drawn in Inter; a fallback face re-wraps text and invents layout differences
  the code does not have. A capture whose `document.fonts.check("600 16px Inter")` is false is refused.
* **A stale bundle is refused.** A screenshot of last week's build would score as a result and describe nothing
  that ships (`vp_capture_marketing.dist_problem`).
* **Two statuses besides `captured`, each gated both ways.** `unbuilt` (the Manage Devices states): the capture
  visits the route and **fails if it stops rendering the site's 404 view**, so the flag cannot outlive the screen.
  `not-rendered` (V4 and R5, which the handoff says are deliberately not shipped until the backend can prove expiry):
  `vp_compare` probes the **shipped bundle** (`dist/assets/*.js`, not source comments) for the forbidden copy and
  fails if it appears; the probe carries a control string that must be present, or a probe over the wrong folder
  would pass for every state.
* **The deviation gate reads the page, not the pixels.** Metrics: `doc_height` (the page is at least N px tall),
  `text_present` and `text_absent` (a regex over every rendered text node: the honest-content decisions).
  Each can fail and each is demonstrated failing in `vp_selftest.py`.
* **Contrast is surveyed, not gated.** `vp_compare` lists every text node whose colour-on-backdrop is below the
  AA threshold its own size demands. A gradient/image backdrop is reported `unknown`, never given a made-up number.
  It is reported rather than gated because the audit exists to record those findings; gate it per page once a page
  has been through the accessibility fix.
* **The Figma legacy colours versus the code `--sc-*` tokens are a deliberate layer**
  (`AUTH-LANDING-PAGES-HANDOFF` 2.2). `vp_style_diff` labels a colour `colour~` only when the build's value equals
  the mapped token; a colour used in the wrong *role* is `colour`, not excused.

### Environment (verified 2026-10-03)

The Python scripts need Pillow and Playwright (Chromium; WebKit for `--engine both`) in the interpreter that runs them. On this box that is
`/usr/bin/python3` 3.9.6 (Pillow 11.3, Playwright with Chromium 148 and WebKit 26.4). A Homebrew `python3` earlier on `PATH` has neither: the scripts then stop
with "visual-parity harness needs Pillow", which is the right outcome and not a defect. The capture also needs network to load Inter from Google Fonts (a capture
without Inter is refused), and `npm run build` in `implementation/marketing` first.

### Bounds

Every cap below has a control in `vp_selftest.py` that **fails when the cap is removed**; each was proved by deleting the cap on a scratch copy
of `scripts/` and watching the named control go red. That proof is repeatable, not a one-off: `docs/design/visual-parity/marketing/mutations.json`
lists one edit per control (75 today: the caps, the banding, the fail-closed gates, the wiring paths, the checker's rules and the proof tool's own guarantees) and
`python3 scripts/vp_mutation_proof.py` applies each to a scratch copy and requires the named self-test to exit non-zero. These all fail the run: a mutation that does not
apply (the code moved), a self-test that survives, a self-test that **hangs** (a hang proves nothing; it is killed with everything it started, in its own process group),
and an **unmutated** copy that does not pass its own self-test first (the baseline). The scratch copy holds real copies of `scripts/`, `docs/` and `implementation/marketing/`
(no `node_modules` or `dist`) and a scratch git repository that reads the real object store through git's `alternates` file; an earlier version symlinked `docs/`,
`implementation/` and `.git`, and a symlink writes through, so that guarantee was false. As belt and braces the real checkout's HEAD, `git status` and a digest of every
modified or untracked file's content are compared before the first and after the last mutation, and the run fails if anything changed (do not edit the tree while it runs).
`--self-check` (about 20 seconds) proves those guarantees with synthetic cases, and each is itself in `mutations.json`. `--only ID ...` runs some, `--list` prints them.
The full run takes about 5 to 6 minutes (248 seconds at 62 mutations), which is why it is not in `make ci`: re-run it after changing a cap, a gate or a
checker rule. A cap with no such control is not listed here.

| bound | cap | what refuses | the control that fails without it |
|---|---|---|---|
| reference store: PNGs **and** style dumps | 48 entries, 12 MB (35 entries, 6,335,237 bytes today) | `ReferenceStore.ingest` / `register_style` refuse, never evict | `test_marketing_suite_has_its_own_bounded_store`, `test_style_dump_registration_is_validated_and_bounded` |
| style dump | 2500 nodes (`MAX_STYLE_NODES`); the extractor caps itself at 1500 and a capped dump is refused | `register_style` | `test_style_and_figma_node_caps_bite` |
| style diff inputs | 2500 nodes per file (`vp_style_diff.MAX_NODES`) | `load_figma`, `load_dom` | `test_style_and_figma_node_caps_bite` |
| DOM dump | 1500 items (`MAX_DOM_ITEMS`) and 80 focus entries (`MAX_FOCUS_ITEMS`), re-imposed in Python after the page returns; a truncated dump **fails the capture and the comparison** | `enforce_dump_caps`, `capture_entry`, `load_dom_checked` | `test_dump_and_call_caps_bite`, `test_capture_entry_wiring`, `test_comparator_main_wiring` |
| recorded GraphQL calls and held requests | 50 each (`MAX_CALLS`) | `_bind_api` | `test_dump_and_call_caps_bite` |
| settle wait | 5000 ms (`MAX_SETTLE_MS`) | `capture_entry` | `test_capture_entry_wiring` |
| decoded pixels | 60 Mpx (`MAX_CAPTURE_PIXELS`), read from the file header and refused **before** decoding; a page that large is also refused before it is photographed; the refusal quotes the measured comparison cost (234 MB + 12.2 MB per Mpx), pinned by the same test | `pixel_budget_problem`, `vp_compare.main`, `capture_entry`, `encode_image` | `test_pixel_budget_refuses_before_decoding`, `test_capture_entry_wiring` |
| comparator memory | similarity, the diff picture and pixel statistics are computed in 512/1024-row bands; peak 623 MB on today's 35 surfaces (was 1.16 GB), same scores to 1e-9; switching banding off costs 745 MB to 971 MB on a 41.6 Mpx capture; measured cost model: peak = 234 MB + 12.2 MB per captured Mpx (489 MB at 20.8 Mpx, 947 MB at 58.2 Mpx) | `block_ssim`, `diff_image`, `pixel_delta_stats`, `ink_coverage` | `test_banded_similarity_equals_the_whole_image_result`, `test_banding_bounds_the_rows_each_step_holds` (the band count and band height of every step), `test_pixel_statistics_are_pinned` |
| run size | 300 files per marketing run (`MARKETING_MAX_FILES_PER_RUN`): 35 surfaces x 3 files (screenshot, diff, DOM dump) x 2 engines + 4 run-level files = 214 at the most; 172 today; the 3 report files still to be written are counted; the oldest of 5 runs is evicted | `vp_compare.run_files_problem` (driven end to end through `main`), `prune_runs` | `test_per_run_file_cap_is_enforced`, `test_comparator_main_wiring` |
| bundle probe | at most 400 `.js` files (`MAX_PROBE_JS_FILES`), counting only `.js`; a bundle over the cap **fails** the probe | `source_probe_problem` | `test_bundle_probe_counts_only_js_and_fails_at_its_cap` |
| `vp_slice` output | 12 Mpx (`MAX_OUT_PIXELS`), computed from the requested numbers **before any crop is allocated** | `plan_slice` | `test_slice_output_cap_is_checked_before_allocation` |
| artifact page | 80 images and 13 MB (`MAX_IMAGES`, `MAX_TOTAL_BYTES`), both checked before any file is written; encoding stops at the image that crosses the byte cap | `build_fidelity_artifact.build` | `test_artifact_builder_caps_refuse_before_writing` |
| capture server | one daemon thread running `serve_forever` on 127.0.0.1 with one short-lived daemon handler thread per connection (`ThreadingMixIn`); serves `dist/` only, no cache, path-traversal guarded | `_Handler._serve` | `test_capture_server_is_confined` |

**Ctrl-C.** A KeyboardInterrupt during a capture skips the Playwright teardown and exits 130: closing a context after an interrupt spins
at 100% CPU with the driver and every browser still alive (reproduced 3 of 3 by the performance review). The skip is covered by
`test_capture_entry_wiring` (the context is not closed on an interrupt). The end-to-end behaviour needs a browser, so it was checked by hand on a real
capture of the real catalogue, the capture started in its own session and every process attributed to it by ancestry and by its own
`--user-data-dir` (never by "new since I started": other agents run browsers on this machine too), each case against the code before and after the fix:
- SIGINT to the whole process group (what Ctrl-C does): before, the python never exited in 30 seconds and spun at 99% CPU; after, it exited 130 in 0.5 seconds with none of its processes left.
- SIGINT to the python process alone (`kill -INT <pid>`): before, it spun at 100% CPU and left 4 browser processes alive; after, it exited 130 in 0.4 seconds with none left.
Anything the test started was removed afterwards by exact PID.**Scores are reproducible to about +-0.001.** The same code on the same machine produced fourth-decimal differences on 7 of 29 pairs
(up to 0.0010, e.g. Home 0.6439 then 0.6431): text edges antialias slightly differently between runs. No verdict changes at that size.
Quote a score to two decimals.

**Disk.** The reference store adds 6.3 MB to every clone for good (history keeps replaced exports): re-ingest only the frames that changed, and
consider Git LFS before adding a second viewport suite.

### Extracting a Figma frame's style dump

`use_figma` is used **read-only**. Paste `scripts/figma_extract_style.js` with `__NODE_ID__` replaced, save the JSON it
returns verbatim as `docs/design/visual-parity/marketing/figma-style/<slug>.json`, then
`python3 scripts/vp_reference.py --suite marketing style --slug <slug>` (or `--all`). Registration checks that the dump names the
reference's node, has text and box lists, and was not capped.

### Using it for a fix ticket

A fix ticket for an area re-runs `visual_parity.py --suite marketing --only <its slugs>` and `vp_style_diff.py` for each,
and shows that every remaining difference is a documented B (with its source), C or D. A fix is not finished while a class A
line is still printed for its surfaces. `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` is the starting list.

### The deviation gate was proven to go red on real captures

Each marketing entry was mutated on a scratch copy of a real run and the comparator re-run (`vp_compare --suite marketing`, with
`SELAHCUE_MARKETING_DIST` pointing at a copied `dist/`): the privacy page's height set back to the Figma placeholder's 1772px turned
`legal-pages-render-the-real-drafts-privacy` red; removing the disabled-state copy turned `download-actions-are-honest-disabled-states` red; adding
"Continue with Google" to the Sign in dump turned `signin-has-no-google-button` red; appending V4's title to a copy of the bundle turned the
`verify-v4` bundle probe red. In every run only the mutated entry failed; its siblings stayed `INTENTIONAL`. Never mutate the real `dist/` or a
committed run: the checkout is shared.

### The audit data

`findings/*.json` (one file per audit area) hold every difference, each with a class A to E, severity, Figma and build values, evidence and fix/source/
decision as the class requires. A finding may carry `dup_of` (the same defect seen again on another page: shown, counted once under the canonical
finding) or `owned_by` (a ClickUp id: an A that another ticket already owns, so it raises no fix here). `check_fidelity_audit.py` enforces the rules and
`--write-report` renders `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` from the data, and `--check-report` fails when the committed report
no longer matches what the data would render (a finding edited without regenerating it).

The checker reads meaning, not just shape. It rejects: an `owned_by` that is not one of the five approved owner tickets, is on anything but a class A, or
exempts more than 10 findings; a `dup_of` that points at a finding of another class or another area (unless that one is shared); a figma/build/fix/decision
text too thin to act on; a class B finding whose source cites nothing that resolves (a document, a decision, a file or a commit that exists, and a contrast
figure that recomputes); a surface list that is not the 16 pages and 19 states of the catalogue with the right Figma node ids; a finding naming a ticket that
does not exist or belongs to another group; a ticket url that is not exactly `https://app.clickup.com/t/<id>` (the url becomes an `href` on the Artifact
page, and `javascript:` would run); a bug with no group; an api gap with an invented status; and findings files that audited different commits.
`--require-tickets` adds that every class A and E finding names its ticket. Each rule has a control in `--self-test` and a mutation in `mutations.json`.

**Shallow clones.** The commit checks (a class B source that cites `commit <sha>`, and the audited `origin_main`) need history. In a shallow clone, which is what `actions/checkout` makes by default, a commit that is not reachable may just be cut off, so there it means "cannot tell" (the same answer as when git is missing) and does not fail; in a full clone a made-up commit still fails. The controls run against a scratch repository built inside the self-test (a full one and a `--depth 1` clone of it), so none depends on this repository's history; a `--depth 1` clone of the branch passes `--check-report`, `--self-test` and `vp_selftest.py`. Any CI job that runs these should still check out with `fetch-depth: 0`, so the commit checks actually run.

### Self-test

`python3 scripts/vp_selftest.py` (206 checks) carries the marketing controls alongside the operator ones (suite caps, style registration,
top-crop alignment, bundle probe and freshness, the three deviation metrics, DOM contrast, style-diff pairing and detection, box
diff, catalogue validation, server confinement, committed references, and the capture and comparator wiring driven through the real entry points with
fake pages and synthetic runs). `python3 scripts/check_fidelity_audit.py --self-test` (97 checks) proves the audit checker rejects each kind of
incomplete audit. Neither is in `make ci` yet: that is a separate ticket, [CI] Run the visual-parity self-test and the audit checker's self-test in
`make ci` and CI (ClickUp 17tnw2b2fum, linked to the CI-masking ticket 86ak5rjh7); it was kept out of this change on purpose, so that a change to
what `make ci` runs is reviewed on its own.


### Pipe-safe capture commands (17tnw2b1wpc)

The Blink viewport probe, capture passes and version probe, marketing auth gate,
and native raster collector use `scripts/headless_chrome.py`'s shared file-backed
process lifecycle. A completed command returns after its own PID exits, even if a
background helper still holds stderr. In-group helpers and temporary stdout/stderr
files are cleaned after success, timeout or interruption. Escaped Chrome shared
services retain the helper module's documented ownership limits.

HTML callers retain their private page file. Existing local files and the auth
gate's already running HTTP server use `page_html=None, page_url=url`; flags and
URLs pass through unchanged. Do not add a temporary Chrome `--user-data-dir` or
redirect TMPDIR; the helper module documents the macOS failures those cause.

Native capture still runs the exact `cargo test` target shown above with
`SELAHCUE_VISUAL_OUT` and collects its PNG/index protocol. It gets no Chrome flags
or Chrome litter sweep. The whole Cargo command now has a600-second wall limit;
a real timeout prints `FAIL: the native capture target timed out (infra)` and
returns1 without accepting any partial index. This is a bounded build/render
allowance, not a measured claim about cold builds. Prebuild the target with the
same manifest/profile/features when preparing a slow or cold machine; for builds
that legitimately need longer, finish that build separately before running the
collector. For the default profile/features, the prebuild command is:

```sh
cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-present --test visual_parity_render --no-run
```

There is no new operator override or silent unbounded mode.

Run `python3 scripts/test_pipe_safe_launchers.py` to exercise all three actual
callers with interpreter-backed commands (no executable temporary scripts), held
descriptors, complete-looking hangs, missing protocol results and nonzero exits.
The existing always-run Linux workflow gate also runs it using the documented
Pillow dependency. Real browser/render assertions remain separate gates; these
fixtures make no claim about raster pixels or a real Cargo build's duration.
