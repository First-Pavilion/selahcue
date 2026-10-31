#!/usr/bin/env node
// Offline behavioral controls for the real shared Operator pilot-status client.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const dist = process.env.PILOT_TEST_DIST || path.join(__dirname, '../implementation/desktop/crates/selahcue-operator/dist');
const deadline = 1809129599;
const pilot = (notes = 'available', transcription = 'available') => ({
  state: notes, notes_state: notes, transcription_state: transcription, notes_uses_pilot: true,
  effective_expiry_unix_seconds: deadline, replacement_required: notes !== 'available',
});
function harness() {
  let now = (deadline - 10) * 1000;
  let serial = 0;
  const timers = new Map(), calls = [], listeners = new Map();
  function events(prefix) {
    return {
      addEventListener(type, cb) { listeners.set(prefix + type, cb); },
      removeEventListener(type, cb) { if (listeners.get(prefix + type) === cb) listeners.delete(prefix + type); },
    };
  }
  const document = Object.assign({hidden: false}, events('document:'));
  const window = Object.assign({}, events('window:'));
  window.__TAURI__ = {core: {invoke(cmd) {
    return new Promise((resolve, reject) => calls.push({cmd, resolve, reject}));
  }}};
  class Clock extends Date { static now() { return now; } }
  const context = vm.createContext({window, document, Date: Clock, Promise, Number, JSON,
    setTimeout(cb, ms) { const id = ++serial; timers.set(id, {cb, ms}); return id; },
    clearTimeout(id) { timers.delete(id); },
  });
  assert.ok(fs.existsSync(path.join(dist, 'pilot-access.js')), 'shared pilot status client is implemented');
  vm.runInContext(fs.readFileSync(path.join(dist, 'pilot-access.js'), 'utf8'), context);
  return {api: window.scPilotAccess, calls, timers, window, document, listeners,
    setNow(seconds) { now = seconds * 1000; },
    fireTimer() { const [id, item] = timers.entries().next().value; timers.delete(id); item.cb(); },
    event(name) { listeners.get(name)?.(); },
  };
}
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

test('fixed expiry equality refuses both lanes while preserving ordinary null state', () => {
  const {api} = harness();
  assert.equal(api.normalize(null, deadline), null);
  assert.equal(api.normalize(pilot(), deadline - 1).notes_state, 'available');
  for (const now of [deadline, deadline + 1]) {
    const status = api.normalize(pilot(), now);
    assert.equal(status.notes_state, 'expired');
    assert.equal(status.transcription_state, 'expired');
  }
});
test('one rejected lane does not disable the other available lane', () => {
  const {api} = harness();
  const status = api.normalize(pilot('rejected', 'available'), deadline - 1);
  assert.equal(status.state, 'rejected');
  assert.equal(status.notes_state, 'rejected');
  assert.equal(status.transcription_state, 'available');
  assert.equal(status.replacement_required, true);
});
test('malformed status fails closed and does not copy extra native fields', () => {
  const {api} = harness();
  for (const status of [{}, {notes_state: 'available'}, pilot('unknown'), {...pilot(), effective_expiry_unix_seconds: NaN}]) {
    assert.equal(api.normalize(status, deadline - 1).notes_state, 'unavailable');
  }
  const normalized = api.normalize({...pilot(), key: 'synthetic-secret-do-not-render'}, deadline - 1);
  assert.ok(!JSON.stringify(normalized).includes('synthetic-secret'));
});
test('pilot messages use fixed recovery copy and UTC without developer environment advice', () => {
  const {api} = harness();
  assert.match(api.message(api.normalize(pilot(), deadline - 1), 'notes'), /2027-04-30.*23:59:59.*UTC/);
  for (const state of ['expired', 'rejected', 'unavailable']) {
    const message = api.message(api.normalize(pilot(state, state), deadline - 1), 'notes');
    assert.match(message, /current pilot build|pilot coordinator/);
    assert.doesNotMatch(message, /\.env|API_KEY|synthetic/);
  }
  assert.match(api.errorMessage('pilot_expired'), /expired/);
  assert.match(api.errorMessage('pilot_access_rejected'), /rejected/);
  assert.equal(api.errorMessage('transport'), null);
});
test('visible watcher polls once, expires at cutoff, tears down hidden timers and refreshes on focus', async () => {
  const h = harness();
  let visible = true;
  const seen = [];
  const stop = h.api.watch(() => visible, status => seen.push(status));
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].cmd, 'pilot_access_status');
  h.calls[0].resolve(pilot()); await flush();
  assert.equal(seen.at(-1).notes_state, 'available');
  assert.equal(h.timers.size, 1);
  h.setNow(deadline); h.fireTimer();
  assert.equal(seen.at(-1).notes_state, 'expired');
  assert.equal(h.calls.length, 2);
  visible = false; h.api.visibilityChanged();
  assert.equal(h.timers.size, 0);
  h.calls[1].resolve(pilot()); await flush();
  assert.equal(seen.at(-1).notes_state, 'expired');
  visible = true; h.api.visibilityChanged();
  assert.equal(h.calls.length, 3);
  h.calls[2].resolve(pilot()); await flush();
  h.event('window:focus'); assert.equal(h.calls.length, 4);
  stop(); assert.equal(h.timers.size, 0);
  assert.equal(h.listeners.size, 0);
});
test('late IPC cannot overwrite a fresher provider snapshot and pending IPC never fans out', async () => {
  const h = harness();
  h.api.watch(() => true, () => {});
  h.api.accept(pilot('rejected', 'available'), h.api.revision());
  for (let i = 0; i < 12; i++) h.api.refresh();
  assert.equal(h.calls.length, 1);
  h.calls[0].resolve(pilot()); await flush();
  assert.equal(h.api.current().notes_state, 'rejected');
  assert.equal(h.calls.length, 2);
  const old = h.api.revision();
  h.api.accept(pilot('expired', 'expired'), old);
  assert.equal(h.api.accept(pilot(), old), false);
  assert.equal(h.api.current().notes_state, 'expired');
});
test('ordinary builds keep no idle poll and IPC failure does not invent pilot access', async () => {
  const h = harness();
  h.api.watch(() => true, () => {});
  h.calls[0].resolve(null); await flush();
  assert.equal(h.api.current(), null);
  assert.equal(h.timers.size, 0);
  h.event('window:focus'); h.calls[1].reject(new Error('synthetic transport detail')); await flush();
  assert.equal(h.api.current(), null);
  assert.equal(h.timers.size, 0);
});

