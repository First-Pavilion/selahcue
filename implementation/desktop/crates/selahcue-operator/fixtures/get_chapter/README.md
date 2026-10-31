# Real get_chapter replies (17tnw2b13y0)

`host-replies.json` contains the exact JSON payload emitted by the actual Rust `get_chapter` command recording test on hosted Linux, plus one newline. See `provenance.json` for immutable source/tree, diagnostic parent/workflow-only proof, run/job and official raw/output hashes. No expected verses, canonical names, parser behavior, chapter lengths or errors were produced from the headless mock.

The eight cases include the six required bare/single/range/past-end/missing/unparseable classes, an end-of-corpus navigation case and a genuine WEB verse gap. Results preserve every serialized field and verse text. A host past-end selection is still2..10 although Psalm1 ends at6; the modal clamps its linked selection. WEB Luke17:36 returns the real chapter with35/37 and no36. `Ok`/`Err` is the recorder’s serde Result envelope: a browser adapter must resolve the `Ok` payload or reject the exact `Err` string. This envelope is not Tauri IPC framing.

The default Rust fixture contract compares whole actual command results to these frozen bytes. Tests never rewrite this file. For an intentional host contract change, record the actual reviewed command again through the hosted recorder, inspect the full payload and provenance, update both Rust and modal consumers deliberately, and rerun meaningful serialization/navigation/error/consumer mutants and exact restoration. Merely regenerating fixtures to hide a failure is not verification.

Backend recording and fixture locking alone do not complete this ticket: the actual headless modal must replay these same fixtures after F31’s script ownership is released, with current full normal CI and four independent reviews.
