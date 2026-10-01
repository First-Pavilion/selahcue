<script setup lang="ts">
/**
 * A legal document (Privacy Policy, Terms of Service) rendered from typed content that was
 * generated from `docs/legal/*.md` (see `scripts/sync_legal.ts`). Nothing about the
 * document is written in this file.
 *
 * Draft treatment is automatic. While the text still contains a `{{PLACEHOLDER}}` the page
 * shows a prominent draft banner, every placeholder is a highlighted chip, and a robots
 * `noindex` tag is sent. Fill the last placeholder, regenerate, and all three disappear
 * with no code change (`legalPageState` is the single decision point).
 */
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import UiBadge from '@/components/UiBadge.vue'
import { goToAnchor, scrollToElement } from '@/lib/legal/anchors.ts'
import {
  DRAFT_NOTICE,
  legalPageState,
  legalTitle,
  placeholderSummary,
  tableOfContents,
  versionLabel,
} from '@/lib/legal/document.ts'
import type { Block, LegalDocument } from '@/lib/legal/types.ts'
import { useLegalHead } from '@/lib/legal/useLegalHead.ts'
import { useScrollSpy } from '@/lib/legal/useScrollSpy.ts'
import LegalBlocks from './LegalBlocks.vue'
import LegalInline from './LegalInline.vue'

const props = defineProps<{ doc: LegalDocument; badge: string }>()

const route = useRoute()
const router = useRouter()

const state = computed(() => legalPageState(props.doc))
const version = computed(() => versionLabel(props.doc.version))
const toc = computed(() => tableOfContents(props.doc))

useLegalHead(
  () => legalTitle(props.doc),
  () => state.value.noindex,
)

const body = ref<HTMLElement | null>(null)
const { active } = useScrollSpy(body, route.hash ? route.hash.slice(1) : null)

/** Contents is a collapsible block below ~820px; always open above it. */
const tocOpen = ref(false)

async function onTocClick(id: string): Promise<void> {
  active.value = id
  tocOpen.value = false
  await goToAnchor(router, id)
}

/**
 * On a long document (the Terms have 25 sections) Contents scrolls inside its sticky
 * frame, so keep the active entry in view there. Adjusts the frame's own scrollTop rather
 * than the built-in scroll-into-view call, which could also move the page.
 */
const tocFrame = ref<HTMLElement | null>(null)
watch(active, async () => {
  await nextTick()
  const frame = tocFrame.value
  const link = frame?.querySelector<HTMLElement>('.toc-link.is-active')
  if (!frame || !link || frame.scrollHeight <= frame.clientHeight) return
  const top = link.offsetTop // the frame is `position: sticky`, so it is the link's offsetParent
  if (top < frame.scrollTop) frame.scrollTop = Math.max(0, top - 8)
  else if (top + link.offsetHeight > frame.scrollTop + frame.clientHeight) {
    frame.scrollTop = top + link.offsetHeight - frame.clientHeight + 8
  }
})

const textTarget = ref<HTMLElement | null>(null)
async function skipToText(): Promise<void> {
  await nextTick()
  const target = textTarget.value
  if (!target) return
  target.focus({ preventScroll: true })
  scrollToElement(target) // honours #legal-text's own scroll-margin-top, so the first heading clears the navbar
}

const hasClauses = (blocks: readonly Block[]): boolean =>
  blocks.some((b) => b.kind === 'paragraph' && b.clause)

const summaryTitleId = 'summary-title'
/** Built here because a literal double brace cannot be written inside a Vue template. */
const EXAMPLE_TOKEN = '{{' + 'EXAMPLE_DETAIL' + '}}'
</script>

