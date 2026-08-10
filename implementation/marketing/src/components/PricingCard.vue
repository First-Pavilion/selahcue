<script setup lang="ts">
import UiButton from './UiButton.vue'
import UiBadge from './UiBadge.vue'

defineProps({
  name: { type: String, required: true },
  price: { type: [Number, String], required: true },
  period: { type: String, default: 'month' },
  description: { type: String, required: true },
  features: { type: Array as () => string[], required: true },
  cta: { type: String, required: true },
  popular: { type: Boolean, default: false },
  annual: { type: Boolean, default: false }
})
</script>

<template>
  <div :class="['pricing-card', { popular }]">
    <div v-if="popular" class="popular-tag">
      <UiBadge variant="accent" size="sm">MOST POPULAR</UiBadge>
    </div>

    <h3 class="plan-name">{{ name }}</h3>
    
    <div class="plan-price-box">
      <template v-if="typeof price === 'number'">
        <span class="price-val">${{ annual && price > 0 ? Math.round(price * 0.8) : price }}</span>
        <span class="price-period">/ {{ period }}</span>
      </template>
      <template v-else>
        <span class="price-val custom">{{ price }}</span>
      </template>
    </div>

    <p class="plan-desc">{{ description }}</p>

    <div class="cta-wrapper">
      <UiButton :variant="popular ? 'gradient' : 'outline'" size="md" block>
        {{ cta }}
      </UiButton>
    </div>

    <div class="features-divider"></div>

    <ul class="features-list">
      <li v-for="feature in features" :key="feature">
        <span class="check-icon">✓</span>
        <span>{{ feature }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.pricing-card {
  background: #12151e;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  padding: 36px 30px;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.pricing-card.popular {
  border-color: var(--sc-primary);
  box-shadow: 0 0 40px rgba(110, 92, 240, 0.25), 0 20px 40px rgba(0, 0, 0, 0.5);
  background: linear-gradient(180deg, #161926 0%, #12141e 100%);
}

.popular-tag {
  position: absolute;
  top: -14px;
  right: 24px;
}

.plan-name {
  font-size: 22px;
  font-weight: 800;
  color: #ffffff;
  margin: 0 0 16px 0;
}

.plan-price-box {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 12px;
}

.price-val {
  font-size: 44px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1;
}

.price-val.custom {
  font-size: 36px;
}

.price-period {
  font-size: 15px;
  color: #717d93;
}

.plan-desc {
  font-size: 14px;
  color: #8c97a8;
  line-height: 1.5;
  margin: 0 0 24px 0;
  min-height: 42px;
}

.cta-wrapper {
  margin-bottom: 28px;
}

.features-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin-bottom: 24px;
}

.features-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.features-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 14px;
  color: #c5cedc;
  line-height: 1.4;
}

.check-icon {
  color: #2bb673;
  font-weight: 800;
  font-size: 14px;
  flex-shrink: 0;
}
</style>
