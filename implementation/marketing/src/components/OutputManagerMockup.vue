<script setup lang="ts">
import UiBadge from './UiBadge.vue'
</script>

<template>
  <div class="output-manager-card">
    <div class="card-header">
      <span class="card-title">OUTPUT MANAGER</span>
      <UiBadge variant="accent" size="sm">3 OUTPUTS ACTIVE</UiBadge>
    </div>

    <div class="output-rows">
      <!-- Row 1: Main Output -->
      <div class="output-row">
        <div class="row-left">
          <div class="output-icon live">📺</div>
          <div>
            <h4 class="output-name">Audience - Main</h4>
            <span class="output-sub">Display 2 &middot; 1920x1080 &middot; 60fps</span>
          </div>
        </div>
        <UiBadge variant="live">MAIN &middot; LIVE</UiBadge>
      </div>

      <!-- Row 2: Stage Display -->
      <div class="output-row">
        <div class="row-left">
          <div class="output-icon ready">🖥️</div>
          <div>
            <h4 class="output-name">Stage Display</h4>
            <span class="output-sub">Display 3 &middot; Confidence View</span>
          </div>
        </div>
        <UiBadge variant="ready">STAGE &middot; READY</UiBadge>
      </div>

      <!-- Row 3: NDI Stream -->
      <div class="output-row">
        <div class="row-left">
          <div class="output-icon ndi">📡</div>
          <div>
            <h4 class="output-name">Livestream Program</h4>
            <span class="output-sub">NDI 5 Stream &middot; Alpha Channel</span>
          </div>
        </div>
        <UiBadge variant="ndi">NDI &middot; BROADCASTING</UiBadge>
      </div>
    </div>
  </div>
</template>

<style scoped>
.output-manager-card {
  background: #12151e;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
}

.card-header {
  height: 48px;
  background: #181c28;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.card-title {
  font-size: 12px;
  font-weight: 700;
  color: #717d93;
  letter-spacing: 0.06em;
}

.output-rows {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.output-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #191d2a;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px 18px;
}

.row-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.output-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.output-icon.live { background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.25); }
.output-icon.ready { background: rgba(245, 165, 36, 0.15); border: 1px solid rgba(245, 165, 36, 0.25); }
.output-icon.ndi { background: rgba(43, 182, 115, 0.15); border: 1px solid rgba(43, 182, 115, 0.25); }

.output-name {
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 4px 0;
}

.output-sub {
  font-size: 12px;
  color: #717d93;
}
</style>