// Minimal DOM test seam: actual settings/transcript production modules run unchanged.
function uiHarness(status, ordinary = false) {
  const h = harness();
  const base = new Map();
  function matches(node, selector) {
    const last = selector.trim().split(/\s+/).at(-1);
    if (last.startsWith('#')) return node.id === last.slice(1);
    if (last.startsWith('.')) return node.className.split(/\s+/).includes(last.slice(1));
    return node.tagName.toLowerCase() === last.toLowerCase();
  }
  class Element {
    constructor(tag) {
      this.tagName = tag.toUpperCase(); this.children = []; this.attributes = {}; this.listeners = {};
      this.style = {}; this.dataset = {}; this.className = ''; this.hidden = false; this.disabled = false;
      this.clientHeight = 400; this.clientWidth = 500; this.scrollTop = 0; this._text = '';
      this.classList = {contains: cls => this.className.split(/\s+/).includes(cls),
        add: cls => { if (!this.classList.contains(cls)) this.className += ' ' + cls; },
        remove: cls => { this.className = this.className.split(/\s+/).filter(c => c !== cls).join(' '); },
        toggle: (cls, on) => { if (on) this.classList.add(cls); else this.classList.remove(cls); }};
    }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(c => c.textContent).join(' '); }
    set innerHTML(_) { this.textContent = ''; }
    get innerHTML() { return this.textContent; }
    appendChild(node) { this.children.push(node); node.parentNode = this; return node; }
    removeChild(node) { this.children = this.children.filter(c => c !== node); }
    get firstChild() { return this.children[0] || null; }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    getAttribute(key) { return this.attributes[key] ?? null; }
    removeAttribute(key) { delete this.attributes[key]; }
    addEventListener(type, cb) { this.listeners[type] = cb; }
    click() { if (!this.disabled) this.listeners.click?.({preventDefault() {}, target: this}); }
    focus() { h.document.activeElement = this; }
    getBoundingClientRect() { return {top: 0, bottom: 400, left: 0, right: 500, height: 400, width: 500}; }
    querySelectorAll(selector) {
      const found = [];
      const walk = node => { for (const child of node.children) { if (matches(child, selector)) found.push(child); walk(child); } };
      walk(this); return found;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    contains(node) { return node === this || this.children.some(c => c.contains(node)); }
  }
  for (const m of fs.readFileSync(path.join(dist, 'index.html'), 'utf8').matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/gi)) {
    const node = new Element(m[1]); node.id = m[2]; node.hidden = /\bhidden(?:[\s>])/.test(m[0]); base.set(node.id, node);
  }
  h.document.body = new Element('body');
  h.document.createElement = tag => new Element(tag);
  h.document.createDocumentFragment = () => new Element('fragment');
  h.document.createTextNode = text => { const n = new Element('text'); n.textContent = text; return n; };
  h.document.getElementById = id => {
    if (base.has(id)) return base.get(id);
    for (const node of base.values()) { const found = node.querySelector('#' + id); if (found) return found; }
    return null;
  };
  h.document.querySelectorAll = selector => {
    const found = [];
    for (const node of base.values()) {
      if (matches(node, selector)) found.push(node);
      found.push(...node.querySelectorAll(selector));
    }
    return found;
  };
  h.document.querySelector = selector => h.document.querySelectorAll(selector)[0] || null;
  let providerReads = 0;
  const defaults = {
    transcription_mode: 'on_device', on_device: {ready: false, detail: 'Model is not installed'},
    cloud_transcription_consent: true, cloud_notes_consent: true, include: {},
    notes_templates: [], translations: [], cloud_status: ordinary ? 'key_missing' : status && status.notes_uses_pilot === false ? 'hosted' : 'direct_provider',
    notes_available: !ordinary, notes_provider: ordinary ? null : {name: status && status.notes_uses_pilot === false ? 'Hosted fixture' : 'OpenAI', kind: status && status.notes_uses_pilot === false ? 'selahcue_hosted' : 'openai', model: 'fixture', developer_key: false},
    transcription_available: !ordinary,
    transcription_provider: ordinary ? null : {name: 'Deepgram', model: 'nova-3', developer_key: false},
    pilot_access: ordinary ? null : status,
  };
  h.commands = [];
  h.generationResult = {ok: false, error: 'pilot_access_rejected', message: 'synthetic-secret-response-body'};
  h.window.__TAURI__.core.invoke = cmd => {
    h.commands.push(cmd);
    if (cmd === 'transcript_generate_notes') return h.pendingGeneration || Promise.resolve(h.generationResult);
    if (cmd === 'providers_view') { providerReads++; return Promise.resolve(defaults); }
    if (cmd === 'pilot_access_status') return Promise.resolve(ordinary ? null : status);
    if (cmd === 'transcript_list') return Promise.resolve([{id: 1, label: 'Fixture sermon', started_at_ms: 0, ended_at_ms: 2000, segment_count: 1}]);
    if (cmd === 'transcript_get') return Promise.resolve({id: 1, label: 'Fixture sermon', started_at_ms: 0, ended_at_ms: 2000, segments: [{text: 'A sufficiently long completed synthetic sermon transcript for the confirmation preview.', start_ms: 0, end_ms: 2000}], notes: null, draft: h.savedDraft || null, detections: []});
    if (cmd === 'note_generation_limits') return Promise.resolve({max_transcript_chars: 1000});
    return Promise.resolve(null);
  };
  const context = vm.createContext({window: h.window, document: h.document, console, Promise, Date, Number, JSON,
    requestAnimationFrame() { return 1; }, cancelAnimationFrame() {},
    setTimeout, clearTimeout, ResizeObserver: class {observe() {} disconnect() {}},
  });
  h.window.requestAnimationFrame = () => 1;
  h.window.cancelAnimationFrame = () => {};
  h.load = file => vm.runInContext(fs.readFileSync(path.join(dist, file), 'utf8'), context);
  h.node = id => h.document.getElementById(id);
  h.providerReads = () => providerReads;
  h.setStatus = next => { status = next; defaults.pilot_access = next; };
  return h;
}
test('actual Providers panel shows per-lane pilot recovery, retains focus and ordinary developer guidance', async () => {
  const status = pilot('rejected', 'available');
  const h = uiHarness(status);
  h.node('surface-settings').classList.add('active');
  h.load('settings.js'); h.window.settingsActivate(); await flush();
  assert.match(h.node('pp-ai').textContent, /Pilot.*rejected/);
  assert.doesNotMatch(h.node('pp-ai').textContent, /\.env|developer key|Coming soon/);
  assert.match(h.node('pp-trans').textContent, /Pilot.*available until/);
  const control = h.node('pp-consent-notes'); control.focus();
  h.api.accept({...status, notes_state: 'expired'}, h.api.revision()); await flush();
  assert.equal(h.document.activeElement.id, 'pp-consent-notes');
  assert.match(h.node('pp-ai').textContent, /expired/);
  const ordinary = uiHarness(null, true);
  ordinary.load('settings.js'); ordinary.window.settingsActivate(); await flush();
  assert.match(ordinary.node('pp-ai').textContent, /No key configured/);
  assert.match(ordinary.node('pp-ai').textContent, /developer API key/);
});

