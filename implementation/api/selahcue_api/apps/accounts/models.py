from django.db import models


class CustomerStatus(models.TextChoices):
    PROSPECT = "PROSPECT", "Prospect"
    TRIAL = "TRIAL", "Trial"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    SUSPENDED = "SUSPENDED", "Suspended"
    CANCELLED = "CANCELLED", "Cancelled"
    CHURNED = "CHURNED", "Churned"
    ARCHIVED = "ARCHIVED", "Archived"


class CustomerOrg(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    status = models.CharField(max_length=32, choices=CustomerStatus.choices, default=CustomerStatus.PROSPECT)
    primary_contact_email = models.EmailField()
    billing_contact_email = models.EmailField(blank=True)
    country = models.CharField(max_length=2)
    timezone = models.CharField(max_length=64, default="UTC")
    plan = models.CharField(max_length=64, default="TRIAL")
    device_limit = models.PositiveIntegerField(default=1)
    internal_notes = models.TextField(blank=True)
    created_by_actor_id = models.CharField(max_length=128)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["created_by_actor_id", "idempotency_key"],
                name="uniq_customer_org_actor_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "country"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["primary_contact_email"]),
        ]

    def __str__(self) -> str:
        return self.name


class CustomerUserStatus(models.TextChoices):
    # INVITED = created but email not yet verified (cannot mint a session).
    INVITED = "INVITED", "Invited"
    # ACTIVE = email verified, may sign in.
    ACTIVE = "ACTIVE", "Active"
    # DISABLED = admin/seat revocation; sign-in refused with POLICY_DENIED.
    DISABLED = "DISABLED", "Disabled"


class CustomerRole(models.TextChoices):
    # ADMIN may manage devices/account (FR-137); MEMBER is read-only for those controls.
    ADMIN = "ADMIN", "Administrator"
    MEMBER = "MEMBER", "Member"


class CustomerUser(models.Model):
    """A per-person login principal for a customer org (DEC-007 / ADR-0023).

    The tenant ``CustomerOrg`` is NOT a login — it has only non-unique contact
    emails and no password. This is the missing principal that makes
    ``ActorKind.CUSTOMER`` and ``require_customer_org()`` reachable in prod.
    Credentials follow the shipped hashed-credential convention
    (``make_password`` hash + ``HMAC-SHA256(SECRET_KEY)`` fingerprint), NOT
    Django's ``AUTH_USER_MODEL`` (unused; ``AUTH_USER_MODEL`` is unset).
    """

    customer = models.ForeignKey(
        "selahcue_accounts.CustomerOrg",
        on_delete=models.PROTECT,
        related_name="users",
    )
    # Normalised (.strip().lower()) at the service layer, as create_customer does.
    email = models.EmailField()
    # Deterministic HMAC-SHA256(SECRET_KEY, normalised_email) lookup column — keys the
    # no-enumeration login/reset path (same pattern as the device/license fingerprints).
    email_fingerprint = models.CharField(max_length=64)
    # make_password(password); NEVER plaintext, NEVER == compared. 256 matches
    # AppLicenseKey.secret_hash / DeviceToken.token_hash.
    password_hash = models.CharField(max_length=256)
    status = models.CharField(
        max_length=32, choices=CustomerUserStatus.choices, default=CustomerUserStatus.INVITED
    )
    # Field default is least-privilege MEMBER; the signup service promotes the first
    # user in an org to ADMIN. A stray direct create can never accidentally be admin.
    role = models.CharField(max_length=32, choices=CustomerRole.choices, default=CustomerRole.MEMBER)
    display_name = models.CharField(max_length=200, blank=True)
    # null == unverified; login is gated (POLICY_DENIED) until set.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Bumped on every password set/reset; sessions with issued_at < this are rejected
    # (mass session invalidation on password change).
    password_changed_at = models.DateTimeField(null=True, blank=True)
    # Bounded soft-lockout counters (no unbounded growth).
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    # 'self_signup' or the inviting admin's actor_id.
    created_by_actor_id = models.CharField(max_length=128)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Global-unique login email: one email -> one login -> one org via the FK
            # (v1 assumption per DEC-007; login has no org context to disambiguate).
            models.UniqueConstraint(fields=["email"], name="uniq_customer_user_email"),
            # Unique deterministic lookup column (also serves login lookups as an index).
            models.UniqueConstraint(
                fields=["email_fingerprint"], name="uniq_customer_user_email_fp"
            ),
            # Idempotency guard, mirroring CustomerOrg.
            models.UniqueConstraint(
                fields=["created_by_actor_id", "idempotency_key"],
                name="uniq_customer_user_actor_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.customer_id})"


class CustomerSessionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVOKED = "REVOKED", "Revoked"


class CustomerSession(models.Model):
    """An opaque, server-side, hashed account session token (DEC-007 / ADR-0023) — a structural
    clone of ``DeviceToken``, NOT a JWT. Only the masked triple + hash + unique fingerprint are
    stored; the full token leaves the system exactly once (the login/refresh response). Server-side
    storage makes it instantly revocable (logout, password change, seat removal)."""

    customer_user = models.ForeignKey(
        "selahcue_accounts.CustomerUser",
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    token_prefix = models.CharField(max_length=32)
    token_suffix = models.CharField(max_length=16)
    masked_token = models.CharField(max_length=64)
    token_hash = models.CharField(max_length=256)
    token_fingerprint = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=16, choices=CustomerSessionStatus.choices, default=CustomerSessionStatus.ACTIVE
    )
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("issued_at")),
                name="customer_session_expires_after_issue",
            ),
        ]
        indexes = [
            models.Index(fields=["customer_user", "status"]),
        ]

    def __str__(self) -> str:
        return self.masked_token


class CredentialTokenPurpose(models.TextChoices):
    EMAIL_VERIFY = "EMAIL_VERIFY", "Email verification"
    PASSWORD_RESET = "PASSWORD_RESET", "Password reset"


class CredentialToken(models.Model):
    """A single-use, show-once credential token for email verification and password reset
    (purpose-discriminated), cloning the ``DeviceToken`` storage shape. High-entropy, hashed at
    rest, short-lived; the raw token is delivered exactly once via the email link and never stored
    plaintext. A future TOTP/2FA purpose extends the enum without reshaping the table."""

    customer_user = models.ForeignKey(
        "selahcue_accounts.CustomerUser",
        on_delete=models.PROTECT,
        related_name="credential_tokens",
    )
    purpose = models.CharField(max_length=32, choices=CredentialTokenPurpose.choices)
    token_hash = models.CharField(max_length=256)
    token_fingerprint = models.CharField(max_length=64, unique=True)
    masked_token = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["customer_user", "purpose"]),
        ]

    def __str__(self) -> str:
        return f"{self.purpose}:{self.masked_token}"
