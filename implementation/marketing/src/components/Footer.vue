<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { MOBILE_QUERY } from '@/lib/ui/breakpoints.ts'

/**
 * Footer link columns.
 *
 * Desktop (>= 1200) shows the three columns hugging their content on the right of the brand,
 * tablet (768-1199) a two-up grid, and mobile (< 768) stacks them as collapsible sections -- tap a
 * heading to expand (design 8c).
 *
 * The collapse is a MOBILE-ONLY behaviour, so it is driven by `isMobile` (matchMedia)
 * rather than by CSS alone: above the breakpoint every column is always shown and the
 * heading is plain text, not a control that does nothing. The visibility uses `v-show`
 * (an inline `display: none`) rather than the `hidden` attribute, because a class-level
 * `display` rule would defeat `hidden` -- the same WebKit-visible trap the operator
 * webview has already hit.
 *
 * THE LINKS ARE FIGMA'S (frame 479:133, identical on all 14 pages): Product, Resources and Company,
 * with Privacy and Terms in the bottom bar instead of a fourth Legal column. "Setup guides" and "NDI &
 * streaming" are the design's entries for the docs and the features page (handoff section 1), so two
 * links share a target on purpose. Every target is a real route: `tests/chrome.test.ts` walks this
 * list against the router table, so a link to a page that does not exist (the old `/how-it-works`,
 * which rendered the 404 page) fails the build.
 */
const columns = [
  {
    title: 'Product',
    links: [
      { to: '/features', label: 'Features' },
      { to: '/pricing', label: 'Pricing' },
      { to: '/download', label: 'Download' },
      { to: '/changelog', label: 'Changelog' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { to: '/docs', label: 'Documentation' },
      { to: '/docs', label: 'Setup guides' },
      { to: '/features', label: 'NDI & streaming' },
      { to: '/support', label: 'Support' },
    ],
  },
  {
    title: 'Company',
    links: [
      { to: '/about', label: 'About' },
      { to: '/blog', label: 'Blog' },
      { to: '/contact', label: 'Contact' },
      { to: '/careers', label: 'Careers' },
      { to: '/affiliates', label: 'Affiliates' },
    ],
  },
]

/** The bottom bar's own links (Figma 479:162), beside the platforms line. */
const legalLinks = [
  { to: '/privacy', label: 'Privacy' },
  { to: '/terms', label: 'Terms' },
]

const isMobile = ref(false)
/** Titles of the sections the visitor has opened. Bounded: at most `columns.length`. */
const open = ref<string[]>([])

const isOpen = (title: string) => !isMobile.value || open.value.includes(title)

const toggle = (title: string) => {
  open.value = open.value.includes(title)
    ? open.value.filter((t) => t !== title)
    : [...open.value, title]
}

let query: MediaQueryList | null = null
const sync = () => {
  isMobile.value = query?.matches ?? false
}

// Read the query during setup so the first paint is already correct (no flash of expanded
// columns on a phone). It is a client-only SPA, so `window` exists here.
if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  query = window.matchMedia(MOBILE_QUERY)
  isMobile.value = query.matches
}

onMounted(() => {
  query?.addEventListener('change', sync)
})

onBeforeUnmount(() => {
  query?.removeEventListener('change', sync)
  query = null
})
</script>

<template>
  <footer :class="['footer', { 'is-mobile': isMobile }]">
    <div class="container footer-content">
      <div class="footer-top">
        <div class="brand-column">
          <router-link to="/" class="brand">
            <!-- The wordmark names the link; the mark is decoration (see Navbar.vue). -->
            <span class="brand-mark brand-mark-footer"><img src="/selahcue-logo.png" alt="" aria-hidden="true" /></span>
            <span class="wordmark">SelahCue</span>
          </router-link>
          <p class="tagline">Church presentation, reengineered</p>
        </div>

        <nav class="links-grid" aria-label="Footer">
          <div v-for="(column, index) in columns" :key="column.title" class="link-column">
            <h3 class="column-title">
              <button
                v-if="isMobile"
                type="button"
                class="column-toggle"
                :aria-expanded="isOpen(column.title)"
                :aria-controls="`footer-col-${index}`"
                @click="toggle(column.title)"
              >
                <span>{{ column.title }}</span>
                <svg class="chevron" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M5 8l5 5 5-5" />
                </svg>
              </button>
              <template v-else>{{ column.title }}</template>
            </h3>
            <div v-show="isOpen(column.title)" :id="`footer-col-${index}`" class="column-links">
              <router-link v-for="link in column.links" :key="link.label" :to="link.to" class="footer-link">
                {{ link.label }}
              </router-link>
            </div>
          </div>
        </nav>
      </div>

      <div class="footer-bottom">
        <p class="copyright">© 2026 SelahCue. All rights reserved.</p>
        <div class="legal-links">
          <router-link v-for="link in legalLinks" :key="link.to" :to="link.to" class="legal-link">{{ link.label }}</router-link>
          <span class="platforms">Windows · macOS</span>
        </div>
      </div>
    </div>
  </footer>
</template>

<style scoped>
/* Figma 479:133: the page colour (the 1px top stroke is what separates it), padding 56 / 96 / 40 / 96,
   the 96px sides coming from the shared `.container`. */
.footer {
  background: var(--sc-base);
  border-top: 1px solid var(--sc-border);
  /* 55 + the 1px top border = Figma's 56px: its 1px stroke is drawn INSIDE the frame's 56px padding, so
     the first heading sits 56px from the top and the whole footer is 358px, not 359. */
  padding-top: 55px;
  padding-bottom: 40px;
}

