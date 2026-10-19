import hashlib
import hmac


def verify_signature(
    payload: bytes,
    secret: str,
    signature_header: str | None,
) -> bool:
    """
    Verify a GitHub webhook using HMAC-SHA256.

    The payload must be the exact raw request body received from GitHub.

    Verification fails closed: an unset secret can never produce a valid
    signature, because an HMAC keyed with an empty string is trivially
    computable by anyone.
    """

    if not secret or not secret.strip():
        return False

    if not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        expected_signature,
        signature_header,
    )
