"""
Dependency providers for FastAPI.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.rbac import get_current_user as rbac_get_current_user
from app.db.database import get_db
from app.models.user import User
from app.core.logging_config import logger

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract token from Authorization header."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_current_user(
    token: str = Depends(get_token),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token."""
    return rbac_get_current_user(token=token, db=db)
