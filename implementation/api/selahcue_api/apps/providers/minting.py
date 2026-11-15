"""Single-authority Deepgram mint dispatch and receipt handling."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
import time
from uuid import UUID

from .adapters.deepgram_grants import parse_grant
from .adapters.grants_transport import TransportFailure, run_grant_transport
from .contracts import DefiniteFailure, Granted, MintFailureCode as Code, MintOutcome, MintPolicy, OutcomeUnknown, SecretBytes
from .stt_circuit import STT_CIRCUIT
from .stt_policy import STT_MINT_POLICY


@dataclass(frozen=True, slots=True)
class SttDispatchAuthorization:
    attempt_id: UUID
    owner_nonce: UUID
    reservation_id: UUID
    mapping_id: UUID
    mapping_revision: int
    org_id: int
    parent_scope_id: str
    external_project_id: str
    external_api_key_id: str
    secret: SecretBytes = field(repr=False)
    reserved_at: datetime
    reserved_monotonic_ns: int
    send_not_after_utc: datetime
    send_not_after_ns: int


@dataclass(frozen=True, slots=True)
class MintDispatch:
    authorization: SttDispatchAuthorization = field(repr=False)
    request_started_at: datetime
    invocation_monotonic_ns: int
    overall_deadline_ns: int
    io_deadline_ns: int


@dataclass(frozen=True, slots=True)
class MintReceipt:
    outcome: MintOutcome = field(repr=False)
    response_received_at: datetime | None


def mint(mapping_id: UUID, policy: MintPolicy, *, dispatch: MintDispatch) -> MintReceipt:
    authority = dispatch.authorization
    if (
        type(policy) is not MintPolicy or policy != STT_MINT_POLICY
        or any(type(seconds) is not int for seconds in (
            policy.credential_ttl_seconds, policy.connect_timeout_seconds,
            policy.read_timeout_seconds, policy.absolute_deadline_seconds,
        ))
    ):
        return MintReceipt(DefiniteFailure(Code.CONFIGURATION_UNAVAILABLE), None)
    expected_end = min(
        dispatch.invocation_monotonic_ns + 4_000_000_000, authority.send_not_after_ns + 4_000_000_000,
    )
    if (
        dispatch.overall_deadline_ns != expected_end or dispatch.io_deadline_ns != expected_end - 500_000_000
        or type(mapping_id) is not UUID or mapping_id != authority.mapping_id
        or authority.external_project_id != authority.parent_scope_id
        or dispatch.invocation_monotonic_ns >= authority.send_not_after_ns
        or dispatch.request_started_at >= authority.send_not_after_utc
    ):
        return MintReceipt(DefiniteFailure(Code.REQUEST_REJECTED_LOCALLY), None)
    generation = STT_CIRCUIT.admit()
    if generation is None:
        return MintReceipt(DefiniteFailure(Code.REQUEST_REJECTED_LOCALLY), None)
    outcome = None
    try:
        reply = run_grant_transport(dispatch)
        if isinstance(reply, TransportFailure):
            if reply.before_http:
                outcome = DefiniteFailure(Code.REQUEST_REJECTED_LOCALLY)
            else:
                outcome = OutcomeUnknown(reply.code)
            return MintReceipt(outcome, None)
        outcome = parse_grant(
            reply.status, reply.body, response_received_at=reply.response_received_at,
            request_started_at=dispatch.request_started_at,
        )
        if time.monotonic_ns() >= dispatch.overall_deadline_ns:
            outcome = OutcomeUnknown(Code.TRANSPORT_TIMEOUT)
        if isinstance(outcome, Granted) and outcome.grant.expires_at <= datetime.now(UTC):
            outcome = OutcomeUnknown(Code.INVALID_PROVIDER_RESPONSE)
        return MintReceipt(outcome, reply.response_received_at)
    finally:
        STT_CIRCUIT.finish(generation, outcome)
