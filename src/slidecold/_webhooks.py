import hashlib
import hmac
from typing import Union


def verify_webhook_signature(raw_body: Union[bytes, str], signature: str, secret: str) -> bool:
    """Check the `X-SlideCold-Signature` header: hex HMAC-SHA256 of the raw request body keyed by the
    endpoint secret (`whsec_...`). Pass the body exactly as received, before any JSON parsing."""
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature or "").strip().lower())
