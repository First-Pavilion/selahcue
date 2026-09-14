# ADR-0026 spike evidence

Standalone probes behind ADR-0026 rev 2. They test the ENGINE, not this repo's code,
so they run against `fixture.html` (a synthetic 5,000-row scroller), not `transcripts.js`.

    pip install playwright && playwright install chromium webkit
    python3 spike1_write_vs_mutation.py   # scrollTop write vs DOM mutation, during a native key animation
    python3 spike2_native_anchoring.py    # does native scroll anchoring actually work, incl. on WebKit

Both print a summary and write `*_results.json` beside themselves. Every measurement
carries a negative control; see each file's module docstring for what it discriminates.
