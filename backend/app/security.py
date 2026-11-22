import hashlib
import hmac
import secrets


def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)


def hash_admin_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_admin_token(token: str | None, token_hash: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(hash_admin_token(token), token_hash)
