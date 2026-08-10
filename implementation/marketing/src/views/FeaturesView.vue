<script setup lang="ts">
import UiButton from '@/components/UiButton.vue'
import UiBadge from '@/components/UiBadge.vue'
</script>

<template>
  <div class="features-view">
    <!-- Hero Header -->
    <section class="hero-section">
      <div class="container">
        <UiBadge variant="featured">CAPABILITIES DEEP DIVE</UiBadge>
        <h1 class="hero-title">Powerful features for modern worship</h1>
        <p class="hero-sub">Everything you need to run a flawless Sunday service, built into one reliable application.</p>
      </div>
    </section>

    <!-- Feature Rows -->
    <div class="feature-rows">
      <!-- Feature 1: Live Outputs -->
      <section class="feature-row">
        <div class="container row-layout">
          <div class="text-content">
            <UiBadge variant="live" size="sm">ZERO-BLANK GUARANTEE</UiBadge>
            <h2>Live Presentation &amp; Outputs</h2>
            <p>Multi-screen support with our hardware buffer protection. Keep the focus on worship without technical glitches or black screens.</p>
            <ul class="feature-list">
              <li><span class="check">✓</span> Zero-blank hardware frame buffer protection (NFR-024)</li>
              <li><span class="check">✓</span> Independent audience, stage, and stream display routing</li>
              <li><span class="check">✓</span> Smooth hardware-accelerated crossfades and motion backgrounds</li>
            </ul>
          </div>
          <div class="visual-content">
            <div class="mock-card">
              <div class="mock-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="mock-title">Audience Output &middot; 4K 60fps</span>
              </div>
              <div class="mock-body slide-bg">
                <h3 class="slide-text">"Great are You, Lord"</h3>
                <p class="slide-sub">It's Your breath in our lungs</p>
                <div class="mock-tag"><UiBadge variant="live">LIVE ON MAIN</UiBadge></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Feature 2: Scripture -->
      <section class="feature-row alt">
        <div class="container row-layout reverse">
          <div class="text-content">
            <UiBadge variant="preview" size="sm">SCRIPTURE SEARCH</UiBadge>
            <h2>Scripture at Your Fingertips</h2>
            <p>Built-in WEB Bible with instant verse-by-verse lookup. Navigate passages seamlessly during sermon delivery.</p>
            <ul class="feature-list">
              <li><span class="check">✓</span> Sub-second fuzzy and reference search (e.g. Rom 8:28)</li>
              <li><span class="check">✓</span> Copyrighted Bible entitlements (NIV, ESV, NLT) post-activation</li>
              <li><span class="check">✓</span> Customizable typography, verse numbers, and translations</li>
            </ul>
          </div>
          <div class="visual-content">
            <div class="mock-card">
              <div class="mock-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="mock-title">Scripture Search &middot; Romans 8:28</span>
              </div>
              <div class="mock-body scripture-bg">
                <div class="scripture-box">
                  <span class="verse-num">28</span>
                  <p class="verse-text">And we know that in all things God works for the good of those who love him...</p>
                </div>
                <div class="mock-tag"><UiBadge variant="preview">WEB BIBLE &middot; INSTANT</UiBadge></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Feature 3: Service Plans & Timers -->
      <section class="feature-row">
        <div class="container row-layout">
          <div class="text-content">
            <UiBadge variant="warn" size="sm">BOUNDED WORKFLOW</UiBadge>
            <h2>Service Plans &amp; Timers</h2>
            <p>Structured service flows with countdown timers to keep pastors, musicians, and tech teams on schedule.</p>
            <ul class="feature-list">
              <li><span class="check">✓</span> Drag-and-drop service order planning</li>
              <li><span class="check">✓</span> Automated segment countdown clocks &amp; TIME UP alerts</li>
              <li><span class="check">✓</span> Monotonic clock accuracy independent of frame rendering</li>
            </ul>
          </div>
          <div class="visual-content">
            <div class="mock-card">
              <div class="mock-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="mock-title">Service Run Sheet &middot; Sunday 10 AM</span>
              </div>
              <div class="mock-body timer-bg">
                <div class="timer-display">
                  <span class="timer-label">SERMON COUNTDOWN</span>
                  <span class="timer-value">24:13</span>
                </div>
                <div class="mock-tag"><UiBadge variant="warn">RUNNING</UiBadge></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Feature 4: Stage Monitor -->
      <section class="feature-row alt">
        <div class="container row-layout reverse">
          <div class="text-content">
            <UiBadge variant="ndi" size="sm">CONFIDENCE DISPLAY</UiBadge>
            <h2>Stage &amp; Confidence Monitor</h2>
            <p>Dedicated stage display showing current lyrics, next slide, presenter notes, and private operator messages.</p>
            <ul class="feature-list">
              <li><span class="check">✓</span> High-contrast confidence view for worship leaders</li>
              <li><span class="check">✓</span> Next slide preview so singers are never caught off guard</li>
              <li><span class="check">✓</span> Private stage alerts and timer warnings</li>
            </ul>
          </div>
          <div class="visual-content">
            <div class="mock-card">
              <div class="mock-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="mock-title">Stage Monitor Output</span>
              </div>
              <div class="mock-body stage-bg">
                <div class="stage-split">
                  <div class="stage-col">
                    <span class="st-tag">CURRENT</span>
                    <p class="st-text">Holy, Holy, Holy is the Lord</p>
                  </div>
                  <div class="stage-col">
                    <span class="st-tag muted">NEXT</span>
                    <p class="st-text muted">Singing Holy, Holy, Holy</p>
                  </div>
                </div>
                <div class="mock-tag"><UiBadge variant="ready">STAGE READY</UiBadge></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Feature 5: NDI & Multi-Output -->
      <section class="feature-row">
        <div class="container row-layout">
          <div class="text-content">
            <UiBadge variant="ndi" size="sm">BROADCAST INTEGRATION</UiBadge>
            <h2>NDI 5 &amp; Multi-Output</h2>
            <p>Direct broadcast streaming to send lower-thirds and lyrics into OBS, vMix, Wirecast, or hardware switchers.</p>
            <ul class="feature-list">
              <li><span class="check">✓</span> Alpha channel transparency for lower-third overlays</li>
              <li><span class="check">✓</span> Zero capture-card latency over Gigabit Ethernet</li>
              <li><span class="check">✓</span> Independent graphics styling for house vs. broadcast</li>
            </ul>
          </div>
          <div class="visual-content">
            <div class="mock-card">
              <div class="mock-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="mock-title">NDI Broadcast Feed &middot; 1080p60</span>
              </div>
              <div class="mock-body stream-bg">
                <div class="lower-third-overlay">
                  <span class="lt-title">Pastor John Davies</span>
                  <span class="lt-sub">"Walking in Grace" — Series</span>
                </div>
                <div class="mock-tag"><UiBadge variant="ndi">NDI STREAMING</UiBadge></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Feature 6: On-Device Transcript -->
      <section class="feature-row alt">
        <div class="container row-layout reverse">
          <div class="text-content">
            <UiBadge variant="preview" size="sm">LOCAL AI SPEECH</UiBadge>
            <h2>On-Device AI Transcript</h2>
            <p>Offline speech-to-text powered by local Whisper AI without relying on cloud services or internet latency.</p>
            <ul class="feature-list">
              <li><span class="check">✓</span> Real-time speech-to-text with zero cloud data transmission</li>
              <li><span class="check">✓</span> Automatic sermon transcript generation</li>
              <li><span class="check">✓</span> Local GPU hardware acceleration (Metal / Direct3D)</li>
            </ul>
          </div>
          <div class="visual-content">
            <div class="mock-card">
              <div class="mock-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="mock-title">Whisper AI &middot; Local Engine</span>
              </div>
              <div class="mock-body transcript-bg">
                <div class="transcript-box">
                  <span class="tr-label">LIVE TRANSCRIPT</span>
                  <p class="tr-text">"...and we see throughout scripture that grace is not earned, but freely given."</p>
                </div>
                <div class="mock-tag"><UiBadge variant="preview">OFFLINE WHISPER AI</UiBadge></div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Final CTA Section -->
    <section class="cta-section">
      <div class="container cta-card">
        <h2>Experience the SelahCue difference</h2>
        <p>Start free today and experience flawless Sunday services.</p>
        <div class="cta-btns">
          <UiButton variant="gradient" size="lg" to="/download">Download SelahCue Free</UiButton>
          <UiButton variant="outline" size="lg" to="/pricing">View Pricing</UiButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.features-view {
  background: var(--sc-base);
  padding-bottom: 80px;
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

.hero-section {
  padding: 80px 0 50px;
  text-align: center;
}

.hero-title {
  font-size: 44px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 16px 0;
}

.hero-sub {
  font-size: 18px;
  color: var(--sc-text-secondary);
  max-width: 640px;
  margin: 0 auto;
}

.feature-rows {
  display: flex;
  flex-direction: column;
}

.feature-row {
  padding: 80px 0;
}

.feature-row.alt {
  background: var(--sc-surface);
  border-top: 1px solid var(--sc-border);
  border-bottom: 1px solid var(--sc-border);
}

.row-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  align-items: center;
}

