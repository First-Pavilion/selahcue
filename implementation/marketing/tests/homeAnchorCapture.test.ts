import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('./home_anchor_capture.js', import.meta.url), 'utf8');
const actionId = 'a'.repeat(32);
const targetId = 'how-it-works';

type Cleanup = { complete: boolean; reasons: string[] };
type Receipt = {
  reasons: string[];
  counts: Record<string, number>;
  lookups: { present: boolean | null; outcome: string; entry_ms: number }[];
  commands: Record<string, string | number | null>[];
  routes: { path: string; hash: string; source: string; observed_ms: number }[];
  first_presence_ms: number;
  latest_route_observed_ms: number;
  scroll: { latest_y: number };
  click: { is_trusted: boolean };
  lifecycle: { visibility: string; pagehide_persisted: boolean };
  snapshot: { target_present: boolean };
  geometry: { document_target_top: number; anchor_gap: number | null };
  cleanup: Cleanup;
};
type Controller = {
  dispose(): Cleanup;
  finish(measure: () => number | null): { top: number | null; capture: Receipt };
};

function events() {
  const listeners = new Map<string, { callback: (event: object) => void; options: AddEventListenerOptions }>();
  return {
    listeners,
    addEventListener(type: string, callback: (event: object) => void, options: AddEventListenerOptions) {
      listeners.set(type, { callback, options });
    },
    removeEventListener(type: string, callback: (event: object) => void, options: EventListenerOptions) {
      const saved = listeners.get(type);
      if (saved?.callback === callback && Boolean(saved.options.capture) === Boolean(options.capture)) {
        listeners.delete(type);
      }
    },
    dispatch(type: string, event = {}) {
      listeners.get(type)?.callback(event);
    },
  };
}

function fixture({ fixedScroll = false, rememberCalls = true } = {}) {
  const geometry: string[] = [];
  const app = {};
  const documentElement = { clientWidth: 1440, clientHeight: 900 };
  const node = { getBoundingClientRect() { geometry.push('target'); return { top: 95 }; } };
  const navbar = { getBoundingClientRect() { geometry.push('navbar'); return { bottom: 79 }; } };
  const returnValue = {};
  const lookupCalls: { receiver: unknown; args: unknown[] }[] = [];
  const scrollCalls: { receiver: unknown; args: unknown[] }[] = [];
  const state = {
    target: null as typeof node | null,
    nativeError: null as object | null,
    clockError: null as object | null,
    now: 0,
    lookups: 0,
    scrolls: 0,
    brokenStyle: false,
  };

  function getElementById(this: unknown, ...args: unknown[]) {
    state.lookups++;
    if (rememberCalls) lookupCalls.push({ receiver: this, args });
    if (state.nativeError) throw state.nativeError;
    return args[0] === targetId ? state.target : null;
  }

  function scrollTo(this: unknown, ...args: unknown[]) {
    state.scrolls++;
    if (rememberCalls) scrollCalls.push({ receiver: this, args });
    if (state.nativeError) throw state.nativeError;
    return returnValue;
  }

  const document = Object.assign(Object.create({ getElementById }), events(), {
    documentElement,
    fonts: { status: 'loaded' },
    visibilityState: 'visible',
    querySelector(selector: string) {
      if (selector === '#app') return app;
      if (selector === '#app header') return navbar;
      return null;
    },
  });
  const window = {
    ...events(),
    innerWidth: 1456,
    scrollY: 0,
    location: { pathname: '/pricing', hash: '' },
    matchMedia: () => ({ matches: false }),
  };
  Object.defineProperty(window, 'scrollTo', {
    value: scrollTo, configurable: !fixedScroll, writable: !fixedScroll, enumerable: false,
  });

  class FixtureMutationObserver {
    target: object | null = null;
    active = false;
    callback: () => void;
    constructor(callback: () => void) {
      this.callback = callback;
    }
    observe(target: object) {
      this.target = target;
      this.active = true;
    }
    disconnect() {
      this.active = false;
    }
  }

  let currentObserver: FixtureMutationObserver | undefined;
  const install = runInNewContext(source, {
    window,
    document,
    MutationObserver: function (callback: () => void) {
      const observer = new FixtureMutationObserver(callback);
      currentObserver = observer;
      return observer;
    },
    performance: {
      now() {
        if (state.clockError) throw state.clockError;
        return ++state.now;
      },
    },
    getComputedStyle() {
      geometry.push('style');
      if (state.brokenStyle) throw Error('style sentinel');
      return { getPropertyValue: () => '16px' };
    },
  });
  const browserWindow = window as typeof window & {
    scrollTo: typeof scrollTo;
    __scHomeAnchorCapture?: Controller;
  };

  return {
    app, document, window: browserWindow, state, node, returnValue, geometry, lookupCalls, scrollCalls,
    originalScroll: Object.getOwnPropertyDescriptor(window, 'scrollTo'),
    arm: (id = actionId) => install({ actionId: id }),
    get controller() { return browserWindow.__scHomeAnchorCapture; },
    finish(measure: () => number | null) {
      const controller = browserWindow.__scHomeAnchorCapture;
      assert.ok(controller);
      return controller.finish(measure);
    },
    get observer() { return currentObserver; },
    mutate() { if (currentObserver?.active) currentObserver?.callback(); },
    measure() { return document.getElementById(targetId)?.getBoundingClientRect().top ?? null; },
  };
}