<template>
  <div class="legal-page" data-legal-page>
    <a class="skip-link" href="#legal-text" @click.prevent="skipToText">Skip to the document text</a>

    <div class="legal-shell">
      <header class="legal-header">
        <UiBadge variant="preview">{{ badge }}</UiBadge>
        <h1 class="legal-title">{{ doc.title }}</h1>
        <p v-if="version" class="legal-version">
          <time :datetime="version.iso">{{ version.text }}</time>
        </p>
      </header>

      <section v-if="state.draft" class="draft-banner" aria-labelledby="draft-banner-title" data-draft-banner>
        <p id="draft-banner-title" class="draft-title">{{ DRAFT_NOTICE }}</p>
        <p v-if="state.bannerHeadline" class="draft-headline">{{ state.bannerHeadline }}</p>
        <!-- The document's own banner text, in full: status, launch caveats, the pointer to the
             separate Controller app policy. A visitor is entitled to all of it. -->
        <template v-if="doc.banner">
          <template v-for="(note, ni) in doc.banner.notes" :key="ni">
            <p v-if="note.kind === 'paragraph'" class="draft-note"><LegalInline :nodes="note.inline" mention /></p>
          </template>
        </template>
        <p v-if="state.placeholderCount > 0" class="draft-detail">
          {{ placeholderSummary(state) }}
          Each one is highlighted in the text, like
          <mark class="draft-example"
            ><span class="draft-sr">Example placeholder: </span>{{ EXAMPLE_TOKEN }}</mark
          >.
        </p>
      </section>

      <ul v-if="doc.facts.length > 0" class="legal-facts" aria-label="Key details">
        <li v-for="(f, i) in doc.facts" :key="i" class="legal-fact"><LegalInline :nodes="f.inline" /></li>
      </ul>

      <div ref="body" class="legal-layout">
        <aside class="toc-col">
          <nav ref="tocFrame" class="toc" aria-label="Contents" :class="{ 'is-open': tocOpen }">
            <p class="toc-label">Contents</p>
            <button
              type="button"
              class="toc-toggle"
              :aria-expanded="tocOpen"
              aria-controls="toc-list"
              @click="tocOpen = !tocOpen"
            >
              <span>Contents</span>
              <span class="toc-caret" aria-hidden="true"></span>
            </button>
            <div id="toc-list" class="toc-list">
              <template v-for="(g, gi) in toc" :key="gi">
                <p v-if="g.heading" class="toc-group">{{ g.heading }}</p>
                <ul class="toc-items">
                  <li v-for="e in g.entries" :key="e.id">
                    <a
                      class="toc-link"
                      :class="{ 'is-active': active === e.id }"
                      :href="`#${e.id}`"
                      :aria-current="active === e.id ? 'location' : undefined"
                      @click.prevent="onTocClick(e.id)"
                      >{{ e.label }}</a
                    >
                  </li>
                </ul>
              </template>
            </div>
          </nav>
        </aside>

        <div id="legal-text" ref="textTarget" class="legal-text" tabindex="-1">
          <section
            v-if="doc.summary"
            class="summary-box"
            :data-spy="doc.summary.id"
            :aria-labelledby="summaryTitleId"
          >
            <span :id="doc.summary.id" class="legal-anchor" aria-hidden="true"></span>
            <h2 :id="summaryTitleId" class="summary-title">{{ doc.summary.title }}</h2>
            <LegalBlocks :blocks="doc.summary.blocks" :table-label="doc.summary.title" />
          </section>

          <template v-for="(part, pi) in doc.parts" :key="pi">
            <h2 v-if="part.label && part.title" class="part-title">
              <span class="part-label">{{ part.label }}</span> — {{ part.title }}
            </h2>
            <section
              v-for="s in part.sections"
              :key="s.id"
              :class="['legal-section', { 'has-clauses': hasClauses(s.blocks) }]"
              :data-spy="s.id"
              :aria-labelledby="`${s.id}-title`"
            >
              <span :id="s.id" class="legal-anchor" aria-hidden="true"></span>
              <component :is="`h${s.level}`" :id="`${s.id}-title`" :class="['sec-title', `sec-h${s.level}`]">
                <span v-if="s.number" class="sec-num">{{ s.number }}.</span> {{ s.title }}
              </component>
              <LegalBlocks :blocks="s.blocks" :table-label="s.title" />
              <template v-for="c in s.children" :key="c.id">
                <span :id="c.id" class="legal-anchor" aria-hidden="true"></span>
                <h3 :id="`${c.id}-title`" class="sec-title sec-h3">
                  <span v-if="c.number" class="sec-num">{{ c.number }}</span> {{ c.title }}
                </h3>
                <LegalBlocks :blocks="c.blocks" :table-label="c.title" />
              </template>
            </section>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/*
 * Deliberately NOT scoped: shared by LegalBlocks (clause anchors) and the one `html` rule.
 *
 * The anchor is a zero-height block lifted by the sticky navbar's height plus a little air
 * (`--legal-anchor-offset`, defined on .legal-page), so whatever scrolls to it leaves the
 * heading below the bar. See lib/legal/anchors.ts for why this, and only this, carries the
 * offset.
 */
