<script setup lang="ts">
import { ref, useId } from 'vue'

const props = defineProps({
  items: {
    type: Array as () => Array<{ question: string; answer: string }>,
    required: true
  },
  defaultOpen: {
    type: Number,
    default: 0
  },
  /**
   * The Affiliates frame: one card (880px, radius 16, 1px border) with ruled rows of 18px 22px.
   * Opt-in; the Home and Pricing frames draw the plain rows, which stay the default.
   */
  boxed: {
    type: Boolean,
    default: false
  }
})

const openIndex = ref<number | null>(props.defaultOpen)

const toggle = (index: number) => {
  openIndex.value = openIndex.value === index ? null : index
}

/**
 * One id prefix per accordion, so two on a page never share an id. Each question and its
 * answer get a pair of ids: the button controls the answer, the answer is labelled by the
 * button (the disclosure pattern, WAI-ARIA APG).
 */
const uid = useId()

const questionId = (index: number) => `${uid}-q-${index}`
const answerId = (index: number) => `${uid}-a-${index}`
</script>

<template>
  <div :class="['faq-accordion', { 'is-boxed': boxed }]">
    <div
      v-for="(item, index) in items"
      :key="index"
      class="faq-item"
      :class="{ open: openIndex === index }"
    >
      <button
        :id="questionId(index)"
        class="faq-question"
        :aria-expanded="openIndex === index"
        :aria-controls="answerId(index)"
        @click="toggle(index)"
      >
        <span>{{ item.question }}</span>
        <svg
          class="toggle-icon"
          :class="{ rotated: openIndex === index }"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
      </button>
      <div
        :id="answerId(index)"
        role="region"
        :aria-labelledby="questionId(index)"
        class="faq-answer-wrapper"
        :class="{ open: openIndex === index }"
        :inert="openIndex !== index"
        :aria-hidden="openIndex === index ? undefined : 'true'"
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
  width: 22px;
  height: 22px;
  color: var(--sc-text-secondary);
  transition: transform 0.3s ease;
  flex-shrink: 0;
  margin-left: 16px;
}

.toggle-icon.rotated {
  transform: rotate(45deg);
  color: var(--sc-primary);
}

/*
 * A collapsed answer is only 0fr tall, which on its own leaves it in the accessibility tree,
 * found by find-in-page, and its links still tab stops. `inert` and `aria-hidden` (set on this
 * element in the template) take it out of both trees at once; `visibility` does the same for a
 * browser without `inert`, and waits for the collapse to finish so the animation is not cut off.
 */
.faq-answer-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  visibility: hidden;
  transition: grid-template-rows 0.3s ease, visibility 0s linear 0.3s;
}

.faq-answer-wrapper.open {
  grid-template-rows: 1fr;
  visibility: visible;
  transition: grid-template-rows 0.3s ease, visibility 0s;
}

@media (prefers-reduced-motion: reduce) {
  .faq-answer-wrapper,
  .faq-answer-wrapper.open {
    transition: none;
  }
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

/*
 * The boxed card (Affiliates, Figma 542:199): 880 wide, radius 16, --sc-base fill and a 1px
 * --sc-border; rows ruled by the same 1px; question 16/600, answer 15/23 with the answer
 * text 790 wide; a 10.5px plus at 1.5px stroke, primary when open.
 *
 * Figma draws every stroke INSIDE the frame, so the rows are 55 high (113 open with a two-line
 * answer) and the card 333, rule and border included. Here the card's outline is an inset
 * shadow (it takes no room), and each ruled row takes the rule's 1px off its bottom padding.
 * Review of PR 173 measured 56, 114 and 339 before this.
 */
.faq-accordion.is-boxed {
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  box-sizing: border-box;
  background: var(--sc-base);
  box-shadow: inset 0 0 0 1px var(--sc-border);
  border-radius: 16px;
  overflow: hidden;
}

.is-boxed .faq-question {
  padding: 18px 22px;
  font-size: 16px;
  line-height: 19px;
}

.is-boxed .faq-item:not(:last-child) .faq-question {
  padding-bottom: 17px;
}

.is-boxed .faq-item.open .faq-question {
  padding-bottom: 12px;
}

.is-boxed .toggle-icon {
  width: 16px;
  height: 16px;
  margin-right: 1px;
  /* The plus fills two thirds of the icon's 24-unit box: 16px draws it 10.7px across (Figma
     10.5), and a 2.25-unit stroke scales to the drawn 1.5px. */
  stroke-width: 2.25px;
}

.is-boxed .faq-answer p {
  padding: 0 68px 18px 22px;
  font-size: 15px;
  line-height: 23px;
}

.is-boxed .faq-item:not(:last-child) .faq-answer p {
  padding-bottom: 17px;
}
</style>
