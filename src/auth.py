"""
auth.py - JWT Authentication & Authorization for the Campus Knowledge Assistant.

How it works:
1. Users call POST /token with username + password (OAuth2 password flow).
2. Server returns a JWT containing the user's role (student/professor/admin).
3. Protected endpoints extract the role from the JWT via `get_current_user`.
4. The role drives RBAC filtering inside the RAG retriever.

Security notes:
- Passwords are hashed with bcrypt.
- JWTs are signed with HS256 using a secret from .env (JWT_SECRET).
- Token expiry defaults to 60 minutes.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET", "campus-rag-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))

# ── OAuth2 scheme (tells Swagger UI to show a lock icon) ──────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ── Password hashing (bcrypt directly) ─────────────────────────────────
def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Pydantic models ────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str
    role: str


class User(BaseModel):
    username: str
    role: str  # student | professor | admin
    disabled: bool = False


class UserInDB(User):
    hashed_password: str


# ── Demo user database ─────────────────────────────────────────────────
# In production, replace with a real database table.
DEMO_USERS: dict[str, dict] = {
    "alice": {
        "username": "alice",
        "role": "student",
        "disabled": False,
        "hashed_password": hash_password("studentpass"),
    },
    "bob": {
        "username": "bob",
        "role": "professor",
        "disabled": False,
        "hashed_password": hash_password("profpass"),
    },
    "carol": {
        "username": "carol",
        "role": "admin",
        "disabled": False,
        "hashed_password": hash_password("adminpass"),
    },
}


def get_user(username: str) -> Optional[UserInDB]:
    """Look up a user from the demo database."""
    if username in DEMO_USERS:
        return UserInDB(**DEMO_USERS[username])
    return None


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Verify username + password, return user if valid."""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ── JWT helpers ─────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT with an expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    FastAPI dependency: decode the JWT from the Authorization header,
    extract username + role, and return a User object.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user(username)
    if user is None or user.disabled:
        raise credentials_exception
    return user
