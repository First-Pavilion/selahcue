<script setup lang="ts">
import AffiliateShell from '@/components/AffiliateShell.vue'
import UiButton from '@/components/UiButton.vue'
import UiBadge from '@/components/UiBadge.vue'

const assets = [
  { name: 'SelahCue Logo Pack (PNG, SVG, EPS)', category: 'Brand Assets', size: '4.2 MB' },
  { name: 'Banner Creatives (728x90, 300x250, 1080x1080)', category: 'Banners', size: '12.8 MB' },
  { name: 'Email Template: "Why Our Church Switched to SelahCue"', category: 'Copy', size: '24 KB' },
  { name: 'Social Media Copy & Screenshots Pack', category: 'Social Media', size: '8.5 MB' }
]
</script>

<template>
  <AffiliateShell>
    <div class="container">
      <div class="page-header">
        <h1>Marketing Resources &amp; Assets</h1>
        <p>Promotional banners, brand assets, email templates, and copy to boost your conversions.</p>
      </div>

      <div class="assets-grid">
        <div v-for="asset in assets" :key="asset.name" class="asset-card">
          <div class="asset-icon">📦</div>
          <div class="asset-info">
            <UiBadge variant="preview" size="sm">{{ asset.category }}</UiBadge>
            <h3>{{ asset.name }}</h3>
            <span class="asset-size">File size: {{ asset.size }}</span>
          </div>
          <UiButton variant="outline" size="sm">Download Asset</UiButton>
        </div>
      </div>
    </div>
  </AffiliateShell>
</template>

<style scoped>
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.page-header { margin-bottom: 32px; }
.page-header h1 { font-size: 28px; font-weight: 700; color: var(--sc-text); margin: 0 0 8px 0; }
.page-header p { font-size: 15px; color: var(--sc-text-secondary); margin: 0; }

.assets-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
.asset-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 28px; display: flex; flex-direction: column; gap: 16px; align-items: flex-start; }
.asset-icon { font-size: 32px; }
.asset-info h3 { font-size: 17px; font-weight: 600; color: var(--sc-text); margin: 8px 0 4px 0; }
.asset-size { font-size: 13px; color: var(--sc-text-muted); }

@media (max-width: 768px) {
  .assets-grid { grid-template-columns: 1fr; }
}
</style>
