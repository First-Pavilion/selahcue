"""Immutable quota metadata exposed by the cloud command surface."""
from dataclasses import dataclass

from selahcue_api.apps.usage.contracts import QuotaSnapshot


@dataclass(frozen=True, slots=True)
class MeterPolicyVersions:
    policy_version: str
    consent_version: str


@dataclass(frozen=True, slots=True)
class CloudPolicies:
    stt: MeterPolicyVersions | None
    notes: MeterPolicyVersions | None


@dataclass(frozen=True, slots=True)
class QuotaEnvelope:
    stt: QuotaSnapshot
    notes: QuotaSnapshot
    policies: CloudPolicies
