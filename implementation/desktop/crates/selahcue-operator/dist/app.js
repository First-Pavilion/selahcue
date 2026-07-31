      const invoke = window.__TAURI__.core.invoke;
      let editing = null;       // item id with an open inline editor
      let confirmDelete = null; // item id in the two-click delete confirm state
      let lastRendered = "";    // skip DOM rebuilds when nothing changed

      function render(view) {
        // Chrome (emergency footer, LIVE chip, timer, blackout) syncs on EVERY
        // view — the blackout toggle must read true state even while an editor
        // is open.
        syncChrome(view);
        // The saved-theme library (86ajq4xmy) rides on every view. Refresh the Theme
        // Designer's template list whenever it changes — but never while the save-name
        // field is focused (a mid-type rebuild would clobber the entry), and only after
        // the built-ins have loaded (tdList needs them). This runs before the plan's
        // early-returns so the library stays live even with an open plan editor.
        syncSavedThemes(view);
        // Never clobber an open editor or a pending delete-confirm, and skip
        // identical re-renders (the 1s poll must not eat in-flight clicks).
        const key = JSON.stringify(view);
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
          row.onclick = () => act(() => invoke("select", { itemId: it.id }));

          const main = document.createElement("span");
          main.className = "main";
          const title = document.createElement("span");
          title.className = "title";
          title.textContent = it.title;
          const kind = document.createElement("span");
          kind.className = "kind";
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

          // Per-item theme override (S8-3d): a small picker on each row. Blank = the
          // global theme; a built-in OR a saved-library theme (86ajq69ft) renders THIS
          // item on that template.
          const themeSel = document.createElement("select");
          themeSel.className = "item-theme";
          themeSel.title = "Item theme (blank = follow the global theme)";
          themeSel.onclick = (e) => e.stopPropagation();
          const optGlobal = document.createElement("option");
          optGlobal.value = "";
          optGlobal.textContent = "◈ theme";
          themeSel.appendChild(optGlobal);
          (view.themes || []).forEach((name) => {
            const o = document.createElement("option");
            o.value = name;
            o.textContent = name;
            themeSel.appendChild(o);
          });
          // Saved (named custom) themes from the library, in a labelled group.
          const savedNames = (view.saved_themes || []).map((t) => t.name);
          if (savedNames.length) {
            const grp = document.createElement("optgroup");
            grp.label = "Saved";
            savedNames.forEach((name) => {
              const o = document.createElement("option");
              o.value = name;
              o.textContent = name;
              grp.appendChild(o);
            });
            themeSel.appendChild(grp);
          }
          themeSel.value = it.theme || "";
          if (it.theme) themeSel.classList.add("on");
          themeSel.onchange = (e) => {
            e.stopPropagation();
            const v = e.target.value;
            act(() => invoke("set_item_theme", { itemId: it.id, theme: v || null }));
          };

          row.appendChild(main);
          // Outside `tools` (which hides until hover) so an ACTIVE override stays visible.
          row.appendChild(themeSel);
          tools.appendChild(ren);
          tools.appendChild(up);
          tools.appendChild(down);
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

      function syncChrome(view) {
        // Top-bar LIVE chip: on air only when something is actually live.
        document.getElementById("live-chip").classList.toggle("on", view.live_index != null);

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
        setPanel(
          "live",
          itemAt(view.live_index) ||
            scriptureAs(view.live_scripture) ||
            freeAs(view.live_free_text),
          "main output",
          "Output idle"
        );

        const t = view.timer;
        const big = document.getElementById("timer-big");
        if (!t) {
          big.textContent = "–:––";
          big.classList.remove("up");
          big.style.color = "";
        } else if (t.time_up) {
          big.textContent = "TIME UP";
          big.classList.add("up");
          big.style.color = "";
        } else {
          const secs = t.remaining_secs != null ? t.remaining_secs : t.elapsed_secs;
          big.textContent = fmtClock(secs);
          big.classList.remove("up");
          big.style.color = t.warn ? "var(--warn-ink)" : "var(--preview-ink)";
        }

        renderOutputs(view);

        // The live-adjust buttons act on a RUNNING (or pending) timer only.
        const hasTimer = !!view.timer;
        document.getElementById("timer-plus").disabled = !hasTimer;
        document.getElementById("timer-minus").disabled = !hasTimer;

        // Non-colour blackout state: label + aria-pressed + the live-panel
        // overlay, not just the red fill.
        const b = document.getElementById("blackout");
        b.classList.toggle("on", view.blackout);
        b.dataset.on = view.blackout ? "1" : "0";
        b.setAttribute("aria-pressed", view.blackout ? "true" : "false");
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
      function drawConsoleFrame(canvasId, frame) {
        if (!frame || !frame.rgba || !frame.w || !frame.h) return false;
        const cv = document.getElementById(canvasId);
        if (!cv) return false;
        let bytes;
        try {
          bytes = Uint8Array.from(atob(frame.rgba), (c) => c.charCodeAt(0));
        } catch (e) {
          return false;
        }
        if (bytes.length !== frame.w * frame.h * 4) return false; // guard a malformed payload
        cv.width = frame.w;
        cv.height = frame.h;
        cv.getContext("2d").putImageData(
          new ImageData(new Uint8ClampedArray(bytes), frame.w, frame.h),
          0,
          0
        );
        return true;
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
          setConsoleRender(false); // command missing (older host) → keep the text placeholder
          return;
        }
        if (!res || !res.available) {
          setConsoleRender(false); // Remote host: pixels are not on the wire → text fallback
          return;
        }
        const okP = drawConsoleFrame("preview-canvas", res.preview);
        const okL = drawConsoleFrame("live-canvas", res.live);
        setConsoleRender(okP || okL);
      }

      // OUTPUTS panel (FR-040/151): role -> display, assignment picker, health dot.
      let outputsKey = "";
      let outputsPending = null; // deferred view while a picker has focus
      function renderOutputs(view) {
        const outs = view.outputs || [];
        const displays = view.displays || [];
        const themes = view.themes || [];
        const activeTheme = view.theme || "";
        // Per-screen theme map (86ajq321k): screen id → its assigned theme name. A screen
        // absent from the map follows the global; the picker shows that as its selection.
        const screenThemes = {};
        (view.screen_themes || []).forEach((st) => { screenThemes[st.screen] = st.theme; });
        const key = JSON.stringify([outs, displays, themes, activeTheme, view.screen_themes || [], view.saved_themes || []]);
        if (key === outputsKey) return; // pickers are interactive: rebuild only on change
        const list = document.getElementById("screens-list");
        // Never yank a picker out from under the operator: an open/focused
        // select survives; the fresh data renders when focus leaves the surface.
        if (list.contains(document.activeElement)) {
          outputsPending = view;
          return;
        }
        outputsPending = null;
        outputsKey = key;

        // Outputs/screens are shown + managed on the Screens surface (menu →
        // Screens); the console no longer carries an outputs panel.
        document.getElementById("screens-identify").disabled = outs.length === 0;

        // A per-SCREEN Theme picker (86ajq321k): sets THIS screen's theme (not the
        // global) and reflects the screen's current theme. Returned as a label + select.
        const themePickerFor = (screen) => {
          const frag = document.createDocumentFragment();
          const cl = document.createElement("label"); cl.textContent = "Theme"; frag.appendChild(cl);
          const sel = document.createElement("select");
          sel.setAttribute("aria-label", "Theme for the " + screen + " screen");
          if (!themes.length) {
            const opt = document.createElement("option");
            opt.textContent = "No themes offered"; opt.disabled = true; opt.selected = true;
            sel.appendChild(opt); sel.disabled = true;
          } else {
            // Whether this screen has an EXPLICIT per-screen theme (vs. following the
            // global). Membership, not value — "explicitly classic" ≠ "unset (global)".
            const explicit = Object.prototype.hasOwnProperty.call(screenThemes, screen);
            // A "follow global" entry (empty value) — sending it clears the override
            // (the backend's empty-name clear). Mirrors the per-item picker (S8-3d).
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
        };

        // --- Full Screens list (per-screen: role → content control) ---
        list.innerHTML = "";
        if (!outs.length) {
          const p = document.createElement("p");
          p.className = "coming-soon";
          p.textContent = "No outputs detected — connect a display or start the output window.";
          list.appendChild(p);
          return;
        }
        outs.forEach((o) => {
          const audience = o.role === "main";
          const row = document.createElement("div"); row.className = "screen-row";
          const head = document.createElement("div"); head.className = "screen-head";
          const name = document.createElement("strong");
          name.style.fontSize = "17px";
          name.textContent = audience ? "Main Screen" : "Stage Display";
          const rb = document.createElement("span"); rb.className = "role-badge";
          rb.textContent = audience ? "Audience" : "Stage";
          const rc = audience ? "var(--accent)" : "var(--warn-ink)";
          rb.style.color = rc; rb.style.borderColor = rc;
          head.appendChild(name); head.appendChild(rb);
          row.appendChild(head);

          const fields = document.createElement("div"); fields.className = "screen-fields";
          // Output assignment
          const of = document.createElement("div");
          const ol = document.createElement("label"); ol.textContent = "Output"; of.appendChild(ol);
          if (displays.length) {
            const sel = document.createElement("select");
            sel.setAttribute("aria-label", "Assign the " + o.role + " output to a display");
            if (!o.assigned) sel.classList.add("mismatch");
            const none = document.createElement("option");
            none.value = "";
            none.textContent = o.assigned ? "Assign to display…" : "— not assigned · select";
            sel.appendChild(none);
            displays.forEach((d) => {
              const opt = document.createElement("option");
              opt.value = d.key;
              opt.textContent = d.name + " (" + d.width + "×" + d.height + ")";
              if (o.assigned_key && o.assigned_key === d.key) opt.selected = true;
              sel.appendChild(opt);
            });
            sel.onchange = () => {
              const chosen = sel.value;
              if (chosen) {
                sel.value = o.assigned_key || "";
                act(() => invoke("assign_output", { role: o.role, displayKey: chosen }));
              }
            };
            of.appendChild(sel);
          } else {
            const f = document.createElement("div"); f.className = "field";
            f.textContent = o.display || "No displays found";
            of.appendChild(f);
          }
          fields.appendChild(of);
          // Format (read-only for now)
          const ff = document.createElement("div");
          const fl = document.createElement("label"); fl.textContent = "Format"; ff.appendChild(fl);
          const fv = document.createElement("div"); fv.className = "field";
          fv.textContent = o.width + " × " + o.height;
          ff.appendChild(fv); fields.appendChild(ff);
          // Content — role-driven: Audience → per-screen Theme; Stage → layout chips.
          const cf = document.createElement("div");
          if (audience) {
            cf.appendChild(themePickerFor("main"));
          } else {
            const cl = document.createElement("label"); cl.textContent = "Stage layout"; cf.appendChild(cl);
            const chips = document.createElement("div"); chips.className = "stage-chips";
            ["Current", "Next", "Timer"].forEach((l) => {
              const c = document.createElement("span"); c.className = "stage-chip on";
              c.textContent = l; chips.appendChild(c);
            });
            cf.appendChild(chips);
          }
          fields.appendChild(cf);
          row.appendChild(fields);
          list.appendChild(row);
        });

        // Virtual Audience-class screens (86ajq321k): lower-third + stream. Each carries
        // its OWN per-screen theme now (real); their physical NDI/stream OUTPUT delivery
        // is the honest remaining seam. Rendered only when the main output exists.
        if (outs.length) {
          [
            { screen: "lower-third", name: "Lower Third", badge: "Lower-third" },
            { screen: "stream", name: "Stream", badge: "Stream" },
          ].forEach((v) => {
            const row = document.createElement("div"); row.className = "screen-row";
            const head = document.createElement("div"); head.className = "screen-head";
            const name = document.createElement("strong");
            name.style.fontSize = "17px"; name.textContent = v.name;
            const rb = document.createElement("span"); rb.className = "role-badge";
            rb.textContent = v.badge;
            rb.style.color = "var(--accent)"; rb.style.borderColor = "var(--accent)";
            head.appendChild(name); head.appendChild(rb);
            row.appendChild(head);

            const fields = document.createElement("div"); fields.className = "screen-fields";
            // Output — an honest seam: NDI/stream delivery arrives later.
            const of = document.createElement("div");
            const ol = document.createElement("label"); ol.textContent = "Output"; of.appendChild(ol);
            const f = document.createElement("div"); f.className = "field coming-soon";
            f.textContent = "NDI / stream — delivery arrives later";
            of.appendChild(f); fields.appendChild(of);
            // Theme — REAL per-screen theme (composed now; shown on the output when delivery lands).
            const cf = document.createElement("div");
            cf.appendChild(themePickerFor(v.screen));
            fields.appendChild(cf);
            row.appendChild(fields);
            list.appendChild(row);
          });
        }

        // Honest seam: physical multi-output delivery + enable/disable + add/delete.
        const note = document.createElement("p");
        note.className = "coming-soon"; note.style.fontSize = "11px";
        note.textContent =
          "Each Audience screen now carries its OWN theme (86ajq321k). Physical NDI/stream OUTPUT delivery for the lower-third/stream screens, plus enable/disable and add/delete a virtual screen, arrive next.";
        list.appendChild(note);
      }

      document.getElementById("screens-list").addEventListener("focusout", () => {
        setTimeout(() => {
          const list = document.getElementById("screens-list");
          if (outputsPending && !list.contains(document.activeElement)) {
            const v = outputsPending;
            outputsPending = null;
            renderOutputs(v);
          }
        }, 0);
      });

      // --- App menu + surface routing (86ajq321f) ---
      const APP_SURFACES = ["console", "theme-designer", "screens", "plan", "settings"];
      const SURFACE_LABEL = {
        console: "Live Console", "theme-designer": "Theme Designer",
        screens: "Screens", plan: "Plan / Library", settings: "Settings",
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
      function showSurface(name) {
        APP_SURFACES.forEach((s) => {
          const el = document.getElementById("surface-" + s);
          if (el) el.classList.toggle("active", s === name);
        });
        navItems.forEach((it) => {
          if (it.dataset.surface === name) it.setAttribute("aria-current", "page");
          else it.removeAttribute("aria-current");
        });
        closeAppMenu();
        // Move focus INTO the new surface (never leave it on a now-hidden element)
        // and announce the route to assistive tech (NAV-IA §2/§5).
        const surf = document.getElementById("surface-" + name);
        if (surf) { surf.tabIndex = -1; surf.focus(); }
        document.getElementById("route-status").textContent =
          "Now on: " + (SURFACE_LABEL[name] || name);
        // Refresh the true Preview/Live render when returning to the console (86ajtwq28).
        if (name === "console") scheduleConsoleRender();
      }
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
      navItems.forEach((it, i) => {
        it.onclick = () => showSurface(it.dataset.surface);
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
          b.textContent = name;
          b.setAttribute("aria-pressed", tdSelectedKind === "builtin" && name === tdSelected ? "true" : "false");
          b.onclick = () => {
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
          row.appendChild(b);
          row.appendChild(tag);
          box.appendChild(row);
        });
        // Saved (named custom) themes from the library — selectable (load into the
        // editor) and deletable (✕). A confirm-on-second-click delete mirrors the plan.
        tdSaved.forEach(({ name, theme_json }) => {
          const row = document.createElement("div");
          row.className = "td-theme-row td-theme-saved";
          const b = document.createElement("button");
          b.className = "td-theme-name";
          b.textContent = name;
          b.setAttribute("aria-pressed", tdSelectedKind === "saved" && name === tdSelected ? "true" : "false");
          b.onclick = () => {
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
          row.appendChild(b);
          row.appendChild(del);
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

      // Update just the Layout fields + the selection box (called on every drag frame).
      function tdSyncLayout() {
        const r = tdActive();
        if (!r) return;
        // Never rewrite a field the user is actively typing in (numeric entry commits
        // on `change`; a concurrent drag must not clobber a focused field mid-keystroke).
        const set = (id, val) => { const el = document.getElementById(id); if (el !== document.activeElement) el.value = val; };
        set("td-x", (r.x_permille / 10).toFixed(1));
        set("td-y", (r.y_permille / 10).toFixed(1));
        set("td-w", (r.w_permille / 10).toFixed(1));
        set("td-h", (r.h_permille / 10).toFixed(1));
        tdDrawSel();
      }

      function tdSync() {
        if (!tdTheme) return;
        const isEl = tdActiveIsEl();
        // Toggle inspector mode: region controls (region picker / align / text) hide when an
        // element is selected; the element inspector shows. Layout (X/Y/W/H) + Theme
        // background are shared/always-visible.
        const showReg = (id) => {
          const el = document.getElementById(id);
          if (el) el.style.display = isEl ? "none" : "";
        };
        showReg("td-lbl-region");
        showReg("td-region");
        showReg("td-region-align");
        showReg("td-region-text");
        document.getElementById("td-el-inspector").hidden = !isEl;
        document.getElementById("td-bg").value = tdHex(tdTheme.background); // theme-level, always
        if (isEl) {
          tdSyncEl();
          tdSyncLayout();
          return;
        }
        tdSel.setAttribute("aria-label", "Selected region — drag to move, handles to resize");
        const r = tdTheme[tdRegion];
        document.getElementById("td-color").value = tdHex(r.color);
        document.getElementById("td-size").value = r.size_permille;
        document.getElementById("td-size-v").textContent = (r.size_permille / 10).toFixed(1);
        document.getElementById("td-lh").value = r.line_height_permille;
        document.getElementById("td-lh-v").textContent = (r.line_height_permille / 1000).toFixed(2);
        tdSeg("td-region", tdRegion, "region");
        tdSeg("td-align", r.align_h, "a");
        tdSeg("td-valign", r.align_v, "v");
        tdSeg("td-fit", r.fit, "f");
        // Reflect the theme's font (86ajq6fxt); "" = the bundled default. If the theme's
        // font isn't installed on THIS machine, still show it (a "(not installed here)"
        // entry) so it is faithfully reflected + preserved, not silently blanked/cleared.
        tdEnsureFontOption(tdTheme.font);
        document.getElementById("td-font").value = tdTheme.font || "";
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
        tdSel.setAttribute(
          "aria-label",
          (el.kind === "image" ? "Selected image element" : "Selected shape element") +
            " — drag to move, handles to resize",
        );
        const kind = el.kind === "image" ? "image" : "shape";
        const order = tdPaintOrder();
        const pos = order.indexOf(tdSelEl) + 1;
        document.getElementById("td-el-head").textContent =
          (kind === "image" ? "Image" : "Shape") + " — " + pos + " of " + tdEls().length;
        const front = tdZ(el) >= 0;
        const chip = document.getElementById("td-el-zchip");
        chip.textContent = front ? "In front of text" : "Behind text";
        chip.className = "td-chip " + (front ? "front" : "behind");
        const opPct = Math.round((tdOpacity(el) * 100) / 255);
        document.getElementById("td-el-op").value = opPct;
        document.getElementById("td-el-op-v").textContent = opPct;
        document.getElementById("td-el-shape").hidden = kind !== "shape";
        document.getElementById("td-el-image").hidden = kind !== "image";
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
        } else {
          document.getElementById("td-el-src").textContent = el.source || "(no file chosen)";
        }
      }

      let tdTimer = null;
      function tdPreview() {
        if (!tdTheme) return;
        clearTimeout(tdTimer);
        tdTimer = setTimeout(async () => {
          try {
            const p = await invoke("preview_theme", { themeJson: JSON.stringify(tdTheme) });
            const bytes = Uint8Array.from(atob(p.rgba), (c) => c.charCodeAt(0));
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
      document.getElementById("td-bg").oninput = (e) => { if (!tdTheme) return; tdTheme.background = tdRgb(e.target.value); tdPreview(); };
      document.getElementById("td-color").oninput = (e) => { if (!tdTheme) return; tdTheme[tdRegion].color = tdRgb(e.target.value); tdPreview(); };
      document.getElementById("td-size").oninput = (e) => { if (!tdTheme) return; tdTheme[tdRegion].size_permille = +e.target.value; document.getElementById("td-size-v").textContent = (e.target.value / 10).toFixed(1); tdPreview(); };
      document.getElementById("td-lh").oninput = (e) => { if (!tdTheme) return; tdTheme[tdRegion].line_height_permille = +e.target.value; document.getElementById("td-lh-v").textContent = (e.target.value / 1000).toFixed(2); tdPreview(); };
      // Numeric X/Y/W/H (percent) — the same rect the on-canvas handles edit. Commit
      // on `change` (blur/Enter), NOT per-keystroke, so multi-digit entry isn't
      // normalized away mid-typing. X/Y clamp as position (keep size); W/H clamp to the
      // frame keeping the region's origin (anchored top-left, no jump). Non-numeric input
      // is rejected and the field is restored to the current value.
      [["td-x", "x_permille"], ["td-y", "y_permille"], ["td-w", "w_permille"], ["td-h", "h_permille"]].forEach(([id, key]) => {
        document.getElementById(id).onchange = (e) => {
          if (!tdTheme) return;
          const pm = Math.round(parseFloat(e.target.value) * 10);
          const r = tdActive();
          if (!r) return;
          if (!Number.isFinite(pm)) { tdSyncLayout(); return; }
          if (key === "w_permille") r.w_permille = tdClamp(pm, 20, 1000 - r.x_permille);
          else if (key === "h_permille") r.h_permille = tdClamp(pm, 20, 1000 - r.y_permille);
          else if (key === "x_permille") r.x_permille = tdClamp(pm, 0, 1000 - r.w_permille);
          else r.y_permille = tdClamp(pm, 0, 1000 - r.h_permille);
          tdSyncLayout();
          tdPreview();
        };
      });
      document.querySelectorAll("#td-region button").forEach((b) => (b.onclick = () => { tdSelEl = -1; tdRegion = b.dataset.region; tdSync(); }));
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
              tdAnnounce((tdEls()[hit].kind === "image" ? "Image" : "Shape") + " selected");
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
          // Lock aspect: constrain the height to the region's original w:h ratio
          // (width-driven), re-anchored on the dragged vertical edge + clamped to the frame.
          if (document.getElementById("td-lock").checked && tdDrag.h > 0) {
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
        // Escape deselects an element back to region editing (keyboard path — the region
        // buttons are hidden in element mode, so Escape is how a keyboard user returns).
        if (e.key === "Escape" && tdActiveIsEl()) {
          e.preventDefault();
          tdSelEl = -1;
          tdSync();
          const rb = document.getElementById("td-region-body");
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
            (el.kind === "image" ? "Image" : "Shape") +
              " selected, " + (front ? "in front of" : "behind") + " the text",
          );
          return;
        }
        // Clicked empty canvas (no element) while an element was selected → deselect back to
        // region editing, so the Body/Reference region controls are reachable again.
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
      document.getElementById("td-new").onclick = tdNew;
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
        const what = kind === "image" ? "Image" : (TD_SHAPE_LABELS[el.variant || "rect"] || "Shape");
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
      document.querySelectorAll("#td-el-z button").forEach((b) => (b.onclick = () => tdArrange(b.dataset.z)));

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
        tdAnnounce((clone.kind === "image" ? "Image" : "Shape") + " pasted, selected");
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
      tdLoadBuiltins();
      tdLoadFonts();

      function miniBtn(label, onclick) {
        const b = document.createElement("button");
        b.textContent = label;
        b.style.cssText = "padding:2px 8px;margin-left:4px;font-size:11px";
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

      document.getElementById("prev").onclick = () => act(() => invoke("previous"));
      document.getElementById("next").onclick = () => act(() => invoke("next"));
      document.getElementById("golive").onclick = () => act(() => invoke("go_live"));
      document.getElementById("blackout").onclick = toggleBlackout;
      document.getElementById("clear-all").onclick = clearAll;
      document.getElementById("timer-5").onclick = () =>
        act(() => invoke("start_timer", { seconds: 300 }));
      document.getElementById("timer-10").onclick = () =>
        act(() => invoke("start_timer", { seconds: 600 }));
      document.getElementById("timer-stop").onclick = () => act(() => invoke("stop_timer"));
      document.getElementById("timer-start-custom").onclick = () => {
        // Sanitize + bound (the input's max attribute does not block typing):
        // whole minutes, 1..=999 — the same cap the field declares.
        const raw = Number(document.getElementById("timer-mins").value);
        if (!Number.isFinite(raw)) return;
        const mins = Math.min(999, Math.floor(raw));
        if (mins >= 1) act(() => invoke("start_timer", { seconds: mins * 60 }));
      };
      document.getElementById("timer-mins").onkeydown = (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          document.getElementById("timer-start-custom").click();
        }
      };
      document.getElementById("timer-plus").onclick = () =>
        act(() => invoke("adjust_timer", { deltaSecs: 60 }));
      document.getElementById("timer-minus").onclick = () =>
        act(() => invoke("adjust_timer", { deltaSecs: -60 }));
      // ── Scriptures chapter browser (86ajpkfcd, Pewbeam-style; KJV default).
      // Type a reference -> the chapter opens as a numbered verse list; ↑/↓
      // move the highlighted verse AND stage it; the canonical Enter (Go Live)
      // then sends it to the audience. Keywords fall back to search hits.
      let currentTranslation = "KJV";
      let currentChapter = null; // {reference, verses:[[num,text]...], prev, next}
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
      function setCursor(i, stage) {
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
          stageTimer = setTimeout(() => {
            act(() =>
              invoke("stage_scripture", {
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
          row.onclick = () => setCursor(i, true);
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

      document.getElementById("add-item").onclick = () => {
        const title = document.getElementById("add-title").value.trim();
        const kind = document.getElementById("add-kind").value;
        if (title) {
          // Songs may carry stanza lyrics (S8-1): plain text, stanzas
          // separated by blank lines — each stanza becomes one slide.
          const lyricsEl = document.getElementById("add-lyrics");
          const lyrics = kind === "song" ? lyricsEl.value.trim() : "";
          act(() =>
            invoke("add_item", {
              kind,
              title,
              content: lyrics ? lyrics : null,
            })
          );
          document.getElementById("add-title").value = "";
          lyricsEl.value = "";
        }
      };
      // The lyrics box only makes sense for songs — show it per kind.
      const addKindSel = document.getElementById("add-kind");
      const syncLyricsVisibility = () => {
        document.getElementById("add-lyrics").style.display =
          addKindSel.value === "song" ? "" : "none";
      };
      addKindSel.onchange = syncLyricsVisibility;
      syncLyricsVisibility();

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
          setCursor(verseCursor + (e.key === "ArrowDown" ? 1 : -1), true);
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
            act(() => invoke("go_live"));
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

      act(() => invoke("view"));
      // Poll so a running countdown ticks in the UI (the host advances it each frame).
      setInterval(async () => {
        try {
          render(await invoke("view"));
        } catch (e) {
          /* transient */
        }
      }, 1000);
