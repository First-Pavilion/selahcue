/**
 * Whether a page was reached from inside the app (a click or back/forward) rather than as the
 * first thing the visitor opened. Pure so it can be tested in node.
 *
 * vue-router records the previous in-app location in `history.state.back`; it is null on the
 * first entry of a session. See `useFocusHeading.ts` for why that decides where focus goes.
 */
export function cameFromInsideTheApp(historyState: unknown): boolean {
  if (typeof historyState !== 'object' || historyState === null) return false
  return (historyState as { back?: unknown }).back != null
}
