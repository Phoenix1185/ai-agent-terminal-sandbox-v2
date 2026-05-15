"""Security utilities with multi-machine API key support"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Header, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.services.api_key_manager import api_key_manager

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_api_key(api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    Verify API key against volume-stored keys.
    Works consistently across all Fly.io machines.
    """
    # First check environment variable (Fly.io secret)
    if api_key == settings.API_KEY:
        return api_key

    # Then check volume-stored keys
    if api_key_manager.verify_key(api_key):
        return api_key

    raise HTTPException(status_code=403, detail="Invalid API key")


def verify_api_key_ws(api_key: str) -> bool:
    """Verify API key for WebSocket connections"""
    if api_key == settings.API_KEY:
        return True
    return api_key_manager.verify_key(api_key)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_api_key(name: str = "Generated Key", permissions: list = None, expires_days: int = None) -> str:
    """Generate a new API key stored on the volume"""
    return api_key_manager.generate_key(
        name=name,
        permissions=permissions or ["*"],
        expires_days=expires_days
    )


def hash_password(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)
