"""
Authentication endpoints.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, UserRead, TokenResponse, TokenRefreshRequest, TokenRefreshResponse
from app.services.auth import AuthService, TokenService
from app.core.deps import get_current_user, get_token
from app.core.logging_config import logger
from app.core.security import revoke_token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    
    - **username**: Unique username (3-50 chars)
    - **email**: Valid email address
    - **password**: Strong password (8+ chars)
    - **first_name**: Optional
    - **last_name**: Optional
    """
    try:
        user = AuthService.register_user(db, user_data)
        logger.info(f"User registered: {user.username} (ID: {user.id})")
        return user
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Login with username and password.
    
    Returns access token and refresh token.
    
    - **username**: User's username
    - **password**: User's password
    """
    try:
        user = AuthService.authenticate_user(db, login_data)
        tokens = TokenService.create_tokens(user)
        logger.info(f"User logged in: {user.username}")
        return tokens
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(request: TokenRefreshRequest):
    """
    Refresh an expired access token using a refresh token.
    
    - **refresh_token**: Valid refresh token
    """
    try:
        access_token = TokenService.refresh_access_token(request.refresh_token)
        logger.info("Access token refreshed")
        return TokenRefreshResponse(
            access_token=access_token,
            expires_in=15 * 60  # 15 minutes
        )
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise


@router.post("/logout")
async def logout(
    token: str = Depends(get_token),
    current_user: User = Depends(get_current_user),
):
    """Invalidate the current bearer token for this process."""
    revoke_token(token)
    logger.info(f"User logged out: {current_user.username}")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user profile."""
    return current_user
