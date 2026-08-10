<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const roles = [
  { title: 'Rust Systems & Graphics Engineer', dept: 'Core Engine', location: 'Remote (US/EU/Africa)', type: 'Full-time' },
  { title: 'Senior Vue / Frontend Engineer', dept: 'Web & Dashboard', location: 'Remote', type: 'Full-time' },
  { title: 'Worship Tech Solutions Specialist', dept: 'Customer Success', location: 'Remote', type: 'Full-time' }
]
</script>

<template>
  <div class="careers-page">
    <section class="hero-section">
      <div class="container">
        <UiBadge variant="featured">Join Our Team</UiBadge>
        <h1 class="hero-title">Build software that serves local churches worldwide</h1>
        <p class="hero-sub">We are an engineering-driven, remote-first team committed to high-performance, offline-first worship presentation technology.</p>
      </div>
    </section>

    <!-- Culture Grid -->
    <section class="culture-section">
      <div class="container">
        <h2 class="section-title">Why Work With Us</h2>
        <div class="culture-grid">
          <div class="culture-card">
            <div class="icon">🌍</div>
            <h3>Fully Remote &amp; Flexible</h3>
            <p>Work from anywhere in the world with flexible hours built around your life and family.</p>
          </div>
          <div class="culture-card">
            <div class="icon">🚀</div>
            <h3>High Technical Standards</h3>
            <p>We write Rust, wgpu, and Vue 3 TypeScript. Zero compromise on memory safety, frame latency, or UX quality.</p>
          </div>
          <div class="culture-card">
            <div class="icon">⛪</div>
            <h3>Impact for the Local Church</h3>
            <p>Your work directly supports thousands of volunteer tech teams and worship leaders every single Sunday.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Open Roles -->
    <section class="roles-section">
      <div class="container">
        <h2 class="section-title">Open Positions</h2>
        <div class="roles-list">
          <div v-for="r in roles" :key="r.title" class="role-row">
            <div>
              <h3 class="role-title">{{ r.title }}</h3>
              <p class="role-meta">{{ r.dept }} &middot; {{ r.location }} &middot; {{ r.type }}</p>
            </div>
            <UiButton variant="outline" size="sm" to="/contact">Apply Now →</UiButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.careers-page { background: var(--sc-base); padding-bottom: 80px; }
.container { max-width: 1000px; margin: 0 auto; padding: 0 24px; }
.hero-section { padding: 80px 0 50px; text-align: center; }
.hero-title { font-size: 40px; font-weight: 800; color: var(--sc-text); margin: 16px 0; }
.hero-sub { font-size: 16px; color: var(--sc-text-secondary); max-width: 640px; margin: 0 auto; }

.section-title { font-size: 26px; font-weight: 700; color: var(--sc-text); margin-bottom: 32px; }

.culture-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-bottom: 60px; }
.culture-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 28px; }
.icon { font-size: 32px; margin-bottom: 12px; }
.culture-card h3 { font-size: 18px; color: var(--sc-text); margin: 0 0 8px 0; }
.culture-card p { font-size: 14px; color: var(--sc-text-secondary); line-height: 1.5; margin: 0; }

.roles-list { display: flex; flex-direction: column; gap: 16px; }
.role-row { display: flex; justify-content: space-between; align-items: center; background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 12px; padding: 20px 24px; }
.role-title { font-size: 18px; font-weight: 600; color: var(--sc-text); margin: 0 0 4px 0; }
.role-meta { font-size: 13px; color: var(--sc-text-muted); margin: 0; }

@media (max-width: 768px) {
  .culture-grid { grid-template-columns: 1fr; }
  .role-row { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
