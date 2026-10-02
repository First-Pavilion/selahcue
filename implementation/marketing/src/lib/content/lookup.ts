/**
 * Lookups shared by the three article collections. Pure, no Vue.
 *
 * Every public function takes `unknown` for the slug/category because they arrive from
 * `route.params`, which vue-router types as `string | string[]`. A value that is not a
 * plain string is "not found", never an exception.
 */
import type { Neighbour } from './types.ts'

export function asParam(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/** Previous / next entries around `index`, or null at either end. */
export function neighbours<T>(
  list: readonly T[],
  index: number,
  toNeighbour: (item: T) => Neighbour,
): { prev: Neighbour | null; next: Neighbour | null } {
  const prev = index > 0 ? list[index - 1] : undefined
  const next = index >= 0 && index < list.length - 1 ? list[index + 1] : undefined
  return {
    prev: prev === undefined ? null : toNeighbour(prev),
    next: next === undefined ? null : toNeighbour(next),
  }
}
