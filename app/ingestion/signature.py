"""Meta webhook signature checks (WhatsApp Cloud API and Messenger/Instagram)."""

import hashlib
import hmac


def meta_body_signature(body: bytes, app_secret: str) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def signatures_match(body: bytes, header: str | None, app_secret: str) -> bool:
    """True when ``X-Hub-Signature-256`` is the HMAC-SHA256 of the raw body."""
    if not app_secret or not header:
        return False
    provided = header.strip()
    expected = meta_body_signature(body, app_secret)
    if len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)


def verify_tokens_match(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    provided_bytes = provided.encode("utf-8")
    expected_bytes = expected.encode("utf-8")
    if len(provided_bytes) != len(expected_bytes):
        return False
    return hmac.compare_digest(provided_bytes, expected_bytes)
