import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from server.db import get_connection

SESSION_TTL_DAYS = 30
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return digest.hex(), salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    computed, _ = hash_password(password, salt)
    return hmac.compare_digest(computed, expected_hash)


def create_user(conn, email: str, name: str, password: str, phone_number: str = ""):
    password_hash, salt = hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, password_salt, phone_number) VALUES (?, ?, ?, ?, ?)",
        (email.strip().lower(), name.strip(), password_hash, salt, phone_number.strip()),
    )
    conn.commit()
    return cur.lastrowid


def authenticate(conn, email: str, password: str):
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_salt"], row["password_hash"]):
        return None
    return row


def create_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    conn.commit()
    return token


def destroy_session(conn, token: str):
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def get_user_by_session(conn, token: str):
    if not token:
        return None
    row = conn.execute(
        "SELECT sessions.user_id, sessions.expires_at, users.* "
        "FROM sessions JOIN users ON users.id = sessions.user_id "
        "WHERE sessions.token = ?",
        (token,),
    ).fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        destroy_session(conn, token)
        return None
    return row
