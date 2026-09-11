"""
JWT and authentication utilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from app.core.exceptions import UnauthorizedException

TOKEN_REVOCATION_STORE: set[str] = set()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def revoke_token(token: str) -> None:
    """Add a token to the in-memory revocation set for this runtime."""
    TOKEN_REVOCATION_STORE.add(token)


def is_token_revoked(token: str) -> bool:
    """Return whether the token has been revoked in this runtime."""
    return token in TOKEN_REVOCATION_STORE


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    try:
        if is_token_revoked(token):
            raise UnauthorizedException("Token has been revoked")
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise UnauthorizedException(f"Invalid token: {str(e)}")


def get_token_expiry_seconds(token_type: str = "access") -> int:
    """Get token expiry time in seconds."""
    if token_type == "refresh":
        return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
