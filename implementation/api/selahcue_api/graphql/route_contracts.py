from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphQLEndpointContract:
    surface: str
    path: str
    schema_name: str
    auth_context: str
    allow_queries_via_get: bool
    multipart_uploads_enabled: bool
    graphql_ide: str | None


# What a `device_token` route does for a device whose licence is SUSPENDED (D3 / DEC-010).
# Every route whose auth_context is exactly "device_token" MUST pick one (the account-session
# bearer on `activations:with-session` is gated through activation instead): a suspension
# degrades commercial surfaces and nothing else, so each route is either one of those
# surfaces or deliberately not. Nothing else enforces this, because `authenticate_device_token`
# checks the token and never the licence.
#
# COMMERCIAL — refused with POLICY_DENIED while the licence is not activatable, by calling
#   `devices.services.require_commercial_service` (the one named enforcement point).
# ALLOWED_WHILE_SUSPENDED — reachable on purpose; the reason is on the route below.
LICENSE_GATE_COMMERCIAL = "commercial"
LICENSE_GATE_ALLOWED_WHILE_SUSPENDED = "allowed_while_suspended"
LICENSE_GATES = frozenset({LICENSE_GATE_COMMERCIAL, LICENSE_GATE_ALLOWED_WHILE_SUSPENDED})


@dataclass(frozen=True)
class CommandEndpointContract:
    surface: str
    path: str
    method: str
    auth_context: str
    # Required for `device_token` routes, empty for every other auth context.
    # `tests/test_license_suspend_reinstate.py` sweeps `desktop_command_contracts()` and fails
    # when a device-token route declares neither value, and fails when a `v1/` route exists in
    # the URLconf without an entry here.
    license_gate: str = ""


def graphql_endpoint_contracts(*, debug: bool) -> tuple[GraphQLEndpointContract, ...]:
    graphql_ide = "graphiql" if debug else None
    return (
        GraphQLEndpointContract(
            surface="admin",
            path="graphql/admin",
            schema_name="admin_schema",
            auth_context="staff_session_with_csrf",
            allow_queries_via_get=False,
            multipart_uploads_enabled=False,
            graphql_ide=graphql_ide,
        ),
        GraphQLEndpointContract(
            surface="account",
            path="graphql/account",
            schema_name="account_schema",
            auth_context="customer_session_with_csrf",
            allow_queries_via_get=False,
            multipart_uploads_enabled=False,
            graphql_ide=graphql_ide,
        ),
    )


def desktop_command_contracts() -> tuple[CommandEndpointContract, ...]:
    return (
        CommandEndpointContract("desktop", "v1/activations", "POST", "app_key_then_device_token"),
        # Native account sign-in/cleanup (86ak5t1gw,17tnw2b1wf2). These are CSRF-exempt, which is sound only because
        # neither reads or sets a cookie: the session travels in `Authorization: Bearer` alone.
        CommandEndpointContract("desktop", "v1/sessions", "POST", "account_credentials_no_cookie"),
        CommandEndpointContract(
            "desktop", "v1/activations:with-session", "POST", "account_session_bearer_no_cookie"
        ),
        CommandEndpointContract(
            "desktop", "v1/sessions:revoke", "POST", "account_session_bearer_no_cookie"
        ),
        # Refresh reports the licence status truthfully (including SUSPENDED) so the device
        # can act on it; refusing it would blind the very device that needs to learn it.
        CommandEndpointContract(
            "desktop", "v1/license:refresh", "POST", "device_token",
            license_gate=LICENSE_GATE_ALLOWED_WHILE_SUSPENDED,
        ),
        CommandEndpointContract(
            "desktop", "v1/entitlements/manifest", "GET", "device_token",
            license_gate=LICENSE_GATE_COMMERCIAL,
        ),
        # Downloads are declared reachable while suspended on the strength of FR-531, which keeps
        # SECURITY PATCHES available in degraded licence states (the show must be patchable). Two
        # cautions for whoever builds these: FR-531 is a proposed requirement and covers security
        # patches only, so a feature-upgrade request through `downloads:prepare` must still call
        # `require_commercial_service` (or this route needs a third, partly-commercial
        # declaration); and both routes are 501 stubs today, so the sweep cannot test this
        # declaration against real behaviour yet.
        CommandEndpointContract(
            "desktop", "v1/downloads:prepare", "POST", "device_token",
            license_gate=LICENSE_GATE_ALLOWED_WHILE_SUSPENDED,
        ),
        CommandEndpointContract(
            "desktop", "v1/downloads/<lease_id>:complete", "POST", "device_token",
            license_gate=LICENSE_GATE_ALLOWED_WHILE_SUSPENDED,
        ),
        # Metered usage is a commercial surface (FR-533/546). Still 501, so nothing enforces
        # it yet; the sweep requires a commercial route to refuse a suspended licence the
        # moment it stops answering 501.
        CommandEndpointContract(
            "desktop", "v1/usage-events:batch", "POST", "device_token",
            license_gate=LICENSE_GATE_COMMERCIAL,
        ),
    )


def browser_bootstrap_contract() -> CommandEndpointContract:
    """The GET that issues the `csrftoken` cookie both browser surfaces require.

    Declared here like every other route so the contract module stays a complete inventory.
    `auth_context` is "none" because a CSRF token is not a credential — it is only meaningful
    paired with the cookie of the browser that asked for it.
    """
    return CommandEndpointContract(
        surface="browser",
        path="graphql/csrf",
        method="GET",
        auth_context="none_issues_csrf_cookie",
    )


def billing_webhook_contract() -> CommandEndpointContract:
    return CommandEndpointContract(
        surface="billing_provider",
        path="webhooks/billing/<provider>",
        method="POST",
        auth_context="provider_signature",
    )
