/* Native account setup. Rust owns persistence, signed facts and custody. */
(function () {
  "use strict";

  const errors = {
    invalid_credentials: "The email or password could not be verified.",
    account_not_active: "This account can’t sign in yet. Check your email for a verification link or contact your administrator.",
    unknown_key: "We don’t recognise that key. Check for typos or ask your administrator for a new one.",
    // Refused for a device that is already activated (a refresh after the beta, for example).
    policy_denied_activated: "This computer isn’t included in your church’s current plan. On the Free plan, only the first computer you set up stays connected. SelahCue keeps working here, but it can’t refresh its licence or use cloud features.",
    policy_denied: "This device could not be activated under the organisation’s activation policy. Ask your administrator for help.",
    permission_denied: "This account doesn’t have permission to activate this device. Ask your administrator for help.",
    no_active_license: "This account has no active SelahCue plan. Ask your administrator to check the plan.",
    network_unavailable: "We couldn’t connect to activate this device. Check your internet connection and try again.",
    service_unavailable: "SelahCue couldn’t complete the request right now. You can try again later.",
    invalid_input: "Check the information you entered and try again.",
    rate_limited: "Too many requests. Wait a moment before trying again.",
    metadata_unavailable: "SelahCue couldn’t read or save the device’s account information.",
    metadata_changed: "Device information changed during this request. Check the current status before trying again.",
    pending_activation_path: "A previous activation is pending. Continue its original setup method.",
    credential_presence_unavailable: "SelahCue couldn’t check the device credential in system storage.",
    credential_save_failed: "The device was registered, but its credential couldn’t be saved in system storage.",
    account_session_save_failed: "SelahCue couldn’t save the temporary account session in system storage.",
    manifest_unavailable: "A verified entitlement is unavailable. Check again when you’re connected.",
    license_inactive: "This device’s licence is inactive. Ask your administrator to check the plan.",
    identity_recovery_required: "SelahCue couldn’t restore the device identity. Contact your administrator for recovery.",
    device_recovery_required: "This device needs administrator-assisted credential recovery.",
    reauthentication_required: "Sign in again to finish setting up this device.",
    enrollment_key_required: "Enter the original enrollment key to continue this activation.",
    session_cleanup_unconfirmed: "SelahCue couldn’t confirm that the temporary sign-in session was closed.",
    session_cleanup_local_failure: "SelahCue couldn’t finish cleaning up the temporary session in system storage.",
    activation_completion_pending: "This device’s activation is pending. Check its status to continue.",
    activation_operation_completed: "A previous activation completed, but this install needs administrator-assisted recovery.",
    legacy_activation_outcome_unknown: "The outcome of a previous activation is unknown. Contact your administrator for recovery.",
    device_binding_mismatch: "The returned activation doesn’t match this device. Contact your administrator.",
    bound_activation_unsupported: "SelahCue couldn’t complete device activation through this service. Contact support.",
    worker_unavailable: "Account setup is temporarily unavailable. Your presentation controls are available.",
  };

  const statuses = {
    device: {
      unknown: "Device status unavailable",
      unregistered: "Device not activated",
      credential_present: "Device activated",
      credential_missing: "Device credential missing",
      custody_unavailable: "Device credential storage unavailable",
      credential_not_saved: "Device credential could not be saved",
      credential_unconfirmed: "Device credential not yet confirmed",
      reauthentication_needed: "Device needs account attention",
    },
    entitlement: {
      unavailable: "Signed entitlement unavailable",
      current: "Signed entitlement verified",
      expired: "Signed entitlement expired",
      future_or_clock_skew: "Cannot confirm the signed entitlement is current. Check this device’s date and time.",
    },
    license: {
      active: "Licence active",
      renewal_needed: "Licence renewal needed",
      inactive: "Licence inactive",
    },
  };

  const months = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];

  // "5 May 2027" in UTC. Built by hand so the month name never depends on the ICU locale data
  // (en-GB abbreviates September as "Sept" in newer engines). Unparseable input comes back
  // unchanged, so a surprising value is shown rather than hidden.
  // Only an explicit UTC marker or numeric offset is trusted: a timezone-less value would be read
  // as local time and shift the day.
  const zoned = /(Z|[+-]\d{2}:\d{2})$/;

  // The error text for the view. POLICY_DENIED on an already-activated device (credential present)
  // can only come from a refresh or another call on it, never from activating.
  function viewError(view) {
    const code = view.error_code;
    return code === "policy_denied" && view.device_state === "credential_present" ?
      errors.policy_denied_activated : errors[code];
  }

  function formatAccountDate(rfc3339) {
    if (typeof rfc3339 !== "string" || !zoned.test(rfc3339)) return rfc3339;
    const when = new Date(rfc3339);
    if (Number.isNaN(when.getTime())) return rfc3339;
    return when.getUTCDate() + " " + months[when.getUTCMonth()] + " " + when.getUTCFullYear();
  }

  // An exclusive end such as the plan end: the last day it covers is the day before the instant,
  // so midnight UTC on 6 May reads "5 May 2027".
  function formatAccountEndDate(rfc3339) {
    if (typeof rfc3339 !== "string" || !zoned.test(rfc3339)) return rfc3339;
    const when = new Date(rfc3339);
    if (Number.isNaN(when.getTime())) return rfc3339;
    return formatAccountDate(new Date(when.getTime() - 1).toISOString());
  }

  function planLine(view) {
    if (!view.plan_label) return null;
    return view.plan_ends_at ? view.plan_label + " until " + formatAccountEndDate(view.plan_ends_at) : view.plan_label;
  }

  function needsSignIn(view) {
    return view.device_state === "reauthentication_needed" || view.error_code === "reauthentication_required";
  }

  function createAccount(invoke, update, canShowStartup = () => true) {
    let view = {};
    let source = null;
    let stage = "chooser";
    let path = "signIn";
    let formError = null;
    let skipError = false;
    let localError = false;
    let skipPending = false;
    let operationPending = false;
    let webRequest = null;
    let webError = false;
    let firstRunEligible = true;
    let opening = null;
    let generation = 0;

    function draw(focus = false) {
      update({ view, source, stage, path, formError, skipError, skipPending, operationPending, localError,
        webPending: webRequest !== null, webError }, focus);
    }

    function clearWebFeedback() {
      webError = false;
      if (webRequest) webRequest.reportError = false;
    }

    function receive(next) {
      if (!next || !Number.isFinite(next.revision) || next.revision < (view.revision ?? -1)) return false;
      view = next;
      localError = false;
      if (firstRunEligible && view.setup_state !== "unknown") {
        firstRunEligible = false;
        if (view.setup_state === "needed" && !source && canShowStartup()) open("startup", false);
      }
      draw();
      return true;
    }

    async function read() {
      try {
        receive(await invoke("account_view"));
        return view;
      } catch (_) {
        localError = true;
        draw();
      }
    }

    function open(nextSource, focus = true, firstStage = "chooser") {
      firstRunEligible = false;
      if (source === nextSource) return;
      generation += 1;
      source = nextSource;
      clearWebFeedback();
      choose(firstStage, focus);
    }

    function close(focus = false) {
      firstRunEligible = false;
      if (!source) return;
      generation += 1;
      source = null;
      formError = null;
      clearWebFeedback();
      draw(focus);
    }

    function choose(nextStage, focus = true) {
      if (nextStage === "signIn" || nextStage === "enroll") path = nextStage;
      if (stage !== nextStage) clearWebFeedback();
      stage = nextStage;
      formError = stage === "signIn" && view.error_code === "reauthentication_required" ? view.error_code : null;
      draw(focus);
    }

    async function dismiss() {
      if (skipPending) return;
      const persist = source === "startup" || skipError;
      close(true);
      if (!persist) return;
      skipPending = true;
      skipError = false;
      draw();
      try {
        const next = await invoke("account_skip_setup");
        receive(next);
        skipError = next?.setup_state !== "skipped" && next?.setup_state !== "completed";
      } catch (_) {
        skipError = true;
      } finally {
        skipPending = false;
        draw();
      }
    }

    function resolveOperation(next, activating) {
      if (!source || !activating) return;
      const code = next?.error_code;
      if (next?.setup_state === "completed" && next.device_state === "credential_present") {
        close(true);
      } else if (code === "reauthentication_required") {
        choose("signIn");
      } else if (code === "network_unavailable" || code === "service_unavailable") {
        choose("offline");
      } else if (code === "no_active_license") {
        choose("license");
      } else if (code === "policy_denied" || code === "permission_denied") {
        choose("policy");
      } else if (code === "unknown_key" || code === "enrollment_key_required" ||
                 code === "invalid_credentials" || code === "account_not_active" || code === "invalid_input") {
        if (code === "unknown_key" || code === "enrollment_key_required") path = "enroll";
        stage = path;
        formError = code;
        draw(true);
      } else {
        choose("attention");
      }
    }

    async function operation(command, args, activating = false) {
      if (operationPending || view.operation_state === "busy") return;
      operationPending = true;
      const started = generation;
      if (activating) choose("pending");
      else draw();
      try {
        // Keep entered values only in the call into native IPC.
        const request = invoke(command, args);
        args = undefined;
        const next = await request;
        const accepted = receive(next);
        if (started === generation) resolveOperation(accepted ? next : view, activating);
      } catch (_) {
        localError = true;
        if (started === generation && activating) choose("attention");
      } finally {
        operationPending = false;
        draw();
      }
    }

    async function openWeb(destination) {
      if (!source || stage !== "signIn" || webRequest) return;
      const request = { reportError: true };
      webRequest = request;
      webError = false;
      draw();
      try {
        await invoke("account_open_web", { destination });
      } catch (_) {
        webError = request.reportError;
      } finally {
        webRequest = null;
        draw();
      }
    }

    function submit(fields) {
      if (stage === "signIn") {
        return operation("account_sign_in_and_activate", {
          email: fields.email.trim(), password: fields.password, displayName: fields.displayName,
        }, true);
      }
      if (stage === "enroll") {
        return operation("account_activate_with_enrollment", {
          enrollmentKey: fields.enrollmentKey.trim(), displayName: fields.displayName.trim(),
        }, true);
      }
    }

    function retry() {
      if (view.error_code === "reauthentication_required") {
        choose("signIn");
        return;
      }
      // An ambiguous enrollment needs the original key. Only native code owns the
      // bound operation nonce, even when the user supplies the key again.
      if (view.operation_state === "retry_pending" &&
          (path === "signIn" || view.device_state === "credential_not_saved")) {
        return operation("account_retry_activation", undefined, true);
      }
      choose(path);
    }

    return {
      start() { return opening || (opening = read()); },
      receive,
      openSettings() {
        open("settings", true, needsSignIn(view) ? "signIn" : "chooser");
      },
      close,
      choose,
      dismiss,
      openWeb,
      submit,
      retry,
      read,
      refresh(explicit = true) { return operation("account_refresh", { explicit }); },
      cleanup() { return operation("account_retry_session_cleanup"); },
      recover() { return operation("account_retry_activation"); },
    };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { createAccount, formatAccountDate, formatAccountEndDate };
    return;
  }

  const $ = (id) => document.getElementById(id);
  const firstRun = $("account-first-run");
  const card = $("account-card");
  const consolePage = $("surface-console");
  const settingsPage = $("set-page-account");
  const setupStatus = $("account-setup-status");
  const forms = [$("account-sign-in"), $("account-enroll")];
  const password = $("account-password");
  const webActions = card.querySelectorAll("[data-account-web]");
  const enrollmentKey = $("account-enrollment-key");
  let lastSource = null;
  let lastStage = null;
  let returnFocus = null;

  function put(id, value) {
    const element = $(id);
    if (element.textContent !== value) element.textContent = value;
  }

  function optionalField(id, value, text = value) {
    const field = $(id);
    field.closest("dl > div").hidden = value == null || value === "";
    put(id, text ?? "");
    if (field.tagName === "TIME") field.dateTime = value ?? "";
  }

  function setError(field, message) {
    const element = $(field);
    put(field, message);
    element.hidden = !message;
  }

  function deviceDetails(view) {
    const platforms = { macos: "macOS", windows: "Windows", linux: "Linux" };
    return [platforms[view.platform] || view.platform, view.app_version && "SelahCue " + view.app_version]
      .filter(Boolean).join(" · ");
  }

  function renderStatus(state) {
    const { view, operationPending, localError } = state;
    const busy = view.operation_state === "busy" || operationPending;
    const device = statuses.device[view.device_state] || "Checking device status…";
    const entitlement = statuses.entitlement[view.entitlement_state] || "Checking signed entitlement…";
    put("account-device-status", device);
    put("account-entitlement-status", entitlement);
    put("account-device-name", view.display_name || "This device");
    const detail = deviceDetails(view);
    put("account-device-details", detail);
    $("account-device-details").hidden = !detail;
    $("account-active-dot").hidden = view.device_state !== "credential_present";
    $("account-device-chip").hidden = view.device_state !== "credential_present";
    $("account-entitlement-chip").hidden = view.entitlement_state !== "current";
    $("account-status-banner").classList.toggle("account-entitlement-current",
      view.device_state === "credential_present" && view.entitlement_state === "current");
    optionalField("account-plan-label", planLine(view));
    optionalField("account-license-status", statuses.license[view.license_state]);
    // The <time> keeps the machine-readable value; the text is the readable date.
    optionalField("account-license-expiry", view.license_expires_at,
      view.license_expires_at && formatAccountDate(view.license_expires_at));
    optionalField("account-manifest-expiry", view.manifest_expires_at,
      view.manifest_expires_at && formatAccountDate(view.manifest_expires_at));
    optionalField("account-last-checked", view.last_checked_at);
    const counts = Number.isInteger(view.instances_used) && Number.isInteger(view.instance_limit);
    optionalField("account-instance-count", counts ? view.instances_used + " of " + view.instance_limit + " used" : null);
    const meter = $("account-instance-meter");
    meter.hidden = !counts || view.instance_limit <= 0;
    $("account-plan-empty").hidden = !!view.plan_label || counts;
    if (!meter.hidden) {
      meter.max = view.instance_limit;
      meter.value = view.instances_used;
    }
    let issue = "";
    if (localError) issue = errors.worker_unavailable;
    else if (view.error_code) issue = viewError(view) || "SelahCue couldn’t confirm the account status.";
    setError("account-status-error", state.source === "settings" ? "" : issue);
    setError("account-preparation-error", errors[view.preparation_error_code] || "");
    put("account-cleanup-status", errors[view.cleanup_error_code] ||
      "The temporary sign-in session still needs to be closed.");
    $("account-cleanup-row").hidden = !view.pending_cleanup;
    $("account-cleanup").disabled = busy;
    const setup = $("account-start-setup");
    const reauthenticate = needsSignIn(view);
    setup.hidden = (view.setup_state === "completed" && !reauthenticate) ||
      view.error_code === "device_recovery_required";
    setup.disabled = busy || view.setup_state === "unknown";
    put("account-start-setup", reauthenticate ? "Sign in to continue" : "Set up this device");
    $("account-refresh").disabled = busy || view.device_state !== "credential_present";
    $("account-refresh").hidden = view.device_state !== "credential_present";
    $("account-recover").hidden = view.operation_state !== "retry_pending" ||
      view.error_code === "enrollment_key_required" || view.error_code === "reauthentication_required";
    $("account-recover").disabled = busy;
    $("account-settings-controls").hidden = state.source === "settings";
  }

  function render(state, focus) {
    const { source, stage, view, formError, localError } = state;
    const locationChanged = source !== lastSource;
    if (locationChanged && source) returnFocus = document.activeElement;
    renderStatus(state);
    const stageChanged = stage !== lastStage;
    if (locationChanged || stageChanged) {
      password.value = "";
      enrollmentKey.value = "";
      if (stage === "signIn" && formError === "reauthentication_required") $("account-email").value = "";
    }
    if (locationChanged && source) {
      (source === "startup" ? firstRun : $("account-settings-setup")).append(card);
    }
    firstRun.hidden = source !== "startup";
    firstRun.parentElement.classList.toggle("account-first-run-open", source === "startup");
    card.hidden = !source;
    card.classList.toggle("account-card-pending", stage === "pending");
    for (const item of card.querySelectorAll("[data-account-view]")) {
      item.hidden = item.dataset.accountView !== stage;
    }
    if (stage === "enroll" && (locationChanged || stageChanged)) {
      $("account-device-display-name").value = view.display_name || "";
    }
    const metadata = deviceDetails(view);
    setError("account-enroll-device", metadata ? "This device: " + metadata : "");
    setError("account-sign-in-error", stage === "signIn" ? errors[formError] || "" : "");
    const webError = $("account-web-error");
    const webErrorAppeared = state.webError && webError.hidden;
    $("account-web-help").hidden = state.webError;
    setError("account-web-error", state.webError ? "SelahCue couldn’t open your browser. Try again." : "");
    for (const button of webActions) {
      button.setAttribute("aria-disabled", String(state.webPending));
    }
    setError("account-enrollment-error", stage === "enroll" ? errors[formError] || "" : "");
    forms[1].querySelector('button[type="submit"]').textContent = formError === "unknown_key" ?
      "Try again" : "Activate this device";
    $("account-email").setAttribute("aria-invalid", String(formError === "invalid_credentials"));
    password.setAttribute("aria-invalid", String(formError === "invalid_credentials"));
    enrollmentKey.setAttribute("aria-invalid", String(formError === "unknown_key"));
    put("account-policy-message", viewError(view) || errors.policy_denied);
    put("account-offline-message", errors[view.error_code] || errors.network_unavailable);
    put("account-attention-message", localError ? errors.worker_unavailable :
      viewError(view) || "Check your device status in Settings › Account, or try setting up again.");
    for (const form of forms) {
      form.querySelector("button[type=submit]").disabled = state.operationPending || view.operation_state === "busy";
    }
    const showRetry = stage === "offline" || stage === "policy" || stage === "license" || stage === "attention";
    $("account-card-retry").hidden = !showRetry;
    $("account-card-retry").disabled = view.operation_state === "busy";
    const dismiss = $("account-dismiss");
    dismiss.textContent = source === "settings" ? "Back to Account" :
      showRetry ? "Continue offline" : "Skip — set up later";
    dismiss.classList.toggle("account-action-secondary", showRetry);
    $("account-skip-retry").hidden = !state.skipError;
    const skipMessage = state.skipError ? "Setup was closed, but SelahCue couldn’t remember your choice." :
      state.skipPending ? "Remembering your setup choice…" : "";
    setupStatus.hidden = !skipMessage;
    put("account-setup-status-message", skipMessage);
    setupStatus.parentElement.classList.toggle("account-has-notice", !!skipMessage);
    put("account-activation-status", stage === "pending" && source ? "Activation in progress." : "");

    if (focus && source && (stageChanged || locationChanged || formError)) {
      const target = formError === "unknown_key" ? enrollmentKey :
        card.querySelector("[data-account-view]:not([hidden]) h2");
      target?.focus();
    } else if (focus && locationChanged && !source) {
      const fallback = lastSource === "settings" ? $("account-settings-title") : consolePage;
      const target = returnFocus?.isConnected && !returnFocus.closest("[hidden]") &&
        returnFocus !== document.body && !returnFocus.disabled ? returnFocus : fallback;
      if (target === consolePage) target.tabIndex = -1;
      target.focus({ preventScroll: true });
      returnFocus = null;
    }
    if (webErrorAppeared && source === "startup" && stage === "signIn") {
      // Reveal new feedback in the card's own scroll area without shifting focus.
      const region = webError.closest(".account-view");
      const bounds = region.getBoundingClientRect();
      const feedback = webError.getBoundingClientRect();
      if (feedback.bottom > bounds.bottom) {
        region.scrollTop += Math.ceil(feedback.bottom - bounds.bottom);
      } else if (feedback.top < bounds.top) {
        region.scrollTop += Math.floor(feedback.top - bounds.top);
      }
    }
    lastStage = stage;
    lastSource = source;
  }

  const core = window.__TAURI__?.core;
  const account = createAccount(
    (command, args) => core.invoke(command, args),
    render,
    () => consolePage.classList.contains("active"),
  );

  card.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-account-go]");
    if (button) account.choose(button.dataset.accountGo);
  });
  for (const button of webActions) {
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-disabled") === "true") return;
      password.value = "";
      account.openWeb(button.dataset.accountWeb);
    });
  }
  forms[0].addEventListener("submit", (event) => {
    event.preventDefault();
    const entered = password.value;
    password.value = "";
    account.submit({ email: $("account-email").value, password: entered,
      displayName: $("account-device-name").textContent });
  });
  forms[1].addEventListener("submit", (event) => {
    event.preventDefault();
    const entered = enrollmentKey.value;
    enrollmentKey.value = "";
    account.submit({ enrollmentKey: entered, displayName: $("account-device-display-name").value ||
      $("account-device-name").textContent });
  });

  $("account-dismiss").onclick = () => account.dismiss();
  $("account-skip-retry").onclick = () => account.dismiss();
  $("account-card-retry").onclick = () => account.retry();
  $("account-start-setup").onclick = () => account.openSettings();
  $("account-refresh").onclick = () => account.refresh();
  $("account-cleanup").onclick = () => account.cleanup();
  $("account-recover").onclick = () => account.recover();
  $("account-open-providers").onclick = () => {
    setSettingsPage("providers");
    document.querySelector('.set-nav[data-setpage="providers"]').focus();
  };

  window.scAccount = {
    async activateSettings() {
      const view = await account.read();
      if (view?.device_state === "credential_present" && view.setup_state === "completed" &&
          !settingsPage.hidden && $("surface-settings").classList.contains("active")) {
        await account.refresh(false);
      }
    },
    showFirstRun() { return account.start(); },
    hideFirstRun() { if (lastSource === "startup") account.close(); },
    visibilityChanged() {
      if ((lastSource === "startup" && !consolePage.classList.contains("active")) ||
          (lastSource === "settings" && (settingsPage.hidden || !$("surface-settings").classList.contains("active")))) {
        account.close();
      }
    },
  };
  const events = window.__TAURI__?.event;
  if (events) {
    // Start the read immediately as well as after event registration. This closes
    // the registration/read gap if native startup publishes between the two.
    Promise.resolve(events.listen("account-state-changed", (event) => account.receive(event.payload)))
      .then(() => account.read(), () => {});
  }
  window.scAccount.showFirstRun();
})();
