import hashlib
import hmac

from app.integrations.github.security import verify_signature

SECRET = "correct-horse-battery-staple"
PAYLOAD = b'{"action": "completed"}'


def sign(payload: bytes, secret: str) -> str:
    """
    Generate a GitHub-compatible HMAC SHA-256 signature.
    """

    digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def test_valid_signature_is_accepted() -> None:
    assert verify_signature(PAYLOAD, SECRET, sign(PAYLOAD, SECRET)) is True


def test_signature_from_a_different_secret_is_rejected() -> None:
    assert verify_signature(PAYLOAD, SECRET, sign(PAYLOAD, "other-secret")) is False


def test_missing_signature_is_rejected() -> None:
    assert verify_signature(PAYLOAD, SECRET, None) is False


def test_signature_without_the_sha256_prefix_is_rejected() -> None:
    assert verify_signature(PAYLOAD, SECRET, sign(PAYLOAD, SECRET)[7:]) is False


def test_tampered_payload_is_rejected() -> None:
    signature = sign(PAYLOAD, SECRET)

    assert verify_signature(PAYLOAD + b" ", SECRET, signature) is False


def test_empty_secret_never_validates() -> None:
    """
    An HMAC keyed with an empty string is computable by anyone, so an unset
    secret must never be able to produce a valid signature.
    """

    forged = sign(PAYLOAD, "")

    assert verify_signature(PAYLOAD, "", forged) is False


def test_whitespace_only_secret_never_validates() -> None:
    forged = sign(PAYLOAD, "   ")

    assert verify_signature(PAYLOAD, "   ", forged) is False
