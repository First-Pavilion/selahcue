<script setup lang="ts">
const props = defineProps({
  /**
   * `featured`  the pill above a page headline (Figma: 12px/700, 0.1em, 6px 12px, elevated fill)
   * `eyebrow`   the plain label above a section headline: no pill, 13px/700
   * `accent`    a brand chip (MOST POPULAR, a change type); `warn` an amber chip
   * `live`, `preview`, `ready`, `ndi`, `new`  status tones
   *
   * Every variant has a rule below; `tests/sharedComponents.test.ts` fails when a view passes
   * a variant that is not listed here, or when one is listed without a rule.
   */
  variant: {
    type: String,
    default: 'preview',
    validator: (val: string) =>
      ['live', 'preview', 'ready', 'ndi', 'featured', 'new', 'accent', 'warn', 'eyebrow'].includes(val)
  },
  size: {
    type: String,
    default: 'sm',
    validator: (val: string) => ['sm', 'md'].includes(val)
  },
  dot: {
    type: Boolean,
    default: false
  },
  /**
   * NOT RENDERED. The slot is the only way to give a badge text.
   *
   * `PricingView` passes `text="Save 20%"`. That never rendered, and it must not start to: the
   * repo has no annual plan, so the words are an unbacked claim (audit finding pricing-18,
   * class C; the owner decision is that honest content wins). Declaring the prop is what lets
   * development say so out loud instead of leaving the attribute to fall through unread.
   */
  text: {
    type: String,
    default: undefined
  }
})

if (import.meta.env.DEV && props.text !== undefined) {
  console.warn(
    '[UiBadge] the `text` prop is not rendered; put the words in the default slot. ' +
      'It has never rendered, and showing it now would publish copy nobody has checked (audit pricing-18).'
  )
}
</script>

<template>
  <span :class="['ui-badge', `variant-${variant}`, `size-${size}`]">
    <span v-if="dot" class="dot"></span>
    <slot></slot>
  </span>
</template>

<style scoped>
/*
 * One badge scale, taken from the Figma pills (every one is bold, uppercase, on an elevated
 * fill): sm = 10.5px/0.6px, 21px tall (PAID, change types); md = 11px/0.7px, 23px tall
 * (ACTIVE, PRO PLAN). A fixed line-height makes the height the design's, whatever line-height
 * the page inherits. The 1px border is transparent and only there so the status tones that
 * keep a border (live, ready) do not change the size.
 */
.ui-badge {
  display: inline-flex;
  align-items: center;
  border-radius: var(--pill-radius);
  font-weight: 700;
  text-transform: uppercase;
  line-height: 13px;
  border: 1px solid transparent;
}

/* A badge with nothing in its slot draws nothing. `PricingView` gives its "Annual" badge only a
   `text` attribute, which is not rendered (see the prop); without this it would now be an
   empty dark pill beside the word, because the pill has a fill. */
.ui-badge:empty {
  display: none;
}

.size-sm {
  padding: 3px 9px;
  font-size: 10.5px;
  letter-spacing: 0.6px;
}
.size-md {
  padding: 4px 9px;
  font-size: 11px;
  letter-spacing: 0.7px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 6px;
  background-color: currentColor;
}

.variant-live .dot {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 77, 77, 0.7); }
  70% { box-shadow: 0 0 0 6px rgba(255, 77, 77, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 77, 77, 0); }
}

.variant-live {
  background: var(--sc-live-soft);
  color: var(--sc-live);
  border-color: var(--sc-live-border);
}

.variant-preview {
  background: var(--sc-elevated);
  color: var(--sc-preview);
}

.variant-ready {
  background: var(--sc-warn-soft);
  color: var(--sc-warn);
  border-color: var(--sc-warn-border);
}

.variant-ndi {
  background: var(--sc-info-soft);
  color: var(--sc-info);
}

.variant-new {
  background: var(--sc-primary);
  color: white;
}

.variant-warn {
  background: var(--sc-elevated);
  color: var(--sc-warn);
}

/*
 * THE BRAND INK, in one place.
 *
 * Figma draws these three in brand blue (#5b6bd6), which is 3.4:1 on the elevated fill and
 * fails WCAG AA for small text; the code's own --sc-primary is 3.5:1. Which accessible tint
 * replaces it is Uma's decision (audit class D: account-25, home-44, pricing-21), so none is
 * chosen here. Each variant reads `--ui-badge-ink` and falls back to the ink it renders
 * today: `featured` keeps --sc-primary, `accent` and `eyebrow` keep the readable
 * --sc-text they have always rendered (the missing variant made them white). When Uma
 * decides, one line, `--ui-badge-ink: <tint>;`, in tokens.css (or any ancestor) changes
 * all three. The property is deliberately NOT declared in this file: a declaration here
 * would beat the one outside it.
 *
 * Declared after the sizes on purpose: `featured` and `eyebrow` are size-independent looks
 * and win over `.size-sm` / `.size-md` by order.
 */
.variant-featured {
  background: var(--sc-elevated);
  color: var(--ui-badge-ink, var(--sc-primary));
  padding: 5px 11px;
  font-size: 12px;
  letter-spacing: 0.1em;
  line-height: 15px;
}

.variant-accent {
  background: var(--sc-elevated);
  color: var(--ui-badge-ink, var(--sc-text));
}

.variant-eyebrow {
  background: none;
  color: var(--ui-badge-ink, var(--sc-text));
  border: 0;
  border-radius: 0;
  padding: 0;
  font-size: 13px;
  letter-spacing: 0.3px;
  line-height: 16px;
}
</style>
