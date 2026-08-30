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
    # The submitted password does not meet the password policy — and NOTHING ELSE about the
    # request was wrong. Deliberately distinct from VALIDATION_FAILED, and the ONLY sanctioned
    # split of it (FR-551, DEC-012).
    #
    # This is not a hole in the anti-enumeration posture (CON-P6 / FR-529), because of WHERE it
    # is raised: `confirm_password_reset` returns it only AFTER the reset token has been looked
    # up and found live. A caller who does not hold a valid token never reaches the password
    # check at all and still sees the single collapsed VALIDATION_FAILED, exactly as before, so
    # unknown / consumed / expired / wrong-purpose stay mutually indistinguishable. The only
    # caller who can observe this code has already proved possession of a working link, and is
    # told the one thing they need — their password is too short — instead of "your link is
    # broken", which sends them round the loop FR-551 exists to end.
    #
    # It carries no policy detail (length, which rule failed): the client mirrors the rule
    # itself (`marketing/src/lib/auth/passwordPolicy.ts`) and renders its own copy.
    PASSWORD_INVALID = "PASSWORD_INVALID"
    # Server-side misconfiguration or failure. Distinct from NOT_IMPLEMENTED, which
    # says "by design"; INTERNAL says "this should work and does not".
    INTERNAL = "INTERNAL"


SAFE_MESSAGES = {
    ErrorCode.UNAUTHENTICATED: "Authentication is required.",
    ErrorCode.PERMISSION_DENIED: "You do not have permission to perform this action.",
    ErrorCode.VALIDATION_FAILED: "The request is invalid.",
    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.CONFLICT: "The request conflicts with the current resource state.",
    ErrorCode.POLICY_DENIED: "The current policy does not allow this action.",
    ErrorCode.RATE_LIMITED: "Too many requests.",
    ErrorCode.NOT_IMPLEMENTED: "This API contract exists, but the behaviour is not implemented in this slice.",
    # Names the password as the problem without restating the policy.
    ErrorCode.PASSWORD_INVALID: "The new password does not meet the password policy.",
    # Deliberately says nothing about what failed — a misconfiguration must not describe
    # itself to a caller.
    ErrorCode.INTERNAL: "The request could not be completed.",
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
