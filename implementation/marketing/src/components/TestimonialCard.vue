<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  quote: { type: String, required: true },
  author: { type: String, required: true },
  /** "Role · Church", the frame's separator. */
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
  <!-- A quotation and its source: figure, blockquote, figcaption. The name is not a heading (it used
       to be an h4 under an h2, which skipped a level), and the initials repeat it, so they are hidden. -->
  <figure class="testimonial-card">
    <blockquote class="quote-text">“{{ quote }}”</blockquote>
    <figcaption class="author-row">
      <div :class="['avatar-circle', avatarColor]" aria-hidden="true">
        {{ initials }}
      </div>
      <div class="author-info">
        <p class="author-name">{{ author }}</p>
        <p class="author-role">{{ role }}</p>
      </div>
    </figcaption>
  </figure>
</template>

<style scoped>
/*
 * Figma 478:129: 400 wide at 1440, radius 16, padding 28, 22px between quote and source, on the base
 * ground inside the panel band, 1px border. Quote 17/26 regular in the primary ink, with typographic
 * marks and no italics; avatar a 42px circle; name 14.5/600; role 12.5 in the secondary ink.
 */
.testimonial-card {
  margin: 0;
  background: var(--sc-base);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.quote-text {
  margin: 0;
  font-size: 17px;
  line-height: 26px;
  color: var(--sc-text);
}

.author-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: auto;
}

.avatar-circle {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  /* Pure white on the brand fill (4.7:1). The green and gold fills take the dark ink instead: Figma's
     white initials are 2.3:1 and 2.0:1 on them (audit home-44, class D); 8.4:1 and 10.9:1 here. */
  color: #fff;
}

.avatar-circle.blue { background: var(--sc-primary); }
.avatar-circle.green { background: var(--sc-preview); color: var(--sc-base); }
.avatar-circle.amber { background: var(--sc-gold); color: var(--sc-base); }

.author-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.author-name {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
  line-height: 18px;
  color: var(--sc-text);
}

.author-role {
  margin: 0;
  font-size: 12.5px;
  line-height: 15px;
  color: var(--sc-text-secondary);
}
</style>
