import hashlib
import hmac
import secrets
import sqlite3
import time
import uuid
from typing import Optional

from fastapi import Cookie, HTTPException, status

from agent.config import get_config
from agent.database import get_db


AUTH_COOKIE_NAME = "auth_session"

# 游客用户名冲突时的重试次数
GUEST_USERNAME_MAX_RETRY = 5


def _password_hash(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def _user_dict(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "avatar": row["avatar"],
        "role": row["role"],
        "status": row["status"],
        "last_login_time": row["last_login_time"],
        "last_login_ip": row["last_login_ip"],
        "created_time": row["created_time"],
        "updated_time": row["updated_time"],
    }


def create_auth_cookie(user_id: str) -> str:
    signature = hmac.new(
        get_config().auth_cookie_secret.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{user_id}.{signature}"


def verify_auth_cookie(value: str) -> Optional[str]:
    try:
        user_id, signature = value.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(
        get_config().auth_cookie_secret.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return user_id


def get_current_user(auth_session: Optional[str] = Cookie(default=None)) -> dict:
    if not auth_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    user_id = verify_auth_cookie(auth_session)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效")
    row = get_db().execute(
        "SELECT * FROM users WHERE id = ? AND status = 'active'",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效")
    return _user_dict(row)


class AuthService:
    def register(
        self,
        username: str,
        password: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> dict:
        db = get_db()
        if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise ValueError("用户名已存在")

        user_id = str(uuid.uuid4())
        settings_id = str(uuid.uuid4())
        salt = uuid.uuid4().hex
        now = int(time.time())
        try:
            db.execute(
                "INSERT INTO users (id, username, password_hash, salt, avatar, display_name, email, role, status, last_login_time, last_login_ip, created_time, updated_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'user', 'active', NULL, NULL, ?, ?)",
                (
                    user_id,
                    username,
                    _password_hash(password, salt),
                    salt,
                    avatar,
                    display_name,
                    email,
                    now,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO user_settings (id, user_id, theme, locale, created_time, updated_time) VALUES (?, ?, NULL, NULL, ?, ?)",
                (settings_id, user_id, now, now),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise ValueError("用户名已存在") from exc
        except Exception:
            db.rollback()
            raise
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_dict(row)

    def login(self, username: str, password: str, client_ip: Optional[str]) -> dict:
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row or not hmac.compare_digest(
            row["password_hash"] or "", _password_hash(password, row["salt"] or "")
        ):
            raise PermissionError("用户名或密码错误")
        if row["status"] == "disabled":
            raise PermissionError("账号已禁用")
        if row["status"] != "active":
            raise PermissionError("账号不可用")

        now = int(time.time())
        db.execute(
            "UPDATE users SET last_login_time = ?, last_login_ip = ?, updated_time = ? WHERE id = ?",
            (now, client_ip, now, row["id"]),
        )
        db.commit()
        updated = db.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
        return _user_dict(updated)

    def create_guest(self, client_ip: Optional[str] = None) -> dict:
        """创建游客账号：随机用户名 + 占位密码（不对外返回），role='guest'"""
        db = get_db()
        username = self._generate_guest_username(db)

        user_id = str(uuid.uuid4())
        settings_id = str(uuid.uuid4())
        salt = uuid.uuid4().hex
        # 密码仅为满足表结构的占位符，游客不可用它登录，保留账号的唯一途径是转正
        placeholder_password = secrets.token_urlsafe(16)
        now = int(time.time())
        try:
            db.execute(
                "INSERT INTO users (id, username, password_hash, salt, avatar, display_name, email, role, status, last_login_time, last_login_ip, created_time, updated_time) "
                "VALUES (?, ?, ?, ?, NULL, NULL, NULL, 'guest', 'active', ?, ?, ?, ?)",
                (
                    user_id,
                    username,
                    _password_hash(placeholder_password, salt),
                    salt,
                    now,
                    client_ip,
                    now,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO user_settings (id, user_id, theme, locale, created_time, updated_time) VALUES (?, ?, NULL, NULL, ?, ?)",
                (settings_id, user_id, now, now),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise ValueError("游客账号创建失败，请重试") from exc
        except Exception:
            db.rollback()
            raise
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_dict(row)

    def upgrade(
        self,
        user_id: str,
        username: str,
        password: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> dict:
        """游客转正：写入真实凭据并将 role 改为 'user'，user_id 保持不变"""
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise PermissionError("登录状态无效")
        if row["role"] != "guest":
            raise ValueError("当前账号无需完善信息")
        if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise ValueError("用户名已存在")

        # 换新 salt 重新哈希，丢弃游客期的占位密码
        salt = uuid.uuid4().hex
        now = int(time.time())
        try:
            db.execute(
                "UPDATE users SET username = ?, password_hash = ?, salt = ?, email = ?, display_name = ?, "
                "role = 'user', updated_time = ? WHERE id = ?",
                (
                    username,
                    _password_hash(password, salt),
                    salt,
                    email,
                    display_name or row["display_name"],
                    now,
                    user_id,
                ),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise ValueError("用户名已存在") from exc
        except Exception:
            db.rollback()
            raise
        updated = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_dict(updated)

    @staticmethod
    def _generate_guest_username(db) -> str:
        """生成 guest_ + 6 位随机字符的用户名，重复则重试"""
        for _ in range(GUEST_USERNAME_MAX_RETRY):
            username = f"guest_{secrets.token_hex(3)}"
            if not db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                return username
        raise ValueError("游客账号创建失败，请重试")


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
