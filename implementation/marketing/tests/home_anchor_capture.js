/* global window, document, performance, MutationObserver, getComputedStyle */
// Playwright and the stand-in browser evaluate this file for its function value.
/* eslint-disable-next-line @typescript-eslint/no-unused-expressions */
(function installHomeAnchorCapture(options) {
  'use strict';

  const { actionId } = options;

  const key = '__scHomeAnchorCapture';
  const targetId = 'how-it-works';
  const targetHash = '#how-it-works';
  const recordLimit = 16;
  const scrollLimit = 256;
  const mutationLimit = 128;
  const counterLimit = 1_000_000;
  const reasons = new Set();
  const removals = [];
  const passive = { passive: true };
  const counts = {
    target_lookups: 0, lookup_dropped: 0, scroll_commands: 0, command_dropped: 0,
    route_observations: 0, route_dropped: 0, scroll_callbacks: 0, mutation_callbacks: 0,
    anchor_clicks: 0, visibility_changes: 0, pagehides: 0,
  };
  const lookups = [];
  const commands = [];
  const routes = [];
  const scroll = { first_ms: null, latest_ms: null, first_y: null, latest_y: null, min_y: null, max_y: null };
  const lifecycle = { visibility: null, visibility_ms: null, pagehide_persisted: null, pagehide_ms: null };
  let click = null;
  let firstPresence = null;
  let latestRouteLabels = null;
  let latestRouteMs = null;
  let observing = false;
  let projecting = false;
  let cleanup;
  let originalLookup;
  let now;
  let origin = null;
  let stopMutation = () => {};

  function safely(read, reason = 'projection_unavailable') {
    try {
      return read();
    } catch {
      reasons.add(reason);
      return null;
    }
  }

  function project(read) {
    if (projecting) return null;
    projecting = true;
    try {
      return safely(read);
    } finally {
      projecting = false;
    }
  }

  function number(value, reason = 'projection_unavailable') {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= 1_000_000_000) {
      return value;
    }
    reasons.add(reason);
    return null;
  }

  function timestamp() {
    if (origin === null) return null;
    return safely(() => number(now() - origin));
  }

  function increment(counter) {
    if (counts[counter] < counterLimit) counts[counter]++;
    else reasons.add('counter_saturated');
  }

  function retain(records, dropped, reason, record) {
    if (records.length < recordLimit) {
      records.push(record);
    } else {
      increment(dropped);
      reasons.add(reason);
    }
  }

  function routeLabels() {
    const { pathname, hash } = window.location;
    return {
      path: pathname === '/pricing' ? 'pricing' : pathname === '/' && hash === targetHash ? 'home_anchor' : 'other',
      hash: hash === '' ? 'none' : hash === targetHash ? 'how_it_works' : 'other',
    };
  }

  function observeRoute(labels, source) {
    if (!labels || (latestRouteLabels?.path === labels.path && latestRouteLabels.hash === labels.hash)) return;
    latestRouteLabels = labels;
    latestRouteMs = timestamp();
    increment('route_observations');
    retain(routes, 'route_dropped', 'route_limit', { ...labels, observed_ms: latestRouteMs, source });
  }

  function visibility() {
    const value = document.visibilityState;
    return value === 'visible' || value === 'hidden' || value === 'prerender' ? value : null;
  }

  function fontStatus() {
    const value = document.fonts?.status;
    return value === 'loaded' || value === 'loading' ? value : null;
  }

  function presence() {
    return Reflect.apply(originalLookup, document, [targetId]) !== null;
  }

  function notePresence(present, source) {
    if (present && firstPresence === null) {
      firstPresence = { observed_ms: timestamp(), source };
      safely(stopMutation, 'cleanup_incomplete');
    }
  }

  function snapshot() {
    const unexpected = 'sample_incomplete';
    const result = {
      ...safely(routeLabels, unexpected),
      visibility: safely(visibility, unexpected),
      font_status: safely(fontStatus, unexpected),
      reduced_motion: safely(() => {
        const value = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        return typeof value === 'boolean' ? value : null;
      }, unexpected),
      inner_width: safely(() => number(window.innerWidth, unexpected), unexpected),
      client_width: safely(() => number(document.documentElement.clientWidth, unexpected), unexpected),
      client_height: safely(() => number(document.documentElement.clientHeight, unexpected), unexpected),
      scroll_y: safely(() => number(window.scrollY, unexpected), unexpected),
      target_present: safely(presence, unexpected),
    };
    if (Object.values(result).includes(null)) reasons.add(unexpected);
    return result;
  }

  function intercept(original, receiver, args, record) {
    if (!observing || projecting) return Reflect.apply(original, receiver, args);

    const entry_ms = project(timestamp);
    let result;
    let outcome = 'threw';
    try {
      result = Reflect.apply(original, receiver, args);
      outcome = 'returned';
      return result;
    } finally {
      project(() => record(args, result, { entry_ms, return_ms: timestamp(), outcome }));
    }
  }

  function recordLookup(_args, result, timing) {
    increment('target_lookups');
    const present = timing.outcome === 'returned' ? result !== null : null;
    retain(lookups, 'lookup_dropped', 'lookup_limit', { ...timing, present });
    observeRoute(safely(routeLabels), 'lookup');
    notePresence(present, 'lookup');
  }

  function scrollOptions(args) {
    const first = args[0];
    if (typeof first === 'number') {
      return {
        overload: 'numeric', projection_quality: 'numeric', left: number(first),
        top: number(args[1]), behavior: 'absent',
      };
    }
    if (first === null || typeof first !== 'object') {
      reasons.add('projection_unavailable');
      return { overload: 'other', projection_quality: 'unsupported', left: null, top: null, behavior: null };
    }

    const result = {
      overload: 'options', projection_quality: 'post_call_own_data', left: null, top: null, behavior: null,
    };
    for (const field of ['top', 'left', 'behavior']) {
      try {
        const descriptor = Object.getOwnPropertyDescriptor(first, field);
        if (!descriptor) {
          if (field === 'behavior') result.behavior = 'absent';
        } else if (!Object.hasOwn(descriptor, 'value')) {
          reasons.add('projection_unavailable');
        } else if (field !== 'behavior') {
          result[field] = number(descriptor.value);
        } else if (typeof descriptor.value === 'string') {
          const { value } = descriptor;
          result.behavior = ['auto', 'instant', 'smooth'].includes(value) ? value : 'other';
        } else {
          reasons.add('projection_unavailable');
        }
      } catch {
        result.projection_quality = 'projection_error';
        reasons.add('projection_unavailable');
        break;
      }
    }
    return result;
  }

  function recordScroll(args, _result, timing) {
    increment('scroll_commands');
    if (commands.length < recordLimit) {
      commands.push({ ...timing, argument_count: args.length <= 16 ? args.length : 'many', ...scrollOptions(args) });
    } else {
      increment('command_dropped');
      reasons.add('command_limit');
    }
    observeRoute(safely(routeLabels), 'command');
  }

  function wrap(object, property, wrapper) {
    const descriptor = Object.getOwnPropertyDescriptor(object, property);
    Object.defineProperty(object, property, descriptor && Object.hasOwn(descriptor, 'value')
      ? { ...descriptor, value: wrapper }
      : { configurable: true, enumerable: descriptor?.enumerable ?? false, writable: true, value: wrapper });
    removals.push(() => {
      const current = Object.getOwnPropertyDescriptor(object, property);
      if (current?.value !== wrapper) {
        reasons.add('wrapper_replaced');
      } else if (descriptor) {
        Object.defineProperty(object, property, descriptor);
      } else {
        delete object[property];
      }
    });
  }

  function listen(object, eventName, callback, options = passive) {
    const listener = event => {
      if (observing) project(() => callback(event));
    };
    let attached = true;
    const remove = () => {
      if (attached) object.removeEventListener(eventName, listener, options);
      attached = false;
    };
    removals.push(remove);
    object.addEventListener(eventName, listener, options);
    return remove;
  }

  function wireEvents() {
    listen(document, 'click', event => {
      const link = event.target?.closest?.('a[href]');
      if (link?.getAttribute('href') !== '/' + targetHash) return;
      increment('anchor_clicks');
      click = { observed_ms: timestamp(), is_trusted: event.isTrusted === true };
      observeRoute(safely(routeLabels), 'click');
    }, { capture: true, passive: true });
    const stopScroll = listen(window, 'scroll', () => {
      if (counts.scroll_callbacks > scrollLimit) return;
      increment('scroll_callbacks');
      if (counts.scroll_callbacks > scrollLimit) {
        reasons.add('scroll_limit');
        safely(stopScroll, 'cleanup_incomplete');
        return;
      }
      const time = timestamp();
      const y = safely(() => number(window.scrollY));
      if (counts.scroll_callbacks === 1) {
        scroll.first_ms = time;
        scroll.first_y = y;
      }
      scroll.latest_ms = time;
      scroll.latest_y = y;
      if (y !== null) {
        scroll.min_y = scroll.min_y === null ? y : Math.min(scroll.min_y, y);
        scroll.max_y = scroll.max_y === null ? y : Math.max(scroll.max_y, y);
      }
      observeRoute(safely(routeLabels), 'scroll');
    });
    listen(window, 'hashchange', () => observeRoute(safely(routeLabels), 'hashchange'));
    listen(window, 'popstate', () => observeRoute(safely(routeLabels), 'popstate'));
    listen(document, 'visibilitychange', () => {
      increment('visibility_changes');
      lifecycle.visibility = safely(visibility);
      lifecycle.visibility_ms = timestamp();
      observeRoute(safely(routeLabels), 'visibilitychange');
    });
    listen(window, 'pagehide', event => {
      increment('pagehides');
      lifecycle.pagehide_ms = timestamp();
      lifecycle.pagehide_persisted = event.persisted === true;
      observeRoute(safely(routeLabels), 'pagehide');
    });
  }

  function watchPresence() {
    let attached = true;
    const observer = new MutationObserver(() => {
      if (!observing || !attached || counts.mutation_callbacks > mutationLimit) return;
      project(() => {
        increment('mutation_callbacks');
        if (counts.mutation_callbacks > mutationLimit) {
          reasons.add('mutation_limit');
          safely(stopMutation, 'cleanup_incomplete');
          return;
        }
        observeRoute(safely(routeLabels), 'mutation');
        notePresence(safely(presence), 'mutation');
      });
    });
    stopMutation = () => {
      if (attached) observer.disconnect();
      attached = false;
    };
    removals.push(stopMutation);
    observer.observe(document.querySelector('#app') ?? document.documentElement, { childList: true, subtree: true });
  }

  function dispose() {
    if (cleanup) return cleanup;
    observing = false;
    while (removals.length) safely(removals.pop(), 'cleanup_incomplete');
    const problems = ['wrapper_replaced', 'cleanup_incomplete'].filter(reason => reasons.has(reason));
    cleanup = { complete: problems.length === 0, reasons: problems };
    return cleanup;
  }

  function captureFinal(top, cleanupSummary) {
    const final = snapshot();
    observeRoute(final.path ? { path: final.path, hash: final.hash } : null, 'finish');
    notePresence(final.target_present, 'finish');
    const sampleNumber = value => number(value, 'sample_incomplete');
    const targetTop = sampleNumber(top);
    const documentTop = targetTop === null || final.scroll_y === null ? null : sampleNumber(targetTop + final.scroll_y);
    const navbarBottom = safely(() => sampleNumber(document.querySelector('#app header')?.getBoundingClientRect().bottom),
      'sample_incomplete');
    const gap = safely(() => sampleNumber(parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--sc-anchor-gap'),
    )), 'sample_incomplete');
    if (navbarBottom === null || gap === null) reasons.add('sample_incomplete');

    return {
      complete: reasons.size === 0,
      reasons: [...reasons],
      counts, lookups, commands, routes, click, scroll, lifecycle,
      first_presence_ms: firstPresence?.observed_ms ?? null,
      first_presence_source: firstPresence?.source ?? null,
      latest_route_observed_ms: latestRouteMs,
      snapshot: final,
      geometry: {
        document_target_top: documentTop,
        document_target_top_basis: 'sequential_target_top_and_scroll_y',
        navbar_bottom: navbarBottom,
        anchor_gap: gap,
      },
      cleanup: cleanupSummary,
    };
  }

  function finish(measureTargetTop) {
    const cleanupSummary = dispose();
    // This is the existing assertion's sample. Any error from it propagates unchanged.
    const top = measureTargetTop();
    const capture = safely(() => captureFinal(top, cleanupSummary), 'sample_incomplete');
    return { top, capture: capture ?? { complete: false, reasons: [...reasons], counts, cleanup: cleanupSummary } };
  }

  try {
    if (typeof actionId !== 'string' || !/^[0-9a-f]{32}$/.test(actionId) || key in window) {
      return { installed: false, reasons: ['install_failed'] };
    }
    originalLookup = document.getElementById;
    const originalScroll = window.scrollTo;
    if (typeof originalLookup !== 'function' || typeof originalScroll !== 'function') {
      return { installed: false, reasons: ['install_failed'] };
    }
    origin = safely(() => {
      const method = performance.now;
      now = () => Reflect.apply(method, performance, []);
      return number(now());
    });

    const initial = snapshot();
    observeRoute(initial.path ? { path: initial.path, hash: initial.hash } : null, 'arm');
    notePresence(initial.target_present, 'arm');
    wrap(document, 'getElementById', function (...args) {
      if (args[0] !== targetId) return Reflect.apply(originalLookup, this, args);
      return intercept(originalLookup, this, args, recordLookup);
    });
    wrap(window, 'scrollTo', function (...args) {
      return intercept(originalScroll, this, args, recordScroll);
    });
    wireEvents();
    if (!initial.target_present) watchPresence();

    const controller = Object.freeze({ actionId, finish, dispose });
    Object.defineProperty(window, key, { configurable: true, writable: true, value: controller });
    removals.push(() => {
      const current = Object.getOwnPropertyDescriptor(window, key);
      if (current?.value === controller) delete window[key];
    });
    observing = true;
    return { installed: true, actionId, snapshot: initial, reasons: [...reasons] };
  } catch {
    reasons.add('install_failed');
    return { installed: false, reasons: [...reasons], cleanup: dispose() };
  }
})
