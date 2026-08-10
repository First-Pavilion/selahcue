<script setup lang="ts">
</script>

<template>
  <div class="console-mockup">
    <!-- Window Header Bar -->
    <div class="window-header">
      <div class="traffic-lights">
        <span class="light close"></span>
        <span class="light minimize"></span>
        <span class="light maximize"></span>
      </div>
      <div class="window-title">SelahCue Operator Console</div>
    </div>

    <!-- Interface Content Grid (2 Side-by-Side Output Panels) -->
    <div class="interface-grid">
      <!-- Left Panel: Main Live Output -->
      <div class="screen-panel live">
        <div class="panel-topbar">
          <span class="status-badge live">● LIVE</span>
          <span class="panel-label">MAIN OUTPUT</span>
        </div>
        <div class="screen-content">
          <h2 class="slide-text">FOR GOD SO LOVED THE WORLD...</h2>
          <p class="slide-ref">JOHN 3:16 &middot; WEB BIBLE</p>
        </div>
      </div>

      <!-- Right Panel: Stage Preview Display -->
      <div class="screen-panel preview">
        <div class="panel-topbar">
          <span class="status-badge ready">● PREVIEW</span>
          <span class="panel-label">STAGE DISPLAY</span>
        </div>
        <div class="screen-content">
          <span class="stage-tag">CURRENT</span>
          <h2 class="slide-text stage">FOR GOD SO LOVED THE WORLD...</h2>
          <span class="stage-tag next">NEXT</span>
          <p class="slide-next">THAT HE GAVE HIS ONE AND ONLY SON</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.console-mockup {
  background: #0e1017;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.05);
}

.window-header {
  height: 42px;
  background: #141722;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  padding: 0 16px;
  position: relative;
}

.traffic-lights {
  display: flex;
  gap: 8px;
}

.light {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.light.close { background: #ff5f56; }
.light.minimize { background: #ffbd2e; }
.light.maximize { background: #27c93f; }

.window-title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 13px;
  font-weight: 500;
  color: #717d93;
}

.interface-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 20px;
  background: #090a0f;
}

.screen-panel {
  background: #12151f;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #181c29;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.panel-label {
  font-size: 11px;
  font-weight: 700;
  color: #717d93;
  letter-spacing: 0.05em;
}

.status-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
}

.status-badge.live {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.status-badge.ready {
  background: rgba(245, 165, 36, 0.15);
  color: #f5a524;
  border: 1px solid rgba(245, 165, 36, 0.3);
}

.screen-content {
  padding: 40px 24px;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  background: #0a0b10;
}

.slide-text {
  font-size: 18px;
  font-weight: 700;
  color: #f2b84b;
  margin: 0 0 8px 0;
  letter-spacing: 0.03em;
  line-height: 1.4;
}

.slide-text.stage {
  font-size: 16px;
  color: #ffffff;
}

.slide-ref {
  font-size: 12px;
  color: #717d93;
  margin: 0;
  font-weight: 600;
}

.stage-tag {
  font-size: 10px;
  font-weight: 800;
  color: #f5a524;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.stage-tag.next {
  color: #717d93;
  margin-top: 14px;
}

.slide-next {
  font-size: 13px;
  color: #717d93;
  margin: 0;
}

@media (max-width: 768px) {
  .interface-grid {
    grid-template-columns: 1fr;
  }
}
</style>
