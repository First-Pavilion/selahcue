<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

interface Role {
  title: string
  dept: string
  location: string
  type: string
}

/**
 * EMPTY ON PURPOSE (ClickUp 17tnw2b0x3h). The three roles that stood here, with their departments, places and Apply buttons,
 * were invented: nothing in the repo or the company's records opens a role. A role goes here only when it is real. The row
 * layout below (Figma 503:173) is kept for that day; `tests/secondaryPages.test.ts` renders it with fixture data.
 *
 * The "culture strip" (remote-first, "high standards", "thousands of volunteer tech teams") made company claims nobody
 * backed and is gone; its one product-true card, the offline rule, is already told on Home and in the docs.
 */
const roles: Role[] = []
</script>

<template>
  <div class="careers-page">
    <section class="hero-section container">
      <UiBadge variant="featured">CAREERS</UiBadge>
      <h1 class="hero-title">Build tools churches rely on</h1>
      <p class="hero-sub">SelahCue is offline-first presentation software for churches.</p>
    </section>

    <!-- Open Roles: a full-bleed band. -->
    <section class="roles-band" aria-labelledby="roles-heading">
      <div class="container roles-inner">
        <h2 id="roles-heading" class="roles-title">Open roles</h2>
        <!-- Nothing is open, so nothing is listed and nobody is invited to apply. -->
        <p v-if="roles.length === 0" class="roles-empty">There are no open roles right now.</p>
        <template v-else>
          <div class="roles-list">
            <article v-for="r in roles" :key="r.title" class="role-row">
              <div class="role-main">
                <h3 class="role-title">{{ r.title }}</h3>
                <ul class="role-tags" aria-label="Role details">
                  <li class="role-tag">{{ r.dept }}</li>
                  <li class="role-tag">{{ r.location }}</li>
                  <li class="role-tag">{{ r.type }}</li>
                </ul>
              </div>
              <UiButton variant="secondary" size="sm" to="/contact">Apply Now →<span class="sr-only"> for {{ r.title }}</span></UiButton>
            </article>
          </div>
          <!-- Plain text, no link: the one place it could send people (the contact page) has no working form. -->
          <p class="roles-note">Don't see your role? We're glad to meet thoughtful people.</p>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.careers-page { background: var(--sc-base); }

/* HERO (Figma 503:139): padding 96 top / 44 bottom, 20px between the pill, the headline and the subline, all
   centred. The headline is 498 wide, so it breaks as "Build tools churches / rely on"; it takes the shared
   page-hero token and is set to the frame's 50/56 from the desktop breakpoint up. */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding-top: 96px;
  padding-bottom: 44px;
  text-align: center;
}

.hero-title { font: var(--font-h1-page); color: var(--sc-text); max-width: 500px; }

@media (min-width: 1200px) {
  .hero-title { font-size: 50px; line-height: 56px; }
}

.hero-sub { max-width: 700px; font-size: 19px; line-height: 30px; color: var(--sc-text-secondary); }

/* ROLES (Figma 503:173): a full-bleed panel-surface band, padding 44 / 48, 24px between its parts; a centred
   30/700 heading; the list 940 wide, rows 14px apart; each row radius 16 on the page fill, padding 20 / 24 from
   the edge, the title over three tag pills on the left and the button on the right; then a centred closing line. */
.roles-band { background: var(--sc-surface-alt); }

.roles-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding-top: 44px;
  padding-bottom: 48px;
}

.roles-title { font-size: 30px; font-weight: 700; line-height: 36px; text-align: center; color: var(--sc-text); }

.roles-list { display: flex; flex-direction: column; gap: 14px; width: 100%; max-width: 940px; }

.role-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  background: var(--sc-base);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 19px 23px;
}

.role-main { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.role-title { font-size: 18px; font-weight: 600; line-height: 22px; color: var(--sc-text); }

.role-tags { display: flex; flex-wrap: wrap; gap: 8px; }

.role-tag {
  padding: 5px 10px;
  border-radius: var(--pill-radius);
  background: var(--sc-elevated);
  font-size: 12px;
  font-weight: 500;
  line-height: 15px;
  color: var(--sc-text-secondary);
}

.roles-empty { max-width: 640px; font-size: 16px; line-height: 24px; text-align: center; color: var(--sc-text-secondary); }

.roles-note { max-width: 640px; font-size: 15px; line-height: 22px; text-align: center; color: var(--sc-text-secondary); }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@media (max-width: 767.98px) {
  .hero-section { padding-top: 56px; padding-bottom: 28px; gap: 16px; }
  .hero-sub { font-size: 17px; line-height: 26px; }
  .roles-inner { padding-top: 36px; padding-bottom: 40px; }
  .role-row { flex-direction: column; align-items: flex-start; gap: 14px; padding: 19px; }
}
</style>
