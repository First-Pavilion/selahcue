/**
 * `document.title` and the robots `noindex` tag for a legal page.
 *
 * WHY CLAIMS INSTEAD OF "SET ON ENTER, UNDO ON LEAVE". App.vue wraps the router view in
 * <Suspense>, which sets up the NEW page before it unmounts the OLD one. Going from
 * /privacy to /terms therefore runs Terms' setup first and Privacy's teardown second, and
 * a plain "remove the tag on unmount" would delete the tag Terms had just added: the
 * second page would be a draft served WITHOUT `noindex`. So each mounted page holds a
 * claim, the tag exists while at least one claim wants it, and the title and tag are given
 * back only when the LAST claim is released.
 *
 * Only a tag this module created is ever touched (it carries `data-legal-noindex`); a
 * robots tag the site ships itself is left alone.
 */

/** The slice of `Document` this needs, so a test can pass a tiny fake. */
export interface HeadHost {
  title: string
  head: { appendChild(node: HTMLMetaElement): unknown }
  createElement(tag: 'meta'): HTMLMetaElement
  querySelector(selector: string): Element | null
}

export interface HeadClaim {
  update(next: { title: string; noindex: boolean }): void
  release(): void
}

export const NOINDEX_SELECTOR = 'meta[name="robots"][data-legal-noindex]'

export class LegalHead {
  private readonly host: HeadHost
  /** Newest last. Bounded by the number of mounted legal pages (two, mid-transition). */
  private readonly claims: { title: string; noindex: boolean }[] = []
  private baseTitle: string | null = null
  private lastWrittenTitle: string | null = null

  constructor(host: HeadHost) {
    this.host = host
  }

  claim(initial: { title: string; noindex: boolean }): HeadClaim {
    const mine = { ...initial }
    if (this.claims.length === 0) this.baseTitle = this.host.title
    this.claims.push(mine)
    this.sync()
    let released = false
    return {
      update: (next) => {
        if (released) return
        mine.title = next.title
        mine.noindex = next.noindex
        this.sync()
      },
      release: () => {
        if (released) return
        released = true
        const at = this.claims.indexOf(mine)
        if (at !== -1) this.claims.splice(at, 1)
        this.sync()
      },
    }
  }

  /** Number of live claims; exposed so tests can prove nothing leaks. */
  get activeClaims(): number {
    return this.claims.length
  }

  private sync(): void {
    const newest = this.claims[this.claims.length - 1]
    const existing = this.host.querySelector(NOINDEX_SELECTOR)
    const wantNoindex = this.claims.some((c) => c.noindex)

    if (wantNoindex && !existing) {
      const tag = this.host.createElement('meta')
      tag.setAttribute('name', 'robots')
      tag.setAttribute('content', 'noindex')
      tag.setAttribute('data-legal-noindex', '')
      this.host.head.appendChild(tag)
    } else if (!wantNoindex && existing) {
      existing.remove()
    }

    if (newest) {
      this.host.title = newest.title
      this.lastWrittenTitle = newest.title
    } else if (this.baseTitle !== null) {
      // Give the title back only if nobody else has written one since.
      if (this.host.title === this.lastWrittenTitle) this.host.title = this.baseTitle
      this.baseTitle = null
      this.lastWrittenTitle = null
    }
  }
}
