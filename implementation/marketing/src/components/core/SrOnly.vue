<script setup lang="ts">
/*
 * Text for assistive technology only: present in the accessibility tree, not drawn. ONE copy of the rule
 * for the core pages (it was pasted into two scoped style blocks; review round 2, Cody N22). A shared
 * `.sr-only` in main.css is the shared-components pass's to add.
 *
 * `position: absolute` needs a positioned ancestor to be contained: the table's scroller is `relative`
 * (an uncontained one widened the page 124px on a phone), and the requirement card is too.
 */
defineProps({
  /** The element to render: a heading keeps its level (`h2`), a label is a `span`. */
  tag: { type: String, default: 'span' },
})
</script>

<template>
  <component :is="tag" class="sr-only"><slot /></component>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
