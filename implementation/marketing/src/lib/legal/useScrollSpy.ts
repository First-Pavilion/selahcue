import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** What the spy needs from the page: the elements to watch. */
export interface SpyHost {
  querySelectorAll(selector: string): ArrayLike<SpyTarget>
}
export interface SpyTarget {
  readonly dataset: { readonly spy?: string }
}
export interface SpyEntry {
  readonly target: SpyTarget
  readonly isIntersecting: boolean
}
export interface SpyObserver {
  observe(target: SpyTarget): void
  disconnect(): void
}
export type SpyObserverCtor = new (
  callback: (entries: SpyEntry[]) => void,
  options: { rootMargin: string; threshold: number },
) => SpyObserver

/**
 * Which section is the reader in? Reports the first section (in document order) that
 * overlaps a band near the top of the viewport, via ONE IntersectionObserver.
 *
 * Bounded by construction: one observer, one `Set` the size of the section count at most,
 * and `disconnect()` releases the observer and silences any callback still in flight. No
 * scroll listener, so nothing runs per scroll event. Sections are the `[data-spy]` elements
 * inside `host`; the attribute's value is the id.
 *
 * Pure (the observer constructor is passed in) so a test can prove the disconnect.
 */
export function createScrollSpy(
  host: SpyHost,
  onActive: (id: string) => void,
  Observer: SpyObserverCtor,
): { disconnect(): void } {
  const sections = [...Array.from(host.querySelectorAll('[data-spy]'))]
  const order = sections.map((s) => s.dataset.spy ?? '')
  const visible = new Set<string>()
  let live = true
  const observer = new Observer(
    (entries) => {
      if (!live) return
      for (const e of entries) {
        const id = e.target.dataset.spy ?? ''
        if (e.isIntersecting) visible.add(id)
        else visible.delete(id)
      }
      // Keep the last answer when nothing is in the band (above the first section, or
      // below the last) instead of flickering to "none".
      const first = order.find((id) => visible.has(id))
      if (first !== undefined) onActive(first)
    },
    // The band: 96px down (clears the sticky navbar) to 45% of the viewport height.
    { rootMargin: '-96px 0px -55% 0px', threshold: 0 },
  )
  for (const s of sections) observer.observe(s)
  return {
    disconnect(): void {
      live = false
      visible.clear()
      observer.disconnect()
    },
  }
}

export function useScrollSpy(root: Ref<HTMLElement | null>, initial: string | null = null) {
  const active = ref<string | null>(initial)
  let spy: { disconnect(): void } | null = null

  onMounted(() => {
    const host = root.value
    if (!host || typeof IntersectionObserver === 'undefined') return
    spy = createScrollSpy(
      host as unknown as SpyHost,
      (id) => {
        active.value = id
      },
      IntersectionObserver as unknown as SpyObserverCtor,
    )
  })

  onBeforeUnmount(() => {
    spy?.disconnect()
    spy = null
  })

  return { active }
}
