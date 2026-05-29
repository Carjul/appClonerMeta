from __future__ import annotations

import hashlib
import hmac
import secrets

_PASSWORD_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 260_000


def make_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS)
    return f"{_PASSWORD_PREFIX}${_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        prefix, iterations, salt, digest = (stored_hash or "").split("$", 3)
        if prefix != _PASSWORD_PREFIX:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False