.footer-content {
  display: flex;
  flex-direction: column;
}

.footer-top {
  display: flex;
  flex-direction: column;
  gap: 48px;
  margin-bottom: 40px;
}

.brand-column {
  max-width: 300px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  text-decoration: none;
}

/* 28px in the footer, 32px in the navbar (the shared `.brand-mark` takes its size from this). */
.brand-mark-footer {
  --mark-size: 28px;
}

.wordmark {
  font-family: var(--font-family);
  font-weight: 700;
  font-size: 18px;
  color: var(--sc-text);
  letter-spacing: 0;
}

.tagline {
  color: var(--sc-text-secondary);
  font-size: 14px;
  line-height: 21px;
}

/* Tablet default: two-up. `minmax(0, 1fr)` so a long link can never widen a track. */
.links-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px 24px;
}

/* heading line 15px, 13px to the first link (28 in all), links on a 17px line and 13px apart (30 pitch). */
.link-column {
  display: flex;
  flex-direction: column;
  gap: 13px;
  min-width: 0;
}

.column-links {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

/* Muted capitals over bright links (Figma): 12/Bold, +0.1px, text/muted which the token layer maps to
   --sc-text-secondary (8.7:1 on the page colour). */
.column-title {
  color: var(--sc-text-secondary);
  font-size: 12px;
  font-weight: 700;
  line-height: 15px;
  letter-spacing: 0.1px;
  text-transform: uppercase;
  margin: 0;
}

.column-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 48px;
  padding: 0;
  background: none;
  border: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.column-toggle:focus-visible,
.footer-link:focus-visible,
.legal-link:focus-visible,
.brand:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
  border-radius: 4px;
}

.chevron {
  flex-shrink: 0;
  color: var(--sc-text-secondary);
  transition: transform var(--transition-fast);
}

.column-toggle[aria-expanded='true'] .chevron {
  transform: rotate(180deg);
}

.footer-link {
  color: var(--sc-text);
  font-size: 14px;
  line-height: 17px;
  text-decoration: none;
}

/* The link ink is already the brightest, so the hover cue cannot be a colour change. */
.footer-link:hover,
.legal-link:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* 40px under the columns, a 1px divider, 40px under it, the 16px bottom row (Figma 479:159, 479:160). */
.footer-bottom {
  padding-top: 40px;
  border-top: 1px solid var(--sc-border);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 24px;
}

.copyright,
.legal-link,
.platforms {
  color: var(--sc-text-secondary);
  font-size: 13px;
  line-height: 16px;
  margin: 0;
}

.legal-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: 22px;
  row-gap: 4px;
}

/* Desktop (>= 1200): the brand column sits beside the links, which hug their content on the right at
   64px gaps (PRODUCT x=973, RESOURCES x=1109, COMPANY x=1280 in Figma). Tablet (768-1199) keeps the brand
   above a two-up grid (the base styles); mobile is the `.is-mobile` block below. */
@media (min-width: 1200px) {
  .links-grid {
    display: flex;
    justify-content: flex-end;
    gap: 64px;
  }

  .link-column {
    flex: 0 0 auto;
  }

  .footer-top {
    flex-direction: row;
    justify-content: space-between;
  }
}

/* 44px lockup target on phones and coarse pointers only: at desktop it would push the
   tagline down 12px and change the designed footer. */
.footer.is-mobile .brand {
  min-height: 44px;
}

@media (pointer: coarse) {
  .brand {
    min-height: 44px;
  }
}

/* Mobile: one stacked column of collapsible sections.
   Driven by `.is-mobile` (set from MOBILE_QUERY in the script), NOT by a CSS media query:
   the collapse behaviour in JS and the stacked layout in CSS must flip at the same width,
   and a second hand-typed breakpoint here is exactly how they would drift apart.
   The mobile sections keep their own heading and link treatment (design 8c): 15px sentence-case
   headings that are controls, dim links. Only the desktop footer follows the Figma frame. */
.footer.is-mobile {
  padding-top: var(--section-pad);
  padding-bottom: 0;
}

.footer.is-mobile .footer-top {
  gap: 32px;
  margin-bottom: 32px;
}

.footer.is-mobile .links-grid {
  grid-template-columns: minmax(0, 1fr);
  gap: 0;
  border-top: 1px solid var(--sc-border);
}

.footer.is-mobile .link-column {
  gap: 0;
  border-bottom: 1px solid var(--sc-border);
}

.footer.is-mobile .column-title {
  margin: 0;
  color: var(--sc-text);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 0;
  text-transform: none;
}

.footer.is-mobile .column-links {
  gap: 0;
  padding-bottom: 8px;
}

/* 44px+ rows. Flex + min-height on the <a> so the whole row taps. */
.footer.is-mobile .footer-link {
  display: flex;
  align-items: center;
  min-height: 44px;
  color: var(--sc-text-secondary);
  font-size: 15px;
}

.footer.is-mobile .footer-bottom {
  padding-block: 24px;
  flex-direction: column;
  align-items: flex-start;
}

/* 44px both ways: "Terms" is only 37px wide as text, and a touch target is judged on its smaller side. */
.footer.is-mobile .legal-link {
  display: flex;
  align-items: center;
  min-height: 44px;
  min-width: 44px;
}

@media (prefers-reduced-motion: reduce) {
  .chevron {
    transition: none;
  }
}
</style>