test('actual transcript UI blocks expired notes while preserving the stored transcript surface', async () => {
  const h = uiHarness(pilot('expired', 'available'));
  h.node('surface-transcripts').classList.add('active');
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  assert.ok(h.node('tr-pilot-access'), 'transcript pilot status is visible');
  assert.match(h.node('tr-pilot-access').textContent, /expired.*current pilot build/);
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  assert.equal(h.node('tr-detail-title').textContent, 'Fixture sermon');
  assert.equal(h.node('tr-generate').disabled, true);
  h.node('tr-generate').click(); await flush();
  assert.equal(h.commands.filter(cmd => cmd === 'transcript_generate_notes').length, 0);
});
test('actual Generate preview and rejected result use pilot copy without clearing the transcript', async () => {
  const h = uiHarness(pilot());
  h.node('surface-transcripts').classList.add('active');
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  assert.equal(h.node('tr-detail-error').hidden, true);
  h.node('tr-generate').click(); await flush();
  assert.equal(h.node('tr-gen-preview').hidden, false);
  assert.match(h.node('tr-gen-preview').textContent, /Pilot.*available until/);
  h.node('tr-gen-preview-confirm').click(); await flush();
  assert.equal(h.commands.filter(cmd => cmd === 'transcript_generate_notes').length, 1);
  assert.match(h.node('tr-gen-result').textContent, /Pilot.*rejected.*pilot coordinator/);
  assert.doesNotMatch(h.node('tr-gen-result').textContent, /synthetic-secret|\.env/);
  assert.equal(h.node('tr-detail-title').textContent, 'Fixture sermon');
});

