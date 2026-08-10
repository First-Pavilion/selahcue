<script setup lang="ts">
defineProps({
  lines: { type: Number, default: 3 },
  widths: { type: Array as () => number[], default: () => [40, 100, 60] },
  height: { type: Number, default: 14 }
})
</script>

<template>
  <div class="skeleton-wrapper" aria-hidden="true">
    <div 
      v-for="n in lines" 
      :key="n"
      class="skeleton-line"
      :style="{
        width: (widths[n - 1] || 100) + '%',
        height: height + 'px'
      }"
    ></div>
  </div>
</template>

<style scoped>
.skeleton-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.skeleton-line {
  background: var(--sc-elevated);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}

.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.05),
    transparent
  );
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  100% {
    transform: translateX(100%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-line::after {
    animation: none;
  }
}
</style>
