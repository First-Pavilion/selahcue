"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { createAccount } = require("../implementation/desktop/crates/selahcue-operator/dist/account.js");

function snapshot(revision, fields = {}) {
  return { revision, setup_state: "needed", device_state: "unregistered",
    entitlement_state: "unavailable", operation_state: "idle", ...fields };
}

function defer() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("Skip acknowledges while activation is pending and late activation cannot regain focus", async () => {
  const held = defer();
  const calls = [];
  let state;
  const account = createAccount((command, args) => {
    calls.push([command, args]);
    if (command === "account_view") return Promise.resolve(snapshot(1));
    if (command === "account_sign_in_and_activate") return held.promise;
    assert.equal(command, "account_skip_setup");
    return Promise.resolve(snapshot(3, { setup_state: "skipped", operation_state: "busy" }));
  }, (next) => { state = next; });

  await account.start();
  assert.equal(state.stage, "chooser");
  account.choose("signIn");
  const action = account.submit({ email: " person@example.test ", password: "synthetic", displayName: "Booth" });
  account.submit({ email: "person@example.test", password: "duplicate", displayName: "Booth" });
  assert.equal(state.stage, "pending");
  await account.dismiss();
  assert.equal(state.source, null);
  held.resolve(snapshot(4, { setup_state: "completed", device_state: "credential_present" }));
  await action;
  assert.equal(state.source, null);
  assert.deepEqual(calls, [
    ["account_view", undefined],
    ["account_sign_in_and_activate", { email: "person@example.test", password: "synthetic", displayName: "Booth" }],
    ["account_skip_setup", undefined],
  ]);
});

test("restart respects durable Skip, and older events cannot overwrite signed device details", async () => {
  let state;
  const account = createAccount(async () => snapshot(4, { setup_state: "skipped" }), (next) => { state = next; });
  await account.start();
  assert.equal(state.source, null);
  account.receive(snapshot(8, { setup_state: "completed", device_state: "credential_present",
    entitlement_state: "current", plan_label: "Verified plan", instances_used: 0, instance_limit: 4,
    manifest_expires_at: "2027-12-01T12:34:56.123456789Z" }));
  account.receive(snapshot(5));
  assert.equal(state.view.plan_label, "Verified plan");
  assert.equal(state.view.instances_used, 0);
  assert.equal(state.view.manifest_expires_at, "2027-12-01T12:34:56.123456789Z");
  assert.equal(state.source, null);
});

test("enrollment uses typed errors, and enrollment retry asks for the key again", async () => {
  const calls = [];
  let state, reply = snapshot(2, { error_code: "unknown_key" });
  const account = createAccount(async (command, args) => {
    calls.push([command, args]);
    if (command === "account_view") return snapshot(1);
    return reply;
  }, (next) => { state = next; });
  await account.start();
  account.choose("enroll");
  await account.submit({ enrollmentKey: " synthetic-key ", displayName: "Booth" });
  assert.equal(state.stage, "enroll");
  assert.equal(state.formError, "unknown_key");
  assert.deepEqual(calls[1], ["account_activate_with_enrollment", { enrollmentKey: "synthetic-key", displayName: "Booth" }]);

  reply = snapshot(3, { error_code: "network_unavailable", operation_state: "retry_pending" });
  await account.submit({ enrollmentKey: "synthetic-key", displayName: "Booth" });
  assert.equal(state.stage, "offline");
  await account.retry();
  assert.equal(state.stage, "enroll");
  assert.equal(calls.length, 3);
});

test("ambiguous sign-in with a lost account session asks for fresh credentials", async () => {
  const calls = [];
  const ambiguous = snapshot(2, { operation_state: "retry_pending", error_code: "network_unavailable" });
  const reauth = snapshot(3, { operation_state: "retry_pending", error_code: "reauthentication_required" });
  const completed = snapshot(4, { setup_state: "completed", device_state: "credential_present" });
  let state;
  const account = createAccount(async (command, args) => {
    calls.push([command, args]);
    if (command === "account_view") return snapshot(1);
    if (command === "account_retry_activation") return reauth;
    assert.equal(command, "account_sign_in_and_activate");
    return args.password === "fresh-synthetic" ? completed : ambiguous;
  }, (next) => { state = next; });

  await account.start();
  account.choose("signIn");
  await account.submit({ email: "person@example.test", password: "old-synthetic", displayName: "Booth" });
  assert.equal(state.stage, "offline");
  await account.retry();
  assert.equal(state.stage, "signIn");
  assert.equal(state.formError, "reauthentication_required");
  assert.equal(state.view, reauth);
  assert.equal(state.operationPending, false);

  // Even with a native retry record, only an explicit fresh sign-in can proceed.
  await account.retry();
  assert.equal(state.stage, "signIn");
  assert.equal(state.formError, "reauthentication_required");
  assert.equal(calls.length, 3);
  await account.submit({ email: " person@example.test ", password: "fresh-synthetic", displayName: "Booth" });
  assert.equal(state.view, completed);
  assert.equal(state.source, null);
  assert.deepEqual(calls.slice(2), [
    ["account_retry_activation", undefined],
    ["account_sign_in_and_activate", { email: "person@example.test", password: "fresh-synthetic", displayName: "Booth" }],
  ]);
});

