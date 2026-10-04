<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'

// The roles are the build's own and stay exactly as they were: whether any role exists to list, and what
// the page says when none does, are the owner's and Uma's decisions (careers-07, careers-09). The Figma
// roles are placeholders and are not added.
const roles = [
  { title: 'Rust Systems & Graphics Engineer', dept: 'Core Engine', location: 'Remote (US/EU/Africa)', type: 'Full-time' },
  { title: 'Senior Vue / Frontend Engineer', dept: 'Web & Dashboard', location: 'Remote', type: 'Full-time' },
  { title: 'Worship Tech Solutions Specialist', dept: 'Customer Success', location: 'Remote', type: 'Full-time' }
]

/**
 * The culture strip (Figma 503:144): four cards, each an icon tile on the frame's fills (brand, green, amber,
 * red). The first three keep the build's own copy (what it may claim about remote work and impact is the
 * owner's decision, careers-08). The fourth is backed by the product itself: the offline-first rule the
 * architecture and the blog post state, so it adds no company claim the repo does not support.
 */
const culture = [
  {
    icon: 'globe',
    tone: 'brand',
    title: 'Fully Remote & Flexible',
    body: 'Work from anywhere in the world with flexible hours built around your life and family.'
  },
  {
    icon: 'check-circle',
    tone: 'preview',
    title: 'High Technical Standards',
    body: 'We write Rust, wgpu, and Vue 3 TypeScript. Zero compromise on memory safety, frame latency, or UX quality.'
  },
  {
    icon: 'heart',
    tone: 'warn',
    title: 'Impact for the Local Church',
    body: 'Your work directly supports thousands of volunteer tech teams and worship leaders every single Sunday.'
  },
  {
    icon: 'wifi-off',
    tone: 'live',
    title: 'Built to Work Offline',
    body: 'A service cannot be repeated, so slides, scripture and timers run on the desktop with no network.'
  }
] as const
</script>

<template>
  <div class="careers-page">
    <section class="hero-section container">
      <UiBadge variant="featured">CAREERS</UiBadge>
      <h1 class="hero-title">Build tools churches rely on</h1>
      <p class="hero-sub">We are an engineering-driven, remote-first team committed to high-performance, offline-first worship presentation technology.</p>
    </section>

    <!-- Culture strip: four icon-tile cards straight under the hero, no heading. -->
    <section class="culture-section container">
      <div class="culture-grid">
        <div v-for="c in culture" :key="c.title" class="culture-card">
          <CategoryIcon class="culture-icon" :name="c.icon" :tone="c.tone" size="tile" />
          <h2>{{ c.title }}</h2>
          <p>{{ c.body }}</p>
        </div>
      </div>
    </section>

    <!-- Open Roles: a full-bleed band. -->
    <section class="roles-band" aria-labelledby="roles-heading">
      <div class="container roles-inner">
        <h2 id="roles-heading" class="roles-title">Open roles</h2>
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
        <!-- Plain text, no link: this line is new, and the one place it could send people (the contact page) is a form
             that sends nothing. A destination returns when the contact form is honest (ClickUp 17tnw2b0x3h). -->
        <p class="roles-note">Don't see your role? We're always glad to meet thoughtful people — reach out.</p>
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

/* CULTURE (Figma 503:144): padding 32 top / 48 bottom, four 294px cards 24px apart, radius 18, padding 26 / 24
   from the edge (the stroke is drawn inside), 13px between the tile, the title and the text. */
.culture-section { padding-top: 32px; padding-bottom: 48px; }

.culture-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; }

.culture-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 13px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
  padding: 25px 23px;
}

.culture-card h2 { font-size: 17.5px; font-weight: 600; line-height: 21px; color: var(--sc-text); }
.culture-card p { font-size: 14px; line-height: 21px; color: var(--sc-text-secondary); }

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

.roles-note { max-width: 640px; font-size: 15px; line-height: 22px; text-align: center; color: var(--sc-text-secondary); }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@media (max-width: 1199.98px) {
  .culture-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 767.98px) {
  .hero-section { padding-top: 56px; padding-bottom: 28px; gap: 16px; }
  .hero-sub { font-size: 17px; line-height: 26px; }
  .culture-section { padding-top: 16px; padding-bottom: 40px; }
  .culture-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .culture-card { padding: 21px; }
  .roles-inner { padding-top: 36px; padding-bottom: 40px; }
  .role-row { flex-direction: column; align-items: flex-start; gap: 14px; padding: 19px; }
}
</style>
