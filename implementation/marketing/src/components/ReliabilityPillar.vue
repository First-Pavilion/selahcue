<script setup lang="ts">
import UiBadge from './UiBadge.vue'

defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  metric: { type: String, required: true },
  variant: { type: String, default: 'primary' } // 'primary' | 'preview' | 'warn'
})
</script>

<template>
  <div class="pillar-card">
    <div :class="['icon-box', variant]">
      <span class="icon-text">{{ icon }}</span>
    </div>
    <h3 class="pillar-title">{{ title }}</h3>
    <p class="pillar-desc">{{ description }}</p>
    <div class="pillar-footer">
      <UiBadge :variant="variant === 'primary' ? 'accent' : variant === 'preview' ? 'preview' : 'warn'" size="sm">
        {{ metric }}
      </UiBadge>
    </div>
  </div>
</template>

<style scoped>
.pillar-card {
  background: #12151e;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 16px;
  padding: 32px 28px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.icon-box {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.icon-box.primary {
  background: rgba(110, 92, 240, 0.15);
  border: 1px solid rgba(110, 92, 240, 0.3);
}

.icon-box.preview {
  background: rgba(43, 182, 115, 0.15);
  border: 1px solid rgba(43, 182, 115, 0.3);
}

.icon-box.warn {
  background: rgba(245, 165, 36, 0.15);
  border: 1px solid rgba(245, 165, 36, 0.3);
}

.icon-text {
  font-size: 20px;
}

.pillar-title {
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 10px 0;
}

.pillar-desc {
  font-size: 14px;
  color: #8c97a8;
  line-height: 1.6;
  margin: 0 0 24px 0;
  flex-grow: 1;
}

.pillar-footer {
  margin-top: auto;
}
</style>
