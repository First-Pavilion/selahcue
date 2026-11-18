#!/usr/bin/env python3
"""Verify the operator Account UI in the actual dist shell with deterministic native IPC."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


OPERATOR = Path(__file__).resolve().parents[1] / "implementation/desktop/crates/selahcue-operator"
DIST = OPERATOR / "dist"
MAIN_WINDOW = next(
    window for window in json.loads((OPERATOR / "tauri.conf.json").read_text())["app"]["windows"]
    if window["label"] == "main"
)
SUPPORTED_VIEWPORTS = (
    (MAIN_WINDOW["minWidth"], MAIN_WINDOW["minHeight"]),
    (MAIN_WINDOW["width"], MAIN_WINDOW["height"]),
)
LONG_DEVICE_NAME = "W" * 80

STUB = r"""
(() => {
  const base = {
    revision: 1, setup_state: "needed", device_state: "unregistered",
    entitlement_state: "unavailable", operation_state: "idle",
    platform: "macos", app_version: "0.1.0", pending_cleanup: false,
  };
  const fixture = window.accountFixture = {
    view: { ...base, ...INITIAL_VIEW },
    response: {},
    calls: [],
    resolve: null,
    skipFailure: false,
    finishWebOpen: null,
    holdWebOpen: false,
    publish(fields) {
      this.view = { ...base, revision: this.view.revision + 1, ...fields };
      for (const listener of listeners) listener({ payload: this.view });
    },
  };
  const listeners = [];
  const operator = {
    plan_name: "Fixture service",
    items: [{ id: 1, kind: "scripture", title: "Genesis 1:13", is_live: true, is_staged: true }],
    live_index: 0, staged_index: 0, blackout: false, timer: null, staged_scripture: "Genesis 1:13",
    live_scripture: "Genesis 1:13", live_free_text: null,
    outputs: [{ role: "main", assigned: true, signal: "healthy" }], displays: [],
    translations: ["KJV"], theme: "classic", themes: ["classic"], saved_themes: [], screen_themes: [],
  };
  window.__TAURI__ = {
    event: {
      async listen(name, listener) {
        if (name === "account-state-changed") listeners.push(listener);
        return () => {};
      },
    },
    core: {
      async invoke(cmd, args) {
        if (cmd === "account_replace_device_credential") {
          fixture.calls.push({ cmd, keys: Object.keys(args).sort(), email: args.email,
            displayName: args.displayName, passwordMatched: args.password === "synthetic-password" });
        } else {
          fixture.calls.push({ cmd, args });
        }
        if (cmd === "account_view") return fixture.view;
        if (cmd === "account_open_web") {
          if (fixture.holdWebOpen) {
            const succeeds = await new Promise((resolve) => { fixture.finishWebOpen = resolve; });
            if (!succeeds) throw "browser_open_failed";
          }
          return;
        }
        if (cmd === "account_skip_setup") {
          if (fixture.skipFailure) throw "metadata_unavailable";
          fixture.view = { ...fixture.view, setup_state: "skipped", revision: fixture.view.revision + 1 };
          return fixture.view;
        }
        if (cmd === "account_sign_in_and_activate" || cmd === "account_activate_with_enrollment" ||
            cmd === "account_replace_device_credential") {
          const fields = fixture.response;
          if (fields.hold) {
            await new Promise((resolve) => { fixture.resolve = resolve; });
          }
          fixture.view = {
            ...base, revision: fixture.view.revision + 1, setup_state: fixture.view.setup_state, ...fields,
          };
          return fixture.view;
        }
        if (cmd === "account_retry_activation" || cmd === "account_retry_session_cleanup") {
          fixture.view = { ...fixture.view, ...fixture.response, revision: fixture.view.revision + 1 };
          return fixture.view;
        }
        if (cmd === "account_refresh") return fixture.view;
        if (cmd === "blackout") {
          operator.blackout = args.on;
          return { ...operator };
        }
        if (cmd === "clear" || cmd === "view") return { ...operator };
        if (cmd === "system_fonts" || cmd === "builtin_themes") return [];
        if (cmd === "render_console") {
          const frame = { w: 1, h: 1, rgba: btoa("\x00\x00\x00\xff") };
          return { available: true, preview: frame, live: frame };
        }
        return null;
      },
    },
  };
})();
"""

ACTIVE = {
    "setup_state": "completed",
    "device_state": "credential_present",
    "entitlement_state": "current",
    "license_state": "active",
    "display_name": "Fixture Booth",
    "plan_label": "Signed fixture plan",
    "instances_used": 0,
    "instance_limit": 5,
    "license_expires_at": "2028-01-01T00:00:00.123456789Z",
    "manifest_expires_at": "2027-10-01T00:00:00.987654321Z",
    "last_checked_at": "2027-09-01T12:34:56.001Z",
}


def rules(page, fields):
    page.evaluate("(fields) => { accountFixture.response = fields; }", fields)


def click(page, name):
    page.get_by_role("button", name=name, exact=True).click()


def fill_sign_in(page):
    page.get_by_label("Email", exact=True).fill("account@example.test")
    page.get_by_label("Password", exact=True).fill("synthetic-password")


def open_account(page, via_providers=True):
    page.locator("#app-menu-btn").click()
    page.locator('[data-surface="settings"]').first.click()
    if via_providers:
        click(page, "Account and device activation")
    else:
        page.locator('.set-nav[data-setpage="account"]').click()
    expect(page.locator("#account-settings-title")).to_be_visible()
    order = page.locator(".set-side [data-setpage]").evaluate_all("(items) => items.map(x => x.dataset.setpage)")
    assert order[:4] == ["general", "account", "preservice", "providers"]


def boot(browser, dist, viewport, initial=None):
    width, height = viewport
    page = browser.new_page(viewport={"width": width, "height": height}, reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
    page.add_init_script(STUB.replace("INITIAL_VIEW", json.dumps(initial or {})))
    page.goto((dist / "index.html").as_uri())
    return page, errors


def capture(page, directory, name):
    if directory:
        page.screenshot(path=directory / f"{name}.png", animations="disabled")


def assert_emergency_hit_targets(page, state):
    toolbar = page.get_by_role("toolbar", name="Emergency controls", exact=True)
    targets = []
    for name in ("Blackout the audience output", "Clear all live layers (double-Escape)"):
        button = toolbar.get_by_role("button", name=name, exact=True)
        geometry = button.evaluate("""button => {
          const { left, right, top, bottom, width, height } = button.getBoundingClientRect();
          const x = left + width / 2;
          const y = top + height / 2;
          return {
            left, right, top, bottom, x, y,
            viewportWidth: innerWidth, viewportHeight: innerHeight,
            onTarget: button.contains(document.elementFromPoint(x, y)),
            usable: !button.disabled && button.getAttribute("aria-disabled") !== "true",
          };
        }""")
        assert 0 <= geometry["left"] < geometry["right"] <= geometry["viewportWidth"], (state, name, geometry)
        assert 0 <= geometry["top"] < geometry["bottom"] <= geometry["viewportHeight"], (state, name, geometry)
        assert geometry["onTarget"] and geometry["usable"], (state, name, geometry)
        targets.append((geometry["x"], geometry["y"]))
    return targets


def assert_console_emergency(page):
    expect(page.locator("#surface-console")).to_be_visible()
    # Click the checked viewport coordinates so Playwright cannot scroll a
    # clipped control into view and accidentally turn the failure green.
    for x, y in assert_emergency_hit_targets(page, "sign-in before emergency clicks"):
        page.mouse.click(x, y)
    password = page.get_by_label("Password", exact=True)
    password.focus()
    assert_emergency_hit_targets(page, "focused password before emergency shortcuts")
    page.keyboard.press("Control+Shift+B")
    page.keyboard.press("Control+Shift+Period")
    page.wait_for_function("""() =>
        ["blackout", "clear"].every(cmd => accountFixture.calls.filter(call => call.cmd === cmd).length === 2)
    """)
    assert_emergency_hit_targets(page, "after emergency shortcuts")
    assert password.evaluate(
        """el => !el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true }))"""
    )


def assert_long_device_name(page):
    name = page.locator("#account-device-name")
    expect(name).to_have_text(LONG_DEVICE_NAME)
    expect(page.locator("#account-device-chip")).to_have_text("Activated")
    geometry = name.evaluate("""name => {
      const text = document.createRange();
      text.selectNodeContents(name);
      const chip = document.getElementById("account-device-chip").getBoundingClientRect();
      const row = name.closest(".set-row").getBoundingClientRect();
      return {
        textRight: Math.max(...Array.from(text.getClientRects(), line => line.right)),
        chipLeft: chip.left, chipRight: chip.right, rowRight: row.right,
        viewportWidth: innerWidth, viewportHeight: innerHeight,
      };
    }""")
    assert geometry["textRight"] <= geometry["chipLeft"] < geometry["chipRight"] <= geometry["rowRight"], geometry


def exercise(browser, dist, screenshots, viewport):
    page, errors = boot(browser, dist, viewport)
    expect(page.get_by_role("heading", name="Activate SelahCue")).to_be_visible()
    assert page.locator(".account-offline-pill img").evaluate("img => img.complete && img.naturalWidth === 7")
    assert_emergency_hit_targets(page, "startup chooser")
    capture(page, screenshots, "a0-chooser")
    click(page, "Enter an organisation enrollment key")
    expect(page.get_by_role("heading", name="Enter your enrollment key")).to_be_focused()
    assert_emergency_hit_targets(page, "startup enrollment after heading focus")
    page.get_by_label("Organisation enrollment key").focus()
    assert_emergency_hit_targets(page, "startup enrollment after key focus")
    capture(page, screenshots, "a2-startup-enrollment")
    click(page, "Sign in with your account instead")
    expect(page.get_by_role("heading", name="Sign in to SelahCue")).to_be_focused()
    assert_emergency_hit_targets(page, "sign-in after heading focus")
    assert page.locator("#account-dismiss").evaluate("""button => {
      const region = document.getElementById("account-first-run").getBoundingClientRect();
      const action = button.getBoundingClientRect();
      return action.top >= region.top && action.bottom <= region.bottom;
    }""")
    capture(page, screenshots, "a1-sign-in")
    fill_sign_in(page)
    assert_console_emergency(page)
    rules(page, {"error_code": "invalid_credentials"})
    click(page, "Continue")
    expect(page.locator("#account-sign-in-error")).to_contain_text("could not be verified")
    expect(page.locator("#account-password")).to_have_value("")
    assert_emergency_hit_targets(page, "sign-in after invalid credentials")
    fill_sign_in(page)
    rules(page, {"hold": True, **ACTIVE})
    page.get_by_label("Password", exact=True).press("Enter")
    expect(page.get_by_role("heading", name="Activating this device…")).to_be_visible()
    expect(page.locator("#account-password")).to_have_value("")
    assert_emergency_hit_targets(page, "sign-in activation held")
    capture(page, screenshots, "a3-pending")
    page.locator("#account-sign-in").evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true }))")
    assert page.evaluate("""() => accountFixture.calls.filter(x => x.cmd === "account_sign_in_and_activate").length""") == 2
    click(page, "Skip — set up later")
    expect(page.locator("#account-card")).to_be_hidden()
    expect(page.locator("#surface-console")).to_be_focused()
    page.wait_for_function("accountFixture.view.setup_state === 'skipped'")
    page.locator("#blackout").focus()
    page.evaluate("accountFixture.resolve()")
    page.wait_for_function("accountFixture.view.setup_state === 'completed'")
    expect(page.locator("#account-card")).to_be_hidden()
    expect(page.locator("#blackout")).to_be_focused()
    assert not errors, errors
    page.close()

    restarted, errors = boot(browser, dist, viewport, {"setup_state": "skipped"})
    restarted.wait_for_function("accountFixture.calls.some(x => x.cmd === 'account_view')")
    expect(restarted.locator("#account-first-run")).to_be_hidden()
    open_account(restarted)
    assert_emergency_hit_targets(restarted, "Settings Account entry")
    expect(restarted.get_by_role("button", name="Set up this device")).to_be_visible()
    click(restarted, "Set up this device")
    click(restarted, "Enter an organisation enrollment key")
    assert_emergency_hit_targets(restarted, "Settings enrollment before key focus")
    capture(restarted, screenshots, "a2-enrollment")
    restarted.get_by_label("Organisation enrollment key").fill("fixture-enrollment-key")
    restarted.get_by_label("Device name").fill("Fixture Booth")
    rules(restarted, {"error_code": "unknown_key"})
    click(restarted, "Activate this device")
    expect(restarted.locator("#account-enrollment-error")).to_contain_text("don’t recognise")
    expect(restarted.get_by_label("Organisation enrollment key")).to_have_value("")
    expect(restarted.get_by_label("Organisation enrollment key")).to_be_focused()
    assert_emergency_hit_targets(restarted, "Settings enrollment with key error and focus")
    capture(restarted, screenshots, "a4-unknown-key")

    for code, heading, screenshot in [
        ("policy_denied", "This device couldn’t be activated", "a5-policy"),
        ("no_active_license", "No active SelahCue plan", "a6-no-plan"),
        ("network_unavailable", "Can’t reach SelahCue right now", "a7-offline"),
    ]:
        rules(restarted, {"error_code": code, "operation_state": "retry_pending" if code == "network_unavailable" else "idle"})
        restarted.get_by_label("Organisation enrollment key").fill("fixture-enrollment-key")
        restarted.locator('#account-enroll button[type="submit"]').click()
        expect(restarted.get_by_role("heading", name=heading)).to_be_visible()
        capture(restarted, screenshots, screenshot)
        click(restarted, "Try again")
        expect(restarted.get_by_label("Organisation enrollment key")).to_have_value("")

    rules(restarted, {"hold": True, **ACTIVE})
    restarted.get_by_label("Organisation enrollment key").fill("fixture-enrollment-key")
    click(restarted, "Activate this device")
    expect(restarted.get_by_role("heading", name="Activating this device…")).to_be_visible()
    assert_emergency_hit_targets(restarted, "Settings enrollment activation held")
    click(restarted, "Back to Account")
    expect(restarted.locator("#account-card")).to_be_hidden()
    restarted.locator("#account-open-providers").click()
    expect(restarted.get_by_role("heading", name="Providers & Privacy")).to_be_visible()
    restarted.evaluate("accountFixture.resolve()")
    click(restarted, "Account and device activation")
    expect(restarted.locator("#account-device-name")).to_have_text("Fixture Booth")
    expect(restarted.locator("#account-instance-count")).to_have_text("0 of 5 used")
    expect(restarted.locator("#account-manifest-expiry")).to_have_text(ACTIVE["manifest_expires_at"])
    expect(restarted.locator("#account-last-checked")).to_have_text(ACTIVE["last_checked_at"])
    expect(restarted.get_by_text("SelahCue cloud providers unavailable")).to_be_visible()
    expect(restarted.get_by_role("button", name="Deactivate this device")).to_have_count(0)
    restarted.wait_for_function("""() => accountFixture.calls.some(
      x => x.cmd === "account_refresh" && x.args.explicit === false
    )""")
    assert restarted.locator("#account-active-dot").evaluate("img => img.complete && img.naturalWidth === 9")
    assert restarted.locator("#account-entitlement-dot").evaluate("img => img.complete && img.naturalWidth === 6")
    assert_emergency_hit_targets(restarted, "Settings activated")
    capture(restarted, screenshots, "a8-a10-activated-status")
    for fields in (
        {"setup_state": "completed", "device_state": "reauthentication_needed"},
        {"setup_state": "skipped", "device_state": "unregistered", "operation_state": "retry_pending"},
    ):
        restarted.evaluate("(fields) => accountFixture.publish(fields)",
                           {**fields, "error_code": "reauthentication_required"})
        expect(restarted.locator("#account-recover")).to_be_hidden()
        click(restarted, "Sign in to continue")
        expect(restarted.get_by_role("heading", name="Sign in to SelahCue")).to_be_focused()
        expect(restarted.locator("#account-sign-in-error")).to_have_text(
            "Sign in again to finish setting up this device."
        )
        click(restarted, "Back to Account")
    restarted.evaluate("""() => accountFixture.publish({
      setup_state: 'skipped', device_state: 'custody_unavailable', error_code: 'credential_presence_unavailable'
    })""")
    expect(restarted.locator("#account-device-status")).to_contain_text("storage unavailable")
    expect(restarted.locator("#account-plan-label")).to_be_hidden()
    expect(restarted.locator("#account-manifest-expiry")).to_be_hidden()
    assert_emergency_hit_targets(restarted, "Settings credential storage unavailable")
    assert not errors, errors
    restarted.close()

    activated_restart, errors = boot(browser, dist, viewport, {**ACTIVE, "display_name": LONG_DEVICE_NAME})
    activated_restart.wait_for_function("accountFixture.calls.some(x => x.cmd === 'account_view')")
    expect(activated_restart.locator("#account-first-run")).to_be_hidden()
    open_account(activated_restart, via_providers=False)
    expect(activated_restart.locator("#account-device-status")).to_have_text("Device activated")
    expect(activated_restart.locator("#account-plan-label")).to_have_text("Signed fixture plan")
    expect(activated_restart.locator("#account-start-setup")).to_be_hidden()
    assert_long_device_name(activated_restart)
    assert_emergency_hit_targets(activated_restart, "Settings restored long-name device")
    capture(activated_restart, screenshots, "a8-a10-long-device-name")
    assert not errors, errors
    activated_restart.close()

    offline, errors = boot(browser, dist, viewport)
    expect(offline.get_by_role("heading", name="Activate SelahCue")).to_be_visible()
    offline.evaluate("accountFixture.skipFailure = true")
    click(offline, "Sign in to your SelahCue account")
    fill_sign_in(offline)
    rules(offline, {"error_code": "network_unavailable"})
    click(offline, "Continue")
    assert_emergency_hit_targets(offline, "startup network error")
    click(offline, "Continue offline")
    expect(offline.locator("#account-card")).to_be_hidden()
    expect(offline.get_by_role("button", name="Retry saving choice")).to_be_visible()
    offline.evaluate("accountFixture.skipFailure = false")
    click(offline, "Retry saving choice")
    expect(offline.locator("#account-setup-status")).to_be_hidden()
    assert_emergency_hit_targets(offline, "durable Skip retry complete")
    assert offline.evaluate("""() => ![localStorage, sessionStorage].some(store =>
      JSON.stringify(store).includes("synthetic-password"))""")
    assert not errors, errors
    offline.close()


def exercise_web_links(browser, dist, screenshots, viewport):
    page, errors = boot(browser, dist, viewport)
    original_url = page.url
    sign_in = page.get_by_role("heading", name="Sign in to SelahCue", exact=True)
    click(page, "Sign in to your SelahCue account")
    expect(sign_in).to_be_focused()
    fill_sign_in(page)

    actions = [
        ("Create account", "signup"),
        ("Forgot password?", "forgot_password"),
        ("Verify email / resend link", "verification"),
    ]
    previous = page.get_by_role("button", name="Continue", exact=True)
    # macOS WebKit uses Option-Tab to traverse every focusable control.
    next_control = "Alt+Tab" if sys.platform == "darwin" and browser.browser_type.name == "webkit" else "Tab"
    for label, _ in actions:
        action = page.get_by_role("button", name=label, exact=True)
        previous.press(next_control)
        expect(action).to_be_focused()
        assert action.evaluate("""button => {
          const r = button.getBoundingClientRect();
          return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth &&
            button.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
        }"""), (viewport, label)
        previous = action
    capture(page, screenshots, "a1-browser-entry-points")

    signup = page.get_by_role("button", name=actions[0][0], exact=True)
    page.evaluate("accountFixture.holdWebOpen = true")
    signup.press("Enter")
    expect(signup).to_be_focused()
    expect(signup).to_have_attribute("aria-disabled", "true")
    expect(page.get_by_label("Password", exact=True)).to_have_value("")
    assert_emergency_hit_targets(page, "startup sign-in while browser dispatch is held")
    signup.press("Enter")
    assert page.evaluate("""() => accountFixture.calls.filter(
      x => x.cmd === "account_open_web"
    ).length""") == 1
    page.evaluate("accountFixture.finishWebOpen(false)")
    error = page.locator("#account-web-error")
    expect(error).to_be_in_viewport(ratio=1)
    expect(page.locator("#account-sign-in-error")).to_be_hidden()
    expect(signup).to_have_attribute("aria-disabled", "false")
    expect(signup).to_be_focused()
    capture(page, screenshots, "a1-browser-open-failure")

    page.evaluate("accountFixture.holdWebOpen = false")
    for label, _ in actions:
        click(page, label)
        expect(page.get_by_role("button", name=label, exact=True)).to_have_attribute("aria-disabled", "false")
        expect(sign_in).to_be_visible()
        expect(error).to_be_hidden()
    assert page.url == original_url and len(page.context.pages) == 1
    assert page.evaluate("""() => accountFixture.calls.filter(
      x => x.cmd.startsWith("account_") && x.cmd !== "account_view"
    )""") == [{"cmd": "account_open_web", "args": {"destination": dest}}
               for dest in ["signup", *(item[1] for item in actions)]]
    fill_sign_in(page)
    rules(page, {"error_code": "account_not_active"})
    click(page, "Continue")
    expect(page.locator("#account-sign-in-error")).to_be_visible()
    expect(page.get_by_role("button", name=actions[2][0], exact=True)).to_be_visible()
    assert page.evaluate("""() => accountFixture.calls.filter(
      x => x.cmd === "account_sign_in_and_activate"
    ).length""") == 1

    click(page, "Skip — set up later")
    page.wait_for_function("accountFixture.view.setup_state === 'skipped'")
    open_account(page, via_providers=False)
    click(page, "Set up this device")
    click(page, "Sign in to your SelahCue account")
    page.evaluate("accountFixture.holdWebOpen = true")
    click(page, "Forgot password?")
    expect(page.get_by_role("button", name="Continue", exact=True)).to_be_enabled()
    assert_emergency_hit_targets(page, "Settings sign-in while browser dispatch is held")
    page.locator('.set-nav[data-setpage="providers"]').click()
    expect(page.locator("#account-card")).to_be_hidden()
    click(page, "Account and device activation")
    click(page, "Set up this device")
    click(page, "Sign in to your SelahCue account")
    page.evaluate("accountFixture.finishWebOpen(false)")
    expect(page.get_by_role("button", name="Forgot password?", exact=True)).to_have_attribute("aria-disabled", "false")
    expect(error).to_be_hidden()
    expect(sign_in).to_be_focused()
    assert_emergency_hit_targets(page, "Settings sign-in after late browser dispatch failure")
    assert page.url == original_url
    assert not errors, errors
    page.close()


def exercise_combined_errors(browser, dist, screenshots, viewport, code):
    page, errors = boot(browser, dist, viewport)
    click(page, "Sign in to your SelahCue account")
    fill_sign_in(page)
    rules(page, {"error_code": code})
    click(page, "Continue")
    sign_in_error = page.locator("#account-sign-in-error")
    expect(sign_in_error).to_be_visible()

    next_control = "Alt+Tab" if sys.platform == "darwin" and browser.browser_type.name == "webkit" else "Tab"
    page.get_by_role("button", name="Continue", exact=True).focus()
    for label in ("Create account", "Forgot password?", "Verify email / resend link"):
        page.keyboard.press(next_control)
        action = page.get_by_role("button", name=label, exact=True)
        expect(action).to_be_focused()
    page.evaluate("accountFixture.holdWebOpen = true")
    page.keyboard.press("Enter")
    expect(action).to_have_attribute("aria-disabled", "true")
    scroll_positions = """() => [document.scrollingElement, document.getElementById("surface-console")]
      .map(element => [element.scrollLeft, element.scrollTop])"""
    before = page.evaluate(scroll_positions)

    page.evaluate("accountFixture.finishWebOpen(false)")
    error = page.locator("#account-web-error")
    expect(error).to_contain_text("couldn’t open your browser")
    expect(error, f"{viewport} {code} browser feedback must fit inside the visible card").to_be_in_viewport(
        ratio=1, timeout=2000
    )
    expect(action).to_be_focused()
    expect(action).to_have_attribute("aria-disabled", "false")
    expect(action).to_be_in_viewport(ratio=1)
    assert page.evaluate(scroll_positions) == before
    assert_emergency_hit_targets(page, f"startup sign-in with {code} and browser launch errors")
    skip = page.get_by_role("button", name="Skip — set up later", exact=True)
    assert skip.evaluate("""button => {
      const { x, y, width, height } = button.getBoundingClientRect();
      return button.contains(document.elementFromPoint(x + width / 2, y + height / 2));
    }""")
    capture(page, screenshots, f"a1-browser-open-failure-{code}")

    page.evaluate("accountFixture.holdWebOpen = false")
    page.keyboard.press("Enter")
    expect(error).to_be_hidden()
    expect(sign_in_error).to_be_visible()
    expect(action).to_be_focused()
    assert page.evaluate("""() => accountFixture.calls.filter(x => x.cmd === "account_open_web")""") == [
        {"cmd": "account_open_web", "args": {"destination": "verification"}},
        {"cmd": "account_open_web", "args": {"destination": "verification"}},
    ]
    click(page, "Skip — set up later")
    expect(page.locator("#account-card")).to_be_hidden()
    page.wait_for_function("accountFixture.view.setup_state === 'skipped'")
    assert not errors, errors
    page.close()


def exercise_reauthentication(browser, dist, viewport):
    page, errors = boot(browser, dist, viewport)
    click(page, "Sign in to your SelahCue account")
    fill_sign_in(page)
    rules(page, {"operation_state": "retry_pending", "error_code": "network_unavailable"})
    click(page, "Continue")
    expect(page.get_by_role("heading", name="Can’t reach SelahCue right now")).to_be_focused()

    rules(page, {"operation_state": "retry_pending", "error_code": "reauthentication_required"})
    click(page, "Try again")
    expect(page.get_by_role("heading", name="Sign in to SelahCue")).to_be_focused()
    expect(page.locator("#account-sign-in-error")).to_have_text("Sign in again to finish setting up this device.")
    expect(page.get_by_label("Email", exact=True)).to_have_value("")
    expect(page.get_by_label("Password", exact=True)).to_have_value("")
    expect(page.get_by_role("button", name="Try again", exact=True)).to_be_hidden()
    assert_emergency_hit_targets(page, "startup sign-in after requested reauthentication")

    fill_sign_in(page)
    rules(page, ACTIVE)
    page.get_by_label("Password", exact=True).press("Enter")
    expect(page.locator("#account-card")).to_be_hidden()
    expect(page.get_by_label("Password", exact=True)).to_have_value("")
    assert page.evaluate("""() => accountFixture.calls.filter(x => x.cmd === "account_retry_activation" ||
      x.cmd === "account_sign_in_and_activate").map(x => x.cmd)""") == [
        "account_sign_in_and_activate", "account_retry_activation", "account_sign_in_and_activate"
    ]
    assert not errors, errors
    page.close()


def exercise_replacement_consent(browser, dist, viewport, *, cancel=False):
    recovery = {**ACTIVE, "device_state": "reauthentication_needed", "error_code": "reauthentication_required"}
    page, errors = boot(browser, dist, viewport, initial=recovery)
    action = "Replace this device’s credential"
    explanation = "The previous credential for this installation will stop working. Sign in as an administrator to continue."
    try:
        open_account(page)
        replace = page.get_by_role("button", name=action, exact=True)
        assert replace.is_visible(), f"{viewport}: established-device recovery must offer ‘{action}’"
        replace.click()
        assert page.get_by_text(explanation, exact=True).is_visible(), (
            "The administrator must see the effect of replacement before submitting credentials"
        )
        password = page.get_by_label("Password", exact=True)
        assert password.is_visible(), "The explicit replacement action must open administrator sign-in"
        form = password.locator("xpath=ancestor::form")
        assert page.evaluate("document.getElementById('account-card').contains(document.activeElement)"), (
            "Keyboard focus must follow the replacement action into its form"
        )
        assert not page.evaluate("""() => accountFixture.calls.some(call =>
          ["account_replace_device_credential", "account_retry_activation",
           "account_sign_in_and_activate"].includes(call.cmd))""")
        fill_sign_in(page)
        passwords_cleared = """() => [...document.querySelectorAll('input[type="password"]')].every(
          input => input.value === "")"""
        if cancel:
            back = page.locator("#account-card").get_by_role("button", name=re.compile("back|cancel", re.I)).first
            assert back.is_visible(), "Provide a way to leave the replacement form before submitting"
            back.click()
            assert page.evaluate(passwords_cleared), "Leaving replacement must clear the typed password"
            assert not page.evaluate("""() => accountFixture.calls.some(
              call => call.cmd === "account_replace_device_credential")""")
            assert not errors, errors
            return
        rules(page, {**ACTIVE, "hold": True})
        # Model two rapid submit events on the real form before the IPC reply.
        form.evaluate("""form => { form.requestSubmit(); form.dispatchEvent(
          new Event("submit", { bubbles: true, cancelable: true })); }""")
        assert page.evaluate("typeof accountFixture.resolve === 'function'"), (
            "The administrator's submit must reach the native replacement command"
        )
        assert page.evaluate(passwords_cleared), "Clear the password on submit"
        assert not form.is_visible() or form.locator('button[type="submit"]').is_disabled(), (
            "The form must stop accepting input while replacement is pending"
        )
        assert page.evaluate("""() => accountFixture.calls.filter(
          call => call.cmd === "account_replace_device_credential")""") == [{
            "cmd": "account_replace_device_credential", "keys": ["displayName", "email", "password"],
            "email": "account@example.test", "displayName": "Fixture Booth", "passwordMatched": True,
        }]
        page.evaluate("accountFixture.resolve()")
        expect(page.locator("#account-card")).to_be_hidden()
        assert not errors, errors
    finally:
        page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("chromium", "webkit"), default="chromium")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    dist = Path(os.environ.get("SELAHCUE_OPERATOR_DIST", str(DIST))).resolve()
    with sync_playwright() as playwright:
        browser = getattr(playwright, args.engine).launch()
        for width, height in SUPPORTED_VIEWPORTS:
            size = f"{width}x{height}"
            screenshots = args.screenshots / size if args.screenshots else None
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
            exercise(browser, dist, screenshots, (width, height))
            exercise_web_links(browser, dist, screenshots, (width, height))
            for code in ("invalid_credentials", "account_not_active"):
                exercise_combined_errors(browser, dist, screenshots, (width, height), code)
            exercise_reauthentication(browser, dist, (width, height))
            print(f"Account setup, browser links, Settings and emergency hit targets passed in {args.engine} at {size}.", flush=True)
        for viewport in SUPPORTED_VIEWPORTS:
            exercise_replacement_consent(browser, dist, viewport)
            exercise_replacement_consent(browser, dist, viewport, cancel=True)
        browser.close()


if __name__ == "__main__":
    main()
