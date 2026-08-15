"""Deployment checks for the browser-facing account surface.

`CORS_ALLOWED_ORIGINS` has been read from `SELAHCUE_CORS_ALLOWED_ORIGINS` since the
foundation slice, but nothing has ever consumed it: `corsheaders` is in neither
INSTALLED_APPS nor MIDDLEWARE, and no first-party middleware emits the headers either. A
probe confirms it — with an Origin set, the response carries no `Access-Control-Allow-Origin`
at all and an OPTIONS preflight returns 405.

That is a trap rather than a mere dead setting. An operator sets the variable, sees a
plausible-looking allow-list, and concludes cross-origin access is configured. It is not,
and the symptom is an opaque browser CORS failure with nothing in the server log.

The setting is NOT wired up here, and that is deliberate. SelahCue serves the SPA
SAME-ORIGIN — `implementation/marketing/vite.config.ts` proxies `/graphql` in dev and
`nginx.conf` does the production half — because the account session cookie is
`SameSite=Strict` and a browser never sends it on a cross-site request. Enabling CORS would
add a second, weaker route to the same surface that cannot carry that cookie and would
invite exactly the "just set SameSite=None" fix the Strict setting exists to prevent.
Turning it on is a security decision for the owner, not a config tweak.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import Warning as CheckWarning, register

INERT_CORS_WARNING = "selahcue_accounts.W001"


def _cors_middleware_installed() -> bool:
    return any("cors" in entry.lower() for entry in settings.MIDDLEWARE)


@register()
def cors_allowed_origins_has_no_middleware(app_configs, **kwargs):
    """Warn when an allow-list is configured that nothing can enforce.

    Silent by default: `SELAHCUE_CORS_ALLOWED_ORIGINS` is unset in CI, in tests and in the
    compose stack, so `manage.py check` stays clean. It fires only for the operator who
    actually set the variable and would otherwise be debugging a browser error.

    A Warning, not an Error, and the direction of failure is why: with no CORS headers the
    browser BLOCKS the request, so the misconfiguration fails closed. Nothing is exposed —
    something merely does not work.
    """
    if not getattr(settings, "CORS_ALLOWED_ORIGINS", ()) or _cors_middleware_installed():
        return []
    return [
        CheckWarning(
            "SELAHCUE_CORS_ALLOWED_ORIGINS is set, but no CORS middleware is installed, so "
            "the API emits no CORS headers and every cross-origin browser request is blocked.",
            hint=(
                "This allow-list is enforced by nothing. SelahCue serves the SPA SAME-ORIGIN "
                "instead: implementation/marketing/vite.config.ts proxies /graphql in dev and "
                "nginx.conf does the same in production, which is what lets the "
                "SameSite=Strict account session cookie work at all. Prefer that — unset the "
                "variable. If a genuinely separate origin is required, note that it CANNOT use "
                "the session cookie (SameSite=Strict) and must use the show-once Bearer token, "
                "and that Django's CSRF check will also refuse the cross-origin POST; raise it "
                "as a security decision rather than relaxing SameSite."
            ),
            id=INERT_CORS_WARNING,
        )
    ]
