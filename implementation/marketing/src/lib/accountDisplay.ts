/**
 * Pure display rules for the Account page (ClickUp 17tnw2bhkd2).
 *
 * Kept out of the view so they run under `node --test`. Dates are always UTC: the API
 * speaks UTC, and a church office in another zone must not see a different day from the
 * desktop app. Quota values arrive as decimal STRINGS (a counter can pass 2^53), so they
 * are handled as BigInt and never through `Number`.
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "5 May 2027" in UTC, or '' when the text is not a timestamp. */
export function formatAccountDate(iso: string): string {
  const at = new Date(iso)
  if (iso === '' || Number.isNaN(at.getTime())) return ''
  return `${at.getUTCDate()} ${MONTHS[at.getUTCMonth()]} ${at.getUTCFullYear()}`
}

/**
 * The last day of a plan whose end is EXCLUSIVE: 2027-05-06T00:00:00 means the plan runs
 * through 5 May. One millisecond is taken off before formatting. '' when null or unreadable.
 */
export function formatPlanEnd(iso: string | null): string {
  if (iso === null) return ''
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return ''
  return formatAccountDate(new Date(at.getTime() - 1).toISOString())
}

function counter(text: string): bigint | null {
  return /^\d+$/.test(text) ? BigInt(text) : null
}

/** Seconds (as a decimal string) as whole minutes, rounded down; null when unreadable. */
export function wholeMinutes(seconds: string): string | null {
  const value = counter(seconds)
  return value === null ? null : (value / 60n).toString()
}

export interface QuotaFigures {
  remaining: string
  limit: string
}

/** "120 min left of 180"; '' when either figure is unreadable. */
export function minutesLeftLine(quota: QuotaFigures): string {
  const left = wholeMinutes(quota.remaining)
  const of = wholeMinutes(quota.limit)
  return left === null || of === null ? '' : `${left} min left of ${of}`
}

/** Used minutes = limit less what remains, so holds and carried debt count as used. */
export function minutesUsed(quota: QuotaFigures): string | null {
  const limit = counter(quota.limit)
  const remaining = counter(quota.remaining)
  if (limit === null || remaining === null) return null
  const used = limit > remaining ? limit - remaining : 0n
  return (used / 60n).toString()
}

/** Notes are counted, not timed: "1 left of 3". */
export function countLeftLine(quota: QuotaFigures): string {
  const left = counter(quota.remaining)
  const of = counter(quota.limit)
  return left === null || of === null ? '' : `${left} left of ${of}`
}

export function countUsed(quota: QuotaFigures): string | null {
  const limit = counter(quota.limit)
  const remaining = counter(quota.remaining)
  if (limit === null || remaining === null) return null
  return (limit > remaining ? limit - remaining : 0n).toString()
}

/** A device's name, or something identifiable when its owner never named it. */
export function deviceLabel(device: { displayName: string; platform: string }): string {
  const name = device.displayName.trim()
  if (name !== '') return name
  const platform = device.platform.trim()
  return platform === '' ? 'Unnamed computer' : `Unnamed computer (${platform})`
}