.legal-anchor {
  display: block;
  position: relative;
  top: calc(-1 * var(--legal-anchor-offset, 88px));
  height: 0;
  visibility: hidden;
}

/*
 * While a legal page is mounted the page-wide `scroll-padding-top` (PR #135 sets one on
 * `html` for the article pages) is zeroed: the anchors already carry the offset, and the
 * browser would otherwise add the padding on top of it for native fragment navigation.
 * Focus-visibility under the navbar is kept by the per-element rule in the scoped block.
 *
 * WHEN #135 LANDS: this rule and `--legal-anchor-offset` are the legal pages' only offset
 * mechanism and are self-contained, so nothing needs deleting for correctness. To fold the
 * legal pages into #135's single mechanism instead: add 'privacy' and 'terms' to
 * ANCHORED_ROUTES in router/scroll.ts, then delete this rule, the lift in `.legal-anchor`
 * and `--legal-anchor-offset`.
 */
html:has(.legal-page) {
  scroll-padding-top: 0;
}
</style>

<style scoped>
.legal-page {
  background: var(--sc-base);
  padding: 60px 0 80px;
  --clause-indent: 3em;
  --clause-gap: 10px;
  /* Navbar height (the shared --nav-height token when a stylesheet defines it; 68px is the
     navbar's real height today) plus a little air. The single offset for every anchor. */
  --legal-anchor-offset: calc(var(--nav-height, 68px) + 20px);
}

/* Keyboard focus must not end up under the sticky navbar (WCAG 2.2 SC 2.4.11). */
.legal-page :deep(:is(a[href], button, [tabindex])) {
  scroll-margin-top: calc(var(--nav-height, 68px) + 16px);
}
/* The skip-link target: its first heading must clear the navbar, not sit behind it. */
#legal-text {
  scroll-margin-top: var(--legal-anchor-offset);
}
.legal-shell {
  max-width: 1120px;
  margin: 0 auto;
  padding-inline: clamp(20px, 5vw, 24px);
}

/*
 * Visually hidden until focused, with the clip pattern rather than parking the link far
 * off-screen with a huge negative offset. An off-screen link is a layout oddity every
 * responsive audit has to special-case (PR #140's sweep fails on it), and the clip keeps
 * the element's box inside the viewport. On focus it is a high-contrast chip (near-black on near-white, about 17:1;
 * white on the brand colour was 4.36:1).
 */
.skip-link {
  position: absolute;
  top: 8px;
  left: 16px;
  z-index: 200;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  border: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  background: var(--sc-text);
  color: var(--sc-base);
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
}
.skip-link:focus,
.skip-link:focus-visible {
  width: auto;
  height: auto;
  margin: 0;
  padding: 10px 16px;
  overflow: visible;
  clip-path: none;
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

.legal-header {
  text-align: center;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--sc-border);
  padding-bottom: 32px;
}
.legal-title {
  font-size: 36px;
  font-weight: 800;
  line-height: 1.15;
  color: var(--sc-text);
  margin: 16px 0 8px;
  overflow-wrap: anywhere;
}
.legal-version { font-size: 14px; color: var(--sc-text-secondary); }

