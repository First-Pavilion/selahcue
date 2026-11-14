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