test("late reauthentication updates native status without changing the current route or focus", async () => {
  for (const leave of ["dismiss", "navigate"]) {
    const held = defer();
    const draws = [];
    const account = createAccount(async (command) => {
      if (command === "account_view") return snapshot(1);
      if (command === "account_sign_in_and_activate") {
        return snapshot(2, { operation_state: "retry_pending", error_code: "service_unavailable" });
      }
      if (command === "account_skip_setup") {
        return snapshot(3, { setup_state: "skipped", operation_state: "retry_pending", error_code: "service_unavailable" });
      }
      assert.equal(command, "account_retry_activation");
      return held.promise;
    }, (state, focus) => { draws.push({ state, focus }); });

    await account.start();
    account.choose("signIn");
    await account.submit({ email: "person@example.test", password: "synthetic", displayName: "Booth" });
    const retrying = account.retry();
    if (leave === "dismiss") await account.dismiss();
    else {
      account.close();
      account.openSettings();
    }
    const current = draws.at(-1).state;
    draws.length = 0;
    const reauth = snapshot(4, {
      setup_state: leave === "dismiss" ? "skipped" : "needed",
      operation_state: "retry_pending", error_code: "reauthentication_required",
    });
    held.resolve(reauth);
    await retrying;
    assert.ok(draws.length);
    for (const { state, focus } of draws) {
      assert.equal(state.source, current.source);
      assert.equal(state.stage, current.stage);
      assert.equal(state.formError, null);
      assert.equal(focus, false);
    }
    assert.equal(draws.at(-1).state.view, reauth);
    assert.equal(draws.at(-1).state.operationPending, false);
  }
});

test("failed durable Skip stays usable and may be retried", async () => {
  let state, fails = true;
  const account = createAccount(async (command) => {
    if (command === "account_view") return snapshot(1);
    if (fails) throw "metadata_unavailable";
    return snapshot(2, { setup_state: "skipped" });
  }, (next) => { state = next; });
  await account.start();
  await account.dismiss();
  assert.equal(state.source, null);
  assert.equal(state.skipError, true);
  fails = false;
  await account.dismiss();
  assert.equal(state.skipError, false);
  assert.equal(state.view.setup_state, "skipped");
});

test("browser entry points leave activation to a separate native sign-in", async () => {
  for (const destination of ["signup", "forgot_password", "verification"]) {
    const calls = [];
    let state;
    const account = createAccount(async (command, args) => {
      calls.push([command, args]);
      if (command === "account_view") return snapshot(1);
      if (command === "account_open_web") return;
      assert.equal(command, "account_sign_in_and_activate");
      return snapshot(2, { error_code: "invalid_credentials" });
    }, (next) => { state = next; });

    await account.start();
    account.choose("signIn");
    const before = state.view;
    await account.openWeb(destination);
    assert.equal(state.stage, "signIn");
    assert.equal(state.view, before);
    assert.equal(state.operationPending, false);
    assert.deepEqual(calls, [["account_view", undefined], ["account_open_web", { destination }]]);
    await account.submit({ email: " account@example.test ", password: "synthetic", displayName: "Booth" });
    assert.deepEqual(calls[2], ["account_sign_in_and_activate", {
      email: "account@example.test", password: "synthetic", displayName: "Booth",
    }]);
  }
});

