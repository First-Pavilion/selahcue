# Workload Model

SelahCue is a **single-operator, offline-first desktop app** with a small number of same-network LAN
peers. There is no hosted multi-tenant surface, so the workload model is about *realistic service use*,
not concurrent-user scale.

## Personas / clients

| Persona | Client | Concurrency | Dominant operations |
| --- | --- | --- | --- |
| Operator | Tauri console + native output window | 1 | Stage/trigger slides + scripture, watch live transcript + detected scripture |
| Mobile controller | Flutter app over pinned-TLS WebSocket | 0–few (LAN) | RBAC-checked control commands (stage, go-live, blackout, next/prev) |
| Audience output | Native winit+wgpu window | 1 | Continuous ~60 Hz redraw of the current live frame |
| STT/detection | In-process worker threads | 1 each | Continuous mic capture → framing/VAD → interim/final segments → fuzzy detection |

## Session model

- A service is a single continuous session, typically 60–120 minutes.
- The audience window renders continuously for the whole service (long-running stability matters).
- STT runs continuously while "listening" is on: speech is bracketed into utterances (≤10 s force-close),
  emitting interim segments ~every 0.8 s and a final segment per utterance.

## Operation mix (per service, representative)

- Slide/scripture triggers: dozens to low-hundreds of go-lives.
- Detections: one fuzzy match per finalised utterance over a 3-segment rolling window; operator-confirmed
  before anything reaches Preview/Live (FR-115 — never auto-display).
- Keyword searches: occasional, worst case a rare phrase forcing a full ~31 k-verse scan.
- LAN commands: intermittent, one control channel, one request in flight at a time.

## Contention paths (the ones that matter)

- **Render thread ↔ control thread** — both touch the controller mutex; a remote command can wait up to
  ~one vsync behind a present (finding #6). Bounded and small.
- **STT worker ↔ drain task** — bounded `mpsc(256)` with `try_send` that drops under backpressure and
  never blocks the worker (verified).
- **Console poll ↔ live control (remote mode)** — thumbnail/state polls share the remote mutex with
  go-live (finding #4). Head-of-line only; tokio mutex, no OS-thread block.

## Long-running / endurance considerations

- Every collection touched on the continuous paths (transcript log, detection queue, dedup ring, text
  caches, PCM ring, segment queue) is hard-capped, so a multi-hour service cannot grow memory without
  bound. This is asserted by the flood tests rather than a live soak; the live-RSS soak is the owner-run
  NFR gap (M18/M19).

## Arrival / pacing

- Human-paced operator actions (no synthetic high-rate arrival is realistic).
- STT arrival is real-time audio (fixed frame cadence), modelled by the injected-clock pipeline tests.
