<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  quote: { type: String, required: true },
  author: { type: String, required: true },
  role: { type: String, required: true },
  avatarColor: { type: String, default: 'blue' } // 'blue' | 'green' | 'amber'
})

const initials = computed(() => {
  return props.author
    .split(' ')
    .map(n => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase()
})
</script>

<template>
  <div class="testimonial-card">
    <p class="quote-text">{{ quote }}</p>
    <div class="author-row">
      <div :class="['avatar-circle', avatarColor]">
        {{ initials }}
      </div>
      <div class="author-info">
        <h4 class="author-name">{{ author }}</h4>
        <p class="author-role">{{ role }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.testimonial-card {
  background: #12151e;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 32px 28px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.quote-text {
  font-size: 15px;
  color: #c5cedc;
  line-height: 1.6;
  margin: 0 0 28px 0;
  font-style: italic;
}

.author-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.avatar-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
}

.avatar-circle.blue { background: #5b6bd6; }
.avatar-circle.green { background: #2bb673; }
.avatar-circle.amber { background: #f2b53c; }

.author-name {
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 2px 0;
}

.author-role {
  font-size: 13px;
  color: #717d93;
  margin: 0;
}
</style>
