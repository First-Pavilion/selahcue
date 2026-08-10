<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps({
  items: {
    type: Array as () => Array<{ question: string; answer: string }>,
    required: true
  },
  defaultOpen: {
    type: Number,
    default: 0
  }
})

const openIndex = ref<number | null>(props.defaultOpen)

const toggle = (index: number) => {
  openIndex.value = openIndex.value === index ? null : index
}
</script>

<template>
  <div class="faq-accordion">
    <div 
      v-for="(item, index) in items" 
      :key="index"
      class="faq-item"
    >
      <button 
        class="faq-question" 
        @click="toggle(index)"
        :aria-expanded="openIndex === index"
      >
        <span>{{ item.question }}</span>
        <svg 
          class="toggle-icon" 
          :class="{ rotated: openIndex === index }"
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
      </button>
      <div 
        class="faq-answer-wrapper"
        :class="{ open: openIndex === index }"
      >
        <div class="faq-answer">
          <p>{{ item.answer }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.faq-accordion {
  display: flex;
  flex-direction: column;
}

.faq-item {
  border-bottom: 1px solid var(--sc-border);
}

.faq-item:last-child {
  border-bottom: none;
}

.faq-question {
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  padding: 24px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  color: var(--sc-text);
  font-family: var(--font-family);
  font-size: 17px;
  font-weight: 600;
  transition: color var(--transition-fast);
}

.faq-question:hover {
  color: var(--sc-primary-hover);
}

.toggle-icon {
  width: 24px;
  height: 24px;
  color: var(--sc-text-secondary);
  transition: transform 0.3s ease;
  flex-shrink: 0;
  margin-left: 16px;
}

.toggle-icon.rotated {
  transform: rotate(45deg);
  color: var(--sc-primary);
}

.faq-answer-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
}

.faq-answer-wrapper.open {
  grid-template-rows: 1fr;
}

.faq-answer {
  overflow: hidden;
}

.faq-answer p {
  padding-bottom: 24px;
  margin: 0;
  color: var(--sc-text-secondary);
  font-size: 15px;
  line-height: 1.6;
}
</style>
