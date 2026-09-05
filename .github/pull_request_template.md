## Summary

<!-- What changed and why. Link the ClickUp task. -->

## Feature-flag reachability

<!--
86akcmzyq: FR-122 sermon notes shipped, merged, and passed four-reviewer review behind an
off-by-default Cargo feature (`openai-notes`) — but `make launch`/`make operator` never
requested it, so it stayed invisible from the one command a developer actually runs. Answer
this for every PR that adds or changes a Cargo feature flag on a crate `make launch`/`make
operator`/`make output` builds (selahcue-operator, selahcue-desktop, and anything they depend
on with an optional feature):
-->

- [ ] This PR does not add or change a Cargo feature flag on a crate the dev launch targets build. *(skip the rest of this section)*
- [ ] It does, and the new/changed feature is reachable from `make launch`/`make operator`/`make output` the way a developer would actually run it — either auto-enabled (see `STT ?= auto` / `AI ?= auto` in the `Makefile`) or documented as an explicit opt-in flag with a printed status line, per `CLAUDE.md`'s "Commands" section.
- [ ] If the feature can read a credential, a key, or any other release-sensitive input: the `RELEASE=1` boundary is structural (a `RELEASE=1`/`--release` build cannot enable it through `make`, and ideally not through a bare `cargo build --release` either) — not merely "the default happens to be off." See the "AI-assisted sermon notes" comment in the `Makefile` and `selahcue-operator/src/dev_env.rs` for the pattern this repo already uses.

## Test plan

<!-- Commands run, evidence, screenshots/logs where relevant. -->
