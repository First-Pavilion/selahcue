from cross_web.exceptions import HTTPException
from django.http import JsonResponse
from strawberry.django.views import GraphQLView

from selahcue_api.graphql.errors import ErrorCode, safe_error_payload, safe_graphql_error


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