test('forwards exactly once and returns the original sample', () => {
  const f = fixture();
  f.state.target = f.node;
  assert.equal(f.arm().actionId, actionId);
  const initialCalls = f.state.lookups;
  assert.equal(f.document.getElementById(targetId), f.node);
  assert.equal(f.state.lookups, initialCalls + 1);
  assert.equal(f.window.scrollTo(0, 120), f.returnValue);
  assert.equal(f.state.scrolls, 1);
  let measurements = 0;
  assert.equal(f.finish(() => { measurements++; return 94.75; }).top, 94.75);
  assert.equal(measurements, 1);
});

test('records_target_lookup_and_scroll_without_touching_arguments', () => {
  const f = fixture();
  f.state.target = f.node;
  f.arm();
  f.lookupCalls.length = 0;
  const receiver = {};
  const opts = { top: 400, left: 0, behavior: 'smooth' };
  let conversions = 0;
  const otherId = { toString() { conversions++; return targetId; } };

  assert.equal(f.document.getElementById.call(receiver, targetId), f.node);
  assert.equal(f.document.getElementById(otherId), null);
  assert.equal(f.window.scrollTo.call(receiver, opts), f.returnValue);
  assert.equal(f.lookupCalls.length, 2);
  assert.equal(f.lookupCalls[0].receiver, receiver);
  assert.equal(f.lookupCalls[1].args[0], otherId);
  assert.equal(f.scrollCalls.length, 1);
  assert.equal(f.scrollCalls[0].receiver, receiver);
  assert.equal(f.scrollCalls[0].args[0], opts);
  assert.equal(conversions, 0);

  const { capture } = f.finish(f.measure);
  assert.equal(capture.lookups.length, 1);
  assert.equal(capture.lookups[0].present, true);
  assert.equal(capture.lookups[0].outcome, 'returned');
  assert.equal(capture.commands.length, 1);
  assert.equal(capture.commands[0].overload, 'options');
  assert.equal(capture.commands[0].projection_quality, 'post_call_own_data');
  assert.equal(capture.commands[0].top, 400);
  assert.equal(capture.commands[0].left, 0);
  assert.equal(capture.commands[0].behavior, 'smooth');
  assert.equal(capture.commands[0].argument_count, 1);
});

test('preserves_throw_identity_and_contains_projection_failure', () => {
  const f = fixture();
  f.arm();
  const sentinel = {};
  f.state.nativeError = sentinel;
  f.state.clockError = {};
  const startCount = f.state.lookups;
  assert.throws(() => f.document.getElementById(targetId), error => error === sentinel);
  assert.throws(() => f.window.scrollTo(0, 400), error => error === sentinel);
  assert.equal(f.state.lookups, startCount + 1);
  assert.equal(f.state.scrolls, 1);
  f.state.nativeError = null;
  f.state.clockError = null;

  const { capture } = f.finish(f.measure);
  assert.ok(capture.reasons.includes('projection_unavailable'));
  assert.equal(capture.lookups[0]?.outcome, 'threw');
  assert.equal(capture.commands[0]?.outcome, 'threw');
  assert.equal(capture.commands[0]?.entry_ms, null);
});

test('does_not_invoke_options_getters', () => {
  const f = fixture();
  f.arm();
  let getters = 0;
  const opts = { get top() { getters++; return 1; }, behavior: 'private value' };
  const trapError = {};
  const bad = new Proxy({}, { getOwnPropertyDescriptor() { throw trapError; } });
  assert.equal(f.window.scrollTo(opts), f.returnValue);
  assert.equal(f.window.scrollTo(bad), f.returnValue);
  const sentinel = {};
  f.state.nativeError = sentinel;
  assert.throws(() => f.window.scrollTo(bad), error => error === sentinel);
  f.state.nativeError = null;
  assert.equal(getters, 0);

  const { capture } = f.finish(f.measure);
  assert.equal(capture.commands[0]?.top, null);
  assert.equal(capture.commands[0]?.behavior, 'other');
  assert.equal(capture.commands[1]?.projection_quality, 'projection_error');
  assert.equal(capture.commands[2]?.outcome, 'threw');
  assert.ok(capture.reasons.includes('projection_unavailable'));
});

