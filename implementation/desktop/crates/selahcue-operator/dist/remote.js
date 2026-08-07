// Remote Control surface (Design 2.0, Figma 359:124). Pair phones/tablets as controllers over the
// LAN, approve a pending pair request with a role, and manage paired devices (role · last seen ·
// status · revoke). Self-contained (the surface is registered in app.js's APP_SURFACES; nav +
// ⌘⇧R are handled there). Loaded after app.js.
//
// DATA: uses a local model with a sample fallback — the SAME pattern the Screens surface uses for
// its default registry — because the operator does not yet have an IPC channel to the host output
// window's pairing/session/RBAC service. When that contract lands, swap the sample seed + the
// approve/deny/revoke/role/new-code handlers to real Tauri commands (see the handoff for the
// proposed command set). Roles are the REAL selahcue-lan RBAC roles (Operator/Producer/Assistant/
// Viewer); the design's "Scripture Operator / Worship Leader / Observer" are friendlier aliases.
(function () {
  "use strict";
  var root = document.getElementById("surface-remote");
  if (!root) return;

  var ROLES = [
    { id: "operator", label: "Operator", cls: "rc-role-operator" },
    { id: "producer", label: "Producer", cls: "rc-role-producer" },
    { id: "assistant", label: "Assistant", cls: "rc-role-assistant" },
    { id: "viewer", label: "Viewer", cls: "rc-role-viewer" },
  ];
  var ROLE_BY = {};
  ROLES.forEach(function (r) { ROLE_BY[r.id] = r; });
  var STATUS = {
    online: { label: "Online", cls: "rc-status-online" },
    idle: { label: "Idle", cls: "rc-status-idle" },
    offline: { label: "Offline", cls: "rc-status-offline" },
  };
  var CODE_TTL = 60000; // a pairing code is single-use and short-lived

  // --- local model (sample fallback; see file header) ---
  var uid = 1;
  var state = {
    code: null,
    pending: [
      { id: uid++, name: "Anna’s iPhone", platform: "iPhone", role: "assistant" },
    ],
    devices: [
      { id: uid++, name: "Booth iPad", meta: "iPadOS · 192.168.1.20", role: "producer", seen: "just now", status: "online" },
      { id: uid++, name: "Stage phone", meta: "Android · 192.168.1.31", role: "operator", seen: "2 min ago", status: "online" },
      { id: uid++, name: "Guest tablet", meta: "iPadOS · 192.168.1.44", role: "viewer", seen: "18 min ago", status: "idle" },
    ],
  };

  // ---------- helpers ----------
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function announce(msg) {
    var live = document.getElementById("rc-live");
    if (live) live.textContent = msg;
  }
  function randHex(bytes) {
    var a;
    if (window.crypto && crypto.getRandomValues) { a = new Uint8Array(bytes); crypto.getRandomValues(a); }
    else { a = []; for (var i = 0; i < bytes; i++) a.push(Math.floor(Math.random() * 256)); }
    return Array.prototype.map.call(a, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("").toUpperCase();
  }

  // Decorative QR: a version-1-style module grid (three finder patterns + a payload-seeded data
  // field) so "New code" visibly changes it. NOT a scannable code — the real single-use pairing
  // QR is emitted by the host output window; this mirrors it visually until that data is exposed.
  function hashStr(s) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return h >>> 0;
  }
  function drawQR(payload) {
    var cv = document.getElementById("rc-qr");
    if (!cv || !cv.getContext) return;
    var ctx = cv.getContext("2d");
    var W = cv.width, N = 25, m = W / N;
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, W, W);
    ctx.fillStyle = "#0b0d12";
    var seed = hashStr(payload);
    function rnd() { seed = (Math.imul(seed, 1103515245) + 12345) >>> 0; return (seed >>> 8) / 16777216; }
    function finder(gx, gy) {
      for (var y = 0; y < 7; y++) for (var x = 0; x < 7; x++) {
        var on = (x === 0 || x === 6 || y === 0 || y === 6) || (x >= 2 && x <= 4 && y >= 2 && y <= 4);
        if (on) ctx.fillRect((gx + x) * m, (gy + y) * m, m, m);
      }
    }
    for (var y = 0; y < N; y++) for (var x = 0; x < N; x++) {
      if ((x < 8 && y < 8) || (x >= N - 8 && y < 8) || (x < 8 && y >= N - 8)) continue; // finder zones
      if (rnd() > 0.5) ctx.fillRect(x * m, y * m, m, m);
    }
    finder(0, 0); finder(N - 7, 0); finder(0, N - 7);
  }

  function genCode() {
    var raw = randHex(4); // 4 bytes → 8 hex chars
    var fp = raw.slice(0, 2) + " · " + raw.slice(2, 4) + " · " + raw.slice(4, 6) + " · " + raw.slice(6, 8);
    var fpShort = raw.slice(0, 2) + "·" + raw.slice(2, 4) + "·" + raw.slice(4, 6);
    state.code = { fp: fp, fpShort: fpShort, expiresAt: Date.now() + CODE_TTL };
    drawQR("selahcue://pair?fp=" + raw + "&t=" + Date.now());
    var fpEl = document.getElementById("rc-fp");
    if (fpEl) fpEl.textContent = fp;
    tickCountdown();
  }

  // ---------- countdown (single bounded interval) ----------
  var cdTimer = null;
  function tickCountdown() {
    var c = state.code; if (!c) return;
    var exp = document.getElementById("rc-expiry");
    var txt = document.getElementById("rc-expiry-txt");
    if (!exp || !txt) return;
    var ms = c.expiresAt - Date.now();
    if (ms <= 0) { exp.classList.add("rc-expired"); txt.textContent = "Single-use · code expired — generate a new one"; return; }
    exp.classList.remove("rc-expired");
    var s = Math.ceil(ms / 1000), mm = Math.floor(s / 60), ss = ("0" + (s % 60)).slice(-2);
    txt.textContent = "Single-use · expires in " + mm + ":" + ss;
  }

  // ---------- role picker ----------
  function roleSelect(current, ariaLabel, onChange) {
    var sel = document.createElement("select");
    sel.className = "rc-role " + ROLE_BY[current].cls;
    sel.setAttribute("aria-label", ariaLabel);
    ROLES.forEach(function (r) {
      var o = document.createElement("option");
      o.value = r.id; o.textContent = r.label;
      if (r.id === current) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener("change", function () {
      sel.className = "rc-role " + ROLE_BY[sel.value].cls;
      onChange(sel.value);
    });
    return sel;
  }

  // ---------- render ----------
  function renderCount() {
    var n = document.getElementById("rc-count-n");
    if (n) n.textContent = String(state.devices.length);
  }

  function renderPending() {
    var host = document.getElementById("rc-pending");
    host.innerHTML = "";
    if (!state.pending.length) {
      host.appendChild(el("div", "rc-empty", "No pending requests. New pair attempts appear here for approval."));
      return;
    }
    state.pending.forEach(function (p) {
      var card = el("div", "rc-pending-card");
      card.appendChild(el("div", "rc-dev-ico", "📱"));
      var body = el("div", "rc-pending-body");
      body.appendChild(el("div", "rc-pending-name", p.name));
      body.appendChild(el("div", "rc-pending-sub",
        "wants to pair · verify fingerprint " + (state.code ? state.code.fpShort : "—") + " matches the phone"));
      card.appendChild(body);
      var wrap = el("div", "rc-role-wrap");
      wrap.appendChild(el("span", "rc-role-lbl", "Role:"));
      wrap.appendChild(roleSelect(p.role, "Role for " + p.name, function (id) { p.role = id; }));
      card.appendChild(wrap);
      var ap = el("button", "rc-approve", "Approve");
      ap.type = "button";
      ap.setAttribute("aria-label", "Approve " + p.name);
      ap.addEventListener("click", function () { approve(p.id); });
      card.appendChild(ap);
      var dn = el("button", "rc-deny", "Deny");
      dn.type = "button";
      dn.setAttribute("aria-label", "Deny " + p.name);
      dn.addEventListener("click", function () { deny(p.id); });
      card.appendChild(dn);
      host.appendChild(card);
    });
  }

  function wireRevoke(btn, d) {
    var armed = false, t = null;
    btn.addEventListener("click", function () {
      if (armed) { clearTimeout(t); removeDevice(d.id); return; }
      armed = true;
      btn.classList.add("armed");
      btn.textContent = "Confirm?";
      btn.setAttribute("aria-label", "Confirm revoke " + d.name);
      t = setTimeout(function () {
        armed = false;
        btn.classList.remove("armed");
        btn.textContent = "Revoke";
        btn.setAttribute("aria-label", "Revoke " + d.name);
      }, 4000);
    });
  }

  function renderRows() {
    var host = document.getElementById("rc-rows");
    host.innerHTML = "";
    if (!state.devices.length) {
      host.appendChild(el("div", "rc-empty", "No devices paired yet — scan the code on a phone to add one."));
      renderCount();
      return;
    }
    state.devices.forEach(function (d) {
      var row = el("div", "rc-row"); row.setAttribute("role", "row");
      var c1 = el("div", "rc-cell rc-c-device rc-devcell"); c1.setAttribute("role", "cell");
      c1.appendChild(el("div", "rc-dev-ico", "📱"));
      var info = el("div", "rc-devinfo");
      info.appendChild(el("div", "rc-devname", d.name));
      info.appendChild(el("div", "rc-devmeta", d.meta));
      c1.appendChild(info); row.appendChild(c1);

      var c2 = el("div", "rc-cell rc-c-role"); c2.setAttribute("role", "cell");
      c2.appendChild(roleSelect(d.role, "Role for " + d.name, function (id) {
        d.role = id; announce(d.name + " is now " + ROLE_BY[id].label);
      }));
      row.appendChild(c2);

      var c3 = el("div", "rc-cell rc-c-seen"); c3.setAttribute("role", "cell");
      c3.appendChild(el("span", "rc-seen", d.seen)); row.appendChild(c3);

      var c4 = el("div", "rc-cell rc-c-status"); c4.setAttribute("role", "cell");
      var st = STATUS[d.status] || STATUS.offline;
      var pill = el("span", "rc-status " + st.cls);
      pill.appendChild(el("span", "rc-status-dot"));
      pill.appendChild(document.createTextNode(st.label));
      c4.appendChild(pill); row.appendChild(c4);

      var c5 = el("div", "rc-cell rc-c-act"); c5.setAttribute("role", "cell");
      var rv = el("button", "rc-revoke", "Revoke");
      rv.type = "button"; rv.setAttribute("aria-label", "Revoke " + d.name);
      wireRevoke(rv, d); c5.appendChild(rv); row.appendChild(c5);

      host.appendChild(row);
    });
    renderCount();
  }

  function render() { renderPending(); renderRows(); }

  // ---------- actions (local model) ----------
  function approve(pendingId) {
    var i = state.pending.findIndex(function (p) { return p.id === pendingId; });
    if (i < 0) return;
    var p = state.pending[i];
    state.devices.push({ id: uid++, name: p.name, meta: p.platform + " · just paired", role: p.role, seen: "just now", status: "online" });
    state.pending.splice(i, 1);
    render();
    announce("Approved " + p.name + " as " + ROLE_BY[p.role].label);
  }
  function deny(pendingId) {
    var i = state.pending.findIndex(function (p) { return p.id === pendingId; });
    if (i < 0) return;
    var name = state.pending[i].name;
    state.pending.splice(i, 1);
    render();
    announce("Denied " + name);
  }
  function removeDevice(id) {
    var i = state.devices.findIndex(function (d) { return d.id === id; });
    if (i < 0) return;
    var name = state.devices[i].name;
    state.devices.splice(i, 1);
    render();
    announce("Revoked " + name);
  }

  // ---------- init ----------
  var nc = document.getElementById("rc-newcode");
  if (nc) nc.addEventListener("click", function () { genCode(); announce("New pairing code generated"); });
  genCode();
  render();
  if (!cdTimer) cdTimer = setInterval(tickCountdown, 1000);
})();
