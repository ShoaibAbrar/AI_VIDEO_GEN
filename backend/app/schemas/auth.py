"""
Pydantic schemas for authentication and user management.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


class RoleBase(BaseModel):
    """Base role schema."""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)


class RoleRead(RoleBase):
    """Role read schema."""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8, max_length=255)


class UserLogin(BaseModel):
    """User login schema."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserRead(UserBase):
    """User read schema."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    roles: List[RoleRead] = []
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """User update schema."""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenRefreshRequest(BaseModel):
    """Token refresh request schema."""
    refresh_token: str


class UserRoleUpdateRequest(BaseModel):
    """Update a user's roles as an admin."""
    roles: List[str] = Field(default_factory=list)


class AdminUserCreateRequest(UserBase):
    """Admin user creation schema."""
    password: str = Field(..., min_length=8, max_length=255)
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    """Admin user update schema."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class UserStatusUpdateRequest(BaseModel):
    """Toggle user active status."""
    is_active: bool


class PasswordResetRequest(BaseModel):
    """Admin-triggered password reset."""
    password: str = Field(..., min_length=8, max_length=255)


class TokenRefreshResponse(BaseModel):
    """Token refresh response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
