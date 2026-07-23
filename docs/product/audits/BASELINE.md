# SelahCue — Verified Baseline (Stage 1)

Date: 2026-07-23 · Author: /build (Stage 1) · Status: Verified

Each fact is classified: **OBSERVED** (directly inspected this session), **DOCUMENTED** (stated in a repo file), **INFERRED** (reasoned), or **UNKNOWN**.

## 1. Repository state

| Fact | Classification | Evidence |
|---|---|---|
| Working dir `/Users/m.oluwole/Documents/code/scph` is **not** a git repository | OBSERVED | `git status` → "fatal: not a git repository" |
| No application source code, tests, build config, CI, or infrastructure files exist | OBSERVED | `find` tree: only `.claude/`, `product/`, `.DS_Store` |
| `product/PRODUCT-BRIEF.md` present — a research/PRD/decomposition brief for a church presentation & ministry-assistance app | OBSERVED | Read (994 lines) |
| `.claude/team/` holds 12 process docs (goal protocol, build gates, ClickUp workflow, task schema, quality gates, role matrix, artefacts, templates) | OBSERVED | Directory listing + reads |
| `.claude/skills/` holds 16 specialist skills (product/eng/qa/security/devops/docs + goal + build) | OBSERVED | Directory listing |
| No existing PRD, research, architecture, ADRs, designs, or docs/ tree | OBSERVED | `find` |

**Conclusion:** Greenfield build. No existing implementation or technical debt to reconcile — the brief is the sole product input.

## 2. Technology stack

| Fact | Classification | Evidence |
|---|---|---|
| No stack chosen or committed in the repo | OBSERVED | no manifests/lockfiles/build files |
| Brief lists **candidate** technologies: Rust, Tauri, native rendering, wgpu, GStreamer, SQLite, local AI runtimes | DOCUMENTED | PRODUCT-BRIEF.md §Performance |
| Brief explicitly forbids choosing the stack solely from its suggestions; requires documented trade-off analysis before recommending | DOCUMENTED | PRODUCT-BRIEF.md L677-678 |
| Final stack | UNKNOWN | to be decided Stage 5 via ADRs |

## 3. Available tooling / MCP

| Fact | Classification | Evidence |
|---|---|---|
| ClickUp MCP connected and functional | OBSERVED | `get_workspace_hierarchy` returned 9 spaces |
| Figma MCP available | OBSERVED | tool list (design stages) |
| Postman MCP + Google Calendar MCP available | OBSERVED | tool list |
| WebSearch / WebFetch available for research | OBSERVED | deferred tool list |
| Chrome MCP (requested by brief for reference-product study) | UNKNOWN | not observed in tool list; WebSearch/WebFetch are the available research path — tracked RISK-007 |
| `scripts/validate_goal_contract.py` | OBSERVED (was missing; created this stage) | new file |
| "PM artifact validator" referenced by brief/skill | UNKNOWN | does not exist; tracked RISK-006 |

## 4. ClickUp workspace

| Fact | Classification | Evidence |
|---|---|---|
| Workspace `First Pavilion (Engineering)` space id 90136583508 | OBSERVED | hierarchy |
| Empty `SelahCue` folder (901318653689) existed prior to this build | OBSERVED | `get_folder` — no lists |
| Product-organising conventions: `Product Epics` folder holds per-product lists (Pavilion Sounds, EduQuest, LandOwner Portal, Yharah, Onward CTCS, LivingSpring, ProjectLens); sprint folders for execution | OBSERVED | hierarchy |
| No existing SelahCue tasks / Build Control / PRD in ClickUp | OBSERVED | `search` → 0 results |
| New `SelahCue — Delivery` list (901327960792) created for Build Control (user-approved) | OBSERVED | `create_list_in_folder` success |
| Build Control task `86ajnx548` created | OBSERVED | `create_task` success |

## 5. Product intent (from brief)

DOCUMENTED. Cross-platform (Windows/macOS/Linux desktop + Android/iOS/iPadOS mobile controller) church presentation & ministry-assistance app combining strongest ideas of PewBeam & ProPresenter as an **original** product. Feature pillars: presentation/slides/song lyrics; Bible scripture system; multiple independent outputs; stage/confidence displays; lower thirds; timers with "TIME UP"; live transcription; automatic scripture detection (explicit + quoted/paraphrased); AI sermon notes; text-to-speech; mobile remote control; livestream content; media playback; service planning. Priorities: live reliability, low CPU/memory, cross-platform, fast live operation, offline-first, operator control over AI, privacy of recordings/transcripts, crash/network/display/provider-failure recovery.

## 6. Baseline conclusion

Greenfield, well-specified by a detailed brief. No reconciliation with existing code needed. The build proceeds through the full 13-stage workflow starting from research. Material unknowns (platform scope bounding, tech stack, licensing, realistic AI accuracy, offline transcription feasibility) are tracked in the risk register and resolved in Stages 2–5. Two tooling gaps (PM artifact validator, Chrome MCP) are surfaced as risks with mitigations.
