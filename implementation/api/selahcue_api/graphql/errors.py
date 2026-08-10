from enum import Enum

from graphql import GraphQLError


class ErrorCode(str, Enum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    POLICY_DENIED = "POLICY_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


SAFE_MESSAGES = {
    ErrorCode.UNAUTHENTICATED: "Authentication is required.",
    ErrorCode.PERMISSION_DENIED: "You do not have permission to perform this action.",
    ErrorCode.VALIDATION_FAILED: "The request is invalid.",
    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.CONFLICT: "The request conflicts with the current resource state.",
    ErrorCode.POLICY_DENIED: "The current policy does not allow this action.",
    ErrorCode.RATE_LIMITED: "Too many requests.",
    ErrorCode.NOT_IMPLEMENTED: "This API contract exists, but the behaviour is not implemented in this slice.",
}


class SafeAPIError(GraphQLError):
    def __init__(self, code: ErrorCode, message: str | None = None):
        self.code = code
        super().__init__(message or SAFE_MESSAGES[code], extensions={"code": code.value})


def safe_graphql_error(error: GraphQLError) -> dict:
    code_value = (getattr(error, "extensions", None) or {}).get("code")
    try:
        code = ErrorCode(code_value)
    except ValueError:
        code = ErrorCode.VALIDATION_FAILED

    return {
        "message": SAFE_MESSAGES[code],
        "extensions": {"code": code.value},
    }


def safe_error_payload(code: ErrorCode) -> dict:
    return {
        "errors": [
            {
                "message": SAFE_MESSAGES[code],
                "extensions": {"code": code.value},
            }
        ]
    }
