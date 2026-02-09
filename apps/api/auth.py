import base64
import hashlib
import hmac
import os
from typing import Optional
from datetime import datetime, timedelta, timezone

from packages.config import JWT_ALG, JWT_EXP_MINUTES, JWT_SECRET, PW_MIN_LEN, PW_REQUIRE_CLASSES


def hash_password(password: str, salt: Optional[str] = None) -> str:
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


def validate_password(password: str, username: Optional[str] = None) -> None:
    errors = []
    if len(password) < PW_MIN_LEN:
        errors.append(f"Password must be at least {PW_MIN_LEN} characters.")
    classes = 0
    if any(c.islower() for c in password):
        classes += 1
    if any(c.isupper() for c in password):
        classes += 1
    if any(c.isdigit() for c in password):
        classes += 1
    if any(not c.isalnum() for c in password):
        classes += 1
    if classes < PW_REQUIRE_CLASSES:
        errors.append("Password must include at least two character classes (lower/upper/digit/symbol).")
    if username and username.lower() in password.lower():
        errors.append("Password must not contain the username.")
    if errors:
        raise ValueError(" ".join(errors))


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
