"""Official Python SDK for the SlideCold API."""

from ._client import AsyncSlideCold, SlideCold
from ._config import DEFAULT_BASE_URL
from ._exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    SlideColdError,
)
from ._operations import OPERATIONS
from ._version import __version__
from ._webhooks import verify_webhook_signature

__all__ = [
    "SlideCold",
    "AsyncSlideCold",
    "SlideColdError",
    "APIError",
    "APIConnectionError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitError",
    "verify_webhook_signature",
    "OPERATIONS",
    "DEFAULT_BASE_URL",
    "__version__",
]
