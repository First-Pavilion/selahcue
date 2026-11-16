# Cargo JSON scanner encoding repair implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the release-key scanner read Cargo UTF-8 receipts independently of the OS text default while preserving every security gate.
**Architecture:** Actual CLI fixture regression under verified ASCII locale, one explicit receipt decode, existing cheap CI job invocation.
**Tech Stack:** Python3 standard library, Cargo JSON, GitHub Actions Ubuntu/Windows.
**Spec:** docs/superpowers/specs/2026-11-16-cargo-json-utf8-scanner.md

## Global Constraints

Own scripts/test_dev_key_scan.py, scripts/dev_key_scan.py and one CI test step only. StrictUTF8 receiptinput, no lossydecoding/catches/artifactglob/keygateweakening. Tests precedeproductionfixandmustfailcorrectly. SmalllocalstdlibCLI suite explicitlyallowed with sequential5schildtimeouts/tinyfiles; all builds/imports/apps/browser/services/network remainheld. No subagents/remote mutation/secrets, preserveothers'work.

## Review Focus

- NonUTF8localedefault: verifyactualchildencoding and UTF8metadata bytes; positiveCLIrequires success.
- Lossydecoder mutation: invalidUTF8mustfail before selection.
- Falseempty-scan success: missingrequiredrlib/exe fails with owning category.
- Broken positive controls: missingdebugkey separately fails forlibrary/executable.
- Bypassedreleasegate: synthetic key in either current releaseartifact is refused while malformedunrelatedJSON remains tolerated.

### Task 1: Prove and repair the scanner text boundary

Read the binding spec and root preflight E/release-evidence/open-pr-review/windows-cargo-json-preflight-20261116.md. Work in supplied isolatedUbranch at design-onlydispatchHEAD. You are not alone; no siblingplans/otherworkerchangesmaybereverted.

- [ ] Add the actualCLI unittest fixtures/control cases from the spec beforeediting scanner. Read writing-good-tests reference. Use /opt/homebrew/bin/python3.14 explicitly forlocaltestinvocations; subprocessesuseits sys.executable. Capture full command/output/encoding, not a shortenedclaim.
- [ ] Run fullnewtestfile with unchangedscanner. Confirm intendedpositiveUTF8caseFAILSbecauseUnicodeDecodeError; baselineandnegativecontrols must reach their expected categories. Ifdifferentfailure, fixfixtureonly and rerunbeforeproductionedit. Commit test-only checkpoint and record it.
- [ ] Apply minimal strictUTF8 receiptread and wire exactlyonecheapCIstep in existing lint-workflows. Run whole new suite toGREEN plus AST syntax/actionlint/Gitdiffchecks. Preserveallothergates/paths. Commit fix+CIwiring separately.
- [ ] Write task-1-report.md with exactRED/GREENcommits,commandsandfullsavedoutputs, retainedcontrols, staticchecks and actualWindowsbinarygateUNRUN. Returnconcise/status/commits;rootowns newfull-ci and independenttask/finalreviews. No pushorCI dispatch.

## Completion

ActualregressionRED/GREEN and scopedreviewpass; currentWindowsrealCargoartifactscan andallrequiredcoveringCIrunpass; source/target/tree and finalreviewverifiedbeforemerge.
