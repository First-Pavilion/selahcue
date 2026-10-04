<script setup lang="ts">
/*
 * The small caps labels the four pages draw on an elevated pill: a row eyebrow (OUTPUTS), a status
 * chip inside a panel (LIVE), a window-title chip (OUTPUTS, 10px) and the requirement chips
 * (MINIMUM). Figma sets each at 10-11px/700 with its own tracking and padding, which is why this is not
 * `UiBadge`: that component is one badge scale (and its brand ink is Uma's, not set here).
 *
 * Inks: `live`, `warn`, `ready` are the status tokens (5.0, 8.1, 7.1:1 on the elevated fill). `brand`
 * is Figma's brand blue (#5b6bd6, 3.39:1 on that fill: a Figma pairing that fails AA), so it reads the
 * ONE overridable property UiBadge uses, `--ui-badge-ink`, and falls back to the readable text colour:
 * when Uma picks the accessible tint (audit class D, account-25), every brand label on the site follows.
 */
defineProps({
  tone: {
    type: String,
    default: 'muted',
    validator: (v: string) => ['muted', 'live', 'warn', 'ready', 'brand'].includes(v),
  },
  /** row: 11/700, 1.1px, 6/12 · status: 11/700, 0.4px, 5/10 · title: 10/700, 0.8px, 5/10 · req: 11/700, 0.9px, 5/10 */
  kind: {
    type: String,
    default: 'row',
    validator: (v: string) => ['row', 'status', 'title', 'req'].includes(v),
  },
})
</script>

<template>
  <span :class="['tone-chip', `kind-${kind}`, `tone-${tone}`]"><slot /></span>
</template>

<style scoped>
.tone-chip {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  background: var(--sc-elevated);
  border-radius: var(--pill-radius);
  font-weight: 700;
  text-transform: uppercase;
  white-space: nowrap;
}

.kind-row {
  padding: 6px 12px;
  font-size: 11px;
  line-height: 13px;
  letter-spacing: 1.1px;
}
.kind-status {
  padding: 5px 10px;
  font-size: 11px;
  line-height: 13px;
  letter-spacing: 0.4px;
}
.kind-title {
  padding: 5px 10px;
  font-size: 10px;
  line-height: 12px;
  letter-spacing: 0.8px;
}
.kind-req {
  padding: 5px 10px;
  font-size: 11px;
  line-height: 13px;
  letter-spacing: 0.9px;
}

.tone-muted {
  color: var(--sc-text-secondary);
}
.tone-live {
  color: var(--sc-live);
}
.tone-warn {
  color: var(--sc-warn);
}
.tone-ready {
  color: var(--sc-preview);
}
.tone-brand {
  color: var(--ui-badge-ink, var(--sc-text));
}
</style>