.row-layout.reverse {
  direction: ltr;
}

.text-content h2 {
  font-size: 32px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 16px 0;
  line-height: 1.25;
}

.text-content p {
  font-size: 16px;
  color: var(--sc-text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  color: var(--sc-text);
}

.check {
  color: var(--sc-preview);
  font-weight: 800;
}

/* Mock Card Styles */
.mock-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}

.mock-bar {
  height: 36px;
  background: var(--sc-elevated);
  border-bottom: 1px solid var(--sc-border);
  display: flex;
  align-items: center;
  padding: 0 14px;
  gap: 8px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.dot.red { background: #ff5f56; }
.dot.yellow { background: #ffbd2e; }
.dot.green { background: #27c93f; }

.mock-title {
  margin-left: 8px;
  font-size: 12px;
  color: var(--sc-text-muted);
  font-family: monospace;
}

.mock-body {
  height: 220px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
}

.slide-bg { background: linear-gradient(135deg, #1b1b36, #0e0d21); text-align: center; justify-content: center; }
.slide-text { font-size: 24px; font-weight: 700; color: #fff; margin: 0 0 8px 0; }
.slide-sub { font-size: 14px; color: var(--sc-text-muted); margin: 0; }

.scripture-bg { background: #12141a; }
.scripture-box { background: var(--sc-elevated); border-left: 4px solid var(--sc-primary); padding: 16px; border-radius: 8px; }
.verse-num { font-weight: 700; color: var(--sc-gold); font-size: 14px; margin-right: 8px; }
.verse-text { font-size: 15px; color: var(--sc-text); margin: 0; display: inline; }

.timer-bg { background: #0b0d12; align-items: center; justify-content: center; }
.timer-display { text-align: center; }
.timer-label { font-size: 11px; font-weight: 700; color: var(--sc-warn); letter-spacing: 0.05em; display: block; margin-bottom: 4px; }
.timer-value { font-size: 48px; font-weight: 800; font-family: monospace; color: var(--sc-text); }

.stage-bg { background: #000; }
.stage-split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.st-tag { font-size: 11px; font-weight: 700; color: var(--sc-preview); display: block; margin-bottom: 4px; }
.st-tag.muted { color: var(--sc-text-muted); }
.st-text { font-size: 16px; color: #fff; margin: 0; }
.st-text.muted { color: var(--sc-text-muted); font-size: 14px; }

.stream-bg { background: #090b10; justify-content: flex-end; }
.lower-third-overlay { background: rgba(20, 22, 29, 0.9); border-left: 4px solid var(--sc-primary); padding: 12px 18px; border-radius: 6px; }
.lt-title { font-weight: 700; font-size: 15px; color: #fff; display: block; }
.lt-sub { font-size: 13px; color: var(--sc-gold); }

.transcript-bg { background: #14161d; }
.transcript-box { background: var(--sc-elevated); padding: 16px; border-radius: 8px; border: 1px solid var(--sc-border); }
.tr-label { font-size: 10px; font-weight: 700; color: var(--sc-preview); letter-spacing: 0.05em; display: block; margin-bottom: 6px; }
.tr-text { font-size: 14px; font-style: italic; color: var(--sc-text); margin: 0; }

.mock-tag { position: absolute; bottom: 16px; right: 16px; }

.cta-section { padding: 80px 0 0 0; }
.cta-card { background: linear-gradient(135deg, var(--sc-surface), #1c1a3a); border: 1px solid var(--sc-primary); border-radius: 24px; padding: 60px 40px; text-align: center; }
.cta-card h2 { font-size: 32px; font-weight: 800; color: var(--sc-text); margin: 0 0 12px 0; }
.cta-card p { font-size: 16px; color: var(--sc-text-secondary); margin: 0 0 32px 0; }
.cta-btns { display: flex; justify-content: center; gap: 16px; }

@media (max-width: 900px) {
  .row-layout { grid-template-columns: 1fr; gap: 32px; }
  .cta-btns { flex-direction: column; }
}
</style>