test("browser launch errors can be retried independently of the sign-in form", async () => {
  let state;
  const held = defer();
  const destinations = [];
  const account = createAccount(async (command, args) => {
    if (command === "account_view") return snapshot(1);
    assert.equal(command, "account_open_web");
    destinations.push(args.destination);
    if (destinations.length === 1) return held.promise;
  }, (next) => { state = next; });

  await account.start();
  account.choose("signIn");
  const opening = account.openWeb("signup");
  assert.equal(state.webPending, true);
  assert.equal(state.operationPending, false);
  await account.openWeb("verification");
  assert.deepEqual(destinations, ["signup"]);
  held.reject("browser_open_failed");
  await opening;
  assert.equal(state.webPending, false);
  assert.equal(state.webError, true);
  assert.equal(state.formError, null);
  await account.openWeb("signup");
  assert.equal(state.webError, false);
  assert.deepEqual(destinations, ["signup", "signup"]);
});

test("a late browser launch error is discarded when returning to sign-in", async () => {
  let state;
  const held = defer();
  const account = createAccount(async (command) => {
    if (command === "account_view") return snapshot(1);
    assert.equal(command, "account_open_web");
    return held.promise;
  }, (next) => { state = next; });

  await account.start();
  account.choose("signIn");
  const opening = account.openWeb("forgot_password");
  account.choose("chooser");
  account.choose("signIn");
  held.reject("browser_open_failed");
  await opening;
  assert.equal(state.stage, "signIn");
  assert.equal(state.webPending, false);
  assert.equal(state.webError, false);
});

test("established-device recovery requires consent and a fresh administrator submission", async () => {
  const recovery = snapshot(1, { setup_state: "completed", device_state: "reauthentication_needed",
    error_code: "reauthentication_required", entitlement_state: "current", display_name: "Booth" });
  const held = defer();
  const calls = [];
  let state;
  const account = createAccount(async (command, args) => {
    // Inspect the synthetic password at the IPC boundary; retain only its match.
    calls.push({ command, keys: Object.keys(args || {}).sort(), email: args?.email,
      displayName: args?.displayName, passwordMatches: args?.password === "fixture-password" });
    if (command === "account_replace_device_credential") return held.promise;
    return recovery;
  }, (next) => { state = next; });

  await account.start();
  await account.recover();
  assert.deepEqual(calls.map(call => call.command), ["account_view"],
    "Opening established-device replacement must let the administrator review consent before any native operation");

  const fields = { email: " operator@example.test ", password: "fixture-password", displayName: "Booth" };
  const submission = account.submit(fields);
  assert.equal(state.operationPending, true);
  const duplicate = account.submit(fields);
  const [replacement] = calls.slice(1);
  assert.equal(calls.length, 2, "A second submit must not dispatch while replacement is pending");
  assert.deepEqual(replacement, { command: "account_replace_device_credential",
    keys: ["displayName", "email", "password"], email: "operator@example.test",
    displayName: "Booth", passwordMatches: true });
  held.resolve(snapshot(2, { setup_state: "completed", device_state: "credential_present" }));
  await Promise.all([submission, duplicate]);
  assert.equal(state.operationPending, false);
});

test("leaving credential replacement restores ordinary sign-in", async () => {
  const calls = [];
  const recovery = snapshot(1, { setup_state: "completed", device_state: "reauthentication_needed",
    error_code: "reauthentication_required", entitlement_state: "current", display_name: "Booth" });
  const account = createAccount(async (command) => {
    calls.push(command);
    return recovery;
  }, () => {});
  await account.start();
  await account.recover();
  account.close();
  account.openSettings();
  account.choose("signIn");
  await account.submit({ email: "operator@example.test", password: "fixture-password", displayName: "Booth" });
  assert.deepEqual(calls, ["account_view", "account_sign_in_and_activate"],
    "Closing recovery must clear replacement consent before ordinary sign-in");
});

test("background refresh and ordinary Retry on an established device preserve ordinary sign-in", async () => {
  const calls = [];
  const established = snapshot(1, { setup_state: "completed", device_state: "reauthentication_needed",
    error_code: "reauthentication_required", entitlement_state: "current", display_name: "Booth" });
  const account = createAccount(async (command, args) => {
    calls.push({ command, explicit: args?.explicit });
    return established;
  }, () => {});
  await account.start();
  await account.refresh(false);
  account.openSettings();
  await account.retry();
  await account.submit({ email: "operator@example.test", password: "fixture-password", displayName: "Booth" });
  assert.deepEqual(calls, [
    { command: "account_view", explicit: undefined },
    { command: "account_refresh", explicit: false },
    { command: "account_sign_in_and_activate", explicit: undefined },
  ]);
});
