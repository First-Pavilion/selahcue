<script setup lang="ts">
import HomeIcon from './home/HomeIcon.vue'

defineProps({
  /** A `HomeIcon` name (shield-check, wifi-off, zap). */
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  /** The tile's fill: brand, preview green or warn amber. */
  variant: { type: String, default: 'primary' } // 'primary' | 'preview' | 'warn'
})
</script>

<template>
  <div class="pillar-card">
    <div :class="['icon-box', variant]">
      <HomeIcon :name="icon" />
    </div>
    <h3 class="pillar-title">{{ title }}</h3>
    <p class="pillar-desc">{{ description }}</p>
  </div>
</template>

<style scoped>
/*
 * Figma 474:130: 397 wide at 1440, radius 14, padding 28/24, 14px between the blocks, on the base
 * ground inside the panel band, 1px border. Nothing follows the description: the frame draws no
 * metric badge (audit home-22, class D: Uma decides; the "0 Blanks" and "100% Offline" badges were
 * claims with no counter behind them and "≤3s Start" is an unmeasured number, home-23).
 */
.pillar-card {
  background: var(--sc-base);
  border: 1px solid var(--sc-border);
  border-radius: 14px;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
}

/* Figma 474:131: a 46px tile, radius 12, FILLED with the status colour, holding a white 22px icon. */
.icon-box {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  /* Pure white, Figma's own non-token colour for an icon on a coloured fill. The icon is decorative
     (the title says the same thing), so it is not held to the 3:1 a meaningful graphic needs. */
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-box.primary {
  background: var(--sc-primary);
}

.icon-box.preview {
  background: var(--sc-preview);
}

.icon-box.warn {
  background: var(--sc-warn);
}

.pillar-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 24px;
  color: var(--sc-text);
  margin: 0;
}

.pillar-desc {
  font-size: 15px;
  line-height: 23px;
  color: var(--sc-text-secondary);
  margin: 0;
}
</style>