test('observed expiry is not reversed by a backwards wall clock', async () => {
  const h = harness();
  h.api.watch(() => true, () => {});
  h.calls[0].resolve(pilot()); await flush();
  h.setNow(deadline); h.fireTimer();
  assert.equal(h.api.current().notes_state, 'expired');
  h.setNow(deadline - 100);
  assert.equal(h.api.current().notes_state, 'expired');
});
test('document hide and pagehide stop timers, then pageshow refreshes authoritative status', async () => {
  const h = harness();
  const stop = h.api.watch(() => true, () => {});
  h.calls[0].resolve(pilot()); await flush();
  h.document.hidden = true; h.event('document:visibilitychange');
  assert.equal(h.timers.size, 0);
  h.event('window:focus'); assert.equal(h.calls.length, 1);
  h.document.hidden = false; h.event('document:visibilitychange');
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve(pilot()); await flush();
  h.event('window:pagehide'); assert.equal(h.timers.size, 0);
  h.event('window:pageshow'); assert.equal(h.calls.length, 3);
  stop();
});
test('expired open preview cannot send and moves focus to the recovery notice', async () => {
  const h = uiHarness(pilot());
  h.node('surface-transcripts').classList.add('active');
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  h.node('tr-generate').click(); await flush();
  const confirm = h.node('tr-gen-preview-confirm'); confirm.focus();
  h.setNow(deadline); h.api.visibilityChanged(); await flush();
  assert.equal(confirm.disabled, true);
  assert.equal(h.document.activeElement.id, 'tr-pilot-access');
  assert.match(h.node('tr-gen-preview-pilot').textContent, /expired/);
  confirm.click(); await flush();
  assert.equal(h.commands.filter(cmd => cmd === 'transcript_generate_notes').length, 0);
  h.node('tr-gen-preview-cancel').click();
  assert.equal(h.node('tr-gen-preview').hidden, true);
});
test('healthy notes remain usable after transcription rejection and refused regeneration retains saved draft', async () => {
  const h = uiHarness(pilot('available', 'rejected'));
  h.savedDraft = {title: 'Saved fixture draft', summary: 'Preserve this accepted summary', sections: []};
  h.node('surface-transcripts').classList.add('active');
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  assert.match(h.node('tr-gen-result').textContent, /Preserve this accepted summary/);
  assert.equal(h.node('tr-regenerate').disabled, false);
  h.node('tr-regenerate').click(); await flush();
  h.node('tr-gen-preview-confirm').click(); await flush();
  assert.equal(h.commands.filter(cmd => cmd === 'transcript_generate_notes').length, 1);
  assert.match(h.node('tr-pilot-access').textContent, /rejected/);
  assert.match(h.node('tr-gen-result').textContent, /Preserve this accepted summary/);
  assert.equal(h.node('tr-gen-edit').disabled, false);
});

