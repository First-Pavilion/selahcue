from cross_web.exceptions import HTTPException
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from strawberry.django.views import GraphQLView

from selahcue_api.graphql.errors import ErrorCode, safe_error_payload, safe_graphql_error


@require_GET
@ensure_csrf_cookie
def csrf_bootstrap(request):
    """Issue the `csrftoken` cookie the browser surfaces require. Call once on SPA load.

    WHY THIS ENDPOINT EXISTS. Both GraphQL surfaces declare `*_session_with_csrf`
    (`route_contracts.py`) and `CsrfViewMiddleware` enforces it — but the SPA is served as
    STATIC files by Vite/nginx, so Django never renders a page, and nothing else called
    `get_token()`. The cookie could therefore never come into existence, which made every
    account mutation a permanent 403 for every real browser (`verifyEmail`,
    `resendVerificationEmail`, the reset pair, `login`, and the DEC-005 admin device path).
    The Django test client bypasses CSRF unless `enforce_csrf_checks=True`, which is why a
    green suite sat on top of a surface no browser could reach.

    The fix is to seed the cookie, NOT to exempt the route: `csrf_exempt` would delete a
    declared, tested control, and `SameSite=Strict` alone is not an equivalent substitute —
    SameSite is scoped to the SITE, so it still carries the session cookie for a same-site
    attacker (a taken-over `*.selahcue.com` host), where a CSRF token does not.

    SameSite=Strict does NOT get in the way here. The awkward case looks like the verification
    link: a cross-site TOP-LEVEL navigation out of a webmail client, which by definition sends
    no Strict cookie. It does not need to — that navigation only fetches static assets. Once
    the page is loaded the top-level browsing context IS this site, so this GET is a same-site
    XHR: the cookie is accepted here and sent on the mutation that follows.

    Unauthenticated on purpose: a CSRF token is not a credential and is not secret from the
    browser holding it. Fetching this cross-origin gains an attacker nothing — they receive a
    token bound to THEIR OWN cookie, which is useless against a victim's, and no
    `Access-Control-Allow-Origin` header lets them read the response at all.
    """
    response = JsonResponse({"ready": True})
    # A shared cache must never serve one visitor the token minted for another. Django already
    # adds `Vary: Cookie` when it sets the cookie, but that does not stop a cache storing the
    # response to a request that arrived with NO cookie — which is precisely this one.
    response["Cache-Control"] = "no-store"
    return response


class SafeGraphQLView(GraphQLView):
    def dispatch(self, request, *args, **kwargs):
        try:
            return self.run(request=request)
        except HTTPException as error:
            code = ErrorCode.NOT_FOUND if error.status_code == 404 else ErrorCode.VALIDATION_FAILED
            return JsonResponse(safe_error_payload(code), status=error.status_code)

    def process_result(self, request, result):
        response = super().process_result(request, result)
        if result.errors:
            response["errors"] = [safe_graphql_error(error) for error in result.errors]
        return response


class AdminGraphQLView(SafeGraphQLView):
    surface = "admin"


class AccountGraphQLView(SafeGraphQLView):
    surface = "account"
