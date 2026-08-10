      const invoke = window.__TAURI__.core.invoke;
      let editing = null;       // item id with an open inline editor
      let confirmDelete = null; // item id in the two-click delete confirm state
      let lastRendered = "";    // skip DOM rebuilds when nothing changed
      let resetInFlight = false; // guards Timer Reset against a double-fire (the 1s poll re-enables the button)

      function render(view) {
        // Chrome (emergency footer, LIVE chip, timer, blackout) syncs on EVERY
        // view — the blackout toggle must read true state even while an editor
        // is open.
        syncChrome(view);
        // Live Console slide picker (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec): reflect the staged
        // presentation in the Slides tab + filmstrip. Runs before the plan early-returns (like the
        // chrome sync) so the picker stays live even with an open plan/theme editor.
        if (window.__syncSlides) window.__syncSlides(view);
        // The saved-theme library (86ajq4xmy) rides on every view. Refresh the Theme
        // Designer's template list whenever it changes — but never while the save-name
        // field is focused (a mid-type rebuild would clobber the entry), and only after
        // the built-ins have loaded (tdList needs them). This runs before the plan's
        // early-returns so the library stays live even with an open plan editor.
        syncSavedThemes(view);
        // Live transcript (R3) + scripture detection queue (R4). Run before the plan
        // early-returns (like the saved-theme sync) so they stay live with an open plan
        // editor; each gates on its own change-key so the 1s poll neither thrashes the
        // DOM nor eats an in-flight Stage/Dismiss click.
        syncTranscript(view);
        syncDetections(view);
        // Never clobber an open editor or a pending delete-confirm, and skip
        // identical re-renders (the 1s poll must not eat in-flight clicks).
        // The key is scoped to EXACTLY the fields the plan build below reads:
        // plan_name (39), items (incl. per-item is_live/is_staged/theme/slide, 44+),
        // themes + saved_themes (the per-row picker options, 132/139). `view.timer`
        // is deliberately EXCLUDED — like the console-render sig (below) — so a running
        // countdown (which advances the timer every second) does NOT tear down and
        // rebuild the whole plan list every poll; transcript/detections likewise have
        // their own change-keyed syncs above (audit M1).
        const key = JSON.stringify([
          view.plan_name,
          view.items,
          view.themes,
          view.saved_themes,
        ]);
        if (editing !== null || confirmDelete !== null) return;
        // Never yank an OPEN per-item theme picker out from under the operator: the 1s
        // poll would otherwise rebuild the plan (a running timer changes the view every
        // second) and tear out the focused <select> before a choice is made. Defer the
        // plan rebuild while it holds focus; it renders when focus leaves (chrome above
        // already synced, so emergency/timer state stays live).
        if (
          document.activeElement &&
          document.activeElement.classList.contains("item-theme")
        )
          return;
        if (key === lastRendered) return;
        lastRendered = key;
        document.getElementById("plan-name").textContent = view.plan_name;
        document.getElementById("plan-sub").textContent = view.items.length + " items";

        const plan = document.getElementById("plan");
        plan.innerHTML = "";
        view.items.forEach((it, i) => {
          const row = document.createElement("div");
          row.className =
            "item" + (it.is_live ? " is-live" : "") + (it.is_staged ? " is-staged" : "");
          row.dataset.itemId = it.id; // anchor for post-link-commit focus restore (WCAG 2.4.3)
          row.onclick = () => act(() => invoke("select", { itemId: it.id }));

          const main = document.createElement("span");
          main.className = "main";
          const title = document.createElement("span");
          title.className = "title";
          title.textContent = it.title;
          const kind = document.createElement("span");
          // Colour-coded kind badge (Design 2.0): kind-song/scripture/announcement/section.
          kind.className = "kind kind-" + it.kind;
          // Truthful slide bookkeeping (S8-1): "song · 2/6" for multi-slide
          // items (position shows for the staged/live item).
          kind.textContent =
            it.kind +
            (it.slide_count
              ? " · " +
                (it.slide_index != null ? (it.slide_index + 1) + "/" : "") +
                it.slide_count
              : "");
          main.appendChild(title);
          main.appendChild(kind);
          // Linked content (ADR-0020): the scripture passage / deck / media this item
          // shows. Undefined-safe — an unlinked item (no `link`) renders no chip, exactly
          // as before. A deck whose library entry is gone renders a "missing" chip (FR-007).
          if (it.link) main.appendChild(planLinkChip(it.link));

          const tools = document.createElement("span");
          tools.className = "tools";

          // In-page editing only: WKWebView implements neither prompt() nor
          // confirm(), so native dialogs are silently dead in the shell.
          const ren = miniBtn("✏", (e) => {
            e.stopPropagation();
            editing = it.id;
            const input = document.createElement("input");
            input.value = it.title;
            input.style.cssText = "width:100%;font:inherit;font-size:13px;color:var(--text);background:var(--bg);border:1px solid var(--accent);border-radius:4px;padding:4px 6px";
            input.onclick = (ev) => ev.stopPropagation();
            input.onkeydown = (ev) => {
              if (ev.key === "Enter") {
                const t = input.value.trim();
                editing = null;
                if (t && t !== it.title) act(() => invoke("rename_item", { itemId: it.id, title: t }));
                else act(() => invoke("view"));
              } else if (ev.key === "Escape") {
                editing = null;
                act(() => invoke("view"));
              }
            };
            input.onblur = () => { if (editing === it.id) { editing = null; act(() => invoke("view")); } };
            title.replaceWith(input);
            input.focus();
            input.select();
          });
          const up = miniBtn("↑", (e) => {
            e.stopPropagation();
            if (i > 0) act(() => invoke("move_item", { itemId: it.id, to: i - 1 }));
          });
          const down = miniBtn("↓", (e) => {
            e.stopPropagation();
            act(() => invoke("move_item", { itemId: it.id, to: i + 1 }));
          });
          const del = miniBtn("✕", (e) => {
            e.stopPropagation();
            if (confirmDelete === it.id) {
              confirmDelete = null;
              act(() => invoke("remove_item", { itemId: it.id }));
            } else {
              confirmDelete = it.id;
              // An armed destructive control must never be invisible: pin the
              // tools open for the confirm window even if the pointer leaves.
              tools.classList.add("confirming");
              del.textContent = "sure?";
              del.style.color = "var(--live-ink)";
              setTimeout(() => { if (confirmDelete === it.id) { confirmDelete = null; act(() => invoke("view")); } }, 3000);
            }
          });

          row.appendChild(main);
          tools.appendChild(ren);
          tools.appendChild(up);
          tools.appendChild(down);
          // Link content (ADR-0020): scripture items link a passage; slide-group items link
          // a deck. Opens a picker that sets the reference/deck via `set_item_content` — a
          // plan edit that never touches Live (staging happens in Preview on select).
          if (it.kind === "scripture" || it.kind === "slide_group") {
            const lnk = miniBtn(it.link ? "🔗" : "＋🔗", (e) => {
              e.stopPropagation();
              openLinkModal(it);
            });
            lnk.title = it.link ? "Change linked content" : "Link a scripture or presentation";
            lnk.setAttribute("aria-label", lnk.title);
            lnk.classList.add("plan-link-btn"); // focus target after a link commit rebuilds the row
            tools.appendChild(lnk);
          }
          tools.appendChild(del);
          row.appendChild(tools);
          if (it.is_live) row.appendChild(badge("live", "LIVE"));
          else if (it.is_staged) row.appendChild(badge("preview", "PREVIEW"));
          plan.appendChild(row);
        });

      }

      function setPanel(which, item, capText, idleText) {
        const surface = document.querySelector("#" + which + "-panel .surface");
        const title = document.getElementById(which + "-title");
        const cap = document.getElementById(which + "-cap");
        if (item) {
          surface.classList.remove("idle");
          title.textContent = item.title;
          cap.textContent = item.kind + " · " + capText;
        } else {
          surface.classList.add("idle");
          title.textContent = idleText;
          cap.textContent = "";
        }
      }

      // Reflect the Stage sub-tab state (active template + live production message) from the
      // host view — stage-output-only; the host is authoritative.
      function syncStage(view) {
        const tpl = view.stage_template || "worship";
        document.querySelectorAll("#stage-themes .stage-theme").forEach((b) => {
          const on = b.dataset.template === tpl;
          b.classList.toggle("active", on);
          b.setAttribute("aria-checked", on ? "true" : "false");
        });
        const msg = view.stage_message || "";
        const active = document.getElementById("stage-msg-active");
        if (active) {
          active.hidden = !msg;
          active.textContent = msg ? "● On stage: " + msg : "";
        }
        document.querySelectorAll("#stage-presets .stage-preset").forEach((b) => {
          b.classList.toggle("active", !!msg && b.dataset.msg === msg);
        });
      }

      function syncChrome(view) {
        // Top-bar LIVE chip: on air only when something is actually live.
        document.getElementById("live-chip").classList.toggle("on", view.live_index != null);
        syncStage(view);

        // The HOST's translation list wins: a newer shell against an older host
        // must not offer codes the host will deny (silent stage/search no-ops).
        if (view.translations && view.translations.length) {
          renderTranslations(view.translations);
        }

        // Preview / Live panels (Figma console): the on-air truth must never go
        // stale — an emergency clear/Go-Live can land while an inline editor or
        // delete-confirm is open, so the panels sync on EVERY view (they touch
        // only static DOM, never the guarded plan rows).
        const itemAt = (i) => (i == null ? null : view.items[i] || null);
        const scriptureAs = (ref) => (ref ? { title: ref, kind: "scripture" } : null);
        const freeAs = (t) => (t ? { title: t, kind: "slide" } : null);
        setPanel(
          "preview",
          itemAt(view.staged_index) || scriptureAs(view.staged_scripture),
          "staged",
          "Nothing staged"
        );
        // A deck slide presented via the authored-slide path (the Live Console slide picker's Go
        // Live) sets live_authored_id and clears live_index — reflect it on the Live panel (the real
        // slide is on the canvas), titled by the staged presentation, so it isn't shown as idle.
        const authoredLive = view.live_authored_id != null;
        const presLive = () => {
          const s = itemAt(view.staged_index);
          return {
            title: s && s.kind === "slide_group" ? s.title : "Presentation",
            kind: "slide_group",
          };
        };
        setPanel(
          "live",
          itemAt(view.live_index) ||
            scriptureAs(view.live_scripture) ||
            freeAs(view.live_free_text) ||
            (authoredLive ? presLive() : null),
          "main output",
          "Output idle"
        );

        const t = view.timer;
        const big = document.getElementById("timer-big");
        // Colour via classes (Design 2.0): .warn = amber, .up = live-red (no inline style).
        big.classList.remove("up", "warn");
        let bigText = "–:––";
        if (!t) {
          // no timer
        } else if (t.time_up) {
          bigText = "TIME UP";
          big.classList.add("up");
        } else {
          const secs = t.remaining_secs != null ? t.remaining_secs : t.elapsed_secs;
          bigText = fmtClock(secs);
          if (t.warn) big.classList.add("warn");
        }
        big.textContent = bigText;
        // Topbar timer chip mirrors the readout (hidden when no timer is active).
        const topTimer = document.getElementById("top-timer");
        const topTimerVal = document.getElementById("top-timer-val");
        if (topTimer && topTimerVal) {
          topTimer.hidden = !t;
          topTimerVal.textContent = bigText;
        }
        // RUNNING / PAUSED / TIME UP status pill on the timer card header.
        const state = document.getElementById("timer-state");
        const stateLabel = document.getElementById("timer-state-label");
        if (state && stateLabel) {
          state.hidden = !t;
          if (t) {
            const isPaused = !!t.paused;
            state.classList.toggle("paused", isPaused || t.time_up);
            stateLabel.textContent = t.time_up ? "TIME UP" : isPaused ? "PAUSED" : "RUNNING";
          }
        }

        renderOutputs(view);

        // The live-adjust + pause/reset buttons act on an active timer only.
        const hasTimer = !!view.timer;
        const isPaused = hasTimer && !!view.timer.paused;
        document.getElementById("timer-plus").disabled = !hasTimer;
        document.getElementById("timer-minus").disabled = !hasTimer;
        const pauseBtn = document.getElementById("timer-pause");
        const resetBtn = document.getElementById("timer-reset");
        if (pauseBtn) {
          pauseBtn.disabled = !hasTimer;
          pauseBtn.textContent = isPaused ? "Resume" : "Pause";
          pauseBtn.setAttribute(
            "aria-label",
            isPaused ? "Resume the paused timer" : "Pause the running timer"
          );
        }
        if (resetBtn) resetBtn.disabled = !hasTimer || resetInFlight;

        // Non-colour blackout state on BOTH triggers (footer #blackout + the global topbar
        // #top-blackout): label + aria-pressed + the live-panel overlay, not just red fill.
        ["blackout", "top-blackout"].forEach((id) => {
          const el = document.getElementById(id);
          if (!el) return;
          el.classList.toggle("on", view.blackout);
          el.dataset.on = view.blackout ? "1" : "0";
          el.setAttribute("aria-pressed", view.blackout ? "true" : "false");
        });
        document.getElementById("blackout-state").textContent = view.blackout ? "ON" : "";
        document.getElementById("live-panel").classList.toggle("blackout", view.blackout);

        // Draw the TRUE composited Preview/Live output (86ajtwq28) — a debounced, read-only
        // host readback (rendering never changes what is on air). Only re-render when a
        // render-affecting field changed (the 1 s poll must not re-fetch an identical frame);
        // switching TO the console always renders (showSurface), so this dedup is safe.
        // `items` is included so a WITHIN-item change that keeps the same live/staged index —
        // advancing a slide in a multi-slide song (slide_index) or a per-item theme override —
        // still refreshes the panels; the scriptures/free-text/blackout/theme/screens cover
        // the non-plan output states. `view.timer` is deliberately EXCLUDED: the countdown is
        // a speaker aid composited onto the stage/confidence monitor only, NOT the audience
        // preview/live output (controller.rs `tick`), so a running timer must not force an
        // identical re-render every second on the console.
        const sig = JSON.stringify([
          view.items, view.staged_index, view.staged_scripture, view.live_index,
          view.live_scripture, view.live_free_text, view.blackout, view.theme,
          view.screen_themes,
        ]);
        if (sig !== lastConsoleSig) {
          lastConsoleSig = sig;
          scheduleConsoleRender();
          scheduleScreenPreviews(); // the live content / theme changed → refresh per-screen previews too (86ajq321k)
        }
      }

      // --- Preview/Live TRUE render (86ajtwq28): the real composited pixels the audience
      // preview + live show, drawn to a <canvas> per console panel. The title/caption text
      // stays as the accessible label AND the fallback when no frame is available (a Remote
      // host has no local pixels; an older host lacks the command). Read-only readback. ---
      let consoleRenderTimer = null;
      let lastConsoleSig = null; // last render-affecting view signature (poll dedup)
      function scheduleConsoleRender() {
        clearTimeout(consoleRenderTimer);
        consoleRenderTimer = setTimeout(renderConsole, 120);
      }
      function setConsoleRender(on) {
        const p = document.querySelector("#preview-panel .surface");
        const l = document.querySelector("#live-panel .surface");
        if (p) p.classList.toggle("has-render", on);
        if (l) l.classList.toggle("has-render", on);
      }
      // Decode base64 RGBA into a preallocated typed array with a TIGHT indexed loop
      // (audit M5). `Uint8Array.from(atob(s), c => c.charCodeAt(0))` invokes a JS closure
      // PER BYTE — V8's slow path — for ~0.9MB frames on the main thread; a plain indexed
      // loop is JIT-friendly and byte-identical. `atob` throws on malformed input (callers
      // guard with try/catch).
      function b64ToBytes(b64) {
        const bin = atob(b64);
        const n = bin.length;
        const bytes = new Uint8Array(n);
        for (let i = 0; i < n; i++) bytes[i] = bin.charCodeAt(i);
        return bytes;
      }
      // Blit a base64 RGBA `frame` ({w,h,rgba}) into a canvas ELEMENT (shared by the console
      // panels and the per-screen previews, 86ajq321k). Returns whether it drew.
      function blitFrame(cv, frame) {
        if (!cv || !frame || !frame.rgba || !frame.w || !frame.h) return false;
        let bytes;
        try {
          bytes = b64ToBytes(frame.rgba);
        } catch (e) {
          return false;
        }
        if (bytes.length !== frame.w * frame.h * 4) return false; // guard a malformed payload
        try {
          cv.width = frame.w;
          cv.height = frame.h;
          cv.getContext("2d").putImageData(
            new ImageData(new Uint8ClampedArray(bytes), frame.w, frame.h),
            0,
            0
          );
        } catch (e) {
          return false;
        }
        return true;
      }
      function drawConsoleFrame(canvasId, frame) {
        if (!frame || !frame.rgba || !frame.w || !frame.h) {
          console.warn("[SelahCue] drawConsoleFrame bad frame", canvasId, frame && { w: frame.w, h: frame.h, hasRgba: !!frame.rgba });
          return false;
        }
        return blitFrame(document.getElementById(canvasId), frame);
      }

      // --- Per-screen PREVIEW (86ajq321k): each Audience screen (main/lower-third/stream)
      // renders its OWN theme from the same live content; the secondaries have no physical
      // output yet, so this small canvas is the only way to SEE each screen's design. A read
      // (render_screen), debounced + gated on the Screens surface being active (like the
      // console render), so it never fetches while another surface is up or per-poll spuriously. ---
      let screenPreviewTimer = null;
      function scheduleScreenPreviews() {
        clearTimeout(screenPreviewTimer);
        screenPreviewTimer = setTimeout(renderScreenPreviews, 120);
      }
      async function renderScreenPreviews() {
        const surf = document.getElementById("surface-screens");
        if (!surf || !surf.classList.contains("active")) return; // skip while another surface is up
        const canvases = Array.from(
          document.querySelectorAll("#screens-list canvas.screen-preview")
        );
        for (const cv of canvases) {
          let res;
          try {
            res = await invoke("render_screen", { screen: cv.dataset.screen, maxW: 192, maxH: 108 });
          } catch (e) {
            continue; // a Remote/older host without the command → leave the placeholder
          }
          if (res && res.available && res.frame) {
            blitFrame(cv, res.frame);
            cv.classList.add("has-render");
            // Overlay the safe-area guides on the OPERATOR preview only (Design 2.0) — the
            // audience output never carries them.
            if (cv.dataset.safeArea === "1") drawSafeAreaGuides(cv);
          }
        }
      }
      // Draw broadcast-style safe-area guides onto a preview canvas: an action-safe rectangle
      // (~3.5% inset) and a dashed title-safe rectangle (~5% inset), in the preview accent so
      // the operator can frame content. Preview-only — never touches the audience output.
      function drawSafeAreaGuides(cv) {
        const ctx = cv.getContext && cv.getContext("2d");
        if (!ctx) return;
        const w = cv.width, h = cv.height;
        if (!w || !h) return;
        const inset = (frac, dash) => {
          const x = Math.round(w * frac), y = Math.round(h * frac);
          ctx.setLineDash(dash ? [Math.max(2, Math.round(w / 48)), Math.max(2, Math.round(w / 96))] : []);
          ctx.strokeRect(x + 0.5, y + 0.5, w - 2 * x - 1, h - 2 * y - 1);
        };
        ctx.save();
        ctx.lineWidth = Math.max(1, Math.round(w / 240));
        ctx.strokeStyle = "rgba(53,192,138,0.9)"; // --sc-preview
        inset(0.035, false); // action-safe
        inset(0.05, true);   // title-safe (dashed)
        ctx.restore();
      }
      // Surface a render-console DIAGNOSTIC into the panels (visible in a screenshot) + the
      // devtools console, so a real-app render failure can be pinpointed without the GUI here.
      function renderDiag(msg) {
        console.warn("[SelahCue] render_console:", msg);
        const pt = document.getElementById("preview-title");
        const lt = document.getElementById("live-title");
        if (pt) pt.textContent = "⚠ " + msg;
        if (lt) lt.textContent = "⚠ " + msg;
      }
      async function renderConsole() {
        // Only when the Live Console surface is visible — skip the host round-trip + payload
        // while another surface (Theme Designer, Settings, …) is up.
        const surf = document.getElementById("surface-console");
        if (!surf || !surf.classList.contains("active")) return;
        const box = document.getElementById("preview-panel");
        const dpr = window.devicePixelRatio || 1;
        const base = box && box.clientWidth ? box.clientWidth : 480;
        const w = Math.max(160, Math.min(640, Math.round(base * dpr)));
        const h = Math.round((w * 9) / 16);
        let res;
        try {
          res = await invoke("render_console", { maxW: w, maxH: h });
        } catch (e) {
          setConsoleRender(false);
          renderDiag("command error: " + (e && e.message ? e.message : String(e)));
          return;
        }
        try {
          console.log("[SelahCue] render_console ->", JSON.stringify({
            available: res && res.available,
            pv: res && res.preview && { w: res.preview.w, h: res.preview.h, len: (res.preview.rgba || "").length },
            lv: res && res.live && { w: res.live.w, h: res.live.h, len: (res.live.rgba || "").length },
          }));
        } catch (e2) { /* logging only */ }
        if (!res || !res.available) {
          setConsoleRender(false);
          renderDiag("available=false (remote host / no local pixels)");
          return;
        }
        // When a deck slide is staged, the filmstrip owns the Preview panel (real deck pixels), so
        // skip the host's title composite here — otherwise it would overwrite the slide every cycle.
        const okP = window.__consoleDeckPreview
          ? true
          : drawConsoleFrame("preview-canvas", res.preview);
        const okL = drawConsoleFrame("live-canvas", res.live);
        setConsoleRender(okP || okL);
        if (!(okP || okL)) {
          renderDiag(
            "decode failed pv=" +
              JSON.stringify(res.preview && { w: res.preview.w, h: res.preview.h, len: (res.preview.rgba || "").length })
          );
        }
      }

      // OUTPUTS surface (Design 2.0, Figma 327:124): a card grid + a fixed inspector for the
      // selected output. Role → display, per-output config, honest telemetry.
      let outputsKey = "";
      let outputsPending = null; // deferred view while a picker has focus
      let selectedScreen = null; // the output shown in the inspector (defaults to the first)
      let lastOutputsView = null; // stashed so a card-select can re-render the inspector alone

      // Display name for a screen id/role (built-in or a virtual "Stream 2" feed).
      function screenDisplayName(s) {
        if (s.screen === "main") return "Audience — Main";
        if (s.screen === "stage") return "Stage Display";
        if (s.screen === "lower-third") return "Lower Third";
        if (s.screen === "stream") return "Livestream Program";
        const base = s.role === "lower-third" ? "Lower Third" : s.role === "stream" ? "Stream" : s.role;
        const m = /-(\d+)$/.exec(s.screen);
        return m ? base + " " + m[1] : base;
      }
      // Short role-badge label (Design 2.0 §ROLE BADGE).
      function roleBadgeText(role) {
        return role === "main" ? "MAIN" : role === "stage" ? "STAGE"
          : role === "lower-third" ? "L3 · ALPHA" : "STREAM";
      }
      // Normalize a ScreenView.config (omitted → identity default) into a full object.
      function cfgOf(s) {
        const c = (s && s.config) || {};
        const L = c.layers || {};
        return {
          orientation: c.orientation || 0,
          scale_fit: c.scale_fit || "fill",
          mirror: !!c.mirror,
          delay_ms: c.delay_ms || 0,
          frame_rate: c.frame_rate || 60,
          safe_area_guides: !!c.safe_area_guides,
          layers: {
            background: L.background !== false,
            text: L.text !== false,
            lower_third: L.lower_third !== false,
            logo: L.logo !== false,
            timer: L.timer !== false,
          },
          ndi_enabled: !!c.ndi_enabled,
          ndi_name: c.ndi_name || "",
        };
      }

      function renderOutputs(view) {
        const outs = view.outputs || [];
        const displays = view.displays || [];
        const themes = view.themes || [];
        const activeTheme = view.theme || "";
        // Per-screen theme map (86ajq321k): screen id → its assigned theme name. A screen
        // absent from the map follows the global; the picker shows that as its selection.
        const screenThemes = {};
        (view.screen_themes || []).forEach((st) => { screenThemes[st.screen] = st.theme; });
        // The SCREEN REGISTRY (Screens page — dynamic registry): the authoritative managed
        // screen list with role/enabled/deletable. An older host that doesn't send it falls
        // back to the four built-ins (all enabled, none deletable) so the page still works.
        // Only the two physical outputs are default (Audience `main` + Stage `stage`); secondary
        // audience feeds (lower-third / stream) are added on demand via "+ Add virtual output".
        const registry = (view.screens && view.screens.length) ? view.screens : [
          { screen: "main", role: "main", enabled: true, deletable: false },
          { screen: "stage", role: "stage", enabled: true, deletable: false },
        ];
        lastOutputsView = view;
        // The selected output must always name a real screen (default the first).
        if (!registry.some((s) => s.screen === selectedScreen)) {
          selectedScreen = registry[0] ? registry[0].screen : null;
        }
        const key = JSON.stringify([outs, displays, themes, activeTheme, view.screen_themes || [], view.saved_themes || [], registry, selectedScreen]);
        if (key === outputsKey) return; // pickers are interactive: rebuild only on change
        const list = document.getElementById("screens-list");
        // Never yank an OPEN PICKER out from under the operator: a focused <select>
        // survives, and the fresh data renders when focus leaves it. A toggle/button
        // click is a completed action, so it does NOT defer — the row updates at once.
        const ae = document.activeElement;
        if (ae && (list.contains(ae) || (document.getElementById("screens-inspector") || {}).contains && document.getElementById("screens-inspector").contains(ae)) && ae.tagName === "SELECT") {
          outputsPending = view;
          return;
        }
        outputsPending = null;
        outputsKey = key;

        // The topbar Identify targets every physical display; disabled with no outputs.
        document.getElementById("screens-identify").disabled = outs.length === 0;
        // Cap the number of outputs at MAX_OUTPUTS (mirrors selahcue-app MAX_SCREENS — the
        // host enforces it server-side; this disables the "+ Add virtual output" affordance
        // + its role picker at the cap so the operator sees the limit rather than a silently
        // refused click).
        const MAX_OUTPUTS = 8;
        const atCap = registry.length >= MAX_OUTPUTS;
        const addBtn = document.getElementById("screen-add-btn");
        const addRole = document.getElementById("screen-add-role");
        if (addBtn) {
          addBtn.disabled = atCap;
          addBtn.title = atCap ? ("Maximum of " + MAX_OUTPUTS + " outputs reached") : "";
          addBtn.setAttribute(
            "aria-label",
            atCap ? ("Add virtual output — maximum of " + MAX_OUTPUTS + " outputs reached") : "Add a virtual output"
          );
        }
        if (addRole) addRole.disabled = atCap;
        // The "N connected" pill: physical outputs bound to a display (honest — a virtual
        // feed composes + previews but has no physical connection yet).
        const conn = document.getElementById("screens-conn");
        if (conn) {
          const n = outs.filter((o) => o.assigned).length;
          conn.textContent = "● " + n + " connected";
        }

        // Physical output (display assignment + format + telemetry) is keyed by role.
        const outByRole = {};
        outs.forEach((o) => { outByRole[o.role] = o; });

        // Preserve KEYBOARD focus across the destructive innerHTML rebuild (a11y): a toggle
        // or button (unlike a <select>, handled above) is destroyed by the rebuild, dropping
        // focus to <body>. Remember which control was focused so we can re-focus its
        // equivalent after the rows are rebuilt.
        const focused = document.activeElement;
        let refocusSel = null;
        if (focused && list.contains(focused)) {
          const fr = focused.closest(".screen-row");
          const fsid = fr && fr.dataset.screen;
          if (fsid && focused.classList.contains("screen-enable-toggle")) {
            refocusSel = '.screen-row[data-screen="' + fsid + '"] .screen-enable-toggle';
          } else if (fsid && focused.classList.contains("screen-delete")) {
            refocusSel = '.screen-row[data-screen="' + fsid + '"] .screen-delete';
          }
        }

        // --- OUTPUT CARDS (Design 2.0): each is a .screen-row[data-screen] carrying the
        // pinned hooks (preview canvas for audience, enable toggle, delete-on-virtual). ---
        list.innerHTML = "";
        registry.forEach((s) => {
          const isStage = s.role === "stage";
          const audience = !isStage; // main / lower-third / stream are Audience-class
          const o = outByRole[s.role]; // the physical output for main/stage (if any)
          const card = document.createElement("div");
          card.className = "screen-row scr-card" + (s.enabled ? "" : " screen-disabled")
            + (s.screen === selectedScreen ? " scr-card-selected" : "");
          card.dataset.screen = s.screen;

          // (1) Preview thumbnail — a live canvas for Audience screens (86ajq321k); the Stage
          // card shows its Current/Next/Timer chips (no preview canvas → the pinned "exactly
          // 3 audience previews" count holds).
          const thumb = document.createElement("div"); thumb.className = "scr-thumb";
          if (audience) {
            const cv = document.createElement("canvas");
            cv.className = "screen-preview"; cv.dataset.screen = s.screen;
            // Safe-area guides are an OPERATOR-preview overlay only (never the audience output)
            // — flag the canvas so renderScreenPreviews draws the guides after blitting.
            cv.dataset.safeArea = cfgOf(s).safe_area_guides ? "1" : "";
            cv.setAttribute("aria-label", "Live preview of the " + s.screen + " screen's themed output");
            thumb.appendChild(cv);
          } else {
            const chips = document.createElement("div"); chips.className = "stage-chips";
            ["Current", "Next", "Timer"].forEach((l) => {
              const c = document.createElement("span"); c.className = "stage-chip on"; c.textContent = l;
              chips.appendChild(c);
            });
            thumb.appendChild(chips);
          }
          card.appendChild(thumb);

          // (2) Name + role badge  /  status pill + enable toggle
          const nameRow = document.createElement("div"); nameRow.className = "scr-card-namerow";
          const nameGroup = document.createElement("div"); nameGroup.className = "scr-card-namegroup";
          const nm = document.createElement("strong"); nm.className = "scr-card-name";
          nm.textContent = screenDisplayName(s);
          const rb = document.createElement("span");
          rb.className = "scr-role-badge scr-role-" + s.role;
          rb.textContent = roleBadgeText(s.role);
          nameGroup.appendChild(nm); nameGroup.appendChild(rb);
          const rightGroup = document.createElement("div"); rightGroup.className = "scr-card-right";
          rightGroup.appendChild(statusPillFor(s, o));
          // The Enable toggle (pinned .screen-enable-toggle) — a D2 switch in the card head.
          const toggle = document.createElement("label"); toggle.className = "scr-toggle scr-card-enable";
          const cb = document.createElement("input");
          cb.type = "checkbox"; cb.checked = s.enabled;
          cb.className = "screen-enable-toggle"; cb.dataset.screen = s.screen;
          cb.setAttribute("aria-label", (s.enabled ? "Disable" : "Enable") + " the " + screenDisplayName(s) + " output");
          cb.onchange = () => {
            // Revert the optimistic native flip to the authoritative value BEFORE the round
            // trip: a SUCCESS re-renders with the new state; a REJECTED call (RBAC / older
            // host) leaves the switch showing the true, unchanged state — never a lie.
            const want = cb.checked;
            cb.checked = s.enabled;
            act(() => invoke("set_screen_enabled", { screen: s.screen, enabled: want }));
          };
          const knob = document.createElement("span"); knob.className = "scr-toggle-knob";
          toggle.appendChild(cb); toggle.appendChild(knob);
          rightGroup.appendChild(toggle);
          nameRow.appendChild(nameGroup); nameRow.appendChild(rightGroup);
          card.appendChild(nameRow);

          // (3) Meta line  /  Identify · Configure (· Delete for a virtual output)
          const metaRow = document.createElement("div"); metaRow.className = "scr-card-metarow";
          const meta = document.createElement("span"); meta.className = "scr-card-meta";
          meta.textContent = metaLine(s, o, cfgOf(s));
          const actions = document.createElement("div"); actions.className = "scr-card-actions";
          const idBtn = document.createElement("button");
          idBtn.type = "button"; idBtn.className = "btn-secondary scr-card-btn";
          idBtn.textContent = "Identify";
          idBtn.disabled = outs.length === 0;
          idBtn.setAttribute("aria-label", "Identify " + screenDisplayName(s));
          idBtn.onclick = () => act(() => invoke("identify_outputs"));
          const cfgBtn = document.createElement("button");
          cfgBtn.type = "button"; cfgBtn.className = "btn-secondary scr-card-btn";
          cfgBtn.textContent = "Configure";
          cfgBtn.setAttribute("aria-label", "Configure " + screenDisplayName(s) + " in the inspector");
          cfgBtn.onclick = () => selectScreen(s.screen);
          actions.appendChild(idBtn); actions.appendChild(cfgBtn);
          if (s.deletable) {
            const del = document.createElement("button");
            del.type = "button"; del.className = "screen-delete scr-card-btn"; del.dataset.screen = s.screen;
            del.textContent = "Delete";
            del.setAttribute("aria-label", "Delete the " + screenDisplayName(s) + " output");
            del.onclick = () => act(() => invoke("remove_screen", { screen: s.screen }));
            actions.appendChild(del);
          }
          metaRow.appendChild(meta); metaRow.appendChild(actions);
          card.appendChild(metaRow);

          // Clicking a card body (not a control) selects it into the inspector.
          card.addEventListener("click", (e) => {
            if (e.target.closest("button, input, select, label")) return;
            selectScreen(s.screen);
          });
          list.appendChild(card);
        });

        // Restore keyboard focus to the rebuilt equivalent control (a11y).
        if (refocusSel) {
          const rf = list.querySelector(refocusSel);
          if (rf) rf.focus();
        }
        renderInspector(view, registry, outByRole, screenThemes, themes);
        scheduleScreenPreviews(); // fill each Audience screen's preview canvas (86ajq321k)
      }

      // The status pill for a card (Design 2.0 §STATUS PILL): honest — LIVE only when the
      // physical output is presenting; CONNECTED when assigned; READY for a composed virtual
      // feed; NO SIGNAL when a physical role has no display.
      function statusPillFor(s, o) {
        const pill = document.createElement("span"); pill.className = "scr-pill";
        let variant = "ready", label = "READY";
        if (s.role === "main" || s.role === "stage") {
          if (o && o.assigned && o.signal === "healthy") { variant = "live"; label = "LIVE"; }
          else if (o && o.assigned) { variant = "connected"; label = "CONNECTED"; }
          else if (o && o.signal === "degraded") { variant = "warning"; label = "DEGRADED"; }
          else { variant = "warning"; label = "NO SIGNAL"; }
        } else {
          // A virtual audience feed composes + previews; if it broadcasts NDI, surface that.
          const cfg = cfgOf(s);
          if (s.enabled && cfg.ndi_enabled) {
            variant = "connected"; label = "NDI";
          } else {
            variant = s.enabled ? "connected" : "ready";
            label = s.enabled ? "COMPOSED" : "MUTED";
          }
        }
        pill.classList.add("scr-pill-" + variant);
        pill.textContent = "● " + label;
        return pill;
      }

      // The card meta line: resolution · fps · orientation (honest — only what the host
      // reports). A virtual feed shows its composed nature.
      function metaLine(s, o, cfg) {
        const parts = [];
        if (o && o.width) parts.push(o.width + "×" + o.height);
        if (o && typeof o.fps === "number") parts.push(o.fps + "fps");
        else if (o) parts.push(cfg.frame_rate + "fps target");
        parts.push(cfg.orientation % 2 === 0 ? "Landscape" : "Portrait");
        if (!o && s.role !== "stage") return "Composed feed · " + (cfg.orientation % 2 === 0 ? "Landscape" : "Portrait");
        return parts.join(" · ");
      }

      // Move the inspector to a different output (card Configure / body click). Re-renders the
      // inspector alone (no grid rebuild → no preview thrash) and re-marks the selected card.
      function selectScreen(id) {
        if (selectedScreen === id) return;
        selectedScreen = id;
        const list = document.getElementById("screens-list");
        list.querySelectorAll(".scr-card").forEach((c) => {
          c.classList.toggle("scr-card-selected", c.dataset.screen === id);
        });
        if (lastOutputsView) {
          const view = lastOutputsView;
          const registry = (view.screens && view.screens.length) ? view.screens : [];
          const outByRole = {}; (view.outputs || []).forEach((o) => { outByRole[o.role] = o; });
          const screenThemes = {}; (view.screen_themes || []).forEach((st) => { screenThemes[st.screen] = st.theme; });
          // Re-render the inspector for the new selection and re-mark the card IN PLACE — no
          // grid rebuild here, so the preview canvases are not thrashed on a mere selection.
          // outputsKey is deliberately left alone: selectedScreen is part of the change-gate
          // key, so the next poll reconciles the grid on its own only if the data changed.
          renderInspector(view, registry, outByRole, screenThemes, view.themes || []);
        }
      }

      // A per-SCREEN Theme picker (86ajq321k): sets THIS screen's theme (not the global) and
      // reflects the screen's current theme. Returned as a label + select for the inspector.
      function themePickerFor(screen, themes, screenThemes, view) {
        const frag = document.createDocumentFragment();
        const cl = document.createElement("label"); cl.className = "scr-irow-label"; cl.textContent = "Theme";
        frag.appendChild(cl);
        const sel = document.createElement("select"); sel.className = "scr-select scr-select-gold";
        sel.setAttribute("aria-label", "Theme for the " + screen + " screen");
        if (!themes.length) {
          const opt = document.createElement("option");
          opt.textContent = "No themes offered"; opt.disabled = true; opt.selected = true;
          sel.appendChild(opt); sel.disabled = true;
        } else {
          // Whether this screen has an EXPLICIT per-screen theme (vs. following the global).
          const explicit = Object.prototype.hasOwnProperty.call(screenThemes, screen);
          const glob = document.createElement("option");
          glob.value = ""; glob.textContent = "◈ Follow global";
          if (!explicit) glob.selected = true;
          sel.appendChild(glob);
          themes.forEach((t) => {
            const opt = document.createElement("option");
            opt.value = t; opt.textContent = t;
            if (explicit && t === screenThemes[screen]) opt.selected = true;
            sel.appendChild(opt);
          });
          // Saved (named custom) themes from the library (86ajq69ft), in a labelled group.
          const savedNames = (view.saved_themes || []).map((t) => t.name);
          if (savedNames.length) {
            const grp = document.createElement("optgroup");
            grp.label = "Saved";
            savedNames.forEach((name) => {
              const opt = document.createElement("option");
              opt.value = name; opt.textContent = name;
              if (explicit && name === screenThemes[screen]) opt.selected = true;
              grp.appendChild(opt);
            });
            sel.appendChild(grp);
          }
          sel.onchange = () => act(() => invoke("set_screen_theme", { screen, name: sel.value }));
        }
        frag.appendChild(sel);
        return frag;
      }

      // --- INSPECTOR (Design 2.0 §INSPECTOR): the per-output config panel for the selected
      // screen. Every control drives a real backend command; a value the host cannot report
      // (telemetry, a virtual feed's monitor) shows an honest dash, never a fabricated number.
      function renderInspector(view, registry, outByRole, screenThemes, themes) {
        const insp = document.getElementById("screens-inspector");
        if (!insp) return;
        insp.innerHTML = "";
        const s = registry.find((r) => r.screen === selectedScreen);
        if (!s) {
          const empty = document.createElement("div");
          empty.className = "scr-isection scr-imuted";
          empty.textContent = "Select an output to configure it.";
          insp.appendChild(empty);
          return;
        }
        const o = outByRole[s.role];
        const cfg = cfgOf(s);
        const isPhysical = s.role === "main" || s.role === "stage";
        const audience = s.role !== "stage";
        const displays = view.displays || [];

        // A titled section container.
        const section = (title) => {
          const sec = document.createElement("div"); sec.className = "scr-isection";
          if (title) {
            const t = document.createElement("div"); t.className = "scr-isection-title";
            t.textContent = title; sec.appendChild(t);
          }
          return sec;
        };
        const divider = () => { const d = document.createElement("div"); d.className = "scr-idivider"; return d; };
        // A label-left / <select>-right config row with optimistic revert (a rejected change
        // never shows a false value — the poll re-render reflects the true state).
        const selectRow = (labelText, ariaLabel, options, current, onChange, goldValue) => {
          const row = document.createElement("div"); row.className = "scr-irow";
          const lab = document.createElement("label"); lab.className = "scr-irow-label"; lab.textContent = labelText;
          const sel = document.createElement("select");
          sel.className = "scr-select" + (goldValue ? " scr-select-gold" : "");
          sel.setAttribute("aria-label", ariaLabel);
          options.forEach(([v, t]) => {
            const opt = document.createElement("option");
            opt.value = String(v); opt.textContent = t;
            if (String(v) === String(current)) opt.selected = true;
            sel.appendChild(opt);
          });
          sel.onchange = () => {
            const want = sel.value; sel.value = String(current); onChange(want);
          };
          const id = "scr-irow-" + Math.random().toString(36).slice(2, 8);
          lab.setAttribute("for", id); sel.id = id;
          row.appendChild(lab); row.appendChild(sel);
          return row;
        };
        // A read-only label-left / value-right row.
        const valueRow = (labelText, valueText) => {
          const row = document.createElement("div"); row.className = "scr-irow";
          const lab = document.createElement("label"); lab.className = "scr-irow-label"; lab.textContent = labelText;
          const val = document.createElement("span"); val.className = "scr-irow-value"; val.textContent = valueText;
          row.appendChild(lab); row.appendChild(val);
          return row;
        };
        // A label-left / toggle-right row with optimistic revert.
        const toggleRow = (labelText, ariaLabel, checked, onChange) => {
          const row = document.createElement("div"); row.className = "scr-irow";
          const lab = document.createElement("label"); lab.className = "scr-irow-label"; lab.textContent = labelText;
          const tog = document.createElement("label"); tog.className = "scr-toggle";
          const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = checked;
          cb.setAttribute("aria-label", ariaLabel);
          cb.onchange = () => { const want = cb.checked; cb.checked = checked; onChange(want); };
          const knob = document.createElement("span"); knob.className = "scr-toggle-knob";
          tog.appendChild(cb); tog.appendChild(knob);
          row.appendChild(lab); row.appendChild(tog);
          return row;
        };

        // --- Header: selected identity + status pill + subtitle ---
        const header = section(null); header.classList.add("scr-iheader");
        const idRow = document.createElement("div"); idRow.className = "scr-iheader-row";
        const nm = document.createElement("strong"); nm.className = "scr-iheader-name";
        nm.textContent = screenDisplayName(s);
        idRow.appendChild(nm); idRow.appendChild(statusPillFor(s, o));
        header.appendChild(idRow);
        const sub = document.createElement("div"); sub.className = "scr-iheader-sub";
        const roleTag = roleBadgeText(s.role);
        const where = o && o.display ? o.display : (isPhysical ? "No display assigned" : "Composed feed — no physical output");
        sub.textContent = roleTag + " role · " + where;
        header.appendChild(sub);
        insp.appendChild(header); insp.appendChild(divider());

        // --- DISPLAY ---
        const disp = section("DISPLAY");
        // Monitor (assign) — physical roles bind a display; a virtual feed is an honest seam.
        if (isPhysical && displays.length && o) {
          const row = document.createElement("div"); row.className = "scr-irow";
          const lab = document.createElement("label"); lab.className = "scr-irow-label"; lab.textContent = "Monitor";
          const sel = document.createElement("select"); sel.className = "scr-select";
          sel.setAttribute("aria-label", "Assign the " + s.role + " output to a display");
          if (!o.assigned) sel.classList.add("mismatch");
          const none = document.createElement("option");
          none.value = ""; none.textContent = o.assigned ? "Assign to display…" : "— not assigned";
          sel.appendChild(none);
          displays.forEach((d) => {
            const opt = document.createElement("option");
            opt.value = d.key; opt.textContent = d.name;
            if (o.assigned_key && o.assigned_key === d.key) opt.selected = true;
            sel.appendChild(opt);
          });
          sel.onchange = () => {
            const chosen = sel.value; sel.value = o.assigned_key || "";
            if (chosen) act(() => invoke("assign_output", { role: s.role, displayKey: chosen }));
          };
          const id = "scr-mon-" + s.screen; lab.setAttribute("for", id); sel.id = id;
          row.appendChild(lab); row.appendChild(sel); disp.appendChild(row);
        } else if (isPhysical) {
          disp.appendChild(valueRow("Monitor", o && o.display ? o.display : "No displays found"));
        } else {
          disp.appendChild(valueRow("Monitor", "No physical output"));
        }
        disp.appendChild(valueRow("Resolution", o && o.width ? o.width + " × " + o.height : "—"));
        disp.appendChild(selectRow(
          "Frame rate", "Target frame rate for " + s.screen,
          [[24, "24 fps"], [30, "30 fps"], [48, "48 fps"], [50, "50 fps"], [60, "60 fps"]],
          cfg.frame_rate,
          (v) => act(() => invoke("set_output_frame_rate", { screen: s.screen, fps: parseInt(v, 10) }))
        ));
        disp.appendChild(selectRow(
          "Orientation", "Orientation for " + s.screen,
          [[0, "Landscape"], [1, "Portrait"], [2, "Landscape flipped"], [3, "Portrait flipped"]],
          cfg.orientation,
          (v) => act(() => invoke("set_output_orientation", { screen: s.screen, quarterTurns: parseInt(v, 10) }))
        ));
        insp.appendChild(disp); insp.appendChild(divider());

        // --- APPEARANCE ---
        const app = section("APPEARANCE");
        if (audience) {
          const themeRow = document.createElement("div"); themeRow.className = "scr-irow";
          themeRow.appendChild(themePickerFor(s.screen, themes, screenThemes, view));
          app.appendChild(themeRow);
        } else {
          app.appendChild(valueRow("Theme", "Stage layout"));
        }
        app.appendChild(selectRow(
          "Scaling / fit", "Scaling and fit for " + s.screen,
          [["fill", "Fill"], ["fit", "Fit"], ["stretch", "Stretch"]],
          cfg.scale_fit,
          (v) => act(() => invoke("set_output_scale_fit", { screen: s.screen, fit: v }))
        ));
        app.appendChild(toggleRow(
          "Show safe-area guides", "Show safe-area guides on the operator preview for " + s.screen,
          cfg.safe_area_guides,
          (on) => act(() => invoke("set_output_safe_area", { screen: s.screen, on }))
        ));
        insp.appendChild(app); insp.appendChild(divider());

        // --- VISIBLE LAYERS ---
        const layers = section("VISIBLE LAYERS");
        [
          ["background", "Background", cfg.layers.background],
          ["text", "Text / lyrics", cfg.layers.text],
          ["lower-third", "Lower third", cfg.layers.lower_third],
          ["logo", "Church logo", cfg.layers.logo],
          ["timer", "Service timer", cfg.layers.timer],
        ].forEach(([layer, label, on]) => {
          layers.appendChild(toggleRow(
            label, label + " layer on " + s.screen, on,
            (vis) => act(() => invoke("set_screen_layer_visible", { screen: s.screen, layer, visible: vis }))
          ));
        });
        insp.appendChild(layers); insp.appendChild(divider());

        // --- TIMING ---
        const timing = section("TIMING");
        timing.appendChild(selectRow(
          "Output delay", "Output delay for " + s.screen,
          [[0, "0 ms"], [40, "40 ms"], [80, "80 ms"], [120, "120 ms"], [250, "250 ms"], [500, "500 ms"], [1000, "1000 ms"]],
          cfg.delay_ms,
          (v) => act(() => invoke("set_output_delay", { screen: s.screen, ms: parseInt(v, 10) }))
        ));
        timing.appendChild(toggleRow(
          "Mirror horizontally", "Mirror " + s.screen + " horizontally",
          cfg.mirror,
          (on) => act(() => invoke("set_output_mirror", { screen: s.screen, on }))
        ));
        insp.appendChild(timing); insp.appendChild(divider());

        // --- NDI OUTPUT (Audience-class feeds: publish the composed feed as an NDI source
        // that OBS / vMix / another SelahCue can receive over the network). Name + enable are
        // set together; the host validates the name + uniqueness. ---
        if (audience) {
          const ndi = section("NDI OUTPUT");
          const nameRow = document.createElement("div"); nameRow.className = "scr-irow";
          const nameLab = document.createElement("label"); nameLab.className = "scr-irow-label";
          nameLab.textContent = "Source name";
          const nameInput = document.createElement("input");
          nameInput.type = "text"; nameInput.className = "scr-input";
          nameInput.value = cfg.ndi_name;
          nameInput.maxLength = 64;
          nameInput.placeholder = "e.g. SelahCue Program";
          nameInput.setAttribute("aria-label", "NDI source name for " + s.screen);
          const nameId = "scr-ndi-name-" + s.screen;
          nameLab.setAttribute("for", nameId); nameInput.id = nameId;
          // Commit the name + a target enabled state atomically to the host.
          const commitNdi = (enabled) => {
            const name = nameInput.value.trim();
            act(() => invoke("set_ndi_output", { screen: s.screen, name, enabled }));
          };
          nameInput.onchange = () => commitNdi(cfg.ndi_enabled);
          nameRow.appendChild(nameLab); nameRow.appendChild(nameInput);
          ndi.appendChild(nameRow);
          // Broadcast toggle — reads the (possibly just-edited) name; enabling with an empty
          // name is rejected by the host and reverts, so the control never lies.
          ndi.appendChild(toggleRow(
            "Broadcast as NDI", "Broadcast " + s.screen + " as an NDI source",
            cfg.ndi_enabled,
            (on) => commitNdi(on)
          ));
          // Honest status: broadcasting (with the source name) or off.
          const st = document.createElement("div"); st.className = "scr-signal";
          if (cfg.ndi_enabled && cfg.ndi_name) {
            st.classList.add("scr-signal-ok");
            st.textContent = "● Broadcasting NDI · " + cfg.ndi_name;
          } else {
            st.classList.add("scr-signal-neutral");
            st.textContent = "NDI off — set a source name and enable to broadcast on the network";
          }
          ndi.appendChild(st);
          insp.appendChild(ndi); insp.appendChild(divider());
        }

        // --- DEVICE ---
        const dev = section("DEVICE");
        const devRow = document.createElement("div"); devRow.className = "scr-idevice-row";
        const idBtn = document.createElement("button");
        idBtn.type = "button"; idBtn.className = "btn-secondary scr-idevice-btn"; idBtn.textContent = "Identify";
        idBtn.disabled = (view.outputs || []).length === 0;
        idBtn.onclick = () => act(() => invoke("identify_outputs"));
        const testBtn = document.createElement("button");
        testBtn.type = "button"; testBtn.className = "btn-secondary scr-idevice-btn"; testBtn.textContent = "Test pattern";
        testBtn.disabled = true; testBtn.title = "A calibration test pattern arrives with physical NDI/SDI delivery.";
        devRow.appendChild(idBtn); devRow.appendChild(testBtn); dev.appendChild(devRow);
        const fs = document.createElement("button");
        fs.type = "button"; fs.className = "btn-primary scr-ifullscreen"; fs.textContent = "⛶  Go fullscreen";
        fs.disabled = true; fs.title = "Full-screen control of a physical output arrives with NDI/SDI delivery.";
        dev.appendChild(fs);
        // Honest signal-health footer (telemetry — never fabricated).
        const foot = document.createElement("div"); foot.className = "scr-signal";
        let sig = "neutral", txt = "Signal — · awaiting host telemetry";
        if (o && o.signal === "healthy") {
          sig = "ok";
          txt = "● Signal healthy" + (typeof o.fps === "number" ? " · " + o.fps + "fps" : "")
            + (typeof o.dropped_frames === "number" ? " · " + o.dropped_frames + " dropped frames" : "");
        } else if (o && o.signal === "degraded") {
          sig = "warn"; txt = "● Signal degraded"
            + (typeof o.dropped_frames === "number" ? " · " + o.dropped_frames + " dropped frames" : "");
        } else if (o && o.signal === "no_signal") {
          sig = "bad"; txt = "● No signal · no monitor attached";
        } else if (!isPhysical) {
          sig = "neutral"; txt = "Composed feed · no physical signal yet";
        }
        foot.classList.add("scr-signal-" + sig); foot.textContent = txt;
        dev.appendChild(foot);
        insp.appendChild(dev);
      }

      document.getElementById("screens-list").addEventListener("focusout", () => {
        setTimeout(() => {
          const list = document.getElementById("screens-list");
          const insp = document.getElementById("screens-inspector");
          const active = document.activeElement;
          const stillInside = (list && list.contains(active)) || (insp && insp.contains(active));
          if (outputsPending && !stillInside) {
            const v = outputsPending;
            outputsPending = null;
            renderOutputs(v);
          }
        }, 0);
      });

      // --- App menu + surface routing (86ajq321f) ---
      const APP_SURFACES = ["console", "preservice", "presentation", "theme-designer", "screens", "remote", "plan", "settings"];
      // Kept in sync with the nav items' .nav-t labels — the topbar surface label + the SR
      // route announcement read from here, so a drift would show a name the menu doesn't use.
      const SURFACE_LABEL = {
        console: "Live Console", preservice: "Pre-service Check", presentation: "Presentation", "theme-designer": "Theme Designer",
        screens: "Screens & Outputs", remote: "Remote Control", plan: "Service Plan", settings: "Settings",
      };
      const appMenu = document.getElementById("app-menu");
      const appMenuBtn = document.getElementById("app-menu-btn");
      const navItems = Array.from(appMenu.querySelectorAll(".nav-item"));
      function isMenuOpen() { return appMenu.classList.contains("open"); }
      // Roving tabindex: only the focused menuitem is tabbable (APG menu pattern).
      function focusNav(i) {
        navItems.forEach((it, j) => { it.tabIndex = j === i ? 0 : -1; });
        navItems[i].focus();
      }
      // Lazy-init the Theme Designer on FIRST activation (audit L3): its built-ins + the full
      // system-font list (300–800 <option> nodes + 2 host round-trips) are otherwise built at
      // boot even for operators who never open it. Only the designer surface reads them — the
      // plan's per-row theme picker uses the host `view.themes`, and `syncSavedThemes`/`tdList`
      // already no-op until the built-ins exist — so deferring is safe for the console/plan.
      let tdLoaded = false;
      function ensureThemeDesignerLoaded() {
        if (tdLoaded) return;
        tdLoaded = true;
        tdLoadBuiltins();
        tdLoadFonts();
      }
      function showSurface(name) {
        if (name === "theme-designer") ensureThemeDesignerLoaded();
        APP_SURFACES.forEach((s) => {
          const el = document.getElementById("surface-" + s);
          if (el) el.classList.toggle("active", s === name);
        });
        navItems.forEach((it) => {
          // Mark ONLY the primary entry for a surface as current — a sub-region jump
          // (data-focus, e.g. "Transcript & Notes" → console) shares the surface but must
          // not also read as the current page (review #21: avoid two aria-current items).
          if (it.dataset.surface === name && !it.dataset.focus) it.setAttribute("aria-current", "page");
          else it.removeAttribute("aria-current");
        });
        closeAppMenu();
        if (typeof pmLibCloseMenu === "function") pmLibCloseMenu(); // dismiss any open Library ⋯ menu on surface switch (no orphan over the next surface)
        // Move focus INTO the new surface (never leave it on a now-hidden element)
        // and announce the route to assistive tech (NAV-IA §2/§5).
        const surf = document.getElementById("surface-" + name);
        if (surf) { surf.tabIndex = -1; surf.focus(); }
        // The Theme Designer canvas fits the available area once its surface is laid out.
        if (name === "theme-designer" && typeof tdFitCanvasSoon === "function") tdFitCanvasSoon();
        const label = SURFACE_LABEL[name] || name;
        document.getElementById("route-status").textContent = "Now on: " + label;
        // The topbar surface label reflects the active surface (the header is global).
        const surfLabel = document.getElementById("surface-label");
        if (surfLabel) surfLabel.textContent = label;
        // Refresh the true Preview/Live render when returning to the console (86ajtwq28).
        if (name === "console") scheduleConsoleRender();
        if (name === "screens") scheduleScreenPreviews(); // refresh the per-screen previews (86ajq321k)
        // The Presentation surface loads its deck view + fits its canvas on activation.
        if (name === "presentation" && typeof pmActivate === "function") pmActivate();
        // The Pre-service Check runs its checks on activation (and starts a bounded auto-refresh).
        if (name === "preservice" && typeof psActivate === "function") psActivate();
        // The Service Plan builder loads the plan + deck names on activation.
        if (name === "plan" && typeof planActivate === "function") planActivate();
        // Settings opens to Providers & Privacy by default (the sidebar's first built page); it loads
        // the real providers_view() lazily. A caller wanting another page (e.g. ⌘⇧R → Network & Mobile)
        // calls setSettingsPage() AFTER showSurface, overriding this default.
        if (name === "settings" && typeof setSettingsPage === "function") setSettingsPage("providers");
      }
      // Settings sidebar routing (Design 2.0, Figma 338:124). Providers + Network & Mobile are built;
      // the rest show the shared "coming soon" page. Providers loads lazily via settingsActivate.
      function setSettingsPage(page, label) {
        let lbl = label;
        document.querySelectorAll("#surface-settings .set-nav").forEach((b) => {
          const on = b.dataset.setpage === page;
          b.classList.toggle("active", on);
          if (on) {
            b.setAttribute("aria-current", "page");
            if (!lbl) lbl = b.textContent.trim();
          } else {
            b.removeAttribute("aria-current");
          }
        });
        const built = { providers: "set-page-providers", network: "set-page-network" };
        document.querySelectorAll("#surface-settings .set-page").forEach((p) => {
          p.hidden = true;
        });
        if (built[page]) {
          document.getElementById(built[page]).hidden = false;
          if (page === "providers" && typeof settingsActivate === "function") settingsActivate();
        } else {
          document.getElementById("set-placeholder").hidden = false;
          document.getElementById("set-ph-title").textContent = lbl || "Settings";
        }
      }
      (function initSettingsSidebar() {
        const side = document.querySelector("#surface-settings .set-side");
        if (!side) return;
        side.querySelectorAll(".set-nav").forEach((b) => {
          b.onclick = () => setSettingsPage(b.dataset.setpage);
        });
        const openRemote = document.getElementById("set-open-remote");
        if (openRemote) openRemote.onclick = () => showSurface("remote"); // Network & Mobile → devices
      })();
      function openAppMenu() {
        appMenu.classList.add("open");
        appMenuBtn.setAttribute("aria-expanded", "true");
        const cur = navItems.findIndex((i) => i.getAttribute("aria-current") === "page");
        focusNav(cur >= 0 ? cur : 0);
      }
      function closeAppMenu() {
        appMenu.classList.remove("open");
        appMenuBtn.setAttribute("aria-expanded", "false");
      }
      function toggleAppMenu() { isMenuOpen() ? closeAppMenu() : openAppMenu(); }
      appMenuBtn.onclick = toggleAppMenu;
      // Navigate to a menu item's surface. Guards items with no data-surface (an honest
      // "later" affordance, or an aria-disabled item) so a click can never blank the router.
      // data-focus scrolls a sub-region of the target surface into view.
      const navGo = (it) => {
        if (it.getAttribute("aria-disabled") === "true" || !it.dataset.surface) return;
        showSurface(it.dataset.surface);
        const focusSel = it.dataset.focus;
        if (focusSel) {
          const el = document.getElementById(focusSel);
          if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
        }
      };
      navItems.forEach((it, i) => {
        it.onclick = () => navGo(it);
        it.addEventListener("keydown", (e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); focusNav((i + 1) % navItems.length); }
          else if (e.key === "ArrowUp") { e.preventDefault(); focusNav((i - 1 + navItems.length) % navItems.length); }
          else if (e.key === "Home") { e.preventDefault(); focusNav(0); }
          else if (e.key === "End") { e.preventDefault(); focusNav(navItems.length - 1); }
          else if (e.key === "Escape") { e.preventDefault(); closeAppMenu(); appMenuBtn.focus(); }
          else if (e.key === "Tab") { closeAppMenu(); } // Tab moves focus on AND closes the menu
        });
      });
      document.addEventListener("click", (e) => {
        if (isMenuOpen() && !appMenu.contains(e.target) && e.target !== appMenuBtn) closeAppMenu();
      });
      document.getElementById("screens-identify").onclick = () => act(() => invoke("identify_outputs"));
      // "+ Add virtual output" (Design 2.0 topbar): mint a VIRTUAL Audience-class feed
      // (lower-third / stream) from the role select. The host caps the registry, so this is
      // refused (harmlessly) at the bound.
      document.getElementById("screen-add-btn").onclick = () => {
        const roleSel = document.getElementById("screen-add-role");
        act(() => invoke("add_screen", { role: roleSel.value }));
      };

      // --- Theme Designer (S8-3c; refine: full-center canvas + on-canvas drag/resize) ---
      // Built-ins come from the HOST (`builtin_themes`) so the editor previews/applies
      // the REAL themes from theme.rs — no hand-mirrored JS copy to drift (e.g. the
      // lower-third band). The preview is a pure host render; Apply is authoritative.
      const tdCanvas = document.getElementById("td-preview");
      const tdCtx = tdCanvas.getContext("2d");
      const tdBox = document.getElementById("td-canvas-box");
      const tdSel = document.getElementById("td-sel");
      let TD_BUILTINS = {}; // name -> theme object (from the host)
      let tdOrder = []; // built-in template names, in order
      let tdSaved = []; // saved library themes: [{name, theme_json}] (from the host view)
      let tdSavedKey = ""; // change-detect so the 1s poll only rebuilds the list on a real change
      let tdTheme = null; // the theme being edited
      let tdRegion = "body";
      let tdSelEl = -1; // selected element index into tdTheme.elements, or -1 = a region (86ajq6j4p)
      let tdElDelArm = false; // two-click element-delete arm (reset on every selection change)
      let tdElDelTimer = null;
      let tdSelected = ""; // the selected TEMPLATE name (built-in or saved), "" = a new/unsaved theme
      let tdSelectedKind = ""; // "builtin" | "saved" | "" — disambiguates a saved theme that shares a built-in's name
      let tdConfirmDel = null; // saved-theme name in the two-click delete-confirm state
      const tdHex = (c) => "#" + [c.r, c.g, c.b].map((v) => v.toString(16).padStart(2, "0")).join("");
      // A human label for an element's kind (announcements / heads). Text is 86ajq6j64.
      const tdElLabel = (el) => (el && el.kind === "image") ? "Image" : (el && el.kind === "text") ? "Text" : "Shape";
      const tdRgb = (h) => ({ r: parseInt(h.slice(1, 3), 16), g: parseInt(h.slice(3, 5), 16), b: parseInt(h.slice(5, 7), 16), a: 255 });
      const tdClamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
      const tdSeg = (id, val, attr) =>
        document.querySelectorAll("#" + id + " button").forEach((b) => {
          const sel = b.dataset[attr] === val;
          b.classList.toggle("on", sel);
          // Selection must be perceivable to assistive tech, not colour-only (WCAG 4.1.2).
          b.setAttribute("aria-pressed", sel ? "true" : "false");
        });

      // Fold the host's saved-theme library (from every operator view) into the Theme
      // Designer list. Change-detected so the 1s poll only rebuilds on a real change,
      // and never while the save-name field is focused (would clobber a half-typed name).
      function syncSavedThemes(view) {
        const incoming = Array.isArray(view.saved_themes) ? view.saved_themes : [];
        const key = JSON.stringify(incoming);
        if (key === tdSavedKey) return;
        // Leave the key unconsumed while typing a name so it rebuilds once focus leaves.
        if (document.activeElement && document.activeElement.id === "td-save-name") return;
        tdSavedKey = key;
        tdSaved = incoming;
        // Only rebuild once the built-ins exist (tdLoadBuiltins renders the first list).
        if (tdOrder.length) tdList();
      }

      // Ensure the Font picker has an option for `font` even when it is NOT installed on
      // THIS machine (a theme designed elsewhere) — so a saved theme's font is reflected +
      // preserved, never silently blanked. Deduped; a no-op for the default ("").
      function tdEnsureFontOption(font) {
        if (!font) return;
        const sel = document.getElementById("td-font");
        if (Array.from(sel.options).some((o) => o.value === font)) return;
        const o = document.createElement("option");
        o.value = font;
        o.textContent = font + " (not installed here)";
        sel.appendChild(o);
      }

      // Populate the Font picker from the fonts installed on THIS machine (86ajq6fxt).
      // The default "Noto Sans (default)" option (value "") stays; families append after.
      async function tdLoadFonts() {
        const sel = document.getElementById("td-font");
        let fonts = [];
        try {
          fonts = await invoke("system_fonts");
        } catch (e) {
          console.error(e);
        }
        fonts.forEach((fam) => {
          const o = document.createElement("option");
          o.value = fam;
          o.textContent = fam;
          sel.appendChild(o);
        });
        if (tdTheme) {
          tdEnsureFontOption(tdTheme.font);
          sel.value = tdTheme.font || "";
        }
      }

      async function tdLoadBuiltins() {
        let list = [];
        try {
          list = await invoke("builtin_themes");
        } catch (e) {
          console.error(e);
          document.getElementById("td-status").textContent = "Couldn't load the built-in themes.";
        }
        TD_BUILTINS = {};
        tdOrder = [];
        list.forEach(({ name, theme }) => { TD_BUILTINS[name] = theme; tdOrder.push(name); });
        tdSelected = tdOrder[0] || "";
        tdSelectedKind = tdSelected ? "builtin" : "";
        tdTheme = tdSelected ? JSON.parse(JSON.stringify(TD_BUILTINS[tdSelected])) : null;
        tdSelEl = -1; // clear any element selection when the theme changes
        tdList();
        tdSync();
        tdPreview();
      }

      // A compact template thumbnail (Design 2.0 strip, Figma 319:152): the theme's REAL
      // background (solid / gradient / image→neutral) + a title/body bar pair, so each card
      // reflects the actual theme — never a generic fake.
      function tdThumb(theme) {
        const t = document.createElement("div");
        t.className = "td-theme-thumb";
        t.setAttribute("aria-hidden", "true");
        const bg = theme && theme.background;
        if (bg && Number.isFinite(bg.r)) t.style.background = tdHex(bg); // solid ({r,g,b,a})
        else if (bg && bg.from && bg.to)
          t.style.background = "linear-gradient(160deg, " + tdHex(bg.from) + ", " + tdHex(bg.to) + ")";
        else t.style.background = "var(--sc-inset)"; // image / unknown → neutral inset
        const bar = (cls, color) => {
          const d = document.createElement("div");
          d.className = "td-theme-thumb-bar " + cls;
          d.style.background = color;
          return d;
        };
        const titleC = theme && theme.title && theme.title.color ? tdHex(theme.title.color) : "rgba(242,184,75,.9)";
        const bodyC = theme && theme.body && theme.body.color ? tdHex(theme.body.color) : "rgba(255,255,255,.85)";
        t.appendChild(bar("title", titleC));
        t.appendChild(bar("body", bodyC));
        return t;
      }

      function tdList() {
        const box = document.getElementById("td-themes");
        box.innerHTML = "";
        // A rebuild recreates every ✕ in its UNARMED look, so any pending two-click
        // delete-confirm must be dropped here too — otherwise the button would show
        // "✕" while the state stayed armed, and one click would delete without a confirm.
        tdConfirmDel = null;
        // Built-ins first — read-only reference templates (load into the editor, never
        // edited in place). Selecting one loads a working COPY. Selection is keyed by
        // KIND too, so a saved theme that shares a built-in's name never co-highlights.
        tdOrder.forEach((name) => {
          const row = document.createElement("div");
          row.className = "td-theme-row";
          const b = document.createElement("button");
          b.className = "td-theme-name";
          b.type = "button";
          b.textContent = name;
          b.setAttribute("aria-pressed", tdSelectedKind === "builtin" && name === tdSelected ? "true" : "false");
          // Selecting a template = clicking anywhere on the CARD (the thumbnail is the dominant
          // target), not just the name text. The whole row is the control; the name stays a
          // focusable button so keyboard Enter/Space activates it and bubbles to this handler.
          row.onclick = () => {
            tdSelected = name;
            tdSelectedKind = "builtin";
            tdTheme = JSON.parse(JSON.stringify(TD_BUILTINS[name]));
            tdSelEl = -1;
            tdSync();
            tdPreview();
            tdList();
          };
          const tag = document.createElement("span");
          tag.className = "td-theme-tag";
          tag.textContent = "built-in";
          row.dataset.current = tdSelectedKind === "builtin" && name === tdSelected ? "true" : "false";
          const foot = document.createElement("div");
          foot.className = "td-theme-cardfoot";
          foot.appendChild(b);
          foot.appendChild(tag);
          row.appendChild(tdThumb(TD_BUILTINS[name]));
          row.appendChild(foot);
          box.appendChild(row);
        });
        // Saved (named custom) themes from the library — selectable (load into the
        // editor) and deletable (✕). A confirm-on-second-click delete mirrors the plan.
        tdSaved.forEach(({ name, theme_json }) => {
          const row = document.createElement("div");
          row.className = "td-theme-row td-theme-saved";
          const b = document.createElement("button");
          b.className = "td-theme-name";
          b.type = "button";
          b.textContent = name;
          b.setAttribute("aria-pressed", tdSelectedKind === "saved" && name === tdSelected ? "true" : "false");
          // Whole-card select (see the built-in branch); the ✕ stops propagation so deleting
          // never also loads the theme.
          row.onclick = () => {
            let parsed;
            try {
              parsed = JSON.parse(theme_json);
            } catch (e) {
              tdStatus("That saved theme is unreadable and can't be loaded.");
              return;
            }
            tdSelected = name;
            tdSelectedKind = "saved";
            tdTheme = parsed;
            tdSelEl = -1;
            tdSync();
            tdPreview();
            tdList();
          };
          const del = document.createElement("button");
          del.className = "td-theme-del";
          del.textContent = "✕";
          del.title = "Delete this saved theme";
          del.setAttribute("aria-label", "Delete saved theme " + name);
          del.onclick = (ev) => {
            ev.stopPropagation();
            if (tdConfirmDel === name) {
              tdConfirmDel = null;
              // The next view (poll or this reply) drops it from tdSaved → list rebuilds.
              act(() => invoke("delete_theme", { name }));
              if (tdSelectedKind === "saved" && tdSelected === name) {
                tdSelected = "";
                tdSelectedKind = "";
              }
              tdStatus("Deleted “" + name + "”.");
            } else {
              tdConfirmDel = name;
              del.textContent = "✕?";
              del.classList.add("confirm");
              tdStatus("Click ✕ again to delete “" + name + "”.");
              setTimeout(() => {
                if (tdConfirmDel === name) {
                  tdConfirmDel = null;
                  del.textContent = "✕";
                  del.classList.remove("confirm");
                }
              }, 3000);
            }
          };
          row.dataset.current = tdSelectedKind === "saved" && name === tdSelected ? "true" : "false";
          let thumbTheme = null;
          try { thumbTheme = JSON.parse(theme_json); } catch (e) { thumbTheme = null; }
          const foot = document.createElement("div");
          foot.className = "td-theme-cardfoot";
          foot.appendChild(b);
          foot.appendChild(del);
          row.appendChild(tdThumb(thumbTheme));
          row.appendChild(foot);
          box.appendChild(row);
        });
      }

      // --- Canvas ELEMENT editing (86ajq6j4p): the active target is a REGION or an ELEMENT.
      // The rect fields (x/y/w/h_permille) are identical, so the region drag/resize machinery
      // generalises by resolving the active target instead of a hard-coded `tdTheme[tdRegion]`.
      // (tdSelEl is declared with the theme state above: -1 = a region is the active target.)
      function tdEls() { return tdTheme && Array.isArray(tdTheme.elements) ? tdTheme.elements : []; }
      function tdActiveIsEl() { return tdSelEl >= 0 && tdSelEl < tdEls().length; }
      // The active rect-bearing object: the selected element, else the selected region.
      function tdActive() { return tdActiveIsEl() ? tdEls()[tdSelEl] : tdTheme ? tdTheme[tdRegion] : null; }
      const tdZ = (e) => (e && Number.isFinite(e.z) ? e.z : 0);
      const tdOpacity = (e) => (e && Number.isFinite(e.opacity) ? e.opacity : 255);
      // Per-layer visibility (Design 2.0 LAYERS): an element is shown unless `visible === false`
      // (the field is OMITTED when shown so the theme JSON stays byte-stable — see theme.rs).
      const tdVisible = (e) => !(e && e.visible === false);
      // Element indices in composite PAINT order (compose_slide stable-sorts by z, THEN list
      // index; z is the sole determinant, the index only breaks ties). Back-to-front.
      function tdPaintOrder() {
        return tdEls()
          .map((_, i) => i)
          .sort((a, b) => tdZ(tdEls()[a]) - tdZ(tdEls()[b]) || a - b);
      }
      // The topmost ELEMENT index at a client point (front-to-back paint order), or -1.
      function tdHitTest(clientX, clientY) {
        const box = tdBox.getBoundingClientRect();
        const xp = ((clientX - box.left) / (box.width || 1)) * 1000;
        const yp = ((clientY - box.top) / (box.height || 1)) * 1000;
        const order = tdPaintOrder();
        for (let k = order.length - 1; k >= 0; k--) {
          const el = tdEls()[order[k]];
          if (
            xp >= el.x_permille && xp <= el.x_permille + el.w_permille &&
            yp >= el.y_permille && yp <= el.y_permille + el.h_permille
          ) {
            return order[k];
          }
        }
        return -1;
      }
      // Whether a client point falls within a per-mille rect (region or element).
      function tdPointInRect(cx, cy, r) {
        const box = tdBox.getBoundingClientRect();
        const xp = ((cx - box.left) / (box.width || 1)) * 1000;
        const yp = ((cy - box.top) / (box.height || 1)) * 1000;
        return (
          xp >= r.x_permille && xp <= r.x_permille + r.w_permille &&
          yp >= r.y_permille && yp <= r.y_permille + r.h_permille
        );
      }
      // The text REGION under a client point, or null. Clicking the Body / Reference-Title text
      // on the canvas selects that region (only VISIBLE regions — you select what you see). Body
      // is checked first (it renders on top of the title where they overlap).
      function tdRegionAt(cx, cy) {
        if (!tdTheme) return null;
        if (tdTheme.body && tdTheme.body.visible !== false && tdPointInRect(cx, cy, tdTheme.body)) return "body";
        if (tdTheme.title && tdTheme.title.visible !== false && tdPointInRect(cx, cy, tdTheme.title)) return "title";
        return null;
      }
      // Screen-reader announcement (reuses the aria-live #td-status region).
      function tdAnnounce(msg) {
        const s = document.getElementById("td-status");
        if (s) s.textContent = msg;
      }

      // Position the on-canvas selection box from the active target's rect% (per-mille → %).
      function tdDrawSel() {
        const r = tdActive();
        if (!tdTheme || !r) {
          tdSel.style.display = "none";
          return;
        }
        // A region gates on `.visible`; an element always shows its selection box.
        const show = tdActiveIsEl() ? true : r.visible;
        tdSel.style.display = show ? "block" : "none";
        tdSel.classList.toggle("is-element", tdActiveIsEl());
        tdSel.style.left = r.x_permille / 10 + "%";
        tdSel.style.top = r.y_permille / 10 + "%";
        tdSel.style.width = r.w_permille / 10 + "%";
        tdSel.style.height = r.h_permille / 10 + "%";
      }

      // Redraw the on-canvas selection box for the active target (called on every drag frame).
      // (The numeric X/Y/W/H fields were removed — position/size is edited on the canvas.)
      function tdSyncLayout() {
        const r = tdActive();
        if (!r) return;
        tdDrawSel();
      }

      function tdSync() {
        if (!tdTheme) return;
        const isEl = tdActiveIsEl();
        // Toggle inspector mode: the region-only controls (alignment + text/typography) hide
        // when an element is selected; the element inspector shows instead. Theme background is
        // shared/always-visible. (Region selection is via the LAYERS list / canvas — there is
        // no Region picker; position/size is edited on the canvas — there is no numeric panel.)
        const showReg = (id) => {
          const el = document.getElementById(id);
          if (el) el.style.display = isEl ? "none" : "";
        };
        showReg("td-region-align");
        showReg("td-region-text");
        document.getElementById("td-el-inspector").hidden = !isEl;
        tdSyncHead(isEl); // Design 2.0 selection header (chip + name + subtext)
        tdLayers(); // Design 2.0 LAYERS panel (regions + elements, front→back)
        tdBgResync = true; // a full render snaps the bg type selector to the stored bg type
        tdSyncBg(); // theme background editor (solid / gradient / image, 86ajq3225)
        if (isEl) {
          tdSyncEl();
          tdSyncLayout();
          return;
        }
        tdSel.setAttribute("aria-label", "Selected region — drag to move, handles to resize");
        const r = tdTheme[tdRegion];
        document.getElementById("td-color").value = tdHex(r.color);
        // Design 2.0: SIZE is a % of height (size_permille/10), LINE a multiplier
        // (line_height_permille/1000) — number fields, not sliders.
        document.getElementById("td-size").value = (r.size_permille / 10).toFixed(1);
        document.getElementById("td-lh").value = (r.line_height_permille / 1000).toFixed(2);
        tdSeg("td-align", r.align_h, "a");
        tdSeg("td-valign", r.align_v, "v");
        tdSeg("td-fit", r.fit, "f");
        // Reflect the theme's font (86ajq6fxt); "" = the bundled default. If the theme's
        // font isn't installed on THIS machine, still show it (a "(not installed here)"
        // entry) so it is faithfully reflected + preserved, not silently blanked/cleared.
        tdEnsureFontOption(tdTheme.font);
        document.getElementById("td-font").value = tdTheme.font || "";
        // Reflect the theme-level weight + letter-spacing (86ajq3225); em = permille/1000.
        document.getElementById("td-weight").value = String(tdTheme.weight || 400);
        document.getElementById("td-letter").value = String((tdTheme.letter_spacing_permille || 0) / 1000);
        tdSyncLayout();
      }

      // Bind the element inspector (opacity / arrange / per-kind controls) from the selection.
      function tdSyncEl() {
        const el = tdActive();
        if (!el) return;
        // Reset the two-click delete arm on any selection change (never leak across elements).
        tdElDelArm = false;
        clearTimeout(tdElDelTimer);
        const delBtn = document.getElementById("td-el-del");
        if (delBtn) delBtn.textContent = "Delete element";
        // Reflect the selection class in the group's accessible name (was "Selected region").
        const kind = el.kind === "image" ? "image" : el.kind === "text" ? "text" : "shape";
        const kindLabel = kind === "image" ? "image" : kind === "text" ? "text" : "shape";
        tdSel.setAttribute(
          "aria-label",
          "Selected " + kindLabel + " element — drag to move, handles to resize",
        );
        const order = tdPaintOrder();
        const pos = order.indexOf(tdSelEl) + 1;
        const headKind = kind === "image" ? "Image" : kind === "text" ? "Text" : "Shape";
        document.getElementById("td-el-head").textContent =
          headKind + " — " + pos + " of " + tdEls().length;
        const front = tdZ(el) >= 0;
        const chip = document.getElementById("td-el-zchip");
        chip.textContent = front ? "In front of text" : "Behind text";
        chip.className = "td-chip " + (front ? "front" : "behind");
        const opPct = Math.round((tdOpacity(el) * 100) / 255);
        document.getElementById("td-el-op").value = opPct;
        document.getElementById("td-el-op-v").textContent = opPct;
        document.getElementById("td-el-shape").hidden = kind !== "shape";
        document.getElementById("td-el-image").hidden = kind !== "image";
        document.getElementById("td-el-text").hidden = kind !== "text";
        if (kind === "shape") {
          document.getElementById("td-el-fill").value = tdHex(el.fill || { r: 58, g: 65, b: 80 });
          document.getElementById("td-el-border").value = tdHex(el.border || { r: 0, g: 0, b: 0 });
          const bw = Number.isFinite(el.border_permille) ? el.border_permille : 0;
          document.getElementById("td-el-bw").value = bw;
          document.getElementById("td-el-bw-v").textContent = (bw / 10).toFixed(1);
          // Corner radius is meaningful only for a rounded rectangle (86ajtwq24).
          const variant = TD_SHAPE_LABELS[el.variant] ? el.variant : "rect";
          const cornerRow = document.getElementById("td-el-corner-row");
          cornerRow.hidden = variant !== "rounded_rect";
          if (variant === "rounded_rect") {
            const cp = Number.isFinite(el.corner_permille) ? el.corner_permille : 0;
            const cpPct = Math.round(cp / 10);
            document.getElementById("td-el-corner").value = cpPct;
            document.getElementById("td-el-corner-v").textContent = cpPct;
          }
          // Name the specific geometry in the head (e.g. "Ellipse — 2 of 3").
          document.getElementById("td-el-head").textContent =
            TD_SHAPE_LABELS[variant] + " — " + pos + " of " + tdEls().length;
        } else if (kind === "text") {
          document.getElementById("td-el-text-content").value = el.text || "";
          document.getElementById("td-el-text-color").value = tdHex(el.color || { r: 255, g: 255, b: 255 });
          const sz = Number.isFinite(el.size_permille) ? el.size_permille : 80;
          document.getElementById("td-el-text-size").value = Math.round(sz / 10);
          document.getElementById("td-el-text-size-v").textContent = Math.round(sz / 10);
          document.getElementById("td-el-text-align").value = el.align_h || "center";
        } else {
          document.getElementById("td-el-src").textContent = el.source || "(no file chosen)";
        }
      }

      // --- Design 2.0 inspector header + LAYERS panel (Figma 317:124 / 325:189) ---
      // Selection header: a type chip + the selected region/element name + a subtext line.
      function tdSyncHead(isEl) {
        const title = document.getElementById("td-insp-title");
        const sub = document.getElementById("td-insp-sub");
        const chip = document.getElementById("td-insp-chip");
        if (!title || !sub || !chip) return;
        if (isEl) {
          const el = tdActive();
          const kind = el && el.kind === "image" ? "Image" : el && el.kind === "text" ? "Text" : "Shape";
          title.textContent =
            el && el.kind === "shape" ? (TD_SHAPE_LABELS[el.variant] || "Shape") : kind;
          sub.textContent = kind + " element · selected on canvas";
          chip.textContent = kind === "Image" ? "🖼" : kind === "Text" ? "T" : "●";
        } else {
          title.textContent = tdRegion === "title" ? "Reference / Title" : "Body";
          sub.textContent = "Text region · selected on canvas";
          chip.textContent = "T";
        }
      }

      // A single LAYERS row descriptor: a region (pinned at the text layer) or an element.
      // Effective z orders the list front→back: an element's z; regions sit at the text
      // boundary (body just above title, both between the behind/front element passes).
      function tdLayerRows() {
        const rows = [];
        tdEls().forEach((el, i) => rows.push({ kind: "el", i, ez: tdZ(el) }));
        if (tdTheme && tdTheme.title) rows.push({ kind: "region", region: "title", ez: -0.5 });
        if (tdTheme && tdTheme.body) rows.push({ kind: "region", region: "body", ez: -0.4 });
        // Descending effective z = topmost first; a stable tie-break keeps insertion order.
        // Descending effective z = topmost first. Tie-break DESCENDING insertion index so it
        // matches compose_slide's paint order (a stable sort by z, then list index → the
        // LATER element paints last = in FRONT); ascending would invert equal-z elements.
        return rows.map((r, k) => ({ r, k })).sort((a, b) => b.r.ez - a.r.ez || b.k - a.k).map((x) => x.r);
      }

      function tdSelectLayer(r) {
        if (r.kind === "el") tdSelEl = r.i;
        else { tdSelEl = -1; tdRegion = r.region; }
        tdSync();
        tdPreview();
        // Announce the selection (the LAYERS list is a keyboard/SR selection surface — mirror
        // the canvas-click announcements so keyboard selection isn't silent).
        if (r.kind === "el") {
          const el = tdEls()[r.i];
          tdAnnounce((el ? tdElLabel(el) : "Element") + " selected");
        } else {
          tdAnnounce((r.region === "title" ? "Reference / Title" : "Body") + " region selected");
        }
      }

      // Toggle a layer's visibility (real: honored by the host compositor). An element omits
      // the field when shown (byte-stable JSON); a region always carries `visible`.
      function tdToggleVisible(r) {
        if (!tdTheme) return;
        if (r.kind === "el") {
          const el = tdEls()[r.i];
          if (!el) return;
          if (tdVisible(el)) el.visible = false;
          else delete el.visible;
        } else {
          const reg = tdTheme[r.region];
          reg.visible = !(reg.visible !== false);
        }
        tdSync(); // rebuilds the LAYERS panel + inspector (a hidden region hides its sel box)
        tdPreview();
      }

      // Visual drag-reorder for the Layers panel (elements only; the text regions are pinned).
      // Pointer-based — WKWebView has no reliable native HTML5 DnD. The grabbed row LIFTS out of
      // flow and follows the pointer; a placeholder holds the drop slot and the other rows part
      // around it; on release the element z-values are reassigned to the new front→back order,
      // preserving each element's side of the text layer (front = z>0, behind = z<0).
      let tdLayerDrag = null;
      function tdLayerDragStart(ev, idx) {
        if (ev.button !== undefined && ev.button !== 0) return;
        const box = document.getElementById("td-layers");
        const row = ev.target && ev.target.closest(".td-layer");
        if (!box || !row) return;
        ev.preventDefault();
        const rect = row.getBoundingClientRect();
        // A placeholder holds the row's slot while the row is lifted out of flow.
        const ph = document.createElement("div");
        ph.className = "td-layer-placeholder";
        ph.style.height = rect.height + "px";
        box.insertBefore(ph, row);
        // Lift the row: fixed to the viewport so it tracks the pointer; keep its width/left.
        const grabDy = ev.clientY - rect.top;
        row.classList.add("dragging");
        row.style.position = "fixed";
        row.style.left = rect.left + "px";
        row.style.width = rect.width + "px";
        row.style.top = rect.top + "px";
        tdLayerDrag = { idx, box, row, ph, grabDy };
        box.classList.add("td-layers-dragging");
        window.addEventListener("pointermove", tdLayerDragMove);
        // pointerup COMMITS the reorder; pointercancel (WKWebView gesture takeover / palm-reject
        // / release outside the WebView — which never fires pointerup) REVERTS it with no z change
        // and stops the leaked drag.
        window.addEventListener("pointerup", tdLayerDragCommit);
        window.addEventListener("pointercancel", tdLayerDragCancel);
      }
      function tdLayerDragMove(ev) {
        const D = tdLayerDrag;
        if (!D) return;
        D.row.style.top = ev.clientY - D.grabDy + "px";
        // Auto-scroll when dragging near the top/bottom edge of an overflowing list.
        const br = D.box.getBoundingClientRect();
        if (ev.clientY < br.top + 24) D.box.scrollTop -= 8;
        else if (ev.clientY > br.bottom - 24) D.box.scrollTop += 8;
        // Move the placeholder to the gap under the pointer (skip the lifted row + placeholder).
        const kids = Array.from(D.box.children).filter((c) => c !== D.row && c !== D.ph);
        let ref = null;
        for (const c of kids) {
          const r = c.getBoundingClientRect();
          if (ev.clientY < r.top + r.height / 2) { ref = c; break; }
        }
        if (ref) D.box.insertBefore(D.ph, ref);
        else D.box.appendChild(D.ph);
      }
      // Detach listeners + drag state (idempotent — pointerup/pointercancel may both fire).
      function tdLayerTeardown() {
        const D = tdLayerDrag;
        tdLayerDrag = null;
        window.removeEventListener("pointermove", tdLayerDragMove);
        window.removeEventListener("pointerup", tdLayerDragCommit);
        window.removeEventListener("pointercancel", tdLayerDragCancel);
        if (D) D.box.classList.remove("td-layers-dragging");
        return D;
      }
      // Cancel: discard the drag with NO z change — drop the lifted styles + placeholder and
      // rebuild the original order (a WKWebView-cancelled gesture must never reorder).
      function tdLayerDragCancel() {
        const D = tdLayerTeardown();
        if (!D) return;
        if (D.ph.parentNode) D.ph.parentNode.removeChild(D.ph);
        D.row.classList.remove("dragging");
        D.row.removeAttribute("style");
        tdLayers();
      }
      // Commit: apply the drop — reassign element z to the new front→back order.
      function tdLayerDragCommit() {
        const D = tdLayerTeardown();
        if (!D) return;
        // Read the new front→back order from the DOM — the placeholder marks the dragged
        // element's slot; region rows mark the text layer.
        const order = [];
        Array.from(D.box.children).forEach((c) => {
          if (c === D.row) return; // the lifted original — its real slot is the placeholder
          if (c === D.ph) order.push({ el: D.idx });
          else if (c.dataset.idx !== undefined) order.push({ el: Number(c.dataset.idx) });
          else if (c.dataset.region) order.push({ region: true });
        });
        // Reassign z: elements ABOVE the first text region get descending positive z (front),
        // those BELOW get descending negative z (behind) — distinct integers, order preserved,
        // the elements array itself is never reordered (mirrors tdArrange's z-only model).
        const els = tdEls();
        const firstRegion = order.findIndex((o) => o.region);
        let front = order.filter((o, i) => o.el !== undefined && (firstRegion === -1 || i < firstRegion)).length;
        let back = 0;
        order.forEach((o, i) => {
          if (o.el === undefined || !els[o.el]) return;
          if (firstRegion === -1 || i < firstRegion) { els[o.el].z = front; front -= 1; }
          else { back -= 1; els[o.el].z = back; }
        });
        if (D.ph.parentNode) D.ph.parentNode.removeChild(D.ph);
        D.row.classList.remove("dragging");
        D.row.removeAttribute("style");
        tdSelEl = D.idx; // keep the moved element selected (its array index is unchanged)
        tdSync(); // rebuilds the Layers list in the new order + refreshes the inspector
        tdPreview();
        const npos = tdPaintOrder().indexOf(D.idx) + 1;
        tdAnnounce("Reordered — layer " + npos + " of " + els.length);
      }

      // Build one LAYERS row element.
      function tdLayerRow(r) {
        const row = document.createElement("div");
        row.className = "td-layer";
        row.setAttribute("role", "listitem");
        row.tabIndex = 0;
        const isEl = r.kind === "el";
        const selected = isEl
          ? tdActiveIsEl() && tdSelEl === r.i
          : !tdActiveIsEl() && tdRegion === r.region;
        if (selected) row.classList.add("sel");
        // Expose the selection to assistive tech (not colour-only) — aria-current is valid on a
        // role=listitem. The LAYERS list is the only keyboard/SR way to pick a region/element.
        if (selected) row.setAttribute("aria-current", "true");
        // The row being pointer-dragged shows the dimmed .dragging affordance.
        if (isEl && tdLayerDrag && tdLayerDrag.idx === r.i) row.classList.add("dragging");
        let visible, name, meta, glyph;
        if (isEl) {
          const el = tdEls()[r.i];
          visible = tdVisible(el);
          glyph = el.kind === "image" ? "🖼" : el.kind === "text" ? "T" : "●";
          name =
            el.kind === "text"
              ? (el.text ? el.text.split("\n")[0].slice(0, 24).trim() || "Text" : "Text")
              : el.kind === "image"
                ? "Image"
                : (TD_SHAPE_LABELS[el.variant] || "Shape");
          meta = tdElLabel(el) + " · z" + tdZ(el);
        } else {
          const reg = tdTheme[r.region];
          visible = reg.visible !== false;
          glyph = "T";
          name = r.region === "title" ? "Reference / Title" : "Body";
          meta = "Region";
        }
        if (!visible) row.classList.add("layer-hidden");
        row.setAttribute("aria-label", name + " — " + meta + (visible ? "" : " (hidden)") + (selected ? " (selected)" : ""));

        const handle = document.createElement("span");
        handle.className = "td-layer-handle";
        handle.textContent = "⋮⋮";
        handle.setAttribute("aria-hidden", "true");
        if (isEl) handle.addEventListener("pointerdown", (ev) => tdLayerDragStart(ev, r.i));
        else handle.setAttribute("aria-disabled", "true");

        const ico = document.createElement("span");
        ico.className = "td-layer-ico";
        ico.textContent = glyph;
        ico.setAttribute("aria-hidden", "true");

        const body = document.createElement("div");
        body.className = "td-layer-body";
        const nm = document.createElement("span");
        nm.className = "td-layer-name";
        nm.textContent = name;
        const mt = document.createElement("span");
        mt.className = "td-layer-meta";
        mt.textContent = meta;
        body.appendChild(nm);
        body.appendChild(mt);

        const eye = document.createElement("button");
        eye.className = "td-layer-eye";
        eye.type = "button";
        eye.textContent = visible ? "👁" : "🚫";
        eye.setAttribute("aria-pressed", visible ? "true" : "false");
        eye.setAttribute("aria-label", (visible ? "Hide " : "Show ") + name);
        eye.title = visible ? "Hide layer" : "Show layer";
        eye.onclick = (ev) => {
          ev.stopPropagation();
          tdToggleVisible(r);
        };

        row.onclick = () => tdSelectLayer(r);
        row.onkeydown = (ev) => {
          // Only handle keys that originate ON the row itself — a keydown from the child eye
          // <button> must reach the button's native Enter/Space activation (toggle visibility)
          // and must NOT be preventDefault-ed into a row selection (keyboard/pointer parity).
          if (ev.target !== row) return;
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            tdSelectLayer(r);
          } else if (isEl && ev.altKey && (ev.key === "ArrowUp" || ev.key === "ArrowDown")) {
            ev.preventDefault();
            tdSelEl = r.i;
            tdArrange(ev.key === "ArrowUp" ? "forward" : "backward");
          }
        };

        row.dataset.kind = r.kind;
        if (isEl) row.dataset.idx = String(r.i);
        else row.dataset.region = r.region;
        row.appendChild(handle);
        row.appendChild(ico);
        row.appendChild(body);
        row.appendChild(eye);
        return row;
      }

      function tdLayers() {
        const box = document.getElementById("td-layers");
        if (!box || !tdTheme) return;
        // Preserve keyboard focus across the innerHTML rebuild (a11y — mirrors the Screens
        // registry pattern). A keyboard reorder (Alt+↑/↓) or an eye toggle rebuilds every row,
        // destroying the focused node; without this the focus falls to <body> and repeated
        // keyboard reordering is unusable. The stable data-* attrs re-identify the row.
        const active = document.activeElement;
        let refocus = null;
        if (active && box.contains(active)) {
          const rowEl = active.closest(".td-layer");
          if (rowEl) {
            refocus = {
              sel: rowEl.dataset.idx !== undefined
                ? '.td-layer[data-idx="' + rowEl.dataset.idx + '"]'
                : rowEl.dataset.region
                  ? '.td-layer[data-region="' + rowEl.dataset.region + '"]'
                  : null,
              onEye: active.classList.contains("td-layer-eye"),
            };
          }
        }
        box.innerHTML = "";
        tdLayerRows().forEach((r) => box.appendChild(tdLayerRow(r)));
        if (refocus && refocus.sel) {
          const row = box.querySelector(refocus.sel);
          if (row) (refocus.onEye ? row.querySelector(".td-layer-eye") : row).focus();
        }
      }

      let tdTimer = null;
      function tdPreview() {
        if (!tdTheme) return;
        clearTimeout(tdTimer);
        tdTimer = setTimeout(async () => {
          try {
            const p = await invoke("preview_theme", { themeJson: JSON.stringify(tdTheme) });
            const bytes = b64ToBytes(p.rgba); // tight decode (audit M5)
            tdCanvas.width = p.w; tdCanvas.height = p.h;
            tdCtx.putImageData(new ImageData(new Uint8ClampedArray(bytes), p.w, p.h), 0, 0);
          } catch (e) { console.error(e); }
        }, 120);
      }

      // Apply a rect patch to the ACTIVE target (region or element), clamped to the frame
      // (0..1000) with a minimum size so it can never invert or leave the canvas.
      function tdSetRect(patch) {
        const r = tdActive();
        if (!r) return;
        Object.assign(r, patch);
        r.w_permille = tdClamp(Math.round(r.w_permille), 20, 1000);
        r.h_permille = tdClamp(Math.round(r.h_permille), 20, 1000);
        r.x_permille = tdClamp(Math.round(r.x_permille), 0, 1000 - r.w_permille);
        r.y_permille = tdClamp(Math.round(r.y_permille), 0, 1000 - r.h_permille);
      }

      // Per-theme font family (86ajq6fxt): "" = the bundled default (drop the field so
      // the theme JSON stays byte-stable); a name = a system font on this machine.
      document.getElementById("td-font").onchange = (e) => {
        if (!tdTheme) return;
        const fam = e.target.value;
        if (fam) tdTheme.font = fam; else delete tdTheme.font;
        tdPreview();
      };
      // Theme-level font weight (86ajq3225): 400 (Regular) = the default, dropped from the
      // JSON so it stays byte-stable; a heavier weight is a real bold face (system font) or a
      // deterministic faux-bold (bundled default).
      document.getElementById("td-weight").onchange = (e) => {
        if (!tdTheme) return;
        const w = +e.target.value || 400;
        if (w === 400) delete tdTheme.weight; else tdTheme.weight = w;
        tdPreview();
      };
      // Letter-spacing in em → per-mille of the font size (bounded); 0 = none (dropped).
      document.getElementById("td-letter").onchange = (e) => {
        if (!tdTheme) return;
        const em = Number(e.target.value);
        const permille = Number.isFinite(em)
          ? Math.round(Math.max(-0.2, Math.min(1, em)) * 1000)
          : 0;
        if (permille === 0) delete tdTheme.letter_spacing_permille;
        else tdTheme.letter_spacing_permille = permille;
        tdPreview();
      };
      // --- Theme background editor (86ajq3225): solid colour / gradient / image ---
      // The background is an untagged shape: {r,g,b,a} solid, {from,to,direction} gradient,
      // or {source} image. `tdBgType` discriminates by the present fields.
      let tdBgResync = true; // when true, tdSyncBg snaps the type selector to the stored bg type
      let tdBgSel = "solid"; // the bg TYPE segment currently shown (UI state; may lead the stored bg for "image")
      function tdBgType(bg) {
        if (bg && typeof bg === "object") {
          if (typeof bg.source !== "undefined") return "image";
          if (bg.from && bg.to) return "gradient";
        }
        return "solid";
      }
      // The selector value is the user's chosen type (the UI intent); the STORED background is
      // only ever a VALID Background. Switching to Image shows the image panel but does NOT
      // write a malformed {source:""} (the host rejects an empty MediaRef, breaking preview +
      // save) — the background becomes an image only when a real source is picked/typed. On a
      // full designer render, tdBgResync snaps the selector back to the stored type.
      function tdSyncBg() {
        if (!tdTheme) return;
        const bg = tdTheme.background || { r: 0, g: 0, b: 0, a: 255 };
        const stored = tdBgType(bg);
        // Design 2.0: the bg TYPE is a segmented control (Solid/Gradient/Image), not a select.
        // A full designer render snaps the shown segment back to the stored bg type.
        if (tdBgResync) { tdBgSel = stored; tdBgResync = false; }
        const type = tdBgSel;
        tdSeg("td-bg-type", type, "bg"); // reflect the active segment (on + aria-pressed)
        document.getElementById("td-bg-solid").hidden = type !== "solid";
        document.getElementById("td-bg-gradient").hidden = type !== "gradient";
        document.getElementById("td-bg-image").hidden = type !== "image";
        if (type === "solid") {
          document.getElementById("td-bg").value = tdHex(stored === "solid" ? bg : { r: 0, g: 0, b: 0 });
        } else if (type === "gradient") {
          const g = stored === "gradient" ? bg : { from: { r: 0, g: 0, b: 0 }, to: { r: 255, g: 255, b: 255 }, direction: "vertical" };
          document.getElementById("td-bg-from").value = tdHex(g.from);
          document.getElementById("td-bg-to").value = tdHex(g.to);
          document.getElementById("td-bg-dir").value = g.direction || "vertical";
        } else {
          const src = stored === "image" ? (bg.source || "") : "";
          document.getElementById("td-bg-img-path").value = src;
          document.getElementById("td-bg-img-src").textContent =
            src ? ("Using: " + src) : "Pick or type an image path to use it as the background.";
        }
        tdBgReflect();
      }
      // Direction → CSS gradient keyword (matches the host compositor's interpretation).
      function tdGradCss(from, to, dir) {
        const d = { vertical: "to bottom", horizontal: "to right", diagonal_down: "to bottom right", diagonal_up: "to top right" }[dir] || "to bottom";
        return "linear-gradient(" + d + ", " + tdHex(from) + ", " + tdHex(to) + ")";
      }
      // Update the Design 2.0 background PREVIEWS (hex readouts + colour dot, the live gradient
      // bar, the image drop-zone state) from the current tdTheme.background. Called by tdSyncBg
      // and live during colour drags so the previews track without a full designer re-render.
      function tdBgReflect() {
        if (!tdTheme) return;
        const bg = tdTheme.background || { r: 0, g: 0, b: 0, a: 255 };
        const stored = tdBgType(bg);
        const solid = stored === "solid" ? bg : (stored === "gradient" ? bg.from : { r: 0, g: 0, b: 0 });
        const solidHex = tdHex(solid).toUpperCase();
        const hx = document.getElementById("td-bg-hex"); if (hx) hx.textContent = solidHex;
        const dot = document.getElementById("td-bg-hex-dot"); if (dot) dot.style.background = solidHex;
        if (stored === "gradient") {
          const fh = document.getElementById("td-bg-from-hex"); if (fh) fh.textContent = tdHex(bg.from).toUpperCase();
          const th = document.getElementById("td-bg-to-hex"); if (th) th.textContent = tdHex(bg.to).toUpperCase();
          const gp = document.getElementById("td-bg-grad-preview"); if (gp) gp.style.background = tdGradCss(bg.from, bg.to, bg.direction);
        }
        const src = stored === "image" ? (bg.source || "") : "";
        const dz = document.getElementById("td-bg-dropzone"); if (dz) dz.classList.toggle("has-image", !!src);
        const dzt = document.getElementById("td-bg-dz-t");
        if (dzt) dzt.textContent = src ? "Image set — click to replace" : "Choose a background image";
      }
      // Commit an image background from a validated, NON-EMPTY path; an empty path leaves the
      // current (valid) background unchanged — so the theme is never malformed.
      function tdCommitBgImage(path) {
        if (!tdTheme) return;
        path = (path || "").trim();
        if (!path) return;
        if (path.indexOf("\0") !== -1 || tdNameBytes(path) > 1024) { tdStatus("That image path is not valid."); return; }
        tdTheme.background = { source: path };
        tdSyncBg();
        tdPreview();
      }
      // Background TYPE segmented control (Design 2.0): each segment shows its panel; Solid /
      // Gradient commit immediately, Image defers until a real source is chosen (no {source:""}).
      document.querySelectorAll("#td-bg-type button").forEach((b) => (b.onclick = () => {
        if (!tdTheme) return;
        const val = b.dataset.bg;
        tdBgSel = val;
        const cur = tdTheme.background;
        const curType = tdBgType(cur);
        const solid = curType === "solid" ? cur : (curType === "gradient" ? cur.from : { r: 0, g: 0, b: 0, a: 255 });
        if (val === "gradient") {
          tdTheme.background = { from: solid, to: { r: 255, g: 255, b: 255, a: 255 }, direction: "vertical" };
          tdPreview();
        } else if (val === "solid") {
          tdTheme.background = solid;
          tdPreview();
        }
        tdSyncBg();
      }));
      document.getElementById("td-bg").oninput = (e) => { if (tdTheme) { tdTheme.background = tdRgb(e.target.value); tdPreview(); tdBgReflect(); } };
      document.getElementById("td-bg-from").oninput = (e) => { if (tdTheme && tdBgType(tdTheme.background) === "gradient") { tdTheme.background.from = tdRgb(e.target.value); tdPreview(); tdBgReflect(); } };
      document.getElementById("td-bg-to").oninput = (e) => { if (tdTheme && tdBgType(tdTheme.background) === "gradient") { tdTheme.background.to = tdRgb(e.target.value); tdPreview(); tdBgReflect(); } };
      document.getElementById("td-bg-dir").onchange = (e) => { if (tdTheme && tdBgType(tdTheme.background) === "gradient") { tdTheme.background.direction = e.target.value; tdPreview(); tdBgReflect(); } };
      // Preset swatches (Solid): one tap sets the background colour + snaps to the Solid segment.
      document.querySelectorAll("#td-bg-presets button").forEach((b) => (b.onclick = () => {
        if (!tdTheme) return;
        tdBgSel = "solid";
        tdTheme.background = tdRgb(b.dataset.color);
        tdSyncBg();
        tdPreview();
      }));
      document.getElementById("td-bg-img-path").onchange = (e) => { tdCommitBgImage(e.target.value); };
      // The native picker (FR-138 seam). Shared by the "Choose image…" button AND the drop-zone
      // card — clicking either opens the OS picker; a WKWebView with no dialog falls back to the
      // paste-a-path field. (HTML5 file-drop is unreliable in WKWebView, so the card is click-only.)
      async function tdPickBgImage() {
        if (!tdTheme) { tdStatus("Load or start a theme first."); return; }
        let path;
        try { path = await invoke("pick_image"); }
        catch (e) { tdStatus("No native picker — paste the image path in the field below."); document.getElementById("td-bg-img-path").focus(); return; }
        if (!path) return; // cancelled
        document.getElementById("td-bg-img-path").value = path;
        tdCommitBgImage(path);
        tdAnnounce("Background image set");
      }
      document.getElementById("td-bg-img-pick").onclick = tdPickBgImage;
      const tdDropzone = document.getElementById("td-bg-dropzone");
      if (tdDropzone) tdDropzone.onclick = tdPickBgImage;
      document.getElementById("td-color").oninput = (e) => { if (!tdTheme) return; tdTheme[tdRegion].color = tdRgb(e.target.value); tdPreview(); };
      // SIZE % → size_permille (×10); LINE multiplier → line_height_permille (×1000). Bounded to
      // the field's range. A BLANK or non-numeric field is ignored (no commit) so clearing it to
      // retype can't snap the theme to the min (Number("") is 0 — guard the raw string). `change`
      // (blur/Enter) repopulates the field from the clamped model so the shown number always
      // matches what's applied (mirrors the X/Y/W/H rect fields).
      const tdSizeInput = document.getElementById("td-size");
      const tdLhInput = document.getElementById("td-lh");
      tdSizeInput.oninput = (e) => { if (!tdTheme) return; const s = e.target.value.trim(); if (s === "") return; const pct = Number(s); if (!Number.isFinite(pct)) return; tdTheme[tdRegion].size_permille = tdClamp(Math.round(pct * 10), 20, 140); tdPreview(); };
      tdSizeInput.onchange = () => { if (tdTheme) tdSizeInput.value = (tdTheme[tdRegion].size_permille / 10).toFixed(1); };
      tdLhInput.oninput = (e) => { if (!tdTheme) return; const s = e.target.value.trim(); if (s === "") return; const mult = Number(s); if (!Number.isFinite(mult)) return; tdTheme[tdRegion].line_height_permille = tdClamp(Math.round(mult * 1000), 1000, 1600); tdPreview(); };
      tdLhInput.onchange = () => { if (tdTheme) tdLhInput.value = (tdTheme[tdRegion].line_height_permille / 1000).toFixed(2); };
      // (The numeric X/Y/W/H fields + Lock aspect were removed — position/size is edited with
      // the on-canvas move/resize handles.)
      // (The explicit Region picker was removed — a region is selected via the LAYERS rows or by
      // clicking its text on the canvas, both of which set tdRegion + tdSelEl=-1.)
      document.querySelectorAll("#td-align button").forEach((b) => (b.onclick = () => { if (!tdTheme) return; tdTheme[tdRegion].align_h = b.dataset.a; tdSeg("td-align", b.dataset.a, "a"); tdPreview(); }));
      document.querySelectorAll("#td-valign button").forEach((b) => (b.onclick = () => { if (!tdTheme) return; tdTheme[tdRegion].align_v = b.dataset.v; tdSeg("td-valign", b.dataset.v, "v"); tdPreview(); }));
      document.querySelectorAll("#td-fit button").forEach((b) => (b.onclick = () => { if (!tdTheme) return; tdTheme[tdRegion].fit = b.dataset.f; tdSeg("td-fit", b.dataset.f, "f"); tdPreview(); }));

      // --- On-canvas drag (move) + resize (handles). Pointer deltas map to per-mille
      // via the canvas-box size; the rect is clamped to the frame. Pointer capture is
      // on the selection box, so a drag that starts on a handle still tracks. ---
      let tdDrag = null;
      function tdPointerDown(e) {
        if (!tdTheme || e.button !== 0) return; // primary button only (right-click → context menu)
        if (!tdMenu.hidden) { tdCloseCtx(); return; } // a click dismisses the open menu — nothing else
        // Re-hit-test on pointerdown (#3): the topmost element under the cursor may differ from
        // the current selection because the selection box overlays the canvas — select it so
        // clicking an element BENEATH the box (e.g. under the large Body region) works. Skip when
        // grabbing a resize handle. EXCEPTION: keep a selected ELEMENT when the grab is inside its
        // own rect (a sticky grab-to-move, so an overlapping element can't steal the drag); a
        // region always re-hit-tests (so clicking an element over it still selects the element).
        if (!e.target.dataset.h) {
          const grabbingCurrent = tdActiveIsEl() && tdPointInRect(e.clientX, e.clientY, tdActive());
          if (!grabbingCurrent) {
            const hit = tdHitTest(e.clientX, e.clientY);
            if (hit >= 0 && hit !== tdSelEl) {
              tdSelEl = hit;
              tdSync();
              tdAnnounce(tdElLabel(tdEls()[hit]) + " selected");
            }
          }
        }
        const r = tdActive();
        if (!r) return;
        const box = tdBox.getBoundingClientRect();
        tdDrag = {
          handle: e.target.dataset.h || null, // a resize handle, or null = move
          sx: e.clientX, sy: e.clientY, bw: box.width || 1, bh: box.height || 1,
          x: r.x_permille, y: r.y_permille, w: r.w_permille, h: r.h_permille,
        };
        try { tdSel.setPointerCapture(e.pointerId); } catch (_) {} // WKWebView pointer quirk-safe
        e.preventDefault();
      }
      function tdPointerMove(e) {
        if (!tdDrag) return;
        const dxp = ((e.clientX - tdDrag.sx) / tdDrag.bw) * 1000;
        const dyp = ((e.clientY - tdDrag.sy) / tdDrag.bh) * 1000;
        const hh = tdDrag.handle;
        if (!hh) {
          // Move: keep the size, clamp the origin into the frame.
          tdSetRect({ x_permille: tdDrag.x + dxp, y_permille: tdDrag.y + dyp });
        } else {
          // Resize: move ONLY the dragged edge(s). The opposite edge stays anchored, and
          // the dragged edge stops at the frame / a 20‰ minimum — it never jumps the anchor.
          const MIN = 20;
          let left = tdDrag.x, top = tdDrag.y, right = tdDrag.x + tdDrag.w, bottom = tdDrag.y + tdDrag.h;
          if (hh.includes("e")) right = tdClamp(right + dxp, left + MIN, 1000);
          if (hh.includes("w")) left = tdClamp(left + dxp, 0, right - MIN);
          if (hh.includes("s")) bottom = tdClamp(bottom + dyp, top + MIN, 1000);
          if (hh.includes("n")) top = tdClamp(top + dyp, 0, bottom - MIN);
          // Lock aspect (only if the optional checkbox exists — it was removed from the
          // streamlined inspector, so resize is free by default): constrain the height to the
          // region's original w:h ratio, re-anchored on the dragged edge + clamped to the frame.
          const tdLockEl = document.getElementById("td-lock");
          if (tdLockEl && tdLockEl.checked && tdDrag.h > 0) {
            const aspect = tdDrag.w / tdDrag.h;
            const newH = (right - left) / aspect;
            if (hh.includes("n")) top = bottom - newH;
            else bottom = top + newH;
            top = Math.max(0, top);
            bottom = Math.min(1000, bottom);
            const w2 = (bottom - top) * aspect;
            if (hh.includes("w")) left = right - w2;
            else right = left + w2;
            left = Math.max(0, left);
            right = Math.min(1000, right);
          }
          const r = tdActive();
          r.x_permille = Math.round(left);
          r.y_permille = Math.round(top);
          r.w_permille = Math.round(right - left);
          r.h_permille = Math.round(bottom - top);
        }
        tdSyncLayout();
        tdPreview();
      }
      function tdPointerUp(e) {
        if (!tdDrag) return;
        try { tdSel.releasePointerCapture(e.pointerId); } catch (_) {}
        tdDrag = null;
      }
      tdSel.addEventListener("pointerdown", tdPointerDown);
      tdSel.addEventListener("pointermove", tdPointerMove);
      tdSel.addEventListener("pointerup", tdPointerUp);
      // A cancelled pointer (touch palm-reject / OS gesture / interrupted mouse) releases
      // capture WITHOUT a pointerup — clear the drag so a later hover can't move the region.
      tdSel.addEventListener("pointercancel", tdPointerUp);
      // Keyboard-operable (a11y): arrows nudge the region; Shift+arrows resize (1% steps),
      // anchored at the origin so a resize at the frame edge doesn't shift the top-left.
      tdSel.addEventListener("keydown", (e) => {
        if (!tdTheme) return;
        // Escape deselects an element back to region editing (keyboard path). Focus returns to
        // the active region's LAYERS row (the Region picker was removed; regions are selected
        // via the LAYERS list / canvas), so a keyboard user lands on a sensible control.
        if (e.key === "Escape" && tdActiveIsEl()) {
          e.preventDefault();
          tdSelEl = -1;
          tdSync();
          const rb = document.querySelector('#td-layers .td-layer[data-region="' + tdRegion + '"]');
          if (rb) rb.focus();
          tdAnnounce("Deselected — editing regions");
          return;
        }
        // Arrange (element only): Cmd/Ctrl+] forward / [ backward, +Shift = front/back.
        if ((e.metaKey || e.ctrlKey) && (e.key === "]" || e.key === "[")) {
          if (tdActiveIsEl()) {
            e.preventDefault();
            const fwd = e.key === "]";
            tdArrange(e.shiftKey ? (fwd ? "front" : "back") : fwd ? "forward" : "backward");
          }
          return;
        }
        // Delete the selected element.
        if ((e.key === "Delete" || e.key === "Backspace") && tdActiveIsEl()) {
          e.preventDefault();
          tdDeleteEl();
          return;
        }
        const d = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] }[e.key];
        if (!d) return;
        e.preventDefault();
        const r = tdActive();
        if (!r) return;
        if (e.shiftKey) {
          r.w_permille = tdClamp(r.w_permille + d[0], 20, 1000 - r.x_permille);
          r.h_permille = tdClamp(r.h_permille + d[1], 20, 1000 - r.y_permille);
        } else {
          tdSetRect({ x_permille: r.x_permille + d[0], y_permille: r.y_permille + d[1] });
        }
        tdSyncLayout();
        tdPreview();
      });

      // Click-to-select an element: pointerdown on the canvas box (NOT on the selection box,
      // which handles its own drag) hit-tests the element rects in FRONT-to-back paint order.
      tdBox.addEventListener("pointerdown", (e) => {
        if (!tdTheme || e.button !== 0 || tdSel.contains(e.target)) return; // primary button; on-box → tdPointerDown
        if (!tdMenu.hidden) { tdCloseCtx(); return; } // a click dismisses the open menu — nothing else
        const hit = tdHitTest(e.clientX, e.clientY);
        if (hit >= 0) {
          tdSelEl = hit;
          tdSync();
          tdSel.focus();
          const el = tdEls()[hit];
          // Start dragging the newly-selected element in the SAME gesture (grab-and-move).
          const box = tdBox.getBoundingClientRect();
          tdDrag = {
            handle: null,
            sx: e.clientX, sy: e.clientY, bw: box.width || 1, bh: box.height || 1,
            x: el.x_permille, y: el.y_permille, w: el.w_permille, h: el.h_permille,
          };
          try { tdSel.setPointerCapture(e.pointerId); } catch (_) {}
          const front = tdZ(el) >= 0;
          tdAnnounce(
            tdElLabel(el) +
              " selected, " + (front ? "in front of" : "behind") + " the text",
          );
          return;
        }
        // No element hit → clicking the Body or Reference/Title text on the canvas selects
        // that region automatically (so you can edit what you clicked).
        const reg = tdRegionAt(e.clientX, e.clientY);
        if (reg) {
          if (tdActiveIsEl() || tdRegion !== reg) {
            tdSelEl = -1;
            tdRegion = reg;
            tdSync();
            tdAnnounce((reg === "title" ? "Reference / Title" : "Body") + " region selected");
          }
          return;
        }
        // Clicked truly empty canvas while an element was selected → deselect back to region
        // editing, so the Body/Reference region controls are reachable again.
        if (tdActiveIsEl()) {
          tdSelEl = -1;
          tdSync();
          tdAnnounce("Deselected — editing regions");
        }
      });

      const tdStatus = (msg) => { document.getElementById("td-status").textContent = msg; };
      // The host caps a theme name at 64 BYTES (MAX_THEME_NAME_LEN, UTF-8), not chars —
      // so a short non-Latin name can still be rejected. Measure bytes to agree exactly.
      const TD_NAME_MAX_BYTES = 64;
      const tdNameBytes = (s) => {
        try { return new TextEncoder().encode(s).length; }
        catch (e) { return unescape(encodeURIComponent(s)).length; } // WKWebView fallback
      };
      const tdNew = () => { tdSelected = ""; tdSelectedKind = ""; tdList(); tdStatus("Editing a new theme from the current values."); };
      // The Design 2.0 topbar drops the old header "New" (Duplicate + the strip's "New from
      // current" cover it) — guard the legacy #td-new binding so a missing node can't abort boot.
      const tdNewBtn = document.getElementById("td-new");
      if (tdNewBtn) tdNewBtn.onclick = tdNew;
      document.getElementById("td-new-2").onclick = tdNew;
      // Honest 'later' affordances (design fidelity, no fake success): importing /
      // exporting a theme FILE is deferred; the in-app library (Save changes) is live.
      document.getElementById("td-import").onclick = () => tdStatus("Importing a theme file is a later increment; save named themes in the library for now.");
      document.getElementById("td-export").onclick = () => tdStatus("Exporting a theme file is a later increment; save named themes in the library for now.");
      document.getElementById("td-tab-slides").onclick = () => tdStatus("Slide (non-scripture) templates arrive in a later increment; scripture templates are shown now.");

      // Save changes → name the current design into the library (86ajq4xmy). An inline
      // name form (no window.prompt, which WKWebView blocks); Enter saves, Esc cancels.
      const tdSaveRow = document.getElementById("td-save-row");
      const tdSaveName = document.getElementById("td-save-name");
      const tdCloseSaveRow = () => {
        tdSaveRow.hidden = true;
        tdSaveName.value = "";
      };
      const tdOpenSaveRow = () => {
        if (!tdTheme) { tdStatus("Nothing to save yet."); return; }
        // The save form lives inside the collapsible Templates panel — expand it first, else
        // clicking the topbar "Save theme" while Templates are collapsed would silently do
        // nothing (the form would be inside a display:none subtree).
        tdSetTemplatesCollapsed(false);
        // Pre-fill the name only when re-saving an existing SAVED theme (overwrite) —
        // keyed by kind so a selected BUILT-IN (read-only) never pre-fills its name and
        // silently overwrites a same-named saved copy (Save = save-as-new for a built-in).
        const isSaved = tdSelectedKind === "saved";
        tdSaveName.value = isSaved ? tdSelected : "";
        tdSaveRow.hidden = false;
        tdSaveName.focus();
        tdSaveName.select();
      };
      const tdDoSave = () => {
        if (!tdTheme) return;
        const name = tdSaveName.value.trim();
        if (!name) { tdStatus("Enter a name to save this theme."); tdSaveName.focus(); return; }
        // Reject client-side what the host would reject, so an over-long name never
        // produces a false "Saved" (a host DENY resolves Ok with the unchanged view).
        if (tdNameBytes(name) > TD_NAME_MAX_BYTES) {
          tdStatus("That name is too long (max " + TD_NAME_MAX_BYTES + " bytes). Try a shorter name.");
          tdSaveName.focus();
          return;
        }
        // A built-in name is reserved — a saved theme named like a built-in would be
        // shadowed (built-ins resolve first) and never applyable by name (86ajq69ft).
        if (tdOrder.indexOf(name) !== -1) {
          tdStatus("“" + name + "” is a built-in template name — choose a different name.");
          tdSaveName.focus();
          return;
        }
        tdStatus("Saving…");
        tdCloseSaveRow();
        // Confirm success against the RETURNED view — a host-side DENY (name too long,
        // library full) resolves Ok with the UNCHANGED view, so promise-resolution alone
        // must never be reported as saved. Only claim success if the name is really there.
        act(() => invoke("save_theme", { name, themeJson: JSON.stringify(tdTheme) })
          .then((v) => {
            const saved = v && Array.isArray(v.saved_themes) && v.saved_themes.some((t) => t.name === name);
            if (saved) {
              tdSelected = name;
              tdSelectedKind = "saved";
              tdStatus("Saved “" + name + "” to the library.");
            } else {
              tdStatus("Couldn't save “" + name + "” — the name may be too long or the library is full.");
            }
            return v;
          })
          .catch((e) => { tdStatus("Couldn't save the theme — the library is unchanged."); throw e; }));
      };
      document.getElementById("td-save").onclick = tdOpenSaveRow;
      document.getElementById("td-save-confirm").onclick = tdDoSave;
      document.getElementById("td-save-cancel").onclick = () => { tdCloseSaveRow(); tdStatus("Save cancelled."); };
      tdSaveName.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); tdDoSave(); }
        else if (e.key === "Escape") { e.preventDefault(); tdCloseSaveRow(); }
      });
      // --- Add content + element inspector (86ajq6j4p) ---
      // The four shape geometries (86ajtwq24). `rect` is the default and is left OFF the
      // element (the host skips serialising it) so a rectangle's JSON stays byte-identical.
      const TD_SHAPE_LABELS = { rect: "Rectangle", ellipse: "Ellipse", rounded_rect: "Rounded rectangle", triangle: "Triangle" };
      function tdAddDefaults(kind, variant) {
        const maxZ = tdEls().reduce((m, e) => Math.max(m, tdZ(e)), -1);
        const base = { x_permille: 350, y_permille: 400, w_permille: 300, h_permille: 200, opacity: 255, z: maxZ + 1 };
        if (kind === "image") return Object.assign(base, { kind: "image", source: "" });
        if (kind === "text") return Object.assign(base, {
          kind: "text",
          text: "Text",
          color: { r: 255, g: 255, b: 255, a: 255 },
          size_permille: 80,
          line_height_permille: 1150,
          align_h: "center",
          align_v: "middle",
          fit: "shrink_to_fit",
        });
        // A visible default fill (neutral panel) + no border, so a new shape is never invisible.
        const el = Object.assign(base, { kind: "shape", fill: { r: 58, g: 65, b: 80, a: 255 }, border: { r: 0, g: 0, b: 0, a: 0 }, border_permille: 0 });
        const v = TD_SHAPE_LABELS[variant] ? variant : "rect";
        if (v !== "rect") el.variant = v; // omit for a rectangle → byte-identical JSON
        if (v === "rounded_rect") el.corner_permille = 150; // a sensible default radius (15%)
        return el;
      }
      function tdAddElement(kind, source, variant) {
        if (!tdTheme) { tdStatus("Load or start a theme first."); return; }
        if (!Array.isArray(tdTheme.elements)) tdTheme.elements = [];
        if (tdTheme.elements.length >= 64) { tdStatus("Maximum 64 elements per theme."); return; }
        const el = tdAddDefaults(kind, variant);
        if (kind === "image") el.source = source || "";
        tdTheme.elements.push(el);
        tdSelEl = tdTheme.elements.length - 1;
        tdSync();
        tdPreview();
        tdSel.focus();
        const what = kind === "image" ? "Image" : kind === "text" ? "Text" : (TD_SHAPE_LABELS[el.variant || "rect"] || "Shape");
        tdAnnounce(what + " added, selected");
      }

      // Add / Replace an image via a host-local PATH (the native OS file-picker + FR-138
      // media-root confinement are a later increment — no dialog crate in the offline build).
      const tdImgRow = document.getElementById("td-img-row");
      const tdImgPath = document.getElementById("td-img-path");
      let tdImgReplace = false;
      const tdOpenImgRow = (replace) => {
        if (!tdTheme) { tdStatus("Load or start a theme first."); return; }
        if (!replace && tdEls().length >= 64) { tdStatus("Maximum 64 elements per theme."); return; }
        tdImgReplace = !!replace;
        tdImgPath.value = replace && tdActiveIsEl() ? tdActive().source || "" : "";
        tdImgRow.hidden = false;
        tdImgPath.focus();
        tdImgPath.select();
      };
      const tdCloseImgRow = () => { tdImgRow.hidden = true; tdImgPath.value = ""; };
      const tdDoImg = () => {
        const path = tdImgPath.value.trim();
        if (!path) { tdStatus("Paste an image file path on this machine."); tdImgPath.focus(); return; }
        // Match MediaRef's host-side validation exactly (CAP = 1024 BYTES, NUL rejected) so the
        // client never emits a theme JSON the host would reject (which would poison the theme).
        if (path.indexOf("\0") !== -1) { tdStatus("That path contains an invalid character."); tdImgPath.focus(); return; }
        if (tdNameBytes(path) > 1024) { tdStatus("That path is too long (max 1024 bytes)."); tdImgPath.focus(); return; }
        tdCloseImgRow();
        if (tdImgReplace && tdActiveIsEl()) {
          tdActive().source = path;
          tdSyncEl();
          tdPreview();
          tdAnnounce("Image source replaced");
        } else {
          tdAddElement("image", path);
        }
      };
      // Native OS file picker (#1): the primary Add-Image / Replace path. Falls back to the
      // manual path row if the picker command is unavailable. The chosen path (validated like
      // MediaRef) becomes an Element::Image source.
      async function tdPickImage(replace) {
        if (!tdTheme) { tdStatus("Load or start a theme first."); return; }
        if (!replace && tdEls().length >= 64) { tdStatus("Maximum 64 elements per theme."); return; }
        let path;
        try {
          path = await invoke("pick_image");
        } catch (e) {
          tdOpenImgRow(replace); // no native dialog → the manual path row
          return;
        }
        if (!path) return; // the user cancelled
        if (path.indexOf("\0") !== -1 || tdNameBytes(path) > 1024) {
          tdStatus("That image path is not valid (too long or contains an invalid character).");
          return;
        }
        if (replace && tdActiveIsEl()) {
          tdActive().source = path;
          tdSyncEl();
          tdPreview();
          tdAnnounce("Image source replaced");
        } else {
          tdAddElement("image", path);
        }
      }
      document.getElementById("td-img-add").onclick = tdDoImg;
      document.getElementById("td-img-cancel").onclick = () => { tdCloseImgRow(); tdStatus("Add image cancelled."); };
      tdImgPath.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); tdDoImg(); }
        else if (e.key === "Escape") { e.preventDefault(); tdCloseImgRow(); }
      });
      // Add Shape → a shape picker (86ajtwq24): choose the geometry, then add the element.
      const tdShapeRow = document.getElementById("td-shape-row");
      const tdCloseShapeRow = () => { tdShapeRow.hidden = true; };
      const tdOpenShapeRow = () => {
        if (!tdTheme) { tdStatus("Load or start a theme first."); return; }
        if (tdEls().length >= 64) { tdStatus("Maximum 64 elements per theme."); return; }
        tdShapeRow.hidden = false;
        const first = tdShapeRow.querySelector("[data-shape]");
        if (first) first.focus();
      };
      tdShapeRow.querySelectorAll("[data-shape]").forEach((b) => {
        b.onclick = () => { const v = b.dataset.shape; tdCloseShapeRow(); tdAddElement("shape", null, v); };
      });
      document.getElementById("td-shape-cancel").onclick = () => { tdCloseShapeRow(); tdStatus("Add shape cancelled."); };
      tdShapeRow.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { e.preventDefault(); tdCloseShapeRow(); tdStatus("Add shape cancelled."); }
      });
      document.querySelectorAll("#surface-theme-designer .td-addbar button[data-add]").forEach((b) => {
        if (b.disabled) return; // Text / Scripture — a later increment
        b.onclick = () => {
          if (b.dataset.add === "shape") tdOpenShapeRow();
          else if (b.dataset.add === "image") tdPickImage(false);
          else if (b.dataset.add === "text") tdAddElement("text"); // 86ajq6j64
        };
      });

      // Arrange (z-order) per CANVAS-EDITING-spec §2a: compose sorts by z, so arrange
      // rewrites the z VALUE (never the array order) and keeps z values distinct.
      function tdArrange(op) {
        if (!tdActiveIsEl()) return;
        const els = tdEls();
        const el = els[tdSelEl];
        const before = tdZ(el);
        const zs = els.map(tdZ);
        // i16 clamp so repeated front/back can never overflow the host's z: i16.
        if (op === "front") el.z = Math.min(Math.max(...zs) + 1, 32767);
        else if (op === "back") el.z = Math.max(Math.min(...zs) - 1, -32768);
        else if (op === "forward" || op === "backward") {
          // Step past the neighbour in composite PAINT order (z then index) — this handles
          // equal-z ties (an externally-authored theme) that a "nearest strictly-higher z"
          // swap would no-op on.
          const order = tdPaintOrder();
          const j = op === "forward" ? order[order.indexOf(tdSelEl) + 1] : order[order.indexOf(tdSelEl) - 1];
          if (j !== undefined) {
            const zj = tdZ(els[j]);
            if (zj === before) el.z = op === "forward" ? before + 1 : before - 1; // tie → step past
            else { els[j].z = before; el.z = zj; } // distinct z → swap
          }
        }
        tdSync();
        tdPreview();
        // Announce only when the stacking actually changed, and convey the new position.
        if (tdZ(el) !== before) {
          const npos = tdPaintOrder().indexOf(tdSelEl) + 1;
          tdAnnounce(
            "Moved " + (tdZ(el) >= 0 ? "in front of the text" : "behind the text") +
              " — " + npos + " of " + els.length,
          );
        }
      }
      // (The inspector "Arrange (z-order)" buttons were removed — the LAYERS panel now owns
      // z-order via drag-and-drop; tdArrange still backs the keyboard chords + context menu.)

      // Delete an element (two-click confirm, mirroring the saved-theme delete pattern).
      function tdDeleteEl() {
        if (!tdActiveIsEl()) return;
        const btn = document.getElementById("td-el-del");
        if (!tdElDelArm) {
          tdElDelArm = true;
          btn.textContent = "Click again to delete";
          tdAnnounce("Press Delete again to remove this element.");
          clearTimeout(tdElDelTimer);
          tdElDelTimer = setTimeout(() => { tdElDelArm = false; btn.textContent = "Delete element"; }, 3000);
          return;
        }
        clearTimeout(tdElDelTimer);
        tdElDelArm = false;
        btn.textContent = "Delete element";
        const i = tdSelEl;
        tdEls().splice(i, 1);
        tdSelEl = tdEls().length ? Math.min(i, tdEls().length - 1) : -1;
        tdSync();
        tdPreview();
        tdAnnounce("Element deleted");
      }
      document.getElementById("td-el-del").onclick = tdDeleteEl;
      document.getElementById("td-el-replace").onclick = () => tdPickImage(true);

      // Per-element controls: opacity (the single alpha) + shape fill/border/border-width.
      document.getElementById("td-el-op").oninput = (e) => {
        if (!tdActiveIsEl()) return;
        tdActive().opacity = Math.round((+e.target.value * 255) / 100);
        document.getElementById("td-el-op-v").textContent = e.target.value;
        tdPreview();
      };
      document.getElementById("td-el-fill").oninput = (e) => { if (tdActiveIsEl()) { tdActive().fill = tdRgb(e.target.value); tdPreview(); } };
      document.getElementById("td-el-border").oninput = (e) => { if (tdActiveIsEl()) { tdActive().border = tdRgb(e.target.value); tdPreview(); } };
      document.getElementById("td-el-bw").oninput = (e) => {
        if (!tdActiveIsEl()) return;
        const el = tdActive();
        el.border_permille = +e.target.value;
        // A border width with a fully-transparent border colour draws nothing — make it visible.
        if (el.border_permille > 0 && (!el.border || el.border.a === 0)) el.border = { r: 255, g: 255, b: 255, a: 255 };
        document.getElementById("td-el-bw-v").textContent = (+e.target.value / 10).toFixed(1);
        tdSyncEl();
        tdPreview();
      };
      // Corner radius (rounded-rect only, 86ajtwq24): slider % of the shorter side → per-mille.
      document.getElementById("td-el-corner").oninput = (e) => {
        if (!tdActiveIsEl()) return;
        tdActive().corner_permille = Math.round(+e.target.value * 10);
        document.getElementById("td-el-corner-v").textContent = e.target.value;
        tdPreview();
      };
      // Text-box controls (86ajq6j64): content / colour / size / alignment on the selected
      // Text element. Bound the content on the CLIENT to the host cap (MAX_TEXT_ELEMENT_LEN)
      // so the UI can never author a theme the host would reject (which would make Apply
      // falsely report success / Save misdiagnose the failure). The auto-fit shrinks it to
      // the rect. `maxlength` guards typed/pasted input; this slice also guards a programmatic
      // set, and keeps the textarea + model in sync when a paste is truncated.
      const TD_MAX_TEXT = 2000;
      document.getElementById("td-el-text-content").oninput = (e) => {
        if (!tdActiveIsEl()) return;
        let v = e.target.value;
        if (v.length > TD_MAX_TEXT) {
          v = v.slice(0, TD_MAX_TEXT);
          e.target.value = v;
          tdStatus("Text box capped at " + TD_MAX_TEXT + " characters.");
        }
        tdActive().text = v;
        tdPreview();
      };
      document.getElementById("td-el-text-color").oninput = (e) => {
        if (tdActiveIsEl()) { tdActive().color = tdRgb(e.target.value); tdPreview(); }
      };
      document.getElementById("td-el-text-size").oninput = (e) => {
        if (!tdActiveIsEl()) return;
        tdActive().size_permille = Math.round(+e.target.value * 10);
        document.getElementById("td-el-text-size-v").textContent = e.target.value;
        tdPreview();
      };
      document.getElementById("td-el-text-align").onchange = (e) => {
        if (tdActiveIsEl()) { tdActive().align_h = e.target.value; tdPreview(); }
      };

      // --- Right-click context menu (#4): Copy / Paste / Delete / Send-to-back / Bring-to-front ---
      let tdClip = null; // session clipboard: a deep-cloned element
      const tdMenu = document.getElementById("td-ctx"); // (tdCtx is the canvas 2D context)
      const tdCloseCtx = () => { tdMenu.hidden = true; };
      function tdOpenCtx(x, y) {
        const hasEl = tdActiveIsEl();
        const q = (a) => tdMenu.querySelector('[data-ctx="' + a + '"]');
        ["copy", "delete", "front", "back"].forEach((a) => (q(a).disabled = !hasEl));
        q("paste").disabled = !tdClip || tdEls().length >= 64;
        tdMenu.hidden = false;
        const w = tdMenu.offsetWidth || 168, h = tdMenu.offsetHeight || 180;
        tdMenu.style.left = Math.max(4, Math.min(x, window.innerWidth - w - 6)) + "px";
        tdMenu.style.top = Math.max(4, Math.min(y, window.innerHeight - h - 6)) + "px";
        const first = Array.from(tdMenu.querySelectorAll("button")).find((b) => !b.disabled);
        if (first) first.focus();
      }
      function tdCopy() {
        if (!tdActiveIsEl()) return;
        tdClip = JSON.parse(JSON.stringify(tdActive()));
        tdAnnounce("Element copied");
      }
      function tdPaste() {
        if (!tdClip || !tdTheme) return;
        if (!Array.isArray(tdTheme.elements)) tdTheme.elements = [];
        if (tdTheme.elements.length >= 64) { tdStatus("Maximum 64 elements per theme."); return; }
        const clone = JSON.parse(JSON.stringify(tdClip));
        // Offset so the paste is visibly distinct + on top (a fresh max z).
        clone.x_permille = tdClamp((clone.x_permille || 0) + 30, 0, 1000 - (clone.w_permille || 20));
        clone.y_permille = tdClamp((clone.y_permille || 0) + 30, 0, 1000 - (clone.h_permille || 20));
        clone.z = tdEls().reduce((m, el) => Math.max(m, tdZ(el)), -1) + 1;
        tdTheme.elements.push(clone);
        tdSelEl = tdTheme.elements.length - 1;
        tdSync();
        tdPreview();
        tdSel.focus();
        tdAnnounce(tdElLabel(clone) + " pasted, selected");
      }
      function tdCtxDelete() {
        if (!tdActiveIsEl()) return;
        const i = tdSelEl;
        tdEls().splice(i, 1);
        tdSelEl = tdEls().length ? Math.min(i, tdEls().length - 1) : -1;
        tdSync();
        tdPreview();
        tdAnnounce("Element deleted");
      }
      tdMenu.querySelectorAll("button").forEach((b) => (b.onclick = () => {
        const a = b.dataset.ctx;
        tdCloseCtx();
        if (a === "copy") tdCopy();
        else if (a === "paste") tdPaste();
        else if (a === "front") tdArrange("front");
        else if (a === "back") tdArrange("back");
        else if (a === "delete") tdCtxDelete();
        tdSel.focus();
      }));
      tdMenu.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { e.preventDefault(); tdCloseCtx(); tdSel.focus(); return; }
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          const items = Array.from(tdMenu.querySelectorAll("button")).filter((b) => !b.disabled);
          const idx = items.indexOf(document.activeElement);
          const n = e.key === "ArrowDown" ? (idx + 1) % items.length : (idx - 1 + items.length) % items.length;
          if (items[n]) items[n].focus();
        }
      });
      // Right-click on the canvas opens the menu (selecting the element under the cursor first).
      tdBox.addEventListener("contextmenu", (e) => {
        if (!tdTheme) return;
        e.preventDefault();
        const hit = tdHitTest(e.clientX, e.clientY);
        if (hit >= 0 && hit !== tdSelEl) { tdSelEl = hit; tdSync(); }
        tdOpenCtx(e.clientX, e.clientY);
      });
      // Close the menu on any pointerdown outside it (cheap no-op while hidden).
      document.addEventListener("pointerdown", (e) => { if (!tdMenu.hidden && !tdMenu.contains(e.target)) tdCloseCtx(); });
      // Keyboard: Cmd/Ctrl+C copy, Cmd/Ctrl+V paste; ContextMenu / Shift+F10 opens the menu.
      tdSel.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && (e.key === "c" || e.key === "C") && tdActiveIsEl()) { e.preventDefault(); tdCopy(); }
        else if ((e.metaKey || e.ctrlKey) && (e.key === "v" || e.key === "V")) { e.preventDefault(); tdPaste(); }
        else if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
          e.preventDefault();
          const r = tdSel.getBoundingClientRect();
          tdOpenCtx(r.left + r.width / 2, r.top + r.height / 2);
        }
      });

      document.getElementById("td-apply").onclick = () => {
        if (!tdTheme) return;
        const s = document.getElementById("td-status");
        s.textContent = "Applying…";
        // Surface BOTH outcomes on the aria-live status: a rejected apply (host
        // disconnect / IPC failure in the Remote backend) must not leave the operator
        // stuck on "Applying…" believing the audience theme changed when it did not.
        act(() => invoke("set_custom_theme", { themeJson: JSON.stringify(tdTheme) })
          .then((v) => { s.textContent = "Applied to the audience output."; return v; })
          .catch((e) => { s.textContent = "Couldn't apply the theme — the audience output is unchanged."; throw e; }));
      };
      // Duplicate (Design 2.0 topbar): deep-clone the current design into a NEW unsaved
      // working theme (save-as-new on the next Save). No backend call — pure client clone.
      document.getElementById("td-duplicate").onclick = () => {
        if (!tdTheme) { tdStatus("Nothing to duplicate yet."); return; }
        tdTheme = JSON.parse(JSON.stringify(tdTheme));
        tdSelected = "";
        tdSelectedKind = "";
        tdSelEl = -1;
        tdList();
        tdSync();
        tdPreview();
        tdStatus("Duplicated — editing a new unsaved copy. Use “Save theme” to name it.");
      };

      // Preview zoom (Design 2.0): scales the on-screen preview box ONLY (a CSS transform;
      // getBoundingClientRect accounts for it, so pointer→per-mille stays exact). Bounded
      // 25–200%; never persisted; never changes the 1920×1080 audience output.
      let tdZoom = 1;
      const tdZoomV = document.getElementById("td-zoom-v");
      function tdApplyZoom() {
        tdBox.style.setProperty("--td-zoom", String(tdZoom));
        if (tdZoomV) tdZoomV.textContent = Math.round(tdZoom * 100) + "%";
      }
      document.getElementById("td-zoom-in").onclick = () => { tdZoom = tdClamp(Math.round((tdZoom + 0.1) * 100) / 100, 0.25, 2); tdApplyZoom(); };
      document.getElementById("td-zoom-out").onclick = () => { tdZoom = tdClamp(Math.round((tdZoom - 0.1) * 100) / 100, 0.25, 2); tdApplyZoom(); };
      tdApplyZoom();

      // Fit the 16:9 preview box to the available canvas area (letterbox: bound by BOTH the
      // width and the height so it never overflows/clips — the previous fixed 860px width
      // clipped the top on short screens). The zoom transform still scales from this base.
      function tdFitCanvas() {
        const scroll = tdBox.parentElement;
        if (!scroll || !scroll.clientWidth) return; // hidden surface → 0; re-run on activation
        const cs = getComputedStyle(scroll);
        const availW = scroll.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        const availH = scroll.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
        if (availW <= 0 || availH <= 0) return;
        const fitW = Math.max(160, Math.min(availW, availH * (16 / 9)));
        tdBox.style.width = Math.floor(fitW) + "px";
        tdBox.style.maxWidth = "none";
      }
      let tdFitRaf = 0;
      function tdFitCanvasSoon() { cancelAnimationFrame(tdFitRaf); tdFitRaf = requestAnimationFrame(tdFitCanvas); }
      window.addEventListener("resize", tdFitCanvasSoon);

      // Collapsible Templates row — collapse it to give the canvas more room to work; the
      // reclaimed height flows to the canvas area, so re-fit the preview after toggling.
      const tdTemplatesEl = document.querySelector(".td-templates");
      const tdTemplatesToggle = document.getElementById("td-templates-toggle");
      // Hoisted so tdOpenSaveRow (defined earlier) can force-expand the strip before revealing
      // the save form, which lives inside the collapsible #td-panel.
      function tdSetTemplatesCollapsed(collapsed) {
        if (!tdTemplatesEl) return;
        tdTemplatesEl.classList.toggle("collapsed", collapsed);
        if (tdTemplatesToggle) {
          tdTemplatesToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
          const t = collapsed ? "Show templates" : "Collapse templates";
          tdTemplatesToggle.title = t;
          tdTemplatesToggle.setAttribute("aria-label", t);
        }
        tdFitCanvasSoon();
      }
      if (tdTemplatesToggle && tdTemplatesEl) {
        tdTemplatesToggle.onclick = () => tdSetTemplatesCollapsed(!tdTemplatesEl.classList.contains("collapsed"));
      }

      // "+ Add layer" (LAYERS header): adds a Text element (the most common new layer),
      // reusing the canonical add-content path (bounded by the 64-element cap).
      document.getElementById("td-layers-add").onclick = () => tdAddElement("text");

      // (Theme Designer built-ins + fonts load lazily on first activation — see
      // ensureThemeDesignerLoaded / showSurface, audit L3. Not loaded at boot.)

      function miniBtn(label, onclick, ariaLabel) {
        const b = document.createElement("button");
        b.textContent = label;
        b.style.cssText = "padding:2px 8px;margin-left:4px;font-size:11px";
        // A glyph-only control (↑ ↓ ✏ ✕) has no accessible name; pass ariaLabel so screen
        // readers announce the action instead of the raw character (WCAG 4.1.2).
        if (ariaLabel) {
          b.setAttribute("aria-label", ariaLabel);
          b.title = ariaLabel;
        }
        b.onclick = onclick;
        return b;
      }

      function badge(cls, text) {
        const el = document.createElement("span");
        el.className = "badge " + cls;
        el.textContent = text;
        return el;
      }

      function fmtClock(secs) {
        return Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0");
      }

      async function act(fn) {
        try {
          // Any explicit action invalidates the render cache (e.g. a cancelled
          // inline edit must restore the normal row even if the view is unchanged).
          lastRendered = "";
          render(await fn());
        } catch (e) {
          console.error(e);
        }
      }

      const toggleBlackout = () => {
        const on = document.getElementById("blackout").dataset.on !== "1";
        act(() => invoke("blackout", { on }));
      };
      const clearAll = () => act(() => invoke("clear"));

      const goPrev = () => act(() => invoke("previous"));
      const goNext = () => act(() => invoke("next"));
      const goLive = () => {
        // When a deck slide is staged, GO LIVE routes the ACTUAL slide to the output (authored-slide
        // present) rather than the plan-item go_live (which would show only the item title).
        const dp = window.__consoleDeckPreview;
        if (dp && dp.slideId != null) {
          act(() => invoke("present_plan_deck_slide", { deckId: dp.deckId, slideId: dp.slideId }));
        } else {
          act(() => invoke("go_live"));
        }
      };
      document.getElementById("prev").onclick = goPrev;
      document.getElementById("next").onclick = goNext;
      document.getElementById("golive").onclick = goLive;
      document.getElementById("blackout").onclick = toggleBlackout;
      document.getElementById("clear-all").onclick = clearAll;
      // Global topbar transport (always reachable, on every surface) — the same actions
      // as the console/footer controls, wired to the same handlers.
      const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
      bind("top-prev", goPrev);
      bind("top-next", goNext);
      bind("top-golive", goLive);
      bind("top-blackout", toggleBlackout);
      document.getElementById("timer-5").onclick = () =>
        act(() => invoke("start_timer", { seconds: 300 }));
      document.getElementById("timer-10").onclick = () =>
        act(() => invoke("start_timer", { seconds: 600 }));
      document.getElementById("timer-stop").onclick = () => act(() => invoke("stop_timer"));

      // --- Timer | Stage sub-tabs + the stage theme picker / message composer (stage-only) ---
      (function wireStageTab() {
        const segTimer = document.getElementById("seg-timer");
        const segStage = document.getElementById("seg-stage");
        const panTimer = document.getElementById("stab-timer");
        const panStage = document.getElementById("stab-stage");
        if (!segTimer || !segStage || !panTimer || !panStage) return;
        const showStage = (on) => {
          segStage.classList.toggle("active", on);
          segTimer.classList.toggle("active", !on);
          segStage.setAttribute("aria-selected", on ? "true" : "false");
          segTimer.setAttribute("aria-selected", on ? "false" : "true");
          segStage.tabIndex = on ? 0 : -1;
          segTimer.tabIndex = on ? -1 : 0;
          panStage.hidden = !on;
          panTimer.hidden = on;
        };
        segTimer.onclick = () => showStage(false);
        segStage.onclick = () => showStage(true);
        // Theme picker: one confidence template per stage screen (set_stage_template). The
        // active card is re-derived from the host view in syncStage, so no optimistic lie.
        document.querySelectorAll("#stage-themes .stage-theme").forEach((btn) => {
          btn.onclick = () =>
            act(() => invoke("set_stage_template", { template: btn.dataset.template }));
        });
        // Message: a preset chip sends immediately; the custom field + Send sends its text.
        document.querySelectorAll("#stage-presets .stage-preset").forEach((btn) => {
          btn.onclick = () => act(() => invoke("set_stage_message", { text: btn.dataset.msg }));
        });
        const input = document.getElementById("stage-msg-input");
        const send = () => {
          const text = input.value.trim();
          if (text) act(() => invoke("set_stage_message", { text }));
        };
        document.getElementById("stage-msg-send").onclick = send;
        input.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            send();
          }
        });
        document.getElementById("stage-msg-clear").onclick = () => {
          input.value = "";
          act(() => invoke("set_stage_message", { text: "" }));
        };
      })();
      // Custom time as HH:MM:SS (Figma 365) — composed to seconds for the existing
      // start_timer command. Each field is sanitised + bounded; total capped at 99h.
      // The custom-time ceiling (23:59:59) — matches the #timer-hh max="23" attribute so the
      // input and the JS agree, and bounds every path that feeds start_timer (custom + reset).
      const MAX_TIMER_SECS = 23 * 3600 + 59 * 60 + 59;
      const readHms = () => {
        const val = (id, max) => {
          const raw = Number(document.getElementById(id).value);
          if (!Number.isFinite(raw)) return 0;
          return Math.max(0, Math.min(max, Math.floor(raw)));
        };
        return val("timer-hh", 23) * 3600 + val("timer-mm", 59) * 60 + val("timer-ss", 59);
      };
      document.getElementById("timer-start-custom").onclick = () => {
        const secs = Math.min(MAX_TIMER_SECS, readHms());
        if (secs >= 1) act(() => invoke("start_timer", { seconds: secs }));
      };
      ["timer-hh", "timer-mm", "timer-ss"].forEach((id) => {
        document.getElementById(id).addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            document.getElementById("timer-start-custom").click();
          }
        });
      });
      document.getElementById("timer-plus").onclick = () =>
        act(() => invoke("adjust_timer", { deltaSecs: 60 }));
      document.getElementById("timer-minus").onclick = () =>
        act(() => invoke("adjust_timer", { deltaSecs: -60 }));
      // Pause toggles pause_timer / resume_timer by the current paused state (read from the
      // button's live label, kept in sync by syncChrome). Reset restarts the countdown from
      // its full length (remaining + elapsed at the moment of reset).
      const pauseBtnEl = document.getElementById("timer-pause");
      if (pauseBtnEl) {
        pauseBtnEl.onclick = () => {
          const resume = pauseBtnEl.textContent.trim() === "Resume";
          act(() => invoke(resume ? "resume_timer" : "pause_timer"));
        };
      }
      const resetBtnEl = document.getElementById("timer-reset");
      if (resetBtnEl) {
        resetBtnEl.onclick = () => {
          // Restart the countdown from its ORIGINAL length. Prefer the host's total_secs —
          // correct even in overrun, where remaining+elapsed no longer equals the original
          // (elapsed keeps growing past TIME UP, review #1). Fall back to remaining+elapsed
          // for an older host that doesn't send total_secs. resetInFlight guards against a
          // double-fire while the round-trip is pending (the 1s poll re-enables the button).
          if (resetInFlight) return;
          resetInFlight = true;
          resetBtnEl.disabled = true;
          act(async () => {
            try {
              const v = await invoke("view");
              const t = v && v.timer;
              if (!t) return v;
              const raw =
                typeof t.total_secs === "number"
                  ? t.total_secs
                  : (t.remaining_secs != null ? t.remaining_secs : 0) + (t.elapsed_secs || 0);
              // Bound the host-supplied value with the same ceiling the custom-time path uses
              // (defence-in-depth — never pass an unbounded seconds to start_timer). await so
              // the in-flight guard clears only after the restart round-trip actually completes.
              const total = Math.min(MAX_TIMER_SECS, raw);
              return total >= 1 ? await invoke("start_timer", { seconds: total }) : v;
            } finally {
              resetInFlight = false;
            }
          });
        };
      }
      // ── Scriptures chapter browser (86ajpkfcd, Pewbeam-style; KJV default).
      // Type a reference -> the chapter opens as a numbered verse list; ↑/↓
      // move the highlighted verse AND stage it; the canonical Enter (Go Live)
      // then sends it to the audience. Keywords fall back to search hits.
      let currentTranslation = "KJV";
      let currentChapter = null; // {reference, verses:[[num,text]...], prev, next}

      // Called only when the operator STAGES a detection (an explicit confirm) — open the
      // detected verse's FULL chapter in the browser, cursored to the verse, for follow-on
      // browsing. A bare detection never touches this panel (or Preview/Live).
      window.__openChapterForStage = function (reference) {
        if (reference) loadChapter(reference, null);
      };
      let verseCursor = -1;
      let scriptureTimer = null;
      let scriptureHits = [];
      let scriptureGen = 0;

      const translationSel = document.getElementById("translation");
      let translationCodes = "";
      const renderTranslations = (codes) => {
        // Set-compare (not length): a changed SET with the same count must
        // re-render, and the current selection survives when still offered.
        const key = codes.join(",");
        if (key === translationCodes) return;
        translationCodes = key;
        if (!codes.includes(currentTranslation)) {
          currentTranslation = codes[0] || "KJV";
        }
        translationSel.innerHTML = "";
        codes.forEach((c) => {
          const opt = document.createElement("option");
          opt.value = c;
          opt.textContent = c;
          if (c === currentTranslation) opt.selected = true;
          translationSel.appendChild(opt);
        });
      };
      renderTranslations(["KJV", "WEB", "ASV", "WEBBE", "DBY"]);

      translationSel.onchange = () => {
        currentTranslation = translationSel.value;
        if (currentChapter) {
          const num =
            verseCursor >= 0 && currentChapter.verses[verseCursor]
              ? currentChapter.verses[verseCursor][0]
              : null;
          loadChapter(currentChapter.reference, num);
        }
      };

      let hitCursor = -1; // keyboard selection inside the hits list
      let hitsTranslation = "KJV"; // the translation the CURRENT hits came from
      // Escape-safe highlight: text nodes + styled spans, never innerHTML.
      const snippetWithHighlight = (text, query) => {
        const out = document.createElement("span");
        out.className = "snippet";
        const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
        if (!words.length || !text) {
          out.textContent = text;
          return out;
        }
        let lower = text.toLowerCase();
        // Earliest match; at the same index the LONGEST word wins so tails
        // like "loves" are fully marked for the query "love loves".
        const firstMatch = (from) => {
          let best = -1;
          let bestWord = null;
          for (const w of words) {
            const i = lower.indexOf(w, from);
            if (i < 0) continue;
            if (best < 0 || i < best || (i === best && w.length > bestWord.length)) {
              best = i;
              bestWord = w;
            }
          }
          return best < 0 ? null : { at: best, word: bestWord };
        };
        // The row is a single ellipsized line: window the text so the FIRST
        // match is visible even deep inside a long verse.
        const lead = firstMatch(0);
        if (lead && lead.at > 40) {
          const cut = text.lastIndexOf(" ", lead.at - 20);
          const start = cut > 0 ? cut + 1 : lead.at - 20;
          text = "… " + text.slice(start);
          lower = text.toLowerCase();
        }
        let pos = 0;
        while (pos < text.length) {
          const m = firstMatch(pos);
          if (!m) {
            out.appendChild(document.createTextNode(text.slice(pos)));
            break;
          }
          if (m.at > pos) out.appendChild(document.createTextNode(text.slice(pos, m.at)));
          const mark = document.createElement("span");
          mark.className = "hl";
          mark.textContent = text.slice(m.at, m.at + m.word.length);
          out.appendChild(mark);
          pos = m.at + m.word.length;
        }
        return out;
      };
      const openHit = (hit) => {
        document.getElementById("scripture-q").value = hit.reference;
        clearTimeout(scriptureTimer);
        scriptureGen++;
        scriptureHits = [];
        hitCursor = -1;
        renderHits();
        loadChapter(hit.reference, null);
      };
      const renderHits = () => {
        const box = document.getElementById("scripture-hits");
        const q = document.getElementById("scripture-q").value;
        box.innerHTML = "";
        scriptureHits.slice(0, 6).forEach((hit, i) => {
          const el = document.createElement("div");
          el.className = "hit" + (i === hitCursor ? " sel" : "");
          el.setAttribute("role", "option");
          const ref = document.createElement("span");
          ref.className = "ref";
          ref.textContent = hit.reference;
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent = hitsTranslation;
          el.appendChild(ref);
          el.appendChild(chip);
          el.appendChild(snippetWithHighlight(hit.text, q));
          el.onclick = () => openHit(hit);
          box.appendChild(el);
        });
      };

      function verseRef(i) {
        const v = currentChapter.verses[i];
        return currentChapter.reference + ":" + v[0];
      }

      const setStatus = (msg) => {
        document.getElementById("scrip-status").textContent = msg || "";
      };

      // Staging trails the cursor by 120ms so held-arrow traversal lands ONE
      // stage on the final verse instead of a wire burst per repeat.
      let stageTimer = null;
      let dblclickBusy = false; // no debounced stage may land mid double-click
      // `follow` = true only for verse NAVIGATION within the open chapter (arrow-scroll /
      // clicking a verse) — refine #8 (86ajtwq2b): moving through the reading advances Live
      // too, but only when a scripture is already live (the host gates it). A chapter LOAD
      // (search / hit / prev-next / translation change) passes `follow` falsy → Preview-only
      // (stage_scripture), so deliberately opening a NEW passage never jumps the audience.
      function setCursor(i, stage, follow) {
        if (!currentChapter || !currentChapter.verses.length) return;
        verseCursor = Math.max(0, Math.min(i, currentChapter.verses.length - 1));
        const list = document.getElementById("verse-list");
        [...list.children].forEach((el, j) =>
          el.classList.toggle("cursor", j === verseCursor)
        );
        const el = list.children[verseCursor];
        if (el) el.scrollIntoView({ block: "nearest" });
        if (stage) {
          if (dblclickBusy) return; // the dblclick flow owns staging right now
          setStatus("");
          clearTimeout(stageTimer);
          const ref = verseRef(verseCursor);
          const cmd = follow ? "follow_scripture" : "stage_scripture";
          stageTimer = setTimeout(() => {
            act(() =>
              invoke(cmd, {
                reference: ref,
                translation: currentTranslation,
              })
            );
          }, 120);
        }
      }

      function renderChapter() {
        document.getElementById("chapter-ref").textContent =
          currentChapter.reference + " (" + currentChapter.translation + ")";
        document.getElementById("ch-prev").disabled = !currentChapter.prev;
        document.getElementById("ch-next").disabled = !currentChapter.next;
        const list = document.getElementById("verse-list");
        list.innerHTML = "";
        currentChapter.verses.forEach(([num, text], i) => {
          const row = document.createElement("div");
          row.className = "verse";
          row.setAttribute("role", "option");
          const n = document.createElement("span");
          n.className = "vnum";
          n.textContent = num;
          const t = document.createElement("span");
          t.textContent = text;
          row.appendChild(n);
          row.appendChild(t);
          row.onclick = () => setCursor(i, true, true);
          // Double-click = straight to live (owner request 86ajpwcxc): the
          // explicit double gesture is the confirmation, bypassing Preview.
          // VERIFIED at each step — a denied stage must never commit whatever
          // was in Preview before, and "→ LIVE" is only claimed when the view
          // confirms THIS verse is on air (review 7af A/B/C/D).
          row.ondblclick = async () => {
            const ref = verseRef(i); // captured before any await
            clearTimeout(stageTimer);
            dblclickBusy = true;
            setCursor(i, false);
            try {
              const staged = await invoke("stage_scripture", {
                reference: ref,
                translation: currentTranslation,
              });
              render(staged);
              if (staged.staged_scripture !== ref) {
                setStatus("Could not stage " + ref + " — nothing was sent live");
                return;
              }
              clearTimeout(stageTimer); // anything armed during the round trip
              const after = await invoke("go_live");
              render(after);
              if (after.live_scripture === ref) {
                setStatus(ref + " → LIVE");
              } else {
                setStatus("Go Live did not commit " + ref);
              }
            } catch (err) {
              console.error(err);
              setStatus("Could not send " + ref + " live");
            } finally {
              dblclickBusy = false;
            }
          };
          list.appendChild(row);
        });
      }

      // cursorVerseNum is a verse NUMBER (not an index): KJV/WEB verse
      // numbering diverges in six chapters, so indexes silently shift verses.
      async function loadChapter(reference, cursorVerseNum) {
        try {
          const ch = await invoke("get_chapter", {
            reference,
            translation: currentTranslation,
          });
          currentChapter = ch;
          renderTranslations(ch.translations);
          renderChapter();
          setStatus("");
          // The HOST parsed the query — land/stage from ITS verse selection
          // ("gen 1 5", "Gen 1:5", "Gen 1:1-3" all resolve identically; no
          // regex guessing on the raw string).
          const isRange =
            ch.verse_start != null &&
            ch.verse_end != null &&
            ch.verse_end > ch.verse_start;
          let wantNum = null;
          if (cursorVerseNum != null) wantNum = cursorVerseNum;
          else if (ch.verse_start != null) wantNum = ch.verse_start;
          let idx = wantNum == null ? 0
            : ch.verses.findIndex(([n]) => n === wantNum);
          if (wantNum != null && idx < 0) {
            // The verse number does not exist in this translation (e.g. WEB
            // omits Acts 8:37): land nearby but do NOT silently stage it.
            idx = ch.verses.findIndex(([n]) => n > wantNum);
            if (idx < 0) idx = ch.verses.length - 1;
            setCursor(idx, false);
            setStatus(
              ch.reference + ":" + wantNum + " is not present in " + ch.translation
            );
            // The chapter DID render — report success so the caller neither
            // clobbers this status with a keyword search nor keeps focus in
            // the box (review 7ag).
            return true;
          }
          if (isRange) {
            // The whole passage stages; the cursor lands without re-staging.
            setCursor(Math.max(0, idx), false);
            act(() =>
              invoke("stage_scripture", {
                reference:
                  ch.reference + ":" + ch.verse_start + "-" + ch.verse_end,
                translation: currentTranslation,
              })
            );
          } else {
            setCursor(Math.max(0, idx), true);
          }
          return true;
        } catch (e) {
          setStatus(String(e));
          return false;
        }
      }

      document.getElementById("ch-prev").onclick = () => {
        if (currentChapter && currentChapter.prev) loadChapter(currentChapter.prev, null);
      };
      document.getElementById("ch-next").onclick = () => {
        if (currentChapter && currentChapter.next) loadChapter(currentChapter.next, null);
      };

      document.getElementById("scripture-q").oninput = (e) => {
        clearTimeout(scriptureTimer);
        const gen = ++scriptureGen;
        scriptureHits = [];
        hitCursor = -1;
        renderHits();
        const q = e.target.value.trim();
        if (!q) return;
        scriptureTimer = setTimeout(async () => {
          try {
            const searched = currentTranslation;
            const hits = await invoke("scripture_search", {
              query: q,
              translation: searched,
            });
            if (gen !== scriptureGen) return; // superseded while in flight
            scriptureHits = hits;
            hitsTranslation = searched;
            renderHits();
          } catch (err) {
            console.error(err);
          }
        }, 250);
      };
      document.getElementById("scripture-q").onkeydown = async (e) => {
        if ((e.key === "ArrowDown" || e.key === "ArrowUp") && scriptureHits.length) {
          e.preventDefault();
          const n = Math.min(scriptureHits.length, 6);
          if (hitCursor < 0) {
            hitCursor = e.key === "ArrowDown" ? 0 : n - 1;
          } else {
            hitCursor =
              e.key === "ArrowDown"
                ? (hitCursor + 1) % n
                : (hitCursor - 1 + n) % n;
          }
          renderHits();
          return;
        }
        if (e.key !== "Enter") return;
        e.preventDefault();
        const q = document.getElementById("scripture-q").value.trim();
        if (!q) return;
        clearTimeout(scriptureTimer);
        const gen = ++scriptureGen;
        if (scriptureHits.length) {
          const hit = scriptureHits[Math.max(0, hitCursor)];
          scriptureHits = [];
          hitCursor = -1;
          renderHits();
          if (await loadChapter(hit.reference, null)) e.target.blur();
          return;
        }
        // No hits yet (the debounce may not have fired): try it as a chapter;
        // a keyword query falls through to an IMMEDIATE search — Enter is
        // never a silent dead-end and never discards the search.
        if (await loadChapter(q, null)) {
          scriptureHits = [];
          renderHits();
          e.target.blur(); // hand the arrows to the verse list
          return;
        }
        try {
          const searched = currentTranslation;
          const hits = await invoke("scripture_search", {
            query: q,
            translation: searched,
          });
          if (gen !== scriptureGen) return;
          scriptureHits = hits;
          hitsTranslation = searched;
          renderHits();
          setStatus(hits.length ? "" : "No matches for “" + q + "”");
        } catch (err) {
          console.error(err);
        }
      };

      // (The console Service Plan panel's quick-add footer was removed — redundant with the
      // dedicated Service Plan builder's Add-item palette. Adding items happens in the builder.)

      // Top-bar clock (Figma console) — local time, ticks independently.
      const tickClock = () => {
        const d = new Date();
        document.getElementById("clock").textContent =
          String(d.getHours()).padStart(2, "0") + ":" +
          String(d.getMinutes()).padStart(2, "0") + ":" +
          String(d.getSeconds()).padStart(2, "0");
      };
      tickClock();
      setInterval(tickClock, 1000);

      // Mouse-clicked buttons blur so Enter/Space stay global afterwards.
      // Keyboard activation keeps focus (a keyboard-synthesized click has
      // e.detail === 0), so Tab users are not thrown back to the top.
      document.addEventListener("click", (e) => {
        const btn = e.target && e.target.closest && e.target.closest("button");
        if (btn && e.detail > 0) btn.blur();
      });

      // Canonical keybindings (UX-CANONICAL §1) — the JS mirror of
      // selahcue_app::keymap (contract-tested in Rust; hexes/keys pinned here).
      // Double-Esc window matches keymap::DOUBLE_ESC_WINDOW (1000ms).
      let lastEsc = 0;
      let armTimer = null;
      const armClearHint = (armed) => {
        document.getElementById("clear-all").classList.toggle("armed", armed);
        if (armTimer) {
          clearTimeout(armTimer);
          armTimer = null;
        }
        if (armed) {
          // The armed state expires with the double-tap window — never stale.
          armTimer = setTimeout(() => {
            lastEsc = 0;
            armClearHint(false);
          }, 1000);
        }
      };
      const disarm = () => {
        lastEsc = 0;
        armClearHint(false);
      };
      window.addEventListener(
        "keydown",
        (e) => {
        // OS auto-repeat is never a deliberate action for the emergency and
        // transport keys (a held Esc must not complete the double-tap, a held
        // B must not strobe) — but held ARROWS legitimately traverse the verse
        // list (staging trails the cursor, so no wire burst).
        if (e.repeat && !(e.key === "ArrowUp" || e.key === "ArrowDown")) return;
        const mod = e.ctrlKey || e.metaKey;
        // Emergency chords pierce everything, including text fields (§3):
        // Ctrl/Cmd+Shift+B = blackout, Ctrl/Cmd+Shift+. = clear all. Matched by
        // PHYSICAL key (e.code) — with Shift held, e.key is "B" but also ">"
        // for Period on most layouts, so e.key would make the chord dead.
        if (mod && e.shiftKey && e.code === "KeyB") {
          e.preventDefault();
          disarm();
          toggleBlackout();
          return;
        }
        if (mod && e.shiftKey && e.code === "Period") {
          e.preventDefault();
          disarm();
          clearAll();
          return;
        }
        // Command palette: ⌘/Ctrl+K opens it from anywhere (even a focused field).
        if (mod && !e.shiftKey && (e.key === "k" || e.key === "K")) {
          e.preventDefault();
          disarm();
          if (window.__cmdPalette) window.__cmdPalette.open();
          return;
        }
        // A destructive-confirm alertdialog is modal: suppress surface navigation (⌘1–6 / ⌘⇧P) and
        // everything below it while it is up (its own capture listener handles Esc + the Tab trap).
        // The emergency blackout / clear-all CHORDS above still pierce — that is deliberate safety.
        if (document.querySelector(".pm-confirm-back")) return;
        // While a modal (palette / shortcuts) is open, Esc closes it and transport/
        // emergency-arming keys are suppressed (the palette input's own listener drives
        // its arrows/Enter). The emergency CHORDS above still pierce.
        if (window.__cmdPalette && window.__cmdPalette.isOpen()) {
          disarm();
          if (e.key === "Escape") {
            e.preventDefault();
            window.__cmdPalette.closeAll();
          }
          return;
        }
        // Global ⌘/Ctrl+1–6 jump to the six navigable sections — makes the menu's ⌘N badges
        // and the Shortcuts reference REAL (they map by menu order; the disabled "Presentation"
        // item carries no number, so it is filtered out). Works whether the menu is open or not.
        if (mod && !e.shiftKey && !e.altKey && e.key >= "1" && e.key <= "6") {
          // The Presentation item is navigable but `data-nodigit` (it carries no ⌘-number, so it
          // never shifts the six ⌘1–6 targets — its shortcut is ⌘⇧P below).
          const targets = navItems.filter(
            (it) =>
              it.dataset.surface &&
              it.getAttribute("aria-disabled") !== "true" &&
              !it.dataset.nodigit
          );
          const it = targets[Number(e.key) - 1];
          if (it) {
            e.preventDefault();
            disarm();
            closeAppMenu();
            navGo(it);
            return;
          }
        }
        // ⌘/Ctrl+⇧+P jumps to the Presentation surface (it carries no ⌘-digit — see the filter).
        if (mod && e.shiftKey && (e.key === "p" || e.key === "P")) {
          e.preventDefault();
          disarm();
          closeAppMenu();
          showSurface("presentation");
          return;
        }
        // ⌘/Ctrl+⇧+R opens Settings › Network & Mobile (Remote Control left the top-nav — Figma
        // 336:124; its surface is reached from there via "Manage devices").
        if (mod && e.shiftKey && (e.key === "r" || e.key === "R")) {
          e.preventDefault();
          disarm();
          closeAppMenu();
          showSurface("settings");
          if (typeof setSettingsPage === "function") setSettingsPage("network");
          return;
        }
        // ⌘/Ctrl+⇧+K jumps to the Pre-service Check surface (data-nodigit — no ⌘-number).
        if (mod && e.shiftKey && (e.key === "k" || e.key === "K")) {
          e.preventDefault();
          disarm();
          closeAppMenu();
          showSurface("preservice");
          return;
        }
        // App menu: F10 opens/closes the surface navigation (reachable anywhere).
        // Cmd/Ctrl+M is intentionally NOT bound — it is the macOS "Minimize window"
        // accelerator. disarm() so opening the menu can't leave a Clear-all armed.
        if (e.key === "F10") {
          e.preventDefault();
          disarm();
          toggleAppMenu();
          return;
        }
        // While the app menu is OPEN, only the menu's own arrow/Home/End/Esc/Tab
        // keys act — transport/emergency keys must NOT drive the live output
        // (opening the menu is a benign navigation gesture; the emergency chords
        // above still pierce). review 86ajq321f-HIGH.
        if (isMenuOpen()) {
          if (e.key !== "Escape") disarm();
          return;
        }
        // Transport keys (Space/Enter/arrows/b/Backspace) act on the LIVE CONSOLE
        // ONLY — never while a config surface (Screens/Settings/…) is active, so
        // navigating those can't advance/clear/blackout the show. The emergency
        // chords (handled above) remain global. review 86ajq321f.
        if (!document.getElementById("surface-console").classList.contains("active")) {
          if (e.key !== "Escape") disarm();
          return;
        }
        // ANY intervening key disarms the double-tap — including keys typed in
        // a field and host chords (mirrors keymap.rs: Esc-then-anything-then-Esc
        // is never a clear).
        if (e.key !== "Escape") disarm();
        // Presentation-focus keys are inactive while typing in a field (the
        // inline editor owns Enter/Escape there) and on a focused button
        // (Enter/Space must activate THAT control, not fire Go Live/Next).
        const tag = (e.target && e.target.tagName) || "";
        if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
        if (tag === "BUTTON" && (e.key === "Enter" || e.key === " ")) return;
        // ↑/↓ own the chapter browser when one is open: move + stage the
        // highlighted verse (Enter then goes live via the canonical map).
        if ((e.key === "ArrowUp" || e.key === "ArrowDown") && currentChapter) {
          e.preventDefault();
          setCursor(verseCursor + (e.key === "ArrowDown" ? 1 : -1), true, true);
          return;
        }
        switch (e.key) {
          case " ":
          case "ArrowRight":
            e.preventDefault();
            act(() => invoke("next"));
            break;
          case "ArrowLeft":
            e.preventDefault();
            act(() => invoke("previous"));
            break;
          case "Enter":
            e.preventDefault();
            goLive(); // routes the staged deck slide via present_authored (else the plan-item go_live)
            break;
          case "b":
          case "B":
            e.preventDefault();
            toggleBlackout();
            break;
          case "Backspace":
            // Clear current layer (§1). The live output is single-layer until
            // per-layer clearing (86ajpy59e) — today this equals Clear-all.
            e.preventDefault();
            clearAll();
            break;
          case "Escape": {
            e.preventDefault();
            const now = Date.now();
            if (now - lastEsc <= 1000) {
              disarm();
              clearAll();
            } else {
              lastEsc = now;
              armClearHint(true);
            }
            break;
          }
        }
        },
        true // capture: first in line, nothing can swallow the canonical keys
      );

      // WKWebView (86ajphu2h): key events reach the page only when an element
      // inside the document has focus — before the first click, nothing does,
      // and every canonical key is dead. Keep the body focusable and focused
      // whenever nothing else claims focus.
      document.body.tabIndex = -1;
      const grabFocus = () => {
        const a = document.activeElement;
        if (!a || a === document.body || a === document.documentElement) {
          document.body.focus();
        }
      };
      grabFocus();
      window.addEventListener("focus", grabFocus);
      document.addEventListener("focusout", () => setTimeout(grabFocus, 0));

      // --- Live transcript (R3) + scripture detection approval queue (R4) ----------
      // Both render from the host-authoritative view (`view.transcript` /
      // `view.detections`). All host/verse text is placed via textContent — never
      // innerHTML — because transcript and detected text are untrusted.
      let transcriptKey = "";
      let detectionsKey = "";

      // Defensive client cap on the transcript DOM (audit M4): the host already tails the
      // transcript (OPERATOR_TRANSCRIPT_TAIL=60), but #transcript-log must stay bounded even
      // if a Remote/older/newer host ever returned an untailed list — slice to the newest N
      // (2x the host tail, generous headroom) BEFORE the prune/append so the DOM can never
      // grow 1:1 with the sermon. The prune below drops rows not in this sliced set.
      const MAX_TRANSCRIPT_ROWS = 120;
      function syncTranscript(view) {
        const all = Array.isArray(view.transcript) ? view.transcript : [];
        const segs =
          all.length > MAX_TRANSCRIPT_ROWS ? all.slice(-MAX_TRANSCRIPT_ROWS) : all;
        const partial =
          typeof view.partial_transcript === "string" ? view.partial_transcript : "";
        const empty = document.getElementById("transcript-empty");
        // The live in-progress line (streaming interim). Updated EVERY poll — before the log's
        // change-key early-return — so recognised words appear as they're spoken even when the
        // finalised log hasn't changed. Untrusted → textContent.
        const partialEl = document.getElementById("transcript-partial");
        if (partialEl) {
          partialEl.textContent = partial;
          partialEl.hidden = !partial;
        }
        // Report activity (finalised lines OR a live partial) so the listen status can tell
        // "waiting for speech…" from "transcribing". Set by wireTranscriptListen.
        if (window.__sttNoteTranscript)
          window.__sttNoteTranscript(segs.length + (partial ? 1 : 0));
        if (empty) empty.style.display = segs.length || partial ? "none" : "";
        const key = JSON.stringify(segs.map((s) => [s.id, s.text]));
        if (key === transcriptKey) return; // poll-safe: skip identical re-renders of the log
        transcriptKey = key;
        const log = document.getElementById("transcript-log");
        if (!log || !empty) return;
        // APPEND-ONLY by segment id: the log is an aria-live region, so clearing and
        // rebuilding it would make assistive tech re-announce the WHOLE transcript on
        // every new line. Instead drop rows that scrolled out of the bounded tail and
        // append only genuinely new segments, so only the newest line is announced.
        const wanted = new Set(segs.map((s) => String(s.id)));
        for (const row of Array.from(log.children)) {
          if (!wanted.has(row.dataset.segId)) log.removeChild(row);
        }
        const present = new Set(
          Array.from(log.children).map((r) => r.dataset.segId)
        );
        for (const s of segs) {
          if (present.has(String(s.id))) continue;
          const row = document.createElement("div");
          row.className = "seg";
          row.dataset.segId = String(s.id);
          const t = document.createElement("span");
          t.className = "seg-time";
          t.textContent = fmtClock(Math.floor((s.start_ms || 0) / 1000));
          const txt = document.createElement("span");
          txt.className = "seg-text";
          txt.textContent = s.text; // untrusted → textContent, never innerHTML
          row.appendChild(t);
          row.appendChild(txt);
          log.appendChild(row);
        }
        log.scrollTop = log.scrollHeight; // keep the newest line in view
      }

      function syncDetections(view) {
        // Newest detection first: the host queues them oldest-first, so reverse for display.
        const dets = (Array.isArray(view.detections) ? view.detections : []).slice().reverse();
        // Confidence is part of the change key so a match-% update re-renders the row.
        const key = JSON.stringify(dets.map((d) => [d.id, d.reference, d.text, d.confidence]));
        if (key === detectionsKey) return;
        detectionsKey = key;
        const list = document.getElementById("detections-list");
        const empty = document.getElementById("detections-empty");
        if (!list || !empty) return;
        // "N new" count pill in the card header (hidden when none).
        const count = document.getElementById("detections-count");
        if (count) {
          count.hidden = dets.length === 0;
          count.textContent = dets.length + " new";
        }
        // Surface a new detection on the right-column tab (never steals focus / interrupts a
        // timer edit). A detection does NOT touch Preview/Live or the Scriptures browser — that
        // only happens when the operator clicks Stage (an explicit confirm).
        if (window.__rightTabsOnDetections) window.__rightTabsOnDetections(dets.length);
        list.innerHTML = "";
        empty.style.display = dets.length ? "none" : "";
        for (const d of dets) {
          const row = document.createElement("div");
          row.className = "detection";
          row.setAttribute("role", "listitem");

          const head = document.createElement("div");
          head.className = "detection-head";
          const ref = document.createElement("span");
          ref.className = "ref";
          ref.textContent = d.reference;
          head.appendChild(ref);
          // Match-% pill — ONLY when the host supplied a real confidence (honest-empty
          // until R4 scoring lands); green when confident, amber tint when fuzzy.
          if (typeof d.confidence === "number") {
            const pct = Math.max(0, Math.min(100, Math.round(d.confidence)));
            const m = document.createElement("span");
            m.className = "match-pill" + (pct >= 90 ? "" : " fuzzy");
            m.textContent = pct + "% MATCH";
            head.appendChild(m);
          }
          row.appendChild(head);

          if (d.text) {
            const snip = document.createElement("div");
            snip.className = "snippet";
            snip.textContent = d.text; // untrusted verse text → textContent
            row.appendChild(snip);
          }

          const actions = document.createElement("div");
          actions.className = "detection-actions";
          // Stage = the operator's confirmation (FR-115): it stages the verse in Preview AND
          // pushes it Live to the audience in one action, then opens its full chapter in the
          // Scriptures browser. A bare detection never displays anything on its own.
          const approve = document.createElement("button");
          approve.className = "det-stage";
          approve.type = "button";
          approve.textContent = "Stage";
          approve.setAttribute("aria-label", "Stage " + d.reference + " and show it live");
          approve.onclick = () =>
            act(async () => {
              await invoke("approve_detection", { detectionId: d.id }); // stage in Preview
              const v = await invoke("go_live"); // confirmed → push to the audience output
              if (window.__openChapterForStage) window.__openChapterForStage(d.reference);
              return v;
            });
          const dismiss = document.createElement("button");
          dismiss.type = "button";
          dismiss.textContent = "Dismiss";
          dismiss.setAttribute("aria-label", "Dismiss " + d.reference);
          dismiss.onclick = () =>
            act(() => invoke("dismiss_detection", { detectionId: d.id }));
          actions.appendChild(approve);
          actions.appendChild(dismiss);
          row.appendChild(actions);

          list.appendChild(row);
        }
      }

      // Live transcript is audio-based (R3): a Start / Stop listening toggle flips the
      // capture state and the REC indicator. It drives the on-device STT source over the
      // host commands `start_listening` / `stop_listening`; recognised lines then stream
      // into #transcript-log from the host-authoritative `view.transcript` (rendered by
      // `syncTranscript` on the 1s poll) — never fabricated. The button only reflects
      // "listening" once the backend confirms; a build without on-device STT (or a missing
      // model) surfaces the reason honestly and stays in the prior state.
      (function wireTranscriptListen() {
        const btn = document.getElementById("transcript-listen");
        const label = document.getElementById("transcript-listen-label");
        const ico = btn && btn.querySelector(".listen-ico");
        const rec = document.getElementById("transcript-rec");
        const msg = document.getElementById("transcript-empty-msg");
        const sub = document.getElementById("transcript-empty-sub");
        const status = document.getElementById("transcript-status");
        const meter = document.getElementById("transcript-meter");
        const meterFill = document.getElementById("transcript-meter-fill");
        const meterVal = document.getElementById("transcript-meter-val");
        if (!btn) return;

        // A small state machine so the control NEVER sits silently disabled: pressing Start
        // moves idle → preparing → (downloading the model, first run only) → listening; a
        // build/model/mic failure surfaces the reason and returns to idle. `start_listening`
        // resolves only once the host worker has loaded the model + opened the mic — which on
        // first run downloads a ~1.6 GB model (minutes) — so we show that progress instead of
        // a dead button. Recognition itself is host-authoritative: recognised lines arrive in
        // `#transcript-log` via the 1s poll (syncTranscript); this only drives the control and
        // the empty-state copy, and reports whether any lines have been recognised yet.
        let sttState = "idle"; // idle | preparing | downloading | listening | error
        let dlPct = null;
        let lastErr = "";
        let hasLines = false;
        let micPct = null; // live input level while listening (null until the host reports one)
        let zeroTicks = 0; // consecutive mic-level reports at 0% while listening (no audio)
        const NO_AUDIO_TICKS = 12; // ~2.5s of silence (levels arrive ~5/s) → surface the hint

        function apply() {
          const listening = sttState === "listening";
          const busy = sttState === "preparing" || sttState === "downloading";
          btn.disabled = busy;
          btn.classList.toggle("listening", listening);
          btn.setAttribute("aria-pressed", listening ? "true" : "false");
          if (label)
            label.textContent = busy
              ? "Preparing…"
              : listening
                ? "Stop listening"
                : "Start listening";
          if (ico) ico.textContent = listening ? "⏹" : "▶";
          if (rec) rec.hidden = !listening;
          if (msg)
            msg.textContent = listening
              ? "Listening for the sermon…"
              : busy
                ? "Preparing on-device transcription…"
                : "Not listening yet.";
          if (sub) {
            sub.textContent =
              sttState === "downloading"
                ? "Downloading the speech model (one-time)" +
                  (dlPct == null ? "…" : " — " + dlPct + "%")
                : sttState === "preparing"
                  ? "Loading the speech model and opening the microphone. First run downloads it (~1.6 GB) and can take a minute."
                  : listening
                    ? zeroTicks >= NO_AUDIO_TICKS && !hasLines
                      ? "No audio is reaching the microphone (0%). Grant mic access in System Settings → Privacy & Security → Microphone, then stop and start listening again."
                      : "On-device transcription is running — recognised lines appear here as the sermon is spoken."
                    : "Press Start listening to capture the sermon audio.";
          }
          if (status)
            status.textContent =
              sttState === "downloading"
                ? "Downloading model…" + (dlPct == null ? "" : " " + dlPct + "%")
                : sttState === "preparing"
                  ? "Preparing on-device transcription…"
                  : sttState === "error"
                    ? lastErr
                    : listening
                      ? hasLines
                        ? "Listening — transcribing on-device."
                        : "Listening — waiting for speech…"
                      : "";
          applyMeter();
        }

        // Update the live mic-level meter (shown only while listening). Called on every stt://level
        // tick — cheap, and a role=meter value is NOT an aria-live region, so frequent updates never
        // spam assistive tech (the aria-live status text no longer carries the level). Clamped 0..100.
        function applyMeter() {
          if (!meter) return;
          const listening = sttState === "listening";
          meter.hidden = !listening;
          const pct = Math.max(0, Math.min(100, micPct == null ? 0 : micPct));
          meter.setAttribute("aria-valuenow", String(pct));
          if (meterFill) meterFill.style.width = pct + "%";
          if (meterVal) meterVal.textContent = pct + "%";
        }

        // The 1s poll reports whether any recognised lines have arrived, so the status can
        // honestly distinguish "listening but nothing recognised yet" (mic/speech) from
        // "transcribing" — turning a silent empty panel into a diagnosable state.
        window.__sttNoteTranscript = function (count) {
          const now = count > 0;
          if (now !== hasLines) {
            hasLines = now;
            if (sttState === "listening") apply();
          }
        };

        // Optional first-run model-download progress, pushed from the host worker. The control
        // still works without it (just without a %); only meaningful while starting.
        if (window.__TAURI__ && window.__TAURI__.event && window.__TAURI__.event.listen) {
          window.__TAURI__.event.listen("stt://progress", function (e) {
            const p = (e && e.payload) || {};
            if (sttState === "preparing" || sttState === "downloading") {
              sttState = "downloading";
              dlPct = typeof p.pct === "number" ? p.pct : null;
              apply();
            }
          });
          // Live mic level: lets the "waiting for speech…" status show whether audio is even
          // arriving (a level stuck at 0 while speaking ⇒ mic/permission, not the UI).
          window.__TAURI__.event.listen("stt://level", function (e) {
            const p = (e && e.payload) || {};
            if (typeof p.pct !== "number") return;
            micPct = p.pct;
            if (sttState !== "listening") return;
            applyMeter(); // cheap, frequent — the visual meter
            // Track a run of silence so a mic that delivers nothing (0% — usually denied
            // permission) turns into an actionable hint. Only re-render the aria-live status when
            // that hint actually toggles (avoids announcing on every level tick).
            const wasNoAudio = zeroTicks >= NO_AUDIO_TICKS;
            zeroTicks = p.pct === 0 && !hasLines ? zeroTicks + 1 : 0;
            if (wasNoAudio !== (zeroTicks >= NO_AUDIO_TICKS)) apply();
          });
        }

        btn.addEventListener("click", async () => {
          if (sttState === "preparing" || sttState === "downloading") return; // starting; ignore
          if (sttState === "listening") {
            // Stop — reflect it immediately (stop is idempotent host-side).
            sttState = "idle";
            dlPct = null;
            lastErr = "";
            hasLines = false;
            micPct = null;
            zeroTicks = 0;
            apply();
            try {
              await invoke("stop_listening");
            } catch (err) {
              /* idempotent; nothing to surface */
            }
            return;
          }
          // Start — show progress at once so the control never looks hung during the load.
          sttState = "preparing";
          dlPct = null;
          lastErr = "";
          hasLines = false;
          apply();
          try {
            await invoke("start_listening");
            sttState = "listening";
          } catch (err) {
            lastErr = err && err.message ? err.message : String(err);
            sttState = "error";
          }
          apply();
        });
        apply();
      })();

      // --- Right column tabs: Service Timer | Detected Scriptures (Figma 430:124). Tabbing
      // the two gives the detection list the full column height (≥3 cards). A real tablist:
      // ←/→ move between tabs, aria-selected + roving tabindex, panels toggle `hidden`. A NEW
      // detection surfaces the Detected tab — but never while the operator is setting a timer,
      // and never by stealing focus. ---
      (function wireRightTabs() {
        const tabs = [
          document.getElementById("rtab-timer"),
          document.getElementById("rtab-detections"),
        ];
        if (!tabs[0] || !tabs[1]) return;
        const panelOf = (t) => document.getElementById(t.getAttribute("aria-controls"));
        function select(tab, focus) {
          for (const t of tabs) {
            const on = t === tab;
            t.classList.toggle("active", on);
            t.setAttribute("aria-selected", on ? "true" : "false");
            t.tabIndex = on ? 0 : -1;
            const p = panelOf(t);
            if (p) p.hidden = !on;
          }
          if (focus) tab.focus();
        }
        tabs.forEach((t, i) => {
          t.addEventListener("click", () => select(t, false));
          t.addEventListener("keydown", (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
              e.preventDefault();
              const d = e.key === "ArrowRight" ? 1 : tabs.length - 1;
              select(tabs[(i + d) % tabs.length], true);
            } else if (e.key === "Home") {
              e.preventDefault();
              select(tabs[0], true);
            } else if (e.key === "End") {
              e.preventDefault();
              select(tabs[tabs.length - 1], true);
            }
          });
        });
        // Called by syncDetections after the count updates.
        let prevCount = 0;
        window.__rightTabsOnDetections = function (count) {
          const det = tabs[1];
          if (count > prevCount && det.getAttribute("aria-selected") !== "true") {
            const timerPanel = document.getElementById("rpanel-timer");
            const editingTimer =
              timerPanel && timerPanel.contains(document.activeElement);
            if (!editingTimer) select(det, false); // surface, don't steal focus
          }
          prevCount = count;
        };
      })();

      // --- Center CONTENT tabs: Scriptures | Slides + the presentation slide-picker filmstrip
      // (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §1/§2/§4). Mirrors wireRightTabs (tabs) + pmGrid
      // (bounded thumb cache, IntersectionObserver lazy render, role=option roving tabindex), but
      // wired to the plan/console commands: plan_deck_slides · render_plan_deck_slide · select_slide.
      // Staging is Preview-only (FR-012); only Go Live commits. ---
      (function wireContentTabs() {
        const tabs = [
          document.getElementById("ctab-scriptures"),
          document.getElementById("ctab-slides"),
        ];
        const strip = document.getElementById("slide-strip");
        if (!tabs[0] || !tabs[1] || !strip) return;
        const disabled = (t) => t.getAttribute("aria-disabled") === "true";
        const panelOf = (t) => document.getElementById(t.getAttribute("aria-controls"));
        window.__activeContentTab = "scriptures";
        function select(tab, focus) {
          if (disabled(tab)) return;
          for (const t of tabs) {
            const on = t === tab;
            t.classList.toggle("active", on);
            t.setAttribute("aria-selected", on ? "true" : "false");
            t.tabIndex = on ? 0 : -1;
            const p = panelOf(t);
            if (p) p.hidden = !on;
          }
          window.__activeContentTab = tab === tabs[1] ? "slides" : "scriptures";
          if (focus) tab.focus();
        }
        window.__selectContentTab = (which, focus) =>
          select(which === "slides" ? tabs[1] : tabs[0], focus);
        tabs.forEach((t, i) => {
          t.addEventListener("click", () => select(t, false));
          t.addEventListener("keydown", (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
              e.preventDefault();
              const d = e.key === "ArrowRight" ? 1 : tabs.length - 1;
              const target = tabs[(i + d) % tabs.length];
              if (!disabled(target)) select(target, true);
            } else if (e.key === "Home") {
              e.preventDefault();
              select(tabs[0], true);
            } else if (e.key === "End") {
              e.preventDefault();
              if (!disabled(tabs[tabs.length - 1])) select(tabs[tabs.length - 1], true);
            }
          });
        });

        // Bounded thumbnail cache (mirrors pmGrid's PM_THUMB_MAX — no unbounded growth).
        const THUMB_MAX = 60;
        const thumbCache = new Map(); // "deckId:slideId" -> dataURL
        function thumbPut(key, url) {
          thumbCache.set(key, url);
          while (thumbCache.size > THUMB_MAX) thumbCache.delete(thumbCache.keys().next().value);
        }
        function thumbFail(cv) {
          const c = cv && cv.parentElement;
          if (!c || c.querySelector(".slide-card-fail")) return;
          const s = document.createElement("span");
          s.className = "slide-card-fail";
          s.textContent = "⚠ Can't preview";
          c.appendChild(s);
        }
        async function thumb(deckId, slideId, cv) {
          if (!cv) return;
          const key = deckId + ":" + slideId;
          if (thumbCache.has(key)) {
            const im = new Image();
            // Restore the backing store size (a dropped off-screen card was shrunk to 1×1), then
            // repaint from the bounded cache — no re-render/re-encode.
            im.onload = () => {
              try {
                cv.width = im.naturalWidth || cv.width;
                cv.height = im.naturalHeight || cv.height;
                cv.getContext("2d").drawImage(im, 0, 0);
              } catch (e) {}
            };
            im.src = thumbCache.get(key);
            return;
          }
          try {
            const r = await invoke("render_plan_deck_slide", { deckId: deckId, slideId: slideId, maxW: 320, maxH: 180 });
            if (r && r.available && r.frame && blitFrame(cv, r.frame)) thumbPut(key, cv.toDataURL());
            else thumbFail(cv); // missing media / no frame → honest "can't preview" (never a silent blank)
          } catch (e) { thumbFail(cv); }
        }

        const S = { deckId: null, itemId: null, slides: [], io: null };
        const el = (id) => document.getElementById(id);
        function cards() {
          return Array.prototype.slice.call(strip.querySelectorAll(".slide-card"));
        }
        function stageSlide(i, goLiveToo) {
          if (S.itemId == null) return;
          const slide = S.slides[i];
          if (goLiveToo && S.deckId != null && slide) {
            // Go Live routes the ACTUAL deck slide to the audience output via the authored-slide
            // present path (the same mechanism the deck editor uses) — NOT the plan-item go_live,
            // which would composite only the item title (the host has no deck pixels).
            act(() => invoke("present_plan_deck_slide", { deckId: S.deckId, slideId: slide.slide_id }));
          } else {
            act(() => invoke("select_slide", { itemId: S.itemId, slideIndex: i })); // Preview only (FR-012)
          }
        }
        // Paint the STAGED deck slide into the console Preview panel (#preview-canvas). The host
        // composites only the plan-item TITLE for a deck (it has no deck pixels), so the console
        // renders the real slide operator-side; renderConsole skips its own preview draw while a deck
        // is staged. Cached — re-render only when the staged slide id changes.
        let lastPreviewKey = null;
        async function renderPreviewSlide(deckId, slideId) {
          const cv = document.getElementById("preview-canvas");
          if (!cv || deckId == null || slideId == null) return;
          const key = deckId + ":" + slideId;
          if (key === lastPreviewKey) return;
          // Render the Preview at full 640×360. Do NOT reuse the 320px filmstrip `thumbCache`
          // (that blitted an upscaled, blurry thumbnail into the larger Preview panel). Advance
          // `lastPreviewKey` only AFTER a successful paint, so a transiently-failed render is retried
          // on the next call rather than leaving Preview stale/blank.
          try {
            const r = await invoke("render_plan_deck_slide", { deckId: deckId, slideId: slideId, maxW: 640, maxH: 360 });
            if (r && r.available && r.frame) {
              blitFrame(cv, r.frame);
              lastPreviewKey = key;
            }
          } catch (e) {}
        }
        window.__resetDeckPreviewKey = function () { lastPreviewKey = null; };
        // Filmstrip keyboard (set once on the container; survives card rebuilds). Scoped keys
        // stopPropagation so they don't ALSO fire the global ← Space ⏎ console shortcuts.
        strip.addEventListener("keydown", (e) => {
          const cs = cards();
          if (!cs.length) return;
          const cur = cs.findIndex((c) => c.tabIndex === 0);
          const i = cur < 0 ? 0 : cur;
          // Enter is handled by the global console shortcut (→ goLive() → present the staged deck
          // slide), so let it bubble — don't double-fire here.
          let j = null;
          if (e.key === "ArrowRight" || e.key === "ArrowDown") j = Math.min(cs.length - 1, i + 1);
          else if (e.key === "ArrowLeft" || e.key === "ArrowUp") j = Math.max(0, i - 1);
          else if (e.key === "Home") j = 0;
          else if (e.key === "End") j = cs.length - 1;
          else return;
          e.preventDefault(); e.stopPropagation();
          cs.forEach((c, k) => { c.tabIndex = k === j ? 0 : -1; });
          cs[j].focus();
          stageSlide(j, false); // move + stage to Preview
        });

        function mark(stagedSlide, liveSlideId) {
          const cs = cards();
          cs.forEach((c, i) => {
            const isStaged = i === stagedSlide;
            // LIVE follows the authored slide actually on the output (live_authored_id), matched by
            // slide id — so it marks the slide the audience sees, even if it differs from Preview.
            const isLive = liveSlideId != null && Number(c.dataset.slideId) === liveSlideId;
            c.classList.toggle("staged", isStaged && !isLive);
            c.classList.toggle("live", isLive);
            c.setAttribute("aria-current", isStaged ? "true" : "false");
            c.tabIndex = isStaged ? 0 : -1;
            let tag = c.querySelector(".slide-card-tag");
            if (isStaged || isLive) {
              if (!tag) { tag = document.createElement("span"); tag.className = "slide-card-tag"; c.appendChild(tag); }
              tag.classList.toggle("preview", isStaged && !isLive);
              tag.classList.toggle("live", isLive);
              tag.textContent = isLive ? "LIVE" : "PREVIEW"; // text, never colour-only
            } else if (tag) { tag.remove(); }
            const base = c.dataset.baseLabel || ("Slide " + (i + 1));
            c.setAttribute("aria-label", base + (isLive ? " (live on the audience output)" : isStaged ? " (preview)" : ""));
          });
          const pos = el("slides-pos");
          if (pos) { pos.hidden = cs.length === 0; pos.textContent = "Preview " + (stagedSlide + 1) + " / " + cs.length; }
        }

        async function load(deckId, stagedSlide, liveSlide, hostCount, link) {
          const empty = el("slides-empty");
          const status = el("slides-status");
          strip.innerHTML = "";
          let res = null;
          try { res = await invoke("plan_deck_slides", { deckId: deckId }); } catch (e) { res = null; }
          if (!res || !res.available) { // the linked deck was removed (FR-007) → honest missing state
            strip.hidden = true; empty.hidden = false;
            el("slides-empty-msg").textContent = "Presentation missing — the linked deck was removed.";
            el("slides-empty-sub").textContent = "Re-link it from the service plan.";
            if (status) status.textContent = "Presentation missing.";
            return;
          }
          const slides = res.slides || [];
          S.slides = slides;
          // Self-heal (spec §6): the operator owns the deck, so if the host's stored slide count is
          // absent (a legacy link) or stale (the deck was edited after linking), sync the true count
          // so per-slide staging clamps correctly. One-shot — after the sync hostCount === real.
          if (link && slides.length > 0 && hostCount !== slides.length) {
            const synced = Object.assign({}, link, { slide_count: slides.length });
            act(() => invoke("set_item_content", { itemId: S.itemId, link: synced }));
          }
          if (!slides.length) {
            strip.hidden = true; empty.hidden = false;
            el("slides-empty-msg").textContent = "This presentation has no slides yet.";
            el("slides-empty-sub").textContent = "Open it in Presentations to add slides.";
            if (status) status.textContent = "";
            return;
          }
          strip.hidden = false; empty.hidden = true;
          if (status) status.textContent = "";
          // Release the prior observer before rebuilding (no observer leak on deck switch, Perf-7/L1).
          if (S.io) { try { S.io.disconnect(); } catch (e) {} S.io = null; }
          // Windowed thumbnails: render the visible (± margin) cards, and DROP the backing store of a
          // card that scrolls off-screen (shrink to 1×1) so retained RGBA stays window-bounded, not
          // O(N slides) (spec §2 bounded-memory). Re-entry repaints cheaply from the bounded cache.
          const io = ("IntersectionObserver" in window)
            ? new IntersectionObserver((es) => es.forEach((e) => {
                const cv2 = e.target.querySelector("canvas");
                if (e.isIntersecting) {
                  thumb(deckId, Number(e.target.dataset.slideId), cv2);
                } else if (cv2 && cv2.width > 1) {
                  cv2.width = 1; cv2.height = 1; // drop the off-screen backing store
                }
              }), { root: strip, rootMargin: "96px" })
            : null;
          S.io = io;
          slides.forEach((s, i) => {
            const card = document.createElement("div");
            card.className = "slide-card";
            card.dataset.slideId = String(s.slide_id);
            card.dataset.index = String(i);
            card.setAttribute("role", "option");
            card.setAttribute("aria-selected", "false");
            card.tabIndex = i === 0 ? 0 : -1;
            card.dataset.baseLabel = "Slide " + (i + 1) + " of " + slides.length + (s.label ? " — " + s.label : "");
            card.setAttribute("aria-label", card.dataset.baseLabel);
            const cv = document.createElement("canvas"); cv.width = 168; cv.height = 94; card.appendChild(cv);
            const n = document.createElement("span"); n.className = "slide-card-n"; n.textContent = String(i + 1); card.appendChild(n);
            card.onclick = () => { cards().forEach((c, k) => { c.tabIndex = k === i ? 0 : -1; }); stageSlide(i, false); };
            card.ondblclick = () => stageSlide(i, true);
            strip.appendChild(card);
            if (io) io.observe(card); else thumb(deckId, s.slide_id, cv);
          });
          mark(stagedSlide, liveSlide);
          // Now that S.slides is fresh, publish the staged slide (for GO LIVE) + paint the Preview panel.
          const psid = (slides[stagedSlide] || {}).slide_id;
          window.__consoleDeckPreview = psid != null ? { deckId: deckId, slideId: psid } : null;
          renderPreviewSlide(deckId, psid);
        }

        function setEnabled(on, count) {
          const tab = tabs[1];
          const pill = el("slides-count");
          if (on) {
            tab.removeAttribute("aria-disabled");
            if (pill && count != null) { pill.hidden = false; pill.textContent = String(count); }
          } else {
            tab.setAttribute("aria-disabled", "true");
            if (pill) pill.hidden = true;
          }
        }

        // Inspection hook (bounded-memory verification, spec §2): the thumbnail LRU size, the count of
        // cards still holding a full-resolution backing store, and a force-render-all that walks every
        // card so a test can prove the LRU evicts past its cap.
        window.__slidesDebug = {
          thumbCacheSize: () => thumbCache.size,
          liveCanvas: () => cards().filter((c) => { const cv = c.querySelector("canvas"); return cv && cv.width > 1; }).length,
          renderAll: async () => { for (const c of cards()) { await thumb(S.deckId, Number(c.dataset.slideId), c.querySelector("canvas")); } },
        };

        // Called from render() on every view. Detects a staged presentation (a slide_group item
        // linked to a deck), enables + auto-surfaces the Slides tab, (re)loads the filmstrip when the
        // presentation changes, and re-marks the staged/live slide otherwise.
        window.__syncSlides = function (view) {
          const idx = view && view.staged_index;
          const staged = (idx != null && view.items) ? view.items[idx] : null;
          const isPres = !!(staged && staged.kind === "slide_group" && staged.link && staged.link.kind === "deck");
          if (!isPres) {
            setEnabled(false);
            S.deckId = null; S.itemId = null;
            // Hand the Preview panel back to the host composite (renderConsole resumes drawing it).
            window.__consoleDeckPreview = null;
            if (window.__resetDeckPreviewKey) window.__resetDeckPreviewKey();
            if (window.__activeContentTab === "slides") window.__selectContentTab("scriptures", false);
            return;
          }
          const deckId = staged.link.id;
          const itemId = staged.id;
          // The STAGED (Preview) cursor: staged_slide_index when present (distinct from slide_index,
          // which is LIVE-first). Falls back for an older host.
          const stagedSlide = (staged.staged_slide_index != null)
            ? staged.staged_slide_index
            : (staged.slide_index || 0);
          // LIVE follows the authored slide actually on the output. Presenting a deck slide routes it
          // via present_authored_slide, which sets live_authored_id (a slide id) — matched by id in
          // mark(), so PREVIEW (cursor) and LIVE (on-air slide) can be different slides of the deck.
          const liveSlideId = (view.live_authored_id != null) ? view.live_authored_id : null;
          setEnabled(true, staged.slide_count != null ? staged.slide_count : (S.slides.length || null));
          const nameEl = el("slides-deck-name");
          if (nameEl) nameEl.textContent = staged.title || "Slides";
          // The staged deck slide (for the global GO LIVE button + the Preview panel render) is
          // published by load()/mark() below, once S.slides is current for this presentation.
          if (S.deckId !== deckId || S.itemId !== itemId) {
            S.deckId = deckId; S.itemId = itemId;
            // Edge-triggered auto-surface (a NEW presentation was staged) — never steal focus, and
            // never yank the operator out of a scripture search they're typing.
            const q = el("scripture-q");
            if (window.__activeContentTab !== "slides" && !(q && document.activeElement === q)) {
              window.__selectContentTab("slides", false);
            }
            load(deckId, stagedSlide, liveSlideId, staged.slide_count, staged.link);
          } else {
            mark(stagedSlide, liveSlideId);
            // Refresh the staged slide id after any reorder/re-mark, then paint the Preview panel.
            const sid = (S.slides[stagedSlide] || {}).slide_id;
            window.__consoleDeckPreview = sid != null ? { deckId: deckId, slideId: sid } : null;
            renderPreviewSlide(deckId, sid);
          }
        };
      })();

      // --- Command palette (⌘K) + Shortcuts modal (app menu → footer buttons). Searches
      // and runs the same navigation / transport / emergency actions the console already
      // exposes — no new host commands, just a faster way to reach them. Exposed to the
      // global keymap via window.__cmdPalette so ⌘K + Esc integrate with the chords. ---
      (function wireCommandPalette() {
        const palette = document.getElementById("cmd-palette");
        const input = document.getElementById("cmd-input");
        const listEl = document.getElementById("cmd-list");
        const shortcuts = document.getElementById("shortcuts");
        if (!palette || !input || !listEl) return;
        const emptyEl = palette.querySelector(".cmd-empty");

        const commands = () => {
          const cmds = [];
          navItems.forEach((it) => {
            if (!it.dataset.surface || it.getAttribute("aria-disabled") === "true") return;
            const t = it.querySelector(".nav-t");
            const name = (t ? t.textContent : it.textContent).trim();
            cmds.push({ label: "Go to " + name, ico: "→", run: () => navGo(it) });
          });
          cmds.push({ label: "Go Live", ico: "●", sub: "⏎", run: () => act(() => invoke("go_live")) });
          cmds.push({ label: "Next item", ico: "▶", sub: "Space", run: () => act(() => invoke("next")) });
          cmds.push({ label: "Previous item", ico: "◀", sub: "←", run: () => act(() => invoke("previous")) });
          cmds.push({ label: "Blackout output", ico: "■", sub: "B", run: () => toggleBlackout() });
          cmds.push({ label: "Clear output", ico: "✕", sub: "Esc Esc", run: () => clearAll() });
          // Presentation-surface actions are offered only while that surface is active (they act
          // on the authored deck) — keyboard-first parity for the slide editor (FR-021/022).
          const pmActive = document.getElementById("surface-presentation");
          if (pmActive && pmActive.classList.contains("active") && typeof pmMode !== "undefined") {
            if (pmMode === "grid") {
              // Grid mode owns presenting — present the cursor slide (double-click / Enter equivalent).
              cmds.push({ label: "Present slide", ico: "▶", run: () => { if (typeof pmGridGoLive === "function") pmGridGoLive(pmGridCursor); } });
            } else if (pmMode === "editor") {
              cmds.push({ label: "Add slide", ico: "+", run: () => { if (typeof pmAddSlide === "function") pmAddSlide(); } });
              cmds.push({ label: "Present slide", ico: "▶", run: () => { if (typeof pmPresent === "function") pmPresent(); } });
              cmds.push({ label: "Undo slide edit", ico: "↶", sub: "⌘Z", run: () => { if (typeof pmUndo === "function") pmUndo(); } });
              cmds.push({ label: "Redo slide edit", ico: "↷", sub: "⌘⇧Z", run: () => { if (typeof pmRedo === "function") pmRedo(); } });
            }
          }
          cmds.push({ label: "Keyboard shortcuts", ico: "⌨", run: () => openShortcuts() });
          return cmds;
        };

        let filtered = [];
        let active = 0;
        // Point the combobox at the active option so a screen reader announces it
        // (aria-activedescendant is declared on #cmd-input; each option carries an id).
        const syncActiveDescendant = () => {
          if (filtered.length) input.setAttribute("aria-activedescendant", "cmd-opt-" + active);
          else input.removeAttribute("aria-activedescendant");
        };
        const paint = () => {
          Array.from(listEl.children).forEach((li, i) => {
            const on = i === active;
            li.classList.toggle("active", on);
            li.setAttribute("aria-selected", on ? "true" : "false");
            if (on && li.scrollIntoView) li.scrollIntoView({ block: "nearest" });
          });
          syncActiveDescendant();
        };
        const render = () => {
          const q = input.value.trim().toLowerCase();
          filtered = commands().filter((c) => !q || c.label.toLowerCase().includes(q));
          if (active >= filtered.length) active = Math.max(0, filtered.length - 1);
          listEl.innerHTML = "";
          filtered.forEach((c, i) => {
            const li = document.createElement("li");
            li.className = "cmd-item" + (i === active ? " active" : "");
            li.id = "cmd-opt-" + i;
            li.setAttribute("role", "option");
            li.setAttribute("aria-selected", i === active ? "true" : "false");
            const ico = document.createElement("span");
            ico.className = "cmd-item-ico"; ico.setAttribute("aria-hidden", "true");
            ico.textContent = c.ico || "•";
            const label = document.createElement("span");
            label.textContent = c.label; // command labels are static, but textContent regardless
            li.appendChild(ico);
            li.appendChild(label);
            if (c.sub) {
              const s = document.createElement("span");
              s.className = "cmd-item-sub"; s.textContent = c.sub;
              li.appendChild(s);
            }
            li.addEventListener("mousemove", () => { if (active !== i) { active = i; paint(); } });
            li.addEventListener("click", () => runAt(i));
            listEl.appendChild(li);
          });
          if (emptyEl) emptyEl.hidden = filtered.length > 0;
          syncActiveDescendant();
        };
        const runAt = (i) => { const c = filtered[i]; if (!c) return; closePalette(); c.run(); };

        // Focus management for the modal contract (role=dialog aria-modal): remember what
        // was focused before the modal stack opened and restore it on close. Palette and
        // Shortcuts are mutually exclusive; `switching` suppresses a restore during a
        // palette↔shortcuts handoff so focus doesn't bounce to the opener mid-transition.
        // Opening either also closes the app menu, so ⌘K over an open menu is well-behaved.
        let opener = null, switching = false;
        const modalOpen = () => !palette.hidden || (shortcuts && !shortcuts.hidden);
        const restoreFocus = () => {
          if (switching) return;
          const o = opener; opener = null;
          // Idempotent: once a session's focus has been restored, opener is null, so a second
          // call (e.g. closeAll() closing both modals, or the global Esc + the input's own Esc
          // both firing) must NOT steal focus to the menu button — leave it on the restored
          // element. Only the FIRST close of a session restores.
          if (!o) return;
          if (document.contains(o) && o.offsetParent !== null) { o.focus(); return; }
          const mb = document.getElementById("app-menu-btn");
          if (mb) mb.focus();
        };

        function openPalette() {
          if (!modalOpen()) opener = document.activeElement;
          switching = true; closeAppMenu(); closeShortcuts(); switching = false;
          palette.hidden = false;
          active = 0; input.value = ""; render(); input.focus();
        }
        function closePalette() { palette.hidden = true; restoreFocus(); }
        function openShortcuts() {
          if (!modalOpen()) opener = document.activeElement;
          switching = true; closeAppMenu(); closePalette(); switching = false;
          if (shortcuts) { shortcuts.hidden = false; const c = document.getElementById("sc-close"); if (c) c.focus(); }
        }
        function closeShortcuts() { if (shortcuts) shortcuts.hidden = true; restoreFocus(); }

        input.addEventListener("input", () => { active = 0; render(); });
        input.addEventListener("keydown", (e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(filtered.length - 1, active + 1); paint(); }
          else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(0, active - 1); paint(); }
          else if (e.key === "Enter") { e.preventDefault(); runAt(active); }
          else if (e.key === "Escape") { e.preventDefault(); closePalette(); }
          // Trap Tab: #cmd-input is the only focusable node in the dialog, so keep it here
          // (aria-modal requires focus not to escape to the page behind the palette).
          else if (e.key === "Tab") { e.preventDefault(); }
        });
        palette.addEventListener("click", (e) => { if (e.target === palette) closePalette(); });
        if (shortcuts) shortcuts.addEventListener("click", (e) => { if (e.target === shortcuts) closeShortcuts(); });
        const scClose = document.getElementById("sc-close");
        if (scClose) scClose.addEventListener("click", closeShortcuts);
        // Shortcuts modal: Esc closes; Tab is trapped to the close button (its only
        // focusable node) so focus can't fall behind the role=dialog overlay.
        if (shortcuts) shortcuts.addEventListener("keydown", (e) => {
          if (e.key === "Escape") { e.preventDefault(); closeShortcuts(); }
          else if (e.key === "Tab") { e.preventDefault(); if (scClose) scClose.focus(); }
        });
        document.querySelectorAll("[data-open]").forEach((b) => {
          b.addEventListener("click", () => {
            closeAppMenu();
            if (b.dataset.open === "palette") openPalette();
            else if (b.dataset.open === "shortcuts") openShortcuts();
          });
        });

        // Bridge for the global keymap: ⌘K opens the palette; Esc closes an open modal
        // (and, crucially, the double-Esc clear-all does NOT arm while a modal is open).
        window.__cmdPalette = {
          open: openPalette,
          isOpen: () => !palette.hidden || (shortcuts && !shortcuts.hidden),
          closeAll: () => { closePalette(); closeShortcuts(); },
        };
      })();

      // Host connection pill: green "Connected" while the view poll succeeds; amber
      // "Reconnecting…" when a poll throws (a remote host dropped). Local mode never fails.
      // Only touch the DOM when the state actually FLIPS — the 1s poll must not rewrite the
      // pill every second (no needless class/text/attr churn on the hot path).
      let lastConn = null;
      const setConn = (ok) => {
        if (ok === lastConn) return;
        lastConn = ok;
        const pill = document.getElementById("conn-pill");
        const label = document.getElementById("conn-label");
        if (!pill) return;
        pill.classList.toggle("reconnecting", !ok);
        if (label) label.textContent = ok ? "Connected" : "Reconnecting…";
        pill.setAttribute("aria-label", ok ? "Host connected" : "Reconnecting to host");
      };
      (async () => {
        try { render(await invoke("view")); setConn(true); }
        catch (e) { setConn(false); }
        // The console's deck-link chips resolve names/missing status against planDecks, which is
        // otherwise only loaded on the plan surface — so a deck-linked item on the console showed a
        // generic "▦ presentation" and never the "⚠ missing" state (FR-007). Load the list once at
        // boot, then bust the render cache so the chips repaint with resolved names (bounded: one
        // deck_list, cached thereafter).
        try {
          await planLoadDecks();
          lastRendered = "";
          render(await invoke("view"));
        } catch (e) { /* offline / no host — chips stay generic, harmless */ }
      })();
      // "Open in Live ▶" (Service Plan header) is a PURE surface switch to the Live Console — never
      // a go-live (a plan edit must not commit to Live). It is a plain button, not a .nav-item, so
      // navGo's .nav-item delegation does not cover it; wire it explicitly, nav-only.
      const planOpenLive = document.getElementById("plan-open-live");
      if (planOpenLive) planOpenLive.onclick = () => showSurface("console");
      // Poll so a running countdown ticks in the UI (the host advances it each frame).
      setInterval(async () => {
        try {
          render(await invoke("view"));
          setConn(true);
        } catch (e) {
          setConn(false);
        }
      }, 1000);

      // =====================================================================================
      // Presentation & Media (Design 2.0, Figma node 329:124) — the authored slide editor +
      // media library. Its own render loop (renderPresentation from a DeckView), independent of
      // the console's render(OperatorView): deck_* commands return a separate DeckView, so the
      // LAN-shared OperatorView (and its pinned wire fixtures) is never touched. The slide canvas
      // shows a NATIVE-composited preview (render_deck_slide → blitFrame), never an HTML render.
      // =====================================================================================
      let pmDv = null; // last DeckView
      let pmMediaFilter = "all";
      let pmMediaQuery = "";
      let pmDrag = null; // active canvas drag: {index, startX, startY, ox, oy, w, h}
      let pmRightMode = "media"; // right panel: "media" | "inspector"
      let pmLastSelKey = null; // (slide id):(element index) of the last selection, for auto-switch
      let pmReplaceTarget = null; // element index awaiting a media-cell pick to replace its image
      let pmRowId = 0; // monotonic id source so each inspector control gets a <label for> (a11y)
      let pmFontsLoading = false; // in-flight guard so concurrent activations don't double-fetch fonts

      const pmEl = (id) => document.getElementById(id);

      let pmLastAct = null; // { fn, opName } of the last deck action, for the error-banner Retry
      let pmToastTimer = null; // bounded auto-dismiss timer for the action toast
      let pmFonts = null; // system font families (loaded once, shared by the Text inspector)
      let pmBusyCount = 0; // in-flight deck-command count (a COUNTER, not a flag, so overlapping
      // commands don't clobber each other's busy state — the earlier one's finally must not clear
      // busy while a later one is still running).

      // One round trip: run a deck command and re-render from the returned DeckView. Sets an
      // `aria-busy` loading state on the canvas for the duration; on rejection shows the error
      // banner (role=alert) with a Retry. Returns true on success, false on failure (so callers
      // like delete-with-toast only fire their follow-up when the command actually applied).
      async function pAct(fn, opName) {
        pmLastAct = { fn, opName };
        pmSetBusy(true);
        try {
          pmDv = await fn();
          pmClearError();
          renderPresentation(pmDv);
          return true;
        } catch (e) {
          console.error("[SelahCue] deck action failed", e);
          pmShowError(opName);
          return false;
        } finally {
          pmSetBusy(false);
        }
      }

      // Reflect the canvas loading state: `aria-busy` + a `.busy` skeleton shimmer while ANY deck
      // command is in flight (C-004). Reference-counted so overlapping round-trips stay busy until
      // the LAST one settles. Assistive tech hears "busy"; sighted users see the shimmer.
      function pmSetBusy(on) {
        pmBusyCount = Math.max(0, pmBusyCount + (on ? 1 : -1));
        const box = pmEl("pm-canvas-box");
        if (!box) return;
        const busy = pmBusyCount > 0;
        box.setAttribute("aria-busy", busy ? "true" : "false");
        box.classList.toggle("busy", busy);
      }

      // Show the error banner (role=alert) for a rejected deck command; Retry re-runs the last one.
      // Un-hide FIRST, then set the text: an alert region must be ON the a11y tree when its content
      // changes to be reliably announced (a `hidden`→populate→unhide order is not — WKWebView/VO).
      function pmShowError(opName) {
        const banner = pmEl("pm-error");
        const msg = pmEl("pm-error-msg");
        if (!banner || !msg) return;
        banner.hidden = false;
        msg.textContent = "Couldn't " + (opName || "complete that action") + " — please retry.";
      }
      function pmClearError() {
        const banner = pmEl("pm-error");
        if (banner) banner.hidden = true;
      }

      // A transient action toast (role=status) with an optional action button (e.g. Undo). Bounded:
      // one toast at a time, auto-dismissed after ~7s (cleared timer, no unbounded stack). Un-hidden
      // BEFORE its content is set so the live region announces the change (see pmShowError).
      function pmToast(message, actionLabel, onAction) {
        const t = pmEl("pm-toast");
        if (!t) return;
        if (pmToastTimer) { clearTimeout(pmToastTimer); pmToastTimer = null; }
        t.hidden = false;
        t.innerHTML = "";
        const msg = document.createElement("span");
        msg.className = "pm-toast-msg";
        msg.textContent = message;
        t.appendChild(msg);
        if (actionLabel && onAction) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "pm-toast-action";
          btn.textContent = actionLabel;
          btn.onclick = () => { pmToastDismiss(); onAction(); };
          t.appendChild(btn);
        }
        pmToastTimer = setTimeout(pmToastDismiss, 7000);
      }
      function pmToastDismiss() {
        const t = pmEl("pm-toast");
        // If focus is on the toast's Undo button when it dismisses (e.g. the 7s timer fires), don't
        // strand it on <body> — land it on the canvas (⌘Z still undoes). WCAG 2.4.3.
        if (t && t.contains(document.activeElement)) { const cv = pmEl("pm-canvas"); if (cv) cv.focus(); }
        if (t) { t.hidden = true; t.innerHTML = ""; }
        if (pmToastTimer) { clearTimeout(pmToastTimer); pmToastTimer = null; }
      }

      // A modal confirm dialog (role=alertdialog) for a destructive action: Cancel-focused,
      // Esc cancels, focus is trapped inside, and the backdrop click cancels (C-001/C-002/C-009).
      function pmConfirm(opts) {
        // One modal at a time: never stack confirms (would duplicate the fixed ids + double-trap).
        if (document.querySelector(".pm-confirm-back")) return;
        const prevFocus = document.activeElement;
        const back = document.createElement("div");
        back.className = "pm-confirm-back";
        const dlg = document.createElement("div");
        dlg.className = "pm-confirm";
        dlg.setAttribute("role", "alertdialog");
        dlg.setAttribute("aria-modal", "true");
        const titleId = "pm-confirm-title";
        const bodyId = "pm-confirm-body";
        dlg.setAttribute("aria-labelledby", titleId);
        const h = document.createElement("h2");
        h.className = "pm-confirm-title";
        h.id = titleId;
        h.textContent = opts.title || "Are you sure?";
        dlg.appendChild(h);
        const p = document.createElement("p");
        p.className = "pm-confirm-body";
        p.id = bodyId;
        p.textContent = opts.body || "";
        dlg.appendChild(p);
        // The safety warning ("… is LIVE", "Used on N slides") MUST be in the accessible description
        // — otherwise AT announces only the generic body and the consequence is silent (WCAG 4.1.2).
        let describedBy = bodyId;
        if (opts.warning) {
          const w = document.createElement("p");
          w.className = "pm-confirm-warn";
          w.id = "pm-confirm-warn";
          w.textContent = opts.warning;
          dlg.appendChild(w);
          describedBy = bodyId + " pm-confirm-warn";
        }
        dlg.setAttribute("aria-describedby", describedBy);
        const row = document.createElement("div");
        row.className = "pm-confirm-actions";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "pm-btn-ghost";
        cancel.textContent = "Cancel";
        const ok = document.createElement("button");
        ok.type = "button";
        ok.className = "pm-btn-danger";
        ok.textContent = opts.confirmLabel || "Delete";
        row.appendChild(cancel);
        row.appendChild(ok);
        dlg.appendChild(row);
        back.appendChild(dlg);
        document.body.appendChild(back);

        const close = () => {
          document.removeEventListener("keydown", onKey, true);
          back.remove();
          if (prevFocus && prevFocus.focus) prevFocus.focus();
        };
        cancel.onclick = close;
        ok.onclick = () => { close(); if (opts.onConfirm) opts.onConfirm(); };
        back.onmousedown = (ev) => { if (ev.target === back) close(); };
        // Focus trap + Esc: keep Tab within [cancel, ok]; Esc cancels (WCAG modal semantics).
        const onKey = (ev) => {
          if (ev.key === "Escape") { ev.preventDefault(); close(); return; }
          if (ev.key === "Tab") {
            const els = [cancel, ok];
            const i = els.indexOf(document.activeElement);
            ev.preventDefault();
            const next = ev.shiftKey ? (i <= 0 ? els.length - 1 : i - 1) : (i >= els.length - 1 ? 0 : i + 1);
            els[next].focus();
          }
        };
        document.addEventListener("keydown", onKey, true);
        cancel.focus(); // Cancel-focused: the safe default for a destructive confirm.
      }

      // Load the machine's font families once (shared with the Text inspector Font picker). After
      // the async load, re-render the inspector so an open Text element gets its populated picker.
      async function pmLoadFonts() {
        if (pmFonts !== null || pmFontsLoading) return; // cached OR already in flight → don't re-fetch
        pmFontsLoading = true;
        try {
          pmFonts = await invoke("system_fonts");
        } catch (e) {
          console.error(e);
          pmFonts = [];
        }
        pmFontsLoading = false;
        if (pmDv && pmRightMode === "inspector") pmRenderInspector(pmDv);
      }

      // Delete the selected element, then offer an Undo toast (⌘Z-backed) — but ONLY if an element
      // was actually removed (a stale/out-of-range index is a host no-op → no toast, no misleading
      // Undo that would pop an unrelated edit). Focus, orphaned when the inspector rebuilds/hides,
      // lands back on the canvas (WCAG 2.4.3).
      async function pmDeleteElement(idx) {
        const before = pmElements().length;
        const ok = await pAct(() => invoke("deck_remove_element", { index: idx }), "delete the element");
        if (ok && pmElements().length < before) {
          if (!document.body.contains(document.activeElement) || document.activeElement === document.body) {
            const cv = pmEl("pm-canvas"); if (cv) cv.focus();
          }
          pmToast("Element deleted", "Undo", () => pmUndo());
        }
      }

      // Referenced by showSurface + the command palette (via typeof guards) — keep as bare names.
      function pmActivate() { pmSetMode("library"); pmLibLoad(); pmLoadFonts(); }

      // === Presentations Library (view mode of the Presentation surface) ==========================
      // A text-input modal (role=dialog) for New / Rename — reuses the confirm modal chrome + trap.
      function pmPrompt(opts) {
        if (document.querySelector(".pm-confirm-back")) return;
        const prevFocus = document.activeElement;
        const back = document.createElement("div"); back.className = "pm-confirm-back";
        const dlg = document.createElement("div"); dlg.className = "pm-confirm"; dlg.setAttribute("role", "dialog"); dlg.setAttribute("aria-modal", "true");
        dlg.setAttribute("aria-labelledby", "pm-prompt-title");
        const h = document.createElement("h2"); h.className = "pm-confirm-title"; h.id = "pm-prompt-title"; h.textContent = opts.title || "Name"; dlg.appendChild(h);
        const field = document.createElement("div"); field.style.display = "flex"; field.style.flexDirection = "column"; field.style.gap = "6px";
        const lab = document.createElement("label"); lab.className = "pm-insp-lbl"; lab.textContent = opts.label || "Name"; lab.htmlFor = "pm-prompt-input";
        const input = document.createElement("input"); input.type = "text"; input.id = "pm-prompt-input"; input.className = "pm-insp-ctrl"; input.value = opts.value || ""; input.style.width = "100%"; input.style.maxWidth = "none"; input.setAttribute("aria-label", opts.label || "Name");
        field.appendChild(lab); field.appendChild(input); dlg.appendChild(field);
        const row = document.createElement("div"); row.className = "pm-confirm-actions";
        const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "pm-btn-ghost"; cancel.textContent = "Cancel";
        const ok = document.createElement("button"); ok.type = "button"; ok.className = "pm-btn-primary"; ok.textContent = opts.confirmLabel || "OK";
        row.appendChild(cancel); row.appendChild(ok); dlg.appendChild(row);
        back.appendChild(dlg); document.body.appendChild(back);
        const close = () => { document.removeEventListener("keydown", onKey, true); back.remove(); if (prevFocus && prevFocus.focus) prevFocus.focus(); };
        const submit = () => { const v = input.value; close(); if (opts.onConfirm) opts.onConfirm(v); };
        cancel.onclick = close; ok.onclick = submit;
        back.onmousedown = (ev) => { if (ev.target === back) close(); };
        const onKey = (ev) => {
          if (ev.key === "Escape") { ev.preventDefault(); close(); }
          else if (ev.key === "Enter" && document.activeElement === input) { ev.preventDefault(); submit(); }
          else if (ev.key === "Tab") { const els = [input, cancel, ok]; const i = els.indexOf(document.activeElement); ev.preventDefault(); const n = ev.shiftKey ? (i <= 0 ? els.length - 1 : i - 1) : (i >= els.length - 1 ? 0 : i + 1); els[n].focus(); }
        };
        document.addEventListener("keydown", onKey, true);
        input.focus(); input.select();
      }

      // === Service-plan content linking (ADR-0020) — link a scripture / deck to a plan item ===
      // The read side (link status chips) + the write side (a picker → `set_item_content`).
      // Deck names/missing-status resolve against a lazily-loaded deck list (the console does
      // not otherwise load it); scripture uses the host's `scripture_search` + translation list.
      let planDecks = null; // cached [{id,name,slides}] or null (not yet loaded)
      async function planLoadDecks() {
        try {
          const r = await invoke("deck_list");
          planDecks = (r && r.decks) || [];
        } catch (e) {
          console.error(e);
          // Load FAILED — stay UNRESOLVED (null), not empty. planLinkChip only shows "⚠ missing"
          // when planDecks is a loaded list lacking the id; leaving it null renders the generic
          // chip instead of falsely flagging every deck-linked item as missing on a transient error.
          planDecks = null;
        }
        return planDecks || [];
      }
      function planDeckName(id) {
        if (!planDecks) return null;
        const d = planDecks.find((x) => x.id === id);
        return d ? d.name : null;
      }
      // Translations the host offers — reuse the Scriptures browser's populated <select>
      // so the picker never invents a code the host can't stage.
      function planTranslations() {
        const sel = document.getElementById("translation");
        if (sel && sel.options.length) return Array.from(sel.options).map((o) => o.value);
        return ["KJV", "WEB"];
      }
      function planLinkChip(link) {
        const el = document.createElement("span");
        el.className = "link-chip link-" + link.kind;
        if (link.kind === "scripture") {
          el.textContent =
            "✦ " + (link.reference || "scripture") + (link.translation ? " · " + link.translation : "");
        } else if (link.kind === "deck") {
          const name = planDeckName(link.id);
          if (planDecks && !name) {
            // The deck list is loaded and this id is gone → the plan item is missing content.
            el.className = "link-chip link-missing";
            el.textContent = "⚠ presentation missing";
          } else {
            el.textContent = "▦ " + (name || "presentation");
          }
        } else if (link.kind === "media") {
          el.textContent = "▷ media";
        } else {
          el.textContent = link.kind;
        }
        return el;
      }

      // A list-body modal (reuses the confirm chrome + focus-trap) that links a scripture
      // passage or a deck to `item`, or unlinks it. Commits via `set_item_content` — a plan
      // edit that never changes Live (WKWebView-safe DOM overlay; no <dialog>).
      function openLinkModal(item) {
        if (document.querySelector(".pm-confirm-back")) return; // one modal at a time
        const isScripture = item.kind === "scripture";
        const prevFocus = document.activeElement;
        const back = document.createElement("div");
        back.className = "pm-confirm-back";
        const dlg = document.createElement("div");
        dlg.className = "pm-confirm pm-link";
        dlg.setAttribute("role", "dialog");
        dlg.setAttribute("aria-modal", "true");
        dlg.setAttribute("aria-labelledby", "pm-link-title");
        const h = document.createElement("h2");
        h.className = "pm-confirm-title";
        h.id = "pm-link-title";
        h.textContent = isScripture ? "Link a scripture" : "Link a presentation";
        dlg.appendChild(h);
        const sub = document.createElement("p");
        sub.className = "pm-confirm-body";
        // Context-neutral copy: this modal opens from BOTH the console (where selecting a row
        // stages Preview) and the builder (where it does not) — so it must not claim a
        // select-to-Preview action. It only sets the item's content; it never changes Live (§9).
        sub.textContent = "Linking sets this item's content — it never changes Live output.";
        dlg.appendChild(sub);
        const body = document.createElement("div");
        body.className = "pm-link-body";
        dlg.appendChild(body);
        // Inline error (role=alert): a host-rejected reference/deck leaves the plan UNCHANGED, so
        // the modal stays open and announces the failure rather than closing on a silent no-op.
        const err = document.createElement("p");
        err.className = "pm-link-err";
        err.setAttribute("role", "alert");
        err.hidden = true;
        dlg.appendChild(err);
        const actions = document.createElement("div");
        actions.className = "pm-confirm-actions";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "pm-btn-ghost";
        cancel.textContent = "Cancel";
        actions.appendChild(cancel);
        dlg.appendChild(actions);
        back.appendChild(dlg);
        document.body.appendChild(back);

        const close = () => {
          document.removeEventListener("keydown", onKey, true);
          back.remove();
          if (prevFocus && prevFocus.focus) prevFocus.focus();
        };
        // Disable every control while a command is in flight (aria-busy so AT knows the dialog is
        // working) — prevents a double-submit and the close-before-resolve race.
        const setBusy = (on) => {
          dlg.setAttribute("aria-busy", on ? "true" : "false");
          dlg.querySelectorAll("button, input, select").forEach((c) => {
            c.disabled = on;
          });
        };
        const showErr = (msg) => {
          err.textContent = msg;
          err.hidden = false;
        };
        const commit = (link) => {
          err.hidden = true;
          setBusy(true);
          // Keep the modal OPEN until the host confirms. set_item_content rejects an unparseable
          // reference / unknown deck and leaves the plan unchanged, so closing optimistically would
          // hide the failure. Close only on success; on rejection re-enable + surface an inline
          // error. The returned OperatorView refreshes the console AND (if open) the builder — a
          // plan edit that never changes Live.
          invoke("set_item_content", { itemId: item.id, link })
            .then((v) => {
              // Restore focus to the item after the rebuild (WCAG 2.4.3). close() calls
              // prevFocus.focus() on the opener button, but the following render/planRenderBuilder
              // DESTROY that button — so re-target focus deliberately AFTER the rebuild: the
              // run-sheet row on the builder, or the row's link control on the console.
              const ps = document.getElementById("surface-plan");
              const planActive = !!(ps && ps.classList.contains("active"));
              if (planActive) planFocusAfterRender = { kind: "row", id: item.id };
              close();
              lastRendered = "";
              render(v);
              if (planActive && typeof planRenderBuilder === "function") {
                planRenderBuilder(v);
              } else {
                const btn = document.querySelector('#plan .item[data-item-id="' + item.id + '"] .plan-link-btn');
                if (btn) btn.focus();
              }
            })
            .catch((e) => {
              console.error(e);
              setBusy(false);
              showErr(
                link
                  ? "The host couldn't link that — check the reference or presentation and try again."
                  : "The host couldn't unlink this item."
              );
            });
        };
        cancel.onclick = close;
        back.onmousedown = (ev) => {
          if (ev.target === back) close();
        };
        // Focus trap + Esc (WCAG 2.4.3 / 2.1.1): the background console (which holds live-control
        // buttons like Go Live / Next) is NOT inert, so Tab MUST be contained within the dialog —
        // otherwise focus could land on a live-control button behind the backdrop and Enter would
        // fire it (a live-cueing-invariant breach). The focusable set changes as search hits / deck
        // rows appear, so it is queried live on each Tab rather than captured once.
        const onKey = (ev) => {
          if (ev.key === "Escape") {
            ev.preventDefault();
            close();
            return;
          }
          if (ev.key === "Tab") {
            // Visible + enabled focusables, queried live. Use getClientRects/offset size (not
            // offsetParent, which is null for a position:fixed dialog) so the trap works in the
            // real WKWebView shell where the modal is fixed-positioned.
            const els = Array.prototype.filter.call(
              dlg.querySelectorAll("button, input, select, [tabindex]"),
              (n) => !n.disabled && n.tabIndex !== -1 && (n.offsetWidth > 0 || n.offsetHeight > 0 || n.getClientRects().length > 0)
            );
            ev.preventDefault();
            if (!els.length) return;
            const i = els.indexOf(document.activeElement);
            const next = ev.shiftKey ? (i <= 0 ? els.length - 1 : i - 1) : (i >= els.length - 1 ? 0 : i + 1);
            els[next].focus();
          }
        };
        document.addEventListener("keydown", onKey, true);
        // An already-linked item can be unlinked (clears the reference; the deck/passage is untouched).
        if (item.link) {
          const unlink = document.createElement("button");
          unlink.type = "button";
          unlink.className = "pm-btn-ghost";
          unlink.textContent = "Unlink";
          unlink.onclick = () => commit(null);
          actions.insertBefore(unlink, cancel);
        }
        if (isScripture) {
          // planScriptureBody ends with input.focus() — keep the reference field focused so a
          // keyboard operator can type immediately (don't override it with cancel.focus()).
          planScriptureBody(body, item, commit);
        } else {
          // planDeckBody is async (awaits the deck list); focus Cancel while it loads. The primary
          // action is select-then-confirm, so an initial Cancel focus is the right default here.
          planDeckBody(body, item, commit);
          cancel.focus();
        }
      }

      function planScriptureBody(wrap, item, commit) {
        const cur = item.link && item.link.kind === "scripture" ? item.link : {};
        let chapter = null,
          vStart = null,
          vEnd = null,
          vps = cur.verses_per_slide || null;
        const row = document.createElement("div");
        row.className = "pm-link-row";
        const input = document.createElement("input");
        input.className = "pm-insp-ctrl";
        input.type = "text";
        input.placeholder = "Reference — e.g. Romans 8:28-30";
        input.value = cur.reference || "";
        input.setAttribute("aria-label", "Scripture reference");
        const trans = document.createElement("select");
        trans.className = "pm-insp-ctrl";
        trans.setAttribute("aria-label", "Translation");
        planTranslations().forEach((t) => {
          const o = document.createElement("option");
          o.value = t;
          o.textContent = t;
          if (cur.translation === t) o.selected = true;
          trans.appendChild(o);
        });
        const browse = document.createElement("button");
        browse.type = "button";
        browse.className = "pm-btn-ghost";
        browse.textContent = "Browse";
        const go = document.createElement("button");
        go.type = "button";
        go.className = "pm-btn-primary";
        go.textContent = "Link";
        row.appendChild(input);
        row.appendChild(trans);
        row.appendChild(browse);
        row.appendChild(go);
        wrap.appendChild(row);
        const hits = document.createElement("div");
        hits.className = "pm-link-hits";
        wrap.appendChild(hits);

        // Verse picker (frame 610:124): chapter nav + verse list with the selected range highlighted
        // + verses-per-slide + a gold reference preview. Hidden until a chapter is browsed/loaded.
        // NOTE: no `display` rule on `.pm-verse-picker` in CSS, so the `hidden` attribute still hides it.
        const picker = document.createElement("div");
        picker.className = "pm-verse-picker";
        picker.hidden = true;
        const head = document.createElement("div");
        head.className = "pm-verse-head";
        const chref = document.createElement("span");
        chref.className = "pm-verse-ref";
        const nav = document.createElement("span");
        nav.className = "pm-verse-nav";
        const prev = document.createElement("button");
        prev.type = "button";
        prev.className = "pm-verse-navbtn";
        prev.textContent = "◀";
        prev.setAttribute("aria-label", "Previous chapter");
        const next = document.createElement("button");
        next.type = "button";
        next.className = "pm-verse-navbtn";
        next.textContent = "▶";
        next.setAttribute("aria-label", "Next chapter");
        nav.appendChild(prev);
        nav.appendChild(next);
        head.appendChild(chref);
        head.appendChild(nav);
        const vlist = document.createElement("div");
        vlist.className = "pm-verse-list";
        vlist.setAttribute("role", "listbox");
        vlist.setAttribute("aria-label", "Verses");
        vlist.setAttribute("aria-multiselectable", "true"); // a contiguous verse RANGE can be selected
        const foot = document.createElement("div");
        foot.className = "pm-verse-foot";
        const vpsLbl = document.createElement("label");
        vpsLbl.className = "pm-verse-vps";
        vpsLbl.textContent = "Verses / slide";
        const vpsIn = document.createElement("input");
        vpsIn.type = "number";
        vpsIn.min = "1";
        vpsIn.className = "pm-insp-ctrl";
        vpsIn.value = vps || "";
        vpsIn.setAttribute("aria-label", "Verses per slide");
        vpsIn.oninput = () => {
          vps = parseInt(vpsIn.value, 10) || null;
        };
        vpsLbl.appendChild(vpsIn);
        foot.appendChild(vpsLbl);
        const preview = document.createElement("div");
        preview.className = "pm-verse-preview";
        picker.appendChild(head);
        picker.appendChild(vlist);
        picker.appendChild(foot);
        picker.appendChild(preview);
        wrap.appendChild(picker);

        const refString = () => {
          if (chapter && vStart != null) {
            let r = chapter.reference + ":" + vStart;
            if (vEnd != null && vEnd > vStart) r += "-" + vEnd;
            return r;
          }
          return input.value.trim();
        };
        const updatePreview = () => {
          const r = refString();
          preview.textContent = r ? "✦ " + r + (trans.value ? " · " + trans.value : "") : "";
        };
        const renderVerses = () => {
          if (!chapter) {
            picker.hidden = true;
            return;
          }
          picker.hidden = false;
          chref.textContent = chapter.reference + " (" + chapter.translation + ")";
          prev.disabled = !chapter.prev;
          next.disabled = !chapter.next;
          vlist.innerHTML = "";
          (chapter.verses || []).forEach(([num, text]) => {
            const vr = document.createElement("button");
            vr.type = "button";
            vr.className = "pm-verse";
            vr.dataset.vnum = num;
            vr.setAttribute("role", "option");
            const inRange = vStart != null && (vEnd != null ? num >= vStart && num <= vEnd : num === vStart);
            vr.classList.toggle("sel", inRange);
            vr.setAttribute("aria-selected", inRange ? "true" : "false");
            const n = document.createElement("span");
            n.className = "pm-verse-n";
            n.textContent = num;
            const t = document.createElement("span");
            t.className = "pm-verse-t";
            t.textContent = text;
            vr.appendChild(n);
            vr.appendChild(t);
            vr.onclick = () => {
              // First click (or after a complete range) sets the start; a later click at/after the
              // start extends the range; a click before the start resets to a new start.
              if (vStart == null || vEnd != null) {
                vStart = num;
                vEnd = null;
              } else if (num >= vStart) {
                vEnd = num;
              } else {
                vStart = num;
                vEnd = null;
              }
              renderVerses();
              updatePreview();
            };
            vlist.appendChild(vr);
          });
          updatePreview();
        };
        const loadCh = async (ref) => {
          if (!ref) return;
          try {
            const ch = await invoke("get_chapter", { reference: ref, translation: trans.value || null });
            chapter = ch;
            vStart = ch.verse_start != null ? ch.verse_start : ch.verses && ch.verses[0] ? ch.verses[0][0] : null;
            vEnd = ch.verse_end != null && ch.verse_end > (ch.verse_start || 0) ? ch.verse_end : null;
            renderVerses();
          } catch (e) {
            console.error(e);
          }
        };
        prev.onclick = () => {
          if (chapter && chapter.prev) loadCh(chapter.prev);
        };
        next.onclick = () => {
          if (chapter && chapter.next) loadCh(chapter.next);
        };
        browse.onclick = () => loadCh(input.value.trim());

        const doLink = () => {
          const r = refString();
          if (!r) return;
          const link = { kind: "scripture", reference: r, translation: trans.value || null };
          if (vps) link.verses_per_slide = vps;
          commit(link);
        };
        go.onclick = doLink;
        input.onkeydown = (ev) => {
          if (ev.key === "Enter") {
            ev.preventDefault();
            doLink();
          }
        };
        // Live search: clicking a hit loads its chapter so the operator can refine the verse range.
        let t = null;
        input.oninput = () => {
          // Editing the reference invalidates any browsed/seeded chapter so a freshly-typed reference
          // wins on Link — otherwise refString() would keep committing the STALE browsed reference.
          if (chapter) {
            chapter = null;
            vStart = null;
            vEnd = null;
            renderVerses();
          }
          clearTimeout(t);
          t = setTimeout(async () => {
            const q = input.value.trim();
            if (q.length < 2) {
              hits.textContent = "";
              return;
            }
            try {
              const res = await invoke("scripture_search", { query: q, translation: trans.value || null });
              hits.textContent = "";
              (res || []).slice(0, 8).forEach((hit) => {
                const b = document.createElement("button");
                b.type = "button";
                b.className = "pm-link-hit";
                const ref = document.createElement("b");
                ref.textContent = hit.reference;
                const txt = document.createElement("span");
                txt.textContent = " " + (hit.text || "").slice(0, 90);
                b.appendChild(ref);
                b.appendChild(txt);
                b.onclick = () => {
                  input.value = hit.reference;
                  hits.textContent = "";
                  loadCh(hit.reference);
                };
                hits.appendChild(b);
              });
            } catch (e) {
              console.error(e);
            }
          }, 200);
        };
        if (cur.reference) loadCh(cur.reference); // editing an existing link → seed its chapter
        input.focus();
      }

      async function planDeckBody(wrap, item, commit) {
        const loading = document.createElement("p");
        loading.className = "pm-confirm-body";
        loading.textContent = "Loading presentations…";
        wrap.appendChild(loading);
        const decks = await planLoadDecks();
        loading.remove();
        const curId = item.link && item.link.kind === "deck" ? item.link.id : null;
        // Select-then-confirm (handoff §4.2): a click SELECTS a deck (indigo border + a non-colour
        // "✓ Selected" marker); the footer "Link to item" commits it — a mis-click never commits.
        // Only PRESELECT a deck that still exists (a Change… on a deleted deck selects nothing).
        let selId = decks.some((d) => d.id === curId) ? curId : null;

        // Grid / List view toggle (frame 610:390 reuses the Presentations-library grid).
        const bar = document.createElement("div");
        bar.className = "pm-deck-bar";
        const seg = document.createElement("div");
        seg.className = "pm-deck-seg";
        seg.setAttribute("role", "group");
        seg.setAttribute("aria-label", "Presentations view");
        const grid = document.createElement("div");
        grid.className = "pm-deck-grid";
        grid.setAttribute("role", "listbox");
        grid.setAttribute("aria-label", "Presentations");
        const setView = (v) => {
          grid.classList.toggle("as-list", v === "list");
          Array.prototype.forEach.call(seg.children, (b) => {
            const on = b.dataset.view === v;
            b.classList.toggle("on", on);
            b.setAttribute("aria-pressed", on ? "true" : "false");
          });
        };
        [["grid", "▦ Grid"], ["list", "☰ List"]].forEach(([v, label]) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "pm-deck-seg-btn";
          b.dataset.view = v;
          b.textContent = label;
          b.onclick = () => setView(v);
          seg.appendChild(b);
        });
        bar.appendChild(seg);
        wrap.appendChild(bar);
        if (!decks.length) {
          const note = document.createElement("p");
          note.className = "pm-confirm-body";
          note.textContent = "No presentations yet — create one below.";
          wrap.appendChild(note);
        }
        wrap.appendChild(grid);

        const linkBtn = document.createElement("button");
        linkBtn.type = "button";
        linkBtn.className = "pm-btn-primary";
        linkBtn.textContent = "Link to item";
        const refresh = () => {
          Array.prototype.forEach.call(grid.querySelectorAll(".pm-link-hit"), (b) => {
            const on = String(b.dataset.deckId) === String(selId);
            b.classList.toggle("sel", on);
            b.setAttribute("aria-selected", on ? "true" : "false");
            const mark = b.querySelector(".pm-link-sel");
            if (mark) mark.hidden = !on;
          });
          linkBtn.disabled = selId == null;
        };
        decks.forEach((d) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "pm-link-hit pm-deck-card";
          b.dataset.deckId = d.id;
          b.setAttribute("role", "option");
          const thumb = document.createElement("span");
          thumb.className = "pm-deck-thumb";
          thumb.textContent = "▦";
          thumb.setAttribute("aria-hidden", "true");
          const name = document.createElement("b");
          name.className = "pm-deck-cardname";
          name.textContent = d.name;
          const pill = document.createElement("span");
          pill.className = "pm-deck-pill";
          pill.textContent = d.slides + (d.slides === 1 ? " slide" : " slides");
          const sel = document.createElement("span");
          sel.className = "pm-link-sel";
          sel.textContent = "✓ Selected";
          sel.hidden = true;
          b.appendChild(thumb);
          b.appendChild(name);
          b.appendChild(pill);
          b.appendChild(sel);
          b.onclick = () => {
            selId = d.id;
            refresh();
            linkBtn.focus();
          };
          grid.appendChild(b);
        });
        // New-presentation card: creates an "Untitled presentation" and links it (the operator
        // names/builds it via "Open in editor"). Placed OUTSIDE the role=listbox grid — it is an
        // action, not a selectable option. Re-entrancy-guarded (no duplicate decks) and aborts if
        // the dialog was dismissed mid-flight (Escape/Cancel), mirroring commit()'s busy discipline.
        const newCard = document.createElement("button");
        newCard.type = "button";
        newCard.className = "pm-deck-new";
        newCard.setAttribute("aria-label", "New presentation");
        const plus = document.createElement("span");
        plus.className = "pm-deck-thumb";
        plus.textContent = "＋";
        plus.setAttribute("aria-hidden", "true");
        const nlabel = document.createElement("b");
        nlabel.className = "pm-deck-cardname";
        nlabel.textContent = "New presentation";
        newCard.appendChild(plus);
        newCard.appendChild(nlabel);
        let newBusy = false;
        newCard.onclick = async () => {
          if (newBusy) return; // guard double-activation → no duplicate decks
          newBusy = true;
          newCard.disabled = true;
          try {
            const before = (planDecks || []).map((d) => d.id);
            await invoke("deck_new", { name: "Untitled presentation" });
            const after = await planLoadDecks();
            if (!newCard.isConnected) return; // dialog dismissed while deck_new was in flight → don't relink
            const created = after.filter((d) => before.indexOf(d.id) < 0)[0]; // only a genuinely new deck
            if (created) {
              // Carry the deck's slide count to the host (it owns no deck store) so the plan item
              // reports the real count + can stage a specific slide (LIVE-CONSOLE… spec §6).
              commit({ kind: "deck", id: created.id, slide_count: created.slides }); // success → modal closes
            } else {
              newCard.disabled = false;
              newBusy = false;
            }
          } catch (e) {
            console.error(e);
            newCard.disabled = false;
            newBusy = false;
          }
        };
        wrap.appendChild(newCard);

        linkBtn.onclick = () => {
          if (selId != null) {
            // Carry the selected deck's slide count to the host (spec §6) so per-slide staging works.
            const d = (planDecks || []).find((x) => x.id === selId);
            commit({ kind: "deck", id: selId, slide_count: d ? d.slides : undefined });
          }
        };
        const foot = document.createElement("div");
        foot.className = "pm-link-foot";
        foot.appendChild(linkBtn);
        wrap.appendChild(foot);
        setView("grid");
        refresh();
      }

      // === Service Plan builder (the dedicated `plan` surface) =================================
      // A three-column editor (Add-item palette · run sheet · item inspector) over the same host
      // OperatorView the console uses. Editing here never changes Live — "Open in Live" (a nav to
      // the console) is the only path to the live surfaces; selecting an item stages Preview there.
      const PLAN_ADD_KINDS = [
        ["song", "Song"],
        ["scripture", "Scripture"],
        ["slide_group", "Presentation"],
        ["media", "Media"],
        ["announcement", "Announcement"],
        ["timer", "Timer"],
        ["section", "Section"],
      ];
      let planSelectedId = null;
      // After planRenderBuilder blanks + rebuilds the run sheet, keyboard focus would fall to
      // <body>; this records what the last user action should re-focus (the selected row, or a
      // moved row's ↑/↓ button) so focus survives the rebuild (WCAG 2.4.3). Null on a background
      // re-render (poll / link-commit refresh) so it never steals focus.
      let planFocusAfterRender = null;
      function planKindLabel(kind) {
        const f = PLAN_ADD_KINDS.find((k) => k[0] === kind);
        return f ? f[1] : kind;
      }
      function planActivate() {
        planFocusAfterRender = null; // fresh navigation must not inherit a stale reorder intent
        buildPlanPalette();
        // Deck names/missing-status for link chips; then render with resolved names.
        planLoadDecks().then(() => {
          if (document.getElementById("plan-b-list")) invoke("view").then(planRenderBuilder).catch(console.error);
        });
        invoke("view").then(planRenderBuilder).catch(console.error);
      }
      function buildPlanPalette() {
        const box = document.getElementById("plan-palette-btns");
        if (!box || box.childElementCount) return; // built once
        PLAN_ADD_KINDS.forEach(([kind, label]) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "plan-palette-btn";
          b.textContent = "＋ " + label;
          b.setAttribute("aria-label", "Add " + label);
          b.onclick = () => planAddItem(kind, label);
          box.appendChild(b);
        });
      }
      async function planAddItem(kind, label) {
        try {
          const v = await invoke("add_item", { kind, title: label });
          if (v && v.items && v.items.length) {
            planSelectedId = v.items[v.items.length - 1].id;
            planFocusAfterRender = { kind: "row", id: planSelectedId }; // focus the new row
          }
          planRenderBuilder(v);
        } catch (e) {
          console.error(e);
        }
      }
      // Run a plan mutation, then refresh the builder from the returned view.
      async function planMutate(fn) {
        try {
          planRenderBuilder(await fn());
        } catch (e) {
          console.error(e);
          // The caller may have set a focus intent (e.g. a reorder) BEFORE the mutation; a rejected
          // mutation never re-renders, so clear it — otherwise a later background re-render would
          // consume the stale intent and steal focus onto an item the operator didn't just touch.
          planFocusAfterRender = null;
        }
      }
      // Reorder an item to a target index (persists via move_item; the moved row keeps focus). A plan
      // edit — never a live-control command.
      function planReorderTo(itemId, toIndex, last) {
        if (toIndex < 0 || toIndex > last) return;
        planFocusAfterRender = { kind: "row", id: itemId };
        planMutate(() => invoke("move_item", { itemId, to: toIndex }));
      }
      // === Pointer-based run-sheet drag reorder (frame 611:820) ================================
      // Pointer events (not HTML5 DnD) for WKWebView reliability + headless testability, mirroring
      // the Theme Designer LAYERS reorder. A cancelled/2px-threshold drag never reorders; the drop
      // line shows where the row will land; keyboard reorder is Alt+↑/↓ (below), so the ⠿ handle is
      // aria-hidden (a pointer affordance only).
      let planDrag = null;
      function planRunRows() {
        return Array.prototype.slice.call(document.querySelectorAll("#plan-b-list .plan-b-row"));
      }
      function planStartRowDrag(e, itemId, fromIndex, row) {
        if (e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        const line = document.createElement("div");
        line.className = "plan-b-dropline";
        line.setAttribute("aria-hidden", "true");
        planDrag = {
          itemId,
          fromIndex,
          row,
          list: document.getElementById("plan-b-list"),
          line,
          targetIndex: fromIndex,
          startY: e.clientY,
          active: false,
          pointerId: e.pointerId,
        };
        window.addEventListener("pointermove", planDragMove, true);
        window.addEventListener("pointerup", planDragEnd, true);
        window.addEventListener("pointercancel", planDragCancel, true);
      }
      function planDragMove(e) {
        if (!planDrag) return;
        if (!planDrag.active) {
          if (Math.abs(e.clientY - planDrag.startY) < 2) return; // threshold: a click is not a drag
          planDrag.active = true;
          planDrag.row.classList.add("dragging");
        }
        const rows = planRunRows();
        let target = rows.length;
        for (let k = 0; k < rows.length; k++) {
          const r = rows[k].getBoundingClientRect();
          if (e.clientY < r.top + r.height / 2) {
            target = k;
            break;
          }
        }
        planDrag.targetIndex = target;
        if (target >= rows.length) planDrag.list.appendChild(planDrag.line);
        else planDrag.list.insertBefore(planDrag.line, rows[target]);
      }
      function planDragTeardown() {
        window.removeEventListener("pointermove", planDragMove, true);
        window.removeEventListener("pointerup", planDragEnd, true);
        window.removeEventListener("pointercancel", planDragCancel, true);
        if (planDrag) {
          if (planDrag.line && planDrag.line.parentNode) planDrag.line.remove();
          if (planDrag.row) planDrag.row.classList.remove("dragging");
        }
        planDrag = null;
      }
      function planDragCancel() {
        planDragTeardown();
      }
      function planDragEnd() {
        if (!planDrag) return;
        const d = planDrag;
        planDragTeardown();
        if (!d.active) return; // never moved past the threshold → treat as a non-drag
        // Insertion index → move_item target: dropping BELOW the origin shifts by one after removal.
        let to = d.targetIndex > d.fromIndex ? d.targetIndex - 1 : d.targetIndex;
        if (to === d.fromIndex) return; // no-op
        planReorderTo(d.itemId, to, planRunRows().length - 1);
      }
      function planRenderBuilder(view) {
        const list = document.getElementById("plan-b-list");
        if (!list || !view) return; // not on the plan surface
        const count = document.getElementById("plan-b-count");
        if (count) count.textContent = view.items.length + " items";
        list.innerHTML = "";
        if (!view.items.length) {
          // Empty state (handoff §5, frame 611:124): a centered CTA, not a bare line. Template /
          // Duplicate / Import need backend commands outside this API, so they are shown as honest
          // "coming soon" affordances rather than omitted (match-the-full-shell).
          const empty = document.createElement("div");
          empty.className = "plan-empty";
          const eh = document.createElement("h3");
          eh.className = "plan-empty-h";
          eh.textContent = "Build your service plan";
          const es = document.createElement("p");
          es.className = "plan-empty-sub";
          es.textContent = "Add songs, scriptures, and presentations to the run sheet, then link content to each item.";
          const ec = document.createElement("button");
          ec.type = "button";
          ec.id = "plan-empty-add";
          ec.className = "pm-btn-primary";
          ec.textContent = "＋ Add first item";
          ec.onclick = () => {
            const first = document.querySelector("#plan-palette-btns .plan-palette-btn");
            if (first) first.focus();
          };
          const el8 = document.createElement("p");
          el8.className = "plan-empty-later";
          el8.textContent = "Start from a template · Duplicate a past plan · Import — coming soon";
          empty.appendChild(eh);
          empty.appendChild(es);
          empty.appendChild(ec);
          empty.appendChild(el8);
          list.appendChild(empty);
          planClearInspector();
          return;
        }
        const last = view.items.length - 1;
        view.items.forEach((it, i) => {
          const row = document.createElement("div");
          row.className =
            "plan-b-row" +
            (it.id === planSelectedId ? " sel" : "") +
            (it.is_live ? " is-live" : "") +
            (it.is_staged ? " is-staged" : "");
          // An interactive listbox option (not a passive listitem): the row is selectable, and its
          // selected state is exposed to AT via aria-selected (not border-colour alone). WCAG 1.4.1/4.1.2.
          row.setAttribute("role", "option");
          row.setAttribute("aria-selected", it.id === planSelectedId ? "true" : "false");
          row.dataset.itemId = it.id;
          row.tabIndex = 0;
          const main = document.createElement("span");
          main.className = "plan-b-main";
          const title = document.createElement("span");
          title.className = "plan-b-title";
          title.textContent = it.title;
          const kind = document.createElement("span");
          kind.className = "kind kind-" + it.kind;
          kind.textContent = planKindLabel(it.kind);
          main.appendChild(title);
          main.appendChild(kind);
          if (it.link) main.appendChild(planLinkChip(it.link));
          // Drag handle (pointer reorder). aria-hidden — keyboard users reorder via Alt+↑/↓ (below),
          // so the glyph handle is a pointer affordance only and stays out of the tab order / AT tree.
          const handle = document.createElement("span");
          handle.className = "plan-b-handle";
          handle.textContent = "⠿";
          handle.setAttribute("aria-hidden", "true");
          handle.title = "Drag to reorder";
          handle.onpointerdown = (e) => planStartRowDrag(e, it.id, i, row);
          handle.onclick = (e) => e.stopPropagation(); // a handle interaction must not select the row
          row.appendChild(handle);
          row.appendChild(main);
          const tools = document.createElement("span");
          tools.className = "plan-b-tools";
          const up = miniBtn(
            "↑",
            (e) => {
              e.stopPropagation();
              if (i > 0) {
                planFocusAfterRender = { kind: "up", id: it.id };
                planMutate(() => invoke("move_item", { itemId: it.id, to: i - 1 }));
              }
            },
            "Move “" + it.title + "” up"
          );
          up.className = "plan-b-up";
          up.disabled = i === 0;
          const down = miniBtn(
            "↓",
            (e) => {
              e.stopPropagation();
              if (i < last) {
                planFocusAfterRender = { kind: "down", id: it.id };
                planMutate(() => invoke("move_item", { itemId: it.id, to: i + 1 }));
              }
            },
            "Move “" + it.title + "” down"
          );
          down.className = "plan-b-down";
          down.disabled = i === last;
          tools.appendChild(up);
          tools.appendChild(down);
          row.appendChild(tools);
          if (it.is_live) row.appendChild(badge("live", "LIVE"));
          else if (it.is_staged) row.appendChild(badge("preview", "PREVIEW"));
          const select = () => {
            planSelectedId = it.id;
            planFocusAfterRender = { kind: "row", id: it.id };
            planRenderBuilder(view);
          };
          row.onclick = select;
          row.onkeydown = (e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              select();
              return;
            }
            // Alt+↑/↓ reorders the row (NFR-019 keyboard reorder); focus follows the moved row.
            if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
              e.preventDefault();
              planReorderTo(it.id, i + (e.key === "ArrowUp" ? -1 : 1), last);
            }
          };
          list.appendChild(row);
        });
        // Restore focus after the innerHTML rebuild so keyboard select/reorder doesn't dump focus
        // to <body> (WCAG 2.4.3). Only fires for an explicit user action that set the intent.
        if (planFocusAfterRender) {
          const f = planFocusAfterRender;
          planFocusAfterRender = null;
          const trow = list.querySelector('.plan-b-row[data-item-id="' + f.id + '"]');
          if (trow) {
            const btn = f.kind === "up" ? trow.querySelector(".plan-b-up") : f.kind === "down" ? trow.querySelector(".plan-b-down") : null;
            (btn && !btn.disabled ? btn : trow).focus();
          }
        }
        const sel = view.items.find((x) => x.id === planSelectedId);
        if (sel) planRenderInspector(sel);
        else planClearInspector();
      }
      function planClearInspector() {
        const box = document.getElementById("plan-b-insp");
        if (box)
          box.innerHTML =
            '<p class="coming-soon">Select an item to edit it and link its scripture or presentation.</p>';
      }
      // A richer linked-deck card for the inspector (frame 608:124): name + slide count, resolved
      // from the loaded deck list; a deleted deck renders the missing treatment.
      function planDeckCard(link) {
        const card = document.createElement("div");
        card.className = "plan-deck-card";
        const name = planDeckName(link.id);
        if (planDecks && !name) {
          card.classList.add("missing");
          const w = document.createElement("div");
          w.className = "plan-deck-card-name link-missing";
          w.textContent = "⚠ presentation missing";
          const m = document.createElement("div");
          m.className = "plan-deck-card-meta";
          m.textContent = "The linked deck was deleted from the library — relink it.";
          card.appendChild(w);
          card.appendChild(m);
          return card;
        }
        const deck = planDecks ? planDecks.find((d) => d.id === link.id) : null;
        const nm = document.createElement("div");
        nm.className = "plan-deck-card-name";
        nm.textContent = "▦ " + (name || "Presentation");
        const meta = document.createElement("div");
        meta.className = "plan-deck-card-meta";
        meta.textContent = deck ? deck.slides + (deck.slides === 1 ? " slide" : " slides") : "";
        card.appendChild(nm);
        card.appendChild(meta);
        return card;
      }
      function planRenderInspector(it) {
        const box = document.getElementById("plan-b-insp");
        if (!box) return;
        box.innerHTML = "";
        const kindRow = document.createElement("div");
        kindRow.className = "plan-insp-kind";
        const k = document.createElement("span");
        k.className = "kind kind-" + it.kind;
        k.textContent = planKindLabel(it.kind);
        kindRow.appendChild(k);
        box.appendChild(kindRow);
        const tl = document.createElement("label");
        tl.className = "pm-insp-lbl";
        tl.textContent = "Title";
        tl.htmlFor = "plan-insp-title";
        const ti = document.createElement("input");
        ti.className = "pm-insp-ctrl";
        ti.id = "plan-insp-title";
        ti.type = "text";
        ti.value = it.title;
        ti.setAttribute("aria-label", "Item title");
        ti.onkeydown = (e) => {
          if (e.key === "Enter") {
            const t = ti.value.trim();
            if (t && t !== it.title) {
              planFocusAfterRender = { kind: "row", id: it.id }; // keep focus on the item after the rebuild
              planMutate(() => invoke("rename_item", { itemId: it.id, title: t }));
            }
          }
        };
        box.appendChild(tl);
        box.appendChild(ti);
        if (it.kind === "scripture" || it.kind === "slide_group") {
          const ll = document.createElement("div");
          ll.className = "pm-insp-lbl";
          ll.textContent = it.kind === "scripture" ? "LINKED SCRIPTURE" : "LINKED PRESENTATION";
          box.appendChild(ll);
          const isDeckLink = it.link && it.kind === "slide_group" && it.link.kind === "deck";
          if (isDeckLink) {
            box.appendChild(planDeckCard(it.link)); // deck card: name + slide count / missing
          } else if (it.link) {
            const chip = planLinkChip(it.link); // scripture reference chip
            chip.classList.add("plan-insp-chip");
            box.appendChild(chip);
          } else {
            const warn = document.createElement("p");
            warn.className = "plan-insp-unlinked";
            warn.textContent =
              it.kind === "scripture"
                ? "No reference yet — this item won't display until it's linked."
                : "No presentation linked — this item will show missing on the audience output.";
            box.appendChild(warn);
          }
          const acts = document.createElement("div");
          acts.className = "plan-insp-actions";
          const linkBtn = document.createElement("button");
          linkBtn.type = "button";
          linkBtn.className = "pm-btn-primary";
          linkBtn.textContent = it.link
            ? "Change…"
            : it.kind === "scripture"
            ? "Link a scripture…"
            : "Link a presentation…";
          linkBtn.onclick = () => openLinkModal(it);
          acts.appendChild(linkBtn);
          // Open in editor: jump to the Presentation surface with this deck open (deck edits happen
          // there, not in the plan builder). Only for a resolvable deck link.
          if (isDeckLink && planDeckName(it.link.id)) {
            const openEd = document.createElement("button");
            openEd.type = "button";
            openEd.className = "pm-btn-ghost";
            openEd.textContent = "Open in editor";
            openEd.onclick = () => {
              showSurface("presentation");
              if (typeof pmLibOpen === "function") pmLibOpen(it.link.id);
            };
            acts.appendChild(openEd);
          }
          if (it.link) {
            const un = document.createElement("button");
            un.type = "button";
            un.className = "pm-btn-ghost";
            un.textContent = "Unlink";
            un.onclick = () => {
              planFocusAfterRender = { kind: "row", id: it.id }; // keep focus on the item after the rebuild
              planMutate(() => invoke("set_item_content", { itemId: it.id, link: null }));
            };
            acts.appendChild(un);
          }
          box.appendChild(acts);
        }
        const danger = document.createElement("div");
        danger.className = "plan-insp-actions plan-insp-danger";
        const del = document.createElement("button");
        del.type = "button";
        del.className = "pm-btn-danger";
        del.textContent = "Remove item";
        del.onclick = () =>
          pmConfirm({
            title: "Remove “" + it.title + "”?",
            body: "Only this run-sheet item is removed — any linked scripture or presentation is untouched.",
            confirmLabel: "Remove",
            onConfirm: () => {
              if (planSelectedId === it.id) planSelectedId = null;
              planMutate(() => invoke("remove_item", { itemId: it.id }));
            },
          });
        danger.appendChild(del);
        box.appendChild(danger);
        const note = document.createElement("p");
        note.className = "plan-insp-note";
        note.textContent = "🔒 Editing here never changes Live. Open in Live loads the plan into the console.";
        box.appendChild(note);
      }

      let pmLibDecks = [], pmLibOpenId = null, pmLibPersistent = true, pmLibQuery = "", pmLibSort = "name", pmLibMenuCleanup = null;
      const pmLibBody = () => document.querySelector("#surface-presentation .pm-body");
      // Presentation surface has three modes (Design 2.0 browse/present/edit): the Library list, the
      // slide GRID, and the authoring EDITOR (.pm-body). pmSetMode toggles which one is visible.
      let pmMode = "library";
      function pmSetMode(mode) {
        pmMode = mode;
        const lib = pmEl("pm-library"); if (lib) lib.hidden = mode !== "library";
        const grid = pmEl("pm-grid"); if (grid) grid.hidden = mode !== "grid";
        const b = pmLibBody(); if (b) b.style.display = mode === "editor" ? "" : "none";
      }
      function pmShowLibrary() {
        pmSetMode("library");
        pmLibLoad();
        const q = pmEl("pm-lib-q"); if (q) q.focus();
      }
      function pmHideLibrary() {
        pmLibCloseMenu();
        const wasOpen = pmEl("pm-library") && !pmEl("pm-library").hidden;
        pmSetMode("editor");
        // Restore focus to the deck-switcher after the view-swap (WCAG 2.4.3) — the card / menu-item /
        // button that triggered the swap is now hidden, so focus would otherwise fall to <body>.
        if (wasOpen) { const ds = pmEl("pm-deckswitch"); if (ds) ds.focus(); }
      }
      async function pmLibLoad() {
        const grid = pmEl("pm-lib-grid");
        grid.setAttribute("aria-busy", "true");
        pmEl("pm-lib-error").hidden = true;
        try {
          pmApplyLibrary(await invoke("deck_list"));
        } catch (e) {
          console.error("[SelahCue] deck_list failed", e);
          grid.innerHTML = ""; pmEl("pm-lib-empty").hidden = true; pmEl("pm-lib-error").hidden = false;
        } finally {
          grid.setAttribute("aria-busy", "false");
        }
      }
      function pmApplyLibrary(view) {
        pmLibDecks = (view && view.decks) || [];
        pmLibOpenId = view ? view.open : null;
        pmLibPersistent = view ? view.persistent : true;
        pmEl("pm-lib-nopersist").hidden = pmLibPersistent !== false;
        pmRenderLibGrid();
      }
      function pmRenderLibGrid() {
        const grid = pmEl("pm-lib-grid");
        const q = (pmLibQuery || "").trim().toLowerCase();
        let decks = pmLibDecks.filter((d) => !q || (d.name || "").toLowerCase().includes(q));
        decks = decks.slice().sort((a, b) => pmLibSort === "slides" ? (b.slides - a.slides) : (a.name || "").toLowerCase().localeCompare((b.name || "").toLowerCase()));
        const total = pmLibDecks.length;
        pmEl("pm-lib-count").textContent = total + " presentation" + (total === 1 ? "" : "s") + (q ? " · " + decks.length + " matching" : "");
        pmEl("pm-lib-empty").hidden = total !== 0;
        grid.innerHTML = "";
        if (total === 0) return; // the empty-state block carries its own CTA
        if (!q) grid.appendChild(pmLibNewTile());
        decks.forEach((d) => grid.appendChild(pmLibCard(d)));
        if (q && decks.length === 0) {
          const nr = document.createElement("div"); nr.className = "pm-lib-empty-sub"; nr.style.gridColumn = "1 / -1"; nr.style.padding = "26px 4px";
          nr.textContent = 'No presentations match "' + pmLibQuery + '"'; grid.appendChild(nr);
        }
      }
      function pmLibNewTile() {
        const t = document.createElement("button"); t.type = "button"; t.className = "pm-lib-new-tile"; t.setAttribute("aria-label", "New presentation");
        const p = document.createElement("span"); p.className = "pm-lib-new-plus"; p.setAttribute("aria-hidden", "true"); p.textContent = "＋"; t.appendChild(p);
        const l = document.createElement("span"); l.className = "pm-lib-new-label"; l.textContent = "New presentation"; t.appendChild(l);
        const s = document.createElement("span"); s.className = "pm-lib-new-sub"; s.textContent = "Start a blank deck"; t.appendChild(s);
        t.onclick = () => pmLibNew();
        return t;
      }
      function pmLibCard(deck) {
        const isOpen = deck.id === pmLibOpenId;
        const name = deck.name || "Untitled presentation";
        const meta = deck.slides + " slide" + (deck.slides === 1 ? "" : "s");
        const card = document.createElement("div"); card.className = "pm-lib-card" + (isOpen ? " open" : "");
        card.setAttribute("role", "listitem"); card.dataset.id = String(deck.id);
        const open = document.createElement("button"); open.type = "button"; open.className = "pm-lib-open";
        open.setAttribute("aria-label", "Open " + name + ", " + meta + (isOpen ? " (currently open)" : ""));
        open.onclick = () => pmLibOpen(deck.id);
        const th = document.createElement("div"); th.className = "pm-lib-thumb"; th.innerHTML = '<span aria-hidden="true">▦</span>';
        if (isOpen) { const of = document.createElement("span"); of.className = "pm-lib-openflag"; of.textContent = "OPEN"; th.appendChild(of); }
        const pill = document.createElement("span"); pill.className = "pm-lib-pill"; pill.textContent = meta; th.appendChild(pill);
        open.appendChild(th);
        const info = document.createElement("div"); info.className = "pm-lib-info";
        const col = document.createElement("div"); col.className = "pm-lib-info-col";
        const nm = document.createElement("span"); nm.className = "pm-lib-name"; nm.textContent = name; col.appendChild(nm);
        const mt = document.createElement("span"); mt.className = "pm-lib-meta"; mt.textContent = meta; col.appendChild(mt);
        info.appendChild(col); open.appendChild(info); card.appendChild(open);
        const dots = document.createElement("button"); dots.type = "button"; dots.className = "pm-lib-dots"; dots.textContent = "⋯";
        dots.setAttribute("aria-label", "More actions for " + name); dots.setAttribute("aria-haspopup", "true");
        dots.onclick = (ev) => { ev.stopPropagation(); pmLibOpenMenu(deck, dots); };
        card.appendChild(dots);
        return card;
      }
      function pmLibOpenMenu(deck, anchor) {
        pmLibCloseMenu();
        const menu = document.createElement("div"); menu.className = "pm-lib-menu"; menu.id = "pm-lib-menu"; menu.setAttribute("role", "menu");
        const item = (label, fn, danger) => { const b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "menuitem"); if (danger) b.className = "danger"; b.textContent = label; b.onclick = () => { pmLibCloseMenu(); fn(); }; menu.appendChild(b); return b; };
        const first = item("Open", () => pmLibOpen(deck.id));
        item("Rename…", () => pmLibRename(deck.id, deck.name));
        item("Duplicate", () => pmLibDuplicate(deck.id));
        const div = document.createElement("div"); div.className = "pm-lib-menu-div"; menu.appendChild(div);
        item("Delete", () => pmLibDelete(deck.id, deck.name), true);
        document.body.appendChild(menu);
        const r = anchor.getBoundingClientRect();
        menu.style.top = Math.max(8, Math.min(r.bottom + 4, window.innerHeight - menu.offsetHeight - 8)) + "px";
        menu.style.left = Math.max(8, Math.min(r.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 8)) + "px";
        first.focus();
        const onDoc = (e) => { if (!menu.contains(e.target)) pmLibCloseMenu(); };
        const onKey = (e) => {
          if (e.key === "Escape") { e.preventDefault(); pmLibCloseMenu(); anchor.focus(); }
          else if (e.key === "Tab") { e.preventDefault(); pmLibCloseMenu(); anchor.focus(); } // Tab closes the menu and returns to the ⋯ trigger (no orphaned popover)
          else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const items = Array.from(menu.querySelectorAll("button")); let i = items.indexOf(document.activeElement); i = e.key === "ArrowDown" ? (i + 1) % items.length : (i - 1 + items.length) % items.length; items[i].focus(); }
        };
        menu.addEventListener("keydown", onKey);
        setTimeout(() => document.addEventListener("mousedown", onDoc), 0);
        pmLibMenuCleanup = () => { document.removeEventListener("mousedown", onDoc); if (menu.parentNode) menu.remove(); };
      }
      function pmLibCloseMenu() { if (pmLibMenuCleanup) { pmLibMenuCleanup(); pmLibMenuCleanup = null; } }
      // After a mutating action re-renders the grid, move focus to a stable element (WCAG 2.4.3):
      // the card / menu-item / dialog trigger that ran the action is now gone, so focus would
      // otherwise fall to <body>. Prefer the affected deck's card, else the first card, else search.
      function pmLibFocusDeck(id) {
        const grid = pmEl("pm-lib-grid"); if (!grid) return;
        let t = id != null ? grid.querySelector('.pm-lib-card[data-id="' + id + '"] .pm-lib-open') : null;
        if (!t) t = grid.querySelector(".pm-lib-card .pm-lib-open");
        if (!t) t = pmEl("pm-lib-q") || pmEl("pm-lib-new");
        if (t) t.focus();
      }
      function pmLibNew() {
        pmPrompt({
          title: "New presentation", label: "Name", value: "Untitled presentation", confirmLabel: "Create presentation",
          onConfirm: async (name) => {
            try { const dv = await invoke("deck_new", { name: name }); pmDv = dv; renderPresentation(dv); pmHideLibrary(); pmToast("Presentation created"); }
            catch (e) { console.error(e); pmShowError("create the presentation"); }
          },
        });
      }
      async function pmLibOpen(id) {
        try { const dv = await invoke("deck_open", { id: id }); pmDv = dv; pmSetMode("grid"); pmRenderGrid(dv); }
        catch (e) { console.error(e); pmShowError("open the presentation"); }
      }

      // --- Slide GRID (Design 2.0 browse/present mode) ---------------------------------------------
      const PM_THUMB_MAX = 60;             // bounded thumbnail cache (no unbounded growth)
      const pmThumbCache = new Map();      // slideId -> dataURL
      function pmThumbPut(id, url) {
        pmThumbCache.set(id, url);
        while (pmThumbCache.size > PM_THUMB_MAX) pmThumbCache.delete(pmThumbCache.keys().next().value);
      }
      function pmThumbFail(cv) {
        const t = cv && cv.parentElement; if (!t || t.querySelector(".pm-tile-failmsg")) return;
        t.classList.add("pm-tile-fail");
        const s = document.createElement("span"); s.className = "pm-tile-failmsg"; s.textContent = "⚠ Can't preview"; t.appendChild(s);
      }
      async function pmThumb(id, cv) {
        if (!cv) return;
        if (pmThumbCache.has(id)) {
          const im = new Image();
          im.onload = () => { try { cv.getContext("2d").drawImage(im, 0, 0, cv.width, cv.height); } catch (e) {} };
          im.src = pmThumbCache.get(id);
          return;
        }
        try {
          const r = await invoke("render_deck_slide", { id: id, maxW: 320, maxH: 180 });
          if (r && r.available && r.frame && blitFrame(cv, r.frame)) pmThumbPut(id, cv.toDataURL());
          else pmThumbFail(cv); // missing media / no frame → honest "can't preview" tile (not a silent blank)
        } catch (e) { pmThumbFail(cv); }
      }
      let pmGridCursor = null;             // selected slide id (safe — never touches live)
      let pmGridLiveId = null;             // HOST-truth live authored slide id (drives ring/transport)
      function pmGridAnnounce(msg) { const r = pmEl("pm-grid-live-region"); if (r) r.textContent = msg; }
      function pmGridTiles() { const g = pmEl("pm-grid-tiles"); return g ? Array.prototype.slice.call(g.querySelectorAll(".pm-tile")) : []; }
      function pmGridSelect(id, focus) {
        if (id == null) return;
        pmGridCursor = id;
        pmGridTiles().forEach((t) => {
          const on = Number(t.dataset.id) === id;
          t.classList.toggle("sel", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
          t.tabIndex = on ? 0 : -1;
          if (on && focus) t.focus();
        });
      }
      async function pmGridGoLive(id) {
        if (id == null) return;
        // deck_go_live presents the HOST-selected slide, so always select the target first (the
        // client cursor is not the host's selection). The ◀▶ transport / live-mode arrows use the
        // atomic deck_go_live_delta instead.
        if (!(await pAct(() => invoke("deck_select_slide", { id: id }), "select the slide"))) { await pmGridSyncLive(); return; }
        pmGridCursor = id;
        await pAct(() => invoke("deck_go_live"), "present the slide"); // failure → pAct shows the error banner; the ring stays host-truth
        await pmGridSyncLive();
      }
      // Advance the LIVE slide by delta (−1 prev / +1 next) atomically — ◀▶ transport + live arrows.
      async function pmGridDelta(delta) {
        await pAct(() => invoke("deck_go_live_delta", { delta: delta }), "advance the live slide");
        await pmGridSyncLive();
      }
      // Ring the LIVE slide from HOST truth (view().live_authored_id — the deck-local annotation can
      // go stale when the console drives plan content) and drive the transport bar.
      async function pmGridSyncLive() {
        let v = null, liveId = null;
        try { v = await invoke("view"); liveId = (v && v.live_authored_id != null) ? v.live_authored_id : null; }
        catch (e) {
          // Host link dropped — keep the last-known ring; disable the transport until reconnect.
          const p = pmEl("pm-prev"), n = pmEl("pm-next");
          if (p) p.setAttribute("aria-disabled", "true");
          if (n) n.setAttribute("aria-disabled", "true");
          return;
        }
        pmGridLiveId = liveId;
        const tiles = pmGridTiles();
        const tp = pmEl("pm-transport"); if (tp) tp.hidden = liveId == null;
        const badge = pmEl("pm-grid-badge");
        if (liveId == null) {
          tiles.forEach((t) => { t.classList.remove("live", "preview"); const l = t.querySelector(".pm-tile-live"); if (l) l.remove(); });
          if (badge) badge.hidden = true;
          return;
        }
        // Honest present state: a true red LIVE ring ONLY when a real audience output is connected;
        // with no output show a distinct PREVIEW ring + badge, never implying the audience sees a
        // slide no display is showing (the local backend returns Ok silently — never-surprise, §8/§9).
        let connected = true; try { connected = await invoke("output_connected"); } catch (e) {}
        const blackedOut = !!(v && v.blackout);
        const ids = tiles.map((t) => Number(t.dataset.id)); const idx = ids.indexOf(liveId);
        tiles.forEach((t) => {
          const on = Number(t.dataset.id) === liveId;
          t.classList.toggle("live", on && connected);
          t.classList.toggle("preview", on && !connected);
          let lbl = t.querySelector(".pm-tile-live");
          if (on) {
            if (!lbl) { lbl = document.createElement("span"); lbl.className = "pm-tile-live"; t.appendChild(lbl); }
            lbl.textContent = connected ? "● LIVE" : "PREVIEW";
            lbl.classList.toggle("prev", !connected);
          } else if (lbl) { lbl.remove(); }
        });
        // Focus + cursor follow live (spec §6/§9) so arrows/Enter operate from the live slide.
        pmGridCursor = liveId;
        tiles.forEach((t) => { const on = Number(t.dataset.id) === liveId; t.classList.toggle("sel", on); t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1; });
        if (pmMode === "grid" && tiles[idx]) { try { tiles[idx].focus(); } catch (e) {} }
        const lv = pmEl("pm-tp-live");
        const word = blackedOut ? "BLACKED OUT · slide " : (connected ? "● LIVE — slide " : "PREVIEW — slide ");
        if (lv) { lv.textContent = word + (idx + 1) + " / " + ids.length; lv.classList.toggle("blk", blackedOut); lv.classList.toggle("prev", !connected && !blackedOut); }
        const prev = pmEl("pm-prev"); if (prev) prev.setAttribute("aria-disabled", idx <= 0 ? "true" : "false");
        const next = pmEl("pm-next"); if (next) next.setAttribute("aria-disabled", idx >= ids.length - 1 ? "true" : "false");
        if (badge) { badge.hidden = connected; if (!connected) badge.textContent = "Preview only — no audience output"; }
        pmGridAnnounce((blackedOut ? "Blacked out; pending slide " : (connected ? "Now live: slide " : "Preview only — slide ")) + (idx + 1) + " of " + ids.length);
      }
      function pmRenderGrid(dv) {
        pmDv = dv;
        const nm = pmEl("pm-grid-name"); if (nm) nm.textContent = dv.name || "Presentation";
        const ct = pmEl("pm-grid-count"); if (ct) ct.textContent = "· " + (dv.count || 0) + " slides";
        const tiles = pmEl("pm-grid-tiles"); if (!tiles) return;
        tiles.innerHTML = "";
        const slides = dv.slides || [];
        const empty = slides.length === 0;
        const emptyBox = pmEl("pm-grid-empty"); if (emptyBox) emptyBox.hidden = !empty;
        tiles.hidden = empty;
        const io = ("IntersectionObserver" in window)
          ? new IntersectionObserver((es) => { es.forEach((e) => { if (e.isIntersecting) { io.unobserve(e.target); pmThumb(Number(e.target.dataset.id), e.target.querySelector("canvas")); } }); })
          : null;
        slides.forEach((s, i) => {
          const tile = document.createElement("div"); tile.className = "pm-tile"; tile.dataset.id = String(s.id);
          tile.setAttribute("role", "option"); tile.setAttribute("aria-selected", "false"); tile.tabIndex = i === 0 ? 0 : -1;
          tile.setAttribute("aria-label", "Slide " + (i + 1) + (s.lines && s.lines[0] ? ": " + s.lines[0] : ""));
          const cv = document.createElement("canvas"); cv.className = "pm-tile-cv"; cv.width = 320; cv.height = 180; tile.appendChild(cv);
          const n = document.createElement("span"); n.className = "pm-tile-n"; n.textContent = String(i + 1); tile.appendChild(n);
          const id = s.id;
          tile.onclick = () => pmGridSelect(id, false);
          tile.ondblclick = () => pmGridGoLive(id);
          tiles.appendChild(tile);
          // Eager-render the initial batch (first fold); lazy-load the rest via the observer. This
          // keeps visible thumbnails immediate (and headless-testable) while staying bounded.
          if (io && i >= 12) io.observe(tile); else pmThumb(id, cv);
        });
        pmGridSelect(dv.selected != null ? dv.selected : (slides[0] && slides[0].id), false);
        pmGridSyncLive();
        // Static grid controls (idempotent wiring).
        const back = pmEl("pm-grid-back"); if (back) back.onclick = () => { pmSetMode("library"); pmLibLoad(); };
        const edit = pmEl("pm-grid-edit"); if (edit) edit.onclick = () => { pmThumbCache.clear(); pmSetMode("editor"); renderPresentation(pmDv); };
        const eEdit = pmEl("pm-grid-empty-edit"); if (eEdit) eEdit.onclick = () => { pmThumbCache.clear(); pmSetMode("editor"); renderPresentation(pmDv); };
        const prev = pmEl("pm-prev"); if (prev) prev.onclick = () => { if (prev.getAttribute("aria-disabled") !== "true") pmGridDelta(-1); };
        const next = pmEl("pm-next"); if (next) next.onclick = () => { if (next.getAttribute("aria-disabled") !== "true") pmGridDelta(1); };
        tiles.onkeydown = (e) => {
          const ids = pmGridTiles().map((t) => Number(t.dataset.id));
          if (!ids.length) return;
          const i = Math.max(0, ids.indexOf(pmGridCursor == null ? ids[0] : pmGridCursor));
          if (e.key === "Enter") { e.preventDefault(); pmGridGoLive(ids[i]); return; }
          const fwd = (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === " ");
          const back2 = (e.key === "ArrowLeft" || e.key === "ArrowUp");
          if (!fwd && !back2) return;
          e.preventDefault();
          // Owner decision: once a slide is LIVE, arrows advance live directly; before that they
          // move the (safe) selection cursor.
          if (pmGridLiveId != null) pmGridDelta(fwd ? 1 : -1);
          else pmGridSelect(ids[fwd ? Math.min(ids.length - 1, i + 1) : Math.max(0, i - 1)], true);
        };
      }

      function pmLibRename(id, current) {
        pmPrompt({
          title: "Rename presentation", label: "Name", value: current || "", confirmLabel: "Rename",
          onConfirm: async (name) => {
            try {
              pmApplyLibrary(await invoke("deck_rename", { id: id, name: name }));
              if (id === pmLibOpenId) { const m = pmLibDecks.find((d) => d.id === id); if (m && pmDv) { pmDv.name = m.name; const el = pmEl("pm-plan-name"); if (el) el.textContent = m.name; } }
              pmLibFocusDeck(id); // restore focus to the renamed card (the dialog trigger is gone)
            } catch (e) { console.error(e); pmShowError("rename the presentation"); }
          },
        });
      }
      async function pmLibDuplicate(id) {
        try { pmApplyLibrary(await invoke("deck_duplicate", { id: id })); pmLibFocusDeck(id); }
        catch (e) { console.error(e); pmShowError("duplicate the presentation"); }
      }
      function pmLibDelete(id, name) {
        const inUse = id === pmLibOpenId;
        pmConfirm({
          title: "Delete “" + (name || "Untitled presentation") + "”?",
          body: "This removes the presentation and its slides from your library. This can’t be undone.",
          warning: inUse ? "It’s the presentation you have open — deleting it switches the editor to another." : null,
          confirmLabel: "Delete",
          onConfirm: async () => {
            try {
              pmApplyLibrary(await invoke("deck_delete", { id: id }));
              if (inUse) { const dv = await invoke("deck_view"); pmDv = dv; renderPresentation(dv); } // editor switched by the host
              pmToast("Presentation deleted");
              pmLibFocusDeck(null); // the deleted card is gone → focus the first remaining card / search
            } catch (e) { console.error(e); pmShowError("delete the presentation"); }
          },
        });
      }
      function pmAddSlide() { pAct(() => invoke("deck_add_slide")); }
      // "▶ Present": mark the slide live in the editor AND route it to the native audience output
      // (deck_go_live now sends the composed slide over the LAN link). A toast confirms it reached
      // the output; a failure (e.g. no output window) surfaces the error banner via pAct.
      async function pmPresent() {
        if (await pAct(() => invoke("deck_go_live"), "present the slide")) {
          pmToast("Now presenting on the audience output");
        }
      }
      function pmUndo() { pAct(() => invoke("deck_undo")); }
      function pmRedo() { pAct(() => invoke("deck_redo")); }

      // The selected slide's elements (from the last DeckView), front data for hit-testing.
      function pmElements() { return (pmDv && pmDv.slide && pmDv.slide.elements) || []; }
      function pmSelectedElement() {
        const idx = pmDv && pmDv.slide ? pmDv.slide.selected_element : null;
        return idx == null ? null : pmElements()[idx];
      }
      // Element indices ordered front (highest z) → back, stable within equal z — the order the
      // keyboard Tab-cycle walks (matches the compositor's paint order).
      function pmZOrder() {
        const els = pmElements();
        // Front (highest z) → back. Tie-break on index DESCENDING to match compose_slide's paint
        // order (stable sort by z asc then list index → the LATER equal-z element paints in FRONT).
        return els
          .map((_, i) => i)
          .sort((a, b) => (els[b].z || 0) - (els[a].z || 0) || b - a);
      }
      // Announce an editor action to assistive tech via the polite live region.
      function pmAnnounce(msg) {
        const r = pmEl("pm-live-region");
        if (r) r.textContent = msg;
      }

      // --- render -------------------------------------------------------------------------
      function renderPresentation(dv) {
        if (!dv) return;
        pmEl("pm-plan-name").textContent = dv.name || "Presentation";
        pmEl("pm-plan-count").textContent = "· " + (dv.count || 0) + " slide" + (dv.count === 1 ? "" : "s");
        pmRenderSlides(dv);
        // slide position + editor controls
        const sel = dv.slide;
        const n = sel ? (dv.slides.findIndex((s) => s.id === sel.id) + 1) : 0;
        pmEl("pm-slide-pos").textContent = "Slide " + (n || "—") + " / " + (dv.count || "—") + " · 1920×1080";
        const notes = pmEl("pm-notes");
        // Do not clobber the notes field while the operator is typing in it.
        if (document.activeElement !== notes) notes.value = sel ? sel.notes || "" : "";
        notes.disabled = !sel;
        const trans = pmEl("pm-transition");
        trans.value = sel ? sel.transition || "cut" : "cut";
        trans.disabled = !sel;
        const auto = pmEl("pm-autoadv");
        auto.value = sel && sel.auto_advance_secs ? String(sel.auto_advance_secs) : "0";
        auto.disabled = !sel;
        // undo/redo enablement
        pmEl("pm-undo").disabled = !dv.can_undo;
        pmEl("pm-redo").disabled = !dv.can_redo;
        pmRenderMedia(dv);
        pmRenderCanvas();
        pmSyncRightPanel(dv);
      }

      // The right column is contextual: Media Library by default, the per-element Inspector when an
      // element is selected. Selecting an element AUTO-OPENS the Inspector; deselecting returns to
      // Media. The auto-switch fires only on a CHANGE of selection (so a manual tab switch persists),
      // and never moves focus (a canvas drag-select must not yank focus off the canvas).
      function pmSyncRightPanel(dv) {
        const slide = dv.slide;
        const selIdx = slide ? slide.selected_element : null;
        const hasSel = selIdx != null && slide.elements && slide.elements[selIdx];
        const inspTab = pmEl("pm-tab-inspector");
        if (hasSel) { inspTab.removeAttribute("aria-disabled"); inspTab.title = ""; }
        else { inspTab.setAttribute("aria-disabled", "true"); inspTab.title = "Select an element"; }
        const key = hasSel ? slide.id + ":" + selIdx : null;
        if (key !== pmLastSelKey) {
          // A selection/slide change ends any armed image-Replace flow (so a later media pick can
          // never replace an element the operator is no longer on — review 86ajvjtax #1/#3).
          if (pmReplaceTarget != null) pmEndReplace();
          pmLastSelKey = key;
          pmSetRight(hasSel ? "inspector" : "media");
          if (hasSel) pmAnnounce("Inspector — " + (slide.elements[selIdx].kind || "") + " element selected");
        } else if (hasSel && pmRightMode === "inspector") {
          pmRenderInspector(dv); // same selection, still inspecting → refresh values after an edit
        } else if (!hasSel && pmRightMode === "inspector") {
          pmSetRight("media");
        }
      }

      function pmSetRight(mode) {
        pmRightMode = mode;
        const showInsp = mode === "inspector";
        pmEl("pm-media-body").hidden = showInsp;
        pmEl("pm-inspector-body").hidden = !showInsp;
        const mTab = pmEl("pm-tab-media"), iTab = pmEl("pm-tab-inspector");
        mTab.setAttribute("aria-selected", showInsp ? "false" : "true");
        iTab.setAttribute("aria-selected", showInsp ? "true" : "false");
        mTab.tabIndex = showInsp ? -1 : 0;
        iTab.tabIndex = showInsp ? 0 : -1;
        pmEl("pm-panel").setAttribute("aria-labelledby", showInsp ? "pm-tab-inspector" : "pm-tab-media");
        if (showInsp && pmDv) pmRenderInspector(pmDv);
      }

      // --- inspector control helpers ---
      const pmHex = (c) => "#" + [c && c.r, c && c.g, c && c.b].map((v) => (v || 0).toString(16).padStart(2, "0")).join("");
      const pmFromHex = (h) => ({ r: parseInt(h.slice(1, 3), 16) || 0, g: parseInt(h.slice(3, 5), 16) || 0, b: parseInt(h.slice(5, 7), 16) || 0, a: 255 });
      function pmUpdate(idx, patch) { pAct(() => invoke("deck_update_element", { index: idx, patch: patch })); }
      function pmInspRow(labelText, ctrl) {
        const r = document.createElement("div"); r.className = "pm-insp-row";
        // A REAL <label for> (not a bare span) so each control has an accessible name (WCAG 4.1.2 /
        // 3.3.2). A composite control (e.g. the Align button group) is a <span> the `for` can't bind,
        // but its inner buttons carry their own aria-labels; the aria-label fallback below covers the
        // form controls (input/select) without overriding one already set (Font/Fit).
        const l = document.createElement("label"); l.className = "pm-insp-lbl"; l.textContent = labelText;
        if (!ctrl.id) ctrl.id = "pm-ictl-" + (++pmRowId);
        l.htmlFor = ctrl.id;
        if (!ctrl.getAttribute("aria-label")) ctrl.setAttribute("aria-label", labelText);
        r.appendChild(l); r.appendChild(ctrl); return r;
      }
      function pmNum(value, onCommit) {
        const i = document.createElement("input"); i.type = "number"; i.className = "pm-insp-ctrl num"; i.value = value;
        i.addEventListener("change", () => { const v = parseInt(i.value, 10); if (!Number.isNaN(v)) onCommit(v); });
        return i;
      }
      function pmSelect(opts, value, onCommit) {
        const s = document.createElement("select"); s.className = "pm-insp-ctrl";
        opts.forEach(([val, lbl]) => { const o = document.createElement("option"); o.value = val; o.textContent = lbl; if (String(val) === String(value)) o.selected = true; s.appendChild(o); });
        s.addEventListener("change", () => onCommit(s.value)); return s;
      }
      // The Text inspector's Font-family picker, from `system_fonts` (C-006). "System default"
      // (value "") clears `font` to null (the bundled Noto Sans). The element's current family is
      // always shown selected — even a font not installed on THIS machine (labelled so).
      function pmFontSelect(current, onCommit) {
        const s = document.createElement("select"); s.className = "pm-insp-ctrl"; s.dataset.ik = "font";
        s.setAttribute("aria-label", "Font family");
        const opts = [["", "System default"]];
        const fams = pmFonts || [];
        fams.forEach((f) => opts.push([f, f]));
        // Preserve a chosen family that is not installed here, so it renders selected not blank.
        if (current && !fams.includes(current)) opts.push([current, current + " (not installed here)"]);
        const cur = current || "";
        opts.forEach(([val, lbl]) => { const o = document.createElement("option"); o.value = val; o.textContent = lbl; if (val === cur) o.selected = true; s.appendChild(o); });
        s.addEventListener("change", () => onCommit(s.value)); return s;
      }
      function pmColor(rgba, onCommit) {
        const i = document.createElement("input"); i.type = "color"; i.className = "pm-insp-ctrl"; i.value = pmHex(rgba || {});
        i.addEventListener("change", () => onCommit(pmFromHex(i.value))); return i;
      }
      function pmArrangeZ(dv, idx, dir) {
        const els = (dv.slide && dv.slide.elements) || [];
        const zs = els.map((e) => e.z || 0);
        const cur = els[idx] ? els[idx].z || 0 : 0;
        let z = dir === "front" ? Math.max(...zs) + 1 : dir === "back" ? Math.min(...zs) - 1 : dir === "forward" ? cur + 1 : cur - 1;
        z = Math.max(-128, Math.min(127, z));
        pAct(() => invoke("deck_set_element_z", { index: idx, z: z }));
      }

      // --- LAYERS panel (Design 2.0, mirrors the Theme Designer): the slide's elements listed
      // front→back, each selectable + visibility-toggle + drag-to-reorder. Reuses the shared
      // `td-layer*` row styling. Reorder commits via deck_reorder_elements (one host round-trip /
      // one undo); the moved element stays selected (only z changes, never its array index). ---
      let pmLayerDrag = null;
      function pmLayerRow(dv, idx, selIdx) {
        const el = ((dv.slide && dv.slide.elements) || [])[idx];
        const row = document.createElement("div");
        row.className = "td-layer" + (idx === selIdx ? " sel" : "");
        row.setAttribute("role", "listitem");
        row.tabIndex = 0;
        row.dataset.idx = String(idx);
        const visible = el.visible !== false;
        const glyph = el.kind === "image" ? "🖼" : el.kind === "text" ? "T" : "●";
        const name = el.kind === "text"
          ? ((el.text || "").split("\n")[0].slice(0, 24).trim() || "Text")
          : el.kind === "image" ? (el.name || "Image") : "Shape";
        const meta = el.kind.charAt(0).toUpperCase() + el.kind.slice(1) + " · z" + (el.z || 0);
        if (!visible) row.classList.add("layer-hidden");
        if (idx === selIdx) row.setAttribute("aria-current", "true");
        row.setAttribute("aria-label", name + " — " + meta + (visible ? "" : " (hidden)") + (idx === selIdx ? " (selected)" : ""));
        const handle = document.createElement("span"); handle.className = "td-layer-handle"; handle.textContent = "⋮⋮"; handle.setAttribute("aria-hidden", "true");
        handle.addEventListener("pointerdown", (ev) => pmLayerDragStart(ev, idx));
        const ico = document.createElement("span"); ico.className = "td-layer-ico"; ico.textContent = glyph; ico.setAttribute("aria-hidden", "true");
        const bd = document.createElement("div"); bd.className = "td-layer-body";
        const nm = document.createElement("span"); nm.className = "td-layer-name"; nm.textContent = name;
        const mt = document.createElement("span"); mt.className = "td-layer-meta"; mt.textContent = meta;
        bd.appendChild(nm); bd.appendChild(mt);
        const eye = document.createElement("button"); eye.type = "button"; eye.className = "td-layer-eye"; eye.textContent = visible ? "👁" : "🚫";
        eye.setAttribute("aria-pressed", visible ? "true" : "false"); eye.setAttribute("aria-label", (visible ? "Hide " : "Show ") + name); eye.title = visible ? "Hide layer" : "Show layer";
        eye.onclick = (ev) => { ev.stopPropagation(); pAct(() => invoke("deck_toggle_element_visible", { index: idx })); };
        row.onclick = () => { if (idx !== selIdx) pAct(() => invoke("deck_select_element", { index: idx })); };
        row.onkeydown = (ev) => {
          if (ev.target !== row) return; // let the eye button's own Enter/Space fire
          if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); if (idx !== selIdx) pAct(() => invoke("deck_select_element", { index: idx })); }
          else if (ev.altKey && (ev.key === "ArrowUp" || ev.key === "ArrowDown")) { ev.preventDefault(); pmArrangeZ(dv, idx, ev.key === "ArrowUp" ? "forward" : "backward"); }
        };
        row.appendChild(handle); row.appendChild(ico); row.appendChild(bd); row.appendChild(eye);
        return row;
      }
      function pmRenderLayers(dv, selIdx) {
        const box = document.createElement("div");
        box.className = "td-layers pm-layers"; box.id = "pm-layers";
        box.setAttribute("role", "list"); box.setAttribute("aria-label", "Layers — front to back; drag to reorder");
        pmZOrder().forEach((idx) => box.appendChild(pmLayerRow(dv, idx, selIdx)));
        return box;
      }
      function pmLayerDragStart(ev, idx) {
        if (ev.button !== undefined && ev.button !== 0) return;
        const box = pmEl("pm-layers");
        const row = ev.target && ev.target.closest(".td-layer");
        if (!box || !row) return;
        ev.preventDefault();
        const rect = row.getBoundingClientRect();
        const ph = document.createElement("div"); ph.className = "td-layer-placeholder"; ph.style.height = rect.height + "px";
        box.insertBefore(ph, row);
        const grabDy = ev.clientY - rect.top;
        row.classList.add("dragging");
        row.style.position = "fixed";
        row.style.left = rect.left + "px";
        row.style.width = rect.width + "px";
        row.style.top = rect.top + "px";
        pmLayerDrag = { idx, box, row, ph, grabDy };
        box.classList.add("td-layers-dragging");
        window.addEventListener("pointermove", pmLayerDragMove);
        window.addEventListener("pointerup", pmLayerDragCommit);
        window.addEventListener("pointercancel", pmLayerDragCancel);
      }
      function pmLayerDragMove(ev) {
        const D = pmLayerDrag;
        if (!D) return;
        D.row.style.top = ev.clientY - D.grabDy + "px";
        const br = D.box.getBoundingClientRect();
        if (ev.clientY < br.top + 24) D.box.scrollTop -= 8;
        else if (ev.clientY > br.bottom - 24) D.box.scrollTop += 8;
        const kids = Array.from(D.box.children).filter((c) => c !== D.row && c !== D.ph);
        let ref = null;
        for (const c of kids) {
          const r = c.getBoundingClientRect();
          if (ev.clientY < r.top + r.height / 2) { ref = c; break; }
        }
        if (ref) D.box.insertBefore(D.ph, ref);
        else D.box.appendChild(D.ph);
      }
      function pmLayerTeardown() {
        const D = pmLayerDrag;
        pmLayerDrag = null;
        window.removeEventListener("pointermove", pmLayerDragMove);
        window.removeEventListener("pointerup", pmLayerDragCommit);
        window.removeEventListener("pointercancel", pmLayerDragCancel);
        if (D) D.box.classList.remove("td-layers-dragging");
        return D;
      }
      function pmLayerDragCancel() {
        const D = pmLayerTeardown();
        if (!D) return;
        if (D.ph.parentNode) D.ph.parentNode.removeChild(D.ph);
        D.row.classList.remove("dragging"); D.row.removeAttribute("style");
        if (pmDv) pmRenderInspector(pmDv); // revert to the real order, no z change
      }
      function pmLayerDragCommit() {
        const D = pmLayerTeardown();
        if (!D) return;
        // Read the new FRONT→BACK order from the DOM (placeholder marks the dragged element's slot).
        const order = [];
        Array.from(D.box.children).forEach((c) => {
          if (c === D.row) return; // the lifted original — its real slot is the placeholder
          if (c === D.ph) order.push(D.idx);
          else if (c.dataset.idx !== undefined) order.push(Number(c.dataset.idx));
        });
        if (D.ph.parentNode) D.ph.parentNode.removeChild(D.ph);
        D.row.classList.remove("dragging"); D.row.removeAttribute("style");
        pAct(() => invoke("deck_reorder_elements", { order: order }));
      }
      function pmStartReplace(idx) {
        pmReplaceTarget = idx;
        pmMediaFilter = "image";
        document.querySelectorAll("#surface-presentation .pm-mtab").forEach((x) => x.setAttribute("aria-pressed", x.dataset.filter === "image" ? "true" : "false"));
        pmEl("pm-replace-hint").hidden = false;
        pmSetRight("media");
        if (pmDv) pmRenderMedia(pmDv);
      }
      // End the armed image-Replace flow: clear the target, hide the hint, and reset the media
      // filter back to All (so the library isn't left silently stuck on Images).
      function pmEndReplace() {
        pmReplaceTarget = null;
        pmEl("pm-replace-hint").hidden = true;
        pmMediaFilter = "all";
        document.querySelectorAll("#surface-presentation .pm-mtab").forEach((x) => x.setAttribute("aria-pressed", x.dataset.filter === "all" ? "true" : "false"));
      }

      function pmRenderInspector(dv) {
        const body = pmEl("pm-inspector-body");
        const slide = dv.slide;
        const idx = slide ? slide.selected_element : null;
        const el = idx != null && slide.elements ? slide.elements[idx] : null;
        // Don't clobber a focused INPUT/TEXTAREA/SELECT mid-edit (a re-render on the same
        // selection). For a focused BUTTON, rebuild but RESTORE focus to the equivalent control
        // afterward (its `data-ik`), so keyboard use of Align/Arrange/eye keeps its place (WCAG 2.4.3).
        const ae0 = document.activeElement;
        if (body.contains(ae0) && ["INPUT", "TEXTAREA", "SELECT"].indexOf(ae0.tagName) >= 0) return;
        const focusedIk = body.contains(ae0) && ae0.dataset ? ae0.dataset.ik : null;
        body.innerHTML = "";
        if (!el) { const p = document.createElement("p"); p.className = "pm-insp-note"; p.textContent = "Select an element to edit it."; body.appendChild(p); return; }
        // Serde omits default-valued fields (skip_serializing_if) → default them here so their
        // controls render selected, not blank (review 86ajvjtax #5).
        const D = { weight: el.weight != null ? el.weight : 400, variant: el.variant || "rect", corner: el.corner_permille || 0, border: el.border_permille || 0, alignH: el.align_h || "left", alignV: el.align_v || "middle", fit: el.fit || "shrink_to_fit", size: el.size_permille || 90, line: el.line_height_permille || 1100, opacity: el.opacity != null ? el.opacity : 255 };
        const kindTitle = { text: "Text element", shape: "Shape element", image: "Image element" }[el.kind] || "Element";
        // header: title · n of m · visibility · delete
        const hdr = document.createElement("div"); hdr.className = "pm-insp-header";
        const ttl = document.createElement("span"); ttl.className = "pm-insp-title"; ttl.textContent = kindTitle; hdr.appendChild(ttl);
        const hr = document.createElement("span"); hr.className = "pm-insp-hdr-r";
        const cnt = document.createElement("span"); cnt.className = "pm-insp-count"; cnt.textContent = (idx + 1) + " of " + slide.elements.length; hr.appendChild(cnt);
        const eye = document.createElement("button"); eye.type = "button"; eye.className = "pm-iconbtn"; eye.dataset.ik = "eye"; eye.textContent = el.visible ? "👁" : "🚫"; eye.setAttribute("aria-label", el.visible ? "Hide element" : "Show element"); eye.setAttribute("aria-pressed", el.visible ? "false" : "true"); eye.onclick = () => pAct(() => invoke("deck_toggle_element_visible", { index: idx })); hr.appendChild(eye);
        const del = document.createElement("button"); del.type = "button"; del.className = "pm-iconbtn danger"; del.dataset.ik = "del"; del.textContent = "🗑"; del.setAttribute("aria-label", "Delete element"); del.onclick = () => pmDeleteElement(idx); hr.appendChild(del);
        hdr.appendChild(hr); body.appendChild(hdr);
        // kind-specific
        if (el.kind === "text") {
          const ta = document.createElement("textarea"); ta.className = "pm-insp-ctrl"; ta.value = el.text || ""; ta.setAttribute("aria-label", "Text content");
          ta.addEventListener("change", () => pmUpdate(idx, { text: ta.value })); body.appendChild(ta);
          body.appendChild(pmInspRow("Size ‰", pmNum(D.size, (v) => pmUpdate(idx, { size_permille: Math.max(1, v) }))));
          body.appendChild(pmInspRow("Line ‰", pmNum(D.line, (v) => pmUpdate(idx, { line_height_permille: Math.max(1, v) }))));
          body.appendChild(pmInspRow("Font", pmFontSelect(el.font, (v) => pmUpdate(idx, { font: v || null }))));
          body.appendChild(pmInspRow("Weight", pmSelect([["400", "Regular"], ["700", "Bold"]], D.weight, (v) => pmUpdate(idx, { weight: parseInt(v, 10) }))));
          const align = document.createElement("span"); align.className = "pm-insp-align";
          [["left", "≡"], ["center", "≣"], ["right", "≡"]].forEach(([val, gl]) => { const b = document.createElement("button"); b.type = "button"; b.className = "pm-insp-ctrl"; b.dataset.ik = "align-" + val; b.textContent = gl; b.setAttribute("aria-label", "Align " + val); b.setAttribute("aria-pressed", D.alignH === val ? "true" : "false"); b.onclick = () => pmUpdate(idx, { align_h: val }); align.appendChild(b); });
          body.appendChild(pmInspRow("Align", align));
          body.appendChild(pmInspRow("V-align", pmSelect([["top", "Top"], ["middle", "Middle"], ["bottom", "Bottom"]], D.alignV, (v) => pmUpdate(idx, { align_v: v }))));
          body.appendChild(pmInspRow("Colour", pmColor(el.color, (c) => pmUpdate(idx, { color: c }))));
          body.appendChild(pmInspRow("Fit", pmSelect([["shrink_to_fit", "Shrink to fit"], ["clip", "Clip"]], D.fit, (v) => pmUpdate(idx, { fit: v }))));
        } else if (el.kind === "shape") {
          body.appendChild(pmInspRow("Fill", pmColor(el.fill, (c) => pmUpdate(idx, { fill: c }))));
          body.appendChild(pmInspRow("Border", pmColor(el.border, (c) => pmUpdate(idx, { border: c }))));
          body.appendChild(pmInspRow("Border ‰", pmNum(D.border, (v) => pmUpdate(idx, { border_permille: Math.max(0, v) }))));
          body.appendChild(pmInspRow("Corner ‰", pmNum(D.corner, (v) => pmUpdate(idx, { corner_permille: Math.max(0, v) }))));
          body.appendChild(pmInspRow("Shape", pmSelect([["rect", "Rectangle"], ["rounded_rect", "Rounded"], ["ellipse", "Ellipse"], ["triangle", "Triangle"]], D.variant, (v) => pmUpdate(idx, { variant: v }))));
        } else if (el.kind === "image") {
          const info = document.createElement("div"); info.className = "pm-insp-row";
          const thumb = document.createElement("span"); thumb.className = "pm-insp-thumb"; info.appendChild(thumb);
          const nm = document.createElement("span"); nm.className = el.missing ? "pm-insp-missing" : "pm-insp-lbl"; nm.textContent = (el.missing ? "⚠ Missing — " : "") + (el.name || "image"); info.appendChild(nm);
          body.appendChild(info);
          const rep = document.createElement("button"); rep.type = "button"; rep.className = "pm-insp-ctrl"; rep.dataset.ik = "replace"; rep.style.width = "100%"; rep.style.maxWidth = "none"; rep.textContent = el.missing ? "Relink…" : "Replace…"; rep.onclick = () => pmStartReplace(idx); body.appendChild(rep);
          // Live Fit control (C-008): Stretch (distort) / Fit (letterbox) / Fill (cover+crop),
          // driving the additive `fit` on the image element — the raster honours all three.
          const fitSel = pmSelect([["stretch", "Stretch"], ["fit", "Fit (letterbox)"], ["fill", "Fill (cover)"]], el.fit || "stretch", (v) => pmUpdate(idx, { fit: v }));
          fitSel.dataset.ik = "imgfit"; fitSel.setAttribute("aria-label", "Image fit");
          body.appendChild(pmInspRow("Fit", fitSel));
        }
        // common: opacity
        const sect = document.createElement("div"); sect.className = "pm-insp-sect"; sect.textContent = "OPACITY"; body.appendChild(sect);
        body.appendChild(pmInspRow("Opacity", pmNum(D.opacity, (v) => pmUpdate(idx, { opacity: Math.max(0, Math.min(255, v)) }))));
        // LAYERS panel: the whole slide's elements front→back — select · toggle · drag-reorder.
        const lsect = document.createElement("div"); lsect.className = "pm-insp-sect"; lsect.textContent = "LAYERS"; body.appendChild(lsect);
        body.appendChild(pmRenderLayers(dv, idx));
        // restore focus to the equivalent control after a button-triggered rebuild (WCAG 2.4.3).
        if (focusedIk) { const again = body.querySelector('[data-ik="' + focusedIk + '"]'); if (again) again.focus(); }
      }

      function pmRenderSlides(dv) {
        const list = pmEl("pm-slide-list");
        // Preserve keyboard focus across the rebuild (innerHTML wipe drops focus to <body>):
        // record the focused slide id, restore its card afterward.
        let focusedId = null;
        const ae = document.activeElement;
        if (ae && ae.closest) {
          const row = ae.closest(".pm-slide");
          if (row) focusedId = row.dataset.id;
        }
        list.innerHTML = "";
        (dv.slides || []).forEach((s) => {
          const isLive = s.id === dv.live;
          const isSel = s.id === dv.selected;
          const li = document.createElement("li");
          li.className = "pm-slide" + (isSel ? " sel" : "") + (isLive ? " live" : "");
          li.dataset.id = s.id;
          const nEl = document.createElement("span");
          nEl.className = "pm-slide-n";
          nEl.textContent = s.n;
          const card = document.createElement("button");
          card.type = "button";
          card.className = "pm-slide-card";
          // Non-colour state in the accessibility tree: selection + LIVE both in the label.
          card.setAttribute("aria-label",
            "Slide " + s.n + (isSel ? " (selected)" : "") + (isLive ? " (live on the audience output)" : ""));
          if (isSel) card.setAttribute("aria-current", "true");
          const lines = s.lines && s.lines.length ? s.lines : ["Empty slide"];
          lines.forEach((t, i) => {
            const d = document.createElement("div");
            d.className = i === 0 ? "l0" : "ln";
            d.textContent = t;
            card.appendChild(d);
          });
          // A visible, non-colour-only LIVE badge on the presented slide.
          if (isLive) {
            const badge = document.createElement("span");
            badge.className = "pm-slide-live-badge";
            badge.textContent = "LIVE";
            card.appendChild(badge);
          }
          card.onclick = () => pAct(() => invoke("deck_select_slide", { id: s.id }));
          li.appendChild(nEl);
          li.appendChild(card);
          // Delete-slide affordance → a role="alertdialog" confirm (C-001). A deck keeps at least
          // one slide, so the affordance is disabled (labelled) when this is the only slide.
          const only = (dv.slides || []).length <= 1;
          const delBtn = document.createElement("button");
          delBtn.type = "button";
          delBtn.className = "pm-slide-del";
          delBtn.dataset.del = s.id;
          delBtn.textContent = "🗑";
          delBtn.setAttribute("aria-label", "Delete slide " + s.n);
          if (only) {
            delBtn.disabled = true;
            delBtn.setAttribute("aria-disabled", "true");
            delBtn.title = "A deck keeps at least one slide";
          } else {
            delBtn.title = "Delete slide " + s.n;
            delBtn.onclick = (ev) => {
              ev.stopPropagation();
              pmConfirm({
                title: "Delete slide " + s.n + "?",
                body: "This removes the slide and its elements from the deck. You can undo it.",
                warning: isLive ? "This slide is LIVE on the audience output right now." : null,
                confirmLabel: "Delete slide",
                // Focus lands on Add-slide after the removal (the deleted card's slot is gone — WCAG 2.4.3).
                onConfirm: async () => {
                  const ok = await pAct(() => invoke("deck_remove_slide", { id: s.id }), "delete the slide");
                  if (ok) { const add = pmEl("pm-add-slide"); if (add) add.focus(); }
                },
              });
            };
          }
          li.appendChild(delBtn);
          list.appendChild(li);
        });
        // Restore focus to the equivalent slide card if the list had focus before the rebuild.
        if (focusedId != null) {
          const again = list.querySelector('.pm-slide[data-id="' + focusedId + '"] .pm-slide-card');
          if (again) again.focus();
        }
      }

      function pmRenderMedia(dv) {
        const m = (dv && dv.media) || { assets: [], total_label: "—", missing_count: 0, unused_count: 0 };
        const q = pmMediaQuery.trim().toLowerCase();
        const match = (a) => {
          if (pmMediaFilter !== "all" && a.kind !== pmMediaFilter) return false;
          if (q && !(a.name || "").toLowerCase().includes(q)) return false;
          return true;
        };
        // grid: images + video; audio list: audio.
        const grid = pmEl("pm-media-grid");
        grid.innerHTML = "";
        const visual = m.assets.filter((a) => a.kind !== "audio" && match(a));
        if (!visual.length) {
          const empty = document.createElement("div");
          empty.className = "pm-media-empty";
          empty.textContent = "No matching media.";
          grid.appendChild(empty);
        }
        // The asset used by the currently-selected image element → mark its cell "in use".
        const selEl = dv.slide && dv.slide.selected_element != null ? dv.slide.elements[dv.slide.selected_element] : null;
        const inUsePath = selEl && selEl.kind === "image" ? selEl.source : null;
        visual.forEach((a) => {
          const isInUse = a.path && a.path === inUsePath;
          const cell = document.createElement("div");
          cell.className = "pm-asset" + (a.missing ? " missing" : "") + (isInUse ? " in-use" : "");
          cell.setAttribute("role", "listitem");
          const thumb = document.createElement("button");
          thumb.type = "button";
          thumb.className = "pm-asset-thumb";
          // A non-image, non-missing grid cell (video) is not yet placeable — label it honestly,
          // not "Add media" (review 86ajvjtax #6). The "in use" state is named, not colour-only (1.4.1).
          thumb.setAttribute("aria-label",
            a.missing ? "Missing media " + a.name
              : a.kind !== "image" ? a.name + ", " + a.kind + " — on-slide playback arrives later"
                : "Add media " + a.name + (isInUse ? " (in use)" : a.unused ? " (unused)" : ""));
          if (a.missing) {
            thumb.innerHTML = '<span aria-hidden="true">⚠</span>';
          } else if (a.kind === "video") {
            thumb.innerHTML = '<span class="pm-play" aria-hidden="true">▶</span>';
            if (a.duration_label) {
              const b = document.createElement("span");
              b.className = "pm-badge";
              b.textContent = a.duration_label;
              thumb.appendChild(b);
            }
          }
          // Clicking an IMAGE asset either REPLACES the selected image element's source (when a
          // Replace… flow is armed) or adds it to the current slide (video/audio: no on-slide render).
          if (!a.missing && a.kind === "image") {
            thumb.onclick = () => {
              if (pmReplaceTarget != null) {
                const t = pmReplaceTarget;
                pmEndReplace();
                pmLastSelKey = null; // re-open the Inspector after the replace
                pAct(() => invoke("deck_replace_element_image", { index: t, mediaId: a.id }));
              } else {
                pAct(() => invoke("deck_add_image_element", { mediaId: a.id }));
              }
            };
          } else {
            // Missing, or a not-yet-placeable video → inert (disabled, not a dead enabled button).
            thumb.onclick = () => {};
            thumb.disabled = true;
            thumb.setAttribute("aria-disabled", "true");
          }
          const name = document.createElement("div");
          name.className = "pm-asset-name";
          name.textContent = a.name;
          const meta = document.createElement("div");
          meta.className = "pm-asset-meta";
          meta.textContent = a.missing ? "File moved" : a.kind.toUpperCase() + (a.size_label ? " · " + a.size_label : "");
          // Remove-from-library affordance → a role="alertdialog" confirm that warns when the asset
          // is still used on k slides (C-002). Removing it there leaves those slides missing media.
          const rm = document.createElement("button");
          rm.type = "button";
          rm.className = "pm-asset-del";
          rm.textContent = "✕";
          rm.setAttribute("aria-label", "Remove " + a.name + " from the library" + (a.uses ? " (used on " + a.uses + " slide" + (a.uses === 1 ? "" : "s") + ")" : ""));
          rm.title = "Remove from library";
          rm.onclick = (ev) => {
            ev.stopPropagation();
            pmConfirm({
              title: "Remove " + a.name + "?",
              body: "This removes the file from the media library. You can undo it.",
              warning: a.uses ? "Used on " + a.uses + " slide" + (a.uses === 1 ? "" : "s") + " — removing it leaves " + (a.uses === 1 ? "that slide" : "those slides") + " with missing media." : null,
              confirmLabel: "Remove",
              onConfirm: () => pAct(() => invoke("deck_remove_media", { id: a.id }), "remove the media"),
            });
          };
          cell.appendChild(thumb);
          cell.appendChild(name);
          cell.appendChild(meta);
          cell.appendChild(rm);
          grid.appendChild(cell);
        });
        // audio
        const audio = m.assets.filter((a) => a.kind === "audio" && (pmMediaFilter === "all" || pmMediaFilter === "audio") && (!q || (a.name || "").toLowerCase().includes(q)));
        const audioWrap = pmEl("pm-media-audio");
        const audioHead = pmEl("pm-media-audio-h");
        audioWrap.innerHTML = "";
        const showAudio = audio.length > 0;
        audioHead.style.display = showAudio ? "" : "none";
        audioWrap.style.display = showAudio ? "" : "none";
        audio.forEach((a) => {
          const row = document.createElement("div");
          row.className = "pm-audio-row";
          row.setAttribute("role", "listitem");
          row.innerHTML = '<span class="pm-play" aria-hidden="true">▶</span>';
          const nm = document.createElement("span");
          nm.className = "pm-audio-name";
          nm.textContent = a.name;
          const du = document.createElement("span");
          du.className = "pm-audio-dur";
          du.textContent = a.duration_label || "";
          row.appendChild(nm);
          row.appendChild(du);
          audioWrap.appendChild(row);
        });
        // footer
        pmEl("pm-media-total").textContent = (m.total_label || "—") + " of media";
        const stats = pmEl("pm-media-stats");
        const parts = [];
        if (m.missing_count) parts.push(m.missing_count + " missing");
        if (m.unused_count) parts.push(m.unused_count + " unused");
        stats.textContent = parts.join(" · ");
        stats.classList.toggle("warn", m.missing_count > 0);
      }

      // --- canvas preview + selection overlay ---------------------------------------------
      function pmRenderCanvas() {
        const cv = pmEl("pm-canvas");
        if (!cv) return;
        invoke("render_deck_slide", { id: null, maxW: 960, maxH: 540 })
          .then((r) => {
            if (r && r.available && r.frame && blitFrame(cv, r.frame)) {
              cv.classList.add("has-render");
            }
            pmDrawSelection();
          })
          .catch(() => {});
      }

      function pmDrawSelection() {
        const selBox = pmEl("pm-sel");
        const el = pmSelectedElement();
        const cv = pmEl("pm-canvas");
        const box = pmEl("pm-canvas-box");
        if (!selBox || !el || !cv || !box) {
          if (selBox) selBox.hidden = true;
          return;
        }
        const cr = cv.getBoundingClientRect();
        const br = box.getBoundingClientRect();
        const ox = cr.left - br.left;
        const oy = cr.top - br.top;
        selBox.hidden = false;
        selBox.style.left = ox + (el.x / 1000) * cr.width + "px";
        selBox.style.top = oy + (el.y / 1000) * cr.height + "px";
        selBox.style.width = (el.w / 1000) * cr.width + "px";
        selBox.style.height = (el.h / 1000) * cr.height + "px";
      }

      // Hit-test the topmost (highest z) visible element at a per-mille point.
      function pmHitTest(xp, yp) {
        const els = pmElements();
        let hit = null;
        els.forEach((e, i) => {
          if (!e.visible) return;
          if (xp >= e.x && xp <= e.x + e.w && yp >= e.y && yp <= e.y + e.h) {
            if (hit == null || e.z >= els[hit].z) hit = i;
          }
        });
        return hit;
      }

      // --- Inline text editing: double-click a text element to edit its content directly on the
      // canvas (PowerPoint / Google-Slides style). A textarea is overlaid on the element's rect;
      // blur or ⌘/Ctrl+Enter COMMITS via deck_set_element_text, Esc CANCELS. One editor at a time. ---
      let pmTextEditIdx = null;
      function pmEndTextEdit() {
        const ta = pmEl("pm-text-edit");
        pmTextEditIdx = null; // clear FIRST so the removal-triggered blur is a no-op
        if (ta) ta.remove();
      }
      function pmStartTextEdit(idx) {
        pmEndTextEdit();
        const el = pmElements()[idx];
        const cv = pmEl("pm-canvas"), box = pmEl("pm-canvas-box");
        if (!el || el.kind !== "text" || !cv || !box) return;
        const cr = cv.getBoundingClientRect(), br = box.getBoundingClientRect();
        if (!cr.width || !cr.height) return;
        const ta = document.createElement("textarea");
        ta.id = "pm-text-edit"; ta.className = "pm-text-edit";
        ta.value = el.text || "";
        ta.setAttribute("aria-label", "Edit text content — Enter for a new line, Escape to cancel");
        ta.style.left = (cr.left - br.left) + (el.x / 1000) * cr.width + "px";
        ta.style.top = (cr.top - br.top) + (el.y / 1000) * cr.height + "px";
        ta.style.width = (el.w / 1000) * cr.width + "px";
        ta.style.height = (el.h / 1000) * cr.height + "px";
        pmTextEditIdx = idx;
        box.appendChild(ta);
        ta.focus();
        ta.setSelectionRange(ta.value.length, ta.value.length);
        const commit = () => {
          if (pmTextEditIdx == null) return;
          const v = ta.value, i = pmTextEditIdx;
          pmEndTextEdit();
          pAct(() => invoke("deck_set_element_text", { index: i, text: v }), "edit the text");
        };
        ta.addEventListener("blur", commit);
        ta.addEventListener("keydown", (ev) => {
          if (ev.key === "Escape") { ev.preventDefault(); pmEndTextEdit(); cv.focus(); }
          else if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); commit(); cv.focus(); }
          // Keep every keystroke inside the editor — app shortcuts (⌘Z / ⌘1–6 / Delete) must not
          // fire while typing. Plain Enter falls through so it inserts a newline (multi-line text).
          ev.stopPropagation();
        });
      }

      // --- wire the static controls (they exist at load; #surface-presentation is in the DOM) ---
      (function wirePresentation() {
        pmEl("pm-add-slide").onclick = pmAddSlide;
        if (pmEl("pm-done")) pmEl("pm-done").onclick = () => { pmSetMode("grid"); pmRenderGrid(pmDv); }; // editor → grid
        pmEl("pm-undo").onclick = pmUndo;
        pmEl("pm-redo").onclick = pmRedo;
        pmEl("pm-import").onclick = () => pAct(() => invoke("deck_import_image"), "import the image");
        // Error banner: Retry re-runs the last rejected deck action; Dismiss hides it.
        pmEl("pm-error-retry").onclick = () => { if (pmLastAct) pAct(pmLastAct.fn, pmLastAct.opName); };
        pmEl("pm-error-dismiss").onclick = pmClearError;
        // Presentations Library: the deck-switcher opens it; ＋ New creates; the library controls.
        pmEl("pm-deckswitch").onclick = pmShowLibrary;
        pmEl("pm-newpres").onclick = pmLibNew;
        pmEl("pm-lib-new").onclick = pmLibNew;
        pmEl("pm-lib-empty-new").onclick = pmLibNew;
        pmEl("pm-lib-retry").onclick = pmLibLoad;
        pmEl("pm-lib-q").addEventListener("input", (e) => { pmLibQuery = e.target.value; pmRenderLibGrid(); });
        pmEl("pm-lib-sort").addEventListener("change", (e) => { pmLibSort = e.target.value; pmRenderLibGrid(); });
        // add-content toolbar
        document.querySelectorAll("#surface-presentation .pm-tool[data-add]").forEach((b) => {
          // The host handles each kind: "background" adds a full-frame shape behind the content,
          // "image" adds the first library image (or is a no-op when there is none). A no-op never
          // corrupts undo/redo (the host snapshots only on a real edit).
          b.onclick = () => pAct(() => invoke("deck_add_element", { kind: b.dataset.add }));
        });
        // per-slide props
        pmEl("pm-notes").addEventListener("change", (e) =>
          pAct(() => invoke("deck_set_notes", { notes: e.target.value })));
        pmEl("pm-transition").addEventListener("change", (e) =>
          pAct(() => invoke("deck_set_transition", { transition: e.target.value })));
        pmEl("pm-autoadv").addEventListener("change", (e) => {
          const secs = parseInt(e.target.value, 10) || 0;
          pAct(() => invoke("deck_set_auto_advance", { secs: secs > 0 ? secs : null }));
        });
        // media filters + search
        document.querySelectorAll("#surface-presentation .pm-mtab").forEach((t) => {
          t.onclick = () => {
            pmMediaFilter = t.dataset.filter;
            document.querySelectorAll("#surface-presentation .pm-mtab").forEach((x) =>
              x.setAttribute("aria-pressed", x === t ? "true" : "false"));
            if (pmDv) pmRenderMedia(pmDv);
          };
        });
        pmEl("pm-media-q").addEventListener("input", (e) => {
          pmMediaQuery = e.target.value;
          if (pmDv) pmRenderMedia(pmDv);
        });

        // Right-panel Media/Inspector tabs (roving tabindex + Left/Right).
        const mTab = pmEl("pm-tab-media"), iTab = pmEl("pm-tab-inspector");
        mTab.onclick = () => pmSetRight("media");
        iTab.onclick = () => { if (iTab.getAttribute("aria-disabled") !== "true") pmSetRight("inspector"); };
        [mTab, iTab].forEach((t, i, arr) => {
          t.addEventListener("keydown", (e) => {
            if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
            e.preventDefault();
            const other = arr[(i + 1) % 2];
            if (other.getAttribute("aria-disabled") === "true") return;
            other.focus();
            other.click();
          });
        });
        pmEl("pm-replace-cancel").onclick = () => {
          pmEndReplace();
          pmLastSelKey = null; // re-open the Inspector for the still-selected element
          if (pmDv) renderPresentation(pmDv);
        };

        // canvas: click-to-select + drag-to-move (per-mille), keyboard edits.
        const cv = pmEl("pm-canvas");
        cv.tabIndex = 0;
        const pointToPermille = (ev) => {
          const cr = cv.getBoundingClientRect();
          if (!cr.width || !cr.height) return null;
          const xp = Math.round(((ev.clientX - cr.left) / cr.width) * 1000);
          const yp = Math.round(((ev.clientY - cr.top) / cr.height) * 1000);
          return { xp: Math.max(0, Math.min(1000, xp)), yp: Math.max(0, Math.min(1000, yp)) };
        };
        cv.addEventListener("pointerdown", (ev) => {
          cv.focus();
          const p = pointToPermille(ev);
          if (!p) return;
          const idx = pmHitTest(p.xp, p.yp);
          if (idx == null) {
            if (pmSelectedElement()) pAct(() => invoke("deck_select_element", { index: null }));
            return;
          }
          const el = pmElements()[idx];
          pmDrag = { index: idx, grabX: p.xp, grabY: p.yp, ox: el.x, oy: el.y, w: el.w, h: el.h, moved: false };
          if (cv.setPointerCapture) { try { cv.setPointerCapture(ev.pointerId); } catch (e) {} }
          if (!pmDv.slide || pmDv.slide.selected_element !== idx) {
            pAct(() => invoke("deck_select_element", { index: idx }));
          }
        });
        // Minimum element size while resizing (per-mille) — never let a drag collapse an element.
        const PM_MIN = 20;
        cv.addEventListener("pointermove", (ev) => {
          if (!pmDrag) return;
          const p = pointToPermille(ev);
          if (!p) return;
          const dx = p.xp - pmDrag.grabX, dy = p.yp - pmDrag.grabY;
          let x = pmDrag.ox, y = pmDrag.oy, w = pmDrag.w, h = pmDrag.h;
          if (pmDrag.handle) {
            // RESIZE: the grabbed edge/corner moves; the opposite edge stays anchored. Each axis is
            // clamped into 0..1000 with a PM_MIN floor so it never inverts or leaves the frame.
            const right = pmDrag.ox + pmDrag.w, bottom = pmDrag.oy + pmDrag.h, d = pmDrag.handle;
            if (d.indexOf("e") >= 0) w = Math.max(PM_MIN, Math.min(1000 - pmDrag.ox, pmDrag.w + dx));
            if (d.indexOf("w") >= 0) { x = Math.max(0, Math.min(right - PM_MIN, pmDrag.ox + dx)); w = right - x; }
            if (d.indexOf("s") >= 0) h = Math.max(PM_MIN, Math.min(1000 - pmDrag.oy, pmDrag.h + dy));
            if (d.indexOf("n") >= 0) { y = Math.max(0, Math.min(bottom - PM_MIN, pmDrag.oy + dy)); h = bottom - y; }
          } else {
            // MOVE: translate, clamped so the top-left stays on the frame.
            x = Math.max(0, Math.min(1000, pmDrag.ox + dx));
            y = Math.max(0, Math.min(1000, pmDrag.oy + dy));
          }
          pmDrag.nx = x; pmDrag.ny = y; pmDrag.nw = w; pmDrag.nh = h; pmDrag.moved = true;
          // live overlay feedback (commit on pointerup)
          const selBox = pmEl("pm-sel"), box = pmEl("pm-canvas-box"), cr = cv.getBoundingClientRect(), br = box.getBoundingClientRect();
          if (selBox && !selBox.hidden) {
            selBox.style.left = (cr.left - br.left) + (x / 1000) * cr.width + "px";
            selBox.style.top = (cr.top - br.top) + (y / 1000) * cr.height + "px";
            selBox.style.width = (w / 1000) * cr.width + "px";
            selBox.style.height = (h / 1000) * cr.height + "px";
          }
        });
        const endDrag = () => {
          if (pmDrag && pmDrag.moved && pmDrag.nx != null) {
            const d = pmDrag;
            pAct(() => invoke("deck_move_element", { index: d.index, x: d.nx, y: d.ny, w: d.nw, h: d.nh }));
          }
          pmDrag = null;
        };
        cv.addEventListener("pointerup", endDrag);
        cv.addEventListener("pointercancel", () => { pmDrag = null; });
        // Double-click a TEXT element → inline edit its content on the canvas (PowerPoint-style).
        cv.addEventListener("dblclick", (ev) => {
          const p = pointToPermille(ev);
          if (!p) return;
          const idx = pmHitTest(p.xp, p.yp);
          if (idx == null) return;
          const el = pmElements()[idx];
          if (el && el.kind === "text") { ev.preventDefault(); pmStartTextEdit(idx); }
        });
        // Resize handles on the selection box: start a resize drag (the box/overlay are
        // pointer-events:none, so these small handles are the only pointer targets there). Capture
        // the pointer on the canvas so the existing pointermove/up drive the resize + commit.
        document.querySelectorAll("#pm-sel .pm-h").forEach((hEl) => {
          hEl.addEventListener("pointerdown", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const idx = pmDv && pmDv.slide ? pmDv.slide.selected_element : null;
            if (idx == null) return;
            const el = pmElements()[idx];
            if (!el) return;
            const p = pointToPermille(ev);
            if (!p) return;
            pmDrag = { index: idx, handle: hEl.dataset.h, grabX: p.xp, grabY: p.yp, ox: el.x, oy: el.y, w: el.w, h: el.h, moved: false };
            if (cv.setPointerCapture) { try { cv.setPointerCapture(ev.pointerId); } catch (e) {} }
          });
        });
        cv.addEventListener("keydown", (ev) => {
          const els = pmElements();
          const cur = pmDv && pmDv.slide ? pmDv.slide.selected_element : null;
          // Keyboard SELECTION (WCAG 2.1.1): Tab cycles elements front→back (Shift+Tab reverses);
          // when nothing is selected, Tab or an arrow selects the topmost element — so a
          // keyboard-only operator can reach ANY element, not just a just-added one.
          if (ev.key === "Tab" && els.length) {
            ev.preventDefault();
            const order = pmZOrder(); // element indices, front (highest z) → back
            let pos = cur == null ? -1 : order.indexOf(cur);
            pos = ev.shiftKey ? (pos - 1 + order.length) % order.length : (pos + 1) % order.length;
            const next = order[pos];
            pmAnnounce("Selected " + (els[next].label || els[next].kind) + " element");
            pAct(() => invoke("deck_select_element", { index: next }));
            return;
          }
          const idx = cur;
          if (idx == null) {
            if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].indexOf(ev.key) >= 0 && els.length) {
              ev.preventDefault();
              pAct(() => invoke("deck_select_element", { index: pmZOrder()[0] }));
            }
            return;
          }
          const el = els[idx];
          if (!el) return;
          const step = ev.shiftKey ? 50 : 10;
          const clamp = (v) => Math.max(0, Math.min(1000, v));
          // Alt+arrows RESIZE (keyboard parity with the drag handles, WCAG 2.1.1): the top-left is
          // anchored, so Right/Down grow and Left/Up shrink the width/height (floored at PM_MIN=20,
          // kept within the frame). Shift makes a coarse step. Handled before the plain-arrow move.
          if (ev.altKey && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].indexOf(ev.key) >= 0) {
            ev.preventDefault();
            let w = el.w, h = el.h;
            if (ev.key === "ArrowRight") w = Math.min(1000 - el.x, el.w + step);
            else if (ev.key === "ArrowLeft") w = Math.max(20, el.w - step);
            else if (ev.key === "ArrowDown") h = Math.min(1000 - el.y, el.h + step);
            else if (ev.key === "ArrowUp") h = Math.max(20, el.h - step);
            pAct(() => invoke("deck_move_element", { index: idx, x: el.x, y: el.y, w, h }));
            return;
          }
          const nudge = (dx, dy) => {
            ev.preventDefault();
            pAct(() => invoke("deck_move_element", { index: idx, x: clamp(el.x + dx), y: clamp(el.y + dy), w: el.w, h: el.h }));
          };
          if (ev.key === "ArrowLeft") nudge(-step, 0);
          else if (ev.key === "ArrowRight") nudge(step, 0);
          else if (ev.key === "ArrowUp") nudge(0, -step);
          else if (ev.key === "ArrowDown") nudge(0, step);
          else if (ev.key === "Delete" || ev.key === "Backspace") { ev.preventDefault(); pmDeleteElement(idx); }
          else if (ev.key === "[") { ev.preventDefault(); pAct(() => invoke("deck_set_element_z", { index: idx, z: Math.max(-128, el.z - 1) })); }
          else if (ev.key === "]") { ev.preventDefault(); pAct(() => invoke("deck_set_element_z", { index: idx, z: Math.min(127, el.z + 1) })); }
          else if (ev.key === "h" || ev.key === "H") { ev.preventDefault(); pAct(() => invoke("deck_toggle_element_visible", { index: idx })); }
        });

        // ⌘/Ctrl+Z undo, ⌘/Ctrl+⇧Z redo — only while the Presentation surface is active and not
        // typing in a field (native text undo wins there) or a modal is open (FR-016, ≥20 steps).
        document.addEventListener("keydown", (ev) => {
          const surf = document.getElementById("surface-presentation");
          if (!surf || !surf.classList.contains("active")) return;
          if (window.__cmdPalette && window.__cmdPalette.isOpen()) return;
          if (document.querySelector(".pm-confirm-back")) return; // don't act behind an open confirm/dialog
          if (!(ev.ctrlKey || ev.metaKey) || ev.altKey) return;
          if ((ev.key === "n" || ev.key === "N") && !ev.shiftKey) { ev.preventDefault(); pmLibNew(); return; }
          if (ev.key !== "z" && ev.key !== "Z") return;
          const t = ev.target;
          if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
          ev.preventDefault();
          if (ev.shiftKey) pmRedo();
          else pmUndo();
        });

        // Keep the selection overlay aligned when the window resizes.
        window.addEventListener("resize", () => { if (pmDv) pmDrawSelection(); });
      })();
