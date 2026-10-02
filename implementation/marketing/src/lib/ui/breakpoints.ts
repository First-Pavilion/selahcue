/**
 * The site's responsive breakpoints (design: MARKETING-PORTAL-GAP-FILL-HANDOFF.md section 8a).
 *
 *   desktop  >= 1200px   (as designed)
 *   tablet    768 - 1199 (gutters 48, 2-up grids)
 *   mobile   <  768      (gutters 20, 1-up, nav collapses to a sheet)
 *
 * NEAR-COMPLEMENTARY RANGES. Mobile is `max-width: 767.98px` and tablet starts at
 * `min-width: 768px` -- not `767px`, which leaves a whole pixel (767, 768) for fractional
 * viewport widths (browser zoom can produce 767.5px) where NEITHER range matches and a page
 * gets half of each layout. The `.98` form shrinks that to a 0.02px window, 767.98 to 768,
 * where only the base styles apply (hamburger nav, tablet gutter, JS "not mobile"). It is
 * not zero: Chromium and WebKit snap the layout viewport to integer widths, so in practice
 * only a fractionally zoomed Firefox can land there. Every `@media` below 768 in the SFCs
 * uses `767.98px` for the same reason; `tests/responsive.test.ts` pins that (and lists the
 * one whole-pixel exception), and the sweep renders 767/768 and 1199/1200.
 *
 * ONE SOURCE FOR JS. CSS cannot read this file, so the pixel values are repeated in the
 * SFCs' media queries. Anything that needs BOTH the CSS and the JS to agree on which side of
 * 768 it is on takes its mobile state from `MOBILE_QUERY` and styles off a class that JS
 * sets (see `Footer.vue`'s `.is-mobile`), so the two cannot diverge.
 */
export const MOBILE_MAX_WIDTH = 767.98

/** True below 768px. Used for behaviour CSS alone cannot express (nav sheet, footer sections). */
export const MOBILE_QUERY = `(max-width: ${MOBILE_MAX_WIDTH}px)`
