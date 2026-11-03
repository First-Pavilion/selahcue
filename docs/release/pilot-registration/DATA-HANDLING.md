# Pilot registration handling procedure

Ticket: [Pilot collection notice](https://app.clickup.com/t/17tnw2bbhxn). Notice version `pilot-registration-2026-11-03`; shared authored text is `notice.json`. The marketing page and generated n8n form both consume that text. This is an approved product handling policy, not a legal-controller classification or a certification of legal compliance.

The tester retains ownership of the church data supplied. SelahCue support operations is responsible for administering collection and deletion requests. The deployment owner must designate the restricted Sheet administrator before enabling collection; the role is recorded here, but no person/account or Google protection is asserted to exist.

## Required fields and purpose

Name/email: contact about the test and registration. Church name/role/city/country: identify the test setting and coverage. Platform: choose the installer. Phone remains optional. Do not add congregation records, audio or transcripts. No account/payment requirement or marketing checkbox is added. Any future marketing opt-in must be separate and optional. Cloud audio/transcript consent remains in the application and is not granted by registration.

n8n sends the contact/church values to a dedicated Google Sheet. The API ledger stores UUID, keyed payload/destination fingerprints, row/platform/notice version and timestamps, not raw contact/church values. These identifiers/fingerprints remain pseudonymous/linkable while keys or corresponding records remain; do not describe them as anonymous.

## Fixed retention deadline and earlier requests

The pilot ends `2027-04-30T23:59:59Z`. SelahCue support operations must clear identifiable contact/church values and dispose of identifiable registration records by `2027-07-29T23:59:59Z`, 90 days later. This is a fixed final deadline, not 90 days after registration or a fresh period on retry. Operations must assign and calendar this deletion before enabling collection; this source does not schedule or implement a purge engine.

Deletion requests go to legal@selahcueapp.com (primary) or support@selahcueapp.com (alternate). Ask for the registered email and optional registration ID, never passwords/provider keys/audio. Verify using the existing contact rather than an arbitrary new destination; restrict request access to support operations. Pause the affected registration's use and retire its attempts/receipts before clearing it. If the current service cannot retire the individual record safely, disable collection and grants for that channel and reconcile before proceeding; do not claim an unsupported per-record deletion API exists.

Clear the assigned Sheet row's values without deleting/inserting/moving/sorting rows or recycling its allocation. Preserve allocator counters and minimal binding ledger while any corresponding attempt or receipt could remain valid. Once the pilot/receipts are invalid, support operations must reconcile and dispose of remaining linkable ledger rows and identifiers by the final deadline while keeping collection/grants disabled. Do not reset counters and reopen the same channel after destructive state loss; use a reconciled ledger or a new isolated channel/tab.

Inspect relevant n8n execution histories, exports, support copies and service backups; execution payload saving is disabled in the shipped workflow. Document what was cleared and any residual backup retention/access restrictions and communicate that to the requester. Do not promise immediate or universal backup erasure. Do not put submitted values or screenshots of personal data in tickets/logs. Keep a minimal deletion-action record without retaining the deleted contact/church payload.

## Before enabling collection

- Designate the restricted Sheet administrator under SelahCue support operations and record protected dedicated A:M tab/access evidence. Limit the workflow identity to that Sheet; no shared/public link.
- Keep the workflow inactive and marketing config disabled until actual API/n8n/Google credentials, notice configuration, package manifest/grants and live persistence/private-read evidence pass their existing gates.
- Configure the approved notice version and real origin explicitly. `SELAHCUE_PILOT_RETENTION_DAYS` currently retires attempts/receipts relative to their creation; it does not delete Sheet content or implement the fixed final deadline. Pick an attempt lifetime within this policy, record it accurately, and complete the fixed deletion procedure separately. Do not present that setting as an automated purge.
- The existing marketing config's `data_owner` identifies the SelahCue collection administrator (not a transfer of the tester's church-data ownership). Its displayed `retention_days` must describe the attempt lifetime accurately and link to the fixed-deadline notice. Do not enable a contradictory public configuration.
- Assign/calendar the fixed deadline and rehearse a synthetic earlier-request clear/retire/reconcile without moving rows. Confirm mailbox handling and backup copy procedures. No live collection or deletion execution is claimed by this source.

Rollback: disable collection/grants/marketing before reverting notice configuration; preserve allocation history and honour already-collected records' stated handling policy.
