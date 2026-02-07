from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.config import AUTH_DISABLED
from .auth import decode_token, hash_password
from .utils import get_db


auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if AUTH_DISABLED:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, username FROM users ORDER BY id LIMIT 1")
            row = cur.fetchone()
            if row:
                return {"id": row[0], "username": row[1]}
            # Auto-create a dev user if none exist, and backfill user_id for existing rows.
            dev_hash = hash_password("dev")
            cur.execute(
                "INSERT INTO users(username, password_hash) VALUES(?, ?)",
                ("dev", dev_hash),
            )
            user_id = cur.lastrowid
            for table in ("activities_raw", "streams_raw", "weather_raw", "activities", "activities_calc"):
                cur.execute(f"UPDATE {table} SET user_id=? WHERE user_id IS NULL", (user_id,))
            conn.commit()
            return {"id": user_id, "username": "dev"}
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    username = payload.get("username")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return {"id": int(user_id), "username": username}
