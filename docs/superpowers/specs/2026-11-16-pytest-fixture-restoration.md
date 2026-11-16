# Restore the concrete Django connection in query controls

This review correction belongs to PR #422's pytest 9.2.0 update. The user has authorized TDD, subagent implementation, re-review and merge after passing. Its only implementation path is `implementation/api/tests/test_usage_retained_history_load.py`.

## Observed regression and choice

Candidate `c69546ef129619817ecee439bd29031b226c7611` failed hosted run 43859947767. The four-statement capacity control passed its assertion, then Django's PostgreSQL flush failed because `DatabaseWrapper.force_debug_cursor` was missing. The run reached 2,635 distinct cases and left 569 unexecuted. The same failure occurred in the dependent action-pin PR #420. The predecessor on pytest 9.1.1 passed all 3,193 tests plus 57 subtests with 11 skips.

The source preflight at `designs/pytest-fixture-restoration-preflight-20261116.md` in the evidence workspace explains the change using RECORD-verified cached pytest and Django sources. Pytest 9.2.0 records instance attributes from the target's own dictionary. Django's proxy stores neither temporary attribute, and forwards deletion to the real wrapper. The passing in-body assertion checks a different, inner capture context.

Possible corrections were reverting the dependency, changing the query-measurement helper, or fixing the two test fixtures' patch target and lifetime. Use the concrete wrapper with an inner patch context. This preserves the updated dependency and existing measurement contract. No production query, fixture scope, global monkeypatch policy, workflow, dependency pin or timeout change is authorized.

## Required behavior

Resolve the current default connection wrapper and ensure it is connected before capturing the original `queries_log` object and `force_debug_cursor` value. In each of the two affected tests, use an inner `monkeypatch.context()` to patch that concrete wrapper to a fresh `deque(maxlen=4)` and `False`. Exit the context before transactional test teardown.

Preserve both statement-count parameters 4 and 5; the exact capacity error matcher; the original exception object's identity; both inner false-flag checks; and the existing real SELECT/fetch in the exception test while its tiny log remains active. Preserve the measurement helpers and the positive one-query and 9,200-query transaction controls byte for byte.

After each inner patch context, require the exact original deque object and original flag, then execute `SELECT 1` through the normal proxy cursor and require `(1,)`. A recreated default deque does not satisfy restoration. These observations must precede Django's ordinary transactional teardown, which must also pass in the full hosted suite.

Do not change the separate proxy patch of the inherited `commit` method: its restoration removes an instance override and correctly reveals the class method, and it passed the failing candidate's earlier execution. Preserve all unrelated tests and assertions. No skipped cases, retries, weakened error matching or exception swallowing.

## Execution and boundaries

The archived teardown error is the actual failing regression this fixture-only correction addresses. It is not a new production feature assertion. Root has read the report and raw exception and independently rehashed its complete archive. The worker must read that evidence before authoring the correction and must label every unexecuted check honestly. No local project runtime, imports, installs, databases or resource probes while paging is active.

Hosted GREEN must execute all five existing admission controls, their restored-state checks and transactional teardown under pinned pytest 9.2.0/PostgreSQL, then complete the entire API suite including the previously unreached suffix. Preserve historical failed results, exact skips and changed pytest parameter labels. Other triggered CI remains required. All four relevant domains and the final whole-branch reviewer must assess the exact corrected composition before merge.
