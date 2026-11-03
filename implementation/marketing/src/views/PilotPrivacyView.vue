<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import notice from '../../../../docs/release/pilot-registration/notice.json'
</script>

<template>
  <article class="pilot-privacy container" aria-labelledby="pilot-privacy-heading">
    <UiBadge variant="featured">FIELD TEST PILOT</UiBadge>
    <h1 id="pilot-privacy-heading">{{ notice.title }}</h1>
    <p class="notice-version">Notice {{ notice.version }}</p>
    <p class="availability">Pilot registration is not open yet. This notice explains the handling policy for the planned pilot form.</p>
    <section v-for="(section, index) in notice.sections" :key="section.title" :aria-labelledby="`pilot-notice-${index}`">
      <h2 :id="`pilot-notice-${index}`">{{ section.title }}</h2>
      <p v-for="paragraph in section.paragraphs" :key="paragraph">{{ paragraph }}</p>
    </section>
    <p class="notice-contacts">Contact <a :href="`mailto:${notice.primary_contact}`">{{ notice.primary_contact }}</a> or <a :href="`mailto:${notice.alternate_contact}`">{{ notice.alternate_contact }}</a>.</p>
    <router-link class="pilot-back" to="/download#pilot-downloads">Back to pilot download availability</router-link>
  </article>
</template>

<style scoped>
.pilot-privacy { max-width: 920px; padding-block: 48px 72px; overflow-wrap: anywhere; }
h1 { margin-block: 18px 12px; font-size: clamp(30px, 5vw, 46px); line-height: 1.2; }
h2 { margin-block: 32px 12px; font-size: 24px; line-height: 1.3; }
p { color: var(--sc-text-secondary); line-height: 1.7; margin-block: 12px; }
.notice-version { font-size: 14px; }
.availability { border-left: 3px solid var(--sc-primary); padding-left: 16px; }
a { color: var(--sc-text); text-decoration: underline; }
a:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 4px; }
.notice-contacts { margin-top: 28px; }
.notice-contacts a, .pilot-back { display: inline-flex; align-items: center; min-height: 44px; }
</style>
