"""
RBAC (Role-Based Access Control) utilities.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError
from app.core.security import verify_token
from app.core.exceptions import UnauthorizedException
from app.db.database import get_db
from app.models.user import User
from app.core.logging_config import logger
from typing import List


def get_current_user(
    token: str = Depends(lambda: None),  # Will be overridden
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    This is meant to be called after extracting the token from headers.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        
        return user
    except (JWTError, UnauthorizedException) as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(required_roles: List[str]):
    """
    Dependency factory to create role-based access control.
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(["admin"]))])
        async def admin_endpoint(current_user: User = Depends(get_current_user)):
            ...
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        user_roles = [role.name for role in current_user.roles]
        
        if not any(role in user_roles for role in required_roles):
            logger.warning(
                f"Access denied for user {current_user.username}: required roles {required_roles}, has {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(required_roles)}",
            )
        
        return current_user
    
    return check_role
