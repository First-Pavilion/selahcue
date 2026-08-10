<script setup lang="ts">
defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true }
})
</script>

<template>
  <div class="feature-card">
    <div class="icon-box">
      <span class="icon-text">{{ icon }}</span>
    </div>
    <h3 class="card-title">{{ title }}</h3>
    <p class="card-desc">{{ description }}</p>
  </div>
</template>

<style scoped>
.feature-card {
  background: #12151e;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 16px;
  padding: 32px 28px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.feature-card:hover {
  transform: translateY(-4px);
  border-color: rgba(110, 92, 240, 0.4);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
}

.icon-box {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: #1b1f2c;
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.icon-text {
  font-size: 20px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 10px 0;
  line-height: 1.3;
}

.card-desc {
  font-size: 14px;
  color: #8c97a8;
  line-height: 1.6;
  margin: 0;
}
</style>
