import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from packages.config import JWT_ALG, JWT_EXP_MINUTES, JWT_SECRET


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    digest = base64.urlsafe_b64encode(dk).decode("utf-8")
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = hash_password(password, salt)
    return hmac.compare_digest(calc, f"{salt}${digest}")


def create_token(user_id: int, username: str) -> str:
    import jwt

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXP_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    import jwt

    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
