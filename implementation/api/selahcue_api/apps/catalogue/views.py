"""Unauthenticated same-origin read surface; no cookie/header actor interpretation."""
from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse

from selahcue_api.apps.catalogue.public_catalogue import PUBLIC_CACHE, CatalogueUnavailable
from selahcue_api.apps.throttling.decorators import throttle


def _error(code, status):
    return JsonResponse({"error": {"code": code}}, status=status)


@throttle("public-catalogue", "SELAHCUE_THROTTLE_PUBLIC_CATALOGUE", (120, 60), fail_closed_on_store_unavailable=True)
def _read(request):
    try:
        return HttpResponse(PUBLIC_CACHE.read(), content_type="application/json")
    except (DatabaseError, CatalogueUnavailable):
        return _error("catalogue_unavailable", 503)


def plans(request):
    if request.method != "GET":
        response = _error("get_required", 405)
        response["Allow"] = "GET"
    elif request.GET:
        # No filters/pagination/currency default; one finite projection/cache entry.
        response = _error("catalogue_invalid_request", 400)
    else:
        response = _read(request)
        if response.status_code == 429:
            retry_after = response["Retry-After"]
            response = _error("catalogue_rate_limited", 429)
            response["Retry-After"] = retry_after
    # Shared/browser caches must neither bypass the limiter nor hide the next data edit.
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
