"""Password hashing and opaque token primitives."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2id with library defaults (RFC 9106 "low memory" profile).
_hasher = PasswordHasher()
# Used to equalise timing when the account does not exist.
_DUMMY_HASH = _hasher.hash("sneha-timing-equaliser")

TOKEN_BYTES = 32
PAIRING_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
PAIRING_CODE_LENGTH = 8


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time verification; also runs when the user does not exist."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    """A 256-bit URL-safe bearer token. Only its SHA-256 digest is stored."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_pairing_code() -> str:
    return "".join(secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))


def normalise_pairing_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_pairing_code(code: str, secret: bytes) -> str:
    """Keyed hash: an 8-character code has too little entropy for a plain hash."""
    return hmac.new(secret, normalise_pairing_code(code).encode(), hashlib.sha256).hexdigest()