/* Draft banner: the page must never be mistaken for a final policy. */
.draft-banner {
  background: var(--sc-warn-soft);
  border: 1px solid var(--sc-warn-border);
  border-left: 4px solid var(--sc-warn);
  border-radius: 12px;
  padding: 18px 22px;
  margin: 0 0 32px;
}
.draft-title { font-size: 18px; font-weight: 700; color: var(--sc-warn); margin: 0 0 6px; }
.draft-headline {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--sc-text);
  margin: 0 0 8px;
}
.draft-note { font-size: 13px; line-height: 1.6; color: var(--sc-text-secondary); margin: 0 0 8px; }
.draft-detail { font-size: 14px; line-height: 1.6; color: var(--sc-text-secondary); margin: 0; }
.draft-example {
  background: var(--sc-warn-soft);
  color: var(--sc-warn);
  border: 1px dashed var(--sc-warn);
  border-radius: 4px;
  padding: 0 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.88em;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.draft-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.legal-facts {
  margin: 0 0 40px;
  padding: 16px 22px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
}
.legal-fact {
  font-size: 15px;
  line-height: 1.7;
  color: var(--sc-text-secondary);
  padding: 3px 0;
  overflow-wrap: anywhere;
}

/* Layout: Contents | text. Stacks below ~820px (handoff section 8). */
.legal-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 48px;
}
.toc-col { min-width: 0; }
.toc {
  position: sticky;
  top: 88px;
  max-height: calc(100vh - 112px);
  overflow-y: auto;
  padding-right: 4px;
}
.toc-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--sc-text-secondary);
  margin: 0 0 12px;
}
.toc-toggle { display: none; }
.toc-group {
  font-size: 12px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 16px 0 6px;
}
.toc-group:first-child { margin-top: 0; }
.toc-items { margin: 0; }
.toc-link {
  display: block;
  padding: 6px 10px;
  border-left: 2px solid var(--sc-border);
  font-size: 14px;
  line-height: 1.4;
  color: var(--sc-text-secondary);
}
.toc-link:hover { color: var(--sc-text); border-left-color: var(--sc-border-strong); }
.toc-link.is-active {
  color: var(--sc-text);
  font-weight: 600;
  border-left-color: var(--sc-primary);
  background: var(--sc-accent-soft);
}
.toc-link:focus-visible,
.toc-toggle:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

.legal-text { min-width: 0; max-width: 760px; outline: none; overflow-wrap: break-word; }

.summary-box {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-left: 4px solid var(--sc-primary);
  border-radius: 12px;
  padding: 24px 24px 8px;
  margin-bottom: 40px;
}
.summary-title { font-size: 22px; font-weight: 700; color: var(--sc-text); margin: 0 0 12px; }

.part-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--sc-text-secondary);
  border-top: 1px solid var(--sc-border);
  padding-top: 24px;
  margin: 48px 0 0;
}
.part-title:first-child { margin-top: 0; }
.part-label { color: var(--sc-primary-hover); }

.legal-section { margin-bottom: 8px; }
.sec-title { color: var(--sc-text); }
.sec-h2 { font-size: 22px; font-weight: 700; line-height: 1.3; margin: 36px 0 12px; }
.sec-h3 { font-size: 17px; font-weight: 600; line-height: 1.4; margin: 22px 0 8px; }
.legal-section:first-of-type .sec-h2,
.legal-section:first-of-type .sec-h3 { margin-top: 24px; }
.sec-num { color: var(--sc-text-secondary); font-variant-numeric: tabular-nums; margin-right: 2px; }
.sec-title:focus { outline: none; }

/* Lists under a numbered clause align with the clause text, not the number. */
.has-clauses > :deep(.ll) { margin-left: var(--clause-indent); }

@media (max-width: 819px) {
  .legal-page { padding: 40px 0 64px; }
  .legal-layout { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .toc { position: static; max-height: none; overflow: visible; padding-right: 0; }
  .toc-label { display: none; }
  .toc-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 44px;
    padding: 10px 14px;
    background: var(--sc-surface);
    border: 1px solid var(--sc-border);
    border-radius: 10px;
    color: var(--sc-text);
    font: inherit;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
  }
  .toc-caret {
    width: 8px;
    height: 8px;
    border-right: 2px solid var(--sc-text-secondary);
    border-bottom: 2px solid var(--sc-text-secondary);
    transform: rotate(45deg);
    transition: transform 0.15s ease;
  }
  .toc.is-open .toc-caret { transform: rotate(-135deg); }
  .toc-list {
    display: none;
    margin-top: 8px;
    padding: 12px;
    border: 1px solid var(--sc-border);
    border-radius: 10px;
    background: var(--sc-surface);
    max-height: 60vh;
    overflow-y: auto;
  }
  .toc.is-open .toc-list { display: block; }
  .toc-link { padding: 10px 10px; }
}

@media (max-width: 767px) {
  .legal-title { font-size: 30px; }
  .summary-box { padding: 20px 18px 4px; }
  .legal-facts { padding: 12px 16px; }
  .draft-banner { padding: 16px; }
}

@media (max-width: 519px) {
  /* No room for a hanging number on a phone: it sits inline before the text. */
  .legal-page { --clause-indent: 0px; --clause-gap: 8px; }
}

@media (prefers-reduced-motion: reduce) {
  .toc-caret { transition: none; }
}
</style>
