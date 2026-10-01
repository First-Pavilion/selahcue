/**
 * The site's responsive breakpoints (design: MARKETING-PORTAL-GAP-FILL-HANDOFF.md section 8a).
 *
 *   desktop  >= 1200px   (as designed)
 *   tablet    768 - 1199 (gutters 48, 2-up grids)
 *   mobile   <  768      (gutters 20, 1-up, nav collapses to a sheet)
 *
 * CSS cannot read these, so every `@media` rule in the SFCs repeats the pixel values; this
 * file is the one place JS reads them, and `tests/responsive.test.ts` pins that the two
 * stay in step.
 */
export const MOBILE_MAX_WIDTH = 767
export const TABLET_MAX_WIDTH = 1199

/** True below 768px. Used for behaviour CSS alone cannot express (nav sheet, footer sections). */
export const MOBILE_QUERY = `(max-width: ${MOBILE_MAX_WIDTH}px)`
