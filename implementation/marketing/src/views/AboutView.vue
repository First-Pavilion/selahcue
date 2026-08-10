<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
</script>

<template>
  <div class="about-page">
    <!-- Hero Section -->
    <section class="hero-section">
      <div class="container">
        <UiBadge variant="featured">Our Story & Mission</UiBadge>
        <h1 class="hero-title">Reengineering how the church presents the Gospel</h1>
        <p class="hero-sub">
          We built SelahCue because worship leaders and media volunteers deserve tools that are 100% reliable, offline-first, and effortless to operate.
        </p>
      </div>
    </section>

    <!-- Mission & Values Grid -->
    <section class="values-section">
      <div class="container">
        <h2 class="section-title">The Principles Behind SelahCue</h2>
        
        <div class="values-grid">
          <div class="value-card">
            <div class="value-icon">🛡️</div>
            <h3>Never Blank the Screen</h3>
            <p>Sunday morning is the one moment you can't repeat. SelahCue holds the live output on hardware buffers so the screen never goes dark during a service.</p>
          </div>

          <div class="value-card">
            <div class="value-icon">📶</div>
            <h3>Offline First, Always</h3>
            <p>Church Wi-Fi drops. Internet backhauls fail. SelahCue runs 100% locally on venue hardware — Bibles, lyrics, media, and stage displays need no cloud connection.</p>
          </div>

          <div class="value-card">
            <div class="value-icon">⚡</div>
            <h3>Volunteer-Friendly Speed</h3>
            <p>A new volunteer should be able to run a service within 5 minutes. We prioritize clean, intuitive operator UX over cluttered menus.</p>
          </div>

          <div class="value-card">
            <div class="value-icon">📖</div>
            <h3>Scripture & Rights Protection</h3>
            <p>We respect copyright law and publishers. Public domain Bibles are bundled; copyrighted translations are safely entitled and encrypted post-activation.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="cta-section">
      <div class="container cta-card">
        <h2>Ready to upgrade your church's presentation?</h2>
        <p>Join thousands of churches running services with total confidence.</p>
        <div class="cta-btns">
          <UiButton variant="gradient" size="lg" to="/download">Download SelahCue Free</UiButton>
          <UiButton variant="outline" size="lg" to="/contact">Contact Our Team</UiButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.about-page {
  background: var(--sc-base);
  padding-bottom: 80px;
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

.hero-section {
  padding: 80px 0 60px;
  text-align: center;
}

.hero-title {
  font-size: 44px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 20px 0;
  line-height: 1.25;
}

.hero-sub {
  font-size: 18px;
  color: var(--sc-text-secondary);
  max-width: 760px;
  margin: 0 auto;
  line-height: 1.6;
}

.values-section {
  padding: 60px 0;
}

.section-title {
  text-align: center;
  font-size: 32px;
  font-weight: 700;
  color: var(--sc-text);
  margin-bottom: 48px;
}

.values-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 28px;
}

.value-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 32px;
}

.value-icon {
  font-size: 36px;
  margin-bottom: 16px;
}

.value-card h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 12px 0;
}

.value-card p {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 1.6;
  margin: 0;
}

.cta-section {
  padding: 40px 0;
}

.cta-card {
  background: linear-gradient(135deg, var(--sc-surface), #1c1a3a);
  border: 1px solid var(--sc-primary);
  border-radius: 24px;
  padding: 60px 40px;
  text-align: center;
}

.cta-card h2 {
  font-size: 32px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 16px 0;
}

.cta-card p {
  font-size: 16px;
  color: var(--sc-text-secondary);
  margin: 0 0 32px 0;
}

.cta-btns {
  display: flex;
  justify-content: center;
  gap: 16px;
}

@media (max-width: 768px) {
  .hero-title { font-size: 32px; }
  .values-grid { grid-template-columns: 1fr; }
  .cta-btns { flex-direction: column; }
}
</style>
