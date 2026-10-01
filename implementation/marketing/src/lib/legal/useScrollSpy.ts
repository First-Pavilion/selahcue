import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/**
 * Which section is the reader in? Reports the first section (in document order) that
 * overlaps a band near the top of the viewport, via one IntersectionObserver.
 *
 * Bounded by construction: one observer, one `Set` the size of the section count at most,
 * and `disconnect()` on unmount — nothing accumulates across navigations. No scroll
 * listener, so nothing runs per scroll event.
 *
 * Sections are found by `[data-spy]` inside `root`; the attribute's value is the id.
 */
export function useScrollSpy(root: Ref<HTMLElement | null>, initial: string | null = null) {
  const active = ref<string | null>(initial)
  let observer: IntersectionObserver | null = null

  onMounted(() => {
    const host = root.value
    if (!host || typeof IntersectionObserver === 'undefined') return
    const sections = [...host.querySelectorAll<HTMLElement>('[data-spy]')]
    const order = sections.map((s) => s.dataset.spy ?? '')
    const visible = new Set<string>()
    observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const id = (e.target as HTMLElement).dataset.spy ?? ''
          if (e.isIntersecting) visible.add(id)
          else visible.delete(id)
        }
        // Keep the last answer when nothing is in the band (above the first section, or
        // below the last) instead of flickering to "none".
        const first = order.find((id) => visible.has(id))
        if (first !== undefined) active.value = first
      },
      // The band: 96px down (clears the sticky navbar) to 45% of the viewport height.
      { rootMargin: '-96px 0px -55% 0px', threshold: 0 },
    )
    for (const s of sections) observer.observe(s)
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return { active }
}
