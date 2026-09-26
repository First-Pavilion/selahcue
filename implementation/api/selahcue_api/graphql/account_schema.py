import strawberry
from django.conf import settings
from strawberry.extensions import DisableIntrospection

from selahcue_api.apps.accounts.services import (
    ACCOUNT_SESSION_TTL,
    ConfirmPasswordResetResult,
    LoginData,
    RegisterCustomerUserData,
    ResendVerificationData,
    confirm_password_reset,
    login as login_service,
    logout_session,
    refresh_session,
    register_customer_user,
    request_password_reset,
    resend_email_verification,
    verify_email,
)
from selahcue_api.apps.throttling.services import client_ip
from selahcue_api.apps.devices.services import (
    ActivateDeviceWithSessionData,
    activate_device_with_session,
)
from selahcue_api.graphql.context import (
    ACCOUNT_SESSION_COOKIE,
    _read_account_session_token,
    actor_from_info,
    require_customer_org,
)


@strawberry.type
class AccountViewer:
    surface: str
    actor_id: str
    org_id: str


# --- inputs ----------------------------------------------------------------
@strawberry.input
class RegisterCustomerUserInput:
    idempotency_key: str
    email: str
    password: str
    org_name: str
    country: str
    display_name: str = ""
    timezone: str = "UTC"


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.input
class ConfirmPasswordResetInput:
    token: str
    new_password: str


# --- payloads --------------------------------------------------------------
@strawberry.type
class RegisterPayload:
    # Uniform whether or not the email already exists (no user-enumeration).
    accepted: bool


@strawberry.type
class VerifyEmailPayload:
    verified: bool


@strawberry.type
class LoginPayload:
    # session_token is the only field permitted to carry a one-time secret (show-once).
    session_token: str
    expires_at: str
    role: str
    org_id: str


@strawberry.type
class RefreshPayload:
    session_token: str
    expires_at: str


@strawberry.type
class LogoutPayload:
    revoked: bool


@strawberry.type
class RequestPasswordResetPayload:
    accepted: bool


@strawberry.type
class ResendVerificationPayload:
    # Always true. Deliberately carries NO detail: an unknown address, an unverified account
    # and an already-verified one must be indistinguishable, so there is nothing else to say.
    accepted: bool


@strawberry.type
class ConfirmPasswordResetPayload:
    reset: bool


@strawberry.input
class ActivateDeviceInput:
    idempotency_key: str
    device_fingerprint: str
    platform: str
    app_version: str = ""
    display_name: str = ""


@strawberry.type
class ActivateDevicePayload:
    # full_token is the show-once device token; null on an idempotent replay.
    full_token: str | None
    created: bool
    device_public_id: str
    platform: str


def _set_session_cookie(info: strawberry.Info, token: str) -> None:
    """Best-effort: also set the opaque session token as an HttpOnly/Secure/SameSite=Strict cookie
    for browser clients. Desktop clients use the show-once token from the payload (OS keychain)."""
    response = getattr(getattr(info, "context", None), "response", None)
    if response is None:
        return
    response.set_cookie(
        ACCOUNT_SESSION_COOKIE,
        token,
        max_age=int(ACCOUNT_SESSION_TTL.total_seconds()),
        httponly=True,
        secure=getattr(settings, "SESSION_COOKIE_SECURE", True),
        samesite="Strict",
    )


@strawberry.type
class AccountQuery:
    @strawberry.field
    def account_viewer(self, info: strawberry.Info) -> AccountViewer:
        actor = actor_from_info(info)
        checked = require_customer_org(actor, actor.org_id if actor else "")
        return AccountViewer(surface="account", actor_id=checked.actor_id, org_id=checked.org_id or "")


