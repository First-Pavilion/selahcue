<script setup lang="ts">
import HomeIcon from './home/HomeIcon.vue'

defineProps({
  /** A `HomeIcon` name (monitor, book, list, layout, radio, mic). */
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true }
})
</script>

<template>
  <div class="feature-card">
    <div class="icon-box">
      <HomeIcon :name="icon" />
    </div>
    <h3 class="card-title">{{ title }}</h3>
    <p class="card-desc">{{ description }}</p>
  </div>
</template>

<style scoped>
/*
 * Figma 472:130: 402 wide at 1440, radius 14, padding 28/26, 15px between the blocks, on the panel fill
 * with the 1px border. The icon tile (472:131) is a 44px pure-black square, radius 11, holding a white
 * 22px stroke icon at 1.74px. The title is 18.5/600, the blurb 14.5/22 in the secondary ink.
 */
.feature-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 14px;
  padding: 28px 26px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 15px;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

/* Not drawn in Figma (audit home-19, class D: Uma decides whether it stays). Kept as it was, on tokens. */
.feature-card:hover {
  transform: translateY(-4px);
  border-color: var(--sc-primary);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
}

.icon-box {
  width: 44px;
  height: 44px;
  border-radius: 11px;
  /* Figma draws the tile pure black; there is no token for it. */
  background: #000;
  /* Pure white, Figma's own non-token colour for an icon on a coloured fill. */
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-title {
  font-size: 18.5px;
  font-weight: 600;
  line-height: 22px;
  color: var(--sc-text);
  margin: 0;
}

.card-desc {
  font-size: 14.5px;
  line-height: 22px;
  color: var(--sc-text-secondary);
  margin: 0;
}
</style>
