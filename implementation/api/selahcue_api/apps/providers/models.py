"""Durable mapping identity, custody envelope and history invariants."""
from uuid import uuid4

from django.db import DEFAULT_DB_ALIAS, IntegrityError, connections, models, router
from django.db.models import F, Q, Value
from django.db.models.functions import Length
from django.db.models.lookups import Exact, GreaterThanOrEqual, LessThanOrEqual

from .configuration import valid_id
from .contracts import ProviderMappingState as State

EXTERNAL_FIELDS = ("external_project_id", "external_service_account_id", "external_api_key_id")
ENVELOPE_FIELDS = ("secret_version", "wrapping_key_id", "secret_nonce", "secret_ciphertext")
OWNING_STATES = (State.PROVISIONING.value, State.ACTIVE.value)
TERMINAL_STATES = (State.FAILED.value, State.RETIRED.value)

_NO_ENVELOPE = Q(**{f"{name}__isnull": True for name in ENVELOPE_FIELDS})
_HAS_ENVELOPE = (
    Q(**{f"{name}__isnull": False for name in ENVELOPE_FIELDS})
    & Q(secret_version=1)
    & Exact(Length("secret_nonce"), Value(12))
    & GreaterThanOrEqual(Length("secret_ciphertext"), Value(17))
    & LessThanOrEqual(Length("secret_ciphertext"), Value(4112))
)


class ProviderCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    org = models.ForeignKey("selahcue_accounts.CustomerOrg", on_delete=models.PROTECT)
    provider = models.CharField(max_length=8, choices=[("deepgram", "Deepgram"), ("openai", "OpenAI")])
    parent_scope_id = models.CharField(max_length=256)
    external_project_id = models.CharField(max_length=256, null=True)
    external_service_account_id = models.CharField(max_length=256, null=True)
    external_api_key_id = models.CharField(max_length=256, null=True)
    state = models.CharField(max_length=12, choices=[(item.value, item.value) for item in State],
                             default=State.PROVISIONING.value)
    secret_version = models.PositiveSmallIntegerField(null=True)
    wrapping_key_id = models.CharField(max_length=256, null=True)
    secret_nonce = models.BinaryField(null=True)
    secret_ciphertext = models.BinaryField(null=True)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    activated_at = models.DateTimeField(null=True)
    terminal_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "provider"], condition=Q(state__in=OWNING_STATES),
                                    name="provider_credential_owner_uniq"),
            models.UniqueConstraint(
                fields=["provider", "external_project_id", "external_api_key_id"],
                condition=Q(external_api_key_id__isnull=False), name="provider_credential_key_uniq",
            ),
            models.UniqueConstraint(
                fields=["external_project_id"], condition=Q(provider="openai", external_project_id__isnull=False),
                name="provider_openai_project_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(provider="deepgram", external_project_id__isnull=False,
                      external_project_id=F("parent_scope_id"), external_service_account_id__isnull=True)
                    | (
                        Q(provider="openai")
                        & (Q(external_service_account_id__isnull=True) | Q(external_project_id__isnull=False))
                        & (Q(external_api_key_id__isnull=True) | Q(external_service_account_id__isnull=False))
                    )
                ), name="provider_credential_identity_shape",
            ),
            models.CheckConstraint(condition=_NO_ENVELOPE | _HAS_ENVELOPE, name="provider_credential_envelope"),
            models.CheckConstraint(
                condition=(
                    Q(state__in=[item.value for item in State], revision__gte=1)
                    & (
                        Q(state__in=OWNING_STATES, terminal_at__isnull=True)
                        | Q(state__in=TERMINAL_STATES, terminal_at__isnull=False)
                    )
                    & (
                        (Q(state__in=(State.PROVISIONING.value, State.FAILED.value)) & _NO_ENVELOPE
                         & Q(activated_at__isnull=True))
                        | (Q(state=State.RETIRED.value, activated_at__isnull=True) & _NO_ENVELOPE)
                        | (
                            Q(state__in=(State.ACTIVE.value, State.RETIRED.value), activated_at__isnull=False,
                              external_project_id__isnull=False, external_api_key_id__isnull=False)
                            & _HAS_ENVELOPE
                        )
                    )
                ), name="provider_credential_state_shape",
            ),
        ]

    def save(self, *args, **kwargs):
        # PostgreSQL is authoritative even for bulk updates and direct SQL.
        ids = (self.parent_scope_id, self.wrapping_key_id, *(getattr(self, name) for name in EXTERNAL_FIELDS))
        if not valid_id(self.parent_scope_id) or any(value is not None and not valid_id(value) for value in ids):
            raise IntegrityError("Invalid provider mapping identifier")
        alias = kwargs.get("using") or router.db_for_write(type(self), instance=self) or DEFAULT_DB_ALIAS
        if connections[alias].vendor == "sqlite":
            if self._state.adding:
                if self.state != State.PROVISIONING or self.revision != 1:
                    raise IntegrityError("Invalid initial provider mapping state")
            else:
                before = type(self).objects.using(alias).filter(pk=self.pk).first()
                if before is None:
                    raise IntegrityError("Provider mapping history is immutable")
                self._validate_history(before)
        return super().save(*args, **kwargs)

    def _validate_history(self, before):
        immutable = ("id", "org_id", "provider", "parent_scope_id", "created_at")
        old_state = before.state
        transitions = {
            State.PROVISIONING: {State.PROVISIONING, State.ACTIVE, State.FAILED, State.RETIRED},
            State.ACTIVE: {State.ACTIVE, State.RETIRED},
            State.FAILED: {State.FAILED},
            State.RETIRED: {State.RETIRED},
        }
        if (
            any(getattr(self, name) != getattr(before, name) for name in immutable)
            or any(
                getattr(self, name) != getattr(before, name)
                and (old_state != State.PROVISIONING or getattr(before, name) is not None)
                for name in EXTERNAL_FIELDS
            )
            or self.state not in transitions[old_state]
            or self.revision != before.revision + 1
            or (before.activated_at is not None and self.activated_at != before.activated_at)
            or (before.activated_at is None and self.activated_at is not None
                and not (old_state == State.PROVISIONING and self.state == State.ACTIVE))
            or (before.terminal_at is not None and self.terminal_at != before.terminal_at)
        ):
            raise IntegrityError("Provider mapping history is immutable")

    def delete(self, *args, **kwargs):
        raise IntegrityError("Provider mapping history is retained")
