import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from packages.config import (
    AUTH_LOGIN_IP_LIMIT,
    AUTH_LOGIN_USER_LIMIT,
    AUTH_LOGIN_WINDOW_SEC,
    REFRESH_ENABLED,
    REFRESH_TTL_DAYS,
)
from ..auth import create_token, verify_password
from ..deps import get_current_user
from ..rate_limit import check_rate_limit, clear_rate_limit
from ..schemas import LoginRequest, LoginResponse, LogoutRequest, LogoutResponse, RefreshRequest
from ..utils import get_db


router = APIRouter()


def _create_refresh_token() -> str:
    return secrets.token_urlsafe(32)


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request):
    username = (payload.username or "").strip()
    password = payload.password or ""
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing credentials")

    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login:user:{username}", limit=AUTH_LOGIN_USER_LIMIT, window_sec=AUTH_LOGIN_WINDOW_SEC):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")
    if not check_rate_limit(f"login:ip:{client_host}", limit=AUTH_LOGIN_IP_LIMIT, window_sec=AUTH_LOGIN_WINDOW_SEC):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row or not verify_password(password, row[1]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        clear_rate_limit(f"login:user:{username}")
        clear_rate_limit(f"login:ip:{client_host}")
        token = create_token(row[0], username)
        refresh_token = None
        if REFRESH_ENABLED:
            refresh_token = _create_refresh_token()
            expires_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS)).isoformat()
            conn.execute(
                "INSERT INTO refresh_tokens(user_id, token, expires_at) VALUES(?,?,?)",
                (row[0], refresh_token, expires_at),
            )
            conn.commit()
    return {"access_token": token, "token_type": "bearer", "refresh_token": refresh_token}


@router.post("/auth/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest):
    if not REFRESH_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh tokens disabled")
    token = payload.refresh_token
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, expires_at, revoked
            FROM refresh_tokens
            WHERE token=?
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        user_id, expires_at, revoked = row
        if revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        if expires_dt <= now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
        cur.execute("SELECT username FROM users WHERE id=?", (user_id,))
        user_row = cur.fetchone()
        if not user_row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        access_token = create_token(user_id, user_row[0])
        new_refresh = _create_refresh_token()
        new_expires = (now + timedelta(days=REFRESH_TTL_DAYS)).isoformat()
        cur.execute("UPDATE refresh_tokens SET revoked=1 WHERE token=?", (token,))
        cur.execute(
            "INSERT INTO refresh_tokens(user_id, token, expires_at) VALUES(?,?,?)",
            (user_id, new_refresh, new_expires),
        )
        conn.commit()
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": new_refresh}


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(payload: LogoutRequest, current_user=Depends(get_current_user)):
    if not REFRESH_ENABLED:
        return {"status": "ok"}
    with get_db() as conn:
        cur = conn.cursor()
        if payload.refresh_token:
            cur.execute(
                "SELECT user_id FROM refresh_tokens WHERE token=?",
                (payload.refresh_token,),
            )
            row = cur.fetchone()
            if row and row[0] != current_user["id"]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid refresh token")
            cur.execute("UPDATE refresh_tokens SET revoked=1 WHERE token=?", (payload.refresh_token,))
        else:
            cur.execute("UPDATE refresh_tokens SET revoked=1 WHERE user_id=?", (current_user["id"],))
        conn.commit()
    return {"status": "ok"}
