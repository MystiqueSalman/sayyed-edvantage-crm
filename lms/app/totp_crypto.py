"""TOTP MFA secrets encrypted at rest (Fernet, key derived from SECRET_KEY).

Security hardening follow-up to Phase 13: authenticator-app (TOTP) secrets
must never sit in the database in plaintext. Every secret is encrypted with
Fernet before it is written and decrypted transparently on read. The Fernet
key is derived from the ``SECRET_KEY`` environment variable via PBKDF2-HMAC
(SHA-256, 600k iterations, domain-separated salt) — no extra key to manage,
but rotating ``SECRET_KEY`` requires re-encrypting (run the
``backfill-totp-secrets`` CLI command after a rotation with the old key...
in practice: rotate by decrypting with the old key and re-encrypting with
the new one before switching the env var).

Fail-closed: if ``SECRET_KEY`` is missing/empty, ``require_totp_encryption()``
raises ``MissingTotpKeyError``. ``create_app()`` calls it first, so the app
refuses to boot rather than silently storing plaintext.

Backfill: ``backfill_totp_secrets()`` encrypts any legacy plaintext secrets
in place (detected by failed Fernet decrypt + base32 shape check). It is
idempotent and runs automatically at startup (guarded) plus via the
``flask backfill-totp-secrets`` CLI command.
"""

import base64
import os
import re

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENV_VAR = "SECRET_KEY"
# Domain-separation salt for the KDF. Fixed per deployment line; changing it
# invalidates all previously encrypted secrets (re-encrypt first).
_KDF_SALT = b"sayyed-edvantage-totp-v1"
_KDF_ITERATIONS = 600_000

# Legacy plaintext pyotp secrets are base32 (A-Z2-7). Used only to recognise
# pre-encryption rows during backfill / graceful reads.
_BASE32_RE = re.compile(r"^[A-Z2-7]{16,64}$")

# Cache Fernet instances per SECRET_KEY value (cheap, avoids re-deriving).
_FERNET_CACHE = {}


class MissingTotpKeyError(RuntimeError):
    """Raised when SECRET_KEY is unavailable — fail closed, never plaintext."""


def _missing_key_error() -> MissingTotpKeyError:
    return MissingTotpKeyError(
        "SECRET_KEY environment variable is not set (or is empty). "
        "TOTP MFA secrets cannot be encrypted at rest without it, so the "
        "application refuses to start rather than store secrets in "
        "plaintext. Set SECRET_KEY to a long random string (see .env.example) "
        "and restart."
    )


def _derive_fernet_key(secret: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


def get_fernet() -> Fernet:
    """Return the Fernet instance for the current SECRET_KEY (fail closed)."""
    secret = os.environ.get(ENV_VAR, "")
    if not secret or not secret.strip():
        raise _missing_key_error()
    secret = secret.strip()
    fernet = _FERNET_CACHE.get(secret)
    if fernet is None:
        fernet = Fernet(_derive_fernet_key(secret))
        _FERNET_CACHE[secret] = fernet
    return fernet


def require_totp_encryption() -> None:
    """Fail closed at startup if TOTP secret encryption is unavailable.

    Called as the first step of ``create_app()``: a missing SECRET_KEY is a
    hard startup error, never a silent fallback to plaintext storage.
    """
    get_fernet()


def encrypt_totp_secret(plaintext: str) -> str:
    """Encrypt a TOTP secret for storage. Raises if no SECRET_KEY (no plaintext)."""
    if not plaintext:
        raise ValueError("cannot encrypt an empty TOTP secret")
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def is_encrypted(value) -> bool:
    """True if ``value`` decrypts with the current key (i.e. already encrypted)."""
    if not value:
        return False
    try:
        get_fernet().decrypt(str(value).encode("utf-8"))
        return True
    except InvalidToken:
        return False
    except Exception:
        return False


def decrypt_totp_secret(value: str) -> str:
    """Decrypt a stored TOTP secret.

    Legacy plaintext (base32) rows pass through unchanged so the backfill
    path can detect and re-encrypt them, and logins keep working during
    rollout. Anything that is neither valid ciphertext nor a legacy-shaped
    plaintext raises (tamper/corruption -> fail closed, never guess).
    """
    if not value:
        raise ValueError("no TOTP secret stored")
    try:
        return get_fernet().decrypt(str(value).encode("utf-8")).decode("utf-8")
    except InvalidToken:
        if _BASE32_RE.match(str(value).strip()):
            return str(value).strip()  # legacy plaintext — re-encrypt ASAP
        raise RuntimeError(
            "TOTP secret failed to decrypt and is not a legacy plaintext "
            "value — refusing to use it."
        )


def backfill_totp_secrets() -> int:
    """Encrypt any plaintext TOTP secrets in place. Returns rows encrypted.

    Idempotent: already-encrypted rows are skipped. Detection = Fernet
    decrypt fails AND the value has the legacy base32 shape.
    """
    from app import db  # noqa: E402  (avoid circular import at module load)
    from app.models13_auth import UserSecurity13  # noqa: E402

    count = 0
    rows = UserSecurity13.query.filter(
        UserSecurity13.totp_secret.isnot(None)).all()
    for row in rows:
        stored = row.totp_secret or ""
        if not stored or is_encrypted(stored):
            continue
        if not _BASE32_RE.match(stored.strip()):
            # Not ciphertext, not legacy plaintext -> leave alone, never guess.
            continue
        row.totp_secret = encrypt_totp_secret(stored.strip())
        count += 1
    if count:
        db.session.commit()
    return count
