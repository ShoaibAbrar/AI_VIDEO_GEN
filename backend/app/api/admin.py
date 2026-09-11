"""Admin endpoints for user management and RBAC."""


from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.user import Role, User
from app.schemas.auth import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    PasswordResetRequest,
    UserRead,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from app.services.auth import ensure_default_roles
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


def ensure_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has admin privileges."""
    if not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


@router.get("/users", response_model=List[UserRead])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """List all users."""
    return db.query(User).all()


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """Get a specific user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """Create a new user as an admin."""
    ensure_default_roles(db)

    existing_user = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with that username or email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        hashed_password=hash_password(payload.password),
        is_active=payload.is_active,
    )

    default_role = db.query(Role).filter(Role.name == "user").first()
    if default_role is None:
        default_role = ensure_default_roles(db)["user"]
    user.roles.append(default_role)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """Update a user profile."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.username is not None:
        if db.query(User).filter(User.username == payload.username, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = payload.username

    if payload.email is not None:
        if db.query(User).filter(User.email == payload.email, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = payload.email

    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/status", response_model=UserRead)
async def update_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """Enable or disable a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/password", response_model=UserRead)
async def reset_user_password(
    user_id: int,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """Reset a user's password as an admin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/roles", response_model=UserRead)
async def update_user_roles(
    user_id: int,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(ensure_admin),
):
    """Update the roles assigned to a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ensure_default_roles(db)

    roles = []
    for role_name in payload.roles:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{role_name}' does not exist",
            )
        roles.append(role)

    user.roles = roles
    db.commit()
    db.refresh(user)
    return user
