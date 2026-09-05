## Summary

<!-- What changed and why. Link the ClickUp task. -->

## Feature-flag reachability

<!--
86akcmzyq: FR-122 sermon notes shipped, merged, and passed four-reviewer review behind an
off-by-default Cargo feature (`openai-notes`) — but `make launch`/`make operator` never
requested it, so it stayed invisible from the one command a developer actually runs. It happened
again for `cloud-stt` (86akby7th, closed by 86akd10dq) because this checklist is a human step,
not a control — an unchecked (or wrongly-checked) box blocks nothing on its own. Answer this for
every PR that adds or changes a Cargo feature flag on a crate `make launch`/`make operator`/`make
output` builds (selahcue-operator, selahcue-desktop, and anything they depend on with an optional
feature):

If the crate is `selahcue-operator` or `selahcue-desktop` (the two `CRATE_MANIFESTS` entries in
`scripts/check_launch_reachability.py` — every crate the dev-launch path builds directly):
`scripts/check_launch_reachability.py` now ENFORCES this — every non-`default` feature in that
crate's `[features]` table must carry BOTH a `# LAUNCH_REACHABILITY: REQUIRED|AUTO|OPT-IN` line
AND a `# RELEASE: SAFE|UNSAFE` line in its own comment block, or `make ci`/CI fails outright
(86akd10dq). Add both tags when you add the feature; this checklist is then a sanity prompt, not
the only thing standing between an invisible (or release-leaked) feature and a merge. Adding a
feature-building crate that ISN'T one of those two? The same script hard-fails with "reference
crate(s) not in CRATE_MANIFESTS" the first time `make ci`/CI runs against it — add it there too.
-->

- [ ] This PR does not add or change a Cargo feature flag on a crate the dev launch targets build. *(skip the rest of this section)*
- [ ] It does, and the new/changed feature is reachable from `make launch`/`make operator`/`make output` the way a developer would actually run it — either auto-enabled (see `STT ?= auto` / `AI ?= auto` in the `Makefile`) or documented as an explicit opt-in flag with a printed status line, per `CLAUDE.md`'s "Commands" section. For `selahcue-operator`/`selahcue-desktop` features, this is also enforced: the feature's `# LAUNCH_REACHABILITY:` tag in `Cargo.toml` is set to `REQUIRED` if it must be default-reachable, `AUTO` if it is reachable only via an environment/SDK probe, or `OPT-IN` if a developer must explicitly request it.
- [ ] If the feature can read a credential, a key, or any other release-sensitive input: the `RELEASE=1` boundary is structural (a `RELEASE=1`/`--release` build cannot enable it through `make`, and ideally not through a bare `cargo build --release` either) — not merely "the default happens to be off." See the "AI-assisted sermon notes" comment in the `Makefile` and `selahcue-operator/src/dev_env.rs` for the pattern this repo already uses. The feature's `# RELEASE:` tag is set to `UNSAFE` in that case, and `UNSAFE` features are cross-checked against the Makefile's `RELEASE_UNSAFE_FEATURES` registry — add the token there too (`release-ai-guard` is what actually refuses the build).

## Test plan

<!-- Commands run, evidence, screenshots/logs where relevant. -->
