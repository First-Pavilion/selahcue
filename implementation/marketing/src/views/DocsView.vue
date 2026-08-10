<script setup lang="ts">
import { ref } from 'vue'

const activeDoc = ref('getting-started')

const topics = [
  { id: 'getting-started', title: 'Getting Started', desc: 'Overview, installation & system requirements' },
  { id: 'display-outputs', title: 'Display & Outputs', desc: 'Configuring main projector, stage monitor & NDI' },
  { id: 'scripture-bibles', title: 'Scripture & Bibles', desc: 'Built-in Bibles & copyrighted entitlement downloads' },
  { id: 'timers-clocks', title: 'Timers & Service Plans', desc: 'Setting up service order & stage countdown timers' },
  { id: 'mobile-control', title: 'Mobile Control App', desc: 'Pairing Flutter mobile controller via local LAN' },
  { id: 'troubleshooting', title: 'Troubleshooting', desc: 'Graphics drivers, performance tuning & logs' }
]
</script>

<template>
  <div class="docs-page">
    <div class="container">
      <div class="docs-layout">
        <!-- Left Sidebar Navigation -->
        <aside class="docs-sidebar">
          <div class="sidebar-header">
            <span class="sidebar-title">Documentation</span>
          </div>
          <nav class="sidebar-nav">
            <button 
              v-for="item in topics" 
              :key="item.id"
              :class="['nav-item', { active: activeDoc === item.id }]"
              @click="activeDoc = item.id"
            >
              {{ item.title }}
            </button>
          </nav>
        </aside>

        <!-- Right Content Area -->
        <main class="docs-content">
          <div class="breadcrumb">Docs &gt; {{ topics.find(t => t.id === activeDoc)?.title }}</div>
          
          <h1 class="doc-title">{{ topics.find(t => t.id === activeDoc)?.title }}</h1>
          <p class="doc-lead">{{ topics.find(t => t.id === activeDoc)?.desc }}</p>

          <div class="doc-body">
            <h2>Overview</h2>
            <p>
              SelahCue is an offline-first presentation application built specifically for church environments. 
              The application separates the staged <strong>Preview</strong> content from the <strong>Live Program</strong> output to ensure full confidence during live worship.
            </p>

            <div class="callout tip">
              <span class="callout-icon">💡</span>
              <div>
                <strong>Pro Tip:</strong> You can stage any scripture verse or song slide by double-clicking it, or press <kbd>Enter</kbd> to send the staged preview directly to live.
              </div>
            </div>

            <h2>Key Hardware &amp; System Requirements</h2>
            <ul>
              <li><strong>Operating System:</strong> Windows 10/11 (64-bit) or macOS 12+ (Apple Silicon or Intel)</li>
              <li><strong>GPU / Decoders:</strong> Direct3D 12 (Windows) / Metal (macOS) hardware decoder support</li>
              <li><strong>Network:</strong> Gigabit Ethernet or 5GHz Wi-Fi (only required for NDI output and mobile pairing over LAN)</li>
            </ul>

            <div class="callout warning">
              <span class="callout-icon">⚠️</span>
              <div>
                <strong>Copyrighted Bible Entitlements:</strong> Licensed translations (such as NIV, ESV, or NLT) are downloaded post-activation into an encrypted local store. Public-domain versions (WEB, ASV, BSB) are bundled offline out of the box.
              </div>
            </div>

            <h2>Code Example: NDI Configuration</h2>
            <pre class="code-block"><code>// selahcue-output.json
{
  "outputs": [
    { "name": "Audience Main", "target": "Display 2", "resolution": "1920x1080" },
    { "name": "Stage Display", "target": "Display 3", "mode": "confidence" },
    { "name": "NDI Stream", "target": "ndi://selahcue-program", "fps": 60 }
  ]
}</code></pre>
          </div>

          <div class="doc-feedback">
            <span>Was this article helpful?</span>
            <button type="button" class="feedback-btn">👍 Yes</button>
            <button type="button" class="feedback-btn">👎 No</button>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.docs-page {
  padding: 60px 0;
  background: var(--sc-base);
  min-height: calc(100vh - 160px);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.docs-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 48px;
  align-items: start;
}

/* Sidebar */
.docs-sidebar {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 20px;
  position: sticky;
  top: 100px;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--sc-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: block;
  margin-bottom: 16px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  background: none;
  border: none;
  text-align: left;
  padding: 10px 14px;
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--sc-text-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.nav-item:hover {
  background: var(--sc-elevated);
  color: var(--sc-text);
}

.nav-item.active {
  background: var(--sc-accent-soft);
  color: var(--sc-primary);
  font-weight: 600;
}

/* Content */
.docs-content {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 48px;
}

.breadcrumb {
  font-size: 13px;
  color: var(--sc-text-muted);
  margin-bottom: 16px;
}

.doc-title {
  font-size: 36px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 0 0 12px 0;
}

.doc-lead {
  font-size: 18px;
  color: var(--sc-text-secondary);
  margin: 0 0 32px 0;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--sc-border);
}

.doc-body h2 {
  font-size: 22px;
  color: var(--sc-text);
  margin: 32px 0 16px 0;
}

.doc-body p {
  font-size: 16px;
  color: var(--sc-text-secondary);
  line-height: 1.7;
  margin-bottom: 20px;
}

.doc-body ul {
  padding-left: 20px;
  margin-bottom: 24px;
}

.doc-body li {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
}

/* Callouts */
.callout {
  display: flex;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 12px;
  margin: 24px 0;
  font-size: 14px;
  line-height: 1.6;
}

.callout.tip {
  background: var(--sc-preview-soft);
  border: 1px solid var(--sc-preview-border);
  color: var(--sc-text);
}

.callout.warning {
  background: var(--sc-warn-soft);
  border: 1px solid var(--sc-warn-border);
  color: var(--sc-text);
}

.callout-icon { font-size: 20px; }

kbd {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 12px;
}

.code-block {
  background: var(--sc-inset);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 20px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 14px;
  color: var(--sc-gold);
}

.doc-feedback {
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--sc-border);
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
  color: var(--sc-text-muted);
}

.feedback-btn {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 6px 14px;
  color: var(--sc-text);
  font-size: 13px;
  cursor: pointer;
}

.feedback-btn:hover {
  background: var(--sc-border);
}

@media (max-width: 900px) {
  .docs-layout { grid-template-columns: 1fr; }
  .docs-sidebar { position: static; }
}
</style>
