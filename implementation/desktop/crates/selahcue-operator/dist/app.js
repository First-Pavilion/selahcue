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
        // CON-136 — the on-air link runs on EVERY poll, independent of syncDetections' own
        // change-key: it must clear the instant view.live_scripture stops matching, even when
        // view.detections itself hasn't changed (e.g. a Prev/Next or a blackout is what moved
        // live content on, not a new detection).
        syncDetOnAir(view);
        // System & recovery states (Frame G). MUST run before the early-returns below: the
        // change-key at 37-42 covers plan_name/items/themes/saved_themes only, so a host that
        // reports a NEW fault while the plan is unchanged would never reach a sync placed after
        // it — the console would sit on a stale "healthy" while the output was held.
        syncRecovery(view);
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
        // CON-099/101/102 — the engaged blackout state, in words. The label states WHAT the state
        // is, the explanation states what the AUDIENCE sees and how to get back, and Restore is a
        // dedicated recovery control. The fill deliberately stays the canonical #8f2030 and does
        // NOT follow the frame's #ff4d4d, on which the 13px white label measures 3.27:1.
        const bLabel = document.getElementById("blackout-label");
        if (bLabel) bLabel.textContent = view.blackout ? "BLACKED OUT" : "BLACKOUT";
        const bExplain = document.getElementById("blackout-explain");
        const bRestore = document.getElementById("restore-output");
        const bNote = document.querySelector("#emergency .note");
        if (bExplain) bExplain.hidden = !view.blackout;
        if (bRestore) bRestore.hidden = !view.blackout;
        // The explanation takes the note's slot: two competing sentences in one 56px bar reads as
        // neither. The note is general guidance; during a blackout the specific state wins.
        if (bNote) bNote.hidden = !!view.blackout;
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
      // Short role-badge label (Design 2.0 §ROLE BADGE). This names the screen's ROLE, which is
      // true in both the open and closed states — the open/closed distinction is carried by the
      // status pill, the meta line and the toggle's label, not duplicated here.
      function roleBadgeText(role) {
        return role === "main" ? "MAIN" : role === "stage" ? "STAGE"
          : role === "lower-third" ? "L3 · ALPHA" : "STREAM";
      }
      // Does this screen own an OS OUTPUT WINDOW? For the two BUILT-IN physical screens
      // (`main` / `stage`) `enabled` no longer means "composite an all-black frame" (a mute, with
      // the window still up) — it means THE OUTPUT WINDOW EXISTS. Toggling off destroys the
      // window; toggling on re-creates it; the window's own close button performs the identical
      // action, so a close from the OS flips this flag with NO operator interaction.
      //
      // A VIRTUAL feed (lower-third / stream) has NO window at all — its `enabled` still gates
      // NDI output only — so window language must NEVER be applied to one. The built-ins are
      // exactly the non-deletable `main`/`stage` entries: an added virtual always mints a
      // suffixed id (`stream-2`, `main-2`, …) because the bare ids are taken by the registry.
      function hasOutputWindow(s) {
        return !s.deletable && (s.screen === "main" || s.screen === "stage");
      }
      // The enable switch's accessible name. For a windowed screen it names the WINDOW action
      // (close / open), because that is what the toggle now does; for a virtual feed it stays
      // enable/disable, which is what its flag still means.
      function enableToggleLabel(s) {
        if (hasOutputWindow(s)) {
          return (s.enabled ? "Close" : "Open") + " the " + screenDisplayName(s) + " output window";
        }
        return (s.enabled ? "Disable" : "Enable") + " the " + screenDisplayName(s) + " output";
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
        // Physical output (display assignment + format + telemetry) is keyed by role.
        // Computed BEFORE the deferred-rebuild guard below, which needs it to reconcile the
        // status pills in place.
        const outByRole = {};
        outs.forEach((o) => { outByRole[o.role] = o; });
        // Never yank an OPEN PICKER out from under the operator: a focused <select>
        // survives, and the fresh data renders when focus leaves it. A toggle/button
        // click is a completed action, so it does NOT defer — the row updates at once.
        const ae = document.activeElement;
        const inspEl = document.getElementById("screens-inspector");
        if (ae && (list.contains(ae) || (inspEl && inspEl.contains(ae))) && ae.tagName === "SELECT") {
          outputsPending = view;
          // …but a screen's `enabled` can now change with NO operator interaction: for a
          // built-in main/stage it means the OS output window exists, and the window's own
          // close button destroys it. A <select> can hold focus indefinitely, so deferring the
          // WHOLE rebuild would leave the switch showing ON — and the pill showing LIVE — for a
          // window that is already gone, with nothing scheduled to correct it. Reconcile just
          // that authoritative state in place; it touches no <select>, so the open picker
          // survives exactly as before. `outputsKey` is deliberately NOT set here, so the full
          // rebuild still happens once focus leaves.
          syncEnableState(registry, outByRole);
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
          // The AUTHORITATIVE enable state, carried on the element rather than only in this
          // render pass's closure — syncEnableState updates it in place when the grid rebuild
          // is deferred (see renderOutputs), and the revert below reads it back.
          cb.dataset.enabled = s.enabled ? "1" : "0";
          cb.setAttribute("aria-label", enableToggleLabel(s));
          cb.onchange = () => {
            // Revert the optimistic native flip to the authoritative value BEFORE the round
            // trip: a SUCCESS re-renders with the new state; a REJECTED call (RBAC / older
            // host) leaves the switch showing the true, unchanged state — never a lie.
            // Read that value from `dataset.enabled`, NOT from this closure's `s.enabled`:
            // `enabled` can now change with no operator interaction (the output window's own
            // close button destroys the window), and syncEnableState reconciles it onto the
            // element without a rebuild — so the closure can be stale while the dataset is not.
            const want = cb.checked;
            cb.checked = cb.dataset.enabled === "1";
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

      // Reconcile ONLY the authoritative enable state onto the already-rendered cards, with no
      // grid rebuild. Used on the deferred path in renderOutputs, where a focused <select> must
      // not be destroyed but the enable switch must still tell the truth: for a built-in
      // main/stage, `enabled` now tracks whether the OS output window exists, and the window's
      // own close button flips it with no operator interaction at all.
      //
      // Every value written here comes from the SAME helpers the full rebuild uses
      // (statusPillFor / metaLine / enableToggleLabel), so the two paths cannot drift. Nothing
      // here touches a <select>, an <option>, or the card's structure.
      function syncEnableState(registry, outByRole) {
        const list = document.getElementById("screens-list");
        if (!list) return;
        const byScreen = {};
        registry.forEach((s) => { byScreen[s.screen] = s; });
        // Match on dataset rather than a built selector so an unusual screen id can never
        // produce an invalid querySelector.
        Array.from(list.querySelectorAll(".screen-row")).forEach((card) => {
          const s = byScreen[card.dataset.screen];
          if (!s) return; // a card whose screen has gone: the deferred full rebuild handles it
          const o = outByRole[s.role];
          card.classList.toggle("screen-disabled", !s.enabled);
          const cb = card.querySelector(".screen-enable-toggle");
          if (cb) {
            // Both the visible switch AND the authoritative value its revert reads back.
            cb.checked = s.enabled;
            cb.dataset.enabled = s.enabled ? "1" : "0";
            cb.setAttribute("aria-label", enableToggleLabel(s));
          }
          const pill = card.querySelector(".scr-pill");
          if (pill && pill.parentNode) pill.parentNode.replaceChild(statusPillFor(s, o), pill);
          const meta = card.querySelector(".scr-card-meta");
          if (meta) meta.textContent = metaLine(s, o, cfgOf(s));
        });
        // The inspector header mirrors the selected card's status, so reconcile it too — the
        // focused <select> that caused the deferral is often IN the inspector, and a header
        // still reading LIVE beside a CLOSED card would be a visible contradiction.
        const insp = document.getElementById("screens-inspector");
        const sel = byScreen[selectedScreen];
        if (insp && sel) {
          const hpill = insp.querySelector(".scr-iheader .scr-pill");
          if (hpill && hpill.parentNode) {
            hpill.parentNode.replaceChild(statusPillFor(sel, outByRole[sel.role]), hpill);
          }
          const sub = insp.querySelector(".scr-iheader-sub");
          if (sub) sub.textContent = inspectorSubtitle(sel, outByRole[sel.role]);
        }
      }

      // The inspector's identity subtitle: "<ROLE> role · <where it is>". Shared by the full
      // inspector render and the in-place reconcile above so the two cannot drift.
      function inspectorSubtitle(s, o) {
        const isPhysical = s.role === "main" || s.role === "stage";
        let where;
        if (hasOutputWindow(s) && !s.enabled) where = "No output window";
        else if (o && o.display) where = o.display;
        else where = isPhysical ? "No display assigned" : "Composed feed — no physical output";
        return roleBadgeText(s.role) + " role · " + where;
      }

      // The status pill for a card (Design 2.0 §STATUS PILL): honest — CLOSED when a windowed
      // screen has no output window; LIVE only when the physical output is presenting;
      // CONNECTED when assigned; READY for a composed virtual feed; NO SIGNAL when a physical
      // role has no display.
      function statusPillFor(s, o) {
        const pill = document.createElement("span"); pill.className = "scr-pill";
        let variant = "ready", label = "READY";
        if (s.role === "main" || s.role === "stage") {
          if (hasOutputWindow(s) && !s.enabled) {
            // No window exists. The display assignment and the signal telemetry both describe
            // a window that is not open, so reporting LIVE / CONNECTED / NO SIGNAL here would
            // claim an output that the operator has already closed. CLOSED is neutral, not a
            // fault: it is a deliberate operator state, and the toggle re-opens the window.
            variant = "closed"; label = "CLOSED";
          } else if (o && o.assigned && o.signal === "healthy") { variant = "live"; label = "LIVE"; }
          else if (o && o.assigned) { variant = "connected"; label = "CONNECTED"; }
          else if (o && o.signal === "degraded") { variant = "warning"; label = "DEGRADED"; }
          else { variant = "warning"; label = "NO SIGNAL"; }
        } else {
          // A virtual audience feed composes + previews; if it broadcasts NDI, surface that.
          const cfg = cfgOf(s);
          if (s.enabled && cfg.ndi_enabled) {
            variant = "connected"; label = "NDI";
          } else {
            // A virtual feed has no window to close — disabling it only stops the NDI
            // broadcast, so its wording stays COMPOSED / MUTED (never "closed").
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
        // A closed windowed screen has NO window: its resolution / fps / orientation all
        // describe a surface that does not currently exist, so the meta line reports the
        // absence rather than the specification of a window nobody can see.
        if (hasOutputWindow(s) && !s.enabled) return "No output window";
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
        sub.textContent = inspectorSubtitle(s, o);
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
        if (hasOutputWindow(s) && !s.enabled) {
          // No window, so there is no signal to report — stale telemetry from the last open
          // window must not be presented as the current state of a closed one.
          sig = "neutral"; txt = "Output window closed · nothing is being displayed";
        } else if (o && o.signal === "healthy") {
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
      const APP_SURFACES = ["console", "preservice", "presentation", "theme-designer", "screens", "remote", "plan", "settings", "transcripts"];
      // Kept in sync with the nav items' .nav-t labels — the topbar surface label + the SR
      // route announcement read from here, so a drift would show a name the menu doesn't use.
      const SURFACE_LABEL = {
        console: "Live Console", preservice: "Pre-service Check", presentation: "Presentation", "theme-designer": "Theme Designer",
        screens: "Screens & Outputs", remote: "Remote Control", plan: "Service Plan", settings: "Settings", transcripts: "Transcripts",
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
        // Transcripts (86akcffvt) reloads the list every time the surface is opened — a fresh read
        // from the shared store each visit, never a stale in-memory cache from a prior visit.
        if (name === "transcripts" && typeof trActivate === "function") trActivate();
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
          // Pre-service Check lives in the Settings sidebar but is a full surface (driven by
          // preservice.js) — open it directly rather than routing to a Settings sub-page.
          if (b.dataset.setpage === "preservice") {
            b.onclick = () => { closeAppMenu(); showSurface("preservice"); };
          } else {
            b.onclick = () => setSettingsPage(b.dataset.setpage);
          }
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

      // === Theme Designer undo/redo (client-side snapshot history, ⌘Z / ⌘⇧Z) =================
      // The whole editable document is the serialisable `tdTheme` object, so history is a bounded
      // stack of JSON snapshots. Capture is DIFF-ON-RENDER: tdSync()/tdPreview() run after every
      // edit and ask tdHistory.note() whether tdTheme changed since the last committed state. A
      // pointer drag or a typing burst COALESCES into ONE step — pointerdown/focusin unseals,
      // pointerup/change/blur seals — so dragging a slider isn't one undo entry per pixel. Bounded
      // (no unbounded growth): both stacks are capped at TD_HISTORY_MAX.
      const TD_HISTORY_MAX = 60; // matches the deck's MAX_UNDO; each entry is one bounded theme JSON
      const tdHistory = {
        undo: [],
        redo: [],
        baseline: null, // JSON of tdTheme as of the last committed state (null = uninitialised)
        sealed: true, // false while a gesture coalesces changes (commit deferred to seal())
        applying: false, // true while undo/redo swaps state (suppresses capture)
        // Start a fresh document (theme load / switch): drop history so ⌘Z can't cross themes.
        reset() {
          this.undo.length = 0;
          this.redo.length = 0;
          this.baseline = tdTheme ? JSON.stringify(tdTheme) : null;
          this.sealed = true;
        },
        // Called after any potential mutation. Commits the pre-edit baseline once tdTheme has
        // actually changed AND we are neither mid-gesture nor mid-undo.
        note() {
          if (this.applying || !tdTheme) return;
          const cur = JSON.stringify(tdTheme);
          if (this.baseline === null) { this.baseline = cur; return; } // first sight: seed baseline
          if (cur === this.baseline) return; // nothing changed
          if (!this.sealed) return; // mid-gesture: defer the commit to seal()
          this.undo.push(this.baseline);
          if (this.undo.length > TD_HISTORY_MAX) this.undo.shift();
          this.redo.length = 0; // a new edit invalidates the redo branch
          this.baseline = cur;
        },
        openGesture() { this.sealed = false; },
        seal() { if (!this.sealed) { this.sealed = true; this.note(); } },
        canUndo() { return this.undo.length > 0; },
        canRedo() { return this.redo.length > 0; },
        undoAct() {
          if (!this.undo.length || !tdTheme) return false;
          this.redo.push(JSON.stringify(tdTheme));
          if (this.redo.length > TD_HISTORY_MAX) this.redo.shift();
          this._apply(this.undo.pop());
          return true;
        },
        redoAct() {
          if (!this.redo.length || !tdTheme) return false;
          this.undo.push(JSON.stringify(tdTheme));
          if (this.undo.length > TD_HISTORY_MAX) this.undo.shift();
          this._apply(this.redo.pop());
          return true;
        },
        _apply(snapJson) {
          this.applying = true; // suppress note() while the re-render touches tdSync/tdPreview
          tdTheme = JSON.parse(snapJson);
          this.baseline = snapJson;
          this.sealed = true;
          const n = tdEls().length; // the restored theme may hold fewer elements than the selection
          if (tdSelEl >= n) tdSelEl = n - 1; // -1 when none → a region is active
          if (tdSelEl < -1) tdSelEl = -1;
          tdRerenderAll();
          this.applying = false;
        },
      };
      // Re-render the whole designer from tdTheme (mirrors the theme-load path + the selection box).
      function tdRerenderAll() {
        tdSync(); // inspector + LAYERS + background + region controls
        tdPreview(); // canvas raster
        tdDrawSel(); // selection overlay
      }
      // Keyboard + gesture wiring for Theme Designer undo/redo. Gesture coalescing makes a drag or
      // a typing burst one step; ⌘Z / ⌘⇧Z (Ctrl on Win/Linux) act while the designer is active and
      // focus is not in a text field (native field-undo wins there).
      (function tdWireHistory() {
        const surf = document.getElementById("surface-theme-designer");
        if (!surf) return;
        surf.addEventListener("pointerdown", () => tdHistory.openGesture(), true);
        surf.addEventListener("focusin", () => tdHistory.openGesture());
        surf.addEventListener("change", () => tdHistory.seal());
        surf.addEventListener("focusout", () => tdHistory.seal());
        // A drag can end outside the surface — seal on the window pointerup (no-op if already sealed).
        window.addEventListener("pointerup", () => tdHistory.seal(), true);
        document.addEventListener("keydown", (ev) => {
          if (!surf.classList.contains("active")) return;
          if (window.__cmdPalette && window.__cmdPalette.isOpen()) return;
          if (document.querySelector(".pm-confirm-back")) return; // a modal dialog owns keys
          if (isMenuOpen()) return;
          if (!(ev.ctrlKey || ev.metaKey) || ev.altKey) return;
          if (ev.key !== "z" && ev.key !== "Z") return;
          const t = ev.target;
          if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
          ev.preventDefault();
          if (ev.shiftKey) tdAnnounce(tdHistory.redoAct() ? "Redo" : "Nothing to redo");
          else tdAnnounce(tdHistory.undoAct() ? "Undo" : "Nothing to undo");
        });
      })();

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
        tdHistory.reset(); // a loaded theme is a fresh document — no undo across the switch
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
            tdHistory.reset(); // fresh document on load — no undo across the switch
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
            tdHistory.reset(); // fresh document on load — no undo across the switch
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
        tdHistory.note(); // structural edits (add/delete/paste/reorder/toggle) land here first
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
        tdHistory.note(); // fold any edit that led here into undo history (coalesced by gesture)
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
        let result;
        try { result = await invoke("pick_image"); }
        catch (e) { tdStatus("No native picker — paste the image path in the field below."); document.getElementById("td-bg-img-path").focus(); return; }
        if (result.outcome === "cancelled") return;
        if (result.outcome === "rejected") { tdStatus(result.reason); return; }
        const path = result.path;
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
        // Delete the selected element (single press — the global capture handler normally gets
        // here first; this is the focused-canvas fallback).
        if ((e.key === "Delete" || e.key === "Backspace") && tdActiveIsEl()) {
          e.preventDefault();
          tdDeleteElNow();
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
        let result;
        try {
          result = await invoke("pick_image");
        } catch (e) {
          tdOpenImgRow(replace); // no native dialog → the manual path row
          return;
        }
        if (result.outcome === "cancelled") return;
        if (result.outcome === "rejected") { tdStatus(result.reason); return; }
        const path = result.path;
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
      // Immediate delete (no arm) — used by the Delete/Backspace key: a keypress is already a
      // deliberate action, so it removes the selected element in one press.
      function tdDeleteElNow() {
        if (!tdActiveIsEl()) return;
        clearTimeout(tdElDelTimer);
        tdElDelArm = false;
        const btn = document.getElementById("td-el-del");
        if (btn) btn.textContent = "Delete element";
        const i = tdSelEl;
        tdEls().splice(i, 1);
        tdSelEl = tdEls().length ? Math.min(i, tdEls().length - 1) : -1;
        tdSync();
        tdPreview();
        tdAnnounce("Element deleted");
      }
      // Button path keeps a two-click arm — a stray MOUSE click shouldn't destroy work.
      function tdDeleteEl() {
        if (!tdActiveIsEl()) return;
        const btn = document.getElementById("td-el-del");
        if (!tdElDelArm) {
          tdElDelArm = true;
          btn.textContent = "Click again to delete";
          tdAnnounce("Click again to remove this element.");
          clearTimeout(tdElDelTimer);
          tdElDelTimer = setTimeout(() => { tdElDelArm = false; btn.textContent = "Delete element"; }, 3000);
          return;
        }
        tdDeleteElNow();
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
      // CON-102 — Restore explicitly turns blackout OFF (never a toggle: this button only ever
      // means "bring the audience back", so double-activation cannot re-black the output).
      // The button disappears with the state it undoes, so focus is returned to #blackout
      // deliberately rather than being dropped on <body> (WCAG 2.4.3).
      const restoreBtn = document.getElementById("restore-output");
      if (restoreBtn) {
        restoreBtn.onclick = () => {
          act(() => invoke("blackout", { on: false }));
          const bo = document.getElementById("blackout");
          if (bo) bo.focus();
        };
      }
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
        // ←/→ (and Home/End) move between the two sub-tabs — the APG tablist pattern, matching
        // the content + right-column tablists. Keyboard selection also moves focus to the new tab.
        [segTimer, segStage].forEach((tab) => {
          tab.addEventListener("keydown", (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
              e.preventDefault();
              const toStage = tab === segTimer; // two tabs: either arrow flips to the other
              showStage(toStage);
              (toStage ? segStage : segTimer).focus();
            } else if (e.key === "Home") {
              e.preventDefault();
              showStage(false);
              segTimer.focus();
            } else if (e.key === "End") {
              e.preventDefault();
              showStage(true);
              segStage.focus();
            }
          });
        });
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
      // browsing. A bare detection never touches this panel (or Preview/Live). loadChapter's
      // default (stage=true, omitted here) is exactly right for this caller.
      window.__openChapterForStage = function (reference) {
        if (reference) loadChapter(reference, null);
      };
      // Sana's security review (PR #61) caught that __openChapterForStage is NOT read-only:
      // loadChapter's non-range branch arms setCursor's 120ms stageTimer -> stage_scripture, and
      // its range branch invokes stage_scripture immediately, synchronously, with no timer to
      // cancel at all. CON-134's Edit and CON-138's History re-stage were built on the WRONG
      // assumption that opening a chapter has no side effect — both were silently staging
      // content to Preview. This is the genuinely read-only entry point for both: loadChapter's
      // explicit stage=false suppresses BOTH staging paths, so browsing a reference here can
      // never move anything onto Preview or Live without a further, explicit operator action
      // (the same manual stage/double-click-to-live gestures the Scriptures browser always
      // offers, per its own footnote).
      window.__openChapterToBrowse = function (reference) {
        if (reference) loadChapter(reference, null, false);
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
        // Sana's security review (PR #61): a non-staging call (stage=false — CON-134's Edit,
        // CON-138's History re-stage) must cancel any timer a PRIOR staging call left pending.
        // Without this, real race: Stage a verse (arms the 120ms timer), then WITHIN that window
        // click Edit on a different detection or re-stage from History — the old timer was never
        // cancelled and fires anyway, staging content neither read-only action asked for.
        // Sana's follow-up review (PR #64, finding B): this alone is narrowed, not closed — it
        // only runs once setCursor itself is reached, and loadChapter's own get_chapter fetch
        // (async, 300ms+ is realistic) sits BEFORE this call, so a timer already pending when the
        // read-only flow started could still fire mid-fetch. loadChapter now clears it too,
        // before that fetch starts (see its own comment) — this line is the complementary half,
        // for a staging call that races in while a read-only fetch is already in flight.
        if (!stage) clearTimeout(stageTimer);
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
      // `stage` defaults to true (omitted at every pre-existing call site, all of which rely on
      // the load-and-stage-as-you-browse behaviour the Scriptures panel's own footnote
      // describes) — pass stage=false explicitly for a genuinely read-only load
      // (window.__openChapterToBrowse; see its own comment for why this distinction exists).
      async function loadChapter(reference, cursorVerseNum, stage) {
        if (stage === undefined) stage = true;
        // Sana's security review (PR #64, finding B): clearing the pending stage timer only
        // inside setCursor closed most of the race but left a real window open — get_chapter
        // below is an async host round trip (300ms+ is realistic), and a PRE-EXISTING pending
        // timer (armed by an earlier Stage, before this read-only load even started) can still
        // fire DURING that fetch, before setCursor(idx, false) ever runs to cancel it. Clearing
        // it here too, before the fetch starts, closes that window instead of merely narrowing
        // it. setCursor's own clearTimeout(stageTimer) remains for the complementary case: a
        // stray staging call racing in WHILE this read-only fetch is still in flight.
        if (!stage) clearTimeout(stageTimer);
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
            // The whole passage stages; the cursor lands without re-staging. Gated on `stage` —
            // this call has no timer to cancel (unlike the non-range branch below), so the
            // guard has to sit here, not at the call site.
            setCursor(Math.max(0, idx), false);
            if (stage) {
              act(() =>
                invoke("stage_scripture", {
                  reference:
                    ch.reference + ":" + ch.verse_start + "-" + ch.verse_end,
                  translation: currentTranslation,
                })
              );
            }
          } else {
            setCursor(Math.max(0, idx), stage);
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
        // A destructive-confirm alertdialog is modal: suppress surface navigation (⌘1–7) and
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
        // While the presentation-search modal is open, Esc closes it and other global keys are
        // suppressed (its own input drives arrows/Enter). The emergency CHORDS above still pierce.
        if (window.__gsearch && window.__gsearch.isOpen()) {
          disarm();
          if (e.key === "Escape") {
            e.preventDefault();
            window.__gsearch.close();
          }
          return;
        }
        // Presentation search: ⌘/Ctrl+S opens the global search modal from anywhere (overriding the
        // browser save-page). Suppressed above while a confirm/palette/search modal is already open.
        if (mod && !e.shiftKey && !e.altKey && (e.key === "s" || e.key === "S")) {
          e.preventDefault();
          disarm();
          closeAppMenu();
          if (window.__gsearch) window.__gsearch.open();
          return;
        }
        // Global ⌘/Ctrl+1–8 jump to the eight navigable sections in menu order — makes the menu's
        // ⌘N badges and the Shortcuts reference REAL. Works whether the menu is open or not.
        // (86akcffvt added Transcripts as the 8th entry — raised from 7.)
        if (mod && !e.shiftKey && !e.altKey && e.key >= "1" && e.key <= "8") {
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
        // (Presentation now carries ⌘2 as a normal menu-order digit — no separate ⌘⇧P chord.)
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
        // ⌘/Ctrl+⇧+K jumps to Pre-service Check (moved into the Settings sidebar — the surface
        // itself stays, so the shortcut still opens it directly).
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
        // Delete / Backspace removes the SELECTED element in the element editors (Theme Designer /
        // Presentation) — regardless of which sub-control holds focus, as long as the operator is
        // not typing in a field. Runs BEFORE the console-only guard below (these surfaces aren't the
        // console). stopPropagation so the surfaces' own Delete handlers don't ALSO fire (a bubble
        // re-run would double-delete on the Presentation canvas).
        if (e.key === "Delete" || e.key === "Backspace") {
          const t = e.target || {};
          const typing = t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA" || t.isContentEditable;
          if (!typing) {
            const onTD = document.getElementById("surface-theme-designer").classList.contains("active");
            const onPM = document.getElementById("surface-presentation").classList.contains("active");
            if (onTD && typeof tdActiveIsEl === "function" && tdActiveIsEl()) {
              e.preventDefault(); e.stopPropagation(); disarm();
              tdDeleteElNow();
              return;
            }
            const pmSel = (typeof pmDv !== "undefined" && pmDv && pmDv.slide) ? pmDv.slide.selected_element : null;
            if (onPM && pmSel != null && typeof pmDeleteElement === "function") {
              e.preventDefault(); e.stopPropagation(); disarm();
              pmDeleteElement(pmSel);
              return;
            }
          }
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
        // Bridge to the Providers & Privacy "Generate" flow (settings.js), which owns no
        // transcript store of its own and reads this global rather than a second channel
        // (86akby7d8 defect 1: nothing ever set this before, so every Generate click sent ""
        // and billed for a fully fabricated draft). FINALISED segments only — never `partial`,
        // which by definition is not yet part of the "completed transcript" FR-132 promises is
        // all that's ever sent. `all` is already the host-tailed bounded list
        // (OPERATOR_TRANSCRIPT_TAIL), so this stays bounded exactly like the rendered log does:
        // it is the recent tail, not a persisted full-service transcript — no such store exists
        // on the frontend yet (that's FR-130's post-service workspace, not built here).
        //
        // Maps `segs` (the same MAX_TRANSCRIPT_ROWS-capped list #transcript-log renders from),
        // not the unsliced `all` (L-3, Vera): nothing bites today — the 240-segment core log
        // bounds `all` upstream and the 400k clamp bounds the request downstream — but bridging
        // from the same capped list keeps this bound symmetric with the DOM cap that exists for
        // exactly the case (a misbehaving/older/newer host skipping its own tail) that cap is for.
        window.scCompletedTranscript = segs
          .map((s) => (s && typeof s.text === "string") ? s.text : "")
          .join("\n");
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
          row.className = "tr-seg";
          row.dataset.segId = String(s.id);
          const t = document.createElement("span");
          t.className = "tr-seg-time";
          t.textContent = fmtClock(Math.floor((s.start_ms || 0) / 1000));
          const txt = document.createElement("span");
          txt.className = "tr-seg-text";
          txt.textContent = s.text; // untrusted → textContent, never innerHTML
          row.appendChild(t);
          row.appendChild(txt);
          log.appendChild(row);
        }
        log.scrollTop = log.scrollHeight; // keep the newest line in view
      }

      // Compact "spoken Ns ago" formatter for a detection's provenance line.
      function fmtAgo(secs) {
        if (secs < 60) return secs + "s";
        if (secs < 3600) return Math.floor(secs / 60) + "m";
        return Math.floor(secs / 3600) + "h";
      }

      // NOT fmtClock (defined earlier at ~line 3194, m:ss FROM A SECONDS COUNT — the run-sheet
      // duration formatter). This is wall-clock TIME OF DAY from a ms epoch, for a History row's
      // timestamp — a real name collision here (two functions named fmtClock, the later one
      // silently winning) previously broke every duration render in the Service Plan panel.
      function fmtHistoryTime(ms) {
        const d = new Date(ms);
        const h12 = ((d.getHours() + 11) % 12) + 1;
        const m = d.getMinutes();
        return h12 + ":" + (m < 10 ? "0" : "") + m;
      }

      // Quinn's QA review (PR #61, bug 17tnw2axre8): a WHOLE-CHAPTER detection (e.g. a spoken
      // "Isaiah 61", no verse) never lit the on-air card, because the host narrows it before it
      // ever goes live. controller.rs's stage_reference_for_detection (ApproveDetection handler)
      // appends ":1" to a bare "Book Chapter" reference — "a reference that already names a
      // verse (or doesn't parse) is returned unchanged" (its own doc comment) — so
      // view.live_scripture after Approve reads "Isaiah 61:1" while the DETECTION's own
      // reference (d.reference, from view.detections) is still the raw "Isaiah 61" the operator
      // approved. A bare `===` compare can therefore never match for this real, common input
      // shape. This encodes exactly that one documented transformation — not a general fuzzy
      // match — so it stays exact everywhere the host doesn't narrow anything.
      function detectionWentLiveAs(reference, liveScripture) {
        return liveScripture === reference || liveScripture === reference + ":1";
      }

      // --- CON-136/CON-137/CON-138 — client-side state layered onto the host-authoritative
      // view.detections, the same pattern detHealth/sttState already use elsewhere in this
      // file. NONE of this changes what Stage/Approve/Dismiss DO (CON-120's Approve semantics
      // are untouched) — it only decides how a detection the host already sent renders, and
      // remembers what the operator already did with a reference. Every collection here is
      // bounded (repo convention: no unbounded queues/caches).
      //
      // CON-137 REDESIGN (Sana's security review, PR #61): the original build here was an
      // AUTOMATIC client-side "you already saw this" cooldown — a de-emphasised card, a
      // countdown, "Show anyway" — triggered whenever the SAME reference reappeared shortly
      // after being Staged/Approved/Dismissed. The PR's own justification for building it
      // ("no dedup signal exists anywhere in the wire protocol") was WRONG: the host already
      // dedupes at the source. selahcue-core::TranscriptEngine keeps a bounded ring
      // (RECENT_DEDUP_WINDOW = 16, detection.rs) of recently-enqueued reference STRINGS and
      // silently drops a re-detection of one still in that ring — BEFORE it is ever enqueued,
      // so it never reaches view.detections at all. For the exact scenario this UI was built
      // for (a preacher re-quoting a verse shortly after first saying it), the host has almost
      // always already suppressed the second detection by the time it would have reached this
      // client — the automatic client-side cooldown was therefore near-unreachable in normal
      // production use, reachable mainly via a harness that bypasses the host or a busy service
      // that cycles 16+ other distinct references through the ring in between. Shipping it
      // added real bug surface (the mute-loop below) for a case the host already owns, so the
      // automatic half of CON-137 is REMOVED here, not just relabelled.
      //
      // What stays, because it is NOT redundant with the host: "Mute this verse" is
      // OPERATOR-DIRECTED, not automatic — an explicit "never show me this reference again this
      // service" the host has no concept of (its ring is a blind, short, automatic eviction
      // window with no operator control and no persistence). That is real, distinct value, so
      // it now lives directly on every normal detection card instead of being gated behind the
      // removed auto-duplicate state.
      const DET_HISTORY_MAX = 50;    // bounded session audit trail
      const DET_MUTED_MAX = 200;     // defence-in-depth cap against a pathological reference set
      let onAirDetection = null;        // {reference, translation, text, approvedAtMs} | null
      let detectionsHistory = [];       // bounded session trail: {id, reference, translation, outcome, resolvedAtMs}
      const mutedRefs = new Set();        // references the operator asked never to see again this service
      // Sana's security review (PR #61): a muted reference used to re-fire dismiss_detection on
      // EVERY render that reached it, for as long as the host's view kept reporting the same id
      // — no cap, no record, and a symptom the operator could see ("No scriptures detected yet"
      // with the tab's count pill still reading "1 new"). Each id is dismissed at most once.
      // Bounded by SIZE (evict oldest), not by "is this id still in the current queue" — an
      // earlier version pruned an id the instant it briefly disappeared from view.detections
      // (which happens almost immediately: right after its own dismiss succeeds), which defeated
      // the guard for the exact case it exists for — the host reporting the same id again for a
      // poll or two while it catches up. Remembering it slightly longer than strictly necessary
      // is harmless (still bounded); forgetting it too early re-opens the repeat-dismiss bug.
      const DET_MUTED_DISMISS_SENT_MAX = 200;
      const mutedDismissSent = new Set(); // detection ids already sent a mute-driven dismiss
      function rememberMutedDismiss(id) {
        if (mutedDismissSent.size >= DET_MUTED_DISMISS_SENT_MAX) {
          mutedDismissSent.delete(mutedDismissSent.values().next().value); // bounded — evict oldest
        }
        mutedDismissSent.add(id);
      }
      let detHistoryKey = "";
      let lastDetView = null; // most recent view syncDetOnAir saw, for the "Next verse" local dismiss

      // Recorded at CLICK time (optimistic, matching how every other action in this panel
      // already behaves — nothing here waits for a second host round trip to confirm). Feeds
      // the History log (CON-138).
      function recordDetectionOutcome(d, outcome) {
        detectionsHistory.push({
          id: d.id,
          reference: d.reference,
          translation: d.translation || "",
          outcome, // "staged" | "dismissed" | "muted" — "auto" is unreachable today (FR-115 disables auto modes)
          resolvedAtMs: Date.now(),
        });
        if (detectionsHistory.length > DET_HISTORY_MAX) {
          detectionsHistory.splice(0, detectionsHistory.length - DET_HISTORY_MAX);
        }
        renderDetectionHistory();
      }

      function renderDetectionHistory() {
        const list = document.getElementById("detections-history-list");
        const empty = document.getElementById("detections-history-empty");
        if (!list || !empty) return;
        const key = JSON.stringify(detectionsHistory.map((h) => [h.id, h.outcome, h.resolvedAtMs]));
        if (key === detHistoryKey) return;
        detHistoryKey = key;
        list.innerHTML = "";
        empty.style.display = detectionsHistory.length ? "none" : "";
        const rows = detectionsHistory.slice().reverse(); // newest first
        for (const h of rows) {
          const row = document.createElement("div");
          row.className = "det-history-row";
          row.setAttribute("role", "listitem");

          const body = document.createElement("div");
          body.className = "det-history-body";
          const ref = document.createElement("div");
          ref.className = "det-history-ref";
          ref.textContent = h.reference;
          body.appendChild(ref);
          const badge = document.createElement("span");
          badge.className = "det-history-badge " + h.outcome;
          badge.textContent =
            h.outcome === "staged" ? "STAGED" :
            h.outcome === "auto" ? "AUTO" :
            h.outcome === "muted" ? "MUTED" : "DISMISSED";
          body.appendChild(badge);
          row.appendChild(body);

          const time = document.createElement("span");
          time.className = "det-history-time";
          time.textContent = fmtHistoryTime(h.resolvedAtMs);
          row.appendChild(time);

          // Sana's review (PR #61): a mute had no reverse gear short of restarting the app and
          // losing every other bit of session state with it. This IS the un-mute control —
          // reusing the History record that already names the exact reference and when it was
          // muted, rather than a separate "manage muted references" surface. Only offered while
          // the reference is STILL muted (mutedRefs is the live source of truth; History rows
          // are a permanent log, so this checks current state at render time, not the outcome).
          if (h.outcome === "muted" && mutedRefs.has(h.reference)) {
            const unmute = document.createElement("button");
            unmute.type = "button";
            unmute.className = "det-history-unmute";
            unmute.textContent = "Unmute";
            unmute.setAttribute("aria-label", "Unmute " + h.reference);
            unmute.onclick = () => {
              mutedRefs.delete(h.reference);
              detHistoryKey = ""; // force a re-render so the Unmute button clears immediately
              // Sana's security review (PR #64, finding D): without also invalidating
              // detectionsKey, a still-queued detection for this exact reference computes the
              // SAME key it had while muted (nothing in view.detections changed, only mutedRefs
              // did) — syncDetections's memoization short-circuits on that unchanged key and the
              // card never reappears until some unrelated change perturbs the key. Verified live
              // over repeated polls with an unchanged host view.
              detectionsKey = "";
              renderDetectionHistory();
            };
            row.appendChild(unmute);
          }

          const restage = document.createElement("button");
          restage.type = "button";
          restage.className = "det-history-restage";
          restage.setAttribute("aria-label", "Jump to " + h.reference + " in the Scriptures browser");
          restage.textContent = "↺";
          // A resolved detection's id is already gone from the host's pending queue —
          // re-invoking approve_detection on it would be refused, not replayed. "Re-stage"
          // instead reuses the real chapter LOOKUP Stage relies on, but through the read-only
          // entry point (window.__openChapterToBrowse, not …ForStage — Sana's review, PR #61):
          // it only opens the chapter and positions the cursor, it does NOT itself stage
          // anything. The operator still takes an explicit further action (stage/double-click)
          // to actually move it — never an automatic side effect of clicking ↺, and never a
          // fabricated replay of an event that already happened.
          restage.onclick = () => {
            const liveBtn = document.getElementById("det-view-live");
            if (liveBtn) liveBtn.click();
            const ctab = document.getElementById("ctab-scriptures");
            if (ctab && !ctab.classList.contains("active")) ctab.click();
            if (window.__openChapterToBrowse) window.__openChapterToBrowse(h.reference);
          };
          row.appendChild(restage);

          list.appendChild(row);
        }
      }

      // CON-138 — Live | History. Mirrors wireStageTab's tablist pattern exactly (Home/End +
      // arrow-key roving tabindex), a distinct class family per the CON-142 lesson (never share
      // a segmented-control class across features).
      (function wireDetectionsView() {
        const liveBtn = document.getElementById("det-view-live");
        const histBtn = document.getElementById("det-view-history");
        const liveView = document.getElementById("detections-live-view");
        const histView = document.getElementById("detections-history-view");
        if (!liveBtn || !histBtn || !liveView || !histView) return;
        const show = (onLive) => {
          liveBtn.classList.toggle("active", onLive);
          histBtn.classList.toggle("active", !onLive);
          liveBtn.setAttribute("aria-selected", onLive ? "true" : "false");
          histBtn.setAttribute("aria-selected", onLive ? "false" : "true");
          liveBtn.tabIndex = onLive ? 0 : -1;
          histBtn.tabIndex = onLive ? -1 : 0;
          liveView.hidden = !onLive;
          histView.hidden = onLive;
          if (!onLive) renderDetectionHistory();
        };
        liveBtn.onclick = () => show(true);
        histBtn.onclick = () => show(false);
        [liveBtn, histBtn].forEach((tab) => {
          tab.addEventListener("keydown", (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
              e.preventDefault();
              const toHistory = tab === liveBtn;
              show(!toHistory);
              (toHistory ? histBtn : liveBtn).focus();
            } else if (e.key === "Home") {
              e.preventDefault();
              show(true);
              liveBtn.focus();
            } else if (e.key === "End") {
              e.preventDefault();
              show(false);
              histBtn.focus();
            }
          });
        });
      })();

      // CON-136 — the on-air link. Runs on every poll (called from render(), not gated by
      // detectionsKey): it must clear the instant view.live_scripture stops matching, even when
      // view.detections itself is unchanged.
      function syncDetOnAir(view) {
        lastDetView = view;
        const box = document.getElementById("det-onair");
        if (!box) return;
        // Never a stale claim — the same field the manual double-click-to-live flow verifies
        // against (app.js, stage_scripture/go_live flow) is the truth here too.
        // detectionWentLiveAs, not a bare !==: a whole-chapter reference stays narrowed on every
        // later poll too (Quinn, bug 17tnw2axre8) — a plain !== would clear the card on the very
        // next poll after correctly showing it.
        if (onAirDetection && (view.blackout || !detectionWentLiveAs(onAirDetection.reference, view.live_scripture))) {
          onAirDetection = null;
        }
        box.hidden = !onAirDetection;
        if (!onAirDetection) return;
        document.getElementById("det-onair-ref").textContent = onAirDetection.reference;
        const tr = document.getElementById("det-onair-translation");
        if (tr) {
          tr.textContent = onAirDetection.translation;
          tr.style.display = onAirDetection.translation ? "" : "none";
        }
        const snip = document.getElementById("det-onair-snippet");
        if (snip) {
          snip.textContent = onAirDetection.text;
          snip.style.display = onAirDetection.text ? "" : "none";
        }
        const agoS = Math.max(0, Math.round((Date.now() - onAirDetection.approvedAtMs) / 1000));
        document.getElementById("det-onair-meta").textContent =
          "Live on main output · staged " + fmtAgo(agoS) + " ago";
      }
      (function wireDetOnAir() {
        const clearBtn = document.getElementById("det-onair-clear");
        const nextBtn = document.getElementById("det-onair-next");
        // Same command the emergency footer's Clear Output button already invokes — not a new
        // contract, and CON-136's own note: use the canonical #a3283a fill (see the CSS), never
        // the frame's white-on-#ff4d4d (3.27:1, A11Y-DEFECT).
        if (clearBtn) clearBtn.onclick = () => act(() => invoke("clear"));
        // "Next verse" is a LOCAL dismiss only — it never touches output. The operator is done
        // watching the link, not necessarily done with what's live (the auto-clear in
        // syncDetOnAir already handles the case where output genuinely moved on).
        if (nextBtn) {
          nextBtn.onclick = () => {
            onAirDetection = null;
            syncDetOnAir(lastDetView || {});
          };
        }
      })();

      // Test-only reset for the module-level state above (mutedRefs/detectionsHistory/
      // onAirDetection are intentionally session-persistent in production — that IS the
      // feature — but a headless test suite that reuses the same stock reference strings
      // ("John 3:16", etc.) across unrelated fixtures needs a clean slate between sections. No
      // production code path calls this; it exists only so scripts/operator_headless.py can
      // isolate test sections.
      window.__detResetForTest = function () {
        onAirDetection = null;
        mutedRefs.clear();
        mutedDismissSent.clear();
        detectionsHistory = [];
        detHistoryKey = "";
        detectionsKey = "";
      };

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
        // "N new" count pill in the card header (hidden when none) — counts the RAW host queue,
        // matching what the host itself considers unactioned (a muted item is still sitting in
        // that queue for the one render before its dismiss is sent).
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
        let rendered = 0;
        for (const d of dets) {
          // CON-137 — a MUTED reference is auto-dismissed the instant it re-detects: the
          // operator already said "not this one again". Never rendered at all. Dismissed and
          // RECORDED at most once per id (Sana, PR #61) — previously this fired on every render
          // that reached a still-queued muted id, with no audit trail of what happened.
          if (mutedRefs.has(d.reference)) {
            if (!mutedDismissSent.has(d.id)) {
              rememberMutedDismiss(d.id);
              // Vera's performance review (PR #64, P2): recording the id BEFORE the invoke
              // resolves means a FAILED dismiss (busy host, link blip, refusal) used to leave
              // the id permanently marked as "handled" with no retry — the exact visible
              // inconsistency Sana's original finding was about (empty panel, stale count
              // pill), now persistent instead of transient. On failure, un-remember the id so
              // the NEXT poll gets a genuine retry; the once-per-id guard still holds on the
              // success path, which is the only path that matters for the repeat-fire bug.
              //
              // Sana's security review (PR #64, finding C): recordDetectionOutcome used to fire
              // unconditionally, right here, BEFORE the invoke settled — so a refused dismiss
              // still wrote a MUTED row to the audit trail, claiming a resolution that never
              // actually reached the host. Worse, once the id is un-remembered on failure, the
              // NEXT poll's retry re-enters this branch and would write a SECOND row for the
              // same id. Moving the record into the success branch means the audit trail reports
              // what actually happened, exactly once, no matter how many attempts it took — this
              // one outcome genuinely depends on host confirmation, unlike "staged"/"dismissed"
              // elsewhere in this file, which record the operator's own local action.
              invoke("dismiss_detection", { detectionId: d.id })
                .then(() => { recordDetectionOutcome(d, "muted"); })
                .catch(() => {
                  mutedDismissSent.delete(d.id);
                  // Un-remembering the id alone is not enough: this whole function bails out at
                  // its own top (`if (key === detectionsKey) return;`) whenever the host's view
                  // is byte-identical to last time — which is exactly the "host hasn't caught up
                  // yet" case this retry exists for. Without also invalidating detectionsKey, the
                  // retry is inert: the next poll never even reaches this branch to re-check it.
                  // Forcing one extra re-evaluation on a failure is a rare, cheap cost — the
                  // memoization is a perf optimization, not a correctness guarantee.
                  detectionsKey = "";
                });
            }
            continue;
          }
          list.appendChild(buildDetectionCard(d, view));
          rendered++;
        }
        empty.style.display = rendered ? "none" : "";
      }

      function buildDetectionCard(d, view) {
        const row = document.createElement("div");
        row.className = "detection";
        row.setAttribute("role", "listitem");
        const hasConfidence = typeof d.confidence === "number";
        const pct = hasConfidence ? Math.max(0, Math.min(100, Math.round(d.confidence))) : null;
        // Sana's security review (PR #61, non-blocking): this used to read
        // `hasConfidence && pct < 90`, which FAILED OPEN — a detection with NO reported
        // confidence at all fell through to the CONFIDENT branch (the Approve fast-path to the
        // audience) purely because `hasConfidence && …` short-circuits false on a missing score.
        // An unscored match is at least as uncertain as a known-low one, so it takes the same
        // cautious branch (Edit, not Approve) — `!hasConfidence` alone is enough to route here;
        // the match-pill and the tint below still render nothing when confidence is genuinely
        // absent (honest-empty stays honest-empty — this only changes which ACTIONS are safe).
        const fuzzy = !hasConfidence || pct < 90;
        // CON-129 — card tint by confidence, the same token pair the match-pill already uses.
        if (hasConfidence) row.classList.add(fuzzy ? "det-fuzzy" : "det-confident");

        const head = document.createElement("div");
        head.className = "detection-head";
        const ref = document.createElement("span");
        ref.className = "ref";
        ref.textContent = d.reference;
        head.appendChild(ref);
        // Translation label — WHICH translation the snippet is in (card spec: reference ·
        // translation · match-%). Honest-empty when the host omits it.
        if (d.translation) {
          const tr = document.createElement("span");
          tr.className = "det-translation";
          tr.textContent = d.translation;
          head.appendChild(tr);
        }
        // Match-% pill — ONLY when the host supplied a real confidence (honest-empty
        // until R4 scoring lands); green when confident, amber tint when fuzzy.
        if (hasConfidence) {
          const m = document.createElement("span");
          m.className = "match-pill" + (fuzzy ? " fuzzy" : "");
          m.textContent = pct + "% MATCH";
          head.appendChild(m);
        }
        // CON-137 (redesigned, Sana's review PR #61) — operator-directed mute, on every card:
        // "never show me this reference again this service". Distinct from the host's own
        // automatic RECENT_DEDUP_WINDOW ring (selahcue-core::TranscriptEngine) — this is
        // explicit and operator-controlled, the host's is a blind short-lived eviction window;
        // the two are not redundant. Recorded to History (outcome "muted"), reversible from
        // there, and future re-detections of this reference are auto-dismissed exactly once
        // each (see the mutedDismissSent guard in syncDetections).
        const mute = document.createElement("button");
        mute.type = "button";
        mute.className = "det-mute-btn";
        const muteGlyph = document.createElement("span");
        muteGlyph.setAttribute("aria-hidden", "true"); // the button's own aria-label carries the name
        muteGlyph.textContent = "🔇";
        mute.appendChild(muteGlyph);
        mute.setAttribute("aria-label", "Mute " + d.reference + " for this service — undo from History");
        mute.onclick = () => {
          if (mutedRefs.size >= DET_MUTED_MAX) {
            mutedRefs.delete(mutedRefs.values().next().value); // bounded — evict oldest first
          }
          mutedRefs.add(d.reference);
          rememberMutedDismiss(d.id); // this id's dismiss attempt happens right here; the History
          // record now waits for confirmation (Sana's finding C, below) rather than firing here.
          detectionsKey = "";
          // Not act() here (Vera's review, PR #64, P2): act() swallows a rejection internally
          // (console.error only, never re-thrown), so there is no way to un-remember the id on
          // failure from outside it. A failed dismiss must restore the retry the once-per-id
          // guard would otherwise permanently deny it — same reasoning as the auto-dismiss path
          // in syncDetections above.
          //
          // recordDetectionOutcome moved out of the synchronous click handler and into .then()
          // (Sana's security review, PR #64, finding C): recording it optimistically, before the
          // host confirmed the dismiss, wrote a MUTED row to the audit trail even when the
          // refusal meant nothing actually changed on the host — and because a refused attempt
          // un-remembers the id for retry, the following poll's success would have written a
          // SECOND row for the same id. This is the one outcome that genuinely depends on host
          // confirmation (unlike "staged"/"dismissed" elsewhere in this file, which record the
          // operator's own local action and stay optimistic on purpose).
          invoke("dismiss_detection", { detectionId: d.id })
            .then((v) => {
              recordDetectionOutcome(d, "muted");
              lastRendered = "";
              render(v);
            })
            .catch((e) => {
              console.error(e);
              mutedDismissSent.delete(d.id);
              // Same reasoning as the auto-dismiss loop's catch: if a poll lands between this
              // click and this failure, syncDetections's own memoization may already have
              // re-stored detectionsKey to match the still-queued view, in which case clearing
              // only mutedDismissSent leaves the retry inert. Forcing it here too closes that race.
              detectionsKey = "";
            });
        };
        head.appendChild(mute);
        row.appendChild(head);

        // CON-130 — the confidence bar: the one non-textual, non-colour cue for match strength.
        // role="img" + an accessible name carries the same information a sighted operator reads
        // from the fill width, rather than a bare decorative div a screen reader would skip.
        if (hasConfidence) {
          const track = document.createElement("div");
          track.className = "det-bar-track";
          track.setAttribute("role", "img");
          track.setAttribute("aria-label", pct + "% match confidence");
          const fill = document.createElement("span");
          fill.className = "det-bar-fill" + (fuzzy ? " fuzzy" : "");
          fill.style.width = pct + "%";
          track.appendChild(fill);
          row.appendChild(track);
        }

        if (d.text) {
          const snip = document.createElement("div");
          snip.className = "snippet";
          snip.textContent = d.text; // untrusted verse text → textContent
          row.appendChild(snip);
        }

        // Provenance meta: the spoken phrase (source transcript segment) + "spoken Ns ago".
        const meta = document.createElement("div");
        meta.className = "det-meta";
        const seg =
          typeof d.source_segment === "number" && Array.isArray(view.transcript)
            ? view.transcript.find((s) => s.id === d.source_segment)
            : null;
        const metaParts = [];
        if (seg && seg.text) {
          const phrase = seg.text.length > 48 ? seg.text.slice(0, 48) + "…" : seg.text;
          metaParts.push("“" + phrase + "”");
        } else {
          metaParts.push("Live transcript");
        }
        if (seg && typeof seg.start_ms === "number") {
          const nowMs = view.transcript.reduce(
            (mx, s) => Math.max(mx, s.end_ms || s.start_ms || 0),
            0
          );
          const agoS = Math.max(0, Math.round((nowMs - seg.start_ms) / 1000));
          metaParts.push("spoken " + fmtAgo(agoS) + " ago");
        }
        meta.textContent = metaParts.join(" · "); // untrusted phrase → textContent, never innerHTML
        row.appendChild(meta);

        // CON-134 — a low-confidence match owes the operator an honest explanation for why
        // there's no ALTERNATIVES list, rather than one this build cannot honestly draw (no
        // alternate-candidate data exists anywhere in the detection wire protocol — see the CSS
        // comment on .det-alt-note).
        if (fuzzy) {
          const note = document.createElement("div");
          note.className = "det-alt-note";
          note.textContent = "No alternative matches available yet — use Edit to find the right verse.";
          row.appendChild(note);
        }

        const actions = document.createElement("div");
        actions.className = "detection-actions";
        // Operator-confirmed actions (FR-115 — a detection never displays on its own).
        // approve_detection dequeues + stages the verse in PREVIEW; only GoLive commits to the
        // audience. So: Stage = review in Preview first; Approve = stage AND go live in one; both
        // dequeue. Dismiss discards without staging.
        const mkAction = (label, cls, aria, run) => {
          const b = document.createElement("button");
          b.type = "button";
          if (cls) b.className = cls;
          b.textContent = label;
          b.setAttribute("aria-label", aria);
          b.onclick = run;
          return b;
        };
        const stage = mkAction("Stage", "det-stage", "Stage " + d.reference + " in Preview", () =>
          act(async () => {
            const v = await invoke("approve_detection", { detectionId: d.id }); // Preview only
            if (window.__openChapterForStage) window.__openChapterForStage(d.reference);
            recordDetectionOutcome(d, "staged");
            return v;
          })
        );
        actions.appendChild(stage);
        if (fuzzy) {
          // CON-134 — Edit replaces Approve for a low-confidence match: no one-click fast path to
          // the audience for a match the detector itself is unsure of (334:142 draws only
          // Stage/Edit/Dismiss). Non-destructive: it does not dequeue or dismiss, so the operator
          // can still Stage/Dismiss afterward if the reference turns out to be right after all.
          // Genuinely non-destructive, not just in name — window.__openChapterToBrowse (NOT
          // …ForStage) is the read-only entry point: Sana's security review (PR #61) proved that
          // …ForStage silently stages to Preview (immediately for a verse range, or after
          // setCursor's 120ms debounce otherwise), which this action must never do on its own.
          const edit = mkAction("Edit", "det-edit", "Look up " + d.reference + " to correct it", () => {
            const ctab = document.getElementById("ctab-scriptures");
            if (ctab && !ctab.classList.contains("active")) ctab.click();
            if (window.__openChapterToBrowse) window.__openChapterToBrowse(d.reference);
          });
          actions.appendChild(edit);
        } else {
          const approve = mkAction(
            "Approve",
            "det-approve",
            "Approve " + d.reference + " and show it live",
            () =>
              act(async () => {
                await invoke("approve_detection", { detectionId: d.id }); // stage in Preview
                const v = await invoke("go_live"); // confirmed → push to the audience output
                if (window.__openChapterForStage) window.__openChapterForStage(d.reference);
                recordDetectionOutcome(d, "staged");
                // CON-136 — only claim on-air once the host confirms THIS reference is what
                // actually went live (the same verification the manual double-click-to-live
                // flow already uses at the stage_scripture/go_live call site above).
                // detectionWentLiveAs, not a bare ===: a whole-chapter detection goes live under
                // its host-narrowed first verse (Quinn, bug 17tnw2axre8) — see that function's
                // own comment.
                if (v && detectionWentLiveAs(d.reference, v.live_scripture)) {
                  onAirDetection = {
                    reference: d.reference,
                    translation: d.translation || "",
                    text: d.text || "",
                    approvedAtMs: Date.now(),
                  };
                }
                return v;
              })
          );
          actions.appendChild(approve);
        }
        const dismiss = mkAction("Dismiss", "", "Dismiss " + d.reference, () =>
          act(() => {
            recordDetectionOutcome(d, "dismissed");
            return invoke("dismiss_detection", { detectionId: d.id });
          })
        );
        actions.appendChild(dismiss);
        row.appendChild(actions);

        return row;
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
          // Re-read detector liveness immediately rather than waiting up to a second for the
          // poll: toggling listening is exactly when the detections panel's state changes, and
          // "Listening — no scriptures yet" arriving a beat late reads as "detection is off".
          if (typeof readDetectionHealth === "function") readDetectionHealth();
        });
        apply();
      })();

      // === Offline download modal (Figma 396-124) — ONE dialog for every first-time offline
      // download, driven by the host's `stt://phase` events (downloading / verifying / ready /
      // failed{connect|offline|verify}). The same states serve the Whisper model and any Bible
      // translation (assetKind). Hide backgrounds the download to a pill; Cancel aborts it
      // (cancel_download) + stops the pending listen; Retry re-runs it. The scrim never covers the
      // emergency footer, so BLACKOUT / Clear stay reachable. ---
      (function wireDownloadModal() {
        const back = document.getElementById("dl-modal-back");
        const dialog = document.getElementById("dl-modal");
        if (!back || !dialog) return;
        const $ = (id) => document.getElementById(id);
        const ico = $("dl-modal-ico"), title = $("dl-modal-title"), sub = $("dl-modal-sub");
        const progwrap = $("dl-modal-progwrap"), progfill = $("dl-modal-progfill");
        const progbytes = $("dl-modal-progbytes"), progpct = $("dl-modal-progpct");
        const note = $("dl-modal-note"), live = $("dl-modal-live");
        const btnHide = $("dl-modal-hide"), btnSecondary = $("dl-modal-secondary"), btnPrimary = $("dl-modal-primary");
        const pill = $("dl-pill");

        // Asset descriptors — the SAME dialog serves the Whisper model + (later) a Bible translation.
        const MODEL = {
          title: "speech model",
          sub: "Whisper · English · on-device",
          note: "Runs once. SelahCue works fully offline after it finishes.",
          readyTitle: "Speech model ready",
          readySub: "Installed · verified",
          readyNote: "On-device transcription is ready. Listening will start now.",
          offlineNote: "Connect to the internet once to download the speech model. After that, transcription runs fully offline.",
          retry: () => { try { invoke("start_listening"); } catch (e) {} },
        };
        let asset = MODEL; // current descriptor (model now; a translation reuses this dialog)
        // State 7: the SAME dialog for a Bible translation. Built from the bible://phase payload
        // (name + catalog id); Retry re-invokes download_translation with that id.
        function translationAsset(p) {
          const t = (p && p.name) || "translation";
          const id = p && p.id;
          return {
            title: t,
            sub: "Bible translation · offline text",
            note: "Runs once per translation. Read and search it offline afterward.",
            readyTitle: t + " ready",
            readySub: "Installed · verified",
            readyNote: "This translation is ready to read and search offline.",
            offlineNote: "Connect to the internet once to download " + t + ". After that, it reads fully offline.",
            retry: id ? (() => { try { invoke("download_translation", { id: id }); } catch (e) {} }) : null,
          };
        }
        let state = "idle", active = false, backgrounded = false, lastPayload = null;
        let lastPct = 0, lastTotal = 0, lastDone = 0, lastAnnounced = -1;
        let readyTimer = null, prevFocus = null;

        function fmtBytes(n) {
          if (!n || n < 0) return "0 MB";
          const gb = n / 1e9;
          if (gb >= 1) return (Math.round(gb * 10) / 10 + "").replace(/\.0$/, "") + " GB";
          return Math.round(n / 1e6) + " MB";
        }
        function announce(msg) { if (live) live.textContent = msg; }
        function btn(el, show, label, disabled) {
          if (!show) { el.hidden = true; return; }
          el.hidden = false; if (label != null) el.textContent = label; el.disabled = !!disabled;
        }
        function focusMain() {
          setTimeout(() => {
            const t = !btnPrimary.hidden ? btnPrimary : (!btnSecondary.hidden ? btnSecondary : btnHide);
            if (t && !t.hidden) try { t.focus(); } catch (e) {}
          }, 0);
        }
        function openModal() {
          if (back.hidden) { prevFocus = document.activeElement; back.hidden = false; }
          pill.hidden = true; backgrounded = false;
        }
        function closeModal() {
          clearTimeout(readyTimer);
          back.hidden = true; pill.hidden = true; state = "idle"; active = false; backgrounded = false;
          if (prevFocus && prevFocus.focus) try { prevFocus.focus(); } catch (e) {}
        }
        function hideToBackground() {
          back.hidden = true; backgrounded = true; pill.hidden = false;
          pill.textContent = "Downloading… " + lastPct + "%";
          try { pill.focus(); } catch (e) {}
        }
        function renderDownloading() {
          state = "downloading";
          ico.textContent = "↓"; ico.className = "dl-modal-ico";
          title.textContent = "Downloading " + asset.title; sub.textContent = asset.sub;
          progwrap.hidden = false; progwrap.classList.remove("is-indeterminate");
          progfill.className = "dl-modal-progfill";
          progfill.style.width = lastPct + "%"; progfill.setAttribute("aria-valuenow", String(lastPct));
          progbytes.textContent = lastTotal ? (fmtBytes(lastDone) + " of " + fmtBytes(lastTotal)) : "Starting…";
          progpct.hidden = false; progpct.textContent = lastPct + "%";
          note.textContent = asset.note;
          btn(btnHide, true, "Hide"); btn(btnSecondary, true, "Cancel"); btn(btnPrimary, false);
          const step = Math.floor(lastPct / 10);
          if (step !== lastAnnounced) { lastAnnounced = step; announce("Downloading " + asset.title + ", " + lastPct + " percent"); }
        }
        function renderVerifying() {
          state = "verifying";
          ico.textContent = "↻"; ico.className = "dl-modal-ico";
          title.textContent = "Verifying " + asset.title; sub.textContent = "Checking integrity…";
          progwrap.hidden = false; progwrap.classList.add("is-indeterminate");
          progfill.className = "dl-modal-progfill"; progfill.removeAttribute("aria-valuenow");
          progbytes.textContent = "Making sure it's complete & untampered"; progpct.hidden = true;
          note.textContent = "This guards against a corrupted or tampered file. Takes a few seconds.";
          // No Hide during verify, and Esc is suppressed (can't safely abort a verify).
          btn(btnHide, false); btn(btnSecondary, true, "Cancel"); btn(btnPrimary, false);
          announce("Verifying " + asset.title);
        }
        function renderReady() {
          state = "ready";
          ico.textContent = "✓"; ico.className = "dl-modal-ico is-ready";
          title.textContent = asset.readyTitle; sub.textContent = asset.readySub;
          progwrap.hidden = false; progwrap.classList.remove("is-indeterminate");
          progfill.className = "dl-modal-progfill is-ready";
          progfill.style.width = "100%"; progfill.setAttribute("aria-valuenow", "100");
          progbytes.textContent = "Integrity verified"; progpct.hidden = true;
          note.textContent = asset.readyNote;
          btn(btnHide, false); btn(btnSecondary, false); btn(btnPrimary, true, "Start listening");
          announce(asset.readyTitle);
          clearTimeout(readyTimer); readyTimer = setTimeout(() => { if (state === "ready") closeModal(); }, 1500);
          focusMain();
        }
        function renderFailed(reason) {
          if (reason === "verify") {
            state = "couldnt-verify";
            ico.textContent = "!"; ico.className = "dl-modal-ico is-integrity";
            title.textContent = "Download couldn’t be verified"; sub.textContent = "Discarded for your safety";
            progwrap.hidden = true;
            note.textContent = "The file didn’t match its security checksum, so SelahCue deleted it and installed nothing. This is usually a bad connection — try again.";
          } else if (reason === "offline") {
            state = "offline";
            ico.textContent = "⚠"; ico.className = "dl-modal-ico is-warn";
            title.textContent = "You’re offline"; sub.textContent = "Connection needed one time";
            progwrap.hidden = true; note.textContent = asset.offlineNote;
          } else { // connect / other
            state = "couldnt-connect";
            ico.textContent = "!"; ico.className = "dl-modal-ico is-warn";
            title.textContent = "Download interrupted"; sub.textContent = lastPct ? ("Paused at " + lastPct + "%") : "Paused";
            progwrap.hidden = false; progwrap.classList.remove("is-indeterminate");
            progfill.className = "dl-modal-progfill is-warn"; progfill.style.width = lastPct + "%";
            progbytes.textContent = "Waiting to reconnect…"; progpct.hidden = true;
            note.textContent = "Couldn’t reach the download server. Check your connection — try again.";
          }
          const secondary = reason === "offline" ? "Not now" : "Cancel";
          const primary = reason === "offline" ? "Try again" : "Retry";
          btn(btnHide, false); btn(btnSecondary, true, secondary); btn(btnPrimary, true, primary);
          announce(title.textContent + ". " + sub.textContent);
          focusMain();
        }
        function reRender() {
          if (state === "downloading") renderDownloading();
          else if (state === "verifying") renderVerifying();
          else if (state === "ready") renderReady();
          else if (lastPayload && lastPayload.phase === "failed") renderFailed(lastPayload.reason);
        }
        // Drive the dialog from a host phase event. Exposed on window for the headless harness.
        function onPhase(p) {
          if (!p || !p.phase) return;
          lastPayload = p;
          if (p.phase === "downloading") {
            if (typeof p.pct === "number") lastPct = p.pct;
            if (p.total) lastTotal = p.total;
            if (typeof p.done === "number") lastDone = p.done;
            active = true;
          } else if (p.phase === "verifying") {
            active = true;
          } else if (p.phase === "ready" && !active) {
            return; // a warm cache hit emits a lone `ready` — never pop a modal just to say so
          }
          if (backgrounded && (p.phase === "downloading" || p.phase === "verifying")) {
            pill.textContent = p.phase === "verifying" ? "Verifying…" : ("Downloading… " + lastPct + "%");
            return; // stay backgrounded while it progresses; ready/failed re-surfaces below
          }
          backgrounded = false;
          if (p.phase === "downloading") { openModal(); renderDownloading(); }
          else if (p.phase === "verifying") { openModal(); renderVerifying(); }
          else if (p.phase === "ready") { openModal(); renderReady(); active = false; }
          else if (p.phase === "failed") {
            if (p.message === "cancelled") { closeModal(); return; } // user cancel — just close
            openModal(); renderFailed(p.reason); active = false;
          }
        }

        btnHide.addEventListener("click", hideToBackground);
        pill.addEventListener("click", () => { pill.hidden = true; openModal(); reRender(); focusMain(); });
        btnSecondary.addEventListener("click", () => {
          // Cancel / Not now — abort the in-flight download + stop the pending listen, then close.
          try { invoke("cancel_download"); } catch (e) {}
          try { invoke("stop_listening"); } catch (e) {}
          closeModal();
        });
        btnPrimary.addEventListener("click", () => {
          if (state === "ready") { closeModal(); return; } // Start listening — already underway
          // Retry / Try again — re-run the download+listen flow; incoming phases re-render the dialog.
          if (asset.retry) asset.retry();
        });
        // Focus trap + Esc=Cancel (never during Verifying — can't safely abort a verify).
        dialog.addEventListener("keydown", (ev) => {
          if (ev.key === "Escape") {
            if (state !== "verifying" && !btnSecondary.hidden) { ev.preventDefault(); btnSecondary.click(); }
            return;
          }
          if (ev.key !== "Tab") return;
          const f = Array.prototype.filter.call(dialog.querySelectorAll("button"), (b) => !b.hidden && !b.disabled);
          if (!f.length) return;
          const first = f[0], last = f[f.length - 1];
          if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
          else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
        });

        // The SAME dialog serves the speech model (stt://phase) and any Bible translation
        // (bible://phase, whose payload carries the translation name + catalog id). Each wrapper
        // sets the asset descriptor, then runs the shared state machine.
        function onModelPhase(p) { asset = MODEL; onPhase(p || {}); }
        function onBiblePhase(p) { asset = translationAsset(p || {}); onPhase(p || {}); }
        if (window.__TAURI__ && window.__TAURI__.event && window.__TAURI__.event.listen) {
          window.__TAURI__.event.listen("stt://phase", (e) => onModelPhase((e && e.payload) || {}));
          window.__TAURI__.event.listen("bible://phase", (e) => onBiblePhase((e && e.payload) || {}));
        }
        // Test/refresh hook for the headless behavioural harness.
        window.__dlModal = { onPhase: onModelPhase, onBiblePhase: onBiblePhase, close: closeModal, hide: hideToBackground, state: () => state };
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

        // Commands are grouped by `section`; render() lays them out under ACTIONS / NAVIGATE /
        // SCRIPTURES headers (Design 2.0 command-palette). Same host commands as before — just
        // sectioned, badged, and with the whole top-level app menu mirrored under NAVIGATE.
        const commands = (rawQ) => {
          const q = (rawQ || "").trim();
          const cmds = [];
          // ACTIONS — transport + emergency, keyboard-first parity.
          cmds.push({ section: "ACTIONS", label: "Go Live", ico: "▶", sub: "⏎", run: () => act(() => invoke("go_live")) });
          cmds.push({ section: "ACTIONS", label: "Blackout output", ico: "■", sub: "B", run: () => toggleBlackout() });
          cmds.push({ section: "ACTIONS", label: "Clear all layers", ico: "✕", sub: "Esc Esc", run: () => clearAll() });
          cmds.push({ section: "ACTIONS", label: "Start service timer", ico: "⏱", run: () => act(() => invoke("start_timer", { seconds: 300 })) });
          cmds.push({ section: "ACTIONS", label: "Next item", ico: "»", sub: "Space", run: () => act(() => invoke("next")) });
          cmds.push({ section: "ACTIONS", label: "Previous item", ico: "«", sub: "←", run: () => act(() => invoke("previous")) });
          // Presentation-surface actions are offered only while that surface is active (they act
          // on the authored deck) — keyboard-first parity for the slide editor (FR-021/022).
          const pmActive = document.getElementById("surface-presentation");
          if (pmActive && pmActive.classList.contains("active") && typeof pmMode !== "undefined") {
            if (pmMode === "grid") {
              // Grid mode owns presenting — present the cursor slide (double-click / Enter equivalent).
              cmds.push({ section: "ACTIONS", label: "Present slide", ico: "▶", run: () => { if (typeof pmGridGoLive === "function") pmGridGoLive(pmGridCursor); } });
            } else if (pmMode === "editor") {
              cmds.push({ section: "ACTIONS", label: "Add slide", ico: "+", run: () => { if (typeof pmAddSlide === "function") pmAddSlide(); } });
              cmds.push({ section: "ACTIONS", label: "Present slide", ico: "▶", run: () => { if (typeof pmPresent === "function") pmPresent(); } });
              cmds.push({ section: "ACTIONS", label: "Undo slide edit", ico: "↶", sub: "⌘Z", run: () => { if (typeof pmUndo === "function") pmUndo(); } });
              cmds.push({ section: "ACTIONS", label: "Redo slide edit", ico: "↷", sub: "⌘⇧Z", run: () => { if (typeof pmRedo === "function") pmRedo(); } });
            }
          }
          cmds.push({ section: "ACTIONS", label: "Keyboard shortcuts", ico: "⌨", run: () => openShortcuts() });
          // NAVIGATE — the whole top-level app menu, mirrored with each item's real icon + ⌘ badge
          // (read from the menu DOM, so it stays in sync with the ⌘1–⌘7 order automatically).
          navItems.forEach((it) => {
            if (!it.dataset.surface || it.getAttribute("aria-disabled") === "true") return;
            const t = it.querySelector(".nav-t");
            // Collapse internal whitespace — some nav labels wrap across lines in the markup
            // (e.g. "Screens &\n Outputs"), which textContent would otherwise carry into the label.
            const name = (t ? t.textContent : it.textContent).replace(/\s+/g, " ").trim();
            const icoEl = it.querySelector(".nav-ico");
            const keyEl = it.querySelector(".nav-key");
            cmds.push({
              section: "NAVIGATE",
              label: "Go to " + name,
              ico: icoEl ? icoEl.textContent : "→",
              sub: keyEl ? keyEl.textContent : "",
              run: () => navGo(it),
            });
          });
          // Pre-service Check left the top nav (now in the Settings sidebar) — keep it reachable
          // from the palette, and surface its ⌘⇧K shortcut.
          cmds.push({ section: "NAVIGATE", label: "Go to Pre-service Check", ico: "✓", sub: "⌘⇧K", run: () => showSurface("preservice") });
          // SCRIPTURES — a live Bible lookup for the typed query, reusing the console's scripture_search.
          if (q) {
            cmds.push({
              section: "SCRIPTURES",
              label: 'Search "' + q + '" in Bible',
              ico: "✦",
              run: () => {
                showSurface("console");
                if (typeof window.__selectContentTab === "function") window.__selectContentTab("scriptures", true);
                const sq = document.getElementById("scripture-q");
                if (sq) { sq.value = q; sq.dispatchEvent(new Event("input")); sq.focus(); }
              },
            });
          }
          return cmds;
        };
        const SECTION_ORDER = ["ACTIONS", "NAVIGATE", "SCRIPTURES"];

        let filtered = [];
        let active = 0;
        // Point the combobox at the active option so a screen reader announces it
        // (aria-activedescendant is declared on #cmd-input; each option carries an id).
        const syncActiveDescendant = () => {
          if (filtered.length) input.setAttribute("aria-activedescendant", "cmd-opt-" + active);
          else input.removeAttribute("aria-activedescendant");
        };
        const paint = () => {
          // Only the .cmd-item rows are selectable — the .cmd-group headers are skipped, so the
          // active index maps 1:1 onto `filtered`.
          listEl.querySelectorAll(".cmd-item").forEach((li, i) => {
            const on = i === active;
            li.classList.toggle("active", on);
            li.setAttribute("aria-selected", on ? "true" : "false");
            if (on && li.scrollIntoView) li.scrollIntoView({ block: "nearest" });
          });
          syncActiveDescendant();
        };
        const render = () => {
          const raw = input.value.trim();
          const q = raw.toLowerCase();
          const matched = commands(raw).filter((c) => !q || c.label.toLowerCase().includes(q));
          if (active >= matched.length) active = Math.max(0, matched.length - 1);
          // `filtered` (arrow-nav + runAt index into it) is rebuilt in RENDER order = section order,
          // so an inserted section header never shifts the selection map.
          filtered = [];
          listEl.innerHTML = "";
          SECTION_ORDER.forEach((sec) => {
            const items = matched.filter((c) => (c.section || "ACTIONS") === sec);
            if (!items.length) return;
            const head = document.createElement("li");
            head.className = "cmd-group";
            head.setAttribute("role", "presentation");
            head.setAttribute("aria-hidden", "true");
            head.textContent = sec;
            listEl.appendChild(head);
            items.forEach((c) => {
              const i = filtered.length;
              filtered.push(c);
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

      // --- Global presentation search (⌘/Ctrl+S): a dedicated modal that searches deck NAMES +
      // slide TEXT across the operator-local library (host `deck_search`), and opens the chosen
      // presentation in the editor. Mirrors the command-palette modal a11y (dialog / listbox /
      // ↑↓ / Enter / Esc; roving active option). Exposed as window.__gsearch for the global keymap. ---
      (function wireGlobalSearch() {
        const modal = document.getElementById("gsearch");
        const input = document.getElementById("gsearch-input");
        const listEl = document.getElementById("gsearch-list");
        const emptyEl = document.getElementById("gsearch-empty");
        if (!modal || !input || !listEl) return;

        let results = [];
        let active = 0;
        let seq = 0; // request sequence — drop stale async responses (a slow query can't clobber a newer one)
        let debounceTimer = null;
        let opener = null;

        const syncActiveDescendant = () => {
          if (results.length) input.setAttribute("aria-activedescendant", "gs-opt-" + active);
          else input.removeAttribute("aria-activedescendant");
        };
        const paint = () => {
          listEl.querySelectorAll(".gsearch-item").forEach((li, i) => {
            const on = i === active;
            li.classList.toggle("active", on);
            li.setAttribute("aria-selected", on ? "true" : "false");
            if (on && li.scrollIntoView) li.scrollIntoView({ block: "nearest" });
          });
          syncActiveDescendant();
        };
        const render = () => {
          listEl.innerHTML = "";
          results.forEach((r, i) => {
            const li = document.createElement("li");
            li.className = "cmd-item gsearch-item" + (i === active ? " active" : "");
            li.id = "gs-opt-" + i;
            li.setAttribute("role", "option");
            li.setAttribute("aria-selected", i === active ? "true" : "false");
            const ico = document.createElement("span");
            ico.className = "cmd-item-ico"; ico.setAttribute("aria-hidden", "true");
            ico.textContent = "▦";
            const text = document.createElement("span");
            text.className = "gsearch-text";
            const name = document.createElement("span");
            name.className = "gsearch-name";
            name.textContent = r.name; // untrusted deck name → textContent
            text.appendChild(name);
            let aria = r.name;
            if (r.kind === "content" && r.snippet) {
              const where = typeof r.slide_index === "number" ? "slide " + (r.slide_index + 1) + " · " : "";
              const sub = document.createElement("span");
              sub.className = "gsearch-sub";
              sub.textContent = where + "“" + r.snippet + "”"; // untrusted slide text → textContent
              text.appendChild(sub);
              aria = r.name + " — " + where + r.snippet;
            }
            li.setAttribute("aria-label", aria);
            li.appendChild(ico);
            li.appendChild(text);
            li.addEventListener("mousemove", () => { if (active !== i) { active = i; paint(); } });
            li.addEventListener("click", () => openAt(i));
            listEl.appendChild(li);
          });
          if (emptyEl) {
            const q = input.value.trim();
            if (results.length > 0) {
              emptyEl.hidden = true;
            } else {
              emptyEl.hidden = false;
              emptyEl.textContent = q
                ? "No presentations match “" + q + "”"
                : "Type to search your presentations";
            }
          }
          syncActiveDescendant();
        };
        const search = () => {
          const q = input.value.trim();
          const mine = ++seq;
          if (!q) { results = []; active = 0; render(); return; }
          Promise.resolve(invoke("deck_search", { query: q }))
            .then((res) => {
              if (mine !== seq) return; // superseded by a newer query
              results = res && Array.isArray(res.hits) ? res.hits : [];
              active = 0;
              render();
            })
            .catch(() => { if (mine === seq) { results = []; render(); } });
        };
        const openAt = (i) => {
          const r = results[i];
          if (!r) return;
          close();
          showSurface("presentation");
          // Reuse the existing open-into-editor flow (deck_open → grid render).
          if (typeof pmLibOpen === "function") pmLibOpen(r.deck_id);
          else invoke("deck_open", { id: r.deck_id });
        };

        function open() {
          opener = document.activeElement;
          closeAppMenu();
          modal.hidden = false;
          input.value = ""; results = []; active = 0; render();
          input.focus();
        }
        function close() {
          modal.hidden = true;
          if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; } // no host round-trip after close
          // Restore focus to the opener; fall back to the app-menu button when the opener is gone
          // or not focusable (e.g. a position:fixed control like the download pill, whose
          // offsetParent is null) — mirrors the command palette's restoreFocus so keyboard focus
          // is never dropped to <body>.
          const o = opener; opener = null;
          if (o && o.focus && document.contains(o) && o.offsetParent !== null) { o.focus(); }
          else { const mb = document.getElementById("app-menu-btn"); if (mb) mb.focus(); }
        }
        const isOpen = () => !modal.hidden;

        input.addEventListener("input", () => {
          if (debounceTimer) clearTimeout(debounceTimer);
          debounceTimer = setTimeout(search, 120); // debounce the host round-trip
        });
        input.addEventListener("keydown", (e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(results.length - 1, active + 1); paint(); }
          else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(0, active - 1); paint(); }
          else if (e.key === "Enter") { e.preventDefault(); openAt(active); }
          else if (e.key === "Escape") { e.preventDefault(); close(); }
          else if (e.key === "Tab") { e.preventDefault(); } // trap focus (aria-modal: #gsearch-input is the only tabbable node)
        });
        modal.addEventListener("click", (e) => { if (e.target === modal) close(); });

        window.__gsearch = { open, close, isOpen };
      })();

      // ===================================================================================
      // SYSTEM & RECOVERY STATES (Design 2.0 Frame G, node 346:124)
      // Contract: docs/delivery/HOST-SIGNAL-WEBVIEW-CONTRACT.md
      //
      // THE ONE RULE: there are always THREE cases, never two — the host reports a problem,
      // the host reports it is fine, or the host DOES NOT REPORT. The third is *unknown*. It
      // is not a fault (that is the `else -> NO SIGNAL` bug this replaces) and it is not
      // healthy (a subsystem nobody is asking about is not confirmed fine). Every branch
      // below is written so that absent data produces neither of the other two answers.
      //
      // TWO ENCODINGS OF ABSENT, and they differ BY NESTING LEVEL on the Tauri path:
      //   - `view.output_health` / `.storage` / `.session` are top-level fields of
      //     OperatorView, which carries no skip_serializing_if, so absent is JSON `null`
      //     with the key PRESENT.
      //   - the fields INSIDE those objects are the selahcue-lan protocol structs, whose
      //     skip_serializing_if applies on the Tauri path too, so `holds`/`recoveries` are a
      //     genuinely MISSING KEY at zero and a healthy session serialises as `{}`.
      // Hence: never `"key" in obj`, never a truthiness test on a counter, and read every
      // optional number through numOr0(). (The headless fixture omits these keys entirely,
      // giving `undefined` where real Tauri gives `null` — both must behave identically.)
      //
      // MEMORY: this whole feature retains four scalars and one short string, below. No
      // queue, no history, no timer handles — the transient confirmation is cleared by a
      // later poll comparing timestamps, not by an accumulating set of setTimeouts.
      // ===================================================================================

      // Previous-poll counters for EDGE detection. `null` means "no previous observation",
      // which is distinct from 0 and must not itself read as an edge.
      let prevHolds = null;
      let prevRecoveries = null;
      // The transient "recovered" confirmation: one message + one timestamp.
      let recoveredMsg = "";
      let recoveredAt = 0;
      // How many times a recovery edge has been ANNOUNCED this session. Exposed below for the
      // headless gate, alongside the existing __detHealthRefresh hook.
      let rcvAnnounced = 0;
      // The session notice is informational, so the operator can dismiss it for the service.
      let sessionDismissed = false;
      // Real link state once link_status is available; null until then.
      let linkState = null;
      // Whether a host link exists at all (false = stand-alone/demo backend, where there is
      // no link and none is wanted — reporting that as "Connected" was fabrication #3).
      let hostRemote = null;

      const RECOVERED_MS = 8000;

      // Optional host numbers are absent-or-number. `x || 0` would also swallow a real 0 but,
      // worse, `x.toFixed()` on an omitted key throws — so normalise once, here.
      function numOr0(x) { return (typeof x === "number" && isFinite(x)) ? x : 0; }

      function rcvEl(id) { return document.getElementById(id); }

      // A human name for an output that NEVER invents one. The frame says "HDMI-2"; no seam
      // carries a display identity, so we use what the host actually reports and fall back to
      // the role, never to a made-up connector name.
      function outputName(o) {
        if (o && typeof o.display === "string" && o.display) return o.display;
        const role = o && typeof o.role === "string" ? o.role : "";
        if (role === "main") return "Main output";
        if (role === "stage") return "Stage output";
        return role ? role.charAt(0).toUpperCase() + role.slice(1) + " output" : "Output";
      }

      // G.5 — session recovery. A notice, not a dialog: the host has already restored (or
      // already started clean) before this renders, and no command exists to change that.
      function syncSessionNotice(view) {
        const card = rcvEl("rcv-session");
        if (!card) return false;
        const s = view && view.session;
        // `null`/absent = this host does not report session health at all -> unknown -> say
        // nothing. `{}` = it reports and there is nothing wrong. Both are silent, for
        // different reasons, and neither is an error.
        if (sessionDismissed || !s || typeof s !== "object") { card.hidden = true; return false; }
        const loop = s.crash_loop === true;
        const restored = s.restored === true;
        const err = (typeof s.autosave_error === "string" && s.autosave_error) ? s.autosave_error : "";
        const st = view && view.storage;
        const paused = !!(st && typeof st === "object" && st.checkpoints_paused === true);
        if (!loop && !restored && !err && !paused) { card.hidden = true; return false; }

        let title, text;
        if (loop) {
          // The breaker tripped. "Started clean" reads as data loss unless we say the session
          // is preserved — protocol.rs:803-807 is explicit that it is skipped, never deleted.
          const n = numOr0(s.rapid_launches);
          title = "Started clean after repeated restarts";
          text = (n > 1 ? "SelahCue restarted " + n + " times in quick succession, so this launch did not resume automatically. "
            : "SelahCue restarted repeatedly, so this launch did not resume automatically. ")
            + "Your previous session is preserved — relaunch once this run is stable to resume it.";
        } else if (restored) {
          // NOT the frame's "SelahCue closed unexpectedly". `restored` is documented as
          // "crash OR restart", and a clean exit also saves a session, so a normal
          // quit-and-relaunch sets it too. Asserting a crash here would be false most times.
          title = "Session restored";
          text = "Your plan, themes, slides and edits were restored from the last autosave.";
        } else {
          title = "Your recent work may not be saved";
          text = "The host is not writing checkpoints right now. Live output is unaffected — only saving has stopped.";
        }
        rcvEl("rcv-session-title").textContent = title;
        rcvEl("rcv-session-text").textContent = text;

        const chip = rcvEl("rcv-session-chip");
        if (err) {
          // The host's OWN reason, not a generic "something went wrong". Already truncated to
          // 200 bytes host-side by truncate_for_wire, so this cannot grow unbounded.
          chip.textContent = "Last autosave failed: " + err;
          chip.hidden = false;
        } else if (paused) {
          chip.textContent = "Checkpoints are paused — recent changes are not being saved.";
          chip.hidden = false;
        } else {
          chip.textContent = "";
          chip.hidden = true;
        }
        card.hidden = false;
        return true;
      }

      // The link state the UI should render. Prefers the real producer; falls back to what is
      // knowable without it, and NEVER invents "reconnecting" — nothing re-dials.
      function currentLinkState() {
        if (linkState) return linkState;
        if (hostRemote === false) return "local";
        if (hostRemote === null) return null;      // not yet known -> unknown, render nothing
        return lastConn === false ? "disconnected" : "connected";
      }

      // G.2 — control-link loss, scoped to the operator<->host link. The frame's "Mobile
      // remotes are paused" is deliberately NOT built: no seam reports LAN controller peers.
      function syncLinkState() {
        const card = rcvEl("rcv-link");
        if (!card) return false;
        const st = currentLinkState();
        // "local" is a real, healthy answer meaning there is no link and none is wanted.
        // "connected" is healthy. null is unknown. None of the three is a banner.
        if (st !== "disconnected" && st !== "reconnecting") { card.hidden = true; return false; }
        const retry = rcvEl("rcv-link-retry");
        if (st === "reconnecting") {
          // Reachable only once a producer guarantees an attempt really is scheduled. The
          // contract makes that a biconditional, so if we ever read it, it is true.
          retry.lastElementChild.textContent = "Reconnecting…";
        } else {
          retry.lastElementChild.textContent = "No automatic reconnect — restart the console to reconnect.";
        }
        card.hidden = false;
        return true;
      }

      // G.3 — per-output signal loss AND the never-blank hold. These are two DIFFERENT host
      // signals and are deliberately not conflated:
      //   view.outputs[].signal  — real per-output telemetry that moves today (a detached
      //                            monitor reports "no_signal"); carries a display identity.
      //   view.output_health     — GPU/decoder/disk faults against the LIVE output; carries no
      //                            display identity, and means "holding last good frame".
      function syncOutputState(view) {
        const card = rcvEl("rcv-output");
        if (!card) return false;
        const outs = (view && Array.isArray(view.outputs)) ? view.outputs : [];
        let bad = null;
        for (let i = 0; i < outs.length; i++) {
          const o = outs[i];
          if (!o || o.assigned !== true) continue;   // nothing assigned is not a fault
          // Only a REPORTED bad signal counts. An absent `signal` is unknown and is skipped —
          // this is the exact fallthrough that used to render unknown telemetry as NO SIGNAL.
          if (o.signal === "no_signal" || o.signal === "degraded") { bad = o; break; }
        }
        const oh = view && view.output_health;
        const held = !!(oh && typeof oh === "object" && oh.held === true);
        if (!bad && !held) { card.hidden = true; return false; }

        const pill = rcvEl("rcv-output-pill");
        const label = rcvEl("rcv-output-pill-label");
        const nameEl = rcvEl("rcv-output-name");
        pill.classList.remove("unknown", "degraded");
        let text;
        if (bad && bad.signal === "no_signal") {
          nameEl.textContent = outputName(bad);
          label.textContent = "SIGNAL LOST";
          text = outputName(bad) + " reports no display signal.";
        } else if (bad) {
          nameEl.textContent = outputName(bad);
          pill.classList.add("degraded");
          label.textContent = "DEGRADED";
          const dropped = numOr0(bad.dropped_frames);
          text = outputName(bad) + " is dropping frames"
            + (dropped > 0 ? " (" + dropped + " dropped)." : ".");
        } else {
          // Held with no per-output fault: the live output is holding, but the host does not
          // attribute it to a display. Name the live output generically rather than guessing.
          nameEl.textContent = "Live output";
          label.textContent = "OUTPUT HELD";
          text = "The live output is holding its last good frame.";
        }
        // "Other outputs are unaffected" is ASSERTED FROM DATA, never as boilerplate: only
        // when there really are other assigned outputs and all of them report healthy.
        if (bad) {
          let others = 0, ok = 0;
          for (let i = 0; i < outs.length; i++) {
            const o = outs[i];
            if (!o || o === bad || o.assigned !== true) continue;
            others++;
            if (o.signal === "healthy") ok++;
          }
          if (others > 0 && others === ok) text += " Other outputs are unaffected.";
        }
        rcvEl("rcv-output-text").textContent = text;
        // The held line appears ONLY while the host reports a hold, and is worded as the
        // guarantee working — "output held (audience unaffected)" is accurate, "output
        // failed" is not. `fault` is never cached across a recovery, so nothing stale shows.
        rcvEl("rcv-output-held").hidden = !held;
        // A reattach promise only makes sense for a display that went away.
        rcvEl("rcv-output-reattach").hidden = !(bad && bad.signal === "no_signal");
        card.hidden = false;
        return true;
      }

      // G.3 — the recovery confirmation. THE reason holds/recoveries exist as counters.
      //
      // The console polls at 1 Hz and there is NO health event channel, so a hold that begins
      // and ends between two polls leaves `held` false in BOTH samples and would be invisible
      // forever. Reading these as LEVELS is the documented way to get this wrong: `recoveries
      // > 0` means recoveries have happened at some point, NOT that one is happening now.
      // Only the DELTA against the previous poll is an event.
      function syncRecovered(view) {
        const card = rcvEl("rcv-recovered");
        if (!card) return false;
        const oh = view && view.output_health;
        if (!oh || typeof oh !== "object") {
          // Unknown -> drop the baseline. Keeping it would make the next known sample look
          // like a delta against a world we can no longer vouch for.
          prevHolds = null;
          prevRecoveries = null;
          card.hidden = true;
          return false;
        }
        const holds = numOr0(oh.holds);
        const recs = numOr0(oh.recoveries);
        if (prevHolds === null) {
          // First observation establishes a baseline only. Treating it as a delta would
          // announce a "recovery" for every counter the host happened to be carrying already.
          prevHolds = holds;
          prevRecoveries = recs;
        } else {
          // A DECREASE needs no branch of its own, and must not have one. Both counters are
          // monotonic and saturating host-side, so a decrease means a new host or a new
          // session — and the delta test below already refuses it, because a negative delta is
          // not a positive one. An explicit decrease branch would produce the identical result
          // by a second route, and two mechanisms guarding one behaviour cannot BOTH be pinned
          // by a test: removing either leaves the other, so the suite goes green on a real
          // regression. (Found by mutation: disabling either one alone changed nothing.)
          // Re-baselining is unconditional at the end of this branch, which is what a new
          // host needs anyway.
          const gained = recs - prevRecoveries;
          if (gained > 0) {
            recoveredMsg = gained > 1
              ? "Live output recovered " + gained + " times — it held its last frame each time and has resumed."
              : "Live output recovered — it held its last frame and has resumed.";
            recoveredAt = Date.now();
            // A monotonic count of ANNOUNCEMENTS (not of recoveries). The confirmation is a
            // transient whose visible window outlives the moment it fired, so "is the card on
            // screen?" cannot distinguish "a new edge fired" from "the last one is still
            // showing". Tests assert the edge itself against this. One integer, never reset.
            rcvAnnounced++;
          }
          prevHolds = holds;
          prevRecoveries = recs;
        }
        // Still showing? Cleared by a later poll, not by a timer — no setTimeout to leak and
        // nothing to cancel if the host goes away mid-window.
        const showing = !!recoveredMsg && (Date.now() - recoveredAt) < RECOVERED_MS;
        if (!showing) { card.hidden = true; return false; }
        rcvEl("rcv-recovered-text").textContent = recoveredMsg;
        card.hidden = false;
        return true;
      }

      // The region is visible exactly when at least one state is. Derived from the cards' own
      // visibility rather than from a return value, so the several callers that update only ONE
      // card (the link surfaces, the dismiss handler) cannot strand the region open or closed.
      function rcvRegionSync() {
        const region = rcvEl("recovery");
        if (!region) return;
        const ids = ["rcv-session", "rcv-link", "rcv-output", "rcv-recovered"];
        let any = false;
        for (let i = 0; i < ids.length; i++) {
          const e = rcvEl(ids[i]);
          if (e && !e.hidden) { any = true; break; }
        }
        region.hidden = !any;
      }

      // Test seam (mirrors window.__detHealthRefresh): the headless gate asserts recovery
      // EDGES, and an edge is an event, not a visible state.
      window.__rcvAnnounced = function () { return rcvAnnounced; };

      function syncRecovery(view) {
        if (!rcvEl("recovery")) return;
        // Evaluate all four unconditionally (no short-circuit): each owns its own card's
        // visibility, and skipping one would strand a card visible after its cause cleared.
        syncSessionNotice(view);
        syncLinkState();
        syncOutputState(view);
        syncRecovered(view);
        rcvRegionSync();
      }

      (function wireSessionDismiss() {
        const x = document.getElementById("rcv-session-x");
        if (!x) return;
        x.onclick = () => {
          sessionDismissed = true;
          const card = rcvEl("rcv-session");
          if (card) card.hidden = true;
          rcvRegionSync();
        };
      })();

      // Host connection pill: green "Connected" while the view poll succeeds; amber
      // "Reconnecting…" when a poll throws (a remote host dropped). Local mode never fails.
      // Only touch the DOM when the state actually FLIPS — the 1s poll must not rewrite the
      // pill every second (no needless class/text/attr churn on the hot path).
      let lastConn = null;
      let lastPillKey = "";

      const setConn = (ok) => { lastConn = ok; paintConnPill(); };

      // The pill, rewritten against the real link state. It previously carried three separate
      // fabrications, all removed here:
      //   1. a permanent green "Connected" in the stand-alone build, because that backend's
      //      view() cannot fail — green for the absence of a failure path, not for a host;
      //   2. "Reconnecting…" while nothing whatsoever was retrying;
      //   3. no way at all to say "I do not know yet".
      function paintConnPill() {
        const pill = document.getElementById("conn-pill");
        const label = document.getElementById("conn-label");
        if (!pill) return;
        const st = currentLinkState();
        let cls, text, aria;
        if (st === "local") {
          // Plainly stated, per the contract. Not a degraded connection — no link is wanted.
          cls = "local"; text = "Local"; aria = "Stand-alone — no host link, and none needed";
        } else if (st === "connected") {
          cls = ""; text = "Connected"; aria = "Host connected";
        } else if (st === "reconnecting") {
          // Honest here and ONLY here. Unreachable until a producer schedules real attempts.
          cls = "reconnecting"; text = "Reconnecting…"; aria = "Reconnecting to host";
        } else if (st === "disconnected") {
          // Down, and nothing is happening. The label must not imply otherwise, and no retry
          // control is offered because this shell has none to honour.
          cls = "down"; text = "Host unreachable"; aria = "Host unreachable — restart the console to reconnect";
        } else {
          cls = "unknown"; text = "Checking…"; aria = "Checking the host link";
        }
        const key = cls + "|" + text;
        // The 1 Hz poll must not rewrite the pill every second — only on a real flip.
        if (key === lastPillKey) return;
        lastPillKey = key;
        pill.classList.remove("reconnecting", "local", "down", "unknown");
        if (cls) pill.classList.add(cls);
        if (label) label.textContent = text;
        pill.setAttribute("aria-label", aria);
      }

      // Tier 2 producer. Absence of the command is UNKNOWN, never a fault: an older shell simply
      // leaves linkState null and currentLinkState() falls back to what is knowable.
      async function readLinkStatus() {
        try {
          const r = await invoke("link_status");
          linkState = (r && typeof r.state === "string") ? r.state : null;
        } catch (e) {
          linkState = null;
        }
        refreshLinkSurfaces();
      }

      // THE PROPERTY THAT MATTERS: the pill and the link banner must stay truthful with NO
      // operator interaction. They cannot ride render(), because render() is only reached when
      // the view poll SUCCEEDS — exactly the case where the link is fine. When the link drops,
      // render() stops being called at all, so anything that depended on it would freeze
      // showing "Connected" forever. Hence both failure and success paths call this.
      function refreshLinkSurfaces() {
        paintConnPill();
        syncLinkState();
        rcvRegionSync();
      }
      // Does a host link exist at all? `false` means the stand-alone/demo backend, where there
      // is no link and none is wanted — which is a healthy answer, not a disconnection. Left
      // `null` (unknown) if the call fails, so a failure here can never manufacture a banner.
      (async () => {
        try { hostRemote = (await invoke("host_connected")) === true; }
        catch (e) { hostRemote = null; }
      })();
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
          const polled = await invoke("view");
          render(polled);
          planSyncPublishFromPoll(polled);
          planSyncViewerFromPoll(polled);
          setConn(true);
        } catch (e) {
          // The link (or a render) just failed, so render() did NOT run and syncRecovery() was
          // never reached. Refresh the link surfaces directly — otherwise the one state that
          // exists to report a dropped link would be unreachable precisely when it is true.
          setConn(false);
          refreshLinkSurfaces();
        }
        readDetectionHealth();
        readLinkStatus();
      }, 1000);
      readDetectionHealth();
      readLinkStatus();

      // ===================================================================================
      // Detector liveness (CON-128 / CON-139) — docs/delivery/HOST-SIGNAL-WEBVIEW-CONTRACT.md
      //
      // The owner's acceptance bar for this whole batch: "a dead scripture detector and a silent
      // room must not render identically". Only `state` answers that. SILENCE IS EVIDENCE OF
      // NEITHER, so nothing below infers detector health from the absence of transcript text —
      // inferring it that way is exactly what made the two indistinguishable.
      //
      // Tri-state, and the third case is the one that gets fixed wrong: a host that does not
      // report health at all is UNKNOWN, never a fault and never "healthy". Both wrong readings
      // collapse three states into two.
      // ===================================================================================
      let detHealth = null;       // the last successfully-read reply
      let detHealthKnown = false; // false = the host has not told us; NOT "it is fine"
      // The host's refusal of the operator's LAST retry attempt. Held separately because the 1 Hz
      // poll re-renders this card every second: writing the refusal straight into the DOM would
      // erase it before it could be read. Cleared as soon as the detector actually recovers.
      let detRetryError = null;
      async function readDetectionHealth() {
        try {
          const h = await invoke("detection_health");
          // Guard the shape rather than trusting it: a reply without a state string is not a
          // healthy detector, it is an unreadable one.
          detHealth = h && typeof h.state === "string" ? h : null;
          detHealthKnown = !!detHealth;
        } catch (e) {
          // An older host has no such command. That is unknown, not broken.
          detHealth = null;
          detHealthKnown = false;
        }
        renderDetectionHealth();
      }
      function renderDetectionHealth() {
        const box = document.getElementById("det-health");
        if (!box) return;
        const ico = document.getElementById("det-health-ico");
        const title = document.getElementById("det-health-title");
        const body = document.getElementById("det-health-body");
        const retry = document.getElementById("det-health-retry");
        const emptyMsg = document.getElementById("det-empty-msg");
        const emptySub = document.getElementById("det-empty-sub");
        const engineNote = document.getElementById("det-engine-note");
        const st = detHealthKnown && detHealth ? detHealth.state : null; // null = unknown
        // 86akby7th PR #22 review (Vera, Medium): checked on EVERY render, independent of `st`
        // and of whether #detections-empty is showing — an engine-change or audio-dropped
        // disclosure must be visible mid-sermon, not only in the (now overlapping) empty state
        // below, which JS hides the instant a detection row exists.
        if (engineNote) {
          const noteText = detHealthKnown && detHealth && detHealth.note ? String(detHealth.note) : "";
          engineNote.textContent = noteText;
          engineNote.hidden = !noteText;
        }
        // A recovered detector clears a stale refusal — the message described a world that no
        // longer exists (contract: do not show a stale fault after recovery).
        if (st === "listening" || st === "idle") detRetryError = null;
        box.className = "det-health";
        if (st === "unavailable") {
          box.hidden = false;
          ico.textContent = "⚠";
          title.textContent = "Detection unavailable";
          // The host's OWN retained failure. Only fall back to generic copy when it gave none —
          // never overwrite a specific reason with a reassuring one.
          // Precedence: what the operator just tried and was refused, then the host's retained
          // failure, and only then generic copy. Never overwrite a specific reason with a
          // reassuring one.
          body.textContent =
            detRetryError ||
            (detHealth.error
              ? String(detHealth.error)
              : "The on-device detector isn’t responding. Slides, search and staging are unaffected — you can still find and stage scriptures manually.");
          // Offer retry ONLY where it can work. In "unsupported" the host cannot even construct
          // the permission token, so a button there would be one that cannot possibly fire.
          retry.hidden = !detHealth.can_retry;
        } else if (st === "unsupported") {
          box.hidden = false;
          box.className = "det-health det-health-quiet";
          ico.textContent = "○";
          title.textContent = "Detection not built in";
          body.textContent = "This build has no on-device speech-to-text. Scripture search and staging work normally.";
          retry.hidden = true;
        } else if (st === null) {
          box.hidden = false;
          box.className = "det-health det-health-quiet";
          ico.textContent = "—";
          title.textContent = "Detector status unknown";
          body.textContent = "This host doesn’t report detector health. Detections still appear here if it finds any.";
          retry.hidden = true;
        } else {
          box.hidden = true;
          retry.hidden = true;
        }
        // The empty state must say WHICH kind of nothing this is. "Listening, nothing yet" and
        // "not listening" used to render as the same sentence, which is the bar this misses.
        if (emptyMsg && emptySub) {
          if (st === "listening") {
            emptyMsg.textContent = "Listening — no scriptures detected yet.";
            emptySub.textContent =
              "Detections appear the moment a reference or quote is recognised" +
              (detHealth.provider ? " (" + detHealth.provider + ")" : "") +
              ". Nothing stages or goes live on its own — it stays operator-confirmed (FR-115).";
              // 86akby7th: the engine-change / audio-dropped disclosure now renders in the
              // always-visible #det-engine-note above, not appended here — appending it here
              // ALSO meant it vanished the moment a detection row appeared (Vera, PR #22
              // review, Medium), since this whole element is hidden then.
          } else if (st === "idle") {
            emptyMsg.textContent = "Detection is not running.";
            emptySub.textContent =
              "Press Start listening to capture the sermon audio; spoken scriptures then surface here to stage in one tap.";
          } else {
            emptyMsg.textContent = "No scriptures detected yet.";
            emptySub.textContent =
              "Scriptures spoken aloud surface here to stage in one tap. Automatic detection (R4) never stages or goes live on its own — it stays operator-confirmed (FR-115).";
          }
        }
      }
      // The same kind of cross-module hook the transcript and right-tab counters already use
      // (window.__sttNoteTranscript, window.__rightTabsOnDetections): lets anything that changes
      // detector state ask this panel to re-read it now instead of waiting for the next poll.
      window.__detHealthRefresh = readDetectionHealth;
      (function wireDetectionRetry() {
        const b = document.getElementById("det-health-retry");
        if (!b) return;
        b.onclick = async () => {
          b.disabled = true;
          try {
            const h = await invoke("retry_detection");
            detHealth = h && typeof h.state === "string" ? h : null;
            detHealthKnown = !!detHealth;
            detRetryError = null; // the attempt was accepted; any earlier refusal is history
          } catch (e) {
            // The host refuses with its own operator-facing reason. Stored, not written straight
            // to the DOM, so the next poll's re-render cannot erase it a second later.
            detRetryError = String(e && e.message ? e.message : e);
          } finally {
            b.disabled = false;
            renderDetectionHealth();
          }
        };
      })();

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

      // Import an image into the media library (FR-138 / 86ak0qmzv). NOT routed through `pAct`:
      // a validation refusal is a final, specific reason (e.g. "that file is too large to
      // import"), not a transient failure worth a generic "Couldn't import the image — please
      // retry" — same reasoning as `pmLibRestore`'s own `pmShowErrorRaw` use above.
      async function pmImportImage() {
        pmSetBusy(true);
        try {
          pmDv = await invoke("deck_import_image");
          pmClearError();
          renderPresentation(pmDv);
        } catch (e) {
          console.error("[SelahCue] deck action failed", e);
          pmShowErrorRaw(String(e && e.message ? e.message : e));
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
      // Show the host's OWN refusal text. pmShowError composes a generic "Couldn't X — please
      // retry", which is wrong for a refusal that is final and has a specific reason.
      function pmShowErrorRaw(message) {
        const banner = pmEl("pm-error");
        const msg = pmEl("pm-error-msg");
        if (!banner || !msg) return;
        banner.hidden = false;
        msg.textContent = message || "That didn’t work.";
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
      // A focus-trapped name prompt. Three optional hooks were added for the plan-lifecycle
      // dialogs (86ak8467m) so those reuse THIS dialog rather than growing a second one:
      //
      //   opts.describe  — a sentence under the title, wired into the dialog's accessible
      //                    description, for a dialog whose consequence is not obvious from
      //                    its title alone.
      //   opts.body(el)  — extra content ABOVE the name field (a template list, a run-sheet
      //                    textarea). The caller keeps its own state in its own closure.
      //   opts.validate(v) — returns the REASON v is unacceptable, or null when it is fine.
      //                    A rejected value is shown inline and never submitted.
      //
      // Every existing caller passes none of them and is unaffected. The Tab trap now walks the
      // dialog's live focusables instead of a hard-coded triple, because opts.body may add some.
      function pmPrompt(opts) {
        if (document.querySelector(".pm-confirm-back")) return;
        const prevFocus = document.activeElement;
        const back = document.createElement("div"); back.className = "pm-confirm-back";
        const dlg = document.createElement("div"); dlg.className = "pm-confirm"; dlg.setAttribute("role", "dialog"); dlg.setAttribute("aria-modal", "true");
        dlg.setAttribute("aria-labelledby", "pm-prompt-title");
        const h = document.createElement("h2"); h.className = "pm-confirm-title"; h.id = "pm-prompt-title"; h.textContent = opts.title || "Name"; dlg.appendChild(h);
        let describedBy = "";
        if (opts.describe) {
          const d = document.createElement("p"); d.className = "pm-confirm-body"; d.id = "pm-prompt-describe"; d.textContent = opts.describe;
          dlg.appendChild(d);
          describedBy = "pm-prompt-describe";
        }
        // The consequence line, mirroring pmConfirm's. It MUST be in the accessible description
        // and not merely drawn: a warning a screen reader never speaks is a warning that did not
        // happen (WCAG 4.1.2), which is the same rule pmConfirm's `warning` already follows.
        if (opts.warning) {
          const w = document.createElement("p"); w.className = "pm-confirm-warn"; w.id = "pm-prompt-warn"; w.textContent = opts.warning;
          dlg.appendChild(w);
          describedBy = describedBy ? describedBy + " pm-prompt-warn" : "pm-prompt-warn";
        }
        if (describedBy) dlg.setAttribute("aria-describedby", describedBy);
        const field = document.createElement("div"); field.style.display = "flex"; field.style.flexDirection = "column"; field.style.gap = "6px";
        const lab = document.createElement("label"); lab.className = "pm-insp-lbl"; lab.textContent = opts.label || "Name"; lab.htmlFor = "pm-prompt-input";
        const input = document.createElement("input"); input.type = "text"; input.id = "pm-prompt-input"; input.className = "pm-insp-ctrl"; input.value = opts.value || ""; input.style.width = "100%"; input.style.maxWidth = "none"; input.setAttribute("aria-label", opts.label || "Name");
        // The field is built FIRST and handed to opts.body, so a caller that needs it (the
        // template picker, whose radios follow the name) takes it directly rather than reaching
        // back into the document by id after pmPrompt returns — which would have grabbed the
        // WRONG input on the one path where this function early-returns (a dialog already open).
        if (opts.body) { const extra = document.createElement("div"); extra.className = "pm-prompt-extra"; opts.body(extra, input); dlg.appendChild(extra); }
        // role=alert, not a silent red line: a refusal the operator cannot hear is a dialog that
        // appears to do nothing when they press Enter (WCAG 3.3.1).
        const err = document.createElement("p"); err.className = "pm-prompt-err"; err.id = "pm-prompt-error"; err.setAttribute("role", "alert"); err.hidden = true;
        field.appendChild(lab); field.appendChild(input); field.appendChild(err); dlg.appendChild(field);
        const row = document.createElement("div"); row.className = "pm-confirm-actions";
        const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "pm-btn-ghost"; cancel.textContent = "Cancel";
        const ok = document.createElement("button"); ok.type = "button"; ok.className = "pm-btn-primary"; ok.textContent = opts.confirmLabel || "OK";
        row.appendChild(cancel); row.appendChild(ok); dlg.appendChild(row);
        back.appendChild(dlg); document.body.appendChild(back);
        const close = () => { document.removeEventListener("keydown", onKey, true); back.remove(); if (prevFocus && prevFocus.focus) prevFocus.focus(); };
        // The field a refusal BLAMES has to be the field that is wrong. `validate` may return a
        // plain string (the name is at fault) or `{ message, field }` naming another control —
        // the import dialog's run-sheet textarea, whose problems were previously reported under
        // the Service name, marking a perfectly good name aria-invalid and pulling focus off the
        // textarea the operator had to fix (WCAG 3.3.1/3.3.2).
        let invalidField = null;
        const clearInvalid = () => {
          if (!invalidField) return;
          invalidField.removeAttribute("aria-invalid");
          invalidField.removeAttribute("aria-describedby");
          invalidField = null;
        };
        const submit = () => {
          const v = input.value;
          if (opts.validate) {
            const why = opts.validate(v);
            const message = why && typeof why === "object" ? why.message : why;
            if (message) {
              const target = (why && typeof why === "object" && why.field) || input;
              err.textContent = message; err.hidden = false;
              clearInvalid();
              invalidField = target;
              target.setAttribute("aria-invalid", "true");
              target.setAttribute("aria-describedby", "pm-prompt-error");
              target.focus();
              return; // the dialog STAYS OPEN with the typed value intact
            }
            err.hidden = true; err.textContent = "";
            clearInvalid();
          }
          close(); if (opts.onConfirm) opts.onConfirm(v);
        };
        cancel.onclick = close; ok.onclick = submit;
        // A stray click on the backdrop closes a NAME prompt harmlessly. It must not throw away
        // a dialog the operator has typed into at length — a 60-line run sheet pasted into the
        // import dialog is gone with no undo and no confirmation.
        back.onmousedown = (ev) => { if (ev.target === back && !opts.body) close(); };
        const focusables = () => Array.prototype.slice.call(
          dlg.querySelectorAll("input, textarea, select, button, [href], [tabindex]:not([tabindex='-1'])")
        ).filter((e) => !e.disabled && !e.hidden && e.getClientRects().length > 0);
        const onKey = (ev) => {
          if (ev.key === "Escape") { ev.preventDefault(); close(); }
          else if (ev.key === "Enter" && document.activeElement === input) { ev.preventDefault(); submit(); }
          else if (ev.key === "Tab") { const els = focusables(); if (!els.length) return; const i = els.indexOf(document.activeElement); ev.preventDefault(); const n = ev.shiftKey ? (i <= 0 ? els.length - 1 : i - 1) : (i >= els.length - 1 ? 0 : i + 1); els[n].focus(); }
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
          // A response without a real decks ARRAY is UNKNOWN, not "loaded and empty". `|| []`
          // here defeated the catch branch below: a host that answers deck_list with null (an
          // older host, or one where the command is not implemented) read as an empty library,
          // so EVERY deck-linked item was flagged "⚠ presentation missing" and counted in the
          // Plan Summary. Only a genuine array means the library was actually read.
          planDecks = r && Array.isArray(r.decks) ? r.decks : null;
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
      // A visually-hidden prefix, so a bare value in a dense row ("Worship", "5:00") still reads
      // as what it IS to a screen reader. The row is one option in a listbox, so an aria-label on
      // a child <span> is unreliable; real text in the accessibility tree is not.
      function srOnly(text) {
        const s = document.createElement("span");
        s.className = "sr-only";
        s.textContent = text;
        return s;
      }
      // The ONE predicate for "this item has a planned duration", used by the run-sheet row AND by
      // planSummaryOf. A row and a total that disagree about what counts is the drift this whole
      // surface was rejected for once; sharing the predicate makes disagreement impossible rather
      // than merely tested-against. Absent = unset (renders "—", excluded from the sum, marks the
      // total partial). An explicit 0 is SET, and renders 0:00.
      // A single plan item longer than 24h is not a duration, it is corrupt or hostile input.
      // isFinite alone is not a bound: 1e308 is finite and rendered "2.77e+304:58:56" as a total.
      const PLAN_MAX_ITEM_SECS = 86400;
      function planHasDuration(it) {
        // Finite and non-negative: a LAN peer is untrusted, and a JSON-valid -1200 or 1e308 would
        // otherwise render "-1:-15:00" / "Infinity:NaN:NaN" in the total (Sana S3). An out-of-range
        // value is treated as UNSET rather than clamped — inventing a duration is worse than
        // showing none.
        return (
          typeof it.planned_secs === "number" &&
          isFinite(it.planned_secs) &&
          it.planned_secs >= 0 &&
          it.planned_secs <= PLAN_MAX_ITEM_SECS
        );
      }
      // Spoken form for AT (UI-A1 §211): "eight colon zero zero" is not useful. The run-sheet row
      // is role=option, so a descendant's aria-label feeds the option's accessible name — which is
      // what a screen reader actually announces for the row.
      function planSpokenDuration(secs) {
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        const sec = secs % 60;
        const parts = [];
        const unit = (n, one) => n + " " + one + (n === 1 ? "" : "s");
        if (h) parts.push(unit(h, "hour"));
        if (m) parts.push(unit(m, "minute"));
        if (sec || !parts.length) parts.push(unit(sec, "second"));
        return parts.join(" ");
      }
      // Row durations: m:ss under an hour (the design's 5:00 / 3:12), h:mm:ss at or above one, so a
      // 65-minute item reads 1:05:00 and never "65:00" — which is indistinguishable from 65 seconds
      // of m:ss at a glance and disagrees with how the total is formatted.
      function planFmtDuration(secs) {
        return secs >= 3600 ? planFmtTotal(secs) : fmtClock(secs);
      }
      // h:mm:ss for a plan total. fmtClock is m:ss, which would render a 53-minute plan as 53:12
      // and a 65-minute one as 1:05 — indistinguishable from 1 minute 5 seconds.
      function planFmtTotal(secs) {
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        return h + ":" + String(m).padStart(2, "0") + ":" + String(secs % 60).padStart(2, "0");
      }
      // Resolution state of a content link — the ONE place that decides it, so the run-sheet chip,
      // the inspector deck card and the Plan Summary can never disagree. Three-state, because
      // "could not check" is not "fine":
      //   "missing"  - checked, and the content is gone   -> missing treatment
      //   "unknown"  - nobody could check                 -> NOT resolved, never counted missing
      //   "resolved" - it is there
      // Decks are operator-owned by design: the host has no deck store and structurally cannot
      // resolve a deck_id, so for a deck link LOCAL resolution stays authoritative whatever the
      // host says. `status` is an additive field (86ajy0hw0), absent today; every branch below
      // already holds without it and honours it the moment it lands.
      function planLinkState(link) {
        if (!link || typeof link !== "object") return "resolved";
        // Decks are settled FIRST, before any host status. The operator owns the deck library and
        // the host has no deck store, so when the library is loaded it is ground truth — a host
        // "missing" for a deck the operator can see is stale, not authoritative. (Sana S1: this
        // check used to sit after the status test, which inverted exactly that rule.)
        if (link.kind === "deck") {
          if (planDecks) return planDecks.some((d) => d && d.id === link.id) ? "resolved" : "missing";
          // Library unavailable — no ground truth here, so defer to whatever the host could say.
          return link.status === "missing" ? "missing" : "unknown";
        }
        if (link.status === "missing") return "missing";
        if (link.status === "unknown") return "unknown";
        return "resolved";
      }
      // Plan Summary figures (frame 608:875). Computed from the view we already hold, so the panel
      // ships today. The backend `summary` object (86ajy0hw0) is additive and arrives on the same
      // view; planRenderSummary reads ONE summary-shaped object either way, so adopting it is a
      // change here and nowhere else.
      // A plan longer than a week is corrupt, not a service. Bounds the host total the way
      // PLAN_MAX_ITEM_SECS bounds a single item's duration.
      const PLAN_MAX_TOTAL_SECS = 86400 * 7;
      const PLAN_MAX_COUNT = 100000;
      const SUMMARY_COUNTS = ["items", "songs", "scripture", "presentations", "media",
                              "announcements", "timers", "sections", "assigned", "missing", "unknown"];
      // Validate the host summary before trusting it, and fall back to the local computation on
      // anything malformed.
      //
      // The pass-through crosses a TRUST BOUNDARY. Handing the host's object straight to the
      // renderer silently inherited every defect the local path had already been hardened against:
      // `{}` rendered "NaN:NaN:NaN", 1e308 rendered "2.77e+304:58:56" (the exact string
      // PLAN_MAX_ITEM_SECS exists to prevent), and a total disagreeing with the rows beneath it is
      // the §9 MAJOR the header total was added to fix. None of that needs an attacker — a host one
      // release ahead or behind is enough.
      //
      // Falling back is always SAFE: the local computation is derived from the very items being
      // rendered, and is separately tested. So this errs strict.
      function planSummaryIsSound(sum, items) {
        if (!sum || typeof sum !== "object") return false;
        const count = (v) => typeof v === "number" && isFinite(v) && Number.isInteger(v) && v >= 0 && v <= PLAN_MAX_COUNT;
        if (!(typeof sum.planned_total_secs === "number" && isFinite(sum.planned_total_secs) &&
              Number.isInteger(sum.planned_total_secs) && sum.planned_total_secs >= 0 &&
              sum.planned_total_secs <= PLAN_MAX_TOTAL_SECS)) return false;
        for (let i = 0; i < SUMMARY_COUNTS.length; i++) if (!count(sum[SUMMARY_COUNTS[i]])) return false;
        if (sum.partial !== undefined && typeof sum.partial !== "boolean") return false;
        if (sum.planned_items !== undefined && !count(sum.planned_items)) return false;
        if (sum.partial === true && sum.planned_items === undefined) return false;
        if (sum.assigned > sum.items) return false;
        if (sum.missing + sum.unknown > sum.items) return false;
        // Every TRIGGERABLE item must land in exactly one per-kind line. Sections are excluded
        // from `items` by the settled rule, so they are excluded here too.
        const kinds = sum.songs + sum.scripture + sum.presentations + sum.media +
                      sum.announcements + sum.timers;
        if (kinds !== sum.items) return false;
        // A subset can never exceed its whole. Backend caught the mirror of this in their own
        // work: a duration set ON a section reached planned_items while the section was absent
        // from items, so planned_items could exceed items and this panel would have rendered
        // "7 of 6". Individually-correct fields that do not add up are what design QA rejected
        // these frames for the first time round, so the seam checks the arithmetic, not just the
        // field types.
        if (sum.planned_items !== undefined && sum.planned_items > sum.items) return false;
        // The total must describe the items actually being rendered. A header reading 99999s over
        // rows summing 600s is precisely the §9 MAJOR. Sections carry no duration, so this holds
        // under either reading of the question above.
        // WHY the two totals agree, and what silently breaks if that changes.
        //
        // This recomputation sums planned_secs over EVERY item it was sent, sections included.
        // The host's planned_total_secs EXCLUDES sections, because a divider is not part of the
        // run sheet. Those are different definitions, and they agree for exactly one reason: the
        // host will not let a section hold a duration at all — ServicePlan::set_item_planned_secs
        // refuses it (PlanError::NotApplicable) and from_parts strips any an older build stored.
        //
        // So this is not 'sections happen to carry no duration'. It is a guarantee another crate
        // makes, in another language, landed in another pull request. If that guard is ever
        // relaxed, the sums diverge, this check returns false, and planSummaryOf falls back to
        // the local computation below — QUIETLY. The panel keeps rendering plausible numbers that
        // are no longer the host's, with nothing thrown and no test failing. The tripwire on the
        // other side is a_section_with_a_duration_would_break_the_operators_summary_validation_seam
        // in selahcue-core/tests/test_plan.rs, and the mirror of this note is on
        // ServicePlan::planned_total. Change either definition and both must move.
        let localTotal = 0;
        items.forEach((x) => { if (planHasDuration(x)) localTotal += x.planned_secs; });
        if (sum.planned_total_secs !== localTotal) return false;
        return true;
      }
      function planSummaryOf(view) {
        // PREFER THE HOST'S SUMMARY. ServicePlan::planned_total() returns the sum and `partial`
        // from ONE pass, so the flag cannot drift from the number it describes — which is why it
        // belongs there and not here. Absent today; this is the whole of the swap when PR #13
        // lands, and until then the local computation below stands in.
        //
        // A consequence worth stating: because `partial` is CONSUMED and never computed here, the
        // "inert sections never set partial" rule (spec §4.2 — unset children, not headers) is the
        // host's to enforce and this client cannot diverge from it. The local fallback carries no
        // partial flag at all, so it has no section rule to get wrong either.
        if (planSummaryIsSound(view && view.summary, (view && view.items) || [])) return view.summary;
        const all = (view && view.items) || [];
        const by = (k) => all.filter((x) => x.kind === k).length;
        // Every summary metric describes the TRIGGERABLE run sheet, so an inert `section` divider
        // is excluded from all of them — items, assigned, the planned total, missing and unknown.
        // Frame 608:875 is explicit: "6 items" and "Assigned 6 / 6" over six rows and THREE
        // dividers, with no Sections line in the panel at all. The `sections` count is still
        // reported below, so nothing is lost; it is simply no longer conflated with the run sheet.
        const items = all.filter((x) => x.kind !== "section");
        let total = 0;
        let assigned = 0;
        let missing = 0;
        let unknown = 0;
        items.forEach((x) => {
          if (planHasDuration(x)) total += x.planned_secs;
          if (x.owner) assigned += 1;
          if (x.link) {
            // missing and unknown are counted SEPARATELY and never merged. "The host could not
            // check" is not "it is fine": the host structurally cannot resolve decks or media, so
            // collapsing unknown into resolved is the failure this three-state field exists to
            // prevent. Decks are settled locally by planLinkState; media has no library in any
            // layer yet, so it stays unknown by design.
            const st = planLinkState(x.link);
            if (st === "missing") missing += 1;
            else if (st === "unknown") unknown += 1;
          }
        });
        // Field names deliberately mirror OperatorStateView.summary (86ajy0hw0) one-for-one, so
        // adopting the host's summary is a swap of this function's body and nothing else.
        // `partial`/`unplanned` are local additions the wire may not carry — see the PR.
        return {
          planned_total_secs: total,
          items: items.length, // triggerable rows only — sections excluded
          planned_items: items.filter(planHasDuration).length,
          songs: by("song"),
          scripture: by("scripture"),
          presentations: by("slide_group"), // slide-group count, per the wire shape
          media: by("media"),
          announcements: by("announcement"),
          timers: by("timer"),
          sections: by("section"),
          assigned: assigned,
          missing: missing,
          unknown: unknown,
        };
      }
      // =======================================================================================
      // PLAN LIFECYCLE (86ak8467m) — the host's viewer / publish / template state, and the five
      // commands that act on it: publish_plan, new_plan, template_plan, duplicate_plan,
      // import_plan. All five require the EXISTING EditPlan permission; no new permission is
      // invented here, and none is enforced here either — the host's authorize() is the gate and
      // this file only reports its verdict.
      //
      // Every reader below is a SINGLE DEFINITION consumed by the renderers, by the send sites,
      // and by the gate's controls. That is deliberate: a control that re-derives a predicate
      // beside the code under test passes while the real predicate is mutated away (86ak643rc).
      // =======================================================================================

      // The label bound the host enforces (`MAX_PLAN_LABEL_LEN` in selahcue-core::plan — one
      // bound for a plan name, an item title and an owner, which is why it is not called a name).
      const PLAN_NAME_MAX = 120;
      // The run-sheet cap the untrusted ingress enforces (`MAX_PLAN_ITEMS`).
      const PLAN_MAX_ITEMS = 500;
      // How many starter templates the picker will render. A picker is a human-scale list that a
      // coordinator SCANS — this build's host ships two — so the bound is generous by an order of
      // magnitude and still nowhere near a number that could hang the console. A host reporting
      // more than this is malformed, and a malformed list reads as no list rather than being
      // silently truncated: quietly dropping templates the host offers is the same fabrication
      // as inventing ones it does not.
      const PLAN_TEMPLATES_MAX = 24;
      // A template id is a wire tag ("sunday-morning"), never displayed.
      const PLAN_TEMPLATE_ID_MAX = 64;

      // The invisible characters the HOST refuses, and the ones it deliberately ADMITS.
      //
      // Two named sets rather than one regex, because the host has two and the distinction is the
      // whole point of its rule (`is_display_hostile` / `is_admitted_invisible`, plan.rs). Mirrored
      // as data so a reader can diff them against that file line by line.
      //
      //  - REFUSED: stateful direction controls, which reorder text BEYOND their own position (an
      //    unterminated RLO reverses the rest of a rendered line — the Trojan-Source primitive),
      //    and zero-orthography invisibles that belong to no script's spelling. Plus the Zl/Zp
      //    line separators, which `\p{Cc}` does not cover and which render as a hard break inside
      //    a single-line run-sheet label (`is_line_separator`).
      //  - ADMITTED: the orthographic joiners and the stateless implicit bidi marks. These are
      //    SPELLING. Sinhala "ශ්‍රී" (as in Sri Lanka) cannot be written without U+200D at all;
      //    Persian and Urdu need U+200C for the plural suffix; and a family emoji is a ZWJ
      //    sequence. Refusing them does not harden a name field, it stops entire writing systems
      //    being typed into one — which is why the host, and now this client, admit them.
      const PLAN_DISPLAY_HOSTILE = /[\u202A-\u202E\u2066-\u2069\u200B\u2060-\u2064\u206A-\u206F\uFFF9-\uFFFB\uFEFF\u2028\u2029]/;
      // Everything that is neither whitespace nor an admitted invisible — the host's
      // `has_visible_content`. A name of nothing but joiners renders as nothing and is refused.
      const PLAN_VISIBLE_CONTENT = /[^\s\u200C\u200D\u200E\u200F\u061C]/u;

      // Why v is unacceptable as a plan name or an imported item title, or null when it is fine.
      //
      // Mirrors `plan_label_valid` (selahcue-core/src/plan.rs), which is the single rule the host
      // applies to a plan name, an item title AND an item owner — `valid_plan_label` in
      // controller.rs calls it for all three. One rule here for the same reason: three copies
      // drift apart and a reviewer then has to check three predicates instead of one.
      //
      // The HOST stays authoritative — this refuses EARLY so a typo shows up under the field
      // instead of coming back as a Denied{bad_request} the operator cannot read, and every host
      // rejection is still surfaced verbatim (planLifecycleFailed).
      //
      // Details that are easy to get wrong and were got wrong here first:
      //
      //  - COUNT SCALAR VALUES, not UTF-16 code units. The host counts `chars()`. `s.length`
      //    counts code units, so a name written in an astral script would be refused by this
      //    client at half the length the host allows — a client stricter than the host for a
      //    reason the operator cannot see or fix.
      //  - Test the CLASS, not a hand-listed set. `\p{Cc}` is exactly the Unicode general
      //    category Rust's `char::is_control` tests. This repo has already shipped a guard that
      //    refused NUL and let every other control character through (commit ee3646f swept it
      //    across the class); repeating that in JS would be the same bug in a second language.
      //  - DRIFT RUNS IN BOTH DIRECTIONS, and the stricter direction is the one that bites a
      //    user. An earlier version of this function mirrored the host's first invisible rule
      //    (`is_invisible_formatting`, 7a6e404) by refusing ALL Cf. The host then narrowed that
      //    rule to a principle (352886d) and now admits the joiners; a client left behind would
      //    have refused a Sinhala, Persian, Urdu, Devanagari or Malayalam service name, and every
      //    family emoji, with a message the operator has no way to act on. Looser drift costs an
      //    unreadable bad_request; stricter drift locks people out of naming their own service.
      //
      // Known, one-directional divergence that remains: JS `trim()` and Rust `str::trim` do not
      // strip an identical set (U+0085 on one side, U+FEFF on the other). Both of those code
      // points are refused above by the control-character and display-hostile tests before the
      // difference can matter, so the two agree on every input either would accept.
      function planNameProblem(v) {
        const t = typeof v === "string" ? v.trim() : "";
        if (!t) return "Enter a name.";
        // Bound the string BEFORE materialising it. `Array.from` builds the whole scalar-value
        // array to learn its length, so one wrong-clipboard paste — a log file, a minified
        // bundle, one long JSON row — froze the console for 3.27s and spiked ~270MB of transient
        // heap on Blink (measured through this dialog on f335a0d). The pre-check is EXACT, not a
        // heuristic: a Unicode scalar value is at most two UTF-16 code units, so any string whose
        // code-unit length exceeds 2 x the bound must exceed the bound in scalar values. No
        // string that would have been accepted can be refused by it.
        if (t.length > PLAN_NAME_MAX * 2) return "Use " + PLAN_NAME_MAX + " characters or fewer.";
        if (Array.from(t).length > PLAN_NAME_MAX) return "Use " + PLAN_NAME_MAX + " characters or fewer.";
        if (/\p{Cc}/u.test(t)) return "Remove control characters (such as tabs or line breaks) from the name.";
        // Tested against the ORIGINAL string, not the trimmed one, and that difference is load
        // bearing: JS `trim()` strips U+FEFF and Rust's does not, so "\uFEFFabc" would pass here
        // and be refused there. None of the refused code points has the Unicode White_Space
        // property, so Rust's `trim` can never remove one — checking the original is therefore
        // exactly equivalent to checking Rust's trimmed form. (The control-character test above
        // stays on the TRIMMED string for the mirror-image reason: Rust trims a leading newline
        // as whitespace before testing, so testing the original there would refuse a name the
        // host accepts.)
        if (PLAN_DISPLAY_HOSTILE.test(v))
          return "Remove invisible formatting characters (such as zero-width or text-direction marks) from the name.";
        // `has_visible_content`, last because the more specific messages above are more useful.
        // A name of nothing but joiners passes `trim()` and renders as nothing.
        if (!PLAN_VISIBLE_CONTENT.test(t)) return "Enter a name.";
        return null;
      }

      // The host's verdict on what this operator may do with the plan (`viewer` on the view).
      //
      // THREE STATES, NOT TWO. An absent `viewer` means THIS HOST DOES NOT REPORT IT — an older
      // host, or a peer with no permission model to report — and that is emphatically NOT
      // "view only". Painting a "View only" badge on an absent field is the fabrication this
      // field exists to remove, and it is the same rule already carried by output_health,
      // storage, session, summary and ContentLinkView.status.
      //
      // `can_edit` is the HOST'S OWN VERDICT, computed from the same authorize() choke point
      // that enforces it, and it is CONSUMED here and never recomputed from `role`. The mobile
      // client's transcribed rbac.dart permission table is precisely the drift this field
      // removes, and that table has already diverged from the backend once in this project.
      // A `viewer` object carrying no usable boolean says nothing, so it reads as unreported.
      function planViewer(view) {
        const v = view && view.viewer;
        if (!v || typeof v !== "object") return { canEdit: null, role: null };
        const canEdit = typeof v.can_edit === "boolean" ? v.can_edit : null;
        // `role` is carried but deliberately NOT rendered and NOT branched on: it is the host's
        // identity label, and the moment a control reads it the re-derivation this field exists
        // to remove is back. (A `reported` boolean lived here too — a third name for
        // `canEdit !== null` that nothing consumed — and is gone rather than left to rot.)
        return { canEdit: canEdit, role: typeof v.role === "string" ? v.role : null };
      }
      // The question every editing control asks. Both of these consume planViewer().canEdit —
      // the one verdict — so an unreported viewer shows the controls AND shows no badge, and
      // neither answer can drift from the other.
      function planCanEdit(view) { return planViewer(view).canEdit !== false; }
      function planIsViewOnly(view) { return planViewer(view).canEdit === false; }

      // The host's publish state for the open plan, or null when the host does not report it.
      //
      // Validated before use, exactly as the host summary is (planSummaryIsSound): a malformed
      // object reads as UNREPORTED rather than being rendered, because a plausible-looking wrong
      // revision printed on a run sheet is worse than no revision at all.
      //
      // `changed` is folded into the SAME expression as `published` here rather than being
      // reported raw, because "changed" has no meaning without a baseline: with nothing
      // published there is nothing to have changed FROM, so a badge there would be inventing
      // state. Every consumer — the badge, the status line, the Publish button's description —
      // reads THIS `changed`, so mutating the conjunction below moves all three at once.
      // THE OBJECT OMITS ITS DEFAULTS. `PublishStateView` is `#[serde(default)]` with
      // skip-if-none / skip-if-zero / skip-if-false, so only `revision` is always present and a
      // fresh draft arrives as the whole object `{"revision":0}`:
      //
      //     missing `version`            = 0        (never published)
      //     missing `published_revision` = null     (draft)
      //     missing `changed`            = false
      //
      // Requiring `version` here — the first version of this function did — made every real
      // draft read as UNREPORTED, so the panel said nothing at all about a plan it could have
      // described correctly. Defaults are applied, then the RESULT is validated.
      function planPublishState(view) {
        const p = view && view.publish;
        if (!p || typeof p !== "object") return null;
        // These are ORDINALS, not counts, so they do not share PLAN_MAX_COUNT's bound. `revision`
        // bumps on every plan edit, undo and redo; a long automated session could pass 100,000,
        // and refusing it there would silently degrade the WHOLE lifecycle panel to "unreported"
        // under a stated reason that was not true. They are only ever rendered as labels — never
        // summed, subtracted or compared for the badge — so the only bound they need is the one
        // past which a number stops being a number.
        const n = (x) => typeof x === "number" && isFinite(x) && Number.isInteger(x) && x >= 0 && x <= Number.MAX_SAFE_INTEGER;
        if (!n(p.revision)) return null; // the one field the host always sends
        const version = p.version === undefined ? 0 : p.version;
        if (!n(version)) return null;
        const pr = p.published_revision;
        const published = pr !== undefined && pr !== null;
        if (published && !n(pr)) return null;
        // `changed: null` is tolerated as false, exactly as `published_revision: null` is
        // tolerated as "not published" four lines up. Neither can arrive from a serde host (both
        // are skip-if-unset on the wire struct), so this is about the READER being internally
        // consistent: silencing the whole panel over one null while accepting another beside it
        // was an inconsistency the next reader would have had to explain.
        if (p.changed !== undefined && p.changed !== null && typeof p.changed !== "boolean") return null;
        return {
          revision: p.revision,
          version: version,
          publishedRevision: published ? pr : null,
          published: published,
          // READ FROM `changed`, NEVER COMPUTED FROM THE REVISIONS. The counters say the
          // document was TOUCHED; `changed` says it actually DIFFERS. An edit that is then
          // undone moves `revision` past `published_revision` while restoring the content, so
          // `revision !== published_revision` with `changed:false` is a normal, meaningful
          // state — and a badge derived from the counters would sit over a plan identical to
          // the published one, offering an operator nothing to review. The obvious
          // implementation is the wrong one and it looks right in testing.
          changed: published && p.changed === true,
        };
      }

      // The starter templates THIS HOST offers, or null when it offers none.
      //
      // Reported by the host rather than transcribed here, for the same reason `themes` and
      // `translations` are: a client carrying its own copy of the list drifts from the host's
      // silently, the first time either side changes. `items` is a COUNT, not an array — the
      // template's contents never cross the wire, only its size, so the picker says how big a
      // skeleton it is about to create and nothing more.
      function planTemplateList(view) {
        const t = view && view.plan_templates;
        if (!Array.isArray(t) || !t.length) return null;
        // BOUNDED BEFORE IT IS READ, not after. The operator shell talks to a host over the LAN
        // link, and `ControlClient` sets no `max_message_size` (client.rs:70) — so while the
        // SERVER caps inbound frames at 64 KiB (server.rs:46), a reply travelling the other way
        // may be up to tungstenite's 64 MiB default. Unbounded, this filter runs over every entry
        // on EVERY plan render and the picker would then build a DOM row for each.
        //
        // The bound is on the ENTITY — the number of entries, and the length of each string that
        // is rendered — not on a byte proxy, because a byte budget alone still admits
        // unboundedly many tiny rows.
        if (t.length > PLAN_TEMPLATES_MAX) return null;
        const str = (v, max) => typeof v === "string" && v.length > 0 && v.length <= max;
        const ok = t.filter(
          (x) =>
            x && typeof x === "object" &&
            str(x.id, PLAN_TEMPLATE_ID_MAX) &&
            str(x.name, PLAN_NAME_MAX) &&
            typeof x.items === "number" && isFinite(x.items) &&
            Number.isInteger(x.items) && x.items >= 0 && x.items <= PLAN_MAX_ITEMS
        );
        return ok.length ? ok : null;
      }

      // Does this host implement the plan-lifecycle COMMANDS?
      //
      // The signal is that it reports `publish`. Publication state and the commands that produce
      // it are one capability landing as one wire addition, so a host that can describe the
      // plan's publication is a host that can act on it.
      //
      // Why gate at all, when the frames simply draw the buttons: this shell talks to whichever
      // host is on the other end — the in-process one, or a REMOTE output window that may be a
      // different build entirely. A button wired to a command the host does not have is a
      // control that looks live and fails on click, which is the exact failure the
      // disabled-with-a-stated-reason treatment in this panel already exists to avoid. Asked
      // once, here, and consumed by every lifecycle control.
      // The title of whatever is on air right now, or null. Read from the HOST's own live_index
      // / live_free_text, never inferred: `live_free_text` is a slide whose plan item is already
      // gone, and it is exactly the case a naive `items[live_index]` lookup misses.
      function planLiveItemTitle(view) {
        if (!view) return null;
        const items = Array.isArray(view.items) ? view.items : [];
        const live = items.find((x) => x && x.is_live);
        if (live && typeof live.title === "string" && live.title) return live.title;
        if (typeof view.live_free_text === "string" && view.live_free_text) return view.live_free_text;
        return null;
      }
      function planLifecycleAvailable(view) { return planPublishState(view) !== null; }
      const PLAN_NO_LIFECYCLE_REASON =
        "This host doesn't report plan publishing, so creating, duplicating, importing and publishing aren't available from here yet.";

      function planLinkChip(link) {
        const el = document.createElement("span");
        el.className = "link-chip link-" + link.kind;
        if (link.kind === "scripture") {
          el.textContent =
            "✦ " + (link.reference || "scripture") + (link.translation ? " · " + link.translation : "");
        } else if (link.kind === "deck") {
          const name = planDeckName(link.id);
          if (planLinkState(link) === "missing") {
            el.className = "link-chip link-missing";
            el.textContent = "⚠ presentation missing";
          } else {
            el.textContent = "▦ " + (name || "presentation");
          }
        } else if (link.kind === "media") {
          // The chip asks planLinkState like everything else, so a host-flagged missing medium is
          // not drawn as a healthy one while the summary counts it missing (Sana S2).
          if (planLinkState(link) === "missing") {
            el.className = "link-chip link-missing";
            el.textContent = "⚠ media missing";
          } else {
            el.textContent = "▷ media";
          }
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
          // reference (and a malformed link — unknown kind, blank reference, missing id) and leaves
          // the plan unchanged, so closing optimistically would hide the failure. It does NOT
          // reject an unknown DECK: the host has no deck store, so any deck id is accepted and the
          // link comes back with status "unknown" for this side to resolve against the library.
          // Close only on success; on rejection re-enable + surface an inline
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
              // Send the deck's name as the link label too: once a deck is deleted, no layer can
              // turn its id back into a name, so the plan item has to have kept one.
              commit({ kind: "deck", id: created.id, slide_count: created.slides, label: created.name }); // success → modal closes
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
            commit({ kind: "deck", id: selId, slide_count: d ? d.slides : undefined, label: d ? d.name : undefined });
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
      let planLastView = null; // last view rendered, for UI-only re-renders
      // After planRenderBuilder blanks + rebuilds the run sheet, keyboard focus would fall to
      // <body>; this records what the last user action should re-focus (the selected row, or a
      // moved row's ↑/↓ button) so focus survives the rebuild (WCAG 2.4.3). Null on a background
      // re-render (poll / link-commit refresh) so it never steals focus.
      let planFocusAfterRender = null;
      function planKindLabel(kind) {
        const f = PLAN_ADD_KINDS.find((k) => k[0] === kind);
        return f ? f[1] : kind;
      }
      // Loading (frame 611:350). planActivate runs on navigation to the surface, so this paints
      // once per visit and the first planRenderBuilder replaces it — a mutation re-render never
      // flashes it. The message is a role=status live region because the missing-content scan is
      // the part an operator actually waits on, so it is announced and not merely drawn. The
      // skeleton rows are aria-hidden: they are texture, and announcing four empty rows is noise.
      function planRenderLoading() {
        const list = document.getElementById("plan-b-list");
        if (!list) return;
        list.innerHTML = "";
        const count = document.getElementById("plan-b-count");
        if (count) count.textContent = "—"; // never a stale count while the real one is unknown
        const totL = document.getElementById("plan-b-total");
        if (totL) totL.textContent = ""; // ...and no stale total sitting beside the "—"
        planBlankSummary("Opening plan…");
        const st = document.createElement("p");
        st.className = "plan-loading-msg";
        st.setAttribute("role", "status");
        st.textContent = "Opening plan… scanning for missing content.";
        list.appendChild(st);
        for (let i = 0; i < 4; i++) {
          const sk = document.createElement("div");
          sk.className = "plan-skel-row";
          sk.setAttribute("aria-hidden", "true");
          list.appendChild(sk);
        }
      }
      // A failed open must not leave the skeleton up forever — an endless loading state is a lie
      // about work still being in flight. This is the MINIMUM honest replacement; the designed
      // error state (frame 612:124: non-blocking banner + Restore last autosave + integrity check)
      // needs autosave-slot wire fields that do not exist yet and belongs to 86ak8467m.
      function planRenderLoadFailed(e) {
        console.error(e);
        const list = document.getElementById("plan-b-list");
        if (!list || !list.querySelector(".plan-skel-row")) return; // a view already painted; leave it
        list.innerHTML = "";
        const count = document.getElementById("plan-b-count");
        if (count) count.textContent = "";
        const totF = document.getElementById("plan-b-total");
        if (totF) totF.textContent = "";
        planBlankSummary("Plan figures unavailable — the plan could not be opened.");
        // Quinn — the previous view's permission chrome outlived the plan it described. A "View
        // only" badge over a surface whose plan could not be opened is a verdict this client does
        // not have: the failure means the viewer field is UNKNOWN, and painting a restriction from
        // an unknown is the exact fabrication the three-state rule on this surface exists to stop.
        // Cleared to the unreported state, and the palette goes with it — there is no plan to add
        // an item to, so an ADD ITEM column here is a control that looks live and cannot work.
        planViewerSig = null; // ...and the next good poll re-baselines rather than reading as a change
        planSyncPermission(null);
        const palette = document.querySelector("#surface-plan .plan-palette");
        if (palette) palette.style.display = "none";
        const p = document.createElement("p");
        p.className = "plan-load-failed";
        p.setAttribute("role", "alert");
        p.textContent = "Couldn't open the plan. Live output is unaffected — reopen this surface to retry.";
        list.appendChild(p);
      }
      // Deselect back to the Plan Summary. Mirrors the Theme Designer's Escape-deselects pattern
      // (tdSel keydown / empty-canvas click). Without this, planSelectedId is only ever SET by a
      // gesture and cleared by deleting the item — so the summary, and the Publish / pre-service
      // actions that live in it, become unreachable after the first row click.
      function planDeselect() {
        if (planSelectedId === null) return; // already on the summary — do not rebuild on every Escape
        planSelectedId = null;
        // Re-render from the view already in hand. Deselecting is a pure UI state change, so it
        // must not cost a host round-trip (and must not race one in).
        if (planLastView) planRenderBuilder(planLastView);
      }
      (function planWireDeselect() {
        document.addEventListener("keydown", (ev) => {
          if (ev.key !== "Escape" || planSelectedId === null) return;
          const surf = document.getElementById("surface-plan");
          if (!surf || !surf.classList.contains("active")) return;
          if (document.querySelector(".pm-confirm-back")) return; // a dialog owns Escape
          if (window.__cmdPalette && window.__cmdPalette.isOpen()) return;
          if (isMenuOpen()) return;
          const t = ev.target;
          if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
          ev.preventDefault();
          planDeselect();
        });
        // Clicking the empty area BELOW the rows also deselects (the pointer path), matching the
        // Theme Designer's empty-canvas click.
        document.addEventListener("click", (ev) => {
          const list = document.getElementById("plan-b-list");
          if (!list || ev.target !== list) return; // a row click bubbles with target = the row
          planDeselect();
        });
      })();
      function planActivate() {
        // A fresh visit must not inherit the last visit's outcome. "Plan published…" sitting
        // under the header describes the plan as it was at that moment; after a few edits, or a
        // trip to the console and back, it is a statement about a run sheet that has moved on.
        planNotice("");
        planFocusAfterRender = null; // fresh navigation must not inherit a stale reorder intent
        planSelectedId = null; // ...nor a stale selection: a fresh visit opens on the Plan Summary
        buildPlanPalette();
        planRenderLoading();
        // Deck names/missing-status for link chips; then render with resolved names.
        planLoadDecks().then(() => {
          if (document.getElementById("plan-b-list")) invoke("view").then(planRenderBuilder).catch(planRenderLoadFailed);
        });
        invoke("view").then(planRenderBuilder).catch(planRenderLoadFailed);
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
          // Any plan EDIT invalidates a lifecycle outcome message: "Plan published" is true of
          // the run sheet that was published, not of the one now on screen.
          planNotice("");
          planRenderBuilder(await fn());
        } catch (e) {
          console.error(e);
          // ...and SAY so. A refused plan edit reached console.error and nothing else, so a host
          // that rejected a rename, a reorder or an undo looked exactly like a control that did
          // nothing — the failure this surface's disabled-with-a-reason treatment exists to
          // avoid, arrived at through the success path instead.
          const detail = e && e.message ? e.message : typeof e === "string" ? e : "";
          planNotice("alert", "That change wasn't applied" + (detail ? " — " + detail : "") + ".");
          // The caller may have set a focus intent (e.g. a reorder) BEFORE the mutation; a rejected
          // mutation never re-renders, so clear it — otherwise a later background re-render would
          // consume the stale intent and steal focus onto an item the operator didn't just touch.
          planFocusAfterRender = null;
        }
      }
      // Plan run-sheet undo/redo (⌘Z / ⌘⇧Z) — backend-authoritative (the LiveController plan
      // history). A plan EDIT is undone, never a live-control action; the host reconciles cursors so
      // the audience output never changes on undo. Remote-host mode is a safe no-op (the host owns
      // its own history). Mirrors the Presentation deck undo (pmUndo/pmRedo) + the Theme Designer.
      function planUndo() { planMutate(() => invoke("plan_undo")); }
      function planRedo() { planMutate(() => invoke("plan_redo")); }
      (function planWireUndo() {
        document.addEventListener("keydown", (ev) => {
          const surf = document.getElementById("surface-plan");
          if (!surf || !surf.classList.contains("active")) return;
          if (window.__cmdPalette && window.__cmdPalette.isOpen()) return;
          if (document.querySelector(".pm-confirm-back")) return; // a modal dialog owns keys
          if (isMenuOpen()) return;
          if (!(ev.ctrlKey || ev.metaKey) || ev.altKey) return;
          if (ev.key !== "z" && ev.key !== "Z") return;
          // Undo and redo are plan EDITS, and this is the SECOND keyboard path that had to be
          // gated on the host's verdict — the Alt+arrow reorder was the first, and a reviewer had
          // to find each of them by mutation. Hiding the buttons while leaving a key combination
          // live makes the restriction hold for the mouse and not for the keyboard, which is not
          // a restriction. Read from the last view rendered: the same verdict every other control
          // on this surface consumes.
          if (!planCanEdit(planLastView)) return;
          const t = ev.target;
          if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
          ev.preventDefault();
          if (ev.shiftKey) planRedo();
          else planUndo();
        });
      })();
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
      // Frame 612:342 — the permission state, applied to the surface chrome.
      //
      // The rule is HIDDEN, NOT GREYED (UX-STATE-MATRIX:111 — the persona pain is literally
      // "seeing controls they can't use"), and hidden means gone from the tab order too. So the
      // add-item column is taken out with an INLINE display:none rather than the `hidden`
      // attribute: in this webview a class-level `display` rule silently defeats `hidden`, and an
      // inline rule cannot be overridden by one. Controls this file builds itself (Publish, the
      // reorder buttons, the inspector's actions) are simply not built at all.
      //
      // A "View only" badge is written ONLY on an explicit can_edit === false. An absent viewer
      // field is the host declining to report, which is not a restriction, so nothing is drawn.
      function planSyncPermission(view) {
        const viewOnly = planIsViewOnly(view);
        const slot = document.getElementById("plan-viewonly-slot");
        if (slot) {
          slot.innerHTML = "";
          if (viewOnly) {
            const badge = document.createElement("span");
            badge.className = "plan-viewonly";
            badge.id = "plan-viewonly";
            // Text, not colour: the badge says what it is (WCAG 1.4.1). aria-disabled is on the
            // badge rather than on removed controls — there are no disabled controls to mark.
            // The text IS the signal. `aria-disabled` on a <span> is inert — it marks a WIDGET
            // unavailable, and this is a label — so it was noise pretending to be an affordance.
            badge.textContent = "View only";
            slot.appendChild(badge);
            const why = document.createElement("span");
            why.className = "plan-viewonly-why";
            why.id = "plan-viewonly-why";
            why.textContent = "You can follow this plan. Your role can't change it.";
            slot.appendChild(why);
          }
        }
        const palette = document.querySelector("#surface-plan .plan-palette");
        if (palette) palette.style.display = viewOnly ? "none" : "";
        // ...and the GRID must lose the track with it. .plan-builder-grid declares three fixed
        // tracks (220px | 1fr | 340px); taking the first child out of flow does not remove its
        // track, it shifts every remaining child one place left — so the run sheet landed in the
        // 220px column and rendered "G…", "We…" beside a 792px-wide inspector and an empty third
        // track. Invisible to the Blink gate (which asserts elements, not track widths) and
        // found by looking at a real WKWebView render.
        const grid = document.querySelector("#surface-plan .plan-builder-grid");
        if (grid) grid.classList.toggle("is-viewonly", viewOnly);
        // The header's Open in Live is a pure surface switch, so it survives view-only — but it
        // reads as the passive thing it is, per design-QA §9 on this frame.
        const openLive = document.getElementById("plan-open-live");
        if (openLive) {
          openLive.textContent = viewOnly ? "Follow in Live ▶" : "Open in Live ▶";
          openLive.className = viewOnly ? "pm-btn-ghost" : "pm-btn-primary";
        }
      }
      // The change badge, refreshed from the 1 Hz poll.
      //
      // WHY IT NEEDS ONE. The builder is rendered only by planActivate and by the operator's own
      // mutations, so `publish.changed` could only ever flip because THIS operator did something
      // — and the state the badge exists to report is the other one: a paired controller edits
      // the plan while the builder sits open. Without this the badge is correct and almost never
      // arrives (found in QA review; the frame's own scenario was the one it could not show).
      //
      // Deliberately NARROW. It re-renders the summary panel and nothing else, and only when
      // every one of these holds: the plan surface is showing, no item is selected (with one
      // selected the panel is the item inspector and the badge is not on screen), no dialog is
      // open, no lifecycle command is in flight, and the publish signature has ACTUALLY changed.
      // A poll that rebuilt the run sheet would eat in-flight clicks — the same reason render()
      // keys its own plan rebuild on a change signature.
      let planPublishSig = null;
      function planSyncPublishFromPoll(view) {
        const surf = document.getElementById("surface-plan");
        if (!surf || !surf.classList.contains("active")) return;
        if (!planLastView || planSelectedId !== null) return;
        if (document.querySelector(".pm-confirm-back")) return;
        if (planLifecycleBusy) return;
        const pub = planPublishState(view);
        const sig = pub ? pub.revision + "/" + pub.publishedRevision + "/" + pub.version + "/" + pub.changed : "none";
        if (sig === planPublishSig) return;
        planPublishSig = sig;
        planLastView = view;
        planClearInspector(view);
      }
      // Quinn — the same finding as the badge, on the other field. `planSyncPermission` runs
      // only from `planActivate` and after this operator's own mutation, so a role DEMOTION
      // arriving from the host left every edit control up until the operator happened to do
      // something — and then had each of them refused.
      //
      // This one rebuilds the WHOLE surface rather than the chrome alone, because the per-row
      // reorder buttons and drag handles are built by planRenderBuilder, not by
      // planSyncPermission: syncing the chrome only would have produced a surface wearing a
      // "View only" badge with live ↑/↓ buttons under it, which is worse than either state.
      //
      // A rebuild eats a click that lands in the same frame, which is why the publish poll above
      // refuses to do one. It is the right trade HERE and only here: this fires at most once per
      // permission change, and at that instant every control it could interrupt is one the host
      // is about to refuse anyway.
      let planViewerSig = null;
      function planViewerSignature(view) {
        const v = planViewer(view);
        return v.role + "/" + v.canEdit;
      }
      function planSyncViewerFromPoll(view) {
        const surf = document.getElementById("surface-plan");
        if (!surf || !surf.classList.contains("active")) return;
        if (!planLastView) return;
        if (document.querySelector(".pm-confirm-back")) return; // a dialog owns the surface
        if (planLifecycleBusy) return;
        const sig = planViewerSignature(view);
        if (planViewerSig === null) { planViewerSig = sig; return; } // first sight is a baseline, not a change
        if (sig === planViewerSig) return;
        planViewerSig = sig;
        planLastView = view;
        planRenderBuilder(view);
      }
      function planRenderBuilder(view) {
        const list = document.getElementById("plan-b-list");
        if (!list || !view) return; // not on the plan surface
        planLastView = view; // so a pure UI change (deselect) can re-render without a round-trip
        {
          // Keep the poll's signature in step with whatever was just drawn, so it never
          // re-renders over a state identical to the one on screen.
          const pubNow = planPublishState(view);
          planPublishSig = pubNow
            ? pubNow.revision + "/" + pubNow.publishedRevision + "/" + pubNow.version + "/" + pubNow.changed
            : "none";
          planViewerSig = planViewerSignature(view);
        }
        planSyncPermission(view);
        // Header counters. The planned total belongs HERE, next to the item count, because the pair
        // is what a reader checks against the rows (section 9: "8 items · 1:12:00" over 6 rows
        // summing 53:12 was the MAJOR). Empty collapses to the single AC-4 string "0 items · 0:00";
        // populated splits into "N items" + a right-aligned "planned H:MM:SS" per frame 608:925.
        const count = document.getElementById("plan-b-count");
        const total = document.getElementById("plan-b-total");
        const hdr = planSummaryOf(view);
        const planned = hdr.planned_total_secs;
        // The header counts the same thing the panel does — TRIGGERABLE rows, sections excluded.
        // Using view.items.length here read "9 items" beside a summary saying "Items 6": two
        // headline numbers describing the same run sheet and disagreeing, which is the §9 MAJOR.
        // The empty-CTA branch still keys off whether ANY row exists, so a plan of nothing but
        // dividers renders its dividers rather than the "add your first item" state.
        if (view.items.length) {
          if (count) count.textContent = hdr.items + " items";
          if (total) total.textContent = "planned " + planFmtTotal(planned);
        } else {
          if (count) count.textContent = "0 items · 0:00";
          if (total) total.textContent = "";
        }
        list.innerHTML = "";
        if (!view.items.length) {
          // Empty state (handoff §5, frame 611:124): a centered CTA, not a bare line. The four
          // designed starts — Create · Template · Duplicate · Import (WORKFLOWS B1) — are built
          // here, each either live or disabled WITH THE REASON IT CANNOT WORK. Nothing on this
          // frame is a no-op.
          const canEditEmpty = planCanEdit(view);
          const empty = document.createElement("div");
          empty.className = "plan-empty";
          const eh = document.createElement("h3");
          eh.className = "plan-empty-h";
          // The COPY follows the permission too, not just the controls. "Build your service
          // plan · Add songs, scriptures and presentations…" is an instruction, and telling
          // someone to do a thing their role forbids is worse than showing them the button.
          // UX-STATE-MATRIX's own view-only heading is "No service plan yet".
          eh.textContent = canEditEmpty ? "Build your service plan" : "No service plan yet";
          empty.appendChild(eh);
          if (canEditEmpty) {
            const es = document.createElement("p");
            es.className = "plan-empty-sub";
            es.textContent = "Add songs, scriptures, and presentations to the run sheet, then link content to each item.";
            empty.appendChild(es);
          } else {
            // View-only on an empty plan: nothing to follow and nothing this operator may
            // create, so the frame says so. No disabled buttons here — a permission is not a
            // "coming soon", and four controls it would then have to explain away is exactly
            // the "seeing controls they can't use" pain this frame exists to fix.
            const ro = document.createElement("p");
            ro.className = "plan-empty-note";
            ro.id = "plan-empty-viewonly";
            ro.textContent = "There's no plan to follow yet, and your role can't create one.";
            empty.appendChild(ro);
            list.appendChild(empty);
            planClearInspector(view);
            return;
          }
          const ec = document.createElement("button");
          ec.type = "button";
          ec.id = "plan-empty-add";
          ec.className = "pm-btn-primary";
          ec.textContent = "＋ Add first item";
          ec.onclick = () => {
            const first = document.querySelector("#plan-palette-btns .plan-palette-btn");
            if (first) first.focus();
          };
          empty.appendChild(ec);

          const acts = document.createElement("div");
          acts.className = "plan-empty-acts";
          const templates = planTemplateList(view);
          const lifecycle = planLifecycleAvailable(view);
          const mk = (id, label, onclick, reasonId) => {
            const b = document.createElement("button");
            b.type = "button";
            b.id = id;
            b.className = "pm-btn-ghost plan-empty-act";
            b.textContent = label;
            if (onclick) b.onclick = onclick;
            else {
              b.disabled = true;
              b.setAttribute("aria-describedby", reasonId);
            }
            acts.appendChild(b);
            return b;
          };
          mk("plan-empty-new", "Create a service…", lifecycle ? () => planNewPlan(planLastView) : null, "plan-empty-later");
          // A template picker with no templates to pick is an empty dialog, so the control is
          // disabled when the host reports none — the same three-state rule as everything else
          // on this surface, applied to a list rather than a flag.
          mk(
            "plan-empty-template",
            "Start from a template…",
            lifecycle && templates ? () => planTemplatePlan(planLastView) : null,
            templates || !lifecycle ? "plan-empty-later" : "plan-empty-no-templates"
          );
          // DISABLED BY DESIGN, not by dependency. `duplicate_plan` copies the plan that is OPEN,
          // which is right for "duplicate this service" (it lives in the Plan Summary) and wrong
          // for this frame: "Duplicate previous" wants a saved-plan LIBRARY to choose a past
          // service from, and this build persists exactly one plan row. There is no library and
          // no ticket for one, so the control states that instead of pretending.
          mk("plan-empty-duplicate", "Duplicate previous…", null, "plan-empty-no-library");
          mk("plan-empty-import", "Import a run sheet…", lifecycle ? () => planImportPlan(planLastView) : null, "plan-empty-later");
          // FR-139's portable bundle is a DIFFERENT thing from the run-sheet import above: it
          // carries items AND their media references. No such format exists in any layer, and
          // letting the run-sheet import stand in for it would ship an "Import" that silently
          // drops every operator's media.
          mk("plan-empty-bundle", "Import a plan bundle…", null, "plan-empty-no-bundle");
          empty.appendChild(acts);

          const reason = (id, text) => {
            const p = document.createElement("p");
            p.className = "plan-empty-later";
            p.id = id;
            p.textContent = text;
            empty.appendChild(p);
          };
          if (!lifecycle) reason("plan-empty-later", PLAN_NO_LIFECYCLE_REASON);
          else if (!templates) reason("plan-empty-no-templates", "This host reported no usable starter templates.");
          reason("plan-empty-no-library", "Duplicating a past service needs a saved-plan library. This build keeps one plan at a time.");
          reason("plan-empty-no-bundle", "A plan bundle carries items and their media together. That file format doesn't exist yet — paste a run sheet instead.");
          list.appendChild(empty);
          planClearInspector(view);
          return;
        }
        const last = view.items.length - 1;
        // Asked ONCE for the whole run sheet, from the host's own verdict. Every reorder
        // affordance below consumes THIS value; none of them re-reads the role.
        const canEdit = planCanEdit(view);
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
          // Reordering is an EDIT, so view-only omits the handle rather than leaving a grab
          // affordance that does nothing when grabbed.
          if (canEdit) {
            const handle = document.createElement("span");
            handle.className = "plan-b-handle";
            handle.textContent = "⠿";
            handle.setAttribute("aria-hidden", "true");
            handle.title = "Drag to reorder";
            handle.onpointerdown = (e) => planStartRowDrag(e, it.id, i, row);
            handle.onclick = (e) => e.stopPropagation(); // a handle interaction must not select the row
            row.appendChild(handle);
          }
          // Per-type accent bar (handoff §3). Purely a scanning cue — the type BADGE inside .main
          // carries the same information as text, so this is aria-hidden and never the only signal.
          const accent = document.createElement("span");
          accent.className = "plan-b-accent kind-" + it.kind;
          accent.setAttribute("aria-hidden", "true");
          row.appendChild(accent);
          row.appendChild(main);
          const tools = document.createElement("span");
          tools.className = "plan-b-tools";
          let up = null;
          let down = null;
          if (canEdit) {
            up = miniBtn(
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
            down = miniBtn(
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
          }
          // Owner + planned duration (handoff §3, FR-004). Both have been on PlanItemView all
          // along and were dropped on the floor here. Absent = unassigned / unplanned, so the
          // element is omitted rather than padded with a placeholder dash that reads as data.
          const meta = document.createElement("span");
          meta.className = "plan-b-meta";
          if (it.owner) {
            const own = document.createElement("span");
            own.className = "plan-b-owner";
            own.appendChild(srOnly("Owner: "));
            own.appendChild(document.createTextNode(it.owner));
            meta.appendChild(own);
          }
          // Unset = the element is OMITTED (86ak846ft AC-1: "without a gap or placeholder text").
          // UI-A1 FR-202 asks for a "—" placeholder instead; the two acceptance criteria conflict
          // and DECISION 86ak84cth owns it. Current behaviour stands until that lands.
          // aria-label carries the SPOKEN form (UI-A1 §211) — "five colon zero zero" is not useful.
          // A section is inert: its duration is excluded from the plan total, so rendering one on
          // the row would put a number in the column that the header total does not include.
          if (planHasDuration(it) && it.kind !== "section") {
            const dur = document.createElement("span");
            dur.className = "plan-b-dur";
            dur.textContent = planFmtDuration(it.planned_secs);
            dur.setAttribute("aria-label", "Planned " + planSpokenDuration(it.planned_secs));
            meta.appendChild(dur);
          }
          if (meta.childElementCount) row.appendChild(meta);
          if (up && down) {
            tools.appendChild(up);
            tools.appendChild(down);
          }
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
            // Gated on the same verdict as the buttons: hiding the buttons while leaving the
            // keyboard path live would make the restriction a lie for keyboard users only.
            if (canEdit && e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
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
        if (sel) planRenderInspector(sel, view);
        else planClearInspector(view);
      }
      // Right panel with NOTHING selected = Plan Summary (frame 608:875). Selecting an item swaps
      // it for the item inspector; the heading swaps with it so the panel always says which one
      // this is.
      // The right panel swaps its ENTIRE subtree between PLAN SUMMARY and ITEM, so keyboard focus
      // inside it would fall to <body> (WCAG 2.4.3). If the operator was focused in there, move
      // focus to the panel itself — it is aria-labelledby the heading, so AT announces which panel
      // they have landed in rather than going silent.
      function planKeepPanelFocus(box, rebuild) {
        const hadFocus = !!(box && box.contains(document.activeElement));
        rebuild();
        if (!hadFocus) return;
        const panel = document.getElementById("plan-insp-panel");
        if (panel && panel.focus) panel.focus();
      }
      // While the plan is loading — or after it failed to open — the right panel must NOT keep
      // reporting the previous plan's figures beside a run sheet that says otherwise. Stale numbers
      // next to "Couldn't open the plan" are worse than no numbers.
      function planBlankSummary(msg) {
        const box = document.getElementById("plan-b-insp");
        if (!box) return;
        planSetInspHeading("PLAN SUMMARY");
        box.innerHTML = "";
        const p = document.createElement("p");
        p.className = "plan-sum-blank";
        p.setAttribute("role", "status");
        p.textContent = msg;
        box.appendChild(p);
      }
      function planSetInspHeading(text) {
        const h = document.getElementById("plan-insp-h");
        if (h) h.textContent = text;
      }
      function planSumRow(label, value, opts) {
        const row = document.createElement("div");
        row.className = "plan-sum-row" + ((opts && opts.cls) ? " " + opts.cls : "");
        const l = document.createElement("span");
        l.className = "plan-sum-label";
        l.textContent = label;
        const v = document.createElement("span");
        v.className = "plan-sum-value";
        v.textContent = value;
        row.appendChild(l);
        row.appendChild(v);
        return row;
      }
      // =======================================================================================
      // PLAN LIFECYCLE — the send sites. One place per command, each reachable from exactly one
      // control, each refusing to run twice and each reporting what the host actually said.
      // =======================================================================================

      // One lifecycle command in flight at a time. These commands REPLACE the plan; two of them
      // racing would leave the operator looking at whichever view came back last with no way to
      // tell which one they got.
      let planLifecycleBusy = false;

      // The plan surface's own feedback strip. The presentation surface's #pm-toast lives inside
      // that surface's subtree, so it is not visible from here — this is the plan surface's
      // equivalent, and it is REBUILT rather than re-texted on each call: a live region whose
      // role changes between status and alert does not reliably re-announce, and "Published"
      // arriving in the element that last said "Couldn't publish" is worth announcing.
      function planNotice(kind, message) {
        const slot = document.getElementById("plan-notice");
        if (!slot) return;
        slot.innerHTML = "";
        if (!message) return;
        const p = document.createElement("p");
        p.className = "plan-notice plan-notice-" + kind;
        p.setAttribute("role", kind === "alert" ? "alert" : "status");
        p.textContent = message;
        slot.appendChild(p);
      }

      // Run one lifecycle command and re-render from the view it returns.
      //
      // On failure the HOST'S OWN MESSAGE is shown. The five commands answer a bad name with
      // Denied{bad_request}, and the operator needs to see which rule they broke — a generic
      // "something went wrong" here would turn a fixable typo into an unexplained dead button.
      // The selection is dropped first because every one of these commands can replace the whole
      // run sheet: keeping a stale id would re-open an inspector onto an item that no longer
      // exists.
      // `replacesPlan` is spelled out at every call site rather than defaulted, because FOUR of
      // the five commands replace the run sheet and ONE does not — and the one that does not is
      // the one a shared loop silently gets wrong. `publish_plan` moves a marker; the plan, its
      // item ids and the operator's selection all survive it, so clearing the selection there
      // would throw them back to the Plan Summary for no reason they could name. The other four
      // mint new ids, and keeping a stale one would re-open an inspector onto an item that no
      // longer exists.
      async function planLifecycleRun(what, replacesPlan, fn) {
        if (planLifecycleBusy) {
          // The panel's whole principle is that a control never looks live and silently does
          // nothing. In this window five of them did — the second press was discarded with no
          // notice, no error and nothing in the live region.
          planNotice("status", "Still finishing the last change. Try again in a moment.");
          return false;
        }
        planLifecycleBusy = true;
        try {
          const v = await fn();
          if (!v || !Array.isArray(v.items)) throw new Error("the host did not return a plan");
          if (replacesPlan) {
            planSelectedId = null;
            planFocusAfterRender = null;
          }
          planRenderBuilder(v);
          return true;
        } catch (e) {
          console.error(e);
          // A Tauri command declared `Result<_, String>` rejects with the bare STRING, not an
          // Error, so both shapes are unwrapped. The host's own words are what make a refused
          // name fixable.
          const detail = e && e.message ? e.message : typeof e === "string" ? e : "";
          planNotice("alert", "Couldn't " + what + (detail ? " — " + detail : "") + ".");
          return false;
        } finally {
          planLifecycleBusy = false;
        }
      }

      // --- publish_plan (frame 608:875, FR-006) ---------------------------------------------
      //
      // COPY NOTE. The shipped button reads "Publish to team", but SERVICE-PLAN-2.0-HANDOFF.md:105
      // describes publish as a purely LOCAL builder-to-console hand-off, which is also FR-006's
      // actual acceptance criterion ("operator opens identical ordered plan"). That conflict is
      // the owner's to settle, so the designed label is left exactly as it is and every sentence
      // written HERE is network-neutral: nothing below claims the plan was sent anywhere.
      function planPublish(view) {
        const pub = planPublishState(view);
        // The same send-site guard the other four make. Unreachable today — view-only never
        // renders this button — but an asymmetric guard across five sibling send sites is the
        // shape a real hole hides in, and the cost of closing it is one clause.
        if (!pub || !planCanEdit(view)) return;
        planLifecycleRun("publish this plan", false, () => invoke("publish_plan")).then((ok) => {
          if (ok) planNotice("status", "Plan published. The Live Console opens this run sheet for the service.");
        });
      }

      // --- new_plan --------------------------------------------------------------------------
      function planNewPlan(view) {
        if (!planLifecycleAvailable(view) || !planCanEdit(view)) return;
        pmPrompt({
          title: "Create a service",
          describe: "Starts an empty run sheet under this name. The plan currently open is replaced.",
          label: "Service name",
          value: "",
          confirmLabel: "Create",
          validate: planNameProblem,
          onConfirm: (name) => {
            planLifecycleRun("create the service", true, () => invoke("new_plan", { name: name.trim() })).then((ok) => {
              if (ok) planNotice("status", "New service created. Add your first item to build the run sheet.");
            });
          },
        });
      }

      // --- template_plan ---------------------------------------------------------------------
      //
      // The list comes from the HOST (`plan_templates`). The picker never invents an id the host
      // cannot build from, and it reports each template's SIZE, which is the only thing about a
      // template's contents that crosses the wire.
      //
      // The NAME FIELD IS NOT OPTIONAL CHROME. `TemplatePlan { template, name }` requires a
      // valid non-blank name and the host does nothing to default it — a template's own name is
      // display text, not a fallback — so a picker that only chose a template would be refused
      // with Denied{bad_request} every time. It is seeded from the chosen template so the
      // obvious gesture still works in one keystroke (UX-FLOWS Flow 1 step 1: pick a template,
      // set the name).
      function planTemplatePlan(view) {
        const templates = planTemplateList(view);
        if (!templates || !planLifecycleAvailable(view) || !planCanEdit(view)) return;
        let chosen = templates[0];
        let nameInput = null;
        pmPrompt({
          title: "Start from a template",
          describe: "Creates a run sheet with the template's items already in order. Rename them, then link content to each one.",
          label: "Service name",
          value: templates[0].name,
          confirmLabel: "Create",
          body: (extra, input) => {
            nameInput = input;
            input.oninput = () => { input.dataset.touched = "1"; };
            const group = document.createElement("div");
            group.className = "plan-tpl-list";
            group.setAttribute("role", "radiogroup");
            group.setAttribute("aria-label", "Template");
            templates.forEach((t, i) => {
              const id = "plan-tpl-" + i;
              const row = document.createElement("label");
              row.className = "plan-tpl-row";
              row.htmlFor = id;
              const r = document.createElement("input");
              r.type = "radio";
              r.name = "plan-template";
              r.id = id;
              r.value = t.id;
              r.checked = i === 0;
              r.onchange = () => {
                chosen = t;
                // Follow the chosen template's name unless the operator has typed their own.
                // Overwriting a typed name would silently discard what they meant to call it.
                if (nameInput && !nameInput.dataset.touched) nameInput.value = t.name;
              };
              const txt = document.createElement("span");
              txt.className = "plan-tpl-txt";
              const nm = document.createElement("span");
              nm.className = "plan-tpl-name";
              nm.textContent = t.name;
              const ct = document.createElement("span");
              ct.className = "plan-tpl-count";
              // `items` is a COUNT reported by the host, never a list rendered from the client.
              ct.textContent = t.items + (t.items === 1 ? " item" : " items");
              txt.appendChild(nm);
              txt.appendChild(ct);
              row.appendChild(r);
              row.appendChild(txt);
              group.appendChild(row);
            });
            extra.appendChild(group);
          },
          validate: (v) => planNameProblem(v),
          onConfirm: (name) => {
            planLifecycleRun("start from that template", true, () =>
              invoke("template_plan", { template: chosen.id, name: name.trim() })
            ).then((ok) => {
              if (ok) planNotice("status", "Service created from “" + chosen.name + "”. Rename the items and link content to each one.");
            });
          },
        });
      }

      // --- duplicate_plan (FR-005) ------------------------------------------------------------
      //
      // Copies the plan that is OPEN, under a new name. That is "duplicate this service", and it
      // is why this control lives beside the open plan's summary rather than in the empty state:
      // the empty state's designed "Duplicate previous" wants a saved-plan LIBRARY to pick from,
      // and this build persists exactly one plan row. See the empty state for that affordance.
      function planDuplicatePlan(view) {
        if (!planLifecycleAvailable(view) || !planCanEdit(view)) return;
        const base = view && typeof view.plan_name === "string" ? view.plan_name : "";
        pmPrompt({
          title: "Duplicate this service",
          describe: "Copies the current run sheet under a new name. The copy is independent — editing it never changes the original.",
          label: "New name",
          // A DISTINCT default, deliberately. Duplicating under the CURRENT name is accepted by
          // the host as a true no-op — it Acks and nothing changes — so an operator who presses
          // Enter on a prefilled unchanged name would be told "Service duplicated" over a plan
          // that had not moved. Prefilling "… (copy)" means the obvious gesture does the
          // obvious thing, and the validator below covers the case where they type it back.
          value: base ? base + " (copy)" : "",
          confirmLabel: "Duplicate",
          // A duplicate REPLACES the open run sheet with the copy, and it can be pressed
          // mid-service. The audience is unaffected — the host carries the live slide across a
          // plan swap — but an operator about to do this while something is on air deserves to
          // be told which of those two things is true, rather than discovering it. Stated, not
          // blocked: duplicating a service that is running is a legitimate thing to want.
          warning: planLiveItemTitle(view)
            ? "“" + planLiveItemTitle(view) + "” is LIVE. The copy replaces the run sheet you are editing; the audience output is unaffected."
            : null,
          validate: (v) => {
            const why = planNameProblem(v);
            if (why) return why;
            // Refused HERE rather than sent. The host would accept it and do nothing, and this
            // client cannot honestly report that outcome: "duplicated" would be false and
            // silence would look like a broken button. Compared trimmed, because that is the
            // form the host compares.
            if (base && v.trim() === base.trim()) {
              return "That is the current name. Give the copy a different one.";
            }
            return null;
          },
          onConfirm: (name) => {
            planLifecycleRun("duplicate this service", true, () => invoke("duplicate_plan", { name: name.trim() })).then((ok) => {
              if (ok) planNotice("status", "Service duplicated. You are now editing the copy.");
            });
          },
        });
      }

      // --- import_plan -------------------------------------------------------------------------
      //
      // A RUN-SHEET ITEM LIST, and nothing more. `import_plan` carries kind + title (+ optional
      // owner and duration) per item; CONTENT LINKS are set afterwards with the existing
      // SetItemContent, so there is deliberately no link handling on this path.
      //
      // This is NOT FR-139. That requirement wants a portable bundle carrying items AND their
      // media references; no such format exists in any layer, and the empty state offers it as a
      // named, disabled affordance with that reason rather than letting this dialog stand in for
      // it. Conflating the two would ship an "Import" that silently loses every operator's media.
      //
      // WHY EACH LINE MUST NAME ITS TYPE. The obvious kindness — treat a bare line as some
      // default type — is the wrong one. Every default is wrong for most lines (a plan of
      // announcements triggers nothing an operator wants; a plan of sections triggers nothing at
      // all, because a section is inert), and a mis-typed item is silent: it looks imported and
      // behaves wrongly on service day. An unrecognised line is reported by line number instead,
      // with the accepted types listed in the dialog.
      const PLAN_IMPORT_EXAMPLE = "Announcement: Welcome\nSong: Great Are You Lord\nScripture: Romans 8:28\nSection: Sermon\nSong: Closing Song";

      // Parse pasted text into wire items. Returns { items, problems } — problems are stated per
      // LINE so the operator can fix the paste rather than re-reading the whole thing.
      //
      // Kinds are matched against PLAN_ADD_KINDS, which is the same table the Add-item palette
      // renders from and is the wire tag set. Both the display label ("Presentation") and the
      // wire tag ("slide_group") are accepted, because the operator is reading labels on screen
      // while the wire carries tags.
      // Bounded in BOTH accumulators and in work done. The loop used to run to the end of the
      // paste and only then compare `items.length` to the cap, so the exact count in the error
      // message ("this paste has 1000000") was itself proof that the whole intermediate had been
      // built — and `validate` re-runs the parse on every submit attempt. Stopping at the cap
      // makes the cost a function of the CAP rather than of the clipboard, and "more than 500"
      // is all the operator needs to know. `problems` is bounded for the same reason: only the
      // first is ever shown.
      const PLAN_IMPORT_MAX_PROBLEMS = 20;
      function planParseRunSheet(text) {
        const items = [];
        const problems = [];
        const note = (msg) => { if (problems.length < PLAN_IMPORT_MAX_PROBLEMS) problems.push(msg); };
        const lines = String(text == null ? "" : text).split(/\r\n|\r|\n/);
        for (let i = 0; i < lines.length; i++) {
          if (items.length > PLAN_MAX_ITEMS) break; // one past the cap is enough to refuse it
          const raw = lines[i];
          if (!raw.trim()) continue; // blank lines are spacing in a pasted order of service
          const at = raw.indexOf(":");
          const label = at < 0 ? "" : raw.slice(0, at).trim().toLowerCase();
          const match = at < 0 ? null : PLAN_ADD_KINDS.find((k) => k[0] === label || k[1].toLowerCase() === label);
          if (!match) {
            note("Line " + (i + 1) + ": start the line with a type, for example “Song: " + raw.trim().slice(0, 40) + "”.");
            continue;
          }
          const title = raw.slice(at + 1).trim();
          // Item titles cross the same untrusted boundary as the plan name and the host applies
          // the same rule to them, so they are checked by the same function — not by a second,
          // looser copy of it written for this path.
          const why = planNameProblem(title);
          if (why) {
            note("Line " + (i + 1) + ": " + why.charAt(0).toLowerCase() + why.slice(1));
            continue;
          }
          items.push({ kind: match[0], title: title });
        }
        if (items.length > PLAN_MAX_ITEMS) {
          problems.push("A plan holds at most " + PLAN_MAX_ITEMS + " items; this paste has more.");
        }
        return { items: items, problems: problems };
      }

      function planImportPlan(view) {
        if (!planLifecycleAvailable(view) || !planCanEdit(view)) return;
        let area = null;
        pmPrompt({
          title: "Import a run sheet",
          describe: "Paste one item per line, each starting with its type. Owners, durations and content links are set afterwards in the item inspector.",
          label: "Service name",
          value: "",
          confirmLabel: "Import",
          body: (extra) => {
            const lab = document.createElement("label");
            lab.className = "pm-insp-lbl";
            lab.htmlFor = "plan-import-text";
            lab.textContent = "Run sheet";
            area = document.createElement("textarea");
            area.id = "plan-import-text";
            area.className = "pm-insp-ctrl plan-import-text";
            area.rows = 8;
            area.placeholder = PLAN_IMPORT_EXAMPLE;
            area.setAttribute("aria-describedby", "plan-import-kinds");
            const kinds = document.createElement("p");
            kinds.id = "plan-import-kinds";
            kinds.className = "plan-import-kinds";
            kinds.textContent = "Types: " + PLAN_ADD_KINDS.map((k) => k[1]).join(" · ");
            extra.appendChild(lab);
            extra.appendChild(area);
            extra.appendChild(kinds);
          },
          validate: (v) => {
            const why = planNameProblem(v);
            if (why) return why; // the NAME is at fault, so the name field is marked
            // ...and everything below is a RUN-SHEET fault, so it is reported against the
            // textarea. Blaming the name field for a bad paste marks a valid name invalid and
            // moves focus away from the control the operator has to fix.
            const parsed = planParseRunSheet(area ? area.value : "");
            if (parsed.problems.length) return { message: parsed.problems[0], field: area };
            if (!parsed.items.length)
              return { message: "Paste at least one item, for example “Song: Great Are You Lord”.", field: area };
            return null;
          },
          onConfirm: (name) => {
            const parsed = planParseRunSheet(area ? area.value : "");
            planLifecycleRun("import that run sheet", true, () =>
              invoke("import_plan", { name: name.trim(), items: parsed.items })
            ).then((ok) => {
              if (ok)
                planNotice(
                  "status",
                  "Imported " + parsed.items.length + (parsed.items.length === 1 ? " item" : " items") +
                    ". Link content to each one to finish the plan."
                );
            });
          },
        });
      }

      // A control that cannot work yet: present, disabled, and pointing at the REASON. Never
      // hidden (an operator looking for Publish must be able to find it and learn when it
      // arrives) and never wired to a no-op (a control that looks live and silently does nothing
      // is worse than one that says it is not ready).
      function planDisabledAction(id, label, reasonId) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pm-btn-ghost plan-sum-btn";
        b.id = id;
        b.textContent = label;
        b.disabled = true;
        b.setAttribute("aria-describedby", reasonId);
        return b;
      }
      function planReasonNote(id, text, cls) {
        const p = document.createElement("p");
        p.className = cls || "plan-sum-later";
        p.id = id;
        p.textContent = text;
        return p;
      }

      // ---------------------------------------------------------------------------------------
      // SEAM — the Plan Summary's WRITE actions (86ak8467m owns these; 86ak846ft owns the panel).
      // Frame 608:875 draws three: Run pre-service check, Publish to team, Open in Live. Only
      // "Open in Live" is a pure surface switch and works today; the other two need the plan
      // lifecycle backend (86ajy0hwg) that does not exist yet.
      //
      // They ship DISABLED with a stated reason rather than hidden — an operator looking for
      // Publish should find it and learn when it arrives — and never wired to a no-op, because a
      // control that looks live and silently does nothing is worse than one that says it is not
      // ready. 86ak8467m enables them HERE, in this function, and must not rebuild the panel.
      //
      // 86ak8467m: Publish and Duplicate are now live WHEN THE HOST REPORTS THE CAPABILITY, and
      // the panel carries the plan's publication state and the frame-612:1020 change badge. The
      // pre-service check stays disabled — no command in this contract performs one.
      // ---------------------------------------------------------------------------------------
      function planSummaryActions(box, view) {
        const canEdit = planCanEdit(view);
        const pub = planPublishState(view);
        const lifecycle = planLifecycleAvailable(view);

        // --- Publication state + the change badge (frame 612:1020) ---------------------------
        // Rendered only when the host REPORTS `publish`. With the field absent nothing may be
        // said about publication at all: no version, no draft label, and above all no badge.
        if (pub) {
          const state = document.createElement("div");
          state.className = "plan-pub" + (pub.changed ? " is-changed" : pub.published ? " is-published" : "");
          const line = document.createElement("p");
          line.className = "plan-pub-line";
          line.id = "plan-pub-line";
          // THE BADGE IS TESTED FIRST, and it consumes `pub.changed` — the one expression in
          // which "published AND edited since" is defined (planPublishState). It deliberately
          // does NOT re-derive `!pub.published` here.
          //
          // That ordering is load-bearing, and this is the second attempt at it. The first wrote
          // `if (!pub.published) … else if (pub.changed)`, which reads identically and is not: it
          // re-assembles the conjunction beside the code under test, so deleting `published &&`
          // from planPublishState left the suite completely green (the mutation battery caught
          // it; CLAUDE.md's 86ak643rc trap, exactly). With the badge consuming the predicate
          // directly, breaking the predicate breaks the badge — which is the only way this rule
          // is actually guarded.
          if (pub.changed) {
            const b = document.createElement("span");
            b.className = "plan-pub-badge";
            b.id = "plan-pub-changed";
            b.textContent = "⟳ Plan updated";
            state.appendChild(b);
            line.textContent = "Edited since version " + pub.version + " was published.";
          } else if (pub.published) {
            line.textContent = "Published · version " + pub.version;
          } else {
            line.textContent = "Draft · not published yet";
          }
          state.appendChild(line);
          box.appendChild(state);
        }

        // --- Pre-service check: still not built, still honest --------------------------------
        const preNote = planReasonNote(
          "plan-sum-precheck-later",
          "The pre-service check isn't built yet."
        );
        const pre = planDisabledAction("plan-sum-precheck", "✓ Run pre-service check", "plan-sum-precheck-later");
        box.appendChild(pre);
        box.appendChild(preNote);

        // --- Publish (frame 608:875, FR-006) -------------------------------------------------
        // View-only HIDES it (UX-STATE-MATRIX:111 — hidden, not greyed, so it also leaves the
        // tab order). Reported-but-unavailable DISABLES it with the reason.
        if (canEdit) {
          if (lifecycle && pub) {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "pm-btn-ghost plan-sum-btn";
            b.id = "plan-sum-publish";
            // The DESIGNED label, left exactly as drawn. Whether it should keep network-implying
            // wording for a local hand-off is an open owner question (see planPublish).
            b.textContent = "↑ Publish to team";
            b.setAttribute(
              "aria-describedby",
              pub.changed ? "plan-pub-line" : "plan-sum-publish-hint"
            );
            b.onclick = () => planPublish(planLastView);
            box.appendChild(b);
            if (!pub.changed) {
              box.appendChild(
                planReasonNote(
                  "plan-sum-publish-hint",
                  pub.published
                    ? "Publishing again hands the current run sheet to the Live Console."
                    : "Publishing hands this run sheet to the Live Console for the service.",
                  "plan-sum-hintline"
                )
              );
            }
            const dup = document.createElement("button");
            dup.type = "button";
            dup.className = "pm-btn-ghost plan-sum-btn";
            dup.id = "plan-sum-duplicate";
            dup.textContent = "⧉ Duplicate this service";
            dup.onclick = () => planDuplicatePlan(planLastView);
            box.appendChild(dup);
          } else {
            box.appendChild(planDisabledAction("plan-sum-publish", "↑ Publish to team", "plan-sum-later"));
            box.appendChild(planDisabledAction("plan-sum-duplicate", "⧉ Duplicate this service", "plan-sum-later"));
            box.appendChild(planReasonNote("plan-sum-later", PLAN_NO_LIFECYCLE_REASON));
          }
        }

        // --- Open in Live: a pure surface switch, never a go-live ----------------------------
        // Design-QA §9 rejected an enabled write-looking action on the view-only frame, so in
        // view-only this reads as the passive thing it actually is. It still NAVIGATES: watching
        // the console is exactly what a view-only operator is there to do, and taking that away
        // would remove a capability the permission never restricted.
        const live = document.createElement("button");
        live.type = "button";
        live.className = (canEdit ? "pm-btn-primary" : "pm-btn-ghost") + " plan-sum-btn";
        live.id = "plan-sum-live";
        live.textContent = canEdit ? "▶ Open in Live" : "▶ Follow in Live";
        live.onclick = () => showSurface("console");
        box.appendChild(live);
      }
      function planClearInspector(view) {
        const box = document.getElementById("plan-b-insp");
        if (!box) return;
        planKeepPanelFocus(box, () => planRenderSummaryInto(box, view));
      }
      function planRenderSummaryInto(box, view) {
        planSetInspHeading("PLAN SUMMARY");
        box.innerHTML = "";
        const sum = planSummaryOf(view);
        const card = document.createElement("div");
        card.className = "plan-sum-card";
        // `partial` is read from the host summary, never computed here. It needs `planned_items`
        // alongside it: ZERO is a legitimate duration meaning "instant" (spec §4.1), so a total of
        // 0 does not imply nothing is set. With nothing planned at all the figure is meaningless
        // and reads "—"; with something planned it is a real but incomplete sum.
        const partial = sum.partial === true;
        const nothingPlanned = partial && sum.planned_items === 0;
        const totalText = (nothingPlanned ? "—" : planFmtTotal(sum.planned_total_secs)) + (partial ? " · partial" : "");
        const totalRow = planSumRow("Total time", totalText, { cls: "plan-sum-total" + (partial ? " is-partial" : "") });
        totalRow.querySelector(".plan-sum-value").setAttribute(
          "aria-label",
          (nothingPlanned ? "Total unknown" : "Total " + planSpokenDuration(sum.planned_total_secs)) +
            (partial ? ", partial — some items have no duration set" : "")
        );
        card.appendChild(totalRow);
        card.appendChild(planSumRow("Items", String(sum.items)));
        card.appendChild(planSumRow("Songs", String(sum.songs)));
        card.appendChild(planSumRow("Scripture", String(sum.scripture)));
        card.appendChild(planSumRow("Presentations", String(sum.presentations)));
        card.appendChild(planSumRow("Media", String(sum.media)));
        card.appendChild(planSumRow("Announcements", String(sum.announcements)));
        // Timers and Sections are rendered too, so the per-kind rows ALWAYS sum to Items. Omitting
        // them (the demo plan in the frame has none) leaves a reader doing arithmetic that does not
        // add up — the same class of defect design-QA §9 rejected these frames for.
        card.appendChild(planSumRow("Timers", String(sum.timers)));
        // No Sections row: frame 608:875 has none, and `items` excludes sections, so a Sections
        // line here would make the per-kind rows stop summing to Items — the exact "figures that
        // do not add up" defect. The count is still carried on the summary object for other uses.
        // Missing content carries a ⚠ in the TEXT when non-zero, not just a colour — the count is
        // the one figure here that means "something is broken" (WCAG 1.4.1).
        card.appendChild(
          planSumRow("Missing content", sum.missing ? "⚠ " + sum.missing : "0", sum.missing ? { cls: "plan-sum-warn" } : null)
        );
        card.appendChild(planSumRow("Assigned", sum.assigned + " / " + sum.items));
        box.appendChild(card);

        planSummaryActions(box, view);

        const note = document.createElement("p");
        note.className = "plan-sum-hint";
        note.textContent = "Select an item to edit it and link its scripture or presentation.";
        box.appendChild(note);
      }
      // A richer linked-deck card for the inspector (frame 608:124): name + slide count, resolved
      // from the loaded deck list; a deleted deck renders the missing treatment.
      function planDeckCard(link) {
        const card = document.createElement("div");
        card.className = "plan-deck-card";
        const name = planDeckName(link.id);
        if (planLinkState(link) === "missing") {
          card.classList.add("missing");
          const w = document.createElement("div");
          w.className = "plan-deck-card-name link-missing";
          // The last known good name, captured when the link was made. The deck's library row
          // is gone, so this is the only thing that can still say WHICH presentation vanished.
          w.textContent = link.label ? "⚠ “" + link.label + "” is missing" : "⚠ presentation missing";
          const m = document.createElement("div");
          m.className = "plan-deck-card-meta";
          m.textContent = link.label
            ? "“" + link.label + "” was deleted from the library. Relink a deck or remove this item."
            : "The linked deck was deleted from the library — relink it.";
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
      function planRenderInspector(it, view) {
        const box = document.getElementById("plan-b-insp");
        if (!box) return;
        planKeepPanelFocus(box, () => planRenderInspectorInto(box, it, view));
      }
      // The item inspector. Frame 612:342 calls for a READ-ONLY inspector under view-only: the
      // item's facts still read, every control that would change them is absent. `view` may be
      // undefined for a caller that has none, and planCanEdit answers "yes" to that — an absent
      // verdict is not a restriction.
      function planRenderInspectorInto(box, it, view) {
        const canEdit = planCanEdit(view);
        planSetInspHeading("ITEM");
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
        box.appendChild(tl);
        if (canEdit) {
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
          box.appendChild(ti);
        } else {
          // STATIC TEXT, not a read-only input. A field that looks like a field and refuses to
          // accept typing is the "controls they can't use" complaint in a different costume.
          const tv = document.createElement("p");
          tv.className = "plan-insp-ro";
          tv.id = "plan-insp-title-ro";
          tv.textContent = it.title;
          box.appendChild(tv);
        }
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
          // Linking and unlinking are plan EDITS; only "Open in editor" below is navigation, and
          // navigation is not what this permission restricts.
          if (canEdit) {
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
          }
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
          if (it.link && canEdit) {
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
        if (canEdit) {
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
        }
        const note = document.createElement("p");
        note.className = "plan-insp-note";
        note.textContent = canEdit
          ? "🔒 Editing here never changes Live. Open in Live loads the plan into the console."
          : "🔒 View only — you can read this item and follow the service. Your role can't change the plan.";
        box.appendChild(note);
      }

      let pmLibDecks = [], pmLibOpenId = null, pmLibPersistent = true, pmLibQuery = "", pmLibSort = "name", pmLibMenuCleanup = null;
      // Deck ids the host says an undo could ACTUALLY put back. The trash is bounded (8 entries /
      // 1.5MB), so this shrinks as deletes age out and a very large deck may never enter it at all.
      // Undo is offered from THIS list — never from "the last delete", which is how you ship an
      // Undo button that fails.
      let pmLibRestorable = [];
      const pmLibBody = () => document.querySelector("#surface-presentation .pm-body");
      // Presentation surface has three modes (Design 2.0 browse/present/edit): the Library list, the
      // slide GRID, and the authoring EDITOR (.pm-body). pmSetMode toggles which one is visible.
      let pmMode = "library";
      function pmSetMode(mode) {
        pmMode = mode;
        const lib = pmEl("pm-library"); if (lib) lib.hidden = mode !== "library";
        const grid = pmEl("pm-grid"); if (grid) grid.hidden = mode !== "grid";
        const b = pmLibBody(); if (b) b.style.display = mode === "editor" ? "" : "none";
        // Both topbar actions act on the OPEN deck, so neither means anything while the operator is
        // browsing the library: nothing is staged to present, and per-card actions belong to the ⋯
        // menu there. HIDDEN rather than disabled, so they leave the tab order too (WCAG 2.4.3) —
        // a disabled control still reads as "this should work" to a keyboard operator.
        const pres = pmEl("pm-present"); if (pres) pres.hidden = mode === "library";
        const atp = pmEl("pm-addtoplan"); if (atp) atp.hidden = mode === "library";
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
        pmLibRestorable = (view && view.restorable) || [];
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
        // PME-055/PME-014: the topbar `▶ Present` control (built for the OPEN deck) covers half
        // of "present a deck" — this closes the other half, presenting a deck straight off its
        // library card without first opening it in the editor.
        item("Present", () => pmLibPresent(deck.id));
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
      // PME-053 — "Start from": Blank deck / Duplicate an existing presentation / From a
      // template (later, honest disabled affordance — no template model exists yet, PME-052/
      // OUT-009). Mirrors planTemplatePlan's radiogroup-with-picker pattern (the Name field
      // follows the chosen source until the operator types their own, via the same
      // `dataset.touched` convention) rather than inventing a second one.
      function pmLibNew() {
        const decks = (pmLibDecks || []).slice().sort((a, b) => (a.name || "").toLowerCase().localeCompare((b.name || "").toLowerCase()));
        let startFrom = "blank";
        let dupSourceId = decks.length ? decks[0].id : null;
        let nameInput = null;
        pmPrompt({
          title: "New presentation", label: "Name", value: "Untitled presentation", confirmLabel: "Create presentation",
          body: (extra, input) => {
            nameInput = input;
            input.oninput = () => { input.dataset.touched = "1"; };
            const group = document.createElement("div");
            group.className = "pm-startfrom";
            group.setAttribute("role", "radiogroup");
            group.setAttribute("aria-label", "Start from");
            // A flex-parented <select> collapses to zero width in WKWebView and the Blink gate
            // cannot see it (the same trap plan-tpl-list's own comment above already documents
            // for this exact dialog) — so the deck picker is a nested radio list, not a <select>.
            const dupPicker = document.createElement("div");
            dupPicker.className = "pm-startfrom-picker";
            dupPicker.setAttribute("role", "radiogroup");
            dupPicker.setAttribute("aria-label", "Presentation to copy");
            dupPicker.hidden = true;
            const followSource = (d) => { if (d && nameInput && !nameInput.dataset.touched) nameInput.value = d.name + " copy"; };
            decks.forEach((d, i) => {
              const rid = "pm-startfrom-src-" + i;
              const r = document.createElement("label");
              r.className = "pm-startfrom-picker-row";
              r.htmlFor = rid;
              const radio = document.createElement("input");
              radio.type = "radio"; radio.name = "pm-startfrom-src"; radio.id = rid; radio.value = String(d.id);
              radio.checked = i === 0;
              radio.onchange = () => { dupSourceId = d.id; followSource(d); };
              const txt = document.createElement("span"); txt.className = "pm-startfrom-picker-txt";
              const nm = document.createElement("span"); nm.className = "pm-startfrom-picker-name"; nm.textContent = d.name || "Untitled presentation";
              const ct = document.createElement("span"); ct.className = "pm-startfrom-picker-meta"; ct.textContent = (d.slides || 0) + ((d.slides === 1) ? " slide" : " slides");
              txt.appendChild(nm); txt.appendChild(ct);
              r.appendChild(radio); r.appendChild(txt);
              dupPicker.appendChild(r);
            });
            const row = (id, label, sub, checked, disabled, reasonTitle) => {
              const r = document.createElement("label");
              r.className = "pm-startfrom-row" + (disabled ? " pm-later" : "");
              r.htmlFor = id;
              if (disabled && reasonTitle) r.title = reasonTitle;
              const radio = document.createElement("input");
              radio.type = "radio"; radio.name = "pm-startfrom"; radio.id = id; radio.value = id;
              radio.checked = checked; if (disabled) radio.disabled = true;
              radio.onchange = () => {
                startFrom = id === "pm-startfrom-dup" ? "duplicate" : "blank";
                dupPicker.hidden = startFrom !== "duplicate";
                if (startFrom === "duplicate") followSource(decks.find((d) => d.id === dupSourceId));
                else if (!nameInput.dataset.touched) nameInput.value = "Untitled presentation";
              };
              const txt = document.createElement("span"); txt.className = "pm-startfrom-txt";
              const nm = document.createElement("span"); nm.className = "pm-startfrom-label"; nm.textContent = label;
              const sb = document.createElement("span"); sb.className = "pm-startfrom-sub"; sb.textContent = sub;
              txt.appendChild(nm); txt.appendChild(sb);
              r.appendChild(radio); r.appendChild(txt);
              return r;
            };
            group.appendChild(row("pm-startfrom-blank", "Blank deck", "One empty slide, ready to edit.", true, false));
            group.appendChild(row("pm-startfrom-dup", "Duplicate an existing presentation", "Copy slides + theme from another deck.", false, decks.length === 0, decks.length === 0 ? "No presentations exist yet to duplicate." : null));
            group.appendChild(dupPicker);
            group.appendChild(row("pm-startfrom-tpl", "From a template", "Themed starters (sermon, song, liturgy) — a later increment.", false, true, "Themed starters are a later increment."));
            extra.appendChild(group);
          },
          onConfirm: async (name) => {
            try {
              if (startFrom === "duplicate" && dupSourceId != null) {
                // deck_duplicate returns the copy's own new_id (present whenever dupSourceId
                // resolved) — read it straight off the raw response, since pmApplyLibrary only
                // caches the fields the library grid renders (decks/open/persistent/restorable).
                const lv = await invoke("deck_duplicate", { id: dupSourceId });
                pmApplyLibrary(lv);
                const newId = lv && lv.new_id != null ? lv.new_id : null;
                // The source deck vanished mid-dialog (deleted by another action between the
                // picker rendering and Create being pressed) — deck_duplicate is a no-op then and
                // nothing was actually created. "Presentation duplicated" would be a false-positive
                // success toast over a request that did nothing; route through the same failure
                // path the catch block below already uses for every other create failure.
                if (newId == null) { pmShowError("create the presentation"); return; }
                const trimmed = (name || "").trim();
                if (trimmed) pmApplyLibrary(await invoke("deck_rename", { id: newId, name: trimmed }));
                const dv = await invoke("deck_open", { id: newId });
                pmDv = dv; renderPresentation(dv); pmHideLibrary(); pmToast("Presentation created");
              } else {
                const dv = await invoke("deck_new", { name: name });
                pmDv = dv; renderPresentation(dv); pmHideLibrary(); pmToast("Presentation created");
              }
            } catch (e) { console.error(e); pmShowError("create the presentation"); }
          },
        });
      }
      async function pmLibOpen(id) {
        try { const dv = await invoke("deck_open", { id: id }); pmDv = dv; pmSetMode("grid"); pmRenderGrid(dv); }
        catch (e) { console.error(e); pmShowError("open the presentation"); }
      }
      // PME-055: "Present" straight from the library card menu — opens the deck (same as
      // pmLibOpen), lands in the slide GRID so the operator sees what is about to go out, and
      // presents its last-selected slide (or the first, for a deck never opened before). Reuses
      // pmGridGoLive rather than duplicating its select-then-go-live sequencing, so this stays
      // the SAME host round-trip (deck_select_slide, then deck_go_live) the grid's own
      // double-click/Enter present gesture uses — never a second, divergent "present" path.
      async function pmLibPresent(id) {
        let dv;
        try { dv = await invoke("deck_open", { id: id }); }
        catch (e) { console.error(e); pmShowError("open the presentation"); return; }
        pmDv = dv; pmSetMode("grid"); pmRenderGrid(dv);
        const slides = dv.slides || [];
        if (!slides.length) return; // an empty deck has nothing to present; grid shows its own empty state
        const target = dv.selected != null ? dv.selected : slides[0].id;
        await pmGridGoLive(target);
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
      // Undo a delete. The host returns the name the deck came back UNDER, which can differ from
      // the one that was deleted (a name taken while it sat in the trash is uniquified) — so the
      // confirmation quotes the RESTORED name, never the remembered one. Saying "restored Sunday
      // Morning" when it came back as "Sunday Morning (2)" would be a fresh lie in the act of
      // fixing one. A refusal carries the host's own operator-facing reason, not a generic retry.
      async function pmLibRestore(id) {
        try {
          const view = await invoke("deck_restore", { id: id });
          pmApplyLibrary(view);
          const name = view && view.restored_name;
          pmToast(name ? "Restored “" + name + "”" : "Presentation restored");
          pmLibFocusDeck(id);
        } catch (e) {
          console.error(e);
          pmShowErrorRaw(String(e && e.message ? e.message : e));
        }
      }
      async function pmLibDuplicate(id) {
        try { pmApplyLibrary(await invoke("deck_duplicate", { id: id })); pmLibFocusDeck(id); }
        catch (e) { console.error(e); pmShowError("duplicate the presentation"); }
      }
      // "its 12 slides" when the library knows the count, "its slides" when it does not. Never a
      // fabricated number: an unknown count is stated vaguely, not invented precisely.
      function pmSlideCountPhrase(id) {
        const d = (pmLibDecks || []).find((x) => x.id === id);
        const n = d && typeof d.slides === "number" ? d.slides : null;
        if (n === null) return "its slides";
        return "its " + n + (n === 1 ? " slide" : " slides");
      }
      async function pmLibDelete(id, name) {
        const inUse = id === pmLibOpenId;
        // PME-059: warn when the deck is linked from a service-plan item — deleting it out from
        // under a plan silently leaves that item showing missing, discovered only on the day
        // someone opens the run sheet expecting it. `view()` is the SAME local Tauri state read
        // used everywhere else on this surface (pmGridSyncLive etc.) — not a LAN round-trip —
        // fetched fresh here rather than from any cached view, because a stale "not referenced"
        // is the one wrong answer that matters: it would let the delete through silently.
        let planRefName = null;
        try {
          const v = await invoke("view");
          const items = (v && v.items) || [];
          const linked = items.some((it) => it.link && it.link.kind === "deck" && it.link.id === id);
          if (linked && v.plan_name) planRefName = v.plan_name;
        } catch (e) {
          // Couldn't check — fail OPEN on the warning (never claim "not referenced" from a
          // failed read) but don't block the delete flow itself on this secondary check.
          console.error(e);
        }
        const warnings = [];
        if (inUse) warnings.push("It’s the presentation you have open — deleting it switches the editor to another.");
        if (planRefName) warnings.push("Used in your service plan “" + planRefName + "” — that plan item will show missing.");
        pmConfirm({
          title: "Delete “" + (name || "Untitled presentation") + "”?",
          // PME-058: name the SLIDE COUNT — "its slides" understates what is about to go. The count
          // comes from the library view (deck_list), and when it is genuinely unknown the sentence
          // falls back to "its slides" rather than printing a fabricated 0.
          //
          // The copy still says this CANNOT be undone, and that stays until it is actually
          // reversible. Q-08 resolved that deck delete SHOULD become undoable, but the host has no
          // way back today: DeckLibrary::delete drops the deck from memory and calls
          // delete_persisted (deck_library.rs:459-467) with no trash, no restore; there is no
          // deck_export/deck_import; and deck_list carries only {id, name, slides}, so the webview
          // cannot rebuild the slides, elements, theme or notes it would have to restore.
          // Promising undo before the seam exists would make the product lie — which is the exact
          // defect PME-058 recorded, only inverted. Flip this sentence WITH the restore command.
          // Q-08: deck delete IS reversible now (deck_restore + a bounded trash), so the old
          // "This can't be undone." is simply false and is gone. It is NOT replaced with "You can
          // undo it" either: whether THIS deck is retained depends on its size against the trash
          // budget, and that is not knowable at confirm time. Promising it here and discovering
          // otherwise afterwards would be the same lie pointed the other way. The promise is made
          // where it can be verified — the toast, gated on the host's own `restorable` list.
          body: "This removes the presentation and " + pmSlideCountPhrase(id) + " from your library.",
          warning: warnings.length ? warnings.join(" ") : null,
          confirmLabel: "Delete",
          onConfirm: async () => {
            try {
              pmApplyLibrary(await invoke("deck_delete", { id: id }));
              if (inUse) { const dv = await invoke("deck_view"); pmDv = dv; renderPresentation(dv); } // editor switched by the host
              // Offer Undo only where it will actually work.
              if ((pmLibRestorable || []).indexOf(id) >= 0) pmToast("Presentation deleted", "Undo", () => pmLibRestore(id));
              else pmToast("Presentation deleted");
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
      // The topbar "▶ Present" acts on whichever mode is showing, which is the same split the ⌘K
      // palette already makes: GRID presents the cursor slide, EDITOR presents the selected one.
      function pmPresentFromTopbar() {
        if (pmMode === "grid") { if (typeof pmGridGoLive === "function") pmGridGoLive(pmGridCursor); }
        else pmPresent();
      }
      // "Add to plan" (Figma 329:138/139): append a Presentation item to the service plan and link
      // the OPEN deck to it. Uses add_item + set_item_content — the same pair the plan builder's own
      // deck-link dialog commits with — so the row resolves to a real name + slide count. deck_list
      // is re-read on click because it, not any cached value, is the authority on which deck is open.
      let pmAddToPlanBusy = false;
      async function pmAddToPlan() {
        if (pmAddToPlanBusy) return; // guard double-activation → never two plan items for one click
        pmAddToPlanBusy = true;
        const btn = pmEl("pm-addtoplan"); if (btn) btn.disabled = true;
        try {
          const lib = await invoke("deck_list");
          const openId = lib ? lib.open : null;
          const deck = ((lib && lib.decks) || []).find((d) => d.id === openId);
          if (!deck) { pmShowError("add this presentation to the plan"); return; }
          const v = await invoke("add_item", { kind: "slide_group", title: deck.name || "Presentation" });
          const item = v && v.items && v.items.length ? v.items[v.items.length - 1] : null;
          if (!item) { pmShowError("add this presentation to the plan"); return; }
          try {
            // Carry the slide count to the host (it owns no deck store) so the row reports the real
            // count and can stage a specific slide — same contract as planDeckBody's commit().
            await invoke("set_item_content", { itemId: item.id, link: { kind: "deck", id: deck.id, slide_count: deck.slides, label: deck.name } });
          } catch (e) {
            // The item landed but carries no deck reference. A plan row that lies about what it
            // holds is worse than no row on a Sunday morning, so roll it back instead of leaving
            // a stub behind, then report the failure honestly.
            console.error(e);
            try { await invoke("remove_item", { itemId: item.id }); } catch (e2) { console.error(e2); }
            pmShowError("add this presentation to the plan");
            return;
          }
          pmClearError();
          pmToast("Added to the service plan", "Undo", () => {
            invoke("remove_item", { itemId: item.id }).catch((e) => { console.error(e); pmShowError("undo that"); });
          });
        } catch (e) {
          console.error(e);
          pmShowError("add this presentation to the plan");
        } finally {
          pmAddToPlanBusy = false;
          if (btn) btn.disabled = false;
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
          // PME-027: left and right previously shared the glyph "≡" (only Center read as
          // "≣"), so the two horizontal-align buttons were visually indistinguishable — an
          // operator could not tell which was pressed without reading the aria-pressed state.
          // Reuses the same distinct left/centre/right glyphs the Theme Designer's own align
          // control already ships (#td-align, index.html) rather than inventing a new set.
          [["left", "⇤"], ["center", "⇔"], ["right", "⇥"]].forEach(([val, gl]) => { const b = document.createElement("button"); b.type = "button"; b.className = "pm-insp-ctrl"; b.dataset.ik = "align-" + val; b.textContent = gl; b.setAttribute("aria-label", "Align " + val); b.setAttribute("aria-pressed", D.alignH === val ? "true" : "false"); b.onclick = () => pmUpdate(idx, { align_h: val }); align.appendChild(b); });
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
          // G.6 · Missing-media fallback (Frame G, node 347:165). The inspector already NAMED the
          // missing file; what it never said is the thing the operator actually needs under
          // pressure — what the AUDIENCE is seeing right now. FR-070 (PRD:206) guarantees a safe
          // placeholder and never an unintended black screen, and the host already honours it:
          // a missing image composes to a placeholder in the rasterizer (raster.rs:1105-1110),
          // so the console does not synthesize a fallback, it only explains the one that exists.
          //
          // The second sentence is a real trap, not padding: repairing the deck does NOT repair
          // what is already on air. Every deck_* repair routes through with_deck, which mutates
          // the workspace and never calls present_authored_slide — correct under FR-012
          // (staging never changes Live), and precisely why the operator must be told to re-push.
          if (el.missing) {
            const miss = document.createElement("p");
            miss.className = "pm-insp-miss";
            miss.setAttribute("role", "status");
            miss.textContent = "The slide still composes without it — the audience sees the background, never an error. "
              + "Relinking fixes the deck; re-push the slide to change what is already on air.";
            body.appendChild(miss);
          }
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
        pmEl("pm-import").onclick = pmImportImage;
        // Error banner: Retry re-runs the last rejected deck action; Dismiss hides it.
        pmEl("pm-error-retry").onclick = () => { if (pmLastAct) pAct(pmLastAct.fn, pmLastAct.opName); };
        pmEl("pm-error-dismiss").onclick = pmClearError;
        // Presentations Library: the deck-switcher opens it; ＋ New creates; the library controls.
        pmEl("pm-deckswitch").onclick = pmShowLibrary;
        pmEl("pm-newpres").onclick = pmLibNew;
        // The two Design 2.0 topbar primaries (PME-014 / PME-015). Guarded: this init block wires
        // the whole surface, so an unguarded lookup on a element someone later removes would throw
        // here and silently take out every wiring BELOW it (the add-content tools, the inspector).
        if (pmEl("pm-present")) pmEl("pm-present").onclick = pmPresentFromTopbar;
        if (pmEl("pm-addtoplan")) pmEl("pm-addtoplan").onclick = pmAddToPlan;
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
