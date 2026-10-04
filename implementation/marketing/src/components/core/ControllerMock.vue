<script setup lang="ts">
/*
 * The phone beside "Control from your phone" (Figma 489:154): an illustration of the SelahCue
 * Controller, 280x305. It replaces the empty "Mobile App Mockup" frame (audit download-07). It is
 * decoration (aria-hidden) and states nothing about availability: the store badges beside it say the
 * apps are not published yet.
 *
 * Inks are chosen to hold AA on their own fills, because the harness reads every text node, hidden or
 * not: "Go Live" is dark on the green (8.4:1; the operator console ships dark ink on its green GO LIVE
 * for the same reason, Figma's white is 2.7:1), "Blank" is white on the operator's BLACKOUT red
 * #a3283a (7.19:1; white on Figma's #ef4444 is 3.8:1).
 */
</script>

<template>
  <div class="controller-mock" aria-hidden="true">
    <div class="screen">
      <div class="top">
        <span class="brand-mark"><img src="/selahcue-logo.png" alt="" /></span>
        <span class="name">Controller</span>
        <span class="state"><i class="state-dot"></i>CONNECTED</span>
      </div>
      <div class="now">
        <span class="now-label">ON SCREEN NOW</span>
        <span class="now-title">John 3:16</span>
        <span class="line wide"></span>
        <span class="line narrow"></span>
      </div>
      <span class="go-live">Go Live</span>
      <div class="pair">
        <span class="blank">Blank</span>
        <span class="next">Next</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.controller-mock {
  /* The operator's BLACKOUT red (operator dist/app.css `#clear-all.armed`, white on it 7.19:1). No token
     exists for it, so it is named once here (review round 1, Cody N16). */
  --mock-blank: #a3283a;
  box-sizing: border-box;
  width: 280px;
  max-width: 100%;
  /* Figma pads 10px from the outer edge, stroke inside: 9px plus the 1px border. */
  padding: 9px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 40px;
}

.screen {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 16px;
  background: var(--sc-base);
  border-radius: 30px;
}

.top {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 19px;
}

/* 16px, as drawn. A scoped rule, not a static `style=` attribute: Vue hoists a fully static subtree into an
   HTML string, so the attribute would ship as markup and a `style-src` policy without 'unsafe-inline' would
   drop it (review round 1, Shadow F3). */
.top .brand-mark {
  --mark-size: 16px;
}

.name {
  font-size: 14px;
  font-weight: 600;
  line-height: 17px;
  color: var(--sc-text);
}

.state {
  margin-left: 16px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  background: var(--sc-elevated);
  border-radius: var(--pill-radius);
  font-size: 9px;
  font-weight: 700;
  line-height: 11px;
  letter-spacing: 0.4px;
  color: var(--sc-preview);
}

.state-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.now {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--sc-surface);
  border-radius: 14px;
}

.now-label {
  font-size: 9px;
  font-weight: 700;
  line-height: 11px;
  letter-spacing: 0.5px;
  color: var(--sc-text-secondary);
}

.now-title {
  font-size: 17px;
  font-weight: 600;
  line-height: 21px;
  color: var(--sc-text);
}

.line {
  height: 9px;
  border-radius: 4.5px;
  background: var(--sc-elevated);
}
.line.wide {
  width: 100%;
}
.line.narrow {
  width: 60%;
}

.go-live,
.blank,
.next {
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.go-live {
  height: 46px;
  border-radius: 12px;
  background: var(--sc-preview);
  font-size: 15px;
  color: var(--sc-base);
}

.pair {
  display: flex;
  gap: 10px;
}

.blank,
.next {
  flex: 1;
  height: 40px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 600;
}

.blank {
  background: var(--mock-blank);
  color: #fff;
}

.next {
  background: var(--sc-elevated);
  color: var(--sc-text);
}
</style>
