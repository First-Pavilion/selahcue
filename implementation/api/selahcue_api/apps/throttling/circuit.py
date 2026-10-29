"""One bounded cache circuit per worker process, independent of caller identity."""

import threading
import time


class CacheCircuit:
    """Serialize admission/state updates, never cache I/O.

    Tokens fence results admitted before a newer failure or recovery probe. A late
    success still returns its real budget decision but cannot close a newer outage.
    Closed-state failures count in completion order; successful current calls reset
    the consecutive count. In-flight calls already admitted may still reach Redis.
    """

    __slots__ = ("_lock", "_failures", "_open_until", "_probing", "_generation", "_epoch")

    def __init__(self):
        self._lock = threading.Lock()
        self._failures = 0
        self._open_until = None
        self._probing = False
        self._generation = 0
        self._epoch = 0

    def admit(self):
        with self._lock:
            if self._open_until is not None:
                if self._probing or time.monotonic() < self._open_until:
                    return None
                self._probing = True
                self._generation += 1
            return self._epoch, self._generation

    def finish(self, token, *, success, threshold, cooldown):
        with self._lock:
            epoch, generation = token
            if epoch != self._epoch:
                return
            if success:
                if generation == self._generation:
                    if self._probing:
                        self._epoch += 1
                    self._failures = 0
                    self._open_until = None
                    self._probing = False
                return
            # Results predating an open circuit/probe cannot extend its deadline
            # or release its single recovery slot.
            if self._open_until is not None and generation != self._generation:
                return
            if self._open_until is not None and not self._probing:
                return
            self._failures = min(threshold, self._failures + 1)
            self._generation += 1
            if self._probing or self._failures >= threshold:
                self._epoch += 1
                self._open_until = time.monotonic() + cooldown
                self._probing = False


CACHE_CIRCUIT = CacheCircuit()
