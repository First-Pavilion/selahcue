<script setup lang="ts">
/**
 * The article prose: maps each typed `Block` to a semantic element.
 *
 * - h2/h3 get stable ids (`headingIds`), shared with the table of contents, plus an
 *   optional "link to this section" anchor (docs, handoff §9b).
 * - callouts use the handoff's soft backgrounds (§9b: --sc-info-soft, --sc-warn-soft,
 *   --sc-preview-soft) and a text label, so meaning never rests on colour alone.
 * - code blocks can offer copy-to-clipboard (docs, §9b). The block is a keyboard-focusable
 *   scroll region so a long line can be read without a mouse.
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import InlineText from './InlineText.vue'
import { headingIds } from '@/lib/content/text.ts'
import type { Block } from '@/lib/content/types.ts'

const props = withDefaults(
  defineProps<{
    blocks: readonly Block[]
    anchors?: boolean
    copyableCode?: boolean
  }>(),
  { anchors: false, copyableCode: false },
)

const ids = computed(() => headingIds(props.blocks))
function idOf(block: Block): string {
  return ids.value.get(block) ?? ''
}

/** Index of the code block whose copy status is showing, and what it says. */
const copyStatusIndex = ref(-1)
const copyStatus = ref('')
let resetTimer: ReturnType<typeof setTimeout> | undefined

function say(index: number, message: string): void {
  copyStatusIndex.value = index
  copyStatus.value = message
  clearTimeout(resetTimer)
  resetTimer = setTimeout(() => {
    copyStatusIndex.value = -1
    copyStatus.value = ''
  }, 2500)
}

async function copy(code: string, index: number): Promise<void> {
  try {
    await navigator.clipboard.writeText(code)
    say(index, 'Copied to clipboard')
  } catch {
    say(index, 'Copy is blocked in this browser. Select the text and copy it instead.')
  }
}

onBeforeUnmount(() => clearTimeout(resetTimer))
</script>

<template>
  <div class="ab">
    <template v-for="(block, i) in blocks" :key="i">
      <p v-if="block.type === 'p'" class="ab-p"><InlineText :text="block.text" /></p>

      <h2 v-else-if="block.type === 'h2'" :id="idOf(block)" class="ab-h2">
        <InlineText :text="block.text" />
        <router-link
          v-if="anchors"
          class="ab-anchor"
          :to="{ hash: '#' + idOf(block) }"
          aria-label="Link to this section"
          >#</router-link
        >
      </h2>

      <h3 v-else-if="block.type === 'h3'" :id="idOf(block)" class="ab-h3">
        <InlineText :text="block.text" />
        <router-link
          v-if="anchors"
          class="ab-anchor"
          :to="{ hash: '#' + idOf(block) }"
          aria-label="Link to this section"
          >#</router-link
        >
      </h3>

      <ul v-else-if="block.type === 'ul'" class="ab-list">
        <li v-for="(item, j) in block.items" :key="j"><InlineText :text="item" /></li>
      </ul>

      <ol v-else-if="block.type === 'ol'" class="ab-list ab-steps">
        <li v-for="(item, j) in block.items" :key="j"><InlineText :text="item" /></li>
      </ol>

      <div v-else-if="block.type === 'callout'" :class="['ab-callout', `is-${block.variant}`]" role="note">
        <p class="ab-callout-title">{{ block.title }}</p>
        <p class="ab-callout-text"><InlineText :text="block.text" /></p>
      </div>

      <figure v-else-if="block.type === 'code'" class="ab-code">
        <figcaption class="ab-code-head">
          <span class="ab-code-label">{{ block.label }}</span>
          <button
            v-if="copyableCode"
            type="button"
            class="ab-copy"
            @click="copy(block.code, i)"
          >
            Copy<span class="ab-sr"> {{ block.label }}</span>
          </button>
        </figcaption>
        <pre class="ab-pre" tabindex="0"><code>{{ block.code }}</code></pre>
        <p v-if="copyableCode" class="ab-copy-status" role="status" aria-live="polite">
          {{ copyStatusIndex === i ? copyStatus : '' }}
        </p>
      </figure>
    </template>
  </div>
</template>

<style scoped>
.ab { font-size: 17px; line-height: 1.75; color: var(--sc-text-secondary); overflow-wrap: break-word; }
.ab-p { margin: 0 0 20px; }
.ab-h2 {
  position: relative;
  font-size: 26px;
  line-height: 1.3;
  font-weight: 700;
  color: var(--sc-text);
  margin: 44px 0 16px;
}
.ab-h3 {
  position: relative;
  font-size: 20px;
  line-height: 1.35;
  font-weight: 600;
  color: var(--sc-text);
  margin: 32px 0 12px;
}
.ab-anchor {
  margin-left: 10px;
  font-weight: 500;
  color: var(--sc-text-secondary);
  text-decoration: none;
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.ab-h2:hover .ab-anchor, .ab-h3:hover .ab-anchor, .ab-anchor:focus-visible { opacity: 1; }
.ab-anchor:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; border-radius: 3px; }
/* No hover on touch screens: keep the anchor discoverable there. */
@media (hover: none) { .ab-anchor { opacity: 0.7; } }

.ab-list { margin: 0 0 24px; padding-left: 24px; }
.ab-list li { margin-bottom: 10px; padding-left: 4px; }
ul.ab-list { list-style: disc; }
ol.ab-steps { list-style: decimal; }
.ab-list li::marker { color: var(--sc-text-secondary); }
ol.ab-steps li::marker { color: var(--sc-primary-hover); font-weight: 600; }

.ab-callout {
  margin: 28px 0;
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid var(--sc-border);
  font-size: 15px;
  line-height: 1.65;
  color: var(--sc-text);
}
.ab-callout.is-tip { background: var(--sc-preview-soft); border-color: var(--sc-preview-border); }
.ab-callout.is-warning { background: var(--sc-warn-soft); border-color: var(--sc-warn-border); }
.ab-callout.is-info { background: var(--sc-info-soft); border-color: rgba(56, 189, 248, 0.35); }
.ab-callout-title { margin: 0 0 4px; font-weight: 700; }
.is-tip .ab-callout-title { color: var(--sc-preview); }
.is-warning .ab-callout-title { color: var(--sc-warn); }
.is-info .ab-callout-title { color: var(--sc-info); }
.ab-callout-text { margin: 0; color: var(--sc-text-secondary); }

.ab-code {
  margin: 28px 0;
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  background: var(--sc-inset);
  overflow: hidden;
}
.ab-code-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 8px 8px 16px;
  border-bottom: 1px solid var(--sc-border);
  font-size: 13px;
  color: var(--sc-text-secondary);
}
.ab-copy {
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  background: var(--sc-elevated);
  color: var(--sc-text);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.ab-copy:hover { background: var(--sc-border); }
.ab-copy:focus-visible, .ab-pre:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: -2px; }
.ab-pre {
  margin: 0;
  padding: 16px;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 14px;
  line-height: 1.6;
  color: var(--sc-text);
}
.ab-copy-status { margin: 0; padding: 0 16px 10px; min-height: 28px; font-size: 13px; color: var(--sc-preview); }
.ab-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@media (max-width: 767px) {
  .ab { font-size: 16px; }
  .ab-h2 { font-size: 22px; margin-top: 36px; }
  .ab-h3 { font-size: 18px; }
}
</style>
