// Remote Control surface (Design 2.0, Figma 359:124). Pair phones/tablets as controllers over the
// LAN, approve a pending pair request with a role, and manage paired devices (role · last seen ·
// status · revoke). Self-contained (the surface is registered in app.js's APP_SURFACES; nav +
// ⌘⇧R are handled there). Loaded after app.js.
//
// DATA: live Tauri commands to the host output window's pairing/session/RBAC service (86ajxer8n) —
// remote_snapshot / remote_approve / remote_deny / remote_revoke / remote_set_role / remote_new_code.
// A local model mirrors the host so mutations apply OPTIMISTICALLY (instant UI), then reconcile from
// the fresh snapshot the host returns; a bounded poll picks up new pair attempts. With no host
// connected (the stand-alone demo, or an older host) the surface simply shows no devices.
// Roles are the REAL selahcue-lan RBAC roles; a remotely-paired device is capped at Producer
// (Operator is refused by the host), so the assignable roles are Producer/Assistant/Viewer.
(function () {
  "use strict";
  var root = document.getElementById("surface-remote");
  if (!root) return;

  // Every role (for labels/colours) + the subset a remote device may be assigned (no Operator —
  // the host clamps it, so we never offer it).
  var ROLES = [
    { id: "operator", label: "Operator", cls: "rc-role-operator" },
    { id: "producer", label: "Producer", cls: "rc-role-producer" },
    { id: "assistant", label: "Assistant", cls: "rc-role-assistant" },
    { id: "viewer", label: "Viewer", cls: "rc-role-viewer" },
  ];
  var ROLE_BY = {};
  ROLES.forEach(function (r) { ROLE_BY[r.id] = r; });
  var ASSIGNABLE = ROLES.filter(function (r) { return r.id !== "operator"; });
  var DEFAULT_ROLE = "producer";
  var STATUS = {
    online: { label: "Online", cls: "rc-status-online" },
    idle: { label: "Idle", cls: "rc-status-idle" },
    offline: { label: "Offline", cls: "rc-status-offline" },
  };
  var CODE_TTL = 120000; // fallback if the host doesn't report an expiry

  // Tauri IPC (absent when opened outside the shell — the surface then stays empty).
  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  // --- local model (mirrors the host snapshot) ---
  var state = { code: null, pending: [], devices: [] };

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

  // Map the host's wire views onto the local rows/cards.
  function humanizeSeen(secs) {
    secs = secs || 0;
    if (secs < 5) return "just now";
    if (secs < 60) return secs + "s ago";
    if (secs < 3600) return Math.floor(secs / 60) + " min ago";
    return Math.floor(secs / 3600) + "h ago";
  }
  function statusFor(secs) {
    secs = secs || 0;
    if (secs < 30) return "online";
    if (secs < 300) return "idle";
    return "offline";
  }
  function mapDevice(d) {
    return {
      id: d.device_id,
      name: d.name || "(unnamed device)",
      meta: (d.platform || "controller") + (d.pinned ? " · pinned" : ""),
      role: d.role,
      seen: humanizeSeen(d.idle_secs),
      status: statusFor(d.idle_secs),
    };
  }
  function mapPending(p) {
    return {
      id: p.device_id,
      name: p.name || "(unnamed device)",
      platform: p.platform || "",
      role: DEFAULT_ROLE,
    };
  }
  // Replace the local model from a host snapshot, preserving the operator's in-progress role
  // choice for any request that is still pending.
  function applySnapshot(snap) {
    if (!snap) return;
    state.devices = (snap.devices || [])
      .filter(function (d) { return d.role !== "operator"; }) // hide operator consoles, not controllers
      .map(mapDevice);
    var prevRole = {};
    state.pending.forEach(function (p) { prevRole[p.id] = p.role; });
    state.pending = (snap.pending || []).map(function (p) {
      var m = mapPending(p);
      if (prevRole[m.id]) m.role = prevRole[m.id];
      return m;
    });
    render();
  }
  function loadSnapshot() {
    return invoke("remote_snapshot").then(applySnapshot).catch(function () {
      /* no host / demo mode — leave the (empty) model as-is */
    });
  }
  // After a mutation, pull the host's truth (also undoes an optimistic change the host rejected).
  function reconcile(err) {
    if (err) announce("Could not reach the host — " + err.message);
    loadSnapshot();
  }

  // Paint the REAL, scannable pairing QR the host minted. `qr` is `{ side, modules }` — a row-major
  // side×side grid of dark-module flags produced by the backend's tested encoder (the same one the
  // native output window uses) over the `selahcue://pair?host=…&port=…&pin=…&code=…` invite. A quiet
  // zone is added here. When the host supplies no invite (an older host, or one bound only to
  // loopback with no LAN), we say so rather than draw a fake code that a phone can't scan.
  function drawQR(qr) {
    var cv = document.getElementById("rc-qr");
    if (!cv || !cv.getContext) return;
    var ctx = cv.getContext("2d");
    var W = cv.width;
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, W, W);
    if (!qr || !qr.side || !qr.modules || qr.modules.length !== qr.side * qr.side) {
      ctx.fillStyle = "#6b7280";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.font = "13px system-ui, -apple-system, sans-serif";
      ctx.fillText("Scan the code shown on the", W / 2, W / 2 - 9);
      ctx.fillText("output window to pair a device", W / 2, W / 2 + 9);
      return;
    }
    var quiet = 4, n = qr.side + quiet * 2, m = W / n;
    ctx.fillStyle = "#0b0d12";
    for (var y = 0; y < qr.side; y++) {
      for (var x = 0; x < qr.side; x++) {
        if (!qr.modules[y * qr.side + x]) continue;
        var px = Math.floor((x + quiet) * m), py = Math.floor((y + quiet) * m);
        // Overshoot to the next module's edge so anti-aliasing leaves no white seams between cells.
        ctx.fillRect(px, py, Math.ceil((x + quiet + 1) * m) - px, Math.ceil((y + quiet + 1) * m) - py);
      }
    }
  }

  // Ask the host to mint a fresh single-use code + fingerprint.
  function genCode() {
    return invoke("remote_new_code")
      .then(function (r) {
        var code = (r && r.code) || "";
        var fp = (r && r.fingerprint) || code;
        var ttl = r && r.expires_in_secs ? r.expires_in_secs * 1000 : CODE_TTL;
        state.code = { code: code, fp: fp, uri: (r && r.uri) || null, expiresAt: Date.now() + ttl };
        drawQR(r && r.qr);
        var fpEl = document.getElementById("rc-fp");
        if (fpEl) {
          // Show a readable prefix; the full host cert fingerprint is on hover. (The automatic
          // TLS-pin check is the real protection; this human check is belt-and-suspenders.)
          fpEl.textContent = fp.length > 23 ? fp.slice(0, 23) + "…" : fp;
          fpEl.setAttribute("title",
            "Host TLS-certificate fingerprint — approve a device only if it shows this same value:\n" + fp);
        }
        tickCountdown();
        renderPending();
      })
      .catch(function (e) { announce("Could not generate a pairing code — " + e.message); });
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

  // ---------- role picker (assignable roles only) ----------
  function roleSelect(current, ariaLabel, onChange) {
    var sel = document.createElement("select");
    sel.className = "rc-role " + (ROLE_BY[current] ? ROLE_BY[current].cls : "");
    sel.setAttribute("aria-label", ariaLabel);
    // Show the current role even if it is not assignable (defensive), then the assignable options.
    var opts = ASSIGNABLE.slice();
    if (current && !opts.some(function (r) { return r.id === current; }) && ROLE_BY[current]) {
      opts = [ROLE_BY[current]].concat(opts);
    }
    opts.forEach(function (r) {
      var o = document.createElement("option");
      o.value = r.id; o.textContent = r.label;
      if (r.id === current) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener("change", function () {
      sel.className = "rc-role " + (ROLE_BY[sel.value] ? ROLE_BY[sel.value].cls : "");
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
        "wants to pair" + (p.platform ? " · " + p.platform : "") + " — approve only a device you recognize"));
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
        d.role = id; announce(d.name + " is now " + (ROLE_BY[id] ? ROLE_BY[id].label : id)); setRole(d.id, id);
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

  // ---------- actions (optimistic local update → persist to the host → reconcile) ----------
  function approve(pendingId) {
    var i = state.pending.findIndex(function (p) { return p.id === pendingId; });
    if (i < 0) return;
    var p = state.pending[i];
    state.devices.push({ id: p.id, name: p.name, meta: (p.platform || "controller") + " · just paired", role: p.role, seen: "just now", status: "online" });
    state.pending.splice(i, 1);
    render();
    announce("Approved " + p.name + " as " + (ROLE_BY[p.role] ? ROLE_BY[p.role].label : p.role));
    invoke("remote_approve", { deviceId: p.id, role: p.role }).then(applySnapshot).catch(reconcile);
  }
  function deny(pendingId) {
    var i = state.pending.findIndex(function (p) { return p.id === pendingId; });
    if (i < 0) return;
    var p = state.pending[i];
    state.pending.splice(i, 1);
    render();
    announce("Denied " + p.name);
    invoke("remote_deny", { deviceId: p.id }).then(applySnapshot).catch(reconcile);
  }
  function removeDevice(id) {
    var i = state.devices.findIndex(function (d) { return d.id === id; });
    if (i < 0) return;
    var name = state.devices[i].name;
    state.devices.splice(i, 1);
    render();
    announce("Revoked " + name);
    invoke("remote_revoke", { deviceId: id }).then(applySnapshot).catch(reconcile);
  }
  function setRole(id, role) {
    invoke("remote_set_role", { deviceId: id, role: role }).then(applySnapshot).catch(reconcile);
  }

  // ---------- init ----------
  var nc = document.getElementById("rc-newcode");
  if (nc) nc.addEventListener("click", function () { genCode().then(function () { announce("New pairing code generated"); }); });
  genCode();
  loadSnapshot();
  render();
  if (!cdTimer) cdTimer = setInterval(tickCountdown, 1000);
  // Poll for new pair attempts (bounded single interval).
  setInterval(loadSnapshot, 3000);
})();
