<script setup lang="ts">
// The busy glyph in front of a loading auth button's label (Figma 749:143). One component for every loading button;
// the reasons are in `auth.css` beside `.au-spinner`, and a test holds every `:loading` button to it.
</script>

<template>
  <span class="au-spinner" aria-hidden="true">↻</span>
</template>
