"""Process-local Deepgram circuit with a single half-open probe."""
import threading
import time

from .contracts import Granted, OutcomeUnknown, UNCERTAIN_MINT_FAILURES


class SttCircuit:
    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._open_until = None
        self._probe = False
        self._generation = 0

    def _blocked(self):
        return self._probe or (self._open_until is not None and self._clock() < self._open_until)

    def available(self):
        with self._lock:
            return not self._blocked()

    def admit(self):
        with self._lock:
            if self._blocked():
                return None
            if self._open_until is not None:
                self._probe = True
                self._generation += 1
            return self._generation

    def finish(self, generation, outcome):
        with self._lock:
            if generation != self._generation:
                return
            was_probe, self._probe = self._probe, False
            if isinstance(outcome, Granted):
                self._open_until, self._failures = None, 0
                if was_probe:
                    self._generation += 1
            elif isinstance(outcome, OutcomeUnknown) and outcome.code in UNCERTAIN_MINT_FAILURES:
                self._failures = min(5, self._failures + 1)
                if was_probe or self._failures == 5:
                    self._open_until = self._clock() + 30
                    self._generation += 1


STT_CIRCUIT = SttCircuit()
