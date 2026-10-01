<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { MOBILE_QUERY } from '@/lib/ui/breakpoints.ts'

/**
 * Footer link columns.
 *
 * Desktop (>= 1200) shows four columns in a row, tablet (768-1199) a 2x2 grid, and mobile
 * (< 768) stacks them as collapsible sections -- tap a heading to expand (design 8c).
 *
 * The collapse is a MOBILE-ONLY behaviour, so it is driven by `isMobile` (matchMedia)
 * rather than by CSS alone: above the breakpoint every column is always shown and the
 * heading is plain text, not a control that does nothing. The visibility uses `v-show`
 * (an inline `display: none`) rather than the `hidden` attribute, because a class-level
 * `display` rule would defeat `hidden` -- the same WebKit-visible trap the operator
 * webview has already hit.
 */
const columns = [
  {
    title: 'Product',
    links: [
      { to: '/features', label: 'Features' },
      { to: '/pricing', label: 'Pricing' },
      { to: '/download', label: 'Download' },
      { to: '/how-it-works', label: 'How it works' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { to: '/docs', label: 'Documentation' },
      { to: '/support', label: 'Support' },
      { to: '/blog', label: 'Blog' },
      { to: '/changelog', label: 'Changelog' },
    ],
  },
  {
    title: 'Company',
    links: [
      { to: '/about', label: 'About' },
      { to: '/careers', label: 'Careers' },
      { to: '/contact', label: 'Contact' },
      { to: '/affiliates', label: 'Affiliates' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { to: '/privacy', label: 'Privacy Policy' },
      { to: '/terms', label: 'Terms of Service' },
    ],
  },
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
  <footer class="footer">
    <div class="container footer-content">
      <div class="footer-top">
        <div class="brand-column">
          <router-link to="/" class="brand">
            <img src="/selahcue-logo.png" alt="SelahCue Logo" class="logo" />
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
              <router-link v-for="link in column.links" :key="link.to" :to="link.to" class="footer-link">
                {{ link.label }}
              </router-link>
            </div>
          </div>
        </nav>
      </div>

      <div class="footer-bottom">
        <p class="copyright">© 2026 SelahCue. All rights reserved.</p>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  background: var(--sc-surface);
  border-top: 1px solid var(--sc-border);
  padding-top: 80px;
}

.footer-content {
  display: flex;
  flex-direction: column;
}

.footer-top {
  display: flex;
  flex-direction: column;
  gap: 48px;
  margin-bottom: 64px;
}

.brand-column {
  max-width: 300px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  min-height: 44px;
  text-decoration: none;
}

.logo {
  height: 32px;
  width: auto;
}

.wordmark {
  font-family: var(--font-family);
  font-weight: 700;
  font-size: 20px;
  color: var(--sc-text);
  letter-spacing: -0.02em;
}

.tagline {
  color: var(--sc-text-secondary);
  font-size: 15px;
  line-height: 1.5;
}

/* Tablet default: 2x2. `minmax(0, 1fr)` so a long link can never widen a track. */
.links-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px 24px;
}

.link-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.column-links {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.column-title {
  color: var(--sc-text);
  font-weight: 600;
  font-size: 15px;
  margin: 0 0 4px 0;
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
  color: var(--sc-text-secondary);
  font-size: 14px;
  transition: color var(--transition-fast);
  text-decoration: none;
}

.footer-link:hover {
  color: var(--sc-text);
}

.footer-bottom {
  padding-block: 32px;
  border-top: 1px solid var(--sc-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.copyright {
  color: var(--sc-text-muted);
  font-size: 14px;
  margin: 0;
}

/* Tablet and up: brand column beside the grid. Desktop (>= 1200) is four across. */
@media (min-width: 1200px) {
  .links-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .footer-top {
    flex-direction: row;
    justify-content: space-between;
  }
}

/* Mobile: one stacked column of collapsible sections. */
@media (max-width: 767px) {
  .footer {
    padding-top: var(--section-pad);
  }

  .footer-top {
    gap: 32px;
    margin-bottom: 32px;
  }

  .links-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
    border-top: 1px solid var(--sc-border);
  }

  .link-column {
    gap: 0;
    border-bottom: 1px solid var(--sc-border);
  }

  .column-title {
    margin: 0;
  }

  .column-links {
    gap: 0;
    padding-bottom: 8px;
  }

  /* 44px+ rows. Padding rather than min-height on the <a> alone so the whole row taps. */
  .footer-link {
    display: flex;
    align-items: center;
    min-height: 44px;
    font-size: 15px;
  }

  .footer-bottom {
    padding-block: 24px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chevron {
    transition: none;
  }
}
</style>
