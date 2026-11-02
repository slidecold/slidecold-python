from typing import Any, Optional

KEYS_URL = "https://slidecold.com/settings"


class SlideColdError(Exception):
    """Base error. `status` is the HTTP status (None for connection errors), `body` the parsed response."""

    def __init__(self, status: Optional[int], message: str, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.body = body

    def __str__(self) -> str:
        return f"{self.message} (HTTP {self.status})" if self.status else self.message


class APIConnectionError(SlideColdError):
    """The request never got a response (DNS, refused connection, timeout)."""


class APIError(SlideColdError):
    """The API returned an error status. Specific statuses use the subclasses below."""


class AuthenticationError(APIError):
    """401: the API key is missing or invalid."""

    def __init__(self, status: Optional[int], message: str, body: Any = None) -> None:
        super().__init__(status, f"{message}. Create an API key at {KEYS_URL}", body)


class PermissionDeniedError(APIError):
    """403: the key is missing a scope (e.g. `campaigns:write`) or a plan limit was hit."""


class NotFoundError(APIError):
    """404."""


class RateLimitError(APIError):
    """429."""


def error_for_status(status: int, message: str, body: Any) -> APIError:
    cls = {401: AuthenticationError, 403: PermissionDeniedError, 404: NotFoundError, 429: RateLimitError}
    return cls.get(status, APIError)(status, message, body)