test('observes_missing_then_present_without_layout_reads', () => {
  const f = fixture();
  const arm = f.arm();
  assert.equal(f.document.getElementById(targetId), null);
  f.state.target = f.node;
  f.mutate();
  assert.deepEqual(f.geometry, []);
  assert.equal(arm.snapshot?.target_present, false);
  assert.equal(f.observer?.target, f.app);
  assert.equal(f.observer?.active, false);

  const { top, capture } = f.finish(f.measure);
  assert.equal(top, 95);
  assert.equal(capture.lookups.length, 1);
  assert.equal(capture.lookups[0].present, false);
  assert.equal(capture.lookups[0].entry_ms < capture.first_presence_ms, true);
  assert.equal(capture.counts.mutation_callbacks, 1);
  assert.equal(capture.snapshot.target_present, true);
});

test('records_observed_route_without_hash_event', () => {
  const f = fixture();
  f.arm();
  f.window.location.pathname = '/';
  f.window.location.hash = '#how-it-works';
  f.window.scrollTo({ top: 500 });

  const { capture } = f.finish(f.measure);
  assert.equal(capture.routes.length, 2);
  assert.equal(capture.routes[0].path, 'pricing');
  assert.equal(capture.routes[1].path, 'home_anchor');
  assert.equal(capture.routes[1].hash, 'how_it_works');
  assert.equal(capture.routes[1].source, 'command');
  assert.equal(typeof capture.commands[0].return_ms, 'number');
  assert.ok(capture.routes[1].observed_ms >= Number(capture.commands[0].return_ms));
  assert.ok(!Object.keys(capture.routes[1]).some(key => key.includes('commit')));
});

test('bounds_retention_and_keeps_forwarding', () => {
  const f = fixture();
  f.arm();
  const initialLookups = f.state.lookups;
  for (let i = 0; i < 18; i++) {
    f.window.location.pathname = i % 2 === 0 ? '/' : '/pricing';
    f.window.location.hash = i % 2 === 0 ? '#how-it-works' : '';
    f.document.getElementById(targetId);
    f.window.scrollTo(0, i);
  }
  assert.equal(f.state.lookups, initialLookups + 18);
  assert.equal(f.state.scrolls, 18);

  for (let i = 0; i < 258; i++) {
    f.window.scrollY = i;
    f.window.dispatch('scroll');
  }
  for (let i = 0; i < 130; i++) f.mutate();
  assert.equal(f.window.listeners.has('scroll'), false);
  assert.equal(f.observer?.active, false);

  const { capture } = f.finish(f.measure);
  assert.equal(capture.lookups.length, 16);
  assert.equal(capture.commands.length, 16);
  assert.equal(capture.routes.length, 16);
  assert.equal(capture.counts.lookup_dropped, 2);
  assert.equal(capture.counts.command_dropped, 2);
  assert.equal(capture.counts.route_dropped, 3);
  assert.ok(capture.latest_route_observed_ms > capture.routes[15].observed_ms);
  assert.equal(capture.counts.scroll_callbacks, 257);
  assert.equal(capture.counts.mutation_callbacks, 129);
  assert.equal(capture.scroll.latest_y, 255);
  for (const reason of ['lookup_limit', 'command_limit', 'route_limit', 'scroll_limit', 'mutation_limit']) {
    assert.ok(capture.reasons.includes(reason), reason);
  }
});

test('saturates lookup counters with continued native forwarding', () => {
  const f = fixture({ rememberCalls: false });
  f.arm();
  const initialLookups = f.state.lookups;
  for (let i = 0; i < 1_000_001; i++) f.document.getElementById(targetId);

  const { capture } = f.finish(() => null);
  assert.equal(f.state.lookups, initialLookups + 1_000_001 + 1); // final presence probe stays internal
  assert.equal(capture.counts.target_lookups, 1_000_000);
  assert.ok(capture.reasons.includes('counter_saturated'));
});

test('measurement_runs_first_once_and_cleanup_preserves_owners', () => {
  const f = fixture();
  f.window.scrollY = 340;
  f.arm();
  f.state.target = f.node;
  const controller = f.controller;
  assert.ok(controller);
  let measurements = 0;
  const { top, capture } = controller.finish(() => {
    measurements++;
    assert.equal(Object.hasOwn(f.document, 'getElementById'), false);
    assert.deepEqual(Object.getOwnPropertyDescriptor(f.window, 'scrollTo'), f.originalScroll);
    assert.equal(f.window.listeners.size + f.document.listeners.size, 0);
    assert.equal(f.observer?.active, false);
    return f.measure();
  });
  assert.equal(top, 95);
  assert.equal(measurements, 1);
  assert.deepEqual(f.geometry, ['target', 'navbar', 'style']);
  assert.equal(capture.geometry.document_target_top, 435);
  assert.equal(capture.cleanup.complete, true);
  assert.equal(controller.dispose(), controller.dispose());

  const replaced = fixture();
  replaced.arm();
  const replacement = () => 'new owner';
  Object.defineProperty(replaced.window, 'scrollTo', { configurable: true, value: replacement });
  assert.ok(replaced.controller);
  const cleanup = replaced.controller.dispose();
  assert.equal(replaced.window.scrollTo, replacement);
  assert.ok(cleanup.reasons.includes('wrapper_replaced'));
  assert.equal(Object.hasOwn(replaced.document, 'getElementById'), false);

  const partial = fixture({ fixedScroll: true });
  assert.equal(partial.arm().installed, false);
  assert.equal(partial.controller, undefined);
  assert.equal(Object.hasOwn(partial.document, 'getElementById'), false);
  assert.deepEqual(Object.getOwnPropertyDescriptor(partial.window, 'scrollTo'), partial.originalScroll);
  assert.equal(partial.window.listeners.size + partial.document.listeners.size, 0);
});

