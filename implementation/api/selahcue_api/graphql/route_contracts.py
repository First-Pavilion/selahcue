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
# Every such route MUST pick one: a suspension degrades commercial surfaces and nothing else,
# so each route is either one of those surfaces or deliberately not. Nothing else enforces
# this, because `authenticate_device_token` checks the token and never the licence.
#
# COMMERCIAL — refused with POLICY_DENIED while the licence is not activatable, by calling
#   `devices.services.require_commercial_service` (the one named enforcement point).
# ALLOWED_WHILE_SUSPENDED — reachable on purpose; the reason is on the route below.
LICENCE_GATE_COMMERCIAL = "commercial"
LICENCE_GATE_ALLOWED_WHILE_SUSPENDED = "allowed_while_suspended"
LICENCE_GATES = frozenset({LICENCE_GATE_COMMERCIAL, LICENCE_GATE_ALLOWED_WHILE_SUSPENDED})


@dataclass(frozen=True)
class CommandEndpointContract:
    surface: str
    path: str
    method: str
    auth_context: str
    # Required for `device_token` routes, empty for every other auth context.
    # `tests/test_license_suspend_reinstate.py` sweeps `desktop_command_contracts()` and fails
    # when a device-token route declares neither value.
    licence_gate: str = ""


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
        # Native account sign-in (86ak5t1gw). Both are CSRF-exempt, which is sound only because
        # neither reads or sets a cookie: the session travels in `Authorization: Bearer` alone.
        CommandEndpointContract("desktop", "v1/sessions", "POST", "account_credentials_no_cookie"),
        CommandEndpointContract(
            "desktop", "v1/activations:with-session", "POST", "account_session_bearer_no_cookie"
        ),
        # Refresh reports the licence status truthfully (including SUSPENDED) so the device
        # can act on it; refusing it would blind the very device that needs to learn it.
        CommandEndpointContract(
            "desktop", "v1/license:refresh", "POST", "device_token",
            licence_gate=LICENCE_GATE_ALLOWED_WHILE_SUSPENDED,
        ),
        CommandEndpointContract(
            "desktop", "v1/entitlements/manifest", "GET", "device_token",
            licence_gate=LICENCE_GATE_COMMERCIAL,
        ),
        # Downloads stay reachable while suspended: FR-531 keeps security patches available in
        # degraded licence states, and the show must be patchable.
        CommandEndpointContract(
            "desktop", "v1/downloads:prepare", "POST", "device_token",
            licence_gate=LICENCE_GATE_ALLOWED_WHILE_SUSPENDED,
        ),
        CommandEndpointContract(
            "desktop", "v1/downloads/<lease_id>:complete", "POST", "device_token",
            licence_gate=LICENCE_GATE_ALLOWED_WHILE_SUSPENDED,
        ),
        # Metered usage is a commercial surface (FR-533/546). Still 501, so nothing enforces
        # it yet; the sweep requires a commercial route to refuse a suspended licence the
        # moment it stops answering 501.
        CommandEndpointContract(
            "desktop", "v1/usage-events:batch", "POST", "device_token",
            licence_gate=LICENCE_GATE_COMMERCIAL,
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
