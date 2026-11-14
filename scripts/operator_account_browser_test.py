#!/usr/bin/env python3
"""Verify the operator Account UI in the actual dist shell with deterministic native IPC."""

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


DIST = Path(__file__).resolve().parents[1] / "implementation/desktop/crates/selahcue-operator/dist"

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
        fixture.calls.push({ cmd, args });
        if (cmd === "account_view") return fixture.view;
        if (cmd === "account_skip_setup") {
          if (fixture.skipFailure) throw "metadata_unavailable";
          fixture.view = { ...fixture.view, setup_state: "skipped", revision: fixture.view.revision + 1 };
          return fixture.view;
        }
        if (cmd === "account_sign_in_and_activate" || cmd === "account_activate_with_enrollment") {
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


def boot(browser, dist, initial=None, width=1520, height=1080):
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


def assert_console_emergency(page):
    expect(page.locator("#surface-console")).to_be_visible()
    page.locator("#blackout").click()
    page.locator("#clear-all").click()
    page.get_by_label("Password", exact=True).focus()
    page.keyboard.press("Control+Shift+B")
    page.keyboard.press("Control+Shift+Period")
    page.wait_for_function("""() =>
        ["blackout", "clear"].every(cmd => accountFixture.calls.filter(call => call.cmd === cmd).length === 2)
    """)
    assert page.get_by_label("Password", exact=True).evaluate(
        """el => !el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true }))"""
    )


def exercise(browser, dist, screenshots):
    page, errors = boot(browser, dist)
    expect(page.get_by_role("heading", name="Activate SelahCue")).to_be_visible()
    capture(page, screenshots, "a0-chooser")
    click(page, "Sign in to your SelahCue account")
    expect(page.get_by_role("heading", name="Sign in to SelahCue")).to_be_focused()
    assert page.locator("#account-dismiss").evaluate("""button => {
      const region = document.getElementById("account-first-run").getBoundingClientRect();
      const action = button.getBoundingClientRect();
      return action.top >= region.top && action.bottom <= region.bottom;
    }""")
    capture(page, screenshots, "a1-sign-in")
    fill_sign_in(page)
    assert_console_emergency(page)
    rules(page, {"hold": True, **ACTIVE})
    page.get_by_label("Password", exact=True).press("Enter")
    expect(page.get_by_role("heading", name="Activating this device…")).to_be_visible()
    expect(page.locator("#account-password")).to_have_value("")
    capture(page, screenshots, "a3-pending")
    page.locator("#account-sign-in").evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true }))")
    assert page.evaluate("""() => accountFixture.calls.filter(x => x.cmd === "account_sign_in_and_activate").length""") == 1
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

    restarted, errors = boot(browser, dist, {"setup_state": "skipped"})
    restarted.wait_for_function("accountFixture.calls.some(x => x.cmd === 'account_view')")
    expect(restarted.locator("#account-first-run")).to_be_hidden()
    open_account(restarted)
    expect(restarted.get_by_role("button", name="Set up this device")).to_be_visible()
    click(restarted, "Set up this device")
    click(restarted, "Enter an organisation enrollment key")
    capture(restarted, screenshots, "a2-enrollment")
    restarted.get_by_label("Organisation enrollment key").fill("fixture-enrollment-key")
    restarted.get_by_label("Device name").fill("Fixture Booth")
    rules(restarted, {"error_code": "unknown_key"})
    click(restarted, "Activate this device")
    expect(restarted.locator("#account-enrollment-error")).to_contain_text("don’t recognise")
    expect(restarted.get_by_label("Organisation enrollment key")).to_have_value("")
    expect(restarted.get_by_label("Organisation enrollment key")).to_be_focused()
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
    capture(restarted, screenshots, "a8-a10-activated-status")
    restarted.evaluate("""() => accountFixture.publish({
      setup_state: 'completed', device_state: 'reauthentication_needed', error_code: 'reauthentication_required'
    })""")
    click(restarted, "Sign in to continue")
    expect(restarted.get_by_role("heading", name="Sign in to SelahCue")).to_be_visible()
    click(restarted, "Back to Account")
    restarted.evaluate("""() => accountFixture.publish({
      setup_state: 'skipped', device_state: 'custody_unavailable', error_code: 'credential_presence_unavailable'
    })""")
    expect(restarted.locator("#account-device-status")).to_contain_text("storage unavailable")
    expect(restarted.locator("#account-plan-label")).to_be_hidden()
    expect(restarted.locator("#account-manifest-expiry")).to_be_hidden()
    assert not errors, errors
    restarted.close()

    activated_restart, errors = boot(browser, dist, ACTIVE)
    activated_restart.wait_for_function("accountFixture.calls.some(x => x.cmd === 'account_view')")
    expect(activated_restart.locator("#account-first-run")).to_be_hidden()
    open_account(activated_restart, via_providers=False)
    expect(activated_restart.locator("#account-device-status")).to_have_text("Device activated")
    expect(activated_restart.locator("#account-plan-label")).to_have_text("Signed fixture plan")
    expect(activated_restart.locator("#account-start-setup")).to_be_hidden()
    assert not errors, errors
    activated_restart.close()

    narrow, errors = boot(browser, dist, width=520, height=760)
    expect(narrow.get_by_role("heading", name="Activate SelahCue")).to_be_visible()
    assert narrow.locator(".account-offline-pill img").evaluate("img => img.complete && img.naturalWidth === 7")
    assert narrow.locator("#account-first-run").evaluate("el => el.scrollWidth <= el.clientWidth")
    narrow.evaluate("accountFixture.skipFailure = true")
    click(narrow, "Sign in to your SelahCue account")
    fill_sign_in(narrow)
    rules(narrow, {"error_code": "network_unavailable"})
    click(narrow, "Continue")
    click(narrow, "Continue offline")
    expect(narrow.locator("#account-card")).to_be_hidden()
    expect(narrow.get_by_role("button", name="Retry saving choice")).to_be_visible()
    narrow.evaluate("accountFixture.skipFailure = false")
    click(narrow, "Retry saving choice")
    expect(narrow.locator("#account-setup-status")).to_be_hidden()
    expect(narrow.locator("#blackout")).to_be_visible()
    expect(narrow.locator("#clear-all")).to_be_visible()
    assert narrow.evaluate("""() => ![localStorage, sessionStorage].some(store =>
      JSON.stringify(store).includes("synthetic-password"))""")
    open_account(narrow, via_providers=False)
    expect(narrow.locator("#account-start-setup")).to_be_visible()
    capture(narrow, screenshots, "account-narrow")
    assert not errors, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("chromium", "webkit"), default="chromium")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    dist = Path(os.environ.get("SELAHCUE_OPERATOR_DIST", str(DIST))).resolve()
    with sync_playwright() as playwright:
        browser = getattr(playwright, args.engine).launch()
        exercise(browser, dist, args.screenshots)
        browser.close()
    print(f"Account setup, Settings, durable Skip readback and emergency controls passed on {args.engine} fixture.")


if __name__ == "__main__":
    main()