test('collision leaves the existing controller and methods alone', () => {
  const f = fixture();
  const existing = {};
  Object.defineProperty(f.window, '__scHomeAnchorCapture', { configurable: true, value: existing });
  assert.equal(f.arm().installed, false);
  assert.equal(f.controller, existing);
  assert.equal(Object.hasOwn(f.document, 'getElementById'), false);
});

test('records passive click and lifecycle observations using fixed scalars', () => {
  const f = fixture();
  f.arm();
  const click = f.document.listeners.get('click');
  assert.equal(click?.options.capture, true);
  assert.equal(click?.options.passive, true);
  f.document.dispatch('click', { target: { closest: () => ({ getAttribute: () => '/ignored' }) }, isTrusted: true });
  f.document.dispatch('click', { target: { closest: () => ({ getAttribute: () => '/#how-it-works' }) }, isTrusted: false });
  f.document.visibilityState = 'hidden';
  f.document.dispatch('visibilitychange');
  f.window.dispatch('pagehide', { persisted: true });

  const { capture } = f.finish(f.measure);
  assert.equal(capture.counts.anchor_clicks, 1);
  assert.equal(capture.click.is_trusted, false);
  assert.equal(capture.counts.visibility_changes, 1);
  assert.equal(capture.lifecycle.visibility, 'hidden');
  assert.equal(capture.lifecycle.pagehide_persisted, true);
});

test('supplemental geometry failure preserves the sampled top', () => {
  const f = fixture();
  f.state.target = f.node;
  f.arm();
  f.state.brokenStyle = true;
  const { top, capture } = f.finish(f.measure);
  assert.equal(top, 95);
  assert.equal(capture.geometry.anchor_gap, null);
  assert.ok(capture.reasons.includes('sample_incomplete'));
});

test('measurement exception is rethrown once with the observer already disposed', () => {
  const f = fixture();
  f.arm();
  const sentinel = {};
  let samples = 0;
  assert.throws(() => f.finish(() => { samples++; throw sentinel; }), error => error === sentinel);
  assert.equal(samples, 1);
  assert.equal(f.controller, undefined);
  assert.equal(f.window.listeners.size + f.document.listeners.size, 0);
  assert.deepEqual(f.geometry, []);
});

test('reentrant option projection forwards the nested call without collecting it', () => {
  const f = fixture();
  f.arm();
  const options = new Proxy({ top: 250 }, {
    getOwnPropertyDescriptor(target, key) {
      if (key === 'top') f.window.scrollTo(0, 900);
      return Reflect.getOwnPropertyDescriptor(target, key);
    },
  });
  assert.equal(f.window.scrollTo(options), f.returnValue);
  assert.equal(f.scrollCalls.length, 2);
  assert.equal(f.scrollCalls[0].args[0], options);
  assert.equal(f.scrollCalls[1].args[1], 900);

  const { capture } = f.finish(f.measure);
  assert.equal(capture.counts.scroll_commands, 1);
  assert.equal(capture.commands[0].top, 250);
});

test('a failed removal still restores methods and runs the original sample', () => {
  const f = fixture();
  f.arm();
  const remove = f.window.removeEventListener;
  f.window.removeEventListener = function (eventName, callback, options) {
    if (eventName === 'scroll') throw Error('failed removal');
    return remove.call(this, eventName, callback, options);
  };
  const { top, capture } = f.finish(() => {
    assert.equal(Object.hasOwn(f.document, 'getElementById'), false);
    assert.deepEqual(Object.getOwnPropertyDescriptor(f.window, 'scrollTo'), f.originalScroll);
    assert.equal(f.document.listeners.size, 0);
    assert.equal(f.window.listeners.has('hashchange'), false);
    return 95;
  });
  assert.equal(top, 95);
  assert.equal(capture.cleanup.complete, false);
  assert.ok(capture.cleanup.reasons.includes('cleanup_incomplete'));
});