test('ordinary Generate remains disabled and busy while native generation IPC is held', async () => {
  const h = uiHarness(null, true);
  let settle;
  h.pendingGeneration = new Promise(resolve => { settle = resolve; });
  h.node('surface-transcripts').classList.add('active');
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  h.node('tr-generate').click(); await flush();
  h.node('tr-gen-preview-confirm').click(); await flush();
  assert.equal(h.node('tr-generate').getAttribute('aria-busy'), 'true');
  assert.equal(h.node('tr-generate').disabled, true);
  settle({ok: false, error: 'transport', message: 'synthetic untrusted detail'}); await flush();
  assert.equal(h.node('tr-generate').getAttribute('aria-busy'), null);
  assert.equal(h.node('tr-generate').disabled, false);
});

test('authoritative hosted source survives pilot expiry and is never described as pilot notes', () => {
  const {api} = harness();
  const status = api.normalize({...pilot(), notes_uses_pilot: false}, deadline);
  assert.equal(status.notes_uses_pilot, false);
  assert.equal(status.notes_state, 'available');
  assert.equal(status.transcription_state, 'expired');
  assert.equal(status.state, 'expired');
  assert.equal(api.message(status, 'notes'), '');
  assert.match(api.message(status, 'transcription'), /expired/);
});
test('missing or malformed notes applicability never exempts notes from pilot admission', () => {
  const {api} = harness();
  for (const flag of [undefined, null, 0, 'false', {}]) {
    const status = api.normalize({...pilot(), notes_uses_pilot: flag}, deadline - 1);
    assert.equal(status.notes_state, 'unavailable');
    assert.equal(status.notes_uses_pilot, true);
    assert.equal(status.transcription_state, 'available');
  }
});
test('configured hosted notes remain available when missing pilot config has no expiry', () => {
  const {api} = harness();
  const status = api.normalize({...pilot('available', 'unavailable'), state: 'unavailable',
    notes_uses_pilot: false, effective_expiry_unix_seconds: null}, deadline);
  assert.equal(status.notes_state, 'available');
  assert.equal(status.transcription_state, 'unavailable');
  assert.equal(status.notes_uses_pilot, false);
});
test('actual mixed-source panels retain normal hosted copy and Generate after pilot transcription expires', async () => {
  const status = {...pilot('available', 'expired'), notes_uses_pilot: false, state: 'expired'};
  const h = uiHarness(status);
  h.node('surface-settings').classList.add('active');
  h.load('settings.js'); h.window.settingsActivate(); await flush();
  assert.match(h.node('pp-ai').textContent, /Hosted fixture.*no accounts, keys or billing/);
  assert.doesNotMatch(h.node('pp-ai').textContent, /PILOT|Pilot access|current pilot build/);
  assert.match(h.node('pp-trans').textContent, /Pilot.*expired/);
  h.node('surface-settings').classList.remove('active');
  h.node('surface-transcripts').classList.add('active');
  h.generationResult = {ok: false, error: 'not_configured', message: 'synthetic untrusted detail'};
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  assert.equal(h.node('tr-generate').disabled, false);
  assert.equal(h.node('tr-pilot-access').hidden, true);
  h.node('tr-generate').click(); await flush();
  assert.doesNotMatch(h.node('tr-gen-preview').textContent, /Pilot|pilot build/);
  h.node('tr-gen-preview-confirm').click(); await flush();
  assert.equal(h.commands.filter(cmd => cmd === 'transcript_generate_notes').length, 1);
  assert.doesNotMatch(h.node('tr-gen-result').textContent, /Pilot|pilot build|synthetic untrusted/);
});

test('late pilot request rejection cannot latch rejection onto newly selected hosted notes', async () => {
  const h = uiHarness(pilot());
  let settle;
  h.pendingGeneration = new Promise(resolve => { settle = resolve; });
  h.node('surface-transcripts').classList.add('active');
  h.load('transcripts.js'); h.window.trActivate(); await flush();
  h.node('tr-list').querySelector('.tr-card-open').click(); await flush();
  h.node('tr-generate').click(); await flush();
  h.node('tr-gen-preview-confirm').click(); await flush();
  const hosted = {...pilot(), notes_uses_pilot: false};
  h.setStatus(hosted); h.api.accept(hosted, h.api.revision());
  settle({ok: false, error: 'pilot_access_rejected', message: 'synthetic provider body'}); await flush();
  assert.equal(h.api.current().notes_uses_pilot, false);
  assert.equal(h.api.current().notes_state, 'available');
  assert.equal(h.api.current().transcription_state, 'available');
  assert.equal(h.node('tr-generate').disabled, false);
  assert.doesNotMatch(h.node('tr-gen-result').textContent, /synthetic provider body/);
});