@strawberry.type
class AccountMutation:
    @strawberry.mutation
    def register_customer_user(
        self, info: strawberry.Info, input: RegisterCustomerUserInput
    ) -> RegisterPayload:
        result = register_customer_user(
            RegisterCustomerUserData(
                idempotency_key=input.idempotency_key,
                email=input.email,
                password=input.password,
                org_name=input.org_name,
                country=input.country,
                display_name=input.display_name,
                timezone=input.timezone,
            )
        )
        return RegisterPayload(accepted=result.accepted)

    @strawberry.mutation
    def verify_email(self, info: strawberry.Info, token: str) -> VerifyEmailPayload:
        """The caller IP is resolved HERE, same as the other unauthenticated mutations on this
        surface and for the same reason: only the transport knows how many proxy hops are
        trustworthy (`SELAHCUE_TRUSTED_PROXY_COUNT`) (86akcn92k)."""
        request = getattr(getattr(info, "context", None), "request", None)
        result = verify_email(token, client_ip=client_ip(request) if request is not None else "")
        return VerifyEmailPayload(verified=result.verified)

    @strawberry.mutation
    def resend_verification_email(
        self, info: strawberry.Info, email: str
    ) -> ResendVerificationPayload:
        """Re-issue the verification link behind /verify's V3-V6 states and desktop A13.

        The caller IP is resolved HERE rather than in the service: only the transport knows
        how many proxy hops are trustworthy (`SELAHCUE_TRUSTED_PROXY_COUNT`), and a service
        that read the header itself would be trusting a caller-supplied value.
        """
        request = getattr(getattr(info, "context", None), "request", None)
        result = resend_email_verification(
            ResendVerificationData(
                email=email,
                client_ip=client_ip(request) if request is not None else "",
            )
        )
        return ResendVerificationPayload(accepted=result.accepted)

    @strawberry.mutation
    def login(self, info: strawberry.Info, input: LoginInput) -> LoginPayload:
        result = login_service(LoginData(email=input.email, password=input.password))
        _set_session_cookie(info, result.session_token)
        return LoginPayload(
            session_token=result.session_token,
            expires_at=result.expires_at,
            role=result.role,
            org_id=result.org_id,
        )

    @strawberry.mutation
    def refresh_session(self, info: strawberry.Info) -> RefreshPayload:
        token = _read_account_session_token(info.context.request)
        result = refresh_session(token or "")
        _set_session_cookie(info, result.session_token)
        return RefreshPayload(session_token=result.session_token, expires_at=result.expires_at)

    @strawberry.mutation
    def logout(self, info: strawberry.Info, all_sessions: bool = False) -> LogoutPayload:
        token = _read_account_session_token(info.context.request)
        result = logout_session(token or "", all_sessions=all_sessions)
        response = getattr(getattr(info, "context", None), "response", None)
        if response is not None:
            response.delete_cookie(ACCOUNT_SESSION_COOKIE)
        return LogoutPayload(revoked=result.revoked)

    @strawberry.mutation
    def request_password_reset(self, info: strawberry.Info, email: str) -> RequestPasswordResetPayload:
        """The caller IP is resolved HERE, same as `resend_verification_email` above and for the
        same reason: only the transport knows how many proxy hops are trustworthy
        (`SELAHCUE_TRUSTED_PROXY_COUNT`), and a service that read the header itself would be
        trusting a caller-supplied value (86akcmfd4 — DEC-013's required follow-up)."""
        request = getattr(getattr(info, "context", None), "request", None)
        result = request_password_reset(
            email, client_ip=client_ip(request) if request is not None else ""
        )
        return RequestPasswordResetPayload(accepted=result.accepted)

    @strawberry.mutation
    def confirm_password_reset(
        self, info: strawberry.Info, input: ConfirmPasswordResetInput
    ) -> ConfirmPasswordResetPayload:
        """Caller IP resolved here for the same reason as `request_password_reset` above
        (86akcmfd4 — DEC-013's required follow-up)."""
        request = getattr(getattr(info, "context", None), "request", None)
        result: ConfirmPasswordResetResult = confirm_password_reset(
            input.token,
            input.new_password,
            client_ip=client_ip(request) if request is not None else "",
        )
        return ConfirmPasswordResetPayload(reset=result.reset)

    @strawberry.mutation
    def activate_device_with_session(
        self, info: strawberry.Info, input: ActivateDeviceInput
    ) -> ActivateDevicePayload:
        result = activate_device_with_session(
            actor_from_info(info),
            ActivateDeviceWithSessionData(
                idempotency_key=input.idempotency_key,
                device_fingerprint=input.device_fingerprint,
                platform=input.platform,
                app_version=input.app_version,
                display_name=input.display_name,
            ),
        )
        return ActivateDevicePayload(
            full_token=result.full_token,
            created=result.created,
            device_public_id=result.device.device_public_id,
            platform=result.device.platform,
        )


schema = strawberry.Schema(
    query=AccountQuery,
    mutation=AccountMutation,
    extensions=[] if settings.GRAPHQL_INTROSPECTION_ENABLED else [DisableIntrospection],
)
