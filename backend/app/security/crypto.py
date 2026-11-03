"""Cryptographic primitives: Argon2, SHA-256 token/CSRF hashes, HMAC CSRF, and AES-GCM QR encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.errors import AppError

_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_PASSWORD_HASH = _ph.hash("taporder-dummy-constant-time-password-placeholder")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_password(password: str) -> None:
    """Constant-time dummy Argon2 check when username does not exist."""
    verify_password(password, DUMMY_PASSWORD_HASH)


def generate_opaque_token() -> str:
    """Generate 256-bit (32-byte) URL-safe base64 token of length 43 without '=' padding."""
    raw = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def sha256_bytes(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def derive_csrf_token(raw_cookie_token: str, kind: str, principal_ref: str, secret: str) -> str:
    """Deterministically derive principal-bound CSRF token so reloads do not invalidate other tabs."""
    msg = f"taporder-csrf-v1:{kind}:{principal_ref}:{raw_cookie_token}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_csrf_token(provided_csrf: str | None, expected_csrf_hash: bytes) -> None:
    if not provided_csrf or not isinstance(provided_csrf, str):
        raise AppError(
            status_code=403,
            code="CSRF_INVALID",
            message="Thiếu hoặc sai mã bảo vệ CSRF.",
            details={},
        )
    provided_hash = sha256_bytes(provided_csrf)
    if not hmac.compare_digest(provided_hash, expected_csrf_hash):
        raise AppError(
            status_code=403,
            code="CSRF_INVALID",
            message="Thiếu hoặc sai mã bảo vệ CSRF.",
            details={},
        )


def _parse_key_spec(spec: str) -> tuple[str, bytes]:
    if ":" not in spec:
        raise ValueError("QR encryption key spec must have format '<key_id>:<base64url_32_byte_key>'")
    key_id, b64_part = spec.split(":", 1)
    key_id = key_id.strip()
    b64_part = b64_part.strip()
    padding = "=" * ((4 - len(b64_part) % 4) % 4)
    try:
        # Support both urlsafe and standard base64
        raw_key = base64.urlsafe_b64decode(b64_part + padding)
    except Exception as exc:
        raise ValueError("Invalid base64 key in QR_ENCRYPTION_KEY") from exc
    if not key_id or len(raw_key) != 32:
        raise ValueError("AES-256-GCM key must decode to exactly 32 bytes")
    return key_id, raw_key


def parse_qr_keyring(primary_spec: str, backup_specs: str = "") -> tuple[str, dict[str, bytes]]:
    try:
        primary_id, primary_key = _parse_key_spec(primary_spec)
        ring: dict[str, bytes] = {primary_id: primary_key}
        if backup_specs.strip():
            for item in backup_specs.split(","):
                if item.strip():
                    kid, kbytes = _parse_key_spec(item.strip())
                    ring[kid] = kbytes
        return primary_id, ring
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Cấu hình khóa mã hóa QR không hợp lệ hoặc bị thiếu.",
            details={},
        ) from exc


def encrypt_qr_token(raw_token: str, primary_spec: str) -> str:
    key_id, ring = parse_qr_keyring(primary_spec)
    aesgcm = AESGCM(ring[key_id])
    nonce = secrets.token_bytes(12)
    aad = f"taporder-qr-v1:{key_id}".encode("utf-8")
    ct = aesgcm.encrypt(nonce, raw_token.encode("utf-8"), aad)
    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii").rstrip("=")
    ct_b64 = base64.urlsafe_b64encode(ct).decode("ascii").rstrip("=")
    return f"{key_id}:{nonce_b64}:{ct_b64}"


def decrypt_qr_token(ciphertext: str, primary_spec: str, backup_specs: str = "") -> str:
    _, ring = parse_qr_keyring(primary_spec, backup_specs)
    parts = ciphertext.split(":")
    if len(parts) != 3:
        raise AppError(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Dữ liệu mã hóa QR không hợp lệ.",
            details={},
        )
    key_id, nonce_b64, ct_b64 = parts
    key = ring.get(key_id)
    if key is None:
        raise AppError(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Không tìm thấy khóa giải mã QR phù hợp.",
            details={},
        )
    try:
        nonce_pad = "=" * ((4 - len(nonce_b64) % 4) % 4)
        ct_pad = "=" * ((4 - len(ct_b64) % 4) % 4)
        nonce = base64.urlsafe_b64decode(nonce_b64 + nonce_pad)
        ct = base64.urlsafe_b64decode(ct_b64 + ct_pad)
        aad = f"taporder-qr-v1:{key_id}".encode("utf-8")
        plaintext = AESGCM(key).decrypt(nonce, ct, aad)
        return plaintext.decode("utf-8")
    except (InvalidTag, ValueError, Exception) as exc:
        raise AppError(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Giải mã token QR thất bại.",
            details={},
        ) from exc


def compute_idempotency_hash(operation: str, payload: dict[str, Any]) -> bytes:
    """Compute canonical SHA-256 payload digest for idempotency checking."""
    envelope = {
        "schema_version": "CONTRACT-1",
        "operation": operation,
        "payload": payload,
    }
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).digest()

